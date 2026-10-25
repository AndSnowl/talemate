"""Scene setup: name matching in the scene prompt, planning a scene from a
storyline prompt plus the world, starting it, and continuing in a new
scene."""

import json
from pathlib import Path

import pytest

import talemate.instance as instance
from talemate.config import Config, get_config
from talemate.config.schema import RecentScenes
from talemate.context import ActiveScene
from talemate.load import load_scene
from talemate.tale_mate import Scene
from talemate.world.dates import WorldDate
from talemate.world.index import WorldIndex
from talemate.world.scenes import MessageRecord
from talemate.world.store import Source
from talemate.worldplay.context import world_context_block
from talemate.world.filing import filings_of
from talemate.worldplay.create import FileIntoRow, current_date
from talemate.worldplay.persistence import (
    close_world_scene,
    save_world_scene,
    world_target,
)
from talemate.worldplay.setup import (
    LocalThing,
    SceneSetup,
    SetupRef,
    continue_setup,
    match_names,
    plan_scene,
    start_scene,
    stubs_to_fill,
)

from conftest import (
    MockClient,
    MockClientContext,
    MockMemoryAgent,
    MockScene,
    bootstrap_scene,
    client_responses,
)
from world.embedding import TrigramEmbeddingFunction, requires_chromadb

START = WorldDate.of(313, 6, 1)


def _queue(*responses: str) -> None:
    for response in responses:
        client_responses.get().append(response)


def _river_world(world):
    """Maren Vos and Maren Holt, Tobin, the Drowned Stag and the River
    Treaty. Returns their ids by short name."""

    with world.revision(Source.manual(note="setup")) as rev:
        vos = rev.create_thing(
            "character",
            fields={"name": "Maren Vos", "born": WorldDate.of(290)},
            valid_from=WorldDate.of(290),
        )
        rev.add_fact(vos, "appearance", "A heron tattoo on her wrist.")
        holt = rev.create_thing("character", fields={"name": "Maren Holt"})
        tobin = rev.create_thing("character", fields={"name": "Tobin"})
        stag = rev.create_thing("place", fields={"name": "The Drowned Stag"})
        rev.add_fact(stag, "description", "A tavern with water on its floor.")
        treaty = rev.create_thing("lore", fields={"name": "The River Treaty"})
        rev.add_fact(treaty, "general", "River tolls are paid at the pillars.")
    return {"vos": vos, "holt": holt, "tobin": tobin, "stag": stag, "treaty": treaty}


DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "worldplay"


def _read_data(name: str) -> str:
    return (DATA_DIR / name).read_text()


SETUP_REPLY = json.dumps(
    {
        "player": "Maren Vos",
        "characters": [
            {"name": "Tobin", "world": True},
            {
                "name": "Daveth Brin",
                "world": False,
                "facts": ["A young smuggler with a bad knee."],
            },
        ],
        "place": {"name": "The Drowned Stag", "world": True},
        "extras": [{"name": "Warden Patrol", "facts": ["Three wardens on rounds."]}],
        "goal": "Settle the toll dispute before the wardens arrive.",
        "intro": "Water laps at the tavern's floorboards as Tobin waits.",
    }
)


# --- name matching ------------------------------------------------------------


def test_match_names_longest_and_possessive(world):
    """Review Focus 3: overlapping names match once, longest first, any
    case, possessive allowed."""

    ids = _river_world(world)

    matches = match_names(world, "maren's boat", None)
    assert len(matches) == 1
    assert (matches[0].start, matches[0].end, matches[0].text) == (0, 5, "maren")
    assert {c.id for c in matches[0].candidates} == {ids["vos"], ids["holt"]}

    matches = match_names(world, "Maren Vos left", None)
    assert len(matches) == 1
    assert matches[0].text == "Maren Vos"
    assert (matches[0].start, matches[0].end) == (0, 9)
    assert matches[0].candidates[0].id == ids["vos"]
    assert matches[0].candidates[0].name == "Maren Vos"
    assert matches[0].candidates[0].kind == "character"


def test_match_names_whole_words_only(world):
    ids = _river_world(world)

    matches = match_names(
        world, "Marenna met TOBIN at the drowned stag's door", WorldDate.of(313)
    )

    assert [m.text for m in matches] == ["TOBIN", "the drowned stag"]
    assert matches[0].candidates[0].id == ids["tobin"]
    assert matches[-1].candidates[0].id == ids["stag"]


def test_match_names_uses_names_at_the_date(world):
    with world.revision(Source.manual(note="setup")) as rev:
        thing = rev.create_thing("character", fields={"name": "Oskar"})
        rev.set_field(thing, "name", "Oskar the Grey", WorldDate.of(317))

    assert match_names(world, "the grey one", WorldDate.of(313)) == []
    assert [m.text for m in match_names(world, "Oskar the Grey", None)] == [
        "Oskar the Grey"
    ]


# --- planning -----------------------------------------------------------------


@requires_chromadb
async def test_plan_scene_uses_picks_and_index(world):
    ids = _river_world(world)
    prompt = "Maren argues with Tobin about the river tolls"

    client = MockClient("test")
    async with MockClientContext():
        _queue(SETUP_REPLY)
        setup = await plan_scene(
            world,
            prompt,
            {"Maren": ids["vos"]},
            None,
            START,
            client,
            embedding_function=TrigramEmbeddingFunction(),
        )

    assert setup.player == SetupRef(thing_id=ids["vos"])
    assert setup.characters == [
        SetupRef(thing_id=ids["tobin"]),
        SetupRef(
            local=LocalThing(
                name="Daveth Brin", facts=["A young smuggler with a bad knee."]
            )
        ),
    ]
    assert setup.place == SetupRef(thing_id=ids["stag"])
    assert setup.extras == [
        LocalThing(name="Warden Patrol", facts=["Three wardens on rounds."])
    ]
    assert setup.start == START
    assert setup.goal == "Settle the toll dispute before the wardens arrive."
    assert setup.intro.startswith("Water laps")
    # the lore came from the index, not the picks
    assert setup.pulled_in == [ids["treaty"]]
    assert setup.invented == ["Daveth Brin", "Warden Patrol"]
    assert setup.prompt == prompt

    sent = str(client.prompt_history[0]["prompt"])
    assert prompt in sent
    # the picked thing, rendered at the date, and the index's lore
    assert "Maren Vos" in sent
    assert "A heron tattoo on her wrist." in sent
    assert "River tolls are paid at the pillars." in sent

    # the index was brought up to date before the query
    index = WorldIndex(world, embedding_function=TrigramEmbeddingFunction())
    assert index.built_rev() == world.head_rev()


@requires_chromadb
async def test_plan_scene_finds_a_setup_wrapped_in_an_outer_object(world):
    """Review-round fix: `create.json_objects` jumps past each top-level
    object rather than descending into it (so a setup reply, itself one
    top-level object, is found whole), but that means a reply that wraps
    the setup in an outer key -- e.g. {"scene": {"player": ..., "intro":
    ...}} -- no longer turns up as a nested top-level object the old
    parser used to find. `_reply_object` must look inside dict values
    when no top-level object has a setup key."""

    ids = _river_world(world)
    prompt = "Maren argues with Tobin about the river tolls"
    wrapped_reply = json.dumps({"scene": json.loads(SETUP_REPLY)})

    client = MockClient("test")
    async with MockClientContext():
        _queue(wrapped_reply)
        setup = await plan_scene(
            world,
            prompt,
            {"Maren": ids["vos"]},
            None,
            START,
            client,
            embedding_function=TrigramEmbeddingFunction(),
        )

    assert setup.player == SetupRef(thing_id=ids["vos"])
    assert setup.goal == "Settle the toll dispute before the wardens arrive."


@requires_chromadb
async def test_plan_scene_player_from_picker(world):
    ids = _river_world(world)

    client = MockClient("test")
    async with MockClientContext():
        _queue(SETUP_REPLY)
        setup = await plan_scene(
            world,
            "Maren argues with Tobin",
            {},
            ids["tobin"],
            START,
            client,
            embedding_function=TrigramEmbeddingFunction(),
        )

    # the owner's pick wins over the model's; the model's player is still
    # in the scene, as a character
    assert setup.player == SetupRef(thing_id=ids["tobin"])
    assert SetupRef(thing_id=ids["vos"]) in setup.characters
    assert SetupRef(thing_id=ids["tobin"]) not in setup.characters
    sent = str(client.prompt_history[0]["prompt"])
    assert "The player plays Tobin" in sent


async def test_plan_scene_start_defaults_to_now_without_an_index(world):
    """With no start, the scene starts at the world's current date. With no
    memory database (no embedding function), the plan goes ahead from the
    picks alone."""

    ids = _river_world(world)
    world.set_present(WorldDate.of(1000))
    scenes = world.scenes()
    earlier = scenes.create("Earlier", WorldDate.of(1001))
    scenes.replace_messages(
        earlier,
        [MessageRecord(id="m1", seq=0, kind="time", data={}, elapsed="P2D")],
    )

    client = MockClient("test")
    async with MockClientContext():
        _queue(SETUP_REPLY)
        setup = await plan_scene(
            world, "Maren and Tobin", {"Maren": ids["vos"]}, None, None, client
        )

    assert setup.start == current_date(world) == WorldDate.of(1001).plus("P2D")
    assert setup.player == SetupRef(thing_id=ids["vos"])
    assert setup.pulled_in == []


async def test_plan_scene_pick_beats_an_exact_name(world):
    """The owner's pick always wins: the model's "Maren" is the Maren the
    owner picked, even though another thing is named exactly "Maren"."""

    ids = _river_world(world)
    with world.revision(Source.manual(note="setup")) as rev:
        rev.create_thing("character", fields={"name": "Maren"})

    setup = await plan_scene(
        world,
        "Maren goes fishing",
        {"Maren": ids["holt"]},
        None,
        START,
        None,
        reply={"player": "Maren", "characters": [], "intro": "Dawn."},
    )

    assert setup.player == SetupRef(thing_id=ids["holt"])
    assert setup.invented == []


async def test_plan_scene_treats_new_names_as_invented(world):
    """A name the owner treats as new is never resolved to a world thing,
    even when exactly one thing has that (first) name."""

    with world.revision(Source.manual(note="setup")) as rev:
        vos = rev.create_thing("character", fields={"name": "Maren Vos"})
        tobin = rev.create_thing("character", fields={"name": "Tobin"})

    reply = {
        "player": "Maren",
        "characters": [
            {"name": "Tobin", "facts": ["A stranger off the barge."]},
            {"name": "Maren Vos"},
        ],
        "intro": "Dawn.",
    }
    setup = await plan_scene(
        world,
        "Maren meets Tobin",
        {},
        None,
        START,
        None,
        reply=reply,
        new_names=["maren", "Tobin"],
    )

    assert setup.player == SetupRef(local=LocalThing(name="Maren"))
    # "Maren" is new, so the model's "Maren Vos" is not the world's either
    assert setup.characters == [
        SetupRef(local=LocalThing(name="Tobin", facts=["A stranger off the barge."])),
        SetupRef(local=LocalThing(name="Maren Vos")),
    ]
    assert setup.invented == ["Maren", "Tobin", "Maren Vos"]

    # without new names the same reply resolves to the world things
    setup = await plan_scene(
        world, "Maren meets Tobin", {}, None, START, None, reply=reply
    )
    assert setup.player == SetupRef(thing_id=vos)
    assert SetupRef(thing_id=tobin) in setup.characters


async def test_plan_scene_accepts_raw_line_breaks_in_reply(world):
    """Regression: a model reply whose "intro" has a real paragraph break
    (a raw newline, not "\\n") instead of escaping it is still a valid
    setup -- the owner's acceptance run hit this with the exact reply in
    tests/data/worldplay/accept-fix-4-reply.txt."""

    reply_text = _read_data("accept-fix-4-reply.txt")

    client = MockClient("test")
    async with MockClientContext():
        _queue(reply_text)
        setup = await plan_scene(
            world,
            "Vasha the mail courier faces the Colonel",
            {},
            None,
            START,
            client,
        )

    assert setup.player == SetupRef(local=LocalThing(name="Vasha"))
    assert {c.local.name for c in setup.characters} == {
        "Colonel Maren Duskhollow",
        "Postmaster Brenn Ashwick",
    }
    duskhollow = next(
        c for c in setup.characters if c.local.name == "Colonel Maren Duskhollow"
    )
    assert duskhollow.local.facts and "crimson uniform" in duskhollow.local.facts[0]
    ashwick = next(
        c for c in setup.characters if c.local.name == "Postmaster Brenn Ashwick"
    )
    assert ashwick.local.facts and "Kalmara Postal Hall" in ashwick.local.facts[0]

    # the test world doesn't have this place, so it's invented even though
    # the model flagged it as a world thing
    assert setup.place is not None
    assert setup.place.thing_id is None
    assert setup.place.local.name == "Kalmara Postal Hall"
    assert "sorting floor" in setup.place.local.facts[0]

    assert setup.goal.startswith("Vasha must decide")
    assert setup.intro.startswith("The sorting room hums")
    # the paragraph break survived
    assert "\n\n" in setup.intro
    assert setup.intro.endswith("and stays there.")


async def test_plan_scene_rejects_unknown_pick(world):
    _river_world(world)
    with pytest.raises(KeyError):
        await plan_scene(
            world, "Maren", {"Maren": "no-such-thing"}, None, START, MockClient("t")
        )


# --- heritage -----------------------------------------------------------------


async def test_setup_invented_character_heritage(world, heritage_world):
    """Task 7: an invented character's "heritage" names Snowy; the local
    thing keeps its id, and the started scene's local character description
    carries Snowy's effective physical/variation facts (here, the plumage
    fact), with its instinct facts as the personality."""

    reply = {
        "player": "Maren",
        "characters": [
            {
                "name": "Rill",
                "world": False,
                "facts": ["A quiet trader."],
                "heritage": "snowy",
            }
        ],
        "intro": "Dawn breaks over the river.",
    }
    setup = await plan_scene(
        world, "Maren meets Rill", {}, None, START, None, reply=reply
    )

    rill = next(c for c in setup.characters if c.local is not None)
    assert rill.local.name == "Rill"
    assert rill.local.heritage_id == heritage_world.snowy

    async with MockClientContext():
        scene_id = await start_scene(world, setup, MockClient("test"))

    local = {
        thing["data"]["name"]: thing for thing in world.scenes().local_things(scene_id)
    }
    rill_data = local["Rill"]["data"]
    assert "A quiet trader." in rill_data["description"]
    # Snowy's own facts, plus what it inherits from Owl-folk
    assert "White plumage." in rill_data["description"]
    assert "Yellow eyes." in rill_data["description"]
    assert "Wings in place of arms." in rill_data["description"]
    assert rill_data["base_attributes"]["personality"] == "Hunts at dusk."
    assert rill_data["world_heritage_id"] == heritage_world.snowy


async def test_setup_unknown_heritage_ignored(world, heritage_world):
    reply = {
        "player": "Maren",
        "characters": [
            {"name": "Rill", "facts": ["A quiet trader."], "heritage": "Dragonkin"}
        ],
        "intro": "Dawn.",
    }
    setup = await plan_scene(
        world, "Maren meets Rill", {}, None, START, None, reply=reply
    )

    rill = next(c for c in setup.characters if c.local is not None)
    assert rill.local.heritage_id is None


async def test_setup_prompt_lists_heritages(world, heritage_world):
    """The setup prompt's `heritages` var names the species and races, each
    race labelled with its species."""

    client = MockClient("test")
    async with MockClientContext():
        _queue(json.dumps({"player": "Anyone", "characters": [], "intro": "Dawn."}))
        await plan_scene(world, "Anyone arrives", {}, None, START, client)

    sent = str(client.prompt_history[0]["prompt"])
    assert "Owl-folk" in sent
    assert "Snowy (Owl-folk)" in sent


async def test_setup_prompt_leaves_stub_heritages_out(world, heritage_world):
    """A heritage stub, ignored or not, has nothing to inherit: it isn't
    offered to the setup model."""

    with world.revision(Source.manual(note="stubs")) as rev:
        rev.create_thing(
            "species", fields={"name": "Fox-kin", "stub": {"ignored": False}}
        )
        rev.create_thing(
            "race", fields={"name": "Ashen Folk", "stub": {"ignored": True}}
        )

    client = MockClient("test")
    async with MockClientContext():
        _queue(json.dumps({"player": "Anyone", "characters": [], "intro": "Dawn."}))
        await plan_scene(world, "Anyone arrives", {}, None, START, client)

    sent = str(client.prompt_history[0]["prompt"])
    assert "Snowy (Owl-folk)" in sent
    assert "Fox-kin" not in sent
    assert "Ashen Folk" not in sent


async def test_setup_heritage_annotated_name_matches(world, heritage_world):
    """Fix round 1, finding 2: the prompt shows a race as "Snowy
    (Owl-folk)", and a local model tends to echo exactly what it's shown,
    so that annotated form must resolve too, not just the bare name."""

    reply = {
        "player": "Maren",
        "characters": [
            {
                "name": "Rill",
                "facts": ["A quiet trader."],
                "heritage": "Snowy (Owl-folk)",
            }
        ],
        "intro": "Dawn.",
    }
    setup = await plan_scene(
        world, "Maren meets Rill", {}, None, START, None, reply=reply
    )

    rill = next(c for c in setup.characters if c.local is not None)
    assert rill.local.heritage_id == heritage_world.snowy


async def test_continue_setup_carries_heritage(world, heritage_world):
    """Fix round 1, finding 1: a heritage-bearing invented character's
    `world_heritage_id` and inherited personality must survive a
    `continue_setup` -> `start_scene` round, and the inherited facts must
    appear exactly once in the new description (not duplicated on top of
    what the first `start_scene` already appended)."""

    reply = {
        "player": "Maren",
        "characters": [
            {
                "name": "Rill",
                "facts": ["A quiet trader."],
                "heritage": "snowy",
            }
        ],
        "intro": "Dawn breaks over the river.",
    }
    setup = await plan_scene(
        world, "Maren meets Rill", {}, None, START, None, reply=reply
    )
    async with MockClientContext():
        old_id = await start_scene(world, setup, MockClient("test"))

    continued = await continue_setup(
        world,
        old_id,
        "next",
        None,
        reply={"player": "Maren", "characters": [], "goal": "g", "intro": "i"},
    )
    async with MockClientContext():
        new_id = await start_scene(world, continued, MockClient("test"))

    local = {
        thing["data"]["name"]: thing for thing in world.scenes().local_things(new_id)
    }
    rill_data = local["Rill"]["data"]
    assert rill_data["world_heritage_id"] == heritage_world.snowy
    assert rill_data["base_attributes"]["personality"] == "Hunts at dusk."
    assert "A quiet trader." in rill_data["description"]
    assert rill_data["description"].count("White plumage.") == 1
    assert rill_data["description"].count("Yellow eyes.") == 1
    assert rill_data["description"].count("Wings in place of arms.") == 1


async def test_continue_setup_carries_heritage_through_a_save(
    world, heritage_world, loadable
):
    """Fix round 2: the normal path is start -> play (which autosaves via
    `save_world_scene`) -> continue, not start -> continue straight off.
    `save_world_scene`'s `_character_entries` re-dumps the scene-local
    character from the live, loaded `Character`, which must still carry
    its own facts separately from the heritage's for the fix to survive
    that round-trip -- not just the raw local-thing data `start_scene`
    first wrote, which `test_continue_setup_carries_heritage` checks."""

    reply = {
        "player": "Maren",
        "characters": [
            {
                "name": "Rill",
                "facts": ["A quiet trader."],
                "heritage": "snowy",
            }
        ],
        "intro": "Dawn breaks over the river.",
    }
    setup = await plan_scene(
        world, "Maren meets Rill", {}, None, START, None, reply=reply
    )
    async with MockClientContext():
        old_id = await start_scene(world, setup, MockClient("test"))

    scene = MockScene()
    bootstrap_scene(scene)
    loaded = await load_scene(scene, world_target(str(world.path), old_id))
    try:
        save_world_scene(loaded)
    finally:
        close_world_scene(loaded)

    continued = await continue_setup(
        world,
        old_id,
        "next",
        None,
        reply={"player": "Maren", "characters": [], "goal": "g", "intro": "i"},
    )
    async with MockClientContext():
        new_id = await start_scene(world, continued, MockClient("test"))

    local = {
        thing["data"]["name"]: thing for thing in world.scenes().local_things(new_id)
    }
    rill_data = local["Rill"]["data"]
    assert rill_data["world_heritage_id"] == heritage_world.snowy
    assert rill_data["base_attributes"]["personality"] == "Hunts at dusk."
    assert "A quiet trader." in rill_data["description"]
    assert rill_data["description"].count("White plumage.") == 1
    assert rill_data["description"].count("Yellow eyes.") == 1
    assert rill_data["description"].count("Wings in place of arms.") == 1


# --- starting -----------------------------------------------------------------


async def _noop(self, *args, **kwargs):
    pass


@pytest.fixture
def loadable(monkeypatch):
    """What loading a world scene needs from a test: no memory database,
    an empty recent-scenes list and no config broadcast (as in
    test_persistence.py)."""

    monkeypatch.setattr(MockMemoryAgent, "set_db", _noop)
    monkeypatch.setattr(MockMemoryAgent, "_get_document", lambda self, id: {})
    monkeypatch.setattr(Scene, "commit_to_memory", _noop)
    monkeypatch.setattr(Config, "set_dirty", _noop)
    monkeypatch.setattr(get_config(), "recent_scenes", RecentScenes(scenes=[]))


def _setup(ids, **overrides) -> SceneSetup:
    values = dict(
        player=SetupRef(thing_id=ids["vos"]),
        characters=[
            SetupRef(thing_id=ids["tobin"]),
            SetupRef(local=LocalThing(name="Daveth Brin", facts=["A smuggler."])),
        ],
        place=SetupRef(thing_id=ids["stag"]),
        extras=[LocalThing(name="Warden Patrol", facts=["Three wardens."])],
        start=START,
        goal="Settle the toll dispute.",
        intro="Water laps at the floorboards.",
        pulled_in=[ids["treaty"]],
        invented=["Daveth Brin", "Warden Patrol"],
        prompt="Maren argues with Tobin about the tolls",
    )
    values.update(overrides)
    return SceneSetup(**values)


async def test_start_scene_writes_scene_and_intro(world, loadable):
    ids = _river_world(world)

    client = MockClient("test")
    async with MockClientContext():
        # only Maren Vos has facts to describe: one prose call
        _queue("Maren Vos is marked by a heron tattoo.")
        scene_id = await start_scene(world, _setup(ids), client)

    assert len(client.prompt_history) == 1
    cache = world.prose()
    assert cache.get(ids["vos"], "description", START).text == (
        "Maren Vos is marked by a heron tattoo."
    )
    assert cache.stale(ids["vos"], "description", START) is False

    store = world.scenes()
    record = store.get(scene_id)
    assert record.start == START
    assert record.goal == "Settle the toll dispute."
    assert record.premise == "Maren argues with Tobin about the tolls"
    assert record.player_thing_id == ids["vos"]
    assert record.continued_from is None
    assert record.state["intro"] == "Water laps at the floorboards."
    assert record.state["place_thing_id"] == ids["stag"]
    assert record.state["pulled_in"] == [ids["treaty"]]

    local = {thing["data"]["name"]: thing for thing in store.local_things(scene_id)}
    assert local["Daveth Brin"]["kind"] == "character"
    assert local["Daveth Brin"]["data"]["description"] == "A smuggler."
    assert local["Warden Patrol"]["kind"] == "extra"
    assert local["Warden Patrol"]["data"]["facts"] == ["Three wardens."]

    entries = record.state["characters"]
    assert [e.get("thing_id") for e in entries] == [ids["vos"], ids["tobin"], None]
    assert entries[2]["local_id"] == local["Daveth Brin"]["local_id"]
    assert all(e["active"] for e in entries)

    # the scene loads, with the intro as its opening narration
    fresh = MockScene()
    bootstrap_scene(fresh)
    loaded = await load_scene(fresh, world_target(str(world.path), scene_id))
    try:
        assert loaded.intro == "Water laps at the floorboards."
        assert loaded.get_player_character().name == "Maren Vos"
        assert set(loaded.active_characters) == {"Maren Vos", "Tobin", "Daveth Brin"}
        assert loaded.world_context.record.goal == "Settle the toll dispute."
    finally:
        close_world_scene(loaded)


async def test_start_scene_local_player_and_place(world):
    ids = _river_world(world)
    setup = _setup(
        ids,
        player=SetupRef(local=LocalThing(name="Ilse", facts=["A ferry hand."])),
        place=SetupRef(local=LocalThing(name="The Weir", facts=["A broken dam."])),
        extras=[],
    )

    async with MockClientContext():
        scene_id = await start_scene(world, setup, MockClient("test"))

    store = world.scenes()
    record = store.get(scene_id)
    assert record.player_thing_id is None
    assert "place_thing_id" not in record.state
    local = {thing["data"]["name"]: thing for thing in store.local_things(scene_id)}
    assert local["Ilse"]["data"]["is_player"] is True
    assert local["The Weir"]["kind"] == "place"
    assert record.state["place_local_id"] == local["The Weir"]["local_id"]


async def test_invented_place_reaches_the_world_block(world):
    """An invented place (a dungeon the prompt made up) is in the scene's
    "World" instruction, with its name and facts."""

    ids = _river_world(world)
    setup = _setup(
        ids,
        place=SetupRef(
            local=LocalThing(
                name="The Sunken Vault", facts=["A flooded dungeon under the weir."]
            )
        ),
    )
    async with MockClientContext():
        _queue("Maren Vos has a heron tattoo.")
        scene_id = await start_scene(world, setup, MockClient("test"))

    record = world.scenes().get(scene_id)
    block = world_context_block(world, record, START)

    assert "The Sunken Vault" in block
    assert "A flooded dungeon under the weir." in block
    assert "Settle the toll dispute." in block


# --- continuing -----------------------------------------------------------------


CONTINUE_REPLY = json.dumps(
    {
        "player": "Maren Vos",
        "characters": [{"name": "Daveth Brin", "world": False}],
        "place": {"name": "The Drowned Stag", "world": True},
        "goal": "Find who tipped off the wardens.",
        "intro": "Morning light finds the tavern quiet.",
    }
)


async def test_continue_setup_carries_date_place_people(world):
    ids = _river_world(world)
    async with MockClientContext():
        _queue("Maren Vos has a heron tattoo.")
        old_id = await start_scene(world, _setup(ids), MockClient("test"))

    store = world.scenes()
    record = store.get(old_id)
    # Tobin left during the scene
    state = dict(record.state)
    state["characters"] = [
        {**entry, "active": entry.get("thing_id") != ids["tobin"]}
        for entry in state["characters"]
    ]
    store.update(old_id, state=state)
    store.replace_messages(
        old_id,
        [
            MessageRecord(
                id="m1",
                seq=0,
                kind="character",
                data={"message": "Tobin: The tolls are robbery.", "typ": "character"},
            ),
            MessageRecord(
                id="m2", seq=1, kind="time", data={"ts": "PT6H"}, elapsed="PT6H"
            ),
            MessageRecord(
                id="m3",
                seq=2,
                kind="narrator",
                data={"message": "Tobin storms out into the rain."},
                elapsed="PT6H",
            ),
        ],
    )

    scene = MockScene()
    bootstrap_scene(scene)
    client = MockClient("test")
    with ActiveScene(scene):
        async with MockClientContext():
            _queue('Tobin argued over the tolls and stormed out."', CONTINUE_REPLY)
            setup = await continue_setup(
                world, old_id, "Find who tipped off the wardens", client
            )

    assert setup.start == START.plus("PT6H")
    assert setup.place == SetupRef(thing_id=ids["stag"])
    assert setup.player == SetupRef(thing_id=ids["vos"])
    # the active people only: Tobin left
    assert setup.characters == [
        SetupRef(local=LocalThing(name="Daveth Brin", facts=["A smuggler."]))
    ]
    assert setup.extras == [LocalThing(name="Warden Patrol", facts=["Three wardens."])]
    assert setup.pulled_in == [ids["treaty"]]
    assert setup.continued_from == old_id
    assert "stormed out" in setup.summary
    assert setup.goal == "Find who tipped off the wardens."
    assert setup.intro == "Morning light finds the tavern quiet."

    # the summary was made from the history, and fed to the setup prompt
    summarized = str(instance.get_agent("summarizer").client.prompt_history[-1])
    assert "Tobin: The tolls are robbery." in summarized
    assert "Tobin storms out into the rain." in summarized
    sent = str(client.prompt_history[-1]["prompt"])
    assert "stormed out" in sent
    assert "Find who tipped off the wardens" in sent

    async with MockClientContext():
        new_id = await start_scene(world, setup, MockClient("test"))
    new = store.get(new_id)
    assert new.continued_from == old_id
    assert new.start == START.plus("PT6H")
    assert "stormed out" in new.premise


async def test_continue_setup_drops_carried_thing_that_was_deleted(world):
    """Review-round fix: a thing carried over from the previous scene
    (player, character or place) may since have been deleted from the
    world. `_carried` must drop it, the same way `pulled_in` already is
    filtered -- otherwise `continue_setup` hands back a dangling
    `SetupRef` and `start_scene` blows up on it (`ensure_prose` ->
    `KeyError: no such thing`)."""

    ids = _river_world(world)
    async with MockClientContext():
        _queue("Maren Vos has a heron tattoo.")
        old_id = await start_scene(world, _setup(ids), MockClient("test"))

    with world.revision(Source.manual(note="deleted Tobin")) as rev:
        rev.remove_thing(ids["tobin"])

    reply = {"player": "Maren Vos", "characters": [], "goal": "g", "intro": "i"}
    setup = await continue_setup(world, old_id, "next", None, reply=reply)

    assert all(ref.thing_id != ids["tobin"] for ref in setup.characters)

    # starting the continued scene must not choke on the deleted carry-over
    new_id = await start_scene(world, setup, None)
    assert new_id


# --- stubs ----------------------------------------------------------------------


def _stubs(world, *, ignored: bool = False):
    """Stubs a scene can use: Aldric (a character), Frosthollow (a place),
    the Order of the Heron (lore) and the Saltfolk (a race, which has no
    species to fill it from). Returns their ids by short name."""

    marker = {"ignored": ignored}
    with world.revision(Source.manual(note="stubs")) as rev:
        aldric = rev.create_thing(
            "character", fields={"name": "Aldric", "stub": dict(marker)}
        )
        frost = rev.create_thing(
            "place", fields={"name": "Frosthollow", "stub": dict(marker)}
        )
        order = rev.create_thing(
            "lore", fields={"name": "Order of the Heron", "stub": dict(marker)}
        )
        salt = rev.create_thing(
            "race", fields={"name": "Saltfolk", "stub": dict(marker)}
        )
    return {"aldric": aldric, "frost": frost, "order": order, "salt": salt}


STUB_SETUP_REPLY = {
    "player": "Maren Vos",
    "characters": [{"name": "Aldric", "world": True}, {"name": "Tobin"}],
    "place": {"name": "Frosthollow", "world": True},
    "goal": "Find the heron order's ledger.",
    "intro": "Snow drifts against the door.",
}


def _created(name: str, category: str, text: str) -> str:
    return json.dumps(
        {"name": name, "facts": [{"category": category, "text": text}], "names": []}
    )


def _queue_stub_previews() -> None:
    """The model's answers for previewing Aldric, Frosthollow and the
    Order, in that order: each create reply, then its prose."""

    _queue(
        _created("Aldric", "background", "A ferryman who keeps the heron ledger."),
        # no personality facts: no personality prose
        "Aldric is a weathered ferryman.",
        _created("Frosthollow", "description", "A snowbound village on the weir."),
        "Frosthollow sits under snow.",
        _created("Order of the Heron", "general", "Keepers of the river ledgers."),
        "The Order keeps the ledgers.",
    )


async def _plan_with_stubs(world, ids, stubs, client):
    return await plan_scene(
        world,
        "Maren meets Aldric in Frosthollow about the Order of the Heron and the Saltfolk",
        {
            "Aldric": stubs["aldric"],
            "Order of the Heron": stubs["order"],
            "Saltfolk": stubs["salt"],
        },
        ids["vos"],
        START,
        client,
        reply=STUB_SETUP_REPLY,
    )


async def test_plan_scene_previews_named_stub(world):
    """Each stub the setup uses -- a character (picked and named by the
    model), the place and picked lore -- gets one preview, made from its
    own kind and name; a race stub is left alone; nothing is written."""

    ids = _river_world(world)
    stubs = _stubs(world)
    head = world.head_rev()

    client = MockClient("test")
    async with MockClientContext():
        _queue_stub_previews()
        setup = await _plan_with_stubs(world, ids, stubs, client)

    assert SetupRef(thing_id=stubs["aldric"]) in setup.characters
    assert setup.place == SetupRef(thing_id=stubs["frost"])
    assert set(setup.pulled_in) == {stubs["order"], stubs["salt"]}

    previews = {p.stub_id: p for p in setup.stub_previews}
    # one each, Aldric too, though he was both picked and named
    assert [p.stub_id for p in setup.stub_previews] == [
        stubs["aldric"],
        stubs["frost"],
        stubs["order"],
    ]
    assert previews[stubs["aldric"]].kind == "character"
    assert previews[stubs["aldric"]].name == "Aldric"
    assert previews[stubs["frost"]].facts[0].text == (
        "A snowbound village on the weir."
    )
    assert previews[stubs["order"]].kind == "lore"
    # the race stub has no species to fill it from: no preview, no failure
    assert stubs["salt"] not in previews

    # planning wrote nothing: the stubs are still stubs
    assert world.head_rev() == head
    view = world.view(None)
    assert all(view.thing(thing_id).is_stub for thing_id in stubs.values())


async def test_start_scene_fills_stub_and_keeps_id(world):
    ids = _river_world(world)
    stubs = _stubs(world)
    async with MockClientContext():
        _queue_stub_previews()
        setup = await _plan_with_stubs(world, ids, stubs, MockClient("test"))

    # the setup goes over the wire and back on Start
    setup = SceneSetup.model_validate(json.loads(setup.model_dump_json()))
    async with MockClientContext():
        scene_id = await start_scene(world, setup, MockClient("test"))

    view = world.view(None)
    for short in ("aldric", "frost", "order"):
        state = view.thing(stubs[short])
        assert not state.is_stub, short
        assert state.facts, short
    assert view.thing(stubs["frost"]).facts[0].text == (
        "A snowbound village on the weir."
    )
    # the race stub stays as it was
    assert view.thing(stubs["salt"]).is_stub

    record = world.scenes().get(scene_id)
    assert record.state["place_thing_id"] == stubs["frost"]
    assert stubs["aldric"] in [e.get("thing_id") for e in record.state["characters"]]
    block = world_context_block(world, record, START)
    assert "A snowbound village on the weir." in block
    assert "Keepers of the river ledgers." in block


async def test_cancelled_setup_leaves_stub(world):
    ids = _river_world(world)
    stubs = _stubs(world)
    head = world.head_rev()
    async with MockClientContext():
        _queue_stub_previews()
        setup = await _plan_with_stubs(world, ids, stubs, MockClient("test"))
    assert setup.stub_previews

    # the owner cancels: start_scene is never called
    assert world.head_rev() == head
    view = world.view(None)
    for thing_id in stubs.values():
        state = view.thing(thing_id)
        assert state.is_stub
        assert state.facts == []
    assert world.scenes().list() == []


async def test_ignored_stub_revived_by_setup(world):
    ids = _river_world(world)
    stubs = _stubs(world, ignored=True)
    async with MockClientContext():
        _queue_stub_previews()
        setup = await _plan_with_stubs(world, ids, stubs, MockClient("test"))
    # ignored stubs are previewed too
    assert {p.stub_id for p in setup.stub_previews} == {
        stubs["aldric"],
        stubs["frost"],
        stubs["order"],
    }

    async with MockClientContext():
        await start_scene(world, setup, MockClient("test"))

    view = world.view(None)
    state = view.thing(stubs["aldric"])
    assert not state.is_stub
    assert not state.stub_ignored
    assert view.thing(stubs["salt"]).stub_ignored


async def test_plan_scene_without_client_leaves_stubs(world):
    """The browser tests' fixed setup has no client: no stub previews, and
    starting leaves the stubs as stubs."""

    ids = _river_world(world)
    stubs = _stubs(world)
    setup = await _plan_with_stubs(world, ids, stubs, None)
    assert setup.stub_previews == []

    await start_scene(world, setup, None)
    view = world.view(None)
    assert all(view.thing(thing_id).is_stub for thing_id in stubs.values())


async def test_start_scene_refuses_a_stub_deleted_since_planning(world):
    """A stub deleted after planning refuses the start before anything is
    written; one filled out by hand in the meantime is left as it is."""

    ids = _river_world(world)
    stubs = _stubs(world)
    async with MockClientContext():
        _queue_stub_previews()
        setup = await _plan_with_stubs(world, ids, stubs, MockClient("test"))

    with world.revision(Source.manual(note="filled by hand")) as rev:
        rev.remove_field_value(stubs["frost"], "stub", None)
        rev.add_fact(stubs["frost"], "description", "Written by hand.")
        rev.remove_thing(stubs["order"])
    head = world.head_rev()
    with pytest.raises(ValueError, match="deleted"):
        await start_scene(world, setup, None)
    assert world.head_rev() == head
    assert world.view(None).thing(stubs["aldric"]).is_stub

    # without the deleted one, the hand-filled entry is kept as written
    setup.stub_previews = [
        p for p in setup.stub_previews if p.stub_id != stubs["order"]
    ]
    setup.pulled_in = [stubs["salt"]]
    await start_scene(world, setup, None)
    view = world.view(None)
    assert not view.thing(stubs["aldric"]).is_stub
    assert [f.text for f in view.thing(stubs["frost"]).facts] == ["Written by hand."]


@requires_chromadb
async def test_index_hit_stubs_are_not_pulled_in_or_filled(world):
    """A stub the index happens to find -- ignored or not -- is no lore the
    scene uses: it isn't pulled in, shown to the model or filled out, so
    it costs no create call and Start doesn't revive an ignored one."""

    ids = _river_world(world)
    with world.revision(Source.manual(note="stubs")) as rev:
        junk = rev.create_thing(
            "lore",
            fields={"name": "River successor states", "stub": {"ignored": True}},
        )
        edict = rev.create_thing(
            "lore", fields={"name": "River Edict", "stub": {"ignored": False}}
        )

    client = MockClient("test")
    async with MockClientContext():
        _queue(SETUP_REPLY)
        setup = await plan_scene(
            world,
            "Maren argues with Tobin about the river tolls",
            {"Maren": ids["vos"]},
            None,
            START,
            client,
            embedding_function=TrigramEmbeddingFunction(),
        )

    assert junk not in setup.pulled_in
    assert edict not in setup.pulled_in
    assert setup.stub_previews == []
    # only the setup itself was asked for
    assert len(client.prompt_history) == 1
    sent = str(client.prompt_history[0]["prompt"])
    assert "River successor states" not in sent


async def test_stub_named_in_the_reply_is_filled(world):
    """A lore stub the setup reply names in its intro or goal is one the
    scene uses: it's pulled in and filled out."""

    ids = _river_world(world)
    with world.revision(Source.manual(note="stubs")) as rev:
        edict = rev.create_thing(
            "lore", fields={"name": "River Edict", "stub": {"ignored": False}}
        )
        unused = rev.create_thing(
            "lore", fields={"name": "Salt Accord", "stub": {"ignored": False}}
        )

    async with MockClientContext():
        _queue(
            _created("River Edict", "general", "The edict closed the river."),
            "The edict closed the river.",
        )
        setup = await plan_scene(
            world,
            "Maren argues with Tobin",
            {},
            ids["vos"],
            START,
            MockClient("test"),
            reply={
                "player": "Maren Vos",
                "characters": ["Tobin"],
                "goal": "Get round the River Edict.",
                "intro": "Rain.",
            },
        )

    assert edict in setup.pulled_in
    assert unused not in setup.pulled_in
    assert [p.stub_id for p in setup.stub_previews] == [edict]


async def test_race_and_mix_stubs_are_not_filled(world):
    """A race or mix stub can't be filled from setup (a race needs its
    species, a mix its parents): it's left a stub, and the plan goes on."""

    ids = _river_world(world)
    with world.revision(Source.manual(note="stubs")) as rev:
        rev.create_thing("species", fields={"name": "Owl-folk"})
        snowy = rev.create_thing(
            "race", fields={"name": "Snowy", "stub": {"ignored": False}}
        )
        blend = rev.create_thing(
            "mix", fields={"name": "Owl-blend", "stub": {"ignored": False}}
        )

    async with MockClientContext():
        setup = await plan_scene(
            world,
            "Maren meets a Snowy and an Owl-blend",
            {"Snowy": snowy, "Owl-blend": blend},
            ids["vos"],
            START,
            MockClient("test"),
            reply={"player": "Maren Vos", "characters": [], "intro": "Rain."},
        )

    assert setup.stub_previews == []
    assert world.view(None).thing(snowy).is_stub


async def test_a_failed_stub_preview_leaves_that_stub(world):
    """One stub's preview failing (here, a reply with no facts) is logged
    and leaves that stub a stub; the other stubs are still filled and the
    plan goes on."""

    ids = _river_world(world)
    stubs = _stubs(world)
    async with MockClientContext():
        _queue(
            json.dumps({"name": "Aldric", "facts": [], "names": []}),
            _created("Frosthollow", "description", "A snowbound village on the weir."),
            "Frosthollow sits under snow.",
            _created("Order of the Heron", "general", "Keepers of the river ledgers."),
            "The Order keeps the ledgers.",
        )
        setup = await _plan_with_stubs(world, ids, stubs, MockClient("test"))

    assert [p.stub_id for p in setup.stub_previews] == [stubs["frost"], stubs["order"]]


@pytest.mark.parametrize("forged", [False, True])
async def test_starting_a_scene_writes_only_the_stubs_own_facts(world, forged):
    """Ruling C25: a stub the scene fills is previewed and accepted with no
    owner to tick anything, so it writes only its own facts. Its elsewhere
    items, its "In" rows, its "File into this" rows and the facts that
    could move here arrive unticked and are never written; no same-thing
    verdict is asked (nobody sees it). Every other entry keeps exactly the
    facts it had (the curation flow probe: a scene start wrote 5 facts
    onto 4 entries and moved 2 of the Church's out)."""

    ids = _river_world(world)
    with world.revision(Source.manual(note="weir")) as rev:
        weir = rev.create_thing("place", fields={"name": "The Weir"})
        rev.add_fact(weir, "description", "Snow lies deep in the hollow below.")
        rev.add_fact(weir, "general", "Frosthollow's ice-fishers mend nets all winter.")
        # a same-thing candidate for Frosthollow, with facts of its own
        inn = rev.create_thing("place", fields={"name": "Frosthollow Inn"})
        rev.add_fact(inn, "description", "A warm inn by the road.")
        frost = rev.create_thing(
            "place",
            fields={
                "name": "Frosthollow",
                "stub": {"ignored": False},
                "filings": [
                    {
                        "target": weir,
                        "role": None,
                        "since": None,
                        "until": None,
                        "within": None,
                        "exceptions": [],
                    }
                ],
            },
        )
    before = {
        thing.id: sorted(f.fact_id for f in thing.facts)
        for thing in world.view().things()
        if thing.id != frost
    }
    frost_reply = json.dumps(
        {
            "name": "Frosthollow",
            "facts": [
                {"category": "description", "text": "A snowbound village on the weir."}
            ],
            "names": [],
            "elsewhere": [
                {
                    "entry": "The Drowned Stag",
                    "text": "The Drowned Stag sells Frosthollow ice.",
                },
                {"entry": "The Weir", "text": "The Weir freezes solid each winter."},
            ],
            "in": [{"entry": "Frosthollow Inn", "role": "beside it"}],
            "file_into": [{"entry": "Frosthollow Inn", "role": None}],
        }
    )
    reply = {
        "player": "Maren Vos",
        "place": {"name": "Frosthollow", "world": True},
        "goal": "Buy ice.",
        "intro": "Snow drifts against the door.",
    }
    client = MockClient("test")
    async with MockClientContext():
        _queue(frost_reply, "Frosthollow sits under snow.")
        setup = await plan_scene(
            world,
            "Maren buys ice in Frosthollow",
            {"Frosthollow": frost},
            ids["vos"],
            START,
            client,
            reply=reply,
        )
    [preview] = setup.stub_previews
    assert preview.elsewhere and not any(e.ticked for e in preview.elsewhere)
    # the Weir's ice-fishers line names Frosthollow: it could move here
    assert preview.move_here and not any(m.ticked for m in preview.move_here)
    assert preview.filings and not any(f.ticked for f in preview.filings)
    # no verdict call: the create and its prose only
    assert len(client.prompt_history) == 2
    assert preview.verdict is None

    setup = SceneSetup.model_validate(json.loads(setup.model_dump_json()))
    if forged:
        # final review minor 4: the start trusts no client's ticks -- a
        # setup sent back with its rows ticked writes only its own facts
        [sent] = setup.stub_previews
        for item in sent.elsewhere:
            item.ticked = True
        for rows in (sent.move_here, sent.filings, sent.file_into):
            for row in rows:
                row.ticked = True
        sent.file_into.append(
            FileIntoRow(thing_id=inn, name="Frosthollow Inn", ticked=True)
        )
    async with MockClientContext():
        await start_scene(world, setup, MockClient("test"))

    view = world.view()
    after = {
        thing.id: sorted(f.fact_id for f in thing.facts)
        for thing in view.things()
        if thing.id != frost
    }
    assert after == before
    assert [view.render(f.text) for f in view.thing(frost).facts] == [
        "A snowbound village on the weir."
    ]
    assert [f.target for f in filings_of(view, frost)] == [weir]
    assert filings_of(view, inn) == []


# --- filed entries -------------------------------------------------------------

VIGIL_REPLY = {
    "player": "Vasha",
    "place": {"name": "Dawn Peak", "world": True},
    "goal": "Keep the vigil.",
    "intro": "Snow on the peak.",
}


async def test_plan_scene_pulls_in_a_named_place(world, spheres_world):
    """A place the prompt names (the Tsardom, the Marches, Kremova; the
    scene at Dawn Peak) is pulled in, so the scene touches it (filing
    spec: what the prompt names is touched), but never the scene's own place, and a named place stub
    isn't previewed (places only ever are as the scene's place)."""

    s = spheres_world
    with world.revision(Source.manual(note="stub")) as rev:
        marches = rev.create_thing(
            "place",
            fields={"name": "The Marches", "stub": {"ignored": False}},
        )
    setup = await plan_scene(
        world,
        "Vasha keeps the vigil at Dawn Peak, far from the Tsardom, the Marches "
        "and Kremova",
        {
            "Dawn Peak": s.dawn_peak,
            "the Tsardom": s.tsardom,
            "the Marches": marches,
            "Kremova": s.kremova,
        },
        s.vasha,
        WorldDate.of(1020),
        None,
        reply=VIGIL_REPLY,
    )

    assert setup.place == SetupRef(thing_id=s.dawn_peak)
    assert setup.pulled_in == [s.tsardom, marches, s.kremova]
    assert stubs_to_fill(world, setup) == []

    # the scene's own place is never pulled in
    setup = await plan_scene(
        world,
        "Vasha rides through the Tsardom",
        {"the Tsardom": s.tsardom},
        s.vasha,
        WorldDate.of(1020),
        None,
        reply={**VIGIL_REPLY, "place": None},
    )
    assert setup.place == SetupRef(thing_id=s.tsardom)
    assert setup.pulled_in == []


async def test_start_scene_leaves_its_place_out_of_pulled_in(world, spheres_world):
    """A setup edited (or continued) after planning whose place became a
    place it also pulled in starts with that place as its place only:
    never pulled in too (Task 7 parked item (a))."""

    s = spheres_world
    setup = await plan_scene(
        world,
        "Vasha keeps the vigil at Dawn Peak, far from the Tsardom",
        {"Dawn Peak": s.dawn_peak, "the Tsardom": s.tsardom},
        s.vasha,
        WorldDate.of(1020),
        None,
        reply=VIGIL_REPLY,
    )
    assert setup.pulled_in == [s.tsardom]
    # the owner moves the scene to the Tsardom
    setup.place = SetupRef(thing_id=s.tsardom)

    async with MockClientContext():
        scene_id = await start_scene(world, setup, None)

    record = world.scenes().get(scene_id)
    assert record.state["place_thing_id"] == s.tsardom
    assert record.state["pulled_in"] == []
