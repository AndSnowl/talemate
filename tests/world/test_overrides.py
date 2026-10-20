"""Fact override links: a fact can name the facts (by stable `fact_id`) it
supersedes, so a more specific layer can drop an inherited one without
changing it."""

import sqlite3

import pytest

from talemate.world import schema
from talemate.world.store import Source, World


def test_add_fact_with_overrides(world):
    with world.revision(Source.manual()) as rev:
        species_id = rev.create_thing("species", fields={"name": "Elf"})
        species_fact_id = rev.add_fact(species_id, "physical", "Pointed ears.")
        c = rev.create_thing("character", fields={"name": "Aria"})
        rev.add_fact(
            c, "appearance", "Rounded ears, unusually.", overrides=[species_fact_id]
        )

    state = world.view().thing(c)
    assert state.facts[0].overrides == [species_fact_id]


def test_override_unknown_fact_rejected(world):
    with world.revision(Source.manual()) as rev:
        c = rev.create_thing("character", fields={"name": "Aria"})
        with pytest.raises(ValueError):
            rev.add_fact(c, "appearance", "x", overrides=["0" * 32])


def test_override_survives_correction(world):
    with world.revision(Source.manual()) as rev:
        species_id = rev.create_thing("species", fields={"name": "Elf"})
        species_fact_id = rev.add_fact(species_id, "physical", "Pointed ears.")
        c = rev.create_thing("character", fields={"name": "Aria"})
        override_fact_id = rev.add_fact(
            c, "appearance", "Rounded ears.", overrides=[species_fact_id]
        )

    # correcting the overridden fact keeps its fact_id, so the override
    # still applies
    with world.revision(Source.manual()) as rev:
        rev.correct_fact(species_fact_id, text="Very pointed ears.")

    state = world.view().thing(c)
    assert state.facts[0].overrides == [species_fact_id]

    # correcting the overriding fact without `overrides` keeps its links
    with world.revision(Source.manual()) as rev:
        rev.correct_fact(override_fact_id, text="Rounded ears, unusually.")

    state = world.view().thing(c)
    assert state.facts[0].overrides == [species_fact_id]
    assert state.facts[0].text == "Rounded ears, unusually."


def _create_v2_database(path) -> None:
    """A database left at schema version 2, as if created before this
    migration existed."""

    conn = sqlite3.connect(path)
    try:
        for migration in schema.MIGRATIONS[:2]:
            for statement in schema._statements(migration):
                conn.execute(statement)
        conn.execute("PRAGMA user_version = 2")
        conn.commit()
    finally:
        conn.close()


def test_migration_2_to_3(tmp_path):
    world_dir = tmp_path / "old-world"
    world_dir.mkdir()
    (world_dir / "assets").mkdir()
    (world_dir / "index").mkdir()
    _create_v2_database(world_dir / "world.sqlite")

    world = World.open(world_dir)
    try:
        version = world._conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 3
        count = world._conn.execute("SELECT COUNT(*) FROM fact_overrides").fetchone()[0]
        assert count == 0
    finally:
        world.close()
