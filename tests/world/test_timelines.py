"""Entry timelines (`talemate.world.timelines`): every dated fact of an
entry in date order, and for a sphere the dated facts it gathers from its
parts and from facts that name it or a part (spec goal 6). The 947
rediscovery lives on Ashenmere and shows on Runeweaving's timeline; the
Codex's compiling, given as 217 and 312, is flagged."""

from dataclasses import dataclass

from talemate.world.dates import WorldDate
from talemate.world.refs import ref
from talemate.world.store import Source
from talemate.world.timelines import TimelineLine, entry_timeline

DRAWER = "d0000001"
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


def _part_of(sphere):
    return {"sphere": sphere, "drawer": DRAWER}


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
            "sphere",
            fields={
                "name": "Runeweaving",
                "template": "field",
                "drawers": [{"id": DRAWER, "type": "knowledge", "title": "Lore"}],
            },
        )
        ashenmere = rev.create_thing(
            "lore", fields={"name": "Ashenmere", "part_of": _part_of(sphere)}
        )
        glyphs = rev.create_thing(
            "lore", fields={"name": "Ashenmere glyphs", "part_of": _part_of(ashenmere)}
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
    # and a lore entry gathers nothing from its parts
    (own,) = _timeline(world, r.ashenmere)
    assert own.fact_id == r.rediscovered and own.here


def test_place_sphere_gathers_its_places(world):
    with world.revision(Source.manual()) as rev:
        tsardom = rev.create_thing(
            "place", fields={"name": "Tsardom", "template": "nation", "drawers": []}
        )
        moskov = rev.create_thing("place", fields={"name": "Moskov", "parent": tsardom})
        quarter = rev.create_thing(
            "place", fields={"name": "Old Quarter", "parent": moskov}
        )
        crowned = rev.add_fact(
            tsardom, "timeline", "The first Tsar crowned.", valid_from=WorldDate.of(700)
        )
        founded = rev.add_fact(
            moskov, "history", "Moskov founded.", valid_from=WorldDate.of(800)
        )
        walled = rev.add_fact(
            quarter, "history", "The quarter walled.", valid_from=WorldDate.of(850)
        )
    assert _ids(_timeline(world, tsardom)) == [crowned, founded, walled]
    assert _ids(_timeline(world, tsardom, reach=1)) == [crowned, founded]
    # a plain place gathers nothing from the places inside it
    assert _ids(_timeline(world, moskov)) == [founded]


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
                "ties": [
                    {
                        "sphere": r.sphere,
                        "role": "scholar",
                        "since": None,
                        "until": None,
                    }
                ],
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
        rev.set_field(r.codex, "part_of", _part_of(r.sphere), None)
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


def test_branch_keeps_its_parents_earlier_timeline(world):
    with world.revision(Source.manual()) as rev:
        dawn = rev.create_thing(
            "sphere", fields={"name": "White Dawn", "template": "religion"}
        )
        old = rev.add_fact(
            dawn, "timeline", "The Dawn first preached.", valid_from=WorldDate.of(900)
        )
        reformed = rev.create_thing(
            "sphere", fields={"name": "Reformed Dawn", "template": "religion"}
        )
        rev.set_field(reformed, "parent", dawn, valid_from=WorldDate.of(1000))
        rev.add_fact(
            dawn, "timeline", "The Dawn built a spire.", valid_from=WorldDate.of(1007)
        )
        split = rev.add_fact(
            reformed, "timeline", "The reformers split.", valid_from=WorldDate.of(1001)
        )
    lines = _timeline(world, reformed)
    assert _ids(lines) == [old, split]
    assert lines[0].owner_id == dawn and not lines[0].here


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
