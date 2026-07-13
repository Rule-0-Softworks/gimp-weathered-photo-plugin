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
