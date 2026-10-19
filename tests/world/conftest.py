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
