"""The `worlds` router's name-list actions (languages 4a, Task 1)."""

import pytest

import talemate.config.state as config_state
from talemate.languages.cleaning import lists
from talemate.server.worlds import WorldsPlugin


class _Handler:
    scene = None

    def __init__(self):
        self.messages: list[dict] = []

    def queue_put(self, data):
        self.messages.append(data)


@pytest.fixture
def plugin(tmp_path, monkeypatch):
    saved = config_state.get_config().name_lists
    monkeypatch.setattr(lists, "save_config", lambda: None)
    plug = WorldsPlugin(_Handler())
    plug.worlds_root = tmp_path
    yield plug
    plug.disconnect()
    config_state.get_config().name_lists = saved


def _last(plugin, action):
    found = [
        m
        for m in plugin.websocket_handler.messages
        if m["type"] == "worlds" and m["action"] == action
    ]
    assert found, plugin.websocket_handler.messages
    return found[-1]


async def _act(plugin, action, **data):
    await plugin.handle({"type": "worlds", "action": action, **data})


async def _edit(plugin, **data):
    """`name_list_edit`; its `edit` field names the change."""

    await plugin.handle({"type": "worlds", **data, "action": "name_list_edit"})


async def test_name_list_edit_answers_with_rows(plugin):
    await _act(plugin, "create_world", name="Vael")
    await _edit(plugin, edit="add", kind="real", name="Yelena")
    rows = _last(plugin, "name_list_edit")["data"]["rows"]
    assert {"name": "Yelena", "kind": "real", "scope": "world", "off": False} in rows
    await _act(plugin, "get_name_lists")
    assert _last(plugin, "get_name_lists")["data"]["rows"] == rows


async def test_an_unknown_kind_is_refused(plugin):
    await _act(plugin, "create_world", name="Vael")
    await _edit(plugin, edit="add", kind="fruit", name="Apple")
    errors = [
        m
        for m in plugin.websocket_handler.messages
        if m.get("action") == "operation_done" and "error" in m
    ]
    assert errors, plugin.websocket_handler.messages
