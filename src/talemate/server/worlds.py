"""Websocket plugin for the fantasymate world screens (`talemate.world`).

Reply contract: a request `{"type": "worlds", "action": <a>, ...}` is
answered with `{"type": "worlds", "action": <a>, "data": {...}}`. Errors go
through `signal_operation_failed` (an `operation_done` envelope with
`error.message`), writing nothing.

- Worlds: `list_worlds`, `create_world {name, present_year}`,
  `open_world {path}`, `get_present`, `set_present {year}`. A world's
  present (default year 1000) is the date things are created at before
  any scene has moved past it. The
  open world is held on the websocket handler (`handler.world`), one per
  connection, and closed when the connection goes.
- Things: `list_things {kind}` (stubs included, each with its `stub`
  marker; ignored stubs left out), `get_thing {id, at}`. A thing's payload
  holds its fields, the facts visible at `at` (each with the inherited
  facts it `overrides`), its cached prose per section (with whether it's
  stale, following its lineage), its whole timeline and the scenes it
  appears in. From `talemate.world.heritage` it adds what it inherits
  (`inherited`, each with what overrides it), its resolved `numbers`, a
  character's `life_stage` (from `born`, at `at` or else the world's
  "now"), and, on a species page, its `races` and `mixes`.
  `referenced_in` is what `thing_references` reports, plus
  `member_scenes`: the scenes with a member character (one whose lineage
  includes the thing) in them.
- Links: each own and inherited fact carries `segments`, its rendered
  text as `{text, ref, stub}` runs (`ref` the thing a run links to, `stub`
  whether that's a stub; a link to an ignored stub is plain text), and
  `prose_segments` holds each section's cached prose the same way, its
  names found by `world.names.find_names` (never the thing's own, and
  never making anything). The payload also has the thing's other names
  (`aka`), its `stub` marker (`null` or `{ignored}`; `fields` holds
  neither), its `mentions` (every other entry's fact that references it)
  and `named_stubs` (`{id, name, kind}` of the stubs its facts link to).
- Stubs: `make_stub {thing_id, fact_id, text, kind}` makes a stub named
  `text` (or reuses the thing that already has that name, reviving an
  ignored stub) and links that phrase in the fact (its first plain
  occurrence, nothing else), answering like `correct_fact`. `list_stubs {include_ignored}` answers `{stubs: [{id, name, kind, first_mentioned:
  {thing_id, name}, mentions, ignored}]}`. `ignore_stub {id, ignored}` and
  `change_stub_kind {id, kind}` answer with the stub's payload.
  `stub_suggestion {id}` answers `{id, prompt, context}`: the create box's
  starting prompt for the stub and the mention context its expansion gets.
- Heritage: `override_fact {thing_id, overridden_fact_id, text, category,
  at}` adds an own fact that overrides an inherited one and answers like
  `add_fact`. `list_heritage` answers `{things: [{id, kind, name,
  species_ids}]}`, every species, race and mix, for the heritage picker.
  `find_mix {parents: [a, b]}` answers `{parents, mix_id}`, the mix of
  those two parents in either order (`null` if there's none yet).
- Create: `preview_thing {kind, prompt, fields, stub_id, picks,
  new_names}` runs in the background and answers `preview_thing {preview}`
  or `preview_failed {message}`; it writes nothing. `stub_id` expands that
  stub, `picks` maps a name written in the prompt to the thing the owner
  matched it to, and `new_names` are written names the owner treats as new.
  `accept_preview {preview, into_stub}` writes it (into the stub
  `into_stub`, if given) and answers with the thing. For the browser
  tests only, `TALEMATE_TEST_FIXED_PREVIEW` names a JSON file (`{name,
  facts, prose, fields?}`) that previews are answered from instead of the
  model (listing what the request's fields inherit, and for a `stub_id`
  its kind, name and mention context, as a real preview does).
- Edits: `add_fact`, `correct_fact`, `end_fact`, `remove_fact` and
  `set_field` each write one revision, answer with the thing, then start a
  background `ensure_prose` that answers `prose_updated {id}` (or
  `prose_failed`); with no AI client the edit stands and the prose is left
  stale. `regenerate_prose {id, at, section?}` regenerates that one
  section (answering `prose_updated {id, section}`), or every section.
  Prose tasks for one thing run one at a time, in order, so a later edit's
  check always sees what the earlier task cached.
- Delete: `thing_references {id}` answers `{id, kind, name, references}`
  (the facts, fields and scenes that use it, from
  `talemate.worldplay.references`), writing nothing. `delete_thing {id}`
  removes it in one manual revision noted "deleted <name>", so undoing
  that revision restores it, and answers `thing_deleted {id, kind}` and
  that kind's `list_things`. A loaded scene keeps playing with it until
  it's reloaded.
- Fact text written by hand (`add_fact`, `correct_fact`, `override_fact`,
  each taking `picks`, `new_names` and `spans`) is linked before it's
  written: first the `spans` (`[{start, end, ref}]`, code points: a fact
  form's existing links, by position, so two links of the same words keep
  their own targets; a span with a null `ref` keeps its words plain), then (`worldplay.links.link_text`) the names of
  entries and stubs, and the picks, in the rest, keeping the words
  written; the thing's own names, and names the owner treats as new, stay
  plain, and unknown phrases are never made stubs.
  `repoint_ref {thing_id, fact_id, occurrence, to_id, at}` points one
  reference of a fact (the `occurrence`-th in its text) at another thing,
  keeping its words and changing nothing else; it answers like
  `correct_fact`.
- Scenes: `match_names {text, at}` finds world thing names in a storyline
  prompt (the reply echoes `text` and `at`), each candidate marked `stub`
  and `via`, plus the `unknown` capitalised phrases no name covers.
  `plan_scene {prompt, picks, new_names, player, start}` (picks and names
  treated as new always win over automatic matching) and
  `continue_scene {scene_id, goal_prompt}` (saving that scene first if
  it's the one loaded) run in the background and answer
  with `{setup, names}` (the world things' names, for display), or
  `plan_failed`/`continue_failed`; they write nothing. The setup's
  `stub_previews` (`CreatePreview` dumps) fill out the stubs it uses.
  `start_scene {setup}` (background too: it brings the characters' prose
  up to date) writes the stub previews into their stubs, then the scene, and
  answers `{scene_id, target, scene}` (or `start_failed`), where
  `target` is the `world://` path the frontend then sends to `load_scene`.
  `list_scenes` lists the world's scenes, newest first.
  `reposition_scene {scene_id, start}` moves a scene's start date; if that
  scene is the one loaded, its characters are rebuilt for the new date and
  its status sent. The scene's world characters' prose is then brought up
  to date at the new start in the background, as after an edit.
  For the browser tests only, `TALEMATE_TEST_FIXED_SETUP` names a JSON
  file holding a scene-setup model reply (`{player, characters, place,
  goal, intro, extras?}`) that `plan_scene` and `continue_scene` use
  instead of asking any model; `start_scene` then leaves the prose as it
  is. With `TALEMATE_TEST_FIXED_PREVIEW` set as well, each stub the setup
  uses gets the fixed preview; without it, stubs stay stubs.

Dates go over the wire as `{"instant", "precision", "label"}`, the label
formatted with the world's calendar; `label` is ignored on the way in.
"""

import asyncio
import json
import os
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import pydantic
import structlog

import talemate.instance as instance
from talemate.path import WORLDS_DIR
from talemate.server.websocket_plugin import Plugin
from talemate.world import heritage
from talemate.world.calendar import Calendar
from talemate.world.dates import WorldDate
from talemate.world.kinds import HERITAGE_KINDS, KINDS
from talemate.world.names import find_names, unknown_proper_phrases
from talemate.world.refs import REF_PATTERN
from talemate.world.scenes import SceneRecord, scene_end
from talemate.world.store import Source, World
from talemate.world.timeline import TimelineEntry
from talemate.world.view import Segment, ThingState, WorldView
from talemate.worldplay import prose_gen
from talemate.worldplay.characters import age_in_years
from talemate.worldplay.create import (
    CreatePreview,
    accept_preview,
    current_date,
    matching_stub,
    preview_inherited,
    preview_thing,
)
from talemate.worldplay.links import (
    LinkSpan,
    NewName,
    link_phrase,
    link_text,
    make_stubs,
    repoint_ref,
)
from talemate.worldplay.mentions import mention_context, mentions, suggested_prompt
from talemate.worldplay.persistence import save_world_scene, world_target
from talemate.worldplay.references import thing_references
from talemate.worldplay.setup import (
    SceneSetup,
    continue_setup,
    match_names,
    plan_scene,
    start_scene,
    stubs_to_fill,
)

__all__ = ["WorldsPlugin"]

log = structlog.get_logger("talemate.server.worlds")


def _date_in(value: Any) -> WorldDate | None:
    if value is None:
        return None
    if isinstance(value, WorldDate):
        return value
    return WorldDate.model_validate(value)


def _date_out(calendar: Calendar, date: WorldDate | None) -> dict | None:
    if date is None:
        return None
    return {
        "instant": date.instant,
        "precision": date.precision.value,
        "label": calendar.format(date),
    }


def _value_out(calendar: Calendar, value: object) -> object:
    if isinstance(value, WorldDate):
        return _date_out(calendar, value)
    return value


# --- payloads -----------------------------------------------------------------


# the present a new world starts at, unless the owner picks another year
DEFAULT_PRESENT_YEAR = 1000

# browser tests only: a JSON file `preview_thing` answers from (see the
# module docstring)
FIXED_PREVIEW_ENV = "TALEMATE_TEST_FIXED_PREVIEW"

# browser tests only: a JSON file holding the scene-setup model reply
# `plan_scene` and `continue_scene` use (see the module docstring)
FIXED_SETUP_ENV = "TALEMATE_TEST_FIXED_SETUP"


class CreateWorldPayload(pydantic.BaseModel):
    name: str
    present_year: int = DEFAULT_PRESENT_YEAR

    @pydantic.field_validator("name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a world needs a name")
        return value.strip()


class OpenWorldPayload(pydantic.BaseModel):
    path: str


class SetPresentPayload(pydantic.BaseModel):
    year: int


class ListThingsPayload(pydantic.BaseModel):
    kind: str


class GetThingPayload(pydantic.BaseModel):
    id: str
    at: dict | None = None


class ThingIdPayload(pydantic.BaseModel):
    id: str


class PreviewPayload(pydantic.BaseModel):
    kind: str
    prompt: str
    fields: dict = pydantic.Field(default_factory=dict)
    # the stub this preview expands
    stub_id: str | None = None
    # a name written in the prompt -> the thing the owner matched it to
    picks: dict[str, str] = pydantic.Field(default_factory=dict)
    # names written in the prompt the owner treats as new
    new_names: list[str] = pydantic.Field(default_factory=list)


class AcceptPreviewPayload(pydantic.BaseModel):
    preview: CreatePreview
    # "fill the stub instead": the stub a preview made without one fills
    into_stub: str | None = None


class _ThingEdit(pydantic.BaseModel):
    thing_id: str
    # the date the thing page is viewing as of: the reply and the prose
    # regenerated afterwards are for this date
    at: dict | None = None


class AddFactPayload(_ThingEdit):
    category: str
    text: str
    valid_from: dict | None = None
    valid_until: dict | None = None
    # a name written in the text -> the thing the owner picked for it
    picks: dict[str, str] = pydantic.Field(default_factory=dict)
    # names written in the text the owner treats as new: left plain
    new_names: list[str] = pydantic.Field(default_factory=list)
    # spans of the text linked by position (code points), before the rest
    spans: list[LinkSpan] = pydantic.Field(default_factory=list)


class CorrectFactPayload(_ThingEdit):
    fact_id: str
    text: str | None = None
    category: str | None = None
    # unset means "keep"; an explicit null means "make it open"
    valid_from: dict | None = None
    valid_until: dict | None = None
    picks: dict[str, str] = pydantic.Field(default_factory=dict)
    new_names: list[str] = pydantic.Field(default_factory=list)
    spans: list[LinkSpan] = pydantic.Field(default_factory=list)


class RepointRefPayload(_ThingEdit):
    fact_id: str
    # which reference of the fact's text, 0-based, in order
    occurrence: int
    to_id: str


class MakeStubPayload(_ThingEdit):
    fact_id: str
    # the phrase in the fact the stub is named after
    text: str
    kind: str


class ListStubsPayload(pydantic.BaseModel):
    include_ignored: bool = False


class IgnoreStubPayload(pydantic.BaseModel):
    id: str
    ignored: bool


class ChangeStubKindPayload(pydantic.BaseModel):
    id: str
    kind: str


class EndFactPayload(_ThingEdit):
    fact_id: str
    until: dict


class RemoveFactPayload(_ThingEdit):
    fact_id: str


class OverrideFactPayload(_ThingEdit):
    overridden_fact_id: str
    text: str
    category: str
    picks: dict[str, str] = pydantic.Field(default_factory=dict)
    new_names: list[str] = pydantic.Field(default_factory=list)
    spans: list[LinkSpan] = pydantic.Field(default_factory=list)


class FindMixPayload(pydantic.BaseModel):
    parents: list[str]

    @pydantic.field_validator("parents")
    @classmethod
    def _two(cls, value: list[str]) -> list[str]:
        if len(value) != 2:
            raise ValueError("a mix has two parents")
        return value


class SetFieldPayload(_ThingEdit):
    field: str
    value: Any
    valid_from: dict | None = None


class RegenerateProsePayload(pydantic.BaseModel):
    id: str
    at: dict | None = None
    # one section to regenerate; every section when left out
    section: str | None = None


class MatchNamesPayload(pydantic.BaseModel):
    text: str
    at: dict | None = None


class PlanScenePayload(pydantic.BaseModel):
    prompt: str
    # a `NameMatch.text` -> the thing id the owner picked for it
    picks: dict[str, str] = pydantic.Field(default_factory=dict)
    # matched names the owner treats as new: always invented
    new_names: list[str] = pydantic.Field(default_factory=list)
    player: str | None = None
    start: dict | None = None


class StartScenePayload(pydantic.BaseModel):
    setup: SceneSetup


class ContinueScenePayload(pydantic.BaseModel):
    scene_id: str
    goal_prompt: str


class RepositionScenePayload(pydantic.BaseModel):
    scene_id: str
    start: dict


def _fixed_file(env: str) -> Path | None:
    """The browser tests' fixed-reply file named by `env`, if it's set and
    a test has written the file; `None` otherwise, so a request with no
    fixed reply goes to the model (or says there's no client) as usual."""

    name = os.environ.get(env)
    if not name:
        return None
    path = Path(name)
    return path if path.exists() else None


async def _fixed_preview(
    path: Path, payload: PreviewPayload, view: WorldView
) -> CreatePreview:
    """The browser tests' stand-in for `preview_thing`: the preview in
    `path`, for the request's kind, prompt, fields and picks, listing what
    they inherit in `view` as the real one does. With a `stub_id` it takes
    the stub's kind and name and carries its mention context; without one,
    a live stub of the same kind and name is offered as `matching_stub_id`.
    Async so it runs through the same background task and reply path as
    the real one."""

    fixed = json.loads(path.read_text(encoding="utf-8"))
    fields = {**payload.fields, **fixed.get("fields", {})}
    kind, name = payload.kind, fixed["name"]
    context: list[tuple[str, list[str]]] = []
    stub = view.thing(payload.stub_id) if payload.stub_id is not None else None
    if payload.stub_id is not None:
        if stub is None or not stub.is_stub:
            raise ValueError(f"not a stub: {payload.stub_id}")
        kind = stub.kind
        name = view.name_of(stub.id) or name
        context = mention_context(view, stub.id)
    return CreatePreview(
        kind=kind,
        prompt=payload.prompt,
        fields=fields,
        name=name,
        facts=fixed["facts"],
        prose=fixed["prose"],
        inherited=preview_inherited(view, kind, fields),
        stub_id=payload.stub_id,
        matching_stub_id=None if stub is not None else matching_stub(view, kind, name),
        context=context,
        picks=payload.picks,
        treated_as_new=payload.new_names,
    )


# --- links ------------------------------------------------------------------


def _stub_out(state: ThingState) -> dict | None:
    """A thing's stub marker for the wire: `None` for a full entry."""

    return {"ignored": state.stub_ignored} if state.is_stub else None


class _Links:
    """Linked text in one view, for the wire: runs of rendered text as
    `{text, ref, stub}`, `ref` the thing a run links to and `stub` whether
    that thing is a stub. A link to an ignored stub is plain text: ignoring
    a stub hides it everywhere. Each linked thing is looked up once."""

    def __init__(self, view: WorldView) -> None:
        self.view = view
        self._states: dict[str, ThingState | None] = {}

    def _state(self, thing_id: str) -> ThingState | None:
        if thing_id not in self._states:
            self._states[thing_id] = self.view.thing(thing_id)
        return self._states[thing_id]

    def _out(self, runs: list[Segment]) -> list[dict]:
        out: list[dict] = []
        for run in runs:
            state = self._state(run.ref) if run.ref is not None else None
            linked = state is not None and not state.stub_ignored
            ref = run.ref if linked else None
            if ref is None and out and out[-1]["ref"] is None:
                out[-1]["text"] += run.text
                continue
            out.append(
                {
                    "text": run.text,
                    "ref": ref,
                    "stub": linked and state is not None and state.is_stub,
                }
            )
        return out

    def segments(self, text: str) -> list[dict]:
        """A fact's text, rendered, as linked runs."""

        return self._out(self.view.segments(text))

    def prose_segments(self, text: str, owner: str) -> list[dict]:
        """Prose as linked runs: each name `find_names` matches links to
        its best candidate, keeping the words. A suggested match, and one
        that may mean `owner` (whose prose it is), stay plain."""

        runs: list[Segment] = []
        end = 0
        for match in find_names(self.view, text):
            if match.suggested or any(c.id == owner for c in match.candidates):
                continue
            runs.append(Segment(text=text[end : match.start], ref=None))
            runs.append(Segment(text=match.text, ref=match.candidates[0].id))
            end = match.end
        runs.append(Segment(text=text[end:], ref=None))
        return self._out([run for run in runs if run.text])

    def named_stubs(self, state: ThingState) -> list[dict]:
        """`{id, name, kind}` of each live stub `state`'s facts link to (not
        an ignored one), in the order they're first linked."""

        found: list[dict] = []
        seen: set[str] = {state.id}
        for fact in state.facts:
            for thing_id in fact.refs:
                if thing_id in seen:
                    continue
                seen.add(thing_id)
                other = self._state(thing_id)
                if other is None or not other.is_stub or other.stub_ignored:
                    continue
                found.append(
                    {
                        "id": thing_id,
                        "name": self.view.name_of(thing_id) or "",
                        "kind": other.kind,
                    }
                )
        return found


# --- the plugin ---------------------------------------------------------------


class WorldsPlugin(Plugin):
    router = "worlds"

    # where worlds live; tests point this at a temp directory
    worlds_root: Path | None = None

    def connect(self):
        # background tasks, kept referenced until they finish
        self.tasks: set[asyncio.Task] = set()
        # one lock per thing id, so its prose tasks run in order
        self._prose_locks: dict[str, asyncio.Lock] = {}

    def disconnect(self):
        self._set_world(None)

    # --- the open world ---------------------------------------------------

    @property
    def root(self) -> Path:
        return Path(self.worlds_root or WORLDS_DIR)

    @property
    def world(self) -> World | None:
        return getattr(self.websocket_handler, "world", None)

    def _set_world(self, world: World | None) -> None:
        """Make `world` the open one, closing the one before it. Background
        tasks still working on the old world are cancelled first."""

        old = self.world
        if old is not None and old is not world:
            for task in list(self.tasks):
                task.cancel()
            old.close()
        self.websocket_handler.world = world

    def _require_world(self) -> World:
        world = self.world
        if world is None:
            raise ValueError("No world is open")
        return world

    def _client(self) -> Any:
        return instance.get_agent("creator").client

    def _fixed_setup(self) -> dict | None:
        """The browser tests' fixed scene-setup reply, or `None` normally."""

        path = _fixed_file(FIXED_SETUP_ENV)
        if path is None:
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _reply(self, action: str, data: Any) -> None:
        self.websocket_handler.queue_put(
            {"type": self.router, "action": action, "data": data}
        )

    def _world_info(self, world: World) -> dict:
        calendar = world.calendar
        return {
            "id": world.id,
            "name": world.name,
            "path": str(world.path),
            "head_rev": world.head_rev(),
            "calendar": calendar.model_dump(mode="json"),
            **self._present_info(world),
        }

    def _present_info(self, world: World) -> dict:
        """The world's present, and the "now" creation uses (the later of
        the present and where the latest scene got to)."""

        calendar = world.calendar
        return {
            "present": _date_out(calendar, world.present()),
            "now": _date_out(calendar, current_date(world)),
        }

    def _thing_payload(self, world: World, thing_id: str, at: WorldDate | None) -> dict:
        view = world.view(at)
        state = view.thing(thing_id)
        if state is None:
            raise KeyError(f"no such thing: {thing_id}")
        calendar = world.calendar

        links = _Links(view)
        facts = [
            {
                "fact_id": fact.fact_id,
                "category": fact.category,
                "text": fact.text,
                "rendered": view.render(fact.text),
                "segments": links.segments(fact.text),
                "valid_from": _date_out(calendar, fact.valid_from),
                "valid_until": _date_out(calendar, fact.valid_until),
                "source_rev": fact.source_rev,
                "overrides": list(fact.overrides),
            }
            for fact in state.facts
        ]
        inherited = [
            {
                "fact_id": item.fact.fact_id,
                "category": item.fact.category,
                "rendered": view.render(item.fact.text),
                "segments": links.segments(item.fact.text),
                "source_id": item.source_id,
                "source_kind": item.source_kind,
                "source_name": item.source_name,
                "overridden_by": item.overridden_by,
            }
            for item in heritage.inherited(view, thing_id)
        ]

        cache = world.prose()
        prose = {}
        prose_segments = {}
        for section in prose_gen.sections_for(state.kind):
            cached = cache.get(thing_id, section, at)
            prose_segments[section] = (
                links.prose_segments(cached.text, thing_id)
                if cached is not None
                else []
            )
            prose[section] = {
                "text": cached.text if cached is not None else None,
                "stale": cache.stale(
                    thing_id,
                    section,
                    at,
                    prose_gen.staleness_also(world, thing_id, section, at),
                ),
                "edited": cached.edited if cached is not None else False,
            }

        timeline = [
            {
                "date": _date_out(calendar, entry.date),
                "change": entry.change,
                "field": entry.field,
                "value": _value_out(calendar, entry.value),
                "fact_id": entry.fact_id,
                "text": entry.text,
                "category": entry.category,
                "source_rev": entry.source_rev,
                "source": entry.source.model_dump(mode="json"),
            }
            for entry in world.timeline(thing_id)
        ]

        return {
            "id": thing_id,
            "kind": state.kind,
            "name": view.name_of(thing_id) or "",
            "at": _date_out(calendar, at),
            "fields": {
                field: _value_out(calendar, value)
                for field, value in state.fields.items()
                # each has a key of its own
                if field not in ("aka", "stub")
            },
            "aka": state.fields.get("aka") or [],
            "stub": _stub_out(state),
            "facts": facts,
            "inherited": inherited,
            "numbers": heritage.numbers(view, thing_id).model_dump(),
            "life_stage": self._life_stage(world, view, state, at),
            **self._species_members(state, view),
            "prose": prose,
            "prose_segments": prose_segments,
            "mentions": [m.model_dump() for m in mentions(view, thing_id)],
            "named_stubs": links.named_stubs(state),
            "timeline": timeline,
            "appears_in": self._appears_in(world, [thing_id]),
            "referenced_in": {
                **thing_references(world, thing_id),
                "member_scenes": self._appears_in(
                    world, heritage.members(view, thing_id)
                ),
            },
        }

    @staticmethod
    def _life_stage(
        world: World, view: WorldView, state: ThingState, at: WorldDate | None
    ) -> dict | None:
        """A character's life stage at `at` (the world's "now" when `at`
        is unset), from its `born` and its resolved numbers; `None` with
        no `born`, no numbers to go by, or not born yet at `at`."""

        born = state.fields.get("born")
        if state.kind != "character" or not isinstance(born, WorldDate):
            return None
        age = age_in_years(born, at if at is not None else current_date(world))
        if age < 0:
            return None
        stage, past_lifespan = heritage.life_stage(
            age, heritage.numbers(view, state.id)
        )
        if stage is None:
            return None
        return {"stage": stage, "past_lifespan": past_lifespan}

    @staticmethod
    def _species_members(state: ThingState, view: WorldView) -> dict:
        """A species page's races and mixes (a mix listed on every species
        it descends from), by name; empty lists for any other kind."""

        found: dict[str, list[dict]] = {"races": [], "mixes": []}
        if state.kind != "species":
            return found
        for kind, key in (("race", "races"), ("mix", "mixes")):
            found[key] = sorted(
                (
                    {"id": other.id, "name": view.name_of(other.id) or ""}
                    for other in view.things(kind)
                    if state.id in heritage.species_of(view, other.id)
                ),
                key=lambda entry: entry["name"],
            )
        return found

    def _appears_in(self, world: World, thing_ids: list[str]) -> list[dict]:
        """The scenes any of `thing_ids` takes part in: as the player, a
        character, the place, or pulled-in lore. Each scene once."""

        calendar = world.calendar
        wanted = set(thing_ids)
        scenes = []
        if not wanted:
            return scenes
        for record in world.scenes().list():
            state = record.state
            characters = state.get("characters") or []
            in_scene = {
                record.player_thing_id,
                state.get("place_thing_id"),
                *(state.get("pulled_in") or []),
                *(
                    entry.get("thing_id")
                    for entry in characters
                    if isinstance(entry, dict)
                ),
            }
            if wanted & in_scene:
                scenes.append(
                    {
                        "id": record.id,
                        "name": record.name,
                        "start": _date_out(calendar, record.start),
                    }
                )
        return scenes

    def _scene_out(self, world: World, record: SceneRecord) -> dict:
        calendar = world.calendar
        messages = world.scenes().messages(record.id)
        end = (
            scene_end(record.start, messages[-1].elapsed) if messages else record.start
        )
        return {
            "id": record.id,
            "name": record.name,
            "start": _date_out(calendar, record.start),
            "end": _date_out(calendar, end),
            "premise": record.premise,
            "goal": record.goal,
            "player_thing_id": record.player_thing_id,
            "continued_from": record.continued_from,
            "updated_at": record.updated_at,
        }

    def _setup_out(self, world: World, setup: SceneSetup) -> dict:
        """A setup for the wire, with the names of the world things in it
        (as of its start) for display."""

        view = world.view(setup.start)
        refs = [setup.player, *setup.characters]
        if setup.place is not None:
            refs.append(setup.place)
        thing_ids = [ref.thing_id for ref in refs if ref.thing_id is not None]
        return {
            "setup": {
                **setup.model_dump(mode="json"),
                "start": _date_out(world.calendar, setup.start),
            },
            "names": {
                thing_id: view.name_of(thing_id) or ""
                for thing_id in [*thing_ids, *setup.pulled_in]
            },
        }

    async def _planned(self, world: World, planning: Coroutine) -> SceneSetup:
        """`planning`'s setup. In the browser tests (a fixed setup, so no
        client to preview stubs with), the fixed preview, if there is one,
        stands in for each stub's preview, as `preview_thing` would."""

        setup = await planning
        fixed = _fixed_file(FIXED_PREVIEW_ENV)
        if fixed is None or setup.stub_previews:
            return setup
        view = world.view()
        setup.stub_previews = [
            await _fixed_preview(
                fixed,
                PreviewPayload(
                    kind=state.kind,
                    prompt=suggested_prompt(view, stub_id),
                    stub_id=stub_id,
                ),
                view,
            )
            for stub_id in stubs_to_fill(world, setup)
            if (state := view.thing(stub_id)) is not None
        ]
        return setup

    # --- background tasks -------------------------------------------------

    def _spawn(self, coro: Coroutine, callback) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        task.add_done_callback(callback)
        return task

    def _schedule_prose(
        self,
        thing_id: str,
        at: WorldDate | None,
        *,
        regenerate: bool = False,
        section: str | None = None,
    ) -> asyncio.Task | None:
        """Bring `thing_id`'s prose up to date at `at` in the background:
        the stale sections, or with `regenerate` every section (just
        `section`, if given). Answers `prose_updated {id}` (with `section`,
        if given) when done. With no client to ask, the edit stands and
        the prose is left stale.

        `thing_id` may be gone by the time this runs -- deleted while the
        task sat queued, or (from `reposition_scene`) a character who's
        since been removed from the world. With `regenerate=False` that's
        skipped quietly rather than reported as "Error generating world
        prose" after what was, from the owner's side, a successful
        delete."""

        world = self._require_world()
        try:
            client = self._client()
        except KeyError:
            client = None
        if client is None:
            if regenerate:
                raise ValueError("No AI client is set up to write the prose")
            log.warning("worlds.prose_skipped", reason="no AI client")
            return None

        lock = self._prose_locks.setdefault(thing_id, asyncio.Lock())

        async def run() -> None:
            async with lock:
                if not regenerate:
                    if world.view(at).thing(thing_id) is None:
                        log.info(
                            "worlds.prose_skipped", reason="thing deleted", id=thing_id
                        )
                        return
                    await prose_gen.ensure_prose(world, thing_id, at, client)
                    return
                state = world.view(at).thing(thing_id)
                if state is None:
                    raise KeyError(f"no such thing: {thing_id}")
                sections = (section,) if section else prose_gen.sections_for(state.kind)
                for name in sections:
                    await prose_gen.generate_section(world, thing_id, name, at, client)

        done = {"id": thing_id, **({"section": section} if section else {})}
        return self._spawn(
            run(),
            self.create_task_done_callback(
                "prose_updated",
                "prose_failed",
                "Error generating world prose",
                success_data=done,
                failure_data=done,
            ),
        )

    def _require_fact_of(
        self, world: World, thing_id: str, fact_id: str
    ) -> TimelineEntry:
        """The live start of `thing_id`'s own fact `fact_id` (its text and
        dates), refusing an edit to a fact that isn't the thing's own, so
        the reply and the prose refresh are for the thing that changed."""

        for entry in world.timeline(thing_id):
            if entry.fact_id == fact_id and entry.change == "fact_start":
                return entry
        raise KeyError(f"no such fact on {thing_id}: {fact_id}")

    @staticmethod
    def _linked(
        world: World,
        thing_id: str,
        text: str,
        picks: dict[str, str],
        at: WorldDate | None,
        new_names: list[str] | None = None,
        spans: list[LinkSpan] | None = None,
    ) -> str:
        """Hand-written fact text with its names linked, as things are
        named at `at` (`links.link_text`): first the `spans` (a fact form's
        existing links, by position: each to its own thing, or kept plain),
        then entries, stubs and the owner's `picks` in the rest, never
        `thing_id` itself, nor a name the owner treats as new
        (`new_names`). A span to `thing_id`, or to a thing that isn't
        there, keeps its words plain. Unknown phrases stay as they are."""

        view = world.view(at)
        kept = [
            span
            if span.ref is None
            or (span.ref != thing_id and view.thing(span.ref) is not None)
            else LinkSpan(start=span.start, end=span.end)
            for span in spans or []
        ]
        return link_text(
            view,
            text,
            picks=picks,
            owner=thing_id,
            as_new=new_names or (),
            spans=kept,
        )

    @staticmethod
    def _require_stub(world: World, thing_id: str) -> ThingState:
        """The stub `thing_id`, refusing a missing thing or a full entry."""

        view = world.view()
        state = view.thing(thing_id)
        if state is None:
            raise KeyError(f"no such thing: {thing_id}")
        if not state.is_stub:
            raise ValueError(f"not a stub: {view.name_of(thing_id) or thing_id}")
        return state

    def _edited(self, action: str, thing_id: str, at: WorldDate | None) -> None:
        """Answer an edit with the thing as of `at`, then refresh its prose."""

        self._reply(action, self._thing_payload(self._require_world(), thing_id, at))
        self._schedule_prose(thing_id, at)

    # --- worlds -----------------------------------------------------------

    async def handle_list_worlds(self, data: dict):
        worlds = [
            {
                "id": info.id,
                "name": info.name,
                "path": str(info.path),
                "head_rev": info.head_rev,
            }
            for info in World.list(self.root)
        ]
        self._reply("list_worlds", {"worlds": worlds})

    async def handle_create_world(self, data: dict):
        payload = CreateWorldPayload(**data)
        # validated before anything is written: years run 1-9999
        present = WorldDate.of(payload.present_year)
        world = World.create(payload.name, root=self.root)
        world.set_present(present)
        self._set_world(world)
        self._reply("create_world", self._world_info(world))

    async def handle_open_world(self, data: dict):
        payload = OpenWorldPayload(**data)
        path = Path(payload.path).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError(f"not a world in {self.root}: {payload.path}")
        world = World.open(path)
        self._set_world(world)
        self._reply("open_world", self._world_info(world))

    async def handle_get_present(self, data: dict):
        self._reply("get_present", self._present_info(self._require_world()))

    async def handle_set_present(self, data: dict):
        payload = SetPresentPayload(**data)
        world = self._require_world()
        world.set_present(WorldDate.of(payload.year))
        self._reply("set_present", self._present_info(world))

    # --- things -----------------------------------------------------------

    async def handle_list_things(self, data: dict):
        payload = ListThingsPayload(**data)
        world = self._require_world()
        view = world.view()
        things = []
        for state in view.things(payload.kind):
            if state.stub_ignored:
                continue
            entry: dict[str, Any] = {
                "id": state.id,
                "kind": state.kind,
                "name": view.name_of(state.id) or "",
            }
            if state.is_stub:
                entry["stub"] = _stub_out(state)
            things.append(entry)
        self._reply("list_things", {"kind": payload.kind, "things": things})

    async def handle_list_heritage(self, data: dict):
        view = self._require_world().view()
        things = [
            {
                "id": state.id,
                "kind": state.kind,
                "name": view.name_of(state.id) or "",
                "species_ids": heritage.species_of(view, state.id),
            }
            for kind in HERITAGE_KINDS
            for state in sorted(
                view.things(kind), key=lambda state: view.name_of(state.id) or ""
            )
        ]
        self._reply("list_heritage", {"things": things})

    async def handle_find_mix(self, data: dict):
        payload = FindMixPayload(**data)
        view = self._require_world().view()
        a, b = payload.parents
        self._reply(
            "find_mix",
            {"parents": payload.parents, "mix_id": heritage.find_mix(view, a, b)},
        )

    async def handle_get_thing(self, data: dict):
        payload = GetThingPayload(**data)
        world = self._require_world()
        self._reply(
            "get_thing", self._thing_payload(world, payload.id, _date_in(payload.at))
        )

    # --- delete -----------------------------------------------------------

    async def handle_thing_references(self, data: dict):
        payload = ThingIdPayload(**data)
        world = self._require_world()
        view = world.view()
        state = view.thing(payload.id)
        if state is None:
            raise KeyError(f"no such thing: {payload.id}")
        self._reply(
            "thing_references",
            {
                "id": payload.id,
                "kind": state.kind,
                "name": view.name_of(payload.id) or "",
                "references": thing_references(world, payload.id),
            },
        )

    async def handle_delete_thing(self, data: dict):
        payload = ThingIdPayload(**data)
        world = self._require_world()
        view = world.view()
        state = view.thing(payload.id)
        if state is None:
            raise KeyError(f"no such thing: {payload.id}")
        name = view.name_of(payload.id) or payload.id
        with world.revision(Source.manual(note=f"deleted {name}")) as rev:
            rev.remove_thing(payload.id)
        log.info("worlds.thing_deleted", id=payload.id, kind=state.kind, name=name)
        self._reply("thing_deleted", {"id": payload.id, "kind": state.kind})
        await self.handle_list_things({"kind": state.kind})

    # --- create -----------------------------------------------------------

    async def handle_preview_thing(self, data: dict):
        payload = PreviewPayload(**data)
        world = self._require_world()
        fixed = _fixed_file(FIXED_PREVIEW_ENV)
        if fixed is not None:
            preview = _fixed_preview(fixed, payload, world.view())
        else:
            client = self._client()
            preview = preview_thing(
                world,
                payload.kind,
                payload.prompt,
                payload.fields,
                client,
                stub_id=payload.stub_id,
                picks=payload.picks,
                new_names=payload.new_names,
            )
        self._spawn(
            preview,
            self.create_task_done_callback(
                "preview_thing",
                "preview_failed",
                "Error previewing a world thing",
                success_data=lambda preview: preview.model_dump(mode="json"),
            ),
        )

    async def handle_accept_preview(self, data: dict):
        payload = AcceptPreviewPayload(**data)
        world = self._require_world()
        thing_id = accept_preview(world, payload.preview, into_stub=payload.into_stub)
        self._reply("accept_preview", self._thing_payload(world, thing_id, None))

    # --- stubs ------------------------------------------------------------

    async def handle_make_stub(self, data: dict):
        """Make a stub named `text` (or reuse the thing already named so,
        reviving an ignored stub) and link that phrase in the fact,
        answering like `correct_fact`. Only the first occurrence of the
        phrase outside any reference is linked; nothing else in the fact
        changes. A phrase the fact doesn't hold that way is refused, writing
        nothing."""

        payload = MakeStubPayload(**data)
        world = self._require_world()
        at = _date_in(payload.at)
        fact = self._require_fact_of(world, payload.thing_id, payload.fact_id)
        phrase = " ".join(payload.text.split())
        if not phrase:
            raise ValueError("a stub needs a name")
        if payload.kind not in KINDS:
            raise ValueError(f"no such kind: {payload.kind!r}")
        old_text = fact.text or ""
        with world.revision(Source.manual(note=f"stub {phrase}")) as rev:
            made = make_stubs(
                rev, world.view(at), [NewName(name=phrase, kind=payload.kind)]
            )
            stub_id = made[phrase]
            if stub_id == payload.thing_id:
                raise ValueError(f"{phrase!r} is this thing's own name")
            reused = world.view(at).thing(stub_id)
            if reused is not None and reused.stub_ignored:
                # the owner asked for it by name: it's no longer ignored
                rev.set_field(stub_id, "stub", {"ignored": False}, None)
            # only the phrase is linked: the rest of the fact stays as the
            # owner left it (a name treated as new stays plain)
            rev.correct_fact(
                payload.fact_id, text=link_phrase(old_text, phrase, stub_id)
            )
        log.info("worlds.stub_made", id=stub_id, name=phrase, kind=payload.kind)
        self._edited("make_stub", payload.thing_id, at)

    async def handle_list_stubs(self, data: dict):
        payload = ListStubsPayload(**data)
        view = self._require_world().view()
        stubs = []
        for state in view.things():
            if not state.is_stub or (
                state.stub_ignored and not payload.include_ignored
            ):
                continue
            found = mentions(view, state.id)
            # the mention written first: the lowest revision, then fact order
            written = {
                fact.fact_id: fact.source_rev
                for _owner, fact in view.referencing(state.id, any_date=True)
            }
            first = min(
                enumerate(found),
                key=lambda pair: (written.get(pair[1].fact_id, 0), pair[0]),
                default=None,
            )
            stubs.append(
                {
                    "id": state.id,
                    "name": view.name_of(state.id) or "",
                    "kind": state.kind,
                    "first_mentioned": (
                        {"thing_id": first[1].owner_id, "name": first[1].owner_name}
                        if first is not None
                        else None
                    ),
                    "mentions": len(found),
                    "ignored": state.stub_ignored,
                }
            )
        stubs.sort(key=lambda stub: (stub["name"].casefold(), stub["id"]))
        self._reply("list_stubs", {"stubs": stubs})

    async def handle_ignore_stub(self, data: dict):
        payload = IgnoreStubPayload(**data)
        world = self._require_world()
        self._require_stub(world, payload.id)
        with world.revision(Source.manual()) as rev:
            rev.set_field(payload.id, "stub", {"ignored": payload.ignored}, None)
        self._reply("ignore_stub", self._thing_payload(world, payload.id, None))

    async def handle_change_stub_kind(self, data: dict):
        payload = ChangeStubKindPayload(**data)
        world = self._require_world()
        self._require_stub(world, payload.id)
        with world.revision(Source.manual()) as rev:
            rev.change_stub_kind(payload.id, payload.kind)
        self._reply("change_stub_kind", self._thing_payload(world, payload.id, None))

    async def handle_stub_suggestion(self, data: dict):
        payload = ThingIdPayload(**data)
        world = self._require_world()
        self._require_stub(world, payload.id)
        view = world.view()
        self._reply(
            "stub_suggestion",
            {
                "id": payload.id,
                "prompt": suggested_prompt(view, payload.id),
                "context": [
                    [heading, facts]
                    for heading, facts in mention_context(view, payload.id)
                ],
            },
        )

    # --- edits ------------------------------------------------------------

    async def handle_add_fact(self, data: dict):
        payload = AddFactPayload(**data)
        world = self._require_world()
        text = self._linked(
            world,
            payload.thing_id,
            payload.text,
            payload.picks,
            _date_in(payload.valid_from) or _date_in(payload.at),
            payload.new_names,
            payload.spans,
        )
        with world.revision(Source.manual()) as rev:
            rev.add_fact(
                payload.thing_id,
                payload.category,
                text,
                valid_from=_date_in(payload.valid_from),
                valid_until=_date_in(payload.valid_until),
            )
        self._edited("add_fact", payload.thing_id, _date_in(payload.at))

    async def handle_correct_fact(self, data: dict):
        payload = CorrectFactPayload(**data)
        world = self._require_world()
        dates = {
            key: _date_in(getattr(payload, key))
            for key in ("valid_from", "valid_until")
            if key in payload.model_fields_set
        }
        self._require_fact_of(world, payload.thing_id, payload.fact_id)
        text = payload.text
        if text is not None:
            text = self._linked(
                world,
                payload.thing_id,
                text,
                payload.picks,
                _date_in(payload.valid_from) or _date_in(payload.at),
                payload.new_names,
                payload.spans,
            )
        with world.revision(Source.manual()) as rev:
            rev.correct_fact(
                payload.fact_id,
                text=text,
                category=payload.category,
                **dates,
            )
        self._edited("correct_fact", payload.thing_id, _date_in(payload.at))

    async def handle_repoint_ref(self, data: dict):
        """Point one reference of an own fact (its `occurrence`-th, in the
        raw text) at `to_id`, keeping its words; nothing else in the fact
        changes. Answers like `correct_fact`."""

        payload = RepointRefPayload(**data)
        world = self._require_world()
        at = _date_in(payload.at)
        fact = self._require_fact_of(world, payload.thing_id, payload.fact_id)
        view = world.view(at)
        if view.thing(payload.to_id) is None:
            raise KeyError(f"no such thing: {payload.to_id}")
        if payload.to_id == payload.thing_id:
            raise ValueError("a fact can't reference its own thing")
        text = fact.text or ""
        old = next(
            (
                found
                for index, found in enumerate(REF_PATTERN.finditer(text))
                if index == payload.occurrence
            ),
            None,
        )
        rendered = (
            "".join(seg.text for seg in view.segments(old.group(0))) if old else ""
        )
        new_text = repoint_ref(text, payload.occurrence, payload.to_id, rendered)
        with world.revision(Source.manual()) as rev:
            rev.correct_fact(payload.fact_id, text=new_text)
        self._edited("repoint_ref", payload.thing_id, at)

    async def handle_end_fact(self, data: dict):
        payload = EndFactPayload(**data)
        world = self._require_world()
        self._require_fact_of(world, payload.thing_id, payload.fact_id)
        until = WorldDate.model_validate(payload.until)
        with world.revision(Source.manual()) as rev:
            rev.end_fact(payload.fact_id, until)
        self._edited("end_fact", payload.thing_id, _date_in(payload.at))

    async def handle_remove_fact(self, data: dict):
        payload = RemoveFactPayload(**data)
        world = self._require_world()
        self._require_fact_of(world, payload.thing_id, payload.fact_id)
        with world.revision(Source.manual()) as rev:
            rev.remove_fact(payload.fact_id)
        self._edited("remove_fact", payload.thing_id, _date_in(payload.at))

    async def handle_set_field(self, data: dict):
        payload = SetFieldPayload(**data)
        world = self._require_world()
        with world.revision(Source.manual()) as rev:
            rev.set_field(
                payload.thing_id,
                payload.field,
                payload.value,
                _date_in(payload.valid_from),
            )
        self._edited("set_field", payload.thing_id, _date_in(payload.at))

    async def handle_override_fact(self, data: dict):
        payload = OverrideFactPayload(**data)
        world = self._require_world()
        at = _date_in(payload.at)
        inherited_ids = {
            item.fact.fact_id
            for item in heritage.inherited(world.view(at), payload.thing_id)
        }
        if payload.overridden_fact_id not in inherited_ids:
            raise KeyError(
                f"{payload.thing_id} doesn't inherit fact {payload.overridden_fact_id}"
            )
        text = self._linked(
            world,
            payload.thing_id,
            payload.text,
            payload.picks,
            at,
            payload.new_names,
            payload.spans,
        )
        with world.revision(Source.manual()) as rev:
            rev.add_fact(
                payload.thing_id,
                payload.category,
                text,
                overrides=[payload.overridden_fact_id],
            )
        self._edited("override_fact", payload.thing_id, at)

    async def handle_regenerate_prose(self, data: dict):
        payload = RegenerateProsePayload(**data)
        world = self._require_world()
        at = _date_in(payload.at)
        if payload.section is not None:
            state = world.view(at).thing(payload.id)
            if state is None:
                raise KeyError(f"no such thing: {payload.id}")
            if payload.section not in prose_gen.sections_for(state.kind):
                raise ValueError(
                    f"a {state.kind} has no {payload.section!r} prose section"
                )
        self._schedule_prose(payload.id, at, regenerate=True, section=payload.section)

    # --- scenes -----------------------------------------------------------

    async def handle_match_names(self, data: dict):
        payload = MatchNamesPayload(**data)
        world = self._require_world()
        at = _date_in(payload.at)
        matches = match_names(world, payload.text, at)
        unknown = unknown_proper_phrases(world.view(at), payload.text)
        self._reply(
            "match_names",
            {
                "text": payload.text,
                # echoed, so the screen can tell which lookup this answers
                "at": payload.at,
                "matches": [m.model_dump() for m in matches],
                "unknown": [u.model_dump() for u in unknown],
            },
        )

    async def handle_plan_scene(self, data: dict):
        payload = PlanScenePayload(**data)
        world = self._require_world()
        fixed = self._fixed_setup()
        client = self._client() if fixed is None else None
        planning = plan_scene(
            world,
            payload.prompt,
            payload.picks,
            payload.player,
            _date_in(payload.start),
            client,
            reply=fixed,
            new_names=payload.new_names,
        )
        self._spawn(
            self._planned(world, planning) if fixed is not None else planning,
            self.create_task_done_callback(
                "plan_scene",
                "plan_failed",
                "Error planning a world scene",
                success_data=lambda setup: self._setup_out(world, setup),
            ),
        )

    async def handle_start_scene(self, data: dict):
        payload = StartScenePayload(**data)
        world = self._require_world()
        client = None if os.environ.get(FIXED_SETUP_ENV) else self._client()

        def started(scene_id: str) -> dict:
            record = world.scenes().get(scene_id)
            assert record is not None
            return {
                "scene_id": scene_id,
                "target": world_target(str(world.path), scene_id),
                "scene": self._scene_out(world, record),
            }

        self._spawn(
            start_scene(world, payload.setup, client),
            self.create_task_done_callback(
                "start_scene",
                "start_failed",
                "Error starting a world scene",
                success_data=started,
            ),
        )

    async def handle_list_scenes(self, data: dict):
        world = self._require_world()
        scenes = [self._scene_out(world, record) for record in world.scenes().list()]
        self._reply("list_scenes", {"scenes": scenes})

    async def handle_continue_scene(self, data: dict):
        """Plan the scene after `scene_id`. If that's the loaded scene, it's
        saved first, so the summary covers what hasn't been saved yet."""

        payload = ContinueScenePayload(**data)
        world = self._require_world()
        scene = self._loaded_scene(world, payload.scene_id)
        if scene is not None:
            save_world_scene(scene)
        fixed = self._fixed_setup()
        client = self._client() if fixed is None else None
        planning = continue_setup(
            world, payload.scene_id, payload.goal_prompt, client, reply=fixed
        )
        self._spawn(
            self._planned(world, planning) if fixed is not None else planning,
            self.create_task_done_callback(
                "continue_scene",
                "continue_failed",
                "Error continuing a world scene",
                success_data=lambda setup: self._setup_out(world, setup),
            ),
        )

    async def handle_reposition_scene(self, data: dict):
        """Move a scene's start date. In the slice nothing from a scene has
        reached the world yet, so only the start changes; the messages move
        with it. If the scene is the one loaded, its characters are rebuilt
        for the new date and its status sent, so open character sheets
        follow. The scene's world characters then get their prose for the
        new start in the background; the loaded scene is rebuilt again once
        that's done."""

        payload = RepositionScenePayload(**data)
        world = self._require_world()
        start = WorldDate.model_validate(payload.start)
        store = world.scenes()
        store.update(payload.scene_id, start=start)
        record = store.get(payload.scene_id)
        assert record is not None

        scene = self._loaded_scene(world, payload.scene_id)
        if scene is not None:
            await self._refresh_loaded(scene)

        prose_tasks = [
            task
            for task in (
                self._schedule_prose(thing_id, start)
                for thing_id in self._world_characters(record)
            )
            if task is not None
        ]
        if scene is not None and prose_tasks:

            async def refresh_after_prose() -> None:
                await asyncio.gather(*prose_tasks, return_exceptions=True)
                if self._loaded_scene(world, payload.scene_id) is scene:
                    await self._refresh_loaded(scene)

            self._spawn(refresh_after_prose(), self._log_failure)

        self._reply("reposition_scene", self._scene_out(world, record))

    def _loaded_scene(self, world: World, scene_id: str) -> Any:
        """The handler's scene if it's world scene `scene_id` of `world`."""

        scene = getattr(self.websocket_handler, "scene", None)
        ref = getattr(scene, "world_ref", None)
        if (
            ref is not None
            and getattr(scene, "world_context", None) is not None
            and ref.scene_id == scene_id
            and Path(ref.world_path).resolve() == world.path.resolve()
        ):
            return scene
        return None

    async def _refresh_loaded(self, scene: Any) -> None:
        """Rebuild a loaded world scene's characters from its (re-read)
        record and send its status."""

        context = scene.world_context
        context.record = context.world.scenes().get(context.record.id)
        await context.refresh_characters(scene)
        scene.emit_status()

    @staticmethod
    def _world_characters(record: SceneRecord) -> list[str]:
        """The world things a scene plays: its player and its characters."""

        thing_ids = [record.player_thing_id] if record.player_thing_id else []
        for entry in record.state.get("characters") or []:
            if isinstance(entry, dict) and entry.get("thing_id"):
                thing_ids.append(entry["thing_id"])
        return list(dict.fromkeys(thing_ids))

    @staticmethod
    def _log_failure(task: asyncio.Task[Any]) -> None:
        if not task.cancelled() and task.exception() is not None:
            log.error("worlds.background_failed", error=str(task.exception()))
