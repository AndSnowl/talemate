"""Websocket plugin for the fantasymate world screens (`talemate.world`).

Reply contract: a request `{"type": "worlds", "action": <a>, ...}` is
answered with `{"type": "worlds", "action": <a>, "data": {...}}`. Errors go
through `signal_operation_failed` (an `operation_done` envelope with
`error.message`), writing nothing.

- Worlds: `list_worlds`, `create_world {name}`, `open_world {path}`. The
  open world is held on the websocket handler (`handler.world`), one per
  connection, and closed when the connection goes.
- Things: `list_things {kind}`, `get_thing {id, at}`. A thing's payload
  holds its fields, the facts visible at `at`, its cached prose per
  section (with whether it's stale), its whole timeline and the scenes it
  appears in.
- Create: `preview_thing {kind, prompt, fields}` runs in the background and
  answers `preview_thing {preview}` or `preview_failed {message}`; it
  writes nothing. `accept_preview {preview}` writes it and answers with the
  new thing.
- Edits: `add_fact`, `correct_fact`, `end_fact`, `remove_fact` and
  `set_field` each write one revision, answer with the thing, then start a
  background `ensure_prose` that answers `prose_updated {id}` (or
  `prose_failed`). `regenerate_prose {id, at}` regenerates every section.
  Prose tasks for one thing run one at a time, in order, so a later edit's
  check always sees what the earlier task cached.

Dates go over the wire as `{"instant", "precision", "label"}`, the label
formatted with the world's calendar; `label` is ignored on the way in.
"""

import asyncio
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
from talemate.world.store import Source, World
from talemate.worldplay import prose_gen
from talemate.worldplay.create import (
    CreatePreview,
    accept_preview,
    current_date,
    preview_thing,
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


class CreateWorldPayload(pydantic.BaseModel):
    name: str

    @pydantic.field_validator("name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a world needs a name")
        return value.strip()


class OpenWorldPayload(pydantic.BaseModel):
    path: str


class ListThingsPayload(pydantic.BaseModel):
    kind: str


class GetThingPayload(pydantic.BaseModel):
    id: str
    at: dict | None = None


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
        stands and the prose is left stale."""

        world = self._require_world()
        try:
            client = self._client()
        except KeyError:
            log.warning("worlds.prose_skipped", reason="no creator agent")
            return None

        lock = self._prose_locks.setdefault(thing_id, asyncio.Lock())

        async def run() -> None:
            async with lock:
                if not regenerate:
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
        world = World.create(payload.name, root=self.root)
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

    # --- create -----------------------------------------------------------

    async def handle_preview_thing(self, data: dict):
        payload = PreviewPayload(**data)
        world = self._require_world()
        client = self._client()
        self._spawn(
            preview_thing(world, payload.kind, payload.prompt, payload.fields, client),
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
