"""`world`: a fresh `World` in a temp directory, same as `tests/world/conftest.py`
(not shared across directories by pytest's fixture scoping, so repeated here),
and `heritage_world`, a small species/race lineage for one character, filed
in a culture."""

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
    """Vasha, a Snowy (a race of the Owl-folk species) filed in the
    Riverfolk culture (lore tagged culture), born 978, whose own blue eyes
    override Snowy's yellow ones."""

    with world.revision(Source.manual(note="heritage")) as rev:
        owl_folk = rev.create_thing(
            "species", fields={"name": "Owl-folk", "lifespan": 70, "adult_age": 12}
        )
        wings = rev.add_fact(owl_folk, "physical", "Wings in place of arms.")
        hunts = rev.add_fact(owl_folk, "instinct", "Hunts at dusk.")
        snowy = rev.create_thing("race", fields={"name": "Snowy", "species": owl_folk})
        yellow_eyes = rev.add_fact(snowy, "physical", "Yellow eyes.")
        plumage = rev.add_fact(snowy, "variation", "White plumage.")
        riverfolk = rev.create_thing(
            "lore", fields={"name": "Riverfolk", "tag": "culture", "hint": "culture"}
        )
        customs = rev.add_fact(riverfolk, "general", "Name their boats.")
        vasha = rev.create_thing(
            "character",
            fields={
                "name": "Vasha",
                "born": WorldDate.of(978),
                "heritage": snowy,
                "filings": [{"target": riverfolk, "role": "of this culture"}],
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


def _in(target, role=None, since=None, until=None):
    """One filing into `target`, as `filings` stores it."""

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
    """The spheres probe's world, small, filed (it was spheres until
    Filing, Task 7): the Tsardom of Moscavia (a place written with the
    nation hint, everyday "Moscavia") holding Kremova; the White Dawn (religion lore, summary
    cached as its description prose) with a doctrine entry whose text
    opens with its name, a belief it holds, Dawn Peak as a holy site and
    two dated facts; the Council of Elders, lore filed in the Dawn; the
    Iron Guild, touched by nothing; Vasha, a practitioner of the Dawn
    since 1010 with two exceptions (worded as character creation writes
    them), and Brenna, an elder of the Council."""

    from talemate.world.refs import ref

    with world.revision(Source.manual(note="spheres")) as rev:
        tsardom = rev.create_thing(
            "place",
            fields={
                "name": "Tsardom of Moscavia",
                "hint": "nation",
                "aka": [{"name": "Moscavia", "tag": "common", "everyday": True}],
            },
        )
        rev.add_fact(tsardom, "description", "Cold forests and frozen rivers.")
        rev.add_fact(tsardom, "about", "A northern realm of owl-folk.")
        rev.add_fact(tsardom, "statement", "Only owl-folk may hold land.")
        rev.add_fact(
            tsardom, "timeline", "Crowned the first Tsar.", valid_from=WorldDate.of(990)
        )
        kremova = rev.create_thing(
            "place",
            fields={"name": "Kremova", "filings": [_in(tsardom)]},
        )
        rev.add_fact(kremova, "description", "The white city.")

        dawn = rev.create_thing(
            "lore", fields={"name": "The White Dawn", "hint": "religion"}
        )
        rev.add_fact(dawn, "general", "A faith of the dawn.")
        dawn_peak = rev.create_thing(
            "place", fields={"name": "Dawn Peak", "filings": [_in(dawn)]}
        )
        separation = rev.create_thing(
            "lore",
            fields={"name": "The Doctrine of Separation", "filings": [_in(dawn)]},
        )
        rev.add_fact(
            separation,
            "general",
            "The Doctrine of Separation forbids the faithful to marry humans.",
        )
        superiority = rev.add_fact(
            dawn, "belief", "Snowy owl-folk are the purest of the folk."
        )
        rev.add_fact(
            dawn,
            "general",
            "Declared the Night of Feathers a purification.",
            valid_from=WorldDate.of(994),
        )
        rev.add_fact(
            dawn,
            "general",
            "Issued the Doctrine of Separation.",
            valid_from=WorldDate.of(1019),
        )

        council = rev.create_thing(
            "lore",
            fields={"name": "The Council of Elders", "filings": [_in(dawn)]},
        )
        rev.add_fact(council, "general", "Seven elders seated in Kremova.")

        guild = rev.create_thing("lore", fields={"name": "The Iron Guild"})
        rev.add_fact(guild, "general", "Smiths of the far south.")

        vasha = rev.create_thing("character", fields={"name": "Vasha"})
        doubts = rev.add_fact(
            vasha,
            "ties",
            "Doesn't believe snowy owl-folk are superior. Departs from a "
            f"teaching of {ref(dawn, 'The White Dawn')}",
            origin={"rejects_fact": superiority},
        )
        marries = rev.add_fact(
            vasha,
            "ties",
            "Means to marry a human. Departs from "
            f"{ref(separation, 'The Doctrine of Separation')}",
        )
        # her filing's "but..." exceptions, as character creation files them
        rev.set_field(
            vasha,
            "filings",
            [
                {
                    **_in(dawn, "practitioner", since=WorldDate.of(1010)),
                    "exceptions": [doubts, marries],
                }
            ],
            None,
        )
        brenna = rev.create_thing(
            "character",
            fields={"name": "Brenna", "filings": [_in(council, "elder")]},
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


class ScribeWorld(NamedTuple):
    tsardom: str
    velikoye: str
    academy: str
    runes: str
    order: str
    post: str
    anastasiya: str
    ilya: str
    oleg: str
    vasha: str
    wattle_row: str


@pytest.fixture
def scribe_world(world):
    """Probe 5's scene, small and filed only (no old structure): the
    Academy, filed in Velikoye and in Runic Magic; Velikoye in the
    Tsardom; Wattle Row, a street of Velikoye, whose opening Velikoye's
    own timeline tells again; the Talon-Scribe Order, with Anastasiya
    Koroleva its chief scribe, Ilya a member and Oleg its ward; Vasha, a
    courier of the Northern Postal Authority."""

    from talemate.world.refs import ref

    with world.revision(Source.manual(note="scribes")) as rev:
        tsardom = rev.create_thing(
            "place",
            fields={
                "name": "Tsardom of Moscavia",
                "tag": "nation",
                "aka": [{"name": "Moscavia", "tag": "common", "everyday": True}],
            },
        )
        rev.add_fact(tsardom, "description", "A northern realm of owl-folk.")
        rev.add_fact(
            tsardom,
            "history",
            "Crowned the first Tsar.",
            valid_from=WorldDate.of(990),
        )
        velikoye = rev.create_thing(
            "place",
            fields={"name": "Velikoye", "tag": "city", "filings": [_in(tsardom)]},
        )
        rev.add_fact(velikoye, "description", "The river capital.")
        rev.add_fact(
            velikoye,
            "history",
            "Wattle Row opened its first workshops.",
            valid_from=WorldDate.of(998),
        )
        wattle_row = rev.create_thing(
            "place",
            fields={"name": "Wattle Row", "tag": "street", "filings": [_in(velikoye)]},
        )
        rev.add_fact(
            wattle_row,
            "history",
            "Wattle Row opened its first workshops by the river.",
            valid_from=WorldDate.of(998),
        )
        runes = rev.create_thing("lore", fields={"name": "Runic Magic", "tag": "field"})
        rev.add_fact(runes, "general", "Runes are cut, never painted.")
        academy = rev.create_thing(
            "place",
            fields={
                "name": "The Academy",
                "tag": "academy",
                "filings": [_in(velikoye), _in(runes, "school of")],
            },
        )
        rev.add_fact(academy, "description", "A courtyard of training stones.")
        order = rev.create_thing(
            "lore", fields={"name": "Talon-Scribe Order", "tag": "order"}
        )
        rev.add_fact(order, "general", f"Keeps the rune census of {ref(tsardom)}.")
        post = rev.create_thing(
            "lore", fields={"name": "Northern Postal Authority", "tag": "service"}
        )
        rev.add_fact(post, "general", "Carries sealed letters by wing.")
        anastasiya = rev.create_thing(
            "character",
            fields={
                "name": "Anastasiya Koroleva",
                "filings": [_in(order, "Chief Scribe")],
            },
        )
        rev.add_fact(
            anastasiya,
            "appearance",
            "A tawny-brown owl-folk with burnt-orange eyes.",
        )
        ilya = rev.create_thing(
            "character",
            fields={"name": "Ilya", "filings": [_in(order, "member")]},
        )
        rev.add_fact(ilya, "appearance", "A grey owl-folk.")
        oleg = rev.create_thing(
            "character",
            fields={"name": "Oleg", "filings": [_in(order, "ward")]},
        )
        rev.add_fact(oleg, "appearance", "A fledgling.")
        vasha = rev.create_thing(
            "character",
            fields={"name": "Vasha", "filings": [_in(post, "courier")]},
        )
        rev.add_fact(vasha, "appearance", "A snowy owl-folk.")

    return ScribeWorld(
        tsardom=tsardom,
        velikoye=velikoye,
        academy=academy,
        runes=runes,
        order=order,
        post=post,
        anastasiya=anastasiya,
        ilya=ilya,
        oleg=oleg,
        vasha=vasha,
        wattle_row=wattle_row,
    )
