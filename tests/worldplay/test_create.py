"""Create a world thing from a prompt: preview (no writes), then accept."""

import itertools
import json
import uuid
from pathlib import Path
from typing import NamedTuple

import pytest

from talemate.world.calendar import Calendar, Era
from talemate.world.dates import Precision, WorldDate
from talemate.world import heritage, store
from talemate.world.refs import ref
from talemate.world.store import Source, World
from talemate.worldplay import prose_gen
from talemate.worldplay.characters import character_from_world
from talemate.worldplay.links import NewName
from talemate.worldplay.create import (
    CreatePreview,
    PreviewFact,
    accept_preview,
    cached_summary,
    homes_block,
    parse_create_reply,
    preview_inherited,
    preview_thing,
)

from conftest import MockClient, MockClientContext, client_responses


def _queue(*responses: str) -> None:
    for response in responses:
        client_responses.get().append(response)


@pytest.fixture
def at_313(world):
    """The world's current date is 313: a scene starts there."""

    world.scenes().create("Opening", WorldDate.of(313))
    return world


DUELIST_REPLY = json.dumps(
    {
        "name": "Corvin Ash",
        "age": 41,
        "facts": [
            {
                "category": "background",
                "text": "Exiled from Ashenmere for killing a younger opponent.",
                "since": 305,
            },
            # the drifted shape: the category as the key
            {"appearance": "A long scar across his sword hand."},
            {"category": "personality", "text": "Quiet, and quick to apologise."},
            # an off-calendar year and a free-text date both become "always"
            {"category": "ability", "text": "A master fencer.", "since": 1734},
            {"category": "speech", "text": "Speaks softly.", "since": "childhood"},
        ],
    }
)


async def test_preview_parses_facts(at_313):
    client = MockClient("test")
    async with MockClientContext():
        _queue(DUELIST_REPLY, "Corvin Ash is lean and scarred.", "Corvin Ash is quiet.")
        preview = await preview_thing(
            at_313, "character", "a disgraced duelist", {}, client
        )

    assert preview.kind == "character"
    assert preview.prompt == "a disgraced duelist"
    assert preview.name == "Corvin Ash"
    assert [(f.category, f.text) for f in preview.facts] == [
        ("background", "Exiled from Ashenmere for killing a younger opponent."),
        ("appearance", "A long scar across his sword hand."),
        ("personality", "Quiet, and quick to apologise."),
        ("ability", "A master fencer."),
        ("speech", "Speaks softly."),
    ]
    assert [f.since for f in preview.facts] == [
        WorldDate.of(305),
        None,
        None,
        None,
        None,
    ]
    # born is derived from the age against the world's current year
    assert preview.fields["born"] == WorldDate.of(313 - 41)
    assert preview.prose == {
        "description": "Corvin Ash is lean and scarred.",
        "personality": "Corvin Ash is quiet.",
    }

    # one creation call, then one prose call per section
    assert len(client.prompt_history) == 3
    create_prompt = str(client.prompt_history[0]["prompt"])
    assert "a disgraced duelist" in create_prompt
    assert "appearance, personality, background" in create_prompt
    assert "year 313" in create_prompt
    # no Talemate jargon the model can't know, and an example `since` that
    # can't be copied as a real year
    assert "`@`" not in create_prompt
    assert '"since": "YEAR"' in create_prompt
    assert "308" not in create_prompt
    # an inherent trait (species, a born appearance, lifelong temperament)
    # gets an open start rather than being dated to the present year
    assert "inherent trait" in create_prompt


async def test_preview_prose_sections_get_identity_background(at_313):
    """Review-round fix: `preview_thing` called `render_section` with no
    `background`, so a section generated from one category of facts alone
    could drift off who it's about (the owl-to-human drift `daf21459`
    fixed for `regenerate_prose`/`generate_section`, which already passes
    the thing's other facts and core fields as background). A preview has
    facts and fields, not a `ThingState`, so the same background must come
    from a helper both callers can use.

    Personality's background leaves out the appearance fact (acceptance
    probe: docs/superpowers/probes/2026-10-21-personality-and-actions.md)
    but keeps identity (name, born) and his other facts (here, the
    background fact), so a fresh preview agrees with a later
    regeneration."""

    client = MockClient("test")
    async with MockClientContext():
        _queue(DUELIST_REPLY, "Corvin Ash is lean and scarred.", "Corvin Ash is quiet.")
        await preview_thing(at_313, "character", "a disgraced duelist", {}, client)

    # [0] is the create call, [1] description, [2] personality
    personality_prompt = str(client.prompt_history[2]["prompt"])
    # the personality section's own facts don't mention his name/born --
    # without identity background, nothing here would
    assert "Named Corvin Ash." in personality_prompt
    assert "Born in" in personality_prompt
    assert "for consistency only" in personality_prompt
    # his background fact survives as context
    assert "Exiled from Ashenmere for killing a younger opponent." in personality_prompt
    # his appearance fact is left out of personality's background entirely
    assert "A long scar across his sword hand." not in personality_prompt


async def test_preview_does_not_write(at_313):
    head = at_313.head_rev()
    client = MockClient("test")
    async with MockClientContext():
        _queue(DUELIST_REPLY, "Lean.", "Quiet.")
        await preview_thing(at_313, "character", "a disgraced duelist", {}, client)

    assert at_313.head_rev() == head
    assert at_313.view().things() == []


async def test_preview_keeps_given_fields(at_313):
    client = MockClient("test")
    born = WorldDate.of(280).model_dump()
    reply = json.dumps(
        {
            "name": "Someone Else",
            "age": 10,
            "facts": [{"category": "background", "text": "A ferryman."}],
        }
    )
    async with MockClientContext():
        _queue(reply, "Old Tam ferries.")
        preview = await preview_thing(
            at_313,
            "character",
            "an old ferryman",
            {"name": "Old Tam", "born": born},
            client,
        )

    # the owner's own picks win over the model's
    assert preview.name == "Old Tam"
    assert preview.fields["born"] == born
    create_prompt = str(client.prompt_history[0]["prompt"])
    assert "Old Tam" in create_prompt
    assert "age 33" in create_prompt


async def test_preview_place_has_one_section(at_313):
    client = MockClient("test")
    reply = json.dumps(
        {
            "name": "Lowmere",
            "facts": [
                {"category": "description", "text": "Half its streets are flooded."},
                {"category": "history", "text": "The dam broke.", "since": 301},
            ],
        }
    )
    async with MockClientContext():
        _queue(reply, "Lowmere is half under water.")
        preview = await preview_thing(
            at_313, "place", "a half-flooded town", {}, client
        )

    assert preview.prose == {"description": "Lowmere is half under water."}
    assert preview.facts[1].since == WorldDate.of(301)


async def test_preview_rejects_kind_outside_the_slice(at_313):
    with pytest.raises(ValueError):
        await preview_thing(at_313, "culture", "a river folk", {}, MockClient("test"))


def test_parse_recovers_complete_objects_from_truncated_reply():
    reply = (
        '{"name": "Tam", "age": 60, "facts": ['
        '{"category": "background", "text": "A ferryman."}, '
        '{"appearance": "Weathered hands."}, '
        '{"category": "personality", "text": "Grumbles at'
    )
    name, age, facts = parse_create_reply(reply, "character", Calendar(), 313)
    assert name == "Tam"
    assert age == 60
    assert [(f.category, f.text) for f in facts] == [
        ("background", "A ferryman."),
        ("appearance", "Weathered hands."),
    ]


def test_parse_accepts_a_bare_list_and_caps_the_count():
    items = [{"category": "general", "text": f"Fact {i}."} for i in range(20)]
    name, age, facts = parse_create_reply(json.dumps(items), "lore", Calendar(), 313)
    assert name is None
    assert age is None
    assert len(facts) == 12
    assert facts[0].text == "Fact 0."


def test_parse_ignores_the_placeholder_name():
    reply = json.dumps({"name": "...", "facts": [{"general": "A treaty."}]})
    name, _, facts = parse_create_reply(reply, "lore", Calendar(), 313)
    assert name is None
    assert facts[0].text == "A treaty."


def test_parse_rejects_the_example_since_placeholder():
    reply = json.dumps(
        {
            "name": "Ivo",
            "facts": [
                {"category": "general", "text": "Copied.", "since": "YEAR"},
            ],
        }
    )
    _name, _age, facts = parse_create_reply(reply, "character", Calendar(), 313)
    assert facts[0].since is None


def test_parse_accepts_a_raw_line_break_in_a_truncated_names_name():
    """Regression (fix round 1): the same bug also hit the name recovered
    from a truncated reply's unterminated head -- `_NAME_RE`'s match is
    decoded with `json.loads` there too, and a raw newline inside it used
    to raise uncaught."""

    reply = (
        '{"name": "Tam\nthe Ferryman", "age": 60, "facts": ['
        '{"category": "background", "text": "A ferryman."}, '
        '{"category": "personality", "text": "Grumbles at'
    )
    name, age, facts = parse_create_reply(reply, "character", Calendar(), 313)
    assert name == "Tam\nthe Ferryman"
    assert age == 60
    assert facts[0].text == "A ferryman."


def test_parse_accepts_a_raw_line_break_in_fact_text():
    """Regression: a model reply with a real newline inside a fact's
    "text" string (instead of an escaped "\\n") is still parsed, the same
    bug the scene-setup reply parser hit (accept-fix-4)."""

    reply = (
        '{"name": "Mira", "facts": [{"category": "background", '
        '"text": "Born in the hills.\nRaised by wolves."}]}'
    )
    name, _, facts = parse_create_reply(reply, "character", Calendar(), 313)
    assert name == "Mira"
    assert facts[0].text == "Born in the hills.\nRaised by wolves."


def test_parse_unknown_category_falls_back():
    reply = json.dumps({"facts": [{"category": "rumour", "text": "Said to be shady."}]})
    _, _, facts = parse_create_reply(reply, "place", Calendar(), 313)
    assert facts[0].category == "general"


def test_parse_since_uses_the_current_era():
    calendar = Calendar(
        eras=[Era(name="Age of Rivers", abbreviation="AR", start_year=300)]
    )
    reply = json.dumps(
        {
            "facts": [
                {"category": "general", "text": "Treaty signed.", "since": 5},
                {"category": "general", "text": "Pillars built.", "since": "10 AR"},
                {"category": "general", "text": "Too late.", "since": 20},
            ]
        }
    )
    # year 313 is 14 AR
    _, _, facts = parse_create_reply(reply, "lore", calendar, 313)
    assert facts[0].since == WorldDate.of(304)
    assert facts[1].since == WorldDate.of(309)
    # 20 AR is after now: treated as an open start
    assert facts[2].since is None


async def test_preview_in_a_world_with_no_scenes_uses_its_present(world):
    world.set_present(WorldDate.of(1000))
    client = MockClient("test")
    async with MockClientContext():
        _queue(DUELIST_REPLY, "Lean.", "Quiet.")
        preview = await preview_thing(world, "character", "a duelist", {}, client)

    assert preview.fields["born"] == WorldDate.of(1000 - 41)
    assert "year 1000" in str(client.prompt_history[0]["prompt"])
    # 305 is a year before now: kept
    assert preview.facts[0].since == WorldDate.of(305)


async def test_set_present_moves_creations_now(at_313):
    # a present later than the latest scene wins
    at_313.set_present(WorldDate.of(400))
    client = MockClient("test")
    async with MockClientContext():
        _queue(DUELIST_REPLY, "Lean.", "Quiet.")
        preview = await preview_thing(at_313, "character", "a duelist", {}, client)
    assert preview.fields["born"] == WorldDate.of(400 - 41)


async def test_derived_born_is_at_least_year_one(world):
    world.set_present(WorldDate.of(20))
    client = MockClient("test")
    async with MockClientContext():
        _queue(DUELIST_REPLY, "Lean.", "Quiet.")
        preview = await preview_thing(world, "character", "a duelist", {}, client)
    assert preview.fields["born"] == WorldDate.of(1)


def test_accept_writes_one_revision(at_313):
    preview = CreatePreview(
        kind="character",
        prompt="a one-eyed warden",
        fields={"born": WorldDate.of(290)},
        name="Maren",
        facts=[
            PreviewFact(category="appearance", text="Tall and grey-eyed."),
            PreviewFact(
                category="appearance",
                text="Lost her left eye.",
                since=WorldDate.of(312),
            ),
            PreviewFact(category="personality", text="A quick laugh."),
        ],
        prose={"description": "Maren is tall.", "personality": "Maren laughs."},
    )
    head = at_313.head_rev()

    thing_id = accept_preview(at_313, preview)

    assert at_313.head_rev() == head + 1
    info = at_313.revisions()[-1]
    assert info.source == Source.manual(note="created from prompt")

    state = at_313.view().thing(thing_id)
    assert state.kind == "character"
    assert state.fields["name"] == "Maren"
    assert state.fields["born"] == WorldDate.of(290)
    assert {f.text for f in state.facts} == {
        "Tall and grey-eyed.",
        "Lost her left eye.",
        "A quick laugh.",
    }
    eye = next(f for f in state.facts if f.text == "Lost her left eye.")
    assert eye.valid_from == WorldDate(
        instant=WorldDate.of(312).instant, precision=Precision.YEAR
    )

    # the preview's prose is cached, fresh, for the current stretch
    cache = at_313.prose()
    for section, text in preview.prose.items():
        cached = cache.get(thing_id, section, None)
        assert cached.text == text
        assert cache.stale(thing_id, section, None) is False
    # before the eye fact, there's nothing cached
    assert cache.get(thing_id, "description", WorldDate.of(311)) is None


def test_accept_rejects_an_invalid_fact_without_writing(at_313):
    preview = CreatePreview(
        kind="place",
        prompt="x",
        name="Nowhere",
        facts=[PreviewFact(category="appearance", text="Not a place category.")],
        prose={},
    )
    head = at_313.head_rev()
    with pytest.raises(ValueError):
        accept_preview(at_313, preview)
    assert at_313.head_rev() == head


async def test_regenerated_prose_wins_after_a_fact_at_a_new_year(at_313):
    """The accepted preview's prose covers the open stretch. A fact dated at
    a new year splits it; the prose regenerated for the new open stretch is
    what "now" reads from then on, with no since line repeating it, and
    nothing is regenerated twice."""

    preview = CreatePreview(
        kind="character",
        prompt="a smith",
        fields={},
        name="Ivo",
        facts=[
            PreviewFact(category="appearance", text="Broad shoulders."),
            PreviewFact(category="personality", text="Calm."),
        ],
        prose={"description": "Ivo is broad.", "personality": "Ivo is calm."},
    )
    thing_id = accept_preview(at_313, preview)
    with at_313.revision(Source.manual(note="a scar")) as rev:
        rev.add_fact(
            thing_id,
            "appearance",
            "A scar from the forge.",
            valid_from=WorldDate.of(312),
        )

    client = MockClient("test")
    async with MockClientContext():
        _queue("Ivo is broad, with a forge scar.", "Ivo is still calm.")
        await prose_gen.ensure_prose(at_313, thing_id, None, client)
        assert len(client.prompt_history) == 2
        # fresh now: a second pass asks for nothing
        await prose_gen.ensure_prose(at_313, thing_id, None, client)
        assert len(client.prompt_history) == 2

    cache = at_313.prose()
    latest = cache.get(thing_id, "description", None)
    assert latest.text == "Ivo is broad, with a forge scar."
    assert cache.stale(thing_id, "description", None) is False
    assert cache.get(thing_id, "personality", None).text == "Ivo is still calm."
    earlier = cache.get(thing_id, "description", WorldDate.of(311))
    assert "scar" not in earlier.text

    character = character_from_world(
        at_313, thing_id, WorldDate.of(313), is_player=False
    )
    assert character.description == "Ivo is broad, with a forge scar."


# --- heritage: species, races, mixes, characters of a heritage ---------------

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "worldplay"


def _reply(name: str) -> str:
    """A real model reply from the heritage create probe
    (docs/superpowers/probes/raw/2026-10-20-heritage-create.json)."""

    return (DATA_DIR / name).read_text()


class ProbeWorld(NamedTuple):
    world: World
    human: str
    lowlander: str
    orc: str
    owl_folk: str
    snowy: str
    facts: dict[str, str]


@pytest.fixture
def probe_world(at_313, monkeypatch):
    """The heritage create probe's world: Human with its Lowlander race,
    Orc, and Owl-folk with its Snowy race (whose white plumage overrides
    Owl-folk's mottled one). `facts` maps the probe's fact ids ("owl-4")
    to the real ones.

    A view orders a thing's facts by `fact_id`, so the ids are made
    sequential here: the prompt then labels the facts in the probe's order,
    and the probe's real replies (F3 = Snowy's yellow eyes) still fit."""

    counter = itertools.count(1)
    monkeypatch.setattr(store.uuid, "uuid4", lambda: uuid.UUID(int=next(counter)))
    facts: dict[str, str] = {}

    def add(rev, thing, key, category, text, overrides=()):
        facts[key] = rev.add_fact(
            thing, category, text, overrides=[facts[o] for o in overrides]
        )

    with at_313.revision(Source.manual(note="probe world")) as rev:
        human = rev.create_thing(
            "species",
            {
                "name": "Human",
                "lifespan": 75,
                "adult_age": 18,
                "measures": [{"name": "height", "min": 5, "max": 6.5, "unit": "ft"}],
            },
        )
        add(rev, human, "human-1", "physical", "Humans have bare skin.")
        add(rev, human, "human-2", "physical", "Humans have rounded ears and no tusks.")
        add(rev, human, "human-3", "physical", "Humans have brown, black or red hair.")
        add(rev, human, "human-4", "instinct", "Humans seek company.")
        lowlander = rev.create_thing(
            "race",
            {
                "name": "Lowlander",
                "species": human,
                "measures": [{"name": "height", "min": 5, "max": 5.7, "unit": "ft"}],
            },
        )
        add(rev, lowlander, "low-1", "physical", "Lowlanders are short and stocky.")
        add(rev, lowlander, "low-2", "physical", "Lowlanders have olive skin.")
        orc = rev.create_thing(
            "species",
            {
                "name": "Orc",
                "lifespan": 60,
                "adult_age": 14,
                "measures": [
                    {"name": "height", "min": 6, "max": 7, "unit": "ft"},
                    {"name": "tusk length", "min": 1.5, "max": 2.5, "unit": "in"},
                ],
            },
        )
        for i, text in enumerate(
            [
                "Orcs have grey-green skin.",
                "Orcs have two lower tusks.",
                "Orcs have coarse black hair.",
                "Orcs have yellow or amber eyes.",
                "Orcs are territorial.",
            ],
            1,
        ):
            add(rev, orc, f"orc-{i}", "instinct" if i == 5 else "physical", text)
        owl_folk = rev.create_thing(
            "species",
            {
                "name": "Owl-folk",
                "lifespan": 70,
                "adult_age": 12,
                "measures": [
                    {"name": "height", "min": 3, "max": 4, "unit": "ft"},
                    {"name": "wingspan", "min": 7, "max": 9, "unit": "ft"},
                ],
            },
        )
        owl_texts = [
            "Owl-folk are fully feathered, with a pair of wings in place of arms.",
            "Owl-folk have a round facial disc, a hooked beak and large "
            "forward-facing eyes.",
            "Owl-folk have taloned feet that serve as hands for fine work.",
            "Owl-folk plumage is mottled brown and grey, for camouflage against bark.",
            "Owl-folk have light, hollow bones and can turn their heads nearly "
            "all the way around.",
        ]
        for i, text in enumerate(owl_texts, 1):
            add(rev, owl_folk, f"owl-{i}", "physical", text)
        add(
            rev,
            owl_folk,
            "owl-6",
            "instinct",
            "Owl-folk are instinctively crepuscular, most alert at dusk and dawn, "
            "and freeze motionless when startled.",
        )
        snowy = rev.create_thing(
            "race",
            {
                "name": "Snowy",
                "species": owl_folk,
                "measures": [{"name": "wingspan", "min": 8.5, "max": 9, "unit": "ft"}],
            },
        )
        add(
            rev,
            snowy,
            "snowy-1",
            "physical",
            "Snowy owl-folk are the largest owl-folk.",
        )
        add(
            rev,
            snowy,
            "snowy-2",
            "physical",
            "Snowy owl-folk have white plumage flecked with grey or black.",
            overrides=["owl-4"],
        )
        add(
            rev, snowy, "snowy-3", "physical", "Snowy owl-folk have bright yellow eyes."
        )
        add(
            rev,
            snowy,
            "snowy-4",
            "instinct",
            "Snowy owl-folk hunt by day as readily as by dusk in the long "
            "northern summers.",
        )

    monkeypatch.undo()
    return ProbeWorld(at_313, human, lowlander, orc, owl_folk, snowy, facts)


async def test_preview_species_numbers(at_313):
    client = MockClient("test")
    async with MockClientContext():
        _queue(_reply("heritage-species-owlfolk-reply.txt"), "Owl-folk is small.")
        preview = await preview_thing(
            at_313,
            "species",
            "Owl-folk: small feathered people with wings instead of arms, who "
            "hunt at dusk in the old forests.",
            {},
            client,
        )

    assert preview.name == "Owl-folk"
    assert preview.fields["lifespan"] == 45
    assert preview.fields["adult_age"] == 8
    assert preview.fields["measures"] == [
        {"name": "height", "min": 2.5, "max": 3.5, "unit": "ft"},
        {"name": "wingspan", "min": 6, "max": 8, "unit": "ft"},
    ]
    assert len(preview.facts) == 12
    assert {f.category for f in preview.facts} == {
        "origin",
        "physical",
        "instinct",
        "variation",
        "general",
    }
    assert all(f.since is None and f.overrides == [] for f in preview.facts)
    assert preview.prose == {"description": "Owl-folk is small."}

    create_prompt = str(client.prompt_history[0]["prompt"])
    assert "You create a new species" in create_prompt
    assert '"lifespan": 0, "adult_age": 0' in create_prompt
    assert "The 0s in the example are placeholders" in create_prompt
    assert 'Leave "since" out: these facts describe the species' in create_prompt


async def test_preview_drops_bad_numbers(at_313):
    reply = json.dumps(
        {
            "name": "Mole-folk",
            # the example's placeholder copied as is is no number
            "lifespan": 0,
            "adult_age": "young",
            "measures": [
                {"name": "height", "min": 2, "max": 3, "unit": "ft"},
                {"name": "claw length", "min": "long", "max": 3, "unit": "in"},
                {"name": "tail length", "min": 0, "max": 0, "unit": "in"},
                {"name": "weight", "min": 90, "max": 40, "unit": "lb"},
            ],
            "facts": [{"category": "physical", "text": "Velvet fur."}],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "Mole-folk are furry.")
        preview = await preview_thing(
            at_313, "species", "burrowing mole people", {}, client
        )

    assert "lifespan" not in preview.fields
    assert "adult_age" not in preview.fields
    assert preview.fields["measures"] == [
        {"name": "height", "min": 2, "max": 3, "unit": "ft"}
    ]


async def test_preview_character_maps_override_labels(probe_world):
    client = MockClient("test")
    async with MockClientContext():
        _queue(
            _reply("heritage-character-snowy-reply.txt"),
            "Thistledown is white.",
            "Thistledown is chatty.",
        )
        preview = await preview_thing(
            probe_world.world,
            "character",
            "A Snowy owl-folk courier with blue eyes, twenty-two, who carries "
            "letters between mountain villages and talks too much.",
            {"heritage": probe_world.snowy},
            client,
        )

    facts = probe_world.facts
    assert preview.name == "Thistledown"
    assert preview.fields["heritage"] == probe_world.snowy
    eyes = next(f for f in preview.facts if "blue" in f.text)
    # F3 is Snowy's "bright yellow eyes", mapped back to its real fact id
    assert eyes.overrides == [facts["snowy-3"]]
    assert all(f.overrides == [] for f in preview.facts if f is not eyes)

    create_prompt = str(client.prompt_history[0]["prompt"])
    assert "The character is Snowy (a race of Owl-folk)" in create_prompt
    assert (
        "Heritage numbers: lifespan 70 years, adult at 12, height 3-4 ft, "
        "wingspan 8.5-9 ft." in create_prompt
    )
    assert (
        "- F3 (Snowy, physical): Snowy owl-folk have bright yellow eyes."
        in create_prompt
    )
    assert "- F9 (Owl-folk, instinct): Owl-folk are instinctively" in create_prompt
    # Snowy's white plumage overrides Owl-folk's mottled one: not inherited
    assert "mottled" not in create_prompt
    assert '"overrides": []' in create_prompt

    # the description section is the character's own appearance facts plus
    # the inherited physical ones, less the yellow eyes the preview overrides
    description_prompt = str(client.prompt_history[1]["prompt"])
    assert "taloned feet that serve as hands" in description_prompt
    assert "bright yellow eyes" not in description_prompt
    assert "Heritage: Snowy, Owl-folk." in description_prompt


async def test_preview_personality_excludes_inherited_physical(probe_world):
    """Review-round fix: `_preview_prose`'s `exclude_by_kind` branch (the
    personality background leaving out an inherited `physical`/`variation`
    fact) had no test exercising it with any inherited fact actually
    present. The preview inherits Snowy's and Owl-folk's own facts, none of
    them overridden here, so both an un-overridden inherited physical fact
    ("the largest owl-folk") and the overridden one ("bright yellow eyes")
    must be absent from the personality prompt, while the inherited
    instinct facts and the heritage line -- not excluded -- still get
    through (acceptance probe:
    docs/superpowers/probes/2026-10-21-personality-and-actions.md)."""

    client = MockClient("test")
    async with MockClientContext():
        _queue(
            _reply("heritage-character-snowy-reply.txt"),
            "Thistledown is white.",
            "Thistledown is chatty.",
        )
        await preview_thing(
            probe_world.world,
            "character",
            "A Snowy owl-folk courier with blue eyes, twenty-two, who carries "
            "letters between mountain villages and talks too much.",
            {"heritage": probe_world.snowy},
            client,
        )

    # [0] is the create call, [1] description, [2] personality
    personality_prompt = str(client.prompt_history[2]["prompt"])
    # an inherited physical fact that isn't overridden by this preview
    assert "the largest owl-folk" not in personality_prompt
    # the one the preview does override -- absent either way, but still
    # worth checking since it was the review's own example
    assert "bright yellow eyes" not in personality_prompt
    # instinct facts aren't excluded -- they're personality's own inherited
    # category -- and the heritage line keeps identity in view
    assert "Owl-folk are instinctively crepuscular" in personality_prompt
    assert "hunt by day as readily as by dusk" in personality_prompt
    assert "Heritage: Snowy, Owl-folk." in personality_prompt


async def test_preview_lists_what_it_inherits(probe_world):
    """The preview carries the inherited facts the model was shown, with
    their real fact ids, so the owner can mark one as overridden before
    accepting (the create box's safety net for missed overrides)."""

    client = MockClient("test")
    async with MockClientContext():
        _queue(
            _reply("heritage-character-snowy-reply.txt"),
            "Thistledown is white.",
            "Thistledown is chatty.",
        )
        preview = await preview_thing(
            probe_world.world,
            "character",
            "A Snowy owl-folk courier with blue eyes, who talks too much.",
            {"heritage": probe_world.snowy},
            client,
        )

    facts = probe_world.facts
    inherited = {row.fact_id: row for row in preview.inherited}
    # Snowy's four facts, then Owl-folk's six less the mottled plumage
    # Snowy overrides
    assert len(preview.inherited) == 9
    assert facts["owl-4"] not in inherited
    eyes = inherited[facts["snowy-3"]]
    assert (eyes.source, eyes.source_id, eyes.category, eyes.text) == (
        "Snowy",
        probe_world.snowy,
        "physical",
        "Snowy owl-folk have bright yellow eyes.",
    )
    assert inherited[facts["owl-6"]].source_id == probe_world.owl_folk
    # it survives the wire, as the accept request sends it back
    sent = CreatePreview.model_validate(preview.model_dump(mode="json"))
    assert sent.inherited == preview.inherited


def test_preview_inherited_for_a_mix_lists_both_parents(probe_world):
    view = probe_world.world.view()
    rows = preview_inherited(
        view, "mix", {"parents": [probe_world.lowlander, probe_world.orc]}
    )
    sources = [row.source for row in rows]
    assert sources[:2] == ["Lowlander", "Lowlander"]
    assert {"Human", "Orc"} <= set(sources)
    assert preview_inherited(view, "place", {}) == []


async def test_preview_unknown_override_label_dropped(probe_world):
    reply = json.dumps(
        {
            "name": "Pell",
            "age": 30,
            "facts": [
                {
                    "category": "appearance",
                    "text": "Grey eyes.",
                    "overrides": ["F3", "F99", "bogus"],
                },
                {"category": "appearance", "text": "Ragged wings.", "overrides": "F77"},
            ],
            "no_longer_true": ["F42"],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "Pell is grey-eyed.", "")
        preview = await preview_thing(
            probe_world.world,
            "character",
            "a grey-eyed Snowy",
            {"heritage": probe_world.snowy},
            client,
        )

    assert preview.facts[0].overrides == [probe_world.facts["snowy-3"]]
    assert preview.facts[1].overrides == []


async def test_preview_mix_requires_two_parents(probe_world):
    client = MockClient("test")
    with pytest.raises(ValueError, match="two parents"):
        await preview_thing(probe_world.world, "mix", "half-orcs", {}, client)
    with pytest.raises(ValueError):
        await preview_thing(
            probe_world.world,
            "mix",
            "half-orcs",
            {"parents": [probe_world.lowlander]},
            client,
        )
    assert client.prompt_history == []


async def test_preview_empty_prompt_only_for_a_mix(probe_world):
    with pytest.raises(ValueError, match="needs a prompt"):
        await preview_thing(probe_world.world, "species", "  ", {}, MockClient("t"))


async def test_preview_mix_empty_prompt_ok(probe_world):
    facts = probe_world.facts
    client = MockClient("test")
    async with MockClientContext():
        _queue(_reply("heritage-mix-halforc-reply.txt"), "Half-orc is a blend.")
        preview = await preview_thing(
            probe_world.world,
            "mix",
            "",
            {"parents": [probe_world.lowlander, probe_world.orc]},
            client,
        )

    assert preview.kind == "mix"
    assert preview.name == "Half-orc"
    assert preview.fields["parents"] == [probe_world.lowlander, probe_world.orc]
    assert preview.fields["lifespan"] == 65
    assert preview.fields["adult_age"] == 16
    by_text = {f.text.split(",")[0]: f.overrides for f in preview.facts}
    # labels run on from parent A (Lowlander, then Human) into parent B (Orc)
    assert by_text[
        "They possess a single pair of prominent lower tusks that jut "
        "above the upper lip"
    ] == [facts["human-2"], facts["orc-1"]]
    height = next(f for f in preview.facts if f.text.startswith("They stand"))
    assert height.overrides == [facts["low-1"]]

    create_prompt = str(client.prompt_history[0]["prompt"])
    assert "You draft a new mix" in create_prompt
    assert "Owner's prompt" not in create_prompt
    assert (
        "Parent A: Lowlander (a race of Human). Numbers: lifespan 75 years, "
        "adult at 18, height 5-5.7 ft." in create_prompt
    )
    assert (
        "Parent B: Orc (a species). Numbers: lifespan 60 years, adult at 14, "
        "height 6-7 ft, tusk length 1.5-2.5 in." in create_prompt
    )
    assert "- F3 (Human, physical): Humans have bare skin." in create_prompt
    assert "- F7 (Orc, physical): Orcs have grey-green skin." in create_prompt
    assert "Invent one if the prompt doesn't give it." in create_prompt

    # the prose sees both parents' facts as background, less the ones the
    # mix's own facts override (its skin fact overrides Lowlander's skin)
    prose_prompt = str(client.prompt_history[1]["prompt"])
    assert "Orcs have coarse black hair." in prose_prompt
    assert "Heritage: Lowlander, Human, Orc." in prose_prompt
    assert "Lowlanders have olive skin." not in prose_prompt


async def test_preview_mix_uses_the_decided_name(probe_world):
    reply = json.dumps(
        {
            "name": "Half-orc",
            "facts": [{"category": "physical", "text": "Small tusks."}],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "Orcling is tusked.")
        preview = await preview_thing(
            probe_world.world,
            "mix",
            "",
            {"name": "Orcling", "parents": [probe_world.orc, probe_world.lowlander]},
            client,
        )

    assert preview.name == "Orcling"
    assert "the Orclings, people of mixed parentage" in str(
        client.prompt_history[0]["prompt"]
    )


def test_accept_writes_overrides(probe_world):
    world = probe_world.world
    yellow = probe_world.facts["snowy-3"]
    preview = CreatePreview(
        kind="character",
        prompt="a blue-eyed Snowy",
        fields={"heritage": probe_world.snowy},
        name="Thistledown",
        facts=[
            PreviewFact(category="appearance", text="Blue eyes.", overrides=[yellow]),
            PreviewFact(category="personality", text="Chatty."),
        ],
        prose={"description": "Thistledown is white.", "personality": "Chatty."},
    )

    thing_id = accept_preview(world, preview)

    view = world.view()
    state = view.thing(thing_id)
    eyes = next(f for f in state.facts if f.text == "Blue eyes.")
    assert eyes.overrides == [yellow]
    effective = {fact.fact_id for fact, _ in heritage.effective_facts(view, thing_id)}
    assert yellow not in effective
    assert probe_world.facts["snowy-1"] in effective


async def test_preview_race_gets_species_as_inherited(probe_world):
    facts = probe_world.facts
    client = MockClient("test")
    async with MockClientContext():
        _queue(_reply("heritage-race-snowy-reply.txt"), "Snowy Owl-folk are white.")
        preview = await preview_thing(
            probe_world.world,
            "race",
            "Snowy: the largest owl-folk, white-plumaged, from the frozen north.",
            {"species": probe_world.owl_folk},
            client,
        )

    assert preview.name == "Snowy Owl-folk"
    assert preview.fields["species"] == probe_world.owl_folk
    # the reply restated the species' own ranges: inherited, not pinned
    assert "measures" not in preview.fields
    # "no_longer_true": ["F4"] attaches to the race's own plumage fact
    plumage = next(f for f in preview.facts if "plumage is pure white" in f.text)
    assert plumage.overrides == [facts["owl-4"]]
    assert all(f.overrides == [] for f in preview.facts if f is not plumage)

    create_prompt = str(client.prompt_history[0]["prompt"])
    assert "You create a new race of the Owl-folk species" in create_prompt
    assert (
        "Owl-folk numbers: lifespan 70 years, adult at 12, height 3-4 ft, "
        "wingspan 7-9 ft." in create_prompt
    )
    assert "Owl-folk facts (inherited):" in create_prompt
    assert (
        "- F4 (Owl-folk, physical): Owl-folk plumage is mottled brown and grey, "
        "for camouflage against bark." in create_prompt
    )
    assert '"name": "wingspan", "min": 0' in create_prompt
    assert '"no_longer_true": []' in create_prompt

    # the preview's prose sees the species' facts as background
    prose_prompt = str(client.prompt_history[1]["prompt"])
    assert "taloned feet that serve as hands" in prose_prompt
    assert "Heritage: Owl-folk." in prose_prompt


async def test_preview_race_attaches_top_level_labels(probe_world):
    """A top-level label goes to the own fact of the same category with the
    most word overlap, else the first own fact of that category, else it's
    dropped."""

    facts = probe_world.facts
    reply = json.dumps(
        {
            "name": "Ashen",
            "lifespan": 70,
            "adult_age": 20,
            "facts": [
                {"category": "physical", "text": "Ashen owl-folk are soot black."},
                {"category": "physical", "text": "Their beaks are short and blunt."},
                {"category": "origin", "text": "From the burnt hills."},
            ],
            # F2 (facial disc, beak) by overlap; F6 (instinct) has no
            # instinct fact to go to; F1 (wings) overlaps nothing
            "no_longer_true": ["F2", "F6", "F1"],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "Ashen are black.")
        preview = await preview_thing(
            probe_world.world,
            "race",
            "soot-black owl-folk",
            {"species": probe_world.owl_folk},
            client,
        )

    soot, beak, origin = preview.facts
    assert beak.overrides == [facts["owl-2"]]
    assert soot.overrides == [facts["owl-1"]]
    assert origin.overrides == []
    # a lifespan equal to the species' is dropped, a different one kept
    assert "lifespan" not in preview.fields
    assert preview.fields["adult_age"] == 20


# --- names, stubs, expansion and context (connections, Task 5) ---------------

# the connections probe's raw replies
# (docs/superpowers/probes/2026-10-21-connections.md)
PROBE_RAW = (
    Path(__file__).resolve().parents[2]
    / "docs/superpowers/probes/raw/2026-10-21-connections.json"
)


def _probe_reply(probe: str, variant: str, n: int) -> str:
    runs = json.loads(PROBE_RAW.read_text())[probe]
    return next(r for r in runs if r["variant"] == variant and r["n"] == n)["reply"]


def _aka(name: str, tag: str = "common", everyday: bool = False) -> dict:
    return {"name": name, "tag": tag, "everyday": everyday}


@pytest.fixture
def at_1020(world):
    """The connections probe's world date: 1020."""

    world.set_present(WorldDate.of(1020))
    return world


OWL_ORIGIN = (
    "In 994, every person in the {tsardom} awoke as owl-folk overnight, in "
    "what Moscavians call the Night of Feathers."
)


def _owl_world(world, *, stub: dict | None = None):
    """The probe's Owl-folk (a species with physical, instinct and origin
    facts) whose origin fact mentions the Tsardom of Moscavia stub. Returns
    `(tsardom, owls)`."""

    with world.revision(Source.manual(note="setup")) as rev:
        tsardom = rev.create_thing(
            "place",
            fields={
                "name": "Tsardom of Moscavia",
                "stub": stub or {"ignored": False},
            },
        )
        owls = rev.create_thing("species", fields={"name": "Owl-folk"})
        rev.add_fact(owls, "physical", "Owl-folk have wings in place of arms.")
        rev.add_fact(owls, "instinct", "Owl-folk are crepuscular.")
        rev.add_fact(
            owls,
            "origin",
            OWL_ORIGIN.format(tsardom=ref(tsardom, "Tsardom of Moscavia")),
        )
    return tsardom, owls


def _linked_ids(view, text: str) -> list[str]:
    return [segment.ref for segment in view.segments(text) if segment.ref]


async def test_accept_makes_stubs_and_links_facts(at_1020):
    """Probe 5's broken reply (its wrapper never closes): the aka and names
    lists are still read, never as facts; the listed names become stubs on
    accept and every fact is linked, keeping its words."""

    world = at_1020
    with world.revision(Source.manual(note="setup")) as rev:
        tsardom = rev.create_thing(
            "place",
            fields={
                "name": "Tsardom of Moscavia",
                "aka": [_aka("Moscavia", everyday=True)],
            },
        )
        rev.add_fact(tsardom, "general", "A northern realm of pine forest.")
    reply = _probe_reply("probe5", "everyday", 2)
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "A town of amber.")
        preview = await preview_thing(
            world,
            "place",
            "an amber market town on a lake in Moscavia",
            {},
            client,
            picks={"Moscavia": tsardom},
        )

    assert preview.name == "Solnechnyy Gorod"
    assert preview.aka == [_aka("Sunny City", everyday=True), _aka("Solnyak")]
    assert len(preview.facts) == 12
    assert all(f.text != "common" for f in preview.facts)
    # the world's Tsardom and the "title" Tsar are dropped
    assert [(n.name, n.kind) for n in preview.new_names] == [
        ("Lake Yelizaveta", "place"),
        ("River Solnitsa", "place"),
        ("Pyotr Solnechnyy", "character"),
        ("Kremova", "place"),
        ("Night of Feathers", "event"),
        ("Solnitsa Brotherhood", "lore"),
        ("Darya Volkovna", "character"),
        ("Amber Festival", "event"),
    ]
    assert preview.stub_id is None
    assert preview.matching_stub_id is None

    # the reply's aka and names are asked for, and the pick is named, with
    # its everyday name, in the prompt
    prompt = str(client.prompt_history[0]["prompt"])
    assert '"aka": [{"name": "...", "tag": "common", "everyday": true}]' in prompt
    assert (
        '"names": [{"name": "...", "kind": "place", "tag": "...", "in": null, '
        '"aka": []}]' in prompt
    )
    assert '"names": after the facts, every proper name your facts use' in prompt
    assert 'a people\'s adjective such as "Moscavian" on its own' in prompt
    assert (
        '"Moscavia" means Tsardom of Moscavia (place, usually called Moscavia):'
        in prompt
    )
    assert "- A northern realm of pine forest." in prompt

    head = world.head_rev()
    thing_id = accept_preview(world, preview)
    assert world.head_rev() == head + 1

    view = world.view(None)
    state = view.thing(thing_id)
    assert not state.is_stub
    assert state.fields["aka"] == preview.aka
    stubs = {
        view.name_of(s.id): s for s in view.things() if s.is_stub and s.id != tsardom
    }
    assert set(stubs) == {n.name for n in preview.new_names}
    assert stubs["Kremova"].kind == "place"
    assert stubs["Night of Feathers"].kind == "event"

    by_text = {view.render(f.text): f.text for f in state.facts}
    # every fact keeps its words
    assert set(by_text) == {f.text for f in preview.facts}
    lake = next(t for t in by_text if t.startswith("Solnechnyy Gorod is"))
    # "the Moscavian interior": the adjective links the Tsardom (Moscavia)
    assert _linked_ids(view, by_text[lake]) == [
        stubs["Lake Yelizaveta"].id,
        tsardom,
    ]
    history = next(t for t in by_text if t.startswith("After the Night"))
    assert _linked_ids(view, by_text[history]) == [
        stubs["Night of Feathers"].id,
        tsardom,
    ]
    # the thing's own name and other names never link inside its own facts
    trade = next(t for t in by_text if t.startswith("Solnechnyy Gorod's primary"))
    assert _linked_ids(view, by_text[trade]) == []
    # one revision made it all
    assert {s.source_rev for s in state.facts} == {head + 1}


async def test_expand_stub_uses_mentions_as_context(at_1020):
    world = at_1020
    tsardom, owls = _owl_world(world)
    reply = _probe_reply("probe2", "b", 0)
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "A realm of owl-folk.")
        # the stub's own kind and name are used, whatever is asked
        preview = await preview_thing(
            world,
            "lore",
            "The Tsardom of Moscavia: the country where everyone turned into owl-folk.",
            {},
            client,
            stub_id=tsardom,
        )

    assert preview.kind == "place"
    assert preview.name == "Tsardom of Moscavia"
    assert preview.stub_id == tsardom
    assert preview.matching_stub_id is None
    origin = OWL_ORIGIN.format(tsardom="Tsardom of Moscavia")
    assert preview.context == [
        (
            "Owl-folk (species)",
            [
                origin,
                "Owl-folk have wings in place of arms.",
                "Owl-folk are crepuscular.",
            ],
        )
    ]
    prompt = str(client.prompt_history[0]["prompt"])
    assert "Mentioned elsewhere in the world (keep these true):" in prompt
    assert f"- Owl-folk (species, origin): {origin}" in prompt
    assert (
        "About those (they already exist in the world; let the place reflect "
        "them -- a place is shaped by the people who live there):\nOwl-folk "
        "(species):\n- Owl-folk have wings in place of arms." in prompt
    )
    # the name is decided: the stub's
    assert "- name: Tsardom of Moscavia" in prompt
    # the world's Owl-folk, and the thing's own name, aren't new
    names = [n.name for n in preview.new_names]
    assert "Owl-folk" not in names
    assert "Tsardom of Moscavia" not in names
    assert names[:3] == ["Vladislav I", "Tsar Mikhail III", "The Night of Feathers"]

    head = world.head_rev()
    thing_id = accept_preview(world, preview)
    assert thing_id == tsardom
    assert world.head_rev() == head + 1
    view = world.view(None)
    state = view.thing(tsardom)
    assert not state.is_stub
    assert state.kind == "place"
    assert state.fields["aka"] == [_aka("Moscavia", everyday=True)]
    assert len(state.facts) == len(preview.facts)
    night = next(
        s.id for s in view.things() if view.name_of(s.id) == "The Night of Feathers"
    )
    for fact in state.facts:
        # its own name ("Tsardom", "Moscavia") never links to itself
        assert tsardom not in _linked_ids(view, fact.text)
    # "Night of Feathers", written without the article, links the stub
    once = next(f for f in state.facts if f.text.startswith("Once a kingdom"))
    assert _linked_ids(view, once.text) == [owls, night]
    assert view.render(once.text) == preview.facts[1].text


async def test_expand_ignored_stub_keeps_id_and_revives(at_1020):
    world = at_1020
    tsardom, owls = _owl_world(world, stub={"ignored": True})
    reply = json.dumps(
        {
            "name": "Tsardom of Moscavia",
            "aka": [_aka("Moscavia", everyday=True)],
            "facts": [{"category": "description", "text": "A realm of owl-folk."}],
            "names": [],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "A realm.")
        preview = await preview_thing(
            world, "place", "the owl-folk's country", {}, client, stub_id=tsardom
        )
    assert accept_preview(world, preview) == tsardom

    view = world.view(None)
    state = view.thing(tsardom)
    assert not state.is_stub
    assert not state.stub_ignored
    # the mention is a normal link to the full entry, and the name now
    # matches in new text
    origin = next(f for f in view.thing(owls).facts if f.category == "origin")
    assert _linked_ids(view, origin.text) == [tsardom]
    from talemate.world.names import find_names

    [match] = find_names(view, "The Tsardom of Moscavia is cold.")
    assert match.candidates[0].id == tsardom


async def test_expand_deleted_stub_refused(at_1020):
    world = at_1020
    tsardom, _owls = _owl_world(world)
    reply = json.dumps(
        {
            "name": "Tsardom of Moscavia",
            "facts": [{"category": "description", "text": "A realm of owl-folk."}],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "A realm.")
        preview = await preview_thing(
            world, "place", "the owl-folk's country", {}, client, stub_id=tsardom
        )
    with world.revision(Source.manual(note="delete")) as rev:
        rev.remove_thing(tsardom)

    head = world.head_rev()
    with pytest.raises(ValueError):
        accept_preview(world, preview)
    with pytest.raises(ValueError):
        accept_preview(
            world, preview.model_copy(update={"stub_id": None}), into_stub=tsardom
        )
    assert world.head_rev() == head
    # a deleted stub can't be previewed either
    with pytest.raises(ValueError):
        await preview_thing(
            world, "place", "again", {}, MockClient("test"), stub_id=tsardom
        )
    # the mention still reads as written, not as an unknown name
    view = world.view(None)
    assert "Tsardom of Moscavia awoke" in view.render(
        next(f.text for f in view.thing(_owls).facts if f.category == "origin")
    )


async def test_preview_offers_matching_stub(at_1020):
    world = at_1020
    with world.revision(Source.manual(note="stubs")) as rev:
        frost = rev.create_thing(
            "place", fields={"name": "Frosthollow", "stub": {"ignored": False}}
        )
        # a stub of another kind with the same name is no match
        rev.create_thing(
            "lore", fields={"name": "Frosthollow", "stub": {"ignored": False}}
        )
        vasha = rev.create_thing("character", fields={"name": "Vasha"})
        mention = rev.add_fact(
            vasha, "background", f"Born in {ref(frost, 'Frosthollow')}."
        )
    reply = json.dumps(
        {
            "name": "Frosthollow",
            "facts": [{"category": "description", "text": "A cold valley."}],
            "names": [],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "A cold valley.")
        preview = await preview_thing(world, "place", "a cold valley", {}, client)

    assert preview.stub_id is None
    assert preview.matching_stub_id == frost
    # filling the stub instead keeps its id and its mention
    assert accept_preview(world, preview, into_stub=frost) == frost
    view = world.view(None)
    state = view.thing(frost)
    assert not state.is_stub
    assert [f.text for f in state.facts] == ["A cold valley."]
    assert (
        view.render(
            next(f.text for f in view.thing(vasha).facts if f.fact_id == mention)
        )
        == "Born in Frosthollow."
    )


async def test_picks_add_named_context(at_1020):
    """Probe 3's matched run: "Moscavian Owls" picked as the Owl-folk puts
    their facts in the prompt, and the reply's "Moscavian Owl-folk" isn't
    a new species."""

    world = at_1020
    with world.revision(Source.manual(note="setup")) as rev:
        owls = rev.create_thing(
            "species", fields={"name": "Owl-folk", "aka": [_aka("Owls", everyday=True)]}
        )
        rev.add_fact(owls, "instinct", "Owl-folk go utterly still when startled.")
        rev.add_fact(owls, "physical", "Owl-folk have wide yellow eyes.")
    reply = _probe_reply("probe3", "matched", 0)
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "A river town.")
        preview = await preview_thing(
            world,
            "place",
            "A river town where Moscavian Owls trade with barge crews",
            {},
            client,
            picks={"Moscavian Owls": owls},
        )

    prompt = str(client.prompt_history[0]["prompt"])
    assert (
        "Named in this prompt (these already exist in the world: use them as "
        "they are, and never invent a new one in their place):\n"
        '"Moscavian Owls" means Owl-folk (species, usually called Owls):\n'
        "- Owl-folk have wide yellow eyes.\n"
        "- Owl-folk go utterly still when startled." in prompt
    )
    assert preview.context == [
        (
            'Named in this prompt: "Moscavian Owls" means Owl-folk '
            "(species, usually called Owls)",
            # in the kind's category order: physical before instinct
            [
                "Owl-folk have wide yellow eyes.",
                "Owl-folk go utterly still when startled.",
            ],
        )
    ]
    assert preview.picks == {"Moscavian Owls": owls}
    # "Moscavian Owl-folk" is the Owl-folk; the rest are new
    assert [n.name for n in preview.new_names] == [
        "Tsardom of Moscavia",
        "Solenka River",
        "Night of Feathers",
    ]

    thing_id = accept_preview(world, preview)
    view = world.view(None)
    general = next(
        f
        for f in view.thing(thing_id).facts
        if view.render(f.text).startswith("Moscavian Owl-folk make up")
    )
    assert _linked_ids(view, general.text) == [owls]
    # the town's own everyday name ("Solenka") doesn't link
    streets = next(
        f
        for f in view.thing(thing_id).facts
        if view.render(f.text).startswith("The streets of Solenka")
    )
    assert _linked_ids(view, streets.text) == []


@pytest.mark.parametrize(
    "kind, fact, prose_section",
    [
        ("event", {"category": "summary", "text": "The dam broke."}, "description"),
        ("item", {"category": "power", "text": "It hums near water."}, "description"),
    ],
)
async def test_event_and_item_creatable(at_1020, kind, fact, prose_section):
    world = at_1020
    reply = json.dumps({"name": "The Thing", "facts": [fact], "names": []})
    client = MockClient("test")
    when = WorldDate.of(1001).model_dump()
    fields = {"when": when} if kind == "event" else {}
    async with MockClientContext():
        _queue(reply, "The Thing is old.")
        preview = await preview_thing(world, kind, f"a {kind}", fields, client)
    prompt = str(client.prompt_history[0]["prompt"])
    assert f"You create a new {kind}" in prompt
    if kind == "event":
        assert "summary, consequence, general" in prompt
        # a date field reads as a date, not as its raw value
        assert f"- when: {world.calendar.format(WorldDate.of(1001))}" in prompt
        assert "instant" not in prompt
    assert preview.prose == {prose_section: "The Thing is old."}

    thing_id = accept_preview(world, preview)
    state = world.view(None).thing(thing_id)
    assert state.kind == kind
    assert [f.text for f in state.facts] == [fact["text"]]


async def test_aka_and_stub_never_leak_as_raw_fields(at_1020):
    """Every kind has `aka` and `stub`; neither reaches the prompt as a raw
    field value."""

    world = at_1020
    reply = json.dumps(
        {"name": "Lowmere", "facts": [{"category": "general", "text": "Wet."}]}
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "Wet.")
        preview = await preview_thing(
            world,
            "place",
            "a wet town",
            {"aka": [_aka("Lowie", everyday=True)], "stub": {"ignored": False}},
            client,
        )
    for call in client.prompt_history:
        text = str(call["prompt"])
        assert "'everyday'" not in text
        assert "ignored" not in text
        assert "- aka:" not in text
    # the owner's other names are the preview's; the stub marker is dropped
    assert preview.aka == [_aka("Lowie", everyday=True)]
    assert "aka" not in preview.fields and "stub" not in preview.fields


def test_parse_names_recovers_lists_from_a_cut_off_reply():
    from talemate.worldplay.create import parse_names

    reply = (
        '{"name": "Port", "aka": [{"name": "Porty", "tag": "nickname", '
        '"everyday": true}, "Old Port"], "facts": [{"category": "general", '
        '"text": "The Vesna runs past it."}], "names": [{"name": "Vesna", '
        '"kind": "place", "aka": ["the River"]}, {"name": "Tsar", "kind": '
        '"title", "aka": []}, {"name": "Cut'
    )
    aka, names = parse_names(reply)
    assert aka == [
        # an unknown tag is proper, and a proper name is never everyday
        {"name": "Porty", "tag": "proper", "everyday": False},
        {"name": "Old Port", "tag": "proper", "everyday": False},
    ]
    # a title is no name (ruling F5)
    assert [(n.name, n.kind, n.aka) for n in names] == [
        ("Vesna", "place", [_aka("the River", tag="proper")]),
    ]
    _name, _age, facts = parse_create_reply(reply, "place", Calendar(), 313)
    assert [f.text for f in facts] == ["The Vesna runs past it."]


async def test_listed_names_follow_the_merge_rule(at_1020):
    """A listed name counts only if the facts use it: in full, without its
    article, or (a fuller name) as a capitalised phrase it holds; echoed
    and lowercase names are dropped, and a stub links its written form."""

    world = at_1020
    with world.revision(Source.manual(note="setup")) as rev:
        maren = rev.create_thing("character", fields={"name": "Maren Vos"})
    reply = json.dumps(
        {
            "name": "Greyhold",
            "aka": [_aka("Greyhold", tag="proper"), _aka("the Hold", everyday=True)],
            "facts": [
                {"category": "history", "text": "Alexei III the Feathery built it."},
                {"category": "general", "text": "Great markets fill the halivas."},
                {"category": "general", "text": "Maren keeps the Hold's gate."},
            ],
            "names": [
                # a title added to the written name
                {"name": "Tsar Alexei III the Feathery", "kind": "character"},
                # its first word opens a sentence: no phrase, so dropped
                {"name": "Great Stone Bridge", "kind": "item"},
                # a lowercase coined word, and a name never written
                {"name": "Halivas", "kind": "place"},
                {"name": "Kremova", "kind": "place"},
                # in the world already, by first name
                {"name": "Maren", "kind": "character"},
                # its own other name, and no kind (lore)
                {"name": "The Hold", "kind": "place"},
                {"name": "Alexei III the Feathery", "kind": ""},
            ],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "Greyhold is grey.")
        preview = await preview_thing(world, "place", "a grey keep", {}, client)

    # the main name isn't another name of itself
    assert preview.aka == [_aka("the Hold", everyday=True)]
    [alexei] = preview.new_names
    assert (alexei.name, alexei.kind, alexei.written) == (
        "Tsar Alexei III the Feathery",
        "character",
        ["Alexei III the Feathery"],
    )

    thing_id = accept_preview(world, preview)
    view = world.view(None)
    stub = next(s for s in view.things("character") if s.is_stub)
    facts = {view.render(f.text): f.text for f in view.thing(thing_id).facts}
    assert _linked_ids(view, facts["Alexei III the Feathery built it."]) == [stub.id]
    assert _linked_ids(view, facts["Maren keeps the Hold's gate."]) == [maren]
    assert _linked_ids(view, facts["Great markets fill the halivas."]) == []


async def test_expand_species_stub_states_its_name(at_1020):
    """The species and race branches show no "Already decided" list, so a
    stub's name is stated where the name is asked for."""

    world = at_1020
    with world.revision(Source.manual(note="stub")) as rev:
        otters = rev.create_thing(
            "species", fields={"name": "Lake Otters", "stub": {"ignored": False}}
        )
    reply = json.dumps(
        {"name": "Otterkind", "facts": [{"category": "physical", "text": "Sleek."}]}
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "Lake Otters are sleek.")
        preview = await preview_thing(
            world, "species", "otter-folk", {}, client, stub_id=otters
        )
    prompt = str(client.prompt_history[0]["prompt"])
    assert 'Use the name already decided: "Lake Otters".' in prompt
    assert preview.name == "Lake Otters"


async def test_expand_mix_stub_gets_context_blocks(probe_world):
    world = probe_world.world
    with world.revision(Source.manual(note="stub")) as rev:
        stub = rev.create_thing(
            "mix", fields={"name": "Orcling", "stub": {"ignored": False}}
        )
        town = rev.create_thing("place", fields={"name": "Tuskford"})
        rev.add_fact(town, "general", f"Most of its smiths are {ref(stub)}s.")
    reply = json.dumps(
        {"name": "Orcling", "facts": [{"category": "physical", "text": "Tusked."}]}
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "Orcling is tusked.")
        preview = await preview_thing(
            world,
            "mix",
            "",
            {"parents": [probe_world.orc, probe_world.lowlander]},
            client,
            stub_id=stub,
            picks={"Tuskford": town},
        )
    prompt = str(client.prompt_history[0]["prompt"])
    # Tuskford's only fact is the mention, so there's no "About those"
    assert (
        "Mentioned elsewhere in the world (keep these true):\n"
        "- Tuskford (place, general): Most of its smiths are Orclings.\n\n"
        "Named in this prompt (these already exist in the world: use them as "
        "they are, and never invent a new one in their place):\n"
        '"Tuskford" means Tuskford (place):\n'
        "- Most of its smiths are Orclings.\n\n"
        "The world's calendar:" in prompt
    )
    assert "About those" not in prompt
    assert '"names": [{"name": "...", "kind": "place", "aka": []}]' in prompt
    assert preview.stub_id == stub


async def test_picked_names_never_become_stubs(at_1020):
    """The owner's picks win: a listed name the owner matched in the prompt
    (written unlike the entry's name or other names) is no new stub."""

    world = at_1020
    with world.revision(Source.manual(note="setup")) as rev:
        court = rev.create_thing("lore", fields={"name": "Court of Tides"})
        rev.add_fact(court, "general", "It meets under the bay.")
    reply = json.dumps(
        {
            "name": "Bayreach",
            "facts": [
                {"category": "general", "text": "The Sunken Court rules Bayreach."}
            ],
            "names": [
                {"name": "Sunken Court", "kind": "lore"},
                {"name": "The Sunken Court", "kind": "lore"},
            ],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "Bayreach is wet.")
        preview = await preview_thing(
            world,
            "place",
            "a bay town ruled by the Sunken Court",
            {},
            client,
            picks={"the Sunken Court": court},
        )
    assert preview.new_names == []

    thing_id = accept_preview(world, preview)
    view = world.view(None)
    assert [s for s in view.things() if s.is_stub] == []
    [fact] = view.thing(thing_id).facts
    assert _linked_ids(view, fact.text) == [court]


def test_parse_names_skips_a_cut_off_entrys_aka():
    from talemate.worldplay.create import parse_names

    reply = (
        '{"name": "Port", "facts": [{"category": "general", "text": "Busy."}], '
        '"names": [{"name": "Vesna", "kind": "place", "aka": []}, '
        '{"name": "Kremova Port", "kind": "place", "aka": [{"name": "Krem", '
        '"tag": "common", "everyday": true}'
    )
    _aka, names = parse_names(reply)
    assert [n.name for n in names] == ["Vesna"]


async def test_accept_refuses_two_different_stubs(at_1020):
    world = at_1020
    tsardom, _owls = _owl_world(world)
    with world.revision(Source.manual(note="other")) as rev:
        other = rev.create_thing(
            "place", fields={"name": "Elsewhere", "stub": {"ignored": False}}
        )
    preview = CreatePreview(
        kind="place",
        prompt="x",
        name="Tsardom of Moscavia",
        facts=[PreviewFact(category="general", text="Cold.")],
        prose={},
        stub_id=tsardom,
    )
    head = world.head_rev()
    with pytest.raises(ValueError):
        accept_preview(world, preview, into_stub=other)
    assert world.head_rev() == head
    # the same stub twice is fine
    assert accept_preview(world, preview, into_stub=tsardom) == tsardom


async def test_listed_names_link_or_stay_suggestions(at_1020):
    """From the Skyfall run: a listed "Owl-folk" while the species
    "Owl-folk of Moscavia" exists links to that species (no duplicate
    stub); a listed "Moscavia", only a suggested part of the "Tsardom of
    Moscavia", stays a suggestion, not a stub."""

    world = at_1020
    with world.revision(Source.manual(note="setup")) as rev:
        owls = rev.create_thing("species", fields={"name": "Owl-folk of Moscavia"})
        rev.create_thing("place", fields={"name": "Tsardom of Moscavia"})
    reply = json.dumps(
        {
            "name": "Velikostok",
            "facts": [
                {"category": "description", "text": "Velikostok lies in Moscavia."},
                {"category": "history", "text": "Owl-folk nest in its towers."},
            ],
            "names": [
                {"name": "Moscavia", "kind": "place"},
                {"name": "Owl-folk", "kind": "species"},
            ],
        }
    )
    async with MockClientContext():
        _queue(reply, "A city of towers.")
        preview = await preview_thing(
            world, "place", "a city of towers", {}, MockClient("test")
        )
    assert [n.name for n in preview.new_names] == ["Owl-folk"]

    thing_id = accept_preview(world, preview)
    view = world.view(None)
    assert [s for s in view.things() if s.is_stub] == []
    texts = {f.category: f.text for f in view.thing(thing_id).facts}
    assert texts["history"] == f"{ref(owls, 'Owl-folk')} nest in its towers."
    assert texts["description"] == "Velikostok lies in Moscavia."


async def test_accept_makes_no_stub_its_facts_never_link(at_1020):
    """A listed name no fact links to (here an inner-capital name written
    in lowercase, so it gets no span) makes no orphan stub; the others are
    made and linked as usual."""

    world = at_1020
    preview = CreatePreview(
        kind="place",
        prompt="a market",
        name="Suq Amber",
        facts=[
            PreviewFact(
                category="general",
                text="Merchants of al-Qadir trade with Kremova here.",
            )
        ],
        prose={},
        new_names=[
            NewName(name="al-Qadir", kind="character"),
            NewName(name="Kremova", kind="place"),
        ],
    )
    thing_id = accept_preview(world, preview)
    view = world.view(None)
    stubs = [view.name_of(s.id) for s in view.things() if s.is_stub]
    assert stubs == ["Kremova"]
    kremova = next(s.id for s in view.things() if s.is_stub)
    assert view.thing(thing_id).facts[0].text == (
        f"Merchants of al-Qadir trade with {ref(kremova, 'Kremova')} here."
    )


async def test_filling_a_stub_under_a_new_name_keeps_the_old_one(at_1020):
    """A stub filled under another name keeps its old name as a common
    other name, so text that calls it that still finds it."""

    world = at_1020
    with world.revision(Source.manual(note="setup")) as rev:
        moskov = rev.create_thing(
            "place", fields={"name": "Moskov", "stub": {"ignored": False}}
        )
    reply = json.dumps(
        {"name": "Moskov", "facts": [{"category": "description", "text": "White."}]}
    )
    async with MockClientContext():
        _queue(reply, "White walls.")
        preview = await preview_thing(
            world, "place", "a white city", {}, MockClient("test"), stub_id=moskov
        )
    # the owner renames it before accepting
    preview.name = "Grand City of Moskov"
    assert accept_preview(world, preview) == moskov

    state = world.view(None).thing(moskov)
    assert state.fields["name"] == "Grand City of Moskov"
    assert state.fields["aka"] == [_aka("Moskov")]


async def test_preview_finds_prompt_names_the_picks_miss(at_1020):
    """A Create clicked before the screen's name matches came back sends no
    picks: the names in the prompt are found here, so they're still
    "Named in this prompt" context. A name treated as new still isn't."""

    world = at_1020
    with world.revision(Source.manual(note="setup")) as rev:
        tsardom = rev.create_thing("place", fields={"name": "Tsardom of Moscavia"})
        rev.add_fact(tsardom, "general", "A northern realm of pine forest.")
        maren = rev.create_thing("character", fields={"name": "Maren Vos"})
        rev.add_fact(maren, "background", "A ferrywoman.")
    reply = json.dumps(
        {"name": "Velikostok", "facts": [{"category": "general", "text": "Pines."}]}
    )
    prompt = "a town in the Tsardom of Moscavia where Maren lives"

    async def preview(**extra):
        client = MockClient("test")
        async with MockClientContext():
            _queue(reply, "Pines.")
            result = await preview_thing(world, "place", prompt, {}, client, **extra)
        return result, str(client.prompt_history[0]["prompt"])

    found, sent = await preview()
    assert found.picks == {"Tsardom of Moscavia": tsardom, "Maren": maren}
    assert "- A northern realm of pine forest." in sent
    assert "- A ferrywoman." in sent

    # "treat as new" wins, and a thing the owner picked isn't found twice
    kept, sent = await preview(new_names=["Maren"], picks={"Tsardom": tsardom})
    assert kept.picks == {"Tsardom": tsardom}
    assert "- A ferrywoman." not in sent
    kept, _sent = await preview(picks={"maren": maren})
    assert kept.picks == {"maren": maren, "Tsardom of Moscavia": tsardom}


def test_adjective_form_name_is_still_stubbed(at_1020):
    """A new name that's only another entry's adjective form ("Magian" of
    the Magi) isn't known: it's stubbed, and its stub, once made, is what
    the text links."""

    from talemate.worldplay.create import _new_names, listed_names
    from talemate.worldplay.links import link_text
    from talemate.world.refs import parse_refs

    world = at_1020
    with world.revision(Source.manual(note="setup")) as rev:
        magi = rev.create_thing("place", fields={"name": "Magi"})
    view = world.view()
    listed = [
        found.name
        for found in listed_names([{"name": "Magian", "kind": "character", "aka": []}])
    ]

    kept = _new_names(view, listed, ["Magian the seer came to the Magi."], [])

    assert [n.name for n in kept] == ["Magian"]
    with world.revision(Source.manual(note="stub")) as rev:
        magian = rev.create_thing(
            "character", fields={"name": "Magian", "stub": {"ignored": False}}
        )
    linked = link_text(world.view(), "Magian the seer came to the Magi.")
    assert parse_refs(linked) == [magian, magi]


# --- a character's "In" rows and their exceptions ------------------------------
#
# The ties at character creation (spheres probe (c)) became "In" rows
# (Filing, Task 4): the entries the character may belong in are shown with
# their items labelled S1..., and an "in" item's "exceptions" map to those
# items, written on accept as `ties` facts the filing's `exceptions` hold.

from talemate.world.filing import filings_of  # noqa: E402


class DawnWorld(NamedTuple):
    dawn: str
    separation: str
    vigil: str
    purity: str
    kremova: str
    tsardom: str
    kovask: str
    law: str


def _filed_in(*targets: str) -> list[dict]:
    return [{"target": target, "role": None} for target in targets]


@pytest.fixture
def dawn_world(at_1020):
    """The spheres probe's White Dawn, now lore tagged religion (everyday
    "the Dawn"), with its creed, a belief, and a doctrine and a rite filed
    in it; Kremova, a holy city filed in the Dawn and in the Tsardom of
    Moscavia, a nation place (other name Moscavia) with one law, which
    Kovask is filed in too."""

    with at_1020.revision(Source.manual(note="filings")) as rev:
        tsardom = rev.create_thing(
            "place",
            fields={
                "name": "Tsardom of Moscavia",
                "tag": "nation",
                "aka": [_aka("Moscavia", everyday=True)],
            },
        )
        rev.add_fact(tsardom, "description", "A northern realm of owl-folk.")
        law = rev.add_fact(tsardom, "law", "Only owl-folk may hold land.")
        kovask = rev.create_thing(
            "place", fields={"name": "Kovask", "filings": _filed_in(tsardom)}
        )
        dawn = rev.create_thing(
            "lore",
            fields={
                "name": "The White Dawn",
                "tag": "religion",
                "aka": [_aka("Dawn Church", tag="proper"), _aka("the Dawn")],
            },
        )
        rev.add_fact(dawn, "general", "The state church of the owl-folk.")
        purity = rev.add_fact(
            dawn, "belief", "Snowy owl-folk are the purest of the folk."
        )
        separation = rev.create_thing(
            "lore",
            fields={
                "name": "The Doctrine of Separation",
                "tag": "doctrine",
                "filings": _filed_in(dawn),
            },
        )
        rev.add_fact(separation, "general", "The faithful may not marry humans.")
        rev.add_fact(separation, "general", "Issued in 1019.")
        kremova = rev.create_thing(
            "place",
            fields={"name": "Kremova", "filings": _filed_in(dawn, tsardom)},
        )
        rev.add_fact(kremova, "general", "The white city.")
        vigil = rev.create_thing(
            "lore",
            fields={
                "name": "The Dawn Vigil",
                "tag": "rite",
                "filings": _filed_in(dawn),
            },
        )
        rev.add_fact(vigil, "general", "The faithful watch the first light.")
    return DawnWorld(dawn, separation, vigil, purity, kremova, tsardom, kovask, law)


DAWN_BLOCK = (
    "Entries in the world the character may belong in (faiths, orders, "
    "cultures, fields of knowledge), each with what it holds, labelled S1, "
    "S2...:\n"
    "The White Dawn (religion):\n"
    "- S1: The state church of the owl-folk.\n"
    # a belief is told as held (ruling C33)
    "- S2: The White Dawn holds: Snowy owl-folk are the purest of the folk.\n"
    "- S3: The Doctrine of Separation (doctrine): The faithful may not marry "
    "humans.\n"
    "- S4: The Dawn Vigil (rite): The faithful watch the first light.\n"
)


def _priestess_reply(into: list) -> str:
    return json.dumps(
        {
            "name": "Ilyana",
            "age": 30,
            "facts": [
                {"category": "background", "text": "Raised in a mountain cloister."},
                {"category": "personality", "text": "Patient and wry."},
            ],
            "names": [],
            "in": into,
        }
    )


async def _preview_priestess(world, prompt: str, into: list, **extra):
    client = MockClient("test")
    async with MockClientContext():
        _queue(_priestess_reply(into), "She is tall.", "She is patient.")
        preview = await preview_thing(world, "character", prompt, {}, client, **extra)
    return preview, str(client.prompt_history[0]["prompt"])


async def test_character_preview_offers_in_rows_with_exceptions(at_1020, dawn_world):
    """An entry named in the prompt is shown with its items labelled
    S1..., places left out, and not again under "Named in this prompt";
    the reply's "in" row resolves to it, unticked (ruling F7), with
    `since` read as a fact's and each exception's label mapped to its
    item."""

    d = dawn_world
    preview, prompt = await _preview_priestess(
        at_1020,
        "a priestess of the White Dawn who loves a human",
        [
            {
                "entry": "The White Dawn",
                "role": "priest",
                "since": "1004",
                "exceptions": [
                    {"text": "She means to marry a human.", "rejects": "S3"},
                    {"text": "She thinks all folk equal.", "rejects": "s2"},
                ],
            }
        ],
    )

    assert DAWN_BLOCK + "\nEntries near this one in the world:\n" in prompt
    assert "Named in this prompt" not in prompt
    assert (
        '"in": [{"entry": "<an entry\'s name>", "role": "a few words", '
        '"exceptions": [{"text": "One sentence.", "rejects": "S1"}]}]' in prompt
    )
    assert (
        '- "exceptions": in an "in" item, only where this character departs '
        'from that entry, each {"text", "rejects"}: "text" one sentence on '
        'what they reject or do differently, and "rejects" the label of the '
        'item it departs from, such as "S3". The character already holds '
        "everything else the entry holds, so never restate it, in an "
        "exception or in the facts. Most entries have no exception or one.\n"
        "- Write each exception only there, never again as one of the facts.\n"
        "\nNo commentary" in prompt
    )

    [row] = preview.filings
    assert (row.target_id, row.target_name, row.role, row.ticked) == (
        d.dawn,
        "The White Dawn",
        "priest",
        False,
    )
    assert row.since == WorldDate.of(1004)
    assert [(e.text, e.thing_id, e.fact_id) for e in row.exceptions] == [
        ("She means to marry a human.", d.separation, None),
        ("She thinks all folk equal.", None, d.purity),
    ]
    # the owner sees the entry as context too
    assert (
        "May belong in: The White Dawn (religion)",
        [
            "S1: The state church of the owl-folk.",
            "S2: The White Dawn holds: Snowy owl-folk are the purest of the folk.",
            "S3: The Doctrine of Separation (doctrine): The faithful may not "
            "marry humans.",
            "S4: The Dawn Vigil (rite): The faithful watch the first light.",
        ],
    ) in preview.context


async def test_no_homes_no_exceptions_wording(at_1020):
    """With nothing in context there's no list of entries, so the prompt
    asks for no "in" rows or exceptions, and a reply's stray ones resolve
    to nothing."""

    preview, prompt = await _preview_priestess(
        at_1020,
        "a wandering priestess",
        [{"entry": "The White Dawn", "role": "priest"}],
    )

    assert "may belong in" not in prompt
    assert '"exceptions"' not in prompt and '"in": [' not in prompt
    assert preview.filings == []


async def test_unknown_in_entry_dropped(at_1020, dawn_world):
    """An "in" row resolves by an entry's name or other name, any case, a
    leading article dropped: an unknown entry and an adjective form
    ("Moscavian") are dropped, an entry listed twice is one row, and a row
    without a role has none."""

    d = dawn_world
    preview, _prompt = await _preview_priestess(
        at_1020,
        "a priestess of the White Dawn",
        [
            {"entry": "The Iron Covenant", "role": "member"},
            {"entry": "Moscavian", "role": "subject"},
            {"entry": "Dawn Church", "role": "priest"},
            {"entry": "moscavia"},
            {"entry": "white dawn", "role": "again"},
            {"entry": "Kremova", "role": "pilgrim"},
            "The White Dawn",
        ],
    )

    assert [(f.target_id, f.role) for f in preview.filings] == [
        (d.dawn, "priest"),
        (d.tsardom, None),
        (d.kremova, "pilgrim"),
    ]


async def test_in_since_parsed_like_a_facts(at_1020, dawn_world):
    """`since` is a string or a number, read like a fact's; a year after
    now, a placeholder or a phrase is no date."""

    sinces = [1004, "1010", "1996", "YEAR", "since childhood", None]
    entries = ["The White Dawn", "Kremova", "Kovask", "Moscavia", "Dawn Vigil"]
    entries += ["Doctrine of Separation"]
    preview, _prompt = await _preview_priestess(
        at_1020,
        "a priestess of the White Dawn",
        [
            {"entry": entry, "role": "priest", "since": s}
            for entry, s in zip(entries, sinces)
        ],
    )

    assert [f.since for f in preview.filings] == [
        WorldDate.of(1004),
        WorldDate.of(1010),
        None,
        None,
        None,
        None,
    ]


async def test_home_labels_run_across_entries(at_1020, dawn_world):
    """A picked place brings what it's filed in (Kremova is in the Dawn and
    the Tsardom), lore or place; an entry reached twice is listed once;
    labels run on from one entry into the next. An exception whose label
    is another entry's item is dropped, as is an unknown or missing one."""

    d = dawn_world
    preview, prompt = await _preview_priestess(
        at_1020,
        "a priestess of the White Dawn from Kremova",
        [
            {
                "entry": "Tsardom of Moscavia",
                "role": "subject",
                "exceptions": [
                    {"text": "She rents land to humans.", "rejects": "S6"},
                    # the Dawn's label under the Tsardom's row: dropped
                    {"text": "She skips the vigil.", "rejects": "S4"},
                    {"text": "Unlabelled.", "rejects": "S99"},
                    {"text": "No label at all."},
                ],
            }
        ],
    )

    assert prompt.count("The White Dawn (religion):") == 1
    assert (
        "Tsardom of Moscavia (nation, usually called Moscavia):\n"
        "- S5: A northern realm of owl-folk.\n"
        "- S6: Only owl-folk may hold land.\n" in prompt
    )
    # Kremova, a plain place, is still named; the Dawn isn't
    assert '"Kremova" means Kremova (place):' in prompt
    assert '"White Dawn"' not in prompt.split("Named in this prompt")[1]
    [row] = preview.filings
    assert row.target_id == d.tsardom
    assert [(e.text, e.fact_id) for e in row.exceptions] == [
        ("She rents land to humans.", d.law)
    ]


async def test_accepted_exceptions_round_trip(at_1020, dawn_world):
    """On accept a ticked row is written as a filing, and each exception
    becomes a `ties` fact whose id the filing's `exceptions` hold: one
    departing from a filed entry ends with a reference to it, one from a
    fact references the entry and records the fact in its origin (ruling
    P3). No `ties` field is written."""

    d = dawn_world
    preview, _prompt = await _preview_priestess(
        at_1020,
        "a priestess of the White Dawn",
        [
            {
                "entry": "The White Dawn",
                "role": "priest",
                "since": 1004,
                "exceptions": [
                    {"text": "She means to marry a human", "rejects": "S3"},
                    {"text": "She thinks all folk equal.", "rejects": "S2"},
                ],
            }
        ],
    )
    preview.filings[0].ticked = True

    thing_id = accept_preview(at_1020, preview)

    view = at_1020.view(None)
    state = view.thing(thing_id)
    assert "ties" not in state.fields
    [filing] = filings_of(view, thing_id)
    assert (filing.target, filing.role, filing.since) == (
        d.dawn,
        "priest",
        WorldDate.of(1004),
    )
    ties_facts = {f.fact_id: f for f in state.facts if f.category == "ties"}
    assert len(ties_facts) == 2
    assert set(filing.exceptions) == set(ties_facts)
    by_thing = next(f for f in ties_facts.values() if d.separation in f.refs)
    assert by_thing.text.endswith(ref(d.separation, "The Doctrine of Separation"))
    assert view.render(by_thing.text) == (
        "She means to marry a human. Departs from The Doctrine of Separation"
    )
    by_fact = next(f for f in ties_facts.values() if f.fact_id != by_thing.fact_id)
    assert by_fact.origin == {"tie": d.dawn, "rejects_fact": d.purity}
    assert by_thing.origin == {"tie": d.dawn}
    assert d.dawn in by_fact.refs
    # no fact of the facts list went to the ties category
    assert all(f.category != "ties" for f in preview.facts)


def test_cut_off_reply_ties_are_no_facts():
    """A reply cut off inside its "in" list: neither an "in" item nor an
    exception object is read as a fact."""

    reply = (
        '{"name": "Ilyana", "facts": [{"category": "background", "text": '
        '"Raised in a cloister."}], "names": [], "in": [{"entry": "The '
        'White Dawn", "role": "priest", "since": 1004, "exceptions": '
        '[{"text": "She marries.", "rejects": "S1"}]}, {"entry": "Mosc'
    )

    _name, _age, facts = parse_create_reply(reply, "character", Calendar(), 1020)

    assert [f.text for f in facts] == ["Raised in a cloister."]


async def test_heritage_character_gets_the_in_wording(probe_world):
    """The heritage branch asks for "in" too, its example object gaining
    the rows (with exceptions when entries are shown) after "names"; the
    block sits before the list of entries near it, and no "elsewhere" is
    asked for."""

    world = probe_world.world
    with world.revision(Source.manual(note="faith")) as rev:
        dawn = rev.create_thing(
            "lore", fields={"name": "The White Dawn", "tag": "religion"}
        )
        rev.add_fact(dawn, "belief", "Snowy owl-folk are pure.")
    client = MockClient("test")
    async with MockClientContext():
        _queue(
            _priestess_reply([{"entry": "White Dawn", "role": "practitioner"}]),
            "She is white.",
            "She is calm.",
        )
        preview = await preview_thing(
            world,
            "character",
            "a Snowy courier of the White Dawn",
            {"heritage": probe_world.snowy},
            client,
        )

    prompt = str(client.prompt_history[0]["prompt"])
    assert (
        "The White Dawn (religion):\n"
        "- S1: The White Dawn holds that Snowy owl-folk are pure.\n"
        "\nEntries near this one in the world:" in prompt
    )
    assert '"overrides": []' in prompt
    assert '"aka": []}], "in": [{"entry": "<an entry\'s name>"' in prompt
    assert '"elsewhere"' not in prompt
    assert [(f.target_id, f.role, f.since) for f in preview.filings] == [
        (dawn, "practitioner", None)
    ]


async def test_accept_leaves_out_a_filing_to_a_deleted_entry(at_1020, dawn_world):
    preview, _prompt = await _preview_priestess(
        at_1020,
        "a priestess of the White Dawn",
        [{"entry": "The White Dawn", "role": "priest"}],
    )
    preview.filings[0].ticked = True
    with at_1020.revision(Source.manual(note="gone")) as rev:
        rev.remove_thing(dawn_world.dawn)
    notes: list[str] = []

    thing_id = accept_preview(at_1020, preview, notes=notes)

    view = at_1020.view(None)
    assert filings_of(view, thing_id, live=False) == []
    assert any("The White Dawn is gone" in note for note in notes)


async def test_homes_block_caps_items_per_entry(at_1020, dawn_world):
    """Ruling P9: each entry shows its first 8 items (places and people
    left out); only those get labels, so the next entry starts at S9."""

    d = dawn_world
    with at_1020.revision(Source.manual(note="more")) as rev:
        for n in range(1, 8):
            rev.add_fact(d.dawn, "general", f"Teaching number {n}.")
    preview, prompt = await _preview_priestess(
        at_1020,
        "a priestess of the White Dawn from Kremova",
        [
            {
                "entry": "Tsardom of Moscavia",
                "role": "subject",
                "exceptions": [{"text": "She rents land to humans.", "rejects": "S10"}],
            }
        ],
    )

    assert "- S8: Teaching number 6.\n" in prompt
    assert "Teaching number 7." not in prompt.split("Entries near this one")[0]
    assert "- S10: Only owl-folk may hold land.\n" in prompt
    assert "S11" not in prompt
    [row] = preview.filings
    assert [e.fact_id for e in row.exceptions] == [d.law]


async def test_homes_block_item_line_not_doubled(at_1020, dawn_world):
    """Ruling P5: a filed entry whose text already opens with its name is
    listed as the text alone, never "Name: Name ..."."""

    d = dawn_world
    with at_1020.revision(Source.manual(note="named")) as rev:
        doctrine = rev.create_thing(
            "lore",
            fields={"name": "The Doctrine of Purity", "filings": _filed_in(d.dawn)},
        )
        rev.add_fact(
            doctrine, "general", "The Doctrine of Purity keeps the roosts apart."
        )
    _preview, prompt = await _preview_priestess(
        at_1020, "a priestess of the White Dawn", []
    )

    assert "- S5: The Doctrine of Purity keeps the roosts apart.\n" in prompt
    assert "The Doctrine of Purity (lore): The Doctrine of Purity" not in prompt


async def test_stub_mentioned_by_a_faith_shows_it_with_its_items(at_1020, dawn_world):
    """Expanding a character stub a faith mentions: the faith comes in
    through the mention context and is shown with its items, never as
    "Named in this prompt", even when picked too."""

    d = dawn_world
    with at_1020.revision(Source.manual(note="stub")) as rev:
        stub = rev.create_thing(
            "character", fields={"name": "Ilyana", "stub": {"ignored": False}}
        )
        rev.add_fact(
            d.dawn, "general", "%s keeps the vigil flame." % ref(stub, "Ilyana")
        )
    for picks in ({}, {"White Dawn": d.dawn}):
        preview, prompt = await _preview_priestess(
            at_1020,
            "a priestess of the White Dawn",
            [{"entry": "The White Dawn", "role": "priest"}],
            stub_id=stub,
            picks=picks,
        )
        assert "The White Dawn (religion):\n" in prompt
        assert "- S3: Ilyana keeps the vigil flame.\n" in prompt
        assert "Named in this prompt" not in prompt
        assert [f.target_id for f in preview.filings] == [d.dawn]


async def test_accept_drops_exceptions_whose_item_is_gone(at_1020, dawn_world):
    """An exception whose item is gone from its entry by accept (a filed
    entry deleted, a fact removed) is dropped quietly; the filing stays."""

    d = dawn_world
    preview, _prompt = await _preview_priestess(
        at_1020,
        "a priestess of the White Dawn",
        [
            {
                "entry": "The White Dawn",
                "role": "priest",
                "exceptions": [
                    {"text": "She means to marry a human.", "rejects": "S3"},
                    {"text": "She skips the vigil.", "rejects": "S4"},
                    {"text": "She thinks all folk equal.", "rejects": "S2"},
                ],
            }
        ],
    )
    preview.filings[0].ticked = True
    with at_1020.revision(Source.manual(note="gone")) as rev:
        rev.remove_thing(d.separation)
        rev.remove_fact(d.purity)

    thing_id = accept_preview(at_1020, preview)

    view = at_1020.view(None)
    state = view.thing(thing_id)
    [filing] = filings_of(view, thing_id)
    assert filing.target == d.dawn
    ties_facts = [f for f in state.facts if f.category == "ties"]
    assert [view.render(f.text) for f in ties_facts] == [
        "She skips the vigil. Departs from The Dawn Vigil"
    ]
    assert filing.exceptions == [ties_facts[0].fact_id]


async def test_accept_skips_blank_exceptions(at_1020, dawn_world):
    """An exception the owner blanked in the preview writes no fact."""

    preview, _prompt = await _preview_priestess(
        at_1020,
        "a priestess of the White Dawn",
        [
            {
                "entry": "The White Dawn",
                "role": "priest",
                "exceptions": [{"text": "She skips the vigil.", "rejects": "S4"}],
            }
        ],
    )
    preview.filings[0].ticked = True
    preview.filings[0].exceptions[0].text = "   "

    thing_id = accept_preview(at_1020, preview)

    view = at_1020.view(None)
    state = view.thing(thing_id)
    assert [f for f in state.facts if f.category == "ties"] == []
    [filing] = filings_of(view, thing_id)
    assert filing.exceptions == []


# --- what the spheres' create tests held for live behaviour (Filing, Task 7)


@pytest.fixture
def church_world(world):
    """Present 1020: the Tsardom of Moscavia (a place), Kremova filed in
    it, and the White Dawn, a lore stub the Tsardom's law names."""

    world.set_present(WorldDate.of(1020))
    with world.revision(Source.manual(note="moscavia")) as rev:
        tsardom = rev.create_thing(
            "place",
            {
                "name": "Tsardom of Moscavia",
                "aka": [{"name": "Moscavia", "tag": "common", "everyday": True}],
            },
        )
        rev.create_thing("place", {"name": "Kremova", "filings": [{"target": tsardom}]})
        dawn = rev.create_thing(
            "lore", {"name": "The White Dawn", "stub": {"ignored": False}}
        )
        rev.add_fact(
            tsardom,
            "law",
            f"{ref(dawn, 'The White Dawn')} is the Tsardom's state church.",
        )
    return dawn


async def test_place_create_prompt_hides_unprompted_categories(church_world, world):
    """A place may hold timeline, summary and statement facts, but its
    create prompt never offers them (`kinds.UNPROMPTED_CATEGORIES`)."""

    reply = json.dumps(
        {
            "name": "Vesnagrad",
            "facts": [
                {"category": "description", "text": "A river town."},
                {"category": "timeline", "text": "Founded long ago."},
            ],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "A river town.")
        preview = await preview_thing(world, "place", "a river town", {}, client)
    prompt = str(client.prompt_history[0]["prompt"])
    assert "description, history, law, general." in prompt
    assert "timeline" not in prompt.split("FORMAT")[-1]
    assert [f.category for f in preview.facts] == ["description", "general"]


async def test_create_prompt_names_faiths_and_orders_as_lore(church_world, world):
    """A thing's create prompt names a faith, order or culture as lore (the
    filing probe's names rule), so a reply that still gives one the old
    sphere kind makes a lore stub."""

    reply = json.dumps(
        {
            "name": "Vesnagrad",
            "facts": [
                {
                    "category": "description",
                    "text": "A river town where the Church of the Vesna keeps "
                    "its oldest shrine.",
                }
            ],
            "names": [
                {
                    "name": "Church of the Vesna",
                    "kind": "sphere",
                    "template": "religion",
                    "aka": [],
                }
            ],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "A river town.")
        preview = await preview_thing(world, "place", "a river town", {}, client)
    prompt = str(client.prompt_history[0]["prompt"])
    assert (
        '"kind" one of character, place, species, race, event, item, lore (a '
        "country, realm or city is a place; a faith, order, council, guild, "
        "culture, field of knowledge or magic, law, script or language is "
        "lore)" in prompt
    )
    assert '"sphere"' not in prompt
    assert [(n.name, n.kind) for n in preview.new_names] == [
        ("Church of the Vesna", "lore")
    ]


async def test_culture_and_order_guesses_become_lore(church_world, world):
    """A culture, an order or a sphere the reply names is lore: there is no
    sphere or culture kind."""

    reply = json.dumps(
        {
            "name": "Vesnagrad",
            "facts": [
                {
                    "category": "description",
                    "text": "Vesnagrad keeps the Moscavian Way and the Rite "
                    "of Amber, and hosts the Guild of Rafters.",
                }
            ],
            "names": [
                {"name": "Moscavian Way", "kind": "culture", "aka": []},
                {"name": "Guild of Rafters", "kind": "order"},
                {"name": "Rite of Amber", "kind": "sphere", "template": "rite"},
            ],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "Vesnagrad on the river.")
        preview = await preview_thing(world, "place", "a river town", {}, client)

    assert {n.name: n.kind for n in preview.new_names} == {
        "Moscavian Way": "lore",
        "Guild of Rafters": "lore",
        "Rite of Amber": "lore",
    }

    accept_preview(world, preview)
    view = world.view()
    (way,) = [t for t in view.things() if view.name_of(t.id) == "Moscavian Way"]
    assert way.kind == "lore"
    assert way.is_stub


async def test_homes_block_carries_a_cached_summary(church_world, world):
    """An entry with no fact but a cached summary (its description prose):
    the character prompt's block of entries it may belong in carries that
    summary line."""

    dawn = church_world
    summary = "The White Dawn is the Tsardom's state church."
    world.prose().put(dawn, "description", None, None, summary, rev=world.head_rev())
    view = world.view()

    (block,), _labels = homes_block(
        view, [dawn], lambda thing_id: cached_summary(world, thing_id)
    )
    assert block[1] == summary

    client = MockClient("test")
    async with MockClientContext():
        reply = {
            "name": "Vasha",
            "facts": [{"category": "background", "text": "Carries letters."}],
            "names": [],
        }
        _queue(json.dumps(reply), "Vasha.", "Dry.")
        await preview_thing(
            world,
            "character",
            "Vasha, a courier of the White Dawn",
            {},
            client,
            picks={"White Dawn": dawn},
        )
        # the queue is shared by the process's tests: nothing left over
        client_responses.get().clear()
    assert summary in str(client.prompt_history[0]["prompt"])


async def test_a_hint_sets_the_agent_default(church_world, world):
    """Accept writes the agent default its prompt hint gives (`kinds.
    HINT_AGENT`): a religion acts, a field doesn't; the owner's own
    `agent` wins, and no hint writes none."""

    def preview(name, hint, fields=None):
        return CreatePreview(
            kind="lore",
            prompt=name,
            name=name,
            facts=[PreviewFact(category="general", text=f"{name} is old.")],
            prose={},
            hint=hint,
            fields=fields or {},
        )

    church = accept_preview(world, preview("Church of Amber", "religion"))
    runes = accept_preview(world, preview("Runeweaving", "field"))
    cult = accept_preview(world, preview("Quiet Cult", "religion", {"agent": False}))
    plain = accept_preview(world, preview("Old Saying", None))
    view = world.view()
    assert view.thing(church).fields["agent"] is True
    assert view.thing(runes).fields["agent"] is False
    assert view.thing(cult).fields["agent"] is False
    assert "agent" not in view.thing(plain).fields

    # filling a stub with a hint sets it too
    filled = accept_preview(
        world,
        preview("The White Dawn", "order").model_copy(update={"stub_id": church_world}),
    )
    assert filled == church_world
    assert world.view().thing(church_world).fields["agent"] is True


def test_a_hint_never_overrides_a_stubs_own_agent(church_world, world):
    """Review M2: a stub whose `agent` is set keeps it when it's filled
    with a hint that would default it otherwise."""

    with world.revision(Source.manual(note="agent")) as rev:
        rev.set_field(church_world, "agent", False, None)
    preview = CreatePreview(
        kind="lore",
        prompt="The White Dawn",
        name="The White Dawn",
        facts=[PreviewFact(category="general", text="A faith of the dawn.")],
        prose={},
        hint="religion",
        stub_id=church_world,
    )
    accept_preview(world, preview)
    assert world.view().thing(church_world).fields["agent"] is False


def _summary_of(world, thing_id):
    from talemate.world.entries import summary, summary_fact

    view = world.view()
    fact = summary_fact(view.thing(thing_id))
    return fact, summary(view, thing_id)


async def test_accept_writes_the_replys_summary_as_the_summary_fact(world):
    """Review F22: a create reply's `summary` is written on accept as the
    entry's summary fact (origin `{"summary": True}`), in the category
    a summary takes on its kind; the reads (`entries.summary`) show it."""

    reply = json.dumps(
        {
            "name": "The Pale Order",
            "summary": "An order of scribes who keep the rune census.",
            "facts": [{"category": "general", "text": "They meet at dusk."}],
            "names": [],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "The Pale Order keeps records.")
        preview = await preview_thing(world, "lore", "an order of scribes", {}, client)
    assert preview.summary == "An order of scribes who keep the rune census."
    thing_id = accept_preview(world, preview)
    fact, text = _summary_of(world, thing_id)
    assert fact is not None and fact.origin == {"summary": True}
    assert fact.category == "general"
    assert text == "An order of scribes who keep the rune census."
    others = [
        f for f in world.view().thing(thing_id).facts if f.fact_id != fact.fact_id
    ]
    assert [f.text for f in others] == ["They meet at dusk."]


def test_accept_marks_the_first_fact_the_summary(church_world, world):
    """Review F22: with no summary in the reply, accept marks the first
    own fact written as the summary, for a new entry and a filled stub
    alike; its holder stays in its origin."""

    preview = CreatePreview(
        kind="lore",
        prompt="Runeweaving",
        name="Runeweaving",
        facts=[
            PreviewFact(category="general", text="Runes are cut.", ticked=False),
            PreviewFact(category="general", text="Runeweaving binds runes."),
            PreviewFact(category="general", text="It is taught in Velikoye."),
        ],
        prose={},
    )
    thing_id = accept_preview(world, preview)
    fact, text = _summary_of(world, thing_id)
    assert fact.origin == {"summary": True}
    assert text == "Runeweaving binds runes."

    filled = accept_preview(
        world,
        CreatePreview(
            kind="lore",
            prompt="The White Dawn",
            name="The White Dawn",
            facts=[
                PreviewFact(
                    category="general",
                    text="The faith of the dawn.",
                    held_by=thing_id,
                ),
            ],
            prose={},
            stub_id=church_world,
        ),
    )
    # every fact held: none is marked the summary (ruling F28)
    fact, _text = _summary_of(world, filled)
    assert fact is None
    [only] = world.view().thing(filled).facts
    assert only.origin == {"held_by": thing_id}


async def test_accept_summary_skips_beliefs(world):
    """Ruling F28: with no summary in the reply, the first plain own fact
    is the summary, never a held one -- under the religion hint the reply
    puts its belief first; with every fact held, none is marked."""

    reply = json.dumps(
        {
            "name": "The White Dawn",
            "tag": "faith",
            "facts": [
                {"category": "belief", "text": "The dead return as stars."},
                {"category": "general", "text": "The faith of the dawn."},
            ],
            "names": [],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "The White Dawn is a faith.")
        preview = await preview_thing(
            world, "lore", "a dawn faith", {}, client, hint="religion"
        )
    assert [f.category for f in preview.facts] == ["belief", "general"]
    thing_id = accept_preview(world, preview)
    fact, text = _summary_of(world, thing_id)
    assert fact is not None and fact.origin == {"summary": True}
    assert text == "The faith of the dawn."

    reply = json.dumps(
        {
            "name": "The Pale Rite",
            "facts": [{"category": "belief", "text": "Ash keeps the dead warm."}],
            "names": [],
        }
    )
    async with MockClientContext():
        _queue(reply, "The Pale Rite is a faith.")
        preview = await preview_thing(
            world, "lore", "a rite of ash", {}, client, hint="religion"
        )
    held = accept_preview(world, preview)
    fact, _text = _summary_of(world, held)
    assert fact is None
    [only] = world.view().thing(held).facts
    assert not (only.origin or {}).get("summary")


async def test_a_summary_repeating_an_own_fact_is_written_once(world):
    """Review round 2: a reply summary with the text of one of its own
    facts (whitespace and case aside) writes one fact, marked the
    summary, never a plain copy beside it."""

    reply = json.dumps(
        {
            "name": "The Pale Order",
            "summary": "  they meet AT dusk. ",
            "facts": [
                {"category": "general", "text": "Scribes of the rune census."},
                {"category": "general", "text": "They meet at dusk."},
            ],
            "names": [],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "The Pale Order keeps records.")
        preview = await preview_thing(world, "lore", "an order of scribes", {}, client)
    thing_id = accept_preview(world, preview)
    facts = world.view().thing(thing_id).facts
    assert sorted((f.text, f.origin) for f in facts) == [
        ("Scribes of the rune census.", None),
        ("They meet at dusk.", {"summary": True}),
    ]


# --- Task 10 fix round 1: drafts --------------------------------------------


async def test_accept_files_into_a_new_name(at_1020):
    """An "In" row on a new name ("+ in..." on a draft, typing a name the
    world hasn't): accept makes that stub, with its kind and tag, then
    files the entry in it, in the one revision."""

    from talemate.worldplay.create import PreviewFiling

    world = at_1020
    head = world.head_rev()
    preview = CreatePreview(
        kind="lore",
        prompt="a host",
        name="The Frostwing Host",
        facts=[PreviewFact(category="general", text="It flies at night.")],
        prose={},
        filings=[
            PreviewFiling(
                new_name=NewName(name="The Owl Legion", kind="lore", tag="army"),
                target_name="The Owl Legion",
                role="a wing of",
                ticked=True,
            ),
            PreviewFiling(
                new_name=NewName(name="Unticked Order", kind="lore"),
                target_name="Unticked Order",
            ),
        ],
    )
    thing_id = accept_preview(world, preview)
    assert world.head_rev() == head + 1
    view = world.view(None)
    (legion,) = [t for t in view.things() if view.name_of(t.id) == "The Owl Legion"]
    assert legion.is_stub
    assert legion.kind == "lore"
    assert legion.fields.get("tag") == "army"
    assert [(f.target, f.role) for f in filings_of(view, thing_id)] == [
        (legion.id, "a wing of")
    ]
    assert not [t for t in view.things() if view.name_of(t.id) == "Unticked Order"]


async def test_accept_writes_a_draft_facts_end(at_1020):
    """A draft fact the owner ended ("End this") is written ended."""

    world = at_1020
    preview = CreatePreview(
        kind="lore",
        prompt="a host",
        name="The Frostwing Host",
        facts=[
            PreviewFact(
                category="general",
                text="It guarded the pass.",
                since=WorldDate.of(990),
                until=WorldDate.of(1010),
            )
        ],
        prose={},
    )
    thing_id = accept_preview(world, preview)
    (fact,) = [
        f
        for f in world.view(WorldDate.of(1000)).thing(thing_id).facts
        if "pass" in f.text
    ]
    assert fact.valid_until == WorldDate.of(1010)
    assert not [
        f
        for f in world.view(WorldDate.of(1015)).thing(thing_id).facts
        if "pass" in f.text
    ]


async def test_lowercase_names_link_only_when_the_owner_selected_them(at_1020):
    """Ruling F26: a model-listed new name written in lowercase still makes
    no stub (no capital, no link); the same words the owner selected on
    the draft (`selected_names`) become a stub and link as written."""

    world = at_1020

    def preview(selected):
        return CreatePreview(
            kind="lore",
            prompt="a host",
            name=f"Host {len(selected)}",
            facts=[PreviewFact(category="general", text="It rings the bells.")],
            prose={},
            new_names=[NewName(name="bells", kind="item")],
            selected_names=selected,
        )

    plain = accept_preview(world, preview([]))
    view = world.view(None)
    assert not [t for t in view.things() if view.name_of(t.id) == "bells"]
    assert view.thing(plain).facts[0].text == "It rings the bells."

    picked = accept_preview(world, preview(["bells"]))
    view = world.view(None)
    (bells,) = [t for t in view.things() if view.name_of(t.id) == "bells"]
    assert view.thing(picked).facts[0].text == f"It rings the {ref(bells.id, 'bells')}."


async def test_accept_drops_fields_a_changed_kind_lacks(at_1020):
    """A draft whose kind the owner changed (a character's draft made a
    place) is written as that kind, the fields it lacks (`born`) left
    out with a note."""

    world = at_1020
    notes: list[str] = []
    preview = CreatePreview(
        kind="place",
        prompt="a ferry crossing",
        name="Oskar's Crossing",
        fields={"born": WorldDate.of(990)},
        facts=[PreviewFact(category="general", text="A ferry crossing.")],
        prose={},
    )
    thing_id = accept_preview(world, preview, notes=notes)
    state = world.view(None).thing(thing_id)
    assert state.kind == "place"
    assert "born" not in state.fields
    assert any("born" in note for note in notes)


async def test_new_name_in_both_new_names_and_in_makes_one_stub(at_1020):
    """A name the facts invent (`new_names`) and the owner's "+ in..." on
    the same name make one stub: the facts link it, and the entry is
    filed in it."""

    from talemate.worldplay.create import PreviewFiling

    world = at_1020
    preview = CreatePreview(
        kind="lore",
        prompt="a host",
        name="The Frostwing Host",
        facts=[PreviewFact(category="general", text="It serves The Owl Legion.")],
        prose={},
        new_names=[NewName(name="The Owl Legion", kind="lore")],
        filings=[
            PreviewFiling(
                new_name=NewName(name="The Owl Legion", kind="lore"),
                target_name="The Owl Legion",
                ticked=True,
            )
        ],
    )
    thing_id = accept_preview(world, preview)
    view = world.view(None)
    legions = [t for t in view.things() if view.name_of(t.id) == "The Owl Legion"]
    assert len(legions) == 1
    legion = legions[0].id
    assert [f.target for f in filings_of(view, thing_id)] == [legion]
    assert view.thing(thing_id).facts[0].text == (
        f"It serves {ref(legion, 'The Owl Legion')}."
    )


async def test_in_new_name_the_world_has_files_in_that_entry(at_1020):
    """A "+ in..." new name the world already has (here an entry, not a
    stub) is filed in that entry: no stub of the name is made."""

    from talemate.worldplay.create import PreviewFiling

    world = at_1020
    with world.revision(Source.manual(note="setup")) as rev:
        court = rev.create_thing("lore", {"name": "The Night Court"})
    preview = CreatePreview(
        kind="lore",
        prompt="a host",
        name="The Frostwing Host",
        facts=[PreviewFact(category="general", text="It flies at night.")],
        prose={},
        filings=[
            PreviewFiling(
                new_name=NewName(name="the Night Court", kind="place"),
                target_name="the Night Court",
                role="answers to",
                ticked=True,
            )
        ],
    )
    thing_id = accept_preview(world, preview)
    view = world.view(None)
    assert [(f.target, f.role) for f in filings_of(view, thing_id)] == [
        (court, "answers to")
    ]
    assert not [t for t in view.things() if t.is_stub]
    assert view.thing(court).kind == "lore"
