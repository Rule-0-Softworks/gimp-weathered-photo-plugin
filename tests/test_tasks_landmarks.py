from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from gimp_weathered_photo_plugin.model_assets import ResolvedModels
from gimp_weathered_photo_plugin.protection import ProtectionDependencyError
from gimp_weathered_photo_plugin.tasks_landmarks import MediaPipeTasksLandmarkProvider


@dataclass
class _Landmark:
    x: float
    y: float


class _FaceDetector:
    closed = False
    close_calls = 0

    def detect(self, _image: object) -> object:
        return type(
            "Result",
            (),
            {"face_landmarks": [[_Landmark(0.2, 0.3), _Landmark(0.4, 0.5)]]},
        )()

    def close(self) -> None:
        self.closed = True
        self.close_calls += 1


class _HandDetector:
    closed = False
    close_calls = 0

    def detect(self, _image: object) -> object:
        return type("Result", (), {"hand_landmarks": [[_Landmark(0.6, 0.7)]]})()

    def close(self) -> None:
        self.closed = True
        self.close_calls += 1


class _Vision:
    RunningMode = type("RunningMode", (), {"IMAGE": "IMAGE"})
    FaceLandmarkerOptions = staticmethod(lambda **_kwargs: object())
    HandLandmarkerOptions = staticmethod(lambda **_kwargs: object())
    FaceLandmarker = type(
        "FaceLandmarker",
        (),
        {"create_from_options": staticmethod(lambda _options: _FaceDetector())},
    )
    HandLandmarker = type(
        "HandLandmarker",
        (),
        {"create_from_options": staticmethod(lambda _options: _HandDetector())},
    )


def _models() -> ResolvedModels:
    return ResolvedModels(
        paths={
            "face-landmarker": Path("C:/face.task"),
            "hand-landmarker": Path("C:/hand.task"),
        },
        adapter_configuration={},
    )


def test_provider_maps_tasks_landmarks_to_normalized_points() -> None:
    provider = MediaPipeTasksLandmarkProvider(
        _models(),
        vision_module=_Vision,
        base_options_factory=lambda _path: object(),
        image_factory=lambda value: value,
    )
    image = np.zeros((3, 3, 3), dtype=np.uint8)

    with provider:
        assert provider.detect_faces(image)[0][0].x == 0.2
        assert provider.detect_faces(image)[0][0].y == 0.3
        assert provider.detect_hands(image)[0][0].x == 0.6


def test_provider_converts_bgra_to_three_channel_rgb_before_creating_tasks_image(
) -> None:
    received: list[np.ndarray] = []
    provider = MediaPipeTasksLandmarkProvider(
        _models(),
        vision_module=_Vision,
        base_options_factory=lambda _path: object(),
        image_factory=lambda value: received.append(value) or value,
    )
    bgra = np.array([[[10, 20, 30, 40]]], dtype=np.uint8)

    with provider:
        provider.detect_faces(bgra)

    assert received[0].shape == (1, 1, 3)
    assert received[0][0, 0].tolist() == [30, 20, 10]


def test_provider_converts_bgr_to_three_channel_rgb_before_creating_tasks_image(
) -> None:
    received: list[np.ndarray] = []
    provider = MediaPipeTasksLandmarkProvider(
        _models(),
        vision_module=_Vision,
        base_options_factory=lambda _path: object(),
        image_factory=lambda value: received.append(value) or value,
    )
    bgr = np.array([[[10, 20, 30]]], dtype=np.uint8)

    with provider:
        provider.detect_faces(bgr)

    assert received[0].shape == (1, 1, 3)
    assert received[0][0, 0].tolist() == [30, 20, 10]


def test_provider_closes_both_task_instances() -> None:
    face = _FaceDetector()
    hand = _HandDetector()

    class _TrackedVision(_Vision):
        FaceLandmarker = type(
            "FaceLandmarker",
            (),
            {"create_from_options": staticmethod(lambda _options: face)},
        )
        HandLandmarker = type(
            "HandLandmarker",
            (),
            {"create_from_options": staticmethod(lambda _options: hand)},
        )

    provider = MediaPipeTasksLandmarkProvider(
        _models(),
        vision_module=_TrackedVision,
        base_options_factory=lambda _path: object(),
        image_factory=lambda value: value,
    )

    with provider:
        pass
    provider.close()

    assert face.closed and hand.closed
    assert face.close_calls == hand.close_calls == 1


def test_provider_rejects_non_normalized_tasks_landmarks() -> None:
    class _OutOfRangeFaceDetector(_FaceDetector):
        def detect(self, _image: object) -> object:
            return type("Result", (), {"face_landmarks": [[_Landmark(1.2, 0.3)]]})()

    class _BadVision(_Vision):
        FaceLandmarker = type(
            "FaceLandmarker",
            (),
            {
                "create_from_options": staticmethod(
                    lambda _options: _OutOfRangeFaceDetector()
                )
            },
        )

    provider = MediaPipeTasksLandmarkProvider(
        _models(),
        vision_module=_BadVision,
        base_options_factory=lambda _path: object(),
        image_factory=lambda value: value,
    )

    with provider:
        assert provider.detect_faces(np.zeros((3, 3, 3), dtype=np.uint8)) == ()


def test_provider_rejects_invalid_images_before_importing_opencv(monkeypatch) -> None:
    provider = MediaPipeTasksLandmarkProvider(
        _models(),
        vision_module=_Vision,
        base_options_factory=lambda _path: object(),
        image_factory=lambda value: value,
    )

    monkeypatch.setitem(sys.modules, "cv2", None)
    with provider, pytest.raises(
        ValueError, match="MediaPipe Tasks requires a three- or four-channel image"
    ):
        provider.detect_faces(np.zeros((3, 3), dtype=np.uint8))


def test_provider_rejects_detection_when_inactive() -> None:
    provider = MediaPipeTasksLandmarkProvider(
        _models(),
        vision_module=_Vision,
        base_options_factory=lambda _path: object(),
        image_factory=lambda value: value,
    )

    with pytest.raises(
        RuntimeError, match=r"^MediaPipe Tasks provider is not active$"
    ):
        provider.detect_faces(np.zeros((3, 3, 3), dtype=np.uint8))


def test_provider_translates_import_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        "gimp_weathered_photo_plugin.tasks_landmarks._load_vision_module",
        lambda: (_ for _ in ()).throw(ImportError("missing mediapipe")),
    )
    provider = MediaPipeTasksLandmarkProvider(_models())

    with pytest.raises(ProtectionDependencyError, match="MediaPipe Tasks"):
        provider.__enter__()


def test_provider_translates_initialization_errors() -> None:
    class _BadVision(_Vision):
        FaceLandmarker = type(
            "FaceLandmarker",
            (),
            {
                "create_from_options": staticmethod(
                    lambda _options: (_ for _ in ()).throw(RuntimeError("bad model"))
                )
            },
        )

    provider = MediaPipeTasksLandmarkProvider(
        _models(),
        vision_module=_BadVision,
        base_options_factory=lambda _path: object(),
        image_factory=lambda value: value,
    )

    with pytest.raises(ProtectionDependencyError, match="MediaPipe Tasks"):
        provider.__enter__()


def test_provider_translates_detection_errors() -> None:
    class _FailingFaceDetector(_FaceDetector):
        def detect(self, _image: object) -> object:
            raise RuntimeError("bad inference")

    class _BadVision(_Vision):
        FaceLandmarker = type(
            "FaceLandmarker",
            (),
            {
                "create_from_options": staticmethod(
                    lambda _options: _FailingFaceDetector()
                )
            },
        )

    provider = MediaPipeTasksLandmarkProvider(
        _models(),
        vision_module=_BadVision,
        base_options_factory=lambda _path: object(),
        image_factory=lambda value: value,
    )

    with provider, pytest.raises(ProtectionDependencyError, match="MediaPipe Tasks"):
        provider.detect_faces(np.zeros((3, 3, 3), dtype=np.uint8))
