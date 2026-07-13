from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, cast

from gimp_weathered_photo_plugin.models import Mark, SoftExclusion, TreatmentRecipe


class GimpOperations(Protocol):
    def retain_source(self) -> None: ...

    def apply_exclusions(self, exclusions: Sequence[SoftExclusion]) -> None: ...

    def apply_mark(self, mark: Mark, asset: Path) -> None: ...

    def apply_local_blur(self, mark: Mark, asset: Path) -> None: ...


def apply_recipe(
    operations: GimpOperations,
    recipe: TreatmentRecipe,
    assets: Mapping[str, Path],
) -> None:
    operations.retain_source()
    operations.apply_exclusions(recipe.exclusions)
    for mark in recipe.marks:
        asset = assets[mark.asset_id]
        if mark.family == "water_stain":
            operations.apply_local_blur(mark, asset)
        else:
            operations.apply_mark(mark, asset)


def validate_interactive_source(path: Path | None, is_dirty: bool) -> Path:
    if path is None:
        raise ValueError("interactive rendering requires a saved PNG")
    if path.suffix.lower() != ".png":
        raise ValueError("interactive rendering requires a saved PNG")
    if is_dirty:
        raise ValueError("interactive rendering requires an unmodified PNG")
    return path


def parse_interactive_request(
    recipe_json: str, asset_map_json: str
) -> tuple[TreatmentRecipe, dict[str, Path]]:
    try:
        recipe = TreatmentRecipe.from_dict(json.loads(recipe_json))
        raw_assets = cast(dict[str, str], json.loads(asset_map_json))
        assets = {asset_id: Path(path) for asset_id, path in raw_assets.items()}
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("interactive recipe or asset map is invalid") from error
    if not all(path.is_absolute() for path in assets.values()):
        raise ValueError("interactive asset paths must be absolute")
    return recipe, assets


@dataclass(frozen=True, slots=True)
class ConsoleRequest:
    source: Path
    png: Path
    xcf: Path
    recipe: TreatmentRecipe
    assets: Mapping[str, Path]

    @classmethod
    def from_json(cls, payload: str) -> ConsoleRequest:
        try:
            data = cast(dict[str, Any], json.loads(payload))
            source = Path(cast(str, data["source"]))
            png = Path(cast(str, data["png"]))
            xcf = Path(cast(str, data["xcf"]))
            assets = {
                asset_id: Path(path)
                for asset_id, path in cast(dict[str, str], data["assets"]).items()
            }
            recipe = TreatmentRecipe.from_dict(data["recipe"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("GIMP console request is invalid") from error
        if not all(path.is_absolute() for path in (source, png, xcf)):
            raise ValueError("GIMP console request paths must be absolute")
        if not all(path.is_absolute() for path in assets.values()):
            raise ValueError("GIMP console asset paths must be absolute")
        if source.suffix.lower() != ".png":
            raise ValueError("GIMP console source must be a PNG")
        return cls(source, png, xcf, recipe, assets)


def run_console_request(request_path: str) -> None:
    """Run a serialized render request inside GIMP's Python interpreter.

    This is intentionally the only code path that imports ``gi.repository``.
    Standard CPython can import the rest of this module without GIMP installed.
    """

    request = ConsoleRequest.from_json(Path(request_path).read_text(encoding="utf-8"))
    Gimp, Gegl, Gio = _load_gimp()
    image = Gimp.file_load(
        Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(str(request.source))
    )
    if image is None:
        raise RuntimeError("GIMP could not load the staged source")
    if (image.get_width(), image.get_height()) != (
        request.recipe.source_size.width,
        request.recipe.source_size.height,
    ):
        raise ValueError("staged source dimensions do not match the recipe")
    layers = image.get_layers()
    if not layers:
        raise RuntimeError("staged source has no drawable layer")
    try:
        operations = _NativeGimpOperations(image, layers[0], Gimp, Gegl, Gio)
        apply_recipe(operations, request.recipe, request.assets)
        if not Gimp.file_save(
            Gimp.RunMode.NONINTERACTIVE,
            image,
            Gio.File.new_for_path(str(request.xcf)),
            None,
        ):
            raise RuntimeError("GIMP could not save the staged XCF")
        if not Gimp.file_save(
            Gimp.RunMode.NONINTERACTIVE,
            image,
            Gio.File.new_for_path(str(request.png)),
            None,
        ):
            raise RuntimeError("GIMP could not export the staged PNG")
    finally:
        image.delete()


def _load_gimp() -> tuple[Any, Any, Any]:
    gi = import_module("gi")
    gi.require_version("Gegl", "0.4")
    gi.require_version("Gimp", "3.0")
    repository = import_module("gi.repository")
    Gegl = repository.Gegl
    Gio = repository.Gio
    Gimp = repository.Gimp

    Gegl.init(None)
    return Gimp, Gegl, Gio


class _NativeGimpOperations:
    def __init__(self, image: Any, source: Any, gimp: Any, gegl: Any, gio: Any) -> None:
        self._image = image
        self._source = source
        self._gimp = gimp
        self._gegl = gegl
        self._gio = gio
        self._exclusions: tuple[SoftExclusion, ...] = ()

    def retain_source(self) -> None:
        # The loaded layer remains untouched; every treatment is a new layer.
        self._source.set_name("Source (original)")

    def apply_exclusions(self, exclusions: Sequence[SoftExclusion]) -> None:
        self._exclusions = tuple(exclusions)

    def apply_mark(self, mark: Mark, asset: Path) -> None:
        layer = self._new_treatment_layer(
            f"Weathered {mark.family}: {asset.stem}", mark
        )
        mask = self._add_source_alpha_mask(layer)
        self._paint_with_brush(layer, mark, asset)
        self._paint_mask_with_brush(mask, mark, asset)
        self._apply_exclusions(mask)
        layer.transform_rotate(math.radians(mark.rotation_degrees), True, 0.0, 0.0)
        layer.set_mode(
            self._gimp.LayerMode.MULTIPLY
            if mark.family == "mottled_sepia"
            else self._gimp.LayerMode.NORMAL
        )

    def apply_local_blur(self, mark: Mark, asset: Path) -> None:
        blurred_source = self._source.copy()
        blurred_source.set_name(f"Water stain blur: {asset.stem}")
        blurred_source.set_opacity(mark.opacity * 100.0)
        self._image.insert_layer(blurred_source, None, 0)
        mask = self._add_black_mask(blurred_source)
        self._apply_water_stain_asset(mask, mark, asset)
        self._clip_mask_to_source_alpha(mask)
        self._apply_exclusions(mask)
        blur = self._gimp.DrawableFilter.new(blurred_source, "gegl:gaussian-blur", None)
        config = blur.get_config()
        radius = max(
            1.0, min(self._image.get_width(), self._image.get_height()) * mark.scale / 8
        )
        config.set_property("std-dev-x", radius)
        config.set_property("std-dev-y", radius)
        blur.merge_filter()

    def _new_treatment_layer(self, name: str, mark: Mark) -> Any:
        layer = self._gimp.Layer.new(
            self._image,
            name,
            self._image.get_width(),
            self._image.get_height(),
            self._source.type_with_alpha(),
            mark.opacity * 100.0,
            self._gimp.LayerMode.NORMAL,
        )
        layer.fill(self._gimp.FillType.TRANSPARENT)
        self._image.insert_layer(layer, None, 0)
        return layer

    def _add_source_alpha_mask(self, layer: Any) -> Any:
        self._image.select_item(self._gimp.ChannelOps.REPLACE, self._source)
        try:
            mask = layer.create_mask(self._gimp.AddMaskType.SELECTION)
            layer.add_mask(mask)
            return mask
        finally:
            self._gimp.Selection.none(self._image)

    def _add_black_mask(self, layer: Any) -> Any:
        mask = layer.create_mask(self._gimp.AddMaskType.BLACK)
        layer.add_mask(mask)
        return mask

    def _paint_with_brush(self, layer: Any, mark: Mark, asset: Path) -> None:
        brush = self._gimp.Brush.get_by_name(asset.stem)
        if brush is None:
            raise RuntimeError(f"GIMP could not find staged brush {asset.stem}")
        self._gimp.context_push()
        try:
            self._gimp.context_set_brush(brush)
            self._gimp.context_set_brush_size(
                max(
                    1.0,
                    min(self._image.get_width(), self._image.get_height()) * mark.scale,
                )
            )
            self._gimp.context_set_brush_angle(mark.direction_degrees)
            self._gimp.context_set_opacity(mark.opacity * 100.0)
            self._gimp.pencil(
                layer,
                [
                    mark.anchor.x * self._image.get_width(),
                    mark.anchor.y * self._image.get_height(),
                ],
            )
        finally:
            self._gimp.context_pop()

    def _paint_mask_with_brush(self, mask: Any, mark: Mark, asset: Path) -> None:
        brush = self._gimp.Brush.get_by_name(asset.stem)
        if brush is None:
            raise RuntimeError(f"GIMP could not find staged brush {asset.stem}")
        self._gimp.context_push()
        try:
            self._gimp.context_set_brush(brush)
            self._gimp.context_set_foreground(self._gegl.Color.new("white"))
            self._gimp.context_set_brush_size(
                max(
                    1.0,
                    min(self._image.get_width(), self._image.get_height()) * mark.scale,
                )
            )
            self._gimp.context_set_brush_angle(mark.direction_degrees)
            self._gimp.context_set_opacity(mark.density * 100.0)
            self._gimp.pencil(
                mask,
                [
                    mark.anchor.x * self._image.get_width(),
                    mark.anchor.y * self._image.get_height(),
                ],
            )
        finally:
            self._gimp.context_pop()

    def _apply_water_stain_asset(self, mask: Any, mark: Mark, asset: Path) -> None:
        asset_image = self._gimp.file_load(
            self._gimp.RunMode.NONINTERACTIVE,
            self._gio.File.new_for_path(str(asset)),
        )
        try:
            asset_layers = asset_image.get_layers()
            if not asset_layers:
                raise RuntimeError(f"GIMP could not load water-stain mask {asset.stem}")
            asset_layer = asset_layers[0]
            target_size = (
                min(self._image.get_width(), self._image.get_height()) * mark.scale
            )
            asset_extent = max(asset_layer.get_width(), asset_layer.get_height())
            scale = target_size / asset_extent
            asset_layer.transform_2d(
                asset_layer.get_width() / 2.0,
                asset_layer.get_height() / 2.0,
                scale,
                scale,
                math.radians(mark.rotation_degrees),
                mark.anchor.x * self._image.get_width(),
                mark.anchor.y * self._image.get_height(),
            )
            if not self._gimp.edit_copy([asset_layer]):
                raise RuntimeError(f"GIMP could not load water-stain mask {asset.stem}")
            pasted = self._gimp.edit_paste(mask, False)
            if not pasted:
                raise RuntimeError(
                    f"GIMP could not paste water-stain mask {asset.stem}"
                )
            if not pasted[0].set_opacity(mark.density * 100.0):
                raise RuntimeError(
                    f"GIMP could not set water-stain mask density {asset.stem}"
                )
            if not self._gimp.floating_sel_anchor(pasted[0]):
                raise RuntimeError(
                    f"GIMP could not anchor water-stain mask {asset.stem}"
                )
        finally:
            asset_image.delete()

    def _clip_mask_to_source_alpha(self, mask: Any) -> None:
        self._image.select_item(self._gimp.ChannelOps.REPLACE, self._source)
        try:
            self._gimp.Selection.invert(self._image)
            mask.edit_clear()
        finally:
            self._gimp.Selection.none(self._image)

    def _apply_exclusions(self, mask: Any) -> None:
        for exclusion in self._exclusions:
            width = exclusion.radius_x * 2.0 * self._image.get_width()
            height = exclusion.radius_y * 2.0 * self._image.get_height()
            x = exclusion.center.x * self._image.get_width() - width / 2.0
            y = exclusion.center.y * self._image.get_height() - height / 2.0
            self._image.select_ellipse(self._gimp.ChannelOps.ADD, x, y, width, height)
            self._gimp.Selection.feather(
                self._image,
                exclusion.feather
                * min(self._image.get_width(), self._image.get_height()),
            )
            mask.edit_clear()
        self._gimp.Selection.none(self._image)


def main() -> None:
    """Register the real GIMP 3 procedures when this file is run by GIMP."""

    Gimp, GLib, GObject = _load_gimp_plugin_runtime()
    _gimp, _Gegl, _Gio = _load_gimp()

    def run_interactive(
        procedure: Any,
        run_mode: Any,
        image: Any,
        drawables: Any,
        config: Any,
        data: Any,
    ) -> Any:
        del run_mode, image, drawables, config, data
        return procedure.new_return_values(
            Gimp.PDBStatusType.CALLING_ERROR,
            GLib.Error(
                "interactive rendering is unavailable; use the batch console renderer"
            ),
        )

    def run_batch(
        procedure: Any, run_mode: Any, request_path: str, config: Any, data: Any
    ) -> Any:
        del run_mode, config, data
        try:
            run_console_request(request_path)
        except Exception as error:
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error(str(error))
            )
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

    class WeatheredPhotoPlugin(Gimp.PlugIn):
        def do_query_procedures(self) -> list[str]:
            return ["python-fu-weathered-photo", "python-fu-weathered-photo-render"]

        def do_create_procedure(self, name: str) -> Any:
            if name == "python-fu-weathered-photo":
                procedure = Gimp.ImageProcedure.new(
                    self, name, Gimp.PDBProcType.PLUGIN, run_interactive, None
                )
                procedure.set_image_types("RGB*, GRAY*")
                procedure.set_menu_label("Weathered Photo")
                procedure.add_menu_path("<Image>/Filters/Artistic")
                procedure.add_string_argument(
                    "recipe-json",
                    "Recipe JSON",
                    "Validated treatment recipe JSON",
                    "",
                    GObject.ParamFlags.READWRITE,
                )
                procedure.add_string_argument(
                    "asset-map-json",
                    "Asset map JSON",
                    "Absolute asset-path map JSON",
                    "",
                    GObject.ParamFlags.READWRITE,
                )
                return procedure
            procedure = Gimp.BatchProcedure.new(
                self, name, "Python 3", Gimp.PDBProcType.PLUGIN, run_batch, None
            )
            procedure.add_string_argument(
                "request-path",
                "Request path",
                "Absolute JSON request path",
                "",
                GObject.ParamFlags.READWRITE,
            )
            return procedure

    import sys

    Gimp.main(WeatheredPhotoPlugin.__gtype__, sys.argv)


def _load_gimp_plugin_runtime() -> tuple[Any, Any, Any]:
    gi = import_module("gi")
    gi.require_version("Gimp", "3.0")
    repository = import_module("gi.repository")
    GLib = repository.GLib
    Gimp = repository.Gimp
    GObject = repository.GObject

    return Gimp, GLib, GObject


if __name__ == "__main__":
    main()
