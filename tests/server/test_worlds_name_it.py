"""The `worlds` router's Name it… actions (languages 4a revised, Tasks 3
and 4)."""

import asyncio
from types import SimpleNamespace

import pytest

import talemate.instance as instance
from conftest import MockClient
from talemate.languages.entry import fields_of
from talemate.languages.models import (
    DictionaryEntry,
    FormChange,
    GeneratorDef,
    Language,
    NameGrammar,
    NamePart,
    NameShape,
    OfRule,
)
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
    # built by the engine (languages 4b-1): each word with its steps
    assert data["candidates"][0]["built_from"][0] == {
        "word": "syev",
        "meaning": "grey",
        "new": False,
        "steps": [],
    }


async def _rename_world(plugin):
    await _act(plugin, "create_world", name="Test")
    with plugin.world.revision(Source.manual()) as rev:
        city = rev.create_thing("place", {"name": "Tsargrad"})
        stub = rev.create_thing(
            "place", {"name": "Novgorod", "stub": {"ignored": False}}
        )
        rev.create_thing("place", {"name": "Velgrad"})
        realm = rev.create_thing("place", {"name": "Otsyenya"})
        rev.add_fact(realm, "general", f"Its capital is [[thing:{city}|Tsargrad]].")
    return city, stub, realm


async def test_renaming_an_entry_keeps_the_old_name_as_another_name(plugin):
    city, _stub, realm = await _rename_world(plugin)
    await _act(plugin, "name_it_rename", thing_id=city, name="Khyagovsk")
    view = plugin.world.view()
    assert view.name_of(city) == "Khyagovsk"
    assert [a["name"] for a in view.thing(city).fields["aka"]] == ["Tsargrad"]
    # the words linking it say the new name
    [fact] = view.thing(realm).facts
    assert fact.text == f"Its capital is [[thing:{city}|Khyagovsk]]."


async def test_renaming_a_stub_forgets_the_old_name(plugin):
    _city, stub, _realm = await _rename_world(plugin)
    await _act(plugin, "name_it_rename", thing_id=stub, name="Sovyetsk")
    view = plugin.world.view()
    assert view.name_of(stub) == "Sovyetsk"
    assert not view.thing(stub).fields.get("aka")


async def test_a_name_in_use_is_refused(plugin):
    city, _stub, _realm = await _rename_world(plugin)
    head = plugin.world.head_rev()
    await _act(plugin, "name_it_rename", thing_id=city, name="Velgrad")
    errors = [
        m
        for m in plugin.websocket_handler.messages
        if m.get("action") == "operation_done" and "error" in m
    ]
    assert errors and plugin.world.head_rev() == head


async def test_removing_an_other_name_rewrites_its_links_to_the_full_name(plugin):
    """Owner's run (Test3): removing "Drassone" from the Principality of
    Drassone's other names rewrites the facts that wrote it to the full
    name, so "Drassone" is free for the capital."""

    await _act(plugin, "create_world", name="Test")
    with plugin.world.revision(Source.manual()) as rev:
        land = rev.create_thing(
            "place",
            {
                "name": "Principality of Drassone",
                "aka": [
                    {"name": "Drassone", "tag": "common", "everyday": True},
                    {"name": "the Principality", "tag": "common", "everyday": False},
                ],
            },
        )
        rev.add_fact(land, "general", "Drassone is cold; the Principality is old.")
        river = rev.create_thing("place", {"name": "Vell"})
        rev.add_fact(
            river,
            "general",
            f"The Vell flows through [[thing:{land}|Drassone]] and"
            f" [[thing:{land}|the Principality]].",
        )
    await _act(
        plugin,
        "set_field",
        thing_id=land,
        field="aka",
        value=[{"name": "the Principality", "tag": "common", "everyday": False}],
    )
    view = plugin.world.view()
    [fact] = view.thing(river).facts
    assert fact.text == (
        f"The Vell flows through [[thing:{land}|Principality of Drassone]] and"
        f" [[thing:{land}|the Principality]]."
    )
    # its own facts write it plain: those words say the full name too
    [own] = view.thing(land).facts
    assert own.text == "Principality of Drassone is cold; the Principality is old."


async def test_a_batch_echoes_its_slot(plugin):
    """Owner's run (Test3): one coined word's rolls come back to its slot."""

    language = await _world(plugin)
    await _act(
        plugin,
        "name_it_batch",
        language_id=language,
        rule_id="words",
        count=4,
        slot="0:1",
    )
    assert _last(plugin, "name_it_batch")["data"]["slot"] == "0:1"


# --- the builder (languages 4b-1, Task 6) ------------------------------------

OWL_LANG = LANG.model_copy(
    update={
        "generators": [
            *LANG.generators,
            GeneratorDef(
                id="men",
                name="Men's names",
                use="character",
                patterns=["[dorvak|zemol]"],
            ),
            GeneratorDef(
                id="owl",
                name="Owl-names",
                use="character",
                shapes=[
                    NameShape(
                        parts=[
                            NamePart(kind="rule", rule="men"),
                            NamePart(kind="word", word="Ul"),
                            NamePart(kind="meaning", forms=["more_than_one"]),
                        ]
                    )
                ],
            ),
        ],
        "dictionary": [
            DictionaryEntry(word="syev", meanings=["grey"], part="adjective"),
            DictionaryEntry(word="zvesk", meanings=["star"], part="noun"),
        ],
        "name_grammar": NameGrammar(
            of=OfRule(text="ul"), more_than_one=[FormChange(kind="ending", text="i")]
        ),
    }
)


async def _owl_world(plugin):
    await _act(plugin, "create_world", name="Test")
    with plugin.world.revision(Source.manual()) as rev:
        lid = rev.create_thing("language", {"name": "Otsyenyan", **fields_of(OWL_LANG)})
        dorvak = rev.create_thing("character", {"name": "Dorvak"})
        rev.add_fact(dorvak, "personality", "Dorvak watches the stars every night.")
    return lid, dorvak


async def test_name_it_parts_answers_without_a_model(plugin):
    lid, _ = await _owl_world(plugin)
    await _act(
        plugin, "name_it_parts", language_id=lid, rule_id="owl", pinned={"0": "Dorvak"}
    )
    data = _last(plugin, "name_it_parts")["data"]
    assert (
        data["language_id"] == lid and data["rule_id"] == "owl" and data["shape"] == 0
    )
    parts = data["parts"]
    assert [r["text"] for r in parts[0]["rolls"]] == ["Dorvak"] and parts[0]["pinned"]
    assert parts[2]["rolls"][0]["text"] == "Zveski"


async def test_name_it_meaning_with_a_rule_fills_the_meaning_part(plugin):
    lid, _ = await _owl_world(plugin)
    await _act(plugin, "name_it_meaning", language_id=lid, text="stars", rule_id="owl")
    data = _last(plugin, "name_it_meaning")["data"]
    assert data["rule_id"] == "owl"
    assert data["parts"][2]["rolls"][0]["text"] == "Zveski"


async def test_name_it_suggest_builds_from_the_entrys_facts(plugin, monkeypatch):
    lid, dorvak = await _owl_world(plugin)
    monkeypatch.setattr(
        WorldsPlugin, "_language_reply", lambda self: (None, '{"noun": "stars"}')
    )
    await _act(
        plugin, "name_it_suggest", language_id=lid, rule_id="owl", thing_id=dorvak
    )
    data = _last(plugin, "name_it_suggest")["data"]
    assert data["thing_id"] == dorvak
    assert data["parts"][2]["rolls"][0]["text"] == "Zveski"
