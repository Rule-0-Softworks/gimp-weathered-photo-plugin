import json
import subprocess
import tempfile
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from gimp_weathered_photo_plugin.gimp_console_bridge import (
    GimpConsoleBridge,
    GimpConsoleError,
)
from tests.test_models import make_recipe


@pytest.fixture(autouse=True)
def temporary_configuration_root(tmp_path: Path, monkeypatch) -> None:
    import gimp_weathered_photo_plugin.gimp_console_bridge as bridge_module

    monkeypatch.setattr(bridge_module, "_TEMP_ROOT", tmp_path / "project-temp")


def test_console_bridge_default_temp_root_is_host_portable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gimp_weathered_photo_plugin.gimp_console_bridge as bridge_module

    monkeypatch.undo()

    assert Path(tempfile.gettempdir()) / "gimp-weathered-photo-plugin" == (
        bridge_module._TEMP_ROOT
    )


def _assets(tmp_path: Path) -> dict[str, Path]:
    brush = tmp_path / "dry-rub-neutral-gray.gbr"
    mask = tmp_path / "water-stain-01.png"
    brush.write_bytes(b"brush")
    mask.write_bytes(b"mask")
    return {"dry-rub-neutral-gray": brush, "water-stain-01": mask}


def test_console_bridge_uses_argument_list_and_absolute_request_paths(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source.png"
    png = tmp_path / "result.png"
    xcf = tmp_path / "result.xcf"
    source.write_bytes(b"source")
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        calls.append((command, kwargs))
        request_path = Path(
            next(
                item.split("=", 1)[1] for item in command if item.startswith("--batch=")
            )
            .split("run_console_request(", 1)[1]
            .split(")", 1)[0]
            .strip("'")
        )
        request = json.loads(request_path.read_text(encoding="utf-8"))
        assert Path(request["source"]).is_absolute()
        assert Path(request["png"]).is_absolute()
        assert Path(request["xcf"]).is_absolute()
        assert all(Path(path).is_absolute() for path in request["assets"].values())
        png.write_bytes(b"png")
        xcf.write_bytes(b"xcf")
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("subprocess.run", fake_run)
    executable = tmp_path / "gimp-console"
    bridge = GimpConsoleBridge(executable)

    bridge.render(source, png, xcf, make_recipe(), _assets(tmp_path))

    assert calls[0][0][0] == str(executable)
    assert calls[0][1]["shell"] is False


def test_console_bridge_cleans_a_per_run_configuration_under_project_temp(
    tmp_path: Path, monkeypatch
) -> None:
    import gimp_weathered_photo_plugin.gimp_console_bridge as bridge_module

    source = tmp_path / "source.png"
    png = tmp_path / "result.png"
    xcf = tmp_path / "result.xcf"
    source.write_bytes(b"source")
    root = tmp_path / "project-temp"
    captured: list[Path] = []

    def fake_run(command: list[str], **_: object) -> CompletedProcess[str]:
        configuration = Path(
            next(
                item.split("=", 1)[1]
                for item in command
                if item.startswith("--gimprc=")
            )
        ).parent
        captured.append(configuration)
        png.write_bytes(b"png")
        xcf.write_bytes(b"xcf")
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(bridge_module, "_TEMP_ROOT", root)
    monkeypatch.setattr("subprocess.run", fake_run)

    GimpConsoleBridge(tmp_path / "gimp-console").render(
        source, png, xcf, make_recipe(), _assets(tmp_path)
    )

    assert captured[0].parent == root
    assert not captured[0].exists()


@pytest.mark.parametrize("failure", ["nonzero", "timeout"])
def test_console_bridge_cleans_temporary_configuration_after_a_failed_job(
    tmp_path: Path, monkeypatch, failure: str
) -> None:
    import gimp_weathered_photo_plugin.gimp_console_bridge as bridge_module

    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    root = tmp_path / "project-temp"
    captured: list[Path] = []

    def fake_run(command: list[str], **_: object) -> CompletedProcess[str]:
        configuration = Path(
            next(
                item.split("=", 1)[1]
                for item in command
                if item.startswith("--gimprc=")
            )
        ).parent
        captured.append(configuration)
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 120)
        return CompletedProcess(command, 1, "", "failed")

    monkeypatch.setattr(bridge_module, "_TEMP_ROOT", root)
    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(GimpConsoleError):
        GimpConsoleBridge(tmp_path / "gimp-console").render(
            source,
            tmp_path / "result.png",
            tmp_path / "result.xcf",
            make_recipe(),
            _assets(tmp_path),
        )

    assert captured[0].parent == root
    assert not captured[0].exists()


@pytest.mark.parametrize("returncode,outputs", [(1, True), (0, False)])
def test_console_bridge_fails_when_gimp_or_expected_outputs_fail(
    tmp_path: Path,
    monkeypatch,
    returncode: int,
    outputs: bool,
) -> None:
    source = tmp_path / "source.png"
    png = tmp_path / "result.png"
    xcf = tmp_path / "result.xcf"
    source.write_bytes(b"source")

    def fake_run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        if outputs:
            png.write_bytes(b"png")
            xcf.write_bytes(b"xcf")
        return CompletedProcess(command, returncode, "", "failed")

    monkeypatch.setattr("subprocess.run", fake_run)
    bridge = GimpConsoleBridge(tmp_path / "gimp-console")

    with pytest.raises(GimpConsoleError):
        bridge.render(source, png, xcf, make_recipe(), _assets(tmp_path))
