# Initial Project Scaffolding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, locally verified Python project scaffold with CI, coverage, security, dependency-update, and release automation, without adding GIMP or image-treatment code.

**Architecture:** Use a minimal `src/gimp_weathered_photo_plugin` package whose only runtime behavior is exposing installed distribution metadata. Keep all development tooling in `pyproject.toml`, validate repository automation as data in pytest, and make GitHub Actions run the same locked uv commands documented for contributors.

**Tech Stack:** Python 3.12+, uv/uv_build, pytest, pytest-cov, Ruff, ty, PyYAML, GitHub Actions, Codecov, CodeQL, Dependabot, Release Please

## Global Constraints

- Work only on `feature/initial-project-scaffolding`.
- Set `requires-python = ">=3.12"` and use Python 3.12 as the canonical local and CI runtime.
- Do not add GIMP integration, image processing, or image-treatment code.
- Do not create Linear or other external project-management artifacts.
- Use uv for project and dependency management and commit `uv.lock`.
- Use pytest and pytest-cov and generate `coverage.xml` for Codecov.
- Use Ruff for formatting and linting and ty for static type checking.
- Use Conventional Commits compatible with Release Please.
- Do not begin `feature/gimp-worn-print-plugin` in this plan.

---

## File Structure

- `pyproject.toml`: package metadata, Python floor, build backend, development dependencies, and tool configuration.
- `.python-version`: canonical Python 3.12 interpreter selection for uv.
- `src/gimp_weathered_photo_plugin/__init__.py`: expose installed package version only.
- `tests/test_package.py`: smoke-test importability and version metadata.
- `tests/test_repository_configuration.py`: parse and assert repository automation/configuration contracts.
- `.github/workflows/ci.yml`: locked sync, coverage tests, format, lint, type check, and Codecov upload.
- `.github/workflows/codeql.yml`: Python CodeQL scanning.
- `.github/workflows/release-please.yml`: Release Please orchestration on `main`.
- `.github/dependabot.yml`: weekly GitHub Actions and uv dependency updates.
- `.codecov.yml`: Codecov project and patch status policy.
- `release-please-config.json`: Python release strategy and changelog settings.
- `.release-please-manifest.json`: initial Release Please version state.
- `.gitignore`: Python, uv, coverage, editor, and OS artifacts.
- `README.md`: exact setup and quality commands, CI overview, and layout.
- `CONTRIBUTING.md`: branch, test-first, Conventional Commit, and pull-request guidance.
- `LICENSE`: retain the existing Apache-2.0 license text.
- `uv.lock`: reproducible development dependency resolution.

---

### Task 1: Python Package and Test-First Smoke Test

**Files:**
- Create: `.python-version`
- Create: `pyproject.toml`
- Create: `tests/test_package.py`
- Create: `src/gimp_weathered_photo_plugin/__init__.py`
- Create: `uv.lock`

**Interfaces:**
- Consumes: Python 3.12 selected by `.python-version`; distribution name `gimp-weathered-photo-plugin`.
- Produces: `gimp_weathered_photo_plugin.__version__: str` sourced from `importlib.metadata.version()`.

- [ ] **Step 1: Add project metadata and the failing smoke test**

Create `.python-version`:

```text
3.12
```

Create `pyproject.toml`:

```toml
[build-system]
requires = ["uv_build>=0.10.0,<0.12.0"]
build-backend = "uv_build"

[project]
name = "gimp-weathered-photo-plugin"
version = "0.0.0"
description = "A GIMP 3 plug-in for applying a weathered print treatment to images."
readme = "README.md"
requires-python = ">=3.12"
license = "Apache-2.0"
authors = [{ name = "Rule 0 Softworks" }]
classifiers = [
  "Development Status :: 1 - Planning",
  "License :: OSI Approved :: Apache Software License",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.12",
]
dependencies = []

[dependency-groups]
dev = [
  "pytest>=8.4,<10",
  "pytest-cov>=6,<8",
  "pyyaml>=6,<7",
  "ruff>=0.12,<1",
  "ty>=0.0.1a20,<1",
]

[tool.pytest.ini_options]
addopts = "--strict-config --strict-markers"
testpaths = ["tests"]

[tool.coverage.run]
branch = true
source = ["gimp_weathered_photo_plugin"]

[tool.coverage.report]
fail_under = 100
show_missing = true

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.ty.environment]
python-version = "3.12"
```

Create `tests/test_package.py`:

```python
from importlib.metadata import version

import gimp_weathered_photo_plugin


def test_package_exposes_distribution_version() -> None:
    assert gimp_weathered_photo_plugin.__version__ == version(
        "gimp-weathered-photo-plugin"
    )
```

- [ ] **Step 2: Lock and sync dependencies**

Run: `uv lock --python 3.12`

Expected: exit 0 and a new `uv.lock` compatible with Python 3.12+.

Run: `uv sync --locked --no-install-project`

Expected: exit 0 with the Python 3.12 environment and development group installed.
The package is intentionally absent until Step 4, so `--no-install-project`
is required here. The full `uv sync --locked` verification remains in Task 4
after the package implementation exists.

- [ ] **Step 3: Run the smoke test and verify RED**

Run: `uv run pytest tests/test_package.py -v`

Expected: collection fails with `ModuleNotFoundError: No module named 'gimp_weathered_photo_plugin'` because the package has not been created.

- [ ] **Step 4: Add the minimal package implementation**

Create `src/gimp_weathered_photo_plugin/__init__.py`:

```python
from importlib.metadata import version

__version__ = version("gimp-weathered-photo-plugin")
```

- [ ] **Step 5: Install the newly created project into the locked environment**

Run: `uv sync --locked`

Expected: exit 0 with the project and development group installed. This is
required because Step 2 intentionally used `--no-install-project` while the
package did not yet exist.

- [ ] **Step 6: Run the smoke test and verify GREEN**

Run: `uv run pytest tests/test_package.py -v`

Expected: `1 passed`.

- [ ] **Step 7: Commit the package foundation**

```powershell
git add .python-version pyproject.toml uv.lock src tests/test_package.py
git commit -m "build: initialize uv python project"
```

---

### Task 2: Test-Validated GitHub and Service Configuration

**Files:**
- Create: `tests/test_repository_configuration.py`
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/codeql.yml`
- Create: `.github/workflows/release-please.yml`
- Create: `.github/dependabot.yml`
- Create: `.codecov.yml`
- Create: `release-please-config.json`
- Create: `.release-please-manifest.json`

**Interfaces:**
- Consumes: the exact local commands defined in `pyproject.toml` and the Python 3.12 baseline.
- Produces: parseable automation configuration with required triggers, permissions, commands, ecosystems, and release settings.

- [ ] **Step 1: Write failing repository-configuration tests**

Create `tests/test_repository_configuration.py`:

```python
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: str) -> dict[str, Any]:
    parsed = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def load_json(path: str) -> dict[str, Any]:
    parsed = json.loads((ROOT / path).read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def test_ci_runs_every_required_quality_command() -> None:
    workflow = load_yaml(".github/workflows/ci.yml")
    steps = workflow["jobs"]["quality"]["steps"]
    runs = {step["run"] for step in steps if "run" in step}

    assert "uv sync --locked" in runs
    assert "uv run pytest --cov --cov-report=xml" in runs
    assert "uv run ruff format --check ." in runs
    assert "uv run ruff check ." in runs
    assert "uv run ty check" in runs


def test_ci_pins_python_and_uploads_coverage() -> None:
    workflow = load_yaml(".github/workflows/ci.yml")
    steps = workflow["jobs"]["quality"]["steps"]

    assert any(step.get("with", {}).get("python-version") == 3.12 for step in steps)
    assert any(str(step.get("uses", "")).startswith("codecov/codecov-action@") for step in steps)


def test_supporting_yaml_configuration_has_expected_structure() -> None:
    codeql = load_yaml(".github/workflows/codeql.yml")
    dependabot = load_yaml(".github/dependabot.yml")
    codecov = load_yaml(".codecov.yml")
    release = load_yaml(".github/workflows/release-please.yml")

    assert "analyze" in codeql["jobs"]
    ecosystems = {update["package-ecosystem"] for update in dependabot["updates"]}
    assert ecosystems == {"github-actions", "uv"}
    assert {"project", "patch"} <= set(codecov["coverage"]["status"])
    assert "release-please" in release["jobs"]


def test_release_please_json_uses_python_manifest_mode() -> None:
    config = load_json("release-please-config.json")
    manifest = load_json(".release-please-manifest.json")

    assert config["packages"]["."]["release-type"] == "python"
    assert manifest == {".": "0.0.0"}
```

- [ ] **Step 2: Run configuration tests and verify RED**

Run: `uv run pytest tests/test_repository_configuration.py -v`

Expected: failures with `FileNotFoundError` for the absent workflow/configuration files.

- [ ] **Step 3: Add CI and Codecov configuration**

Create `.github/workflows/ci.yml` with pull-request and push triggers, read-only contents permission, and SHA-pinned latest releases of `actions/checkout`, `astral-sh/setup-uv`, and `codecov/codecov-action`, each with a readable version comment. Use Python 3.12 and separate failing steps for the five exact commands asserted above. Add Codecov after tests with `token: ${{ secrets.CODECOV_TOKEN }}`, `files: coverage.xml`, and `fail_ci_if_error: true`.

Create `.codecov.yml`:

```yaml
coverage:
  status:
    project:
      default:
        target: auto
    patch:
      default:
        target: 100%
```

- [ ] **Step 4: Add CodeQL, Dependabot, and Release Please configuration**

Create `.github/workflows/codeql.yml` using SHA-pinned latest releases of `github/codeql-action/init` and `github/codeql-action/analyze`, each with a readable version comment, for `languages: python`, triggered by pushes and pull requests to `main` plus a weekly schedule, with `security-events: write` and `contents: read` permissions.

Create `.github/dependabot.yml` with version 2 and weekly updates for both `github-actions` at `/` and `uv` at `/`, each limited to five open pull requests and using the `dependencies` Conventional Commit prefix.

Create `.github/workflows/release-please.yml` triggered by pushes to `main`, with `contents: write`, `issues: write`, and `pull-requests: write`, invoking the SHA-pinned latest `googleapis/release-please-action` release with a readable version comment, the repository token, and the two root JSON configuration paths.

Create `release-please-config.json`:

```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "packages": {
    ".": {
      "release-type": "python",
      "package-name": "gimp-weathered-photo-plugin",
      "changelog-path": "CHANGELOG.md"
    }
  }
}
```

Create `.release-please-manifest.json`:

```json
{
  ".": "0.0.0"
}
```

- [ ] **Step 5: Run configuration tests and verify GREEN**

Run: `uv run pytest tests/test_repository_configuration.py -v`

Expected: all four tests pass.

- [ ] **Step 6: Run formatting, linting, and typing on the new tests**

Run: `uv run ruff format --check .`

Expected: exit 0.

Run: `uv run ruff check .`

Expected: exit 0.

Run: `uv run ty check`

Expected: exit 0.

- [ ] **Step 7: Commit automation configuration**

```powershell
git add .github .codecov.yml release-please-config.json .release-please-manifest.json tests/test_repository_configuration.py
git commit -m "ci: add quality security and release automation"
```

---

### Task 3: Contributor-Facing Repository Documentation

**Files:**
- Modify: `README.md`
- Create: `CONTRIBUTING.md`
- Create: `.gitignore`
- Verify: `LICENSE`

**Interfaces:**
- Consumes: the exact commands and repository structure created in Tasks 1 and 2.
- Produces: copy-pasteable Windows PowerShell and platform-neutral uv workflows for contributors.

- [ ] **Step 1: Replace the README with exact project instructions**

Document the scaffold-only project status, Python 3.12 and uv prerequisites, `uv sync --locked`, all five exact CI commands, the purpose of each GitHub workflow/service, Codecov output location, and a repository tree. State explicitly that no GIMP/image-treatment code exists on this branch.

- [ ] **Step 2: Add contribution guidance**

Create `CONTRIBUTING.md` covering feature branches, test-first behavior changes, the complete local verification sequence, Conventional Commit examples (`feat:`, `fix:`, `docs:`, `test:`, `build:`, `ci:`, `chore:`), focused pull requests, and the requirement not to commit generated environments or coverage output.

- [ ] **Step 3: Add a focused `.gitignore`**

Ignore `.venv/`, Python bytecode/cache directories, build artifacts, distribution metadata, pytest/Ruff/type-check caches, coverage data/XML/HTML output, editor settings, and common OS metadata. Do not ignore `uv.lock`.

- [ ] **Step 4: Verify the existing license**

Run: `Select-String -LiteralPath LICENSE -Pattern 'Apache License'`

Expected: matches identifying Apache License 2.0. Do not replace the existing license.

- [ ] **Step 5: Check documentation and ignore rules**

Run: `git check-ignore coverage.xml .venv/ __pycache__/test.py`

Expected: all three transient paths are ignored.

Run: `git check-ignore uv.lock`

Expected: exit 1 because the lockfile is tracked, not ignored.

- [ ] **Step 6: Commit contributor documentation**

```powershell
git add README.md CONTRIBUTING.md .gitignore LICENSE
git commit -m "docs: add contributor setup and project layout"
```

---

### Task 4: Complete Local Verification and Scope Review

**Files:**
- Verify: all files changed since `origin/main`

**Interfaces:**
- Consumes: completed scaffold and committed lockfile.
- Produces: exact, fresh evidence that every required local gate passes and no GIMP behavior entered scope.

- [ ] **Step 1: Verify locked synchronization on Python 3.12**

Run: `uv sync --locked`

Expected: exit 0 with no lockfile changes.

- [ ] **Step 2: Verify tests and Codecov XML generation**

Run: `uv run pytest --cov --cov-report=xml`

Expected: all tests pass, coverage meets the configured threshold, and `coverage.xml` is generated.

- [ ] **Step 3: Verify formatting and linting**

Run: `uv run ruff format --check .`

Expected: exit 0 with all files formatted.

Run: `uv run ruff check .`

Expected: exit 0 with no lint errors.

- [ ] **Step 4: Verify static types**

Run: `uv run ty check`

Expected: exit 0 with no diagnostics.

- [ ] **Step 5: Review the complete branch diff for scope creep**

Run: `git diff --check origin/main...HEAD`

Expected: exit 0.

Run: `git diff --stat origin/main...HEAD`

Expected: only scaffold, tests, automation, documentation, and planning files.

Run: `git grep -n -i -E '(import gi([^a-z_]|$)|from gi([^a-z_]|$)|gi\.repository|gimp\.|gegl|image treatment|image-processing)' -- src tests`

Expected: no GIMP binding, GEGL, or image-treatment implementation references.
The package and distribution identifiers necessarily include `gimp`, so this
check excludes those identifiers and searches for integration indicators.

- [ ] **Step 6: Confirm branch and working-tree status**

Run: `git status --short --branch`

Expected: branch is `feature/initial-project-scaffolding`; only ignored verification artifacts may exist, and no tracked changes remain.

- [ ] **Step 7: Record external validation boundary**

Do not push unless explicitly requested. Report GitHub Actions, CodeQL, Codecov ingestion, Dependabot, and Release Please execution as pending first remote runs. Do not claim those GitHub-native systems passed based only on local parsing.

---

## Proposed Next Branch Plan Boundary

After this branch is reviewed, propose `feature/gimp-worn-print-plugin`. Before implementation, inspect the target GIMP 3.0.x Python 3.12 runtime and bindings, then design and plan:

1. GIMP 3 plug-in discovery, registration, and procedure metadata.
2. Typed configuration for treatment parameters and batch operation.
3. Pure-Python treatment-planning logic isolated from GIMP bindings for unit tests.
4. GIMP/GEGL adapter code for non-destructive layer operations.
5. Host-level smoke tests in the supported GIMP runtime.
6. Packaging and installation documentation for Windows and other supported platforms.

No item in this section is implemented by the scaffold plan.
