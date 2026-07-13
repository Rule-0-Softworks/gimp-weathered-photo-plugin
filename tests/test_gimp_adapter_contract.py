import math
from pathlib import Path

import pytest

from tests.test_models import make_recipe


class FakeOperations:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def retain_source(self) -> None:
        self.calls.append(("retain_source", None))

    def apply_exclusions(self, exclusions: object) -> None:
        self.calls.append(("apply_exclusions", exclusions))

    def apply_mark(self, mark: object, asset: Path) -> None:
        self.calls.append(("apply_mark", asset))

    def apply_local_blur(self, mark: object, asset: Path) -> None:
        self.calls.append(("apply_local_blur", asset))


def test_apply_recipe_uses_editable_marks_and_only_local_water_stain_blur() -> None:
    from gimp_weathered_photo_plugin.gimp_host import apply_recipe

    recipe = make_recipe()
    operations = FakeOperations()
    assets = {
        "dry-rub-neutral-gray": Path("dry.gbr"),
        "water-stain-01": Path("water.png"),
    }

    apply_recipe(operations, recipe, assets)

    assert operations.calls[0] == ("retain_source", None)
    assert operations.calls[1] == ("apply_exclusions", recipe.exclusions)
    assert ("apply_mark", Path("dry.gbr")) in operations.calls
    assert ("apply_local_blur", Path("water.png")) in operations.calls


class FakeNativeOperations:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def retain_source(self) -> None:
        self.calls.append(("retain_source", None))

    def apply_exclusions(self, exclusions: object) -> None:
        self.calls.append(("apply_exclusions", exclusions))

    def apply_mark(self, mark: object, asset: Path) -> None:
        self.calls.append(("brush_mark", (mark, asset)))

    def apply_local_blur(self, mark: object, asset: Path) -> None:
        self.calls.append(("local_blur", (mark, asset)))


def test_apply_recipe_delivers_all_exclusions_before_editable_treatments() -> None:
    from gimp_weathered_photo_plugin.gimp_host import apply_recipe

    recipe = make_recipe()
    operations = FakeNativeOperations()
    assets = {
        "dry-rub-neutral-gray": Path("dry.gbr"),
        "water-stain-01": Path("water.png"),
    }

    apply_recipe(operations, recipe, assets)

    assert operations.calls[:2] == [
        ("retain_source", None),
        ("apply_exclusions", recipe.exclusions),
    ]
    assert operations.calls[2:] == [
        ("brush_mark", (recipe.marks[0], Path("dry.gbr"))),
        ("local_blur", (recipe.marks[1], Path("water.png"))),
    ]


def test_interactive_source_requires_an_unmodified_filesystem_backed_png() -> None:
    from gimp_weathered_photo_plugin.gimp_host import validate_interactive_source

    assert validate_interactive_source(Path("C:/photos/print.png"), False) == Path(
        "C:/photos/print.png"
    )

    with pytest.raises(ValueError, match="saved PNG"):
        validate_interactive_source(None, False)
    with pytest.raises(ValueError, match="PNG"):
        validate_interactive_source(Path("C:/photos/print.jpg"), False)
    with pytest.raises(ValueError, match="unmodified"):
        validate_interactive_source(Path("C:/photos/print.png"), True)


def test_native_water_stain_transforms_density_scales_and_anchors_its_mask_asset() -> (
    None
):
    from gimp_weathered_photo_plugin.gimp_host import _NativeGimpOperations

    calls: list[object] = []

    class Mask:
        pass

    class FloatingSelection:
        def set_opacity(self, opacity: float) -> bool:
            calls.append(("mask_opacity", opacity))
            return True

    class AssetLayer:
        def get_width(self) -> int:
            return 100

        def get_height(self) -> int:
            return 50

        def set_opacity(self, opacity: float) -> None:
            calls.append(("asset_opacity", opacity))

        def transform_2d(
            self,
            source_x: float,
            source_y: float,
            scale_x: float,
            scale_y: float,
            angle: float,
            destination_x: float,
            destination_y: float,
        ) -> None:
            calls.append(
                (
                    "transform",
                    (
                        source_x,
                        source_y,
                        scale_x,
                        scale_y,
                        angle,
                        destination_x,
                        destination_y,
                    ),
                )
            )

    class AssetImage:
        def get_layers(self) -> list[AssetLayer]:
            return [AssetLayer()]

        def delete(self) -> None:
            calls.append("delete_asset")

    class Gimp:
        RunMode = type("RunMode", (), {"NONINTERACTIVE": object()})

        @staticmethod
        def file_load(*_: object) -> AssetImage:
            calls.append("load_asset")
            return AssetImage()

        @staticmethod
        def edit_copy(drawables: list[object]) -> bool:
            calls.append(("copy", drawables[0]))
            return True

        @staticmethod
        def edit_paste(*_: object) -> list[object]:
            calls.append("paste")
            return [FloatingSelection()]

        @staticmethod
        def floating_sel_anchor(selection: FloatingSelection) -> bool:
            calls.append(("anchor", selection))
            return True

    class Gio:
        class File:
            @staticmethod
            def new_for_path(path: str) -> str:
                return path

    image = type(
        "Image", (), {"get_width": lambda _: 400, "get_height": lambda _: 200}
    )()
    operations = _NativeGimpOperations(image, object(), Gimp, object(), Gio)
    mark = make_recipe().marks[1]

    operations._apply_water_stain_asset(Mask(), mark, Path("C:/assets/water-stain.png"))

    assert calls[0] == "load_asset"
    transform_call = (
        "transform",
        (
            50.0,
            25.0,
            0.6,
            0.6,
            math.radians(mark.rotation_degrees),
            mark.anchor.x * 400,
            mark.anchor.y * 200,
        ),
    )
    copy_index = next(
        index
        for index, call in enumerate(calls)
        if isinstance(call, tuple) and call[0] == "copy"
    )
    assert transform_call in calls
    assert "paste" in calls
    assert calls.index(transform_call) < copy_index
    assert ("mask_opacity", mark.density * 100.0) in calls
    assert any(isinstance(call, tuple) and call[0] == "anchor" for call in calls)
    assert calls[-1] == "delete_asset"


def test_native_water_stain_mask_is_clipped_to_the_source_alpha() -> None:
    from gimp_weathered_photo_plugin.gimp_host import _NativeGimpOperations

    calls: list[tuple[str, object]] = []

    class Mask:
        def edit_clear(self) -> None:
            calls.append(("clear", None))

    class Image:
        def select_item(self, operation: object, source: object) -> None:
            calls.append(("select_item", (operation, source)))

    class Selection:
        @staticmethod
        def invert(image: object) -> None:
            calls.append(("invert", image))

        @staticmethod
        def none(image: object) -> None:
            calls.append(("none", image))

    Gimp = type(
        "Gimp",
        (),
        {
            "ChannelOps": type("ChannelOps", (), {"REPLACE": "replace"}),
            "Selection": Selection,
        },
    )
    image = Image()
    source = object()

    _NativeGimpOperations(
        image, source, Gimp, object(), object()
    )._clip_mask_to_source_alpha(Mask())

    assert calls == [
        ("select_item", ("replace", source)),
        ("invert", image),
        ("clear", None),
        ("none", image),
    ]


def test_native_water_stain_blur_layer_uses_the_mark_opacity() -> None:
    from gimp_weathered_photo_plugin.gimp_host import _NativeGimpOperations

    calls: list[tuple[str, object]] = []

    class Mask:
        def edit_clear(self) -> None:
            calls.append(("clear", None))

    class BlurredLayer:
        def set_name(self, name: str) -> None:
            calls.append(("name", name))

        def set_opacity(self, opacity: float) -> None:
            calls.append(("layer_opacity", opacity))

        def create_mask(self, _: object) -> Mask:
            return Mask()

        def add_mask(self, _: Mask) -> None:
            calls.append(("add_mask", None))

    class Source:
        def copy(self) -> BlurredLayer:
            return BlurredLayer()

    class AssetLayer:
        def get_width(self) -> int:
            return 100

        def get_height(self) -> int:
            return 100

        def transform_2d(self, *_: object) -> None:
            calls.append(("transform", None))

    class AssetImage:
        def get_layers(self) -> list[AssetLayer]:
            return [AssetLayer()]

        def delete(self) -> None:
            calls.append(("delete_asset", None))

    class PastedLayer:
        def set_opacity(self, _: float) -> bool:
            return True

    class Filter:
        def get_config(self) -> "Filter":
            return self

        def set_property(self, *_: object) -> None:
            pass

        def merge_filter(self) -> None:
            calls.append(("merge_blur", None))

    class Image:
        def get_width(self) -> int:
            return 400

        def get_height(self) -> int:
            return 200

        def insert_layer(self, *_: object) -> None:
            calls.append(("insert_layer", None))

        def select_item(self, *_: object) -> None:
            calls.append(("select_source", None))

    class Selection:
        @staticmethod
        def invert(_: Image) -> None:
            calls.append(("invert", None))

        @staticmethod
        def none(_: Image) -> None:
            calls.append(("none", None))

    Gimp = type(
        "Gimp",
        (),
        {
            "RunMode": type("RunMode", (), {"NONINTERACTIVE": object()}),
            "AddMaskType": type("AddMaskType", (), {"BLACK": "black"}),
            "ChannelOps": type("ChannelOps", (), {"REPLACE": "replace"}),
            "Selection": Selection,
            "DrawableFilter": type(
                "DrawableFilter", (), {"new": staticmethod(lambda *_: Filter())}
            ),
            "file_load": staticmethod(lambda *_: AssetImage()),
            "edit_copy": staticmethod(lambda *_: True),
            "edit_paste": staticmethod(lambda *_: [PastedLayer()]),
            "floating_sel_anchor": staticmethod(lambda _: True),
        },
    )

    class Gio:
        class File:
            @staticmethod
            def new_for_path(path: str) -> str:
                return path

    source = Source()
    operations = _NativeGimpOperations(Image(), source, Gimp, object(), Gio)
    operations.apply_exclusions(())
    mark = make_recipe().marks[1]

    operations.apply_local_blur(mark, Path("C:/assets/water-stain.png"))

    assert ("layer_opacity", mark.opacity * 100.0) in calls
    assert ("merge_blur", None) in calls


def test_native_layers_receive_a_source_alpha_mask_from_the_source_selection() -> None:
    from gimp_weathered_photo_plugin.gimp_host import _NativeGimpOperations

    calls: list[tuple[str, object]] = []

    class Layer:
        def create_mask(self, kind: object) -> str:
            calls.append(("create_mask", kind))
            return "mask"

        def add_mask(self, mask: str) -> None:
            calls.append(("add_mask", mask))

    class Image:
        def select_item(self, operation: object, source: object) -> None:
            calls.append(("select_item", (operation, source)))

    class Selection:
        @staticmethod
        def none(image: object) -> None:
            calls.append(("selection_none", image))

    Gimp = type(
        "Gimp",
        (),
        {
            "ChannelOps": type("ChannelOps", (), {"REPLACE": "replace"}),
            "AddMaskType": type("AddMaskType", (), {"SELECTION": "selection"}),
            "Selection": Selection,
        },
    )

    source = object()
    image = Image()
    operations = _NativeGimpOperations(image, source, Gimp, object(), object())

    operations._add_source_alpha_mask(Layer())

    assert calls == [
        ("select_item", ("replace", source)),
        ("create_mask", "selection"),
        ("add_mask", "mask"),
        ("selection_none", image),
    ]


def test_interactive_request_parses_a_recipe_and_absolute_asset_map() -> None:
    import json

    from gimp_weathered_photo_plugin.gimp_host import parse_interactive_request

    recipe = make_recipe()

    parsed_recipe, assets = parse_interactive_request(
        json.dumps(recipe.to_dict()),
        json.dumps(
            {
                "dry-rub-neutral-gray": "C:/assets/dry.gbr",
                "water-stain-01": "C:/assets/water.png",
            }
        ),
    )

    assert parsed_recipe == recipe
    assert assets["water-stain-01"] == Path("C:/assets/water.png")
