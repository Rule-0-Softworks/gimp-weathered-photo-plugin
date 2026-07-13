import json
from pathlib import Path

from gimp_weathered_photo_plugin.models import Point, Size, SoftExclusion
from gimp_weathered_photo_plugin.planning import plan_treatment, weighted_overlap

ASSETS = {
    "dry-rub-neutral-gray": Path("dry-rub-neutral-gray.gbr"),
    "dry-rub-umber": Path("dry-rub-umber.gbr"),
    "mottled-sepia": Path("mottled-sepia.gbr"),
    "water-stain-01": Path("water-stain-01.png"),
    "water-stain-02": Path("water-stain-02.png"),
    "water-stain-03": Path("water-stain-03.png"),
}
EXCLUSIONS = (
    SoftExclusion(
        center=Point(x=0.5, y=0.5),
        radius_x=0.25,
        radius_y=0.25,
        feather=0.2,
        source="emotional_center",
    ),
)


def test_default_plans_use_fresh_entropy() -> None:
    plans = [
        plan_treatment(Size(width=1600, height=900), EXCLUSIONS, ASSETS)
        for _ in range(6)
    ]

    assert len({plan.seed for plan in plans}) > 1
    sequences = {json.dumps(plan.to_dict(), sort_keys=True) for plan in plans}
    assert len(sequences) > 1


def test_default_plan_marks_start_at_edges_or_corners_and_avoid_protection() -> None:
    recipe = plan_treatment(Size(width=1600, height=900), EXCLUSIONS, ASSETS)

    assert recipe.marks
    for mark in recipe.marks:
        assert mark.origin in {"edge", "corner"}
        assert mark.anchor.x in {0.0, 1.0} or mark.anchor.y in {0.0, 1.0}
        assert weighted_overlap(mark, EXCLUSIONS) <= 0.15


def test_explicit_recipe_is_returned_for_replay() -> None:
    recipe = plan_treatment(Size(width=1600, height=900), EXCLUSIONS, ASSETS)

    replayed = plan_treatment(
        Size(width=1600, height=900), EXCLUSIONS, ASSETS, recipe=recipe
    )

    assert replayed == recipe
