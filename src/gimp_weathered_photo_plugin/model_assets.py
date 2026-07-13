"""Verification and advisory policy for packaged MediaPipe task models."""

from __future__ import annotations

import hashlib
import json
import re
import warnings
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import cast

_EXPECTED_MODEL_IDS = frozenset({"face-landmarker", "hand-landmarker"})
_BLOCKING_SEVERITIES = frozenset({"medium", "high", "critical"})
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class ResolvedModel:
    model_id: str
    task_type: str
    version: str
    sha256: str
    path: Path


@dataclass(frozen=True, slots=True)
class ResolvedModels:
    paths: Mapping[str, Path]
    adapter_configuration: Mapping[str, str]


class ModelAssetError(RuntimeError):
    """Raised when a packaged model asset does not match its manifest."""


class ModelSecurityError(RuntimeError):
    """Raised when an offline advisory blocks a packaged model pin."""


class ModelResolver:
    def __init__(self, assets_root: Path | None = None) -> None:
        self._assets_root = assets_root

    @contextmanager
    def resolve(self) -> Iterator[ResolvedModels]:
        """Verify both packaged pins and keep their materialized paths alive."""
        if self._assets_root is not None:
            yield self._resolve_from_root(self._assets_root)
            return

        package_assets = resources.files("gimp_weathered_photo_plugin").joinpath(
            "assets"
        )
        with resources.as_file(package_assets) as assets_root:
            yield self._resolve_from_root(assets_root)

    def _resolve_from_root(self, assets_root: Path) -> ResolvedModels:
        root = assets_root.resolve()
        manifest = _load_json(root / "mediapipe-model-manifest.json", "model manifest")
        advisory_data = _load_json(
            root / "mediapipe-model-advisories.json", "model advisories"
        )
        models = _resolve_manifest_models(root, manifest)
        _evaluate_advisories(advisory_data, models)

        paths = {model.model_id: model.path for model in models.values()}
        configuration = {
            "advisories.schema_version": str(
                _schema_version(advisory_data, "advisories")
            ),
        }
        for model_id in sorted(models):
            model = models[model_id]
            configuration[f"model.{model_id}.sha256"] = model.sha256
            configuration[f"model.{model_id}.version"] = model.version
        return ResolvedModels(paths=paths, adapter_configuration=configuration)


def _load_json(path: Path, name: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ModelAssetError(f"Unable to read {name}: {path}") from error


def _schema_version(document: object, name: str) -> int:
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ModelAssetError(f"Unsupported {name} schema version")
    return 1


def _resolve_manifest_models(root: Path, manifest: object) -> dict[str, ResolvedModel]:
    _schema_version(manifest, "model manifest")
    assert isinstance(manifest, dict)
    entries = manifest.get("models")
    if not isinstance(entries, list):
        raise ModelAssetError("Model manifest must contain a models list")

    models: dict[str, ResolvedModel] = {}
    for entry in entries:
        entry = _require_object(entry, "Model manifest entry")
        model_id = _required_string(entry, "id", "model manifest entry")
        if model_id not in _EXPECTED_MODEL_IDS:
            raise ModelAssetError(f"Unknown model manifest entry: {model_id}")
        if model_id in models:
            raise ModelAssetError(f"Duplicate model manifest entry: {model_id}")
        models[model_id] = _verify_model(root, model_id, entry)

    missing = _EXPECTED_MODEL_IDS - models.keys()
    if missing:
        missing_names = ", ".join(sorted(missing))
        raise ModelAssetError(f"Missing model manifest entries: {missing_names}")
    return models


def _verify_model(root: Path, model_id: str, entry: dict[str, object]) -> ResolvedModel:
    task_type = _required_string(entry, "task_type", model_id)
    version = _required_string(entry, "version", model_id)
    expected_sha256 = _required_string(entry, "sha256", model_id)
    if _SHA256_PATTERN.fullmatch(expected_sha256) is None:
        raise ModelAssetError(f"{model_id} has an invalid lowercase SHA-256")

    expected_size = entry.get("bytes")
    if (
        isinstance(expected_size, bool)
        or not isinstance(expected_size, int)
        or expected_size < 0
    ):
        raise ModelAssetError(f"{model_id} has an invalid byte count")
    relative_path = _required_string(entry, "path", model_id)
    path = _contained_path(root, relative_path, model_id)
    try:
        contents = path.read_bytes()
    except OSError as error:
        raise ModelAssetError(f"Unable to read packaged model {model_id}") from error

    actual_sha256 = hashlib.sha256(contents).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ModelAssetError(f"{model_id} SHA-256 does not match its manifest")
    if len(contents) != expected_size:
        raise ModelAssetError(f"{model_id} byte count does not match its manifest")
    return ResolvedModel(model_id, task_type, version, expected_sha256, path)


def _required_string(entry: dict[str, object], key: str, context: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value:
        raise ModelAssetError(f"{context} requires a non-empty {key}")
    return value


def _require_object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ModelAssetError(f"{context} must be an object")
    return cast(dict[str, object], value)


def _contained_path(root: Path, relative_path: str, model_id: str) -> Path:
    candidate = root / relative_path
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except ValueError as error:
        raise ModelAssetError(f"{model_id} path escapes the asset root") from error
    if not resolved.is_file():
        raise ModelAssetError(f"{model_id} packaged model is missing")
    return resolved


def _evaluate_advisories(
    advisory_data: object, models: Mapping[str, ResolvedModel]
) -> None:
    _schema_version(advisory_data, "advisories")
    assert isinstance(advisory_data, dict)
    advisories = advisory_data.get("advisories")
    if not isinstance(advisories, list):
        raise ModelAssetError("Model advisories must contain an advisories list")

    for advisory in advisories:
        advisory = _require_object(advisory, "Model advisory entry")
        model_id = _required_string(advisory, "model_id", "model advisory")
        affected_version = _required_string(
            advisory, "affected_version", "model advisory"
        )
        severity = _required_string(advisory, "severity", "model advisory")
        reference = _required_string(advisory, "reference", "model advisory")
        replacement = _required_string(
            advisory, "suggested_replacement", "model advisory"
        )
        model = models.get(model_id)
        if model is None:
            raise ModelAssetError(f"Unknown model advisory ID: {model_id}")
        if model.version != affected_version:
            continue
        message = (
            f"Model {model_id} version {affected_version} advisory {reference}: "
            f"{replacement}. A manual update is required."
        )
        if severity == "low":
            warnings.warn(message, UserWarning, stacklevel=2)
        elif severity in _BLOCKING_SEVERITIES:
            raise ModelSecurityError(message)
        else:
            raise ModelAssetError(f"Unsupported advisory severity: {severity}")
