from dataclasses import dataclass

import pytest

from talemate.world.dates import WorldDate
from talemate.world.store import Source, World


@pytest.fixture
def world(tmp_path):
    w = World.create("Test World", root=tmp_path)
    yield w
    w.close()


@dataclass
class Maren:
    id: str
    tattoo: str
    warden: str
    laugh: str
    eye: str
    rev_created: int
    rev_eye: int
    rev_renamed: int


@pytest.fixture
def maren(world):
    """Maren, built across three revisions so revision-dependent tests have
    known rev numbers to view at. Tests needing more (Oskar, a prequel
    scar) add them themselves."""

    with world.revision(Source.manual(note="create Maren")) as rev:
        maren_id = rev.create_thing(
            "character",
            fields={"name": "Maren", "born": WorldDate.of(290)},
            valid_from=WorldDate.of(290),
        )
        tattoo = rev.add_fact(
            maren_id,
            "appearance",
            "A heron tattoo on her wrist.",
            valid_from=WorldDate.of(304),
        )
        warden = rev.add_fact(
            maren_id,
            "background",
            "Warden of the eastern gate.",
            valid_from=WorldDate.of(305),
            valid_until=WorldDate.of(316),
        )
        laugh = rev.add_fact(maren_id, "personality", "A quick laugh.")
        rev_created = rev.rev

    with world.revision(Source.manual(note="Maren loses an eye")) as rev:
        eye = rev.add_fact(
            maren_id,
            "appearance",
            "Lost her left eye.",
            valid_from=WorldDate.of(314),
        )
        rev_eye = rev.rev

    with world.revision(Source.manual(note="Maren the Grey")) as rev:
        rev.set_field(maren_id, "name", "Maren the Grey", WorldDate.of(317))
        rev_renamed = rev.rev

    return Maren(
        id=maren_id,
        tattoo=tattoo,
        warden=warden,
        laugh=laugh,
        eye=eye,
        rev_created=rev_created,
        rev_eye=rev_eye,
        rev_renamed=rev_renamed,
    )


@dataclass
class HeritageWorld:
    human: str
    orc: str
    owl_folk: str
    lowlander: str
    snowy: str
    half_orc: str
    riverfolk: str
    vasha: str
    brenna: str
    yellow_eyes: str
    wings: str
    customs: str


def _measure(name, lo, hi, unit="ft"):
    return {"name": name, "min": lo, "max": hi, "unit": unit}


@pytest.fixture
def heritage_world(world):
    """Three species, two races, a Half-orc mix of Lowlander and Orc, the
    Riverfolk culture (lore tagged culture), and two characters: Vasha
    (Snowy) and Brenna (Half-orc, filed in the Riverfolk)."""

    with world.revision(Source.manual(note="heritage")) as rev:
        human = rev.create_thing(
            "species",
            fields={
                "name": "Human",
                "lifespan": 75,
                "adult_age": 18,
                "measures": [_measure("height", 5, 6.5)],
            },
        )
        orc = rev.create_thing(
            "species",
            fields={
                "name": "Orc",
                "lifespan": 60,
                "adult_age": 14,
                "measures": [_measure("height", 6, 7.5)],
            },
        )
        owl_folk = rev.create_thing(
            "species",
            fields={
                "name": "Owl-folk",
                "lifespan": 70,
                "adult_age": 12,
                "measures": [_measure("wingspan", 7, 9), _measure("height", 4, 5)],
            },
        )
        wings = rev.add_fact(owl_folk, "physical", "Wings in place of arms.")
        lowlander = rev.create_thing(
            "race", fields={"name": "Lowlander", "species": human}
        )
        snowy = rev.create_thing(
            "race",
            fields={
                "name": "Snowy",
                "species": owl_folk,
                "measures": [_measure("wingspan", 8.5, 9)],
            },
        )
        yellow_eyes = rev.add_fact(snowy, "physical", "Yellow eyes.")
        half_orc = rev.create_thing(
            "mix", fields={"name": "Half-orc", "parents": [lowlander, orc]}
        )
        riverfolk = rev.create_thing(
            "lore", fields={"name": "Riverfolk", "tag": "culture", "hint": "culture"}
        )
        customs = rev.add_fact(riverfolk, "general", "Name their boats.")
        vasha = rev.create_thing(
            "character", fields={"name": "Vasha", "heritage": snowy}
        )
        brenna = rev.create_thing(
            "character",
            fields={
                "name": "Brenna",
                "heritage": half_orc,
                "filings": [{"target": riverfolk, "role": "of this culture"}],
            },
        )

    return HeritageWorld(
        human=human,
        orc=orc,
        owl_folk=owl_folk,
        lowlander=lowlander,
        snowy=snowy,
        half_orc=half_orc,
        riverfolk=riverfolk,
        vasha=vasha,
        brenna=brenna,
        yellow_eyes=yellow_eyes,
        wings=wings,
        customs=customs,
    )
