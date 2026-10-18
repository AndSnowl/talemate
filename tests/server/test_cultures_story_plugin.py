"""Tests for the cultures plugin's `counts`/`story` pushes (plan 3 / task 3).

Reuses the Culture agent test setup (`tests/test_culture_agent.py`): a real
`MockScene` with every agent bootstrapped onto it, the Taelrik fixture
imported into a linked shared world, and `build_places`'s nested places so
"Veldhaer" resolves to the Taelrik culture mix through its parent "The
Taelrik Reach". `_MockWebsocketHandler` (from `server.test_cultures_plugin`)
stands in for the real websocket handler.
"""

from pathlib import Path

import pytest

import talemate.instance as instance
from talemate.character import Character
from talemate.cultures.exchange import apply_import
from talemate.cultures.models import CharacterCulture
from talemate.cultures.signals import CulturesEvent
from talemate.cultures.store import WorldStore, world_dir_for_scene
from talemate.server.cultures import CulturesPlugin
from talemate.shared_context import SharedContext
from talemate.world_state.schema import CharacterState

from conftest import MockScene, bootstrap_scene
from cultures._fixtures import build_places
from server.test_cultures_plugin import _MockWebsocketHandler

FIXTURE_PATH = (
    Path(__file__).parent.parent / "cultures" / "data" / "taelrik.culture.json"
)
LOCATION = "The Quillister inn in Veldhaer"


def _link_world(scene, tmp_path) -> WorldStore:
    world_path = tmp_path / "shared-context" / "world.json"
    scene.shared_context = SharedContext(filepath=world_path)
    store = WorldStore(world_dir_for_scene(scene))
    store.root.mkdir(parents=True, exist_ok=True)
    return store


@pytest.fixture
def scene():
    scene = MockScene()
    bootstrap_scene(scene)
    return scene


@pytest.fixture
def world(scene, tmp_path) -> WorldStore:
    store = _link_world(scene, tmp_path)
    apply_import(store, FIXTURE_PATH.read_text(), today="2026-10-18")
    store.save_places(build_places())
    scene.world_state.location = LOCATION

    # An unsure, AI-set character culture, so a test can tell whether
    # `_send_counts` actually folds it into `unreviewed_total` (Ruling R1).
    scene.character_data["Kethrun"] = Character(
        name="Kethrun",
        description="",
        culture=CharacterCulture(culture_id="taelrik", unsure=True),
    )
    scene.world_state.characters = {"Kethrun": CharacterState(snapshot="x")}
    return store


@pytest.fixture
def agent(scene):
    return instance.get_agent("culture")


@pytest.fixture
def plugin(scene):
    handler = _MockWebsocketHandler(scene=scene)
    plug = CulturesPlugin(handler)
    yield plug
    plug.disconnect()


def _by_action(plugin: CulturesPlugin, action: str) -> dict:
    return next(m for m in plugin.websocket_handler.messages if m["action"] == action)


@pytest.mark.asyncio
async def test_get_story_without_world(plugin):
    await plugin.handle_get_story({})

    actions = [m["action"] for m in plugin.websocket_handler.messages]
    assert actions == ["counts", "story"]
    assert _by_action(plugin, "counts")["data"] == {}
    assert _by_action(plugin, "story")["data"] == {"available": False}


@pytest.mark.asyncio
async def test_get_story_has_lexicon_names_and_counts(plugin, world):
    await plugin.handle_get_story({})

    counts = _by_action(plugin, "counts")
    story = _by_action(plugin, "story")

    # Kethrun's unsure, AI-set culture must be folded into `unreviewed_total`
    # exactly like `_send_world` does, not left as the raw store count.
    assert counts["data"]["unreviewed_total"] == world.counts()["unreviewed_total"] + 1

    lexicon_texts = {entry["text"] for entry in story["data"]["lexicon"]}
    assert "Rhok tal'dun!" in lexicon_texts
    assert "saervik" in lexicon_texts

    name_texts = {entry["text"] for entry in story["data"]["names"]}
    assert "Kethrun" in name_texts

    assert story["data"]["characters"][0]["culture_name"] == "Taelrik"


@pytest.mark.asyncio
async def test_lexicon_empty_when_agent_disabled_or_other_scene(plugin, world, agent):
    agent.is_enabled = False

    await plugin.handle_get_story({})

    story = _by_action(plugin, "story")
    assert story["data"]["lexicon"] == []
    assert story["data"]["names"]
    assert story["data"]["available"] is True

    agent.is_enabled = True
    agent.scene = MockScene()
    plugin.websocket_handler.messages.clear()

    await plugin.handle_get_story({})

    story = _by_action(plugin, "story")
    assert story["data"]["lexicon"] == []


def test_scene_cultures_remember_false(scene, world, agent):
    loaded = agent.load_world()
    assert loaded is not None
    assert agent.get_scene_state("current_place_id") is None

    scene_cultures = agent.scene_cultures(loaded, remember=False)

    assert scene_cultures.place is not None
    assert agent.get_scene_state("current_place_id") is None


@pytest.mark.asyncio
async def test_world_reply_sends_counts_story_then_world(plugin, world):
    entry = world.load_glossary()[0]
    plugin.websocket_handler.messages.clear()

    await plugin.handle_review_glossary_entry(
        {"entry_id": entry.id, "status": "reviewed"}
    )

    actions = [m["action"] for m in plugin.websocket_handler.messages]
    assert actions[-3:] == ["counts", "story", "world"]


@pytest.mark.asyncio
async def test_agent_events_push_story(plugin, world):
    world_dir = str(world.root)
    plugin.websocket_handler.messages.clear()

    await plugin.on_cultures_event(
        CulturesEvent(kind="snapshot_processed", world_dir=world_dir, changed=False)
    )
    assert [m["action"] for m in plugin.websocket_handler.messages] == [
        "story",
        "snapshot_processed",
    ]

    plugin.websocket_handler.messages.clear()
    await plugin.on_cultures_event(
        CulturesEvent(kind="context_injected", world_dir=world_dir, changed=False)
    )
    assert [m["action"] for m in plugin.websocket_handler.messages] == [
        "context_injected"
    ]


@pytest.mark.asyncio
async def test_story_errors_reported_not_raised(plugin, world):
    world.glossary_path.write_text("{", encoding="utf-8")
    plugin.websocket_handler.messages.clear()

    await plugin.handle_get_story({})

    counts = _by_action(plugin, "counts")
    story = _by_action(plugin, "story")

    assert counts["data"] == {}
    assert story["data"]["error"]
    assert story["data"]["lexicon"] == []
