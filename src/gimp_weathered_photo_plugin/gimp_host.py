from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from gimp_weathered_photo_plugin.models import Mark, TreatmentRecipe


class GimpOperations(Protocol):
    def retain_source(self) -> None: ...

    def apply_mark(self, mark: Mark, asset: Path) -> None: ...

    def apply_local_blur(self, mark: Mark, asset: Path) -> None: ...


def apply_recipe(
    operations: GimpOperations,
    recipe: TreatmentRecipe,
    assets: Mapping[str, Path],
) -> None:
    operations.retain_source()
    for mark in recipe.marks:
        asset = assets[mark.asset_id]
        if mark.family == "water_stain":
            operations.apply_local_blur(mark, asset)
        else:
            operations.apply_mark(mark, asset)
