import hashlib
import struct
import zlib
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import pytest

from gimp_weathered_photo_plugin.batch import (
    BatchResult,
    SemanticAnalyzer,
    process_batch,
)
from gimp_weathered_photo_plugin.bridge_protocol import (
    AnalysisRequest,
    AnalysisResponse,
    DetectorStatus,
)
from gimp_weathered_photo_plugin.metadata import RenderRecord, load_render_record
from gimp_weathered_photo_plugin.models import Size, TreatmentRecipe
from tests.test_models import make_recipe


def _png(width: int = 10, height: int = 20) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    chunk = b"IHDR" + header
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", len(header))
        + chunk
        + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
    )


def _assets(tmp_path: Path) -> dict[str, Path]:
    root = tmp_path / "assets"
    root.mkdir(parents=True)
    dry_rub = root / "dry-rub-neutral-gray.gbr"
    water_stain = root / "water-stain-01.png"
    dry_rub.write_bytes(b"brush")
    water_stain.write_bytes(b"water")
    return {
        "dry-rub-neutral-gray": dry_rub,
        "water-stain-01": water_stain,
    }


def _recipe() -> TreatmentRecipe:
    return replace(make_recipe(), source_size=Size(width=10, height=20))


def _adapter_configuration() -> dict[str, str]:
    return {
        "advisories.schema_version": "1",
        "model.face-landmarker.sha256": "a" * 64,
        "model.face-landmarker.version": "gcs-generation-1683136941468629",
        "model.hand-landmarker.sha256": "b" * 64,
        "model.hand-landmarker.version": "gcs-generation-1682480005356399",
    }


class FakeRenderer:
    def __init__(self, failing_source: Path | None = None) -> None:
        self.calls: list[Path] = []
        self.source_bytes: list[bytes] = []
        self.failing_source = failing_source

    def render(
        self,
        source: Path,
        png: Path,
        xcf: Path,
        recipe: TreatmentRecipe,
        assets: Mapping[str, Path],
    ) -> None:
        self.calls.append(source)
        self.source_bytes.append(source.read_bytes())
        if source == self.failing_source:
            raise RuntimeError("render failed")
        png.write_bytes(self.source_bytes[-1])
        xcf.write_bytes(b"xcf")


class WritingThenFailRenderer(FakeRenderer):
    def render(
        self,
        source: Path,
        png: Path,
        xcf: Path,
        recipe: TreatmentRecipe,
        assets: Mapping[str, Path],
    ) -> None:
        png.write_bytes(_png())
        raise RuntimeError("render failed")


class FailingFirstRenderer(FakeRenderer):
    def render(
        self,
        source: Path,
        png: Path,
        xcf: Path,
        recipe: TreatmentRecipe,
        assets: Mapping[str, Path],
    ) -> None:
        self.calls.append(source)
        self.source_bytes.append(source.read_bytes())
        if len(self.calls) == 1:
            raise RuntimeError("render failed")
        png.write_bytes(self.source_bytes[-1])
        xcf.write_bytes(b"xcf")


class WrongDimensionRenderer(FakeRenderer):
    def render(
        self,
        source: Path,
        png: Path,
        xcf: Path,
        recipe: TreatmentRecipe,
        assets: Mapping[str, Path],
    ) -> None:
        png.write_bytes(_png(width=11))
        xcf.write_bytes(b"xcf")


class FakeBridge:
    def __init__(self) -> None:
        self.requests: list[AnalysisRequest] = []

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        self.requests.append(request)
        detectors: dict[str, DetectorStatus] = {
            "face": "no_detection",
            "hand": "no_detection",
            "saliency": "detected",
        }
        return AnalysisResponse(
            bridge_schema_version=2,
            source_sha256=request.source_sha256,
            detectors=detectors,
            adapter_configuration=_adapter_configuration(),
            exclusions=_recipe().exclusions,
        )


class FailingBridge:
    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        raise AssertionError("replay must not invoke the semantic bridge")


class _ExplodingBridge:
    def __init__(self) -> None:
        self.calls = 0

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        del request
        self.calls += 1
        raise AssertionError("replay must not invoke the semantic bridge")


class MutatingBridge(FakeBridge):
    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        response = super().analyze(request)
        request.source_path.write_bytes(_png() + b"changed after analysis")
        return response


def _fresh_result(
    source: Path,
    output_dir: Path,
    renderer: FakeRenderer,
    assets: dict[str, Path],
    bridge: SemanticAnalyzer,
    *,
    overwrite: bool = False,
) -> list[BatchResult]:
    return process_batch(
        [source],
        output_dir,
        renderer,
        assets=assets,
        recipe_factory=lambda size, exclusions, _assets: _recipe(),
        semantic_bridge=bridge,
        analyzer_version="1.2.3",
        overwrite=overwrite,
    )


def test_fresh_batch_stages_analyzes_and_persists_the_complete_render_record(
    tmp_path: Path,
) -> None:
    source = tmp_path / "print.png"
    source.write_bytes(_png())
    renderer = FakeRenderer()
    bridge = FakeBridge()

    results = _fresh_result(
        source, tmp_path / "out", renderer, _assets(tmp_path), bridge
    )

    assert results[0].success is True
    assert renderer.calls[0] != source
    assert renderer.source_bytes[0] == source.read_bytes()
    assert bridge.requests[0].source_path == renderer.calls[0].resolve()
    assert bridge.requests[0].source_size == Size(width=10, height=20)
    record = load_render_record(tmp_path / "out/print-worn.recipe.json")
    assert record.source_size == Size(width=10, height=20)
    assert record.exclusions == _recipe().exclusions
    assert record.detectors["saliency"] == "detected"
    assert record.analyzer_version == "1.2.3"
    assert record.adapter_configuration == _adapter_configuration()
    assert record.asset_sha256 == {
        "dry-rub-neutral-gray": hashlib.sha256(b"brush").hexdigest(),
        "water-stain-01": hashlib.sha256(b"water").hexdigest(),
    }


def test_fresh_record_persists_analyzer_returned_model_provenance(
    tmp_path: Path,
) -> None:
    source = tmp_path / "print.png"
    source.write_bytes(_png())

    results = process_batch(
        [source],
        tmp_path / "out",
        FakeRenderer(),
        assets=_assets(tmp_path),
        recipe_factory=lambda size, exclusions, _assets: _recipe(),
        semantic_bridge=FakeBridge(),
        analyzer_version="0.10.35",
    )

    record = load_render_record(results[0].recipe_path)

    assert record.adapter_configuration["model.face-landmarker.sha256"] == "a" * 64
    assert record.adapter_configuration["advisories.schema_version"] == "1"


def test_fresh_batch_requires_analyzer_version_before_rendering(
    tmp_path: Path,
) -> None:
    source = tmp_path / "print.png"
    source.write_bytes(_png())
    renderer = FakeRenderer()

    results = process_batch(
        [source],
        tmp_path / "out",
        renderer,
        assets=_assets(tmp_path),
        recipe_factory=lambda size, exclusions, _assets: _recipe(),
        semantic_bridge=FakeBridge(),
        analyzer_version="",
    )

    assert results[0].success is False
    assert results[0].error is not None
    assert "fresh rendering analyzer version is required" in results[0].error
    assert renderer.calls == []


def test_replay_loads_a_record_without_calling_the_semantic_bridge(
    tmp_path: Path,
) -> None:
    source = tmp_path / "print.png"
    source.write_bytes(_png())
    assets = _assets(tmp_path)
    recipe_path = tmp_path / "saved.recipe.json"
    from gimp_weathered_photo_plugin.metadata import (
        write_render_record,
    )

    record = RenderRecord(
        recipe=_recipe(),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        source_size=Size(width=10, height=20),
        asset_sha256={
            "dry-rub-neutral-gray": hashlib.sha256(b"brush").hexdigest(),
            "water-stain-01": hashlib.sha256(b"water").hexdigest(),
        },
        bridge_schema_version=1,
        recipe_schema_version=1,
        analyzer_version="1.2.3",
        adapter_configuration={},
        detectors={
            "face": "no_detection",
            "hand": "no_detection",
            "saliency": "detected",
        },
        exclusions=_recipe().exclusions,
    )
    write_render_record(recipe_path, record)

    results = process_batch(
        [source],
        tmp_path / "out",
        FakeRenderer(),
        assets=assets,
        recipe_factory=lambda *_args: (_ for _ in ()).throw(AssertionError("called")),
        replay_record=recipe_path,
        semantic_bridge=FailingBridge(),
    )

    assert results[0].success is True


def test_replay_does_not_construct_or_call_the_semantic_bridge(
    tmp_path: Path,
) -> None:
    source = tmp_path / "print.png"
    source.write_bytes(_png())
    assets = _assets(tmp_path)
    record = RenderRecord(
        recipe=_recipe(),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        source_size=Size(width=10, height=20),
        asset_sha256={
            "dry-rub-neutral-gray": hashlib.sha256(b"brush").hexdigest(),
            "water-stain-01": hashlib.sha256(b"water").hexdigest(),
        },
        bridge_schema_version=1,
        recipe_schema_version=1,
        analyzer_version="1.2.3",
        adapter_configuration={},
        detectors={
            "face": "no_detection",
            "hand": "no_detection",
            "saliency": "detected",
        },
        exclusions=_recipe().exclusions,
    )
    bridge = _ExplodingBridge()

    results = process_batch(
        [source],
        tmp_path / "out",
        FakeRenderer(),
        assets=assets,
        recipe_factory=lambda *_args: (_ for _ in ()).throw(AssertionError("called")),
        semantic_bridge=bridge,
        replay_record=record,
    )

    assert results[0].success
    assert bridge.calls == 0


def test_replay_rejects_recipe_assets_missing_from_persisted_and_current_maps(
    tmp_path: Path,
) -> None:
    source = tmp_path / "print.png"
    source.write_bytes(_png())
    assets = _assets(tmp_path)
    record = RenderRecord(
        recipe=_recipe(),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        source_size=Size(width=10, height=20),
        asset_sha256={"dry-rub-neutral-gray": hashlib.sha256(b"brush").hexdigest()},
        bridge_schema_version=1,
        recipe_schema_version=1,
        analyzer_version="1.2.3",
        adapter_configuration={},
        detectors={
            "face": "no_detection",
            "hand": "no_detection",
            "saliency": "detected",
        },
        exclusions=_recipe().exclusions,
    )
    renderer = FakeRenderer()

    results = process_batch(
        [source],
        tmp_path / "out",
        renderer,
        assets=assets,
        recipe_factory=lambda *_args: (_ for _ in ()).throw(AssertionError("called")),
        replay_record=record,
    )

    assert results[0].success is False
    assert results[0].error is not None
    assert "water-stain-01" in results[0].error
    assert renderer.calls == []


def test_fresh_batch_revalidates_the_staged_source_before_rendering(
    tmp_path: Path,
) -> None:
    source = tmp_path / "print.png"
    source.write_bytes(_png())
    renderer = FakeRenderer()

    results = _fresh_result(
        source, tmp_path / "out", renderer, _assets(tmp_path), MutatingBridge()
    )

    assert results[0].success is False
    assert results[0].error is not None
    assert "fingerprint mismatch" in results[0].error
    assert renderer.calls == []


@pytest.mark.parametrize("mismatch", ["source", "asset"])
def test_replay_rejects_source_and_asset_mismatches_before_rendering(
    tmp_path: Path, mismatch: str
) -> None:
    source = tmp_path / "print.png"
    source.write_bytes(_png())
    assets = _assets(tmp_path)
    record = RenderRecord(
        recipe=_recipe(),
        source_sha256=(
            "a" * 64
            if mismatch == "source"
            else hashlib.sha256(source.read_bytes()).hexdigest()
        ),
        source_size=Size(width=10, height=20),
        asset_sha256={
            "dry-rub-neutral-gray": "b" * 64,
            "water-stain-01": hashlib.sha256(b"water").hexdigest(),
        },
        bridge_schema_version=1,
        recipe_schema_version=1,
        analyzer_version="1.2.3",
        adapter_configuration={},
        detectors={
            "face": "no_detection",
            "hand": "no_detection",
            "saliency": "detected",
        },
        exclusions=_recipe().exclusions,
    )
    if mismatch == "source":
        record = replace(
            record,
            asset_sha256={
                "dry-rub-neutral-gray": hashlib.sha256(b"brush").hexdigest(),
                "water-stain-01": hashlib.sha256(b"water").hexdigest(),
            },
        )
    renderer = FakeRenderer()

    results = process_batch(
        [source],
        tmp_path / "out",
        renderer,
        assets=assets,
        recipe_factory=lambda *_args: (_ for _ in ()).throw(AssertionError("called")),
        replay_record=record,
        semantic_bridge=FailingBridge(),
    )

    assert results[0].success is False
    assert renderer.calls == []
    assert results[0].error is not None
    assert "mismatch" in results[0].error


def test_batch_continues_after_one_failure_and_writes_three_outputs(
    tmp_path: Path,
) -> None:
    failed = tmp_path / "failed.png"
    succeeded = tmp_path / "succeeded.png"
    failed.write_bytes(_png())
    succeeded.write_bytes(_png())
    renderer = FailingFirstRenderer()
    results = process_batch(
        [failed, succeeded],
        tmp_path / "out",
        renderer,
        assets=_assets(tmp_path),
        recipe_factory=lambda size, exclusions, _assets: _recipe(),
        semantic_bridge=FakeBridge(),
        analyzer_version="1.2.3",
    )

    assert [result.success for result in results] == [False, True]
    assert (tmp_path / "out/succeeded-worn.png").is_file()
    assert (tmp_path / "out/succeeded-worn.xcf").is_file()
    assert (tmp_path / "out/succeeded-worn.recipe.json").is_file()


def test_batch_validates_staged_png_dimensions_before_publication(
    tmp_path: Path,
) -> None:
    source = tmp_path / "print.png"
    source.write_bytes(_png())

    result = _fresh_result(
        source,
        tmp_path / "out",
        WrongDimensionRenderer(),
        _assets(tmp_path),
        FakeBridge(),
    )

    assert result[0].success is False
    assert not (tmp_path / "out/print-worn.png").exists()
    assert not (tmp_path / "out/print-worn.xcf").exists()
    assert not (tmp_path / "out/print-worn.recipe.json").exists()


def test_publish_output_set_preserves_existing_outputs_when_a_staged_file_is_missing(
    tmp_path: Path,
) -> None:
    from gimp_weathered_photo_plugin.batch import publish_output_set

    final_png = tmp_path / "print-worn.png"
    final_xcf = tmp_path / "print-worn.xcf"
    final_recipe = tmp_path / "print-worn.recipe.json"
    final_png.write_bytes(b"old-png")
    final_xcf.write_bytes(b"old-xcf")
    final_recipe.write_bytes(b"old-recipe")
    staged_png = tmp_path / "staged.png"
    staged_xcf = tmp_path / "staged.xcf"
    staged_recipe = tmp_path / "staged.recipe.json"
    staged_png.write_bytes(b"new-png")
    staged_xcf.write_bytes(b"new-xcf")

    with pytest.raises(FileNotFoundError, match="staged output is missing"):
        publish_output_set(
            (staged_png, staged_xcf, staged_recipe),
            (final_png, final_xcf, final_recipe),
        )

    assert final_png.read_bytes() == b"old-png"
    assert final_xcf.read_bytes() == b"old-xcf"
    assert final_recipe.read_bytes() == b"old-recipe"


def test_publish_output_set_rolls_back_when_a_final_replacement_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from gimp_weathered_photo_plugin.batch import publish_output_set

    final: tuple[Path, Path, Path] = (
        tmp_path / "print-worn.png",
        tmp_path / "print-worn.xcf",
        tmp_path / "print-worn.recipe.json",
    )
    staged: tuple[Path, Path, Path] = (
        tmp_path / "staged.png",
        tmp_path / "staged.xcf",
        tmp_path / "staged.recipe.json",
    )
    for path, content in zip(
        final, (b"old-png", b"old-xcf", b"old-recipe"), strict=True
    ):
        path.write_bytes(content)
    for path, content in zip(
        staged, (b"new-png", b"new-xcf", b"new-recipe"), strict=True
    ):
        path.write_bytes(content)
    original_replace = Path.replace

    def fail_second_staged_replace(self: Path, target: Path) -> Path:
        if self == staged[1]:
            raise OSError("replacement failed")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_second_staged_replace)

    with pytest.raises(OSError, match="replacement failed"):
        publish_output_set(staged, final)

    assert [path.read_bytes() for path in final] == [
        b"old-png",
        b"old-xcf",
        b"old-recipe",
    ]


def test_publish_output_set_restores_outputs_when_backup_replacement_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from gimp_weathered_photo_plugin.batch import publish_output_set

    final: tuple[Path, Path, Path] = (
        tmp_path / "print-worn.png",
        tmp_path / "print-worn.xcf",
        tmp_path / "print-worn.recipe.json",
    )
    staged: tuple[Path, Path, Path] = (
        tmp_path / "staged.png",
        tmp_path / "staged.xcf",
        tmp_path / "staged.recipe.json",
    )
    for path, content in zip(
        final, (b"old-png", b"old-xcf", b"old-recipe"), strict=True
    ):
        path.write_bytes(content)
    for path, content in zip(
        staged, (b"new-png", b"new-xcf", b"new-recipe"), strict=True
    ):
        path.write_bytes(content)
    original_replace = Path.replace

    def fail_second_backup_replace(self: Path, target: Path) -> Path:
        if self == final[1]:
            raise OSError("backup failed")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_second_backup_replace)

    with pytest.raises(OSError, match="backup failed"):
        publish_output_set(staged, final)

    assert [path.read_bytes() for path in final] == [
        b"old-png",
        b"old-xcf",
        b"old-recipe",
    ]


def test_publish_output_set_retains_backups_when_restore_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from gimp_weathered_photo_plugin.batch import publish_output_set

    final: tuple[Path, Path, Path] = (
        tmp_path / "print-worn.png",
        tmp_path / "print-worn.xcf",
        tmp_path / "print-worn.recipe.json",
    )
    staged: tuple[Path, Path, Path] = (
        tmp_path / "staged.png",
        tmp_path / "staged.xcf",
        tmp_path / "staged.recipe.json",
    )
    for path, content in zip(
        final, (b"old-png", b"old-xcf", b"old-recipe"), strict=True
    ):
        path.write_bytes(content)
    for path, content in zip(
        staged, (b"new-png", b"new-xcf", b"new-recipe"), strict=True
    ):
        path.write_bytes(content)
    original_replace = Path.replace

    def fail_publication_and_restore(self: Path, target: Path) -> Path:
        if self == staged[1]:
            raise OSError("publication failed")
        if self.parent.name.startswith(".vezor-publish-backup-") and target == final[0]:
            raise OSError("restore failed")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_publication_and_restore)

    with pytest.raises(RuntimeError, match="rollback failed"):
        publish_output_set(staged, final)

    backups = list(tmp_path.glob(".vezor-publish-backup-*"))
    assert len(backups) == 1
    assert [(backups[0] / str(index)).read_bytes() for index in range(3)] == [
        b"old-png",
        b"old-xcf",
        b"old-recipe",
    ]


def test_batch_preserves_existing_output_set_when_overwrite_render_fails(
    tmp_path: Path,
) -> None:
    source = tmp_path / "print.png"
    source.write_bytes(_png())
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    final_png = output_dir / "print-worn.png"
    final_xcf = output_dir / "print-worn.xcf"
    final_recipe = output_dir / "print-worn.recipe.json"
    final_png.write_bytes(b"old-png")
    final_xcf.write_bytes(b"old-xcf")
    final_recipe.write_bytes(b"old-recipe")

    result = _fresh_result(
        source,
        output_dir,
        WritingThenFailRenderer(),
        _assets(tmp_path),
        FakeBridge(),
        overwrite=True,
    )

    assert result[0].success is False
    assert final_png.read_bytes() == b"old-png"
    assert final_xcf.read_bytes() == b"old-xcf"
    assert final_recipe.read_bytes() == b"old-recipe"
