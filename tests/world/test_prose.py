"""Prose staleness through a thing's lineage: `stretches` and `ProseCache.
stale` take an `also` sequence of ancestor ids (a thing's heritage,
`heritage.lineage` with `depth > 0`) so cached prose that drew on a species,
race or culture goes stale -- and stretches split -- when that ancestor
changes too."""

from talemate.world.dates import WorldDate
from talemate.world.heritage import lineage
from talemate.world.prose import stretches
from talemate.world.store import Source


def _lineage_ids(view, thing_id):
    return [layer.thing_id for layer in lineage(view, thing_id) if layer.depth > 0]


def test_stale_when_species_fact_added(world, heritage_world):
    h = heritage_world
    cache = world.prose()
    cache.put(h.vasha, "description", None, None, "An owl-folk woman.")
    also = _lineage_ids(world.view(), h.vasha)

    assert cache.stale(h.vasha, "description", None) is False
    assert cache.stale(h.vasha, "description", None, also=also) is False

    with world.revision(Source.manual(note="a species fact")) as rev:
        rev.add_fact(h.owl_folk, "physical", "Keen night vision.")

    # unchanged default: a species fact doesn't make the own-only check stale
    assert cache.stale(h.vasha, "description", None) is False
    # but it does when the species is in `also`
    assert cache.stale(h.vasha, "description", None, also=also) is True


def test_stretches_include_species_boundary(world, heritage_world):
    h = heritage_world
    also = _lineage_ids(world.view(), h.vasha)

    with world.revision(Source.manual(note="a dated species fact")) as rev:
        rev.add_fact(
            h.owl_folk, "physical", "Molt each spring.", valid_from=WorldDate.of(500)
        )

    own_only = stretches(lambda: world, h.vasha)
    assert own_only == [(None, None)]

    combined = stretches(lambda: world, h.vasha, also=also)
    assert combined == [(None, WorldDate.of(500)), (WorldDate.of(500), None)]


def test_stale_when_ancestor_deleted(world, heritage_world):
    h = heritage_world
    cache = world.prose()
    cache.put(h.vasha, "description", None, None, "An owl-folk woman.")
    also = _lineage_ids(world.view(), h.vasha)
    assert h.snowy in also

    with world.revision(Source.manual(note="remove the race")) as rev:
        rev.remove_thing(h.snowy)

    assert cache.stale(h.vasha, "description", None) is False
    assert cache.stale(h.vasha, "description", None, also=also) is True
