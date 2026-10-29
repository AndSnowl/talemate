"""The `worlds` router's language actions (languages 3a)."""

import json
from types import SimpleNamespace

import pytest

import talemate.instance as instance
from talemate.languages.models import (
    DictionaryEntry,
    GeneratorDef,
    Language,
    LanguageFile,
)
from talemate.server.worlds import WorldsPlugin
from talemate.world.store import World

from conftest import MockClient


class _Handler:
    scene = None

    def __init__(self):
        self.messages: list[dict] = []

    def queue_put(self, data):
        self.messages.append(data)


@pytest.fixture
def client():
    mock = MockClient("test")
    instance.AGENTS["creator"] = SimpleNamespace(client=mock)
    return mock


@pytest.fixture
def plugin(tmp_path, client):
    plug = WorldsPlugin(_Handler())
    plug.worlds_root = tmp_path
    yield plug
    plug.disconnect()


def _replies(plugin, action):
    return [
        m
        for m in plugin.websocket_handler.messages
        if m["type"] == "worlds" and m["action"] == action
    ]


def _last(plugin, action):
    replies = _replies(plugin, action)
    assert replies, f"no {action!r} reply in {plugin.websocket_handler.messages}"
    return replies[-1]


def _errors(plugin):
    return [m for m in _replies(plugin, "operation_done") if "error" in m]


async def _act(plugin, action, **data):
    await plugin.handle({"type": "worlds", "action": action, **data})


def _file_text(reject=()):
    lang = Language(
        name="Moscavian",
        level="full",
        categories={"C": "k v r s l", "V": "a o e u"},
        generators=[
            GeneratorDef(
                id="w", name="Words", use="words", patterns=["CVC"], reject=list(reject)
            ),
            GeneratorDef(id="p", name="Places", use="places", patterns=["CVCVC"]),
        ],
        dictionary=[DictionaryEntry(word="vel", meaning="great")],
    )
    return (
        "Here it is:\n```json\n"
        + LanguageFile(language=lang).model_dump_json()
        + "\n```"
    )


async def _open(plugin):
    await _act(plugin, "create_world", name="Vael")
    return plugin.world


async def test_language_preview_and_import_handlers(plugin):
    world = await _open(plugin)
    await _act(plugin, "language_preview", text=_file_text())
    preview = _last(plugin, "language_preview")["data"]
    assert preview["report"]["blocking"] == [] and preview["ok"]
    assert (
        "No problems" in preview["repair_note"]
        or "Worth fixing" in preview["repair_note"]
    )
    assert preview["file"]["language"]["name"] == "Moscavian"

    await _act(plugin, "language_import", text=_file_text())
    imported = _last(plugin, "language_import")["data"]
    state = world.view().thing(imported["id"])
    assert state.kind == "language" and state.fields["words"][0]["word"] == "vel"


async def test_language_import_refuses_blocking(plugin):
    world = await _open(plugin)
    head = world.head_rev()
    await _act(plugin, "language_preview", text=_file_text(reject=["("]))
    assert not _last(plugin, "language_preview")["data"]["ok"]
    await _act(plugin, "language_import", text=_file_text(reject=["("]))
    assert _errors(plugin) and world.head_rev() == head


async def test_language_preview_of_junk_is_a_plain_error(plugin):
    await _open(plugin)
    await _act(plugin, "language_preview", text="sorry, I can't")
    (error,) = _errors(plugin)
    assert "no language" in error["error"]["message"]


async def test_language_export_and_samples(plugin):
    world = await _open(plugin)
    await _act(plugin, "language_import", text=_file_text())
    lid = _last(plugin, "language_import")["data"]["id"]
    await _act(plugin, "language_export", thing_id=lid)
    exported = json.loads(_last(plugin, "language_export")["data"]["text"])
    assert exported["language"]["name"] == "Moscavian"
    await _act(plugin, "language_samples", thing_id=lid, seed=3)
    samples = _last(plugin, "language_samples")["data"]
    assert samples["thing_id"] == lid and len(samples["samples"]["p"]) == 20
    assert world.view().thing(lid) is not None


# --- naming (Task 7) ----------------------------------------------------------

import asyncio  # noqa: E402

from conftest import MockClientContext, client_responses  # noqa: E402
from talemate.world.store import Source  # noqa: E402


async def _drain(plugin):
    while plugin.tasks:
        await asyncio.gather(*list(plugin.tasks), return_exceptions=True)


async def _sorau_world(plugin):
    world = await _open(plugin)
    await _act(plugin, "language_import", text=_file_text())
    lid = _last(plugin, "language_import")["data"]["id"]
    with world.revision(Source.manual()) as rev:
        sorau = rev.create_thing(
            "place",
            {
                "name": "Free Provinces of Sorau",
                "languages": [{"language": lid, "role": "official"}],
            },
        )
        town = rev.create_thing(
            "place", {"name": "Thornfield", "filings": [{"target": sorau}]}
        )
    return world, lid, sorau, town


async def test_language_menu_lists_languages_in_reach(plugin):
    world, lid, sorau, town = await _sorau_world(plugin)
    await _act(plugin, "language_menu", thing_id=town)
    menu = _last(plugin, "language_menu")["data"]
    assert menu["default"] == lid
    assert [r["language_id"] for r in menu["rows"]] == [lid]
    assert [lang["id"] for lang in menu["languages"]] == [lid]
    await _act(plugin, "language_menu")
    assert _last(plugin, "language_menu")["data"]["default"] is None


async def test_language_names_rolls_and_defines(plugin, client):
    world, lid, sorau, town = await _sorau_world(plugin)
    async with MockClientContext():
        client_responses.get().append(json.dumps({"definitions": {}}))
        await _act(
            plugin, "language_names", language_id=lid, kind="place", count=4, seed=2
        )
        await _drain(plugin)
    names = _last(plugin, "language_names")["data"]
    assert names["language_id"] == lid and len(names["names"]) == 4
    assert all(set(n) == {"name", "definition"} for n in names["names"])


async def test_language_add_word_and_name_in(plugin, client):
    world, lid, sorau, town = await _sorau_world(plugin)
    await _act(
        plugin, "language_add_word", language_id=lid, word="sorau", meaning="free land"
    )
    words = {w["word"] for w in world.view().thing(lid).fields["words"]}
    assert "sorau" in words

    async with MockClientContext():
        queued = client_responses.get()
        queued.extend([json.dumps({"pick": "", "why": ""})] * 3)
        await _act(plugin, "language_name_in", thing_id=sorau, language_id=lid)
        await _drain(plugin)
        # "Free" and "Provinces" each take a pick; don't leak the spare
        # reply into the next test's shared queue
        queued.clear()
    result = _last(plugin, "language_name_in")["data"]
    assert result["thing_id"] == sorau and result["result"]["name"].endswith("Sorau")

    await _act(
        plugin,
        "language_apply_name_in",
        thing_id=sorau,
        language_id=lid,
        result=result["result"],
    )
    aka = world.view().thing(sorau).fields["aka"]
    assert aka[-1]["language"] == lid and aka[-1]["name"] == result["result"]["name"]


# --- Languages sections (Task 10) --------------------------------------------


async def test_thing_payload_includes_languages_view(plugin):
    world, lid, sorau, town = await _sorau_world(plugin)
    await _act(plugin, "get_thing", id=town)
    page = _last(plugin, "get_thing")["data"]
    rows = page["languages_view"]
    assert [(r["language_id"], r["role"], r["inherited"]) for r in rows] == [
        (lid, "official", True)
    ]
    assert rows[0]["source_id"] == sorau and rows[0]["name"] == "Moscavian"
    assert rows[0]["source_name"] == "Free Provinces of Sorau"
    assert page["languages_source_name"] == "Free Provinces of Sorau"


async def test_thing_payload_names_own_rows_and_deleted_languages(plugin):
    world, lid, sorau, town = await _sorau_world(plugin)
    await _act(plugin, "get_thing", id=sorau)
    own = _last(plugin, "get_thing")["data"]["languages_own"]
    assert own == [{"language": lid, "role": "official", "name": "Moscavian"}]
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(lid)
    await _act(plugin, "get_thing", id=sorau)
    page = _last(plugin, "get_thing")["data"]
    assert page["languages_own"][0]["name"] is None
    assert page["languages_view"] == []


async def test_set_field_clears_a_language_parent(plugin):
    world, lid, sorau, town = await _sorau_world(plugin)
    with world.revision(Source.manual()) as rev:
        old = rev.create_thing("language", {"name": "Old Moscavian"})
    await _act(plugin, "set_field", thing_id=lid, field="descends_from", value=old)
    assert world.view().thing(lid).fields["descends_from"] == old
    await _act(plugin, "set_field", thing_id=lid, field="descends_from", value=None)
    assert not _errors(plugin)
    assert "descends_from" not in world.view().thing(lid).fields


async def test_language_names_without_a_client_come_without_definitions(plugin):
    world, lid, sorau, town = await _sorau_world(plugin)
    instance.AGENTS["creator"] = SimpleNamespace(client=None)
    await _act(plugin, "language_names", language_id=lid, kind="place", count=4, seed=2)
    await _drain(plugin)
    names = _last(plugin, "language_names")["data"]["names"]
    assert len(names) == 4 and all(n["definition"] == "" for n in names)


# --- the scene's message box (Task 12) ---------------------------------------


async def test_scene_menu_uses_speaker_then_place(plugin):
    world, lid, sorau, town = await _sorau_world(plugin)
    with world.revision(Source.manual()) as rev:
        other = rev.create_thing("language", {"name": "Old Moscavian"})
        ivan = rev.create_thing(
            "character",
            {"name": "Ivan", "languages": [{"language": other, "role": "spoken"}]},
        )
    plugin.websocket_handler.scene = SimpleNamespace(
        cancel_requested=False,
        world_context=SimpleNamespace(
            world=world,
            record=SimpleNamespace(
                player_thing_id=ivan, state={"place_thing_id": town}
            ),
        ),
    )
    await _act(plugin, "language_menu", scene=True)
    menu = _last(plugin, "language_menu")["data"]
    assert [r["language_id"] for r in menu["rows"]] == [other, lid]
    assert menu["scene"] is True and menu["default"] == other


async def test_scene_menu_without_a_world_scene_is_empty(plugin):
    await _open(plugin)
    plugin.websocket_handler.scene = SimpleNamespace(cancel_requested=False)
    await _act(plugin, "language_menu", scene=True)
    menu = _last(plugin, "language_menu")["data"]
    assert menu["rows"] == [] and menu["languages"] == []


# --- review fixes ---------------------------------------------------------------


async def test_scene_naming_uses_the_scenes_world_not_the_open_one(plugin, tmp_path):
    opened, lid, sorau, town = await _sorau_world(plugin)
    # a loaded scene holds its own handle on its world (opening another
    # world in the Worlds tab closes the tab's)
    scene_world = World.open(opened.path)
    plugin.websocket_handler.scene = SimpleNamespace(
        cancel_requested=False,
        world_context=SimpleNamespace(
            world=scene_world,
            record=SimpleNamespace(
                player_thing_id=None, state={"place_thing_id": town}
            ),
        ),
    )
    await _act(plugin, "create_world", name="Another")  # now the open world
    assert plugin.world is not scene_world
    await _act(
        plugin,
        "language_names",
        language_id=lid,
        kind="place",
        count=2,
        seed=1,
        scene=True,
    )
    await _drain(plugin)
    assert len(_last(plugin, "language_names")["data"]["names"]) == 2
    await _act(
        plugin,
        "language_add_word",
        language_id=lid,
        word="kolo",
        meaning="wheel",
        scene=True,
    )
    assert not _errors(plugin)
    assert "kolo" in {w["word"] for w in scene_world.view().thing(lid).fields["words"]}


async def test_menu_marks_languages_without_name_rules(plugin):
    world, lid, sorau, town = await _sorau_world(plugin)
    with world.revision(Source.manual()) as rev:
        silent = rev.create_thing(
            "language", {"name": "Whistle", "depth": "description"}
        )
    await _act(plugin, "language_menu")
    languages = {
        lang["id"]: lang for lang in _last(plugin, "language_menu")["data"]["languages"]
    }
    assert languages[lid]["has_names"] is True
    assert languages[silent]["has_names"] is False


async def test_suggest_definition_without_a_client_is_empty(plugin):
    world, lid, sorau, town = await _sorau_world(plugin)
    instance.AGENTS["creator"] = SimpleNamespace(client=None)
    await _act(plugin, "language_suggest_definition", language_id=lid, word="Moscavia")
    await _drain(plugin)
    assert not _errors(plugin)
    assert _last(plugin, "language_definition")["data"]["definition"] == ""


async def test_a_language_page_carries_its_words_uses_as_names(plugin):
    world, lid, sorau, town = await _sorau_world(plugin)
    await _act(plugin, "language_add_word", language_id=lid, word="Soru", meaning="wind")
    with world.revision(Source.manual()) as rev:
        soru = rev.create_thing("character", {"name": "Soru"})
    await _act(plugin, "get_thing", id=lid)
    page = _last(plugin, "get_thing")["data"]
    assert page["word_uses"] == {"soru": [{"id": soru, "name": "Soru", "kind": "character"}]}


async def test_definitions_ask_the_language_agents_client(plugin):
    # the language agent's client answers; the creator has none
    world, lid, sorau, town = await _sorau_world(plugin)
    instance.AGENTS["creator"] = SimpleNamespace(client=None)
    instance.AGENTS["language"] = SimpleNamespace(client=MockClient("language"))
    try:
        async with MockClientContext():
            client_responses.get().append(json.dumps({"definitions": {"vel": "wind"}}))
            await _act(plugin, "language_suggest_definition", language_id=lid, word="vel")
            await _drain(plugin)
    finally:
        instance.AGENTS.pop("language", None)
    assert _last(plugin, "language_definition")["data"]["definition"] == "wind"
