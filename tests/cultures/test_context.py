import json
import random
from pathlib import Path

from talemate.character import Character
from talemate.cultures.context import (
    SPARE_NAMES_PREFIX,
    build_culture_section,
    language_traits,
)
from talemate.cultures.generator import fits
from talemate.cultures.models import (
    CharacterCulture,
    Culture,
    GeneratorDef,
    GlossaryEntry,
    GlossaryOrigin,
    Language,
)
from talemate.cultures.scene_context import resolve_scene_cultures
from talemate.util import count_tokens

from ._fixtures import build_cultures, build_places

TAELRIK_FIXTURE_PATH = Path(__file__).parent / "data" / "taelrik.culture.json"


def load_taelrik_culture() -> Culture:
    data = json.loads(TAELRIK_FIXTURE_PATH.read_text())
    return Culture.model_validate(data["culture"])


def build_elsiri_culture() -> Culture:
    return Culture(
        id="elsiri",
        name="Elsiri",
        description="Coast-folk of the Birch shore. Weavers and net-menders, easy with strangers.",
        language=Language(
            name="Elsiri",
            level="full",
            writable=True,
            sound="Elsiri speech: soft sibilants and long vowels, almost sung.",
            categories={"C": "k t m n l r", "V": "a e i o u"},
            generators=[
                GeneratorDef(
                    id="given",
                    name="Given names",
                    use="people",
                    patterns=["CVCV"],
                    capitalize=True,
                    min_length=3,
                    max_length=10,
                ),
            ],
        ),
        customs=["Guests are offered salt before bread."],
        food="Grilled fish, seaweed bread.",
    )


def build_ghun_culture() -> Culture:
    return Culture(
        id="ghun",
        name="Hollow Choir",
        description="The hollow choir sing rather than speak.",
        language=Language(
            name="Ghûn",
            level="description",
            writable=False,
            sound="Ghûn is a sung language of falling tones, never spoken plainly.",
        ),
    )


def build_test_cultures() -> dict[str, Culture]:
    cultures = build_cultures()
    cultures["taelrik"] = load_taelrik_culture()
    cultures["elsiri"] = build_elsiri_culture()
    cultures["ghun"] = build_ghun_culture()
    return cultures


def scene_at(
    place_name: str, cultures: dict[str, Culture], characters: list | None = None
):
    places = build_places()
    return resolve_scene_cultures(
        cultures,
        places,
        location=None,
        snapshot_places=[place_name],
        characters=characters or [],
    )


def ghun_glossary_entry() -> GlossaryEntry:
    return GlossaryEntry(
        id="ghun-khaz",
        text="the three falling hums",
        language="ghun",
        kind="place",
        true_name="three falling hums",
        renderings={"taelrik": "Khaz-Rull"},
        origin=GlossaryOrigin(by="import"),
    )


def test_section_contains_place_mix_and_spares():
    cultures = build_test_cultures()
    scene = scene_at("Veldhaer", cultures)

    section = build_culture_section(
        scene=scene,
        cultures=cultures,
        glossary=[],
        characters=[],
        recent_text="",
        budget=400,
        rng=random.Random(1),
    )

    assert "The scene is in Veldhaer." in section.text
    assert SPARE_NAMES_PREFIX in section.text

    for spare in section.spares:
        assert fits(cultures["taelrik"].language, spare.text)
        assert spare.text in section.text


def test_traits_insert_exact_curses():
    cultures = build_test_cultures()
    scene = scene_at("Veldhaer", cultures)
    hadrik = Character(name="Hadrik", description="He curses in Taelrik when angry.")

    section = build_culture_section(
        scene=scene,
        cultures=cultures,
        glossary=[],
        characters=[hadrik],
        recent_text="",
        budget=400,
        rng=random.Random(2),
    )

    assert "Rhok tal'dun!" in section.text
    assert "Dhaer tal'skev." in section.text
    assert "Vel'dhaer ossa tae." not in section.text
    assert "Dhun sa'ver, kaeth sa'ver." not in section.text


def test_unwritable_instruction_and_rendering():
    cultures = build_test_cultures()
    ghost = Character(name="Ghost", culture=CharacterCulture(culture_id="ghun"))
    scene = scene_at("Veldhaer", cultures, characters=[ghost])

    section = build_culture_section(
        scene=scene,
        cultures=cultures,
        glossary=[ghun_glossary_entry()],
        characters=[],
        recent_text="",
        budget=400,
        rng=random.Random(3),
    )

    assert "never spell it out" in section.text
    assert "Khaz-Rull" in section.text


def test_food_only_when_relevant():
    cultures = build_test_cultures()
    scene = scene_at("Veldhaer", cultures)
    food_text = cultures["taelrik"].food

    absent = build_culture_section(
        scene=scene,
        cultures=cultures,
        glossary=[],
        characters=[],
        recent_text="They crossed the bridge.",
        budget=400,
        rng=random.Random(4),
    )
    assert food_text not in absent.text

    present = build_culture_section(
        scene=scene,
        cultures=cultures,
        glossary=[],
        characters=[],
        recent_text="They sat down to supper at the inn.",
        budget=400,
        rng=random.Random(4),
    )
    assert food_text in present.text


def test_names_in_use_listed():
    cultures = build_test_cultures()
    scene = scene_at("Veldhaer", cultures)
    kethrun = Character(name="Kethrun")
    entry = GlossaryEntry(
        id="g1",
        text="Kethrun",
        language="taelrik",
        kind="person",
        character_name="Kethrun",
        origin=GlossaryOrigin(by="owner"),
    )

    section = build_culture_section(
        scene=scene,
        cultures=cultures,
        glossary=[entry],
        characters=[kethrun],
        recent_text="",
        budget=400,
        rng=random.Random(5),
    )

    assert "Kethrun (Taelrik, person)" in section.text


def test_section_respects_budget_with_large_world():
    cultures = build_test_cultures()
    many_customs = cultures["taelrik"].customs + [
        f"Custom number {i} of the river-folk." for i in range(300)
    ]
    cultures["taelrik"] = cultures["taelrik"].model_copy(
        update={"customs": many_customs}
    )
    scene = scene_at("Veldhaer", cultures)

    glossary = [
        GlossaryEntry(
            id=f"g{i}",
            text=f"word{i}",
            language="taelrik",
            kind="word",
            origin=GlossaryOrigin(by="import"),
        )
        for i in range(1000)
    ]

    characters = [
        Character(name="Hadrik", description="He curses in Taelrik when angry."),
        Character(name="Mira", description="She swears in Taelrik constantly."),
        Character(name="Old Tolvar", description="He speaks Taelrik fluently."),
    ]

    section = build_culture_section(
        scene=scene,
        cultures=cultures,
        glossary=glossary,
        characters=characters,
        recent_text="They sat down to supper at the inn.",
        budget=120,
        rng=random.Random(6),
    )

    assert count_tokens(section.text) <= 120
    assert section.text.startswith("The scene is in")


def test_empty_without_cultures():
    cultures = build_test_cultures()
    places = build_places()
    scene = resolve_scene_cultures(
        cultures,
        places,
        location="nowhere mapped",
        snapshot_places=[],
        characters=[],
    )

    section = build_culture_section(
        scene=scene,
        cultures=cultures,
        glossary=[],
        characters=[],
        recent_text="",
        budget=400,
        rng=random.Random(7),
    )

    assert section.text == ""
    assert section.tokens == 0
    assert section.spares == []


def test_language_traits_patterns():
    cultures = build_test_cultures()

    swears = Character(name="A", description="He swears in Taelrik constantly.")
    traits = language_traits(swears, cultures)
    assert traits
    assert traits[0].stem == "curse"

    speaks = Character(name="B", description="She speaks Elsiri fluently.")
    traits = language_traits(speaks, cultures)
    assert traits
    assert traits[0].stem is None

    travelled = Character(
        name="C", description="He travelled in Taelrik lands for years."
    )
    traits = language_traits(travelled, cultures)
    assert traits == []


def test_names_in_use_includes_intermediate_ancestor():
    # Quillister House (building) -> Veldhaer (town, no cultures of its
    # own) -> The Taelrik Reach (country, where the mix actually comes
    # from). Veldhaer is an ancestor with no mix of its own, sitting
    # between the matched place and the mix's source.
    cultures = build_test_cultures()
    places = build_places()
    scene = resolve_scene_cultures(
        cultures,
        places,
        location="Quillister House",
        snapshot_places=[],
        characters=[],
    )
    assert scene.place.id == "quillister"
    assert scene.mix_source.id == "reach"
    assert "veldhaer" in scene.ancestor_ids

    entry = GlossaryEntry(
        id="g-ancestor",
        text="Veldhaer",
        language="taelrik",
        kind="place",
        place_id="veldhaer",
        origin=GlossaryOrigin(by="owner"),
    )

    section = build_culture_section(
        scene=scene,
        cultures=cultures,
        glossary=[entry],
        characters=[],
        recent_text="",
        budget=400,
        rng=random.Random(8),
    )

    assert "Veldhaer (place)" in section.text


def _section(scene, cultures, seed, **kwargs):
    defaults = dict(
        scene=scene,
        cultures=cultures,
        glossary=[],
        characters=[],
        recent_text="",
        budget=400,
        rng=random.Random(seed),
    )
    defaults.update(kwargs)
    return build_culture_section(**defaults)


def test_spares_exclude_character_and_place_names():
    cultures = build_test_cultures()
    scene = scene_at("Veldhaer", cultures)
    first = _section(scene, cultures, 5)
    rolled = [spare.text for spare in first.spares]
    assert len(rolled) >= 2

    # the same seed would roll these again
    again = _section(scene, cultures, 5, exclude_names=[rolled[0].upper(), rolled[1]])
    texts = {spare.text for spare in again.spares}
    assert rolled[0] not in texts
    assert rolled[1] not in texts


def test_culture_note_grammar_and_prefixed_lines():
    cultures = build_test_cultures()
    scene = scene_at("Dhunmouth", cultures)
    section = _section(scene, cultures, 6, recent_text="They sat down to supper.")

    assert (
        "Elsiri: Coast-folk of the Birch shore. Their language is Elsiri: Elsiri "
        "speech: soft sibilants and long vowels, almost sung." in section.text
    )
    assert "Their language, " not in section.text
    assert "- Elsiri: Guests are offered salt before bread." in section.text
    assert "- Elsiri: Grilled fish, seaweed bread." in section.text
    assert f"- Taelrik: {cultures['taelrik'].food}" in section.text

    cultures["elsiri"].language.sound = ""
    section = _section(scene, cultures, 6)
    assert "Their language is Elsiri." in section.text


def test_trait_line_uses_a_fixed_verb():
    cultures = build_test_cultures()
    scene = scene_at("Veldhaer", cultures)
    characters = [
        Character(name="Hadrik", description="Swearing in Taelrik is his habit."),
        Character(name="Mira", description="She greets everyone in Elsiri."),
    ]
    section = _section(scene, cultures, 7, characters=characters)
    assert "Hadrik curses in Taelrik." in section.text
    assert "Mira greets in Elsiri." in section.text

    pray = Character(name="Orla", description="She prays in Taelrik at dusk.")
    section = _section(scene, cultures, 7, characters=[pray])
    assert "Orla speaks in Taelrik." in section.text
