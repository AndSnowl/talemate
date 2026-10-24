"""Nearness: what's near an entry, ranked from the links between entries
(references, filings, heritage), and the curation settings a world
keeps."""

import pytest
from pydantic import ValidationError

from talemate.world.dates import WorldDate
from talemate.world.nearness import WEIGHTS, CurationSettings, near
from talemate.world.refs import ref
from talemate.world.store import Source, World


def _in(target, role=None, since=None, until=None, within=None):
    """One filing into `target`, as `filings` stores it."""

    return {
        "target": target,
        "role": role,
        "since": since.model_dump(mode="json") if since else None,
        "until": until.model_dump(mode="json") if until else None,
        "within": within,
        "exceptions": [],
    }


def _filed(*targets):
    """`fields` filing a new thing in each of `targets`."""

    return [_in(target) for target in targets]


def _sphere(rev, name):
    return rev.create_thing("lore", fields={"name": name, "tag": "order"})


def _ids(found):
    return [n.thing_id for n in found]


def test_near_follows_filings_both_ways(world):
    with world.revision(Source.manual()) as rev:
        tsardom = rev.create_thing("place", fields={"name": "Tsardom"})
        moskov = rev.create_thing(
            "place", fields={"name": "Moskov", "filings": _filed(tsardom)}
        )
        order = _sphere(rev, "White Talon")
        bell = rev.create_thing(
            "item", fields={"name": "Bell", "filings": _filed(order)}
        )
        vasha = rev.create_thing(
            "character",
            fields={"name": "Vasha", "filings": [_in(order, role="member")]},
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
    # a place filed in a place, both ways
    assert tsardom in _ids(near(view, moskov, reach=1))
    assert moskov in _ids(near(view, tsardom, reach=1))
    # an item filed in an order, both ways
    assert order in _ids(near(view, bell, reach=1))
    assert bell in _ids(near(view, order, reach=1))
    # a person filed in it with a role, both ways
    assert order in _ids(near(view, vasha, reach=1))
    assert vasha in _ids(near(view, order, reach=1))
    # heritage, both ways
    assert owl in _ids(near(view, snowy, reach=1))
    assert snowy in _ids(near(view, owl, reach=1))

    assert set(_ids(near(view, order, reach=1))) == {bell, vasha}
    assert near(view, bell, reach=1)[0].score == pytest.approx(WEIGHTS["filing"])
    # the old structure links nothing any more
    assert set(WEIGHTS) == {"filing", "reference", "heritage"}
    # the start is never in its own list
    assert order not in _ids(near(view, order, reach=3))


def test_near_scores_filing_above_reference(world):
    with world.revision(Source.manual()) as rev:
        order = _sphere(rev, "White Talon")
        # named "A..." so a name-order tie-break would put it first
        archive = rev.create_thing("lore", fields={"name": "Archive"})
        rite = rev.create_thing(
            "lore", fields={"name": "Rite", "filings": _filed(order)}
        )
        rev.add_fact(order, "general", f"Keeps the {ref(archive)}.")

    found = near(world.view(), order)
    assert _ids(found) == [rite, archive]
    assert WEIGHTS["filing"] == 1.0
    assert found[0].score == pytest.approx(WEIGHTS["filing"])
    assert found[1].score == pytest.approx(WEIGHTS["reference"])
    assert found[0].score > found[1].score
    assert [n.steps for n in found] == [1, 1]


def test_near_respects_reach_and_limit(world):
    with world.revision(Source.manual()) as rev:
        a = rev.create_thing("place", fields={"name": "A"})
        b = rev.create_thing("place", fields={"name": "B", "filings": _filed(a)})
        c = rev.create_thing("place", fields={"name": "C", "filings": _filed(b)})
        d = rev.create_thing("place", fields={"name": "D", "filings": _filed(c)})
        e = rev.create_thing("lore", fields={"name": "E"})
        rev.add_fact(e, "general", f"Of {ref(d)}.")
        # two children of A, equal scores: ordered by name
        z = rev.create_thing("place", fields={"name": "Zed", "filings": _filed(a)})
        y = rev.create_thing("place", fields={"name": "Yew", "filings": _filed(a)})

    view = world.view()
    assert _ids(near(view, a, reach=1)) == [b, y, z]
    two = near(view, a, reach=2)
    # equal scores, so fewer steps first: C (two steps) comes after Yew
    # and Zed, then name order
    assert _ids(two) == [b, y, z, c]
    assert two[3].steps == 2
    three = near(view, a, reach=3)
    assert _ids(three) == [b, y, z, c, d]
    assert d not in _ids(two)
    # a path's score is the product of its links' weights
    four = near(view, a, reach=4)
    assert four[-1].thing_id == e
    assert four[-1].score == pytest.approx(
        WEIGHTS["filing"] ** 3 * WEIGHTS["reference"]
    )
    assert four[-1].steps == 4

    assert _ids(near(view, a, reach=3, limit=2)) == [b, y]
    assert near(view, a, limit=0) == []


def test_near_keeps_best_path(world):
    """A thing reached both by a short weak path and a longer strong one
    keeps the better score, with that path's steps."""

    with world.revision(Source.manual()) as rev:
        a = rev.create_thing("place", fields={"name": "A"})
        b = rev.create_thing("place", fields={"name": "B", "filings": _filed(a)})
        c = rev.create_thing("place", fields={"name": "C", "filings": _filed(b)})
        rev.add_fact(a, "general", f"Near {ref(c)}.")

    found = {n.thing_id: n for n in near(world.view(), a, reach=2)}
    assert found[c].score == pytest.approx(WEIGHTS["filing"] ** 2)
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
        b = rev.create_thing("place", fields={"name": "B", "filings": _filed(a)})
        c = rev.create_thing("place", fields={"name": "C", "filings": _filed(b)})
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
            fields={"name": "Bell", "filings": _filed(order)},
            valid_from=WorldDate.of(100),
        )
        # the Bell's filings, as dated values; Vasha's, by its own dates
        rev.set_field(bell, "filings", [], WorldDate.of(200))
        vasha = rev.create_thing(
            "character",
            fields={
                "name": "Vasha",
                "filings": [
                    _in(order, since=WorldDate.of(150), until=WorldDate.of(250))
                ],
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
        defaults.repeat_untick_threshold,
        defaults.date_threshold,
    ) == (1, 12, 6, 0.4, 2, 0.7, 0.5)

    tuned = CurationSettings(
        reach=3,
        entries=20,
        facts_per_entry=4,
        repeat_threshold=0.5,
        timeline_reach=1,
        repeat_untick_threshold=0.8,
        date_threshold=0.6,
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


def test_ignored_stub_never_near(world):
    with world.revision(Source.manual()) as rev:
        a = rev.create_thing("lore", fields={"name": "A"})
        ignored = rev.create_thing(
            "place", fields={"name": "Ignored", "stub": {"ignored": True}}
        )
        third = rev.create_thing(
            "place", fields={"name": "Third", "filings": _filed(ignored)}
        )
        plain = rev.create_thing(
            "lore", fields={"name": "Plain", "stub": {"ignored": False}}
        )
        rev.add_fact(a, "general", f"Of {ref(ignored)} and {ref(plain)}.")

    view = world.view()
    found = _ids(near(view, a, reach=3))
    assert ignored not in found
    assert third not in found
    # a plain stub stays near
    assert found == [plain]
    assert near(view, ignored) == []


def test_unnamed_things_sort_last(world):
    with world.revision(Source.manual()) as rev:
        a = rev.create_thing("place", fields={"name": "A"})
        unnamed = rev.create_thing("place", fields={"filings": _filed(a)})
        zed = rev.create_thing("place", fields={"name": "Zed", "filings": _filed(a)})

    assert _ids(near(world.view(), a)) == [zed, unnamed]


@pytest.mark.parametrize("stored", ["not json", '{"reach": 9}', '{"entries": "x"}'])
def test_unreadable_curation_falls_back_to_defaults(world, stored):
    world._set_meta("curation", stored)
    assert world.curation() == CurationSettings()


def test_being_filing_is_near_whatever_its_existence(world):
    """A being's filing links it like any entry's: a believed god filed in
    its faith is as near it as a real spirit (a tie, which counted only
    while the being was real, is gone with ties)."""

    with world.revision(Source.manual()) as rev:
        order = _sphere(rev, "White Talon")
        spirit = rev.create_thing(
            "being",
            fields={"name": "Spirit", "existence": "real", "filings": _filed(order)},
        )
        light = rev.create_thing(
            "being",
            fields={"name": "Light", "existence": "believed", "filings": _filed(order)},
        )

    view = world.view()
    assert {spirit, light} == set(_ids(near(view, order, reach=1)))
    assert order in _ids(near(view, spirit, reach=1))
    assert order in _ids(near(view, light, reach=1))


def test_person_within_a_part_is_near_it(world):
    """A person filed in the Tsar's Army within the White Talon is near
    both; a `within` whose part has left the target, or whose part's
    filing hasn't begun at the view's date, links only the target."""

    with world.revision(Source.manual()) as rev:
        army = _sphere(rev, "Tsar's Army")
        talon = rev.create_thing(
            "lore",
            fields={
                "name": "White Talon",
                "filings": [_in(army, since=WorldDate.of(900))],
            },
        )
        oleg = rev.create_thing(
            "character",
            fields={"name": "Oleg", "filings": [_in(army, within=talon)]},
        )

    view = world.view()
    assert set(_ids(near(view, oleg, reach=1))) == {army, talon}
    assert near(view, oleg, reach=1)[0].score == pytest.approx(WEIGHTS["filing"])
    # before the Talon was in the Army, Oleg is in the Army alone
    assert _ids(near(world.view(WorldDate.of(800)), oleg, reach=1)) == [army]
    with world.revision(Source.manual()) as rev:
        rev.set_field(talon, "filings", [], None)
    assert _ids(near(world.view(), oleg, reach=1)) == [army]


def test_ties_break_by_steps_then_references_then_name(world):
    """The curation probe's ranking fix: a direct reference (0.6, one step)
    ties a three-step path of 1.0 x 1.0 x 0.6 on score, and wins it on
    steps; among things tied on score and steps, more references between
    the two win over the name."""

    with world.revision(Source.manual()) as rev:
        # three steps, 1.0 x 1.0 x 0.6: A - Aa (filing) - Ab (filing) - Alpha
        aa = rev.create_thing("place", fields={"name": "Aa"})
        a = rev.create_thing("place", fields={"name": "A", "filings": _filed(aa)})
        ab = rev.create_thing("place", fields={"name": "Ab", "filings": _filed(aa)})
        alpha = rev.create_thing("lore", fields={"name": "Alpha"})
        rev.add_fact(ab, "general", f"Near {ref(alpha)}.")
        # one step at 0.6 each: Zulu named once, Yankee twice
        zulu = rev.create_thing("lore", fields={"name": "Zulu"})
        yankee = rev.create_thing("lore", fields={"name": "Yankee"})
        rev.add_fact(a, "general", f"Of {ref(zulu)} and {ref(yankee)}.")
        rev.add_fact(a, "general", f"Again {ref(yankee)}.")

    view = world.view()
    found = near(view, a, reach=3)
    order = _ids(found)
    scores = {n.thing_id: n for n in found}
    assert scores[alpha].score == pytest.approx(scores[zulu].score)
    assert scores[alpha].steps == 3
    # Yankee (two references) before Zulu (one), both before Alpha (three
    # steps) though "Alpha" sorts first by name
    assert order.index(yankee) < order.index(zulu) < order.index(alpha)


def test_siblings_capped_per_sphere(world):
    """Things filed in the same sphere as the one asked about, reached only
    through it, are kept at most `SIBLINGS` (3) per sphere: a fourth gives
    way to the entries the thing's own facts name. A sibling the thing
    links to itself isn't capped."""

    from talemate.world.nearness import SIBLINGS

    with world.revision(Source.manual()) as rev:
        church = _sphere(rev, "Church")
        doctrine = rev.create_thing(
            "lore", fields={"name": "Doctrine", "filings": _filed(church)}
        )
        siblings = [
            rev.create_thing(
                "lore", fields={"name": f"Rite {n}", "filings": _filed(church)}
            )
            for n in "ABCDE"
        ]
        named = rev.create_thing("place", fields={"name": "Zakonnik"})
        rev.add_fact(doctrine, "general", f"Read in {ref(named)}.")
        rev.add_fact(doctrine, "general", f"Sung at {ref(siblings[4])}.")

    view = world.view()
    found = _ids(near(view, doctrine, reach=2))
    assert SIBLINGS == 3
    assert found[0] == church
    # the three first siblings by name, the one it names itself, and the
    # entry its facts name
    assert set(found) == {church, *siblings[:3], siblings[4], named}
    assert siblings[3] not in found
    # uncapped, all five are there
    assert set(siblings) <= set(_ids(near(view, doctrine, reach=2, siblings=None)))
    # the sphere's own parts aren't siblings of it
    assert set(siblings) <= set(_ids(near(view, church, reach=1)))


def test_siblings_capped_per_shared_target(world):
    """An entry filed in two places has siblings in each: the cap is per
    shared target, so a custom in Velikoye and in Vosgrad keeps up to
    `SIBLINGS` from each."""

    with world.revision(Source.manual()) as rev:
        velikoye = rev.create_thing("place", fields={"name": "Velikoye"})
        vosgrad = rev.create_thing("place", fields={"name": "Vosgrad"})
        dance = rev.create_thing(
            "lore",
            fields={"name": "Feather Dance", "filings": _filed(velikoye, vosgrad)},
        )
        in_velikoye = [
            rev.create_thing(
                "lore", fields={"name": f"V{n}", "filings": _filed(velikoye)}
            )
            for n in range(5)
        ]
        in_vosgrad = [
            rev.create_thing(
                "lore", fields={"name": f"W{n}", "filings": _filed(vosgrad)}
            )
            for n in range(5)
        ]

    found = set(_ids(near(world.view(), dance, reach=2, limit=50)))
    assert found == {velikoye, vosgrad, *in_velikoye[:3], *in_vosgrad[:3]}


def _counting_graphs(monkeypatch):
    """Count the graphs `near` builds (the cache emptied first)."""

    from talemate.world import nearness

    built = []
    real = nearness._graph

    def counted(view):
        built.append((view.rev, view.at))
        return real(view)

    nearness._GRAPHS.clear()
    monkeypatch.setattr(nearness, "_graph", counted)
    return built


def test_near_builds_one_graph_per_revision_and_date(world, monkeypatch):
    """One prompt asks nearness of a scene's place and each of its cast:
    the graph is built once per (world, revision, date), and a new
    revision or another date builds its own."""

    built = _counting_graphs(monkeypatch)
    with world.revision(Source.manual()) as rev:
        moskov = rev.create_thing("place", fields={"name": "Moskov"})
        brenna = rev.create_thing("character", fields={"name": "Brenna"})
        rev.add_fact(brenna, "background", f"Born in {ref(moskov)}.")

    first = near(world.view(), moskov, reach=1)
    assert _ids(near(world.view(), brenna, reach=1)) == [moskov]
    assert _ids(near(world.view(), moskov, reach=1)) == _ids(first) == [brenna]
    assert len(built) == 1

    near(world.view(WorldDate.of(500)), moskov, reach=1)
    assert len(built) == 2

    with world.revision(Source.manual()) as rev:
        vasha = rev.create_thing("character", fields={"name": "Vasha"})
        rev.add_fact(vasha, "background", f"Lives in {ref(moskov)}.")
        latest = rev.rev
    assert set(_ids(near(world.view(), moskov, reach=1))) == {brenna, vasha}
    assert len(built) == 3
    # an older revision is still its own graph, and still as it was
    assert _ids(near(world.view(rev=latest - 1), moskov, reach=1)) == [brenna]


def test_near_never_caches_inside_an_open_revision(world, monkeypatch):
    built = _counting_graphs(monkeypatch)
    with world.revision(Source.manual()) as rev:
        moskov = rev.create_thing("place", fields={"name": "Moskov"})
    with world.revision(Source.manual()) as rev:
        brenna = rev.create_thing("character", fields={"name": "Brenna"})
        rev.add_fact(brenna, "background", f"Born in {ref(moskov)}.")
        inside = world.view(rev=rev.rev)
        assert _ids(near(inside, moskov, reach=1)) == [brenna]
        assert _ids(near(inside, moskov, reach=1)) == [brenna]
        assert len(built) == 2
    # nothing from inside was kept: after it's written, it's built afresh
    assert _ids(near(world.view(), moskov, reach=1)) == [brenna]
    assert len(built) == 3


def test_near_after_undo_builds_a_new_graph(world, monkeypatch):
    built = _counting_graphs(monkeypatch)
    with world.revision(Source.manual()) as rev:
        moskov = rev.create_thing("place", fields={"name": "Moskov"})
        brenna = rev.create_thing("character", fields={"name": "Brenna"})
    with world.revision(Source.manual()) as rev:
        linked = rev.rev
        rev.add_fact(brenna, "background", f"Born in {ref(moskov)}.")
    assert _ids(near(world.view(), moskov, reach=1)) == [brenna]
    assert len(built) == 1
    report = world.undo([linked])
    assert report.undo_rev is not None
    assert _ids(near(world.view(), moskov, reach=1)) == []
    assert len(built) == 2
