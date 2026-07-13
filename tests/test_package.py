from importlib.metadata import version

import gimp_weathered_photo_plugin


def test_package_exposes_distribution_version() -> None:
    assert gimp_weathered_photo_plugin.__version__ == version(
        "gimp-weathered-photo-plugin"
    )
