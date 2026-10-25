"""Entries (`talemate.world.entries`): held by, a fact that's what an
entry (a religion, a character) believes, not world truth. Stored as fact
origin `{"held_by": <thing_id>}`; a fact in the `belief` category is held
by its owner unless its origin says otherwise. The old beliefs-drawer rule
is gone with drawers (filing spec, "What stays as built")."""

from dataclasses import dataclass

import pytest

from talemate.world.entries import held_by, with_held_by
from talemate.world.store import Source


@dataclass
class Faiths:
    church: str
    folk: str
    tsardom: str
    light: str
    doctrine: str
    eternal: str
    candles: str
    stars: str
    land: str
    right: str
    blinded: str


@pytest.fixture
def faiths(world):
    """The Church (religion lore), the Riverfolk (culture lore), the
    Tsardom (a place), each with a plain fact; the Eternal Light (a lore
    entry, its one fact held by the Church by hand) and the Divine Right,
    a doctrine entry filed in the Church."""

    with world.revision(Source.manual(note="faiths")) as rev:
        church = rev.create_thing(
            "lore",
            fields={"name": "The Church of the Eternal Light", "hint": "religion"},
        )
        eternal = rev.add_fact(
            church, "general", "The Light watches over the faithful."
        )
        candles = rev.add_fact(church, "general", "Candles are lit at every baptism.")
        folk = rev.create_thing(
            "lore", fields={"name": "The Riverfolk", "hint": "culture"}
        )
        stars = rev.add_fact(folk, "general", "The dead are reborn as stars.")
        tsardom = rev.create_thing("place", fields={"name": "The Tsardom"})
        land = rev.add_fact(tsardom, "law", "Only the faithful may hold land.")
        light = rev.create_thing("lore", fields={"name": "The Eternal Light"})
        blinded = rev.add_fact(
            light,
            "general",
            "The Light seized every Moscavian in 994.",
            origin={"held_by": church},
        )
        doctrine = rev.create_thing(
            "lore",
            fields={"name": "The Divine Right", "filings": [{"target": church}]},
        )
        right = rev.add_fact(
            doctrine, "general", "The Tsar rules by the grace of the Light."
        )
    return Faiths(
        church=church,
        folk=folk,
        tsardom=tsardom,
        light=light,
        doctrine=doctrine,
        eternal=eternal,
        candles=candles,
        stars=stars,
        land=land,
        right=right,
        blinded=blinded,
    )


def _held(world, thing_id, fact_id, rev=None):
    view = world.view(rev=rev)
    owner = view.thing(thing_id)
    assert owner is not None
    fact = next(f for f in owner.facts if f.fact_id == fact_id)
    return held_by(view, fact, owner)


def test_held_by_origin(world, faiths):
    """A fact whose origin names a holder is held by it; a plain fact is
    held by nobody."""

    assert _held(world, faiths.light, faiths.blinded) == faiths.church
    with world.revision(Source.manual()) as rev:
        plain = rev.add_fact(faiths.light, "general", "Its shrines face east.")
    assert _held(world, faiths.light, plain) is None


def test_held_by_deleted_holder_is_hidden(world, faiths):
    """A holder that's been deleted holds nothing (the fact reads plain);
    undoing the delete brings it back, as a filing into a deleted entry
    does."""

    with world.revision(Source.manual()) as rev:
        rev.remove_thing(faiths.church)
    assert _held(world, faiths.light, faiths.blinded) is None
    world.undo([world.head_rev()])
    assert _held(world, faiths.light, faiths.blinded) == faiths.church


def _hill_clans(world):
    """The Hill Clans, a culture (lore, whose kind takes `belief` facts),
    with one belief unmarked and one marked held by the Church."""

    with world.revision(Source.manual(note="clans")) as rev:
        clans = rev.create_thing(
            "lore", fields={"name": "The Hill Clans", "hint": "culture"}
        )
        stones = rev.add_fact(clans, "belief", "The standing stones hear oaths.")
        light = rev.add_fact(clans, "general", "They keep sheep on the high fells.")
    return clans, stones, light


def test_belief_fact_is_held_by_owner(world):
    """A fact in the `belief` category is held by its owner, unmarked;
    another category of the same owner is plain."""

    clans, stones, plain = _hill_clans(world)
    assert _held(world, clans, stones) == clans
    assert _held(world, clans, plain) is None


def test_held_by_explicit_still_wins(world, faiths):
    """An explicit held-by on a belief fact beats the belief rule: another
    holder holds it, and a cleared one (`None`) leaves it plain."""

    clans, stones, _plain = _hill_clans(world)
    with world.revision(Source.manual()) as rev:
        marked = rev.add_fact(
            clans,
            "belief",
            "The Light is a stranger's god.",
            origin=with_held_by(None, faiths.church),
        )
        cleared = rev.add_fact(
            clans, "belief", "Wolves are kin.", origin=with_held_by(None, None)
        )
    assert _held(world, clans, marked) == faiths.church
    assert _held(world, clans, cleared) is None
    # a deleted explicit holder holds nothing, nor does the owner then
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(faiths.church)
    assert _held(world, clans, marked) is None
    assert _held(world, clans, stones) == clans


def test_other_facts_of_a_faith_are_plain(world, faiths):
    """Only a `belief` fact is held implicitly: a religion's, a culture's
    or a nation's other facts read plain."""

    assert _held(world, faiths.church, faiths.eternal) is None
    assert _held(world, faiths.folk, faiths.stars) is None
    assert _held(world, faiths.church, faiths.candles) is None
    assert _held(world, faiths.tsardom, faiths.land) is None


def test_doctrine_entry_not_held_implicitly(world, faiths):
    """An entry filed in a religion doesn't inherit held-by: its own facts
    are marked one by one."""

    assert _held(world, faiths.doctrine, faiths.right) is None


def test_with_held_by_merges_origin():
    """Held-by is merged into the origin's other keys, never replacing
    them."""

    holder = "a" * 32
    assert with_held_by(None, holder) == {"held_by": holder}
    assert with_held_by({"rejects_fact": "c" * 32, "tie": "b" * 32}, holder) == {
        "rejects_fact": "c" * 32,
        "tie": "b" * 32,
        "held_by": holder,
    }
    # cleared: kept as an explicit "held by nobody"
    assert with_held_by({"tie": "b" * 32, "held_by": holder}, None) == {
        "tie": "b" * 32,
        "held_by": None,
    }


def test_correct_keeps_held_by(world, faiths):
    """An edit to a held fact keeps its held-by and its other origin keys:
    the store copies the origin over."""

    with world.revision(Source.manual()) as rev:
        rev.correct_fact(
            faiths.candles,
            origin=with_held_by({"tie": faiths.tsardom}, faiths.folk),
        )
    with world.revision(Source.manual()) as rev:
        rev.correct_fact(faiths.candles, text="Candles burn at every baptism.")
        rev.correct_fact(faiths.blinded, text="The Light blinded Moscavia in 994.")

    view = world.view()
    church = view.thing(faiths.church)
    candles = next(f for f in church.facts if f.fact_id == faiths.candles)
    assert candles.text == "Candles burn at every baptism."
    assert candles.origin == {"tie": faiths.tsardom, "held_by": faiths.folk}
    assert held_by(view, candles, church) == faiths.folk
    assert _held(world, faiths.light, faiths.blinded) == faiths.church


def test_clear_held_by(world, faiths):
    """Clearing held-by makes the fact plain, and it stays plain through
    an edit; a plain statement can be set to a holder. Undo brings the
    holder back."""

    view = world.view()
    blinded = next(f for f in view.thing(faiths.light).facts)
    with world.revision(Source.manual()) as rev:
        rev.correct_fact(faiths.blinded, origin=with_held_by(blinded.origin, None))
    assert _held(world, faiths.light, faiths.blinded) is None
    cleared_rev = world.head_rev()

    eternal = next(
        f for f in view.thing(faiths.church).facts if f.fact_id == faiths.eternal
    )
    with world.revision(Source.manual()) as rev:
        rev.correct_fact(faiths.eternal, origin=with_held_by(eternal.origin, None))
    assert _held(world, faiths.church, faiths.eternal) is None
    with world.revision(Source.manual()) as rev:
        rev.correct_fact(faiths.eternal, text="The Light watches over all.")
    assert _held(world, faiths.church, faiths.eternal) is None

    church = world.view().thing(faiths.church)
    eternal = next(f for f in church.facts if f.fact_id == faiths.eternal)
    assert eternal.origin == {"held_by": None}
    with world.revision(Source.manual()) as rev:
        rev.correct_fact(
            faiths.eternal, origin=with_held_by(eternal.origin, faiths.folk)
        )
    assert _held(world, faiths.church, faiths.eternal) == faiths.folk

    world.undo([cleared_rev])
    assert _held(world, faiths.light, faiths.blinded) == faiths.church


def test_summary_prefers_cached_then_the_summary_fact(world):
    """Ruling P21: the summary is the cached prose when there is some,
    else the `about` fact marked `summary`, else the first `about` fact;
    "" for an entry with neither, or none at all."""

    from talemate.world.entries import summary, summary_fact

    with world.revision(Source.manual()) as rev:
        realm = rev.create_thing("place", fields={"name": "The Realm"})
        rev.add_fact(realm, "description", "Pine and bog.")
        rev.add_fact(realm, "about", "A northern realm.")
        plain = rev.create_thing("lore", fields={"name": "Plain"})
        rev.add_fact(plain, "general", "Nothing about it.")
    view = world.view()
    assert summary(view, realm) == "A northern realm."
    assert summary(view, realm, "") == "A northern realm."
    assert summary(view, realm, "The realm of pines.") == "The realm of pines."
    assert summary(view, plain) == ""
    assert summary(view, "f" * 32) == ""

    with world.revision(Source.manual()) as rev:
        marked = rev.add_fact(
            realm, "about", "The realm of the Tsar.", origin={"summary": True}
        )
    view = world.view()
    assert summary_fact(view.thing(realm)).fact_id == marked
    assert summary(view, realm) == "The realm of the Tsar."
