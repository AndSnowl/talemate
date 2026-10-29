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
import shutil
import signal
import sys
import tempfile
from collections.abc import Callable
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
    "prepare_folder",
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


class ClaudeCodeError(Exception):
    """A run that went wrong; its message is shown to the owner as is."""


class ClaudeCodeResult(BaseModel):
    text: str
    reply: str
    cost_usd: float | None = None


def _check_wrapper(folder: Path) -> None:
    if sys.platform == "win32":
        (folder / "check.cmd").write_text(
            f'@"{sys.executable}" -m talemate.languages check %*\r\n'
        )
        return
    wrapper = folder / "check"
    wrapper.write_text(
        "#!/bin/sh\n"
        "# the app's language check, for this folder only\n"
        f'exec "{sys.executable}" -m talemate.languages check "$@"\n'
    )
    wrapper.chmod(0o755)


def prepare_folder(brief: str) -> Path:
    """A fresh scratch folder (in the system temp folder, never under
    `~/.claude`, which Claude Code won't write in) holding the skill, the
    check command and the brief."""

    folder = Path(tempfile.mkdtemp(prefix="fm-language-"))
    if SKILL_SOURCE.is_dir():
        shutil.copytree(SKILL_SOURCE, folder / ".claude" / "skills" / "language-design")
    else:
        log.warning("language-design skill not found", path=str(SKILL_SOURCE))
    _check_wrapper(folder)
    (folder / BRIEF_FILE_NAME).write_text(brief, encoding="utf-8")
    return folder


def _check_rule() -> str:
    return "Bash(./check.cmd:*)" if sys.platform == "win32" else "Bash(./check:*)"


def claude_args(settings: MakeSettings, prompt: str) -> list[str]:
    """The spike's invocation: project settings only, the five tools, the
    check the only command allowed, edits only inside the folder."""

    args = [
        "-p", prompt,
        "--setting-sources", "project",
        "--tools", "Read,Write,Edit,Bash,Skill",
        "--allowedTools", f"Skill,{_check_rule()}",
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
        if name == "Bash" and str(tool_input.get("command", "")).startswith("./check"):
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
    folder: Path,
    settings: MakeSettings,
    prompt: str,
    on_progress: Callable[[str], None],
) -> ClaudeCodeResult:
    """Run Claude Code in `folder` with `prompt`, reporting plain progress
    lines, and return the language it made. Cancelling kills it."""

    try:
        proc = await asyncio.create_subprocess_exec(
            settings.claude_command,
            *claude_args(settings, prompt),
            cwd=folder,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=STREAM_LIMIT,
            start_new_session=sys.platform != "win32",
        )
    except FileNotFoundError:
        raise ClaudeCodeError(NOT_INSTALLED)

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
    except asyncio.CancelledError:
        await asyncio.shield(_kill_tree(proc))
        stderr_task.cancel()
        raise

    reply = str((final or {}).get("result") or "")
    if final is None or final.get("is_error"):
        why = reply or next((s for s in reversed(stderr_lines) if s.strip()), "")
        raise ClaudeCodeError(f"Claude Code stopped: {why or 'no reply'}")
    return ClaudeCodeResult(
        text=find_language_text(folder, reply),
        reply=reply,
        cost_usd=final.get("total_cost_usd"),
    )
