# MediaPipe Tasks Model Assets Design

## Purpose

Replace the removed `mediapipe.solutions` face and hand APIs with the supported
MediaPipe Tasks API while preserving the plug-in's existing runtime boundary:
standard CPython performs semantic analysis and GIMP performs every visible
image treatment.

This design corrects the current runtime mismatch without reintroducing hidden
downloads, dependency drift, or GIMP-managed-Python changes.

## Scope

- Use the official, pinned MediaPipe Face Landmarker and Hand Landmarker task
  bundles.
- Bundle those files as package-owned, read-only application assets.
- Verify model identity and known-vulnerability policy before every fresh
  analysis.
- Keep replay independent of MediaPipe, OpenCV, model files, and the advisory
  record.
- Retain the existing normalized exclusion protocol and GIMP-only treatment
  pipeline.

## Non-goals

- No custom model training, custom ONNX model, model generation, or model
  conversion.
- No runtime model download, model auto-update, or network dependency.
- No modification of GIMP's embedded Python or its installation.
- No change to the batch-only GIMP rendering policy.

## Pinned Asset Contract

Two official task bundles are added beneath the package assets directory:

- Face Landmarker: approximately 3.76 MB.
- Hand Landmarker: approximately 7.82 MB.

`mediapipe-model-manifest.json` is the single source of truth for each model.
Each entry records its stable identifier, MediaPipe task type, official source
URL, upstream version, byte count, SHA-256 digest, package-relative path, and
license/attribution reference.

The resolver treats the manifest as immutable runtime configuration. A model
update is one reviewed change containing the replacement file, manifest values,
advisory update, and real smoke-test evidence. The application never downloads
or upgrades a model itself.

## Components and Responsibilities

### ModelResolver

`ModelResolver` is the only component that reads the model manifest or accesses
model files. It resolves package assets through the standard library, validates
their byte count and SHA-256 digest, and exposes verified filesystem paths for
MediaPipe Tasks. It also evaluates the bundled advisory record before returning
paths.

This centralizes model lookup and integrity validation. No detector, batch
coordinator, planner, or GIMP host may duplicate this logic.

### ModelSecurityPolicy

`mediapipe-model-advisories.json` is a bundled, manually maintained record of
known model-version advisories. Each entry identifies the model, affected
version, advisory reference, severity, and suggested pinned replacement.

The policy is offline and deterministic:

- `low` advisories warn and allow fresh analysis.
- `medium`, `high`, and `critical` advisories block fresh analysis before image
  decoding or rendering.
- An advisory never triggers a download or upgrade.

The block message names the affected model/version, advisory reference, and
suggested manual update. Replay skips this policy because it never loads model
assets.

### MediaPipeTasksLandmarkProvider

`MediaPipeTasksLandmarkProvider` is the sole adapter that imports and uses the
MediaPipe Tasks API. It receives verified model paths from `ModelResolver`,
creates the official face and hand task instances, and emits normalized landmark
sequences. It owns the mapping from Tasks results to the existing `Point` type.

It does not perform asset discovery, hash checks, saliency analysis, recipe
planning, JSON protocol handling, or any GIMP call.

### Protection Region Builder

`build_protection_regions()` remains responsible only for combining injected
face/hand landmark detectors with the existing OpenCV saliency-center field and
for producing `SoftExclusion` values. Its public behavior and pure-Python test
seam remain intact; it does not know model paths, manifests, or MediaPipe task
types.

## Fresh Analysis Flow

1. The batch coordinator stages and fingerprints the PNG exactly as it does now.
2. The analyzer resolves and validates both model assets.
3. The analyzer applies the local advisory policy.
4. The Tasks provider runs face and hand landmark detection using only verified
   model paths.
5. The protection builder combines detected landmarks with OpenCV saliency.
6. The existing bridge validates the normalized response, then planning, GIMP
   rendering, and transactional publication proceed unchanged.

No detector result is allowed to modify pixels. A no-detection result for face
or hand remains valid if saliency succeeds.

## Failure Handling

- Missing, size-mismatched, or hash-mismatched model: analyzer dependency
  failure before rendering.
- Medium-or-higher advisory: explicit blocked-analysis failure before rendering.
- Task initialization or detector failure: detector failure before rendering.
- Face or hand absent: valid `no_detection`; continue with saliency protection.
- Replay: never instantiates the resolver, policy, MediaPipe, or OpenCV.

Model identifiers, versions, SHA-256 digests, and advisory-record version are
stored in fresh render provenance so a result can be audited later.

## Testing and Verification

- Unit tests verify manifest parsing, path containment, byte-count/hash
  validation, advisory severity handling, and clear remediation diagnostics.
- Provider tests use fake Tasks results to verify normalized landmark mapping.
- Existing protection tests continue to inject landmark detectors and remain
  independent of MediaPipe.
- `test_real_tasks_models_load_and_process_fixed_image` loads both bundled
  models, creates both Tasks detectors, and processes `model-smoke.png` without
  requiring GIMP. This test is the regression gate for package/API/model
  compatibility.
- The analyzer subprocess test proves the configured standard CPython invokes
  the module with an argument list and returns protocol-valid JSON.
- `test_built_wheel_includes_verified_mediapipe_model_assets` runs `uv build`
  and proves both models and both JSON records are present in the wheel.

## Update Procedure

An operator updates models manually in a reviewed change. The change must
replace the official asset, update the manifest digest/size/version/source,
update the advisory record, run
`test_real_tasks_models_load_and_process_fixed_image`, verify the wheel
contents, commit the reviewed change, and record any license or attribution
change. Runtime network fetching and automatic updates are prohibited.
