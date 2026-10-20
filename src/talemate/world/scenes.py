"""Scenes: played-out stretches of story, kept alongside a world but not
part of it.

Unlike `things`, `field_values` and `facts`, the tables here carry no
`rev_added`/`rev_removed`: scenes don't take part in replay or undo, so
`SceneStore` writes them in plain transactions on the world's own
connection, with the same `BaseException`-safe rollback `World` uses for its
own plain writes (`World._set_meta`), not through `World.revision`.
"""

import json
import sqlite3
import uuid
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

import structlog
from pydantic import BaseModel

from .dates import Precision, WorldDate

log = structlog.get_logger("talemate.world.scenes")

# the scene fields `SceneStore.update` is allowed to change, and how each
# maps to a column (`state` is encoded to `state_json`, `start` is split
# into `start_instant`/`start_precision`; everything else is written as-is
# under its own name)
_UPDATABLE_FIELDS = {"name", "start", "premise", "goal", "player_thing_id", "state"}


def scene_end(start: WorldDate, elapsed: str) -> WorldDate:
    """Where a scene that started at `start` got to after `elapsed` (an
    ISO-8601 duration, a message's `elapsed`). When no time passed, the
    start itself, to its own precision: "PT0S" has a time part, and adding
    it would turn a plain date into an exact midnight."""

    end = start.plus(elapsed)
    return start if end.instant == start.instant else end


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SceneRecord(BaseModel):
    id: str
    name: str
    start: WorldDate
    premise: str
    goal: str
    player_thing_id: str | None
    state: dict[str, object]
    created_at: str
    updated_at: str
    continued_from: str | None


class MessageRecord(BaseModel):
    id: str
    seq: int
    kind: str
    data: dict[str, object]
    elapsed: str = "PT0S"


def _scene_from_row(row: sqlite3.Row) -> SceneRecord:
    return SceneRecord(
        id=row["id"],
        name=row["name"],
        start=WorldDate(
            instant=row["start_instant"],
            precision=Precision(row["start_precision"]),
        ),
        premise=row["premise"],
        goal=row["goal"],
        player_thing_id=row["player_thing_id"],
        state=json.loads(row["state_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        continued_from=row["continued_from"],
    )


def _message_from_row(row: sqlite3.Row) -> MessageRecord:
    return MessageRecord(
        id=row["id"],
        seq=row["seq"],
        kind=row["kind"],
        data=json.loads(row["data_json"]),
        elapsed=row["elapsed"],
    )


class SceneStore:
    """Scenes, their messages and their scene-local invented things, made
    through `World.scenes()`. Every write is its own plain transaction."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(
        self,
        name: str,
        start: WorldDate,
        *,
        premise: str = "",
        goal: str = "",
        player_thing_id: str | None = None,
        continued_from: str | None = None,
        state: dict[str, object] | None = None,
    ) -> str:
        """Create a scene starting at `start`, with `state` (default
        empty). Returns the new scene id."""

        scene_id = uuid.uuid4().hex
        now = _now()
        with self._transaction():
            self._conn.execute(
                "INSERT INTO scenes "
                "(id, name, start_instant, start_precision, premise, goal, "
                " player_thing_id, state_json, created_at, updated_at, "
                " continued_from) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    scene_id,
                    name,
                    start.instant,
                    start.precision.value,
                    premise,
                    goal,
                    player_thing_id,
                    json.dumps(state or {}),
                    now,
                    now,
                    continued_from,
                ),
            )
        return scene_id

    def get(self, scene_id: str) -> SceneRecord | None:
        row = self._conn.execute(
            "SELECT * FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()
        return _scene_from_row(row) if row is not None else None

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")

    def _update_row(self, scene_id: str, fields: dict[str, object]) -> None:
        unknown = set(fields) - _UPDATABLE_FIELDS
        if unknown:
            raise ValueError(f"cannot update field(s): {', '.join(sorted(unknown))}")

        assignments = []
        params: list[object] = []
        for field, value in fields.items():
            if field == "state":
                assignments.append("state_json = ?")
                params.append(json.dumps(value))
            elif field == "start":
                if not isinstance(value, WorldDate):
                    raise ValueError(f"start must be a WorldDate, not {value!r}")
                assignments.append("start_instant = ?")
                params.append(value.instant)
                assignments.append("start_precision = ?")
                params.append(value.precision.value)
            else:
                assignments.append(f"{field} = ?")
                params.append(value)
        assignments.append("updated_at = ?")
        params.append(_now())
        params.append(scene_id)

        cur = self._conn.execute(
            f"UPDATE scenes SET {', '.join(assignments)} WHERE id = ?", params
        )
        if cur.rowcount == 0:
            raise KeyError(f"no such scene: {scene_id}")

    def _replace_message_rows(
        self, scene_id: str, messages: list[MessageRecord]
    ) -> None:
        self._conn.execute(
            "DELETE FROM scene_messages WHERE scene_id = ? AND branch_id = 'main'",
            (scene_id,),
        )
        self._conn.executemany(
            "INSERT INTO scene_messages "
            "(id, scene_id, branch_id, seq, kind, data_json, elapsed) "
            "VALUES (?, ?, 'main', ?, ?, ?, ?)",
            [
                (m.id, scene_id, m.seq, m.kind, json.dumps(m.data), m.elapsed)
                for m in messages
            ],
        )

    def _replace_local_rows(
        self,
        scene_id: str,
        things: list[dict[str, object]],
        kinds: Collection[str] | None,
    ) -> None:
        if kinds is None:
            self._conn.execute(
                "DELETE FROM scene_things WHERE scene_id = ?", (scene_id,)
            )
        else:
            stray = {str(thing["kind"]) for thing in things} - set(kinds)
            if stray:
                raise ValueError(
                    f"local thing kind(s) not being replaced: {', '.join(sorted(stray))}"
                )
            self._conn.executemany(
                "DELETE FROM scene_things WHERE scene_id = ? AND kind = ?",
                [(scene_id, kind) for kind in kinds],
            )
        self._conn.executemany(
            "INSERT INTO scene_things (scene_id, local_id, kind, data_json) "
            "VALUES (?, ?, ?, ?)",
            [
                (
                    scene_id,
                    thing["local_id"],
                    thing["kind"],
                    json.dumps(thing.get("data", {})),
                )
                for thing in things
            ],
        )

    def update(self, scene_id: str, **fields: object) -> None:
        """Update one or more of `name`, `start`, `premise`, `goal`,
        `player_thing_id` or `state`, and bump `updated_at`. Moving `start`
        moves every message with it: a message's date is the start plus
        its `elapsed`. Raises
        `ValueError` for any other field, `KeyError` if `scene_id` doesn't
        exist."""

        with self._transaction():
            self._update_row(scene_id, fields)

    def replace_messages(self, scene_id: str, messages: list[MessageRecord]) -> None:
        """Rewrite the `main` branch's messages in one transaction: a bad
        record fails the whole batch and leaves the old messages alone."""

        with self._transaction():
            self._replace_message_rows(scene_id, messages)

    def set_local_things(self, scene_id: str, things: list[dict[str, object]]) -> None:
        """Replace the scene's local, invented things wholesale. Each entry
        is `{"local_id": ..., "kind": ..., "data": {...}}`."""

        with self._transaction():
            self._replace_local_rows(scene_id, things, None)

    def save(
        self,
        scene_id: str,
        *,
        fields: dict[str, object],
        messages: list[MessageRecord],
        local_things: list[dict[str, object]],
        local_kinds: Collection[str],
    ) -> None:
        """Save a played scene in one transaction: `update(**fields)`,
        `replace_messages(messages)`, and replace the scene's local things
        of `local_kinds` with `local_things` -- local things of any other
        kind are kept. Nothing is written if any part fails; a thing in
        `local_things` whose kind isn't in `local_kinds` is a
        `ValueError`."""

        with self._transaction():
            self._update_row(scene_id, fields)
            self._replace_message_rows(scene_id, messages)
            self._replace_local_rows(scene_id, local_things, local_kinds)

    def messages(self, scene_id: str) -> list[MessageRecord]:
        """The `main` branch's messages, in `seq` order."""

        rows = self._conn.execute(
            "SELECT * FROM scene_messages WHERE scene_id = ? AND branch_id = 'main' "
            "ORDER BY seq",
            (scene_id,),
        ).fetchall()
        return [_message_from_row(row) for row in rows]

    def local_things(self, scene_id: str) -> list[dict[str, object]]:
        rows = self._conn.execute(
            "SELECT local_id, kind, data_json FROM scene_things "
            "WHERE scene_id = ? ORDER BY local_id",
            (scene_id,),
        ).fetchall()
        return [
            {
                "local_id": row["local_id"],
                "kind": row["kind"],
                "data": json.loads(row["data_json"]),
            }
            for row in rows
        ]

    def latest_end(self) -> WorldDate | None:
        """The latest `scene_end(start, elapsed)` over every scene's last
        message, or the scene's own `start` if it has none yet. `None` if
        there are no scenes at all."""

        scene_rows = self._conn.execute(
            "SELECT id, start_instant, start_precision FROM scenes"
        ).fetchall()
        if not scene_rows:
            return None

        latest: WorldDate | None = None
        for row in scene_rows:
            start = WorldDate(
                instant=row["start_instant"],
                precision=Precision(row["start_precision"]),
            )
            last = self._conn.execute(
                "SELECT elapsed FROM scene_messages "
                "WHERE scene_id = ? AND branch_id = 'main' "
                "ORDER BY seq DESC LIMIT 1",
                (row["id"],),
            ).fetchone()
            end = scene_end(start, last["elapsed"]) if last is not None else start
            if latest is None or end > latest:
                latest = end
        return latest

    def list(self) -> list[SceneRecord]:
        """Every scene, newest `updated_at` first."""

        rows = self._conn.execute(
            "SELECT * FROM scenes ORDER BY updated_at DESC"
        ).fetchall()
        return [_scene_from_row(row) for row in rows]
