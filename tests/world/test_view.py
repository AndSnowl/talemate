import sqlite3

from talemate.world.dates import WorldDate
from talemate.world.refs import ref
from talemate.world.store import Source
from talemate.world.view import UNKNOWN_NAME


def _raw_connect(world) -> sqlite3.Connection:
    conn = sqlite3.connect(world.path / "world.sqlite")
    conn.row_factory = sqlite3.Row
    return conn


def test_view_at_date_filters_facts(world, maren):
    view = world.view(at=WorldDate.of(312))
    thing = view.thing(maren.id)

    fact_ids = {fact.fact_id for fact in thing.facts}
    assert fact_ids == {maren.tattoo, maren.warden, maren.laugh}
    assert maren.eye not in fact_ids


def test_open_start_fact_visible_before_any_date(world, maren):
    view = world.view(at=WorldDate.of(291))
    thing = view.thing(maren.id)

    fact_ids = {fact.fact_id for fact in thing.facts}
    assert maren.laugh in fact_ids


def test_latest_view_hides_ended_facts(world, maren):
    view = world.view(at=None)
    thing = view.thing(maren.id)

    fact_ids = {fact.fact_id for fact in thing.facts}
    assert maren.warden not in fact_ids
    assert maren.eye in fact_ids


def test_view_at_old_revision(world, maren):
    view = world.view(at=WorldDate.of(318), rev=maren.rev_eye - 1)
    thing = view.thing(maren.id)

    fact_ids = {fact.fact_id for fact in thing.facts}
    assert maren.eye not in fact_ids


def test_prequel_fact_shows_in_earlier_view(world, maren):
    with world.revision(Source.manual(note="a prequel scar")) as rev:
        scar = rev.add_fact(
            maren.id,
            "appearance",
            "A scar across her palm.",
            valid_from=WorldDate.of(300),
        )

    view = world.view(at=WorldDate.of(312))
    thing = view.thing(maren.id)

    fact_ids = {fact.fact_id for fact in thing.facts}
    assert scar in fact_ids


def test_render_uses_name_at_date(world, maren):
    with world.revision(Source.manual(note="Oskar owes a debt")) as rev:
        oskar_id = rev.create_thing("character", fields={"name": "Oskar"})
        debt_text = f"Owes {ref(maren.id)} a debt."
        rev.add_fact(oskar_id, "relationship", debt_text)

    view_at_date = world.view(at=WorldDate.of(312))
    assert view_at_date.render(debt_text) == "Owes Maren a debt."

    view_latest = world.view(at=None)
    assert view_latest.render(debt_text) == "Owes Maren the Grey a debt."


def test_render_unknown_reference(world, maren):
    missing_id = "0" * 32
    text = f"Friends with {ref(missing_id)}."

    conn = _raw_connect(world)
    try:
        conn.execute(
            "INSERT INTO facts "
            "(fact_id, thing_id, category, text, valid_from, from_precision, "
            " valid_until, until_precision, origin_json, rev_added) "
            "VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?)",
            ("f" * 32, maren.id, "background", text, maren.rev_created),
        )
        conn.commit()
    finally:
        conn.close()

    view = world.view()
    assert view.render(text) == f"Friends with {UNKNOWN_NAME}."


def test_referencing_finds_reverse_links(world, maren):
    with world.revision(Source.manual(note="Oskar owes a debt")) as rev:
        oskar_id = rev.create_thing("character", fields={"name": "Oskar"})
        fact_id = rev.add_fact(
            oskar_id, "relationship", f"Owes {ref(maren.id)} a debt."
        )

    view = world.view()
    results = view.referencing(maren.id)

    assert results == [(oskar_id, results[0][1])]
    assert results[0][1].fact_id == fact_id


def test_removed_thing_absent_from_view(world, maren):
    with world.revision(Source.manual(note="remove Maren")) as rev:
        rev.remove_thing(maren.id)

    view = world.view()
    assert view.thing(maren.id) is None
    assert maren.id not in {thing.id for thing in view.things()}
