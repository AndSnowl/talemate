"""Prose generation and caching for world things.

`render_section` asks the model for a present-tense descriptive profile of
one section -- built from a list of facts, never from a continuing story --
and writes nothing. `generate_section` renders a thing's section from its
facts at `at` and caches the result for the stretch of story time
containing `at` (`World.prose()`, keyed the same way
`talemate.world.prose.stretches` reports them). `ensure_prose` regenerates
whatever section is stale. `create.py` reuses `render_section` for a
preview that isn't in the world yet.

A character has two sections: `description` (from its `appearance` and
`background` facts) and `personality` (from its `personality` facts).
Speech facts never go through here -- `characters.py` reads them straight
into `dialogue_instructions` and `example_dialogue`, no prose needed. Every
other kind has a single `description` section, from all of its facts.
"""

from __future__ import annotations

from typing import Any

import structlog

from talemate.prompts import Prompt
from talemate.world.dates import WorldDate
from talemate.world.kinds import get_kind
from talemate.world.prose import stretches
from talemate.world.store import World
from talemate.world.view import ThingState

log = structlog.get_logger("talemate.worldplay.prose_gen")

# a character's prose sections, and the fact categories each is generated
# from; every other kind has one `description` section from all its facts
SECTIONS: tuple[str, ...] = ("description", "personality")

_SECTION_CATEGORIES: dict[str, tuple[str, ...]] = {
    "description": ("appearance", "background"),
    "personality": ("personality",),
}

# an instant past the proleptic-Gregorian range, mirroring view.py's and
# prose.py's own "+infinity" for at=None
_FAR_FUTURE = 10**15


def sections_for(kind: str) -> tuple[str, ...]:
    """The prose sections a thing of `kind` has."""

    if kind == "character":
        return SECTIONS
    return ("description",)


def section_categories(kind: str, section: str) -> tuple[str, ...]:
    """The fact categories `section` of a `kind` thing is generated from."""

    if kind == "character":
        return _SECTION_CATEGORIES[section]
    return tuple(get_kind(kind).categories)


def _facts_for_section(state: ThingState, section: str) -> list[str]:
    categories = section_categories(state.kind, section)
    return [fact.text for fact in state.facts if fact.category in categories]


def stretch_containing(
    world: World, thing_id: str, at: WorldDate | None
) -> tuple[WorldDate | None, WorldDate | None]:
    """The `(start, end)` stretch -- from `talemate.world.prose.stretches`
    -- that contains `at`. The last, open-ended stretch always matches, so
    this never falls through without a result."""

    at_instant = at.instant if at is not None else _FAR_FUTURE
    for start, end in stretches(lambda: world, thing_id):
        start_instant = start.instant if start is not None else None
        end_instant = end.instant if end is not None else None
        if (start_instant is None or start_instant <= at_instant) and (
            end_instant is None or at_instant < end_instant
        ):
            return start, end
    # unreachable: kept defensive rather than asserting, since a thing with
    # no timeline at all still has one (None, None) stretch from `stretches`
    return None, None


async def render_section(
    kind: str, name: str, section: str, facts: list[str], client: Any
) -> str:
    """Ask the model for `section`'s profile from `facts`, writing nothing.
    With no facts at all there is nothing to describe, so no call is made
    and the prose is empty."""

    if not facts:
        return ""

    _response, extracted = await Prompt.request(
        "world.thing-prose",
        client,
        "create",
        vars={
            "facts": facts,
            "kind": kind,
            "section": section,
            "name": name,
        },
    )
    text: str = extracted["response"].strip()

    # the template primes the response with the thing's name (to keep it
    # third-person and on-topic); a generation that produced nothing comes
    # back as just that name, which is reported as empty prose rather than
    # a one-word profile
    if text == name.strip():
        text = ""
    return text


async def generate_section(
    world: World, thing_id: str, section: str, at: WorldDate | None, client: Any
) -> str:
    """Generate `section`'s prose from the thing's facts at `at`, cache it
    for the stretch containing `at`, and return the text."""

    view = world.view(at)
    state = view.thing(thing_id)
    if state is None:
        raise KeyError(f"no such thing: {thing_id}")

    name = view.name_of(thing_id) or ""
    facts = _facts_for_section(state, section)
    text = await render_section(state.kind, name, section, facts, client)

    # cached at the revision the facts were read at (`view.rev`), not the
    # head when the model returns: a change written while the model was
    # generating then still leaves this entry stale
    start, end = stretch_containing(world, thing_id, at)
    world.prose().put(thing_id, section, start, end, text, rev=view.rev)
    return text


async def ensure_prose(
    world: World, thing_id: str, at: WorldDate | None, client: Any
) -> None:
    """Regenerate every section that's stale at `at` (`World.prose().stale`).
    A section with nothing cached yet counts as stale too."""

    state = world.view(at).thing(thing_id)
    if state is None:
        raise KeyError(f"no such thing: {thing_id}")

    cache = world.prose()
    for section in sections_for(state.kind):
        if cache.stale(thing_id, section, at):
            await generate_section(world, thing_id, section, at, client)
