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

# `builtins` is used below to spell `list[...]` in annotations that come
# after `World.list` in this class: an unqualified `list` there would bind
# to that classmethod instead of the builtin.
import builtins
import functools
import json
import sqlite3
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

import structlog
from pydantic import BaseModel, ValidationError

from talemate.path import WORLDS_DIR

from . import schema
from .calendar import Calendar
from .dates import Precision, WorldDate
from .kinds import (
    KindSpec,
    get_kind,
    moved_category,
    normalise_field,
    normalise_tag,
    validate_field,
)
from .curation import CurationSettings
from .refs import parse_refs
from .filing import check_filings, stored_filings_value
from .view import FactState, WorldView, _fact_state_from_row

if TYPE_CHECKING:
    from .prose import ProseCache
    from .scenes import SceneStore
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
        date = (
            value
            if isinstance(value, WorldDate)
            # a plain {"instant": ..., "precision": ...} dict, passed through
            # as-is; pydantic validates it at construction, same as any other
            # caller-supplied value
            else WorldDate(**cast("dict[str, object]", value))  # type: ignore[arg-type]
        )
        return date.model_dump_json()
    return json.dumps(value)


def _require_open(method: Callable[..., Any]) -> Callable[..., Any]:
    """Reject a call on a `Revision` whose transaction has already ended
    (committed or rolled back), since a write afterwards would either
    autocommit outside that transaction or hit an already-closed
    connection."""

    @functools.wraps(method)
    def wrapper(self: "Revision", *args: Any, **kwargs: Any) -> Any:
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
    # for an undo revision, the revisions it reversed; `[]` otherwise
    reverts: list[int] = []


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
        return cast(str, row[0])

    def _thing_kind(self, thing_id: str) -> str:
        """Return a thing's kind name regardless of removal, raising
        `KeyError` only if the id was never a thing."""

        row = self._conn.execute(
            "SELECT kind FROM things WHERE id = ? ORDER BY row_id DESC LIMIT 1",
            (thing_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"no such thing: {thing_id}")
        return cast(str, row[0])

    def _check_refs(self, text: str) -> None:
        """Raise `ValueError` unless every thing `text` references is live
        at this revision (the same test as `_require_thing`)."""

        for ref_id in parse_refs(text):
            try:
                self._require_thing(ref_id)
            except KeyError:
                raise ValueError(
                    f"fact references unknown or removed thing: {ref_id}"
                ) from None

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

    def _check_overrides(self, overrides: list[str]) -> None:
        """Raise `ValueError` unless every id in `overrides` is a fact live
        at this revision."""

        for fact_id in overrides:
            try:
                self._live_fact(fact_id)
            except KeyError:
                raise ValueError(
                    f"overrides an unknown or removed fact: {fact_id}"
                ) from None

    def _write_fact_overrides(self, row_id: int, overrides: list[str]) -> None:
        if overrides:
            self._conn.executemany(
                "INSERT INTO fact_overrides (row_id, fact_id) VALUES (?, ?)",
                [(row_id, fact_id) for fact_id in overrides],
            )

    def _live_fact_overrides(self, row_id: int) -> list[str]:
        return [
            row[0]
            for row in self._conn.execute(
                "SELECT fact_id FROM fact_overrides WHERE row_id = ?", (row_id,)
            )
        ]

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
        return cast(sqlite3.Row, row)

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
        correction). A `tag` is normalised first (`kinds.normalise_field`);
        `filings` are also checked against the world
        (`filing.check_filings`)."""

        kind = self._require_thing(thing_id)
        kind_spec = get_kind(kind)
        value = normalise_field(field, value)
        validate_field(kind_spec, field, value)
        if field == "filings":
            # what needs the world: no filing into itself, no cycle, a
            # `within` that sits in its target; read at this revision
            errors = check_filings(
                WorldView(self._conn, None, self.rev),
                thing_id,
                cast("list[object]", value),
            )
            if errors:
                raise ValueError("; ".join(errors))
            # the full exact shape, a blank role as None
            value = stored_filings_value(cast("list[object]", value))

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
    def retag(self, old: str, new: str) -> list[str]:
        """Make every `tag` value `old` (as normalised) `new`, at its own
        date, and return the things changed, in id order. A live thing's
        values are corrected as `set_field` corrects one. A removed
        thing's values -- those its removal retired -- get a new value too,
        so undoing the removal brings it back with the new tag (the undo
        finds the slot written after the removal and leaves it alone)."""

        old_tag, new_tag = normalise_tag(old), normalise_tag(new)
        rows = self._conn.execute(
            "SELECT fv.thing_id, fv.value_json, fv.valid_from, fv.from_precision, "
            "fv.rev_removed, "
            "(SELECT t.rev_removed FROM things t WHERE t.id = fv.thing_id "
            " ORDER BY t.row_id DESC LIMIT 1) AS thing_removed "
            "FROM field_values fv WHERE fv.field = 'tag' "
            "AND (fv.rev_removed IS NULL OR fv.rev_removed = "
            " (SELECT t.rev_removed FROM things t WHERE t.id = fv.thing_id "
            "  ORDER BY t.row_id DESC LIMIT 1)) "
            "ORDER BY fv.thing_id, fv.row_id",
        ).fetchall()
        changed: list[str] = []
        for row in rows:
            value = json.loads(row["value_json"])
            if not isinstance(value, str) or normalise_tag(value) != old_tag:
                continue
            thing_id = cast(str, row["thing_id"])
            kind_spec = get_kind(self._thing_kind(thing_id))
            if row["thing_removed"] is None:
                if row["rev_removed"] is not None:
                    continue
                self.set_field(
                    thing_id,
                    "tag",
                    new_tag,
                    _decode_date(row["valid_from"], row["from_precision"]),
                )
            else:
                self._conn.execute(
                    "INSERT INTO field_values (thing_id, field, value_json, "
                    "valid_from, from_precision, rev_added) "
                    "VALUES (?, 'tag', ?, ?, ?, ?)",
                    (
                        thing_id,
                        _encode_value(kind_spec, "tag", new_tag),
                        row["valid_from"],
                        row["from_precision"],
                        self.rev,
                    ),
                )
            if thing_id not in changed:
                changed.append(thing_id)
        return sorted(changed)

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
        origin: dict[str, object] | None = None,
        overrides: list[str] | None = None,
    ) -> str:
        """Add a fact version for `thing_id`. `overrides` names the facts
        (by stable `fact_id`) this one supersedes; each must be live at
        this revision (`ValueError` otherwise). Returns the new `fact_id`."""

        kind = self._require_thing(thing_id)
        kind_spec = get_kind(kind)
        if category not in kind_spec.categories:
            raise ValueError(f"{kind!r} has no fact category {category!r}")

        self._check_span(valid_from, valid_until)
        self._check_refs(text)
        overrides = overrides or []
        self._check_overrides(overrides)

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
        row_id = cast(int, cur.lastrowid)
        self._write_fact_refs(row_id, text)
        self._write_fact_overrides(row_id, overrides)
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
        overrides: list[str] | None = None,
        origin: object = _UNSET,
    ) -> None:
        """Retire the live version of `fact_id` and add a new version with
        the same `fact_id`, copying over any part left unspecified.
        `origin` (a dict, or `None`) replaces its origin. `text`
        and `category` are never legitimately `None`, so `None` there means
        "unspecified"; `valid_from`/`valid_until` use a sentinel instead,
        since `None` is a legitimate value for them (an open end).
        `overrides` is `None` to copy the live version's override links, or
        a list (possibly empty) to replace them."""

        live = self._live_fact(fact_id)

        new_text = live["text"] if text is None else text
        new_category = live["category"] if category is None else category
        new_from: WorldDate | None = (
            _decode_date(live["valid_from"], live["from_precision"])
            if valid_from is _UNSET
            else cast("WorldDate | None", valid_from)
        )
        new_until: WorldDate | None = (
            _decode_date(live["valid_until"], live["until_precision"])
            if valid_until is _UNSET
            else cast("WorldDate | None", valid_until)
        )
        new_overrides = (
            self._live_fact_overrides(live["row_id"])
            if overrides is None
            else overrides
        )

        owner = live["thing_id"]
        origin_json = (
            live["origin_json"]
            if origin is _UNSET
            else (json.dumps(origin) if origin is not None else None)
        )

        kind = self._thing_kind(owner)
        kind_spec = get_kind(kind)
        if new_category not in kind_spec.categories:
            raise ValueError(f"{kind!r} has no fact category {new_category!r}")

        self._check_span(new_from, new_until)
        self._check_refs(new_text)
        self._check_overrides(new_overrides)

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
                owner,
                new_category,
                new_text,
                from_instant,
                from_precision,
                until_instant,
                until_precision,
                origin_json,
                self.rev,
            ),
        )
        row_id = cast(int, cur.lastrowid)
        self._write_fact_refs(row_id, new_text)
        self._write_fact_overrides(row_id, new_overrides)

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

    def _is_stub(self, thing_id: str) -> bool:
        """Whether the thing has a live `stub` value at any date."""

        return (
            self._conn.execute(
                "SELECT 1 FROM field_values "
                "WHERE thing_id = ? AND field = 'stub' AND rev_removed IS NULL",
                (thing_id,),
            ).fetchone()
            is not None
        )

    def _rekind(self, thing_id: str, kind: str) -> None:
        """Retire the thing's row and add one of `kind` with the same id, so
        undo reverses it like any other write."""

        self._conn.execute(
            "UPDATE things SET rev_removed = ? WHERE id = ? AND rev_removed IS NULL",
            (self.rev, thing_id),
        )
        self._conn.execute(
            "INSERT INTO things (id, kind, rev_added) VALUES (?, ?, ?)",
            (thing_id, kind, self.rev),
        )

    @_require_open
    def change_stub_kind(self, thing_id: str, kind: str) -> None:
        """Give a stub another kind, any kind: its thing row is retired and
        a row of `kind` with the same id is added, so undo reverses it like
        any other write. Its facts are kept by id: one in a category `kind`
        lacks takes the category `kinds.moved_category` gives (a new
        version of the fact, as `correct_fact` writes: a lore `general`
        fact is a character's `background`). Its field
        values are kept, but those of a field `kind` lacks (or has with
        another type) are retired with it -- a stub's place `kind` text,
        say. Raises `ValueError` unless the thing is a stub (a live `stub`
        value at any date)."""

        new_spec = _kind_for(kind)
        old_kind = self._require_thing(thing_id)
        if not self._is_stub(thing_id):
            raise ValueError(f"only a stub's kind can be changed: {thing_id}")
        if kind == old_kind:
            return

        old_types = {spec.name: spec.type for spec in get_kind(old_kind).fields}
        new_types = {spec.name: spec.type for spec in new_spec.fields}
        self._conn.execute(
            "UPDATE field_values SET rev_removed = ? "
            "WHERE thing_id = ? AND rev_removed IS NULL "
            "AND field IN (SELECT value FROM json_each(?))",
            (
                self.rev,
                thing_id,
                json.dumps(
                    [
                        field
                        for field, type_ in old_types.items()
                        if new_types.get(field) != type_
                    ]
                ),
            ),
        )
        self._rekind(thing_id, kind)
        facts = self._conn.execute(
            "SELECT fact_id, category, valid_from FROM facts "
            "WHERE thing_id = ? AND rev_removed IS NULL",
            (thing_id,),
        ).fetchall()
        for fact_id, category, valid_from in facts:
            if category not in new_spec.categories:
                self.correct_fact(
                    fact_id,
                    category=moved_category(kind, category, valid_from is not None),
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
        return cast(str, row[0])

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

    def curation(self) -> CurationSettings:
        """The world's curation knobs; the defaults until `set_curation`
        is called, or when the stored value can't be read (logged)."""

        try:
            stored = self._meta("curation")
        except KeyError:
            return CurationSettings()
        try:
            return CurationSettings.model_validate_json(stored)
        except ValidationError as exc:
            log.warning("world.curation_unreadable", stored=stored, error=str(exc))
            return CurationSettings()

    def set_curation(self, settings: CurationSettings) -> None:
        self._set_meta("curation", settings.model_dump_json())

    def present(self) -> WorldDate:
        """The world's "present": the in-world date its owner is working
        at when no scene says otherwise (creating things before any scene
        exists, for one). Year 1 until `set_present` is called."""

        try:
            return WorldDate.model_validate_json(self._meta("present"))
        except KeyError:
            return WorldDate.of(1)

    def set_present(self, date: WorldDate) -> None:
        self._set_meta("present", date.model_dump_json())

    def head_rev(self) -> int:
        row = self._conn.execute("SELECT MAX(rev) FROM revisions").fetchone()
        return row[0] or 0

    def view(self, at: WorldDate | None = None, rev: int | None = None) -> WorldView:
        """A snapshot of the world at `(at, rev)`. `at=None` means the
        latest telling; `rev=None` is resolved to `head_rev()` now, so the
        view stays pinned even as later revisions are written."""

        return WorldView(self._conn, at, rev if rev is not None else self.head_rev())

    def live_facts(self, thing_id: str | None = None) -> builtins.list[FactState]:
        """The facts of `thing_id` (of every thing, if `None`) live at the
        head revision, on every story date, ended ones too: what `view()`
        shows on one date at a time. Ordered by creation."""

        rev = self.head_rev()
        rows = self._conn.execute(
            """
            SELECT f.row_id, f.thing_id, f.fact_id, f.category, f.text, f.valid_from,
                   f.from_precision, f.valid_until, f.until_precision, f.rev_added,
                   f.origin_json,
                   (SELECT MIN(f0.row_id) FROM facts f0
                    WHERE f0.fact_id = f.fact_id) AS created
            FROM facts f
            JOIN things t ON t.id = f.thing_id
              AND t.rev_added <= :rev
              AND (t.rev_removed IS NULL OR t.rev_removed > :rev)
            WHERE f.rev_added <= :rev
              AND (f.rev_removed IS NULL OR f.rev_removed > :rev)
              AND (:thing_id IS NULL OR f.thing_id = :thing_id)
            ORDER BY created
            """,
            {"rev": rev, "thing_id": thing_id},
        ).fetchall()
        facts = []
        for row in rows:
            state = _fact_state_from_row(row)
            state.overrides = self._fact_overrides(row["row_id"])
            facts.append(state)
        return facts

    def _fact_overrides(self, row_id: int) -> builtins.list[str]:
        return [
            r[0]
            for r in self._conn.execute(
                "SELECT fact_id FROM fact_overrides WHERE row_id = ? ORDER BY rowid",
                (row_id,),
            )
        ]

    def timeline(
        self, thing_id: str, rev: int | None = None
    ) -> builtins.list["TimelineEntry"]:
        """Every field value and fact start/end live for `thing_id` at
        `rev`, in story-time order. `rev=None` means `head_rev()`. Raises
        `KeyError` if the thing doesn't exist at `rev`."""

        from .timeline import build_timeline

        return build_timeline(
            self._conn, thing_id, rev if rev is not None else self.head_rev()
        )

    def scenes(self) -> "SceneStore":
        """Scenes, their messages and their scene-local invented things.
        They aren't world things: `SceneStore` writes them in plain
        transactions on this connection, not through `World.revision`."""

        from .scenes import SceneStore

        return SceneStore(self._conn)

    def prose(self) -> "ProseCache":
        """The cached prose for this world's things, kept fresh against
        `timeline()`. Like `scenes()`, written in plain transactions, not
        through `World.revision`."""

        from .prose import ProseCache

        return ProseCache(self._conn, lambda: self)

    def _live_fact_rows(self, rev: int | None = None) -> builtins.list[sqlite3.Row]:
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
    ) -> builtins.list[RevisionInfo]:
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
        reverts: dict[int, list[int]] = {}
        for undo_rev, target_rev in self._conn.execute(
            "SELECT undo_rev, target_rev FROM revision_reverts "
            "ORDER BY undo_rev, target_rev"
        ):
            reverts.setdefault(undo_rev, []).append(target_rev)
        return [
            RevisionInfo(
                rev=row["rev"],
                source=_source_from_revision_row(row),
                created_at=row["created_at"],
                reverts=reverts.get(row["rev"], []),
            )
            for row in rows
        ]

    def undo(self, revs: builtins.list[int], note: str = "") -> "UndoReport":
        """Revert what `revs` did, in one new revision with source kind
        `undo`. Rows changed again by a later revision are left alone and
        reported as conflicts. If nothing can be reverted, no revision is
        written and the report's `undo_rev` is `None`."""

        from .undo import undo_revisions

        return undo_revisions(
            self._conn,
            revs,
            lambda: self._open_revision(Source(kind="undo", note=note)),
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
        outside its own transaction. Raises `ValueError` for an `undo`
        source: only `undo` writes those, since replay (`replay.py`) never
        counts an undo revision's rows as writes."""

        if source.kind == "undo":
            raise ValueError(
                "undo revisions are written by World.undo, not World.revision"
            )
        with self._open_revision(source) as current:
            yield current

    @contextmanager
    def _open_revision(self, source: Source) -> Iterator[Revision]:
        """`revision` without the source check, for `undo` to write its
        own revision through."""

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
            current = Revision(cast(int, cursor.lastrowid), conn)
            yield current
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")
        finally:
            if current is not None:
                current._closed = True
