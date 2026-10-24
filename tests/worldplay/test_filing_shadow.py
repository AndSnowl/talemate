"""Ruling F10's temporary dual-write (`worldplay.filing_shadow`): a writer
of the old fields also writes the matching filings, in its one revision,
until Task 4's single writer replaces it."""

from talemate.world.dates import WorldDate
from talemate.world.entries import held_by
from talemate.world.filing import filed_in, filings_of
from talemate.world.store import Source
from talemate.worldplay.filing_shadow import shadowed_revision, statement_origin

DOCTRINES = "d0000001"
LAWS = "d0000002"


def _targets(world, thing_id, at=None):
    return [
        (f.target, f.role, f.since, f.within)
        for f in filings_of(world.view(at), thing_id, live=False)
    ]


def test_old_fields_are_mirrored_in_filings(world):
    with world.revision(Source.manual()) as rev:
        dawn = rev.create_thing("sphere", fields={"name": "Dawn", "drawers": []})
        tsardom = rev.create_thing("place", fields={"name": "Tsardom"})
    with shadowed_revision(world, Source.manual()) as rev:
        peak = rev.create_thing(
            "place",
            fields={
                "name": "Peak",
                "parent": tsardom,
                "part_of": {"sphere": dawn, "drawer": "unsorted"},
            },
        )
        reformed = rev.create_thing(
            "sphere", fields={"name": "Reformed", "parent": dawn}
        )
        vasha = rev.create_thing(
            "character",
            fields={
                "name": "Vasha",
                "ties": [
                    {
                        "sphere": dawn,
                        "role": "practitioner",
                        "since": WorldDate.of(1010).model_dump(mode="json"),
                        "until": None,
                        "within": reformed,
                    }
                ],
            },
        )
        shadowed = rev.rev

    assert _targets(world, peak) == [
        (dawn, None, None, None),
        (tsardom, None, None, None),
    ]
    assert _targets(world, reformed) == [(dawn, "branch of", None, None)]
    # Reformed sits in the Dawn, so it's a part Vasha can be within
    assert _targets(world, vasha) == [
        (dawn, "practitioner", WorldDate.of(1010), reformed)
    ]

    # a dated end of part_of ends the filing at that date
    with shadowed_revision(world, Source.manual()) as rev:
        rev.set_field(peak, "part_of", None, WorldDate.of(1100))
        ended = rev.rev
    assert [t[0] for t in _targets(world, peak, WorldDate.of(1050))] == [
        dawn,
        tsardom,
    ]
    assert [t[0] for t in _targets(world, peak, WorldDate.of(1200))] == [tsardom]
    assert shadowed < ended

    # one revision: undoing it takes back the filings it shadowed onto
    # the Peak, which was there before, with the old field
    report = world.undo([ended])
    assert report.undo_rev is not None
    for year in (1050, 1200):
        assert [t[0] for t in _targets(world, peak, WorldDate.of(year))] == [
            dawn,
            tsardom,
        ]
    dated = world.view(WorldDate.of(1200)).field_since(peak, "filings")
    assert dated is None


def test_undated_write_rebuilds_the_base_filings(world):
    """An undated write reads the base values, not the latest dated ones:
    the Bell, filed in A and ended there at 1100, then re-filed (undated)
    in B, is in B before 1100 and nowhere after it."""

    with world.revision(Source.manual()) as rev:
        a = rev.create_thing("sphere", fields={"name": "A", "drawers": []})
        b = rev.create_thing("sphere", fields={"name": "B", "drawers": []})
    with shadowed_revision(world, Source.manual()) as rev:
        bell = rev.create_thing(
            "item",
            fields={"name": "Bell", "part_of": {"sphere": a, "drawer": "unsorted"}},
        )
    with shadowed_revision(world, Source.manual()) as rev:
        rev.set_field(bell, "part_of", None, WorldDate.of(1100))
    with shadowed_revision(world, Source.manual()) as rev:
        rev.set_field(bell, "part_of", {"sphere": b, "drawer": "unsorted"}, None)

    assert [t[0] for t in _targets(world, bell, WorldDate.of(1050))] == [b]
    assert _targets(world, bell, WorldDate.of(1200)) == []
    assert [s.id for s, _ in filed_in(world.view(WorldDate.of(1050)), b)] == [bell]
    assert filed_in(world.view(WorldDate.of(1050)), a) == []


def test_beliefs_statement_marked_held_as_written(world):
    """The old rule's beliefs-drawer holding, written into the origin: a
    religion's Doctrines statement is held by it, a nation's Laws aren't."""

    with world.revision(Source.manual()) as rev:
        church = rev.create_thing(
            "sphere",
            fields={
                "name": "Church",
                "template": "religion",
                "drawers": [
                    {"id": DOCTRINES, "type": "beliefs", "title": "Doctrines"},
                    {"id": LAWS, "type": "practices", "title": "Rites"},
                ],
            },
        )
        nation = rev.create_thing(
            "sphere",
            fields={
                "name": "Nation",
                "template": "nation",
                "drawers": [{"id": LAWS, "type": "beliefs", "title": "Laws"}],
            },
        )
    view = world.view()
    assert statement_origin(view, church, DOCTRINES) == {
        "drawer": DOCTRINES,
        "held_by": church,
    }
    assert statement_origin(view, church, LAWS) == {"drawer": LAWS}
    assert statement_origin(view, nation, LAWS) == {"drawer": LAWS}

    with world.revision(Source.manual()) as rev:
        fact_id = rev.add_fact(
            church,
            "statement",
            "The Light is one.",
            origin=statement_origin(view, church, DOCTRINES),
        )
    owner = world.view().thing(church)
    fact = next(f for f in owner.facts if f.fact_id == fact_id)
    assert held_by(world.view(), fact, owner) == church
