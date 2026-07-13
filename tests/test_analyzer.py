import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from gimp_weathered_photo_plugin.analyzer import AnalyzerResult
from gimp_weathered_photo_plugin.bridge_protocol import (
    AnalysisRequest,
    DetectorStatus,
)
from gimp_weathered_photo_plugin.model_assets import ModelResolver
from gimp_weathered_photo_plugin.models import Point, Size, SoftExclusion


class FakeAdapter:
    def __init__(self, *, failed: bool = False) -> None:
        self.failed = failed

    def analyze(self, source: Path) -> AnalyzerResult:
        if self.failed:
            detectors: dict[str, DetectorStatus] = {
                "face": "failed",
                "hand": "no_detection",
                "saliency": "detected",
            }
            return AnalyzerResult(
                detectors=detectors,
                exclusions=(),
                adapter_configuration=_adapter_configuration(),
            )
        detectors: dict[str, DetectorStatus] = {
            "face": "no_detection",
            "hand": "no_detection",
            "saliency": "detected",
        }
        return AnalyzerResult(
            detectors=detectors,
            exclusions=(
                SoftExclusion(
                    center=Point(0.5, 0.5),
                    radius_x=0.3,
                    radius_y=0.28,
                    feather=0.3,
                    source="emotional_center",
                ),
            ),
            adapter_configuration=_adapter_configuration(),
        )


def _adapter_configuration() -> dict[str, str]:
    return {
        "advisories.schema_version": "1",
        "model.face-landmarker.sha256": "a" * 64,
        "model.face-landmarker.version": "pinned-face",
        "model.hand-landmarker.sha256": "b" * 64,
        "model.hand-landmarker.version": "pinned-hand",
    }


def _request(source: Path) -> AnalysisRequest:
    return AnalysisRequest(
        bridge_schema_version=2,
        source_path=source.resolve(),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        source_size=Size(20, 10),
    )


def test_analyzer_keeps_matplotlib_cache_with_the_staged_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from gimp_weathered_photo_plugin.analyzer import analyze_request

    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    monkeypatch.delenv("MPLCONFIGDIR", raising=False)

    analyze_request(_request(source), FakeAdapter())

    assert Path(os.environ["MPLCONFIGDIR"]) == source.parent / ".matplotlib"


def test_analyzer_keeps_saliency_protection_when_no_face_or_hand_is_detected(
    tmp_path: Path,
) -> None:
    from gimp_weathered_photo_plugin.analyzer import analyze_request

    source = tmp_path / "source.png"
    source.write_bytes(b"source")

    response = analyze_request(_request(source), FakeAdapter())

    assert response.detectors == {
        "face": "no_detection",
        "hand": "no_detection",
        "saliency": "detected",
    }
    assert response.exclusions[0].source == "emotional_center"


def test_analyzer_fails_closed_when_an_enabled_detector_fails(tmp_path: Path) -> None:
    from gimp_weathered_photo_plugin.analyzer import AnalyzerError, analyze_request

    source = tmp_path / "source.png"
    source.write_bytes(b"source")

    with pytest.raises(AnalyzerError, match="face detector failed"):
        analyze_request(_request(source), FakeAdapter(failed=True))


def test_analyzer_rejects_a_source_that_changed_after_request_creation(
    tmp_path: Path,
) -> None:
    from gimp_weathered_photo_plugin.analyzer import AnalyzerError, analyze_request

    source = tmp_path / "source.png"
    source.write_bytes(b"before")
    request = _request(source)
    source.write_bytes(b"after")

    with pytest.raises(AnalyzerError, match="source fingerprint mismatch"):
        analyze_request(request, FakeAdapter())


def test_adapter_blocks_on_model_policy_before_opencv_is_loaded(tmp_path: Path) -> None:
    from gimp_weathered_photo_plugin.analyzer import (
        AnalyzerError,
        MediaPipeOpenCvAdapter,
    )
    from gimp_weathered_photo_plugin.model_assets import ModelSecurityError

    class _BlockingResolver:
        def resolve(self) -> object:
            raise ModelSecurityError(
                "face-landmarker pinned-face CVE-2026-0001 manual update"
            )

    def _forbidden_cv2_loader() -> object:
        pytest.fail("OpenCV must not load before model policy passes")

    with pytest.raises(AnalyzerError, match="manual update"):
        MediaPipeOpenCvAdapter(
            resolver=cast(ModelResolver, _BlockingResolver()),
            cv2_loader=_forbidden_cv2_loader,
        ).analyze(tmp_path / "input.png")


def test_analyzer_module_rejects_non_utf8_input_with_exit_code_two() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "gimp_weathered_photo_plugin.analyzer"],
        input=b"\xff",
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stdout == b""
    assert b"UTF-8" in completed.stderr


def test_analyzer_module_writes_one_response_for_a_valid_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import gimp_weathered_photo_plugin.analyzer as analyzer

    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    payload = json.dumps(_request(source).to_dict()).encode("utf-8")
    stdin = io.TextIOWrapper(io.BytesIO(payload), encoding="utf-8")
    stdout = io.StringIO()

    monkeypatch.setattr(analyzer, "MediaPipeOpenCvAdapter", FakeAdapter)
    monkeypatch.setattr(analyzer.sys, "stdin", stdin)
    monkeypatch.setattr(analyzer.sys, "stdout", stdout)

    assert analyzer.main() == 0
    response = json.loads(stdout.getvalue())
    assert response["source_sha256"] == _request(source).source_sha256
    assert response["detectors"]["saliency"] == "detected"
    assert set(response["adapter_configuration"]) == {
        "advisories.schema_version",
        "model.face-landmarker.sha256",
        "model.face-landmarker.version",
        "model.hand-landmarker.sha256",
        "model.hand-landmarker.version",
    }
