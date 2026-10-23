"""Characters built from the world, as of a scene's in-world date.

`character_from_world` never calls the model: it reads whatever prose is
already cached (kept fresh by `prose_gen.ensure_prose`, called elsewhere)
and the thing's facts, and builds an ordinary `talemate.character.Character`.

A cached `description` can go stale between a scene's turns -- time passes,
a fact changes, nothing regenerates it on the spot. `since_lines` covers
that gap: it finds whichever cached stretch *is* fresh enough to use, then
walks the thing's full timeline for everything dated since, so the
character sheet still tells the whole story even with stale prose.

Inheritance is resolved here in code, as of the scene's date: the stretches
follow the character's lineage (`prose_gen.lineage_ids`), the since lines
cover the description facts it inherits, its life stage comes from its
heritage's numbers, and a deleted ancestor simply drops out of the lineage.
"""

from __future__ import annotations

import re

import structlog

from talemate.character import Character
from talemate.util import replace_smart_quotes
from talemate.world import heritage, spheres
from talemate.world.calendar import Calendar
from talemate.world.dates import Precision, WorldDate
from talemate.world.prose import CachedProse, stretches
from talemate.world.refs import REF_PATTERN
from talemate.world.store import World
from talemate.world.timeline import TimelineEntry
from talemate.world.view import ThingState, WorldView
from talemate.worldplay.held import (  # noqa: F401 -- re-exported
    _mid_sentence,
    _opens_with_a_name,
    attributes_itself,
    held_text,
)
from talemate.worldplay.prose_gen import inherited_categories, lineage_ids

log = structlog.get_logger("talemate.worldplay.characters")

# the fact categories `since_lines` watches -- the same ones `prose_gen`
# builds the "description" section from
_DESCRIPTION_CATEGORIES = ("appearance", "background")

_FAR_FUTURE = 10**15

# how character creation ends an exception's `ties` fact, linking what it
# departs from: a thing item, or (for a statement item) the sphere
DEPARTS_FROM = "Departs from"
DEPARTS_FROM_TEACHING = "Departs from a teaching of"

_DEPARTS_SUFFIX = re.compile(
    r"\s*(?:%s|%s)\s+%s\s*$"
    % (
        re.escape(DEPARTS_FROM_TEACHING),
        re.escape(DEPARTS_FROM),
        REF_PATTERN.pattern,
    )
)

# the `Character` fields `character_from_world` derives from the world;
# every other field is per-scene state (color, avatar, voice, details, ...)
WORLD_DERIVED_FIELDS = (
    "name",
    "description",
    "base_attributes",
    "dialogue_instructions",
    "example_dialogue",
)


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
    stretch_list = stretches(lambda: world, thing_id, lineage_ids(world, thing_id, at))
    at_instant = at.instant if at is not None else _FAR_FUTURE
    index = _stretch_index_containing(stretch_list, at_instant)

    for i in range(index, -1, -1):
        start, end = stretch_list[i]
        probe = _probe_within(start, end)
        cached = cache.get(thing_id, section, probe)
        if cached is not None:
            return cached

    return None


def _date_known(entry: CachedProse, date: WorldDate | None) -> bool:
    """Whether the cached `entry`'s stretch covers a change dated `date`,
    going by date alone: everything before its `stretch_end` (all of it,
    for an open stretch). An undated change is never past a stretch end."""

    return (
        entry.stretch_end is None
        or date is None
        or date.instant < entry.stretch_end.instant
    )


def _not_yet_known(
    entry: CachedProse | None, date: WorldDate | None, source_rev: int
) -> bool:
    """Whether a timeline change dated `date`, written in revision
    `source_rev`, could not have made it into the cached `entry`'s text.

    `entry=None` (nothing was ever cached) always qualifies. Otherwise,
    either of two independent reasons does:

    - it was written *after* the cache (`source_rev > entry.rev`),
      whatever its date -- a later revision can add an undated fact, or
      backdate one into a stretch the cache already covers;
    - it's dated at or after the cache's `stretch_end`, when that's set.
    """

    if entry is None:
        return True
    return source_rev > entry.rev or not _date_known(entry, date)


def _facts_at_rev(
    world: World, thing_id: str, rev: int
) -> dict[str, tuple[TimelineEntry, TimelineEntry | None]]:
    """Each fact live for `thing_id` at `rev`, as its (start, end) timeline
    entries -- end `None` for an open-ended fact. Empty if the thing
    didn't exist yet at `rev`."""

    try:
        timeline = world.timeline(thing_id, rev=rev)
    except KeyError:
        return {}

    # a fact's start always sorts before its end in a timeline
    facts: dict[str, tuple[TimelineEntry, TimelineEntry | None]] = {}
    for change in timeline:
        if change.fact_id is None:
            continue
        if change.change == "fact_start":
            facts[change.fact_id] = (change, None)
        elif change.change == "fact_end":
            facts[change.fact_id] = (facts[change.fact_id][0], change)
    return facts


def _same_date(a: WorldDate | None, b: WorldDate | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return bool(a.instant == b.instant)


def _change_lines(
    world: World,
    thing_id: str,
    categories: tuple[str, ...],
    entry: CachedProse | None,
    at: WorldDate | None,
    prefix: str = "",
    skip: frozenset[str] = frozenset(),
) -> list[tuple[int, str]]:
    """`since_lines`' lines for the facts of `thing_id` -- the character
    itself, or a layer it inherits from -- in `categories`, against the
    cached `entry`, as `(lead date's instant, line)` pairs, undated lines
    keyed first. `prefix` leads each line's text; fact ids in `skip` get
    no line."""

    at_instant = at.instant if at is not None else _FAR_FUTURE
    cached_facts = (
        _facts_at_rev(world, thing_id, entry.rev) if entry is not None else {}
    )
    # each fact as it is now, for its held-by (`held_text`)
    live = {fact.fact_id: fact for fact in world.live_facts(thing_id)}

    def dated_by_at(date: WorldDate | None) -> bool:
        return date is None or date.instant <= at_instant

    calendar = world.calendar
    view = world.view(at)
    owner = view.thing(thing_id)
    keyed: list[tuple[int, str]] = []
    for fact_id, (start, end) in _facts_at_rev(
        world, thing_id, world.head_rev()
    ).items():
        if start.category not in categories or fact_id in skip:
            continue

        # the revisions that wrote this start and end, as far as the cached
        # text is concerned: lineage carries an unchanged start (and end)
        # back to the version that was live when the cache was written
        start_rev = start.source_rev
        end_rev = end.source_rev if end is not None else 0
        old_start, old_end = cached_facts.get(fact_id, (None, None))
        if (
            old_start is not None
            and old_start.category in categories
            and old_start.text == start.text
            and _same_date(old_start.date, start.date)
        ):
            start_rev = old_start.source_rev
            if end is not None and old_end is not None:
                if _same_date(old_end.date, end.date):
                    end_rev = old_end.source_rev

        end_date = end.date if end is not None else None
        ended = end_date is not None and dated_by_at(end_date)
        start_news = dated_by_at(start.date) and _not_yet_known(
            entry, start.date, start_rev
        )
        end_news = ended and _not_yet_known(entry, end_date, end_rev)

        text = view.render(start.text or "")
        if owner is not None and fact_id in live:
            text = held_text(view, live[fact_id], owner, text)
        text = prefix + text
        if start_news and start.date is not None and end_date is not None and ended:
            line = (
                f"From {calendar.format(start.date)} until "
                f"{calendar.format(end_date)}: {text}"
            )
            keyed.append((start.date.instant, line))
        elif (start_news or end_news) and end_date is not None and ended:
            keyed.append(
                (end_date.instant, f"Until {calendar.format(end_date)}: {text}")
            )
        elif start_news and start.date is not None:
            keyed.append(
                (start.date.instant, f"Since {calendar.format(start.date)}: {text}")
            )
        elif start_news:
            keyed.append((-_FAR_FUTURE, text))
    return keyed


def since_lines(world: World, thing_id: str, at: WorldDate | None) -> list[str]:
    """One line per appearance/background change not yet reflected in the
    cached description, in story-time order, e.g. `"Since 314: Lost her
    left eye."`, `"Until 316: Member of the Wardens."`, `"From 310 until
    312: A cast on her arm."`, or a plain `"Has a limp."` for an undated
    fact. Dates are formatted by the world's calendar.

    The description facts the thing inherits as of `at`
    (`prose_gen.inherited_categories`: a species', race's or mix's
    `physical` and `variation` facts, a culture's dress) get lines too,
    worded the same and prefixed with their source's name, e.g. `"Since
    500: Owl-folk: live to about 60 years."`. Overridden ones get none.
    Own lines come before inherited ones of the same date. A layer that
    wasn't in the lineage when the description was cached counts as never
    cached, so all of its facts dated by `at` get lines.

    Driven from `World.timeline(thing_id)` -- every fact start/end for the
    thing, regardless of story-time visibility at any one date -- since a
    fact that both starts and ends between two dates never shows up in a
    `world.view(...)` snapshot taken at either one.

    A change needs a line when it's dated at or before `at` (an undated
    change counts as before) and `_not_yet_known` says the cached text
    can't reflect it: nothing is cached, it was written after the cache,
    or it's dated at or after the cache's `stretch_end`. Nothing dated
    after `at` is ever reported, or it would leak the future.

    An undated fact is only in the cached text if it existed when the
    cache was written: one added by a later revision gets a plain line
    (or "Until ..." once it has ended), as does every undated fact still
    true at `at` when nothing is cached at all.

    Lineage: `correct_fact`/`end_fact` write a new version of a fact under
    the same fact_id, with the revision that wrote it. When the version
    live at the cache's `rev` was a description fact with the same start
    and text, the prose already reflects that start, so only what changed
    is news -- typically a new end, giving "Until ..." alone, never a
    repeated "Since"/"From" for the start. A changed text (or start) makes
    the fact news again, reported with its current dates.

    Each fact_id gets at most one line: start and end both news -> "From
    ... until ...", only the start -> "Since ..." (plain when undated),
    only the end, or an undated start with an end -> "Until ..."."""

    entry = _cached_section(world, thing_id, "description", at)
    keyed = _change_lines(world, thing_id, _DESCRIPTION_CATEGORIES, entry, at)

    view = world.view(at)
    overridden = frozenset(
        item.fact.fact_id
        for item in heritage.inherited(view, thing_id)
        if item.overridden_by is not None
    )
    # the layers the cached text was written with, as of a date inside the
    # entry's own stretch (`at` can be past it, after a dated heritage
    # change); a layer the character has come to inherit from since (a
    # heritage switch to a race that already existed) is news in full,
    # however old its facts are
    cached_layers: set[str] = set()
    if entry is not None:
        written_at = _probe_within(entry.stretch_start, entry.stretch_end)
        cached_layers = set(lineage_ids(world, thing_id, written_at, entry.rev))
    by_kind = inherited_categories("description")
    for layer in heritage.lineage(view, thing_id):
        categories = by_kind.get(layer.kind, ())
        if layer.depth == 0 or not categories:
            continue
        prefix = f"{layer.name}: " if layer.name else ""
        layer_entry = entry if layer.thing_id in cached_layers else None
        keyed += _change_lines(
            world, layer.thing_id, categories, layer_entry, at, prefix, overridden
        )

    # a stable sort, so own lines stay ahead of inherited ones on a date
    keyed.sort(key=lambda pair: pair[0])
    return [line for _, line in keyed]


def _speech_facts(view: WorldView, state: ThingState) -> tuple[list[str], list[str]]:
    """Speech facts split into dialogue instructions and example lines --
    a fact that reads like something the character would say (it starts
    with a quote mark) is an example; anything else is an instruction."""

    dialogue_instructions = []
    example_dialogue = []
    for fact in state.facts:
        if fact.category != "speech":
            continue
        text = view.render(fact.text).strip()
        if replace_smart_quotes(text).startswith(('"', "'")):
            example_dialogue.append(text)
        else:
            dialogue_instructions.append(text)
    return dialogue_instructions, example_dialogue


def exception_text(text: str) -> str:
    """An exception fact's raw text less the "Departs from <link>" (or
    "Departs from a teaching of <link>") sentence character creation ends
    it with: that link is for the world's pages, not for reading."""

    return _DEPARTS_SUFFIX.sub("", text).strip()


def mid_sentence_name(name: str) -> str:
    """A name as it reads mid-sentence: a leading "The" lowercased ("of
    the White Dawn")."""

    return "the " + name[4:] if name.startswith("The ") else name


def tie_lines(view: WorldView, calendar: Calendar, thing_id: str) -> list[str]:
    """One line per tie of the character's that holds at `view.at`, e.g.
    "Practitioner of the White Dawn (since 1010), but: doesn't believe
    snowy owl-folk are superior": the role capitalised, "(since <year>)"
    when the tie has a since, and its exceptions (`spheres.exceptions`, in
    the order they were written) joined with "; ". A tie stores its
    sphere's id, not its name, so a tie to a sphere that's since been
    deleted, or that has no name at the view's date, is left out. The
    since is given as its year, however precise."""

    lines: list[str] = []
    for tie in spheres.ties_of(view, thing_id, live=True):
        name = view.name_of(tie.sphere_id)
        if view.thing(tie.sphere_id) is None or not name:
            continue
        role = tie.role.strip() or "member"
        line = f"{role[0].upper()}{role[1:]} of {mid_sentence_name(name)}"
        if tie.since is not None:
            year = WorldDate(instant=tie.since.instant, precision=Precision.YEAR)
            line += f" (since {calendar.format(year)})"
        texts = [
            _mid_sentence(view, raw, view.render(raw))
            for fact in sorted(
                spheres.exceptions(view, thing_id, tie.sphere_id),
                key=lambda fact: fact.created,
            )
            if (raw := exception_text(fact.text))
        ]
        texts = [text for text in texts if text]
        if texts:
            line += ", but: " + "; ".join(texts)
        lines.append(line)
    return lines


def age_in_years(born: WorldDate, at: WorldDate) -> int:
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
    # a safety net for overrides missed when the character was created
    # (the local model skips some deep-layer ones): the agents read that
    # the character's own traits win over anything inherited
    inherits = any(
        layer.depth > 0 for _, layer in heritage.effective_facts(view, thing_id)
    )
    own_traits_line = (
        f"Where {name}'s own traits differ from those of their kind, "
        f"{name}'s own traits hold."
        if inherits
        else ""
    )
    description = "\n".join(
        part
        for part in [
            description_text,
            *since_lines(world, thing_id, at),
            own_traits_line,
        ]
        if part
    )

    base_attributes: dict[str, object] = {}

    born = state.fields.get("born")
    if born is not None:
        age = age_in_years(born, at)
        base_attributes["age"] = age
        base_attributes["born"] = world.calendar.format(born)
        stage, _past_lifespan = heritage.life_stage(
            age, heritage.numbers(view, thing_id)
        )
        if stage is not None:
            base_attributes["life_stage"] = stage

    ties = tie_lines(view, world.calendar, thing_id)
    if ties:
        base_attributes["ties"] = "\n".join(ties)

    personality_entry = _cached_section(world, thing_id, "personality", at)
    if personality_entry is not None and personality_entry.text:
        base_attributes["personality"] = personality_entry.text

    dialogue_instructions, example_dialogue = _speech_facts(view, state)

    return Character(
        name=name,
        description=description,
        base_attributes=base_attributes,
        dialogue_instructions="\n".join(dialogue_instructions) or None,
        example_dialogue=example_dialogue,
        is_player=is_player,
        world_thing_id=thing_id,
    )
