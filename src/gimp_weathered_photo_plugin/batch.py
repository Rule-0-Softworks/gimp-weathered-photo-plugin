from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from gimp_weathered_photo_plugin.metadata import write_recipe
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
    overwrite: bool = False,
) -> list[BatchResult]:
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
            recipe = replay_recipe or recipe_factory(source)
            renderer.render(source, png, xcf, recipe, assets)
            write_recipe(recipe_path, recipe, source)
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


def publish_output_set(
    staged: tuple[Path, Path, Path], final: tuple[Path, Path, Path]
) -> None:
    if any(not path.is_file() for path in staged):
        raise FileNotFoundError("staged output is missing")
    for staged_path, final_path in zip(staged, final, strict=True):
        staged_path.replace(final_path)
