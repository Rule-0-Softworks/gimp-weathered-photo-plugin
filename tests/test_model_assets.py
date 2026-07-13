from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from gimp_weathered_photo_plugin.model_assets import (
    ModelAssetError,
    ModelResolver,
    ModelSecurityError,
)


def _write_assets(tmp_path: Path, *, severity: str | None = None) -> Path:
    models = tmp_path / "models"
    models.mkdir()
    face = models / "face_landmarker.task"
    hand = models / "hand_landmarker.task"
    face.write_bytes(b"face-model")
    hand.write_bytes(b"hand-model")
    manifest = {
        "schema_version": 1,
        "models": [
            {
                "id": "face-landmarker",
                "task_type": "face_landmarker",
                "source_url": "https://example.invalid/face",
                "version": "pinned-face",
                "bytes": face.stat().st_size,
                "sha256": hashlib.sha256(face.read_bytes()).hexdigest(),
                "path": "models/face_landmarker.task",
                "license": "Apache-2.0",
            },
            {
                "id": "hand-landmarker",
                "task_type": "hand_landmarker",
                "source_url": "https://example.invalid/hand",
                "version": "pinned-hand",
                "bytes": hand.stat().st_size,
                "sha256": hashlib.sha256(hand.read_bytes()).hexdigest(),
                "path": "models/hand_landmarker.task",
                "license": "Apache-2.0",
            },
        ],
    }
    (tmp_path / "mediapipe-model-manifest.json").write_text(json.dumps(manifest))
    advisories = {"schema_version": 1, "advisories": []}
    if severity is not None:
        advisories["advisories"].append(
            {
                "model_id": "face-landmarker",
                "affected_version": "pinned-face",
                "severity": severity,
                "reference": "CVE-2026-0001",
                "suggested_replacement": "replace manually with reviewed pin",
            }
        )
    (tmp_path / "mediapipe-model-advisories.json").write_text(json.dumps(advisories))
    return tmp_path


def test_resolver_returns_verified_paths_and_auditable_configuration(
    tmp_path: Path,
) -> None:
    with ModelResolver(_write_assets(tmp_path)).resolve() as models:
        assert models.paths["face-landmarker"].read_bytes() == b"face-model"
        assert models.adapter_configuration == {
            "advisories.schema_version": "1",
            "model.face-landmarker.sha256": hashlib.sha256(b"face-model").hexdigest(),
            "model.face-landmarker.version": "pinned-face",
            "model.hand-landmarker.sha256": hashlib.sha256(b"hand-model").hexdigest(),
            "model.hand-landmarker.version": "pinned-hand",
        }


def test_resolver_rejects_a_hash_mismatch_before_returning_paths(
    tmp_path: Path,
) -> None:
    root = _write_assets(tmp_path)
    (root / "models" / "hand_landmarker.task").write_bytes(b"tampered")
    with pytest.raises(ModelAssetError, match=r"hand-landmarker.*SHA-256"):
        ModelResolver(root).resolve().__enter__()


@pytest.mark.parametrize("severity", ["medium", "high", "critical"])
def test_medium_or_higher_advisory_blocks_with_manual_remediation(
    tmp_path: Path, severity: str
) -> None:
    with pytest.raises(
        ModelSecurityError,
        match=r"face-landmarker.*pinned-face.*CVE-2026-0001.*manually",
    ):
        ModelResolver(_write_assets(tmp_path, severity=severity)).resolve().__enter__()


def test_low_advisory_warns_but_allows_fresh_analysis(tmp_path: Path) -> None:
    resolver = ModelResolver(_write_assets(tmp_path, severity="low"))
    with pytest.warns(UserWarning, match="CVE-2026-0001"), resolver.resolve() as models:
        assert models.paths["hand-landmarker"].is_file()
