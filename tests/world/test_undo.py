import json

import pytest

from talemate.world.dates import WorldDate
from talemate.world.refs import ref
from talemate.world.store import Source


def _fact_texts(world, thing_id, rev=None):
    state = world.view(rev=rev).thing(thing_id)
    return {f.fact_id: f.text for f in state.facts}


def test_undo_reverts_added_fact(world, maren):
    with world.revision(Source.manual()) as rev:
        fact_id = rev.add_fact(maren.id, "background", "Sailed the northern sea.")
        added = rev.rev

    report = world.undo([added])

    assert report.reverted == 1
    assert report.conflicts == []
    assert report.undo_rev == world.head_rev()
    assert fact_id not in _fact_texts(world, maren.id)


def test_undo_restores_corrected_fact(world, maren):
    with world.revision(Source.manual()) as rev:
        rev.correct_fact(maren.laugh, text="A slow, rare laugh.")
        corrected = rev.rev

    report = world.undo([corrected])

    # the corrected version is retired, the original copy restored
    assert report.reverted == 2
    assert report.conflicts == []
    assert _fact_texts(world, maren.id)[maren.laugh] == "A quick laugh."


def test_undo_restores_override_links(world):
    with world.revision(Source.manual()) as rev:
        species_id = rev.create_thing("species", fields={"name": "Elf"})
        species_fact_id = rev.add_fact(species_id, "physical", "Pointed ears.")
        c = rev.create_thing("character", fields={"name": "Aria"})
        override_fact_id = rev.add_fact(
            c, "appearance", "Rounded ears.", overrides=[species_fact_id]
        )

    with world.revision(Source.manual()) as rev:
        rev.remove_fact(override_fact_id)
        removed = rev.rev

    report = world.undo([removed])

    assert report.reverted == 1
    state = world.view().thing(c)
    assert state.facts[0].fact_id == override_fact_id
    assert state.facts[0].overrides == [species_fact_id]


def test_undo_lists_later_edited_rows(world, maren):
    with world.revision(Source.manual()) as rev:
        fact_id = rev.add_fact(maren.id, "background", "Sailed the northern sea.")
        added = rev.rev
    with world.revision(Source.manual(note="hand fix")) as rev:
        rev.correct_fact(fact_id, text="Sailed the southern sea.")
        fixed = rev.rev

    report = world.undo([added])

    assert report.reverted == 0
    assert len(report.conflicts) == 1
    conflict = report.conflicts[0]
    assert conflict.table == "facts"
    assert conflict.thing_id == maren.id
    assert conflict.later_rev == fixed
    assert conflict.reason == "changed again in a later revision"
    assert _fact_texts(world, maren.id)[fact_id] == "Sailed the southern sea."


def test_undo_lists_later_removed_rows(world, maren):
    with world.revision(Source.manual()) as rev:
        fact_id = rev.add_fact(maren.id, "background", "Sailed the northern sea.")
        added = rev.rev
    with world.revision(Source.manual()) as rev:
        rev.remove_fact(fact_id)
        removed = rev.rev

    report = world.undo([added])

    assert report.undo_rev is None
    assert [(c.reason, c.later_rev) for c in report.conflicts] == [
        ("removed in a later revision", removed)
    ]


def test_undo_restore_conflicts_with_newer_version(world, maren):
    with world.revision(Source.manual()) as rev:
        rev.set_field(maren.id, "name", "Maren Vell", WorldDate.of(317))
        renamed_again = rev.rev

    # a correction of a field slot: undo retires it and restores the old value
    report = world.undo([renamed_again])
    assert report.reverted == 2
    assert world.view().thing(maren.id).fields["name"] == "Maren the Grey"

    # a slot the targets retired, now superseded by a later hand edit
    with world.revision(Source.manual()) as rev:
        rev.set_field(maren.id, "name", "Maren Vell", WorldDate.of(317))
        first = rev.rev
    with world.revision(Source.manual()) as rev:
        rev.set_field(maren.id, "name", "Maren Ash", WorldDate.of(317))
        second = rev.rev

    report = world.undo([first])
    assert report.reverted == 0
    assert [(c.table, c.later_rev) for c in report.conflicts] == [
        ("field_values", second)
    ]
    assert world.view().thing(maren.id).fields["name"] == "Maren Ash"


def test_undo_branch_by_source(world, maren):
    facts = {}
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        facts["e1"] = rev.add_fact(maren.id, "background", "E: joined the guard.")
    with world.revision(Source.scene("s1", "F", "m1")) as rev:
        facts["f1"] = rev.add_fact(maren.id, "background", "F: left for the coast.")
    with world.revision(Source.scene("s1", "E", "m2")) as rev:
        facts["e2"] = rev.add_fact(maren.id, "personality", "E: grew stern.")
        rev.correct_fact(facts["e1"], text="E: joined the night guard.")
    with world.revision(Source.scene("s1", "F", "m2")) as rev:
        facts["f2"] = rev.add_fact(maren.id, "personality", "F: grew restless.")

    e_revs = [r.rev for r in world.revisions(branch_id="E")]
    assert len(e_revs) == 2
    report = world.undo(e_revs, note="drop branch E")

    assert report.conflicts == []
    texts = _fact_texts(world, maren.id)
    assert facts["e1"] not in texts
    assert facts["e2"] not in texts
    assert texts[facts["f1"]] == "F: left for the coast."
    assert texts[facts["f2"]] == "F: grew restless."
    assert maren.laugh in texts

    undo_info = world.revisions()[-1]
    assert undo_info.rev == report.undo_rev
    assert undo_info.source.kind == "undo"
    assert undo_info.source.note == "drop branch E"


def test_revisions_filters_combine(world, maren):
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        a = rev.rev
    with world.revision(Source.scene("s1", "E", "m2")):
        pass
    with world.revision(Source.scene("s2", "E", "m1")):
        pass

    assert [r.rev for r in world.revisions()] == list(range(1, world.head_rev() + 1))
    assert [r.rev for r in world.revisions(scene_id="s1", message_id="m1")] == [a]
    assert len(world.revisions(branch_id="E")) == 3
    assert world.revisions(branch_id="F") == []
    info = world.revisions(scene_id="s1", message_id="m1")[0]
    assert info.source == Source.scene("s1", "E", "m1")
    assert info.created_at


def test_undo_nothing_writes_no_revision(world, maren):
    with world.revision(Source.manual()) as rev:
        rev.add_fact(maren.id, "background", "Sailed the northern sea.")
        rev.correct_fact(maren.laugh, text="A slow, rare laugh.")
        target = rev.rev

    first = world.undo([target])
    assert first.reverted == 3
    head = world.head_rev()

    again = world.undo([target])

    assert again.undo_rev is None
    assert again.reverted == 0
    assert again.conflicts == []
    assert world.head_rev() == head


def test_view_before_undo_still_available(world, maren):
    with world.revision(Source.manual()) as rev:
        fact_id = rev.add_fact(maren.id, "background", "Sailed the northern sea.")
        added = rev.rev

    world.undo([added])

    assert fact_id in _fact_texts(world, maren.id, rev=added)
    assert fact_id not in _fact_texts(world, maren.id)


def test_undo_thing_creation_retires_its_rows(world, maren):
    with world.revision(Source.manual()) as rev:
        oskar = rev.create_thing("character", fields={"name": "Oskar"})
        rev.add_fact(oskar, "background", "A ferryman.")
        created = rev.rev

    report = world.undo([created])

    # the thing, its name and its fact
    assert report.reverted == 3
    assert world.view().thing(oskar) is None
    assert world.view(rev=created).thing(oskar).fields["name"] == "Oskar"


def test_undo_thing_creation_conflicts_with_later_rows(world, maren):
    with world.revision(Source.manual()) as rev:
        oskar = rev.create_thing("character", fields={"name": "Oskar"})
        created = rev.rev
    with world.revision(Source.manual()) as rev:
        fact_id = rev.add_fact(oskar, "background", "A ferryman.")
        later = rev.rev

    report = world.undo([created])

    assert report.undo_rev is None
    assert [(c.table, c.thing_id, c.later_rev) for c in report.conflicts] == [
        ("things", oskar, later)
    ]
    state = world.view().thing(oskar)
    assert state.fields["name"] == "Oskar"
    assert [f.fact_id for f in state.facts] == [fact_id]


def test_undo_remove_thing_restores_it(world, maren):
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(maren.id)
        removed = rev.rev

    report = world.undo([removed])

    state = world.view().thing(maren.id)
    assert state is not None
    assert state.fields["name"] == "Maren the Grey"
    assert {f.fact_id for f in state.facts} == {maren.tattoo, maren.laugh, maren.eye}
    # the warden fact ended in 316, so it only shows at an earlier date
    earlier = world.view(at=WorldDate.of(310)).thing(maren.id)
    assert maren.warden in {f.fact_id for f in earlier.facts}
    # the view of the revision in between still shows her removed
    assert world.view(rev=removed).thing(maren.id) is None
    assert world.view(rev=report.undo_rev).thing(maren.id) is not None
    # undoing the removal again is a no-op
    assert world.undo([removed]).undo_rev is None
    # the restored thing can be written to again
    with world.revision(Source.manual()) as rev:
        rev.add_fact(maren.id, "background", "Came back.")
    assert len(world.timeline(maren.id)) > 0


def _live_thing_rows(world, thing_id):
    return world._conn.execute(
        "SELECT COUNT(*) FROM things WHERE id = ? AND rev_removed IS NULL",
        (thing_id,),
    ).fetchone()[0]


def test_undo_branch_that_removed_a_thing_twice(world, maren):
    with world.revision(Source.manual()) as rev:
        oskar = rev.create_thing("character", fields={"name": "Oskar"})
        rev.add_fact(oskar, "background", "A ferryman.")
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        rev.remove_thing(oskar)
        first = rev.rev
    world.undo([first])
    with world.revision(Source.scene("s1", "E", "m2")) as rev:
        rev.remove_thing(oskar)

    report = world.undo([r.rev for r in world.revisions(branch_id="E")])

    # the thing, its name and its fact, each restored once
    assert report.reverted == 3
    assert report.conflicts == []
    assert _live_thing_rows(world, oskar) == 1
    state = world.view().thing(oskar)
    assert state.fields["name"] == "Oskar"
    assert len(state.facts) == 1


def test_undo_creation_never_restores_the_thing(world, maren):
    with world.revision(Source.manual()) as rev:
        oskar = rev.create_thing("character", fields={"name": "Oskar"})
        created = rev.rev
    dropped = world.undo([created]).undo_rev
    world.undo([dropped])
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(oskar)
        removed = rev.rev

    report = world.undo([created, removed])

    assert report.undo_rev is None
    assert report.conflicts == []
    assert world.view().thing(oskar) is None
    assert _live_thing_rows(world, oskar) == 0


def _branch_revs(world, branch_id):
    return [r.rev for r in world.revisions(branch_id=branch_id)]


def test_undo_after_redo_reverts_fact_again(world, maren):
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        scar = rev.add_fact(maren.id, "appearance", "A scar across her cheek.")
        target = rev.rev
    before = _fact_texts(world, maren.id, rev=target - 1)

    undone = world.undo([target])
    redone = world.undo([undone.undo_rev])
    assert scar in _fact_texts(world, maren.id)

    report = world.undo(_branch_revs(world, "E"))

    assert report.undo_rev is not None
    assert report.reverted == 1
    assert report.conflicts == []
    assert _fact_texts(world, maren.id) == before
    # and re-undoing it once more is still a quiet no-op
    again = world.undo([target])
    assert (again.undo_rev, again.reverted, again.conflicts) == (None, 0, [])
    assert redone.conflicts == []


def test_undo_after_redo_restores_corrected_fact(world, maren):
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        rev.correct_fact(maren.laugh, text="A slow, rare laugh.")
        target = rev.rev

    undone = world.undo([target])
    world.undo([undone.undo_rev])
    assert _fact_texts(world, maren.id)[maren.laugh] == "A slow, rare laugh."

    report = world.undo([target])

    assert report.reverted == 2
    assert report.conflicts == []
    assert _fact_texts(world, maren.id)[maren.laugh] == "A quick laugh."


def test_undo_after_redo_reverts_thing_creation_again(world, maren):
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        oskar = rev.create_thing("character", fields={"name": "Oskar"})
        rev.add_fact(oskar, "background", "A ferryman.")
        target = rev.rev

    undone = world.undo([target])
    world.undo([undone.undo_rev])
    assert world.view().thing(oskar).fields["name"] == "Oskar"

    report = world.undo(_branch_revs(world, "E"))

    # the thing, its name and its fact
    assert report.reverted == 3
    assert report.conflicts == []
    assert world.view().thing(oskar) is None
    assert _live_thing_rows(world, oskar) == 0
    assert world.undo([target]).undo_rev is None


def test_undo_after_redo_lists_later_change(world, maren):
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        scar = rev.add_fact(maren.id, "appearance", "A scar across her cheek.")
        target = rev.rev
    undone = world.undo([target])
    world.undo([undone.undo_rev])
    with world.revision(Source.manual(note="hand fix")) as rev:
        rev.correct_fact(scar, text="A faint scar across her cheek.")
        fixed = rev.rev

    report = world.undo([target])

    assert report.undo_rev is None
    assert [(c.table, c.reason, c.later_rev) for c in report.conflicts] == [
        ("facts", "changed again in a later revision", fixed)
    ]
    assert _fact_texts(world, maren.id)[scar] == "A faint scar across her cheek."


def _referencing_write(kind):
    """A write, in a later revision, that makes Oskar (or his home) point
    at the new thing."""

    def fact(rev, oskar, home, new):
        rev.add_fact(oskar, "relationship", f"Owes {ref(new)} a debt.")

    def thing_field(rev, oskar, home, new):
        rev.set_field(oskar, "heritage", new, None)

    return {"fact": fact, "thing": thing_field}[kind]


@pytest.fixture
def oskar_and_home(world):
    with world.revision(Source.manual()) as rev:
        oskar = rev.create_thing("character", fields={"name": "Oskar"})
        home = rev.create_thing("place", fields={"name": "Low Harbour"})
    return oskar, home


@pytest.mark.parametrize("kind", ["fact", "thing"])
def test_undo_creation_conflicts_with_later_reference(world, oskar_and_home, kind):
    oskar, home = oskar_and_home
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        new = rev.create_thing("character", fields={"name": "Maren"})
        created = rev.rev
    with world.revision(Source.scene("s1", "F", "m1")) as rev:
        _referencing_write(kind)(rev, oskar, home, new)
        referenced = rev.rev

    report = world.undo([created])

    assert report.undo_rev is None
    assert [(c.table, c.thing_id, c.reason, c.later_rev) for c in report.conflicts] == [
        ("things", new, "referenced in a later revision", referenced)
    ]
    assert world.view().thing(new).fields["name"] == "Maren"


def test_undo_creation_blocked_by_mix_parent(world):
    with world.revision(Source.manual()) as rev:
        human = rev.create_thing("species", fields={"name": "Human"})
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        orc = rev.create_thing("species", fields={"name": "Orc"})
        created = rev.rev
    with world.revision(Source.scene("s1", "F", "m1")) as rev:
        rev.create_thing("mix", fields={"name": "Half-orc", "parents": [human, orc]})
        referenced = rev.rev

    report = world.undo([created])

    assert report.undo_rev is None
    assert [(c.table, c.thing_id, c.reason, c.later_rev) for c in report.conflicts] == [
        ("things", orc, "referenced in a later revision", referenced)
    ]
    assert world.view().thing(orc).fields["name"] == "Orc"


def test_undo_creation_reports_one_conflict_for_several_references(
    world, oskar_and_home
):
    oskar, home = oskar_and_home
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        maren = rev.create_thing("character", fields={"name": "Maren"})
        created = rev.rev
    with world.revision(Source.scene("s1", "F", "m1")) as rev:
        rev.add_fact(oskar, "relationship", f"Owes {ref(maren)} a debt.")
        rev.set_field(oskar, "heritage", maren, None)
        referenced = rev.rev

    report = world.undo([created])

    assert [(c.reason, c.later_rev) for c in report.conflicts] == [
        ("referenced in a later revision", referenced)
    ]
    assert world.view().thing(maren) is not None
    assert "Maren" in world.view().render(f"{ref(maren)}")


def test_undo_creation_with_reference_inside_targets(world, oskar_and_home):
    oskar, home = oskar_and_home
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        maren = rev.create_thing("character", fields={"name": "Maren"})
    with world.revision(Source.scene("s1", "E", "m2")) as rev:
        rev.add_fact(oskar, "relationship", f"Owes {ref(maren)} a debt.")
        rev.set_field(oskar, "heritage", maren, None)

    report = world.undo(_branch_revs(world, "E"))

    assert report.conflicts == []
    assert world.view().thing(maren) is None
    state = world.view().thing(oskar)
    assert state.facts == []
    assert "heritage" not in state.fields


def test_undo_creation_ignores_retired_reference(world, oskar_and_home):
    oskar, home = oskar_and_home
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        maren = rev.create_thing("character", fields={"name": "Maren"})
        created = rev.rev
    with world.revision(Source.scene("s1", "F", "m1")) as rev:
        debt = rev.add_fact(oskar, "relationship", f"Owes {ref(maren)} a debt.")
    with world.revision(Source.manual()) as rev:
        rev.remove_fact(debt)

    report = world.undo([created])

    assert report.conflicts == []
    assert world.view().thing(maren) is None


def test_redo_of_removal_ignores_earlier_reference(world, maren, oskar_and_home):
    oskar, home = oskar_and_home
    with world.revision(Source.manual()) as rev:
        rev.add_fact(oskar, "relationship", f"Owes {ref(maren.id)} a debt.")
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        rev.remove_thing(maren.id)
        removed = rev.rev
    restored = world.undo([removed])

    # redoing the removal: the reference predates the restored thing
    redo = world.undo([restored.undo_rev])

    assert redo.conflicts == []
    assert world.view().thing(maren.id) is None


def _name(world, thing_id, valid_from=WorldDate.of(317)):
    row = world._conn.execute(
        "SELECT value_json FROM field_values WHERE thing_id = ? AND field = 'name' "
        "AND valid_from IS ? AND rev_removed IS NULL",
        (thing_id, None if valid_from is None else valid_from.instant),
    ).fetchone()
    return None if row is None else json.loads(row[0])


def _set_name(world, thing_id, name, source=None):
    with world.revision(source or Source.manual()) as rev:
        rev.set_field(thing_id, "name", name, WorldDate.of(317))
        return rev.rev


def _correct(world, fact_id, text, source=None):
    with world.revision(source or Source.manual()) as rev:
        rev.correct_fact(fact_id, text=text)
        return rev.rev


def test_reundo_after_unrelated_restore_of_same_value_is_noop(world, maren):
    # P is the fixture's rename; T sets "A" and is undone, then a hand edit
    # sets "A" again and an undo of a later change restores that hand edit
    target = _set_name(world, maren.id, "A", Source.scene("s1", "E", "m1"))
    world.undo([target])
    _set_name(world, maren.id, "A")
    later = _set_name(world, maren.id, "C")
    world.undo([later])
    assert _name(world, maren.id) == "A"
    head = world.head_rev()

    report = world.undo([target])

    assert (report.undo_rev, report.reverted, report.conflicts) == (None, 0, [])
    assert world.head_rev() == head
    assert _name(world, maren.id) == "A"


def test_reundo_after_unrelated_restore_of_same_fact_text_is_noop(world, maren):
    with world.revision(Source.manual()) as rev:
        fact_id = rev.add_fact(maren.id, "background", "c")
    target = _correct(world, fact_id, "d", Source.scene("s1", "E", "m1"))
    world.undo([target])
    _correct(world, fact_id, "d")
    later = _correct(world, fact_id, "e")
    world.undo([later])
    assert _fact_texts(world, maren.id)[fact_id] == "d"

    report = world.undo([target])

    assert (report.undo_rev, report.reverted, report.conflicts) == (None, 0, [])
    assert _fact_texts(world, maren.id)[fact_id] == "d"


def test_two_undos_into_one_slot_not_confused(world, maren):
    target = _set_name(world, maren.id, "d", Source.scene("s1", "E", "m1"))
    world.undo([target])
    _set_name(world, maren.id, "d")
    later = _set_name(world, maren.id, "e")
    restored = world.undo([later])
    assert restored.reverted == 2
    assert _name(world, maren.id) == "d"

    report = world.undo([target])

    assert (report.undo_rev, report.reverted, report.conflicts) == (None, 0, [])
    assert _name(world, maren.id) == "d"


def test_manual_revert_after_redo_is_conflict(world, maren):
    target = _set_name(world, maren.id, "Maren Vell", Source.scene("s1", "E", "m1"))
    undone = world.undo([target])
    world.undo([undone.undo_rev])
    assert _name(world, maren.id) == "Maren Vell"
    fixed = _set_name(world, maren.id, "Maren the Grey")
    head = world.head_rev()

    report = world.undo([target])

    assert report.undo_rev is None
    assert [(c.table, c.reason, c.later_rev) for c in report.conflicts] == [
        ("field_values", "changed again in a later revision", fixed)
    ]
    assert world.head_rev() == head
    assert _name(world, maren.id) == "Maren the Grey"


def test_undo_restored_reference_blocks_uncreation(world, oskar_and_home):
    oskar, home = oskar_and_home
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        new = rev.create_thing("character", fields={"name": "Maren"})
        created = rev.rev
    with world.revision(Source.scene("s1", "F", "m1")) as rev:
        rev.add_fact(oskar, "relationship", f"Owes {ref(new)} a debt.")
        referenced = rev.rev
    undone = world.undo([created, referenced])
    world.undo([undone.undo_rev])
    assert world.view().thing(new) is not None

    report = world.undo([created])

    assert report.undo_rev is None
    assert [(c.table, c.thing_id, c.reason, c.later_rev) for c in report.conflicts] == [
        ("things", new, "referenced in a later revision", referenced)
    ]
    assert world.view().thing(new).fields["name"] == "Maren"


def test_undo_records_reversal_links(world, maren):
    with world.revision(Source.manual()) as rev:
        rev.correct_fact(maren.laugh, text="A slow, rare laugh.")
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(maren.id)
    assert [r.rev for r in world.revisions()][-2:] == [4, 5]

    report = world.undo([4, 5])

    infos = {info.rev: info for info in world.revisions()}
    assert infos[report.undo_rev].reverts == [4, 5]
    assert all(infos[rev].reverts == [] for rev in infos if rev != report.undo_rev)
    restored = 0
    for table in ("things", "field_values", "facts"):
        rows = world._conn.execute(
            f"SELECT restored_from FROM {table} WHERE rev_added = ?",
            (report.undo_rev,),
        ).fetchall()
        assert all(row[0] is not None for row in rows), table
        restored += len(rows)
        # nothing but an undo writes a restored copy
        assert (
            world._conn.execute(
                f"SELECT COUNT(*) FROM {table} "
                "WHERE rev_added != ? AND restored_from IS NOT NULL",
                (report.undo_rev,),
            ).fetchone()[0]
            == 0
        )
    assert restored > 0


def test_reundo_after_undo_of_earlier_write_is_noop(world, maren):
    target = _set_name(world, maren.id, "Maren Vell", Source.scene("s1", "E", "m1"))
    world.undo([target])
    # undoing the rename retires the copy the first undo restored; that's
    # not a redo of the target, so the target stays undone
    world.undo([maren.rev_renamed])
    assert _name(world, maren.id) is None

    report = world.undo([target])

    assert (report.undo_rev, report.reverted, report.conflicts) == (None, 0, [])
    assert _name(world, maren.id) is None


def test_reundo_of_a_netted_out_removal_is_noop(world, maren):
    # pins: an undo stays in effect on a slot it wrote nothing to (R5)
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        oskar = rev.create_thing("character", fields={"name": "Oskar"})
    with world.revision(Source.scene("s1", "E", "m2")) as rev:
        rev.remove_thing(oskar)
        removed = rev.rev
    with world.revision(Source.scene("s1", "E", "m3")) as rev:
        rev.add_fact(maren.id, "background", "Sailed the northern sea.")
    # the creation and the removal cancel out, so this writes nothing for
    # Oskar, but it does revert the removal
    assert world.undo(_branch_revs(world, "E")).reverted == 1

    report = world.undo([removed])

    assert (report.undo_rev, report.reverted, report.conflicts) == (None, 0, [])
    assert world.view().thing(oskar) is None


def test_reundo_after_conflicted_netting_still_restores(world, maren):
    # pins: a thing conflict blocks the undo on the thing's child slots
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        oskar = rev.create_thing("character", fields={"name": "Oskar"})
    with world.revision(Source.scene("s1", "E", "m2")) as rev:
        ferry = rev.add_fact(oskar, "background", "A ferryman.")
    with world.revision(Source.scene("s1", "E", "m3")) as rev:
        rev.remove_fact(ferry)
        removed = rev.rev
    with world.revision(Source.scene("s1", "E", "m4")) as rev:
        rev.add_fact(maren.id, "background", "Sailed the northern sea.")
    with world.revision(Source.scene("s1", "F", "m1")) as rev:
        rev.add_fact(oskar, "background", "Owns a boat.")
    # Oskar has a later fact, so this keeps him (R6) and every row of his,
    # and the fact removal stays in effect
    branch = world.undo(_branch_revs(world, "E"))
    assert [(c.table, c.thing_id) for c in branch.conflicts] == [("things", oskar)]

    report = world.undo([removed])

    assert report.reverted == 1
    assert _fact_texts(world, oskar)[ferry] == "A ferryman."


def test_reundo_after_netting_blocked_by_removed_thing_restores(world, maren):
    # pins: a later thing removal blocks the child slot (REMOVED_LATER)
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        rev.correct_fact(maren.laugh, text="A slow laugh.")
        rev.create_thing("character", fields={"name": "Oskar"})
        corrected = rev.rev
    with world.revision(Source.scene("s1", "E", "m2")) as rev:
        rev.remove_fact(maren.laugh)
        removed = rev.rev
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(maren.id)
        maren_removed = rev.rev
    # the laugh slot can't get its original back with Maren gone, so this
    # leaves the slot alone, the correction-and-removal pair included
    branch = world.undo([corrected, removed])
    assert [(c.table, c.reason) for c in branch.conflicts] == [
        ("facts", "removed in a later revision")
    ]
    world.undo([maren_removed])

    report = world.undo([removed])

    assert report.reverted == 1
    assert _fact_texts(world, maren.id)[maren.laugh] == "A slow laugh."


def test_reundo_after_netting_blocked_by_newer_value_restores(world, maren):
    # pins: a CHANGED_LATER conflict blocks the undo on that slot
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        rev.set_field(maren.id, "name", "Maren Vell", WorldDate.of(317))
        rev.create_thing("character", fields={"name": "Oskar"})
        renamed = rev.rev
    with world.revision(Source.scene("s1", "E", "m2")) as rev:
        rev.remove_field_value(maren.id, "name", WorldDate.of(317))
        cleared = rev.rev
    fixed = _set_name(world, maren.id, "Maren Ash")
    # a later hand edit holds the slot, so this leaves it alone
    branch = world.undo([renamed, cleared])
    assert [(c.table, c.reason, c.later_rev) for c in branch.conflicts] == [
        ("field_values", "changed again in a later revision", fixed)
    ]
    world.undo([fixed])
    assert _name(world, maren.id) is None

    report = world.undo([cleared])

    assert report.reverted == 1
    assert _name(world, maren.id) == "Maren Vell"


def test_undo_records_its_conflicts(world, maren):
    with world.revision(Source.manual()) as rev:
        fact_id = rev.add_fact(maren.id, "background", "Sailed the northern sea.")
        added = rev.rev
    with world.revision(Source.manual()) as rev:
        rev.correct_fact(fact_id, text="Sailed the southern sea.")
        rev.add_fact(maren.id, "personality", "Restless.")
    with world.revision(Source.manual()) as rev:
        rev.remove_fact(maren.eye)
        eye_removed = rev.rev

    report = world.undo([added, eye_removed])

    assert len(report.conflicts) == 1
    rows = world._conn.execute(
        "SELECT table_name, row_id FROM undo_conflicts WHERE undo_rev = ?",
        (report.undo_rev,),
    ).fetchall()
    assert [tuple(r) for r in rows] == [("facts", report.conflicts[0].row_id)]


def test_undo_after_redone_removal_lists_the_removal(world, oskar_and_home):
    oskar, home = oskar_and_home
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        rev.set_field(oskar, "heritage", home, None)
        target = rev.rev
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(oskar)
        removed = rev.rev
    restored = world.undo([removed])
    world.undo([restored.undo_rev])
    assert world.view().thing(oskar) is None

    report = world.undo([target])

    # the redo put the removal back in effect, so this is the same conflict
    # as without the undo and redo in between
    assert report.undo_rev is None
    assert [(c.table, c.reason, c.later_rev) for c in report.conflicts] == [
        ("field_values", "removed in a later revision", removed)
    ]


def test_redo_of_one_undo_leaves_a_change_another_undo_reverts(world, maren):
    # pins: a revision stays reverted while any undo in effect for the slot reverts it
    first = _correct(world, maren.laugh, "A slow laugh.", Source.scene("s1", "E", "m1"))
    second = _correct(
        world, maren.laugh, "A rare laugh.", Source.scene("s1", "E", "m2")
    )
    with world.revision(Source.manual()) as rev:
        rev.add_fact(maren.id, "background", "Sailed the northern sea.")
        other = rev.rev
    netting = world.undo([first, second])
    assert _fact_texts(world, maren.id)[maren.laugh] == "A quick laugh."
    # a no-op for the laugh, but it reverts the pair all the same
    again = world.undo([first, second, other])
    assert again.reverted == 1

    # redoing the first undo changes nothing: the second still reverts the
    # pair, so it writes no revision
    assert world.undo([netting.undo_rev]).undo_rev is None
    assert world.undo([second]).undo_rev is None
    assert _fact_texts(world, maren.id)[maren.laugh] == "A quick laugh."

    # with the second redone, the first still reverts the pair
    assert world.undo([again.undo_rev]).reverted == 1
    assert _fact_texts(world, maren.id)[maren.laugh] == "A quick laugh."

    # and redoing the first as well puts it back in effect
    world.undo([netting.undo_rev])
    assert _fact_texts(world, maren.id)[maren.laugh] == "A rare laugh."
    report = world.undo([second])
    assert report.conflicts == []
    assert _fact_texts(world, maren.id)[maren.laugh] == "A slow laugh."


def test_reundo_after_redo_of_a_later_removal_is_noop(world, oskar_and_home):
    oskar, home = oskar_and_home
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        rev.remove_thing(oskar)
        target = rev.rev
    world.undo([target])
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(oskar)
        removed_again = rev.rev
    restored = world.undo([removed_again])
    # redoing that puts the later removal back, not the target's
    world.undo([restored.undo_rev])
    assert world.view().thing(oskar) is None

    report = world.undo([target])

    assert (report.undo_rev, report.reverted, report.conflicts) == (None, 0, [])
    assert world.view().thing(oskar) is None


def test_undoing_a_redo_keeps_a_change_undone_since(world, oskar_and_home):
    oskar, home = oskar_and_home
    with world.revision(Source.scene("s1", "E", "m1")) as rev:
        rev.set_field(oskar, "heritage", home, None)
        target = rev.rev
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(oskar)
        removed = rev.rev
    restored = world.undo([removed])
    redo = world.undo([restored.undo_rev])
    world.undo([removed])
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(oskar)
        removed_again = rev.rev
    # brings Oskar back without the heritage: the target's write and the
    # removal of it cancel out
    world.undo([target, removed_again])
    assert "heritage" not in world.view().thing(oskar).fields

    # undoing the redo would restore the first undo's copy of the heritage,
    # but the target has been undone since
    world.undo([redo.undo_rev])

    assert "heritage" not in world.view().thing(oskar).fields


def test_redo_restores_a_fact_its_undo_never_wrote(world):
    # Shape A: undo[2,3] retires B but writes nothing for F (r4 already
    # retired it), and undo[1,4] leaves F alone too, since B is gone; redoing
    # undo[2,3] puts r3 back in effect and r4 stays undone, so F is live
    with world.revision(Source.manual()) as rev:
        rev.create_thing("character", {"name": "A"})
        create_a = rev.rev
    with world.revision(Source.manual()) as rev:
        b = rev.create_thing("character", {"name": "B"})
        create_b = rev.rev
    with world.revision(Source.manual()) as rev:
        fact = rev.add_fact(b, "appearance", "F")
        added = rev.rev
    with world.revision(Source.manual()) as rev:
        rev.remove_fact(fact)
        removed = rev.rev
    first = world.undo([create_b, added])
    assert first.conflicts == []
    second = world.undo([create_a, removed])
    assert second.conflicts == []
    assert world.view().thing(b) is None

    report = world.undo([first.undo_rev])

    assert report.conflicts == []
    assert _fact_texts(world, b) == {fact: "F"}
    assert world.view().thing(b).fields["name"] == "B"


def test_undo_uncovers_a_write_between_two_targets(world, maren):
    # R9: T1, N (outside), T2, then undo [T1, T2] gives N's value, quietly
    t1 = _set_name(world, maren.id, "T1", Source.scene("s1", "E", "m1"))
    n = _set_name(world, maren.id, "N")
    t2 = _set_name(world, maren.id, "T2", Source.scene("s1", "E", "m2"))

    report = world.undo([t1, t2])

    assert report.conflicts == []
    assert report.reverted == 2
    assert _name(world, maren.id) == "N"
    # and N itself is still undoable to the value before T1
    assert world.undo([n]).conflicts == []
    assert _name(world, maren.id) == "Maren the Grey"


def test_undo_lists_a_write_after_the_last_target(world, maren):
    # R9's other side: N after both targets is a later change
    t1 = _set_name(world, maren.id, "T1", Source.scene("s1", "E", "m1"))
    t2 = _set_name(world, maren.id, "T2", Source.scene("s1", "E", "m2"))
    n = _set_name(world, maren.id, "N")

    report = world.undo([t1, t2])

    assert report.undo_rev is None
    assert [(c.table, c.reason, c.later_rev) for c in report.conflicts] == [
        ("field_values", "changed again in a later revision", n)
    ]
    assert _name(world, maren.id) == "N"


def test_revision_rejects_an_undo_source(world, maren):
    # only `World.undo` may write an undo revision: replay never counts an
    # undo revision's rows as writes, so a hand-made one would be lost
    head = world.head_rev()
    with pytest.raises(ValueError):
        with world.revision(Source(kind="undo")) as rev:
            rev.add_fact(maren.id, "appearance", "A scar.")
    assert world.head_rev() == head
    assert world.revisions()[-1].source.kind != "undo"


# the undo-of-undo chain is longer than Python's recursion limit allowed the
# old recursive in-effect walk to follow (it failed at about 330 levels)
CHAIN = 600


def test_long_undo_redo_chain_on_one_slot(world, maren):
    last = _set_name(world, maren.id, "Maren Vell")
    for _ in range(CHAIN):
        last = world.undo([last]).undo_rev

    # an even number of undos leaves the rename in effect
    assert _name(world, maren.id) == "Maren Vell"
    assert world.undo([last]).reverted == 2
    assert _name(world, maren.id) == "Maren the Grey"
