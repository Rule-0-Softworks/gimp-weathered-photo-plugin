from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, cast

from gimp_weathered_photo_plugin.bridge_protocol import (
    AnalysisRequest,
    AnalysisResponse,
    DetectorStatus,
)
from gimp_weathered_photo_plugin.models import SoftExclusion
from gimp_weathered_photo_plugin.protection import (
    Image,
    ProtectionDependencyError,
    build_protection_regions,
)


class AnalyzerError(RuntimeError):
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
