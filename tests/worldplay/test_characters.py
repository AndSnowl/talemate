"""Tests for `talemate.worldplay.characters`: building an ordinary
`Character` from a world thing as of a given date, with no model call."""

import pytest

from talemate.world.dates import WorldDate
from talemate.world.store import Source
from talemate.worldplay.characters import character_from_world, since_lines


@pytest.fixture
def oskar(world):
    """A simple character with no dated facts, so its whole timeline is one
    "always" stretch -- just enough to exercise field construction."""

    with world.revision(Source.manual(note="create Oskar")) as rev:
        thing_id = rev.create_thing(
            "character",
            fields={"name": "Oskar", "born": WorldDate.of(280)},
            valid_from=WorldDate.of(280),
        )
        rev.add_fact(thing_id, "speech", "Speaks slowly, weighing every word.")
        rev.add_fact(thing_id, "speech", '"I have seen worse winters."')

    world.prose().put(
        thing_id, "description", None, None, "A broad-shouldered woodsman."
    )
    world.prose().put(thing_id, "personality", None, None, "Patient and watchful.")

    return thing_id


def test_character_from_world_fields(world, oskar):
    character = character_from_world(world, oskar, WorldDate.of(320), is_player=False)

    assert character.name == "Oskar"
    assert character.base_attributes["age"] == 320 - 280
    assert character.base_attributes["born"] == "280"
    assert character.description == "A broad-shouldered woodsman."
    assert character.base_attributes["personality"] == "Patient and watchful."
    assert character.dialogue_instructions == "Speaks slowly, weighing every word."
    assert character.example_dialogue == ['"I have seen worse winters."']
    assert character.world_thing_id == oskar
    assert character.is_player is False


@pytest.fixture
def warden(world):
    """A character whose description is cached for the (304, 314) stretch
    -- before she loses an eye at 314 -- and never regenerated after."""

    with world.revision(Source.manual(note="create Elin")) as rev:
        thing_id = rev.create_thing(
            "character",
            fields={"name": "Elin", "born": WorldDate.of(290)},
            valid_from=WorldDate.of(290),
        )
        rev.add_fact(
            thing_id,
            "appearance",
            "A heron tattoo on her wrist.",
            valid_from=WorldDate.of(304),
        )

    with world.revision(Source.manual(note="Elin loses an eye")) as rev:
        rev.add_fact(
            thing_id,
            "appearance",
            "Lost her left eye.",
            valid_from=WorldDate.of(314),
        )

    world.prose().put(
        thing_id,
        "description",
        WorldDate.of(304),
        WorldDate.of(314),
        "A woman with a heron tattoo on her wrist.",
    )

    return thing_id


def test_character_before_and_after_fact(world, warden):
    before = character_from_world(world, warden, WorldDate.of(312), is_player=False)
    assert "eye" not in before.description

    after = character_from_world(world, warden, WorldDate.of(315), is_player=False)
    assert "A woman with a heron tattoo on her wrist." in after.description
    assert "Since 314: Lost her left eye." in after.description

    lines = since_lines(world, warden, WorldDate.of(315))
    assert lines == ["Since 314: Lost her left eye."]
    assert since_lines(world, warden, WorldDate.of(312)) == []
