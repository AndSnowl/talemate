"""The prose cache: rendered text kept for a thing's sections, valid for as
long as nothing changes within the "stretch" of story time it covers.

A stretch is the span between two consecutive changes to a thing -- any
field value or fact start/end, as `World.timeline` reports them. Like
`scenes.py`, this isn't world data: the cache carries no `rev_added`/
`rev_removed` and `ProseCache` writes it in plain transactions, not through
`World.revision`. `rev` here is just `World.head_rev()` at the time an entry
was cached, used only to tell whether it's gone stale.

`TimelineSource` is a `Protocol`, not `World` itself: this module only needs
a thing's timeline and the current head revision, and spelling that
structurally keeps it from importing `store.py` (which, going the other
way, imports this module -- lazily, inside `World.prose()` -- the same way
`store.py` avoids importing `index.py` at the top level).
"""

import sqlite3
from collections.abc import Callable
from typing import Protocol

import structlog
from pydantic import BaseModel

from .dates import Precision, WorldDate
from .timeline import TimelineEntry

log = structlog.get_logger("talemate.world.prose")

# an instant past the proleptic-Gregorian range (years 1-9999), used as
# "+infinity" for at=None, mirroring view.py's _FAR_FUTURE
_FAR_FUTURE = 10**15


class TimelineSource(Protocol):
    def timeline(
        self, thing_id: str, rev: int | None = None
    ) -> list[TimelineEntry]: ...

    def head_rev(self) -> int: ...


class CachedProse(BaseModel):
    text: str
    stretch_start: WorldDate | None
    stretch_end: WorldDate | None
    rev: int
    edited: bool


def _decode_instant(instant: int | None) -> WorldDate | None:
    """`prose_cache` stores a stretch boundary as a bare instant, with no
    precision column -- there's nothing finer than seconds to ask for once
    a stretch is cached, so `EXACT` is as good a precision as any."""

    if instant is None:
        return None
    return WorldDate(instant=instant, precision=Precision.EXACT)


def _boundary_dates(entries: list[TimelineEntry]) -> list[WorldDate]:
    """The distinct dates `entries` change at, ascending. A `None` date (an
    "always" field or fact) contributes no boundary of its own."""

    by_instant: dict[int, WorldDate] = {}
    for entry in entries:
        if entry.date is not None:
            by_instant[entry.date.instant] = entry.date
    return [by_instant[instant] for instant in sorted(by_instant)]


def stretches(
    view_factory: Callable[[], TimelineSource], thing_id: str
) -> list[tuple[WorldDate | None, WorldDate | None]]:
    """The stretches `thing_id` has been through, as `(start, end)` pairs:
    the boundaries between consecutive changes, per `World.timeline`. The
    first stretch's start is `None` (always); the last one's end is `None`
    (open, "now")."""

    source = view_factory()
    dates = _boundary_dates(source.timeline(thing_id))
    bounds: list[WorldDate | None] = [None, *dates, None]
    return list(zip(bounds[:-1], bounds[1:]))


def _in_stretch(
    date: WorldDate | None,
    stretch_start: WorldDate | None,
    stretch_end: WorldDate | None,
) -> bool:
    """Whether a timeline entry's date falls in `[stretch_start,
    stretch_end)`. A `None` date (an "always" change) is always in, since it
    affects every stretch's rendering."""

    if date is None:
        return True
    if stretch_start is not None and date.instant < stretch_start.instant:
        return False
    if stretch_end is not None and date.instant >= stretch_end.instant:
        return False
    return True


def _newest_rev_in_stretch(
    entries: list[TimelineEntry],
    stretch_start: WorldDate | None,
    stretch_end: WorldDate | None,
) -> int:
    revs = [
        entry.source_rev
        for entry in entries
        if _in_stretch(entry.date, stretch_start, stretch_end)
    ]
    return max(revs, default=0)


class ProseCache:
    """Cached prose, keyed by thing/section/stretch, made through
    `World.prose()`. Every write is its own plain transaction."""

    def __init__(
        self, conn: sqlite3.Connection, view_factory: Callable[[], TimelineSource]
    ) -> None:
        self._conn = conn
        self._view_factory = view_factory

    def get(
        self, thing_id: str, section: str, at: WorldDate | None
    ) -> CachedProse | None:
        """The cached entry for the stretch containing `at` (`None` means
        the open, "now" stretch), or `None` if there isn't one."""

        at_instant = at.instant if at is not None else _FAR_FUTURE
        row = self._conn.execute(
            "SELECT stretch_start, stretch_end, rev, text, edited FROM prose_cache "
            "WHERE thing_id = ? AND section = ? "
            "AND (stretch_start IS NULL OR stretch_start <= ?) "
            "AND (stretch_end IS NULL OR stretch_end > ?)",
            (thing_id, section, at_instant, at_instant),
        ).fetchone()
        if row is None:
            return None
        return CachedProse(
            text=row["text"],
            stretch_start=_decode_instant(row["stretch_start"]),
            stretch_end=_decode_instant(row["stretch_end"]),
            rev=row["rev"],
            edited=bool(row["edited"]),
        )

    def put(
        self,
        thing_id: str,
        section: str,
        stretch_start: WorldDate | None,
        stretch_end: WorldDate | None,
        text: str,
        *,
        edited: bool = False,
    ) -> None:
        """Cache `text` for the stretch `[stretch_start, stretch_end)`,
        replacing whatever was cached for that stretch before."""

        rev = self._view_factory().head_rev()
        start_instant = stretch_start.instant if stretch_start is not None else None
        end_instant = stretch_end.instant if stretch_end is not None else None

        self._conn.execute("BEGIN IMMEDIATE")
        try:
            # `stretch_start` can be NULL ("always"), and SQLite's primary
            # key doesn't dedupe NULLs against each other the way a NOT
            # NULL key would, so the old row (if any) is found and replaced
            # by hand instead of relying on `INSERT ... ON CONFLICT`.
            self._conn.execute(
                "DELETE FROM prose_cache WHERE thing_id = ? AND section = ? "
                "AND ((stretch_start IS NULL AND ? IS NULL) OR stretch_start = ?)",
                (thing_id, section, start_instant, start_instant),
            )
            self._conn.execute(
                "INSERT INTO prose_cache "
                "(thing_id, section, stretch_start, stretch_end, rev, text, edited) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    thing_id,
                    section,
                    start_instant,
                    end_instant,
                    rev,
                    text,
                    int(edited),
                ),
            )
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")

    def stale(self, thing_id: str, section: str, at: WorldDate | None) -> bool:
        """`True` if there's no cached entry for the stretch containing
        `at`, or its `rev` predates the newest timeline change inside that
        stretch."""

        cached = self.get(thing_id, section, at)
        if cached is None:
            return True

        entries = self._view_factory().timeline(thing_id)
        newest = _newest_rev_in_stretch(
            entries, cached.stretch_start, cached.stretch_end
        )
        return cached.rev < newest
