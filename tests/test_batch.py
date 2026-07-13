from pathlib import Path

from gimp_weathered_photo_plugin.batch import process_batch
from tests.test_models import make_recipe


class FakeRenderer:
    def __init__(self, failing_source: Path | None = None) -> None:
        self.calls: list[Path] = []
        self.failing_source = failing_source

    def render(
        self, source: Path, png: Path, xcf: Path, recipe: object, assets: object
    ) -> None:
        self.calls.append(source)
        if source == self.failing_source:
            raise RuntimeError("render failed")
        png.write_bytes(b"png")
        xcf.write_bytes(b"xcf")


def test_batch_continues_after_one_failure_and_writes_three_outputs(
    tmp_path: Path,
) -> None:
    failed = tmp_path / "failed.png"
    succeeded = tmp_path / "succeeded.png"
    failed.write_bytes(b"failed")
    succeeded.write_bytes(b"succeeded")
    renderer = FakeRenderer(failing_source=failed)

    results = process_batch(
        [failed, succeeded],
        tmp_path / "out",
        renderer,
        assets={"dry-rub-neutral-gray": Path("brush.gbr")},
        recipe_factory=lambda _source: make_recipe(),
    )

    assert [result.success for result in results] == [False, True]
    assert renderer.calls == [failed, succeeded]
    assert (tmp_path / "out/succeeded-worn.png").is_file()
    assert (tmp_path / "out/succeeded-worn.xcf").is_file()
    assert (tmp_path / "out/succeeded-worn.recipe.json").is_file()
