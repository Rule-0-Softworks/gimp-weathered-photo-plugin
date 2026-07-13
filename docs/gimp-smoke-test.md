# GIMP 3 native smoke test

The project supports Python 3.12+ and runs semantic analysis in the locked
standard CPython environment. GIMP 3 performs every treatment operation. The
public renderer is batch-only: it does not add assets to an already-open GIMP
window and does not modify GIMP's installation or a permanent user brush
folder.

## Install and discover the host

Create the locked environment from the repository root:

```powershell
uv sync --locked
```

Confirm that GIMP 3 plug-in discovery can find the package source directory
when invoked by the batch host. Use GIMP's console executable (for example,
`gimp-console-3.2.exe`), not GIMP's embedded Python, for rendering. The
temporary GIMP brush configuration is created for each render under the
project temporary directory, receives copies of only the package `.gbr`
brushes, and is removed during staging cleanup on both success and failure.

The six curated assets are original package-owned SVG designs exported with
GIMP 3.2.4's native noninteractive loader and saver. Their editable source
shapes are retained in [`docs/asset-sources`](asset-sources); no third-party
brush pack or generative image work was used. The three water-stain exports
are grayscale (with optional grayscale alpha) PNGs, not photographs.

Check the analyzer dependencies in the standard CPython environment before a
fresh render:

```powershell
uv run python -c "import mediapipe, cv2; print(mediapipe.__version__, cv2.__version__)"
```

## Batch invocation

Fresh renders accept only existing filesystem-backed PNG inputs. Configure the
GIMP batch host and the analyzer executable with absolute paths:

```powershell
uv run python -m gimp_weathered_photo_plugin `
  --gimp-console "C:\\Users\\Josh Romisher\\AppData\\Local\\Programs\\GIMP 3\\bin\\gimp-console-3.2.exe" `
  --analyzer-executable "$PWD\\.venv\\Scripts\\python.exe" `
  --analyzer-version "local-locked" `
  --output-dir .\\out `
  .\\approved-input.png
```

Use `--overwrite` only to replace a complete existing output set. A fresh
render stages and fingerprints its source before analysis, then publishes PNG,
XCF, and recipe sidecar together. Failed jobs clean up their staging directory
and leave no partial final set.

Replay uses a complete saved render record and never starts MediaPipe or
OpenCV, so the analyzer executable is unnecessary:

```powershell
uv run python -m gimp_weathered_photo_plugin `
  --gimp-console "C:\\Users\\Josh Romisher\\AppData\\Local\\Programs\\GIMP 3\\bin\\gimp-console-3.2.exe" `
  --replay-recipe .\\out\\approved-input-worn.recipe.json `
  --output-dir .\\replayed `
  .\\approved-input.png
```

## Inspect one native render

1. Confirm output PNG dimensions match the source dimensions and inspect its
   alpha silhouette; ragged source alpha must remain intact.
2. Open the XCF in GIMP 3. Confirm editable named layers and layer masks are
   present, including water-stain masks. Confirm no full-image tint, blur, or
   flattening was used.
3. Inspect the recipe record for the source fingerprint, analyzer provenance,
   asset fingerprints, exclusions, and exact replay recipe.
4. If the command fails, begin failure diagnosis with the printed batch error:
   verify absolute executable paths, PNG existence, analyzer dependency
   availability, asset preflight, and GIMP console diagnostics.

## Proof limit and visual approval

Do not create examples until the user supplies approved Vezor PNG inputs.
Once available, make exactly four full proof sets from four approved Vezor PNG
inputs, then stop for visual approval before generating more output. This guide
documents the workflow only; it does not claim the treatment has been visually
validated.
