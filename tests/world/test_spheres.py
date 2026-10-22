"""Sphere resolution: drawers, items (with branch inheritance), people from
ties, territory, timeline, ties, exceptions and key facts, all read through
a `WorldView`."""

from dataclasses import dataclass

import pytest

from talemate.world.dates import WorldDate
from talemate.world.kinds import DRAWER_TYPES, SPHERE_TEMPLATES
from talemate.world.spheres import (
    TEMPLATE_DRAWERS,
    UNSORTED,
    Drawer,
    drawers,
    exceptions,
    is_sphere,
    items,
    key_facts,
    people,
    territory,
    ties_of,
    timeline,
)
from talemate.world.store import Source

DOCTRINES = "d0000001"
HIERARCHY = "d0000002"
RITES = "d0000003"
PEOPLE = "d0000004"
HOLY_SITES = "d0000005"
EVENTS = "d0000006"
REFORMED_DOCTRINES = "d0000007"
LANDS = "d0000008"
GOVERNMENT = "d0000009"


def _drawer(drawer_id, type_, title):
    return {"id": drawer_id, "type": type_, "title": title}


def _tie(sphere, role, since=None, until=None):
    return {
        "sphere": sphere,
        "role": role,
        "since": since.model_dump(mode="json") if since else None,
        "until": until.model_dump(mode="json") if until else None,
    }


@dataclass
class Spheres:
    dawn: str
    reformed: str
    council: str
    feather_rite: str
    dawn_peak: str
    tsardom: str
    kovask: str
    little_kovask: str
    vasha: str
    brenna: str
    superiority: str
    prayers: str
    equality: str
    founded: str
    purification: str
    separation: str
    split: str
    about: str
    exception: str
    skips_prayers: str
    unrelated_tie: str


@pytest.fixture
def spheres(world):
    """The White Dawn (a religion) with a Hierarchy holding the Council of
    Elders, rites, two statements, a holy site and a timeline; its
    Reformed Dawn branch (split in 1010, dropping the Feather Rite and
    overriding the superiority doctrine); the Tsardom, a place sphere with
    two towns; Vasha, a practitioner since 1000 with exceptions, and
    Brenna, an elder from 980 to 1005."""

    with world.revision(Source.manual(note="spheres")) as rev:
        dawn = rev.create_thing(
            "sphere",
            fields={
                "name": "The White Dawn",
                "template": "religion",
                "agent": True,
                "drawers": [
                    _drawer(DOCTRINES, "beliefs", "Doctrines"),
                    _drawer(HIERARCHY, "structure", "Hierarchy"),
                    _drawer(RITES, "practices", "Rites and Ceremonies"),
                    _drawer(PEOPLE, "people", "People"),
                    _drawer(HOLY_SITES, "places", "Holy Sites"),
                    _drawer(EVENTS, "events", "Timeline"),
                ],
            },
        )
        about = rev.add_fact(dawn, "about", "A faith of the snowy owl-folk.")
        superiority = rev.add_fact(
            dawn,
            "statement",
            "Snowy owl-folk are the purest of the folk.",
            origin={"drawer": DOCTRINES},
        )
        prayers = rev.add_fact(
            dawn,
            "statement",
            "Prayers at first light.",
            origin={"drawer": RITES},
        )
        founded = rev.add_fact(
            dawn, "timeline", "Founded at Dawn Peak.", valid_from=WorldDate.of(900)
        )
        purification = rev.add_fact(
            dawn,
            "timeline",
            "Declared the transformation a purification.",
            valid_from=WorldDate.of(994),
        )
        separation = rev.add_fact(
            dawn,
            "timeline",
            "Issued the Doctrine of Separation.",
            valid_from=WorldDate.of(1019),
        )
        council = rev.create_thing(
            "lore",
            fields={
                "name": "The Council of Elders",
                "part_of": {"sphere": dawn, "drawer": HIERARCHY},
            },
        )
        rev.add_fact(council, "general", "Seven elders rule the faith.")
        feather_rite = rev.create_thing(
            "lore",
            fields={
                "name": "The Feather Rite",
                "part_of": {"sphere": dawn, "drawer": RITES},
                "stub": {"ignored": False},
            },
        )

        reformed = rev.create_thing(
            "sphere",
            fields={
                "name": "The Reformed Dawn",
                "template": "religion",
                "agent": True,
                "drawers": [
                    _drawer(REFORMED_DOCTRINES, "beliefs", "Reformed Doctrines"),
                    _drawer(EVENTS, "events", "Our Timeline"),
                ],
                "drops": [feather_rite],
            },
        )
        rev.set_field(reformed, "parent", dawn, WorldDate.of(1010))
        equality = rev.add_fact(
            reformed,
            "statement",
            "All owl-folk are equal.",
            origin={"drawer": REFORMED_DOCTRINES},
            overrides=[superiority],
        )
        split = rev.add_fact(
            reformed,
            "timeline",
            "Split from [[thing:%s|the White Dawn]]." % dawn,
            valid_from=WorldDate.of(1010),
        )

        tsardom = rev.create_thing(
            "place",
            fields={
                "name": "The Tsardom",
                "template": "nation",
                "drawers": [
                    _drawer(LANDS, "places", "Lands"),
                    _drawer(GOVERNMENT, "structure", "Government"),
                ],
            },
        )
        kovask = rev.create_thing("place", fields={"name": "Kovask", "parent": tsardom})
        little_kovask = rev.create_thing(
            "place", fields={"name": "Little Kovask", "parent": kovask}
        )
        dawn_peak = rev.create_thing(
            "place",
            fields={
                "name": "Dawn Peak",
                "parent": kovask,
                "part_of": {"sphere": dawn, "drawer": HOLY_SITES},
            },
        )

        vasha = rev.create_thing(
            "character",
            fields={
                "name": "Vasha",
                "ties": [_tie(dawn, "practitioner", since=WorldDate.of(1000))],
            },
        )
        exception = rev.add_fact(
            vasha,
            "ties",
            "Doesn't believe [[thing:%s|the White Dawn]]'s doctrine that snowy "
            "owl-folk are superior." % dawn,
            origin={"rejects_fact": superiority},
        )
        skips_prayers = rev.add_fact(
            vasha,
            "ties",
            "Sleeps through the morning prayers.",
            origin={"rejects_fact": prayers},
        )
        unrelated_tie = rev.add_fact(
            vasha, "ties", "Never sets foot in [[thing:%s]]." % tsardom
        )
        brenna = rev.create_thing(
            "character",
            fields={
                "name": "Brenna",
                "ties": [
                    _tie(
                        dawn, "elder", since=WorldDate.of(980), until=WorldDate.of(1005)
                    ),
                    _tie(reformed, "founder", since=WorldDate.of(1010)),
                ],
            },
        )

    return Spheres(
        dawn=dawn,
        reformed=reformed,
        council=council,
        feather_rite=feather_rite,
        dawn_peak=dawn_peak,
        tsardom=tsardom,
        kovask=kovask,
        little_kovask=little_kovask,
        vasha=vasha,
        brenna=brenna,
        superiority=superiority,
        prayers=prayers,
        equality=equality,
        founded=founded,
        purification=purification,
        separation=separation,
        split=split,
        about=about,
        exception=exception,
        skips_prayers=skips_prayers,
        unrelated_tie=unrelated_tie,
    )


def _by_drawer(found):
    grouped: dict[str, set[str]] = {}
    for item in found:
        grouped.setdefault(item.drawer_id, set()).add(item.thing_id or item.fact_id)
    return grouped


def test_is_sphere(world, spheres):
    s = spheres
    view = world.view()

    assert is_sphere(view.thing(s.dawn))
    assert is_sphere(view.thing(s.tsardom))
    assert not is_sphere(view.thing(s.kovask))
    assert not is_sphere(view.thing(s.council))


def test_items_by_drawer(world, spheres):
    s = spheres
    view = world.view()
    found = items(view, s.dawn)

    assert _by_drawer(found) == {
        DOCTRINES: {s.superiority},
        HIERARCHY: {s.council},
        RITES: {s.feather_rite, s.prayers},
        HOLY_SITES: {s.dawn_peak},
    }
    by_id = {item.thing_id or item.fact_id: item for item in found}
    council = by_id[s.council]
    assert council.fact_id is None
    assert council.name == "The Council of Elders"
    assert council.text == "Seven elders rule the faith."
    assert council.source_id == s.dawn
    assert not council.inherited
    assert not council.stub
    assert by_id[s.feather_rite].stub
    assert by_id[s.feather_rite].text == ""
    statement = by_id[s.superiority]
    assert statement.thing_id is None
    assert statement.text == "Snowy owl-folk are the purest of the folk."
    assert not statement.stub


def test_drawers_own_then_inherited(world, spheres):
    s = spheres
    view = world.view()

    assert [d.id for d in drawers(view, s.dawn)][:2] == [DOCTRINES, HIERARCHY]
    branch = drawers(view, s.reformed)
    # its own first; EVENTS is its own (retitled), not inherited again
    assert [d.id for d in branch] == [
        REFORMED_DOCTRINES,
        EVENTS,
        DOCTRINES,
        HIERARCHY,
        RITES,
        PEOPLE,
        HOLY_SITES,
    ]
    assert branch[1] == Drawer(id=EVENTS, type="events", title="Our Timeline")


def test_branch_inherits_and_drops(world, spheres):
    s = spheres
    view = world.view()
    found = items(view, s.reformed)
    by_id = {item.thing_id or item.fact_id: item for item in found}

    # the dropped Feather Rite and the overridden doctrine are gone
    assert s.feather_rite not in by_id
    assert s.superiority not in by_id
    assert set(by_id) == {s.equality, s.council, s.prayers, s.dawn_peak}
    assert not by_id[s.equality].inherited
    assert by_id[s.equality].source_id == s.reformed
    assert by_id[s.council].inherited
    assert by_id[s.council].source_id == s.dawn
    assert by_id[s.council].drawer_id == HIERARCHY
    # the parent itself is untouched
    assert s.feather_rite in {item.thing_id for item in items(view, s.dawn)}


def test_branch_of_a_branch_keeps_drops(world, spheres):
    s = spheres
    with world.revision(Source.manual()) as rev:
        twig = rev.create_thing(
            "sphere",
            fields={"name": "The Twig", "template": "religion", "parent": s.reformed},
        )

    found = {item.thing_id or item.fact_id for item in items(world.view(), twig)}
    assert found == {s.equality, s.council, s.prayers, s.dawn_peak}


def test_branch_of_deleted_parent(world, spheres):
    s = spheres
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(s.dawn)

    view = world.view()
    found = items(view, s.reformed)

    assert {item.thing_id or item.fact_id for item in found} == {s.equality}
    assert [d.id for d in drawers(view, s.reformed)] == [REFORMED_DOCTRINES, EVENTS]
    assert [fact.fact_id for fact in timeline(view, s.reformed)] == [s.split]


def test_branch_parent_cycle(world, spheres):
    s = spheres
    with world.revision(Source.manual()) as rev:
        rev.set_field(s.dawn, "parent", s.reformed, None)

    view = world.view()
    branch = {item.thing_id or item.fact_id for item in items(view, s.reformed)}
    parent = {item.thing_id or item.fact_id for item in items(view, s.dawn)}

    assert branch == {s.equality, s.council, s.prayers, s.dawn_peak}
    # the Dawn now inherits from the Reformed Dawn, whose equality
    # overrides nothing of the Dawn's own
    assert s.superiority in parent
    assert s.equality in parent
    assert len(drawers(view, s.dawn)) == 7
    assert timeline(view, s.dawn)
    assert timeline(view, s.reformed)


def test_branch_does_not_inherit_itself(world, spheres):
    s = spheres
    with world.revision(Source.manual()) as rev:
        branches = "d000000a"
        rev.set_field(
            s.dawn,
            "drawers",
            [
                *[d.model_dump() for d in drawers(world.view(), s.dawn)],
                _drawer(branches, "branches", "Branches"),
            ],
            None,
        )
        rev.set_field(
            s.reformed, "part_of", {"sphere": s.dawn, "drawer": branches}, None
        )

    view = world.view()
    assert s.reformed in {item.thing_id for item in items(view, s.dawn)}
    assert s.reformed not in {item.thing_id for item in items(view, s.reformed)}


def test_items_of_removed_drawer_are_unsorted(world, spheres):
    s = spheres
    with world.revision(Source.manual()) as rev:
        kept = [
            d.model_dump()
            for d in drawers(world.view(), s.dawn)
            if d.id not in (HIERARCHY, DOCTRINES)
        ]
        rev.set_field(s.dawn, "drawers", kept, None)

    found = _by_drawer(items(world.view(), s.dawn))

    assert found[UNSORTED.id] == {s.council, s.superiority}
    assert HIERARCHY not in found
    assert UNSORTED == Drawer(id="unsorted", type="knowledge", title="Unsorted")


def test_ended_part_of_leaves_the_drawer(world, spheres):
    s = spheres
    with world.revision(Source.manual()) as rev:
        rev.set_field(s.council, "part_of", None, WorldDate.of(1015))

    def council_in(at):
        return s.council in {item.thing_id for item in items(world.view(at), s.dawn)}

    assert council_in(WorldDate.of(1012))
    assert not council_in(WorldDate.of(1016))


def test_people_from_ties_at_date(world, spheres):
    s = spheres

    def tied(at, sphere):
        return {(tie.character_id, tie.role) for tie in people(world.view(at), sphere)}

    assert tied(WorldDate.of(990), s.dawn) == {(s.brenna, "elder")}
    assert tied(WorldDate.of(1002), s.dawn) == {
        (s.brenna, "elder"),
        (s.vasha, "practitioner"),
    }
    assert tied(WorldDate.of(1006), s.dawn) == {(s.vasha, "practitioner")}
    assert tied(None, s.dawn) == {(s.vasha, "practitioner")}
    # a branch's members aren't its parent's
    assert tied(WorldDate.of(1012), s.reformed) == {(s.brenna, "founder")}

    tie = people(world.view(WorldDate.of(1002)), s.dawn)
    vasha = next(t for t in tie if t.character_id == s.vasha)
    assert vasha.sphere_id == s.dawn
    assert vasha.since == WorldDate.of(1000)
    assert vasha.until is None


def test_ties_of(world, spheres):
    s = spheres
    view = world.view(WorldDate.of(1012))

    all_ties = ties_of(view, s.brenna)
    assert [(t.sphere_id, t.role) for t in all_ties] == [
        (s.dawn, "elder"),
        (s.reformed, "founder"),
    ]
    assert all_ties[0].until == WorldDate.of(1005)
    assert [t.sphere_id for t in ties_of(view, s.brenna, live=True)] == [s.reformed]
    assert ties_of(view, s.dawn) == []
    assert ties_of(view, "f" * 32) == []


def test_place_sphere_territory_includes_towns(world, spheres):
    s = spheres
    view = world.view()

    assert set(territory(view, s.tsardom)) == {
        s.tsardom,
        s.kovask,
        s.little_kovask,
        s.dawn_peak,
    }
    assert territory(view, s.tsardom)[0] == s.tsardom
    # a sphere that isn't a place holds the places in its places drawer
    assert territory(view, s.dawn) == [s.dawn_peak]


def test_territory_holds_places_under_a_holy_site(world, spheres):
    s = spheres
    with world.revision(Source.manual()) as rev:
        shrine = rev.create_thing(
            "place", fields={"name": "The Shrine", "parent": s.dawn_peak}
        )
        # a lore item in the places drawer is not territory
        rev.create_thing(
            "lore",
            fields={
                "name": "The Pilgrim Road",
                "part_of": {"sphere": s.dawn, "drawer": HOLY_SITES},
            },
        )

    assert set(territory(world.view(), s.dawn)) == {s.dawn_peak, shrine}
    # inherited by the branch
    assert set(territory(world.view(), s.reformed)) == {s.dawn_peak, shrine}


def test_branch_timeline_cut_at_split(world, spheres):
    s = spheres
    view = world.view()

    assert [f.fact_id for f in timeline(view, s.dawn)] == [
        s.founded,
        s.purification,
        s.separation,
    ]
    # the parent's 1019 doctrine comes after the 1010 split
    assert [f.fact_id for f in timeline(view, s.reformed)] == [
        s.founded,
        s.purification,
        s.split,
    ]


def test_exceptions_by_ref(world, spheres):
    s = spheres
    with world.revision(Source.manual()) as rev:
        by_item = rev.add_fact(
            s.vasha, "ties", "Thinks [[thing:%s]] is too old." % s.council
        )

    view = world.view()
    found = [f.fact_id for f in exceptions(view, s.vasha, s.dawn)]

    assert set(found) == {s.exception, s.skips_prayers, by_item}
    assert s.unrelated_tie not in found
    # the branch overrode the superiority doctrine, so that rejection isn't
    # an exception there; the inherited council and prayers still are
    assert set(f.fact_id for f in exceptions(view, s.vasha, s.reformed)) == {
        s.skips_prayers,
        by_item,
    }


def test_key_facts_capped(world, spheres):
    s = spheres
    with world.revision(Source.manual()) as rev:
        for n in range(4):
            rev.add_fact(
                s.dawn,
                "statement",
                f"Doctrine {n}.",
                origin={"drawer": DOCTRINES},
            )
            rev.add_fact(s.dawn, "statement", f"Rite {n}.", origin={"drawer": RITES})
        for year in (1020, 1021):
            rev.add_fact(
                s.dawn, "timeline", f"Synod of {year}.", valid_from=WorldDate.of(year)
            )

    view = world.view()
    lines = key_facts(view, s.dawn)

    assert len(lines) == 8
    # the summary falls back to the first `about` fact
    assert lines[0] == "A faith of the snowy owl-folk."
    # then the latest three timeline facts, oldest first, at the end
    assert lines[-3:] == [
        "Issued the Doctrine of Separation.",
        "Synod of 1020.",
        "Synod of 1021.",
    ]
    middle = lines[1:-3]
    assert any("Doctrine" in line or "purest" in line for line in middle)
    assert any("Rite" in line or "Prayers" in line for line in middle)

    summarised = key_facts(view, s.dawn, summary="The church of the dawn.")
    assert summarised[0] == "The church of the dawn."
    assert len(summarised) == 8


def test_key_facts_small_sphere(world, spheres):
    s = spheres
    view = world.view()

    lines = key_facts(view, s.dawn)
    assert lines == [
        "A faith of the snowy owl-folk.",
        "Snowy owl-folk are the purest of the folk.",
        "The Feather Rite",
        "Prayers at first light.",
        "The Council of Elders: Seven elders rule the faith.",
        "Founded at Dawn Peak.",
        "Declared the transformation a purification.",
        "Issued the Doctrine of Separation.",
    ]
    # a missing sphere has none
    assert key_facts(view, "f" * 32) == []


def test_template_drawers():
    assert set(TEMPLATE_DRAWERS) == set(SPHERE_TEMPLATES)
    assert TEMPLATE_DRAWERS["religion"] == [
        ("beliefs", "Doctrines"),
        ("structure", "Hierarchy"),
        ("practices", "Rites and Ceremonies"),
        ("people", "People"),
        ("places", "Holy Sites"),
        ("events", "Timeline"),
    ]
    assert TEMPLATE_DRAWERS["nation"] == [
        ("structure", "Government"),
        ("beliefs", "Laws"),
        ("people", "People"),
        ("places", "Lands"),
        ("events", "Timeline"),
    ]
    assert TEMPLATE_DRAWERS["order"] == [
        ("structure", "Ranks"),
        ("knowledge", "Fields of Study"),
        ("practices", "Practices"),
        ("people", "Members"),
        ("places", "Sites"),
        ("events", "Timeline"),
    ]
    assert TEMPLATE_DRAWERS["culture"] == [
        ("practices", "Customs and Holidays"),
        ("beliefs", "Beliefs and Legends"),
        ("people", "People"),
        ("events", "Timeline"),
    ]
    assert TEMPLATE_DRAWERS["field"] == [
        ("knowledge", "Principles"),
        ("practices", "Techniques"),
        ("knowledge", "Frontier"),
        ("people", "Practitioners"),
        ("events", "Timeline"),
    ]
    assert TEMPLATE_DRAWERS["other"] == [("events", "Timeline")]
    for drawer_list in TEMPLATE_DRAWERS.values():
        assert all(type_ in DRAWER_TYPES for type_, _ in drawer_list)
