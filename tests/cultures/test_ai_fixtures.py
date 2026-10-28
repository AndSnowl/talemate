"""The AI world's culture files (tests/ai/data/) are valid and sound distinct.

The AI tests check that a name the model picked came from the scene's
culture. That only works if the two cultures' names can't pass for each
other, so `fits` is checked both ways on rolled names.
"""

import random
from pathlib import Path

import pytest

from talemate.cultures.exchange import CultureFile
from talemate.languages.generator import fits, roll, validate_language

DATA_DIR = Path(__file__).resolve().parents[1] / "ai" / "data"
FILES = {
    "taelrik": DATA_DIR / "taelrik.culture.json",
    "elsiri": DATA_DIR / "elsiri.culture.json",
}
SAMPLE = 20
MAX_CROSS_FITS = 3
MIN_ROLLED = 10


def _load(culture_id: str) -> CultureFile:
    return CultureFile.model_validate_json(
        FILES[culture_id].read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("culture_id", sorted(FILES))
def test_ai_fixtures_validate(culture_id):
    file = _load(culture_id)
    assert file.culture.id == culture_id
    validate_language(file.culture.language)


def test_ai_fixtures_shape():
    taelrik, elsiri = _load("taelrik"), _load("elsiri")
    assert "given_female" in {g.id for g in taelrik.culture.language.generators}

    culture = elsiri.culture
    assert culture.language.level == "naming"
    assert culture.color == "#4FC3F7"
    assert culture.description and culture.language.sound
    assert len(culture.customs) == 3
    assert {g.id for g in culture.language.generators} == {
        "given_female",
        "given_male",
        "place_names",
    }
    assert {entry.text for entry in elsiri.glossary} == {"Ilsara", "Saelin"}
    for banned in ("kh", "dh", "th"):
        assert banned not in culture.language.categories["L"].split()


@pytest.mark.parametrize(
    "source, other", [("elsiri", "taelrik"), ("taelrik", "elsiri")]
)
def test_ai_fixtures_distinct(source, other):
    source_language = _load(source).culture.language
    other_language = _load(other).culture.language
    rng = random.Random(1234)
    for generator in source_language.generators:
        names = roll(source_language, generator.id, count=SAMPLE, rng=rng)
        assert len(names) >= MIN_ROLLED, (generator.id, names)
        if generator.use != "people":
            continue
        cross = [name for name in names if fits(other_language, name)]
        assert len(cross) <= MAX_CROSS_FITS, (generator.id, cross)
