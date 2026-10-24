"""Re-point (`worldplay.repoint.repoint_stub`) on filings (Filing plan,
Task 5): the stub's names and the links' words become the target's other
names, the "hard re-point" rewrites the links' words to one of the
target's names, and filings into the stub, `within` it, and the stub's
own (with their `within` and exceptions) move onto the target, never the
old `part_of`, ties or parent (ruling F11)."""

import pytest

from talemate.world.dates import WorldDate
from talemate.world.filing import filings_of
from talemate.world.refs import ref
from talemate.world.store import Source
from talemate.worldplay.repoint import repoint_stub


def _aka(name, tag="common", everyday=False):
    return {"name": name, "tag": tag, "everyday": everyday}


def _in(target, role=None, *, within=None, since=None, exceptions=()):
    return {
        "target": target,
        "role": role,
        "since": since.model_dump(mode="json") if since else None,
        "until": None,
        "within": within,
        "exceptions": list(exceptions),
    }


def _text(world, fact_id):
    return world.view().fact(fact_id)[1].text


@pytest.fixture
def tsardom(world):
    """The Tsardom of Moscavia (a place, also "Old Moscavy"), and "the
    Tsardom", a stub for it (also "Moscavia"), linked three ways: by its
    name, by its other name and by the target's own name."""

    with world.revision(Source.manual(note="tsardom")) as rev:
        target = rev.create_thing(
            "place",
            {
                "name": "Tsardom of Moscavia",
                "aka": [_aka("Old Moscavy", tag="proper")],
            },
        )
        stub = rev.create_thing(
            "lore",
            {
                "name": "the Tsardom",
                "aka": [_aka("Moscavia", everyday=True)],
                "stub": {"ignored": False},
            },
        )
        maren = rev.create_thing("character", {"name": "Maren"})
        born = rev.add_fact(maren, "background", f"Born in {ref(stub, 'the north')}.")
        fled = rev.add_fact(
            maren, "background", f"Fled {ref(stub, 'Tsardom of Moscavia')} twice."
        )
        dreams = rev.add_fact(
            maren, "personality", f"Dreams of {ref(stub, 'Moscavia')}."
        )
    return {
        "target": target,
        "stub": stub,
        "maren": maren,
        "born": born,
        "fled": fled,
        "dreams": dreams,
    }


def test_repoint_adds_other_names(world, tsardom):
    """The stub's name, its other names and each link's words that differ
    from the target's own names become the target's common other names,
    each once; the target's own name and names, and one another entry
    holds, are left. The links keep their words."""

    t = tsardom
    with world.revision(Source.manual(note="taken")) as rev:
        rev.create_thing("lore", {"name": "The North Wind"})
        rev.add_fact(
            t["maren"], "background", f"Sings of {ref(t['stub'], 'the north')}."
        )
    done = repoint_stub(world, t["stub"], t["target"])

    assert done.aka_added == ["the Tsardom", "Moscavia", "the north"]
    assert world.view().thing(t["target"]).fields["aka"] == [
        _aka("Old Moscavy", tag="proper"),
        _aka("the Tsardom"),
        _aka("Moscavia"),
        _aka("the north"),
    ]
    assert _text(world, t["born"]) == f"Born in {ref(t['target'], 'the north')}."
    assert _text(world, t["fled"]) == (
        f"Fled {ref(t['target'], 'Tsardom of Moscavia')} twice."
    )

    # undone in one step: the names go with it
    world.undo([world.head_rev()])
    assert world.view().thing(t["target"]).fields["aka"] == [
        _aka("Old Moscavy", tag="proper")
    ]


def test_repoint_adds_names_beside_a_dated_value(world, tsardom):
    """The target's other names, last written at a story date, take the
    new ones at that date too, so they show at the latest telling."""

    t = tsardom
    with world.revision(Source.manual(note="dated")) as rev:
        rev.set_field(
            t["target"],
            "aka",
            [_aka("Old Moscavy", tag="proper"), _aka("the Realm")],
            WorldDate.of(990),
        )
    repoint_stub(world, t["stub"], t["target"])
    names = [a["name"] for a in world.view().thing(t["target"]).fields["aka"]]
    assert names == ["Old Moscavy", "the Realm", "the Tsardom", "Moscavia", "the north"]


def test_hard_repoint_uses_chosen_name(world, tsardom):
    """`use_name`: every link's words become that name, one of the target's
    own (its name or an other name, any case, written as the target has
    it), and no other names are added; anything else is refused, writing
    nothing."""

    t = tsardom
    head = world.head_rev()
    for wrong in ("Moscavia", "the Tsardom", "", "Vasha"):
        with pytest.raises(ValueError, match="names"):
            repoint_stub(world, t["stub"], t["target"], use_name=wrong)
    assert world.head_rev() == head

    done = repoint_stub(world, t["stub"], t["target"], use_name="old moscavy")
    assert done.aka_added == []
    assert done.links == 3
    for fact_id, words in (
        (t["born"], "Born in {}."),
        (t["fled"], "Fled {} twice."),
        (t["dreams"], "Dreams of {}."),
    ):
        assert _text(world, fact_id) == words.format(ref(t["target"], "Old Moscavy"))
    assert world.view().thing(t["target"]).fields["aka"] == [
        _aka("Old Moscavy", tag="proper")
    ]
    assert world.view().thing(t["stub"]) is None


def test_repoint_rewrites_filings_into_the_stub(world, tsardom):
    """A thing filed in the stub is filed in the target, its role, dates
    and exceptions kept; one filed `within` the stub is within the target;
    one filed in both keeps its filing in the target, the stub's
    exceptions joining it. No `part_of`, ties or parent is written."""

    t = tsardom
    with world.revision(Source.manual(note="filed")) as rev:
        rev.change_stub_kind(t["stub"], "place")
        army = rev.create_thing("lore", {"name": "The Tsar's Army"})
        city = rev.create_thing("place", {"name": "Kremova"})
        rev.set_field(city, "filings", [_in(t["stub"], "capital")], None)
        rev.set_field(t["stub"], "filings", [_in(army)], None)
        oskar = rev.create_thing("character", {"name": "Oskar"})
        levy = rev.add_fact(
            oskar, "ties", "Exempt from the levies.", origin={"tie": army}
        )
        rev.set_field(
            oskar,
            "filings",
            [_in(army, "trooper", within=t["stub"], exceptions=[levy])],
            None,
        )
        ilya = rev.create_thing("character", {"name": "Ilya"})
        oath = rev.add_fact(ilya, "ties", "Swore no oath.", origin={"tie": t["stub"]})
        rev.set_field(
            ilya,
            "filings",
            [_in(t["target"], "subject"), _in(t["stub"], "soldier", exceptions=[oath])],
            None,
        )

    done = repoint_stub(world, t["stub"], t["target"])
    view = world.view()
    assert [(f.target, f.role) for f in filings_of(view, city)] == [
        (t["target"], "capital")
    ]
    (filing,) = filings_of(view, oskar)
    assert (filing.target, filing.within, filing.exceptions) == (
        army,
        t["target"],
        [levy],
    )
    (filing,) = filings_of(view, ilya)
    assert (filing.target, filing.role, filing.exceptions) == (
        t["target"],
        "subject",
        [oath],
    )
    # the exception filed under the stub is filed under the target
    assert view.fact(oath)[1].origin == {"tie": t["target"]}
    assert any("Ilya was filed in both" in note for note in done.notes)
    for thing_id in (city, oskar, ilya, t["target"]):
        fields = view.thing(thing_id).fields
        assert not {"part_of", "ties", "parent"} & {
            k for k, v in fields.items() if v is not None
        }


def test_repoint_carries_the_stubs_own_filings(world):
    """The stub's own filings go onto the target with their role, dates,
    `within` and exceptions (mapped onto the moved copies), beside the
    target's own (Task 4 review, M5); one into an entry the target is
    filed in already leaves the target's as it is."""

    with world.revision(Source.manual(note="setup")) as rev:
        dawn = rev.create_thing("lore", {"name": "The White Dawn"})
        council = rev.create_thing(
            "lore", {"name": "The Council", "filings": [_in(dawn)]}
        )
        guild = rev.create_thing("lore", {"name": "The Guild"})
        vasha = rev.create_thing(
            "character", {"name": "Vasha", "filings": [_in(guild, "smith")]}
        )
        stub = rev.create_thing(
            "character", {"name": "the Grey Pilgrim", "stub": {"ignored": False}}
        )
        doubt = rev.add_fact(stub, "ties", "Doubts the vigil.", origin={"tie": dawn})
        rev.set_field(
            stub,
            "filings",
            [
                _in(
                    dawn,
                    "pilgrim",
                    within=council,
                    since=WorldDate.of(1010),
                    exceptions=[doubt],
                ),
                _in(guild, "apprentice"),
            ],
            None,
        )

    repoint_stub(world, stub, vasha)
    view = world.view()
    (copy,) = [f for f in view.thing(vasha).facts if f.text == "Doubts the vigil."]
    assert copy.fact_id != doubt
    held, carried = filings_of(view, vasha)
    assert (held.target, held.role) == (guild, "smith")
    assert (carried.target, carried.role, carried.within, carried.since) == (
        dawn,
        "pilgrim",
        council,
        WorldDate.of(1010),
    )
    assert carried.exceptions == [copy.fact_id]


def test_repoint_drops_what_no_longer_holds_under_the_target(world):
    """Onto the Hall: the stub's filing in the Dawn within the Hall can't be
    within the Hall itself, so the Hall is filed in the Dawn whole; its
    filing in the Vigil, which sits in the Hall, would put the Hall inside
    itself and is left. Each with a note."""

    with world.revision(Source.manual(note="setup")) as rev:
        dawn = rev.create_thing("lore", {"name": "The White Dawn"})
        council = rev.create_thing(
            "lore", {"name": "The Council", "filings": [_in(dawn)]}
        )
        hall = rev.create_thing("lore", {"name": "The Hall", "filings": [_in(council)]})
        vigil = rev.create_thing("lore", {"name": "The Vigil", "filings": [_in(hall)]})
        stub = rev.create_thing(
            "lore",
            {
                "name": "the Old Hall",
                "stub": {"ignored": False},
                "filings": [_in(dawn, "seat", within=hall), _in(vigil)],
            },
        )

    done = repoint_stub(world, stub, hall)
    filings = filings_of(world.view(), hall)
    assert [(f.target, f.role, f.within) for f in filings] == [
        (council, None, None),
        (dawn, "seat", None),
    ]
    assert any("within no part" in note for note in done.notes)
    assert any(
        "isn't filed in The Vigil: it would be inside itself" in note
        for note in done.notes
    )


def test_repoint_refuses_a_filing_loop(world):
    """A thing filed in the stub, when the target sits in that thing,
    would be inside itself: refused, writing nothing."""

    with world.revision(Source.manual(note="setup")) as rev:
        realm = rev.create_thing("lore", {"name": "The Realm"})
        city = rev.create_thing("lore", {"name": "The City"})
        rev.set_field(realm, "filings", [_in(city)], None)
        stub = rev.create_thing(
            "lore", {"name": "the Kingdom", "stub": {"ignored": False}}
        )
        rev.set_field(city, "filings", [_in(stub)], None)
    head = world.head_rev()
    with pytest.raises(ValueError, match="The City's filings would put it inside"):
        repoint_stub(world, stub, realm)
    assert world.head_rev() == head
