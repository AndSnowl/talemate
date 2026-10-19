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


def _cached_description(
    world: World, thing_id: str, at: WorldDate | None
) -> tuple[str, WorldDate | None]:
    """The nearest cached `description` entry at or before `at`: its text,
    and the start of the stretch it was cached for. `("", None)` if
    nothing has ever been cached, including the stretch `at` itself falls
    in -- this is what lets a stale cache still have a horizon for
    `since_lines` to measure from, by walking back to the last stretch that
    was actually generated."""

    cache = world.prose()
    stretch_list = stretches(lambda: world, thing_id)
    at_instant = at.instant if at is not None else _FAR_FUTURE
    index = _stretch_index_containing(stretch_list, at_instant)

    for i in range(index, -1, -1):
        start, end = stretch_list[i]
        if start is not None:
            probe = start
        elif end is None:
            # the only stretch there is: "always", still open
            probe = None
        else:
            # before the thing's own timeline begins -- nothing was ever
            # cached for it, and there's no date within it to probe with
            continue
        cached = cache.get(thing_id, "description", probe)
        if cached is not None:
            return cached.text, cached.stretch_start

    return "", None


def since_lines(world: World, thing_id: str, at: WorldDate | None) -> list[str]:
    """One line per appearance/background fact that started or ended after
    the cached description's stretch began, e.g. `"Since 314: lost her left
    eye."` or `"Until 316: member of the Wardens."`, the year formatted by
    the world's calendar."""

    state = world.view(at).thing(thing_id)
    if state is None:
        return []

    _text, stretch_start = _cached_description(world, thing_id, at)
    horizon = stretch_start.instant if stretch_start is not None else None

    calendar = world.calendar
    lines = []
    for fact in state.facts:
        if fact.category not in _DESCRIPTION_CATEGORIES:
            continue
        started_after = fact.valid_from is not None and (
            horizon is None or fact.valid_from.instant > horizon
        )
        ended_after = fact.valid_until is not None and (
            horizon is None or fact.valid_until.instant > horizon
        )
        if started_after:
            lines.append(f"Since {calendar.format(fact.valid_from)}: {fact.text}")
        elif ended_after:
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

    description_text, _stretch_start = _cached_description(world, thing_id, at)
    description = "\n".join(
        part for part in [description_text, *since_lines(world, thing_id, at)] if part
    )

    base_attributes: dict[str, object] = {}

    born = state.fields.get("born")
    if born is not None:
        base_attributes["age"] = at.to_datetime().year - born.to_datetime().year
        base_attributes["born"] = world.calendar.format(born)

    personality_cached = world.prose().get(thing_id, "personality", at)
    if personality_cached is not None and personality_cached.text:
        base_attributes["personality"] = personality_cached.text

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
