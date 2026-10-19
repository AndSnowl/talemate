"""Database schema and migrations for a world's SQLite file.

Each entry in `MIGRATIONS` is the DDL that upgrades a database from its
index's version to the next. `apply` runs the pending ones inside a single
transaction and records the result in `PRAGMA user_version`.
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

    CREATE TABLE things (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        rev_added INTEGER NOT NULL REFERENCES revisions,
        rev_removed INTEGER REFERENCES revisions
    );

    CREATE TABLE field_values (
        row_id INTEGER PRIMARY KEY,
        thing_id TEXT NOT NULL REFERENCES things,
        field TEXT NOT NULL,
        value_json TEXT NOT NULL,
        valid_from INTEGER,
        from_precision TEXT,
        rev_added INTEGER NOT NULL,
        rev_removed INTEGER
    );

    CREATE TABLE facts (
        row_id INTEGER PRIMARY KEY,
        fact_id TEXT NOT NULL,
        thing_id TEXT NOT NULL REFERENCES things,
        category TEXT NOT NULL,
        text TEXT NOT NULL,
        valid_from INTEGER,
        from_precision TEXT,
        valid_until INTEGER,
        until_precision TEXT,
        origin_json TEXT,
        rev_added INTEGER NOT NULL,
        rev_removed INTEGER
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
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
