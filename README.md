# GIMP Weathered Photo Plug-in

This branch contains project scaffolding only. It establishes Python packaging,
tests, quality tooling, coverage, and GitHub automation for a future GIMP 3
plug-in. No GIMP integration, plug-in registration, or image-treatment code
exists here.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

## Local setup and verification

In PowerShell:

```powershell
uv sync --locked
uv run pytest --cov --cov-branch --cov-report=xml
uv run ruff format --check .
uv run ruff check .
uv run ty check
```

The same platform-neutral commands work in other shells:

```text
uv sync --locked
uv run pytest --cov --cov-branch --cov-report=xml
uv run ruff format --check .
uv run ruff check .
uv run ty check
```

The test command creates `coverage.xml` for Codecov.

## Automation

- `ci.yml` runs the locked sync, tests with XML coverage, Ruff format and lint
  checks, ty type checking, and Codecov upload on pushes and pull requests.
- `codeql.yml` performs Python CodeQL analysis on changes to `main` and weekly.
- `release-please.yml` uses Conventional Commits to create release pull
  requests from `main`.
- `dependabot.yml` opens weekly update pull requests for GitHub Actions and uv
  dependencies.
- `.codecov.yml` defines project and patch coverage status policy.

## Repository layout

```text
.
├── .github/                 # CI, CodeQL, Release Please, and Dependabot
├── src/
│   └── gimp_weathered_photo_plugin/  # package metadata only
├── tests/                   # package and automation configuration tests
├── pyproject.toml           # packaging and development-tool configuration
└── uv.lock                  # locked development dependencies
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution expectations.
