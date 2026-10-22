"""Nearness: what's near an entry, ranked from the links between entries
(references, part of, parent and child, ties, heritage), and the curation
settings a world keeps."""

import pytest
from pydantic import ValidationError

from talemate.world.dates import WorldDate
from talemate.world.nearness import WEIGHTS, CurationSettings, near
from talemate.world.refs import ref
from talemate.world.store import Source, World

DRAWER = "d0000001"


def _part_of(sphere):
    return {"sphere": sphere, "drawer": DRAWER}


def _tie(sphere, role="member", since=None, until=None):
    return {
        "sphere": sphere,
        "role": role,
        "since": since.model_dump(mode="json") if since else None,
        "until": until.model_dump(mode="json") if until else None,
    }


def _sphere(rev, name):
    return rev.create_thing(
        "sphere",
        fields={
            "name": name,
            "template": "order",
            "drawers": [{"id": DRAWER, "type": "people", "title": "Members"}],
        },
    )


def _ids(found):
    return [n.thing_id for n in found]


def test_near_follows_links_both_ways(world):
    with world.revision(Source.manual()) as rev:
        tsardom = rev.create_thing("place", fields={"name": "Tsardom"})
        moskov = rev.create_thing("place", fields={"name": "Moskov", "parent": tsardom})
        order = _sphere(rev, "White Talon")
        bell = rev.create_thing(
            "item", fields={"name": "Bell", "part_of": _part_of(order)}
        )
        vasha = rev.create_thing(
            "character", fields={"name": "Vasha", "ties": [_tie(order)]}
        )
        owl = rev.create_thing("species", fields={"name": "Owl-folk"})
        snowy = rev.create_thing("race", fields={"name": "Snowy", "species": owl})
        brenna = rev.create_thing("character", fields={"name": "Brenna"})
        rev.add_fact(brenna, "background", f"Born in {ref(moskov)}.")
        rev.create_thing("lore", fields={"name": "Unrelated"})

    view = world.view()
    # reference: owner -> target and target -> owner
    assert brenna in _ids(near(view, moskov, reach=1))
    assert moskov in _ids(near(view, brenna, reach=1))
    # place parent and child
    assert tsardom in _ids(near(view, moskov, reach=1))
    assert moskov in _ids(near(view, tsardom, reach=1))
    # part of, both ways
    assert order in _ids(near(view, bell, reach=1))
    assert bell in _ids(near(view, order, reach=1))
    # a tie, both ways
    assert order in _ids(near(view, vasha, reach=1))
    assert vasha in _ids(near(view, order, reach=1))
    # heritage, both ways
    assert owl in _ids(near(view, snowy, reach=1))
    assert snowy in _ids(near(view, owl, reach=1))

    assert set(_ids(near(view, order, reach=1))) == {bell, vasha}
    # the start is never in its own list
    assert order not in _ids(near(view, order, reach=3))


def test_near_scores_part_of_above_reference(world):
    with world.revision(Source.manual()) as rev:
        order = _sphere(rev, "White Talon")
        # named "A..." so a name-order tie-break would put it first
        archive = rev.create_thing("lore", fields={"name": "Archive"})
        rite = rev.create_thing(
            "lore", fields={"name": "Rite", "part_of": _part_of(order)}
        )
        rev.add_fact(order, "about", f"Keeps the {ref(archive)}.")

    found = near(world.view(), order)
    assert _ids(found) == [rite, archive]
    assert found[0].score == pytest.approx(WEIGHTS["part_of"])
    assert found[1].score == pytest.approx(WEIGHTS["reference"])
    assert found[0].score > found[1].score
    assert [n.steps for n in found] == [1, 1]


def test_near_respects_reach_and_limit(world):
    with world.revision(Source.manual()) as rev:
        a = rev.create_thing("place", fields={"name": "A"})
        b = rev.create_thing("place", fields={"name": "B", "parent": a})
        c = rev.create_thing("place", fields={"name": "C", "parent": b})
        d = rev.create_thing("place", fields={"name": "D", "parent": c})
        e = rev.create_thing("lore", fields={"name": "E"})
        rev.add_fact(e, "general", f"Of {ref(d)}.")
        # two children of A, equal scores: ordered by name
        z = rev.create_thing("place", fields={"name": "Zed", "parent": a})
        y = rev.create_thing("place", fields={"name": "Yew", "parent": a})

    view = world.view()
    assert _ids(near(view, a, reach=1)) == [b, y, z]
    two = near(view, a, reach=2)
    # equal scores, so name order: C (two steps) sits between B and Yew
    assert _ids(two) == [b, c, y, z]
    assert two[1].steps == 2
    three = near(view, a, reach=3)
    assert _ids(three) == [b, c, d, y, z]
    assert d not in _ids(two)
    # a path's score is the product of its links' weights
    four = near(view, a, reach=4)
    assert four[-1].thing_id == e
    assert four[-1].score == pytest.approx(
        WEIGHTS["parent"] ** 3 * WEIGHTS["reference"]
    )
    assert four[-1].steps == 4

    assert _ids(near(view, a, reach=3, limit=2)) == [b, c]
    assert near(view, a, limit=0) == []


def test_near_keeps_best_path(world):
    """A thing reached both by a short weak path and a longer strong one
    keeps the better score, with that path's steps."""

    with world.revision(Source.manual()) as rev:
        a = rev.create_thing("place", fields={"name": "A"})
        b = rev.create_thing("place", fields={"name": "B", "parent": a})
        c = rev.create_thing("place", fields={"name": "C", "parent": b})
        rev.add_fact(a, "general", f"Near {ref(c)}.")

    found = {n.thing_id: n for n in near(world.view(), a, reach=2)}
    assert found[c].score == pytest.approx(WEIGHTS["parent"] ** 2)
    assert found[c].steps == 2


def test_isolated_entry(world):
    with world.revision(Source.manual()) as rev:
        alone = rev.create_thing("lore", fields={"name": "Alone"})
        rev.add_fact(alone, "general", "Nobody else here.")
        rev.create_thing("lore", fields={"name": "Other"})

    assert near(world.view(), alone) == []
    assert near(world.view(), "0" * 32) == []


def test_deleted_things_never_near(world):
    with world.revision(Source.manual()) as rev:
        a = rev.create_thing("place", fields={"name": "A"})
        b = rev.create_thing("place", fields={"name": "B", "parent": a})
        c = rev.create_thing("place", fields={"name": "C", "parent": b})
        r = rev.create_thing("lore", fields={"name": "R"})
        rev.add_fact(a, "general", f"Mentions {ref(r)}.")
        before = rev.rev

    with world.revision(Source.manual()) as rev:
        rev.remove_thing(b)
        rev.remove_thing(r)

    view = world.view()
    # b is gone, so it neither shows nor bridges a to c; r is gone though
    # a's fact still references it
    assert near(view, a, reach=3) == []
    assert near(view, b) == []
    assert near(view, c) == []
    # an earlier revision still sees them
    assert set(_ids(near(world.view(rev=before), a))) == {b, c, r}


def test_near_reads_the_view_date(world):
    with world.revision(Source.manual()) as rev:
        order = _sphere(rev, "White Talon")
        bell = rev.create_thing(
            "item",
            fields={"name": "Bell", "part_of": _part_of(order)},
            valid_from=WorldDate.of(100),
        )
        rev.set_field(bell, "part_of", None, WorldDate.of(200))
        vasha = rev.create_thing(
            "character",
            fields={
                "name": "Vasha",
                "ties": [_tie(order, since=WorldDate.of(150), until=WorldDate.of(250))],
            },
        )
        scroll = rev.create_thing("lore", fields={"name": "Scroll"})
        rev.add_fact(
            scroll,
            "general",
            f"Kept by {ref(order)}.",
            valid_from=WorldDate.of(120),
            valid_until=WorldDate.of(180),
        )

    def at(year):
        return set(_ids(near(world.view(at=WorldDate.of(year)), order)))

    assert at(50) == set()
    assert at(110) == {bell}
    assert at(160) == {bell, vasha, scroll}
    assert at(210) == {vasha}
    assert at(300) == set()
    # the latest telling: no ended links
    assert set(_ids(near(world.view(), order))) == set()


def test_curation_settings_round_trip(world, tmp_path):
    assert world.curation() == CurationSettings()
    defaults = world.curation()
    assert (
        defaults.reach,
        defaults.entries,
        defaults.facts_per_entry,
        defaults.repeat_threshold,
        defaults.timeline_reach,
    ) == (2, 12, 6, 0.4, 2)

    tuned = CurationSettings(
        reach=3, entries=20, facts_per_entry=4, repeat_threshold=0.5, timeline_reach=1
    )
    world.set_curation(tuned)
    assert world.curation() == tuned

    path = world.path
    world.close()
    reopened = World.open(path)
    try:
        assert reopened.curation() == tuned
    finally:
        reopened.close()

    for bad in (0, 4):
        with pytest.raises(ValidationError):
            CurationSettings(reach=bad)
