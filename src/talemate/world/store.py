"""The world store: open/create/list a world, and write to it by revision.

A world is a folder holding a SQLite database (`world.sqlite`) plus an
`assets/` and `index/` folder. Nothing in the database is ever updated in
place: a row is added at the revision that introduced it (`rev_added`) and,
later, retired at the revision that superseded or removed it
(`rev_removed`). `World.revision()` opens one SQLite transaction per
revision and hands back a `Revision` whose methods make those additions and
retirements; leaving the `with` block normally commits it, an exception
rolls back everything the revision did, including the revision row itself.
"""

import functools
import json
import sqlite3
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import structlog
from pydantic import BaseModel

from talemate.path import WORLDS_DIR

from . import schema
from .calendar import Calendar
from .dates import Precision, WorldDate
from .kinds import KindSpec, get_kind, validate_field
from .refs import parse_refs
from .view import WorldView

if TYPE_CHECKING:
    from .timeline import TimelineEntry
    from .undo import UndoReport

log = structlog.get_logger("talemate.world.store")

DB_FILENAME = "world.sqlite"

# sentinel for correct_fact()'s keyword args, so that passing `None`
# explicitly (meaning "make it open") can be told apart from "unspecified,
# keep the current value"
_UNSET = object()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _date_parts(date: WorldDate | None) -> tuple[int | None, str | None]:
    if date is None:
        return None, None
    return date.instant, date.precision.value


def _decode_date(instant: int | None, precision: str | None) -> WorldDate | None:
    if instant is None:
        return None
    return WorldDate(instant=instant, precision=Precision(precision))


def _kind_for(name: str) -> KindSpec:
    """Look up a kind by name, treating an unknown name as a validation
    error rather than a missing-thing error."""

    try:
        return get_kind(name)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc


def _encode_value(kind_spec: KindSpec, field: str, value: object) -> str:
    spec = next(f for f in kind_spec.fields if f.name == field)
    if spec.type == "date":
        date = value if isinstance(value, WorldDate) else WorldDate(**value)
        return date.model_dump_json()
    return json.dumps(value)


def _require_open(method: Callable) -> Callable:
    """Reject a call on a `Revision` whose transaction has already ended
    (committed or rolled back), since a write afterwards would either
    autocommit outside that transaction or hit an already-closed
    connection."""

    @functools.wraps(method)
    def wrapper(self: "Revision", *args, **kwargs):
        if self._closed:
            raise RuntimeError(
                "this revision has already ended; open a new one with World.revision()"
            )
        return method(self, *args, **kwargs)

    return wrapper


class Source(BaseModel):
    kind: Literal["manual", "scene", "undo"]
    scene_id: str | None = None
    branch_id: str | None = None
    message_id: str | None = None
    note: str = ""

    @classmethod
    def manual(cls, note: str = "") -> "Source":
        return cls(kind="manual", note=note)

    @classmethod
    def scene(cls, scene_id: str, branch_id: str, message_id: str) -> "Source":
        return cls(
            kind="scene",
            scene_id=scene_id,
            branch_id=branch_id,
            message_id=message_id,
        )


def _source_from_revision_row(row: sqlite3.Row) -> Source:
    return Source(
        kind=row["source_kind"],
        scene_id=row["scene_id"],
        branch_id=row["branch_id"],
        message_id=row["message_id"],
        note=row["note"],
    )


class RevisionInfo(BaseModel):
    rev: int
    source: Source
    created_at: str


class WorldInfo(BaseModel):
    id: str
    name: str
    path: Path
    head_rev: int


class Revision:
    """A single SQLite transaction's worth of writes. Every method checks
    the target thing or fact exists and isn't removed (`KeyError`), and
    validates the write against its kind spec (`ValueError`)."""

    def __init__(self, rev: int, conn: sqlite3.Connection):
        self.rev = rev
        self._conn = conn
        self._closed = False

    def _require_thing(self, thing_id: str) -> str:
        """Return the thing's kind name, raising `KeyError` if it's unknown
        or already removed."""

        row = self._conn.execute(
            "SELECT kind FROM things WHERE id = ? "
            "AND rev_added <= ? AND (rev_removed IS NULL OR rev_removed > ?)",
            (thing_id, self.rev, self.rev),
        ).fetchone()
        if row is None:
            raise KeyError(f"no such thing: {thing_id}")
        return row[0]

    def _thing_kind(self, thing_id: str) -> str:
        """Return a thing's kind name regardless of removal, raising
        `KeyError` only if the id was never a thing."""

        row = self._conn.execute(
            "SELECT kind FROM things WHERE id = ? ORDER BY row_id DESC LIMIT 1",
            (thing_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"no such thing: {thing_id}")
        return row[0]

    def _check_refs(self, text: str) -> None:
        for ref_id in parse_refs(text):
            row = self._conn.execute(
                "SELECT 1 FROM things WHERE id = ?", (ref_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"fact references unknown thing: {ref_id}")

    def _check_span(
        self, valid_from: WorldDate | None, valid_until: WorldDate | None
    ) -> None:
        if (
            valid_from is not None
            and valid_until is not None
            and valid_until <= valid_from
        ):
            raise ValueError("valid_until must be after valid_from")

    def _write_fact_refs(self, row_id: int, text: str) -> None:
        refs = parse_refs(text)
        if refs:
            self._conn.executemany(
                "INSERT INTO fact_refs (row_id, thing_id) VALUES (?, ?)",
                [(row_id, ref_id) for ref_id in refs],
            )

    def _retire_field_value(
        self, thing_id: str, field: str, from_instant: int | None
    ) -> bool:
        """Retire the live `field_values` row for `thing_id`/`field` whose
        `valid_from` matches (NULL counts as equal to NULL). Returns whether
        a row was retired."""

        cur = self._conn.execute(
            "UPDATE field_values SET rev_removed = ? "
            "WHERE thing_id = ? AND field = ? AND rev_removed IS NULL "
            "AND ((valid_from IS NULL AND ? IS NULL) OR valid_from = ?)",
            (self.rev, thing_id, field, from_instant, from_instant),
        )
        return cur.rowcount > 0

    def _live_fact(self, fact_id: str) -> sqlite3.Row:
        row = self._conn.execute(
            "SELECT * FROM facts WHERE fact_id = ? AND rev_removed IS NULL",
            (fact_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"no such fact: {fact_id}")
        return row

    @_require_open
    def create_thing(
        self,
        kind: str,
        fields: dict[str, object] | None = None,
        *,
        valid_from: WorldDate | None = None,
    ) -> str:
        """Create a thing of `kind`, applying `fields` through `set_field`.
        Returns the new thing id."""

        _kind_for(kind)
        thing_id = uuid.uuid4().hex
        self._conn.execute(
            "INSERT INTO things (id, kind, rev_added) VALUES (?, ?, ?)",
            (thing_id, kind, self.rev),
        )
        for field, value in (fields or {}).items():
            self.set_field(thing_id, field, value, valid_from)
        return thing_id

    @_require_open
    def set_field(
        self,
        thing_id: str,
        field: str,
        value: object,
        valid_from: WorldDate | None,
    ) -> None:
        """Add a field value at `valid_from`. If a live value of that field
        already has the same `valid_from`, it's retired first (a
        correction)."""

        kind = self._require_thing(thing_id)
        kind_spec = get_kind(kind)
        validate_field(kind_spec, field, value)

        value_json = _encode_value(kind_spec, field, value)
        from_instant, from_precision = _date_parts(valid_from)

        self._retire_field_value(thing_id, field, from_instant)

        self._conn.execute(
            "INSERT INTO field_values "
            "(thing_id, field, value_json, valid_from, from_precision, rev_added) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (thing_id, field, value_json, from_instant, from_precision, self.rev),
        )

    @_require_open
    def remove_field_value(
        self, thing_id: str, field: str, valid_from: WorldDate | None
    ) -> None:
        kind = self._require_thing(thing_id)
        kind_spec = get_kind(kind)
        if field not in {spec.name for spec in kind_spec.fields}:
            raise ValueError(f"{kind!r} has no field {field!r}")

        from_instant, _ = _date_parts(valid_from)
        if not self._retire_field_value(thing_id, field, from_instant):
            raise KeyError(f"no live value for {field!r} at that date")

    @_require_open
    def add_fact(
        self,
        thing_id: str,
        category: str,
        text: str,
        valid_from: WorldDate | None = None,
        valid_until: WorldDate | None = None,
        origin: dict | None = None,
    ) -> str:
        """Add a fact version for `thing_id`. Returns the new `fact_id`."""

        kind = self._require_thing(thing_id)
        kind_spec = get_kind(kind)
        if category not in kind_spec.categories:
            raise ValueError(f"{kind!r} has no fact category {category!r}")

        self._check_span(valid_from, valid_until)
        self._check_refs(text)

        fact_id = uuid.uuid4().hex
        from_instant, from_precision = _date_parts(valid_from)
        until_instant, until_precision = _date_parts(valid_until)
        origin_json = json.dumps(origin) if origin is not None else None

        cur = self._conn.execute(
            "INSERT INTO facts "
            "(fact_id, thing_id, category, text, valid_from, from_precision, "
            " valid_until, until_precision, origin_json, rev_added) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                fact_id,
                thing_id,
                category,
                text,
                from_instant,
                from_precision,
                until_instant,
                until_precision,
                origin_json,
                self.rev,
            ),
        )
        self._write_fact_refs(cur.lastrowid, text)
        return fact_id

    @_require_open
    def correct_fact(
        self,
        fact_id: str,
        *,
        text: str | None = None,
        category: str | None = None,
        valid_from: object = _UNSET,
        valid_until: object = _UNSET,
    ) -> None:
        """Retire the live version of `fact_id` and add a new version with
        the same `fact_id`, copying over any part left unspecified. `text`
        and `category` are never legitimately `None`, so `None` there means
        "unspecified"; `valid_from`/`valid_until` use a sentinel instead,
        since `None` is a legitimate value for them (an open end)."""

        live = self._live_fact(fact_id)

        new_text = live["text"] if text is None else text
        new_category = live["category"] if category is None else category
        new_from = (
            _decode_date(live["valid_from"], live["from_precision"])
            if valid_from is _UNSET
            else valid_from
        )
        new_until = (
            _decode_date(live["valid_until"], live["until_precision"])
            if valid_until is _UNSET
            else valid_until
        )

        kind = self._thing_kind(live["thing_id"])
        kind_spec = get_kind(kind)
        if new_category not in kind_spec.categories:
            raise ValueError(f"{kind!r} has no fact category {new_category!r}")

        self._check_span(new_from, new_until)
        self._check_refs(new_text)

        self._conn.execute(
            "UPDATE facts SET rev_removed = ? WHERE row_id = ?",
            (self.rev, live["row_id"]),
        )

        from_instant, from_precision = _date_parts(new_from)
        until_instant, until_precision = _date_parts(new_until)

        cur = self._conn.execute(
            "INSERT INTO facts "
            "(fact_id, thing_id, category, text, valid_from, from_precision, "
            " valid_until, until_precision, origin_json, rev_added) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                fact_id,
                live["thing_id"],
                new_category,
                new_text,
                from_instant,
                from_precision,
                until_instant,
                until_precision,
                live["origin_json"],
                self.rev,
            ),
        )
        self._write_fact_refs(cur.lastrowid, new_text)

    @_require_open
    def end_fact(self, fact_id: str, until: WorldDate) -> None:
        self.correct_fact(fact_id, valid_until=until)

    @_require_open
    def remove_fact(self, fact_id: str) -> None:
        live = self._live_fact(fact_id)
        self._conn.execute(
            "UPDATE facts SET rev_removed = ? WHERE row_id = ?",
            (self.rev, live["row_id"]),
        )

    @_require_open
    def remove_thing(self, thing_id: str) -> None:
        """Remove a thing, also retiring its live field values and facts."""

        self._require_thing(thing_id)
        self._conn.execute(
            "UPDATE things SET rev_removed = ? WHERE id = ? AND rev_removed IS NULL",
            (self.rev, thing_id),
        )
        self._conn.execute(
            "UPDATE field_values SET rev_removed = ? "
            "WHERE thing_id = ? AND rev_removed IS NULL",
            (self.rev, thing_id),
        )
        self._conn.execute(
            "UPDATE facts SET rev_removed = ? "
            "WHERE thing_id = ? AND rev_removed IS NULL",
            (self.rev, thing_id),
        )


class World:
    """A world's SQLite database, plus its `assets/` and `index/` folders."""

    def __init__(self, path: Path, conn: sqlite3.Connection):
        self._path = path
        self._conn = conn

    @staticmethod
    def _connect(db_path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @classmethod
    def create(
        cls,
        name: str,
        root: Path = WORLDS_DIR,
        calendar: Calendar | None = None,
    ) -> "World":
        world_id = uuid.uuid4().hex
        path = Path(root) / world_id
        path.mkdir(parents=True)
        (path / "assets").mkdir()
        (path / "index").mkdir()

        conn = cls._connect(path / DB_FILENAME)
        schema.apply(conn)

        calendar = calendar or Calendar()
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.executemany(
                "INSERT INTO meta (key, value) VALUES (?, ?)",
                [
                    ("id", world_id),
                    ("name", name),
                    ("calendar", calendar.model_dump_json()),
                    ("created_at", _now()),
                ],
            )
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")

        log.info("world.create", id=world_id, name=name, path=str(path))
        return cls(path, conn)

    @classmethod
    def open(cls, path: Path) -> "World":
        path = Path(path)
        db_path = path / DB_FILENAME
        if not db_path.exists():
            raise FileNotFoundError(f"no world database at {db_path}")

        conn = cls._connect(db_path)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > schema.SCHEMA_VERSION:
            conn.close()
            raise ValueError(
                f"world schema version {version} is newer than supported "
                f"version {schema.SCHEMA_VERSION}"
            )
        schema.apply(conn)
        return cls(path, conn)

    @classmethod
    def list(cls, root: Path = WORLDS_DIR) -> list[WorldInfo]:
        root = Path(root)
        if not root.exists():
            return []

        infos = []
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or not (entry / DB_FILENAME).exists():
                continue
            world = cls.open(entry)
            try:
                infos.append(
                    WorldInfo(
                        id=world.id,
                        name=world.name,
                        path=world.path,
                        head_rev=world.head_rev(),
                    )
                )
            finally:
                world.close()
        return infos

    def _meta(self, key: str) -> str:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            raise KeyError(key)
        return row[0]

    def _set_meta(self, key: str, value: str) -> None:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")

    @property
    def id(self) -> str:
        return self._meta("id")

    @property
    def name(self) -> str:
        return self._meta("name")

    @property
    def path(self) -> Path:
        return self._path

    @property
    def calendar(self) -> Calendar:
        return Calendar.model_validate_json(self._meta("calendar"))

    def set_calendar(self, calendar: Calendar) -> None:
        self._set_meta("calendar", calendar.model_dump_json())

    def head_rev(self) -> int:
        row = self._conn.execute("SELECT MAX(rev) FROM revisions").fetchone()
        return row[0] or 0

    def view(self, at: WorldDate | None = None, rev: int | None = None) -> WorldView:
        """A snapshot of the world at `(at, rev)`. `at=None` means the
        latest telling; `rev=None` is resolved to `head_rev()` now, so the
        view stays pinned even as later revisions are written."""

        return WorldView(self._conn, at, rev if rev is not None else self.head_rev())

    def timeline(self, thing_id: str, rev: int | None = None) -> "list[TimelineEntry]":
        """Every field value and fact start/end live for `thing_id` at
        `rev`, in story-time order. `rev=None` means `head_rev()`. Raises
        `KeyError` if the thing doesn't exist at `rev`."""

        from .timeline import build_timeline

        return build_timeline(
            self._conn, thing_id, rev if rev is not None else self.head_rev()
        )

    def _live_fact_rows(self, rev: int | None = None) -> "list[sqlite3.Row]":
        """Every fact row live at `rev` on the source clock, across every
        story date -- unlike `view()`, this ignores `valid_from`/
        `valid_until` entirely, since the derived search index (`index.py`)
        needs ended facts too. `rev=None` means `head_rev()`."""

        from .index import index_rows

        return index_rows(self._conn, rev if rev is not None else self.head_rev())

    def revisions(
        self,
        *,
        scene_id: str | None = None,
        branch_id: str | None = None,
        message_id: str | None = None,
    ) -> "list[RevisionInfo]":
        """Every revision matching all the given filters, oldest first. This
        is how a branch's or message's contribution is found, e.g. to pass
        to `undo`."""

        clauses = []
        params = []
        for column, value in (
            ("scene_id", scene_id),
            ("branch_id", branch_id),
            ("message_id", message_id),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        rows = self._conn.execute(
            f"SELECT * FROM revisions {where} ORDER BY rev", params
        ).fetchall()
        return [
            RevisionInfo(
                rev=row["rev"],
                source=_source_from_revision_row(row),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def undo(self, revs: "list[int]", note: str = "") -> "UndoReport":
        """Revert what `revs` did, in one new revision with source kind
        `undo`. Rows changed again by a later revision are left alone and
        reported as conflicts. If nothing can be reverted, no revision is
        written and the report's `undo_rev` is `None`."""

        from .undo import undo_revisions

        return undo_revisions(
            self._conn,
            revs,
            lambda: self.revision(Source(kind="undo", note=note)),
        )

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def revision(self, source: Source) -> Iterator[Revision]:
        """One SQLite transaction per revision. Leaving the block normally
        commits it; any exception -- including a `BaseException` such as
        `asyncio.CancelledError` or `KeyboardInterrupt` -- rolls back
        everything, including the revision row. Either way, the `Revision`
        handle is closed on the way out, so it can't be used to write
        outside its own transaction."""

        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        current = None
        try:
            cursor = conn.execute(
                "INSERT INTO revisions "
                "(source_kind, scene_id, branch_id, message_id, note, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    source.kind,
                    source.scene_id,
                    source.branch_id,
                    source.message_id,
                    source.note,
                    _now(),
                ),
            )
            current = Revision(cursor.lastrowid, conn)
            yield current
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")
        finally:
            if current is not None:
                current._closed = True
