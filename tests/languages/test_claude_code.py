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
    prepare_scratch,
    progress_line,
    run_claude_code,
)
from talemate.languages.importer import parse_language_text
from talemate.languages.making import MakeSettings

FAKE = Path("tests/languages/data/fake-claude").resolve()
SAMPLE = Path("tests/languages/data/sample.language.json").resolve()
CHECK = "/tmp/fm-check-x/check"


def _flags(check=CHECK):
    return [
        "--setting-sources", "project",
        "--tools", "Read,Write,Edit,Bash,Skill",
        "--allowedTools", f"Skill,Bash({check}:*)",
        "--disallowedTools", "Bash(git:*)",
        "--permission-mode", "acceptEdits",
        "--output-format", "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--strict-mcp-config",
    ]  # fmt: skip


@pytest.fixture
def scratch():
    made = prepare_scratch()
    made.write_brief("# Make a language for a fantasy world\n")
    yield made
    made.remove()


@pytest.fixture
def folder(scratch):
    return scratch.folder


def _settings(**kw):
    return MakeSettings(claude_command=str(FAKE), **kw)


async def _run(scratch, monkeypatch, mode="ok"):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    lines = []
    result = await run_claude_code(scratch, _settings(), "Read brief.md", lines.append)
    return result, lines


def test_claude_args_are_the_spikes():
    args = claude_args(MakeSettings(), "do it", CHECK)
    assert args == ["-p", "do it", *_flags()]
    with_model = claude_args(MakeSettings(claude_model="sonnet"), "do it", CHECK)
    assert with_model == ["-p", "do it", *_flags(), "--model", "sonnet"]
    assert "bypassPermissions" not in args and "--bare" not in args


def test_the_folder_holds_skill_and_brief(folder):
    assert (folder / ".claude/skills/language-design/SKILL.md").exists()
    assert (folder / "brief.md").read_text().startswith("# Make a language")
    assert Path.home() / ".claude" not in folder.parents


def test_the_check_lives_outside_the_working_folder(scratch):
    # Claude Code may edit anything in its folder: a check kept there could
    # be rewritten into any command and still run as "the check"
    assert os.access(scratch.check, os.X_OK)
    assert scratch.folder not in scratch.check.parents
    assert not (scratch.folder / "check").exists()


def _check(scratch, *args):
    return subprocess.run(
        [str(scratch.check), *args], cwd=scratch.folder, capture_output=True, text=True
    )


def test_the_check_wrapper_runs_the_check(scratch):
    (scratch.folder / "m.language.json").write_text(SAMPLE.read_text())
    done = _check(scratch, "m.language.json")
    assert done.returncode == 0, done.stderr
    assert "Sample names" in done.stdout


def test_a_planted_talemate_package_is_not_imported(scratch):
    planted = scratch.folder / "talemate" / "languages"
    planted.mkdir(parents=True)
    (scratch.folder / "talemate" / "__init__.py").write_text("print('PLANTED')\n")
    (planted / "__init__.py").write_text("print('PLANTED')\n")
    (planted / "__main__.py").write_text("print('PLANTED')\n")
    (scratch.folder / "m.language.json").write_text(SAMPLE.read_text())
    done = _check(scratch, "m.language.json")
    assert "PLANTED" not in done.stdout + done.stderr
    assert "Sample names" in done.stdout


def test_the_check_reads_only_files_in_its_folder(scratch):
    done = _check(scratch, "/etc/hostname")
    assert done.returncode == 2
    assert "only reads language files in its own folder" in done.stdout
    assert _check(scratch, "../outside.language.json").returncode == 2


async def test_settings_left_in_the_folder_are_removed_before_a_run(scratch, monkeypatch):
    # a run may write .claude/settings.json; the next run must not load it
    settings = scratch.folder / ".claude" / "settings.local.json"
    settings.write_text('{"permissions": {"allow": ["Bash"]}}')
    await _run(scratch, monkeypatch)
    assert not settings.exists()


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
    assert progress_line(_tool("Bash", command=f"{CHECK} m.language.json")) == "Running the check"
    assert progress_line(_tool("Bash", command="ls")) is None
    assert progress_line({"type": "system", "subtype": "init"}) is None


async def test_a_run_returns_the_file(scratch, folder, monkeypatch):
    result, lines = await _run(scratch, monkeypatch)
    assert parse_language_text(result.text).language.name
    assert lines == ["Reading the language guide", "Writing moscavian.language.json", "Running the check"]
    args = json.loads((folder / "args.json").read_text())
    assert args[args.index("--permission-mode") + 1] == "acceptEdits"
    assert result.cost_usd == 0.01


async def test_a_reply_only_run_falls_back_to_the_reply(scratch, monkeypatch):
    result, _ = await _run(scratch, monkeypatch, "reply-only")
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


async def test_a_missing_command_says_claude_code_isnt_installed(scratch):
    settings = MakeSettings(claude_command="no-such-claude-here")
    with pytest.raises(ClaudeCodeError, match="Claude Code isn't installed here"):
        await run_claude_code(scratch, settings, "x", lambda line: None)


async def test_an_error_result_is_reported(scratch, monkeypatch):
    with pytest.raises(ClaudeCodeError, match="Claude Code stopped: You've hit your usage limit."):
        await _run(scratch, monkeypatch, "error")


async def test_cancelling_kills_the_process(scratch, folder, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "slow")
    started = asyncio.Event()
    task = asyncio.create_task(
        run_claude_code(scratch, _settings(), "x", lambda line: started.set())
    )
    await asyncio.wait_for(started.wait(), 20)
    pid = int((folder / "pid").read_text())
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0.2)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
