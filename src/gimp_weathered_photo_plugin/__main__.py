from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from gimp_weathered_photo_plugin.assets import resolve_assets
from gimp_weathered_photo_plugin.batch import process_batch
from gimp_weathered_photo_plugin.gimp_console_bridge import GimpConsoleBridge
from gimp_weathered_photo_plugin.metadata import AnalysisProvenance
from gimp_weathered_photo_plugin.planning import plan_treatment
from gimp_weathered_photo_plugin.semantic_bridge import SemanticAnalysisBridge


def resolve_packaged_assets() -> dict[str, Path]:
    return resolve_assets(Path(__file__).with_name("assets"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    inputs = [Path(value) for value in arguments.inputs]
    invalid_input = next((path for path in inputs if not _is_existing_png(path)), None)
    if invalid_input is not None:
        print(
            f"input must be an existing filesystem-backed PNG: {invalid_input}",
            file=sys.stderr,
        )
        return 2

    replay_record = Path(arguments.replay_recipe) if arguments.replay_recipe else None
    if replay_record is None and arguments.analyzer_executable is None:
        print("fresh rendering requires --analyzer-executable", file=sys.stderr)
        return 2
    if replay_record is not None and not replay_record.is_file():
        print(f"replay record does not exist: {replay_record}", file=sys.stderr)
        return 2

    analyzer_executable = (
        Path(arguments.analyzer_executable)
        if arguments.analyzer_executable is not None
        else None
    )
    try:
        renderer = GimpConsoleBridge(Path(arguments.gimp_console))
        bridge = (
            SemanticAnalysisBridge(
                analyzer_executable,
                arguments=("-m", "gimp_weathered_photo_plugin.analyzer"),
            )
            if analyzer_executable is not None and replay_record is None
            else None
        )
        provenance = (
            AnalysisProvenance(
                analyzer_version=arguments.analyzer_version,
                adapter_configuration={
                    "arguments": "-m gimp_weathered_photo_plugin.analyzer",
                    "executable": str(analyzer_executable),
                },
            )
            if bridge is not None
            else None
        )
        results = process_batch(
            inputs,
            Path(arguments.output_dir),
            renderer,
            assets=resolve_packaged_assets(),
            recipe_factory=plan_treatment,
            semantic_bridge=bridge,
            analysis_provenance=provenance,
            replay_record=replay_record,
            overwrite=arguments.overwrite,
        )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"batch setup failed: {error}", file=sys.stderr)
        return 1

    for result in results:
        if result.success:
            print(f"rendered: {result.png}")
        else:
            print(f"failed: {result.source}: {result.error}", file=sys.stderr)
    return 0 if all(result.success for result in results) else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the weathered-photo treatment through GIMP's batch host."
    )
    parser.add_argument(
        "inputs", nargs="+", help="existing filesystem-backed PNG input"
    )
    parser.add_argument(
        "--gimp-console", required=True, help="absolute GIMP console path"
    )
    parser.add_argument(
        "--analyzer-executable",
        help="absolute standard-CPython analyzer executable for fresh renders",
    )
    parser.add_argument(
        "--analyzer-version",
        default="unspecified",
        help="recorded analyzer version for a fresh render",
    )
    parser.add_argument("--output-dir", default=".", help="directory for render sets")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--replay-recipe",
        help="complete render record; skips semantic analysis",
    )
    return parser


def _is_existing_png(path: Path) -> bool:
    return path.suffix.lower() == ".png" and path.is_file()


if __name__ == "__main__":
    raise SystemExit(main())
