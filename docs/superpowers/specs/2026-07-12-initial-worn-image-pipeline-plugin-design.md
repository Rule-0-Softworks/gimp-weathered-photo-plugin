# Vezor Worn Print GIMP 3 Plug-in Design

## Purpose

Build a GIMP 3 plug-in and host-launched batch entry point that gives an
existing ragged-edge PNG a subtle, individually handled worn-print treatment.
The original photograph's composition and pixels remain the base image; the
original alpha silhouette and dimensions are preserved exactly. Each successful
render produces a treated PNG, an editable XCF, and a recipe JSON sidecar.

## Scope and Boundaries

GIMP is the only treatment engine. The plug-in uses the native GIMP Python API
to create editable layers and layer masks, apply curated brushes, transform
those marks, select blend modes, and apply local blur only through water-stain
masks. It does not use Pillow, a generative editor, a global one-click filter,
or a global tint/blur/overlay.

The treatment may add only sparse, low-opacity edge- or corner-originating
marks from three curated asset families: neutral gray/umber dry rub, restrained
mottled sepia, and water stains. It never adds text, notes, frames, borders,
rectangular inset masks, full-frame overlays, perfect circles/rings, or dark
burn blobs.

## Automated Protection Analysis

The plug-in process uses the official `mediapipe` package for face and hand
landmarks and the official `opencv-python` package for image decoding,
preprocessing, saliency, and soft-mask composition. No custom ONNX models are
permitted. These packages only calculate protection fields; they do not alter
the rendered image. GIMP receives the resulting organic masks and executes all
visual work.

Protection has three inputs: detected face landmarks, detected hand landmarks,
and a soft emotional-center field produced from visual saliency plus the image
center. The resulting alpha-like field is feathered and irregular rather than
a visible rectangular exclusion. Candidate marks must start on an edge/corner,
remain sparse, and be rejected when their weighted overlap with the protection
field exceeds the configured limit.

If MediaPipe cannot make a semantic detection, the saliency/center protection
still applies. If the required packages or curated brush assets are absent, the
operation fails before creating outputs and identifies the missing component.

## Architecture

Pure-Python modules own typed recipe data, asset resolution, protection-map
calculation, stochastic planning, metadata serialization, and batch
orchestration. They are testable in CI without importing `gi` or launching a
desktop GIMP instance. A narrow `gimp_adapter` module is the only module that
imports GIMP bindings; it turns a planned recipe into editable GIMP layers,
masks, brushes, transforms, blend modes, local blur, PNG export, and XCF save.

The default planner obtains fresh entropy from the operating system for every
render. It records the resolved seed and every chosen asset and transform in
the recipe. Re-rendering is deterministic only when a caller explicitly passes
that saved recipe; filenames never affect randomization.

## Outputs and Batch Semantics

For each accepted input, batch processing writes beside the chosen output stem:

- `<stem>-worn.png` — flattened export that retains original dimensions and
  alpha values.
- `<stem>-worn.xcf` — editable GIMP working file with named treatment layers
  and masks.
- `<stem>-worn.recipe.json` — schema-versioned record of source fingerprint,
  dimensions, resolved random seed, exclusions, marks, assets, and outputs.

The batch operation processes each file independently, returns a per-file
result, and does not overwrite an existing output unless `--overwrite` is
passed. A failure for one input is reported without hiding failures from later
inputs. Missing assets are preflighted before any output is produced for that
input.

## Test Strategy

CI uses fakes at the GIMP adapter boundary and ordinary image fixtures rather
than an interactive GIMP session. Tests assert exact alpha preservation,
dimension preservation, fresh plans across multiple default renders,
edge/corner placement, protection overlap rejection, missing-asset failure,
recipe capture and explicit replay, and independent batch results. They also
assert that the adapter contract requests native layers, masks, brush strokes,
transforms, blend modes, and localized blur rather than an opaque global filter.

A separately documented local smoke checklist covers GIMP 3 installation,
plug-in discovery, one manual render, inspection of the XCF layers/masks,
alpha comparison, and export verification. It also documents configuring the
GIMP-host Python environment so it can import the locked official MediaPipe and
OpenCV packages. Four, and only four, full-resolution approved Vezor images
are rendered for visual approval after all local gates pass.

## Constraints

- Keep `requires-python = ">=3.12"`; Python 3.12 is canonical locally and in CI.
- Add only the approved direct production dependencies: `mediapipe` and
  `opencv-python`; commit the updated `uv.lock`.
- Preserve existing automation configuration unless a concrete defect requires
  a focused correction.
- Do not require GIMP for unit tests or CI. Remote GitHub checks remain pending
  until a push triggers them.
- Do not start all 22 images or create proofs until four approved input images
  and a usable GIMP 3 batch executable are available.
