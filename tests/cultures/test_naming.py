import json
import random
from pathlib import Path

from talemate.character import Character
from talemate.cultures.generator import roll
from talemate.cultures.models import CharacterCulture, Culture, GeneratorDef, Language
from talemate.cultures.naming import (
    CultureGuess,
    choose_generator,
    guess_culture,
    guess_culture_for_name,
    infer_gender,
    match_candidate,
    roll_candidates,
)
from talemate.cultures.scene_context import resolve_scene_cultures

from ._fixtures import build_cultures, build_places

TAELRIK_FIXTURE_PATH = Path(__file__).parent / "data" / "taelrik.culture.json"


def load_taelrik_culture() -> Culture:
    data = json.loads(TAELRIK_FIXTURE_PATH.read_text())
    return Culture.model_validate(data["culture"])


def taelrik_with_female() -> Culture:
    """Plan 1's Taelrik, plus an in-test copy of its language with a
    `given_female` generator added."""

    culture = load_taelrik_culture()
    female_generator = GeneratorDef(
        id="given_female",
        name="Given names (female)",
        use="people",
        patterns=["CVC[ira|lenn|eth]", "CV(C)C[ira|lenn]"],
        reject=["^ng"],
        capitalize=True,
        min_length=3,
        max_length=12,
    )
    language = culture.language.model_copy(
        update={"generators": culture.language.generators + [female_generator]}
    )
    return culture.model_copy(update={"language": language})


def cultures_with(taelrik: Culture) -> dict[str, Culture]:
    cultures = build_cultures()
    cultures["taelrik"] = taelrik
    return cultures


def scene_at(place_name: str, cultures: dict[str, Culture]):
    places = build_places()
    return resolve_scene_cultures(
        cultures, places, location=None, snapshot_places=[place_name], characters=[]
    )


def test_guess_named_in_description():
    cultures = cultures_with(load_taelrik_culture())
    scene = scene_at("Veldhaer", cultures)

    guess = guess_culture(cultures, scene, "an Elsiri net-mender", random.Random(1))

    assert guess.culture_id == "elsiri"
    assert guess.unsure is False
    assert guess.reason == "named in the description"


def test_guess_weighted_by_mix():
    cultures = cultures_with(load_taelrik_culture())
    scene = scene_at("Birch Coast", cultures)
    rng = random.Random(7)

    counts = {"elsiri": 0, "taelrik": 0}
    for _ in range(200):
        guess = guess_culture(cultures, scene, "a new arrival", rng)
        counts[guess.culture_id] += 1
        if guess.culture_id == "elsiri":
            assert guess.unsure is False
        else:
            assert guess.unsure is True

    assert 160 <= counts["elsiri"] <= 195


def test_guess_no_place_uses_characters_then_none():
    cultures = cultures_with(load_taelrik_culture())
    places = build_places()
    character = Character(name="Mira", culture=CharacterCulture(culture_id="elsiri"))

    scene = resolve_scene_cultures(
        cultures,
        places,
        location="nowhere mapped",
        snapshot_places=[],
        characters=[character],
    )
    guess = guess_culture(cultures, scene, "a visitor", random.Random(2))
    assert guess.culture_id == "elsiri"
    assert guess.unsure is True
    assert guess.reason == "from the people around them"

    empty_scene = resolve_scene_cultures(
        cultures,
        places,
        location="nowhere mapped",
        snapshot_places=[],
        characters=[],
    )
    guess_none = guess_culture(cultures, empty_scene, "a visitor", random.Random(2))
    assert guess_none == CultureGuess(None, True, "no culture here")


def test_guess_for_name_fits_one():
    cultures = cultures_with(load_taelrik_culture())
    scene = scene_at("Veldhaer", cultures)
    taelrik_language = cultures["taelrik"].language

    rolled = roll(taelrik_language, "given_male", count=1, rng=random.Random(3))[0]
    guess = guess_culture_for_name(cultures, scene, rolled)
    assert guess.culture_id == "taelrik"
    assert guess.unsure is False

    guess_unknown = guess_culture_for_name(cultures, scene, "Xylophone")
    assert guess_unknown.culture_id == "taelrik"
    assert guess_unknown.unsure is True


def test_infer_gender():
    assert infer_gender("She was his mother and a kind woman.") == "female"
    assert infer_gender("He was her father, a good man and a king.") == "male"
    assert infer_gender("A traveler arrived at dusk.") is None
    assert infer_gender("He loved her.") is None


def test_choose_generator_by_gender():
    language = taelrik_with_female().language
    rng = random.Random(4)

    female_gen = choose_generator(language, "female", rng)
    assert female_gen is not None
    assert female_gen.id == "given_female"

    male_gen = choose_generator(language, "male", rng)
    assert male_gen is not None
    assert male_gen.id == "given_male"

    for _ in range(20):
        neutral_gen = choose_generator(language, None, rng)
        assert neutral_gen is not None
        assert neutral_gen.id != "family"

    original_language = load_taelrik_culture().language
    assert choose_generator(original_language, "female", rng) is None


def test_invalid_generator_returns_none():
    bad_generator = GeneratorDef(
        id="bad", name="Bad", use="people", patterns=["CV"], reject=["["]
    )
    language = Language(
        name="Broken",
        level="naming",
        categories={"C": "k t", "V": "a e"},
        generators=[bad_generator],
    )

    result = roll_candidates(language, bad_generator, 10, set(), random.Random(5))
    assert result == []


def test_roll_candidates_excludes():
    generator = GeneratorDef(id="g1", name="Generator", use="people", patterns=["CV"])
    language = Language(
        name="Test",
        level="naming",
        categories={"C": "k t", "V": "a e"},
        generators=[generator],
    )
    excluded = {"ka", "KA", "Ta", "te"}

    results = roll_candidates(language, generator, 10, excluded, random.Random(6))

    assert results
    for name in results:
        assert name.lower() not in {value.lower() for value in excluded}


def test_match_candidate_variants():
    candidates = ["Kethrun", "Tovrin"]

    assert match_candidate("Tovrin", candidates) == "Tovrin"
    assert match_candidate('"tovrin."', candidates) == "Tovrin"
    assert match_candidate("Tovrin — fits a ferryman", candidates) == "Tovrin"
    assert match_candidate("I pick Kethrun because…", candidates) == "Kethrun"
    assert match_candidate("", candidates) is None
    assert match_candidate("Marigold", candidates) is None


def test_guess_from_characters_counts_each_character():
    cultures = cultures_with(load_taelrik_culture())
    characters = [
        Character(name="Mira", culture=CharacterCulture(culture_id="elsiri")),
        Character(name="Hadrik", culture=CharacterCulture(culture_id="taelrik")),
        Character(name="Tovrin", culture=CharacterCulture(culture_id="taelrik")),
    ]
    scene = resolve_scene_cultures(
        cultures,
        build_places(),
        location="nowhere mapped",
        snapshot_places=[],
        characters=characters,
    )

    # Elsiri comes first, but two of the three people are Taelrik
    assert [c.id for c in scene.cultures] == ["elsiri", "taelrik"]
    guess = guess_culture(cultures, scene, "a visitor", random.Random(2))
    assert guess.culture_id == "taelrik"
    assert guess.reason == "from the people around them"
