# Vezor Worn Print GIMP 3 Plug-in Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a GIMP 3-native, stochastic worn-print plug-in and batch workflow that preserves a source PNG's dimensions and ragged alpha silhouette while producing PNG, XCF, and recipe outputs.

**Architecture:** Keep recipe planning, semantic protection analysis, asset resolution, and batch orchestration pure Python so they run in CI. Isolate every `gi.repository` call in one adapter that applies the resolved plan through native GIMP layers, masks, brushes, transforms, blend modes, and masked local blur.

**Tech Stack:** Python 3.12+, uv, pytest/pytest-cov, Ruff, ty, GIMP 3 Python API, official `mediapipe`, official `opencv-contrib-python`

## Global Constraints

- Work only on `feature/initial-worn-image-pipeline-plugin`.
- Keep `requires-python = ">=3.12"`; use Python 3.12 locally and in CI.
- Add only `mediapipe` and `opencv-contrib-python` as direct production dependencies; commit `uv.lock`. Never install another `cv2` wheel family.
- Do not use Pillow, custom ONNX models, generative image editing, Canva effects, or a global filter.
- GIMP must perform all visual treatment operations. Do not add text, frames, borders, full-frame overlays, global tint/blur, rings, rectangular masks, or burn blobs.
- Default renders use fresh OS entropy; deterministic replay is allowed only with an explicit saved recipe.
- CI must not require an interactive GIMP desktop session.
- Do not modify Release Please, Codecov, CodeQL, Dependabot, or unrelated scaffold configuration without a concrete defect.

---

## File Structure

- `src/gimp_weathered_photo_plugin/models.py`: immutable, serializable recipe,
  geometry, asset, and output data.
- `src/gimp_weathered_photo_plugin/assets/worn-print-manifest.json`: exact
  package-data map for the three `.gbr` brushes and three water-stain PNG masks
  named in the design spec.
- `src/gimp_weathered_photo_plugin/assets.py`: curated asset manifest and
  preflight resolution.
- `src/gimp_weathered_photo_plugin/protection.py`: MediaPipe/OpenCV protection
  fields and candidate-overlap checks; no GIMP imports.
- `src/gimp_weathered_photo_plugin/planning.py`: entropy, candidate sampling,
  rejection, and explicit recipe replay.
- `src/gimp_weathered_photo_plugin/metadata.py`: recipe JSON schema and source
  fingerprinting.
- `src/gimp_weathered_photo_plugin/gimp_host.py`: sole GIMP API boundary and
  GIMP 3 procedure registration.
- `src/gimp_weathered_photo_plugin/batch.py`: input discovery, preflight,
  result aggregation, and output naming.
- `src/gimp_weathered_photo_plugin/__main__.py`: command validation and batch
  dispatch.
- `tests/`: pure-Python and fake-adapter coverage for every required invariant.
- `docs/gimp-smoke-test.md`: local installation and native-host verification.

---

### Task 1: Establish the typed recipe and approved dependency boundary

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `src/gimp_weathered_photo_plugin/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces `Point`, `Size`, `SoftExclusion`, `Mark`, and `TreatmentRecipe`
  frozen dataclasses. `TreatmentRecipe.to_dict()` and `.from_dict()` preserve
  all fields exactly.

- [ ] Write tests that construct a recipe with two marks and assert JSON-safe
  round-trip equality, positive dimensions, opacity in `(0, 1]`, and a mark
  origin of `edge` or `corner`.
- [ ] Run `uv run pytest tests/test_models.py -v`; observe import failure.
- [ ] Add `mediapipe>=0.10.35,<0.11` and
  `opencv-contrib-python>=5.0.0.93,<5.1` to `[project].dependencies`, run
  `uv lock`, and implement the frozen dataclasses and validation.
- [ ] Re-run the focused test; expect all tests to pass. Run
  `uv run ruff format .`, `uv run ruff check .`, and `uv run ty check`.
- [ ] Inspect the staged diff and commit
  `feat: add worn print recipe models`.

### Task 2: Plan sparse, fresh, edge-safe treatments before rendering

**Files:**
- Create: `src/gimp_weathered_photo_plugin/assets.py`
- Create: `src/gimp_weathered_photo_plugin/planning.py`
- Create: `tests/test_assets.py`
- Create: `tests/test_planning.py`

**Interfaces:**
- `resolve_assets(root: Path) -> dict[str, Path]` validates exactly these IDs:
  `dry-rub-neutral-gray`, `dry-rub-umber`, `mottled-sepia`, `water-stain-01`,
  `water-stain-02`, and `water-stain-03`; it returns their packaged paths or
  raises `MissingBrushAssetsError(ids)`.
- `plan_treatment(size: Size, exclusion: SoftExclusion, assets: Mapping[str,
  Path], recipe: TreatmentRecipe | None = None) -> TreatmentRecipe` creates a
  fresh recipe when `recipe is None`, otherwise validates and returns the
  supplied replay recipe.

- [ ] Write a failing asset test with a temporary manifest and one placeholder
  file per declared path, then assert an absent `water-stain-03` produces its
  exact ID in `MissingBrushAssetsError`. Write failing planning tests for six
  default plans with at least
  two distinct resolved seeds/mark sequences, explicit replay equality, and
  candidate marks whose anchors lie in the configured edge band and do not
  exceed permitted soft-exclusion overlap.
- [ ] Run focused tests and observe collection/import failures.
- [ ] Add `assets/worn-print-manifest.json` with the exact IDs/relative paths
  from the design spec, declare its six original GIMP-authored grayscale asset
  files as package data, and create the two broken dry-rub brushes, one
  restrained mottled brush, and three non-circular water-stain masks with
  GIMP. Implement preflight, `secrets.randbits(128)`
  default entropy, bounded random scale/rotation/opacity/density/direction,
  weighted rejection sampling, and a hard maximum mark count. Do not inspect
  filenames for entropy.
- [ ] Run focused tests until green, then full formatter/linter/type checks.
- [ ] Inspect staged diff and commit `feat: plan stochastic edge treatments`.

### Task 3: Generate organic automated face, hand, and center protection

**Files:**
- Create: `src/gimp_weathered_photo_plugin/protection.py`
- Create: `tests/test_protection.py`

**Interfaces:**
- `build_protection_field(image: npt.NDArray[np.uint8]) -> SoftExclusion`
  combines official MediaPipe face/hand landmarks with `cv2.saliency` and a
  feathered center field.
- `overlap_fraction(mark: Mark, exclusion: SoftExclusion) -> float` supplies
  planning rejection without a GIMP dependency.

- [ ] Write failing tests using mocked MediaPipe landmark results and small
  NumPy arrays: face/hand regions are protected, field edges are feathered,
  no rectangular hard-cutout mask is created, a central salient region is
  protected when no landmark exists, and an edge candidate has less overlap
  than a face candidate.
- [ ] Run `uv run pytest tests/test_protection.py -v`; observe RED.
- [ ] Implement lazy imports with a clear `ProtectionDependencyError`, landmark
  rasterization, OpenCV blur/distance transforms, saliency-center blending,
  clamping, and weighted overlap. Do not load or ship a custom ONNX model.
- [ ] Run focused tests, then full static checks. Confirm production imports
  contain only the approved packages plus their transitive dependencies.
- [ ] Inspect staged diff and commit `feat: add semantic protection fields`.

### Task 4: Capture recipes and coordinate batch processing without GIMP in CI

**Files:**
- Create: `src/gimp_weathered_photo_plugin/metadata.py`
- Create: `src/gimp_weathered_photo_plugin/batch.py`
- Create: `src/gimp_weathered_photo_plugin/__main__.py`
- Create: `tests/test_metadata.py`
- Create: `tests/test_batch.py`

**Interfaces:**
- `write_recipe(path: Path, recipe: TreatmentRecipe, source: Path) -> Path`
  atomically writes versioned UTF-8 JSON only after its matching render
  succeeds.
- `process_batch(inputs: Sequence[Path], output_dir: Path, renderer: Renderer,
  *, replay_recipe: Path | None = None, overwrite: bool = False) ->
  list[BatchResult]` preflights assets, creates or loads a recipe, passes it to
  the renderer, then writes its sidecar per input and reports failures
  independently.
- `Renderer.render(source: Path, png: Path, xcf: Path, recipe:
  TreatmentRecipe, assets: Mapping[str, Path]) -> None` is the
  dependency-injected host boundary.

- [ ] Write failing tests for source SHA-256 and recipe data in JSON, exact
  recipe and resolved assets received by the fake renderer before sidecar
  creation, `--replay-recipe` loading, PNG/XCF/JSON naming, no overwrite by
  default, one failed input not suppressing later inputs, and zero renderer
  calls when assets fail preflight.
- [ ] Run focused tests and observe RED.
- [ ] Implement recipe-before-render ordering, atomic sidecar creation after
  renderer success, deterministic output naming, a narrow CLI parser with
  `--replay-recipe PATH`, and a fake-renderer-friendly batch protocol. The
  standalone CLI must document that it invokes a configured GIMP batch host
  rather than emulating image treatment itself.
- [ ] Run focused tests and quality checks; expect GREEN.
- [ ] Inspect staged diff and commit `feat: add batch recipe workflow`.

### Task 5: Render the approved recipe through native GIMP operations

**Files:**
- Create: `src/gimp_weathered_photo_plugin/gimp_host.py`
- Create: `tests/test_gimp_adapter_contract.py`

**Interfaces:**
- `GimpRenderer.render(source, png, xcf, recipe, assets) -> None` is the
  concrete `Renderer` used only by a GIMP host.
- `apply_recipe(image, recipe, assets) -> None` creates editable named layers
  and masks and never mutates the source layer pixels.

- [ ] Write failing fake-GIMP adapter contract tests asserting: source is
  duplicated/non-destructively retained; every mark creates a named editable
  layer and organic layer mask; dry-rub/sepia marks use brushes, transform and
  blend operations; water stains blur only a duplicated source through their
  local mask; final export restores exact original alpha and dimensions; no
  global filter/tint/blur call is issued.
- [ ] Run the contract tests and observe RED without importing `gi` in CI.
- [ ] Implement `gimp_host.py` as the sole lazy `gi.repository` import module.
  It contains the GIMP 3 procedure registration and the protocol-backed
  `GimpRenderer`. The procedure receives a parsed recipe, resolves package
  assets, calls `apply_recipe`, saves XCF, and exports PNG. Use GIMP-native
  layers, masks, brush resources, transforms, blend modes, and local Gaussian
  blur.
- [ ] Run fake-adapter tests plus all static checks. Verify `rg -n
  'PIL|Pillow|onnx|global.*blur|global.*tint' src tests` finds no forbidden
  treatment engine or custom ONNX usage.
- [ ] Inspect staged diff and commit `feat: add native gimp renderer`.

### Task 6: Document and execute the native smoke boundary

**Files:**
- Create: `docs/gimp-smoke-test.md`
- Modify: `README.md`
- Create: `tests/test_documentation_contract.py`

- [ ] Write a failing documentation-contract test requiring exact Python 3.12,
  GIMP 3 plug-in discovery/install location, locked environment install,
  MediaPipe/OpenCV availability check, batch invocation, alpha/dimension
  inspection, XCF layer/mask inspection, and four-proof limit.
- [ ] Run the documentation test; observe RED.
- [ ] Document Windows Store GIMP executable discovery, how to configure the
  GIMP host Python to import the locked packages, noninteractive batch command,
  failure diagnosis, and manual visual acceptance checklist. Update README
  from scaffold-only status to describe the planned plug-in without claiming
  native validation that has not occurred.
- [ ] Run documentation test, formatter, lint, and type check; expect GREEN.
- [ ] With a usable GIMP batch executable and four approved Vezor input PNGs,
  execute the checklist and create exactly four full-size PNG/XCF/recipe proof
  sets. Stop for visual approval. If either prerequisite is absent, record the
  exact blocker and do not fabricate proofs.
- [ ] Inspect staged diff and commit `docs: add gimp worn print smoke test`.

### Task 7: Run the complete local gate and review scope

- [ ] Run `uv sync --locked`; expect exit 0 with no lock changes.
- [ ] Run `uv run pytest --cov --cov-branch --cov-report=xml`; expect all tests
  pass, 100% configured coverage, and `coverage.xml` generated.
- [ ] Run `uv run ruff format --check .`, `uv run ruff check .`, and
  `uv run ty check`; expect exit 0 for each.
- [ ] Run `git diff --check origin/main...HEAD`, `git diff --stat
  origin/main...HEAD`, and `git status --short --branch`; inspect the complete
  diff for accidental automation changes, global effects, custom models, or
  scope beyond the plug-in.
- [ ] Do not push unless explicitly requested. Report Actions, CodeQL, Codecov,
  Dependabot, and Release Please as pending until remote execution.
