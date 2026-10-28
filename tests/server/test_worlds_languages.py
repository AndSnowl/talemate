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
