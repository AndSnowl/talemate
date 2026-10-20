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
- Things: `list_things {kind}`, `get_thing {id, at}`. A thing's payload
  holds its fields, the facts visible at `at`, its cached prose per
  section (with whether it's stale), its whole timeline and the scenes it
  appears in.
- Create: `preview_thing {kind, prompt, fields}` runs in the background and
  answers `preview_thing {preview}` or `preview_failed {message}`; it
  writes nothing. `accept_preview {preview}` writes it and answers with the
  new thing. For the browser tests only, `TALEMATE_TEST_FIXED_PREVIEW`
  names a JSON file (`{name, facts, prose, fields?}`) that previews are
  answered from instead of the model.
- Edits: `add_fact`, `correct_fact`, `end_fact`, `remove_fact` and
  `set_field` each write one revision, answer with the thing, then start a
  background `ensure_prose` that answers `prose_updated {id}` (or
  `prose_failed`); with no AI client the edit stands and the prose is left
  stale. `regenerate_prose {id, at}` regenerates every section.
  Prose tasks for one thing run one at a time, in order, so a later edit's
  check always sees what the earlier task cached.
- Delete: `thing_references {id}` answers `{id, kind, name, references}`
  (the facts, fields and scenes that use it, from
  `talemate.worldplay.references`), writing nothing. `delete_thing {id}`
  removes it in one manual revision noted "deleted <name>", so undoing
  that revision restores it, and answers `thing_deleted {id, kind}` and
  that kind's `list_things`. A loaded scene keeps playing with it until
  it's reloaded.
- Scenes: `match_names {text, at}` finds world thing names in a storyline
  prompt (the reply echoes `text` and `at`). `plan_scene {prompt, picks, new_names, player, start}` (picks
  and names treated as new always win over automatic matching) and
  `continue_scene {scene_id, goal_prompt}` (saving that scene first if
  it's the one loaded) run in the background and answer
  with `{setup, names}` (the world things' names, for display), or
  `plan_failed`/`continue_failed`; they write nothing. `start_scene {setup}`
  (background too: it brings the characters' prose up to date) writes the
  scene and answers `{scene_id, target, scene}` (or `start_failed`), where
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
  is.

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
from talemate.world.calendar import Calendar
from talemate.world.dates import WorldDate
from talemate.world.scenes import SceneRecord, scene_end
from talemate.world.store import Source, World
from talemate.worldplay import prose_gen
from talemate.worldplay.create import (
    CreatePreview,
    accept_preview,
    current_date,
    preview_thing,
)
from talemate.worldplay.persistence import save_world_scene, world_target
from talemate.worldplay.references import thing_references
from talemate.worldplay.setup import (
    SceneSetup,
    continue_setup,
    match_names,
    plan_scene,
    start_scene,
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


class AcceptPreviewPayload(pydantic.BaseModel):
    preview: CreatePreview


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


class CorrectFactPayload(_ThingEdit):
    fact_id: str
    text: str | None = None
    category: str | None = None
    # unset means "keep"; an explicit null means "make it open"
    valid_from: dict | None = None
    valid_until: dict | None = None


class EndFactPayload(_ThingEdit):
    fact_id: str
    until: dict


class RemoveFactPayload(_ThingEdit):
    fact_id: str


class SetFieldPayload(_ThingEdit):
    field: str
    value: Any
    valid_from: dict | None = None


class RegenerateProsePayload(pydantic.BaseModel):
    id: str
    at: dict | None = None


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


async def _fixed_preview(path: Path, payload: PreviewPayload) -> CreatePreview:
    """The browser tests' stand-in for `preview_thing`: the preview in
    `path`, for the request's kind, prompt and fields. Async so it runs
    through the same background task and reply path as the real one."""

    fixed = json.loads(path.read_text(encoding="utf-8"))
    return CreatePreview(
        kind=payload.kind,
        prompt=payload.prompt,
        fields={**payload.fields, **fixed.get("fields", {})},
        name=fixed["name"],
        facts=fixed["facts"],
        prose=fixed["prose"],
    )


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

        facts = [
            {
                "fact_id": fact.fact_id,
                "category": fact.category,
                "text": fact.text,
                "rendered": view.render(fact.text),
                "valid_from": _date_out(calendar, fact.valid_from),
                "valid_until": _date_out(calendar, fact.valid_until),
                "source_rev": fact.source_rev,
            }
            for fact in state.facts
        ]

        cache = world.prose()
        prose = {}
        for section in prose_gen.sections_for(state.kind):
            cached = cache.get(thing_id, section, at)
            prose[section] = {
                "text": cached.text if cached is not None else None,
                "stale": cache.stale(thing_id, section, at),
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
            },
            "facts": facts,
            "prose": prose,
            "timeline": timeline,
            "appears_in": self._appears_in(world, thing_id),
        }

    def _appears_in(self, world: World, thing_id: str) -> list[dict]:
        """The scenes `thing_id` takes part in: as the player, a character,
        the place, or pulled-in lore."""

        calendar = world.calendar
        scenes = []
        for record in world.scenes().list():
            state = record.state
            characters = state.get("characters") or []
            if (
                record.player_thing_id == thing_id
                or state.get("place_thing_id") == thing_id
                or thing_id in (state.get("pulled_in") or [])
                or any(
                    isinstance(entry, dict) and entry.get("thing_id") == thing_id
                    for entry in characters
                )
            ):
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

    # --- background tasks -------------------------------------------------

    def _spawn(self, coro: Coroutine, callback) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        task.add_done_callback(callback)
        return task

    def _schedule_prose(
        self, thing_id: str, at: WorldDate | None, *, regenerate: bool = False
    ) -> asyncio.Task | None:
        """Bring `thing_id`'s prose up to date at `at` in the background:
        the stale sections, or every section with `regenerate`. Answers
        `prose_updated {id}` when done. With no client to ask, the edit
        stands and the prose is left stale.

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
                for section in prose_gen.sections_for(state.kind):
                    await prose_gen.generate_section(
                        world, thing_id, section, at, client
                    )

        return self._spawn(
            run(),
            self.create_task_done_callback(
                "prose_updated",
                "prose_failed",
                "Error generating world prose",
                success_data={"id": thing_id},
                failure_data={"id": thing_id},
            ),
        )

    def _require_fact_of(self, world: World, thing_id: str, fact_id: str) -> None:
        """Refuse an edit to a fact that isn't `thing_id`'s own, so the
        reply and the prose refresh are for the thing that changed."""

        if not any(entry.fact_id == fact_id for entry in world.timeline(thing_id)):
            raise KeyError(f"no such fact on {thing_id}: {fact_id}")

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
        things = [
            {"id": state.id, "kind": state.kind, "name": view.name_of(state.id) or ""}
            for state in view.things(payload.kind)
        ]
        self._reply("list_things", {"kind": payload.kind, "things": things})

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
            preview = _fixed_preview(fixed, payload)
        else:
            client = self._client()
            preview = preview_thing(
                world, payload.kind, payload.prompt, payload.fields, client
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
        thing_id = accept_preview(world, payload.preview)
        self._reply("accept_preview", self._thing_payload(world, thing_id, None))

    # --- edits ------------------------------------------------------------

    async def handle_add_fact(self, data: dict):
        payload = AddFactPayload(**data)
        world = self._require_world()
        with world.revision(Source.manual()) as rev:
            rev.add_fact(
                payload.thing_id,
                payload.category,
                payload.text,
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
        with world.revision(Source.manual()) as rev:
            rev.correct_fact(
                payload.fact_id,
                text=payload.text,
                category=payload.category,
                **dates,
            )
        self._edited("correct_fact", payload.thing_id, _date_in(payload.at))

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

    async def handle_regenerate_prose(self, data: dict):
        payload = RegenerateProsePayload(**data)
        self._require_world()
        self._schedule_prose(payload.id, _date_in(payload.at), regenerate=True)

    # --- scenes -----------------------------------------------------------

    async def handle_match_names(self, data: dict):
        payload = MatchNamesPayload(**data)
        world = self._require_world()
        matches = match_names(world, payload.text, _date_in(payload.at))
        self._reply(
            "match_names",
            {
                "text": payload.text,
                # echoed, so the screen can tell which lookup this answers
                "at": payload.at,
                "matches": [m.model_dump() for m in matches],
            },
        )

    async def handle_plan_scene(self, data: dict):
        payload = PlanScenePayload(**data)
        world = self._require_world()
        fixed = self._fixed_setup()
        client = self._client() if fixed is None else None
        self._spawn(
            plan_scene(
                world,
                payload.prompt,
                payload.picks,
                payload.player,
                _date_in(payload.start),
                client,
                reply=fixed,
                new_names=payload.new_names,
            ),
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
        self._spawn(
            continue_setup(
                world, payload.scene_id, payload.goal_prompt, client, reply=fixed
            ),
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
