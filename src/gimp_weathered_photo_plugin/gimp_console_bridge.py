from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from gimp_weathered_photo_plugin.models import TreatmentRecipe

_TEMP_ROOT = Path(tempfile.gettempdir()) / "gimp-weathered-photo-plugin"


class GimpConsoleError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GimpConsoleBridge:
    executable: Path
    timeout_seconds: int = 120

    def __post_init__(self) -> None:
        if not self.executable.is_absolute():
            raise GimpConsoleError("GIMP console executable must be an absolute path")
        if self.timeout_seconds <= 0:
            raise GimpConsoleError("GIMP console timeout must be positive")

    def render(
        self,
        source: Path,
        png: Path,
        xcf: Path,
        recipe: TreatmentRecipe,
        assets: Mapping[str, Path],
    ) -> None:
        if source.suffix.lower() != ".png" or not source.is_file():
            raise GimpConsoleError("GIMP rendering requires a staged PNG source")
        source, png, xcf = (path.resolve() for path in (source, png, xcf))
        resolved_assets = {
            asset_id: path.resolve() for asset_id, path in assets.items()
        }
        if not all(path.is_file() for path in resolved_assets.values()):
            raise GimpConsoleError("GIMP render assets are missing")
        _TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="gimp-weathered-", dir=_TEMP_ROOT
        ) as temporary:
            configuration = Path(temporary)
            request_path = configuration / "request.json"
            self._stage_brushes(configuration, resolved_assets)
            self._write_gimprc(configuration)
            request_path.write_text(
                json.dumps(
                    {
                        "source": str(source),
                        "png": str(png),
                        "xcf": str(xcf),
                        "recipe": recipe.to_dict(),
                        "assets": {
                            key: str(value) for key, value in resolved_assets.items()
                        },
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            command = self._command(configuration, request_path)
            try:
                completed = subprocess.run(
                    command,
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    shell=False,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise GimpConsoleError("GIMP console timed out") from error
            if completed.returncode != 0:
                raise GimpConsoleError(
                    "GIMP console failed with exit code "
                    f"{completed.returncode}: {completed.stderr}"
                )
        if any(not path.is_file() or path.stat().st_size == 0 for path in (png, xcf)):
            raise GimpConsoleError("GIMP console did not produce staged PNG and XCF")

    def _command(self, configuration: Path, request_path: Path) -> list[str]:
        host_root = Path(__file__).resolve().parents[1]
        batch = (
            "import sys; "
            f"sys.path.insert(0, {str(host_root)!r}); "
            "from gimp_weathered_photo_plugin.gimp_host import run_console_request; "
            f"run_console_request({str(request_path)!r})"
        )
        return [
            str(self.executable),
            "--no-interface",
            "--new-instance",
            "--console-messages",
            f"--gimprc={configuration / 'gimprc'}",
            "--batch-interpreter=python-fu-eval",
            f"--batch={batch}",
            "--quit",
        ]

    @staticmethod
    def _stage_brushes(configuration: Path, assets: Mapping[str, Path]) -> None:
        brush_directory = configuration / "brushes"
        brush_directory.mkdir()
        for asset in assets.values():
            if asset.suffix.lower() == ".gbr":
                shutil.copy2(asset, brush_directory / asset.name)

    @staticmethod
    def _write_gimprc(configuration: Path) -> None:
        brush_directory = (configuration / "brushes").as_posix()
        (configuration / "gimprc").write_text(
            '(brush-path "${gimp_data_dir}\\\\brushes;' + brush_directory + '")\n'
            '(brush-path-writable "' + brush_directory + '")\n',
            encoding="utf-8",
        )
