from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("gimp-weathered-photo-plugin")
except PackageNotFoundError:
    # GIMP loads plug-ins from their source directory, not an installed wheel.
    __version__ = "0.0.0+gimp"
