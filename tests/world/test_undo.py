from talemate.world.dates import WorldDate
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
