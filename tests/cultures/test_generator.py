import random
import re

import pytest

from talemate.cultures.models import GeneratorDef, Language
from talemate.cultures.generator import GeneratorError, fits, roll, validate_language


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


def _language_with(patterns: list[str], reject: list[str] | None = None) -> Language:
    return Language(
        name="Test",
        level="naming",
        categories={"C": "k t", "V": "a e"},
        generators=[
            GeneratorDef(
                id="g1",
                name="Generator",
                use="people",
                patterns=patterns,
                reject=reject or [],
            )
        ],
    )


def test_bad_reject_regex_raises_generator_error():
    language = _language_with(["CV"], reject=["["])
    with pytest.raises(GeneratorError, match="reject"):
        roll(language, "g1")
    with pytest.raises(GeneratorError):
        validate_language(language)


def test_deeply_nested_pattern_raises_generator_error():
    language = _language_with(["(" * 5000 + "CV" + ")" * 5000])
    with pytest.raises(GeneratorError, match="nest"):
        roll(language, "g1")


def test_deeply_nested_reject_raises_generator_error():
    language = _language_with(["CV"], reject=["(" * 5000 + "a" + ")" * 5000])
    with pytest.raises(GeneratorError):
        roll(language, "g1")


def test_fits_accepts_multi_word_generator_output():
    language = Language(
        name="Two words",
        level="naming",
        categories={"C": "k t r", "V": "a e"},
        generators=[
            GeneratorDef(
                id="full",
                name="Full names",
                use="people",
                patterns=["CV CVC", "CV(C) of CVC", "CV (CV) CVC"],
            )
        ],
    )
    results = roll(language, "full", count=30, rng=random.Random(7))
    assert results
    for name in results:
        assert fits(language, name), name
    # Whitespace is normalised and case doesn't matter.
    assert fits(language, "  ka   TEK ")
    # A single word doesn't match a two-word pattern.
    assert fits(language, "Ka") is False


def test_fits_reject_rules_apply_per_generator():
    language = Language(
        name="Two generators",
        level="naming",
        categories={"C": "k t r", "V": "a e"},
        generators=[
            GeneratorDef(id="a", name="A", use="people", patterns=["CVC"]),
            GeneratorDef(
                id="b", name="B", use="places", patterns=["CVCV"], reject=["k"]
            ),
        ],
    )
    # Valid for A; B's reject rule must not veto it.
    assert fits(language, "Kat") is True
    # Only B's pattern matches, and B's own reject rule vetoes it.
    assert fits(language, "Kata") is False
    assert fits(language, "Tara") is True


def test_duplicate_generator_ids_rejected():
    gen = GeneratorDef(id="g1", name="A", use="people", patterns=["CV"])
    language = Language(
        name="Dup",
        level="naming",
        categories={"C": "k", "V": "a"},
        generators=[gen, gen.model_copy(update={"name": "B"})],
    )
    with pytest.raises(GeneratorError, match="duplicate"):
        validate_language(language)
