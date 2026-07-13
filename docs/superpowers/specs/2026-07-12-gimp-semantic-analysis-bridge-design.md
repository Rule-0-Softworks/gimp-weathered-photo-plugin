# GIMP Semantic Analysis Bridge Design

## Purpose

Allow automatic face, hand, and emotional-center protection without modifying
GIMP's externally managed Python. The existing GIMP 3.2 runtime is a MinGW
CPython build that cannot install the official Windows MediaPipe/OpenCV wheels.
This amendment moves semantic analysis to the locked standard CPython 3.14
environment while keeping every image-treatment operation inside GIMP.

## Scope

Version 1 accepts only existing filesystem-backed PNG files. It rejects an
unsaved GIMP image, an image modified since it was saved, and every non-PNG
input before analysis. Interactive unsaved-image support is intentionally
deferred to `docs/tasks/interactive-unsaved-image-inputs.md`.

## Architecture

Two narrow boundaries isolate the incompatible runtime.

- `ProtectionAnalyzer` is a pure-Python port. `MediaPipeOpenCvAdapter` is its
  sole production adapter and the only module that imports `mediapipe` or
  `cv2`.
- `SemanticAnalysisBridge` is a process bridge. It sends an immutable analysis
  request to the configured standard-CPython analyzer and returns validated
  exclusion geometry. The GIMP host never imports the analyzer dependency
  graph.
- `GimpRenderer` receives a resolved recipe and applies every visible operation
  with GIMP-native layers, masks, brushes, transforms, blend modes, and local
  blur. The analyzer never creates or modifies treatment pixels.

## Immutable Input and Output Publication

For a fresh render, the batch coordinator creates a UUID job directory and
copies the accepted input PNG into it. It computes SHA-256 over those exact
encoded bytes, then sends that expected fingerprint, dimensions, and staged
path to the analyzer. The analyzer echoes the fingerprint after reading that
same file. The coordinator validates the response and renders from the staged
copy, not the original path. It verifies the staged input fingerprint again
immediately before GIMP launch.

PNG, XCF, and recipe are first written under that job directory. Only after all
three exist and validation succeeds are they published to the output directory
as one set. A failed job leaves no final output and never replaces a prior set,
including when `--overwrite` was requested.

## Replay

Fresh render flow is: stage and fingerprint -> analyze -> validate -> plan ->
render -> publish.

Replay flow is: stage and fingerprint -> load saved render record -> validate
source fingerprint, dimensions, asset IDs and asset fingerprints -> render ->
publish. Replay never launches the analyzer and therefore succeeds when its
executable, MediaPipe, or OpenCV is unavailable. The render record persists
the exact exclusions used for planning as well as the recipe.

## Bridge Protocol

The analyzer executable is configured as an absolute path. Development
instructions may use the standard CPython 3.14 interpreter from `uv`, but the
runtime never assumes GIMP's Python, activation scripts, a current working
directory, or a shell. The bridge invokes it with `subprocess.Popen` and an
argument list (`shell=False`).

Requests and responses are UTF-8 JSON. The bridge sends exactly one request on
stdin; a successful analyzer emits exactly one response on stdout, limited to
64 KiB. Diagnostics are UTF-8 stderr, retained up to 8 KiB. The bridge rejects
multiple JSON documents, unsupported bridge-schema versions, invalid UTF-8,
or invalid JSON. It applies a 120-second timeout and terminates the child on
cancellation or timeout.

Exit codes are: `0` success, `2` invalid request, `3` missing analyzer
dependency, `4` unreadable or corrupt source, `5` detector failure, and `70`
unexpected analyzer failure. Any nonzero exit, timeout, malformed response, or
fingerprint mismatch fails the job before GIMP renders.

## Geometry and Detector Status

The response uses bridge schema version 1 and contains at most 32
`SoftExclusion` regions. A region is a normalized ellipse: `(0, 0)` is the
top-left pixel boundary, `(1, 1)` the bottom-right boundary; `center`,
`radius_x`, `radius_y`, and `feather` are finite numbers in `(0, 1]` except
the center coordinates, which are in `[0, 1]`. `feather` is the normalized
elliptical distance added beyond the solid radius before strength reaches zero.
Allowed sources are `face`, `hand`, and `emotional_center`.

Each detector reports one of `detected`, `no_detection`, `disabled`, or
`failed`. Face/hand `no_detection` is valid only when the saliency/center
detector succeeds. A decoder, saliency, or enabled detector `failed` status is
fatal; it is not silently treated as a miss.

The response parser rejects NaN/infinity, unknown fields that affect rendering,
out-of-range data, unsupported detector identifiers, duplicate terminal JSON,
and oversized payloads.

## Versioning and Tests

`bridge_schema_version`, `recipe_schema_version`, analyzer version, adapter
configuration, detector statuses, source fingerprint, and asset fingerprints
are recorded independently. CI uses fake bridges and injected detector adapters
to test both fresh and replay flows without GIMP. Isolated import tests prove
the GIMP host imports without MediaPipe/OpenCV and the analyzer imports without
`gi`. Native smoke verification runs the real bridge and GIMP console, then
creates exactly four approved proof sets.
