"""Making a language on a route, with the repair loop (languages 3b-1,
Task 5)."""

import json
from pathlib import Path

import pytest

import talemate.languages.claude_code as claude_code
from talemate.languages.importer import parse_language_text
from talemate.languages.making import (
    MakeError,
    MakeRequest,
    MakeSettings,
    make_in_app,
    make_language,
)

from conftest import MockClient, MockClientContext, client_responses

SAMPLE = Path("tests/languages/data/sample.language.json")
FAKE = Path("tests/languages/data/fake-claude").resolve()
REQUEST = MakeRequest(text="a unique but recognizably Russian language")


def _reply(text):
    return f"Here is your language:\n\n```json\n{text}\n```\n"


def _broken():
    data = json.loads(SAMPLE.read_text())
    data["language"]["generators"][0]["reject"] = ["("]
    return json.dumps(data)


async def _make(client, replies, settings=None, lines=None):
    async with MockClientContext():
        client_responses.get().extend(replies)
        return await make_language(
            None,
            REQUEST,
            settings or MakeSettings(route="in_app"),
            client,
            (lines if lines is not None else []).append,
        )


async def test_in_app_returns_a_checked_file():
    client = MockClient("test")
    lines = []
    text = await _make(client, [_reply(SAMPLE.read_text())], lines=lines)
    assert parse_language_text(text).language.name
    assert lines[0] == "Asking the model" and "Checking the result" in lines


async def test_a_blocking_problem_is_sent_back_once_then_fixed():
    client = MockClient("test")
    lines = []
    text = await _make(client, [_reply(_broken()), _reply(SAMPLE.read_text())], lines=lines)
    assert len(client.prompt_history) == 2
    repair_prompt = str(client.prompt_history[1]["prompt"])
    assert "These must be fixed before the language can be imported" in repair_prompt
    assert "Fixing what the check found (1 of 2)" in lines
    assert parse_language_text(text).language.generators[0].reject != ["("]


async def test_repairs_stop_after_two():
    client = MockClient("test")
    text = await _make(client, [_reply(_broken())] * 3)
    assert len(client.prompt_history) == 3
    # the last text comes back, its problem and all, for the owner to see
    assert parse_language_text(text).language.generators[0].reject == ["("]


async def test_a_reply_with_no_language_is_sent_back():
    client = MockClient("test")
    await _make(client, ["Sorry, I can't.", _reply(SAMPLE.read_text())])
    assert len(client.prompt_history) == 2
    assert "no language file" in str(client.prompt_history[1]["prompt"])


async def test_the_claude_code_route_runs_the_fake(monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")
    folders = []
    real = claude_code.prepare_folder

    def spy(brief):
        folders.append(real(brief))
        return folders[-1]

    monkeypatch.setattr(claude_code, "prepare_folder", spy)
    lines = []
    text = await make_language(
        None,
        REQUEST,
        MakeSettings(route="claude_code", claude_command=str(FAKE)),
        None,
        lines.append,
    )
    assert parse_language_text(text).language.name
    assert "Running the check" in lines
    assert folders and not folders[0].exists()


async def test_a_claude_code_failure_becomes_a_make_error():
    with pytest.raises(MakeError, match="Claude Code isn't installed here"):
        await make_language(
            None,
            REQUEST,
            MakeSettings(route="claude_code", claude_command="no-such-claude-here"),
            None,
            lambda line: None,
        )


async def test_the_brief_route_is_not_runnable():
    with pytest.raises(MakeError, match="This route only copies the brief"):
        await make_language(None, REQUEST, MakeSettings(route="brief"), None, print)


async def test_in_app_without_a_model_says_so():
    with pytest.raises(MakeError, match="no model"):
        await make_language(None, REQUEST, MakeSettings(route="in_app"), None, print)


async def test_a_fixed_reply_stands_in_for_the_model():
    text = await make_in_app(None, "brief", reply=_reply(SAMPLE.read_text()))
    assert parse_language_text(text).language.name
