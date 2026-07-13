# GIMP Semantic Analysis Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a replay-safe standard-CPython semantic-analysis bridge while retaining GIMP as the sole image-treatment engine.

**Architecture:** The batch coordinator stages an immutable PNG and invokes a validated JSON analyzer bridge. The adapter runs official MediaPipe/OpenCV outside GIMP; the GIMP host receives only the saved recipe and normalized exclusions.

**Tech Stack:** Python 3.14, uv, pytest, GIMP 3 API, MediaPipe, OpenCV contrib.

## Global Constraints

- Keep `requires-python = ">=3.12"`; Python 3.14 is canonical.
- Do not modify GIMP's Python or install MediaPipe/OpenCV into it.
- Accept only existing filesystem-backed PNG inputs.
- Use `shell=False`, UTF-8 JSON IPC, a 64 KiB response limit, and a 120-second timeout.
- GIMP performs every visible image operation; no Pillow or custom ONNX model.
- Fresh renders use analysis; replay never invokes the analyzer.

---

### Task 1: Define validated bridge records

**Files:** Modify `models.py`, `metadata.py`; create `bridge_protocol.py`; test `tests/test_bridge_protocol.py`.

- [ ] Write failing tests for schema version, finite bounded normalized ellipses, 32-region maximum, allowed sources/statuses, and rejection of NaN, oversized, or multiple JSON documents.
- [ ] Run `uv run pytest tests/test_bridge_protocol.py -v`; expect collection/import failure.
- [ ] Implement immutable request/response/render-record types, strict JSON parsing, source and asset fingerprints, and atomic serialization.
- [ ] Re-run the focused test; expect PASS. Commit `feat: add semantic analysis bridge records`.

### Task 2: Implement the analyzer port and official adapter

**Files:** Modify `protection.py`; create `analyzer.py`; test `tests/test_analyzer.py`.

- [ ] Write failing injected-detector tests for detected/no-detection/failed semantics and decoder/saliency failure.
- [ ] Run `uv run pytest tests/test_analyzer.py -v`; expect FAIL.
- [ ] Implement `ProtectionAnalyzer` and `MediaPipeOpenCvAdapter`; accept a staged PNG and emit one bridge response on stdout with diagnostics on stderr and documented exit codes.
- [ ] Re-run focused tests; expect PASS. Commit `feat: add semantic analysis adapter`.

### Task 3: Implement bridge execution and staging

**Files:** Create `semantic_bridge.py`; modify `batch.py`; test `tests/test_semantic_bridge.py` and `tests/test_batch.py`.

- [ ] Write failing tests for argument-list execution, request fingerprint echo, timeout, cancellation, malformed response, unique UUID staging, and two simultaneous source stems.
- [ ] Run focused tests; expect FAIL.
- [ ] Implement configured absolute executable launch with `shell=False`, bounded stdout/stderr, fresh staged input copy, and pre-render fingerprint verification.
- [ ] Re-run focused tests; expect PASS. Commit `feat: bridge staged semantic analysis`.

### Task 4: Make replay and publication transactional

**Files:** Modify `batch.py`, `metadata.py`; test `tests/test_batch.py`, `tests/test_metadata.py`.

- [ ] Write failing tests proving replay does not call the bridge, fails on source/asset mismatch, preserves previous outputs on failure, and publishes PNG/XCF/recipe only after all staged files validate.
- [ ] Run focused tests; expect FAIL.
- [ ] Implement separate fresh/replay flows, full render-record loading, staged output validation, and final-set publication.
- [ ] Re-run focused tests; expect PASS. Commit `feat: publish replay-safe render sets`.

### Task 5: Connect the native GIMP host

**Files:** Create `gimp_host.py`, `gimp_console_bridge.py`; test `tests/test_gimp_adapter_contract.py`, `tests/test_import_boundaries.py`.

- [ ] Write failing fake-host tests for recipe/exclusion delivery and isolated imports without analyzer packages or `gi`.
- [ ] Run focused tests; expect FAIL.
- [ ] Implement GIMP procedure registration and console request handling; use only GIMP-native layers, masks, brushes, transforms, blends, and local blur.
- [ ] Re-run focused tests; expect PASS. Commit `feat: render bridge recipes in gimp`.

### Task 6: Document and verify

**Files:** Modify `README.md`; create `docs/gimp-smoke-test.md`; test `tests/test_documentation_contract.py`.

- [ ] Write failing documentation-contract tests for analyzer executable configuration, filesystem-PNG scope, replay behavior, staging cleanup, and four-proof limit.
- [ ] Run focused tests; expect FAIL.
- [ ] Document standard-CPython analyzer setup, GIMP console invocation, diagnostics, and native smoke checklist.
- [ ] Run `uv sync --locked`, `uv run pytest --cov --cov-branch --cov-report=xml`, `uv run ruff format --check .`, `uv run ruff check .`, and `uv run ty check`; expect exit 0. Commit `docs: document semantic analysis bridge`.
