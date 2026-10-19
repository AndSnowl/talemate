"""Characters built from the world, as of a scene's in-world date.

`character_from_world` never calls the model: it reads whatever prose is
already cached (kept fresh by `prose_gen.ensure_prose`, called elsewhere)
and the thing's facts, and builds an ordinary `talemate.character.Character`.

A cached `description` can go stale between a scene's turns -- time passes,
a fact changes, nothing regenerates it on the spot. `since_lines` covers
that gap: it walks back to whichever stretch's description *is* cached and
reports every fact that started or ended after that stretch began, so the
character sheet still tells the whole story even with stale prose.
"""

from __future__ import annotations

import structlog

from talemate.character import Character
from talemate.util import replace_smart_quotes
from talemate.world.dates import WorldDate
from talemate.world.prose import stretches
from talemate.world.store import World
from talemate.world.view import ThingState

log = structlog.get_logger("talemate.worldplay.characters")

# the fact categories `since_lines` watches -- the same ones `prose_gen`
# builds the "description" section from
_DESCRIPTION_CATEGORIES = ("appearance", "background")

_FAR_FUTURE = 10**15


def _stretch_index_containing(
    stretch_list: list[tuple[WorldDate | None, WorldDate | None]], at_instant: int
) -> int:
    for index, (start, end) in enumerate(stretch_list):
        start_instant = start.instant if start is not None else None
        end_instant = end.instant if end is not None else None
        if (start_instant is None or start_instant <= at_instant) and (
            end_instant is None or at_instant < end_instant
        ):
            return index
    return len(stretch_list) - 1


def _probe_within(start: WorldDate | None, end: WorldDate | None) -> WorldDate | None:
    """A date that `ProseCache.get` resolves to exactly the `[start, end)`
    stretch -- `start` itself when there is one (the lower bound is
    inclusive); otherwise an instant just short of `end` (`end`'s own
    instant minus one second), since `cache.get`'s NULL-start matches at
    *any* date and only `end` need be respected; `None` ("+infinity", only
    matches a NULL `stretch_end`) when the stretch is `(None, None)` --
    the thing's entire timeline, still open."""

    if start is not None:
        return start
    if end is None:
        return None
    return WorldDate(instant=end.instant - 1, precision=end.precision)


def _cached_section(
    world: World, thing_id: str, section: str, at: WorldDate | None
) -> tuple[str, WorldDate | None]:
    """The nearest cached `section` entry at or before `at`: its text, and
    the start of the stretch it was cached for. `("", None)` if nothing
    has ever been cached, including for the stretch `at` itself falls in
    -- this is what lets a stale cache still have a horizon for
    `since_lines` to measure from, by walking back to the last stretch
    that was actually generated."""

    cache = world.prose()
    stretch_list = stretches(lambda: world, thing_id)
    at_instant = at.instant if at is not None else _FAR_FUTURE
    index = _stretch_index_containing(stretch_list, at_instant)

    for i in range(index, -1, -1):
        start, end = stretch_list[i]
        probe = _probe_within(start, end)
        cached = cache.get(thing_id, section, probe)
        if cached is not None:
            return cached.text, cached.stretch_start

    return "", None


def since_lines(world: World, thing_id: str, at: WorldDate | None) -> list[str]:
    """One line per appearance/background fact not yet reflected in the
    cached description, e.g. `"Since 314: Lost her left eye."` or `"Until
    316: Member of the Wardens."`, the date formatted by the world's
    calendar.

    "Not yet reflected" is measured against the *horizon*: the start of
    whichever stretch the cached description actually comes from (from
    `_cached_section`, which walks back past stale/never-generated
    stretches to find it -- see its docstring). A fact gets a line if:

    - it's visible now (`world.view(at)`) and started after the horizon
      ("Since") -- it wasn't there yet when that prose was written;
    - it was visible *at* the horizon (so it *was* baked into that prose)
      but has since ended, and ended no later than `at` ("Until") -- a
      fact that will end later than `at` is left alone; reporting it
      early would leak the future and contradict prose that still
      describes it as true.

    A fact can't satisfy both at once: `world.view(at)` never includes a
    fact already ended by `at`, so the two sources (the view at `at` and
    the view at the horizon) don't overlap for ended facts. A fact that
    both starts and ends strictly between the horizon and `at` -- so it
    appears in neither view -- gets no line; this is a known gap, not
    exercised by anything that calls into this today.

    When nothing has ever been cached (`horizon is None`, `_cached_section`
    found no stretch to anchor to), every fact visible at `at` counts as
    "Since" -- there's no baseline text it could already be reflected in
    -- and nothing can be an "Until", since there's no horizon a fact
    could have been "valid at"."""

    at_state = world.view(at).thing(thing_id)
    if at_state is None:
        return []

    _text, horizon_date = _cached_section(world, thing_id, "description", at)
    horizon = horizon_date.instant if horizon_date is not None else None
    at_instant = at.instant if at is not None else _FAR_FUTURE

    horizon_facts = (
        world.view(horizon_date).thing(thing_id).facts
        if horizon_date is not None
        else []
    )

    calendar = world.calendar
    lines = []

    for fact in at_state.facts:
        if fact.category not in _DESCRIPTION_CATEGORIES:
            continue
        started_after = fact.valid_from is not None and (
            horizon is None or fact.valid_from.instant > horizon
        )
        if started_after:
            lines.append(f"Since {calendar.format(fact.valid_from)}: {fact.text}")

    for fact in horizon_facts:
        if fact.category not in _DESCRIPTION_CATEGORIES:
            continue
        if fact.valid_until is None:
            continue
        if fact.valid_until.instant > at_instant:
            # hasn't ended yet as of `at` -- still true, no leak
            continue
        lines.append(f"Until {calendar.format(fact.valid_until)}: {fact.text}")

    return lines


def _speech_facts(state: ThingState) -> tuple[list[str], list[str]]:
    """Speech facts split into dialogue instructions and example lines --
    a fact that reads like something the character would say (it starts
    with a quote mark) is an example; anything else is an instruction."""

    dialogue_instructions = []
    example_dialogue = []
    for fact in state.facts:
        if fact.category != "speech":
            continue
        text = fact.text.strip()
        if replace_smart_quotes(text).startswith(('"', "'")):
            example_dialogue.append(text)
        else:
            dialogue_instructions.append(text)
    return dialogue_instructions, example_dialogue


def _age_in_years(born: WorldDate, at: WorldDate) -> int:
    """Full years elapsed from `born` to `at`, allowing for the birthday
    not having happened yet this year (a naive `at.year - born.year`
    overcounts by one for every date before it)."""

    born_dt, at_dt = born.to_datetime(), at.to_datetime()
    age = at_dt.year - born_dt.year
    if (at_dt.month, at_dt.day) < (born_dt.month, born_dt.day):
        age -= 1
    return age


def character_from_world(
    world: World, thing_id: str, at: WorldDate, *, is_player: bool
) -> Character:
    """Build a `Character` from the world as of `at`. Never calls the
    model -- prose must already be cached (`prose_gen.ensure_prose`)."""

    view = world.view(at)
    state = view.thing(thing_id)
    if state is None:
        raise KeyError(f"no such thing: {thing_id}")

    name = view.name_of(thing_id) or ""

    description_text, _stretch_start = _cached_section(
        world, thing_id, "description", at
    )
    description = "\n".join(
        part for part in [description_text, *since_lines(world, thing_id, at)] if part
    )

    base_attributes: dict[str, object] = {}

    born = state.fields.get("born")
    if born is not None:
        base_attributes["age"] = _age_in_years(born, at)
        base_attributes["born"] = world.calendar.format(born)

    personality_text, _stretch_start = _cached_section(
        world, thing_id, "personality", at
    )
    if personality_text:
        base_attributes["personality"] = personality_text

    dialogue_instructions, example_dialogue = _speech_facts(state)

    return Character(
        name=name,
        description=description,
        base_attributes=base_attributes,
        dialogue_instructions="\n".join(dialogue_instructions) or None,
        example_dialogue=example_dialogue,
        is_player=is_player,
        world_thing_id=thing_id,
    )
