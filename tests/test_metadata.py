import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from gimp_weathered_photo_plugin.metadata import (
    RenderRecord,
    load_recipe,
    load_render_record,
    write_recipe,
)
from gimp_weathered_photo_plugin.models import Size
from tests.test_models import make_recipe


def _adapter_configuration() -> dict[str, str]:
    return {
        "advisories.schema_version": "1",
        "model.face-landmarker.sha256": "a" * 64,
        "model.face-landmarker.version": "gcs-generation-1683136941468629",
        "model.hand-landmarker.sha256": "b" * 64,
        "model.hand-landmarker.version": "gcs-generation-1682480005356399",
    }


def test_render_record_round_trips_complete_replay_contract(tmp_path: Path) -> None:
    from gimp_weathered_photo_plugin.metadata import write_render_record

    path = tmp_path / "print-worn.recipe.json"
    recipe = replace(make_recipe(), source_size=Size(width=10, height=20))
    record = RenderRecord(
        recipe=recipe,
        source_sha256="a" * 64,
        source_size=Size(width=10, height=20),
        asset_sha256={"dry-rub-neutral-gray": "b" * 64},
        bridge_schema_version=1,
        recipe_schema_version=1,
        analyzer_version="1.2.3",
        adapter_configuration={"model": "holistic"},
        detectors={
            "face": "no_detection",
            "hand": "no_detection",
            "saliency": "detected",
        },
        exclusions=recipe.exclusions,
    )

    write_render_record(path, record)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["source"]["size"] == {"width": 10, "height": 20}
    assert payload["assets"] == {"dry-rub-neutral-gray": "b" * 64}
    assert payload["analysis"] == {
        "adapter_configuration": {"model": "holistic"},
        "analyzer_version": "1.2.3",
        "bridge_schema_version": 1,
        "detectors": {
            "face": "no_detection",
            "hand": "no_detection",
            "saliency": "detected",
        },
    }
    assert load_render_record(path) == record


def test_recipe_sidecar_captures_source_fingerprint_and_recipe(tmp_path: Path) -> None:
    source = tmp_path / "print.png"
    source.write_bytes(b"source-bytes")
    path = tmp_path / "print-worn.recipe.json"
    recipe = make_recipe()

    write_recipe(path, recipe, source)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["source"]["sha256"] == hashlib.sha256(b"source-bytes").hexdigest()
    assert load_recipe(path) == recipe


def test_load_render_record_rejects_incomplete_schema_v2_model_provenance(
    tmp_path: Path,
) -> None:
    path = tmp_path / "print-worn.recipe.json"
    recipe = replace(make_recipe(), source_size=Size(width=10, height=20))
    record = RenderRecord(
        recipe=recipe,
        source_sha256="a" * 64,
        source_size=Size(width=10, height=20),
        asset_sha256={"dry-rub-neutral-gray": "b" * 64},
        bridge_schema_version=2,
        recipe_schema_version=1,
        analyzer_version="1.2.3",
        adapter_configuration=_adapter_configuration(),
        detectors={
            "face": "no_detection",
            "hand": "no_detection",
            "saliency": "detected",
        },
        exclusions=recipe.exclusions,
    )
    from gimp_weathered_photo_plugin.metadata import write_render_record

    write_render_record(path, record)
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["analysis"]["adapter_configuration"]["model.hand-landmarker.version"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        ValueError, match="recipe sidecar must contain a complete render record"
    ):
        load_render_record(path)
