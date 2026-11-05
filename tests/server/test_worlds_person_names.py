"""The `worlds` router's people's-name actions (languages 4b-2, Task 3):
Use this name with parts, editing one part, "built as", titles, the kept
title offer, pet names, Name it's parts for a person, and the page's
`name_parts` and `calls`."""

import asyncio
from types import SimpleNamespace

import pytest

import talemate.instance as instance
from _people_names_helpers import DRASSONAIS
from conftest import MockClient
from talemate.languages.entry import fields_of
from talemate.server.worlds import WorldsPlugin
from talemate.world.store import Source


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
    assert found, plugin.websocket_handler.messages[-3:]
    return found[-1]


async def _act(plugin, action, **data):
    await plugin.handle({"type": "worlds", "action": action, **data})
    while plugin.tasks:
        await asyncio.gather(*list(plugin.tasks), return_exceptions=True)


def _parts(lang, *, house_from=None):
    return {
        "language": lang,
        "rule": "noble-women",
        "shape": 0,
        "built_as": {"sex": "woman", "rank": "noble"},
        "parts": [
            {"label": "given", "text": "Maëlis", "source": "rolled"},
            {"label": "of", "text": "di", "source": "word"},
            {
                "label": "house",
                "text": "Drassone",
                "source": "inherited" if house_from else "typed",
                **(
                    {"from_id": house_from, "from_role": "daughter of"}
                    if house_from
                    else {}
                ),
            },
        ],
    }


async def _world(plugin):
    """Drassonais; Eilhaud (a noble man of house Drassone), Tiboud, and
    Maëlis, Eilhaud's daughter, with her name in parts; Tiboud calls her
    Maë."""

    await _act(plugin, "create_world", name="Test")
    with plugin.world.revision(Source.manual()) as rev:
        lang = rev.create_thing(
            "language", {"name": "Drassonais", **fields_of(DRASSONAIS)}
        )
        eilhaud = rev.create_thing(
            "character",
            {
                "name": "Eilhaud of Drassone",
                "name_parts": {
                    **_parts(lang),
                    "rule": "noble-men",
                    "built_as": {"sex": "man", "rank": "noble"},
                    "parts": [
                        {"label": "given", "text": "Eilhaud", "source": "rolled"},
                        {"label": "of", "text": "di", "source": "word"},
                        {"label": "house", "text": "Drassone", "source": "typed"},
                    ],
                },
            },
        )
        tiboud = rev.create_thing("character", {"name": "Tiboud"})
        maelis = rev.create_thing(
            "character",
            {
                "name": "Maëlis of Drassone",
                "name_parts": _parts(lang, house_from=eilhaud),
                "filings": [{"target": eilhaud, "role": "daughter of"}],
                "aka": [
                    {
                        "name": "Maë",
                        "tag": "proper",
                        "everyday": False,
                        "kind": "own",
                        "by": tiboud,
                    },
                ],
            },
        )
        rev.add_fact(maelis, "relationship", f"Sister of [[thing:{tiboud}|Tiboud]]")
    return SimpleNamespace(lang=lang, eilhaud=eilhaud, tiboud=tiboud, maelis=maelis)


def _thing(plugin, thing_id):
    return plugin.world.view().thing(thing_id)


async def test_name_it_rename_writes_parts(plugin):
    w = await _world(plugin)
    parts = _parts(w.lang, house_from=w.eilhaud)["parts"]
    parts[0]["text"] = "Ysolde"
    await _act(
        plugin,
        "name_it_rename",
        thing_id=w.maelis,
        name="Ysolde of Drassone",
        language_id=w.lang,
        rule_id="noble-women",
        shape=0,
        built_as={"sex": "woman", "rank": "noble"},
        parts=parts,
    )
    stored = _thing(plugin, w.maelis).fields["name_parts"]
    assert stored["parts"][0]["text"] == "Ysolde"
    assert stored["parts"][2]["from_id"] == w.eilhaud
    assert (
        _last(plugin, "name_it_rename")["data"]["name_parts"]["rule"] == "noble-women"
    )


async def test_editing_a_part_renames_everywhere(plugin):
    w = await _world(plugin)
    with plugin.world.revision(Source.manual()) as rev:
        rev.add_fact(
            w.tiboud,
            "relationship",
            f"Brother of [[thing:{w.maelis}|Maëlis of Drassone]]",
        )
    await _act(plugin, "person_name_part", thing_id=w.maelis, index=0, text="Ysolde")
    state = _thing(plugin, w.maelis)
    assert state.fields["name"] == "Ysolde of Drassone"
    assert state.fields["name_parts"]["parts"][0] == {
        "label": "given",
        "text": "Ysolde",
        "source": "typed",
    }
    assert "Ysolde of Drassone" in _thing(plugin, w.tiboud).facts[0].text


async def test_a_hand_rename_clears_parts_and_name_it_starts_fresh(plugin):
    w = await _world(plugin)
    await _act(
        plugin, "set_field", thing_id=w.maelis, field="name", value="Maëlis the Red"
    )
    assert "name_parts" not in _thing(plugin, w.maelis).fields
    await _act(
        plugin,
        "name_it_parts",
        language_id=w.lang,
        rule_id="noble-women",
        thing_id=w.maelis,
    )
    parts = _last(plugin, "name_it_parts")["data"]["parts"]
    assert [p["pinned"] for p in parts] == [False, False, True]
    assert parts[2]["source"] == "inherited" and parts[2]["from_id"] == w.eilhaud


async def test_name_it_parts_picks_the_rule_for_the_person(plugin):
    w = await _world(plugin)
    await _act(plugin, "name_it_parts", language_id=w.lang, thing_id=w.maelis)
    assert _last(plugin, "name_it_parts")["data"]["rule_id"] == "noble-women"


async def test_name_it_parts_for_a_draft(plugin):
    w = await _world(plugin)
    await _act(
        plugin,
        "name_it_parts",
        language_id=w.lang,
        draft={
            "filings": [[w.eilhaud, "daughter of"]],
            "facts": [],
            "built_as": {"sex": "woman", "rank": "noble"},
        },
    )
    data = _last(plugin, "name_it_parts")["data"]
    assert data["rule_id"] == "noble-women"
    assert data["parts"][2]["rolls"][0]["text"] == "Drassone"


async def test_built_as_is_stored_through_the_choices(plugin):
    w = await _world(plugin)
    await _act(
        plugin,
        "person_built_as",
        thing_id=w.maelis,
        built_as={"sex": "woman", "rank": "duchess"},
    )
    assert _thing(plugin, w.maelis).fields["name_parts"]["built_as"] == {
        "sex": "woman",
        "rank": "common",
    }
    assert _thing(plugin, w.maelis).fields["name"] == "Maëlis of Drassone"


async def test_a_shown_title_replaces_the_last(plugin):
    w = await _world(plugin)
    await _act(
        plugin, "person_title_add", thing_id=w.maelis, name="Lady", shown="before"
    )
    await _act(
        plugin, "person_title_add", thing_id=w.maelis, name="Warden", shown="after"
    )
    titles = [
        a for a in _thing(plugin, w.maelis).fields["aka"] if a.get("kind") == "title"
    ]
    assert [(t["name"], t.get("shown")) for t in titles] == [
        ("Lady", None),
        ("Warden", "after"),
    ]
    await _act(plugin, "person_title_remove", thing_id=w.maelis, name="Lady")
    titles = [
        a for a in _thing(plugin, w.maelis).fields["aka"] if a.get("kind") == "title"
    ]
    assert [t["name"] for t in titles] == ["Warden"]


async def test_kept_title_is_offered_not_applied(plugin):
    w = await _world(plugin)
    await _act(plugin, "person_kept_title", thing_id=w.maelis, english="Emperor")
    assert _last(plugin, "person_kept_title")["data"] == {
        "english": "Emperor",
        "word": "Tsar",
        "language_id": w.lang,
    }
    assert not any(
        a.get("kind") == "title" for a in _thing(plugin, w.maelis).fields.get("aka", [])
    )
    await _act(plugin, "person_kept_title", thing_id=w.maelis, english="King")
    assert _last(plugin, "person_kept_title")["data"]["word"] is None


async def test_pet_name_rolls_from_the_rule_and_sets_per_person(plugin):
    w = await _world(plugin)
    await _act(plugin, "person_pet_name", thing_id=w.maelis, mode="roll")
    pets = [a for a in _thing(plugin, w.maelis).fields["aka"] if a.get("kind") == "pet"]
    assert pets == [
        {
            "name": "Maëlisette",
            "tag": "proper",
            "everyday": False,
            "kind": "pet",
            "rule": "pets",
        }
    ]
    await _act(
        plugin,
        "person_pet_name",
        thing_id=w.maelis,
        mode="set",
        name="Mimi",
        by=w.tiboud,
    )
    own = [a for a in _thing(plugin, w.maelis).fields["aka"] if a.get("kind") == "own"]
    assert [(a["name"], a["by"]) for a in own] == [("Mimi", w.tiboud)]


async def test_page_carries_calls_and_fact_refs(plugin):
    w = await _world(plugin)
    await _act(plugin, "get_thing", id=w.maelis)
    page = _last(plugin, "get_thing")["data"]
    assert page["name_parts"]["rule"] == "noble-women"
    assert page["calls"] == [
        {
            "name": "Maë",
            "kind": "own",
            "by": w.tiboud,
            "by_name": "Tiboud",
            "rule": "",
            "meaning": "",
        }
    ]
    assert page["facts"][0]["refs"] == [w.tiboud]


async def test_calls_drop_a_deleted_caller(plugin):
    w = await _world(plugin)
    with plugin.world.revision(Source.manual()) as rev:
        rev.remove_thing(w.tiboud)
    await _act(plugin, "get_thing", id=w.maelis)
    assert _last(plugin, "get_thing")["data"]["calls"] == []


async def test_page_carries_a_name_view(plugin):
    w = await _world(plugin)
    await _act(plugin, "get_thing", id=w.maelis)
    view = _last(plugin, "get_thing")["data"]["name_view"]
    assert view["language"] == {"id": w.lang, "name": "Drassonais"}
    assert view["rule"] == "noble-women"
    assert view["built_as"] == {"sex": "woman", "rank": "noble"}
    assert view["choices"] == {"sex": ["man", "woman"], "rank": ["common", "noble"]}
    assert [p["written"] for p in view["parts"]] == ["Maëlis", "of", "Drassone"]
    assert view["sources"] == {w.eilhaud: {"name": "Eilhaud of Drassone", "sex": "man"}}
    assert view["pet_used_by"] == ["family"]


async def test_a_person_without_parts_has_no_name_view_but_its_language(plugin):
    w = await _world(plugin)
    await _act(plugin, "get_thing", id=w.tiboud)
    assert _last(plugin, "get_thing")["data"]["name_view"] is None
