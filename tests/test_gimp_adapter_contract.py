from pathlib import Path

from tests.test_models import make_recipe


class FakeOperations:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def retain_source(self) -> None:
        self.calls.append(("retain_source", None))

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
    assert ("apply_mark", Path("dry.gbr")) in operations.calls
    assert ("apply_local_blur", Path("water.png")) in operations.calls
