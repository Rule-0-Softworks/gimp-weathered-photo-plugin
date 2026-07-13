from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import hypot
from pathlib import Path
from random import Random
from secrets import randbits

from gimp_weathered_photo_plugin.models import (
    Mark,
    MarkFamily,
    MarkOrigin,
    Point,
    Size,
    SoftExclusion,
    TreatmentRecipe,
)

_ASSET_FAMILIES: dict[str, MarkFamily] = {
    "dry-rub-neutral-gray": "dry_rub",
    "dry-rub-umber": "dry_rub",
    "mottled-sepia": "mottled_sepia",
    "water-stain-01": "water_stain",
    "water-stain-02": "water_stain",
    "water-stain-03": "water_stain",
}
_EDGE_BAND = 0.22
_MAX_MARKS = 12
_MAX_OVERLAP = 0.15
_MAX_ATTEMPTS_PER_MARK = 32


def weighted_overlap(mark: Mark, exclusions: Sequence[SoftExclusion]) -> float:
    if not exclusions:
        return 0.0

    mark_radius = max(mark.scale * mark.extent, 0.01)
    samples = (
        (mark.anchor.x, mark.anchor.y),
        (max(0.0, mark.anchor.x - mark_radius), mark.anchor.y),
        (min(1.0, mark.anchor.x + mark_radius), mark.anchor.y),
        (mark.anchor.x, max(0.0, mark.anchor.y - mark_radius)),
        (mark.anchor.x, min(1.0, mark.anchor.y + mark_radius)),
    )
    total = 0.0
    for sample_x, sample_y in samples:
        strongest = max(
            _region_strength(sample_x, sample_y, exclusion) for exclusion in exclusions
        )
        total += strongest
    return total / len(samples)


def plan_treatment(
    size: Size,
    exclusions: Sequence[SoftExclusion],
    assets: Mapping[str, Path],
    recipe: TreatmentRecipe | None = None,
) -> TreatmentRecipe:
    if recipe is not None:
        if recipe.source_size != size:
            raise ValueError("replay recipe dimensions do not match the source image")
        missing = sorted({mark.asset_id for mark in recipe.marks} - set(assets))
        if missing:
            raise ValueError(
                f"replay recipe references unavailable assets: {', '.join(missing)}"
            )
        return recipe

    unknown_assets = set(assets) - set(_ASSET_FAMILIES)
    missing_assets = set(_ASSET_FAMILIES) - set(assets)
    if unknown_assets or missing_assets:
        raise ValueError("assets must match the curated asset library exactly")

    seed = randbits(128)
    generator = Random(seed)
    marks: list[Mark] = []
    target_count = generator.randint(7, _MAX_MARKS)
    for _ in range(target_count):
        for _ in range(_MAX_ATTEMPTS_PER_MARK):
            candidate = _sample_mark(generator)
            if weighted_overlap(candidate, exclusions) <= _MAX_OVERLAP:
                marks.append(candidate)
                break

    return TreatmentRecipe(
        schema_version=1,
        seed=seed,
        source_size=size,
        exclusions=tuple(exclusions),
        marks=tuple(marks),
    )


def _sample_mark(generator: Random) -> Mark:
    asset_id = generator.choice(tuple(_ASSET_FAMILIES))
    origin, anchor = _sample_edge_anchor(generator)
    family = _ASSET_FAMILIES[asset_id]
    opacity = generator.uniform(0.02, 0.1)
    if family == "water_stain":
        opacity = generator.uniform(0.015, 0.06)
    return Mark(
        asset_id=asset_id,
        family=family,
        origin=origin,
        anchor=anchor,
        scale=generator.uniform(0.08, 0.32),
        rotation_degrees=generator.uniform(0.0, 360.0),
        opacity=opacity,
        density=generator.uniform(0.05, 0.22),
        direction_degrees=generator.uniform(0.0, 360.0),
        extent=generator.uniform(0.05, 0.24),
    )


def _sample_edge_anchor(generator: Random) -> tuple[MarkOrigin, Point]:
    if generator.random() < 0.3:
        x = generator.choice((0.0, 1.0))
        y = generator.choice((0.0, 1.0))
        return "corner", Point(x=x, y=y)

    side = generator.choice(("top", "right", "bottom", "left"))
    coordinate = generator.uniform(_EDGE_BAND, 1.0 - _EDGE_BAND)
    if side == "top":
        return "edge", Point(x=coordinate, y=0.0)
    if side == "right":
        return "edge", Point(x=1.0, y=coordinate)
    if side == "bottom":
        return "edge", Point(x=coordinate, y=1.0)
    return "edge", Point(x=0.0, y=coordinate)


def _region_strength(x: float, y: float, exclusion: SoftExclusion) -> float:
    normalized_distance = hypot(
        (x - exclusion.center.x) / exclusion.radius_x,
        (y - exclusion.center.y) / exclusion.radius_y,
    )
    if normalized_distance <= 1.0:
        return 1.0
    feather_limit = 1.0 + exclusion.feather
    if normalized_distance >= feather_limit:
        return 0.0
    return 1.0 - (normalized_distance - 1.0) / exclusion.feather
