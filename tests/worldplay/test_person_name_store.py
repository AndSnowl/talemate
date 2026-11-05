"""A person's name parts and the other names others call them
(languages 4b-2, Task 3): what the store accepts, and a rename that no
longer matches the parts clears them."""

import pytest

from talemate.world.kinds import get_kind, validate_field
from talemate.world.store import Source
from talemate.worldplay.repoint import rename_everywhere

HEX = "a" * 32
GOOD_PARTS = {
    "language": HEX,
    "rule": "noble-women",
    "shape": 0,
    "built_as": {"sex": "woman", "rank": "noble"},
    "parts": [
        {"label": "given", "text": "Maëlis", "source": "rolled"},
        {"label": "of", "text": "di", "source": "word"},
        {
            "label": "house",
            "text": "Drassone",
            "source": "inherited",
            "from_id": HEX,
            "from_role": "daughter of",
        },
    ],
}
CHARACTER = get_kind("character")


def _aka(name, **more):
    return {"name": name, "tag": "proper", "everyday": False, **more}


def test_name_parts_validate_and_reject_garbage():
    validate_field(CHARACTER, "name_parts", GOOD_PARTS)
    for bad in (
        {"parts": "Maëlis"},
        {**GOOD_PARTS, "shape": "0"},
        {**GOOD_PARTS, "parts": [{"label": "given", "text": "M", "source": "made up"}]},
        {**GOOD_PARTS, "built_as": {"sex": 1}},
    ):
        with pytest.raises(ValueError):
            validate_field(CHARACTER, "name_parts", bad)


def test_akas_with_by_survive_validation():
    validate_field(
        CHARACTER,
        "aka",
        [
            _aka("Lisette", kind="pet", rule="pets"),
            _aka("Maë", kind="own", by=HEX),
            _aka(
                "Car'a'carn",
                kind="title",
                by=HEX,
                meaning="chief of chiefs",
                language=HEX,
                shown="before",
            ),
        ],
    )
    with pytest.raises(ValueError):
        validate_field(
            CHARACTER,
            "aka",
            [
                _aka("A", kind="title", shown="before"),
                _aka("B", kind="title", shown="after"),
            ],
        )
    with pytest.raises(ValueError):
        validate_field(CHARACTER, "aka", [_aka("A", kind="nickname")])
    with pytest.raises(ValueError):
        validate_field(CHARACTER, "aka", [_aka("A", kind="own", by="nobody")])
    with pytest.raises(ValueError):
        validate_field(CHARACTER, "aka", [_aka("A", kind="pet", shown="before")])


def _maelis(world, lang_id):
    with world.revision(Source.manual()) as rev:
        me = rev.create_thing(
            "character",
            {
                "name": "Maëlis of Drassone",
                "name_parts": {**GOOD_PARTS, "language": lang_id},
            },
        )
    return me


def test_a_rename_that_matches_keeps_parts_and_one_that_doesnt_clears_them(
    world, drassonais_id
):
    me = _maelis(world, drassonais_id)
    with world.revision(Source.manual()) as rev:
        rename_everywhere(rev, world, me, "Maëlis of Drassone")
    assert "name_parts" in world.view().thing(me).fields
    with world.revision(Source.manual()) as rev:
        rename_everywhere(rev, world, me, "Maëlis the Red")
    assert "name_parts" not in world.view().thing(me).fields


@pytest.fixture
def drassonais_id(world):
    from _people_names_helpers import DRASSONAIS
    from talemate.languages.entry import fields_of

    with world.revision(Source.manual()) as rev:
        return rev.create_thing(
            "language", {"name": "Drassonais", **fields_of(DRASSONAIS)}
        )
