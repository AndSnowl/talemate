"""Tests for `talemate.worldplay.persistence`: a world-backed `Scene` saves
into, and loads back from, the world database instead of a scene JSON
file."""

import os

import pytest

import talemate.instance as instance
from talemate.character import Character
from talemate.config import Config, get_config
from talemate.config.schema import RecentScenes
from talemate.load import load_scene
from talemate.scene_message import (
    CharacterMessage,
    NarratorMessage,
    TimePassageMessage,
)
from talemate.tale_mate import Actor, Player, Scene
from talemate.world.dates import WorldDate
from talemate.world.store import Source
from talemate.worldplay.characters import character_from_world
from talemate.worldplay.context import WorldSceneContext
from talemate.worldplay.persistence import (
    WorldSceneRef,
    parse_world_target,
    world_target,
)

from conftest import MockMemoryAgent, MockScene, bootstrap_scene

START = WorldDate.of(313, 6, 1)


async def _noop(self, *args, **kwargs):
    pass


@pytest.fixture(autouse=True)
def no_memory_db(monkeypatch):
    """Loading a scene sets up, reads and recommits the memory database;
    the mock memory agent has none."""

    monkeypatch.setattr(MockMemoryAgent, "set_db", _noop)
    monkeypatch.setattr(MockMemoryAgent, "_get_document", lambda self, id: {})
    monkeypatch.setattr(Scene, "commit_to_memory", _noop)


@pytest.fixture(autouse=True)
def recent_scenes(monkeypatch):
    """An empty recent-scenes list, and no `config.changed` broadcast (the
    mock memory agent can't take one) when a save marks the config dirty."""

    monkeypatch.setattr(Config, "set_dirty", _noop)
    fresh = RecentScenes(scenes=[])
    monkeypatch.setattr(get_config(), "recent_scenes", fresh)
    return fresh


@pytest.fixture
def scenes_dir(tmp_path, monkeypatch):
    """Point `Scene.scenes_dir()` at an empty temp directory, so a test can
    see whether anything gets written under it."""

    path = tmp_path / "scenes"
    path.mkdir()
    monkeypatch.setattr(Scene, "scenes_dir", classmethod(lambda cls: str(path)))
    return path


def _make_world_characters(world) -> tuple[str, str]:
    with world.revision(Source.manual(note="setup")) as rev:
        mira = rev.create_thing(
            "character",
            fields={"name": "Mira", "born": WorldDate.of(280)},
            valid_from=WorldDate.of(280),
        )
        tobin = rev.create_thing(
            "character",
            fields={"name": "Tobin", "born": WorldDate.of(290)},
            valid_from=WorldDate.of(290),
        )
    return mira, tobin


async def _world_scene(world, *, goal: str = "", player_thing_id=None):
    """A bootstrapped `MockScene` attached to a new world scene record."""

    scenes = world.scenes()
    scene_id = scenes.create(
        "River Scene",
        START,
        premise="Two rivermen wait out a storm.",
        goal=goal,
        player_thing_id=player_thing_id,
    )
    record = scenes.get(scene_id)

    scene = MockScene()
    bootstrap_scene(scene)
    scene.name = record.name
    scene.description = record.premise  # as `load_world_scene` sets it
    scene.world_ref = WorldSceneRef(world_path=str(world.path), scene_id=scene_id)
    scene.world_context = WorldSceneContext(world=world, record=record)
    return scene, scene_id


async def _add(scene, character: Character, *, player: bool = False) -> None:
    if player:
        actor = Player(character=character, agent=None)
    else:
        actor = Actor(character=character, agent=instance.get_agent("conversation"))
    await scene.add_actor(actor, commit_to_memory=False)
    scene.active_characters.append(character.name)


async def _reload(world, scene_id) -> Scene:
    fresh = MockScene()
    bootstrap_scene(fresh)
    return await load_scene(fresh, world_target(str(world.path), scene_id))


@pytest.mark.asyncio
async def test_world_scene_roundtrip(world, scenes_dir):
    """Review Focus 2: a world scene comes back from save and reload with
    the same history, `ts`, characters, player, goal and start date."""

    mira_id, tobin_id = _make_world_characters(world)
    scene, scene_id = await _world_scene(
        world, goal="Find the missing envoy", player_thing_id=tobin_id
    )

    mira = character_from_world(world, mira_id, START, is_player=False)
    mira.color = "#abc123"  # per-scene state, must survive the round trip
    tobin = character_from_world(world, tobin_id, START, is_player=True)
    await _add(scene, mira)
    await _add(scene, tobin, player=True)

    scene.history = [
        NarratorMessage("Rain hammers the tavern roof."),
        CharacterMessage("Mira: We wait for the river to fall."),
        TimePassageMessage("A day passes.", ts="P1D"),
    ]
    scene.sync_time()
    assert scene.ts == "P1D"
    scene.description = "Two rivermen wait out a storm in a flooded tavern."

    await scene.save()

    loaded = await _reload(world, scene_id)

    assert [(m.message, m.typ) for m in loaded.history] == [
        (m.message, m.typ) for m in scene.history
    ]
    assert loaded.ts == "P1D"
    assert sorted(loaded.character_names) == ["Mira", "Tobin"]
    assert sorted(loaded.active_characters) == ["Mira", "Tobin"]
    assert loaded.get_player_character().name == "Tobin"
    assert loaded.get_character("Mira").color == "#abc123"
    assert loaded.get_character("Mira").world_thing_id == mira_id
    assert loaded.world_context.record.goal == "Find the missing envoy"
    assert loaded.world_context.record.start == START
    assert loaded.world_ref == scene.world_ref
    # the premise is the scene's description
    assert loaded.world_context.record.premise == scene.description
    assert loaded.description == scene.description

    loaded.world_context.world.close()


@pytest.mark.asyncio
async def test_world_save_writes_no_files_outside_world(
    world, scenes_dir, recent_scenes
):
    """Review Focus 5: no scene JSON, changelog or shared-context file."""

    mira_id, _ = _make_world_characters(world)
    scene, scene_id = await _world_scene(world)
    await _add(scene, character_from_world(world, mira_id, START, is_player=False))
    scene.history = [NarratorMessage("Rain hammers the tavern roof.")]

    before = sorted(os.walk(scenes_dir))
    await scene.save()
    assert sorted(os.walk(scenes_dir)) == before

    assert scene.save_dir == os.path.join(str(world.path), "scenes", scene_id)
    assert not os.path.exists(scene.changelog_dir)
    assert not os.path.exists(scene.shared_context_dir)
    json_files = [
        name
        for _, _, files in os.walk(scene.save_dir)
        for name in files
        if name.endswith(".json")
    ]
    assert json_files == []
    assert len(world.scenes().messages(scene_id)) == 1

    # still listed in recent scenes, by its world target
    assert [s.path for s in recent_scenes.scenes] == [
        world_target(str(world.path), scene_id)
    ]


@pytest.mark.asyncio
async def test_message_ids_stable_across_saves(world, scenes_dir):
    scene, scene_id = await _world_scene(world)
    scene.history = [
        NarratorMessage("Rain hammers the tavern roof."),
        NarratorMessage("The door creaks."),
    ]

    await scene.save()
    first = [m.id for m in world.scenes().messages(scene_id)]
    assert all(len(i) == 32 for i in first)
    assert [m.world_id for m in scene.history] == first

    scene.history.append(NarratorMessage("Someone knocks."))
    await scene.save()
    second = [m.id for m in world.scenes().messages(scene_id)]
    assert second[:2] == first
    assert len(set(second)) == 3

    # and across a reload, too
    loaded = await _reload(world, scene_id)
    assert [m.world_id for m in loaded.history] == second
    await loaded.save()
    assert [m.id for m in world.scenes().messages(scene_id)] == second

    loaded.world_context.world.close()


@pytest.mark.asyncio
async def test_message_elapsed_is_time_so_far(world, scenes_dir):
    scene, scene_id = await _world_scene(world)
    scene.history = [
        NarratorMessage("Rain hammers the tavern roof."),
        TimePassageMessage("A day passes.", ts="P1D"),
        NarratorMessage("The storm breaks."),
    ]
    await scene.save()

    records = world.scenes().messages(scene_id)
    assert [m.kind for m in records] == ["narrator", "time", "narrator"]
    assert [m.elapsed for m in records] == ["PT0S", "P1D", "P1D"]


@pytest.mark.asyncio
async def test_local_character_roundtrip(world, scenes_dir):
    """A character invented in the scene (no world thing) is kept as a
    scene-local thing, and comes back exactly."""

    mira_id, _ = _make_world_characters(world)
    scene, scene_id = await _world_scene(world)
    await _add(scene, character_from_world(world, mira_id, START, is_player=False))

    stranger = Character(
        name="The Stranger",
        description="A hooded figure dripping rainwater.",
        color="#334455",
        base_attributes={"gender": "unknown"},
    )
    await _add(scene, stranger)
    scene.history = [NarratorMessage("A hooded stranger walks in.")]

    await scene.save()

    (local,) = world.scenes().local_things(scene_id)
    assert local["kind"] == "character"
    assert len(local["local_id"]) == 32
    assert local["data"]["name"] == "The Stranger"
    assert stranger.world_local_id == local["local_id"]

    loaded = await _reload(world, scene_id)
    restored = loaded.get_character("The Stranger")
    assert restored is not None
    assert restored.description == "A hooded figure dripping rainwater."
    assert restored.color == "#334455"
    assert restored.base_attributes == {"gender": "unknown"}
    assert restored.world_thing_id is None
    assert restored.world_local_id == local["local_id"]
    assert "The Stranger" in loaded.active_characters

    loaded.world_context.world.close()


@pytest.mark.asyncio
async def test_save_keeps_setup_state(world, scenes_dir):
    """Keys scene setup put in `state` (the place, pulled-in lore), which
    `Scene.serialize` knows nothing about, survive a save."""

    scene, scene_id = await _world_scene(world)
    world.scenes().update(
        scene_id, state={"place_thing_id": "p" * 32, "pulled_in": ["l" * 32]}
    )
    scene.world_context.record = world.scenes().get(scene_id)

    await scene.save()

    state = world.scenes().get(scene_id).state
    assert state["place_thing_id"] == "p" * 32
    assert state["pulled_in"] == ["l" * 32]
    assert "history" not in state
    assert "character_data" not in state


@pytest.mark.asyncio
async def test_websocket_load_scene_takes_a_world_target(monkeypatch):
    """`WebsocketHandler.load_scene` hands a `WorldSceneRef` (or its
    `world://` path) on to `load_scene` as the world target."""

    import talemate.server.websocket_server as websocket_server

    seen = []

    async def fake_load_scene(scene, file_path, **kwargs):
        seen.append(file_path)
        return None  # "loading interrupted": skips starting the scene

    monkeypatch.setattr(websocket_server, "load_scene", fake_load_scene)

    class Handler:
        scene = None

        def init_scene(self):
            return MockScene()

        async def load_scene_failure(self, error):
            pass

    ref = WorldSceneRef(world_path="/worlds/abc", scene_id="d" * 32)
    await websocket_server.WebsocketHandler.load_scene(Handler(), ref)
    await websocket_server.WebsocketHandler.load_scene(Handler(), ref.target)

    assert seen == [ref.target, ref.target]
    assert ref.target == world_target("/worlds/abc", "d" * 32)
    assert parse_world_target(ref.target) == ref


@pytest.mark.asyncio
async def test_save_keeps_other_local_things_and_local_ids_across_rename(
    world, scenes_dir
):
    """A save only rewrites the scene's local *characters*: an invented
    place survives it. A local character keeps its `local_id` across a
    reload and a rename."""

    scene, scene_id = await _world_scene(world)
    place = {"local_id": "a" * 32, "kind": "place", "data": {"name": "A shed"}}
    world.scenes().set_local_things(scene_id, [place])

    await _add(scene, Character(name="The Stranger"))
    await scene.save()

    things = {t["kind"]: t for t in world.scenes().local_things(scene_id)}
    assert things["place"] == place
    local_id = things["character"]["local_id"]

    loaded = await _reload(world, scene_id)
    stranger = loaded.get_character("The Stranger")
    stranger.name = "Corvin"
    loaded.character_data["Corvin"] = loaded.character_data.pop("The Stranger")
    loaded.active_characters[loaded.active_characters.index("The Stranger")] = "Corvin"
    await loaded.save()

    things = {t["kind"]: t for t in world.scenes().local_things(scene_id)}
    assert things["place"] == place
    assert things["character"]["local_id"] == local_id
    assert things["character"]["data"]["name"] == "Corvin"

    loaded.world_context.world.close()


@pytest.mark.asyncio
async def test_world_character_missing_from_world_is_skipped(world, scenes_dir):
    mira_id, _ = _make_world_characters(world)
    scene, scene_id = await _world_scene(world)
    await _add(scene, character_from_world(world, mira_id, START, is_player=False))
    await scene.save()

    state = world.scenes().get(scene_id).state
    state["characters"].append({"thing_id": "f" * 32, "active": True})
    world.scenes().update(scene_id, state=state)

    loaded = await _reload(world, scene_id)
    assert loaded.character_names == ["Mira"]

    loaded.world_context.world.close()


@pytest.mark.asyncio
async def test_rename_survives_reload_and_save_as_saves_in_place(world, scenes_dir):
    scene, scene_id = await _world_scene(world)
    scene.name = "The Flooded Tavern"
    await scene.save(save_as=True, copy_name="copy")

    assert world.scenes().get(scene_id).name == "The Flooded Tavern"
    assert [s.id for s in world.scenes().list()] == [scene_id]

    loaded = await _reload(world, scene_id)
    assert loaded.name == "The Flooded Tavern"
    loaded.world_context.world.close()


@pytest.mark.asyncio
async def test_save_restore_writes_nothing_for_a_world_scene(world, scenes_dir):
    scene, _ = await _world_scene(world)
    await scene.save_restore("restore.json")
    assert not os.path.exists(os.path.join(scene.save_dir, "restore.json"))


@pytest.mark.asyncio
async def test_timeline_is_empty_for_a_world_scene(world, scenes_dir):
    from talemate.server.timeline import TimelinePlugin

    scene, scene_id = await _world_scene(world)
    await scene.save()

    class Handler:
        def __init__(self, scene):
            self.scene = scene
            self.messages = []

        def queue_put(self, data):
            self.messages.append(data)

    for active, scene_path in ((scene, None), (None, scene.world_ref.target)):
        plugin = TimelinePlugin(Handler(active))
        await plugin.handle_list_revisions({"scene_path": scene_path})
        await plugin.handle_preview({"rev": 1, "scene_path": scene_path})
        await plugin.handle_fork(
            {"rev": 1, "save_name": "fork", "scene_path": scene_path}
        )

        by_action = {m["action"]: m for m in plugin.websocket_handler.messages}
        assert by_action["revisions"]["data"]["revisions"] == []
        assert by_action["preview"]["data"]["messages"] == []
        assert by_action["operation_done"]["error"]["message"]

    assert not os.path.exists(os.path.join(scene.save_dir, "fork.json"))


def test_recent_scenes_cleanup_keeps_world_scenes(world, tmp_path):
    from talemate.config.schema import RecentScene
    from talemate.config.state import cleanup_removed_recent_scenes

    kept = world_target(str(world.path), "d" * 32)
    gone = world_target(str(tmp_path / "no-such-world"), "d" * 32)
    config = get_config()
    config.recent_scenes.scenes = [
        RecentScene(name=name, path=path, filename="", date="2026-10-19")
        for name, path in (("kept", kept), ("gone", gone))
    ]

    cleanup_removed_recent_scenes(config)

    assert [s.path for s in config.recent_scenes.scenes] == [kept]


@pytest.mark.asyncio
async def test_websocket_closes_the_world_when_the_scene_is_replaced(
    world, scenes_dir, monkeypatch
):
    import sqlite3

    import talemate.server.websocket_server as websocket_server

    scene, scene_id = await _world_scene(world)
    await scene.save()
    loaded = await _reload(world, scene_id)
    loaded_world = loaded.world_context.world

    async def fake_load_scene(scene, file_path, **kwargs):
        return None

    monkeypatch.setattr(websocket_server, "load_scene", fake_load_scene)

    class Handler:
        def __init__(self, scene):
            self.scene = scene

        def init_scene(self):
            return MockScene()

        async def load_scene_failure(self, error):
            pass

    await websocket_server.WebsocketHandler.load_scene(Handler(loaded), "other.json")

    with pytest.raises(sqlite3.ProgrammingError):
        loaded_world.scenes().get(scene_id)


@pytest.mark.asyncio
async def test_a_save_after_the_world_is_closed_is_a_no_op(world, scenes_dir):
    """Closing a replaced scene's world clears `scene.world_context`; an
    auto-save that comes in late is logged and skipped rather than writing
    through a closed connection."""

    from talemate.worldplay.persistence import close_world_scene

    scene, scene_id = await _world_scene(world)
    await scene.save()
    loaded = await _reload(world, scene_id)
    loaded.history.append(NarratorMessage("Too late."))

    close_world_scene(loaded)
    assert loaded.world_context is None

    await loaded.save(auto=True)
    assert world.scenes().messages(scene_id) == []
    assert not any(scenes_dir.iterdir())
