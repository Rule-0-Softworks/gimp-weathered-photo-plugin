from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from gimp_weathered_photo_plugin.models import Size, SoftExclusion

BRIDGE_SCHEMA_VERSION = 2
MAX_RESPONSE_BYTES = 64 * 1024
MAX_EXCLUSIONS = 32
MAX_ADAPTER_CONFIGURATION_ENTRIES = 16
MAX_ADAPTER_CONFIGURATION_STRING_BYTES = 256
DetectorStatus = Literal["detected", "no_detection", "disabled", "failed"]
_DETECTORS = frozenset({"face", "hand", "saliency"})
_STATUSES = frozenset({"detected", "no_detection", "disabled", "failed"})


class BridgeProtocolError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AnalysisRequest:
    bridge_schema_version: int
    source_path: Path
    source_sha256: str
    source_size: Size

    def __post_init__(self) -> None:
        _validate_schema_version(self.bridge_schema_version)
        _validate_sha256(self.source_sha256)
        if not self.source_path.is_absolute():
            raise BridgeProtocolError("source_path must be absolute")

    def to_dict(self) -> dict[str, object]:
        return {
            "bridge_schema_version": self.bridge_schema_version,
            "source_path": self.source_path.as_posix(),
            "source_sha256": self.source_sha256,
            "source_size": self.source_size.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class AnalysisResponse:
    bridge_schema_version: int
    source_sha256: str
    detectors: Mapping[str, DetectorStatus]
    adapter_configuration: Mapping[str, str]
    exclusions: tuple[SoftExclusion, ...]


def parse_response_json(document: str) -> AnalysisResponse:
    if len(document.encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise BridgeProtocolError("analyzer response exceeds 64 KiB")
    try:
        payload = json.loads(document, parse_constant=_reject_nonfinite)
    except (json.JSONDecodeError, UnicodeError, ValueError) as error:
        raise BridgeProtocolError("analyzer response is not valid JSON") from error
    if not isinstance(payload, dict):
        raise BridgeProtocolError("analyzer response must be an object")
    try:
        version = payload["bridge_schema_version"]
        source_sha256 = payload["source_sha256"]
        detectors = _parse_detectors(payload["detectors"])
        adapter_configuration = _parse_adapter_configuration(
            payload["adapter_configuration"]
        )
        exclusions_data = payload["exclusions"]
    except KeyError as error:
        raise BridgeProtocolError(
            f"analyzer response is missing {error.args[0]}"
        ) from error
    _validate_schema_version(version)
    if not isinstance(source_sha256, str):
        raise BridgeProtocolError("source_sha256 must be a string")
    _validate_sha256(source_sha256)
    if not isinstance(exclusions_data, list) or len(exclusions_data) > MAX_EXCLUSIONS:
        raise BridgeProtocolError("exclusions must contain at most 32 regions")
    try:
        exclusions = tuple(SoftExclusion.from_dict(item) for item in exclusions_data)
    except (KeyError, TypeError, ValueError) as error:
        raise BridgeProtocolError("analyzer response has invalid exclusions") from error
    return AnalysisResponse(
        bridge_schema_version=version,
        source_sha256=source_sha256,
        detectors=detectors,
        adapter_configuration=adapter_configuration,
        exclusions=exclusions,
    )


def _parse_detectors(value: object) -> dict[str, DetectorStatus]:
    if not isinstance(value, dict) or set(value) != _DETECTORS:
        raise BridgeProtocolError("detectors must contain face, hand, and saliency")
    result: dict[str, DetectorStatus] = {}
    for name, status in value.items():
        if (
            not isinstance(name, str)
            or not isinstance(status, str)
            or status not in _STATUSES
        ):
            raise BridgeProtocolError("detectors contain an unsupported status")
        result[name] = cast(DetectorStatus, status)
    return result


def _parse_adapter_configuration(value: object) -> dict[str, str]:
    if (
        not isinstance(value, dict)
        or not 1 <= len(value) <= MAX_ADAPTER_CONFIGURATION_ENTRIES
    ):
        raise BridgeProtocolError(
            "adapter_configuration must contain 1 to 16 string entries"
        )
    result: dict[str, str] = {}
    for key, entry in value.items():
        if (
            not isinstance(key, str)
            or not key
            or not isinstance(entry, str)
            or not entry
            or len(key.encode("utf-8")) > MAX_ADAPTER_CONFIGURATION_STRING_BYTES
            or len(entry.encode("utf-8")) > MAX_ADAPTER_CONFIGURATION_STRING_BYTES
        ):
            raise BridgeProtocolError(
                "adapter_configuration keys and values must be non-empty strings "
                "of at most 256 UTF-8 bytes"
            )
        result[key] = entry
    return result


def _validate_schema_version(value: object) -> None:
    if value != BRIDGE_SCHEMA_VERSION:
        raise BridgeProtocolError("unsupported bridge schema version")


def _validate_sha256(value: str) -> None:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise BridgeProtocolError("source_sha256 must be a lowercase SHA-256 digest")


def _reject_nonfinite(value: str) -> Any:
    raise ValueError(f"non-finite JSON value: {value}")
