from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Literal, cast

import numpy as np
import numpy.typing as npt

from gimp_weathered_photo_plugin.models import (
    ExclusionSource,
    Mark,
    Point,
    SoftExclusion,
)
from gimp_weathered_photo_plugin.planning import weighted_overlap

Image = npt.NDArray[np.uint8]
LandmarkDetector = Callable[[Image], Sequence[Sequence[Point]]]
SaliencyCenter = Callable[[Image], Point]


class ProtectionDependencyError(RuntimeError):
    pass


def build_protection_regions(
    image: Image,
    *,
    face_detector: LandmarkDetector | None = None,
    hand_detector: LandmarkDetector | None = None,
    saliency_center: SaliencyCenter | None = None,
) -> tuple[SoftExclusion, ...]:
    if face_detector is None or hand_detector is None:
        raise ValueError("face_detector and hand_detector are required")
    _validate_image(image)
    faces = face_detector(image)
    hands = hand_detector(image)
    center = (saliency_center or _find_saliency_center)(image)

    regions = [
        _region_from_landmarks(landmarks, "face", radius=0.18)
        for landmarks in faces
        if landmarks
    ]
    regions.extend(
        _region_from_landmarks(landmarks, "hand", radius=0.15)
        for landmarks in hands
        if landmarks
    )
    regions.append(
        SoftExclusion(
            center=center,
            radius_x=0.3,
            radius_y=0.28,
            feather=0.3,
            source="emotional_center",
        )
    )
    return tuple(regions)


def overlap_fraction(mark: Mark, exclusions: Sequence[SoftExclusion]) -> float:
    return weighted_overlap(mark, exclusions)


def _region_from_landmarks(
    landmarks: Sequence[Point], source: Literal["face", "hand"], *, radius: float
) -> SoftExclusion:
    center = Point(
        x=sum(point.x for point in landmarks) / len(landmarks),
        y=sum(point.y for point in landmarks) / len(landmarks),
    )
    return SoftExclusion(
        center=center,
        radius_x=radius,
        radius_y=radius,
        feather=0.28,
        source=cast(ExclusionSource, source),
    )


def _find_saliency_center(image: Image) -> Point:
    try:
        import cv2
    except ImportError as error:
        raise ProtectionDependencyError("opencv-contrib-python is required") from error
    saliency_module = cast(Any, cv2.saliency)
    detector = saliency_module.StaticSaliencySpectralResidual_create()
    success, saliency = detector.computeSaliency(image)
    if not success:
        return Point(x=0.5, y=0.5)
    _, _, _, maximum = cv2.minMaxLoc(saliency)
    height, width = image.shape[:2]
    return Point(x=maximum[0] / max(width - 1, 1), y=maximum[1] / max(height - 1, 1))


def _to_rgb(image: Image) -> Image:
    try:
        import cv2
    except ImportError as error:
        raise ProtectionDependencyError("opencv-contrib-python is required") from error
    return cast(Image, cv2.cvtColor(image, cv2.COLOR_BGR2RGB))


def _validate_image(image: Image) -> None:
    if image.ndim != 3 or image.shape[2] not in {3, 4}:
        raise ValueError("protection analysis requires a three- or four-channel image")
    if image.shape[0] < 2 or image.shape[1] < 2:
        raise ValueError(
            "protection analysis requires at least two pixels per dimension"
        )
