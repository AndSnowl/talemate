"""Making a language from inside the app (languages 3b): the route
settings, and the job that runs a route."""

import re
from typing import Literal

from pydantic import BaseModel

from talemate.prompts import Prompt
from talemate.worldplay.ai import world_ai_call

__all__ = ["MakeRequest", "MakeSettings", "QuestionAnswer", "ask_questions"]

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
