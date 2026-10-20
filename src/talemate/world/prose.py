"""The prose cache: rendered text kept for a thing's sections, valid for as
long as nothing changes within the "stretch" of story time it covers.

A stretch is the span between two consecutive changes to a thing -- any
field value or fact start/end, as `World.timeline` reports them. Like
`scenes.py`, this isn't world data: the cache carries no `rev_added`/
`rev_removed` and `ProseCache` writes it in plain transactions, not through
`World.revision`. `rev` here is the revision an entry was generated from
(`World.head_rev()` at the time it was cached, unless the caller says
otherwise), used only to tell whether it's gone stale: a row visible in the
stretch that was added or retired after `rev` makes the entry stale.

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
# "-infinity", for an open (NULL) stretch start when comparing bounds
_FAR_PAST = -_FAR_FUTURE


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
        the open, "now" stretch), or `None` if there isn't one. `put`
        keeps a thing's stretches from overlapping, but should two rows
        still match, the most specific one wins: the latest start, an open
        (NULL) start last."""

        at_instant = at.instant if at is not None else _FAR_FUTURE
        row = self._conn.execute(
            "SELECT stretch_start, stretch_end, rev, text, edited FROM prose_cache "
            "WHERE thing_id = ? AND section = ? "
            "AND (stretch_start IS NULL OR stretch_start <= ?) "
            "AND (stretch_end IS NULL OR stretch_end > ?) "
            "ORDER BY stretch_start IS NULL, stretch_start DESC LIMIT 1",
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
        rev: int | None = None,
    ) -> None:
        """Cache `text` for the stretch `[stretch_start, stretch_end)`,
        replacing whatever was cached for that stretch before. Cached rows
        of the same thing and section that overlap it are clipped to the
        part outside it (or dropped, when nothing is left): a new dated
        change splits a stretch, and the old text stays right only for the
        part before (or after) the new one. `rev` is the
        revision `text` was generated from; `None` means `head_rev()` now.
        Passing the revision the facts were read at keeps a change written
        while the text was being generated from going unnoticed."""

        if rev is None:
            rev = self._view_factory().head_rev()
        start_instant = stretch_start.instant if stretch_start is not None else None
        end_instant = stretch_end.instant if stretch_end is not None else None

        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._clip_overlaps(thing_id, section, start_instant, end_instant)
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

    def _clip_overlaps(
        self,
        thing_id: str,
        section: str,
        start_instant: int | None,
        end_instant: int | None,
    ) -> None:
        """Cut `[start_instant, end_instant)` out of every cached row of
        `thing_id`'s `section` that overlaps it, inside `put`'s
        transaction. A row covering the whole range is split in two."""

        new_start = start_instant if start_instant is not None else _FAR_PAST
        new_end = end_instant if end_instant is not None else _FAR_FUTURE
        rows = self._conn.execute(
            "SELECT stretch_start, stretch_end, rev, text, edited FROM prose_cache "
            "WHERE thing_id = ? AND section = ? "
            "AND (stretch_start IS NULL OR ? IS NULL OR stretch_start < ?) "
            "AND (stretch_end IS NULL OR ? IS NULL OR stretch_end > ?)",
            (thing_id, section, end_instant, end_instant, start_instant, start_instant),
        ).fetchall()

        for row in rows:
            # `stretch_start` can be NULL ("always"), and SQLite's primary
            # key doesn't dedupe NULLs against each other, so a row is
            # matched by hand rather than by `=`
            self._conn.execute(
                "DELETE FROM prose_cache WHERE thing_id = ? AND section = ? "
                "AND ((stretch_start IS NULL AND ? IS NULL) OR stretch_start = ?)",
                (thing_id, section, row["stretch_start"], row["stretch_start"]),
            )
            old_start = (
                row["stretch_start"] if row["stretch_start"] is not None else _FAR_PAST
            )
            old_end = (
                row["stretch_end"] if row["stretch_end"] is not None else _FAR_FUTURE
            )
            pieces: list[tuple[int | None, int | None]] = []
            if old_start < new_start:
                pieces.append((row["stretch_start"], start_instant))
            if old_end > new_end:
                pieces.append((end_instant, row["stretch_end"]))
            for piece_start, piece_end in pieces:
                self._conn.execute(
                    "INSERT INTO prose_cache "
                    "(thing_id, section, stretch_start, stretch_end, rev, text, "
                    "edited) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        thing_id,
                        section,
                        piece_start,
                        piece_end,
                        row["rev"],
                        row["text"],
                        row["edited"],
                    ),
                )

    def _changed_in_stretch_since(self, thing_id: str, cached: CachedProse) -> bool:
        """Whether a field value or fact of `thing_id` visible somewhere in
        the cached stretch was added, or retired (removed, corrected or
        undone), after `cached.rev`. "Visible in the stretch" means its span
        overlaps the stretch, not just that its start falls inside it: a
        fact that started before the stretch and runs through it is in that
        stretch's prose too. A retired row is gone from the timeline, so the
        timeline check in `stale` can't see it; this catches both."""

        start = (
            cached.stretch_start.instant if cached.stretch_start is not None else None
        )
        end = cached.stretch_end.instant if cached.stretch_end is not None else None
        # a field value has no end of its own here: it's visible from its
        # `valid_from` until superseded, so only its start is checked
        starts_before_end = "(valid_from IS NULL OR ? IS NULL OR valid_from < ?)"
        ends_after_start = "(valid_until IS NULL OR ? IS NULL OR valid_until > ?)"

        fact = self._conn.execute(
            "SELECT 1 FROM facts WHERE thing_id = ? "
            "AND (rev_added > ? OR rev_removed > ?) "
            f"AND {starts_before_end} AND {ends_after_start} LIMIT 1",
            (thing_id, cached.rev, cached.rev, end, end, start, start),
        ).fetchone()
        if fact is not None:
            return True
        value = self._conn.execute(
            "SELECT 1 FROM field_values WHERE thing_id = ? "
            "AND (rev_added > ? OR rev_removed > ?) "
            f"AND {starts_before_end} LIMIT 1",
            (thing_id, cached.rev, cached.rev, end, end),
        ).fetchone()
        return value is not None

    def stale(self, thing_id: str, section: str, at: WorldDate | None) -> bool:
        """`True` if there's no cached entry for the stretch containing
        `at`, its `rev` predates the newest timeline change inside that
        stretch, or a row visible in that stretch was added or retired
        after its `rev`."""

        cached = self.get(thing_id, section, at)
        if cached is None:
            return True

        entries = self._view_factory().timeline(thing_id)
        newest = _newest_rev_in_stretch(
            entries, cached.stretch_start, cached.stretch_end
        )
        if cached.rev < newest:
            return True
        return self._changed_in_stretch_since(thing_id, cached)
