from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from gimp_weathered_photo_plugin.bridge_protocol import (
    AnalysisRequest,
    AnalysisResponse,
    BridgeProtocolError,
    parse_response_json,
)

_TIMEOUT_SECONDS = 120


class BridgeExecutionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StagedInput:
    path: Path
    sha256: str


def stage_input(source: Path, staging_root: Path) -> StagedInput:
    if source.suffix.lower() != ".png":
        raise BridgeExecutionError("only filesystem-backed PNG inputs are supported")
    if not source.is_file():
        raise BridgeExecutionError("source PNG does not exist")
    job_directory = staging_root / str(uuid4())
    job_directory.mkdir(parents=True)
    staged_path = job_directory / "source.png"
    shutil.copyfile(source, staged_path)
    return StagedInput(
        path=staged_path,
        sha256=hashlib.sha256(staged_path.read_bytes()).hexdigest(),
    )


@dataclass(frozen=True, slots=True)
class SemanticAnalysisBridge:
    executable: Path
    arguments: tuple[str, ...] = ()
    timeout_seconds: int = _TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if not self.executable.is_absolute():
            raise BridgeExecutionError("analyzer executable must be an absolute path")
        if any(
            not isinstance(argument, str) or not argument for argument in self.arguments
        ):
            raise BridgeExecutionError("analyzer arguments must be non-empty strings")
        if self.timeout_seconds <= 0:
            raise BridgeExecutionError("analyzer timeout must be positive")

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        try:
            completed = subprocess.run(
                [str(self.executable), *self.arguments],
                input=json.dumps(request.to_dict()),
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=self.timeout_seconds,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise BridgeExecutionError("semantic analyzer timed out") from error
        if completed.returncode != 0:
            diagnostic = _truncate_diagnostic(completed.stderr)
            suffix = f": {diagnostic}" if diagnostic else ""
            raise BridgeExecutionError(
                "semantic analyzer failed with exit code "
                f"{completed.returncode}{suffix}"
            )
        try:
            response = parse_response_json(completed.stdout)
        except BridgeProtocolError as error:
            raise BridgeExecutionError(
                "semantic analyzer returned invalid JSON"
            ) from error
        if response.source_sha256 != request.source_sha256:
            raise BridgeExecutionError("semantic analyzer fingerprint mismatch")
        return response


def _truncate_diagnostic(value: str) -> str:
    return value.encode("utf-8")[:8192].decode("utf-8", errors="ignore")
