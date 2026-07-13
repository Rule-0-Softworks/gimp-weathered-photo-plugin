from __future__ import annotations

import hashlib
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from gimp_weathered_photo_plugin.metadata import RenderRecord, write_recipe
from gimp_weathered_photo_plugin.models import TreatmentRecipe


class Renderer(Protocol):
    def render(
        self,
        source: Path,
        png: Path,
        xcf: Path,
        recipe: TreatmentRecipe,
        assets: Mapping[str, Path],
    ) -> None: ...


RecipeFactory = Callable[[Path], TreatmentRecipe]


@dataclass(frozen=True, slots=True)
class BatchResult:
    source: Path
    png: Path
    xcf: Path
    recipe_path: Path
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


def process_batch(
    inputs: Sequence[Path],
    output_dir: Path,
    renderer: Renderer,
    *,
    assets: Mapping[str, Path],
    recipe_factory: RecipeFactory,
    replay_recipe: TreatmentRecipe | None = None,
    replay_record: RenderRecord | None = None,
    overwrite: bool = False,
) -> list[BatchResult]:
    if replay_recipe is not None and replay_record is not None:
        raise ValueError("choose either replay_recipe or replay_record")
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[BatchResult] = []
    for source in inputs:
        png, xcf, recipe_path = _output_paths(source, output_dir)
        if not overwrite and any(path.exists() for path in (png, xcf, recipe_path)):
            results.append(
                BatchResult(
                    source,
                    png,
                    xcf,
                    recipe_path,
                    "output already exists; use overwrite",
                )
            )
            continue
        try:
            if replay_record is not None:
                source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
                if source_sha256 != replay_record.source_sha256:
                    raise ValueError("replay source fingerprint mismatch")
                recipe = replay_record.recipe
            else:
                recipe = replay_recipe or recipe_factory(source)
            staging_directory = output_dir / ".vezor-staging" / str(uuid4())
            staging_directory.mkdir(parents=True)
            staged_png, staged_xcf, staged_recipe = _staged_output_paths(
                staging_directory
            )
            try:
                renderer.render(source, staged_png, staged_xcf, recipe, assets)
                write_recipe(staged_recipe, recipe, source)
                publish_output_set(
                    (staged_png, staged_xcf, staged_recipe),
                    (png, xcf, recipe_path),
                )
            finally:
                shutil.rmtree(staging_directory, ignore_errors=True)
            results.append(BatchResult(source, png, xcf, recipe_path))
        except Exception as error:
            results.append(BatchResult(source, png, xcf, recipe_path, str(error)))
    return results


def _output_paths(source: Path, output_dir: Path) -> tuple[Path, Path, Path]:
    stem = output_dir / f"{source.stem}-worn"
    return (
        stem.with_suffix(".png"),
        stem.with_suffix(".xcf"),
        stem.with_suffix(".recipe.json"),
    )


def _staged_output_paths(directory: Path) -> tuple[Path, Path, Path]:
    return (
        directory / "output.png",
        directory / "output.xcf",
        directory / "output.recipe.json",
    )


def publish_output_set(
    staged: tuple[Path, Path, Path], final: tuple[Path, Path, Path]
) -> None:
    if any(not path.is_file() for path in staged):
        raise FileNotFoundError("staged output is missing")
    for staged_path, final_path in zip(staged, final, strict=True):
        staged_path.replace(final_path)
