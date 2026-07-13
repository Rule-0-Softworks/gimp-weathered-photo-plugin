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


def test_native_water_stain_loads_its_png_asset_into_the_local_mask() -> None:
    from gimp_weathered_photo_plugin.gimp_host import _NativeGimpOperations

    calls: list[object] = []

    class Mask:
        pass

    class FloatingSelection:
        def floating_sel_anchor(self) -> None:
            calls.append("anchor")

    class AssetLayer:
        pass

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
            calls.append(drawables[0])
            return True

        @staticmethod
        def edit_paste(*_: object) -> list[object]:
            calls.append("paste")
            return [FloatingSelection()]

    class Gio:
        class File:
            @staticmethod
            def new_for_path(path: str) -> str:
                return path

    operations = _NativeGimpOperations(object(), object(), Gimp, object(), Gio)

    operations._apply_water_stain_asset(Mask(), Path("C:/assets/water-stain.png"))

    assert calls[0] == "load_asset"
    assert "paste" in calls
    assert "anchor" in calls
    assert calls[-1] == "delete_asset"


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
