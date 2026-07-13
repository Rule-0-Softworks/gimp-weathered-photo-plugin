import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from gimp_weathered_photo_plugin.bridge_protocol import AnalysisRequest, Size


def _response(source_sha256: str) -> str:
    return json.dumps(
        {
            "bridge_schema_version": 1,
            "source_sha256": source_sha256,
            "detectors": {
                "face": "no_detection",
                "hand": "no_detection",
                "saliency": "detected",
            },
            "exclusions": [
                {
                    "center": {"x": 0.5, "y": 0.5},
                    "radius_x": 0.3,
                    "radius_y": 0.28,
                    "feather": 0.3,
                    "source": "emotional_center",
                }
            ],
        }
    )


def test_stage_input_uses_isolated_uuid_directories_for_matching_stems(
    tmp_path: Path,
) -> None:
    from gimp_weathered_photo_plugin.semantic_bridge import stage_input

    first = tmp_path / "first" / "print.png"
    second = tmp_path / "second" / "print.png"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    staged_first = stage_input(first, tmp_path / "jobs")
    staged_second = stage_input(second, tmp_path / "jobs")

    assert staged_first.path.read_bytes() == b"first"
    assert staged_second.path.read_bytes() == b"second"
    assert staged_first.path.parent != staged_second.path.parent
    assert staged_first.sha256 == hashlib.sha256(b"first").hexdigest()


def test_bridge_uses_argument_list_and_validates_fingerprint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from gimp_weathered_photo_plugin.semantic_bridge import SemanticAnalysisBridge

    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    request = AnalysisRequest(
        bridge_schema_version=1,
        source_path=source.resolve(),
        source_sha256=hashlib.sha256(b"source").hexdigest(),
        source_size=Size(10, 10),
    )
    captured: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            ["fake-analyzer"], 0, _response(request.source_sha256), ""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    response = SemanticAnalysisBridge(Path("C:/tools/analyzer.exe")).analyze(request)

    assert response.source_sha256 == request.source_sha256
    assert captured["args"] == ([str(Path("C:/tools/analyzer.exe"))],)
    assert captured["kwargs"] == {
        "input": json.dumps(request.to_dict()),
        "text": True,
        "encoding": "utf-8",
        "capture_output": True,
        "timeout": 120,
        "shell": False,
        "check": False,
    }


def test_bridge_rejects_timeout_and_mismatched_response_fingerprint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from gimp_weathered_photo_plugin.semantic_bridge import (
        BridgeExecutionError,
        SemanticAnalysisBridge,
    )

    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    request = AnalysisRequest(
        1, source.resolve(), hashlib.sha256(b"source").hexdigest(), Size(10, 10)
    )

    def timed_out(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(["fake-analyzer"], 120)

    monkeypatch.setattr(subprocess, "run", timed_out)
    bridge = SemanticAnalysisBridge(Path("C:/tools/analyzer.exe"))
    with pytest.raises(BridgeExecutionError, match="timed out"):
        bridge.analyze(request)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 0, _response("b" * 64), ""
        ),
    )
    with pytest.raises(BridgeExecutionError, match="fingerprint mismatch"):
        bridge.analyze(request)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 5, "", "detector analysis failed"
        ),
    )
    with pytest.raises(BridgeExecutionError, match="detector analysis failed"):
        bridge.analyze(request)


def test_bridge_runs_the_real_analyzer_module_with_standard_cpython(
    tmp_path: Path,
) -> None:
    from gimp_weathered_photo_plugin.semantic_bridge import (
        BridgeExecutionError,
        SemanticAnalysisBridge,
    )

    source = tmp_path / "missing.png"
    request = AnalysisRequest(
        1,
        source.resolve(),
        "a" * 64,
        Size(2, 2),
    )

    bridge = SemanticAnalysisBridge(
        Path(sys.executable),
        arguments=("-m", "gimp_weathered_photo_plugin.analyzer"),
    )
    with pytest.raises(
        BridgeExecutionError, match="exit code 4: source image is unreadable"
    ):
        bridge.analyze(request)
