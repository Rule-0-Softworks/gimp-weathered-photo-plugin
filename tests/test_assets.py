import json
import struct
from pathlib import Path

import pytest

from gimp_weathered_photo_plugin.assets import MissingBrushAssetsError, resolve_assets

PACKAGE_ASSETS = (
    Path(__file__).resolve().parents[1] / "src/gimp_weathered_photo_plugin/assets"
)


def write_manifest(root: Path) -> None:
    assets = {
        "dry-rub-neutral-gray": "brushes/dry-rub-neutral-gray.gbr",
        "dry-rub-umber": "brushes/dry-rub-umber.gbr",
        "mottled-sepia": "brushes/mottled-sepia.gbr",
        "water-stain-01": "masks/water-stain-01.png",
        "water-stain-02": "masks/water-stain-02.png",
        "water-stain-03": "masks/water-stain-03.png",
    }
    (root / "worn-print-manifest.json").write_text(
        json.dumps({"assets": assets}), encoding="utf-8"
    )
    for relative_path in assets.values():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"placeholder")


def test_resolve_assets_reports_the_exact_missing_asset_id(tmp_path: Path) -> None:
    write_manifest(tmp_path)
    (tmp_path / "masks/water-stain-03.png").unlink()

    with pytest.raises(MissingBrushAssetsError) as error:
        resolve_assets(tmp_path)

    assert error.value.asset_ids == ("water-stain-03",)


def test_packaged_assets_are_native_gimp_brushes_and_grayscale_masks() -> None:
    assets = resolve_assets(PACKAGE_ASSETS)
    brushes = (
        "dry-rub-neutral-gray",
        "dry-rub-umber",
        "mottled-sepia",
    )
    masks = ("water-stain-01", "water-stain-02", "water-stain-03")

    for asset_id in brushes:
        header = assets[asset_id].read_bytes()[:28]
        header_size, version, width, height, bytes_per_pixel, magic, spacing = (
            struct.unpack(">7I", header)
        )
        assert header_size >= 28
        assert version == 2
        assert width >= 64 and height >= 64
        assert bytes_per_pixel in (1, 3, 4)
        assert magic == 0x47494D50
        assert spacing > 0

    dimensions: list[tuple[int, int]] = []
    for asset_id in masks:
        header = assets[asset_id].read_bytes()[:29]
        assert header.startswith(b"\x89PNG\r\n\x1a\n")
        assert header[12:16] == b"IHDR"
        width, height, bit_depth, color_type = struct.unpack(">IIBB", header[16:26])
        assert width >= 64 and height >= 64
        assert width != height
        assert bit_depth == 8
        assert color_type in (0, 4)
        dimensions.append((width, height))

    assert len(set(dimensions)) == len(masks)
