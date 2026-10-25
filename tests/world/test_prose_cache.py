from talemate.world.dates import WorldDate
from talemate.world.prose import stretches
from talemate.world.store import Source


def _expected_stretches(world, thing_id):
    """The boundary dates straight from `World.timeline`, deduplicated by
    instant and sorted -- the same data `stretches` is built from, kept
    independent of its implementation."""

    by_instant = {}
    for entry in world.timeline(thing_id):
        if entry.date is not None:
            by_instant[entry.date.instant] = entry.date
    dates = [by_instant[instant] for instant in sorted(by_instant)]
    bounds = [None, *dates, None]
    return list(zip(bounds[:-1], bounds[1:]))


def test_stretches_from_timeline(world, maren):
    result = stretches(lambda: world, maren.id)
    assert result == _expected_stretches(world, maren.id)

    # sanity check against the known timeline-order dates (see
    # test_timeline.test_timeline_order)
    flat_instants = [
        d.instant if d is not None else None for pair in result for d in pair
    ]
    assert flat_instants == [
        None,
        WorldDate.of(290).instant,
        WorldDate.of(290).instant,
        WorldDate.of(304).instant,
        WorldDate.of(304).instant,
        WorldDate.of(305).instant,
        WorldDate.of(305).instant,
        WorldDate.of(314).instant,
        WorldDate.of(314).instant,
        WorldDate.of(316).instant,
        WorldDate.of(316).instant,
        WorldDate.of(317).instant,
        WorldDate.of(317).instant,
        None,
    ]


def _warden_stretch(world, maren):
    return next(
        (start, end)
        for start, end in stretches(lambda: world, maren.id)
        if start is not None and start.instant == WorldDate.of(305).instant
    )


def test_prose_cache_get_by_date(world, maren):
    cache = world.prose()
    start, end = _warden_stretch(world, maren)

    assert cache.get(maren.id, "appearance", WorldDate.of(310)) is None

    cache.put(maren.id, "appearance", start, end, "She guards the eastern gate.")

    got = cache.get(maren.id, "appearance", WorldDate.of(310))
    assert got is not None
    assert got.text == "She guards the eastern gate."
    assert got.stretch_start.instant == start.instant
    assert got.stretch_end.instant == end.instant
    assert got.edited is False

    # outside the stretch: no entry
    assert cache.get(maren.id, "appearance", WorldDate.of(320)) is None

    # a second put for the same stretch replaces, not duplicates
    cache.put(maren.id, "appearance", start, end, "Revised text.", edited=True)
    got2 = cache.get(maren.id, "appearance", WorldDate.of(310))
    assert got2.text == "Revised text."
    assert got2.edited is True


def test_stale_after_new_fact(world, maren):
    cache = world.prose()
    start, end = _warden_stretch(world, maren)

    cache.put(maren.id, "appearance", start, end, "She guards the eastern gate.")
    assert cache.stale(maren.id, "appearance", WorldDate.of(310)) is False

    # no cached entry at all -> stale
    assert cache.stale(maren.id, "background", WorldDate.of(310)) is True

    with world.revision(Source.manual(note="a scar")) as rev:
        rev.add_fact(
            maren.id,
            "appearance",
            "A scar across her jaw.",
            valid_from=WorldDate.of(308),
        )

    assert cache.stale(maren.id, "appearance", WorldDate.of(310)) is True


def _stretch_starting(world, maren, year):
    return next(
        (start, end)
        for start, end in stretches(lambda: world, maren.id)
        if start is not None and start.instant == WorldDate.of(year).instant
    )


def test_stale_after_fact_removed_inside_stretch(world, maren):
    cache = world.prose()
    start, end = _stretch_starting(world, maren, 314)
    cache.put(maren.id, "description", start, end, "One-eyed.")
    assert cache.stale(maren.id, "description", WorldDate.of(315)) is False

    with world.revision(Source.manual(note="never lost it")) as rev:
        rev.remove_fact(maren.eye)

    # the prose still describes the removed fact, so it's stale
    assert cache.stale(maren.id, "description", WorldDate.of(315)) is True


def test_stale_after_removing_fact_that_started_before_stretch(world, maren):
    # the tattoo starts at 304, before the (305, 314) stretch, but is
    # visible all through it -- removing it changes that stretch's prose
    cache = world.prose()
    start, end = _warden_stretch(world, maren)
    cache.put(maren.id, "description", start, end, "Tattooed warden.")

    with world.revision(Source.manual(note="no tattoo")) as rev:
        rev.remove_fact(maren.tattoo)

    assert cache.stale(maren.id, "description", WorldDate.of(310)) is True


def test_not_stale_after_removing_fact_that_ended_before_stretch(world, maren):
    # the warden fact ended at 316, before the (317, None) stretch
    cache = world.prose()
    start, end = _stretch_starting(world, maren, 317)
    cache.put(maren.id, "description", start, end, "The Grey.")

    with world.revision(Source.manual(note="never a warden")) as rev:
        rev.remove_fact(maren.warden)

    assert cache.stale(maren.id, "description", WorldDate.of(318)) is False


def test_stale_after_field_value_removed_inside_stretch(world, maren):
    cache = world.prose()
    start, end = _stretch_starting(world, maren, 317)
    cache.put(maren.id, "description", start, end, "The Grey.")

    with world.revision(Source.manual(note="not renamed")) as rev:
        rev.remove_field_value(maren.id, "name", WorldDate.of(317))

    assert cache.stale(maren.id, "description", WorldDate.of(318)) is True


def test_put_records_given_rev(world, maren):
    # an entry generated from an older revision's facts records that
    # revision, so a change written since still shows as stale
    cache = world.prose()
    start, end = _stretch_starting(world, maren, 314)
    cache.put(maren.id, "description", start, end, "Two eyes.", rev=maren.rev_created)

    assert cache.get(maren.id, "description", WorldDate.of(315)).rev == (
        maren.rev_created
    )
    assert cache.stale(maren.id, "description", WorldDate.of(315)) is True


def test_stale_after_adding_fact_dated_before_stretch(world, maren):
    # a fact dated 300, added after the (305, 314) stretch was cached, is
    # visible all through that stretch
    cache = world.prose()
    start, end = _warden_stretch(world, maren)
    cache.put(maren.id, "description", start, end, "The warden.")

    with world.revision(Source.manual(note="an old scar")) as rev:
        rev.add_fact(
            maren.id, "appearance", "A scar on her chin.", valid_from=WorldDate.of(300)
        )

    assert cache.stale(maren.id, "description", WorldDate.of(310)) is True


def _ivo(world):
    """A character with no dated changes: one open stretch, (None, None)."""

    with world.revision(Source.manual(note="setup")) as rev:
        return rev.create_thing("character", fields={"name": "Ivo"})


def test_a_new_stretch_clips_the_cached_one_it_overlaps(world):
    """A fact at a new date splits the open stretch. The prose generated
    for the new open stretch wins at "now", and the old text keeps only the
    part before the new date, where it's still right."""

    thing_id = _ivo(world)
    cache = world.prose()
    cache.put(thing_id, "description", None, None, "A plain man.")

    with world.revision(Source.manual(note="a scar")) as rev:
        rev.add_fact(
            thing_id,
            "appearance",
            "A scar on his cheek.",
            valid_from=WorldDate.of(1003),
        )
    assert cache.stale(thing_id, "description", None) is True

    cache.put(thing_id, "description", WorldDate.of(1003), None, "A man with a scar.")

    now = cache.get(thing_id, "description", None)
    assert now.text == "A man with a scar."
    assert cache.stale(thing_id, "description", None) is False
    assert cache.get(thing_id, "description", WorldDate.of(1005)).text == (
        "A man with a scar."
    )

    earlier = cache.get(thing_id, "description", WorldDate.of(1001))
    assert earlier.text == "A plain man."
    assert earlier.stretch_start is None
    assert earlier.stretch_end.instant == WorldDate.of(1003).instant
    assert cache.stale(thing_id, "description", WorldDate.of(1001)) is False

    # the old text never comes back at "now", and no rows pile up
    rows = world._conn.execute(
        "SELECT COUNT(*) FROM prose_cache WHERE thing_id = ?", (thing_id,)
    ).fetchone()[0]
    assert rows == 2


def test_a_stretch_inside_a_cached_one_splits_it(world):
    thing_id = _ivo(world)
    cache = world.prose()
    cache.put(thing_id, "description", None, None, "Old.")
    cache.put(thing_id, "description", WorldDate.of(1003), WorldDate.of(1005), "Mid.")

    assert cache.get(thing_id, "description", WorldDate.of(1001)).text == "Old."
    assert cache.get(thing_id, "description", WorldDate.of(1004)).text == "Mid."
    later = cache.get(thing_id, "description", WorldDate.of(1006))
    assert later.text == "Old."
    assert later.stretch_start.instant == WorldDate.of(1005).instant
    assert later.stretch_end is None
    assert cache.get(thing_id, "description", None).text == "Old."


def test_a_stretch_covering_cached_ones_replaces_them(world):
    thing_id = _ivo(world)
    cache = world.prose()
    cache.put(thing_id, "description", None, WorldDate.of(1003), "Before.")
    cache.put(thing_id, "description", WorldDate.of(1003), None, "After.")
    cache.put(thing_id, "description", None, None, "Whole.")

    assert cache.get(thing_id, "description", WorldDate.of(1001)).text == "Whole."
    assert cache.get(thing_id, "description", None).text == "Whole."
    rows = world._conn.execute(
        "SELECT COUNT(*) FROM prose_cache WHERE thing_id = ?", (thing_id,)
    ).fetchone()[0]
    assert rows == 1


def test_get_prefers_the_latest_starting_overlap(world):
    """Rows left overlapping (cached before puts clipped them) resolve to
    the most specific one: the latest start, an open start last."""

    thing_id = _ivo(world)
    rev = world.head_rev()
    for start, text in [(WorldDate.of(1003).instant, "Newer."), (None, "Older.")]:
        world._conn.execute(
            "INSERT INTO prose_cache "
            "(thing_id, section, stretch_start, stretch_end, rev, text, edited) "
            "VALUES (?, 'description', ?, NULL, ?, ?, 0)",
            (thing_id, start, rev, text),
        )

    cache = world.prose()
    assert cache.get(thing_id, "description", None).text == "Newer."
    assert cache.get(thing_id, "description", WorldDate.of(1004)).text == "Newer."
    assert cache.get(thing_id, "description", WorldDate.of(1001)).text == "Older."
    assert cache.stale(thing_id, "description", None) is False


def test_stale_ignores_categories_the_section_does_not_read(world):
    """`ignore_categories`: a new fact, a removed one, or one moved out of
    an ignored category -- of the thing itself -- is no change when its
    category is ignored; the `also` ids are checked in full."""

    with world.revision(Source.manual(note="setup")) as rev:
        dawn = rev.create_thing("place", {"name": "The White Dawn"})
        rev.add_fact(dawn, "about", "The state church.")
        decree = rev.add_fact(
            dawn, "timeline", "Issued a decree.", valid_from=WorldDate.of(1001)
        )
        elder = rev.create_thing("place", {"name": "The Elder Dawn"})
    cache = world.prose()
    cache.put(dawn, "description", None, None, "The church of the dawn.")
    ignore = ("statement", "timeline")

    with world.revision(Source.manual(note="unread")) as rev:
        rev.add_fact(dawn, "statement", "Snow is pure.")
        rev.add_fact(dawn, "timeline", "A synod.", valid_from=WorldDate.of(1010))
        rev.remove_fact(decree)
    assert cache.stale(dawn, "description", None) is True
    assert cache.stale(dawn, "description", None, ignore_categories=ignore) is False

    # a change to an `also` id counts, whatever its category
    with world.revision(Source.manual(note="elder")) as rev:
        rev.add_fact(elder, "timeline", "Split.", valid_from=WorldDate.of(1012))
    assert (
        cache.stale(dawn, "description", None, [elder], ignore_categories=ignore)
        is True
    )

    # a read category counts
    with world.revision(Source.manual(note="read")) as rev:
        rev.add_fact(dawn, "about", "Kept by the elders.")
    assert cache.stale(dawn, "description", None, ignore_categories=ignore) is True
