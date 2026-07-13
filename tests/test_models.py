import json
from typing import cast

import pytest

from gimp_weathered_photo_plugin.models import (
    Mark,
    MarkOrigin,
    Point,
    Size,
    SoftExclusion,
    TreatmentRecipe,
)


def make_recipe() -> TreatmentRecipe:
    return TreatmentRecipe(
        schema_version=1,
        seed=42,
        source_size=Size(width=1600, height=900),
        exclusions=(
            SoftExclusion(
                center=Point(x=0.5, y=0.5),
                radius_x=0.2,
                radius_y=0.25,
                feather=0.1,
                source="emotional_center",
            ),
        ),
        marks=(
            Mark(
                asset_id="dry-rub-neutral-gray",
                family="dry_rub",
                origin="edge",
                anchor=Point(x=0.0, y=0.2),
                scale=0.25,
                rotation_degrees=15.0,
                opacity=0.08,
                density=0.2,
                direction_degrees=90.0,
                extent=0.15,
            ),
            Mark(
                asset_id="water-stain-01",
                family="water_stain",
                origin="corner",
                anchor=Point(x=1.0, y=1.0),
                scale=0.3,
                rotation_degrees=240.0,
                opacity=0.05,
                density=0.1,
                direction_degrees=225.0,
                extent=0.2,
            ),
        ),
    )


def test_recipe_round_trips_through_json_safe_data() -> None:
    recipe = make_recipe()

    encoded = json.dumps(recipe.to_dict())

    assert TreatmentRecipe.from_dict(json.loads(encoded)) == recipe


@pytest.mark.parametrize("width,height", [(0, 1), (1, 0), (-1, 2)])
def test_size_rejects_non_positive_dimensions(width: int, height: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        Size(width=width, height=height)


@pytest.mark.parametrize("opacity", [0.0, -0.01, 1.01])
def test_mark_rejects_opacity_outside_open_closed_unit_interval(
    opacity: float,
) -> None:
    with pytest.raises(ValueError, match="opacity"):
        Mark(
            asset_id="dry-rub-neutral-gray",
            family="dry_rub",
            origin="edge",
            anchor=Point(x=0.0, y=0.2),
            scale=0.25,
            rotation_degrees=15.0,
            opacity=opacity,
            density=0.2,
            direction_degrees=90.0,
            extent=0.15,
        )


def test_mark_rejects_non_edge_or_corner_origin() -> None:
    with pytest.raises(ValueError, match="origin"):
        Mark(
            asset_id="dry-rub-neutral-gray",
            family="dry_rub",
            origin=cast(MarkOrigin, "center"),
            anchor=Point(x=0.5, y=0.5),
            scale=0.25,
            rotation_degrees=15.0,
            opacity=0.08,
            density=0.2,
            direction_degrees=90.0,
            extent=0.15,
        )
