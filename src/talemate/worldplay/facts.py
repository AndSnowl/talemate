"""A few more facts for an entry the world has: "+ Add facts..." and
"+ Add event..." (Filing spec, "An entry page").

`draft_facts` asks the model for a small draft of facts about one entry
from the owner's prompt (`world/add-facts.jinja2`, through
`ai.world_ai_call`, read with `create.parse_create_reply`, which parses
with `create.json_objects`), writing nothing. Given a `year` (an event),
every fact is dated to it. Each fact a fact of the entry already says
arrives as a repeat (`create.repeat_flags`: shown with its match, and
unticked at the untick threshold).

`accept_facts` writes the draft's ticked facts onto the entry in one
revision, linked as a hand-written fact is (`links.link_text`: entries
and stubs by name, never the entry itself). Names the world doesn't have
stay plain words; nothing here makes a stub.

The template's wording is new and unprobed (Filing, Task 12 measures
it).
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, Field

from talemate.prompts import Prompt
from talemate.world import entries
from talemate.world.dates import WorldDate
from talemate.world.kinds import get_kind
from talemate.world.store import Source, World
from talemate.worldplay import prose_gen
from talemate.worldplay.ai import world_ai_call
from talemate.worldplay.create import (
    PreviewFact,
    create_categories,
    current_date,
    default_category,
    holder_named,
    parse_create_reply,
    repeat_flags,
)
from talemate.worldplay.links import link_text

__all__ = ["FactDraft", "accept_facts", "draft_facts"]

log = structlog.get_logger("talemate.worldplay.facts")

# the most facts one draft holds: a few, for the owner to tick
DRAFT_FACTS = 6

# the facts of the entry the prompt shows, so the reply doesn't repeat
# them (the most recent written first)
SHOWN_FACTS = 20

PROMPT_KIND = "creative_instruction_2048"


class FactDraft(BaseModel):
    """A small draft of facts for an entry (`thing_id`), from the owner's
    `prompt`; `year`, the year an event's facts are dated to, or `None`.
    The owner ticks, edits or drops them before `accept_facts`."""

    thing_id: str
    prompt: str
    year: int | None = None
    facts: list[PreviewFact] = Field(default_factory=list)


async def draft_facts(
    world: World,
    thing_id: str,
    prompt: str,
    client: Any,
    *,
    year: int | None = None,
    reply: str | None = None,
) -> FactDraft:
    """A `FactDraft` of at most `DRAFT_FACTS` facts about the entry, from
    the owner's `prompt`, writing nothing. With `year`, each is dated to
    it. `reply` stands in for the model's (the browser tests' fixed
    reply), read through the same parsing. A missing entry is a
    `KeyError`; a reply with no facts a `ValueError`."""

    view = world.view()
    state = view.thing(thing_id)
    if state is None:
        raise KeyError(f"no such entry: {thing_id}")
    if not prompt.strip():
        raise ValueError("say what the facts are about")
    calendar = world.calendar
    now_year = current_date(world).to_datetime().year
    hint = state.fields.get("hint")
    categories = create_categories(state.kind, hint if isinstance(hint, str) else None)
    name = view.name_of(thing_id) or ""
    summary = entries.summary_fact(state)
    known = sorted(state.facts, key=lambda fact: fact.created, reverse=True)
    if reply is None:
        prose_gen.require_client(client)
        with world_ai_call():
            _response, extracted = await Prompt.request(
                "world.add-facts",
                client,
                PROMPT_KIND,
                vars={
                    "name": name,
                    "kind": state.kind,
                    "tag": state.fields.get("tag"),
                    "summary": view.render(summary.text) if summary else "",
                    "facts": [view.render(f.text) for f in known[:SHOWN_FACTS]],
                    "prompt": prompt.strip(),
                    "categories": categories,
                    "year": calendar.format(WorldDate.of(year)) if year else None,
                    "now_year": now_year,
                },
            )
        reply = extracted["response"]
    _name, _age, facts = parse_create_reply(
        reply,
        state.kind,
        calendar,
        now_year,
        holder=lambda held: holder_named(view, held),
        categories=categories,
    )
    if not facts:
        raise ValueError("the model's reply had no facts in it")
    facts = facts[:DRAFT_FACTS]
    if year is not None:
        dated = WorldDate.of(year)
        for fact in facts:
            fact.since = dated
    flags = repeat_flags(view, [f.text for f in facts], [thing_id], world.curation())
    for fact, (repeat_of, ticked) in zip(facts, flags):
        fact.repeat_of, fact.ticked = repeat_of, ticked
    log.info(
        "facts.draft",
        thing_id=thing_id,
        year=year,
        facts=len(facts),
        repeats=sum(1 for f in facts if f.repeat_of is not None),
    )
    return FactDraft(thing_id=thing_id, prompt=prompt, year=year, facts=facts)


def accept_facts(world: World, draft: FactDraft) -> list[str]:
    """Write the draft's ticked facts onto its entry in one revision and
    return their ids: each in its category (`create.default_category`'s
    when the entry's kind has none such), with its date and holder (a
    holder gone since holds nothing), its text linked as a hand-written
    fact's. A blank one is skipped. A missing entry is a `KeyError`."""

    view = world.view()
    state = view.thing(draft.thing_id)
    if state is None:
        raise KeyError(f"no such entry: {draft.thing_id}")
    categories = get_kind(state.kind).categories
    written: list[str] = []
    kept = [fact for fact in draft.facts if fact.ticked and fact.text.strip()]
    if not kept:
        return written
    with world.revision(Source.manual(note="added facts from prompt")) as rev:
        for fact in kept:
            category = (
                fact.category
                if fact.category in categories
                else default_category(state.kind, fact.since is not None)
            )
            if category not in categories:
                category = categories[0]
            holder = fact.held_by
            held = holder is not None and view.thing(holder) is not None
            written.append(
                rev.add_fact(
                    draft.thing_id,
                    category,
                    link_text(
                        view,
                        " ".join(fact.text.split()),
                        owner=draft.thing_id,
                    ),
                    valid_from=fact.since,
                    origin=entries.with_held_by(None, holder) if held else None,
                )
            )
    log.info("facts.accept", thing_id=draft.thing_id, facts=len(written))
    return written
