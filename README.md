# GIMP Weathered Photo Plug-in

[![CI](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/actions/workflows/codeql.yml/badge.svg)](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/actions/workflows/codeql.yml)
[![Codecov](https://codecov.io/gh/Rule-0-Softworks/gimp-weathered-photo-plugin/graph/badge.svg)](https://codecov.io/gh/Rule-0-Softworks/gimp-weathered-photo-plugin)
[![Release](https://img.shields.io/github/v/release/Rule-0-Softworks/gimp-weathered-photo-plugin?display_name=tag&sort=semver)](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/releases)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-D22128)](LICENSE)
[![Status](https://img.shields.io/badge/status-scaffolding-6A5ACD)](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin)

A reproducible Python foundation for a future GIMP 3 plug-in that will apply a
weathered print treatment to images.

> **Project status:** the public scaffold is ready. Packaging, verification,
> coverage, security scanning, dependency updates, and release automation are
> in place; GIMP integration and image-treatment behavior are intentionally
> not implemented yet.

## What is here

- Python 3.12+ package scaffolding managed with uv.
- A locked, reproducible development environment.
- Tests, 100% coverage enforcement, Ruff, and ty checks.
- GitHub Actions CI, CodeQL, Codecov reporting, Dependabot, and Release Please.

## Quick start

### Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

### Verify locally

Run the same checks used by CI:

```powershell
uv sync --locked
uv run pytest --cov --cov-branch --cov-report=xml
uv run ruff format --check .
uv run ruff check .
uv run ty check
```

The commands are shell-agnostic; replace the PowerShell prompt with your
preferred terminal. The test command writes `coverage.xml` for Codecov.

## Quality automation

| Service | Purpose |
| --- | --- |
| [CI](.github/workflows/ci.yml) | Locked sync, tests, coverage, formatting, linting, and type checks. |
| [CodeQL](.github/workflows/codeql.yml) | Python code scanning on changes to `main` and weekly. |
| [Codecov](.codecov.yml) | Project and patch coverage reporting policy. |
| [Dependabot](.github/dependabot.yml) | Weekly GitHub Actions and uv dependency updates. |
| [Release Please](.github/workflows/release-please.yml) | Conventional Commit-driven release pull requests. |

## Repository layout

```text
.
├── .github/                         # CI, CodeQL, Dependabot, Release Please
├── src/gimp_weathered_photo_plugin/ # package metadata only
├── tests/                           # package and automation contracts
├── pyproject.toml                   # packaging and quality-tool configuration
└── uv.lock                          # locked development dependencies
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the test-first workflow,
Conventional Commit guidance, and pull-request expectations.
