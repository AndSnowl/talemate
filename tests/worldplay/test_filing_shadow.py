"""Ruling F10's temporary dual-write (`worldplay.filing_shadow`): a writer
of the old fields also writes the matching filings, in its one revision,
until Task 4's single writer replaces it."""

from talemate.world.dates import WorldDate
from talemate.world.entries import held_by
from talemate.world.filing import filings_of
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
    assert [t[0] for t in _targets(world, peak, WorldDate.of(1050))] == [
        dawn,
        tsardom,
    ]
    assert [t[0] for t in _targets(world, peak, WorldDate.of(1200))] == [tsardom]

    # one revision: undoing it takes the filings back with the old fields
    world.undo([shadowed])
    assert world.view().thing(vasha) is None


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
