"""The `worlds` router's Name it… actions (languages 4a revised, Tasks 3
and 4)."""

import asyncio
from types import SimpleNamespace

import pytest

import talemate.instance as instance
from conftest import MockClient
from talemate.languages.entry import fields_of
from talemate.languages.models import DictionaryEntry, GeneratorDef, Language
from talemate.server.worlds import WorldsPlugin
from talemate.world.store import Source

LANG = Language(
    name="Otsyenyan",
    level="full",
    categories={"C": "k v r s", "V": "a o"},
    generators=[
        GeneratorDef(id="words", name="Words", use="words", patterns=["CVCV"]),
        GeneratorDef(
            id="places",
            name="Place names",
            use="place",
            patterns=["CVCV[grad|gorsk]", "[kolva|syev]insk"],
        ),
    ],
    dictionary=[DictionaryEntry(word="syev", meanings=["grey"])],
)


class _Handler:
    scene = None

    def __init__(self):
        self.messages: list[dict] = []

    def queue_put(self, data):
        self.messages.append(data)


@pytest.fixture
def plugin(tmp_path):
    instance.AGENTS["creator"] = SimpleNamespace(client=MockClient("test"))
    plug = WorldsPlugin(_Handler())
    plug.worlds_root = tmp_path
    yield plug
    plug.disconnect()


def _last(plugin, action):
    found = [m for m in plugin.websocket_handler.messages if m.get("action") == action]
    assert found, plugin.websocket_handler.messages
    return found[-1]


async def _act(plugin, action, **data):
    await plugin.handle({"type": "worlds", "action": action, **data})
    while plugin.tasks:
        await asyncio.gather(*list(plugin.tasks), return_exceptions=True)


async def _world(plugin):
    await _act(plugin, "create_world", name="Test")
    with plugin.world.revision(Source.manual()) as rev:
        lid = rev.create_thing("language", {"name": "Otsyenyan", **fields_of(LANG)})
        rev.create_thing("place", {"name": "Kolvainsk"})
    return lid


async def test_name_it_actions_answer(plugin):
    lid = await _world(plugin)
    await _act(plugin, "name_it_rules", language_id=lid)
    rules = _last(plugin, "name_it_rules")["data"]["rules"]
    assert [r["id"] for r in rules] == ["words", "places"]
    await _act(plugin, "name_it_batch", language_id=lid, rule_id="places", pattern=1)
    names = [n["name"] for n in _last(plugin, "name_it_batch")["data"]["names"]]
    # the pattern's two names, less the entry the world has
    assert names == ["Syevinsk"]
    await _act(plugin, "name_it_meaning", language_id=lid, text="grey hill")
    data = _last(plugin, "name_it_meaning")["data"]
    assert data["candidates"][0]["built_from"][0] == {
        "word": "syev",
        "meaning": "grey",
        "new": False,
    }
