from importlib.metadata import version
from importlib.resources import files

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
