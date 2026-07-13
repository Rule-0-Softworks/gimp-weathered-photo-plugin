import json
from pathlib import Path

import pytest

from gimp_weathered_photo_plugin.assets import MissingBrushAssetsError, resolve_assets


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
