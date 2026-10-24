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
from talemate.world.filing import filings_of
from talemate.world.refs import parse_refs, ref
from talemate.world.store import Source
from talemate.worldplay.decide import contradiction_pairs
from talemate.worldplay.merge import MergePreview, accept_merge, preview_merge
from talemate.worldplay.repoint import repoint_stub

SYSTEM_A = "Ashenmere is a cave system beneath the northern hills."
SYSTEM_B = "The Ashenmere Caves are a cave system beneath the northern hills."
DIALECT_A = "The Ashenmere dialect was rediscovered by the Conclave's scholars."
DIALECT_B = "The Ashenmere dialect was rediscovered by Conclave scholars."
LICHEN_A = "The caves glow with blue lichen."
LICHEN_B = "Green lichen covers the cave walls."
SMUGGLERS = "Smugglers hide their goods in the caves."


def _aka(name, tag="common", everyday=False):
    return {"name": name, "tag": tag, "everyday": everyday}


def _in(target, role=None, *, within=None, since=None, exceptions=()):
    """One filing into `target`, as `filings` stores it."""

    return {
        "target": target,
        "role": role,
        "since": since.model_dump(mode="json") if since else None,
        "until": None,
        "within": within,
        "exceptions": list(exceptions),
    }


def _filed(world, thing_id):
    return [
        (f.target, f.role, f.within)
        for f in filings_of(world.view(), thing_id, live=False)
    ]


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
    """Present 1000. Ashenmere, a region filed in the Tsardom, and The
    Ashenmere Caves, a cave system filed in Northreach: one place written
    twice. The Caves restate Ashenmere's first line (a repeat), date the
    dialect's rediscovery 950 against Ashenmere's 947, and give the lichen
    another colour. Deepvault is filed in the Caves, and Vasha and
    Ashenmere both link to them."""

    world.set_present(WorldDate.of(1000))
    with world.revision(Source.manual(note="mere")) as rev:
        tsardom = rev.create_thing(
            "lore", {"name": "Tsardom of Moscavia", "tag": "nation"}
        )
        northreach = rev.create_thing("place", {"name": "Northreach"})
        ashenmere = rev.create_thing(
            "place",
            {
                "name": "Ashenmere",
                "tag": "region",
                "aka": [_aka("the Mere", everyday=True)],
                "filings": [_in(tsardom)],
            },
        )
        caves = rev.create_thing(
            "place",
            {
                "name": "The Ashenmere Caves",
                "tag": "cave system",
                "filings": [_in(northreach)],
                "aka": [_aka("the Deeps", tag="proper")],
            },
        )
        deepvault = rev.create_thing(
            "place", {"name": "Deepvault", "filings": [_in(caves)]}
        )
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
    assert preview.moves == {"facts": 3, "links": 2, "fields": 0, "filings": 1}


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
    filing naming the Caves pointed at Ashenmere (Ashenmere's own link made
    its words), a conflicting tag noted, Ashenmere's filing kept and the
    Caves' added beside it, the Caves removed; prose for Ashenmere."""

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
    assert _filed(world, m.deepvault) == [(m.ashenmere, None, None)]
    assert _filed(world, m.ashenmere) == [
        (m.tsardom, None, None),
        (m.northreach, None, None),
    ]
    assert ashenmere.fields["tag"] == "region"
    assert any("tag" in note for note in done.notes)
    assert done.prose == [m.ashenmere]


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
        oskar = rev.create_thing("character", {"name": "Oskar"})
    with world.revision(Source.manual(note="gone")) as rev:
        rev.remove_thing(gone)
    world.scenes().create("Descent", WorldDate.of(1000), player_thing_id=m.vasha)
    head = world.head_rev()
    for from_id, into_id, error, words in (
        (m.caves, m.caves, ValueError, "itself"),
        (m.caves, gone, KeyError, "no such thing"),
        (m.caves, hope, ValueError, "ignored"),
        (m.caves, rumour, ValueError, "stub"),
        # ruling C17: one kind (a place and a sphere no longer, Task 3)
        (m.caves, saltlore, ValueError, "only entries of one kind"),
        (m.vasha, m.caves, ValueError, "a character and The Ashenmere Caves a place"),
        (m.caves, m.tsardom, ValueError, "a place and Tsardom of Moscavia a lore"),
        (m.tsardom, m.northreach, ValueError, "only entries of one kind"),
        # a scene's player
        (m.vasha, oskar, ValueError, "the scene Descent"),
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


# --- filings ----------------------------------------------------------------------


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
    """The Tsar's Army (unfiled, with the White Talon filed in it) and the
    Tsar's Host (the same army written twice: filed in the Tsardom, with
    the Frosted Wing filed in it). Oskar rides with the Host, within the
    Frosted Wing; Ilya is a soldier of the Tsardom, within the Host."""

    with world.revision(Source.manual(note="host")) as rev:
        tsardom = rev.create_thing(
            "lore", {"name": "Tsardom of Moscavia", "tag": "nation"}
        )
        army = rev.create_thing("lore", {"name": "The Tsar's Army", "tag": "army"})
        host = rev.create_thing(
            "lore",
            {"name": "The Tsar's Host", "tag": "army", "filings": [_in(tsardom)]},
        )
        talon = rev.create_thing(
            "lore", {"name": "The White Talon", "filings": [_in(army, "division")]}
        )
        frost = rev.create_thing(
            "lore", {"name": "The Frosted Wing", "filings": [_in(host, "division")]}
        )
        oskar = rev.create_thing(
            "character",
            {"name": "Oskar", "filings": [_in(host, "rider", within=frost)]},
        )
        ilya = rev.create_thing(
            "character",
            {"name": "Ilya", "filings": [_in(tsardom, "soldier", within=host)]},
        )
        rev.add_fact(host, "general", "The Tsar's Host is the Tsardom's army.")
    return Host(tsardom, army, host, frost, talon, oskar, ilya)


def test_merge_rewrites_filings(world, host):
    """An entry merged into another: what's filed in it is filed in the
    other, a filing `within` it is within the other, and the other, filed
    nowhere, takes its filings -- so Ilya's part still holds. Filings are
    written, never `part_of`, ties or a parent (ruling F11)."""

    h = host
    preview = preview_merge(world, h.host, h.army)
    assert preview.moves["filings"] == 3
    assert "ties" not in preview.moves
    accept_merge(world, preview, main_name="The Tsar's Army")
    view = world.view()
    assert view.thing(h.host) is None
    assert _filed(world, h.frost) == [(h.army, "division", None)]
    assert _filed(world, h.talon) == [(h.army, "division", None)]
    assert _filed(world, h.army) == [(h.tsardom, None, None)]
    assert _filed(world, h.oskar) == [(h.army, "rider", h.frost)]
    assert _filed(world, h.ilya) == [(h.tsardom, "soldier", h.army)]
    for thing_id in (h.army, h.frost, h.oskar, h.ilya):
        fields = view.thing(thing_id).fields
        assert all(fields.get(old) is None for old in ("part_of", "ties", "parent"))

    # one undo puts the Host and every filing back
    world.undo([world.head_rev()])
    assert _filed(world, h.oskar) == [(h.host, "rider", h.frost)]
    assert _filed(world, h.army) == []


def test_merge_into_a_non_lore_refused(world, host):
    h = host
    with world.revision(Source.manual(note="camp")) as rev:
        camp = rev.create_thing("place", {"name": "The Winter Camp"})
    head = world.head_rev()
    # two kinds never merge
    with pytest.raises(ValueError, match="only entries of one kind"):
        preview_merge(world, h.host, camp)
    assert world.head_rev() == head


def test_merge_into_an_entry_filed_in_it(world, host):
    """The Host merged into its branch, the Northern Host, filed in it: the
    branch sits where the Host sat (its filing in the Host goes, and it
    takes the Host's, in the Tsardom), and what was filed in the Host
    follows it; a note says so."""

    h = host
    with world.revision(Source.manual(note="branch")) as rev:
        branch = rev.create_thing(
            "lore",
            {"name": "The Northern Host", "filings": [_in(h.host, "branch of")]},
        )
    preview = preview_merge(world, h.host, branch)
    done = accept_merge(world, preview, main_name="The Northern Host")
    assert _filed(world, branch) == [(h.tsardom, None, None)]
    assert _filed(world, h.frost) == [(branch, "division", None)]
    assert _filed(world, h.ilya) == [(h.tsardom, "soldier", branch)]
    assert any(
        "The Northern Host was filed in The Tsar's Host: it takes" in note
        for note in done.notes
    )


def test_merge_character_filings_carry_over(world, host):
    """A character's filings go over, but one into an entry the other is
    filed in already, whose exceptions join the other's; its exceptions
    go with its facts (copied, the filing naming the copies)."""

    h = host
    with world.revision(Source.manual(note="grey")) as rev:
        grey = rev.create_thing("character", {"name": "Oskar the Grey"})
        saddle = rev.add_fact(
            grey, "ties", "Rides without a saddle.", origin={"tie": h.host}
        )
        levies = rev.add_fact(
            grey,
            "ties",
            "Exempt from the Tsardom's levies.",
            origin={"tie": h.tsardom},
        )
        rev.set_field(
            grey,
            "filings",
            [
                _in(h.host, "scout", exceptions=[saddle]),
                _in(h.tsardom, "subject", exceptions=[levies]),
            ],
            None,
        )
    preview = preview_merge(world, grey, h.oskar)
    accept_merge(world, preview, main_name="Oskar")
    view = world.view()
    copies = {f.text: f.fact_id for f in world.live_facts(h.oskar)}
    rider, subject = filings_of(view, h.oskar)
    assert (rider.target, rider.role, rider.within) == (h.host, "rider", h.frost)
    assert rider.exceptions == [copies["Rides without a saddle."]]
    assert (subject.target, subject.role) == (h.tsardom, "subject")
    assert subject.exceptions == [copies["Exempt from the Tsardom's levies."]]
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


def test_merge_within_that_no_longer_holds(world, host):
    """A filing re-pointed `within` the into-side, when the into-side won't
    sit in that filing's entry (the Army can't take the Host's filing in
    the Tsardom: the Tsardom is filed in the Army), is within no part,
    with a note."""

    h = host
    with world.revision(Source.manual(note="rivals")) as rev:
        rev.set_field(h.tsardom, "filings", [_in(h.army)], None)
    preview = preview_merge(world, h.host, h.army)
    done = accept_merge(world, preview, main_name="The Tsar's Army")
    assert _filed(world, h.ilya) == [(h.tsardom, "soldier", None)]
    assert any("Ilya's filing in Tsardom of Moscavia" in note for note in done.notes)
    assert any("would be inside itself" in note for note in done.notes)
    assert _filed(world, h.army) == []


# --- fix round 1 -----------------------------------------------------------------


def test_merge_untick_on_a_paired_fact_stands(world, mere):
    """A paired from-fact the owner unticked isn't copied when its pair is
    left as both (or kept as B); picking A ticks it."""

    m = mere
    preview = preview_merge(world, m.caves, m.ashenmere)
    for fact in preview.facts:
        if fact.fact_id in (m.dialect_b, m.lichen_b):
            fact.ticked = False
    accept_merge(
        world,
        preview,
        main_name="Ashenmere",
        keep={_key(preview, m.dialect_b): "a"},
    )
    texts = _texts(world, m.ashenmere)
    assert LICHEN_B not in texts
    assert DIALECT_B in texts
    assert DIALECT_A not in texts


def test_merge_refuses_forged_pairs_and_repeats(world, mere):
    """The client's preview is checked: a pair the world doesn't find (one
    naming a third entry's fact) and a repeat of no into-side fact are
    refused, writing nothing."""

    m = mere
    preview = preview_merge(world, m.caves, m.ashenmere)
    forged = preview.pairs[0].model_copy(
        update={"key": f"{m.smugglers}:{m.explored}", "a": m.smugglers, "b": m.explored}
    )
    preview.pairs.append(forged)
    head = world.head_rev()
    with pytest.raises(ValueError, match="no such pair"):
        accept_merge(world, preview, main_name="Ashenmere", keep={forged.key: "a"})
    assert world.head_rev() == head
    # listed without a choice, it's ignored: Vasha's fact stays
    accept_merge(world, preview, main_name="Ashenmere")
    assert any(f.fact_id == m.explored for f in world.live_facts(m.vasha))
    world.undo([world.head_rev()])

    preview = preview_merge(world, m.caves, m.ashenmere)
    for fact in preview.facts:
        if fact.fact_id == m.system_b:
            fact.repeat_of = {**fact.repeat_of, "fact_id": m.explored}
    head = world.head_rev()
    with pytest.raises(ValueError, match="a repeat of no fact"):
        accept_merge(world, preview, main_name="Ashenmere")
    assert world.head_rev() == head


def test_merge_redirects_the_into_sides_own_filing(world, mere):
    """Ashenmere merged into the Caves, which are filed in Ashenmere: that
    filing goes and the Caves take Ashenmere's own, in the Tsardom, with a
    note; with no filing of Ashenmere's, the Caves are no longer filed
    there and keep the rest."""

    m = mere
    with world.revision(Source.manual(note="filed")) as rev:
        rev.set_field(
            m.caves, "filings", [_in(m.northreach), _in(m.ashenmere, "under")], None
        )
    preview = preview_merge(world, m.ashenmere, m.caves)
    done = accept_merge(world, preview, main_name="Ashenmere")
    assert _filed(world, m.caves) == [
        (m.northreach, None, None),
        (m.tsardom, None, None),
    ]
    assert any(
        "The Ashenmere Caves was filed in Ashenmere: it takes Ashenmere's"
        " filings, Tsardom of Moscavia" in note
        for note in done.notes
    )
    assert world.view().name_of(m.caves) == "Ashenmere"

    world.undo([world.head_rev()])
    with world.revision(Source.manual(note="no filing")) as rev:
        rev.remove_field_value(m.ashenmere, "filings", None)
    preview = preview_merge(world, m.ashenmere, m.caves)
    done = accept_merge(world, preview, main_name="Ashenmere")
    assert _filed(world, m.caves) == [(m.northreach, None, None)]
    assert any("it's no longer filed there" in note for note in done.notes)


def test_merge_repeat_adds_no_word(world, mere):
    """Ruling C16: a fact that restates another but for a word of its own
    is a pair, not a repeat."""

    m = mere
    with world.revision(Source.manual(note="scales")) as rev:
        golden = rev.add_fact(m.ashenmere, "description", "golden scales edged in red")
        black = rev.add_fact(m.caves, "description", "black scales edged in red")
    preview = preview_merge(world, m.caves, m.ashenmere)
    row = next(f for f in preview.facts if f.fact_id == black)
    assert row.ticked is True and row.repeat_of is None
    assert any(p.a == black and p.b == golden for p in preview.pairs)
    # the plain restatement is still a repeat
    assert next(f for f in preview.facts if f.fact_id == m.system_b).ticked is False


def test_merge_overrides_and_rejects_follow_replacements(world, mere):
    """An override of a repeat that went follows what replaced it, through
    a pair the owner settled, to a live fact; one of a fact that went with
    nothing in its place is dropped, with a note. An exception rejecting a
    fact that moved, or went, follows the same way."""

    m = mere
    with world.revision(Source.manual(note="links")) as rev:
        south = rev.add_fact(
            m.caves,
            "general",
            "Ashenmere is a cave system beneath the southern hills, not the northern.",
        )
        rev.correct_fact(m.explored, overrides=[m.system_b, m.smugglers])
        rejects_moved = rev.add_fact(
            m.vasha,
            "ties",
            "Doubts the smugglers.",
            origin={"rejects_fact": m.lichen_b},
        )
        rejects_gone = rev.add_fact(
            m.vasha, "ties", "Doubts the hills.", origin={"rejects_fact": m.system_b}
        )
    preview = preview_merge(world, m.caves, m.ashenmere)
    for fact in preview.facts:
        if fact.fact_id == m.smugglers:
            fact.ticked = False
    pair = next(p for p in preview.pairs if p.a == south and p.b == m.system_a)
    done = accept_merge(world, preview, main_name="Ashenmere", keep={pair.key: "a"})
    by_text = {f.text: f.fact_id for f in world.live_facts(m.ashenmere)}
    south_copy = by_text[
        "Ashenmere is a cave system beneath the southern hills, not the northern."
    ]
    lichen_copy = by_text[LICHEN_B]
    vasha = {f.fact_id: f for f in world.live_facts(m.vasha)}
    assert vasha[m.explored].overrides == [south_copy]
    assert any("no longer overrides" in note for note in done.notes)
    assert vasha[rejects_moved].origin == {"rejects_fact": lichen_copy}
    assert vasha[rejects_gone].origin == {"rejects_fact": south_copy}


def test_merge_link_words_offered_as_akas(world, mere):
    """The links' words the merge would add as other names are listed in
    the preview; unticked, they aren't added."""

    m = mere
    preview = preview_merge(world, m.caves, m.ashenmere)
    assert preview.akas == ["the Caves"]
    accept_merge(world, preview, main_name="Ashenmere", akas=[])
    assert world.view().thing(m.ashenmere).fields["aka"] == [
        _aka("the Mere", everyday=True),
        _aka("The Ashenmere Caves"),
        _aka("the Deeps", tag="proper"),
    ]


# --- fix round 2 -----------------------------------------------------------------

LAWS = "1a5a0001"


def test_merge_lore_into_a_place_refused(world):
    """A lore entry and a place are two kinds (`kinds_can_be_one`), so the
    merge is refused and nothing is written: what's filed in either stays
    where it is."""

    with world.revision(Source.manual(note="realm")) as rev:
        city = rev.create_thing("place", {"name": "The City"})
        guild = rev.create_thing("lore", {"name": "The Guild"})
        charter = rev.create_thing(
            "lore", {"name": "The Charter", "filings": [_in(guild)]}
        )
    head = world.head_rev()
    with pytest.raises(ValueError, match="only entries of one kind"):
        preview_merge(world, guild, city)
    assert world.head_rev() == head
    assert _filed(world, charter) == [(guild, None, None)]


def test_merge_retired_value_note_says_what_shows(world, mere):
    """The Caves were filed in Northreach, then from 990 in Ashenmere:
    merged with Ashenmere (filed nowhere of its own), the 990 value is
    left empty, so it's retired and the note says Northreach shows
    again."""

    m = mere
    with world.revision(Source.manual(note="moved")) as rev:
        rev.remove_field_value(m.ashenmere, "filings", None)
        rev.set_field(m.caves, "filings", [_in(m.ashenmere)], WorldDate.of(990))
    preview = preview_merge(world, m.ashenmere, m.caves)
    done = accept_merge(world, preview, main_name="The Ashenmere Caves")
    assert _filed(world, m.caves) == [(m.northreach, None, None)]
    assert any(
        "filings fall back to its earlier filings, Northreach" in note
        for note in done.notes
    )


def test_merge_refuses_conflicting_choices_for_one_fact(world, mere):
    """The Caves' lichen pairs with two of Ashenmere's facts: kept in one
    pair and dropped in the other is refused, writing nothing."""

    m = mere
    with world.revision(Source.manual(note="floors")) as rev:
        floors = rev.add_fact(
            m.ashenmere, "description", "Green lichen covers the floors."
        )
    preview = preview_merge(world, m.caves, m.ashenmere)
    one = next(p.key for p in preview.pairs if (p.a, p.b) == (m.lichen_b, m.lichen_a))
    two = next(p.key for p in preview.pairs if (p.a, p.b) == (m.lichen_b, floors))
    head = world.head_rev()
    with pytest.raises(ValueError, match="kept in one pair and dropped in another"):
        accept_merge(world, preview, main_name="Ashenmere", keep={one: "a", two: "b"})
    assert world.head_rev() == head
    # the same way in both is fine
    accept_merge(world, preview, main_name="Ashenmere", keep={one: "a", two: "a"})
    texts = _texts(world, m.ashenmere)
    assert LICHEN_B in texts and LICHEN_A not in texts


def test_merge_pairs_an_ended_claim_with_another_start(world):
    """Ruling C23: a merge reconciles two histories, so an ended dated
    claim ("ruled 900-950") still pairs with the other side's same claim
    from another year -- unlike a timeline, where ending one settles it."""

    with world.revision(Source.manual()) as rev:
        old = rev.create_thing("lore", {"name": "The Old Tsars"})
        ruled_from = rev.add_fact(
            old,
            "general",
            "Vladislav ruled the Tsardom from the Ice Throne.",
            valid_from=WorldDate.of(900),
            valid_until=WorldDate.of(950),
        )
        tsars = rev.create_thing("lore", {"name": "The Tsars"})
        ruled_into = rev.add_fact(
            tsars,
            "general",
            "Vladislav ruled the Tsardom from the Ice Throne.",
            valid_from=WorldDate.of(910),
        )
    preview = preview_merge(world, old, tsars)
    assert [(p.a, p.b, p.years) for p in preview.pairs] == [
        (ruled_from, ruled_into, (900, 910))
    ]
    assert contradiction_pairs(world.view(), old, tsars)[0].years == (900, 910)
