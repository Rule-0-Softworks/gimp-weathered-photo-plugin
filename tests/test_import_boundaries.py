import importlib
import importlib.metadata
import sys


def test_gimp_host_import_requires_neither_gi_nor_analyzer_packages(
    monkeypatch,
) -> None:
    for name in tuple(sys.modules):
        if name == "gimp_weathered_photo_plugin.gimp_host" or name.startswith("gi"):
            sys.modules.pop(name)

    monkeypatch.setitem(sys.modules, "gi", None)
    monkeypatch.setitem(sys.modules, "cv2", None)
    monkeypatch.setitem(sys.modules, "mediapipe", None)

    module = importlib.import_module("gimp_weathered_photo_plugin.gimp_host")

    assert module.__name__ == "gimp_weathered_photo_plugin.gimp_host"


def test_package_can_load_inside_gimp_without_installed_distribution(
    monkeypatch,
) -> None:
    def no_distribution(_: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    with monkeypatch.context() as context:
        context.setattr(importlib.metadata, "version", no_distribution)
        sys.modules.pop("gimp_weathered_photo_plugin", None)
        package = importlib.import_module("gimp_weathered_photo_plugin")

        assert package.__version__ == "0.0.0+gimp"

    sys.modules.pop("gimp_weathered_photo_plugin", None)
    importlib.import_module("gimp_weathered_photo_plugin")
