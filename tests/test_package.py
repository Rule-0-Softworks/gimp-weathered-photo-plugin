import subprocess
import zipfile
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path

import gimp_weathered_photo_plugin
from gimp_weathered_photo_plugin.model_assets import ModelResolver


def test_package_exposes_distribution_version() -> None:
    assert gimp_weathered_photo_plugin.__version__ == version(
        "gimp-weathered-photo-plugin"
    )


def test_package_includes_verified_mediapipe_model_assets() -> None:
    assets = files("gimp_weathered_photo_plugin").joinpath("assets")
    assert assets.joinpath("mediapipe-model-manifest.json").is_file()
    assert assets.joinpath("mediapipe-model-advisories.json").is_file()
    assert assets.joinpath("models/face_landmarker.task").is_file()
    assert assets.joinpath("models/hand_landmarker.task").is_file()
    with ModelResolver().resolve() as models:
        assert len(models.paths) == 2
        assert all(path.is_file() for path in models.paths.values())


def test_built_wheel_includes_verified_mediapipe_model_assets() -> None:
    subprocess.run(["uv", "build"], check=True)
    wheel_path = next(Path("dist").glob("*.whl"))

    with zipfile.ZipFile(wheel_path) as wheel:
        members = set(wheel.namelist())

    assert {
        "gimp_weathered_photo_plugin/assets/mediapipe-model-manifest.json",
        "gimp_weathered_photo_plugin/assets/mediapipe-model-advisories.json",
        "gimp_weathered_photo_plugin/assets/models/face_landmarker.task",
        "gimp_weathered_photo_plugin/assets/models/hand_landmarker.task",
    } <= members
