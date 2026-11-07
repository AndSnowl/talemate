"""Picking a person's naming rule (languages 4c): the model reads who the
person is and picks one of their language's main people rules by its
description (probe 4c: 13 of 15 right, against 9 for matching on sex and
rank). It's asked when Name it opens on a person, never ahead of time. A
pick that isn't one of those rules falls back to today's matching."""

from __future__ import annotations

from pydantic import BaseModel, Field

from talemate.languages.models import GeneratorDef, Language
from talemate.languages.naming import PROMPT_KIND
from talemate.languages.person_names import PEOPLE_USES, choose, is_main, pick_rule
from talemate.prompts.base import Prompt
from talemate.worldplay import prose_gen
from talemate.worldplay.ai import world_ai_call
from talemate.worldplay.create import json_objects

__all__ = ["RulePick", "pick_person_rule", "pick_prompt_rules"]


class RulePick(BaseModel):
    rule_id: str
    built_as: dict[str, str] = Field(default_factory=dict)
    # the picked rule's description: what made the model pick it
    why: str = ""
    # today's matching stood in (the model's answer wasn't a rule)
    fallback: bool = False


def _main_people_rules(language: Language) -> list[GeneratorDef]:
    return [
        g for g in language.generators if g.use in PEOPLE_USES and is_main(language, g)
    ]


def pick_prompt_rules(language: Language) -> list[str]:
    """The rules the model picks from, one line each: id, name,
    description, and who the rule is for as a hint."""

    lines = []
    for g in _main_people_rules(language):
        hint = f" [for: {', '.join(g.for_person.values())}]" if g.for_person else ""
        lines.append(f"{g.id}: {g.name} — {g.description or 'no description'}{hint}")
    return lines


async def _pick_reply(client, language: Language, text: str) -> str:
    prose_gen.require_client(client)
    with world_ai_call():
        _response, extracted = await Prompt.request(
            "world.name-pick",
            client,
            PROMPT_KIND,
            vars={
                "language": language.name,
                "rules": pick_prompt_rules(language),
                "character": text,
            },
        )
    return extracted["response"]


def _read(reply: str) -> dict:
    """The reply's object, with or without its first "{" (the prompt
    primes it)."""

    for text in (reply, "{" + reply):
        objects = json_objects(text)
        if objects:
            return objects[0]
    return {}


async def pick_person_rule(
    client, language: Language, text: str, *, reply: str | None = None
) -> RulePick:
    """The person's rule, picked by the model from `text` (who they are:
    the prompt and facts), with sex and rank. A rule given by its name
    counts as its id. An answer that isn't a main people rule gives
    today's matching (`pick_rule`) on what was read, `fallback` set."""

    if reply is None:
        reply = await _pick_reply(client, language, text)
    got = _read(reply)
    read = {k: str(got.get(k) or "").strip() for k in ("sex", "rank") if got.get(k)}
    built_as = choose(language, read)
    rules = _main_people_rules(language)
    answer = str(got.get("rule") or "").strip()
    head = answer.split(" — ")[0].strip().lower()
    found = next(
        (g for g in rules if g.id == answer or g.name.lower() == head or g.id == head),
        None,
    )
    if found is None:
        rule = pick_rule(language, built_as)
        return RulePick(
            rule_id=rule.id, built_as=built_as, why=rule.description, fallback=True
        )
    return RulePick(rule_id=found.id, built_as=built_as, why=found.description)
