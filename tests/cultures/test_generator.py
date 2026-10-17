import random
import re

import pytest

from talemate.cultures.models import GeneratorDef, Language
from talemate.cultures.generator import GeneratorError, fits, roll


@pytest.fixture
def language() -> Language:
    return Language(
        name="Test",
        level="naming",
        categories={"C": "k t r*3", "V": "a e"},
        generators=[
            GeneratorDef(
                id="g1",
                name="Generator",
                use="people",
                patterns=["CV(C)"],
                reject=["rr"],
            )
        ],
    )


def test_roll_is_deterministic_with_seed(language: Language):
    first = roll(language, "g1", rng=random.Random(1))
    second = roll(language, "g1", rng=random.Random(1))
    assert first == second


def test_roll_respects_pattern_shape(language: Language):
    results = roll(language, "g1", rng=random.Random(2))
    assert results
    for name in results:
        assert re.match(r"^[KTR][ae][ktr]?$", name)
        assert "rr" not in name.lower()


def test_roll_excludes_names(language: Language):
    results = roll(language, "g1", exclude={"ka", "Ta"}, rng=random.Random(3))
    assert "Ka" not in results
    assert "Ta" not in results


def test_roll_terminates_when_space_is_small():
    language = Language(
        name="Small",
        level="naming",
        categories={"C": "k t"},
        generators=[
            GeneratorDef(
                id="g1",
                name="Generator",
                use="people",
                patterns=["Ca"],
            )
        ],
    )
    results = roll(language, "g1", count=20, rng=random.Random(4))
    assert set(results) == {"Ka", "Ta"}


def test_optional_and_choice_tokens():
    language = Language(
        name="Choice",
        level="naming",
        generators=[
            GeneratorDef(
                id="g1",
                name="Generator",
                use="people",
                patterns=["[ka|to](n)"],
            )
        ],
    )
    results = roll(language, "g1", count=30, rng=random.Random(5))
    assert results
    assert set(results) <= {"Ka", "Kan", "To", "Ton"}


def test_fits_accepts_generated_and_rejects_foreign(language: Language):
    results = roll(language, "g1", rng=random.Random(6))
    assert results
    for name in results:
        assert fits(language, name)
    assert fits(language, "Xylophone") is False
    assert fits(language, "Karr") is False


def test_fits_true_without_generators():
    language = Language(name="Bare", level="description")
    assert fits(language, "Anything At All") is True


def test_unknown_generator_raises(language: Language):
    with pytest.raises(GeneratorError):
        roll(language, "nope")
