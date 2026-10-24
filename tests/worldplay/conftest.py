"""`world`: a fresh `World` in a temp directory, same as `tests/world/conftest.py`
(not shared across directories by pytest's fixture scoping, so repeated here),
and `heritage_world`, a small species/race/culture lineage for one character."""

from typing import NamedTuple

import pytest

from talemate.world.dates import WorldDate
from talemate.world.store import Source, World


@pytest.fixture
def world(tmp_path):
    w = World.create("Test World", root=tmp_path)
    yield w
    w.close()


class HeritageWorld(NamedTuple):
    owl_folk: str
    snowy: str
    riverfolk: str
    vasha: str
    wings: str
    hunts: str
    yellow_eyes: str
    plumage: str
    customs: str
    blue_eyes: str


@pytest.fixture
def heritage_world(world):
    """Vasha, a Snowy (a race of the Owl-folk species) of the Riverfolk
    culture, born 978, whose own blue eyes override Snowy's yellow ones."""

    with world.revision(Source.manual(note="heritage")) as rev:
        owl_folk = rev.create_thing(
            "species", fields={"name": "Owl-folk", "lifespan": 70, "adult_age": 12}
        )
        wings = rev.add_fact(owl_folk, "physical", "Wings in place of arms.")
        hunts = rev.add_fact(owl_folk, "instinct", "Hunts at dusk.")
        snowy = rev.create_thing("race", fields={"name": "Snowy", "species": owl_folk})
        yellow_eyes = rev.add_fact(snowy, "physical", "Yellow eyes.")
        plumage = rev.add_fact(snowy, "variation", "White plumage.")
        riverfolk = rev.create_thing("culture", fields={"name": "Riverfolk"})
        customs = rev.add_fact(riverfolk, "customs", "Name their boats.")
        vasha = rev.create_thing(
            "character",
            fields={
                "name": "Vasha",
                "born": WorldDate.of(978),
                "heritage": snowy,
                "culture": riverfolk,
            },
        )
        blue_eyes = rev.add_fact(
            vasha, "appearance", "Blue eyes.", overrides=[yellow_eyes]
        )
        rev.add_fact(vasha, "personality", "Quiet and observant.")

    return HeritageWorld(
        owl_folk=owl_folk,
        snowy=snowy,
        riverfolk=riverfolk,
        vasha=vasha,
        wings=wings,
        hunts=hunts,
        yellow_eyes=yellow_eyes,
        plumage=plumage,
        customs=customs,
        blue_eyes=blue_eyes,
    )


class SpheresWorld(NamedTuple):
    tsardom: str
    kremova: str
    dawn_peak: str
    dawn: str
    separation: str
    superiority: str
    council: str
    guild: str
    vasha: str
    brenna: str


def _drawer(drawer_id, type_, title):
    return {"id": drawer_id, "type": type_, "title": title}


def _tie(sphere, role, since=None, until=None):
    return {
        "sphere": sphere,
        "role": role,
        "since": since.model_dump(mode="json") if since else None,
        "until": until.model_dump(mode="json") if until else None,
    }


def _in(target, role=None, since=None, until=None):
    """One filing into `target`, as `filings` stores it: the world's
    readers (nearness, timelines) read these, the old `part_of`, `parent`
    and ties beside them only feeding what still reads those until Task
    7."""

    return {
        "target": target,
        "role": role,
        "since": since.model_dump(mode="json") if since else None,
        "until": until.model_dump(mode="json") if until else None,
        "within": None,
        "exceptions": [],
    }


@pytest.fixture
def spheres_world(world):
    """The spheres probe's world, small: the Tsardom of Moscavia (a nation
    place sphere, everyday "Moscavia") holding Kremova; the White Dawn (a
    religion, summary cached as its description prose) with a doctrine
    entry whose text opens with its name, a statement, Dawn Peak as a holy
    site and a dated timeline; the Council of Elders, an order sphere
    nested in the Dawn's Hierarchy; the Iron Guild, touched by nothing;
    Vasha, a practitioner of the Dawn since 1010 with two exceptions
    (worded as character creation writes them), and Brenna, an elder of
    the Council. Each `part_of`, `parent` and tie has its matching filing;
    the Dawn's beliefs statement is marked held by it."""

    from talemate.world.refs import ref

    with world.revision(Source.manual(note="spheres")) as rev:
        tsardom = rev.create_thing(
            "place",
            fields={
                "name": "Tsardom of Moscavia",
                "aka": [{"name": "Moscavia", "tag": "common", "everyday": True}],
                "template": "nation",
                "drawers": [
                    _drawer("d0000101", "beliefs", "Laws"),
                    _drawer("d0000102", "places", "Lands"),
                ],
            },
        )
        rev.add_fact(tsardom, "description", "Cold forests and frozen rivers.")
        rev.add_fact(tsardom, "about", "A northern realm of owl-folk.")
        rev.add_fact(
            tsardom,
            "statement",
            "Only owl-folk may hold land.",
            origin={"drawer": "d0000101"},
        )
        rev.add_fact(
            tsardom, "timeline", "Crowned the first Tsar.", valid_from=WorldDate.of(990)
        )
        kremova = rev.create_thing(
            "place",
            fields={"name": "Kremova", "parent": tsardom, "filings": [_in(tsardom)]},
        )
        rev.add_fact(kremova, "description", "The white city.")
        dawn_peak = rev.create_thing("place", fields={"name": "Dawn Peak"})

        dawn = rev.create_thing(
            "sphere",
            fields={
                "name": "The White Dawn",
                "template": "religion",
                "drawers": [
                    _drawer("d0000001", "beliefs", "Doctrines"),
                    _drawer("d0000002", "structure", "Hierarchy"),
                    _drawer("d0000003", "practices", "Rites and Ceremonies"),
                    _drawer("d0000004", "places", "Holy Sites"),
                ],
            },
        )
        rev.add_fact(dawn, "about", "A faith of the dawn.")
        separation = rev.create_thing(
            "lore",
            fields={
                "name": "The Doctrine of Separation",
                "part_of": {"sphere": dawn, "drawer": "d0000001"},
                "filings": [_in(dawn)],
            },
        )
        rev.add_fact(
            separation,
            "general",
            "The Doctrine of Separation forbids the faithful to marry humans.",
        )
        superiority = rev.add_fact(
            dawn,
            "statement",
            "Snowy owl-folk are the purest of the folk.",
            origin={"drawer": "d0000001", "held_by": dawn},
        )
        rev.set_field(
            dawn_peak, "part_of", {"sphere": dawn, "drawer": "d0000004"}, None
        )
        rev.set_field(dawn_peak, "filings", [_in(dawn)], None)
        rev.add_fact(
            dawn,
            "timeline",
            "Declared the Night of Feathers a purification.",
            valid_from=WorldDate.of(994),
        )
        rev.add_fact(
            dawn,
            "timeline",
            "Issued the Doctrine of Separation.",
            valid_from=WorldDate.of(1019),
        )

        council = rev.create_thing(
            "sphere",
            fields={
                "name": "The Council of Elders",
                "template": "order",
                "drawers": [_drawer("d0000201", "structure", "Ranks")],
                "part_of": {"sphere": dawn, "drawer": "d0000002"},
                "filings": [_in(dawn)],
            },
        )
        rev.add_fact(council, "about", "Seven elders seated in Kremova.")

        guild = rev.create_thing(
            "sphere", fields={"name": "The Iron Guild", "template": "order"}
        )
        rev.add_fact(guild, "about", "Smiths of the far south.")

        vasha = rev.create_thing(
            "character",
            fields={
                "name": "Vasha",
                "ties": [_tie(dawn, "practitioner", since=WorldDate.of(1010))],
                "filings": [_in(dawn, "practitioner", since=WorldDate.of(1010))],
            },
        )
        rev.add_fact(
            vasha,
            "ties",
            "Doesn't believe snowy owl-folk are superior. Departs from a "
            f"teaching of {ref(dawn, 'The White Dawn')}",
            origin={"rejects_fact": superiority},
        )
        rev.add_fact(
            vasha,
            "ties",
            "Means to marry a human. Departs from "
            f"{ref(separation, 'The Doctrine of Separation')}",
        )
        brenna = rev.create_thing(
            "character",
            fields={
                "name": "Brenna",
                "ties": [_tie(council, "elder")],
                "filings": [_in(council, "elder")],
            },
        )

    world.prose().put(
        dawn,
        "description",
        None,
        None,
        "The White Dawn is the state church of Moscavia.",
    )

    return SpheresWorld(
        tsardom=tsardom,
        kremova=kremova,
        dawn_peak=dawn_peak,
        dawn=dawn,
        separation=separation,
        superiority=superiority,
        council=council,
        guild=guild,
        vasha=vasha,
        brenna=brenna,
    )
