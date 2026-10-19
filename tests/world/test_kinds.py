import pytest

from talemate.world.kinds import get_kind
from talemate.world.refs import parse_refs, ref


def test_kinds_table():
    character = get_kind("character")
    assert [f.name for f in character.fields] == [
        "name",
        "born",
        "culture",
        "voice",
        "color",
    ]
    assert [f.type for f in character.fields] == [
        "text",
        "date",
        "thing",
        "json",
        "text",
    ]
    assert character.categories == [
        "appearance",
        "personality",
        "background",
        "ability",
        "relationship",
        "speech",
    ]

    with pytest.raises(KeyError):
        get_kind("magic")


def test_parse_refs_dedupes_in_order():
    a = "11111111111111111111111111111111"
    b = "22222222222222222222222222222222"
    text = f"{ref(a)} met {ref(b)} again, then {ref(a)} left."
    assert parse_refs(text) == [a, b]
