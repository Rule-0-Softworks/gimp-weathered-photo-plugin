from __future__ import annotations

import hashlib
import shutil
import struct
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from gimp_weathered_photo_plugin.bridge_protocol import (
    BRIDGE_SCHEMA_VERSION,
    AnalysisRequest,
    AnalysisResponse,
)
from gimp_weathered_photo_plugin.metadata import (
    AnalysisProvenance,
    RenderRecord,
    load_render_record,
    write_render_record,
)
from gimp_weathered_photo_plugin.models import Size, SoftExclusion, TreatmentRecipe
from gimp_weathered_photo_plugin.semantic_bridge import stage_input

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class Renderer(Protocol):
    def render(
        self,
        source: Path,
        png: Path,
        xcf: Path,
        recipe: TreatmentRecipe,
        assets: Mapping[str, Path],
    ) -> None: ...


class SemanticAnalyzer(Protocol):
    def analyze(self, request: AnalysisRequest) -> AnalysisResponse: ...


RecipeFactory = Callable[
    [Size, Sequence[SoftExclusion], Mapping[str, Path]], TreatmentRecipe
]


@dataclass(frozen=True, slots=True)
class BatchResult:
    source: Path
    png: Path
    xcf: Path
    recipe_path: Path
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


def process_batch(
    inputs: Sequence[Path],
    output_dir: Path,
    renderer: Renderer,
    *,
    assets: Mapping[str, Path],
    recipe_factory: RecipeFactory,
    semantic_bridge: SemanticAnalyzer | None = None,
    analysis_provenance: AnalysisProvenance | None = None,
    replay_recipe: TreatmentRecipe | None = None,
    replay_record: RenderRecord | Path | None = None,
    overwrite: bool = False,
) -> list[BatchResult]:
    if replay_recipe is not None:
        raise ValueError("replay requires a complete render record")
    if replay_record is not None and semantic_bridge is not None:
        # A replay caller may provide a bridge object, but its availability must
        # not influence replay behavior.
        semantic_bridge = None
    record = _load_replay_record(replay_record)
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[BatchResult] = []
    for source in inputs:
        png, xcf, recipe_path = _output_paths(source, output_dir)
        if not overwrite and any(path.exists() for path in (png, xcf, recipe_path)):
            results.append(
                BatchResult(
                    source,
                    png,
                    xcf,
                    recipe_path,
                    "output already exists; use overwrite",
                )
            )
            continue
        try:
            staged = stage_input(source, output_dir / ".vezor-staging")
            job_directory = staged.path.parent
            try:
                size = read_png_dimensions(staged.path)
                fingerprints = _asset_fingerprints(assets)
                if record is None:
                    render_record = _prepare_fresh_record(
                        staged.path,
                        staged.sha256,
                        size,
                        assets,
                        fingerprints,
                        recipe_factory,
                        semantic_bridge,
                        analysis_provenance,
                    )
                else:
                    _validate_replay_record(record, staged.sha256, size, fingerprints)
                    render_record = record
                if _sha256(staged.path) != staged.sha256:
                    raise ValueError(
                        "staged source fingerprint mismatch before rendering"
                    )
                staged_png, staged_xcf, staged_recipe = _staged_output_paths(
                    job_directory
                )
                renderer.render(
                    staged.path,
                    staged_png,
                    staged_xcf,
                    render_record.recipe,
                    assets,
                )
                write_render_record(staged_recipe, render_record)
                _validate_staged_output(
                    (staged_png, staged_xcf, staged_recipe), size, render_record
                )
                publish_output_set(
                    (staged_png, staged_xcf, staged_recipe),
                    (png, xcf, recipe_path),
                )
            finally:
                shutil.rmtree(job_directory, ignore_errors=True)
            results.append(BatchResult(source, png, xcf, recipe_path))
        except Exception as error:
            results.append(BatchResult(source, png, xcf, recipe_path, str(error)))
    return results


def read_png_dimensions(path: Path) -> Size:
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or not header.startswith(_PNG_SIGNATURE):
        raise ValueError("PNG header is invalid")
    chunk_length = struct.unpack(">I", header[8:12])[0]
    if chunk_length != 13 or header[12:16] != b"IHDR":
        raise ValueError("PNG must begin with an IHDR chunk")
    width, height = struct.unpack(">II", header[16:24])
    return Size(width, height)


def publish_output_set(
    staged: tuple[Path, Path, Path], final: tuple[Path, Path, Path]
) -> None:
    if any(not path.is_file() or path.stat().st_size == 0 for path in staged):
        raise FileNotFoundError("staged output is missing")
    parent = final[0].parent
    if any(path.parent != parent for path in final):
        raise ValueError("final outputs must share a directory")
    backup_directory = parent / f".vezor-publish-backup-{uuid4()}"
    backup_directory.mkdir()
    backups: list[Path | None] = [None, None, None]
    published = [False, False, False]
    cleanup_backup = False
    try:
        for index, final_path in enumerate(final):
            if final_path.exists():
                backup = backup_directory / str(index)
                final_path.replace(backup)
                backups[index] = backup
        for index, (staged_path, final_path) in enumerate(
            zip(staged, final, strict=True)
        ):
            staged_path.replace(final_path)
            published[index] = True
    except Exception:
        try:
            _restore_output_set(final, backups, published)
        except Exception as rollback_error:
            raise RuntimeError("output publication rollback failed") from rollback_error
        cleanup_backup = True
        raise
    else:
        cleanup_backup = True
    finally:
        if cleanup_backup:
            shutil.rmtree(backup_directory, ignore_errors=True)


def _prepare_fresh_record(
    source: Path,
    source_sha256: str,
    size: Size,
    assets: Mapping[str, Path],
    fingerprints: Mapping[str, str],
    recipe_factory: RecipeFactory,
    semantic_bridge: SemanticAnalyzer | None,
    provenance: AnalysisProvenance | None,
) -> RenderRecord:
    if semantic_bridge is None:
        raise ValueError("fresh rendering requires a semantic analysis bridge")
    if provenance is None:
        raise ValueError("fresh rendering analyzer provenance is required")
    response = semantic_bridge.analyze(
        AnalysisRequest(
            bridge_schema_version=BRIDGE_SCHEMA_VERSION,
            source_path=source.resolve(),
            source_sha256=source_sha256,
            source_size=size,
        )
    )
    if response.source_sha256 != source_sha256:
        raise ValueError("semantic analysis source fingerprint mismatch")
    if response.bridge_schema_version != BRIDGE_SCHEMA_VERSION:
        raise ValueError("semantic analysis bridge schema mismatch")
    if (
        "failed" in response.detectors.values()
        or response.detectors["saliency"] != "detected"
    ):
        raise ValueError("semantic analysis detector status is invalid")
    recipe = recipe_factory(size, response.exclusions, assets)
    if recipe.source_size != size:
        raise ValueError("planned recipe dimensions do not match the source image")
    if recipe.exclusions != tuple(response.exclusions):
        raise ValueError("planned recipe exclusions do not match semantic analysis")
    return RenderRecord(
        recipe=recipe,
        source_sha256=source_sha256,
        source_size=size,
        asset_sha256=fingerprints,
        bridge_schema_version=response.bridge_schema_version,
        recipe_schema_version=recipe.schema_version,
        analyzer_version=provenance.analyzer_version,
        adapter_configuration=provenance.adapter_configuration,
        detectors=response.detectors,
        exclusions=tuple(response.exclusions),
    )


def _load_replay_record(record: RenderRecord | Path | None) -> RenderRecord | None:
    if record is None:
        return None
    if isinstance(record, Path):
        return load_render_record(record)
    return record


def _validate_replay_record(
    record: RenderRecord,
    source_sha256: str,
    source_size: Size,
    asset_sha256: Mapping[str, str],
) -> None:
    recipe_assets = {mark.asset_id for mark in record.recipe.marks}
    missing = recipe_assets - set(record.asset_sha256) | recipe_assets - set(
        asset_sha256
    )
    if missing:
        raise ValueError(
            f"replay recipe references unavailable assets: {', '.join(sorted(missing))}"
        )
    if record.source_sha256 != source_sha256:
        raise ValueError("replay source fingerprint mismatch")
    if record.source_size != source_size:
        raise ValueError("replay source dimensions mismatch")
    if dict(record.asset_sha256) != dict(asset_sha256):
        raise ValueError("replay asset fingerprint mismatch")


def _asset_fingerprints(assets: Mapping[str, Path]) -> dict[str, str]:
    return {asset_id: _sha256(path) for asset_id, path in assets.items()}


def _validate_staged_output(
    staged: tuple[Path, Path, Path], size: Size, record: RenderRecord
) -> None:
    png, xcf, recipe = staged
    if not png.is_file() or not xcf.is_file() or not recipe.is_file():
        raise FileNotFoundError("staged output is missing")
    if xcf.stat().st_size == 0:
        raise ValueError("staged XCF is empty")
    if read_png_dimensions(png) != size:
        raise ValueError("staged PNG dimensions do not match the source image")
    if load_render_record(recipe) != record:
        raise ValueError("staged recipe record did not validate")


def _restore_output_set(
    final: tuple[Path, Path, Path],
    backups: Sequence[Path | None],
    published: Sequence[bool],
) -> None:
    for final_path, backup, was_published in zip(
        final, backups, published, strict=True
    ):
        if backup is not None and backup.exists():
            backup.replace(final_path)
        elif was_published:
            final_path.unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _output_paths(source: Path, output_dir: Path) -> tuple[Path, Path, Path]:
    stem = output_dir / f"{source.stem}-worn"
    return (
        stem.with_suffix(".png"),
        stem.with_suffix(".xcf"),
        stem.with_suffix(".recipe.json"),
    )


def _staged_output_paths(directory: Path) -> tuple[Path, Path, Path]:
    return (
        directory / "output.png",
        directory / "output.xcf",
        directory / "output.recipe.json",
    )
