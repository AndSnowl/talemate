"""Running Claude Code headless to make a language (languages 3b-1,
Task 4), with a fake `claude` in its place."""

import asyncio
import json
import os
import subprocess
from pathlib import Path

import pytest

from talemate.languages.claude_code import (
    ClaudeCodeError,
    claude_args,
    find_language_text,
    prepare_folder,
    progress_line,
    run_claude_code,
)
from talemate.languages.importer import parse_language_text
from talemate.languages.making import MakeSettings

FAKE = Path("tests/languages/data/fake-claude").resolve()
SAMPLE = Path("tests/languages/data/sample.language.json").resolve()
EXPECTED_FLAGS = [
    "--setting-sources", "project",
    "--tools", "Read,Write,Edit,Bash,Skill",
    "--allowedTools", "Skill,Bash(./check:*)",
    "--disallowedTools", "Bash(git:*)",
    "--permission-mode", "acceptEdits",
    "--output-format", "stream-json",
    "--verbose",
    "--no-session-persistence",
    "--strict-mcp-config",
]  # fmt: skip


@pytest.fixture
def folder():
    path = prepare_folder("# Make a language for a fantasy world\n")
    yield path
    subprocess.run(["rm", "-rf", str(path)])


def _settings(**kw):
    return MakeSettings(claude_command=str(FAKE), **kw)


async def _run(folder, monkeypatch, mode="ok"):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    lines = []
    result = await run_claude_code(folder, _settings(), "Read brief.md", lines.append)
    return result, lines


def test_claude_args_are_the_spikes():
    args = claude_args(MakeSettings(), "do it")
    assert args == ["-p", "do it", *EXPECTED_FLAGS]
    with_model = claude_args(MakeSettings(claude_model="sonnet"), "do it")
    assert with_model == ["-p", "do it", *EXPECTED_FLAGS, "--model", "sonnet"]
    assert "bypassPermissions" not in args and "--bare" not in args


def test_the_folder_holds_skill_check_and_brief(folder):
    assert (folder / ".claude/skills/language-design/SKILL.md").exists()
    assert os.access(folder / "check", os.X_OK)
    assert (folder / "brief.md").read_text().startswith("# Make a language")
    assert Path.home() / ".claude" not in folder.parents


def test_the_check_wrapper_runs_the_check(folder):
    done = subprocess.run(
        ["./check", str(SAMPLE)], cwd=folder, capture_output=True, text=True
    )
    assert done.returncode == 0, done.stderr
    assert "Sample names" in done.stdout


def _tool(name, **tool_input):
    return {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": name, "input": tool_input}]},
    }


def test_progress_lines_are_plain():
    assert progress_line(_tool("Skill", skill="language-design")) == "Reading the language guide"
    assert (
        progress_line(_tool("Write", file_path="/tmp/x/moscavian.language.json"))
        == "Writing moscavian.language.json"
    )
    assert progress_line(_tool("Read", file_path="/tmp/x/brief.md")) == "Reading brief.md"
    assert progress_line(_tool("Bash", command="./check m.language.json")) == "Running the check"
    assert progress_line(_tool("Bash", command="ls")) is None
    assert progress_line({"type": "system", "subtype": "init"}) is None


async def test_a_run_returns_the_file(folder, monkeypatch):
    result, lines = await _run(folder, monkeypatch)
    assert parse_language_text(result.text).language.name
    assert lines == ["Reading the language guide", "Writing moscavian.language.json", "Running the check"]
    args = json.loads((folder / "args.json").read_text())
    assert args[args.index("--permission-mode") + 1] == "acceptEdits"
    assert result.cost_usd == 0.01


async def test_a_reply_only_run_falls_back_to_the_reply(folder, monkeypatch):
    result, _ = await _run(folder, monkeypatch, "reply-only")
    assert parse_language_text(result.text).language.name


def test_no_file_and_no_language_in_the_reply_fails_plainly(folder):
    with pytest.raises(ClaudeCodeError, match="finished without a language file"):
        find_language_text(folder, "DONE")


def test_the_newest_of_several_files_is_taken(folder):
    old = folder / "old.language.json"
    old.write_text("{}")
    os.utime(old, (1, 1))
    (folder / "new.language.json").write_text(SAMPLE.read_text())
    assert find_language_text(folder, "") == SAMPLE.read_text()


async def test_a_missing_command_says_claude_code_isnt_installed(folder):
    settings = MakeSettings(claude_command="no-such-claude-here")
    with pytest.raises(ClaudeCodeError, match="Claude Code isn't installed here"):
        await run_claude_code(folder, settings, "x", lambda line: None)


async def test_an_error_result_is_reported(folder, monkeypatch):
    with pytest.raises(ClaudeCodeError, match="Claude Code stopped: You've hit your usage limit."):
        await _run(folder, monkeypatch, "error")


async def test_cancelling_kills_the_process(folder, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "slow")
    started = asyncio.Event()
    task = asyncio.create_task(
        run_claude_code(folder, _settings(), "x", lambda line: started.set())
    )
    await asyncio.wait_for(started.wait(), 20)
    pid = int((folder / "pid").read_text())
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0.2)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
