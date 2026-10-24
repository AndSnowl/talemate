"""Entry timelines (`talemate.world.timelines`): every dated fact of an
entry in date order, and the dated facts it gathers from what is filed in
it (its parts, down to the reach) and from facts that name it or a part
(spec goal 6; filing spec, "What stays as built"). The 947 rediscovery
lives on Ashenmere and shows on Runeweaving's timeline; the Codex's
compiling, given as 217 and 312, is flagged."""

from dataclasses import dataclass

from talemate.world.dates import WorldDate
from talemate.world.refs import ref
from talemate.world.store import Source
from talemate.world.timelines import TimelineLine, entry_timeline

THRESHOLD = 0.4

# the Codex's compiling, as the curation probe's world gave it twice
CODEX_217 = (
    "The First Codex of Aelberth is compiled, standardizing 24 foundational runes."
)
CODEX_312 = (
    "The First Codex of Aelberth is the foundational compendium of "
    "Runeweaving, compiled to standardize the art and codify its governing "
    "principles."
)


def _in(target, role=None, since=None, until=None):
    """One filing into `target`, as `filings` stores it."""

    return {
        "target": target,
        "role": role,
        "since": since.model_dump(mode="json") if since else None,
        "until": until.model_dump(mode="json") if until else None,
        "within": None,
        "exceptions": [],
    }


def _filed(*targets):
    return [_in(target) for target in targets]


def _ids(lines):
    return [line.fact_id for line in lines]


def _timeline(world, thing_id, reach=2, at=None):
    return entry_timeline(world.view(at), thing_id, reach=reach, threshold=THRESHOLD)


@dataclass
class Runeweaving:
    sphere: str
    ashenmere: str
    glyphs: str
    kel: str
    codex: str
    founded: str
    rediscovered: str
    carved: str


def _runeweaving(world) -> Runeweaving:
    """Runeweaving, a field, with Ashenmere filed in it and the Ashenmere
    glyphs filed in Ashenmere (a part of a part); Kel is only mentioned."""

    with world.revision(Source.manual()) as rev:
        sphere = rev.create_thing(
            "sphere", fields={"name": "Runeweaving", "tag": "field"}
        )
        ashenmere = rev.create_thing(
            "lore", fields={"name": "Ashenmere", "filings": _filed(sphere)}
        )
        glyphs = rev.create_thing(
            "lore", fields={"name": "Ashenmere glyphs", "filings": _filed(ashenmere)}
        )
        kel = rev.create_thing("lore", fields={"name": "Kel"})
        codex = rev.create_thing("lore", fields={"name": "The Codex"})
        founded = rev.add_fact(
            sphere,
            "timeline",
            f"First taught in {ref(kel)}.",
            valid_from=WorldDate.of(900),
        )
        rediscovered = rev.add_fact(
            ashenmere,
            "general",
            "The Ashenmere dialect was rediscovered.",
            valid_from=WorldDate.of(947),
        )
        carved = rev.add_fact(
            glyphs, "general", "The glyphs were carved.", valid_from=WorldDate.of(960)
        )
        # undated: never on a timeline
        rev.add_fact(ashenmere, "general", "A dialect of runes.")
        # Kel's own history is Kel's, however near
        rev.add_fact(kel, "general", "Kel was founded.", valid_from=WorldDate.of(500))
    return Runeweaving(
        sphere, ashenmere, glyphs, kel, codex, founded, rediscovered, carved
    )


def test_own_dated_facts_in_order(world):
    with world.revision(Source.manual()) as rev:
        maren = rev.create_thing("character", fields={"name": "Maren"})
        later = rev.add_fact(
            maren, "background", "Became a warden.", valid_from=WorldDate.of(320)
        )
        born = rev.add_fact(
            maren, "background", "Born in the hills.", valid_from=WorldDate.of(290)
        )
        # a "since" state and an "in" event: both are lines at their year
        since = rev.add_fact(
            maren,
            "relationship",
            "Married to Oskar.",
            valid_from=WorldDate.of(310),
            valid_until=WorldDate.of(330),
        )
        rev.add_fact(maren, "appearance", "Tall.")
        gone = rev.add_fact(
            maren, "background", "Lost a wager.", valid_from=WorldDate.of(300)
        )
    with world.revision(Source.manual()) as rev:
        rev.remove_fact(gone)

    lines = _timeline(world, maren)
    # ended facts are history, at their start; a removed one never shows
    assert _ids(lines) == [born, since, later]
    assert all(isinstance(line, TimelineLine) for line in lines)
    assert [line.date.to_datetime().year for line in lines] == [290, 310, 320]
    assert [line.text for line in lines] == [
        "Born in the hills.",
        "Married to Oskar.",
        "Became a warden.",
    ]
    assert all(line.here and line.owner_id == maren for line in lines)
    assert all(line.disagrees_with == [] for line in lines)

    # seen at 335 the marriage has ended, and still shows; at 315 the
    # warden's line hasn't happened yet
    assert _ids(_timeline(world, maren, at=WorldDate.of(335))) == [born, since, later]
    assert _ids(_timeline(world, maren, at=WorldDate.of(315))) == [born, since]


def test_sphere_gathers_from_parts_947(world):
    r = _runeweaving(world)
    lines = _timeline(world, r.sphere)
    assert _ids(lines) == [r.founded, r.rediscovered, r.carved]
    by_id = {line.fact_id: line for line in lines}
    assert by_id[r.founded].here and by_id[r.founded].owner_id == r.sphere
    rediscovery = by_id[r.rediscovered]
    assert not rediscovery.here
    assert rediscovery.owner_id == r.ashenmere
    assert rediscovery.text == "The Ashenmere dialect was rediscovered."
    assert rediscovery.date.to_datetime().year == 947
    # it lives on Ashenmere: Ashenmere's own timeline has it, as its own,
    # and gathers the glyphs filed in it, as any entry does
    own, carved = _timeline(world, r.ashenmere)
    assert own.fact_id == r.rediscovered and own.here
    assert carved.fact_id == r.carved and carved.owner_id == r.glyphs


def test_timeline_gathers_from_filed_entries(world):
    """A place gathers the places and customs filed in it, and theirs, to
    the reach; a custom filed in two places shows on both; an entry filed
    only over some dates is gathered only while it's filed."""

    with world.revision(Source.manual()) as rev:
        tsardom = rev.create_thing("place", fields={"name": "Tsardom"})
        moskov = rev.create_thing(
            "place", fields={"name": "Moskov", "filings": _filed(tsardom)}
        )
        quarter = rev.create_thing(
            "place", fields={"name": "Old Quarter", "filings": _filed(moskov)}
        )
        vosgrad = rev.create_thing("place", fields={"name": "Vosgrad"})
        dance = rev.create_thing(
            "lore",
            fields={
                "name": "Feather Dance",
                "tag": "custom",
                "filings": [
                    _in(moskov),
                    _in(vosgrad, since=WorldDate.of(900), until=WorldDate.of(1015)),
                ],
            },
        )
        crowned = rev.add_fact(
            tsardom, "history", "The first Tsar crowned.", valid_from=WorldDate.of(700)
        )
        founded = rev.add_fact(
            moskov, "history", "Moskov founded.", valid_from=WorldDate.of(800)
        )
        walled = rev.add_fact(
            quarter, "history", "The quarter walled.", valid_from=WorldDate.of(850)
        )
        danced = rev.add_fact(
            dance, "general", "First danced.", valid_from=WorldDate.of(950)
        )
    assert _ids(_timeline(world, tsardom)) == [crowned, founded, walled, danced]
    assert _ids(_timeline(world, tsardom, reach=1)) == [crowned, founded]
    assert _ids(_timeline(world, moskov, reach=1)) == [founded, walled, danced]
    # in Vosgrad from 900 to 1015: gathered then, not at the latest telling
    assert _ids(_timeline(world, vosgrad, at=WorldDate.of(1000))) == [danced]
    assert _ids(_timeline(world, vosgrad)) == []


def test_reference_from_outside_counts(world):
    r = _runeweaving(world)
    with world.revision(Source.manual()) as rev:
        named = rev.add_fact(
            r.codex,
            "general",
            f"Cites {ref(r.sphere)} at length.",
            valid_from=WorldDate.of(1000),
        )
        part_named = rev.add_fact(
            r.kel,
            "general",
            f"Scholars of Kel studied {ref(r.ashenmere)}.",
            valid_from=WorldDate.of(980),
        )
        # undated: never a line, however it names the sphere
        rev.add_fact(r.codex, "general", f"Mentions {ref(r.sphere)}.")
    lines = _timeline(world, r.sphere)
    assert _ids(lines) == [
        r.founded,
        r.rediscovered,
        r.carved,
        part_named,
        named,
    ]
    by_id = {line.fact_id: line for line in lines}
    assert by_id[named].owner_id == r.codex and not by_id[named].here
    assert by_id[named].text == "Cites Runeweaving at length."
    # a part's fact that names the sphere shows once
    with world.revision(Source.manual()) as rev:
        both = rev.add_fact(
            r.ashenmere,
            "general",
            f"Taught again in {ref(r.sphere)}.",
            valid_from=WorldDate.of(990),
        )
    assert _ids(_timeline(world, r.sphere)).count(both) == 1


def test_member_births_not_gathered(world):
    r = _runeweaving(world)
    with world.revision(Source.manual()) as rev:
        vasha = rev.create_thing(
            "character",
            fields={
                "name": "Vasha",
                "filings": [_in(r.sphere, role="scholar")],
            },
        )
        rev.add_fact(vasha, "background", "Born in Kel.", valid_from=WorldDate.of(990))
        joined = rev.add_fact(
            vasha,
            "ties",
            f"Joined the scholars of {ref(r.sphere)}.",
            valid_from=WorldDate.of(1010),
        )
    assert _ids(_timeline(world, r.sphere)) == [
        r.founded,
        r.rediscovered,
        r.carved,
        joined,
    ]


def test_mention_only_neighbour_not_gathered(world):
    r = _runeweaving(world)
    # Runeweaving's own line names Kel, so Kel is near it; Kel's founding
    # is Kel's, never Runeweaving's
    ids = _ids(_timeline(world, r.sphere, reach=3))
    assert ids == [r.founded, r.rediscovered, r.carved]


def test_reach_limits_depth(world):
    r = _runeweaving(world)
    assert _ids(_timeline(world, r.sphere, reach=2)) == [
        r.founded,
        r.rediscovered,
        r.carved,
    ]
    assert _ids(_timeline(world, r.sphere, reach=1)) == [r.founded, r.rediscovered]
    assert _ids(_timeline(world, r.sphere, reach=0)) == [r.founded]
    # a fact naming the part of a part only counts within reach too
    with world.revision(Source.manual()) as rev:
        deep = rev.add_fact(
            r.kel,
            "general",
            f"Kel copied {ref(r.glyphs)}.",
            valid_from=WorldDate.of(970),
        )
    assert deep in _ids(_timeline(world, r.sphere, reach=2))
    assert deep not in _ids(_timeline(world, r.sphere, reach=1))


def test_codex_dates_disagree(world):
    r = _runeweaving(world)
    with world.revision(Source.manual()) as rev:
        rev.set_field(r.codex, "filings", _filed(r.sphere), None)
        compiled_217 = rev.add_fact(
            r.sphere, "timeline", CODEX_217, valid_from=WorldDate.of(217)
        )
        compiled_312 = rev.add_fact(
            r.codex, "general", CODEX_312, valid_from=WorldDate.of(312)
        )
    lines = _timeline(world, r.sphere)
    by_id = {line.fact_id: line for line in lines}
    assert by_id[compiled_217].disagrees_with == [compiled_312]
    assert by_id[compiled_312].disagrees_with == [compiled_217]
    assert by_id[r.founded].disagrees_with == []
    # computed on read: nothing is stored, so removing one clears the other
    with world.revision(Source.manual()) as rev:
        rev.remove_fact(compiled_312)
    by_id = {line.fact_id: line for line in _timeline(world, r.sphere)}
    assert compiled_312 not in by_id
    assert by_id[compiled_217].disagrees_with == []


def test_branch_is_filed_in_its_parent(world):
    """A branch is an entry filed in its parent ("branch of"): the parent
    gathers the branch's lines, and the branch keeps its own (the parent's
    are one link away, no longer inherited)."""

    with world.revision(Source.manual()) as rev:
        dawn = rev.create_thing("sphere", fields={"name": "White Dawn"})
        old = rev.add_fact(
            dawn, "timeline", "The Dawn first preached.", valid_from=WorldDate.of(900)
        )
        reformed = rev.create_thing(
            "sphere",
            fields={
                "name": "Reformed Dawn",
                "filings": [_in(dawn, role="branch of", since=WorldDate.of(1000))],
            },
        )
        split = rev.add_fact(
            reformed, "timeline", "The reformers split.", valid_from=WorldDate.of(1001)
        )
        # the parent's line from after the split: never the branch's
        spire = rev.add_fact(
            dawn, "timeline", "The Dawn built a spire.", valid_from=WorldDate.of(1007)
        )
    assert _ids(_timeline(world, reformed)) == [split]
    assert spire not in _ids(_timeline(world, reformed, reach=3))
    lines = _timeline(world, dawn)
    assert _ids(lines) == [old, split, spire]
    assert lines[1].owner_id == reformed and not lines[1].here


def test_isolated_entry(world):
    with world.revision(Source.manual()) as rev:
        alone = rev.create_thing("lore", fields={"name": "Alone"})
        rev.add_fact(alone, "general", "Undated.")
        empty = rev.create_thing(
            "sphere", fields={"name": "Empty", "template": "order"}
        )
    assert _timeline(world, alone) == []
    assert _timeline(world, empty, reach=3) == []
    assert _timeline(world, "0" * 32) == []
    # an entry removed since has no timeline
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(alone)
    assert _timeline(world, alone) == []


def test_ended_fact_shows_its_span(world):
    """Ruling C18: a fact ended by the view's date carries its end
    (`until`); one still running, or seen before it ends, doesn't."""

    with world.revision(Source.manual()) as rev:
        maren = rev.create_thing("character", fields={"name": "Maren"})
        married = rev.add_fact(
            maren,
            "relationship",
            "Married to Oskar.",
            valid_from=WorldDate.of(310),
            valid_until=WorldDate.of(330),
        )
    (line,) = _timeline(world, maren, at=WorldDate.of(335))
    assert line.fact_id == married
    assert line.until is not None and line.until.to_datetime().year == 330
    (line,) = _timeline(world, maren, at=WorldDate.of(320))
    assert line.until is None
    # the latest telling: it has ended
    (line,) = _timeline(world, maren)
    assert line.until is not None


def test_gathering_follows_filings_down_to_the_reach(world):
    """A religion with Kremova filed in it, and a district filed in
    Kremova, gathers Kremova's lines at reach 1 and the district's at 2,
    whatever their kinds."""

    with world.revision(Source.manual()) as rev:
        dawn = rev.create_thing("sphere", fields={"name": "White Dawn"})
        kremova = rev.create_thing(
            "place", fields={"name": "Kremova", "filings": _filed(dawn)}
        )
        district = rev.create_thing(
            "place", fields={"name": "Spire Quarter", "filings": _filed(kremova)}
        )
        seated = rev.add_fact(
            kremova, "history", "The church seated here.", valid_from=WorldDate.of(900)
        )
        walled = rev.add_fact(
            district, "history", "The quarter walled.", valid_from=WorldDate.of(950)
        )
    assert _ids(_timeline(world, dawn, reach=1)) == [seated]
    assert _ids(_timeline(world, dawn, reach=3)) == [seated, walled]


def test_a_character_filed_in_a_sphere_gives_no_births(world):
    """A character (or a real being) filed as a part is a member, not a
    part: its own dated facts stay its own."""

    with world.revision(Source.manual()) as rev:
        order = rev.create_thing(
            "sphere", fields={"name": "Order", "template": "order"}
        )
        vasha = rev.create_thing(
            "character", fields={"name": "Vasha", "filings": _filed(order)}
        )
        god = rev.create_thing(
            "being",
            fields={"name": "Dawn", "existence": "real", "filings": _filed(order)},
        )
        rev.add_fact(vasha, "background", "Born.", valid_from=WorldDate.of(990))
        rev.add_fact(god, "deeds", "Woke.", valid_from=WorldDate.of(10))
        joined = rev.add_fact(
            vasha,
            "background",
            f"Joined {ref(order)}.",
            valid_from=WorldDate.of(1010),
        )
    assert _ids(_timeline(world, order)) == [joined]


def test_timeline_line_dump_round_trips(world):
    r = _runeweaving(world)
    for line in _timeline(world, r.sphere):
        dumped = line.model_dump()
        assert "fact" not in dumped
        again = TimelineLine.model_validate(dumped)
        assert again.fact is None and again.fact_id == line.fact_id


def test_prompt_timeline_skips_disagreements(world, monkeypatch):
    """A prompt's timeline never asks which dates disagree."""

    from talemate.world import timelines

    r = _runeweaving(world)

    def no_pairs(*_args, **_kwargs):
        raise AssertionError("disagreements computed for a prompt")

    monkeypatch.setattr(timelines, "disagreeing_dates", no_pairs)
    assert _ids(
        timelines.prompt_timeline(world.view(), r.sphere, reach=2, threshold=0.4)
    ) == [r.founded, r.rediscovered, r.carved]
    lines = timelines.entry_timeline(
        world.view(), r.sphere, reach=2, threshold=0.4, disagreements=False
    )
    assert all(line.disagrees_with == [] for line in lines)


def test_timeline_and_near_survive_a_cycle(world):
    """The store refuses a filing cycle, but undo restores rows unchecked
    and can bring one back: a timeline and nearness over it still end,
    each entry once."""

    from talemate.world.nearness import near

    with world.revision(Source.manual()) as rev:
        a = rev.create_thing("lore", fields={"name": "A"})
        b = rev.create_thing("lore", fields={"name": "B", "filings": _filed(a)})
        c = rev.create_thing("lore", fields={"name": "C", "filings": _filed(b)})
        in_a = rev.add_fact(a, "general", "A began.", valid_from=WorldDate.of(1))
        in_b = rev.add_fact(b, "general", "B began.", valid_from=WorldDate.of(2))
        in_c = rev.add_fact(c, "general", "C began.", valid_from=WorldDate.of(3))
    with world.revision(Source.manual()) as rev:
        rev.set_field(b, "filings", [], None)
        unfiled = rev.rev
    with world.revision(Source.manual()) as rev:
        # A in C: fine while B is out of A
        rev.set_field(a, "filings", _filed(c), None)
    world.undo([unfiled])
    view = world.view()
    # the cycle is back: A in C in B in A
    assert [f["target"] for f in view.thing(b).fields["filings"]] == [a]
    assert [f["target"] for f in view.thing(a).fields["filings"]] == [c]

    for start in (a, b, c):
        lines = _timeline(world, start, reach=3)
        assert sorted(_ids(lines)) == sorted([in_a, in_b, in_c])
        assert len(lines) == 3
        assert {n.thing_id for n in near(view, start, reach=3)} == {a, b, c} - {start}
