# MediaPipe Tasks Model Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the removed MediaPipe Solutions detectors with pinned, verified MediaPipe Tasks model assets while preserving batch-only GIMP rendering and replay independence.

**Architecture:** Package two official `.task` files and two offline JSON records. `ModelResolver` exclusively owns manifest parsing, resource lookup, integrity verification, and advisory policy; the Tasks provider receives only verified paths and returns normalized landmarks. The analyzer returns the resolver's immutable provenance in bridge schema v2, allowing the batch record to audit fresh renders without allowing replay to load models or dependencies.

**Tech Stack:** Python 3.12+, MediaPipe 0.10.35 Tasks API, OpenCV contrib, standard-library `importlib.resources`, `hashlib`, `warnings`, pytest, uv, GIMP 3 batch console.

## Global Constraints

- Keep `requires-python = ">=3.12"`; do not add, remove, or upgrade Python dependencies.
- Keep `mediapipe>=0.10.35,<0.11` and `opencv-contrib-python>=5.0.0.93,<5.1` unchanged.
- Use only standard CPython for MediaPipe/OpenCV analysis; do not change GIMP's embedded Python or installation.
- GIMP remains batch-only and performs all visible treatment; analysis emits normalized exclusions only.
- Bundle only the official Face Landmarker and Hand Landmarker `.task` files as read-only package assets; no ONNX, custom model, conversion, training, runtime download, or automatic upgrade.
- Resolve models only from the package manifest and package resources. Every fresh analysis verifies byte count and lowercase SHA-256 before image decode or rendering.
- Advisory handling is offline and deterministic: `low` warns and proceeds; `medium`, `high`, and `critical` block fresh analysis with model, version, advisory reference, and manual replacement guidance.
- Replay must not import or instantiate MediaPipe/OpenCV, read models, or read advisories.
- Existing 3-channel BGR and 4-channel BGRA PNG analysis inputs remain supported. Before a MediaPipe `ImageFormat.SRGB` is constructed, convert BGR with `cv2.COLOR_BGR2RGB` and BGRA with `cv2.COLOR_BGRA2RGB`; the Tasks image always receives a 3-channel RGB array.
- Preserve existing normalized `Point`/`SoftExclusion` protocol, saliency behavior, transactional output publication, and source fingerprint checks.
- Store model ID, pinned version, SHA-256, and advisory-record version in fresh render provenance.
- Use TDD: make each listed test fail before its implementation, then run the focused test before committing.

---

## File Structure

- Create `src/gimp_weathered_photo_plugin/model_assets.py`: immutable manifest/advisory data types, package resource resolver, integrity verifier, advisory policy, and verified-model provenance.
- Create `src/gimp_weathered_photo_plugin/tasks_landmarks.py`: the only MediaPipe Tasks import/use site; maps Tasks results to normalized `Point` sequences.
- Create `src/gimp_weathered_photo_plugin/assets/mediapipe-model-manifest.json`: the source-of-truth pin for both official bundles.
- Create `src/gimp_weathered_photo_plugin/assets/mediapipe-model-advisories.json`: versioned, locally maintained advisory record, initially empty.
- Create `src/gimp_weathered_photo_plugin/assets/models/face_landmarker.task` and `src/gimp_weathered_photo_plugin/assets/models/hand_landmarker.task`: exact official model binaries named in the manifest.
- Modify `src/gimp_weathered_photo_plugin/protection.py`: retain geometry and OpenCV saliency only; remove all `mediapipe.solutions` calls.
- Modify `src/gimp_weathered_photo_plugin/analyzer.py`: resolve models before decoding, construct the provider, and emit verified adapter configuration.
- Modify `src/gimp_weathered_photo_plugin/bridge_protocol.py`: add bounded adapter configuration and move the response protocol to v2.
- Modify `src/gimp_weathered_photo_plugin/batch.py`: use analyzer-returned configuration instead of parent-created provenance.
- Modify `src/gimp_weathered_photo_plugin/__main__.py`: stop duplicating adapter provenance; retain only user-supplied analyzer-version identity.
- Modify `src/gimp_weathered_photo_plugin/metadata.py`: validate and persist the explicit model provenance fields already carried in adapter configuration.
- Create `tests/test_model_assets.py` and `tests/test_tasks_landmarks.py`: unit-level resolver/policy and fake-Tasks mapping coverage.
- Modify `tests/test_protection.py`, `tests/test_analyzer.py`, `tests/test_bridge_protocol.py`, `tests/test_batch.py`, `tests/test_cli.py`, `tests/test_metadata.py`, `tests/test_package.py`, and `tests/test_import_boundaries.py`: update seams and add regression coverage.
- Create `tests/fixtures/model-smoke.png`: a fixed tiny PNG consumed by the real Tasks compatibility smoke test.
- Modify `README.md` and `docs/superpowers/specs/2026-07-13-mediapipe-tasks-model-assets-design.md`: document manual model update and vulnerability behavior without offering automatic fetch/upgrade.

### Task 1: Package model pins, integrity verification, and offline advisory policy

**Files:**
- Create: `src/gimp_weathered_photo_plugin/model_assets.py`
- Create: `src/gimp_weathered_photo_plugin/assets/mediapipe-model-manifest.json`
- Create: `src/gimp_weathered_photo_plugin/assets/mediapipe-model-advisories.json`
- Create: `src/gimp_weathered_photo_plugin/assets/models/face_landmarker.task`
- Create: `src/gimp_weathered_photo_plugin/assets/models/hand_landmarker.task`
- Create: `tests/test_model_assets.py`
- Modify: `tests/test_package.py`

**Interfaces:**
- Produces: `ModelResolver`, `ModelAssetError`, `ModelSecurityError`, `ResolvedModels`, and `ResolvedModel` from `gimp_weathered_photo_plugin.model_assets`.
- Produces: `ModelResolver.resolve() -> contextlib.AbstractContextManager[ResolvedModels]`; `ResolvedModels.paths` maps `"face-landmarker"` and `"hand-landmarker"` to verified `Path` values; `ResolvedModels.adapter_configuration` is `Mapping[str, str]`.
- Consumes later: `MediaPipeTasksLandmarkProvider(models: ResolvedModels)` and `MediaPipeOpenCvAdapter(resolver: ModelResolver | None = None)`.

- [ ] **Step 1: Write failing resolver and policy tests**

Create `tests/test_model_assets.py` with a temporary asset tree so behavior is tested before real binaries exist:

```python
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
                "id": "face-landmarker", "task_type": "face_landmarker",
                "source_url": "https://example.invalid/face", "version": "pinned-face",
                "bytes": face.stat().st_size,
                "sha256": hashlib.sha256(face.read_bytes()).hexdigest(),
                "path": "models/face_landmarker.task", "license": "Apache-2.0",
            },
            {
                "id": "hand-landmarker", "task_type": "hand_landmarker",
                "source_url": "https://example.invalid/hand", "version": "pinned-hand",
                "bytes": hand.stat().st_size,
                "sha256": hashlib.sha256(hand.read_bytes()).hexdigest(),
                "path": "models/hand_landmarker.task", "license": "Apache-2.0",
            },
        ],
    }
    (tmp_path / "mediapipe-model-manifest.json").write_text(json.dumps(manifest))
    advisories = {"schema_version": 1, "advisories": []}
    if severity is not None:
        advisories["advisories"].append({
            "model_id": "face-landmarker", "affected_version": "pinned-face",
            "severity": severity, "reference": "CVE-2026-0001",
            "suggested_replacement": "replace manually with reviewed pin",
        })
    (tmp_path / "mediapipe-model-advisories.json").write_text(json.dumps(advisories))
    return tmp_path


def test_resolver_returns_verified_paths_and_auditable_configuration(tmp_path: Path) -> None:
    with ModelResolver(_write_assets(tmp_path)).resolve() as models:
        assert models.paths["face-landmarker"].read_bytes() == b"face-model"
        assert models.adapter_configuration == {
            "advisories.schema_version": "1",
            "model.face-landmarker.sha256": hashlib.sha256(b"face-model").hexdigest(),
            "model.face-landmarker.version": "pinned-face",
            "model.hand-landmarker.sha256": hashlib.sha256(b"hand-model").hexdigest(),
            "model.hand-landmarker.version": "pinned-hand",
        }


def test_resolver_rejects_a_hash_mismatch_before_returning_paths(tmp_path: Path) -> None:
    root = _write_assets(tmp_path)
    (root / "models" / "hand_landmarker.task").write_bytes(b"tampered")
    with pytest.raises(ModelAssetError, match="hand-landmarker.*SHA-256"):
        ModelResolver(root).resolve().__enter__()


@pytest.mark.parametrize("severity", ["medium", "high", "critical"])
def test_medium_or_higher_advisory_blocks_with_manual_remediation(
    tmp_path: Path, severity: str
) -> None:
    with pytest.raises(ModelSecurityError, match="face-landmarker.*pinned-face.*CVE-2026-0001.*manually"):
        ModelResolver(_write_assets(tmp_path, severity=severity)).resolve().__enter__()


def test_low_advisory_warns_but_allows_fresh_analysis(tmp_path: Path) -> None:
    with pytest.warns(UserWarning, match="CVE-2026-0001"):
        with ModelResolver(_write_assets(tmp_path, severity="low")).resolve() as models:
            assert models.paths["hand-landmarker"].is_file()
```

- [ ] **Step 2: Run the resolver tests to prove they fail before implementation**

Run: `uv run pytest tests/test_model_assets.py -v`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'gimp_weathered_photo_plugin.model_assets'`.

- [ ] **Step 3: Implement the single asset/security boundary and add the pinned files**

Create `model_assets.py` with the following public contract; keep JSON parsing and path containment private to this module:

```python
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
    pass


class ModelSecurityError(RuntimeError):
    pass


class ModelResolver:
    def __init__(self, assets_root: Path | None = None) -> None:
        self._assets_root = assets_root

    @contextmanager
    def resolve(self) -> Iterator[ResolvedModels]:
        """Verify both packaged pins and keep their materialized paths alive."""
```

`resolve()` must load `mediapipe-model-manifest.json` and `mediapipe-model-advisories.json` from either the injected test root or `importlib.resources.files("gimp_weathered_photo_plugin").joinpath("assets")`. It must require exactly the two stable IDs, reject unknown/missing/duplicate entries, require lowercase 64-character SHA-256 values, reject model paths that escape the asset root, compare exact byte count and `hashlib.sha256(path.read_bytes()).hexdigest()`, then evaluate advisories before yielding paths. Use `warnings.warn(message, UserWarning, stacklevel=2)` for a low advisory. A blocking error must state `model_id`, `affected_version`, `reference`, and `suggested_replacement`, and must say `manual update`.

Add the initially empty advisory record exactly as:

```json
{
  "schema_version": 1,
  "advisories": []
}
```

Download the two official immutable objects manually during this task, then record the observed size and SHA-256 in the manifest; the application must never contain this download operation. Use the GCS generation-pinned URLs below, not a mutable runtime URL:

```powershell
Invoke-WebRequest -Uri 'https://storage.googleapis.com/download/storage/v1/b/mediapipe-models/o/face_landmarker%2Fface_landmarker%2Ffloat16%2Flatest%2Fface_landmarker.task?generation=1683136941468629&alt=media' -OutFile 'src/gimp_weathered_photo_plugin/assets/models/face_landmarker.task'
Invoke-WebRequest -Uri 'https://storage.googleapis.com/download/storage/v1/b/mediapipe-models/o/hand_landmarker%2Fhand_landmarker%2Ffloat16%2Flatest%2Fhand_landmarker.task?generation=1682480005356399&alt=media' -OutFile 'src/gimp_weathered_photo_plugin/assets/models/hand_landmarker.task'
Get-FileHash -Algorithm SHA256 'src/gimp_weathered_photo_plugin/assets/models/face_landmarker.task'
Get-FileHash -Algorithm SHA256 'src/gimp_weathered_photo_plugin/assets/models/hand_landmarker.task'
Get-Item 'src/gimp_weathered_photo_plugin/assets/models/face_landmarker.task','src/gimp_weathered_photo_plugin/assets/models/hand_landmarker.task' | Select-Object Name,Length
```

Write `mediapipe-model-manifest.json` with `schema_version: 1`, and one entry per file using these immutable identifiers and metadata: `face-landmarker` / `face_landmarker` / version `gcs-generation-1683136941468629` / expected size `3758596`; `hand-landmarker` / `hand_landmarker` / version `gcs-generation-1682480005356399` / expected size `7819105`; paths `models/face_landmarker.task` and `models/hand_landmarker.task`; the exact generation-pinned URL above; `license: "Apache-2.0"`; and the hashes printed by `Get-FileHash`. Do not substitute MD5 or a value from an HTTP header for SHA-256.

- [ ] **Step 4: Run unit and package-asset verification**

Run: `uv run pytest tests/test_model_assets.py tests/test_package.py -v`

Expected: PASS. Add a `tests/test_package.py` assertion that both `.task` files and both JSON files are present under `src/gimp_weathered_photo_plugin/assets` and that `ModelResolver().resolve()` returns two existing paths.

- [ ] **Step 5: Commit the self-contained model asset boundary**

```bash
git add src/gimp_weathered_photo_plugin/model_assets.py src/gimp_weathered_photo_plugin/assets/mediapipe-model-manifest.json src/gimp_weathered_photo_plugin/assets/mediapipe-model-advisories.json src/gimp_weathered_photo_plugin/assets/models tests/test_model_assets.py tests/test_package.py
git commit -m "feat(models): add verified mediapipe task assets"
```

### Task 2: Isolate the supported Tasks adapter and keep protection geometry pure

**Files:**
- Create: `src/gimp_weathered_photo_plugin/tasks_landmarks.py`
- Create: `tests/test_tasks_landmarks.py`
- Modify: `src/gimp_weathered_photo_plugin/protection.py`
- Modify: `tests/test_protection.py`
- Modify: `tests/test_import_boundaries.py`

**Interfaces:**
- Consumes: `ResolvedModels` from `model_assets.py`; `Image`, `LandmarkDetector`, and `Point` from existing modules.
- Produces: `MediaPipeTasksLandmarkProvider(models: ResolvedModels, *, vision_module: object | None = None, base_options_factory: Callable[[str], object] | None = None, image_factory: Callable[[Image], object] | None = None)` context manager with `__enter__() -> MediaPipeTasksLandmarkProvider`, `close() -> None`, `detect_faces(image: Image) -> tuple[tuple[Point, ...], ...]`, and `detect_hands(image: Image) -> tuple[tuple[Point, ...], ...]`. The three optional factories are test seams; production uses the MediaPipe imports.
- Produces: `build_protection_regions(image, *, face_detector, hand_detector, saliency_center)` with no default MediaPipe detector. The analyzer supplies both landmark detector callables.

- [ ] **Step 1: Write failing provider mapping and protection-boundary tests**

Create `tests/test_tasks_landmarks.py` using a fake `vision` module injected into the provider constructor:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from gimp_weathered_photo_plugin.model_assets import ResolvedModels
from gimp_weathered_photo_plugin.tasks_landmarks import MediaPipeTasksLandmarkProvider


@dataclass
class _Landmark:
    x: float
    y: float


class _FaceDetector:
    closed = False

    def detect(self, _image: object) -> object:
        return type("Result", (), {"face_landmarks": [[_Landmark(0.2, 0.3), _Landmark(0.4, 0.5)]]})()

    def close(self) -> None:
        self.closed = True


class _HandDetector:
    closed = False

    def detect(self, _image: object) -> object:
        return type("Result", (), {"hand_landmarks": [[_Landmark(0.6, 0.7)]]})()

    def close(self) -> None:
        self.closed = True


class _Vision:
    RunningMode = type("RunningMode", (), {"IMAGE": "IMAGE"})
    FaceLandmarkerOptions = staticmethod(lambda **_kwargs: object())
    HandLandmarkerOptions = staticmethod(lambda **_kwargs: object())
    FaceLandmarker = type("FaceLandmarker", (), {"create_from_options": staticmethod(lambda _options: _FaceDetector())})
    HandLandmarker = type("HandLandmarker", (), {"create_from_options": staticmethod(lambda _options: _HandDetector())})


def test_provider_maps_tasks_landmarks_to_normalized_points() -> None:
    models = ResolvedModels(
        paths={"face-landmarker": Path("C:/face.task"), "hand-landmarker": Path("C:/hand.task")},
        adapter_configuration={},
    )
    provider = MediaPipeTasksLandmarkProvider(
        models,
        vision_module=_Vision,
        base_options_factory=lambda _path: object(),
        image_factory=lambda value: value,
    )
    image = np.zeros((3, 3, 3), dtype=np.uint8)
    with provider:
        assert provider.detect_faces(image)[0][0].x == 0.2
        assert provider.detect_faces(image)[0][0].y == 0.3
        assert provider.detect_hands(image)[0][0].x == 0.6


def test_provider_converts_bgra_to_three_channel_rgb_before_creating_tasks_image() -> None:
    received: list[np.ndarray] = []
    provider = MediaPipeTasksLandmarkProvider(
        ResolvedModels(paths={"face-landmarker": Path("C:/face.task"), "hand-landmarker": Path("C:/hand.task")}, adapter_configuration={}),
        vision_module=_Vision,
        base_options_factory=lambda _path: object(),
        image_factory=lambda value: received.append(value) or value,
    )
    bgra = np.array([[[10, 20, 30, 40]]], dtype=np.uint8)
    with provider:
        provider.detect_faces(bgra)
    assert received[0].shape == (1, 1, 3)
    assert received[0][0, 0].tolist() == [30, 20, 10]


def test_provider_closes_both_task_instances() -> None:
    face = _FaceDetector()
    hand = _HandDetector()
    class _TrackedVision(_Vision):
        FaceLandmarker = type("FaceLandmarker", (), {"create_from_options": staticmethod(lambda _options: face)})
        HandLandmarker = type("HandLandmarker", (), {"create_from_options": staticmethod(lambda _options: hand)})
    provider = MediaPipeTasksLandmarkProvider(
        ResolvedModels(paths={"face-landmarker": Path("C:/face.task"), "hand-landmarker": Path("C:/hand.task")}, adapter_configuration={}),
        vision_module=_TrackedVision,
        base_options_factory=lambda _path: object(),
        image_factory=lambda value: value,
    )
    with provider:
        pass
    assert face.closed and hand.closed


def test_provider_rejects_non_normalized_tasks_landmarks() -> None:
    class _OutOfRangeFaceDetector(_FaceDetector):
        def detect(self, _image: object) -> object:
            return type("Result", (), {"face_landmarks": [[_Landmark(1.2, 0.3)]]})()
    class _BadVision(_Vision):
        FaceLandmarker = type("FaceLandmarker", (), {"create_from_options": staticmethod(lambda _options: _OutOfRangeFaceDetector())})
    provider = MediaPipeTasksLandmarkProvider(
        ResolvedModels(paths={"face-landmarker": Path("C:/face.task"), "hand-landmarker": Path("C:/hand.task")}, adapter_configuration={}),
        vision_module=_BadVision,
        base_options_factory=lambda _path: object(),
        image_factory=lambda value: value,
    )
    with provider:
        assert provider.detect_faces(np.zeros((3, 3, 3), dtype=np.uint8)) == ()
```

In `tests/test_protection.py`, replace any test that depends on default detector imports with injected lambdas and add:

```python
def test_protection_requires_injected_landmark_detectors() -> None:
    image = np.zeros((3, 3, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="face_detector and hand_detector are required"):
        build_protection_regions(image)
```

- [ ] **Step 2: Run the new tests and prove the removed API boundary is not yet implemented**

Run: `uv run pytest tests/test_tasks_landmarks.py tests/test_protection.py -v`

Expected: FAIL because `tasks_landmarks` does not exist and `build_protection_regions()` still attempts a default detector.

- [ ] **Step 3: Implement the Tasks-only provider and remove Solutions calls**

Implement `MediaPipeTasksLandmarkProvider` so its production constructor lazily imports exactly:

```python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions
```

For each model, create IMAGE-mode options with the verified `model_asset_path` in `__enter__()` and retain the two task instances until `close()`/`__exit__()`. `close()` must be idempotent and call `close()` on each task instance when that method exists. `detect_faces()` and `detect_hands()` must raise `RuntimeError("MediaPipe Tasks provider is not active")` outside the context.

Before passing image data to the injected or production image factory, use a private conversion helper with these exact branches:

```python
if image.ndim != 3 or image.shape[2] not in {3, 4}:
    raise ValueError("MediaPipe Tasks requires a three- or four-channel image")
if image.shape[2] == 3:
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
else:
    rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
```

Call `detect()` with `mediapipe.Image(image_format=mediapipe.ImageFormat.SRGB, data=rgb)`, map `result.face_landmarks` and `result.hand_landmarks` to `Point(x=landmark.x, y=landmark.y)`, discard a whole landmark group if any point is outside `[0.0, 1.0]`, and translate import/init/detect errors to `ProtectionDependencyError` with `MediaPipe Tasks` in the message.

Refactor `protection.py` so it has no `_load_mediapipe`, `_detect_faces`, `_detect_hands`, or `mediapipe` import. Keep `_to_rgb`, `_find_saliency_center`, `_region_from_landmarks`, and overlap behavior. At the start of `build_protection_regions()`, raise `ValueError("face_detector and hand_detector are required")` unless both detector callables are supplied, then run those injected callables and saliency exactly as before.

Add an import-boundary assertion:

```python
def test_only_tasks_landmarks_imports_mediapipe() -> None:
    assert "mediapipe" not in Path("src/gimp_weathered_photo_plugin/protection.py").read_text(encoding="utf-8")
    assert "from mediapipe.tasks.python import vision" in Path("src/gimp_weathered_photo_plugin/tasks_landmarks.py").read_text(encoding="utf-8")
```

- [ ] **Step 4: Run focused behavior and static boundary checks**

Run: `uv run pytest tests/test_tasks_landmarks.py tests/test_protection.py tests/test_import_boundaries.py -v`

Expected: PASS; no test imports `mediapipe.solutions`.

- [ ] **Step 5: Commit the adapter boundary**

```bash
git add src/gimp_weathered_photo_plugin/tasks_landmarks.py src/gimp_weathered_photo_plugin/protection.py tests/test_tasks_landmarks.py tests/test_protection.py tests/test_import_boundaries.py
git commit -m "feat(analyzer): use mediapipe tasks landmarks"
```

### Task 3: Return verified model provenance through bridge schema v2

**Files:**
- Modify: `src/gimp_weathered_photo_plugin/bridge_protocol.py`
- Modify: `src/gimp_weathered_photo_plugin/analyzer.py`
- Modify: `src/gimp_weathered_photo_plugin/semantic_bridge.py`
- Modify: `tests/test_bridge_protocol.py`
- Modify: `tests/test_analyzer.py`
- Modify: `tests/test_semantic_bridge.py`

**Interfaces:**
- Consumes: `ModelResolver.resolve()` and `MediaPipeTasksLandmarkProvider` from Tasks 1–2.
- Produces: bridge schema version `2`; `AnalysisResponse.adapter_configuration: Mapping[str, str]`.
- Produces: `AnalyzerResult(detectors: Mapping[str, DetectorStatus], exclusions: tuple[SoftExclusion, ...], adapter_configuration: Mapping[str, str])` returned by `ProtectionAnalyzer.analyze(source)`.
- Produces: `MediaPipeOpenCvAdapter(resolver: ModelResolver | None = None, cv2_loader: Callable[[], Any] | None = None)`; its default loader imports OpenCV only after `ModelResolver.resolve()` has passed.

- [ ] **Step 1: Write failing schema/provenance and early-failure tests**

Add this expectation to `tests/test_bridge_protocol.py`:

```python
def test_response_requires_bounded_string_adapter_configuration() -> None:
    response = parse_response_json(
        '{"bridge_schema_version":2,"source_sha256":"' + "a" * 64 +
        '","detectors":{"face":"no_detection","hand":"no_detection","saliency":"detected"},'
        '"adapter_configuration":{"model.face-landmarker.version":"gcs-generation-1683136941468629"},"exclusions":[]}'
    )
    assert response.adapter_configuration["model.face-landmarker.version"] == "gcs-generation-1683136941468629"
```

Add an analyzer test with a resolver fake that raises before `cv2.imread` can run:

```python
def test_adapter_blocks_on_model_policy_before_opencv_is_loaded(tmp_path: Path) -> None:
    class _BlockingResolver:
        def resolve(self) -> object:
            raise ModelSecurityError("face-landmarker pinned-face CVE-2026-0001 manual update")
    def _forbidden_cv2_loader() -> object:
        pytest.fail("OpenCV must not load before model policy passes")
    with pytest.raises(AnalyzerError, match="manual update"):
        MediaPipeOpenCvAdapter(
            resolver=_BlockingResolver(), cv2_loader=_forbidden_cv2_loader
        ).analyze(tmp_path / "input.png")
```

Also update the module-main success test to assert JSON includes the five exact resolver configuration keys from Task 1, and add a malformed configuration test (non-string value) expecting `BridgeProtocolError`.

- [ ] **Step 2: Run the schema and analyzer tests to establish their failing state**

Run: `uv run pytest tests/test_bridge_protocol.py tests/test_analyzer.py tests/test_semantic_bridge.py -v`

Expected: FAIL because version 1 is still required and `AnalysisResponse` has no `adapter_configuration`.

- [ ] **Step 3: Implement protocol v2 and analyzer-owned model provenance**

Set `BRIDGE_SCHEMA_VERSION = 2`. Add `adapter_configuration` to `AnalysisResponse`, parse it with a private validator that accepts 1–16 non-empty string keys and values, each no more than 256 UTF-8 bytes, and include it in `_write_response()`.

In `analyzer.py`, define:

```python
@dataclass(frozen=True, slots=True)
class AnalyzerResult:
    detectors: Mapping[str, DetectorStatus]
    exclusions: tuple[SoftExclusion, ...]
    adapter_configuration: Mapping[str, str]
```

Change `ProtectionAnalyzer.analyze()` to return `AnalyzerResult`. Give `MediaPipeOpenCvAdapter` a private default `cv2_loader` that imports and returns `cv2`; accept an optional loader in its constructor strictly for tests. In `MediaPipeOpenCvAdapter.analyze()`, enter `with self._resolver.resolve() as models:` before calling either the OpenCV loader or `cv2.imread`. Inside that context, call `cv2 = self._cv2_loader()`, decode the source, then enter the provider context and call:

```python
with MediaPipeTasksLandmarkProvider(models) as provider:
    exclusions = build_protection_regions(
        cast(Image, image),
        face_detector=provider.detect_faces,
        hand_detector=provider.detect_hands,
    )
```

Return `AnalyzerResult(detectors=..., exclusions=exclusions, adapter_configuration=models.adapter_configuration)`. Translate `ModelAssetError`, `ModelSecurityError`, and `ProtectionDependencyError` to `AnalyzerError` without dropping their remediation message. Extend `_analyzer_error_exit_code()` so model asset/policy failures return dependency exit code `3`; preserve source errors as `4`, semantic failures as `5`, and unexpected exceptions as `70`.

Update `analyze_request()` to validate detector status and construct schema-v2 `AnalysisResponse` using all three `AnalyzerResult` fields. `SemanticAnalysisBridge` needs no subprocess behavior change; it must continue parsing only the child JSON and rejecting a v1 response.

- [ ] **Step 4: Run bridge and subprocess behavior tests**

Run: `uv run pytest tests/test_bridge_protocol.py tests/test_analyzer.py tests/test_semantic_bridge.py -v`

Expected: PASS, including the test proving the advisory blocks before image decoding.

- [ ] **Step 5: Commit the versioned bridge contract**

```bash
git add src/gimp_weathered_photo_plugin/bridge_protocol.py src/gimp_weathered_photo_plugin/analyzer.py src/gimp_weathered_photo_plugin/semantic_bridge.py tests/test_bridge_protocol.py tests/test_analyzer.py tests/test_semantic_bridge.py
git commit -m "feat(bridge): record verified model provenance"
```

### Task 4: Persist fresh provenance while guaranteeing replay stays independent

**Files:**
- Modify: `src/gimp_weathered_photo_plugin/batch.py`
- Modify: `src/gimp_weathered_photo_plugin/metadata.py`
- Modify: `src/gimp_weathered_photo_plugin/__main__.py`
- Modify: `tests/test_batch.py`
- Modify: `tests/test_metadata.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: schema-v2 `AnalysisResponse.adapter_configuration` from Task 3.
- Produces: `process_batch(..., analyzer_version: str | None = None, ...)` for fresh renders; no `analysis_provenance` argument.
- Produces: persisted `analysis.adapter_configuration` containing the five resolver provenance keys on every fresh render; replay reads its existing sidecar and does not create a bridge/resolver/provider.

- [ ] **Step 1: Write failing batch, record, and replay tests**

Update fake analyzer responses in `tests/test_batch.py` to include:

```python
adapter_configuration={
    "advisories.schema_version": "1",
    "model.face-landmarker.sha256": "a" * 64,
    "model.face-landmarker.version": "gcs-generation-1683136941468629",
    "model.hand-landmarker.sha256": "b" * 64,
    "model.hand-landmarker.version": "gcs-generation-1682480005356399",
}
```

Add:

```python
def test_fresh_record_persists_analyzer_returned_model_provenance(...) -> None:
    results = process_batch(..., analyzer_version="0.10.35")
    record = load_render_record(results[0].recipe_path)
    assert record.adapter_configuration["model.face-landmarker.sha256"] == "a" * 64
    assert record.adapter_configuration["advisories.schema_version"] == "1"


def test_replay_does_not_construct_or_call_the_semantic_bridge(...) -> None:
    bridge = _ExplodingBridge()
    results = process_batch(..., semantic_bridge=bridge, replay_record=record)
    assert results[0].success
    assert bridge.calls == 0
```

In `tests/test_metadata.py`, add a malformed record case missing `model.hand-landmarker.version` and assert `load_render_record()` raises `ValueError("recipe sidecar must contain a complete render record")`. In `tests/test_cli.py`, assert fresh execution passes only the CLI analyzer version into `process_batch`; it must not manufacture model hashes or advisory data.

- [ ] **Step 2: Run the persistence tests before changing the coordinator**

Run: `uv run pytest tests/test_batch.py tests/test_metadata.py tests/test_cli.py -v`

Expected: FAIL because `process_batch` still accepts parent-built `AnalysisProvenance` and metadata does not require the model provenance keys.

- [ ] **Step 3: Make the analyzer response the sole source of model provenance**

Remove `analysis_provenance` from `process_batch()` and `_prepare_fresh_record()`. Add required `analyzer_version: str | None` to the fresh path; reject missing/empty values with `ValueError("fresh rendering analyzer version is required")`. Construct the `RenderRecord` with `analyzer_version` and `response.adapter_configuration`.

In `metadata.py`, define:

```python
_MODEL_PROVENANCE_KEYS = frozenset({
    "advisories.schema_version",
    "model.face-landmarker.sha256",
    "model.face-landmarker.version",
    "model.hand-landmarker.sha256",
    "model.hand-landmarker.version",
})
```

Require those keys in `RenderRecord.__post_init__` when `bridge_schema_version >= 2`, and require their SHA entries to pass the existing digest validator. Do not apply this new condition to `bridge_schema_version == 1` records so existing complete records can still replay; do not allow new fresh records to use version 1 because Task 3 sets the global version to 2.

In `__main__.py`, remove the `AnalysisProvenance` import and construction. Pass `analyzer_version=arguments.analyzer_version` only for fresh rendering. Keep the existing replay branch unchanged so it does not require `--analyzer-executable` or model resources.

- [ ] **Step 4: Run provenance persistence and replay regression tests**

Run: `uv run pytest tests/test_batch.py tests/test_metadata.py tests/test_cli.py -v`

Expected: PASS; replay test proves no semantic analyzer is called.

- [ ] **Step 5: Commit record integration separately from detection**

```bash
git add src/gimp_weathered_photo_plugin/batch.py src/gimp_weathered_photo_plugin/metadata.py src/gimp_weathered_photo_plugin/__main__.py tests/test_batch.py tests/test_metadata.py tests/test_cli.py
git commit -m "feat(metadata): persist model analysis provenance"
```

### Task 5: Add real compatibility smoke coverage, wheel verification, and manual update documentation

**Files:**
- Create: `tests/fixtures/model-smoke.png`
- Modify: `tests/test_analyzer.py`
- Modify: `tests/test_package.py`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-07-13-mediapipe-tasks-model-assets-design.md`

**Interfaces:**
- Consumes: actual package resources, `ModelResolver`, and `MediaPipeTasksLandmarkProvider` from Tasks 1–2.
- Produces: an executable regression gate that loads both model files with installed MediaPipe 0.10.35 and a documentation-only manual update procedure.

- [ ] **Step 1: Write the real model/API compatibility test and wheel content assertion**

Add a fixed valid 2×2 RGB PNG at `tests/fixtures/model-smoke.png` using this exact base64 payload once (it is not generated at runtime):

```text
iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVQIHWP8z8DwnwEImBigAAAfFwICVv7Y4QAAAABJRU5ErkJggg==
```

Add this test to `tests/test_analyzer.py`:

```python
def test_real_tasks_models_load_and_process_fixed_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import cv2

    cache = tmp_path / ".matplotlib"
    cache.mkdir()
    monkeypatch.setenv("MPLCONFIGDIR", str(cache))
    image_path = Path(__file__).parent / "fixtures" / "model-smoke.png"
    image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    assert image is not None
    with ModelResolver().resolve() as models:
        with MediaPipeTasksLandmarkProvider(models) as provider:
            faces = provider.detect_faces(cast(Image, image))
            hands = provider.detect_hands(cast(Image, image))
    assert isinstance(faces, tuple)
    assert isinstance(hands, tuple)
```

Add a build test that runs `uv build`, opens the created wheel with `zipfile.ZipFile`, and asserts these exact archive members exist:

```python
"gimp_weathered_photo_plugin/assets/mediapipe-model-manifest.json"
"gimp_weathered_photo_plugin/assets/mediapipe-model-advisories.json"
"gimp_weathered_photo_plugin/assets/models/face_landmarker.task"
"gimp_weathered_photo_plugin/assets/models/hand_landmarker.task"
```

- [ ] **Step 2: Run the real smoke and package tests to establish the gate**

Run: `uv run pytest tests/test_analyzer.py::test_real_tasks_models_load_and_process_fixed_image tests/test_package.py -v`

Expected: FAIL if the wheel omits a resource or the installed MediaPipe Tasks API/model pin is incompatible; otherwise PASS after Tasks 1–2 are complete.

- [ ] **Step 3: Make startup cache handling deterministic and document manual maintenance**

Before importing MediaPipe Tasks in the analyzer process, set `MPLCONFIGDIR` only when it is unset, using a directory under the staged source's parent:

```python
os.environ.setdefault("MPLCONFIGDIR", str(request.source_path.parent / ".matplotlib"))
```

Create that directory with `mkdir(parents=True, exist_ok=True)` before the Tasks import. Do not write it in a GIMP directory, the model directory, a user profile, or outside the staged job directory.

In `README.md`, add a concise **Bundled MediaPipe model updates** section stating that the application never fetches or upgrades models, that low advisories warn, that medium/high/critical advisories block fresh rendering, and that an operator must manually replace the official file, update manifest size/hash/version/source plus advisory record, run the smoke test, and commit the reviewed change. Link to the design document. Update the design document's testing/update wording to name the final test and wheel check; do not alter its approved architecture decisions.

- [ ] **Step 4: Run all required verification commands**

Run: `uv run pytest -v`

Expected: PASS all tests. If the configured 100% coverage gate is not invoked by this command, separately run the project’s coverage command and report its pass/fail result without lowering the configured threshold.

Run: `uv run ruff check .`

Expected: PASS.

Run: `uv run ruff format --check .`

Expected: PASS.

Run: `uv run ty check src tests`

Expected: PASS.

Run: `uv build`

Expected: PASS and a wheel containing both models and both JSON records.

Run: `git diff --check`

Expected: PASS with no whitespace errors.

- [ ] **Step 5: Review scope and commit verification/docs**

Inspect `git diff --check` and `git diff --stat` to confirm the change contains only model pins, analyzer/provenance wiring, tests, fixture, and docs. Then commit:

```bash
git add tests/fixtures/model-smoke.png tests/test_analyzer.py tests/test_package.py README.md docs/superpowers/specs/2026-07-13-mediapipe-tasks-model-assets-design.md
git commit -m "test(models): verify bundled tasks compatibility"
```

## Final Integration Review

- [ ] Verify a fresh batch render cannot reach OpenCV decode, planner, GIMP, or publication when a model hash fails or an advisory has severity `medium`, `high`, or `critical`.
- [ ] Verify the injected OpenCV loader is not called when resolver policy blocks, and that both BGR and BGRA arrays reach the Tasks image factory as three-channel RGB.
- [ ] Verify a low advisory emits a warning and fresh analysis continues using the same pinned asset; verify no code path contains `requests`, `urllib`, `Invoke-WebRequest`, or mutable model download logic.
- [ ] Verify one fresh sidecar contains all five model/advisory provenance keys and that replay of that sidecar completes when the semantic bridge is an exploding fake.
- [ ] Verify the only source module importing MediaPipe Tasks is `tasks_landmarks.py`, and no tracked source imports `mediapipe.solutions`.
- [ ] Verify the real smoke test uses `tmp_path / ".matplotlib"` for `MPLCONFIGDIR` and that provider context exit closes both fake task instances.
- [ ] Re-run `uv run pytest -v`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src tests`, `uv build`, and `git diff --check`; report actual pass/fail status before claiming completion.
