"""Making a language from inside the app (languages 3b): the route
settings, and the job that runs a route."""

import re
import shutil
from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import BaseModel

from talemate.languages.check import check_language, needs_repair, repair_note
from talemate.prompts import Prompt
from talemate.worldplay.ai import world_ai_call

__all__ = [
    "MakeError",
    "MakeRequest",
    "MakeSettings",
    "QuestionAnswer",
    "ask_questions",
    "make_in_app",
    "make_language",
]

MAX_REPAIRS = 2
FIRST_PROMPT = (
    "Read brief.md and do what it says. Use the language-design skill. When "
    "the check passes, reply DONE <file name>."
)
REPAIR_PROMPT = (
    "The app's check found these problems in the language file. Fix them, "
    "run the check again, and reply DONE.\n\n"
)
NO_LANGUAGE = "The reply had no language file in it: {error}"

PROMPT_KIND = "create"
MAX_QUESTIONS = 4
_NUMBERING = re.compile(r"^\s*(?:\d+\s*[.)]|[-*])\s*")

Route = Literal["claude_code", "in_app", "brief"]


class MakeSettings(BaseModel):
    """How languages are made, from the language agent's settings: on
    Claude Code on this computer, on the agent's own model, or by copying
    the brief to any assistant."""

    route: Route = "claude_code"
    claude_command: str = "claude"
    claude_model: str = ""


class QuestionAnswer(BaseModel):
    question: str
    answer: str


class MakeRequest(BaseModel):
    """What the owner asked for: their words, their answers to the
    questions (or "decide for me"), and the entries to take into
    account."""

    kind: Literal["new"] = "new"
    text: str
    answers: list[QuestionAnswer] = []
    decide_for_me: bool = False
    context_ids: list[str] = []


def _questions(reply: str) -> list[str]:
    lines = (_NUMBERING.sub("", line).strip() for line in reply.splitlines())
    return [line for line in lines if line][:MAX_QUESTIONS]


async def ask_questions(
    client, request_text: str, *, reply: str | None = None
) -> list[str]:
    """At most four plain questions about what the owner wants the
    language to sound and feel like; none without a model. `reply`
    stands in for the model's (browser tests)."""

    if reply is None:
        if client is None:
            return []
        with world_ai_call():
            _response, extracted = await Prompt.request(
                "world.language-questions",
                client,
                PROMPT_KIND,
                vars={"request": request_text},
            )
        reply = extracted["response"]
    return _questions(reply)


class MakeError(Exception):
    """A language that couldn't be made; its message is shown as is."""


async def make_in_app(
    client,
    brief: str,
    *,
    repair: str | None = None,
    previous: str | None = None,
    reply: str | None = None,
) -> str:
    """The model's reply to the brief (or, with `repair`, to the check's
    note on its `previous` file). `reply` stands in for the model's."""

    if reply is not None:
        return reply
    if client is None:
        raise MakeError(
            "There's no model to make it with: give the language agent a client"
        )
    with world_ai_call():
        _response, extracted = await Prompt.request(
            "world.language-make",
            client,
            PROMPT_KIND,
            vars={"brief": brief, "repair": repair, "previous": previous},
        )
    return extracted["response"]


def _problems(text: str) -> str | None:
    """What the check wants fixed in `text`, or None when it can go to
    the owner as it is."""

    from talemate.languages.importer import parse_language_text

    try:
        file = parse_language_text(text)
    except Exception as exc:
        return NO_LANGUAGE.format(error=exc)
    report = check_language(file.language)
    return repair_note(report) if needs_repair(report) else None


async def _repaired(
    text: str,
    again: Callable[[str, str], Awaitable[str]],
    on_progress: Callable[[str], None],
) -> str:
    """`text`, sent back with the check's note (`again(problems,
    previous)`) at most twice while the check wants it fixed."""

    for attempt in range(1, MAX_REPAIRS + 1):
        on_progress("Checking the result")
        problems = _problems(text)
        if problems is None:
            break
        on_progress(f"Fixing what the check found ({attempt} of {MAX_REPAIRS})")
        text = await again(problems, text)
    return text


async def make_language(
    view,
    request: MakeRequest,
    settings: MakeSettings,
    client,
    on_progress: Callable[[str], None],
    *,
    fixed: dict | None = None,
) -> str:
    """Make the language `request` asks for on the route `settings` names,
    sending the check's note back at most twice, and return the file's
    text (warnings and all: the owner sees them in the review)."""

    from talemate.languages import claude_code
    from talemate.languages.brief import write_brief

    if settings.route == "brief":
        raise MakeError("This route only copies the brief")

    if settings.route == "in_app":
        brief = write_brief(view, request)
        fixed_reply = (fixed or {}).get("language_file")

        async def in_app_again(problems: str, previous: str) -> str:
            return await make_in_app(
                client, brief, repair=problems, previous=previous, reply=fixed_reply
            )

        on_progress("Asking the model")
        text = await make_in_app(client, brief, reply=fixed_reply)
        return await _repaired(text, in_app_again, on_progress)

    folder = claude_code.prepare_folder(
        write_brief(view, request, check_command="./check")
    )

    async def claude_again(problems: str, previous: str) -> str:
        prompt = REPAIR_PROMPT + problems
        result = await claude_code.run_claude_code(
            folder, settings, prompt, on_progress
        )
        return result.text

    try:
        result = await claude_code.run_claude_code(
            folder, settings, FIRST_PROMPT, on_progress
        )
        return await _repaired(result.text, claude_again, on_progress)
    except claude_code.ClaudeCodeError as exc:
        raise MakeError(str(exc)) from exc
    finally:
        shutil.rmtree(folder, ignore_errors=True)
