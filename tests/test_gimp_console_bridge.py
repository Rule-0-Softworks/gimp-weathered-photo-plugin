import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from gimp_weathered_photo_plugin.gimp_console_bridge import (
    GimpConsoleBridge,
    GimpConsoleError,
)
from tests.test_models import make_recipe


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
    bridge = GimpConsoleBridge(Path("C:/GIMP/bin/gimp-console.exe"))

    bridge.render(source, png, xcf, make_recipe(), _assets(tmp_path))

    assert calls[0][0][0] == "C:\\GIMP\\bin\\gimp-console.exe"
    assert calls[0][1]["shell"] is False


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
    bridge = GimpConsoleBridge(Path("C:/GIMP/bin/gimp-console.exe"))

    with pytest.raises(GimpConsoleError):
        bridge.render(source, png, xcf, make_recipe(), _assets(tmp_path))
