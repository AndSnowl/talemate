"""Sphere data in the world store: the `sphere` kind, sphere fields on
places, part-of links on every kind, ties on characters, and a statement
fact's drawer origin."""

import pytest

from talemate.world.dates import WorldDate
from talemate.world.kinds import (
    DRAWER_TYPES,
    SPHERE_TEMPLATES,
    TEMPLATE_AGENT,
    get_kind,
    validate_field,
)
from talemate.world.store import Source

_SPHERE_ID = "1" * 32
_DRAWER_ID = "a" * 8


def test_sphere_kind_fields():
    sphere = get_kind("sphere")
    assert [f.name for f in sphere.fields] == [
        "name",
        "template",
        "agent",
        "drawers",
        "parent",
        "drops",
        "language",
        "aka",
        "stub",
        "part_of",
    ]
    assert [f.type for f in sphere.fields] == [
        "text",
        "text",
        "json",
        "json",
        "thing",
        "things",
        "json",
        "json",
        "json",
        "json",
    ]
    assert sphere.categories == ["timeline", "about", "statement"]


def test_place_takes_sphere_fields():
    place = get_kind("place")
    names = {f.name: f.type for f in place.fields}
    assert names["template"] == "text"
    assert names["agent"] == "json"
    assert names["drawers"] == "json"
    assert "statement" in place.categories


def test_template_and_agent_constants():
    assert SPHERE_TEMPLATES == (
        "religion",
        "nation",
        "order",
        "culture",
        "field",
        "other",
    )
    assert TEMPLATE_AGENT == {
        "religion": True,
        "nation": True,
        "order": True,
        "culture": False,
        "field": False,
        "other": False,
    }
    assert DRAWER_TYPES == (
        "people",
        "places",
        "practices",
        "beliefs",
        "knowledge",
        "structure",
        "branches",
        "events",
    )


def test_template_validated():
    sphere = get_kind("sphere")
    for template in SPHERE_TEMPLATES:
        validate_field(sphere, "template", template)

    with pytest.raises(ValueError):
        validate_field(sphere, "template", "guild")
    with pytest.raises(ValueError):
        validate_field(sphere, "template", 3)


def test_agent_field_is_bool():
    sphere = get_kind("sphere")
    validate_field(sphere, "agent", True)
    validate_field(sphere, "agent", False)
    with pytest.raises(ValueError):
        validate_field(sphere, "agent", "true")
    with pytest.raises(ValueError):
        validate_field(sphere, "agent", 1)


def test_drawers_validated():
    sphere = get_kind("sphere")
    validate_field(
        sphere,
        "drawers",
        [
            {"id": _DRAWER_ID, "type": "people", "title": "People"},
            {"id": "b" * 8, "type": "places", "title": "Places"},
        ],
    )

    # duplicate id
    with pytest.raises(ValueError):
        validate_field(
            sphere,
            "drawers",
            [
                {"id": _DRAWER_ID, "type": "people", "title": "People"},
                {"id": _DRAWER_ID, "type": "places", "title": "Places"},
            ],
        )

    # unknown type
    with pytest.raises(ValueError):
        validate_field(
            sphere,
            "drawers",
            [{"id": _DRAWER_ID, "type": "secrets", "title": "Secrets"}],
        )

    # blank title
    with pytest.raises(ValueError):
        validate_field(
            sphere,
            "drawers",
            [{"id": _DRAWER_ID, "type": "people", "title": "  "}],
        )

    # not a list
    with pytest.raises(ValueError):
        validate_field(sphere, "drawers", {"id": _DRAWER_ID})


def test_part_of_and_ties_shape():
    place = get_kind("place")
    validate_field(place, "part_of", None)
    validate_field(place, "part_of", {"sphere": _SPHERE_ID, "drawer": _DRAWER_ID})

    with pytest.raises(ValueError):
        validate_field(place, "part_of", {"sphere": _SPHERE_ID})
    with pytest.raises(ValueError):
        validate_field(place, "part_of", {"sphere": "short", "drawer": _DRAWER_ID})
    with pytest.raises(ValueError):
        validate_field(place, "part_of", {"sphere": _SPHERE_ID, "drawer": "zz"})
    with pytest.raises(ValueError):
        validate_field(place, "part_of", "none")

    character = get_kind("character")
    assert "part_of" in {f.name for f in character.fields}
    assert "ties" in {f.name for f in character.fields}
    assert "ties" in character.categories

    validate_field(character, "ties", [])
    validate_field(
        character,
        "ties",
        [
            {
                "sphere": _SPHERE_ID,
                "role": "founder",
                "since": WorldDate.of(12).model_dump(mode="json"),
                "until": None,
            }
        ],
    )
    validate_field(
        character,
        "ties",
        [
            {
                "sphere": _SPHERE_ID,
                "role": "founder",
                "since": WorldDate.of(12),
                "until": WorldDate.of(20),
            }
        ],
    )

    with pytest.raises(ValueError):
        validate_field(character, "ties", "not a list")
    with pytest.raises(ValueError):
        validate_field(
            character,
            "ties",
            [{"sphere": "short", "role": "founder", "since": None, "until": None}],
        )
    with pytest.raises(ValueError):
        validate_field(
            character,
            "ties",
            [{"sphere": _SPHERE_ID, "role": 3, "since": None, "until": None}],
        )
    with pytest.raises(ValueError):
        validate_field(
            character,
            "ties",
            [{"sphere": _SPHERE_ID, "role": "founder", "since": "bad"}],
        )


def test_every_kind_gains_part_of():
    from talemate.world.kinds import KINDS

    for kind in KINDS.values():
        types = {f.name: f.type for f in kind.fields}
        assert types.get("part_of") == "json", kind.name


def test_fact_origin_read_back(world):
    with world.revision(Source.manual(note="a sphere")) as rev:
        sphere_id = rev.create_thing(
            "sphere",
            fields={"name": "The Order of Ash", "template": "order", "agent": True},
        )
        fact_id = rev.add_fact(
            sphere_id,
            "statement",
            "Founded in the ash of the old capital.",
            origin={"drawer": _DRAWER_ID},
        )

    view = world.view()
    thing = view.thing(sphere_id)
    fact = next(f for f in thing.facts if f.fact_id == fact_id)
    assert fact.origin == {"drawer": _DRAWER_ID}


def test_fact_without_origin_is_none(world):
    with world.revision(Source.manual(note="plain fact")) as rev:
        lore_id = rev.create_thing("lore", fields={"name": "The Long Winter"})
        fact_id = rev.add_fact(lore_id, "general", "It lasted three years.")

    view = world.view()
    thing = view.thing(lore_id)
    fact = next(f for f in thing.facts if f.fact_id == fact_id)
    assert fact.origin is None
