from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, ClassVar, Literal, Self, cast

MarkFamily = Literal["dry_rub", "mottled_sepia", "water_stain"]
MarkOrigin = Literal["edge", "corner"]
ExclusionSource = Literal["face", "hand", "emotional_center"]


def _require_mapping(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field_name} must be an object")
    return cast(dict[str, Any], value)


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float

    def __post_init__(self) -> None:
        coordinates = (self.x, self.y)
        if not all(isfinite(value) and 0.0 <= value <= 1.0 for value in coordinates):
            raise ValueError("point coordinates must be finite values in [0, 1]")

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: object) -> Self:
        values = _require_mapping(data, "point")
        return cls(x=float(values["x"]), y=float(values["y"]))


@dataclass(frozen=True, slots=True)
class Size:
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("dimensions must be positive")

    def to_dict(self) -> dict[str, int]:
        return {"width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, data: object) -> Self:
        values = _require_mapping(data, "size")
        return cls(width=int(values["width"]), height=int(values["height"]))


@dataclass(frozen=True, slots=True)
class SoftExclusion:
    sources: ClassVar[frozenset[str]] = frozenset({"face", "hand", "emotional_center"})

    center: Point
    radius_x: float
    radius_y: float
    feather: float
    source: ExclusionSource

    def __post_init__(self) -> None:
        values = (self.radius_x, self.radius_y, self.feather)
        if not all(isfinite(value) and 0.0 < value <= 1.0 for value in values):
            raise ValueError("exclusion radii and feather must be in (0, 1]")
        if self.source not in self.sources:
            raise ValueError("exclusion source is unsupported")

    def to_dict(self) -> dict[str, object]:
        return {
            "center": self.center.to_dict(),
            "radius_x": self.radius_x,
            "radius_y": self.radius_y,
            "feather": self.feather,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: object) -> Self:
        values = _require_mapping(data, "soft exclusion")
        return cls(
            center=Point.from_dict(values["center"]),
            radius_x=float(values["radius_x"]),
            radius_y=float(values["radius_y"]),
            feather=float(values["feather"]),
            source=cast(ExclusionSource, str(values["source"])),
        )


@dataclass(frozen=True, slots=True)
class Mark:
    families: ClassVar[frozenset[str]] = frozenset(
        {"dry_rub", "mottled_sepia", "water_stain"}
    )
    origins: ClassVar[frozenset[str]] = frozenset({"edge", "corner"})

    asset_id: str
    family: MarkFamily
    origin: MarkOrigin
    anchor: Point
    scale: float
    rotation_degrees: float
    opacity: float
    density: float
    direction_degrees: float
    extent: float

    def __post_init__(self) -> None:
        if not self.asset_id:
            raise ValueError("asset_id must not be empty")
        if self.family not in self.families:
            raise ValueError("mark family is unsupported")
        if self.origin not in self.origins:
            raise ValueError("mark origin must be edge or corner")
        unit_values = (self.scale, self.opacity, self.density, self.extent)
        if not all(isfinite(value) and 0.0 < value <= 1.0 for value in unit_values):
            raise ValueError("scale, opacity, density, and extent must be in (0, 1]")
        angles = (self.rotation_degrees, self.direction_degrees)
        if not all(isfinite(value) for value in angles):
            raise ValueError("mark angles must be finite")

    def to_dict(self) -> dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "family": self.family,
            "origin": self.origin,
            "anchor": self.anchor.to_dict(),
            "scale": self.scale,
            "rotation_degrees": self.rotation_degrees,
            "opacity": self.opacity,
            "density": self.density,
            "direction_degrees": self.direction_degrees,
            "extent": self.extent,
        }

    @classmethod
    def from_dict(cls, data: object) -> Self:
        values = _require_mapping(data, "mark")
        return cls(
            asset_id=str(values["asset_id"]),
            family=cast(MarkFamily, str(values["family"])),
            origin=cast(MarkOrigin, str(values["origin"])),
            anchor=Point.from_dict(values["anchor"]),
            scale=float(values["scale"]),
            rotation_degrees=float(values["rotation_degrees"]),
            opacity=float(values["opacity"]),
            density=float(values["density"]),
            direction_degrees=float(values["direction_degrees"]),
            extent=float(values["extent"]),
        )


@dataclass(frozen=True, slots=True)
class TreatmentRecipe:
    schema_version: int
    seed: int
    source_size: Size
    exclusions: tuple[SoftExclusion, ...]
    marks: tuple[Mark, ...]

    def __post_init__(self) -> None:
        if self.schema_version <= 0:
            raise ValueError("schema_version must be positive")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "seed": self.seed,
            "source_size": self.source_size.to_dict(),
            "exclusions": [exclusion.to_dict() for exclusion in self.exclusions],
            "marks": [mark.to_dict() for mark in self.marks],
        }

    @classmethod
    def from_dict(cls, data: object) -> Self:
        values = _require_mapping(data, "treatment recipe")
        exclusions = values["exclusions"]
        marks = values["marks"]
        if not isinstance(exclusions, list) or not isinstance(marks, list):
            raise ValueError("recipe exclusions and marks must be arrays")
        return cls(
            schema_version=int(values["schema_version"]),
            seed=int(values["seed"]),
            source_size=Size.from_dict(values["source_size"]),
            exclusions=tuple(SoftExclusion.from_dict(item) for item in exclusions),
            marks=tuple(Mark.from_dict(item) for item in marks),
        )
