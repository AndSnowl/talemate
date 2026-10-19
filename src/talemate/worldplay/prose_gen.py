"""Prose generation and caching for world things.

The only module in `worldplay` that calls the model. `generate_section`
asks it for a present-tense descriptive profile of one section -- built
from the thing's facts, never from a continuing story -- and caches the
result for the stretch of story time containing `at` (`World.prose()`,
keyed the same way `talemate.world.prose.stretches` reports them).
`ensure_prose` regenerates whatever section is stale.

Two sections only: `description` (from the thing's `appearance` and
`background` facts) and `personality` (from its `personality` facts).
Speech facts never go through here -- `characters.py` reads them straight
into `dialogue_instructions` and `example_dialogue`, no prose needed.
"""

from __future__ import annotations

from typing import Any

import structlog

from talemate.prompts import Prompt
from talemate.world.dates import WorldDate
from talemate.world.prose import stretches
from talemate.world.store import World
from talemate.world.view import ThingState

log = structlog.get_logger("talemate.worldplay.prose_gen")

# the two sections a thing's prose is split into, and the fact categories
# each is generated from
SECTIONS: tuple[str, ...] = ("description", "personality")

_SECTION_CATEGORIES: dict[str, tuple[str, ...]] = {
    "description": ("appearance", "background"),
    "personality": ("personality",),
}

# an instant past the proleptic-Gregorian range, mirroring view.py's and
# prose.py's own "+infinity" for at=None
_FAR_FUTURE = 10**15


def _facts_for_section(state: ThingState, section: str) -> list[str]:
    categories = _SECTION_CATEGORIES[section]
    return [fact.text for fact in state.facts if fact.category in categories]


def _stretch_containing(
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

    _response, extracted = await Prompt.request(
        "world.thing-prose",
        client,
        "create",
        vars={
            "facts": facts,
            "kind": state.kind,
            "section": section,
            "name": name,
        },
    )
    text = extracted["response"].strip()

    # the template primes the response with the thing's name (to keep it
    # third-person and on-topic); a generation that produced nothing comes
    # back as just that name, which is reported as empty prose rather than
    # a one-word profile
    if text == name.strip():
        text = ""

    start, end = _stretch_containing(world, thing_id, at)
    world.prose().put(thing_id, section, start, end, text)
    return text


async def ensure_prose(
    world: World, thing_id: str, at: WorldDate | None, client: Any
) -> None:
    """Regenerate every section that's stale at `at` (`World.prose().stale`).
    A section with nothing cached yet counts as stale too."""

    cache = world.prose()
    for section in SECTIONS:
        if cache.stale(thing_id, section, at):
            await generate_section(world, thing_id, section, at, client)
