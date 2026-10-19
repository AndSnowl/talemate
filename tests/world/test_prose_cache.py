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
