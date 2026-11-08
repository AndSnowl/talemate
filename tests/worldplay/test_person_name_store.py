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
    assert world.view().thing(me).fields["name_parts"]["parts"] == []


@pytest.fixture
def drassonais_id(world):
    from _people_names_helpers import DRASSONAIS
    from talemate.languages.entry import fields_of

    with world.revision(Source.manual()) as rev:
        return rev.create_thing(
            "language", {"name": "Drassonais", **fields_of(DRASSONAIS)}
        )


def test_a_merge_keeps_what_others_call_her_and_carries_no_parts(world, drassonais_id):
    """Final review I10: a stub folded into a person keeps its titles and
    pet names as they were, and its name parts don't land on the target."""

    from talemate.worldplay.repoint import repoint_stub

    with world.revision(Source.manual()) as rev:
        target = rev.create_thing("character", {"name": "Maëlis"})
        stub = rev.create_thing(
            "character",
            {
                "name": "Maëlis of Drassone",
                "stub": {"ignored": False},
                "name_parts": {**GOOD_PARTS, "language": drassonais_id},
                "aka": [
                    _aka("Lady of the Lake", kind="title", shown="before"),
                    _aka("Lisette", kind="pet", rule="pets"),
                ],
            },
        )
    repoint_stub(world, stub, target)
    state = world.view().thing(target)
    kinds = {a["name"]: a.get("kind") for a in state.fields.get("aka") or []}
    assert kinds["Lady of the Lake"] == "title" and kinds["Lisette"] == "pet"
    assert "name_parts" not in state.fields


def test_regnal_must_be_a_roman_numeral():
    validate_field(CHARACTER, "name_parts", {**GOOD_PARTS, "regnal": "III"})
    validate_field(CHARACTER, "name_parts", {**GOOD_PARTS, "regnal": ""})
    with pytest.raises(ValueError):
        validate_field(CHARACTER, "name_parts", {**GOOD_PARTS, "regnal": "the Third"})


def test_the_written_name_ends_with_its_regnal_number(world, drassonais_id):
    from talemate.languages.person_names import stored_written

    stored = {**GOOD_PARTS, "language": drassonais_id, "regnal": "II"}
    assert stored_written(world.view(), stored) == "Maëlis of Drassone II"
