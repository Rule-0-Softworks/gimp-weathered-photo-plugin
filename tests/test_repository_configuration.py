import json
import re
import tomllib
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


def test_ci_pins_python_and_configures_coverage_upload() -> None:
    workflow = load_yaml(".github/workflows/ci.yml")
    steps = workflow["jobs"]["quality"]["steps"]

    codecov_step = next(
        step
        for step in steps
        if str(step.get("uses", "")).startswith("codecov/codecov-action@")
    )

    assert any(step.get("with", {}).get("python-version") == 3.14 for step in steps)
    assert codecov_step["with"]["token"] == "${{ secrets.CODECOV_TOKEN }}"
    assert codecov_step["if"] == "github.actor != 'dependabot[bot]'"


def test_workflows_pin_actions_to_full_commit_shas() -> None:
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

    required_actions = {
        "ci": {
            "actions/checkout",
            "astral-sh/setup-uv",
            "codecov/codecov-action",
        },
        "codeql": {
            "actions/checkout",
            "github/codeql-action/init",
            "github/codeql-action/analyze",
        },
        "release_please": {"googleapis/release-please-action"},
    }

    for workflow_name, workflow_uses in uses.items():
        assert all(
            re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", action) for action in workflow_uses
        )
        assert required_actions[workflow_name] <= {
            action.split("@", maxsplit=1)[0] for action in workflow_uses
        }


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


def test_codecov_coverage_status_policy_allows_small_project_regressions() -> None:
    codecov = load_yaml(".codecov.yml")

    project = codecov["coverage"]["status"]["project"]["default"]
    assert project["target"] == "auto"
    assert project["threshold"] == "0.5%"
    patch = codecov["coverage"]["status"]["patch"]["default"]
    assert patch["target"] == "75%"
    assert patch["threshold"] == "0.5%"


def test_release_please_json_uses_python_manifest_mode() -> None:
    config = load_json("release-please-config.json")
    manifest = load_json(".release-please-manifest.json")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert config["packages"]["."]["release-type"] == "python"
    assert manifest == {".": project["project"]["version"]}
