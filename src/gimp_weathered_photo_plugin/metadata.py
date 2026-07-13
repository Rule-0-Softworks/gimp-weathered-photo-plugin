from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gimp_weathered_photo_plugin.models import TreatmentRecipe


def write_recipe(path: Path, recipe: TreatmentRecipe, source: Path) -> Path:
    payload = {
        "recipe": recipe.to_dict(),
        "source": {
            "name": source.name,
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        },
    }
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    temporary.replace(path)
    return path


def load_recipe(path: Path) -> TreatmentRecipe:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "recipe" not in payload:
        raise ValueError("recipe sidecar must contain a recipe object")
    return TreatmentRecipe.from_dict(payload["recipe"])
