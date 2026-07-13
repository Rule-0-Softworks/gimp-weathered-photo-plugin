import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gimp_weathered_photo_plugin.bridge_protocol import AnalysisRequest
from gimp_weathered_photo_plugin.models import Point, Size, SoftExclusion


class FakeAdapter:
    def __init__(self, *, failed: bool = False) -> None:
        self.failed = failed

    def analyze(self, source: Path) -> tuple[dict[str, str], tuple[SoftExclusion, ...]]:
        if self.failed:
            return (
                {"face": "failed", "hand": "no_detection", "saliency": "detected"},
                (),
            )
        return (
            {"face": "no_detection", "hand": "no_detection", "saliency": "detected"},
            (
                SoftExclusion(
                    center=Point(0.5, 0.5),
                    radius_x=0.3,
                    radius_y=0.28,
                    feather=0.3,
                    source="emotional_center",
                ),
            ),
        )


def _request(source: Path) -> AnalysisRequest:
    return AnalysisRequest(
        bridge_schema_version=1,
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
