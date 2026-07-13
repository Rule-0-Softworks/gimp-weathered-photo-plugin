from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from gimp_weathered_photo_plugin.models import TreatmentRecipe


@dataclass(frozen=True, slots=True)
class RenderRecord:
    recipe: TreatmentRecipe
    source_sha256: str


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
    return load_render_record(path).recipe


def load_render_record(path: Path) -> RenderRecord:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("source"), dict)
        or not isinstance(payload["source"].get("sha256"), str)
        or "recipe" not in payload
    ):
        raise ValueError("recipe sidecar must contain recipe and source fingerprint")
    return RenderRecord(
        recipe=TreatmentRecipe.from_dict(payload["recipe"]),
        source_sha256=payload["source"]["sha256"],
    )
