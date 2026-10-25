"""Tests for the Culture agent's post-snapshot step (plan 2 / task 8): new
places (one model call), new glossary names, character cultures, play
additions (one gated model call) and the `snapshot_processed` event.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import talemate.instance as instance
from talemate.agents.world_state.snapshot import WorldStateSnapshotEmission
from talemate.cultures.exchange import apply_import
from talemate.cultures.models import (
    CharacterCulture,
    Culture,
    GlossaryEntry,
    GlossaryOrigin,
    Language,
    Place,
)
from talemate.cultures.store import WorldStore, world_dir_for_scene
from talemate.prompts.base import Prompt
from talemate.scene_message import NarratorMessage, reset_message_id
from talemate.shared_context import SharedContext
from talemate.world_state.schema import CharacterState, ObjectState

from _director_test_helpers import add_character_to_scene
from conftest import MockScene, bootstrap_scene, connect_recorder
from cultures._fixtures import build_places

FIXTURE_PATH = Path(__file__).parent / "cultures" / "data" / "taelrik.culture.json"
PLACES = "culture.infer-places"
ADDITIONS = "culture.find-additions"
KESTERHOLM_LINE = "Kesterholm | village | Birch Coast | inherit | sure"


@pytest.fixture
def scene():
    scene = MockScene()
    bootstrap_scene(scene)
    return scene


@pytest.fixture
def world(scene, tmp_path) -> WorldStore:
    scene.shared_context = SharedContext(
        filepath=tmp_path / "shared-context" / "world.json"
    )
    store = WorldStore(world_dir_for_scene(scene))
    store.root.mkdir(parents=True, exist_ok=True)
    apply_import(store, FIXTURE_PATH.read_text(), today="2026-10-18")
    store.save_culture(
        Culture(
            id="elsiri",
            name="Elsiri",
            language=Language(name="Elsiri", level="naming"),
        )
    )
    store.save_places(build_places())
    return store


@pytest.fixture
def agent(scene):
    return instance.get_agent("culture")


@pytest.fixture
def events(isolate_signals):
    return connect_recorder(isolate_signals("cultures.event"))


def install_replies(monkeypatch, replies: dict):
    """Stub `Prompt.request`: each template answers `replies[uid]` (a string,
    or a callable raising), as both the response and the extracted anchor.
    Returns the recorded calls."""

    calls: list[dict] = []

    async def _request(cls, uid, client, kind, vars=None, **kwargs):
        calls.append({"template": uid, "kind": kind, "vars": vars or {}})
        reply = replies.get(uid, "")
        if callable(reply):
            reply = reply(vars)
        key = {PLACES: "places", ADDITIONS: "additions"}.get(uid, "response")
        return reply, {key: reply}

    monkeypatch.setattr(Prompt, "request", classmethod(_request), raising=True)
    return calls


def templates(calls) -> list[str]:
    return [call["template"] for call in calls]


def snapshot_emission(scene) -> WorldStateSnapshotEmission:
    return WorldStateSnapshotEmission(
        agent=instance.get_agent("world_state"), world_state=scene.world_state
    )


def set_snapshot(scene, location, characters=(), items=()):
    scene.world_state.location = location
    scene.world_state.characters = {name: CharacterState() for name in characters}
    scene.world_state.items = {name: ObjectState() for name in items}


def narrate(scene, text: str) -> NarratorMessage:
    message = NarratorMessage(message=text)
    scene.history.append(message)
    return message


def processed(events):
    return [e for e in events if e.kind == "snapshot_processed"]


@pytest.mark.asyncio
async def test_snapshot_adds_names_places_and_event(
    scene, world, agent, monkeypatch, events
):
    calls = install_replies(monkeypatch, {PLACES: KESTERHOLM_LINE, ADDITIONS: "NONE"})
    set_snapshot(
        scene,
        "Kesterholm, on the Birch Coast",
        characters=["Brannoch"],
        items=["Grey Gull"],
    )
    narrate(scene, "At Kesterholm, Brannoch tied up beside the Grey Gull.")

    await agent.on_snapshot_after(snapshot_emission(scene))

    assert templates(calls).count(PLACES) == 1
    [kesterholm] = [p for p in world.load_places() if p.name == "Kesterholm"]
    assert kesterholm.parent_id == "birch"
    assert kesterholm.set_by == "ai"
    assert kesterholm.cultures == []

    by_text = {e.text: e for e in world.load_glossary()}
    assert by_text["Brannoch"].kind == "person"
    assert by_text["Brannoch"].status == "unreviewed"
    assert by_text["Brannoch"].origin.by == "ai_free"
    assert by_text["Grey Gull"].kind == "thing"
    assert by_text["Kesterholm"].kind == "place"
    assert by_text["Kesterholm"].place_id == kesterholm.id

    [event] = processed(events)
    assert event.changed is True
    # the location names the place just created first
    assert event.data["place"] == "Kesterholm"
    assert event.data["new_places"] == ["Kesterholm"]
    new_names = {n["text"]: n for n in event.data["new_names"]}
    assert {"Brannoch", "Grey Gull", "Kesterholm"} <= set(new_names)
    assert set(new_names["Brannoch"]) == {
        "text",
        "kind",
        "culture_id",
        "doesnt_fit",
        "origin",
    }
    assert event.data["additions"] == []
    assert event.data["ms"] >= 0


@pytest.mark.asyncio
async def test_snapshot_role_labels_skip_glossary(
    scene, world, agent, monkeypatch, events
):
    # a live run recorded "Innkeeper's Boy" and "Bargemen" (world-state role
    # keys, not names) as persons; they must be skipped
    calls = install_replies(monkeypatch, {ADDITIONS: "NONE"})
    set_snapshot(
        scene,
        "A room at Quillister House in Veldhaer",
        characters=["Innkeeper's Boy", "Bargemen", "Brannoch"],
    )
    narrate(scene, "Brannoch waited while Bargemen hauled crates past the door.")

    await agent.on_snapshot_after(snapshot_emission(scene))

    assert PLACES not in templates(calls)
    texts = {e.text for e in world.load_glossary()}
    assert "Brannoch" in texts
    assert "Innkeeper's Boy" not in texts
    assert "Bargemen" not in texts
    [event] = processed(events)
    new_names = {n["text"] for n in event.data["new_names"]}
    assert "Brannoch" in new_names
    assert "Innkeeper's Boy" not in new_names
    assert "Bargemen" not in new_names


@pytest.mark.asyncio
async def test_no_place_call_without_new_places(
    scene, world, agent, monkeypatch, events
):
    calls = install_replies(monkeypatch, {ADDITIONS: "NONE"})
    set_snapshot(
        scene, "A room at Quillister House in Veldhaer", characters=["Brannoch"]
    )
    narrate(scene, "Brannoch waited by the door.")

    await agent.on_snapshot_after(snapshot_emission(scene))

    assert PLACES not in templates(calls)
    assert "Brannoch" in {e.text for e in world.load_glossary()}
    [event] = processed(events)
    assert event.data["new_places"] == []


@pytest.mark.asyncio
async def test_additions_once_per_new_messages(
    scene, world, agent, monkeypatch, events
):
    calls = install_replies(
        monkeypatch,
        {ADDITIONS: "Taelrik | customs | Ferrymen spit over the rail before landing."},
    )
    set_snapshot(scene, "A room at Quillister House in Veldhaer")
    narrate(scene, "The ferryman spat over the rail before landing, as they all do.")

    await agent.on_snapshot_after(snapshot_emission(scene))

    assert templates(calls) == [ADDITIONS]
    [addition] = world.load_cultures()["taelrik"].additions
    assert addition.section == "customs"
    assert addition.text == "Ferrymen spit over the rail before landing."
    assert addition.status == "unreviewed"
    assert processed(events)[-1].data["additions"] == [
        {
            "culture_id": "taelrik",
            "section": "customs",
            "text": "Ferrymen spit over the rail before landing.",
        }
    ]
    assert processed(events)[-1].changed is True

    # no new messages: no second call
    await agent.on_snapshot_after(snapshot_emission(scene))
    assert templates(calls) == [ADDITIONS]

    # a new message, but the world has no cultures: no call
    for culture_id in list(world.load_cultures()):
        world.delete_culture(culture_id)
    narrate(scene, "Another crossing.")
    await agent.on_snapshot_after(snapshot_emission(scene))
    assert templates(calls) == [ADDITIONS]


@pytest.mark.asyncio
async def test_owner_culture_never_overwritten(
    scene, world, agent, monkeypatch, events
):
    install_replies(
        monkeypatch,
        {
            PLACES: KESTERHOLM_LINE
            + "\nBirch Coast | region | none | Taelrik 100 | sure",
            ADDITIONS: "NONE",
        },
    )
    character = await add_character_to_scene(scene, "Tovrin")
    owner_culture = CharacterCulture(
        culture_id="elsiri", set_by="owner", reason="the owner said so"
    )
    character.culture = owner_culture.model_copy()
    birch_before = next(p for p in world.load_places() if p.id == "birch")
    set_snapshot(scene, "Kesterholm, on the Birch Coast", characters=["Tovrin"])
    narrate(scene, "Tovrin mended a net at Kesterholm.")

    await agent.on_snapshot_after(snapshot_emission(scene))

    assert character.culture == owner_culture
    birch_after = next(p for p in world.load_places() if p.id == "birch")
    assert birch_after == birch_before
    assert birch_after.cultures == birch_before.cultures
    assert processed(events)[0].data["cultures_set"] == []


@pytest.mark.asyncio
async def test_scene_characters_without_culture_get_ai_guess(
    scene, world, agent, monkeypatch, events
):
    install_replies(monkeypatch, {ADDITIONS: "NONE"})
    character = await add_character_to_scene(scene, "Tovrin")
    set_snapshot(scene, "A room at Quillister House in Veldhaer", characters=["Tovrin"])

    await agent.on_snapshot_after(snapshot_emission(scene))

    assert character.culture is not None
    assert character.culture.culture_id == "taelrik"
    assert character.culture.set_by == "ai"
    [event] = processed(events)
    assert event.data["cultures_set"] == [
        {
            "name": "Tovrin",
            "culture_id": "taelrik",
            "unsure": character.culture.unsure,
        }
    ]


@pytest.mark.asyncio
async def test_handler_errors_are_swallowed(scene, world, agent, monkeypatch, events):
    install_replies(monkeypatch, {ADDITIONS: "NONE"})

    def broken_save(self, entries):
        raise OSError("disk full")

    monkeypatch.setattr(WorldStore, "save_glossary", broken_save)
    character = await add_character_to_scene(scene, "Tovrin")
    set_snapshot(
        scene, "A room at Quillister House in Veldhaer", characters=["Brannoch"]
    )
    narrate(scene, "Brannoch waited by the door.")

    assert await agent.on_snapshot_after(snapshot_emission(scene)) is None

    # the other steps still ran
    assert character.culture is not None
    [event] = processed(events)
    assert event.data["new_names"] == []


@pytest.mark.asyncio
async def test_place_call_failure_keeps_other_steps(
    scene, world, agent, monkeypatch, events
):
    def boom(vars):
        raise RuntimeError("model down")

    install_replies(monkeypatch, {PLACES: boom, ADDITIONS: "NONE"})
    set_snapshot(scene, "Kesterholm, on the Birch Coast", characters=["Brannoch"])
    narrate(scene, "Brannoch mended a net at Kesterholm.")

    await agent.on_snapshot_after(snapshot_emission(scene))

    # a failed call creates no place: the name is proposed again later
    assert "Kesterholm" not in {p.name for p in world.load_places()}
    assert "Brannoch" in {e.text for e in world.load_glossary()}
    assert len(processed(events)) == 1

    install_replies(monkeypatch, {PLACES: KESTERHOLM_LINE, ADDITIONS: "NONE"})
    await agent.on_snapshot_after(snapshot_emission(scene))
    assert "Kesterholm" in {p.name for p in world.load_places()}


@pytest.mark.asyncio
async def test_templates_render_with_agent_vars(scene, world, agent, monkeypatch):
    calls = install_replies(monkeypatch, {PLACES: KESTERHOLM_LINE, ADDITIONS: "NONE"})
    set_snapshot(scene, "Kesterholm, on the Birch Coast", characters=["Brannoch"])
    narrate(scene, "Brannoch mended a net at Kesterholm.")

    await agent.on_snapshot_after(snapshot_emission(scene))

    by_template = {call["template"]: call["vars"] for call in calls}
    places_vars = dict(by_template[PLACES], decensor=False)
    prompt = Prompt.get(PLACES, places_vars)
    text = prompt.render()
    assert "New place names: Kesterholm" in text
    assert "- Birch Coast (region, in The Taelrik Reach)" in text
    assert "The scene is in: Birch Coast" in text
    assert "Name | kind | parent | cultures | sure or unsure" in text
    assert "Elsiri: Dhunmouth, Birch Coast" in text
    assert prompt.prepared_response.startswith("<PLACES>")

    additions_vars = dict(by_template[ADDITIONS], decensor=False)
    prompt = Prompt.get(ADDITIONS, additions_vars)
    text = prompt.render()
    assert "Not one person's habits, not events. If none, answer NONE." in text
    assert "- custom: Every crossing ends with a coin dropped" in text
    assert "- custom: Oaths are sworn with wet hands." in text
    assert "Elsiri\n- nothing known yet" in text
    assert "- holidays: Low Water, Lantern Night" in text
    assert "Brannoch mended a net at Kesterholm." in text
    assert prompt.prepared_response.startswith("<ADDITIONS>")


@pytest.mark.asyncio
async def test_inn_named_with_the_is_recorded(scene, world, agent, monkeypatch, events):
    # the model drops the article; the place keeps the name as written
    calls = install_replies(
        monkeypatch,
        {
            PLACES: "**Dhaer's Rest** | Building | Veldhaer | inherit | Sure.",
            ADDITIONS: "NONE",
        },
    )
    set_snapshot(scene, "A room at The Dhaer's Rest in Veldhaer")
    narrate(scene, "The common room of the Dhaer's Rest was full.")

    await agent.on_snapshot_after(snapshot_emission(scene))

    assert calls[0]["vars"]["names"] == ["The Dhaer's Rest"]
    [inn] = [p for p in world.load_places() if p.name == "The Dhaer's Rest"]
    assert inn.kind == "building"
    assert inn.parent_id == "veldhaer"
    assert inn.unsure is False
    by_text = {e.text: e for e in world.load_glossary()}
    assert by_text["The Dhaer's Rest"].place_id == inn.id
    assert processed(events)[0].data["place"] == "The Dhaer's Rest"


@pytest.mark.asyncio
async def test_reused_spare_sets_its_culture(scene, world, agent, monkeypatch):
    install_replies(monkeypatch, {ADDITIONS: "NONE"})
    agent.set_scene_states(
        offered_spares={"tovrin": {"culture_id": "elsiri", "generator_id": "given"}}
    )
    character = await add_character_to_scene(scene, "Tovrin")
    set_snapshot(scene, "A room at Quillister House in Veldhaer", characters=["Tovrin"])

    await agent.on_snapshot_after(snapshot_emission(scene))

    # Veldhaer is Taelrik and the name fits Taelrik, but it was offered as Elsiri
    assert character.culture.culture_id == "elsiri"
    assert character.culture.set_by == "ai"
    assert character.culture.unsure is False
    [entry] = [e for e in world.load_glossary() if e.text == "Tovrin"]
    assert entry.language == "elsiri"
    assert entry.origin.by == "ai"
    assert entry.origin.generator_id == "given"
    assert entry.origin.candidates == []


@pytest.mark.asyncio
async def test_person_in_location_is_not_a_place(
    scene, world, agent, monkeypatch, events
):
    calls = install_replies(monkeypatch, {ADDITIONS: "NONE"})
    await add_character_to_scene(scene, "Hessa")
    entries = world.load_glossary()
    entries.append(
        GlossaryEntry(
            id="varn",
            text="Varn",
            language="taelrik",
            kind="person",
            origin=GlossaryOrigin(by="owner"),
        )
    )
    world.save_glossary(entries)

    set_snapshot(scene, "Old Hessa's stall on the Dhunmouth docks")
    await agent.on_snapshot_after(snapshot_emission(scene))
    set_snapshot(scene, "Captain Varn's cabin aboard the Grey Gull")
    await agent.on_snapshot_after(snapshot_emission(scene))

    assert PLACES not in templates(calls)
    names = {p.name for p in world.load_places()}
    assert "Old Hessa" not in names
    assert "Captain Varn" not in names


@pytest.mark.asyncio
async def test_skipped_name_is_not_a_place_and_not_asked_again(
    scene, world, agent, monkeypatch, events
):
    calls = install_replies(
        monkeypatch,
        {PLACES: "Old Hessa | skip\n" + KESTERHOLM_LINE, ADDITIONS: "NONE"},
    )
    set_snapshot(scene, "Old Hessa's stall in Kesterholm")

    await agent.on_snapshot_after(snapshot_emission(scene))

    assert calls[0]["vars"]["names"] == ["Old Hessa", "Kesterholm"]
    names = {p.name for p in world.load_places()}
    assert "Kesterholm" in names
    assert "Old Hessa" not in names
    assert processed(events)[0].data["new_places"] == ["Kesterholm"]

    # the skipped name isn't proposed again
    await agent.on_snapshot_after(snapshot_emission(scene))
    assert templates(calls).count(PLACES) == 1


@pytest.mark.asyncio
async def test_stale_additions_checkpoint_after_reload(
    scene, world, agent, monkeypatch, events
):
    # a reloaded scene renumbers its messages from 1, so a saved checkpoint
    # can be past the newest id; detection must not stop
    calls = install_replies(
        monkeypatch,
        {ADDITIONS: "Taelrik | customs | Ferrymen spit over the rail before landing."},
    )
    set_snapshot(scene, "A room at Quillister House in Veldhaer")
    # message ids are process-wide: start from 1, as a reload does, so the
    # checkpoint is past them whatever ran before on this worker
    reset_message_id()
    narrate(scene, "The ferry was late again.")
    narrate(scene, "Rain hammered the river.")
    agent.set_scene_states(additions_checked_id=500)

    # what was loaded counts as checked
    await agent.on_snapshot_after(snapshot_emission(scene))
    assert ADDITIONS not in templates(calls)

    narrate(scene, "The ferryman spat over the rail before landing.")
    await agent.on_snapshot_after(snapshot_emission(scene))

    assert templates(calls).count(ADDITIONS) == 1
    assert "spat over the rail" in calls[-1]["vars"]["text"]
    assert "Rain hammered" not in calls[-1]["vars"]["text"]


def _owner_adds_during_await(world, name: str, reply: str):
    """A place reply that, while "the model answers", has the owner add
    `name` in the Cultures tab."""

    def answer(vars):
        places = world.load_places()
        places.append(Place(id="owner-k", name=name, kind="town", parent_id="birch"))
        world.save_places(places)
        return reply

    return answer


@pytest.mark.asyncio
async def test_owner_place_added_during_place_call_survives(
    scene, world, agent, monkeypatch, events
):
    install_replies(
        monkeypatch,
        {
            PLACES: _owner_adds_during_await(world, "Kesterholm", KESTERHOLM_LINE),
            ADDITIONS: "NONE",
        },
    )
    set_snapshot(scene, "Kesterholm, on the Birch Coast")

    await agent.on_snapshot_after(snapshot_emission(scene))

    [kesterholm] = [p for p in world.load_places() if p.name == "Kesterholm"]
    assert kesterholm.id == "owner-k"
    assert kesterholm.kind == "town"
    assert kesterholm.set_by == "owner"
    assert processed(events)[0].data["new_places"] == []


@pytest.mark.asyncio
async def test_last_moment_place_dedupe_ignores_the(
    scene, world, agent, monkeypatch, events
):
    install_replies(
        monkeypatch,
        {
            PLACES: _owner_adds_during_await(
                world,
                "Kesterholm",
                "The Kesterholm | village | Birch Coast | inherit | sure",
            ),
            ADDITIONS: "NONE",
        },
    )
    set_snapshot(scene, "The Kesterholm, on the Birch Coast")

    await agent.on_snapshot_after(snapshot_emission(scene))

    names = [p.name for p in world.load_places()]
    assert "Kesterholm" in names
    assert "The Kesterholm" not in names
