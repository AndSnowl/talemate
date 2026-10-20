"""Saving and loading a world-backed `Scene` through the world database,
instead of a scene JSON file.

A world-backed scene has `scene.world_ref` set. Its record in the world's
`SceneStore` holds everything a scene JSON file would, split up:

- `state`: the `Scene.serialize` keys, minus the ones kept elsewhere
  (`_NOT_IN_STATE`), plus whatever scene setup put there (the place, the
  pulled-in lore), plus `characters` -- one entry per character in the
  scene, `{"thing_id": ..., "active": ..., "scene_fields": {...}}` for a
  world character or `{"local_id": ..., "active": ...}` for one invented in
  the scene (its `local_id` a stable 32-hex id, kept on the in-memory
  character as `Character.world_local_id`);
- `premise` (`scene.description`), `goal` and `player_thing_id`;
- the messages, one row each, with a stable `SceneMessage.world_id`;
- the scene-local things: invented characters, kept whole. Local things of
  any other kind (scene setup's invented places, ...) are never touched by
  a save.

A world character is rebuilt with `character_from_world` at the scene's
current date on every load; only its per-scene fields (`scene_fields`:
color, avatar, voice, ...) are stored, and reapplied on top.

`load_world_scene` (in `talemate.load`) drives the load side, through the
ordinary `load_scene_from_data` path, with the scene data built here.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel

from talemate import util
from talemate.save import SceneEncoder
from talemate.scene_message import TimePassageMessage
from talemate.world.scenes import MessageRecord, SceneRecord
from talemate.world.store import World

from .characters import WORLD_DERIVED_FIELDS, character_from_world
from .context import WorldSceneContext, connect, scene_date

if TYPE_CHECKING:
    from talemate.character import Character
    from talemate.tale_mate import Scene

log = structlog.get_logger("talemate.worldplay.persistence")

TARGET_PREFIX = "world://"

# `Scene.serialize` keys that are not kept in the record's `state`: the
# history and characters have their own rows, and a world scene has no
# shared context and always runs the default node graphs
_NOT_IN_STATE = (
    "history",
    "character_data",
    "shared_context",
    "nodes_filename",
    "creative_nodes_filename",
)

# the scene-local thing kind a save owns, and rewrites
LOCAL_CHARACTER_KIND = "character"

# per-scene fields of a world character: everything but what the world
# gives it, and `is_player`, which comes from the record's `player_thing_id`
_NOT_SCENE_FIELDS = {
    *WORLD_DERIVED_FIELDS,
    "world_thing_id",
    "world_local_id",
    "is_player",
}


class WorldSceneRef(BaseModel):
    """Where a world-backed scene lives: a world directory and a scene id
    in its database."""

    world_path: str
    scene_id: str

    @property
    def scene_dir(self) -> str:
        """The scene's own directory inside the world, for its assets and
        nodes (`Scene.save_dir`)."""

        return os.path.join(self.world_path, "scenes", self.scene_id)

    @property
    def target(self) -> str:
        return world_target(self.world_path, self.scene_id)


def world_target(world_path: str, scene_id: str) -> str:
    """The `load_scene` path for a world scene: `world://<world_path>|<scene_id>`."""

    return f"{TARGET_PREFIX}{world_path}|{scene_id}"


def parse_world_target(target: str) -> WorldSceneRef:
    if not target.startswith(TARGET_PREFIX):
        raise ValueError(f"not a world scene target: {target}")
    world_path, sep, scene_id = target[len(TARGET_PREFIX) :].rpartition("|")
    if not sep or not world_path or not scene_id:
        raise ValueError(f"malformed world scene target: {target}")
    return WorldSceneRef(world_path=world_path, scene_id=scene_id)


def _json_safe(value: object) -> object:
    """`value` as plain JSON data, encoded the way scene files are."""

    return json.loads(json.dumps(value, cls=SceneEncoder))


# --- saving -----------------------------------------------------------------


def _character_entries(
    scene: "Scene",
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """`state["characters"]` and the scene-local things, for every
    character in the scene."""

    entries: list[dict[str, object]] = []
    local_things: list[dict[str, object]] = []
    for name, character in scene.character_data.items():
        active = name in scene.active_characters
        if character.world_thing_id:
            entries.append(
                {
                    "thing_id": character.world_thing_id,
                    "active": active,
                    "scene_fields": character.model_dump(
                        mode="json", exclude=_NOT_SCENE_FIELDS
                    ),
                }
            )
        else:
            if not character.world_local_id:
                character.world_local_id = uuid.uuid4().hex
            entries.append({"local_id": character.world_local_id, "active": active})
            local_things.append(
                {
                    "local_id": character.world_local_id,
                    "kind": LOCAL_CHARACTER_KIND,
                    "data": character.model_dump(mode="json"),
                }
            )
    return entries, local_things


def _message_records(scene: "Scene") -> list[MessageRecord]:
    """One record per history message. A message gets its `world_id` the
    first time it's saved, and keeps it. `elapsed` is the scene time as of
    that message -- `scene.calc_time(0, idx + 1) or "PT0S"`, kept as a
    running total rather than re-summed per message."""

    records = []
    seen: set[str] = set()
    elapsed = "PT0S"
    for idx, message in enumerate(scene.history):
        # a copied message can carry another's id; ids must stay unique
        if not message.world_id or message.world_id in seen:
            message.world_id = uuid.uuid4().hex
        seen.add(message.world_id)

        if isinstance(message, TimePassageMessage):
            elapsed = util.iso8601_add(elapsed, message.ts)

        records.append(
            MessageRecord(
                id=message.world_id,
                seq=idx,
                kind=message.typ,
                data=_json_safe(message.to_dict()),
                elapsed=elapsed,
            )
        )
    return records


def save_world_scene(scene: "Scene") -> None:
    """Write `scene` into its world's database (`scene.world_ref`), in one
    transaction: name, state, premise, goal, player, messages and
    scene-local characters. Keys already in the record's `state` that
    `serialize` doesn't produce (scene setup's place and pulled-in lore),
    and local things that aren't characters, are kept."""

    ref: WorldSceneRef = scene.world_ref
    context: WorldSceneContext | None = getattr(scene, "world_context", None)
    world = context.world if context is not None else World.open(Path(ref.world_path))
    try:
        store = world.scenes()
        record = store.get(ref.scene_id)
        if record is None:
            raise KeyError(f"no such scene: {ref.scene_id}")

        serialized = scene.serialize
        state = dict(record.state)
        state.update(
            _json_safe({k: v for k, v in serialized.items() if k not in _NOT_IN_STATE})
        )
        characters, local_things = _character_entries(scene)
        state["characters"] = characters

        player = scene.get_player_character()
        goal = context.record.goal if context is not None else record.goal

        store.save(
            ref.scene_id,
            fields={
                "name": scene.name or record.name,
                "state": state,
                "premise": scene.description or "",
                "goal": goal,
                "player_thing_id": (
                    player.world_thing_id if player is not None else None
                ),
            },
            messages=_message_records(scene),
            local_things=local_things,
            local_kinds={LOCAL_CHARACTER_KIND},
        )

        if context is not None:
            context.record = store.get(ref.scene_id)
        log.info("save_world_scene", scene_id=ref.scene_id, messages=len(scene.history))
    finally:
        if context is None:
            world.close()


# --- loading ----------------------------------------------------------------


def _character_data(
    world: World,
    record: SceneRecord,
    local_things: list[dict[str, object]],
    at,
) -> tuple[dict[str, dict], list[str]]:
    """`character_data` (as dicts, the way a scene file has them) and the
    active character names, from `state["characters"]`; scene-local
    characters it doesn't mention come back inactive."""

    local = {
        thing["local_id"]: thing
        for thing in local_things
        if thing["kind"] == LOCAL_CHARACTER_KIND
    }
    character_data: dict[str, dict] = {}
    active: list[str] = []

    def add(data: dict, is_active: bool) -> None:
        name = data["name"]
        character_data[name] = data
        if is_active and name not in active:
            active.append(name)

    for entry in record.state.get("characters") or []:
        is_active = bool(entry.get("active", True))
        thing_id = entry.get("thing_id")
        if thing_id:
            try:
                built: Character = character_from_world(
                    world, thing_id, at, is_player=thing_id == record.player_thing_id
                )
            except KeyError:
                log.warning("world scene character not in the world", entry=entry)
                continue
            add({**built.model_dump(), **(entry.get("scene_fields") or {})}, is_active)
            continue

        local_id = entry.get("local_id")
        thing = local.pop(local_id, None)
        if thing is None:
            log.warning("world scene character not found", entry=entry)
            continue
        add({**thing["data"], "world_local_id": local_id}, is_active)

    for local_id, thing in local.items():
        add({**thing["data"], "world_local_id": local_id}, False)

    return character_data, active


def scene_data_from_world(world: World, record: SceneRecord) -> dict:
    """The scene data `load_scene_from_data` takes, for a world scene. The
    characters are built at the scene's date as of its last message."""

    store = world.scenes()
    messages = store.messages(record.id)
    ts = messages[-1].elapsed if messages else "PT0S"

    history = []
    for message in messages:
        data = dict(message.data)
        data.setdefault("typ", message.kind)
        data["world_id"] = message.id
        history.append(data)

    character_data, active = _character_data(
        world, record, store.local_things(record.id), scene_date(record, ts)
    )

    scene_data = {k: v for k, v in record.state.items() if k != "characters"}
    scene_data.update(
        name=record.name,
        description=record.premise,
        history=history,
        character_data=character_data,
        active_characters=active,
    )
    scene_data.setdefault("archived_history", [])
    return scene_data


def attach_world_context(scene: "Scene", world: World, record: SceneRecord) -> None:
    scene.world_context = WorldSceneContext(world=world, record=record)
    connect(scene)


def close_world_scene(scene: "Scene | None") -> None:
    """Close the world connection a loaded world scene holds open (on
    `scene.world_context`), when the scene is replaced or unloaded. Does
    nothing for any other scene."""

    context: WorldSceneContext | None = getattr(scene, "world_context", None)
    if context is not None:
        context.world.close()
