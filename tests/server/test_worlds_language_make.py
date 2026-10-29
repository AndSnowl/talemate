"""Making a language from the worlds screen: the brief, progress, cancel
(languages 3b-1, Task 6). Claude Code is the fake in tests/languages/data."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

import talemate.instance as instance
from talemate.languages.importer import parse_language_text
from talemate.languages.making import MakeSettings
from talemate.server.worlds import CLAUDE_COMMAND_ENV, FIXED_LANGUAGE_ENV, WorldsPlugin

from conftest import MockClient

FAKE = Path("tests/languages/data/fake-claude").resolve()
REQUEST = "a unique but recognizably Russian language"


class _Handler:
    scene = None

    def __init__(self):
        self.messages: list[dict] = []

    def queue_put(self, data):
        self.messages.append(data)


@pytest.fixture
def plugin(tmp_path, monkeypatch):
    instance.AGENTS["creator"] = SimpleNamespace(client=MockClient("test"))
    instance.AGENTS["language"] = SimpleNamespace(
        client=None, make_settings=lambda: MakeSettings(route="claude_code")
    )
    monkeypatch.setenv(CLAUDE_COMMAND_ENV, str(FAKE))
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")
    plug = WorldsPlugin(_Handler())
    plug.worlds_root = tmp_path
    yield plug
    plug.disconnect()
    instance.AGENTS.pop("language", None)


def _replies(plugin, action):
    return [
        m["data"]
        for m in plugin.websocket_handler.messages
        if m["type"] == "worlds" and m["action"] == action
    ]


async def _act(plugin, action, **data):
    await plugin.handle({"type": "worlds", "action": action, **data})


async def _drain(plugin):
    while plugin.tasks:
        await asyncio.gather(*list(plugin.tasks), return_exceptions=True)


async def _open(plugin):
    await _act(plugin, "create_world", name="Vael")


async def test_brief_reply_carries_the_request(plugin):
    await _open(plugin)
    await _act(plugin, "language_brief", text=REQUEST, decide_for_me=True)
    text = _replies(plugin, "language_brief")[-1]["text"]
    assert REQUEST in text and "decide for me" in text
    assert "./check" not in text


async def test_make_with_claude_code_runs_the_fake(plugin):
    await _open(plugin)
    await _act(plugin, "language_make_start", text=REQUEST)
    await _drain(plugin)
    assert _replies(plugin, "language_make_started")[-1]["route"] == "claude_code"
    lines = [r["line"] for r in _replies(plugin, "language_make_progress")]
    assert "Running the check" in lines
    done = _replies(plugin, "language_make_done")[-1]
    assert parse_language_text(done["text"]).language.name


async def test_make_in_app_sends_progress_then_done(plugin, tmp_path, monkeypatch):
    sample = Path("tests/languages/data/sample.language.json").read_text()
    fixed = tmp_path / "fixed-language.json"
    import json

    fixed.write_text(json.dumps({"language_file": sample}))
    monkeypatch.setenv(FIXED_LANGUAGE_ENV, str(fixed))
    instance.AGENTS["language"].make_settings = lambda: MakeSettings(route="in_app")
    await _open(plugin)
    await _act(plugin, "language_make_start", text=REQUEST)
    await _drain(plugin)
    lines = [r["line"] for r in _replies(plugin, "language_make_progress")]
    assert lines[0] == "Asking the model"
    assert _replies(plugin, "language_make_done")


async def test_a_second_make_is_refused_while_one_runs(plugin, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "slow")
    await _open(plugin)
    await _act(plugin, "language_make_start", text=REQUEST)
    await asyncio.sleep(0.5)
    await _act(plugin, "language_make_start", text=REQUEST)
    failed = _replies(plugin, "language_make_failed")
    assert failed and failed[-1]["error"] == "A language is already being made"
    assert plugin._make_task is not None and not plugin._make_task.done()
    await _act(plugin, "language_make_cancel")
    await _drain(plugin)


async def test_cancel_stops_the_job_without_a_done(plugin, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "slow")
    await _open(plugin)
    await _act(plugin, "language_make_start", text=REQUEST)
    for _ in range(100):
        if _replies(plugin, "language_make_progress"):
            break
        await asyncio.sleep(0.1)
    await _act(plugin, "language_make_cancel")
    await _drain(plugin)
    assert _replies(plugin, "language_make_cancelled")
    assert not _replies(plugin, "language_make_done")
    assert not _replies(plugin, "language_make_failed")
    assert plugin._make_task is None


async def test_a_failed_route_reports_its_message(plugin, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "error")
    await _open(plugin)
    await _act(plugin, "language_make_start", text=REQUEST)
    await _drain(plugin)
    error = _replies(plugin, "language_make_failed")[-1]["error"]
    assert error == "Claude Code stopped: You've hit your usage limit."


async def test_make_needs_an_open_world(plugin):
    await _act(plugin, "language_make_start", text=REQUEST)
    assert _replies(plugin, "language_make_failed")[-1]["error"] == "Open a world first"


async def test_a_world_closed_mid_run_still_gets_the_text(plugin, monkeypatch):
    await _open(plugin)
    await _act(plugin, "language_make_start", text=REQUEST)
    plugin._set_world(None)
    await _drain(plugin)
    assert _replies(plugin, "language_make_done")


async def test_disconnecting_stops_the_job(plugin, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "slow")
    await _open(plugin)
    await _act(plugin, "language_make_start", text=REQUEST)
    task = plugin._make_task
    for _ in range(100):
        if _replies(plugin, "language_make_progress"):
            break
        await asyncio.sleep(0.1)
    plugin.disconnect()
    await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled()
