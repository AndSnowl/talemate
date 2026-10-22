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
    ended, `world.view(318)` no longer carries it at all -- the "Until"
    line has to come from the timeline's own `fact_end` entry instead."""

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


@pytest.fixture
def ana(world):
    """Fix round 2 / Finding 1: an undated fact ("always" true, no
    `valid_from`) that ends at 314, cached in the thing's one and only
    stretch, `(None, 314)`. The cached entry's own `stretch_start` is
    `None` -- exactly the value `_cached_section` returns for "nothing
    was ever cached" -- which is precisely what made this fall through
    before: a *found* entry with no start looked identical to no entry at
    all."""

    with world.revision(Source.manual(note="create Ana")) as rev:
        thing_id = rev.create_thing("character", fields={"name": "Ana"})
        rev.add_fact(
            thing_id,
            "background",
            "Apprentice.",
            valid_until=WorldDate.of(314),
        )

    world.prose().put(
        thing_id, "description", None, WorldDate.of(314), "An apprentice."
    )

    return thing_id


def test_since_lines_reports_undated_fact_ended_past_stale_cache(world, ana):
    """Fix round 2 / Finding 1 (the reviewer's repro): at 315, past the
    only cached stretch's end, the ended fact must still produce an
    "Until" line even though it never had a `valid_from` of its own."""

    assert since_lines(world, ana, WorldDate.of(315)) == ["Until 314: Apprentice."]

    description = character_from_world(
        world, ana, WorldDate.of(315), is_player=False
    ).description
    assert "Until 314: Apprentice." in description


@pytest.fixture
def visitor(world):
    """Fix round 2: a character whose description is cached well before a
    fact that both starts *and* ends inside the gap between that cache
    and a later `at` -- the "accepted residual" fix round 1 left open,
    since neither `world.view(at)` nor `world.view(horizon)` alone ever
    shows a fact that's entirely contained between the two."""

    with world.revision(Source.manual(note="create Priya")) as rev:
        thing_id = rev.create_thing(
            "character",
            fields={"name": "Priya", "born": WorldDate.of(290)},
            valid_from=WorldDate.of(290),
        )

    with world.revision(Source.manual(note="Priya breaks her arm")) as rev:
        rev.add_fact(
            thing_id,
            "appearance",
            "A cast on her arm.",
            valid_from=WorldDate.of(310),
            valid_until=WorldDate.of(312),
        )

    world.prose().put(
        thing_id,
        "description",
        WorldDate.of(290),
        WorldDate.of(310),
        "A young woman with calloused hands.",
    )

    return thing_id


def test_since_lines_reports_fact_starting_and_ending_inside_window(world, visitor):
    """Fix round 2: the cache is fresh for (290, 310); the cast starts at
    310 and ends at 312, both inside the (310, 320] window -- one combined
    "From ... until ..." line, not two, and not the gap fix round 1 left
    open."""

    assert since_lines(world, visitor, WorldDate.of(320)) == [
        "From 310 until 312: A cast on her arm."
    ]

    description = character_from_world(
        world, visitor, WorldDate.of(320), is_player=False
    ).description
    assert "From 310 until 312: A cast on her arm." in description


@pytest.fixture
def blank_slate(world):
    """Fix round 3 (a), the reviewer's repro: nothing dated at all yet,
    so the thing's whole timeline is one `(None, None)` stretch -- cached
    once while that's still true. A *later* revision then adds a dated
    fact. The cached entry's own `stretch_end` is `None` (it really was
    fresh when written), but the new fact was written after it, so it
    must be reported regardless of what date it's dated at."""

    with world.revision(Source.manual(note="create Nadia")) as rev:
        thing_id = rev.create_thing("character", fields={"name": "Nadia"})

    world.prose().put(thing_id, "description", None, None, "A trader.")

    with world.revision(Source.manual(note="Nadia loses an eye")) as rev:
        rev.add_fact(
            thing_id, "appearance", "Lost an eye.", valid_from=WorldDate.of(314)
        )

    return thing_id


def test_since_lines_reports_change_written_after_an_open_cache(world, blank_slate):
    """Fix round 3 (a): round 2's rule early-returned `[]` whenever the
    cached entry's own `stretch_end` was `None`, treating "fresh for the
    current, open stretch" and "stale, but was cached before this thing
    had any dated changes at all" as the same thing. They aren't."""

    assert since_lines(world, blank_slate, WorldDate.of(315)) == [
        "Since 314: Lost an eye."
    ]

    description = character_from_world(
        world, blank_slate, WorldDate.of(315), is_player=False
    ).description
    assert "Since 314: Lost an eye." in description


@pytest.fixture
def scarred_warden(world):
    """Fix round 3 (b), the reviewer's repro: a fact added in a *later*
    revision, dated *inside* a stretch that's already cached. Must still
    be reported -- it wasn't known when the cache was written, regardless
    of its own date falling before the stretch's end."""

    with world.revision(Source.manual(note="create Tess")) as rev:
        thing_id = rev.create_thing("character", fields={"name": "Tess"})
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

    with world.revision(Source.manual(note="Tess is scarred")) as rev:
        rev.add_fact(thing_id, "appearance", "Scarred.", valid_from=WorldDate.of(310))

    return thing_id


def test_since_lines_reports_change_written_after_cache_dated_inside_stretch(
    world, scarred_warden
):
    """Fix round 3 (b): round 2's rule compared only the change's own date
    against the cached stretch's end (316), so "Scarred." at 310 -- inside
    that stretch -- was never reported, even though it was written well
    after the cache."""

    assert since_lines(world, scarred_warden, WorldDate.of(312)) == [
        "Since 310: Scarred."
    ]

    description = character_from_world(
        world, scarred_warden, WorldDate.of(312), is_player=False
    ).description
    assert "Since 310: Scarred." in description


def test_since_lines_includes_undated_facts_with_nothing_cached(world):
    """Fix round 3: with nothing cached at all yet, an undated ("always")
    appearance/background fact has no dated timeline entry of its own to
    report -- without this, it would never appear in the description at
    all. It's a plain line, with no "Since"/"Until" prefix, since there's
    no single date to attach to it."""

    with world.revision(Source.manual(note="create Yusuf")) as rev:
        thing_id = rev.create_thing("character", fields={"name": "Yusuf"})
        rev.add_fact(thing_id, "background", "A former soldier.")

    assert since_lines(world, thing_id, WorldDate.of(310)) == ["A former soldier."]

    character = character_from_world(
        world, thing_id, WorldDate.of(310), is_player=False
    )
    assert character.description == "A former soldier."


def test_since_lines_reports_undated_fact_written_after_an_open_cache(world):
    """Fix round 4 (repro 7): an undated fact added by a revision written
    after an open `(None, None)` cache isn't in the cached text, so it gets
    a plain line -- an "always" fact is only baked into a cache that was
    written after it."""

    with world.revision(Source.manual(note="create Mo")) as rev:
        thing_id = rev.create_thing("character", fields={"name": "Mo"})
        rev.add_fact(thing_id, "appearance", "Tall.")

    world.prose().put(thing_id, "description", None, None, "Tall.")

    with world.revision(Source.manual(note="Mo limps")) as rev:
        rev.add_fact(thing_id, "appearance", "Has a limp.")

    assert since_lines(world, thing_id, WorldDate.of(315)) == ["Has a limp."]
    assert since_lines(world, thing_id, None) == ["Has a limp."]

    description = character_from_world(
        world, thing_id, WorldDate.of(315), is_player=False
    ).description
    assert description == "Tall.\nHas a limp."


def test_since_lines_reports_undated_facts_written_after_a_bounded_cache(world):
    """Fix round 4 (repro 7b): undated facts written after a `(305, 316)`
    cache. One that ends at 314 is a plain line while it's still true, and
    an "Until" line once it has ended."""

    with world.revision(Source.manual(note="create Rin")) as rev:
        thing_id = rev.create_thing("character", fields={"name": "Rin"})
        rev.add_fact(
            thing_id,
            "background",
            "Warden.",
            valid_from=WorldDate.of(305),
            valid_until=WorldDate.of(316),
        )

    world.prose().put(
        thing_id, "description", WorldDate.of(305), WorldDate.of(316), "A warden."
    )

    with world.revision(Source.manual(note="Rin limps, shaves")) as rev:
        rev.add_fact(thing_id, "appearance", "Has a limp.")
        rev.add_fact(thing_id, "appearance", "Bearded.", valid_until=WorldDate.of(314))

    assert sorted(since_lines(world, thing_id, WorldDate.of(312))) == [
        "Bearded.",
        "Has a limp.",
    ]
    assert sorted(since_lines(world, thing_id, WorldDate.of(315))) == [
        "Has a limp.",
        "Until 314: Bearded.",
    ]


@pytest.fixture
def ended_warden(world):
    """Fix round 4 (repro 9): a fact from 305, cached in its open stretch;
    a later revision ends it at 314 (`end_fact` writes a new version of
    the same fact_id). The start was already in the cached prose."""

    with world.revision(Source.manual(note="create Zia")) as rev:
        thing_id = rev.create_thing("character", fields={"name": "Zia"})
        fact_id = rev.add_fact(
            thing_id, "background", "Warden.", valid_from=WorldDate.of(305)
        )

    world.prose().put(thing_id, "description", WorldDate.of(305), None, "A warden.")

    with world.revision(Source.manual(note="Zia leaves the Wardens")) as rev:
        rev.end_fact(fact_id, WorldDate.of(314))

    return thing_id, fact_id


def test_since_lines_new_end_of_a_cached_fact_is_only_until(world, ended_warden):
    """Fix round 4 (repro 9): only the new end is news; the start the prose
    already reflects isn't re-emitted as "Since"/"From ... until"."""

    thing_id, _ = ended_warden
    assert since_lines(world, thing_id, WorldDate.of(315)) == ["Until 314: Warden."]
    assert since_lines(world, thing_id, WorldDate.of(310)) == []


def test_since_lines_corrected_text_of_a_cached_fact_is_reported(world, ended_warden):
    """Fix round 4 (lineage): a text correction written after the cache is
    news, reported with the fact's existing dates."""

    thing_id, fact_id = ended_warden
    with world.revision(Source.manual(note="reword")) as rev:
        rev.correct_fact(fact_id, text="Captain of the Wardens.")

    assert since_lines(world, thing_id, WorldDate.of(310)) == [
        "Since 305: Captain of the Wardens."
    ]
    assert since_lines(world, thing_id, WorldDate.of(315)) == [
        "From 305 until 314: Captain of the Wardens."
    ]


# -- inheritance (phase 2 plan B) --------------------------------------------


def _cache_description(world, thing_id, text="Vasha is a pale owl."):
    world.prose().put(thing_id, "description", None, None, text)


def test_since_line_for_species_change(world, heritage_world):
    vasha = heritage_world.vasha
    _cache_description(world, vasha)
    with world.revision(Source.manual()) as rev:
        rev.add_fact(
            heritage_world.owl_folk,
            "physical",
            "live to about 60 years.",
            valid_from=WorldDate.of(500),
        )
        # an instinct change isn't part of the description
        rev.add_fact(
            heritage_world.owl_folk,
            "instinct",
            "Hoard bright things.",
            valid_from=WorldDate.of(500),
        )

    assert since_lines(world, vasha, WorldDate.of(510)) == [
        "Since 500: Owl-folk: live to about 60 years."
    ]
    assert since_lines(world, vasha, WorldDate.of(490)) == []


def test_since_lines_skip_overridden_inherited_fact(world, heritage_world):
    vasha = heritage_world.vasha
    _cache_description(world, vasha)
    with world.revision(Source.manual()) as rev:
        grey = rev.add_fact(
            heritage_world.snowy,
            "variation",
            "Grey crests.",
            valid_from=WorldDate.of(500),
        )
    with world.revision(Source.manual()) as rev:
        rev.add_fact(
            vasha,
            "appearance",
            "No crest at all.",
            valid_from=WorldDate.of(500),
            overrides=[grey],
        )

    assert since_lines(world, vasha, WorldDate.of(510)) == [
        "Since 500: No crest at all."
    ]


def test_since_lines_list_inherited_facts_when_nothing_cached(world, heritage_world):
    assert since_lines(world, heritage_world.vasha, None) == [
        "Blue eyes.",
        "Snowy: White plumage.",
        "Owl-folk: Wings in place of arms.",
    ]


def test_character_sheet_life_stage(world, heritage_world):
    vasha = heritage_world.vasha

    adult = character_from_world(world, vasha, WorldDate.of(1000), is_player=False)
    young = character_from_world(world, vasha, WorldDate.of(986), is_player=False)

    assert adult.base_attributes["life_stage"] == "adult"
    assert young.base_attributes["life_stage"] == "child"


def test_character_sheet_states_own_traits_win(world, heritage_world):
    character = character_from_world(
        world, heritage_world.vasha, WorldDate.of(1000), is_player=False
    )

    assert character.description.endswith(
        "Where Vasha's own traits differ from those of their kind, "
        "Vasha's own traits hold."
    )


def test_character_sheet_without_heritage_has_no_traits_line(world, oskar):
    character = character_from_world(world, oskar, WorldDate.of(320), is_player=False)

    assert "own traits" not in character.description
    assert "life_stage" not in character.base_attributes


def test_character_sheet_with_deleted_species(world, heritage_world):
    vasha = heritage_world.vasha
    _cache_description(world, vasha)
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(heritage_world.owl_folk)

    character = character_from_world(world, vasha, WorldDate.of(1000), is_player=False)

    # Snowy sets no numbers of its own, so with Owl-folk gone there's no stage
    assert "life_stage" not in character.base_attributes
    assert "Wings" not in character.description
    assert since_lines(world, vasha, WorldDate.of(1000)) == []


def test_since_lines_for_switch_to_an_older_race(world, heritage_world):
    """Fix round 1: a race that already existed when the prose was cached,
    but wasn't in the character's lineage then, is news in full -- its
    facts being older than the cache doesn't put them in the cached text."""

    vasha = heritage_world.vasha
    with world.revision(Source.manual()) as rev:
        tawny = rev.create_thing(
            "race", fields={"name": "Tawny", "species": heritage_world.owl_folk}
        )
        rev.add_fact(tawny, "variation", "Brown plumage.")
    _cache_description(world, vasha)
    with world.revision(Source.manual()) as rev:
        rev.set_field(vasha, "heritage", tawny, WorldDate.of(990))

    assert since_lines(world, vasha, WorldDate.of(1000)) == ["Tawny: Brown plumage."]
    # still a Snowy before the switch, as the cached prose already says
    assert since_lines(world, vasha, WorldDate.of(985)) == []


def test_since_lines_after_a_dated_heritage_change_past_the_cache(
    world, heritage_world
):
    """Final review: the prose cached for the stretch before a dated
    heritage change was written with the old lineage, so the new layer is
    news once the clock passes the change -- even though the change was
    already in the store when the prose was cached."""

    h = heritage_world
    with world.revision(Source.manual()) as rev:
        human = rev.create_thing("species", fields={"name": "Human"})
        rev.add_fact(human, "physical", "Two hands.")
        kit = rev.create_thing("character", fields={"name": "Kit", "heritage": human})
    with world.revision(Source.manual()) as rev:
        rev.set_field(kit, "heritage", h.owl_folk, WorldDate.of(400))
    # a scene in 390 caches the stretch that ends at the change
    world.prose().put(
        kit, "description", None, WorldDate.of(400), "A human with two hands."
    )

    assert since_lines(world, kit, WorldDate.of(390)) == []
    assert since_lines(world, kit, WorldDate.of(401)) == [
        "Owl-folk: Wings in place of arms."
    ]


# --- ties ---------------------------------------------------------------------


def test_sheet_has_tie_lines_with_exceptions(world, spheres_world):
    """Each live tie is one line on the sheet: the role capitalised, "of"
    the sphere, "(since <year>)" when there's a since, then "but: " and its
    exceptions read as text (character creation's "Departs from ..." link
    left off), joined with "; "."""

    s = spheres_world
    vasha = character_from_world(world, s.vasha, WorldDate.of(1020), is_player=False)
    assert vasha.base_attributes["ties"] == (
        "Practitioner of the White Dawn (since 1010), but: doesn't believe "
        "snowy owl-folk are superior; means to marry a human"
    )
    assert "ties: Practitioner of the White Dawn" in vasha.sheet
    assert "Departs" not in vasha.sheet
    assert "[[thing:" not in vasha.sheet

    # no since, no exceptions
    brenna = character_from_world(world, s.brenna, WorldDate.of(1020), is_player=False)
    assert brenna.base_attributes["ties"] == "Elder of the Council of Elders"

    # before the tie began, there's none
    young = character_from_world(world, s.vasha, WorldDate.of(1005), is_player=False)
    assert "ties" not in young.base_attributes


def test_sheet_has_one_line_per_live_tie(world, spheres_world):
    s = spheres_world
    with world.revision(Source.manual(note="more ties")) as rev:
        rev.set_field(
            s.brenna,
            "ties",
            [
                {"sphere": s.council, "role": "elder", "since": None, "until": None},
                {
                    "sphere": s.guild,
                    "role": "apprentice",
                    "since": WorldDate.of(990).model_dump(mode="json"),
                    "until": WorldDate.of(1000).model_dump(mode="json"),
                },
                {
                    "sphere": s.tsardom,
                    "role": "subject",
                    "since": WorldDate.of(1001).model_dump(mode="json"),
                    "until": None,
                },
            ],
            None,
        )
    brenna = character_from_world(world, s.brenna, WorldDate.of(1020), is_player=False)
    # one line each, the ended apprenticeship left out; a leading "The"
    # is lowercased mid-line, a name without one is as written
    assert brenna.base_attributes["ties"] == (
        "Elder of the Council of Elders\nSubject of Tsardom of Moscavia (since 1001)"
    )


def test_tie_to_deleted_sphere(world, spheres_world):
    """A tie stores the sphere's id, not its name, so a tie to a sphere
    since deleted has no name to show and is left out (never
    "⟨unknown⟩"), as are its exceptions."""

    s = spheres_world
    with world.revision(Source.manual(note="gone")) as rev:
        rev.remove_thing(s.council)
    brenna = character_from_world(world, s.brenna, WorldDate.of(1020), is_player=False)
    assert "ties" not in brenna.base_attributes
    assert "⟨unknown⟩" not in brenna.sheet

    with world.revision(Source.manual(note="gone too")) as rev:
        rev.remove_thing(s.dawn)
    vasha = character_from_world(world, s.vasha, WorldDate.of(1020), is_player=False)
    assert "ties" not in vasha.base_attributes


def test_exception_text_without_departs_suffix():
    from talemate.worldplay.characters import exception_text

    dawn, item = "a" * 32, "b" * 32
    assert (
        exception_text(
            f"Doesn't believe it. Departs from a teaching of [[thing:{dawn}|The Dawn]]"
        )
        == "Doesn't believe it."
    )
    assert (
        exception_text(f"Means to marry. Departs from [[thing:{item}]]")
        == "Means to marry."
    )
    # only the trailing link sentence goes; a reference elsewhere stays
    assert exception_text(
        f"Skips [[thing:{item}|the vigil]] at Departs from Peak."
    ) == (f"Skips [[thing:{item}|the vigil]] at Departs from Peak.")
    assert exception_text("Sleeps through prayers.") == "Sleeps through prayers."


def test_exception_text_strips_what_creation_appends():
    """Round trip: the link sentence `create.exception_fact` appends to
    an exception (for a thing item, and for a statement, whose item name
    is a whole sentence) is exactly what `exception_text` takes off."""

    from talemate.worldplay.characters import exception_text
    from talemate.worldplay.create import (
        PreviewException,
        PreviewTie,
        exception_fact,
    )

    dawn, item = "a" * 32, "b" * 32
    tie = PreviewTie(sphere_id=dawn, sphere="The White Dawn", role="priest")
    for exception in (
        PreviewException(
            text="Means to marry a human", item="The Doctrine", thing_id=item
        ),
        PreviewException(
            text="Thinks all folk equal.",
            item="Snowy owl-folk are the purest of the folk.",
            fact_id="c" * 32,
        ),
    ):
        text, _origin = exception_fact(exception.text, tie, exception)
        assert "Departs from" in text
        assert exception_text(text) == exception.text.rstrip(".") + "."


def test_tie_line_keeps_names_and_capitals_opening_an_exception(world, spheres_world):
    """An exception opening with a name -- a reference, or the character's
    own (left unlinked by creation) -- or with "I" or a word in capitals
    keeps its case after "but: "; any other opens lowercase."""

    s = spheres_world
    with world.revision(Source.manual(note="more")) as rev:
        rev.add_fact(
            s.vasha,
            "ties",
            f"Vasha skips [[thing:{s.separation}|the doctrine]]'s fast.",
            origin={"tie": s.dawn},
        )
        rev.add_fact(
            s.vasha,
            "ties",
            f"[[thing:{s.kremova}]] is where she breaks "
            f"[[thing:{s.separation}|the doctrine]].",
            origin={"tie": s.dawn},
        )
        rev.add_fact(
            s.vasha,
            "ties",
            f"I'll not bow, she says of [[thing:{s.separation}|the doctrine]].",
            origin={"tie": s.dawn},
        )
        rev.add_fact(
            s.vasha,
            "ties",
            f"NEVER kneels at [[thing:{s.separation}|the doctrine]]'s reading.",
            origin={"tie": s.dawn},
        )
    vasha = character_from_world(world, s.vasha, WorldDate.of(1020), is_player=False)
    assert vasha.base_attributes["ties"].endswith(
        "but: doesn't believe snowy owl-folk are superior; means to marry a "
        "human; Vasha skips the doctrine's fast; Kremova is where she breaks "
        "the doctrine; I'll not bow, she says of the doctrine; NEVER kneels at the "
        "doctrine's reading"
    )


def test_exception_opening_with_a_world_name_keeps_its_capital(world, spheres_world):
    """The first letter after "but:" keeps its case when the text opens
    with a world name, linked or not (Brenna, another character, left
    plain); the character's own name doesn't protect a leading word ("The
    Grey Wanderer" and "The vigil..."); a plain verb is lowercased."""

    s = spheres_world
    with world.revision(Source.manual(note="names")) as rev:
        rev.set_field(s.vasha, "name", "The Grey Wanderer", None)
        rev.add_fact(
            s.vasha,
            "ties",
            f"Brenna taught her to doubt [[thing:{s.separation}|the doctrine]].",
            origin={"tie": s.dawn},
        )
        rev.add_fact(
            s.vasha,
            "ties",
            f"The vigil at [[thing:{s.separation}|the doctrine]]'s feast bores her.",
            origin={"tie": s.dawn},
        )
        rev.add_fact(
            s.vasha,
            "ties",
            f"Skips [[thing:{s.separation}|the doctrine]]'s fast.",
            origin={"tie": s.dawn},
        )
    vasha = character_from_world(world, s.vasha, WorldDate.of(1020), is_player=False)
    assert vasha.base_attributes["ties"].endswith(
        "; Brenna taught her to doubt the doctrine; the vigil at the "
        "doctrine's feast bores her; skips the doctrine's fast"
    )


def test_tie_since_reads_as_a_year(world, spheres_world):
    s = spheres_world
    with world.revision(Source.manual(note="precise")) as rev:
        rev.set_field(
            s.brenna,
            "ties",
            [
                {
                    "sphere": s.council,
                    "role": "elder",
                    "since": WorldDate.of(1010, 3, 4).model_dump(mode="json"),
                    "until": None,
                }
            ],
            None,
        )
    brenna = character_from_world(world, s.brenna, WorldDate.of(1020), is_player=False)
    assert brenna.base_attributes["ties"] == (
        "Elder of the Council of Elders (since 1010)"
    )


def test_tie_to_a_nameless_sphere_is_left_out(world, spheres_world):
    s = spheres_world
    with world.revision(Source.manual(note="nameless")) as rev:
        rev.remove_field_value(s.council, "name", None)
    brenna = character_from_world(world, s.brenna, WorldDate.of(1020), is_player=False)
    assert "ties" not in brenna.base_attributes
    assert "⟨unknown⟩" not in brenna.sheet
