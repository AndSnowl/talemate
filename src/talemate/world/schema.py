"""Database schema and migrations for a world's SQLite file.

Each entry in `MIGRATIONS` is the DDL that upgrades a database from its
index's version to the next. `apply` runs the pending ones inside a single
transaction and records the result in `PRAGMA user_version`.

`things` is versioned like every other table: one row per thing per span
of revisions it's live for (an undo can retire a thing and later restore
it), so `things.id` isn't unique and `field_values`/`facts` can't carry a
foreign key to it. Their thing ids are checked in code instead.

Undo leaves reversal links instead of relying on content: `revision_reverts`
lists, per undo revision, the revisions it reversed, and a row an undo
restores records in `restored_from` the `row_id` (in the same table) of the
row it's a copy of. Every other write leaves `restored_from` NULL. An undo
revision also records in `undo_conflicts` each row it left alone because of
a conflict (`table_name` is `things`, `field_values` or `facts`), so a later
undo knows which of its slots it didn't go through for.
"""

import sqlite3

import structlog

log = structlog.get_logger("talemate.world.schema")

SCHEMA_VERSION = 1

MIGRATIONS: list[str] = [
    # 0 -> 1
    """
    CREATE TABLE meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE revisions (
        rev INTEGER PRIMARY KEY AUTOINCREMENT,
        source_kind TEXT NOT NULL CHECK (source_kind IN ('manual', 'scene', 'undo')),
        scene_id TEXT,
        branch_id TEXT,
        message_id TEXT,
        note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    );

    CREATE TABLE revision_reverts (
        undo_rev INTEGER NOT NULL REFERENCES revisions,
        target_rev INTEGER NOT NULL REFERENCES revisions,
        PRIMARY KEY (undo_rev, target_rev)
    );

    CREATE TABLE undo_conflicts (
        undo_rev INTEGER NOT NULL REFERENCES revisions,
        table_name TEXT NOT NULL,
        row_id INTEGER NOT NULL
    );

    CREATE TABLE things (
        row_id INTEGER PRIMARY KEY,
        id TEXT NOT NULL,
        kind TEXT NOT NULL,
        rev_added INTEGER NOT NULL REFERENCES revisions,
        rev_removed INTEGER REFERENCES revisions,
        restored_from INTEGER
    );

    CREATE TABLE field_values (
        row_id INTEGER PRIMARY KEY,
        thing_id TEXT NOT NULL,
        field TEXT NOT NULL,
        value_json TEXT NOT NULL,
        valid_from INTEGER,
        from_precision TEXT,
        rev_added INTEGER NOT NULL,
        rev_removed INTEGER,
        restored_from INTEGER
    );

    CREATE TABLE facts (
        row_id INTEGER PRIMARY KEY,
        fact_id TEXT NOT NULL,
        thing_id TEXT NOT NULL,
        category TEXT NOT NULL,
        text TEXT NOT NULL,
        valid_from INTEGER,
        from_precision TEXT,
        valid_until INTEGER,
        until_precision TEXT,
        origin_json TEXT,
        rev_added INTEGER NOT NULL,
        rev_removed INTEGER,
        restored_from INTEGER
    );

    CREATE TABLE fact_refs (
        row_id INTEGER NOT NULL REFERENCES facts,
        thing_id TEXT NOT NULL
    );

    CREATE INDEX idx_field_values_thing_field ON field_values (thing_id, field);
    CREATE INDEX idx_field_values_thing ON field_values (thing_id);
    CREATE INDEX idx_field_values_rev_added ON field_values (rev_added);
    CREATE INDEX idx_field_values_rev_removed ON field_values (rev_removed);

    CREATE INDEX idx_facts_fact_id ON facts (fact_id);
    CREATE INDEX idx_facts_thing ON facts (thing_id);
    CREATE INDEX idx_facts_rev_added ON facts (rev_added);
    CREATE INDEX idx_facts_rev_removed ON facts (rev_removed);

    CREATE INDEX idx_fact_refs_thing ON fact_refs (thing_id);

    CREATE INDEX idx_things_id ON things (id);
    CREATE INDEX idx_things_rev_added ON things (rev_added);
    CREATE INDEX idx_things_rev_removed ON things (rev_removed);
    """,
]


def _statements(migration: str) -> list[str]:
    """Split a migration's DDL into individual statements. `executescript`
    isn't used here because it implicitly commits any open transaction
    before running, which would defeat the atomicity below."""

    return [stmt.strip() for stmt in migration.split(";") if stmt.strip()]


def apply(conn: sqlite3.Connection) -> None:
    """Run any migrations the database hasn't seen yet, then record the new
    `user_version`, all inside one transaction."""

    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current >= SCHEMA_VERSION:
        return

    conn.execute("BEGIN IMMEDIATE")
    try:
        for migration in MIGRATIONS[current:SCHEMA_VERSION]:
            for statement in _statements(migration):
                conn.execute(statement)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
