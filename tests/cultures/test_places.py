import pytest

from talemate.cultures.models import Culture, CultureShare, Language, Place
from talemate.cultures.places import (
    PlaceError,
    country_of,
    delete_place,
    describe_mix,
    effective_mix,
    reparent,
    set_share,
    set_shares,
)


def _place(id, name, kind, parent_id=None, cultures=None) -> Place:
    return Place(
        id=id,
        name=name,
        kind=kind,
        parent_id=parent_id,
        cultures=cultures or [],
    )


@pytest.fixture
def places() -> list[Place]:
    return [
        _place(
            "reach",
            "The Taelrik Reach",
            "country",
            cultures=[CultureShare(culture_id="taelrik", share=100)],
        ),
        _place("veldhaer", "Veldhaer", "town", parent_id="reach"),
        _place("quillister", "Quillister House", "building", parent_id="veldhaer"),
        _place(
            "dhunmouth",
            "Dhunmouth",
            "city",
            parent_id="reach",
            cultures=[
                CultureShare(culture_id="taelrik", share=55),
                CultureShare(culture_id="elsiri", share=30),
                CultureShare(culture_id="vaskari", share=15),
            ],
        ),
        _place(
            "birch",
            "Birch Coast",
            "region",
            parent_id="reach",
            cultures=[
                CultureShare(culture_id="elsiri", share=90),
                CultureShare(culture_id="taelrik", share=10),
            ],
        ),
        _place("ilsara", "Ilsara", "village", parent_id="birch"),
        _place(
            "khaz",
            "Khaz-Rull",
            "terrain",
            cultures=[CultureShare(culture_id="ghun", share=100)],
        ),
    ]


def _culture(id, name, language_name) -> Culture:
    return Culture(
        id=id,
        name=name,
        language=Language(name=language_name, level="naming"),
    )


@pytest.fixture
def cultures() -> dict[str, Culture]:
    by_id = [
        _culture("taelrik", "Taelrik", "Taelrik"),
        _culture("elsiri", "Elsiri", "Elsiri"),
        _culture("vaskari", "Vaskari", "Vaskari"),
        _culture("ghun", "Hollow Choir", "Ghûn"),
    ]
    return {c.id: c for c in by_id}


def test_inherits_from_nearest_ancestor(places):
    mix, source = effective_mix(places, "quillister")
    assert [cs.culture_id for cs in mix] == ["taelrik"]
    assert mix[0].share == 100
    assert source.id == "reach"


def test_pocket_overrides_parent(places):
    mix, source = effective_mix(places, "ilsara")
    assert {cs.culture_id for cs in mix} == {"elsiri", "taelrik"}
    assert source.id == "birch"


def test_root_without_cultures(places):
    lone_root = [_place("lonely", "Lonely Hill", "poi")]
    mix, source = effective_mix(lone_root, "lonely")
    assert mix == []
    assert source is None


def test_country_of(places):
    assert country_of(places, "ilsara").id == "reach"
    assert country_of(places, "khaz") is None


def test_reparent_into_descendant_rejected(places):
    with pytest.raises(PlaceError):
        reparent(places, "reach", "ilsara")


def test_set_shares_normalises(places):
    updated = set_shares(
        places,
        "dhunmouth",
        [
            CultureShare(culture_id="a", share=1),
            CultureShare(culture_id="b", share=1),
            CultureShare(culture_id="c", share=1),
            CultureShare(culture_id="d", share=0),
        ],
    )
    place = next(p for p in updated if p.id == "dhunmouth")
    assert [cs.culture_id for cs in place.cultures] == ["a", "b", "c"]
    assert [cs.share for cs in place.cultures] == [34, 33, 33]
    assert sum(cs.share for cs in place.cultures) == 100
    assert place.set_by == "owner"
    assert place.unsure is False


def test_delete_moves_children(places):
    updated = delete_place(places, "veldhaer", move_children_to="reach")
    assert not any(p.id == "veldhaer" for p in updated)
    quillister = next(p for p in updated if p.id == "quillister")
    assert quillister.parent_id == "reach"


def test_describe_mix_pocket(places, cultures):
    text = describe_mix(places, cultures, "birch")
    assert "about 9 in 10 Elsiri" in text
    assert "1 in 10 Taelrik" in text
    assert "Most also speak Taelrik, the language of The Taelrik Reach." in text


def test_inputs_not_mutated(places):
    original_dhunmouth = next(p for p in places if p.id == "dhunmouth")
    original_shares = list(original_dhunmouth.cultures)

    set_shares(
        places,
        "dhunmouth",
        [CultureShare(culture_id="a", share=1)],
    )

    after = next(p for p in places if p.id == "dhunmouth")
    assert after.cultures == original_shares


def test_set_share_keeps_one_and_scales_rest():
    single = [
        _place(
            "p",
            "Place",
            "town",
            cultures=[CultureShare(culture_id="elsiri", share=100)],
        )
    ]
    updated = set_share(single, "p", "taelrik", 55)
    place = next(p for p in updated if p.id == "p")
    shares = {cs.culture_id: cs.share for cs in place.cultures}
    assert shares == {"taelrik": 55, "elsiri": 45}

    mixed = [
        _place(
            "q",
            "Place",
            "town",
            cultures=[
                CultureShare(culture_id="a", share=50),
                CultureShare(culture_id="b", share=30),
                CultureShare(culture_id="c", share=20),
            ],
        )
    ]
    updated = set_share(mixed, "q", "a", 80)
    place = next(p for p in updated if p.id == "q")
    shares = {cs.culture_id: cs.share for cs in place.cultures}
    assert shares == {"a": 80, "b": 12, "c": 8}
    assert sum(shares.values()) == 100
