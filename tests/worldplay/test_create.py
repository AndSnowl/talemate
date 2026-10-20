"""Create a world thing from a prompt: preview (no writes), then accept."""

import json

import pytest

from talemate.world.calendar import Calendar, Era
from talemate.world.dates import Precision, WorldDate
from talemate.world.store import Source
from talemate.worldplay import prose_gen
from talemate.worldplay.characters import character_from_world
from talemate.worldplay.create import (
    CreatePreview,
    PreviewFact,
    accept_preview,
    parse_create_reply,
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
