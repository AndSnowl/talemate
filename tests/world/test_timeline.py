import pytest

from talemate.world.dates import WorldDate
from talemate.world.store import Source


def test_timeline_order(world, maren):
    entries = world.timeline(maren.id)

    actual = [
        (
            e.date.instant if e.date else None,
            e.change,
            e.field if e.change == "field" else e.fact_id,
        )
        for e in entries
    ]
    assert actual == [
        (None, "fact_start", maren.laugh),
        (WorldDate.of(290).instant, "field", "born"),
        (WorldDate.of(290).instant, "field", "name"),
        (WorldDate.of(304).instant, "fact_start", maren.tattoo),
        (WorldDate.of(305).instant, "fact_start", maren.warden),
        (WorldDate.of(314).instant, "fact_start", maren.eye),
        (WorldDate.of(316).instant, "fact_end", maren.warden),
        (WorldDate.of(317).instant, "field", "name"),
    ]

    warden_end = next(e for e in entries if e.change == "fact_end")
    assert warden_end.fact_id == maren.warden
    assert warden_end.source_rev == maren.rev_created


def test_timeline_carries_source(world, maren):
    with world.revision(Source.scene("s1", "b1", "m9")) as rev:
        fact_id = rev.add_fact(maren.id, "background", "Recruited into the guard.")

    entries = world.timeline(maren.id)
    entry = next(e for e in entries if e.fact_id == fact_id)

    assert entry.source.kind == "scene"
    assert entry.source.scene_id == "s1"
    assert entry.source.branch_id == "b1"
    assert entry.source.message_id == "m9"


def test_timeline_excludes_retired_rows(world, maren):
    with world.revision(Source.manual(note="correct born date")) as rev:
        rev.set_field(maren.id, "born", WorldDate.of(291), WorldDate.of(290))

    before = world.timeline(maren.id, rev=maren.rev_renamed)
    after = world.timeline(maren.id)

    born_before = [e for e in before if e.field == "born"]
    born_after = [e for e in after if e.field == "born"]

    assert len(born_before) == 1
    assert born_before[0].value == WorldDate.of(290)

    assert len(born_after) == 1
    assert born_after[0].value == WorldDate.of(291)


def test_timeline_missing_thing_raises(world):
    with pytest.raises(KeyError):
        world.timeline("0" * 32)
