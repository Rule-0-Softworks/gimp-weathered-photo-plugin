from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_smoke_guide_documents_the_native_batch_boundary_and_verification() -> None:
    guide = (ROOT / "docs/gimp-smoke-test.md").read_text(encoding="utf-8").lower()

    required_phrases = (
        "python 3.12+",
        "standard cpython",
        "uv sync --locked",
        "gimp 3",
        "plug-in discovery",
        "batch-only",
        "--gimp-console",
        "--analyzer-executable",
        "mediapipe",
        "opencv",
        "temporary gimp brush configuration",
        "staging cleanup",
        "--replay-recipe",
        "alpha",
        "dimensions",
        "xcf",
        "layers",
        "masks",
        "failure diagnosis",
        "exactly four",
        "approved vezor png",
    )

    assert all(phrase in guide for phrase in required_phrases)


def test_readme_exposes_the_batch_only_entry_point_without_claiming_proof() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()

    assert "python -m gimp_weathered_photo_plugin" in readme
    assert "batch-only" in readme
    assert "--replay-recipe" in readme
    assert "four approved" in readme
    assert "visually validated" not in readme
