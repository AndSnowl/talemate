"""Merge one entry into another (curation Task 9, spec goal 5).

"Merge into..." folds a full entry into another the way Re-point folds a
stub (`repoint.plan_merge`, the generalised mover), and the owner picks
the outcome: the main name, the facts (repeats arrive unticked) and, for
each pair of facts that may disagree, which one stands (ruling C14: the
pairs come from code, `decide.contradiction_pairs`, as the curation
probe's probe 3 fell back to). No model call is made."""

from typing import NamedTuple

import pytest

from talemate.world.dates import WorldDate
from talemate.world.kinds import UNSORTED_DRAWER_ID
from talemate.world.refs import parse_refs, ref
from talemate.world.store import Source
from talemate.worldplay.decide import contradiction_pairs
from talemate.worldplay.merge import MergePreview, accept_merge, preview_merge
from talemate.worldplay.repoint import repoint_stub

LANDS, MILITARY, DIVISIONS, RANKS = "1a4d0001", "3111a001", "d1d50001", "4a5c0001"

SYSTEM_A = "Ashenmere is a cave system beneath the northern hills."
SYSTEM_B = "The Ashenmere Caves are a cave system beneath the northern hills."
DIALECT_A = "The Ashenmere dialect was rediscovered by the Conclave's scholars."
DIALECT_B = "The Ashenmere dialect was rediscovered by Conclave scholars."
LICHEN_A = "The caves glow with blue lichen."
LICHEN_B = "Green lichen covers the cave walls."
SMUGGLERS = "Smugglers hide their goods in the caves."


def _aka(name, tag="common", everyday=False):
    return {"name": name, "tag": tag, "everyday": everyday}


class Mere(NamedTuple):
    tsardom: str
    northreach: str
    ashenmere: str
    caves: str
    deepvault: str
    vasha: str
    system_a: str
    dialect_a: str
    lichen_a: str
    deep_a: str
    system_b: str
    dialect_b: str
    lichen_b: str
    smugglers: str
    explored: str


@pytest.fixture
def mere(world):
    """Present 1000. Ashenmere, a region in the Tsardom's Lands & Sites,
    and The Ashenmere Caves, a cave system under Northreach: one place
    written twice. The Caves restate Ashenmere's first line (a repeat),
    date the dialect's rediscovery 950 against Ashenmere's 947, and give
    the lichen another colour. Deepvault's parent is the Caves, and Vasha
    and Ashenmere both link to them."""

    world.set_present(WorldDate.of(1000))
    with world.revision(Source.manual(note="mere")) as rev:
        tsardom = rev.create_thing(
            "sphere",
            {
                "name": "Tsardom of Moscavia",
                "template": "nation",
                "drawers": [{"id": LANDS, "type": "places", "title": "Lands & Sites"}],
            },
        )
        northreach = rev.create_thing("place", {"name": "Northreach"})
        ashenmere = rev.create_thing(
            "place",
            {
                "name": "Ashenmere",
                "kind": "region",
                "aka": [_aka("the Mere", everyday=True)],
                "part_of": {"sphere": tsardom, "drawer": LANDS},
            },
        )
        caves = rev.create_thing(
            "place",
            {
                "name": "The Ashenmere Caves",
                "kind": "cave system",
                "parent": northreach,
                "aka": [_aka("the Deeps", tag="proper")],
            },
        )
        deepvault = rev.create_thing("place", {"name": "Deepvault", "parent": caves})
        vasha = rev.create_thing("character", {"name": "Vasha"})
        system_a = rev.add_fact(ashenmere, "general", SYSTEM_A)
        dialect_a = rev.add_fact(
            ashenmere, "history", DIALECT_A, valid_from=WorldDate.of(947)
        )
        lichen_a = rev.add_fact(ashenmere, "description", LICHEN_A)
        deep_a = rev.add_fact(
            ashenmere,
            "description",
            f"Its deepest halls open onto {ref(caves, 'the Caves')}.",
        )
        system_b = rev.add_fact(caves, "general", SYSTEM_B)
        dialect_b = rev.add_fact(
            caves, "history", DIALECT_B, valid_from=WorldDate.of(950)
        )
        lichen_b = rev.add_fact(caves, "description", LICHEN_B)
        smugglers = rev.add_fact(caves, "general", SMUGGLERS)
        explored = rev.add_fact(
            vasha, "background", f"Explored {ref(caves, 'the Caves')} as a girl."
        )
    return Mere(
        tsardom=tsardom,
        northreach=northreach,
        ashenmere=ashenmere,
        caves=caves,
        deepvault=deepvault,
        vasha=vasha,
        system_a=system_a,
        dialect_a=dialect_a,
        lichen_a=lichen_a,
        deep_a=deep_a,
        system_b=system_b,
        dialect_b=dialect_b,
        lichen_b=lichen_b,
        smugglers=smugglers,
        explored=explored,
    )


def _texts(world, thing_id):
    view = world.view()
    return [view.render(f.text) for f in world.live_facts(thing_id)]


def _key(preview, a):
    return next(p.key for p in preview.pairs if p.a == a)


def _snapshot(world, ids):
    view = world.view()
    things = {}
    for thing_id in ids:
        state = view.thing(thing_id)
        things[thing_id] = (
            None
            if state is None
            else (
                state.fields,
                sorted(
                    (f.fact_id, f.text, f.valid_from, f.valid_until, f.overrides)
                    for f in world.live_facts(thing_id)
                ),
            )
        )
    return things


# --- the preview ---------------------------------------------------------------


def test_merge_preview_names_facts_pairs(world, mere):
    """The preview offers both names, lists the from-side's facts (the
    repeat unticked, with its match) beside the into-side's, pairs the
    facts that may disagree (the dates first, with their years) and counts
    what moves. It writes nothing, and makes no model call."""

    m = mere
    head = world.head_rev()
    preview = preview_merge(world, m.caves, m.ashenmere)
    assert world.head_rev() == head
    assert isinstance(preview, MergePreview)
    assert preview.names == ["Ashenmere", "The Ashenmere Caves"]

    mine = {f.fact_id: f for f in preview.facts if f.side == "from"}
    assert list(mine) == [m.system_b, m.dialect_b, m.lichen_b, m.smugglers]
    assert mine[m.system_b].ticked is False
    assert mine[m.system_b].repeat_of["fact_id"] == m.system_a
    # a pair is no repeat: the dates disagree, the lichen only overlaps
    for fact_id in (m.dialect_b, m.lichen_b, m.smugglers):
        assert mine[fact_id].ticked is True
        assert mine[fact_id].repeat_of is None
    assert [f.fact_id for f in preview.facts if f.side == "into"] == [
        m.system_a,
        m.dialect_a,
        m.lichen_a,
        m.deep_a,
    ]

    assert [(p.a, p.b, p.years) for p in preview.pairs] == [
        (m.dialect_b, m.dialect_a, (950, 947)),
        (m.lichen_b, m.lichen_a, None),
    ]
    assert preview.pairs[1].a_text == LICHEN_B
    assert preview.pairs[1].b_text == LICHEN_A
    assert preview.moves == {
        "facts": 3,
        "links": 2,
        "fields": 1,
        "filings": 0,
        "ties": 0,
    }


def test_contradiction_pairs_is_code_only(world, mere):
    """The pair finder: one fact from each side with word overlap of 0.4
    or more either way, and the dates that disagree, dated pairs first. The
    restatement is a pair here too; the merge preview leaves it out."""

    m = mere
    pairs = contradiction_pairs(world.view(), m.caves, m.ashenmere)
    assert [(p.a, p.b) for p in pairs] == [
        (m.dialect_b, m.dialect_a),
        (m.system_b, m.system_a),
        (m.lichen_b, m.lichen_a),
    ]
    assert pairs[0].years == (950, 947)
    assert pairs[1].score == 1.0
    assert pairs[2].score == 0.5


# --- the merge ---------------------------------------------------------------


def test_merge_moves_links_and_fields(world, mere):
    """One revision: the ticked facts copied (new ids), the links and the
    field naming the Caves pointed at Ashenmere (Ashenmere's own link made
    its words), an empty field filled and a conflicting one noted, the
    filing kept, the Caves removed; prose for Ashenmere and for the field
    that changed."""

    m = mere
    preview = preview_merge(world, m.caves, m.ashenmere)
    head = world.head_rev()
    done = accept_merge(world, preview, main_name="Ashenmere")
    assert world.head_rev() == head + 1

    view = world.view()
    assert view.thing(m.caves) is None
    ashenmere = view.thing(m.ashenmere)
    assert _texts(world, m.ashenmere) == [
        SYSTEM_A,
        DIALECT_A,
        LICHEN_A,
        "Its deepest halls open onto the Caves.",
        DIALECT_B,
        LICHEN_B,
        SMUGGLERS,
    ]
    copied = [f.fact_id for f in world.live_facts(m.ashenmere)][4:]
    assert not set(copied) & {m.dialect_b, m.lichen_b, m.smugglers}
    assert done.facts_moved == 3
    assert done.links == 2

    vasha = next(f for f in world.live_facts(m.vasha) if f.fact_id == m.explored)
    assert vasha.text == f"Explored {ref(m.ashenmere, 'the Caves')} as a girl."
    assert view.thing(m.deepvault).fields["parent"] == m.ashenmere
    assert ashenmere.fields["parent"] == m.northreach
    assert ashenmere.fields["kind"] == "region"
    assert any("kind" in note for note in done.notes)
    assert ashenmere.fields["part_of"] == {"sphere": m.tsardom, "drawer": LANDS}
    assert done.prose[0] == m.ashenmere
    assert m.deepvault in done.prose


def test_merge_main_name_choice_other_becomes_aka(world, mere):
    m = mere
    preview = preview_merge(world, m.caves, m.ashenmere)
    accept_merge(world, preview, main_name="Ashenmere")
    assert world.view().thing(m.ashenmere).fields["aka"] == [
        _aka("the Mere", everyday=True),
        _aka("The Ashenmere Caves"),
        _aka("the Deeps", tag="proper"),
        _aka("the Caves"),
    ]


def test_merge_main_name_from_the_other_side(world, mere):
    """The from-side's name as the main name: the into-side's own name
    becomes a common other name, and an other name it had that is now the
    main name is dropped."""

    m = mere
    with world.revision(Source.manual(note="aka")) as rev:
        rev.set_field(
            m.ashenmere,
            "aka",
            [_aka("the Mere", everyday=True), _aka("The Ashenmere Caves")],
            None,
        )
    preview = preview_merge(world, m.caves, m.ashenmere)
    done = accept_merge(world, preview, main_name="The Ashenmere Caves")
    view = world.view()
    assert view.name_of(m.ashenmere) == "The Ashenmere Caves"
    assert view.thing(m.ashenmere).fields["aka"] == [
        _aka("the Mere", everyday=True),
        _aka("Ashenmere"),
        _aka("the Deeps", tag="proper"),
        _aka("the Caves"),
    ]
    assert done.target_name == "The Ashenmere Caves"


@pytest.mark.parametrize(
    ("choice", "lose", "into_dialect", "from_dialect"),
    [
        ("a", "remove", None, (950, None)),
        ("b", "remove", (947, None), None),
        ("both", "remove", (947, None), (950, None)),
        ("a", "end", (947, 1000), (950, None)),
        ("b", "end", (947, None), (950, 1000)),
    ],
)
def test_merge_pair_keep_choices(world, mere, choice, lose, into_dialect, from_dialect):
    """Each pair: keep A (the from-side's), B (the into-side's) or both.
    The loser is removed (the from-side's simply isn't copied) or, with
    `lose="end"`, ended at the world's now. A pair left unanswered keeps
    both."""

    m = mere
    preview = preview_merge(world, m.caves, m.ashenmere)
    accept_merge(
        world,
        preview,
        main_name="Ashenmere",
        keep={_key(preview, m.dialect_b): choice},
        lose=lose,
    )

    def years(text):
        found = [
            f
            for f in world.live_facts(m.ashenmere)
            if world.view().render(f.text) == text
        ]
        assert len(found) <= 1
        if not found:
            return None
        fact = found[0]
        return (
            fact.valid_from.to_datetime().year,
            fact.valid_until.to_datetime().year if fact.valid_until else None,
        )

    assert years(DIALECT_A) == into_dialect
    assert years(DIALECT_B) == from_dialect
    # the lichen pair was left: both stand
    assert LICHEN_A in _texts(world, m.ashenmere)
    assert LICHEN_B in _texts(world, m.ashenmere)


def test_merge_repeats_unticked(world, mere):
    """A repeat arrives unticked and isn't copied; ticked by the owner, it
    is. An override of a fact that isn't copied points at what it
    repeats."""

    m = mere
    with world.revision(Source.manual(note="override")) as rev:
        rev.correct_fact(m.explored, overrides=[m.system_b])
    preview = preview_merge(world, m.caves, m.ashenmere)
    accept_merge(world, preview, main_name="Ashenmere")
    assert _texts(world, m.ashenmere).count(SYSTEM_A) == 1
    assert SYSTEM_B not in _texts(world, m.ashenmere)
    explored = next(f for f in world.live_facts(m.vasha) if f.fact_id == m.explored)
    assert explored.overrides == [m.system_a]

    world.undo([world.head_rev()])
    preview = preview_merge(world, m.caves, m.ashenmere)
    for fact in preview.facts:
        if fact.fact_id == m.system_b:
            fact.ticked = True
    accept_merge(world, preview, main_name="Ashenmere")
    assert SYSTEM_B in _texts(world, m.ashenmere)
    copy = next(f.fact_id for f in world.live_facts(m.ashenmere) if f.text == SYSTEM_B)
    explored = next(f for f in world.live_facts(m.vasha) if f.fact_id == m.explored)
    assert explored.overrides == [copy]


def test_merge_refusals_write_nothing(world, mere):
    m = mere
    with world.revision(Source.manual(note="more")) as rev:
        saltlore = rev.create_thing("lore", {"name": "Saltlore"})
        hope = rev.create_thing("lore", {"name": "Hope", "stub": {"ignored": True}})
        rumour = rev.create_thing(
            "place", {"name": "Rumour", "stub": {"ignored": False}}
        )
        gone = rev.create_thing("place", {"name": "Gone"})
    with world.revision(Source.manual(note="gone")) as rev:
        rev.remove_thing(gone)
    world.scenes().create("Descent", WorldDate.of(1000), player_thing_id=m.vasha)
    head = world.head_rev()
    for from_id, into_id, error, words in (
        (m.caves, m.caves, ValueError, "itself"),
        (m.caves, gone, KeyError, "no such thing"),
        (m.caves, hope, ValueError, "ignored"),
        (m.caves, rumour, ValueError, "stub"),
        # Deepvault's parent can't be lore
        (m.caves, saltlore, ValueError, "Deepvault's parent"),
        # a sphere with parts can't fold into a place
        (m.tsardom, m.northreach, ValueError, "isn't a sphere"),
        # a scene's player
        (m.vasha, saltlore, ValueError, "the scene Descent"),
    ):
        with pytest.raises(error, match=words):
            preview_merge(world, from_id, into_id)
    assert world.head_rev() == head

    preview = preview_merge(world, m.caves, m.ashenmere)
    with pytest.raises(ValueError, match="main name"):
        accept_merge(world, preview, main_name="Northreach")
    with pytest.raises(ValueError, match="no such pair"):
        accept_merge(world, preview, main_name="Ashenmere", keep={"x:y": "a"})
    with pytest.raises(ValueError, match="pick"):
        accept_merge(
            world,
            preview,
            main_name="Ashenmere",
            keep={_key(preview, m.dialect_b): "neither"},
        )
    # a fact written on the Caves since the preview: preview it again
    with world.revision(Source.manual(note="later")) as rev:
        rev.add_fact(m.caves, "general", "Bats roost in the upper galleries.")
    head = world.head_rev()
    with pytest.raises(ValueError, match="preview it again"):
        accept_merge(world, preview, main_name="Ashenmere")
    assert world.head_rev() == head


def test_undo_redo_merge(world, mere):
    """One undo restores both entries, the links and the field; undoing
    the undo gives back the merge as it was (ruling R1: the copies have
    ids of their own)."""

    m = mere
    ids = [m.ashenmere, m.caves, m.deepvault, m.vasha]
    before = _snapshot(world, ids)
    preview = preview_merge(world, m.caves, m.ashenmere)
    accept_merge(
        world,
        preview,
        main_name="The Ashenmere Caves",
        keep={_key(preview, m.dialect_b): "a"},
    )
    merged_rev = world.head_rev()
    after = _snapshot(world, ids)

    undone = world.undo([merged_rev])
    assert undone.conflicts == []
    assert _snapshot(world, ids) == before

    redone = world.undo([undone.undo_rev])
    assert redone.conflicts == []
    assert _snapshot(world, ids) == after


# --- ties ----------------------------------------------------------------------


class Host(NamedTuple):
    tsardom: str
    army: str
    host: str
    frost: str
    talon: str
    oskar: str
    ilya: str


@pytest.fixture
def host(world):
    """The Tsar's Army (an order sphere, unfiled, with the White Talon in
    its Divisions) and the Tsar's Host (the same army written twice: an
    order filed in the Tsardom's Military, with the Frosted Wing in its
    Divisions). Oskar rides with the Host, within the Frosted Wing; Ilya
    is a soldier of the Tsardom, within the Host."""

    with world.revision(Source.manual(note="host")) as rev:
        tsardom = rev.create_thing(
            "sphere",
            {
                "name": "Tsardom of Moscavia",
                "template": "nation",
                "drawers": [{"id": MILITARY, "type": "structure", "title": "Military"}],
            },
        )
        army = rev.create_thing(
            "sphere",
            {
                "name": "The Tsar's Army",
                "template": "order",
                "drawers": [
                    {"id": DIVISIONS, "type": "structure", "title": "Divisions"}
                ],
            },
        )
        host = rev.create_thing(
            "sphere",
            {
                "name": "The Tsar's Host",
                "template": "order",
                "drawers": [{"id": RANKS, "type": "structure", "title": "Divisions"}],
                "part_of": {"sphere": tsardom, "drawer": MILITARY},
            },
        )
        talon = rev.create_thing(
            "lore",
            {
                "name": "The White Talon",
                "part_of": {"sphere": army, "drawer": DIVISIONS},
            },
        )
        frost = rev.create_thing(
            "lore",
            {"name": "The Frosted Wing", "part_of": {"sphere": host, "drawer": RANKS}},
        )
        oskar = rev.create_thing(
            "character",
            {
                "name": "Oskar",
                "ties": [
                    {
                        "sphere": host,
                        "role": "rider",
                        "since": None,
                        "until": None,
                        "within": frost,
                    }
                ],
            },
        )
        ilya = rev.create_thing(
            "character",
            {
                "name": "Ilya",
                "ties": [
                    {
                        "sphere": tsardom,
                        "role": "soldier",
                        "since": None,
                        "until": None,
                        "within": host,
                    }
                ],
            },
        )
        rev.add_fact(host, "about", "The Tsar's Host is the Tsardom's army.")
    return Host(tsardom, army, host, frost, talon, oskar, ilya)


def test_merge_sphere_repoints_parts_and_ties(world, host):
    """A sphere merged into a sphere: its parts are filed in the other,
    ties to it and `within` it point at the other, and the other, filed
    nowhere, takes its filing."""

    h = host
    preview = preview_merge(world, h.host, h.army)
    assert preview.moves["filings"] == 1
    assert preview.moves["ties"] == 2
    accept_merge(world, preview, main_name="The Tsar's Army")
    view = world.view()
    assert view.thing(h.host) is None
    # the Host's Divisions drawer isn't the Army's (by id): Unsorted
    assert view.thing(h.frost).fields["part_of"] == {
        "sphere": h.army,
        "drawer": UNSORTED_DRAWER_ID,
    }
    assert view.thing(h.army).fields["part_of"] == {
        "sphere": h.tsardom,
        "drawer": MILITARY,
    }
    (oskar,) = view.thing(h.oskar).fields["ties"]
    assert (oskar["sphere"], oskar["within"]) == (h.army, h.frost)
    (ilya,) = view.thing(h.ilya).fields["ties"]
    assert (ilya["sphere"], ilya["within"]) == (h.tsardom, h.army)


def test_merge_sphere_into_non_sphere_refused(world, host):
    h = host
    head = world.head_rev()
    with pytest.raises(ValueError, match="parts or ties"):
        preview_merge(world, h.host, h.talon)
    assert world.head_rev() == head


def test_merge_character_ties_carry_over(world, host):
    """A character's ties go over, but one the other has by sphere and
    role; its exceptions go with its facts."""

    h = host
    with world.revision(Source.manual(note="grey")) as rev:
        grey = rev.create_thing(
            "character",
            {
                "name": "Oskar the Grey",
                "ties": [
                    {"sphere": h.host, "role": "rider", "since": None, "until": None},
                    {
                        "sphere": h.tsardom,
                        "role": "subject",
                        "since": None,
                        "until": None,
                    },
                ],
            },
        )
        rev.add_fact(
            grey,
            "ties",
            "Exempt from the Tsardom's levies.",
            origin={"tie": h.tsardom},
        )
    preview = preview_merge(world, grey, h.oskar)
    accept_merge(world, preview, main_name="Oskar")
    view = world.view()
    ties = view.thing(h.oskar).fields["ties"]
    assert [(t["sphere"], t["role"]) for t in ties] == [
        (h.host, "rider"),
        (h.tsardom, "subject"),
    ]
    assert ties[0]["within"] == h.frost
    (exception,) = [
        f for f in world.live_facts(h.oskar) if f.origin == {"tie": h.tsardom}
    ]
    assert exception.text == "Exempt from the Tsardom's levies."
    assert parse_refs(exception.text) == []


def test_repoint_stub_unchanged(world, mere):
    """The generalised mover still re-points a stub as before: its facts
    all go over, its names become other names."""

    m = mere
    with world.revision(Source.manual(note="stub")) as rev:
        stub = rev.create_thing(
            "place", {"name": "The Mere", "stub": {"ignored": False}}
        )
        rev.add_fact(stub, "general", "Fog lies on the Mere at dawn.")
        rev.add_fact(m.vasha, "background", f"Swam in {ref(stub, 'the Mere')}.")
    done = repoint_stub(world, stub, m.ashenmere)
    assert done.facts_moved == 1
    assert "Fog lies on the Mere at dawn." in _texts(world, m.ashenmere)
    assert world.view().thing(stub) is None
    with pytest.raises(ValueError, match="not a stub"):
        repoint_stub(world, m.caves, m.ashenmere)


def test_merge_tie_within_a_part_outside_its_sphere(world, host):
    """A tie re-pointed `within` the into-side, when the into-side won't be
    inside that tie's sphere (it keeps a filing elsewhere), is within no
    part, with a note."""

    h = host
    with world.revision(Source.manual(note="rivals")) as rev:
        rivals = rev.create_thing(
            "sphere",
            {
                "name": "The Rival Court",
                "template": "nation",
                "drawers": [{"id": MILITARY, "type": "structure", "title": "Military"}],
            },
        )
        rev.set_field(h.army, "part_of", {"sphere": rivals, "drawer": MILITARY}, None)
    preview = preview_merge(world, h.host, h.army)
    done = accept_merge(world, preview, main_name="The Tsar's Army")
    (ilya,) = world.view().thing(h.ilya).fields["ties"]
    assert (ilya["sphere"], ilya["within"]) == (h.tsardom, None)
    assert any("Ilya's tie" in note for note in done.notes)
    assert world.view().thing(h.army).fields["part_of"]["sphere"] == rivals
