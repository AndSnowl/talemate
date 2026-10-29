"""Running Claude Code headless to make a language (languages 3b).

The invocation, the boundary and the output come from the spike
(`docs/superpowers/probes/2026-10-28-claude-code-route-spike.md`): Claude
Code runs in a fresh scratch folder holding the language-design skill, a
`check` command and the brief. It may read and write only inside that
folder and run only the check; it never skips permissions.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import signal
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import structlog
from pydantic import BaseModel

from talemate.languages.brief import BRIEF_FILE_NAME
from talemate.languages.importer import parse_language_text
from talemate.languages.making import MakeSettings
from talemate.path import TALEMATE_ROOT

__all__ = [
    "ClaudeCodeError",
    "ClaudeCodeResult",
    "claude_args",
    "find_language_text",
    "Scratch",
    "prepare_scratch",
    "progress_line",
    "run_claude_code",
]

log = structlog.get_logger("talemate.languages.claude_code")

SKILL_SOURCE = TALEMATE_ROOT / ".claude" / "skills" / "language-design"
# a Write event carries the whole file: far past asyncio's 64 KiB default
STREAM_LIMIT = 16 * 1024 * 1024
NOT_INSTALLED = (
    "Claude Code isn't installed here: copy the brief instead, or pick "
    "another route in the language agent's settings"
)
NO_FILE = "Claude Code finished without a language file"
TOO_LONG = "Claude Code sent more than the app can read at once"
NOT_SIGNED_IN = (
    "Claude Code isn't signed in: run `claude` once in a terminal to sign in, "
    "or copy the brief instead"
)
CANT_RUN = (
    "Claude Code can't be run with the command in the language agent's "
    "settings: check it, or copy the brief instead"
)
# how Claude Code says nobody's signed in
_SIGNED_OUT = re.compile(r"not logged in|/login|log ?in again|authenticat", re.I)


class ClaudeCodeError(Exception):
    """A run that went wrong; its message is shown to the owner as is."""


class ClaudeCodeResult(BaseModel):
    text: str
    reply: str
    cost_usd: float | None = None


_CHECK_SCRIPT = """\
# The app's language check for one scratch folder (languages 3b). It
# lives outside the folder Claude Code works in, so Claude Code can't
# rewrite it; it runs with -P, so nothing in that folder is imported; and
# it reads only language files inside that folder.
import sys
from pathlib import Path

FOLDER = Path({folder!r}).resolve()
paths = sys.argv[1:]
if not paths or any(not (FOLDER / p).resolve().is_relative_to(FOLDER) for p in paths):
    print("The check only reads language files in its own folder.")
    sys.exit(2)

from talemate.languages.__main__ import main

sys.exit(main(["check", *paths]))
"""


@dataclass
class Scratch:
    """Where Claude Code works (`folder`: the skill, the brief, the file it
    writes) and the check it may run (`check`, kept in a folder of its
    own)."""

    folder: Path
    check: Path

    def write_brief(self, brief: str) -> None:
        (self.folder / BRIEF_FILE_NAME).write_text(brief, encoding="utf-8")

    def remove(self) -> None:
        shutil.rmtree(self.folder, ignore_errors=True)
        shutil.rmtree(self.check.parent, ignore_errors=True)


def _write_check(check_dir: Path, folder: Path) -> Path:
    script = check_dir / "check.py"
    script.write_text(_CHECK_SCRIPT.format(folder=str(folder)), encoding="utf-8")
    if sys.platform == "win32":
        wrapper = check_dir / "check.cmd"
        wrapper.write_text(f'@"{sys.executable}" -P "{script}" %*\r\n')
        return wrapper
    wrapper = check_dir / "check"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" -P "{script}" "$@"\n')
    wrapper.chmod(0o755)
    return wrapper


def prepare_scratch() -> Scratch:
    """Two fresh folders in the system temp folder (never under
    `~/.claude`, which Claude Code won't write in): one for Claude Code to
    work in, holding the skill, and one for the check."""

    folder = Path(tempfile.mkdtemp(prefix="fm-language-")).resolve()
    if SKILL_SOURCE.is_dir():
        shutil.copytree(SKILL_SOURCE, folder / ".claude" / "skills" / "language-design")
    else:
        log.warning("language-design skill not found", path=str(SKILL_SOURCE))
    check_dir = Path(tempfile.mkdtemp(prefix="fm-check-")).resolve()
    return Scratch(folder=folder, check=_write_check(check_dir, folder))


def _forget_settings(folder: Path) -> None:
    """Settings a run left in the folder: a next run there (a repair)
    loads project settings, so they could widen what it may do."""

    for path in (folder / ".claude").glob("settings*.json"):
        path.unlink(missing_ok=True)


def claude_args(settings: MakeSettings, prompt: str, check: str) -> list[str]:
    """The spike's invocation: project settings only, the five tools, the
    check (by its full path) the only command allowed, edits only inside
    the folder."""

    args = [
        "-p", prompt,
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
    if settings.claude_model:
        args += ["--model", settings.claude_model]
    return args


def _file_name(tool_input: dict) -> str:
    return Path(str(tool_input.get("file_path", ""))).name


def progress_line(event: dict) -> str | None:
    """A plain line for the owner from one stream-json event, or None."""

    if event.get("type") != "assistant":
        return None
    for block in (event.get("message") or {}).get("content") or []:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        name, tool_input = block.get("name"), block.get("input") or {}
        if name == "Skill":
            return "Reading the language guide"
        if name in ("Write", "Edit"):
            return f"Writing {_file_name(tool_input)}"
        if name == "Read":
            return f"Reading {_file_name(tool_input)}"
        command = str(tool_input.get("command", "")).split()
        if name == "Bash" and command and Path(command[0]).stem == "check":
            return "Running the check"
    return None


def find_language_text(folder: Path, reply: str) -> str:
    """The language the run made: the newest `*.language.json` in the
    folder, else a language in the reply text."""

    files = sorted(folder.glob("*.language.json"), key=lambda p: p.stat().st_mtime)
    if files:
        return files[-1].read_text(encoding="utf-8")
    try:
        parse_language_text(reply)
    except Exception:
        raise ClaudeCodeError(NO_FILE)
    return reply


async def _kill_tree(proc: asyncio.subprocess.Process) -> None:
    """End Claude Code and anything it started (its commands run as
    children)."""

    if proc.returncode is not None:
        return
    try:
        if sys.platform == "win32":
            killer = await asyncio.create_subprocess_exec(
                "taskkill", "/F", "/T", "/PID", str(proc.pid),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # fmt: skip
            await killer.wait()
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, OSError) as exc:
        log.warning("killing Claude Code", pid=proc.pid, error=str(exc))
    finally:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    await proc.wait()


async def run_claude_code(
    scratch: Scratch,
    settings: MakeSettings,
    prompt: str,
    on_progress: Callable[[str], None],
) -> ClaudeCodeResult:
    """Run Claude Code in the scratch folder with `prompt`, reporting plain
    progress lines, and return the language it made. Cancelling kills it."""

    folder = scratch.folder
    _forget_settings(folder)
    try:
        proc = await asyncio.create_subprocess_exec(
            settings.claude_command,
            *claude_args(settings, prompt, str(scratch.check)),
            cwd=folder,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=STREAM_LIMIT,
            start_new_session=sys.platform != "win32",
        )
    except FileNotFoundError:
        raise ClaudeCodeError(NOT_INSTALLED)
    except PermissionError:
        raise ClaudeCodeError(CANT_RUN)

    stderr_lines: list[str] = []

    async def drain_stderr() -> None:
        # read stderr as it comes, so a full pipe can't stall Claude Code
        async for raw in proc.stderr:
            stderr_lines.append(raw.decode("utf-8", "replace").rstrip())

    stderr_task = asyncio.create_task(drain_stderr())
    final: dict | None = None
    try:
        async for raw in proc.stdout:
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "result":
                final = event
            line = progress_line(event)
            if line:
                on_progress(line)
        await proc.wait()
        await stderr_task
    except BaseException as exc:
        # cancelled, or anything else that stops the reading: Claude Code
        # must not be left running (and billing) on its own
        await asyncio.shield(_kill_tree(proc))
        stderr_task.cancel()
        if isinstance(exc, ValueError) and "limit" in str(exc):
            raise ClaudeCodeError(TOO_LONG) from exc
        raise

    reply = str((final or {}).get("result") or "")
    if final is None or final.get("is_error"):
        why = reply or next((s for s in reversed(stderr_lines) if s.strip()), "")
        if _SIGNED_OUT.search(why):
            raise ClaudeCodeError(NOT_SIGNED_IN)
        raise ClaudeCodeError(f"Claude Code stopped: {why or 'no reply'}")
    return ClaudeCodeResult(
        text=find_language_text(folder, reply),
        reply=reply,
        cost_usd=final.get("total_cost_usd"),
    )
