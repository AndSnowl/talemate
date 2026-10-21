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
from talemate.world.store import Source, World
from talemate.worldplay import prose_gen
from talemate.worldplay.characters import character_from_world
from talemate.worldplay.create import (
    CreatePreview,
    PreviewFact,
    accept_preview,
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
