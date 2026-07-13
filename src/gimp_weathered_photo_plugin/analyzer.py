from __future__ import annotations

import hashlib
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, cast

from gimp_weathered_photo_plugin.bridge_protocol import (
    MAX_RESPONSE_BYTES,
    AnalysisRequest,
    AnalysisResponse,
    BridgeProtocolError,
    DetectorStatus,
)
from gimp_weathered_photo_plugin.models import Size, SoftExclusion
from gimp_weathered_photo_plugin.protection import (
    Image,
    ProtectionDependencyError,
    build_protection_regions,
)


class AnalyzerError(RuntimeError):
    pass


class AnalyzerRequestError(ValueError):
    pass


class ProtectionAnalyzer(Protocol):
    def analyze(
        self, source: Path
    ) -> tuple[Mapping[str, str], tuple[SoftExclusion, ...]]: ...


class MediaPipeOpenCvAdapter:
    def analyze(
        self, source: Path
    ) -> tuple[Mapping[str, str], tuple[SoftExclusion, ...]]:
        try:
            import cv2
        except ImportError as error:
            raise AnalyzerError("opencv-contrib-python is required") from error
        image = cv2.imread(str(source), cv2.IMREAD_UNCHANGED)
        if image is None:
            raise AnalyzerError("source image is unreadable")
        try:
            exclusions = build_protection_regions(cast(Image, image))
        except ProtectionDependencyError as error:
            raise AnalyzerError(str(error)) from error
        except (TypeError, ValueError) as error:
            raise AnalyzerError("protection analysis failed") from error
        sources = {exclusion.source for exclusion in exclusions}
        return (
            {
                "face": "detected" if "face" in sources else "no_detection",
                "hand": "detected" if "hand" in sources else "no_detection",
                "saliency": "detected",
            },
            exclusions,
        )


def analyze_request(
    request: AnalysisRequest, adapter: ProtectionAnalyzer
) -> AnalysisResponse:
    if (
        hashlib.sha256(request.source_path.read_bytes()).hexdigest()
        != request.source_sha256
    ):
        raise AnalyzerError("source fingerprint mismatch")
    os.environ["MPLCONFIGDIR"] = str(request.source_path.parent / ".matplotlib")
    detectors, exclusions = adapter.analyze(request.source_path)
    validated = _validate_detectors(detectors)
    failed = next(
        (name for name, status in validated.items() if status == "failed"), None
    )
    if failed is not None:
        raise AnalyzerError(f"{failed} detector failed")
    if validated["saliency"] != "detected":
        raise AnalyzerError("saliency detector must succeed")
    return AnalysisResponse(
        bridge_schema_version=request.bridge_schema_version,
        source_sha256=request.source_sha256,
        detectors=validated,
        exclusions=exclusions,
    )


def _validate_detectors(detectors: Mapping[str, str]) -> dict[str, DetectorStatus]:
    expected = {"face", "hand", "saliency"}
    if set(detectors) != expected:
        raise AnalyzerError("analyzer must report face, hand, and saliency")
    allowed = {"detected", "no_detection", "disabled", "failed"}
    if any(status not in allowed for status in detectors.values()):
        raise AnalyzerError("analyzer returned an unsupported detector status")
    return {name: cast(DetectorStatus, status) for name, status in detectors.items()}


def main() -> int:
    """Execute one semantic-analysis request received on UTF-8 standard input."""

    try:
        request = _read_request(sys.stdin.buffer.read())
    except AnalyzerRequestError as error:
        _write_diagnostic(str(error))
        return 2

    try:
        response = analyze_request(request, MediaPipeOpenCvAdapter())
        _write_response(response)
    except OSError as error:
        _write_diagnostic(f"source image is unreadable: {error}")
        return 4
    except AnalyzerError as error:
        _write_diagnostic(str(error))
        return _analyzer_error_exit_code(error)
    except Exception as error:
        _write_diagnostic(f"unexpected analyzer failure: {error}")
        return 70
    return 0


def _read_request(payload: bytes) -> AnalysisRequest:
    try:
        document = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AnalyzerRequestError("analyzer request must be valid UTF-8") from error
    try:
        value = json.loads(document, parse_constant=_reject_nonfinite)
        if not isinstance(value, dict):
            raise AnalyzerRequestError("analyzer request must be an object")
        return AnalysisRequest(
            bridge_schema_version=value["bridge_schema_version"],
            source_path=Path(value["source_path"]),
            source_sha256=value["source_sha256"],
            source_size=Size.from_dict(value["source_size"]),
        )
    except (
        BridgeProtocolError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        raise AnalyzerRequestError("analyzer request is invalid") from error


def _write_response(response: AnalysisResponse) -> None:
    document = json.dumps(
        {
            "bridge_schema_version": response.bridge_schema_version,
            "detectors": dict(response.detectors),
            "exclusions": [exclusion.to_dict() for exclusion in response.exclusions],
            "source_sha256": response.source_sha256,
        },
        separators=(",", ":"),
    )
    if len(document.encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise AnalyzerError("analyzer response exceeds 64 KiB")
    print(document)


def _analyzer_error_exit_code(error: AnalyzerError) -> int:
    message = str(error).lower()
    if (
        "mediapipe is required" in message
        or "opencv-contrib-python is required" in message
    ):
        return 3
    if (
        "source image is unreadable" in message
        or "source fingerprint mismatch" in message
    ):
        return 4
    return 5


def _write_diagnostic(message: str) -> None:
    encoded = message.encode("utf-8")[:8192]
    print(encoded.decode("utf-8", errors="ignore"), file=sys.stderr)


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"non-finite JSON value: {value}")


if __name__ == "__main__":
    raise SystemExit(main())
