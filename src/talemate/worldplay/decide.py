"""The judgement calls curation asks of a model, each behind one small
function, so a local decision model (Laya, say) can answer one later by
implementing the same function (ruling C7). Today each asks the world's
LLM; nothing here is a plugin system.

**Same thing?** (`same_thing`): whether a new entry is one the world
already has. The wording and variables are the curation probe's
(docs/superpowers/probes/2026-10-22-curation.md, "Same-thing verdict (a
separate small call)"), at kind `analyze`: each side is labelled "Name
(kind, sphere: template, part of X)" and shows up to 6 facts, each cut at
260 characters. The probe fell back to "owner only" (it called 2 of 8
not-same pairs "same"), so the verdict is a hint shown beside the
question, never a default (ruling C2), and it's asked only when both
sides have facts: the spec's mistakes all involved a bare stub.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

import structlog
from pydantic import BaseModel

from talemate.prompts import Prompt
from talemate.world.store import World
from talemate.world.view import ThingState, WorldView
from talemate.worldplay.ai import world_ai_call

log = structlog.get_logger("talemate.worldplay.decide")

__all__ = [
    "SAME_PROMPT_KIND",
    "SIDE_FACT_CHARS",
    "SIDE_FACTS",
    "Verdict",
    "preview_label",
    "same_thing",
    "thing_label",
]

# the probe's preset: analytical, 500 reply tokens
SAME_PROMPT_KIND = "analyze"
# each side shows at most this many facts, each cut at this many characters
SIDE_FACTS = 6
SIDE_FACT_CHARS = 260

VerdictName = Literal["same", "part", "different"]
_VERDICTS: tuple[str, ...] = ("same", "part", "different")


class Verdict(BaseModel):
    """A judgement of how a new entry relates to one already in the world:
    `same` (one thing: its facts belong there, its name another name),
    `part` (one is part of the other) or `different`, with the reason in
    one sentence. `confidence` is a decision model's probability; the LLM
    gives none."""

    verdict: VerdictName
    why: str
    confidence: float | None = None


def _clip(text: str, limit: int = SIDE_FACT_CHARS) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"


def preview_label(
    name: str, kind: str, template: str | None = None, part_of: str | None = None
) -> str:
    """A side as the prompt labels it: "Name (kind, sphere: template, part
    of X)", the template and sphere only when there are any."""

    bits = [kind]
    if template:
        bits.append(f"sphere: {template}")
    if part_of:
        bits.append(f"part of {part_of}")
    return f"{name} ({', '.join(bits)})"


def thing_label(view: WorldView, state: ThingState) -> str:
    """A thing in the world, labelled as `preview_label` labels a side."""

    template = state.fields.get("template")
    link = state.fields.get("part_of")
    sphere = link.get("sphere") if isinstance(link, dict) else None
    return preview_label(
        view.name_of(state.id) or "",
        state.kind,
        template if isinstance(template, str) else None,
        view.name_of(sphere) if isinstance(sphere, str) else None,
    )


def _side_facts(texts: Sequence[str]) -> list[str]:
    return [_clip(text) for text in texts if text.strip()][:SIDE_FACTS]


def _read_verdict(reply: str) -> Verdict | None:
    """The reply's `{"verdict", "why"}`, the prepared `{` there or not; an
    unknown verdict, or none, is `None`."""

    # imported here: `worldplay.create` imports this module
    from talemate.worldplay.create import json_objects

    for text in (reply, "{" + reply):
        for obj in json_objects(text):
            if "verdict" not in obj:
                continue
            verdict = obj.get("verdict")
            verdict = verdict.strip().lower() if isinstance(verdict, str) else ""
            if verdict not in _VERDICTS:
                log.debug("decide.same_unknown_verdict", verdict=obj.get("verdict"))
                return None
            why = obj.get("why")
            return Verdict(
                verdict=verdict,  # type: ignore[arg-type]
                why=" ".join(why.split()) if isinstance(why, str) else "",
            )
    return None


async def same_thing(
    world: World,
    preview_label: str,
    preview_facts: Sequence[str],
    candidate_id: str,
    client: Any,
) -> Verdict | None:
    """How the new entry (`preview_label`, from `preview_label()`, and its
    facts as they read) relates to the thing `candidate_id`, as the model
    judges it, or `None`: when either side has no facts (no call is made),
    the candidate is gone, or the reply gives no verdict. The facts shown
    are the first `SIDE_FACTS` of each side, the candidate's in the order
    they were made, rendered, each cut at `SIDE_FACT_CHARS`. A failed call
    is logged and is `None` too: a hint never costs the preview."""

    view = world.view()
    state = view.thing(candidate_id)
    if state is None:
        return None
    a_facts = _side_facts(preview_facts)
    b_facts = _side_facts(
        [
            view.render(fact.text)
            for fact in sorted(state.facts, key=lambda fact: fact.created)
        ]
    )
    if not a_facts or not b_facts:
        return None
    variables = {
        "a_label": preview_label,
        "a_facts": a_facts,
        "b_label": thing_label(view, state),
        "b_facts": b_facts,
    }
    try:
        with world_ai_call():
            _response, extracted = await Prompt.request(
                "world.same-thing", client, SAME_PROMPT_KIND, vars=variables
            )
    except Exception as exc:  # noqa: BLE001 - a hint never fails the preview
        log.warning("decide.same_failed", candidate=candidate_id, error=str(exc))
        return None
    verdict = _read_verdict(str(extracted.get("response") or ""))
    log.info(
        "decide.same_thing",
        candidate=candidate_id,
        verdict=verdict.verdict if verdict is not None else None,
    )
    return verdict
