# Contributing

Use a focused feature branch for each change. Keep pull requests small and
limited to one purpose.

## Development workflow

Behavior changes follow test-first development: write a failing test, observe
the expected failure, implement the smallest change, and then verify it passes.

Before opening a pull request, run the complete local verification sequence:

```text
uv sync --locked
uv run pytest --cov --cov-report=xml
uv run ruff format --check .
uv run ruff check .
uv run ty check
```

## Commits and pull requests

Use Conventional Commits so Release Please can determine releases. Common
prefixes include:

- `feat: add a capability`
- `fix: correct a defect`
- `docs: improve setup guidance`
- `test: cover a regression`
- `build: update packaging configuration`
- `ci: adjust automation`
- `chore: maintain repository metadata`

Describe the focused change and verification evidence in every pull request.
Do not commit generated environments, coverage output, caches, or build
artifacts.
