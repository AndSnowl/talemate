"""Tests for `talemate.worldplay.characters`: building an ordinary
`Character` from a world thing as of a given date, with no model call."""

import pytest

from talemate.world.dates import WorldDate
from talemate.world.store import Source
from talemate.worldplay.characters import character_from_world, since_lines


@pytest.fixture
def oskar(world):
    """A simple character with no dated facts beyond her own creation, so
    her timeline is two stretches -- `(None, 280)` and `(280, None)` --
    cached for the second (the real, open one `WorldDate.of(320)` falls
    in), just enough to exercise field construction."""

    with world.revision(Source.manual(note="create Oskar")) as rev:
        thing_id = rev.create_thing(
            "character",
            fields={"name": "Oskar", "born": WorldDate.of(280)},
            valid_from=WorldDate.of(280),
        )
        rev.add_fact(thing_id, "speech", "Speaks slowly, weighing every word.")
        rev.add_fact(thing_id, "speech", '"I have seen worse winters."')

    world.prose().put(
        thing_id, "description", WorldDate.of(280), None, "A broad-shouldered woodsman."
    )
    world.prose().put(
        thing_id, "personality", WorldDate.of(280), None, "Patient and watchful."
    )

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


@pytest.fixture
def herbalist(world):
    """A character with no `born` field, so her only timeline boundary is
    her own first fact's start -- her first stretch is `(None, 314)`, not
    the `(start, end)` shape every other fixture here happens to cache.
    Fix round 1 / Critical 2: the cache walk-back used to skip exactly
    this stretch."""

    with world.revision(Source.manual(note="create Sela")) as rev:
        thing_id = rev.create_thing("character", fields={"name": "Sela"})
        rev.add_fact(
            thing_id,
            "appearance",
            "A burn scar on one hand.",
            valid_from=WorldDate.of(314),
        )

    world.prose().put(
        thing_id,
        "description",
        None,
        WorldDate.of(314),
        "A calm herbalist with ink-stained fingers.",
    )

    return thing_id


def test_cached_description_found_in_first_stretch(world, herbalist):
    """Fix round 1 / Critical 2: before the fix, this returned '' at 312
    (the cache for the thing's very first, `(None, X)`, stretch was never
    found) and only the since line survived at 315."""

    before = character_from_world(world, herbalist, WorldDate.of(312), is_player=False)
    assert before.description == "A calm herbalist with ink-stained fingers."

    after = character_from_world(world, herbalist, WorldDate.of(315), is_player=False)
    assert "A calm herbalist with ink-stained fingers." in after.description
    assert "Since 314: A burn scar on one hand." in after.description


@pytest.fixture
def interim_warden(world):
    """A character whose description is cached fresh for exactly the
    `(305, 316)` stretch her Wardens fact defines -- the fact is already
    baked into the cached prose throughout that stretch."""

    with world.revision(Source.manual(note="create Rin")) as rev:
        thing_id = rev.create_thing("character", fields={"name": "Rin"})
        rev.add_fact(
            thing_id,
            "background",
            "Member of the Wardens.",
            valid_from=WorldDate.of(305),
            valid_until=WorldDate.of(316),
        )

    world.prose().put(
        thing_id,
        "description",
        WorldDate.of(305),
        WorldDate.of(316),
        "A watchful member of the Wardens.",
    )

    return thing_id


def test_since_lines_no_future_leak_before_fact_ends(world, interim_warden):
    """Fix round 1 / Critical 1a: at 310, with prose freshly cached for the
    (305, 316) stretch the Wardens fact is already part of, there must be
    no "Until 316" line -- the fact hasn't ended yet, and the cached prose
    still describes it as true."""

    assert since_lines(world, interim_warden, WorldDate.of(310)) == []

    description = character_from_world(
        world, interim_warden, WorldDate.of(310), is_player=False
    ).description
    assert description == "A watchful member of the Wardens."


def test_since_lines_reports_ended_fact_after_cache_goes_stale(world, interim_warden):
    """Fix round 1 / Critical 1b: at 318, after the Wardens fact has
    ended, `view(at)` no longer carries it at all -- the "Until" line has
    to come from the view at the horizon instead."""

    assert since_lines(world, interim_warden, WorldDate.of(318)) == [
        "Until 316: Member of the Wardens."
    ]

    description = character_from_world(
        world, interim_warden, WorldDate.of(318), is_player=False
    ).description
    assert "Until 316: Member of the Wardens." in description


def test_age_before_and_after_birthday(world):
    """Fix round 1 (small fix): age is full years elapsed, allowing for
    the birthday not having happened yet this year."""

    with world.revision(Source.manual(note="create Tomas")) as rev:
        thing_id = rev.create_thing(
            "character",
            fields={"name": "Tomas", "born": WorldDate.of(280, 6, 15)},
            valid_from=WorldDate.of(280, 6, 15),
        )

    before_birthday = character_from_world(
        world, thing_id, WorldDate.of(300, 3, 1), is_player=False
    )
    assert before_birthday.base_attributes["age"] == 19

    after_birthday = character_from_world(
        world, thing_id, WorldDate.of(300, 7, 1), is_player=False
    )
    assert after_birthday.base_attributes["age"] == 20
