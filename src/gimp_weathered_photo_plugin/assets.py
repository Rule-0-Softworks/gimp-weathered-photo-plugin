from __future__ import annotations

import json
from pathlib import Path

ASSET_IDS = (
    "dry-rub-neutral-gray",
    "dry-rub-umber",
    "mottled-sepia",
    "water-stain-01",
    "water-stain-02",
    "water-stain-03",
)
MANIFEST_NAME = "worn-print-manifest.json"


class MissingBrushAssetsError(FileNotFoundError):
    def __init__(self, asset_ids: tuple[str, ...]) -> None:
        self.asset_ids = asset_ids
        super().__init__(f"missing curated assets: {', '.join(asset_ids)}")


def resolve_assets(root: Path) -> dict[str, Path]:
    manifest_path = root / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("assets"), dict):
        raise ValueError("asset manifest must contain an assets object")

    paths = manifest["assets"]
    if set(paths) != set(ASSET_IDS):
        raise ValueError("asset manifest must declare the curated asset IDs exactly")

    resolved: dict[str, Path] = {}
    missing: list[str] = []
    resolved_root = root.resolve()
    for asset_id in ASSET_IDS:
        relative = paths[asset_id]
        if not isinstance(relative, str):
            raise ValueError(f"asset path for {asset_id} must be a string")
        path = (root / relative).resolve()
        if not path.is_relative_to(resolved_root):
            raise ValueError(f"asset path for {asset_id} escapes the asset root")
        if not path.is_file():
            missing.append(asset_id)
            continue
        resolved[asset_id] = path

    if missing:
        raise MissingBrushAssetsError(tuple(missing))
    return resolved
