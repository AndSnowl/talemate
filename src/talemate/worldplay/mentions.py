"""Where a thing is mentioned, and the context its mentions give.

A stub has no facts of its own; what the world knows about it lives in the
facts of the entries that mention it. This module gathers those, for the
prompt that expands a stub and for what the create box shows the owner:

- `mentions`: every fact, in any other entry and on any story date, that
  references the thing, rendered;
- `gather_mentions`: the context Task 3's probe settled on
  (`docs/superpowers/probes/2026-10-21-connections.md`, recommendation 3):
  "Mentioned elsewhere", up to 12 mentioning facts, the most-mentioning
  entries first; and "About those", the key facts of the first 3 of those
  entries, up to 8 each. A species, race or mix's key facts are its
  physical, instinct and origin facts, then its variation and general
  ones, and its origin facts are never cut by the cap (they're history,
  often of the very place being expanded); any other kind's follow its
  own category order (not probed);
- `mention_context`: the same, as one `(heading, facts)` group per
  mentioning entry. An entry with an everyday name is headed "Owl-folk
  (species, usually called Owls)", as the probe's recommendation (d) names
  things in create prompts;
- `suggested_prompt`: the name, the stub's own facts and sphere, and its
  mentioning facts, as the create box's starting prompt for a stub.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel

from talemate.world.filing import filings_of
from talemate.world.kinds import HERITAGE_KINDS, get_kind
from talemate.world.names import everyday_name
from talemate.world.view import WorldView
from talemate.worldplay.held import filed_as

log = structlog.get_logger("talemate.worldplay.mentions")

__all__ = [
    "About",
    "Mention",
    "MentionContext",
    "entry_label",
    "gather_mentions",
    "mention_context",
    "mentions",
    "suggested_prompt",
]

# the caps Task 3's probe settled on
MENTION_FACTS = 12
ABOUT_ENTRIES = 3
KEY_FACTS = 8

# the order a species, race or mix's key facts come in
HERITAGE_KEY_ORDER = ("physical", "instinct", "origin", "variation", "general")

# the longest suggested prompt, cut back to a sentence's end
PROMPT_MAX = 400

_SENTENCE_ENDS = ".!?"
# words whose full stop doesn't end a sentence ("St. Sophia")
_ABBREVIATIONS = {"St", "Mt", "Mr", "Mrs", "Ms", "Dr"}


class Mention(BaseModel):
    """A fact of another entry that references the thing, rendered."""

    owner_id: str
    owner_name: str
    owner_kind: str
    # the mentioning entry's everyday name, if it has one
    owner_everyday: str | None = None
    fact_id: str
    category: str
    text: str


class About(BaseModel):
    """A mentioning entry and its key facts (rendered, without the facts
    that mention the thing)."""

    id: str
    name: str
    kind: str
    everyday: str | None = None
    facts: list[str]


class MentionContext(BaseModel):
    """What a thing's mentions tell a prompt: "Mentioned elsewhere" and
    "About those", capped."""

    mentioned: list[Mention]
    about: list[About]


def mentions(view: WorldView, thing_id: str) -> list[Mention]:
    """Every fact of another live entry that references `thing_id`, on any
    story date (ended facts too), in the view's fact order."""

    found: list[Mention] = []
    owners: dict[str, tuple[str, str, str | None] | None] = {}
    for owner_id, fact in view.referencing(thing_id, any_date=True):
        if owner_id == thing_id:
            continue
        if owner_id not in owners:
            state = view.thing(owner_id)
            owners[owner_id] = (
                (view.name_of(owner_id) or "", state.kind, everyday_name(state))
                if state
                else None
            )
        owner = owners[owner_id]
        if owner is None:
            continue
        found.append(
            Mention(
                owner_id=owner_id,
                owner_name=owner[0],
                owner_kind=owner[1],
                owner_everyday=owner[2],
                fact_id=fact.fact_id,
                category=fact.category,
                text=view.render(fact.text),
            )
        )
    return found


def _by_entry(found: list[Mention]) -> list[list[Mention]]:
    """`found` grouped by mentioning entry, the most mentions first (ties
    by name, then id), each group in fact order."""

    groups: dict[str, list[Mention]] = {}
    for mention in found:
        groups.setdefault(mention.owner_id, []).append(mention)
    return sorted(
        groups.values(),
        key=lambda group: (
            -len(group),
            group[0].owner_name.casefold(),
            group[0].owner_id,
        ),
    )


def _key_facts(view: WorldView, owner_id: str, skip: set[str]) -> list[str]:
    """Up to `KEY_FACTS` of the entry's facts at the view's date, rendered,
    in its key category order, leaving out the fact ids in `skip`. A
    species', race's or mix's origin facts are never cut: they're history,
    often of the very place being expanded (the connections flow run lost a
    "capital in Moscow" origin fact to the cap, and the country expanded
    from its stub put its capital elsewhere)."""

    state = view.thing(owner_id)
    if state is None:
        return []
    if state.kind in HERITAGE_KINDS:
        order: list[str] = list(HERITAGE_KEY_ORDER)
    else:
        order = list(get_kind(state.kind).categories)
    rank = {category: i for i, category in enumerate(order)}
    facts = sorted(
        (fact for fact in state.facts if fact.fact_id not in skip),
        key=lambda fact: rank.get(fact.category, len(order)),
    )
    kept = facts[:KEY_FACTS]
    if state.kind in HERITAGE_KINDS:
        kept += [fact for fact in facts[KEY_FACTS:] if fact.category == "origin"]
    return [view.render(fact.text) for fact in kept]


def gather_mentions(view: WorldView, thing_id: str) -> MentionContext:
    """The context `thing_id`'s mentions give, capped as Task 3 settled:
    up to `MENTION_FACTS` mentioning facts, the most-mentioning entries
    first, and the key facts of the first `ABOUT_ENTRIES` of them."""

    groups = _by_entry(mentions(view, thing_id))
    mentioned = [mention for group in groups for mention in group][:MENTION_FACTS]
    skip = {mention.fact_id for group in groups for mention in group}
    about = [
        About(
            id=group[0].owner_id,
            name=group[0].owner_name,
            kind=group[0].owner_kind,
            everyday=group[0].owner_everyday,
            facts=_key_facts(view, group[0].owner_id, skip),
        )
        for group in groups[:ABOUT_ENTRIES]
    ]
    return MentionContext(mentioned=mentioned, about=about)


def entry_label(name: str, kind: str, everyday: str | None = None) -> str:
    """How a prompt names an entry: "Owl-folk (species)", or with its
    everyday name "Tsardom of Moscavia (place, usually called Moscavia)"."""

    if everyday:
        return f"{name} ({kind}, usually called {everyday})"
    return f"{name} ({kind})"


def mention_context(view: WorldView, thing_id: str) -> list[tuple[str, list[str]]]:
    """`gather_mentions` as one `(heading, facts)` group per mentioning entry
    within the caps: the heading is its `entry_label`, and the facts are its
    mentioning facts, then (for the first three entries) its key facts."""

    context = gather_mentions(view, thing_id)
    key_facts = {about.id: about.facts for about in context.about}
    groups: dict[str, tuple[str, list[str]]] = {}
    for mention in context.mentioned:
        heading, facts = groups.setdefault(
            mention.owner_id,
            (
                entry_label(
                    mention.owner_name, mention.owner_kind, mention.owner_everyday
                ),
                [],
            ),
        )
        facts.append(mention.text)
    return [
        (heading, [*facts, *key_facts.get(owner_id, [])])
        for owner_id, (heading, facts) in groups.items()
    ]


def _sentence(text: str) -> str:
    text = " ".join(text.split())
    return text if not text or text[-1] in _SENTENCE_ENDS else text + "."


def _cut(text: str, limit: int, start: int) -> str:
    """`text` cut to `limit` characters at the last sentence end past
    `start` (not an abbreviation's full stop), or failing that at the last
    whole word."""

    if len(text) <= limit:
        return text

    def ends_sentence(i: int) -> bool:
        words = text[start:i].split()
        return (
            text[i] in _SENTENCE_ENDS
            and text[i + 1].isspace()
            and bool(words)
            and words[-1] not in _ABBREVIATIONS
        )

    for i in range(limit - 1, start - 1, -1):
        if ends_sentence(i):
            return text[: i + 1]
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _home_line(view: WorldView, thing_id: str) -> str:
    """What the thing is filed in, a sentence a filing (`held.filed_as`):
    "Rite of the White Dawn." for one with a role, "Part of the White
    Dawn." without; "" when it's filed nowhere."""

    return " ".join(
        f"{filed_as(filing.role, name)}."
        for filing in filings_of(view, thing_id)
        if (name := view.name_of(filing.target))
    )


def suggested_prompt(view: WorldView, stub_id: str) -> str:
    """The create box's starting prompt for a stub: "<name>: ", the stub's
    own facts (an item a sphere's core made has its text), what it's filed
    in (`_home_line`), then its mentioning facts, rendered and joined
    (the most-mentioning entries first), cut at `PROMPT_MAX` characters on
    a sentence's end. Just the name when there's none of these.

    Its own facts and sphere lead (the spheres Task 10 session): led by
    a character's mention alone, a rite's prompt was written around her."""

    name = view.name_of(stub_id) or ""
    state = view.thing(stub_id)
    own = [
        _sentence(view.render(fact.text))
        for fact in sorted(state.facts if state else [], key=lambda f: f.created)
    ]
    texts = [
        *own,
        _home_line(view, stub_id),
        *(
            _sentence(mention.text)
            for group in _by_entry(mentions(view, stub_id))
            for mention in group
        ),
    ]
    texts = [text for text in texts if text]
    if not texts:
        return name
    prefix = f"{name}: "
    return _cut(prefix + " ".join(texts), PROMPT_MAX, len(prefix))
