"""MediaPipe Tasks landmark adapter for protection analysis."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from math import isfinite
from typing import Any, cast

from gimp_weathered_photo_plugin.model_assets import ResolvedModels
from gimp_weathered_photo_plugin.models import Point
from gimp_weathered_photo_plugin.protection import Image, ProtectionDependencyError

_FACE_MODEL_ID = "face-landmarker"
_HAND_MODEL_ID = "hand-landmarker"


class MediaPipeTasksLandmarkProvider:
    def __init__(
        self,
        models: ResolvedModels,
        *,
        vision_module: object | None = None,
        base_options_factory: Callable[[str], object] | None = None,
        image_factory: Callable[[Image], object] | None = None,
    ) -> None:
        self._models = models
        self._vision_module = vision_module
        self._base_options_factory = base_options_factory
        self._image_factory = image_factory
        self._face_landmarker: object | None = None
        self._hand_landmarker: object | None = None

    def __enter__(self) -> MediaPipeTasksLandmarkProvider:
        try:
            vision_module = self._vision_module or _load_vision_module()
            base_options_factory = (
                self._base_options_factory or _load_base_options_factory()
            )
            self._face_landmarker = _create_landmarker(
                vision_module,
                "FaceLandmarker",
                "FaceLandmarkerOptions",
                base_options_factory(str(self._models.paths[_FACE_MODEL_ID])),
            )
            self._hand_landmarker = _create_landmarker(
                vision_module,
                "HandLandmarker",
                "HandLandmarkerOptions",
                base_options_factory(str(self._models.paths[_HAND_MODEL_ID])),
            )
            self._vision_module = vision_module
        except Exception as error:
            self.close()
            raise ProtectionDependencyError(
                "MediaPipe Tasks landmark provider could not be initialized"
            ) from error
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        for attribute in ("_face_landmarker", "_hand_landmarker"):
            landmarker = getattr(self, attribute)
            if landmarker is not None:
                close = getattr(landmarker, "close", None)
                if callable(close):
                    close()
                setattr(self, attribute, None)

    def detect_faces(self, image: Image) -> tuple[tuple[Point, ...], ...]:
        return self._detect(image, "_face_landmarker", "face_landmarks")

    def detect_hands(self, image: Image) -> tuple[tuple[Point, ...], ...]:
        return self._detect(image, "_hand_landmarker", "hand_landmarks")

    def _detect(
        self, image: Image, landmarker_attribute: str, result_attribute: str
    ) -> tuple[tuple[Point, ...], ...]:
        landmarker = getattr(self, landmarker_attribute)
        if landmarker is None:
            raise RuntimeError("MediaPipe Tasks provider is not active")
        rgb = _to_tasks_rgb(image)
        try:
            tasks_image = (self._image_factory or _create_tasks_image)(rgb)
            result = cast(Any, landmarker).detect(tasks_image)
            return _map_landmark_groups(getattr(result, result_attribute) or ())
        except ProtectionDependencyError:
            raise
        except Exception as error:
            raise ProtectionDependencyError(
                "MediaPipe Tasks landmark detection failed"
            ) from error


def _load_vision_module() -> object:
    from mediapipe.tasks.python import vision

    return vision


def _load_base_options_factory() -> Callable[[str], object]:
    from mediapipe.tasks.python.core.base_options import BaseOptions

    return lambda model_asset_path: BaseOptions(model_asset_path=model_asset_path)


def _create_landmarker(
    vision_module: object,
    landmarker_name: str,
    options_name: str,
    base_options: object,
) -> object:
    vision = cast(Any, vision_module)
    options = getattr(vision, options_name)(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE,
    )
    return getattr(vision, landmarker_name).create_from_options(options)


def _create_tasks_image(image: Image) -> object:
    import mediapipe

    return mediapipe.Image(image_format=mediapipe.ImageFormat.SRGB, data=image)


def _to_tasks_rgb(image: Image) -> Image:
    try:
        import cv2
    except ImportError as error:
        raise ProtectionDependencyError(
            "MediaPipe Tasks requires opencv-contrib-python"
        ) from error
    if image.ndim != 3 or image.shape[2] not in {3, 4}:
        raise ValueError("MediaPipe Tasks requires a three- or four-channel image")
    if image.shape[2] == 3:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    else:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
    return cast(Image, rgb)


def _map_landmark_groups(
    groups: Sequence[Sequence[object]],
) -> tuple[tuple[Point, ...], ...]:
    mapped: list[tuple[Point, ...]] = []
    for group in groups:
        points: list[Point] = []
        for landmark in group:
            x = getattr(landmark, "x", None)
            y = getattr(landmark, "y", None)
            if not (
                isinstance(x, (int, float))
                and isinstance(y, (int, float))
                and isfinite(x)
                and isfinite(y)
                and 0.0 <= x <= 1.0
                and 0.0 <= y <= 1.0
            ):
                points = []
                break
            points.append(Point(x=float(x), y=float(y)))
        if points:
            mapped.append(tuple(points))
    return tuple(mapped)
