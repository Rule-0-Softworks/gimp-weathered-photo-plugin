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
    assert "sudo apt-get update && sudo apt-get install -y libegl1 libgles2" in runs
    assert "uv run pytest --cov --cov-branch --cov-report=xml" in runs
    assert "uv run ruff format --check ." in runs
    assert "uv run ruff check ." in runs
    assert "uv run ty check" in runs


def test_ci_pins_python_and_uploads_coverage() -> None:
    workflow = load_yaml(".github/workflows/ci.yml")
    steps = workflow["jobs"]["quality"]["steps"]

    codecov_step = next(
        step
        for step in steps
        if str(step.get("uses", "")).startswith("codecov/codecov-action@")
    )

    assert any(step.get("with", {}).get("python-version") == 3.14 for step in steps)
    assert codecov_step["with"]["token"] == "${{ secrets.CODECOV_TOKEN }}"


def test_workflows_pin_actions_to_latest_commit_shas() -> None:
    workflows = {
        "ci": load_yaml(".github/workflows/ci.yml"),
        "codeql": load_yaml(".github/workflows/codeql.yml"),
        "release_please": load_yaml(".github/workflows/release-please.yml"),
    }
    uses = {
        workflow_name: [
            step["uses"]
            for job in workflow["jobs"].values()
            for step in job["steps"]
            if "uses" in step
        ]
        for workflow_name, workflow in workflows.items()
    }

    assert uses["ci"] == [
        "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0",
        "astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990",
        "codecov/codecov-action@8cad3ba95e5920c42f44492e54bc9639cba47959",
    ]
    assert uses["codeql"] == [
        "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0",
        "github/codeql-action/init@24ea975727876cf496b1eb0c5b36e96e01600b51",
        "github/codeql-action/analyze@24ea975727876cf496b1eb0c5b36e96e01600b51",
    ]
    assert uses["release_please"] == [
        "googleapis/release-please-action@45996ed1f6d02564a971a2fa1b5860e934307cf7"
    ]


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
    assert release["permissions"]["issues"] == "write"


def test_codecov_patch_target_is_75_percent() -> None:
    codecov = load_yaml(".codecov.yml")

    assert codecov["coverage"]["status"]["patch"]["default"]["target"] == "75%"


def test_release_please_json_uses_python_manifest_mode() -> None:
    config = load_json("release-please-config.json")
    manifest = load_json(".release-please-manifest.json")

    assert config["packages"]["."]["release-type"] == "python"
    assert manifest == {".": "0.0.0"}
