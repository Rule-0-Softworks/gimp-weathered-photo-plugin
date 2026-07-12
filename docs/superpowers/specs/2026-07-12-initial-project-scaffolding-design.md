# Initial Project Scaffolding Design

## Purpose

Create a reproducible, CI-enforced Python 3.12+ project foundation for the
weathered-photo GIMP plug-in. This branch establishes packaging, quality,
security, dependency-update, coverage, and release infrastructure only. It
must not contain GIMP integration or image-treatment behavior.

## Project Structure

Use a `src/` layout with an importable `gimp_weathered_photo_plugin` package.
The package contains only metadata needed to prove that packaging and imports
work. Tests live under `tests/` and initially verify package import and version
metadata. This creates a real package boundary without prematurely designing
the eventual plug-in API.

Repository-level files provide:

- `pyproject.toml` for Python 3.12+, uv packaging, development dependencies,
  pytest and coverage settings, Ruff formatting/linting, ty type checking, and
  PyYAML for test-only configuration parsing.
- `uv.lock` for reproducible dependency resolution.
- `.gitignore`, Apache-2.0 `LICENSE`, `README.md`, and `CONTRIBUTING.md` for a
  usable contributor experience.
- `.codecov.yml` for coverage reporting policy.
- `.github/workflows/ci.yml` for locked dependency sync, tests with XML
  coverage, formatting checks, lint checks, type checking, and Codecov upload.
- `.github/workflows/codeql.yml` for GitHub CodeQL analysis of Python.
- `.github/workflows/release-please.yml`, `release-please-config.json`, and
  `.release-please-manifest.json` for Conventional Commit-driven releases.
- `.github/dependabot.yml` for GitHub Actions and uv dependency updates.

## Local and CI Commands

The documented local workflow and CI workflow use the same commands:

```powershell
uv sync --locked
uv run pytest --cov --cov-report=xml
uv run ruff format --check .
uv run ruff check .
uv run ty check
```

CI pins the uv setup action, explicitly requests Python 3.12 through uv, and
must fail if dependency synchronization, tests, formatting, linting, or type
checking fails. Codecov upload follows successful test execution and uses the
generated `coverage.xml` report.

## Versioning and Releases

The package version has a single source in `pyproject.toml`; package code reads
it through `importlib.metadata`. Release Please uses the Python release type,
Conventional Commits, and manifest mode to update the project version and
changelog through release pull requests. No release is published directly by
the scaffold workflow beyond Release Please's standard GitHub release process.

## Testing Strategy

Follow test-first development for the only runtime behavior in this scaffold:
package import and version exposure. Add the smoke test first, confirm it fails
because the package does not exist, then add the minimal package implementation
and confirm it passes. Tests parse TOML with `tomllib`, JSON with `json`, and
YAML with PyYAML. They also assert that CI contains the five required commands
and explicit Python/uv setup, and that the supporting GitHub configuration has
the expected top-level structure.

The final verification gate runs all five documented commands from a clean
dependency state, runs the configuration-validation tests as part of pytest,
and reviews the complete Git diff for accidental scope creep. A successful
GitHub Actions run is a post-push review requirement and must be reported as
pending when the branch has not been pushed; it is not represented as local
verification.

## Constraints

- Minimum supported Python version is 3.12 (`requires-python = ">=3.12"`).
  Python 3.12 is also the canonical local and CI runtime so development matches
  the likely GIMP 3 host interpreter. Newer compatible Python versions remain
  allowed but are not the primary scaffold target.
- Use uv for project and dependency management.
- Use pytest and pytest-cov; produce `coverage.xml` for Codecov.
- Use Ruff for formatting and linting and ty for static type checking.
- Do not add GIMP integration, image processing, or image-treatment code.
- Do not create Linear or other external project-management artifacts.
- Keep all commits compatible with Conventional Commits and Release Please.
- Stop after this branch is locally verified and ready for review.

## Next Branch Boundary

Only after this scaffold is complete and ready for review should work begin on
`feature/gimp-worn-print-plugin`. Its implementation plan will cover GIMP 3
entry points, parameter handling, non-destructive layer operations, treatment
pipeline behavior, and GIMP-aware testing separately from this scaffold.
