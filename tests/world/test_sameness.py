"""Same-thing candidates found in code: the things a new name could be the
same as, by its name words (the fact placement probe's "Same-thing check"
and "Code instead of model"), on the names of the owner's acceptance
snapshot."""

from talemate.world.sameness import SameCandidate, same_candidates
from talemate.world.store import Source


def _aka(*names):
    return [
        {"name": n, "tag": "common", "everyday": i == 0} for i, n in enumerate(names)
    ]


# the snapshot's entries (`docs/superpowers/probes/2026-10-22-fact-placement.md`),
# The Ashenmere Caves left out (it's the one being made), spheres, species
# and races as lore: (kind, name, other names, stub)
SNAPSHOT = [
    ("place", "The Illumination Shrine, Moskov", [], True),
    ("lore", "Pure-line Moscavians", [], True),
    ("lore", "The Patriarch of Moscavia", [], True),
    ("event", "The Festival of the Solstice Flame", [], True),
    ("lore", "Zakonnik", [], True),
    ("lore", "Frosted Wing", [], True),
    ("place", "The Shrine of First Dawn", [], True),
    ("event", "Great Synod of Moskov", [], True),
    ("lore", "White Talon", _aka("Belyy Kogtyo"), False),
    ("lore", "The Canonical Texts of Moskov", [], True),
    ("place", "Free Cities of the Southern Reach", [], True),
    ("lore", "The Synod of Lanterns", [], True),
    ("place", "Stonehold", [], True),
    ("place", "Cathedral of the Eternal Light", [], True),
    ("lore", "Snowy Moscavian Owls", _aka("Snow Ow-folk"), False),
    ("place", "Ashenmere", _aka("The Ashen Caves", "Ashenmere Caverns"), False),
    ("lore", "The Doctrine of Cost", [], True),
    ("lore", "Eared Moscavian Owls", _aka("Eared Owl-folk"), False),
    ("lore", "Tsar", [], True),
    ("lore", "Eternal Light", [], False),
    ("place", "Keshra", [], True),
    (
        "lore",
        "Moscavian Owl-folk",
        _aka("Owl-folk", "Moscavian Owls", "Owls"),
        False,
    ),
    ("place", "Greyholm", [], True),
    ("place", "The Cathedral of the Eternal Light, Moskov", [], True),
    ("lore", "Patriarchate", [], True),
    ("lore", "Monastic Scriptoria", [], True),
    ("lore", "The Law of Resonance", [], False),
    ("lore", "The Divine Right of the Tsar", [], False),
    ("place", "Valdmark", [], True),
    ("place", "The Greyholm Archive", [], True),
    ("lore", "Ashenmere rune dialect", [], True),
    ("lore", "The Holy Synod", [], True),
    ("place", "Moskov", _aka("Moscow"), False),
    ("place", "Volga River", [], True),
    ("place", "Kremlin", [], True),
    ("place", "Tsardom of Moscavia", _aka("Moscavia"), False),
    ("lore", "The Feast of the Illumination", [], True),
    ("event", "Blinding Transformation", [], True),
    ("lore", "The Prohibition of the Flesh Rune", [], True),
    ("lore", "Firescribing", [], True),
    ("place", "The Northern Steppe", [], True),
    ("event", "Burning of Greyholm", [], True),
    ("item", "First Codex of Aelberth", _aka("Codex Aelberth"), False),
    ("lore", "Patriarch", [], False),
    ("lore", "Runeweaving", _aka("Runework"), False),
    ("lore", "The Unwritten Rune", _aka("The Blank Rune", "The Unmarked Glyph"), False),
    ("place", "Greymarch Mountains", [], True),
    ("lore", "Deepcarving", _aka("Subsurface Rune Etching"), False),
    ("place", "Moskva River", [], True),
    ("place", "Southern Reach", [], True),
    ("place", "Greywood Valley", [], True),
    ("lore", "The Patriarch of Moskov", [], True),
    ("lore", "Baptism by Candlelight", [], True),
    ("lore", "Church of the Eternal Light", _aka("The Church", "The Light"), False),
    ("lore", "Runeweavers' Conclave", [], True),
    ("lore", "The Dawn Vigil", [], True),
    ("lore", "The Illumination", [], False),
]


def _make(world, entries):
    ids = {}
    with world.revision(Source.manual()) as rev:
        for kind, name, aka, stub in entries:
            fields: dict = {"name": name}
            if aka:
                fields["aka"] = aka
            if stub:
                fields["stub"] = {"ignored": False}
            ids[name] = rev.create_thing(kind, fields=fields)
    return ids


def _found(world, name, ids, near=()):
    by_id = {v: k for k, v in ids.items()}
    return [
        (by_id[c.thing_id], c.reason)
        for c in same_candidates(world.view(), name, near_ids=list(near))
    ]


def test_same_candidates_ashenmere_caves(world):
    ids = _make(world, SNAPSHOT)
    found = _found(world, "The Ashenmere Caves", ids)
    # Ashenmere's name is inside it; the rune dialect only shares a word
    assert found == [("Ashenmere", "inside"), ("Ashenmere rune dialect", "word")]


def test_same_candidates_conclave_inside_runeweavers_conclave(world):
    ids = _make(world, SNAPSHOT)
    assert _found(world, "the Conclave", ids) == [("Runeweavers' Conclave", "inside")]


def test_same_candidates_snapshot_pairs(world):
    """The probe's labelled "same" pairs between entries: each one's other
    side is a candidate."""

    ids = _make(world, SNAPSHOT)
    pairs = [
        (
            "Cathedral of the Eternal Light",
            "The Cathedral of the Eternal Light, Moskov",
        ),
        ("Patriarch", "The Patriarch of Moscavia"),
        ("The Patriarch of Moskov", "The Patriarch of Moscavia"),
        ("The Holy Synod", "The Synod of Lanterns"),
    ]
    for a, b in pairs:
        assert b in [name for name, _ in _found(world, a, ids)], (a, b)


def test_common_word_not_a_candidate(world):
    ids = _make(world, SNAPSHOT)
    # "Moskov" is in 6 of the snapshot's 74 names: the city isn't the same
    # as a foundry in it, nor are the other things named after it
    assert _found(world, "The Moskov Bell Foundry", ids) == []
    # a name that is the city's still finds it
    assert _found(world, "Moskov", ids) == [("Moskov", "aka")]
    # and an uncommon word still counts alongside a common one
    assert _found(world, "The Moskov Kremlin Gate", ids) == [("Kremlin", "inside")]


def test_common_word_tsar(world):
    names = [("lore", f"Thing {n}", [], False) for n in "ABCDEFGHIJKLMNOPQR"]
    names += [
        ("lore", "Tsar", [], False),
        ("lore", "The Divine Right of the Tsar", [], False),
        ("character", "Tsar Alexei", [], False),
    ]
    ids = _make(world, names)
    # 3 of 21 names hold "tsar": too common to make a candidate on its own
    assert _found(world, "The Tsar's Hunt", ids) == []
    assert _found(world, "Tsar", ids) == [("Tsar", "aka")]


def test_small_world_has_no_common_words(world):
    ids = _make(
        world,
        [
            ("lore", "Tsar", [], False),
            ("lore", "The Divine Right of the Tsar", [], False),
            ("character", "Tsar Alexei", [], False),
        ],
    )
    # under 20 names, only the articles and stop words are common
    found = _found(world, "The Tsar's Hunt", ids)
    assert sorted(found) == [
        ("The Divine Right of the Tsar", "word"),
        ("Tsar", "inside"),
        ("Tsar Alexei", "word"),
    ]
    assert found[0] == ("Tsar", "inside")
    assert _found(world, "The Hunt", ids) == []


def test_same_name_candidates_are_told_apart(world):
    with world.revision(Source.manual()) as rev:
        city = rev.create_thing("place", fields={"name": "Moskov"})
        tale = rev.create_thing(
            "lore", fields={"name": "Moskov", "stub": {"ignored": False}}
        )
    view = world.view()
    found = same_candidates(view, "moskov", near_ids=[])
    assert {c.thing_id for c in found} == {city, tale}
    assert all(c.reason == "aka" for c in found)
    assert {view.thing(c.thing_id).kind for c in found} == {"place", "lore"}


def test_same_candidates_other_name(world):
    ids = _make(world, SNAPSHOT)
    # "Codex Aelberth" is the Codex's other name; "Aelberth" alone is inside
    # it, and in nothing else
    assert _found(world, "Codex Aelberth", ids) == [("First Codex of Aelberth", "aka")]
    assert _found(world, "Aelberth", ids) == [("First Codex of Aelberth", "inside")]


def test_reason_then_nearness_orders(world):
    with world.revision(Source.manual()) as rev:
        far_aka = rev.create_thing(
            "place", fields={"name": "Lowmarsh", "aka": _aka("Greyholm Fen")}
        )
        near_inside = rev.create_thing("place", fields={"name": "Greyholm Fen Road"})
        far_word = rev.create_thing("place", fields={"name": "Greyholm Bridge"})
        near_word = rev.create_thing("place", fields={"name": "Fen Mill"})
    view = world.view()
    found = same_candidates(
        view, "the Greyholm Fen", near_ids=[near_word, near_inside], limit=5
    )
    assert [(c.thing_id, c.reason) for c in found] == [
        (far_aka, "aka"),
        (near_inside, "inside"),
        (near_word, "word"),
        (far_word, "word"),
    ]
    scores = [c.score for c in found]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 < s <= 1.0 for s in scores)
    assert found[2].score > found[3].score
    top = same_candidates(view, "the Greyholm Fen", near_ids=[], limit=2)
    assert [c.thing_id for c in top] == [far_aka, near_inside]
    assert same_candidates(view, "the Greyholm Fen", near_ids=[], limit=0) == []


def test_ignored_stubs_and_removed_things_are_never_candidates(world):
    with world.revision(Source.manual()) as rev:
        ignored = rev.create_thing(
            "place", fields={"name": "Greyholm", "stub": {"ignored": True}}
        )
        removed = rev.create_thing("place", fields={"name": "Greyholm Keep"})
        kept = rev.create_thing("place", fields={"name": "Greyholm Gate"})
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(removed)
    found = same_candidates(world.view(), "Greyholm", near_ids=[ignored, removed])
    assert found == [
        SameCandidate(thing_id=kept, reason="inside", score=found[0].score)
    ]


def test_no_candidates_in_empty_world(world):
    assert same_candidates(world.view(), "Ashenmere", near_ids=[]) == []
    assert same_candidates(world.view(), "", near_ids=[]) == []
    assert same_candidates(world.view(), "The", near_ids=[]) == []
