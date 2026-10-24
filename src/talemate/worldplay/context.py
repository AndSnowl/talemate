"""The scene-level world context: the "World" instruction injected into
narrator and actor prompts, and keeping a scene's active characters built
fresh from the world as its clock moves.

The World instruction names who is here by heritage, with each one's body
and instincts (`_cast`), resolved in code as of the scene's date. The
narrator's prompts carry no character sheets -- only what long-term memory
happens to retrieve -- and the heritage play probe
(docs/superpowers/probes/2026-10-20-heritage-play.md) found it writing
owl-folk with hands, fingers and hair when nothing reminded it.

Loading a world scene (`talemate.load.load_world_scene`) attaches the
context and calls `connect`; a scene that never gets a
`scene.world_context` is left alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import structlog

import talemate.emit.async_signals as async_signals
from talemate.agents.base import DynamicInstruction
from talemate.prompts import Prompt
from talemate.world import entries, heritage
from talemate.world.curation import CurationSettings
from talemate.world.dates import WorldDate
from talemate.world.filing import filed_index, filings_of, tag_of
from talemate.world.kinds import HERITAGE_KINDS
from talemate.world.names import everyday_name, find_names
from talemate.world.repeats import overlap
from talemate.world.scenes import SceneRecord
from talemate.world.store import World
from talemate.world.timelines import TimelineLine, dated_line, entry_timeline
from talemate.world.view import FactState, ThingState, WorldView

from .characters import (
    WORLD_DERIVED_FIELDS,
    character_from_world,
    filing_lines,
    held_text,
)
from .held import timeline_text

log = structlog.get_logger("talemate.worldplay.context")

# the scene-local thing kinds of a place and a character invented for a
# scene (`persistence` re-exports the character's)
LOCAL_PLACE_KIND = "place"
LOCAL_CHARACTER_KIND = "character"

# the heritage fact categories the cast lines carry: the body, then how
# the kind behaves
_BODY_CATEGORIES = ("physical", "variation")
_INSTINCT_CATEGORIES = ("instinct",)

SECTION_TITLE = "World"

# a touched entry's lines (filing spec, "Scene context"; probe 5): up to
# this many of its own facts, its latest this many timeline lines, and at
# most this many lines in all
TOUCHED_FACTS = 5
TOUCHED_TIMELINE = 3
TOUCHED_LINES = 8

# filing roles too broad to say who a scene is about (ruling F4): a
# setup that says "a member of the Order" touches no member of it. The
# probe's own list ("member", "part", "practitioner", "of this culture")
# and the like
GENERIC_ROLES: frozenset[str] = frozenset(
    {
        "in",
        "of",
        "part",
        "member",
        "members",
        "practitioner",
        "follower",
        "believer",
        "adherent",
        "faithful",
        "citizen",
        "subject",
        "resident",
        "inhabitant",
        "native",
        "people",
        "folk",
        "branch of",
        "of this culture",
        "took place in",
        "owned by",
    }
)


def scene_date(record: SceneRecord, scene_ts: str) -> WorldDate:
    """The in-world date `scene_ts` (an ISO-8601 duration elapsed since the
    scene's start, `scene.ts`) lands on."""

    return record.start.plus(scene_ts)


def _heritage_name(view: WorldView, heritage_id: str) -> str:
    """`Snowy, a race of Owl-folk`, `Half-orc, a mix of Lowlander and Orc`,
    `Owl-folk, a species`: a heritage thing as a cast line names it. A
    name missing at the view's date (a deleted parent, a heritage not yet
    named) is left out rather than shown blank."""

    state = view.thing(heritage_id)
    name = view.name_of(heritage_id) or ""
    if state is None:
        return name
    if state.kind == "race":
        species = state.fields.get("species")
        species_name = view.name_of(species) if isinstance(species, str) else None
        kind = f"a race of {species_name}" if species_name else ""
    elif state.kind == "mix":
        parents = [
            parent_name
            for parent in state.fields.get("parents") or []
            if isinstance(parent, str) and (parent_name := view.name_of(parent))
        ]
        kind = f"a mix of {' and '.join(parents)}" if parents else ""
    else:
        kind = f"a {state.kind}"
    return ", ".join(part for part in (name, kind) if part)


def _traits(
    view: WorldView, thing_id: str, character: bool
) -> tuple[list[str], list[str]]:
    """`(body, instincts)` fact texts as of `view`, overrides applied, in
    layer order: of the heritage `thing_id` itself and what it inherits
    or, for a `character`, of its heritage layers, led by the character's
    own facts that override one of them (her black eyes, in place of her
    kind's yellow ones)."""

    body: list[str] = []
    instincts: list[str] = []
    for fact, layer in heritage.effective_facts(view, thing_id):
        if character and layer.depth == 0:
            if fact.overrides:
                body.append(view.render(fact.text))
            continue
        if layer.kind not in HERITAGE_KINDS:
            continue
        if fact.category in _BODY_CATEGORIES:
            body.append(view.render(fact.text))
        elif fact.category in _INSTINCT_CATEGORIES:
            instincts.append(view.render(fact.text))
    return body, instincts


def _present(record: SceneRecord) -> list[dict[str, Any]]:
    """The scene's character entries that are here: the player (first,
    when the characters don't list them) and every active character."""

    entries = [
        entry
        for entry in record.state.get("characters") or []
        if isinstance(entry, dict)
    ]
    if record.player_thing_id and not any(
        entry.get("thing_id") == record.player_thing_id for entry in entries
    ):
        entries.insert(0, {"thing_id": record.player_thing_id, "active": True})
    return [entry for entry in entries if entry.get("active", True)]


def _cast(world: World, record: SceneRecord, view: WorldView) -> list[dict]:
    """The scene's player and active characters that have a heritage, each
    as `{"name", "heritage", "body", "instincts"}`, all as of `view`: a
    world character's heritage, with its own overrides, or an invented
    one's `world_heritage_id`, from the heritage alone (as
    `setup.start_scene` described it). A heritage that's gone from the
    world leaves its character out."""

    local = {
        thing["local_id"]: thing["data"]
        for thing in world.scenes().local_things(record.id)
        if thing["kind"] == LOCAL_CHARACTER_KIND and isinstance(thing["data"], dict)
    }

    cast: list[dict] = []
    for entry in _present(record):
        thing_id = entry.get("thing_id")
        if thing_id:
            state = view.thing(thing_id)
            heritage_id = state.fields.get("heritage") if state is not None else None
            name = view.name_of(thing_id) or ""
            source, character = thing_id, True
        else:
            data = local.get(entry.get("local_id") or "", {})
            heritage_id = data.get("world_heritage_id")
            name = str(data.get("name") or "")
            source, character = heritage_id, False
        if not isinstance(heritage_id, str) or view.thing(heritage_id) is None:
            continue
        body, instincts = _traits(view, source, character)
        if not body and not instincts:
            continue
        cast.append(
            {
                "name": name,
                "heritage": _heritage_name(view, heritage_id),
                "body": body,
                "instincts": instincts,
            }
        )
    return cast


def _facts(view: WorldView, state: ThingState, facts: list[FactState]) -> list[str]:
    """`facts` (of `state`) as a scene is told them: rendered, a held one
    as belief (`held_text`)."""

    return [held_text(view, fact, state) for fact in facts]


def _may_be_touched(state: ThingState) -> bool:
    """Whether the thing can be touched: anything but a being that isn't
    real (believed or undecided), which is only spoken of -- its facts
    reach the scene through whatever refers to it."""

    return state.kind != "being" or entries.acts_in_world(state)


def _role_words(role: str | None) -> str:
    return " ".join((role or "").split()).casefold()


def role_named(role: str | None, text: str) -> bool:
    """Whether `text` names the filing's `role` (ruling F4): the role's
    words, whole and in order, any case and spacing ("Chief Scribe" in
    "...to the chief scribe of..."; never "ward" in "toward", nor
    "scribe" in "scribes"). A generic role (`GENERIC_ROLES`), or none,
    is never named."""

    words = _role_words(role)
    if not words or words in GENERIC_ROLES:
        return False
    pattern = r"(?<!\w)" + r"\s+".join(map(re.escape, words.split())) + r"(?!\w)"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _named_in(view: WorldView, text: str) -> list[str]:
    """The live entries `text` names in full (`find_names`, never a mere
    suggestion), each once, in order."""

    found: list[str] = []
    for match in find_names(view, text):
        if match.suggested or not match.candidates:
            continue
        thing_id = match.candidates[0].id
        if thing_id not in found:
            found.append(thing_id)
    return found


def touched_entries(
    view: WorldView, record: SceneRecord, *, reach: int = 2
) -> list[str]:
    """The entries the scene touches (filing spec, "Scene context"), each
    once, in this order:

    - what the scene's place is filed in, followed upward `reach` steps
      (the world's `timeline_reach`; a place filed in several brings each
      in);
    - what each present character is filed in (and the part it's within);
    - what the setup names: the pulled-in entries (the prompt's picks),
      then any entry the goal or premise names in full;
    - (ruling F4) a character, or a real being, filed in one of those or
      in the place whose filing role the goal or premise names
      (`role_named`): the Chief Scribe the scene is about.

    Never the place itself, a present character (their sheet covers
    them), a being that isn't real (`_may_be_touched`), or one gone at the
    view."""

    place_id = record.state.get("place_thing_id")
    place_id = place_id if isinstance(place_id, str) else None
    present = [
        entry["thing_id"]
        for entry in _present(record)
        if isinstance(entry.get("thing_id"), str)
    ]
    skip = {*present, *([place_id] if place_id else [])}
    touched: list[str] = []

    def touch(thing_id: str | None) -> None:
        if thing_id is None or thing_id in skip or thing_id in touched:
            return
        state = view.thing(thing_id)
        if state is not None and _may_be_touched(state):
            touched.append(thing_id)

    if place_id and view.thing(place_id) is not None:
        frontier, seen = [place_id], {place_id}
        for _ in range(reach):
            above: list[str] = []
            for thing_id in frontier:
                for filing in filings_of(view, thing_id):
                    touch(filing.target)
                    if filing.target not in seen:
                        seen.add(filing.target)
                        above.append(filing.target)
            frontier = above
    for thing_id in present:
        for filing in filings_of(view, thing_id):
            touch(filing.target)
            touch(filing.within)
    for thing_id in record.state.get("pulled_in") or []:
        if isinstance(thing_id, str):
            touch(thing_id)
    setup = "\n".join(part for part in (record.goal, record.premise) if part)
    for thing_id in _named_in(view, setup) if setup.strip() else []:
        touch(thing_id)
    if setup.strip():
        index = filed_index(view)
        for target_id in [*([place_id] if place_id else []), *list(touched)]:
            for state, filing in index.get(target_id, []):
                if entries.acts_in_world(state) and role_named(filing.role, setup):
                    touch(state.id)
    return touched


def _summary_fact(state: ThingState) -> FactState | None:
    """The fact a touched entry leads with (as probe 5 read it): its
    summary (`entries.summary_fact`), else its first written `summary` or
    `description` fact, else its first undated fact."""

    fact = entries.summary_fact(state)
    if fact is not None:
        return fact
    for category in ("summary", "description"):
        found = [f for f in state.facts if f.category == category]
        if found:
            return min(found, key=lambda f: f.created)
    undated = [f for f in state.facts if f.valid_from is None]
    return min(undated, key=lambda f: f.created) if undated else None


def _same_event(a: str, b: str, threshold: float) -> bool:
    """Whether two timeline texts tell the same event: either holds at
    least `threshold` of the other's content words."""

    return max(overlap(a, b), overlap(b, a)) >= threshold


def _latest_lines(
    world: World,
    view: WorldView,
    thing_id: str,
    elsewhere: set[str],
    shown: set[str],
    settings: CurationSettings,
    things: list[ThingState],
) -> list[str]:
    """The entry's latest `TOUCHED_TIMELINE` timeline lines, oldest first,
    each "In <year>: <text>" or, once ended, "From <year> to <year>:
    <text>" (ruling C18), a held one as belief: its own dated facts and
    what it gathers (`timelines.entry_timeline`, out to the world's
    `timeline_reach`), less the lines of the things `elsewhere` (shown in
    the block another way) and of facts `shown` already. The same event
    told twice (from two entries: word overlap at the world's
    `date_threshold`) counts once, the entry's own telling kept, and
    neither is told again in the block."""

    lines = [
        line
        for line in entry_timeline(
            view,
            thing_id,
            reach=settings.timeline_reach,
            threshold=settings.date_threshold,
            things=things,
            disagreements=False,
        )
        if line.fact_id not in shown and (line.here or line.owner_id not in elsewhere)
    ]
    kept: list[TimelineLine] = []
    # the other tellings of a kept line's event: told, too
    told: list[str] = []
    for line in reversed(lines):
        twice = next(
            (
                i
                for i, other in enumerate(kept)
                if _same_event(line.text, other.text, settings.date_threshold)
            ),
            None,
        )
        if twice is not None:
            if line.here and not kept[twice].here:
                line, kept[twice] = kept[twice], line
            told.append(line.fact_id)
            continue
        if len(kept) == TOUCHED_TIMELINE:
            break
        kept.append(line)
    kept.sort(
        key=lambda line: (line.date.instant, line.fact.created if line.fact else 0)
    )
    shown.update(told)
    for line in kept:
        shown.add(line.fact_id)
    return [
        dated_line(world.calendar, line.date, timeline_text(view, line), line.until)
        for line in kept
    ]


def _touched_entry(
    world: World,
    view: WorldView,
    thing_id: str,
    elsewhere: set[str],
    shown: set[str],
    settings: CurationSettings,
    things: list[ThingState],
) -> dict[str, Any] | None:
    """One touched entry of the block, `{"name", "kind", "tag", "everyday",
    "lines"}` (probe 5's shape): its summary (`_summary_fact`), a person's
    filing lines as its sheet has them (`filing_lines`: "Chief Scribe of
    the Order, but: ..."), up to `TOUCHED_FACTS` of its own undated
    facts, the most-linked first, then its latest timeline lines
    (`_latest_lines`), at most `TOUCHED_LINES` in all (the own facts give
    way to the timeline), each held fact worded as held; a fact `shown`
    already in the block isn't told again. A person's exceptions to its
    filings (`ties` facts) are told only in its filing lines, never as
    facts with their "Departs from <link>" sentence (Filing Task 11).
    `None` for an entry with nothing to say."""

    state = view.thing(thing_id)
    if state is None:
        return None
    person = entries.acts_in_world(state)
    filed = filing_lines(view, world.calendar, thing_id) if person else []
    head = _summary_fact(state)
    if head is not None and (
        head.fact_id in shown or (person and head.category == "ties")
    ):
        head = None
    own = sorted(
        (
            fact
            for fact in state.facts
            if fact.valid_from is None
            and fact.fact_id not in shown
            and (head is None or fact.fact_id != head.fact_id)
            and not entries.is_summary_fact(fact)
            and not (person and fact.category == "ties")
        ),
        key=lambda fact: (-len(set(fact.refs)), fact.created),
    )[:TOUCHED_FACTS]
    for fact in [*([head] if head else []), *own]:
        shown.add(fact.fact_id)
    timeline = _latest_lines(world, view, thing_id, elsewhere, shown, settings, things)
    room = TOUCHED_LINES - len(timeline) - (1 if head else 0) - len(filed)
    lines = [
        *_facts(view, state, [head] if head else []),
        *filed,
        *_facts(view, state, own[: max(room, 0)]),
        *timeline,
    ][:TOUCHED_LINES]
    if not lines:
        return None
    return {
        "name": view.name_of(thing_id) or "",
        "kind": state.kind,
        "tag": tag_of(state),
        "everyday": everyday_name(state),
        "lines": lines,
    }


def world_context_block(world: World, record: SceneRecord, at: WorldDate) -> str:
    """The "World" instruction's content (probe 5's v2 block): the scene's
    goal, its current place, what the scene touches (`touched_entries`,
    each `_touched_entry`) and who is here by heritage (`_cast`), all as
    of `at`. The place is the world thing `record.state["place_thing_id"]`
    (its facts, a held one as belief) or, when the scene invented its
    place, the scene-local place thing `record.state["place_local_id"]`
    (its name and facts). The agent flag no longer changes it.

    A touched entry's timeline leaves out the lines of the place, of who
    is here and of the other touched entries (each told where it is
    shown), and no fact is told twice in the block.

    A place or touched entry with an everyday name is shown with
    "usually called <everyday>", and the block then opens with a line
    asking for everyday names in narration and dialogue: the connections
    probe (docs/superpowers/probes/2026-10-21-connections.md, probe 4)
    found the plain heading kept the full name every time."""

    view = world.view(at)
    things = view.things()
    settings = world.curation()

    place_thing_id = record.state.get("place_thing_id")
    place_local_id = record.state.get("place_local_id")
    place_state = view.thing(place_thing_id) if place_thing_id else None

    touched = touched_entries(view, record, reach=settings.timeline_reach)

    present = {
        entry["thing_id"]
        for entry in _present(record)
        if isinstance(entry.get("thing_id"), str)
    }
    shown: set[str] = set()
    place = None
    if place_state is not None and place_thing_id:
        shown |= {fact.fact_id for fact in place_state.facts}
        place = {
            "name": view.name_of(place_thing_id) or "",
            "everyday": everyday_name(place_state),
            "facts": _facts(
                view,
                place_state,
                sorted(place_state.facts, key=lambda fact: fact.created),
            ),
        }
    elif place_local_id:
        local = next(
            (
                thing
                for thing in world.scenes().local_things(record.id)
                if thing["local_id"] == place_local_id
                and thing["kind"] == LOCAL_PLACE_KIND
            ),
            None,
        )
        if local is not None:
            data = local["data"]
            place = {
                "name": str(data.get("name") or ""),
                "everyday": None,
                "facts": [str(fact) for fact in data.get("facts") or []],
            }

    touched_block: list[dict[str, Any]] = []
    for thing_id in touched:
        elsewhere = {
            *present,
            *([place_thing_id] if isinstance(place_thing_id, str) else []),
            *(other for other in touched if other != thing_id),
        }
        entry = _touched_entry(
            world, view, thing_id, elsewhere, shown, settings, things
        )
        if entry is not None:
            touched_block.append(entry)

    return str(
        Prompt.get(
            "world.scene-context",
            vars={
                "goal": record.goal,
                "place": place,
                "touched": touched_block,
                "everyday": any(
                    entry["everyday"]
                    for entry in [*([place] if place else []), *touched_block]
                ),
                "cast": _cast(world, record, view),
            },
        )
    )


@dataclass
class WorldSceneContext:
    """Attached as `scene.world_context` for a scene played against a
    shared world. `connect` reads it to build the "World" instruction and
    to refresh characters after time passage."""

    world: World
    record: SceneRecord

    async def refresh_characters(self, scene) -> None:
        """Rebuild every active character from the world at the scene's
        current date (`scene_date(self.record, scene.ts)`), replacing it on
        the scene but keeping the actor binding. Never calls the model --
        characters whose prose has gone stale stay stale until something
        else (not this) regenerates it.

        A character whose world thing has since been deleted is left as
        it is, with a warning logged -- the same thing
        `persistence._character_data` does on load -- rather than failing
        every time-passage signal from here on.

        Only the world-derived fields (name, description, base attributes,
        dialogue instructions, example dialogue) are replaced --
        `character.model_copy(update=...)` keeps everything per-scene
        (color, avatar, voice, details, greeting text, ...) exactly as it
        was."""

        at = scene_date(self.record, scene.ts)
        for actor in scene.actors:
            character = actor.character
            thing_id = getattr(character, "world_thing_id", None)
            if thing_id is None:
                continue

            try:
                rebuilt = character_from_world(
                    self.world, thing_id, at, is_player=character.is_player
                )
            except KeyError:
                log.warning("world scene character not in the world", thing_id=thing_id)
                continue
            updated = character.model_copy(
                update={
                    field: getattr(rebuilt, field) for field in WORLD_DERIVED_FIELDS
                }
            )

            actor.character = updated
            if actor.agent is not None:
                actor.agent.character = updated

            if character.name in scene.active_characters:
                index = scene.active_characters.index(character.name)
                scene.active_characters[index] = updated.name

            if character.name in scene.character_data:
                del scene.character_data[character.name]
            scene.character_data[updated.name] = updated


async def _on_inject_instructions(emission) -> None:
    scene = emission.agent.scene
    context: WorldSceneContext | None = getattr(scene, "world_context", None)
    if context is None:
        return

    at = scene_date(context.record, scene.ts)
    content = world_context_block(context.world, context.record, at)
    if not content.strip():
        return

    emission.dynamic_instructions.append(
        DynamicInstruction(title=SECTION_TITLE, content=content)
    )


async def _on_time_passage(emission) -> None:
    scene = emission.agent.scene
    context: WorldSceneContext | None = getattr(scene, "world_context", None)
    if context is None:
        return
    await context.refresh_characters(scene)


def connect(scene) -> None:
    """Wire the "World" instruction into the narrator and conversation
    agents' prompts, and keep a scene's characters fresh across time
    passage.

    The handlers are module-level, not closures over `scene`: each one
    resolves *its own* scene from `emission.agent.scene` at call time --
    the same pattern `CultureAgent` uses
    (`agents/culture/__init__.py:246-252`) -- rather than from this call's
    `scene` argument. A closure bound to one scene would leak: nothing
    ever disconnects it, so a scene loaded after this one would keep
    getting *this* scene's "World" block and time-passage refresh instead
    of its own. `scene` is accepted (and otherwise unused) only so this
    has the same `connect(scene)` shape every other agent's scene-load
    hook does.

    `AsyncSignal.connect` already dedupes a repeat of the exact same
    function object, so calling this once per scene load -- the normal
    thing to do -- never double-connects. Acting only on a scene that has
    `scene.world_context` set means a non-world scene, or one whose world
    context hasn't loaded yet, is left exactly as before."""

    async_signals.get("agent.conversation.inject_instructions").connect(
        _on_inject_instructions
    )
    async_signals.get("agent.narrator.inject_instructions").connect(
        _on_inject_instructions
    )
    async_signals.get("agent.world_state.time").connect(_on_time_passage)
