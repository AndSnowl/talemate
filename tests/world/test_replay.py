"""Unit tests for talemate.world.replay that don't belong in
test_invariants.py's full-replay checks."""

import sqlite3

from talemate.world import schema
from talemate.world.replay import History


class _SpyConnection(sqlite3.Connection):
    """A connection that records how many parameters each call to
    ``execute`` binds, so a test can assert on it without touching the
    (immutable, C-implemented) ``sqlite3.Connection`` class or instances of
    it directly."""

    bound_counts: list[int]

    def execute(self, sql, parameters=()):
        if parameters:
            self.bound_counts.append(len(parameters))
        return super().execute(sql, parameters)


def test_touched_slots_keeps_bound_params_under_sqlite_limit():
    """`touched_slots` binds each chunk's rev list twice (`rev_added IN
    (...) OR rev_removed IN (...)`), so a chunk sized to the 999-variable
    limit the module comment cites would itself bind 2x that many. Given
    more revs than fit in one chunk, no single query may bind more than
    999 parameters."""

    conn = sqlite3.connect(":memory:", factory=_SpyConnection)
    conn.row_factory = sqlite3.Row
    conn.bound_counts = []
    schema.apply(conn)

    History(conn).touched_slots(range(1, 601))

    assert conn.bound_counts, "expected touched_slots to issue parameterised queries"
    assert max(conn.bound_counts) <= 999
