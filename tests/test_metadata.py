import hashlib
import json
from pathlib import Path

from gimp_weathered_photo_plugin.metadata import load_recipe, write_recipe
from tests.test_models import make_recipe


def test_recipe_sidecar_captures_source_fingerprint_and_recipe(tmp_path: Path) -> None:
    source = tmp_path / "print.png"
    source.write_bytes(b"source-bytes")
    path = tmp_path / "print-worn.recipe.json"
    recipe = make_recipe()

    write_recipe(path, recipe, source)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["source"]["sha256"] == hashlib.sha256(b"source-bytes").hexdigest()
    assert load_recipe(path) == recipe
