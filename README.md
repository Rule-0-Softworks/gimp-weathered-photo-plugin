# GIMP Weathered Photo Plug-in

[![CI](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/actions/workflows/codeql.yml/badge.svg)](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/actions/workflows/codeql.yml)
[![Codecov](https://codecov.io/gh/Rule-0-Softworks/gimp-weathered-photo-plugin/graph/badge.svg)](https://codecov.io/gh/Rule-0-Softworks/gimp-weathered-photo-plugin)
[![Release](https://img.shields.io/github/v/release/Rule-0-Softworks/gimp-weathered-photo-plugin?display_name=tag&sort=semver)](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/releases)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-D22128)](LICENSE)
[![Status](https://img.shields.io/badge/status-scaffolding-6A5ACD)](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin)

A GIMP 3-native batch renderer that applies a weathered print treatment to
filesystem-backed PNG images.

> **Project status:** native smoke validation awaits four approved Vezor PNG
> inputs. This repository does not claim the treatment has been visually
> validated.

## What is here

- Python 3.12+ package managed with uv.
- A locked, reproducible development environment.
- Batch-only GIMP rendering with a temporary per-run brush configuration.
- Standard-CPython MediaPipe/OpenCV semantic analysis for fresh renders.
- Replay from a saved complete render record through `--replay-recipe`.
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

## Batch rendering

The command-line entry point runs GIMP's native batch host; it does not process
pixels itself and it does not modify a permanent GIMP brush folder. Fresh
rendering requires an absolute GIMP console path and an absolute standard-
CPython analyzer executable. Replay does not require analyzer dependencies.

```powershell
uv run python -m gimp_weathered_photo_plugin `
  --gimp-console "C:\\path\\to\\gimp-console-3.2.exe" `
  --analyzer-executable "$PWD\\.venv\\Scripts\\python.exe" `
  --analyzer-version "local-locked" `
  --output-dir .\\out `
  .\\input.png
```

See [the GIMP smoke test](docs/gimp-smoke-test.md) for analyzer setup,
batch diagnostics, replay, staging cleanup, and the four approved Vezor input
limit.

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
├── src/gimp_weathered_photo_plugin/ # batch, analysis, and GIMP bridge
├── tests/                           # package and automation contracts
├── pyproject.toml                   # packaging and quality-tool configuration
└── uv.lock                          # locked development dependencies
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the test-first workflow,
Conventional Commit guidance, and pull-request expectations.
