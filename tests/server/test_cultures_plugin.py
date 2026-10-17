"""Unit tests for the `cultures` websocket plugin.

Uses the Task 5 culture file fixture (tests/cultures/data/taelrik.culture.json)
to exercise import/export/roll against a real `WorldStore`, and the
`_MockWebsocketHandler` / `isolated_scene` patterns used elsewhere in the
test suite (tests/server/test_scene_message.py, tests/test_scene_methods.py).
"""

import json
import os
from pathlib import Path

import pytest

from talemate.cultures.exchange import CultureFile
from talemate.cultures.models import (
    Culture,
    GlossaryEntry,
    GlossaryOrigin,
    Language,
    PlayAddition,
)
from talemate.cultures.store import WorldStore, world_dir_for_scene
from talemate.server.cultures import CulturesPlugin
from talemate.shared_context import SharedContext
from talemate.tale_mate import Scene

FIXTURE_PATH = (
    Path(__file__).parent.parent / "cultures" / "data" / "taelrik.culture.json"
)


def fixture_raw() -> str:
    return FIXTURE_PATH.read_text()


class _MockWebsocketHandler:
    """Minimal handler stand-in: exposes `scene` and a queue_put list."""

    def __init__(self, scene):
        self._scene = scene
        self.messages: list[dict] = []

    @property
    def scene(self):
        return self._scene

    def queue_put(self, data):
        self.messages.append(data)


@pytest.fixture
def isolated_scene(tmp_path, monkeypatch):
    """Real Scene whose save_dir lives under tmp_path."""
    monkeypatch.setattr(
        Scene, "scenes_dir", classmethod(lambda cls: str(tmp_path)), raising=True
    )
    scene = Scene()
    scene.project_name = "test_project"
    os.makedirs(scene.save_dir, exist_ok=True)
    return scene


@pytest.fixture
def scene_with_world(isolated_scene):
    world_path = Path(isolated_scene.save_dir) / "shared-context" / "world.json"
    isolated_scene.shared_context = SharedContext(filepath=world_path)
    return isolated_scene


@pytest.fixture
def plugin(scene_with_world):
    handler = _MockWebsocketHandler(scene=scene_with_world)
    return CulturesPlugin(handler)


def last_message(plugin: CulturesPlugin, action: str | None = None) -> dict:
    messages = plugin.websocket_handler.messages
    if action is None:
        return messages[-1]
    for msg in reversed(messages):
        if msg.get("action") == action:
            return msg
    raise AssertionError(f"no message with action {action!r} in {messages!r}")


def plugin_store(plugin: CulturesPlugin) -> WorldStore:
    return WorldStore(world_dir_for_scene(plugin.scene))


@pytest.mark.asyncio
async def test_no_shared_context_reports_unavailable(isolated_scene):
    handler = _MockWebsocketHandler(scene=isolated_scene)
    plug = CulturesPlugin(handler)

    await plug.handle_get_world({})

    assert handler.messages == [
        {"type": "cultures", "action": "world", "data": {"available": False}}
    ]


@pytest.mark.asyncio
async def test_get_world_empty(plugin):
    await plugin.handle_get_world({})

    msg = last_message(plugin, "world")
    assert msg["data"]["available"] is True
    assert msg["data"]["world_name"] == "world"
    assert msg["data"]["cultures"] == []
    assert msg["data"]["places"] == []
    assert msg["data"]["glossary"] == []


@pytest.mark.asyncio
async def test_import_apply_then_world_has_culture(plugin):
    await plugin.handle_import_apply({"content": fixture_raw()})

    world_msg = last_message(plugin, "world")
    names = [c["name"] for c in world_msg["data"]["cultures"]]
    assert names == ["Taelrik"]

    done = last_message(plugin, "operation_done")
    assert "error" not in done

    wd = world_dir_for_scene(plugin.scene)
    assert wd.name == "world.world"
    assert (wd / "cultures" / "taelrik.json").exists()
    assert (wd / "places.json").exists()
    assert (wd / "glossary.json").exists()


@pytest.mark.asyncio
async def test_save_place_rejects_cycle(plugin):
    await plugin.handle_save_place(
        {"place": {"id": "", "name": "A", "kind": "country"}}
    )
    place_a = next(
        p for p in last_message(plugin, "world")["data"]["places"] if p["name"] == "A"
    )

    await plugin.handle_save_place(
        {
            "place": {
                "id": "",
                "name": "B",
                "kind": "city",
                "parent_id": place_a["id"],
            }
        }
    )
    place_b = next(
        p for p in last_message(plugin, "world")["data"]["places"] if p["name"] == "B"
    )

    # Moving A under its own descendant B is a cycle.
    await plugin.handle_save_place(
        {
            "place": {
                "id": place_a["id"],
                "name": "A",
                "kind": "country",
                "parent_id": place_b["id"],
            }
        }
    )

    done = plugin.websocket_handler.messages[-1]
    assert done["action"] == "operation_done"
    assert "error" in done

    wd = world_dir_for_scene(plugin.scene)
    on_disk = json.loads((wd / "places.json").read_text())
    by_name = {p["name"]: p for p in on_disk["places"]}
    assert by_name["A"]["parent_id"] is None
    assert by_name["B"]["parent_id"] == place_a["id"]


@pytest.mark.asyncio
async def test_save_place_set_share_keeps_value_and_scales_rest(plugin):
    await plugin.handle_save_place(
        {
            "place": {
                "id": "",
                "name": "Dhunmouth",
                "kind": "city",
                "cultures": [
                    {"culture_id": "taelrik", "share": 55},
                    {"culture_id": "elsiri", "share": 30},
                    {"culture_id": "vaskari", "share": 15},
                ],
            }
        }
    )
    place = next(
        p
        for p in last_message(plugin, "world")["data"]["places"]
        if p["name"] == "Dhunmouth"
    )

    await plugin.handle_save_place(
        {
            "place": {"id": place["id"], "name": "Dhunmouth", "kind": "city"},
            "set_share": {"culture_id": "elsiri", "share": 50},
        }
    )

    updated = next(
        p
        for p in last_message(plugin, "world")["data"]["places"]
        if p["id"] == place["id"]
    )
    by_culture = {cs["culture_id"]: cs["share"] for cs in updated["cultures"]}
    assert by_culture["elsiri"] == 50
    assert sum(by_culture.values()) == 100
    # taelrik:vaskari were 55:15 and are scaled proportionally to fill 50.
    assert by_culture["taelrik"] > by_culture["vaskari"]


@pytest.mark.asyncio
async def test_save_glossary_entry_marks_owner_edit(plugin):
    store = plugin_store(plugin)
    store.save_glossary(
        [
            GlossaryEntry(
                id="g1",
                text="Veldhaer",
                language="taelrik",
                kind="place",
                meaning="old ford",
                origin=GlossaryOrigin(by="ai"),
                status="reviewed",
            )
        ]
    )

    await plugin.handle_save_glossary_entry(
        {
            "entry": {
                "id": "g1",
                "text": "Veldhaer",
                "language": "taelrik",
                "kind": "place",
                "meaning": "new meaning",
                "origin": {"by": "ai"},
                "status": "reviewed",
            }
        }
    )

    updated = next(e for e in store.load_glossary() if e.id == "g1")
    assert updated.edited_by_owner is True
    assert updated.meaning == "new meaning"


@pytest.mark.asyncio
async def test_roll_excludes_glossary_names(plugin, monkeypatch):
    await plugin.handle_import_apply({"content": fixture_raw()})

    def fake_roll(language, generator_id, count=20, rng=None, exclude=frozenset()):
        return ["Kethrun", "Brandnew"]

    monkeypatch.setattr("talemate.server.cultures.generator.roll", fake_roll)

    await plugin.handle_roll(
        {
            "culture_id": "taelrik",
            "generator_id": "given_male",
            "count": 5,
            "request_id": "req-123",
        }
    )

    msg = last_message(plugin, "rolled")
    assert msg["data"]["generator_id"] == "given_male"
    assert msg["data"]["names"] == ["Brandnew"]
    # The request id is echoed back unchanged, so the frontend can route the
    # reply to whichever widget asked for it.
    assert msg["data"]["request_id"] == "req-123"


@pytest.mark.asyncio
async def test_roll_request_id_defaults_to_none(plugin, monkeypatch):
    """`request_id` is optional, so callers that don't send one keep working."""
    await plugin.handle_import_apply({"content": fixture_raw()})

    def fake_roll(language, generator_id, count=20, rng=None, exclude=frozenset()):
        return ["Kethrun", "Brandnew"]

    monkeypatch.setattr("talemate.server.cultures.generator.roll", fake_roll)

    await plugin.handle_roll(
        {"culture_id": "taelrik", "generator_id": "given_male", "count": 5}
    )

    msg = last_message(plugin, "rolled")
    assert msg["data"]["request_id"] is None


@pytest.mark.asyncio
async def test_delete_culture_unassigns_entries(plugin):
    await plugin.handle_import_apply({"content": fixture_raw()})
    store = plugin_store(plugin)
    assert "taelrik" in store.load_cultures()

    await plugin.handle_delete_culture({"culture_id": "taelrik"})

    assert "taelrik" not in store.load_cultures()

    glossary = store.load_glossary()
    assert any(e.text == "Veldhaer" for e in glossary)
    assert all(e.language != "taelrik" for e in glossary)

    for place in store.load_places():
        assert all(cs.culture_id != "taelrik" for cs in place.cultures)


@pytest.mark.asyncio
async def test_addition_keep_edit_drop(plugin):
    store = plugin_store(plugin)
    store.save_culture(
        Culture(
            id="taelrik",
            name="Taelrik",
            language=Language(name="Taelrik", level="naming"),
            additions=[
                PlayAddition(
                    id="a1",
                    section="customs",
                    text="Spit for luck.",
                ),
                PlayAddition(
                    id="a2",
                    section="food",
                    text="Eel stew.",
                ),
                PlayAddition(
                    id="a3",
                    section="holidays",
                    text="Low Water.",
                ),
            ],
        )
    )

    await plugin.handle_addition(
        {"culture_id": "taelrik", "addition_id": "a1", "op": "keep"}
    )
    await plugin.handle_addition(
        {
            "culture_id": "taelrik",
            "addition_id": "a2",
            "op": "edit",
            "text": "Eel stew with reed beer.",
        }
    )
    await plugin.handle_addition(
        {"culture_id": "taelrik", "addition_id": "a3", "op": "drop"}
    )

    reloaded = store.load_cultures()["taelrik"]
    by_id = {a.id: a for a in reloaded.additions}
    assert by_id["a1"].status == "reviewed"
    assert by_id["a2"].status == "reviewed"
    assert by_id["a2"].text == "Eel stew with reed beer."
    assert "a3" not in by_id


@pytest.mark.asyncio
async def test_export_returns_content(plugin):
    await plugin.handle_import_apply({"content": fixture_raw()})

    await plugin.handle_export({"culture_id": "taelrik"})

    msg = last_message(plugin, "exported")
    assert msg["data"]["filename"] == "taelrik.culture.json"
    parsed = CultureFile.model_validate_json(msg["data"]["content"])
    assert parsed.culture.id == "taelrik"


def _culture_with_addition() -> Culture:
    return Culture(
        id="taelrik",
        name="Taelrik",
        description="River-folk.",
        customs=["Pay the ford."],
        language=Language(name="Taelrik", level="naming", sound="Clipped."),
        additions=[PlayAddition(id="a1", section="customs", text="Spit for luck.")],
        source_file="taelrik.culture.json",
        imported_at="2026-10-17",
    )


@pytest.mark.asyncio
async def test_save_culture_keeps_additions_and_source_from_disk(plugin):
    store = plugin_store(plugin)
    store.save_culture(_culture_with_addition())

    payload = _culture_with_addition().model_dump(mode="json")
    payload["description"] = "Changed."
    payload["additions"] = [
        {"id": "stale", "section": "food", "text": "Stale addition."}
    ]
    payload["source_file"] = "other.culture.json"
    payload["imported_at"] = "1999-01-01"

    await plugin.handle_save_culture({"culture": payload})

    saved = store.load_cultures()["taelrik"]
    assert saved.description == "Changed."
    assert [a.id for a in saved.additions] == ["a1"]
    assert saved.source_file == "taelrik.culture.json"
    assert saved.imported_at == "2026-10-17"


@pytest.mark.asyncio
async def test_patch_culture_touches_only_named_fields(plugin):
    store = plugin_store(plugin)
    store.save_culture(_culture_with_addition())

    await plugin.handle_patch_culture(
        {
            "culture_id": "taelrik",
            "culture": {"customs": ["New custom."]},
            "language": {"dictionary": [{"word": "dhaer", "meaning": "ford"}]},
        }
    )

    saved = store.load_cultures()["taelrik"]
    assert saved.customs == ["New custom."]
    assert [d.word for d in saved.language.dictionary] == ["dhaer"]
    # Everything not named in the patch is left as it was on disk.
    assert saved.description == "River-folk."
    assert saved.language.sound == "Clipped."
    assert [a.id for a in saved.additions] == ["a1"]
    assert saved.source_file == "taelrik.culture.json"
    assert "world" == last_message(plugin)["action"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "patch",
    [
        {"culture": {"additions": []}},
        {"culture": {"id": "other"}},
        {"culture": {"language": {}}},
        {"language": {"bogus": 1}},
    ],
)
async def test_patch_culture_refuses_fields_it_does_not_own(plugin, patch):
    store = plugin_store(plugin)
    store.save_culture(_culture_with_addition())

    await plugin.handle_patch_culture({"culture_id": "taelrik", **patch})

    done = last_message(plugin)
    assert done["action"] == "operation_done"
    assert "error" in done
    assert store.load_cultures()["taelrik"] == _culture_with_addition()


@pytest.mark.asyncio
async def test_patch_culture_unknown_culture(plugin):
    await plugin.handle_patch_culture(
        {"culture_id": "nope", "culture": {"description": "x"}}
    )
    done = last_message(plugin)
    assert done["action"] == "operation_done"
    assert "unknown culture" in done["error"]["message"]
