"""The `worlds` router and cleaning (languages 4a, Task 5): the browser
tests' fixed cleaning replies, and changing a draft's languages."""

import asyncio
import json
from types import SimpleNamespace

import pytest

import talemate.config.state as config_state
import talemate.instance as instance
from conftest import MockClient
from talemate.languages.entry import fields_of
from talemate.languages.models import GeneratorDef, Language
from talemate.server.worlds import WorldsPlugin
from talemate.world.store import Source

PLACES = ["Zizhigrad", "Sovyetsk", "Lezhograd"]
MOSCAVIAN = Language(
    name="Moscavian",
    level="naming",
    categories={"C": "k", "V": "a"},
    generators=[
        GeneratorDef(
            id="places", name="Places", use="place", patterns=[f"[{'|'.join(PLACES)}]"]
        ),
    ],
)
FIXED = {
    "name": "Tsardom of Moscavia",
    "facts": [{"category": "description", "text": "Fur caravans trade with Novgorod."}],
    "prose": {},
}
CLEAN = {
    "language-roles": {"languages": [{"language": "Moscavian", "role": "official"}]},
    "name-flags": {"names": []},
    "name-picks": {"picks": [{"n": 1, "pick": "Sovyetsk", "meaning": "owl town"}]},
}


class _Handler:
    scene = None

    def __init__(self):
        self.messages: list[dict] = []

    def queue_put(self, data):
        self.messages.append(data)


@pytest.fixture(autouse=True)
def shipped_lists():
    saved = config_state.get_config().name_lists
    config_state.get_config().name_lists = None
    yield
    config_state.get_config().name_lists = saved


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


async def _drain(plugin):
    while plugin.tasks:
        await asyncio.gather(*list(plugin.tasks), return_exceptions=True)


async def _setup(plugin, tmp_path, monkeypatch, prompt):
    await plugin.handle({"type": "worlds", "action": "create_world", "name": "Vael"})
    with plugin.world.revision(Source.manual()) as rev:
        lid = rev.create_thing(
            "language", {"name": "Moscavian", **fields_of(MOSCAVIAN)}
        )
    (tmp_path / "fixed.json").write_text(json.dumps(FIXED))
    (tmp_path / "clean.json").write_text(json.dumps(CLEAN))
    monkeypatch.setenv("TALEMATE_TEST_FIXED_PREVIEW", str(tmp_path / "fixed.json"))
    monkeypatch.setenv("TALEMATE_TEST_FIXED_CLEAN", str(tmp_path / "clean.json"))
    await plugin.handle(
        {
            "type": "worlds",
            "action": "preview_thing",
            "kind": "place",
            "prompt": prompt,
            "fields": {},
            "draft_key": "d1",
        }
    )
    await _drain(plugin)
    return lid


async def test_the_fixed_clean_file_answers_the_cleaning(plugin, tmp_path, monkeypatch):
    lid = await _setup(plugin, tmp_path, monkeypatch, "Tsardom of Moscavia")
    preview = _last(plugin, "preview_thing")["data"]["preview"]
    assert preview["facts"][0]["text"] == "Fur caravans trade with Sovyetsk."
    assert [m["was"] for m in preview["marks"]] == ["Novgorod"]
    assert preview["languages"] == [
        {"language": lid, "role": "official", "from_words": True}
    ]


async def test_changing_the_drafts_languages_cleans_it_again(
    plugin, tmp_path, monkeypatch
):
    lid = await _setup(plugin, tmp_path, monkeypatch, "a cold northern realm")
    preview = _last(plugin, "preview_thing")["data"]["preview"]
    assert [m["kind"] for m in preview["marks"]] == ["suspect"]
    await plugin.handle(
        {
            "type": "worlds",
            "action": "draft_languages",
            "draft_key": "d1",
            "preview": preview,
            "rows": [{"language": lid, "role": "official"}],
        }
    )
    await _drain(plugin)
    data = _last(plugin, "draft_languages")["data"]
    again = data["preview"]
    assert again["facts"][0]["text"] == "Fur caravans trade with Sovyetsk."
    assert [m["kind"] for m in again["marks"]] == ["replaced"]
    assert again["languages"] == [{"language": lid, "role": "official"}]
    assert data["version"] == 1 and len(data["versions"]) == 1


async def _languages(plugin, preview, rows):
    await plugin.handle(
        {
            "type": "worlds",
            "action": "draft_languages",
            "draft_key": "d1",
            "preview": preview,
            "rows": rows,
        }
    )
    await _drain(plugin)
    return _last(plugin, "draft_languages")["data"]["preview"]


async def test_a_name_kept_here_stays_kept_when_languages_change(
    plugin, tmp_path, monkeypatch
):
    """Final I4: "Keep Novgorod here", then a Languages change: Novgorod
    isn't replaced again."""

    lid = await _setup(plugin, tmp_path, monkeypatch, "Tsardom of Moscavia")
    preview = _last(plugin, "preview_thing")["data"]["preview"]
    kept = {
        **preview,
        "facts": [{**preview["facts"][0], "text": "Fur caravans trade with Novgorod."}],
        "marks": [],
        "new_names": [],
    }
    again = await _languages(plugin, kept, [{"language": lid, "role": "spoken"}])
    assert again["facts"][0]["text"] == "Fur caravans trade with Novgorod."
    assert again["marks"] == []


async def test_a_deleted_fact_stays_deleted_when_languages_change(
    plugin, tmp_path, monkeypatch
):
    """Final I5: a fact the owner removed doesn't come back."""

    lid = await _setup(plugin, tmp_path, monkeypatch, "Tsardom of Moscavia")
    preview = _last(plugin, "preview_thing")["data"]["preview"]
    extra = {**preview["facts"][0], "text": "The tsars hunt owls.", "removed": True}
    copy = {**preview, "facts": [preview["facts"][0], extra]}
    again = await _languages(plugin, copy, [{"language": lid, "role": "official"}])
    assert [f["text"] for f in again["facts"]] == ["Fur caravans trade with Sovyetsk."]
