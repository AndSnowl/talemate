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

from dataclasses import dataclass
from typing import Any

import structlog

import talemate.emit.async_signals as async_signals
from talemate.agents.base import DynamicInstruction
from talemate.prompts import Prompt
from talemate.world import entries, heritage, spheres, timelines
from talemate.world.curation import CurationSettings
from talemate.world.dates import WorldDate
from talemate.world.kinds import HERITAGE_KINDS, SPHERE_CATEGORIES
from talemate.world.names import everyday_name
from talemate.world.nearness import near
from talemate.world.spheres import KEY_TIMELINE as _KEY_TIMELINE
from talemate.world.scenes import SceneRecord
from talemate.world.store import World
from talemate.world.view import FactState, ThingState, WorldView

from .characters import (
    WORLD_DERIVED_FIELDS,
    _cached_section,
    character_from_world,
    held_text,
    mid_sentence_name,
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


def _touched_spheres(
    view: WorldView,
    record: SceneRecord,
    place_thing_id: str | None,
    things: list[ThingState],
) -> list[str]:
    """The spheres the scene touches, each once: those whose territory
    holds the scene's place (`spheres.holders`, in the order they were
    made), those the prompt or setup named (pulled in), then those a
    character here has a live tie to (Global Constraints, "Context").
    `things` is one snapshot of the view's things."""

    sphere_ids = {state.id for state in things if spheres.is_sphere(state)}
    touched: list[str] = []

    def touch(sphere_id: str) -> None:
        if sphere_id in sphere_ids and sphere_id not in touched:
            touched.append(sphere_id)

    if place_thing_id:
        for sphere_id in spheres.holders(view, place_thing_id, things):
            touch(sphere_id)
    for thing_id in record.state.get("pulled_in") or []:
        touch(thing_id)
    for entry in _present(record):
        thing_id = entry.get("thing_id")
        if isinstance(thing_id, str):
            for tie in spheres.ties_of(view, thing_id, live=True):
                touch(tie.sphere_id)
    return touched


def _sphere_summary(world: World, view: WorldView, sphere_id: str) -> str:
    """The sphere's summary (`entries.summary`, rulings P1, P21): its
    cached description prose as of the view's date, else its summary
    fact, rendered."""

    cached = _cached_section(world, sphere_id, "description", view.at)
    return entries.summary(view, sphere_id, cached.text if cached else None)


def _sphere_parent(view: WorldView, state: ThingState) -> str | None:
    """The sphere a sphere sits in: a branch's `parent`, else the sphere
    it's part of (the Council of Elders in the White Dawn's Hierarchy);
    `None` when neither is a live sphere."""

    candidates: list[object] = []
    if state.kind == "sphere":
        candidates.append(state.fields.get("parent"))
    part_of = state.fields.get("part_of")
    if isinstance(part_of, dict):
        candidates.append(part_of.get("sphere"))
    for candidate in candidates:
        if not isinstance(candidate, str) or candidate == state.id:
            continue
        parent = view.thing(candidate)
        if parent is not None and spheres.is_sphere(parent):
            return candidate
    return None


def _held_line(view: WorldView) -> spheres.FactLine:
    """Key facts' wording of an item's fact: as belief when it's held
    (`held_text`)."""

    def line(fact: FactState, owner: ThingState, text: str) -> str:
        return held_text(view, fact, owner, text)

    return line


def _facts(view: WorldView, state: ThingState, facts: list[FactState]) -> list[str]:
    """`facts` (of `state`) as a scene is told them: rendered, a held one
    as belief (`held_text`)."""

    return [held_text(view, fact, state) for fact in facts]


def _latest(
    world: World,
    view: WorldView,
    sphere_id: str,
    things: list[ThingState],
    shown: set[str],
    skip: set[str],
    summary: str | None,
    settings: CurationSettings,
) -> list[tuple[str, str]]:
    """The sphere's timeline lines for its key facts, as `(owner id,
    text)`: its gathered timeline (`timelines.prompt_timeline`, as far out
    as `timeline_reach`) less the lines of the things `shown` in the block
    and of the items its key facts print (`spheres.key_items`, `skip` left
    out of them, after the summary: `summary`, else its summary fact), the
    last `_KEY_TIMELINE` of the rest, each "In <year>: <text>" (the
    spheres probe's (d) wording) or "From <year> to <year>: <text>" when
    it has ended (ruling C18), a held one as belief. Only those are worded:
    wording a held line looks names up."""

    lines = timelines.prompt_timeline(
        view,
        sphere_id,
        shown,
        reach=settings.timeline_reach,
        threshold=settings.date_threshold,
        things=things,
    )
    head = 1 if (summary or entries.summary(view, sphere_id)) else 0
    printed = {
        item.thing_id
        for item in spheres.key_items(
            view, sphere_id, head + min(len(lines), _KEY_TIMELINE), things, skip
        )
        if item.thing_id
    }
    kept = [line for line in lines if line.owner_id not in printed][-_KEY_TIMELINE:]
    return [
        (
            line.owner_id,
            spheres.dated_line(
                world.calendar, line.date, timeline_text(view, line), line.until
            ),
        )
        for line in kept
    ]


def _sphere_entries(
    world: World,
    view: WorldView,
    sphere_ids: list[str],
    shown: set[str],
    things: list[ThingState],
    shown_elsewhere: set[str],
    settings: CurationSettings,
    place_thing_id: str | None = None,
) -> list[dict[str, Any]]:
    """The spheres block, one entry per sphere in `sphere_ids`: its key
    facts (`spheres.key_facts`, with its summary, less the items
    `shown_elsewhere` in the block: as lore, or a nested sphere's own
    block, and ending with its gathered timeline less the lines of those
    and of the scene's place: `_latest`) and, for a nested sphere whose
    parent isn't `shown` in the block already, the parent's summary
    alone."""

    entries: list[dict[str, Any]] = []
    for sphere_id in sphere_ids:
        state = view.thing(sphere_id)
        if state is None:
            continue
        template = state.fields.get("template")
        summary = _sphere_summary(world, view, sphere_id) or None
        entry: dict[str, Any] = {
            "name": view.name_of(sphere_id) or "",
            "template": template if isinstance(template, str) else "sphere",
            "everyday": everyday_name(state),
            "parent_name": "",
            "parent_summary": "",
            "key_facts": spheres.key_facts(
                view,
                sphere_id,
                summary,
                world.calendar,
                things,
                shown_elsewhere,
                _held_line(view),
                _latest(
                    world,
                    view,
                    sphere_id,
                    things,
                    shown_elsewhere | ({place_thing_id} if place_thing_id else set()),
                    shown_elsewhere,
                    summary,
                    settings,
                ),
            ),
        }
        parent_id = _sphere_parent(view, state)
        if parent_id is not None and parent_id not in shown:
            entry["parent_name"] = mid_sentence_name(view.name_of(parent_id) or "")
            entry["parent_summary"] = _sphere_summary(world, view, parent_id)
        entries.append(entry)
    return entries


def _may_be_lore(state: ThingState) -> bool:
    """Whether the thing can be shown as lore: anything but a being that
    isn't real (believed or undecided), which is only spoken of -- its
    facts reach the scene through whatever refers to it."""

    return state.kind != "being" or entries.acts_in_world(state)


def _lore_entry(
    view: WorldView, state: ThingState, facts: list[FactState]
) -> dict[str, Any]:
    """A lore entry of the block: the thing's name, its everyday name and
    `facts` as a scene is told them (`_facts`)."""

    return {
        "name": view.name_of(state.id) or "",
        "everyday": everyday_name(state),
        "facts": _facts(view, state, facts),
    }


def _filed_in(state: ThingState) -> str | None:
    """The sphere the thing is filed in (its `part_of`), or `None`."""

    part_of = state.fields.get("part_of")
    sphere = part_of.get("sphere") if isinstance(part_of, dict) else None
    return sphere if isinstance(sphere, str) else None


def _near_lore(
    view: WorldView,
    seeds: list[str],
    shown: set[str],
    touched: list[str],
    room: int,
    settings: CurationSettings,
) -> list[ThingState]:
    """At most `room` things near the scene's place and cast (`seeds`), as
    lore: from each seed's `near` list, at the world's `reach`, the best
    first (score, then fewer steps, then the seeds' order and each list's
    own). Never one `shown` already, a sphere (a sphere the scene touches
    has its own block; one it doesn't isn't the scene's), a thing filed in
    a sphere of `touched` (its block's key facts give it, as the spheres
    probe's (d) block has them), a heritage (the cast lines carry it), a
    being that isn't real (`_may_be_lore`), or a thing with no facts to
    show."""

    if room <= 0 or settings.facts_per_entry <= 0 or not seeds:
        return []
    best: dict[str, tuple[float, int, int]] = {}
    order = 0
    for seed in seeds:
        # each list is cut before the filter below, which skips what's
        # shown and what can't be lore: the limit leaves room for those,
        # so a seed's list can still come up short of `room` when most of
        # its nearest are skipped (the next seed's then fill in)
        for found in near(
            view, seed, reach=settings.reach, limit=room + len(shown) + settings.entries
        ):
            order += 1
            key = (-round(found.score, 9), found.steps, order)
            if found.thing_id not in best or key < best[found.thing_id]:
                best[found.thing_id] = key

    kept: list[ThingState] = []
    for thing_id in sorted(best, key=lambda thing_id: best[thing_id]):
        if thing_id in shown:
            continue
        state = view.thing(thing_id)
        if (
            state is None
            or spheres.is_sphere(state)
            or _filed_in(state) in touched
            or state.kind in HERITAGE_KINDS
            or not _may_be_lore(state)
            or not state.facts
        ):
            continue
        kept.append(state)
        if len(kept) == room:
            break
    return kept


def world_context_block(world: World, record: SceneRecord, at: WorldDate) -> str:
    """The "World" instruction's content: the scene's goal, its current
    place, whatever lore has been pulled into it, and who is here by
    heritage (`_cast`), all as of `at`. The
    place is the world thing `record.state["place_thing_id"]` or, when the
    scene invented its place, the scene-local place thing
    `record.state["place_local_id"]` (its name and facts); the lore entries
    are `record.state["pulled_in"]`, then (curation spec, goal 10) the
    things nearest the scene's place and the characters here
    (`_near_lore`), each with at most the world's `facts_per_entry` facts,
    while the place, lore and sphere blocks number fewer than its
    `entries`. Today's rules come first: what's near only fills the room
    left, and never shows a thing a second time.

    The spheres the scene touches (`_touched_spheres`) follow the lore,
    one block each under one lead line (the spheres probe's (d)), with
    their key facts, which end with the latest lines of each one's gathered
    timeline (`_latest`); a pulled-in sphere shows there, not as lore, and
    a pulled-in or near item of a sphere shows as lore, and a nested sphere
    in its own block, not again in its parent's key facts.
    When the
    scene's place is itself a sphere, it shows once, as the place: its own
    place facts, then its key facts (summary from its `about` fact, since
    its description prose retells those place facts), never again as a
    sphere block.

    A place or lore entry with an everyday name is shown "<main> (usually
    called <everyday>)", and the block then opens with a line asking for
    everyday names in narration and dialogue: the connections probe
    (docs/superpowers/probes/2026-10-21-connections.md, probe 4) found the
    plain heading kept the full name every time."""

    view = world.view(at)
    # one snapshot of the world's things for every sphere lookup below
    things = view.things()
    settings = world.curation()

    lore = []
    # a sphere's item pulled in as lore shows once, there, in full: the
    # sphere's key facts leave it out
    as_lore: set[str] = set()
    for lore_thing_id in record.state.get("pulled_in") or []:
        lore_state = view.thing(lore_thing_id)
        if lore_state is None or spheres.is_sphere(lore_state):
            continue
        # a being that isn't real is only spoken of: its facts reach the
        # scene through whatever refers to it, never as lore of its own
        if not _may_be_lore(lore_state):
            continue
        as_lore.add(lore_thing_id)
        lore.append(_lore_entry(view, lore_state, lore_state.facts))

    place_thing_id = record.state.get("place_thing_id")
    place_local_id = record.state.get("place_local_id")
    place_state = view.thing(place_thing_id) if place_thing_id else None

    touched = _touched_spheres(view, record, place_thing_id, things)
    in_block = [sphere_id for sphere_id in touched if sphere_id != place_thing_id]

    # then what's near the place and the cast, as lore, within the knobs
    present = [
        entry["thing_id"]
        for entry in _present(record)
        if isinstance(entry.get("thing_id"), str)
    ]
    seeds = ([place_thing_id] if place_state is not None else []) + present
    shown = {*seeds, *as_lore, *touched}
    room = settings.entries - len(lore) - len(in_block) - (1 if place_state else 0)
    for near_state in _near_lore(view, seeds, shown, touched, room, settings):
        as_lore.add(near_state.id)
        lore.append(
            _lore_entry(
                view,
                near_state,
                sorted(near_state.facts, key=lambda fact: fact.created)[
                    : settings.facts_per_entry
                ],
            )
        )

    place = None
    if place_state is not None and place_thing_id:
        facts = _facts(view, place_state, place_state.facts)
        if spheres.is_sphere(place_state):
            facts = _facts(
                view,
                place_state,
                [
                    fact
                    for fact in place_state.facts
                    if fact.category not in SPHERE_CATEGORIES
                ],
            ) + spheres.key_facts(
                view,
                place_thing_id,
                None,
                world.calendar,
                things,
                as_lore,
                _held_line(view),
                _latest(
                    world,
                    view,
                    place_thing_id,
                    things,
                    as_lore,
                    as_lore,
                    None,
                    settings,
                ),
            )
        place = {
            "name": view.name_of(place_thing_id) or "",
            "everyday": everyday_name(place_state),
            "facts": facts,
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

    # a nested sphere with a block of its own is left out of its parent's
    # key facts too (ruling P20)
    sphere_entries = _sphere_entries(
        world,
        view,
        in_block,
        set(touched),
        things,
        as_lore | set(in_block),
        settings,
        place_thing_id,
    )

    return str(
        Prompt.get(
            "world.scene-context",
            vars={
                "goal": record.goal,
                "place": place,
                "lore": lore,
                "spheres": sphere_entries,
                "everyday": any(
                    entry["everyday"]
                    for entry in [*([place] if place else []), *lore, *sphere_entries]
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
