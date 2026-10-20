"""Characters built from the world, as of a scene's in-world date.

`character_from_world` never calls the model: it reads whatever prose is
already cached (kept fresh by `prose_gen.ensure_prose`, called elsewhere)
and the thing's facts, and builds an ordinary `talemate.character.Character`.

A cached `description` can go stale between a scene's turns -- time passes,
a fact changes, nothing regenerates it on the spot. `since_lines` covers
that gap: it finds whichever cached stretch *is* fresh enough to use, then
walks the thing's full timeline for everything dated since, so the
character sheet still tells the whole story even with stale prose.
"""

from __future__ import annotations

import structlog

from talemate.character import Character
from talemate.util import replace_smart_quotes
from talemate.world.dates import WorldDate
from talemate.world.prose import CachedProse, stretches
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
) -> CachedProse | None:
    """The nearest cached `section` entry at or before `at`, found by
    walking back from the stretch `at` itself falls in past any
    stale/never-generated stretch to the last one that was actually
    generated -- or `None` if nothing has ever been cached at all. The
    `None` case and a found entry whose own `stretch_start` happens to be
    `None` (the thing's very first stretch, "always" up to some dated
    change) are different things: callers must tell them apart by testing
    the return value itself, not any field on it."""

    cache = world.prose()
    stretch_list = stretches(lambda: world, thing_id)
    at_instant = at.instant if at is not None else _FAR_FUTURE
    index = _stretch_index_containing(stretch_list, at_instant)

    for i in range(index, -1, -1):
        start, end = stretch_list[i]
        probe = _probe_within(start, end)
        cached = cache.get(thing_id, section, probe)
        if cached is not None:
            return cached

    return None


def _change_not_yet_known(
    entry: CachedProse | None, date_instant: int, source_rev: int
) -> bool:
    """Whether a timeline change dated at `date_instant`, written in
    revision `source_rev`, could not have made it into the cached
    `entry`'s text.

    `entry=None` (nothing was ever cached) always qualifies. Otherwise,
    either of two independent reasons does:

    - it was written *after* the cache (`source_rev > entry.rev`),
      whatever date it's dated at -- a later revision can backdate a
      change into a stretch the cache already covers (e.g. a fact added
      after the fact, dated inside an already-cached stretch);
    - it's dated at or after what the cache's own stretch covers
      (`entry.stretch_end`, when set -- `None` only for the thing's
      current, still-open stretch, nothing to compare against there).

    Either alone is enough; a stretch-end comparison alone (round 2's
    rule) misses a change backdated into an already-cached span by a
    later revision, and a revision comparison alone would miss a change
    that's simply dated later than the cache, however old the revision
    that added it."""

    if entry is None:
        return True
    if source_rev > entry.rev:
        return True
    return entry.stretch_end is not None and date_instant >= entry.stretch_end.instant


def since_lines(world: World, thing_id: str, at: WorldDate | None) -> list[str]:
    """One line per appearance/background fact not yet reflected in the
    cached description, in story-time order, e.g. `"Since 314: Lost her
    left eye."`, `"Until 316: Member of the Wardens."`, or (started and
    ended without the cache ever catching up) `"From 310 until 312: A cast
    on her arm."`. Dates are formatted by the world's calendar.

    Driven from `World.timeline(thing_id)` -- every dated fact start/end
    for the thing, regardless of story-time visibility at any one date --
    rather than from what's visible in a `world.view(...)` snapshot. A
    snapshot approach has a hole no pair of snapshots closes: a fact that
    both starts and ends between two dates never appears in a snapshot
    taken at either one. The timeline doesn't have that hole, since it
    reports every change directly.

    "Not yet reflected" is `_change_not_yet_known` (see its docstring for
    the exact rule -- it's not just "dated after the cache's stretch
    ends": a revision written after the cache counts too, whatever date
    it backdates its change to). A change dated after `at` is never
    reported either way, or it would leak the future. An undated
    ("always") start or end isn't a reportable moment and is skipped.

    With nothing cached at all, an undated-start appearance/background
    fact still visible at `at` gets a plain line (no "Since"/"Until" --
    there's no single date to attach), so a character with no prose yet
    still has *some* description; an undated fact otherwise never
    produces a timeline entry of its own to report.

    A fact_id with a start, an end, or both not yet known gets exactly
    one line: both -> "From ... until ...", only a start -> "Since ...",
    only an end -> "Until ..." (its start was already known -- either
    baked into the cached text, or, with nothing cached, not itself
    newsworthy)."""

    at_instant = at.instant if at is not None else _FAR_FUTURE
    entry = _cached_section(world, thing_id, "description", at)

    lines: list[str] = []

    if entry is None:
        at_state = world.view(at).thing(thing_id)
        if at_state is not None:
            for fact in at_state.facts:
                if fact.category in _DESCRIPTION_CATEGORIES and fact.valid_from is None:
                    lines.append(fact.text)

    order: list[str] = []
    starts: dict[str, WorldDate] = {}
    ends: dict[str, WorldDate] = {}
    texts: dict[str, str] = {}

    for change in world.timeline(thing_id):
        if change.change not in ("fact_start", "fact_end"):
            continue
        if change.category not in _DESCRIPTION_CATEGORIES:
            continue
        if change.date is None:
            continue  # "always" -- not a reportable moment
        if change.date.instant > at_instant:
            continue  # never emit a change dated after `at`
        if not _change_not_yet_known(entry, change.date.instant, change.source_rev):
            continue

        fact_id = change.fact_id
        if fact_id not in texts:
            order.append(fact_id)
        texts[fact_id] = change.text
        if change.change == "fact_start":
            starts[fact_id] = change.date
        else:
            ends[fact_id] = change.date

    calendar = world.calendar
    for fact_id in order:
        start, end, text = starts.get(fact_id), ends.get(fact_id), texts[fact_id]
        if start is not None and end is not None:
            lines.append(
                f"From {calendar.format(start)} until {calendar.format(end)}: {text}"
            )
        elif start is not None:
            lines.append(f"Since {calendar.format(start)}: {text}")
        else:
            lines.append(f"Until {calendar.format(end)}: {text}")

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

    description_entry = _cached_section(world, thing_id, "description", at)
    description_text = description_entry.text if description_entry is not None else ""
    description = "\n".join(
        part for part in [description_text, *since_lines(world, thing_id, at)] if part
    )

    base_attributes: dict[str, object] = {}

    born = state.fields.get("born")
    if born is not None:
        base_attributes["age"] = _age_in_years(born, at)
        base_attributes["born"] = world.calendar.format(born)

    personality_entry = _cached_section(world, thing_id, "personality", at)
    if personality_entry is not None and personality_entry.text:
        base_attributes["personality"] = personality_entry.text

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
