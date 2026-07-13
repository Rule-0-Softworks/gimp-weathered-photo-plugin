import json
from pathlib import Path

import pytest

from gimp_weathered_photo_plugin.models import Point, Size, SoftExclusion

EXCLUSION: dict[str, object] = {
    "center": {"x": 0.5, "y": 0.5},
    "radius_x": 0.3,
    "radius_y": 0.28,
    "feather": 0.3,
    "source": "emotional_center",
}


def _response_payload(
    *, exclusions: list[dict[str, object]] | None = None
) -> dict[str, object]:
    return {
        "bridge_schema_version": 2,
        "source_sha256": "a" * 64,
        "detectors": {
            "face": "no_detection",
            "hand": "no_detection",
            "saliency": "detected",
        },
        "adapter_configuration": {
            "model.face-landmarker.version": "gcs-generation-1683136941468629"
        },
        "exclusions": exclusions or [EXCLUSION],
    }


def test_request_serializes_immutable_input_identity() -> None:
    from gimp_weathered_photo_plugin.bridge_protocol import AnalysisRequest

    request = AnalysisRequest(
        bridge_schema_version=2,
        source_path=Path("C:/staging/job/source.png"),
        source_sha256="a" * 64,
        source_size=Size(width=1600, height=1200),
    )

    assert request.to_dict() == {
        "bridge_schema_version": 2,
        "source_path": "C:/staging/job/source.png",
        "source_sha256": "a" * 64,
        "source_size": {"width": 1600, "height": 1200},
    }


def test_response_parses_bounded_normalized_exclusions() -> None:
    from gimp_weathered_photo_plugin.bridge_protocol import parse_response_json

    response = parse_response_json(json.dumps(_response_payload()))

    assert response.exclusions == (
        SoftExclusion(
            center=Point(x=0.5, y=0.5),
            radius_x=0.3,
            radius_y=0.28,
            feather=0.3,
            source="emotional_center",
        ),
    )
    assert response.detectors["saliency"] == "detected"


def test_response_requires_bounded_string_adapter_configuration() -> None:
    from gimp_weathered_photo_plugin.bridge_protocol import parse_response_json

    response = parse_response_json(
        '{"bridge_schema_version":2,"source_sha256":"'
        + "a" * 64
        + '","detectors":{"face":"no_detection","hand":"no_detection",'
        '"saliency":"detected"},"adapter_configuration":'
        '{"model.face-landmarker.version":"gcs-generation-1683136941468629"},'
        '"exclusions":[]}'
    )

    assert (
        response.adapter_configuration["model.face-landmarker.version"]
        == "gcs-generation-1683136941468629"
    )


def test_response_rejects_non_string_adapter_configuration_values() -> None:
    from gimp_weathered_photo_plugin.bridge_protocol import (
        BridgeProtocolError,
        parse_response_json,
    )

    payload = _response_payload()
    payload["adapter_configuration"] = {"model.face-landmarker.version": 1}

    with pytest.raises(BridgeProtocolError, match="adapter_configuration"):
        parse_response_json(json.dumps(payload))


def test_response_rejects_adapter_configuration_lone_surrogate() -> None:
    from gimp_weathered_photo_plugin.bridge_protocol import (
        BridgeProtocolError,
        parse_response_json,
    )

    document = (
        '{"bridge_schema_version":2,"source_sha256":"'
        + "a" * 64
        + '","detectors":{"face":"no_detection","hand":"no_detection",'
        '"saliency":"detected"},"adapter_configuration":{"model":"\\ud800"},'
        '"exclusions":[]}'
    )

    with pytest.raises(BridgeProtocolError, match="adapter_configuration"):
        parse_response_json(document)


@pytest.mark.parametrize(
    "document",
    [
        json.dumps(
            _response_payload(exclusions=[{**EXCLUSION, "radius_x": float("nan")}])
        ),
        json.dumps(_response_payload(exclusions=[EXCLUSION] * 33)),
        json.dumps(_response_payload()) + "\n" + json.dumps(_response_payload()),
    ],
)
def test_response_rejects_untrusted_geometry_and_multiple_documents(
    document: str,
) -> None:
    from gimp_weathered_photo_plugin.bridge_protocol import (
        BridgeProtocolError,
        parse_response_json,
    )

    with pytest.raises(BridgeProtocolError):
        parse_response_json(document)
