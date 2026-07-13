from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from gimp_weathered_photo_plugin.models import Size, SoftExclusion, TreatmentRecipe

_DETECTORS = frozenset({"face", "hand", "saliency"})
_STATUSES = frozenset({"detected", "no_detection", "disabled", "failed"})
_MODEL_PROVENANCE_KEYS = frozenset(
    {
        "advisories.schema_version",
        "model.face-landmarker.sha256",
        "model.face-landmarker.version",
        "model.hand-landmarker.sha256",
        "model.hand-landmarker.version",
    }
)


@dataclass(frozen=True, slots=True)
class RenderRecord:
    recipe: TreatmentRecipe
    source_sha256: str
    source_size: Size
    asset_sha256: Mapping[str, str]
    bridge_schema_version: int
    recipe_schema_version: int
    analyzer_version: str
    adapter_configuration: Mapping[str, str]
    detectors: Mapping[str, str]
    exclusions: tuple[SoftExclusion, ...]

    def __post_init__(self) -> None:
        _validate_sha256(self.source_sha256)
        if self.source_size != self.recipe.source_size:
            raise ValueError("record dimensions do not match the recipe")
        if self.recipe_schema_version != self.recipe.schema_version:
            raise ValueError("record recipe schema does not match the recipe")
        if self.bridge_schema_version <= 0:
            raise ValueError("bridge schema version must be positive")
        if not self.analyzer_version:
            raise ValueError("analyzer version must not be empty")
        if self.exclusions != self.recipe.exclusions:
            raise ValueError("record exclusions do not match the recipe")
        if not all(
            isinstance(asset_id, str) and asset_id for asset_id in self.asset_sha256
        ):
            raise ValueError("asset fingerprints must use non-empty asset IDs")
        for fingerprint in self.asset_sha256.values():
            _validate_sha256(fingerprint)
        if set(self.detectors) != _DETECTORS or any(
            status not in _STATUSES for status in self.detectors.values()
        ):
            raise ValueError("record detectors are invalid")
        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in self.adapter_configuration.items()
        ):
            raise ValueError("adapter configuration must contain string values")
        if self.bridge_schema_version >= 2:
            if not _MODEL_PROVENANCE_KEYS.issubset(self.adapter_configuration):
                raise ValueError("adapter configuration is missing model provenance")
            _validate_sha256(
                self.adapter_configuration["model.face-landmarker.sha256"]
            )
            _validate_sha256(
                self.adapter_configuration["model.hand-landmarker.sha256"]
            )


def write_render_record(path: Path, record: RenderRecord) -> Path:
    payload = {
        "analysis": {
            "adapter_configuration": dict(record.adapter_configuration),
            "analyzer_version": record.analyzer_version,
            "bridge_schema_version": record.bridge_schema_version,
            "detectors": dict(record.detectors),
        },
        "assets": dict(record.asset_sha256),
        "exclusions": [exclusion.to_dict() for exclusion in record.exclusions],
        "recipe": record.recipe.to_dict(),
        "recipe_schema_version": record.recipe_schema_version,
        "source": {
            "sha256": record.source_sha256,
            "size": record.source_size.to_dict(),
        },
    }
    _write_json_atomically(path, payload)
    return path


def write_recipe(path: Path, recipe: TreatmentRecipe, source: Path) -> Path:
    payload = {
        "recipe": recipe.to_dict(),
        "source": {
            "name": source.name,
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        },
    }
    _write_json_atomically(path, payload)
    return path


def load_recipe(path: Path) -> TreatmentRecipe:
    payload = _read_payload(path)
    return TreatmentRecipe.from_dict(payload["recipe"])


def load_render_record(path: Path) -> RenderRecord:
    payload = _read_payload(path)
    try:
        source = _require_mapping(payload["source"], "source")
        analysis = _require_mapping(payload["analysis"], "analysis")
        assets = _string_mapping(payload["assets"], "assets")
        adapter_configuration = _string_mapping(
            analysis["adapter_configuration"], "adapter configuration"
        )
        detectors = _string_mapping(analysis["detectors"], "detectors")
        exclusions_data = payload["exclusions"]
        if not isinstance(exclusions_data, list):
            raise ValueError("exclusions must be an array")
        return RenderRecord(
            recipe=TreatmentRecipe.from_dict(payload["recipe"]),
            source_sha256=_require_string(source["sha256"], "source fingerprint"),
            source_size=Size.from_dict(source["size"]),
            asset_sha256=assets,
            bridge_schema_version=_require_int(
                analysis["bridge_schema_version"], "bridge schema version"
            ),
            recipe_schema_version=_require_int(
                payload["recipe_schema_version"], "recipe schema version"
            ),
            analyzer_version=_require_string(
                analysis["analyzer_version"], "analyzer version"
            ),
            adapter_configuration=adapter_configuration,
            detectors=detectors,
            exclusions=tuple(SoftExclusion.from_dict(item) for item in exclusions_data),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            "recipe sidecar must contain a complete render record"
        ) from error


def _write_json_atomically(path: Path, payload: Mapping[str, object]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    temporary.replace(path)


def _read_payload(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _require_mapping(payload, "recipe sidecar")


def _require_mapping(value: object, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field_name} must be an object")
    return cast(dict[str, object], value)


def _string_mapping(value: object, field_name: str) -> dict[str, str]:
    mapping = _require_mapping(value, field_name)
    if not all(isinstance(item, str) for item in mapping.values()):
        raise ValueError(f"{field_name} must contain strings")
    return {key: value for key, value in mapping.items() if isinstance(value, str)}


def _require_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _require_int(value: object, field_name: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _validate_sha256(value: str) -> None:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError("fingerprint must be a lowercase SHA-256 digest")
