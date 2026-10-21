"""Prose staleness through a thing's lineage: `stretches` and `ProseCache.
stale` take an `also` sequence of ancestor ids (a thing's heritage,
`heritage.lineage` with `depth > 0`) so cached prose that drew on a species,
race or culture goes stale -- and stretches split -- when that ancestor
changes too."""

from talemate.world.dates import WorldDate
from talemate.world.heritage import lineage
from talemate.world.prose import stretches
from talemate.world.refs import ref
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


# --- edits that change no rendered text ----------------------------------------


def _cached_fresh(world, h):
    """Prose for Snowy and Vasha (whose lineage holds Owl-folk), fresh."""

    cache = world.prose()
    for thing_id in (h.snowy, h.vasha):
        cache.put(thing_id, "description", None, None, "Owls.")
    return cache


def _all_fresh(world, cache, h):
    return {
        name: cache.stale(
            thing_id,
            "description",
            None,
            also=_lineage_ids(world.view(), thing_id),
        )
        for name, thing_id in (("snowy", h.snowy), ("vasha", h.vasha))
    }


def test_other_names_and_stub_marker_leave_prose_fresh(world, heritage_world):
    """Teaching a thing an other name, or ignoring/reviving a stub, changes
    no rendered text: the thing and what inherits from it stay fresh."""

    h = heritage_world
    cache = _cached_fresh(world, h)
    with world.revision(Source.manual(note="other name")) as rev:
        rev.set_field(
            h.owl_folk,
            "aka",
            [{"name": "Owls", "tag": "common", "everyday": True}],
            None,
        )
        rev.set_field(
            h.snowy,
            "aka",
            [{"name": "Snowies", "tag": "common", "everyday": False}],
            None,
        )
    with world.revision(Source.manual(note="a stub marker, then none")) as rev:
        rev.set_field(h.owl_folk, "stub", {"ignored": True}, None)
    with world.revision(Source.manual(note="expanded")) as rev:
        rev.remove_field_value(h.owl_folk, "stub", None)
    assert _all_fresh(world, cache, h) == {"snowy": False, "vasha": False}


def test_link_only_fact_edits_leave_prose_fresh(world, heritage_world):
    """Linking a word of a fact, or re-pointing a link that keeps its
    words, renders the same text: nothing goes stale. Changing the words,
    or re-pointing a link shown by its target's name, does."""

    h = heritage_world
    cache = _cached_fresh(world, h)
    with world.revision(Source.manual(note="link arms")) as rev:
        rev.correct_fact(h.wings, text=f"Wings in place of {ref(h.human, 'arms')}.")
    with world.revision(Source.manual(note="re-point arms")) as rev:
        rev.correct_fact(h.wings, text=f"Wings in place of {ref(h.orc, 'arms')}.")
    assert _all_fresh(world, cache, h) == {"snowy": False, "vasha": False}

    with world.revision(Source.manual(note="by name")) as rev:
        rev.correct_fact(h.wings, text=f"Wings in place of {ref(h.orc)} arms.")
    assert _all_fresh(world, cache, h) == {"snowy": True, "vasha": True}

    cache = _cached_fresh(world, h)
    with world.revision(Source.manual(note="by another name")) as rev:
        rev.correct_fact(h.wings, text=f"Wings in place of {ref(h.human)} arms.")
    assert _all_fresh(world, cache, h) == {"snowy": True, "vasha": True}

    cache = _cached_fresh(world, h)
    with world.revision(Source.manual(note="new words")) as rev:
        rev.correct_fact(h.wings, text="Wings, and no arms.")
    assert _all_fresh(world, cache, h) == {"snowy": True, "vasha": True}
