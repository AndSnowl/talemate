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
