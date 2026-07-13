import numpy as np
import pytest

from gimp_weathered_photo_plugin.models import Mark, Point
from gimp_weathered_photo_plugin.protection import (
    build_protection_regions,
    overlap_fraction,
)


def test_landmarks_and_saliency_produce_feathered_soft_regions() -> None:
    image = np.zeros((100, 200, 3), dtype=np.uint8)

    regions = build_protection_regions(
        image,
        face_detector=lambda _image: ((Point(x=0.3, y=0.35),),),
        hand_detector=lambda _image: ((Point(x=0.7, y=0.65),),),
        saliency_center=lambda _image: Point(x=0.55, y=0.45),
    )

    assert {region.source for region in regions} == {
        "face",
        "hand",
        "emotional_center",
    }
    assert all(region.feather > 0.0 for region in regions)
    assert all(region.radius_x != 1.0 or region.radius_y != 1.0 for region in regions)


def test_saliency_center_protects_image_when_no_landmarks_are_found() -> None:
    image = np.zeros((100, 200, 3), dtype=np.uint8)

    regions = build_protection_regions(
        image,
        face_detector=lambda _image: (),
        hand_detector=lambda _image: (),
        saliency_center=lambda _image: Point(x=0.6, y=0.4),
    )

    assert len(regions) == 1
    assert regions[0].source == "emotional_center"
    assert regions[0].center == Point(x=0.6, y=0.4)


def test_face_candidate_has_more_overlap_than_an_edge_candidate() -> None:
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    regions = build_protection_regions(
        image,
        face_detector=lambda _image: ((Point(x=0.5, y=0.5),),),
        hand_detector=lambda _image: (),
        saliency_center=lambda _image: Point(x=0.5, y=0.5),
    )
    face_mark = make_mark(Point(x=0.5, y=0.5))
    edge_mark = make_mark(Point(x=0.0, y=0.1))

    assert overlap_fraction(face_mark, regions) > overlap_fraction(edge_mark, regions)


def test_protection_requires_injected_landmark_detectors() -> None:
    image = np.zeros((3, 3, 3), dtype=np.uint8)

    with pytest.raises(
        ValueError, match="face_detector and hand_detector are required"
    ):
        build_protection_regions(image)


def make_mark(anchor: Point) -> Mark:
    return Mark(
        asset_id="dry-rub-neutral-gray",
        family="dry_rub",
        origin="edge",
        anchor=anchor,
        scale=0.2,
        rotation_degrees=0.0,
        opacity=0.05,
        density=0.1,
        direction_degrees=0.0,
        extent=0.1,
    )
