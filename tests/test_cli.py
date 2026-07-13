from __future__ import annotations

from pathlib import Path

import pytest

from gimp_weathered_photo_plugin.batch import BatchResult


def test_cli_requires_existing_filesystem_png_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from gimp_weathered_photo_plugin.__main__ import main

    exit_code = main(
        [
            "--gimp-console",
            str(tmp_path / "gimp-console.exe"),
            "--analyzer-executable",
            str(tmp_path / "python.exe"),
            str(tmp_path / "not-a-png.jpg"),
        ]
    )

    assert exit_code == 2
    assert "existing filesystem-backed PNG" in capsys.readouterr().err


def test_cli_requires_analyzer_for_a_fresh_render(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from gimp_weathered_photo_plugin.__main__ import main

    source = tmp_path / "source.png"
    source.write_bytes(b"png")

    exit_code = main(
        ["--gimp-console", str(tmp_path / "gimp-console.exe"), str(source)]
    )

    assert exit_code == 2
    assert "requires --analyzer-executable" in capsys.readouterr().err


def test_cli_requires_an_existing_replay_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from gimp_weathered_photo_plugin.__main__ import main

    source = tmp_path / "source.png"
    source.write_bytes(b"png")
    record = tmp_path / "missing.recipe.json"

    exit_code = main(
        [
            "--gimp-console",
            str(tmp_path / "gimp-console.exe"),
            "--replay-recipe",
            str(record),
            str(source),
        ]
    )

    assert exit_code == 2
    assert "replay record does not exist" in capsys.readouterr().err


def test_cli_resolves_the_packaged_asset_manifest() -> None:
    from gimp_weathered_photo_plugin.__main__ import resolve_packaged_assets

    assert set(resolve_packaged_assets()) == {
        "dry-rub-neutral-gray",
        "dry-rub-umber",
        "mottled-sepia",
        "water-stain-01",
        "water-stain-02",
        "water-stain-03",
    }


def test_cli_configures_native_batch_renderer_and_analyzer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import gimp_weathered_photo_plugin.__main__ as cli

    source = tmp_path / "source.png"
    source.write_bytes(b"png")
    output_directory = tmp_path / "outputs"
    captured_args: tuple[object, ...] = ()
    captured_kwargs: dict[str, object] = {}

    def fake_process_batch(*args: object, **kwargs: object) -> list[BatchResult]:
        nonlocal captured_args
        captured_args = args
        captured_kwargs.update(kwargs)
        return [
            BatchResult(
                source=source,
                png=output_directory / "source-worn.png",
                xcf=output_directory / "source-worn.xcf",
                recipe_path=output_directory / "source-worn.recipe.json",
            )
        ]

    monkeypatch.setattr(cli, "process_batch", fake_process_batch)
    monkeypatch.setattr(cli, "resolve_packaged_assets", lambda: {"asset": source})

    exit_code = cli.main(
        [
            "--gimp-console",
            str(tmp_path / "gimp-console.exe"),
            "--analyzer-executable",
            str(tmp_path / "python.exe"),
            "--analyzer-version",
            "1.2.3",
            "--output-dir",
            str(output_directory),
            "--overwrite",
            str(source),
        ]
    )

    assert exit_code == 0
    assert captured_args == (
        [source],
        output_directory,
        cli.GimpConsoleBridge(tmp_path / "gimp-console.exe"),
    )
    assert captured_kwargs["assets"] == {"asset": source}
    assert captured_kwargs["recipe_factory"] is cli.plan_treatment
    assert captured_kwargs["overwrite"] is True
    bridge = captured_kwargs["semantic_bridge"]
    assert isinstance(bridge, cli.SemanticAnalysisBridge)
    assert bridge.executable == tmp_path / "python.exe"
    assert bridge.arguments == ("-m", "gimp_weathered_photo_plugin.analyzer")
    provenance = captured_kwargs["analysis_provenance"]
    assert isinstance(provenance, cli.AnalysisProvenance)
    assert provenance.analyzer_version == "1.2.3"
    assert provenance.adapter_configuration == {
        "arguments": "-m gimp_weathered_photo_plugin.analyzer",
        "executable": str(tmp_path / "python.exe"),
    }


def test_cli_replay_skips_analyzer_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import gimp_weathered_photo_plugin.__main__ as cli

    source = tmp_path / "source.png"
    source.write_bytes(b"png")
    record = tmp_path / "source-worn.recipe.json"
    record.write_text("{}", encoding="utf-8")
    captured_kwargs: dict[str, object] = {}

    def fake_process_batch(*args: object, **kwargs: object) -> list[BatchResult]:
        del args
        captured_kwargs.update(kwargs)
        return []

    monkeypatch.setattr(cli, "process_batch", fake_process_batch)
    monkeypatch.setattr(cli, "resolve_packaged_assets", lambda: {"asset": source})

    exit_code = cli.main(
        [
            "--gimp-console",
            str(tmp_path / "gimp-console.exe"),
            "--replay-recipe",
            str(record),
            str(source),
        ]
    )

    assert exit_code == 0
    assert captured_kwargs["replay_record"] == record
    assert captured_kwargs["semantic_bridge"] is None
    assert captured_kwargs["analysis_provenance"] is None


def test_cli_reports_setup_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from gimp_weathered_photo_plugin.__main__ import main

    source = tmp_path / "source.png"
    source.write_bytes(b"png")

    exit_code = main(
        [
            "--gimp-console",
            "relative-gimp-console.exe",
            "--analyzer-executable",
            str(tmp_path / "python.exe"),
            str(source),
        ]
    )

    assert exit_code == 1
    assert "batch setup failed" in capsys.readouterr().err


def test_cli_returns_failure_when_a_batch_job_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import gimp_weathered_photo_plugin.__main__ as cli

    source = tmp_path / "source.png"
    source.write_bytes(b"png")

    monkeypatch.setattr(cli, "resolve_packaged_assets", lambda: {"asset": source})
    monkeypatch.setattr(
        cli,
        "process_batch",
        lambda *_args, **_kwargs: [
            BatchResult(
                source=source,
                png=tmp_path / "output.png",
                xcf=tmp_path / "output.xcf",
                recipe_path=tmp_path / "output.recipe.json",
                error="native renderer failed",
            )
        ],
    )

    exit_code = cli.main(
        [
            "--gimp-console",
            str(tmp_path / "gimp-console.exe"),
            "--analyzer-executable",
            str(tmp_path / "python.exe"),
            str(source),
        ]
    )

    assert exit_code == 1
