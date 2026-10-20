"""Scene setup: name matching in the scene prompt, planning a scene from a
storyline prompt plus the world, starting it, and continuing in a new
scene."""

import json

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
from talemate.worldplay.create import current_date
from talemate.worldplay.persistence import close_world_scene, world_target
from talemate.worldplay.setup import (
    LocalThing,
    SceneSetup,
    SetupRef,
    continue_setup,
    match_names,
    plan_scene,
    start_scene,
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


async def test_plan_scene_rejects_unknown_pick(world):
    _river_world(world)
    with pytest.raises(KeyError):
        await plan_scene(
            world, "Maren", {"Maren": "no-such-thing"}, None, START, MockClient("t")
        )


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
        _queue("Maren Vos has a heron tattoo.")
        scene_id = await start_scene(world, _setup(ids), client)

    assert len(client.prompt_history) == 1
    cache = world.prose()
    assert cache.get(ids["vos"], "description", START).text == (
        "Maren Vos has a heron tattoo."
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
