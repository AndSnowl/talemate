"""Repeats and dates that disagree, found in code: the fact placement
probe's token-overlap measure (`scripts/dev/probe_fact_placement_score.py`),
on the probe's own texts (the owner's acceptance snapshot, labelled in
`docs/superpowers/probes/raw/2026-10-22-fact-placement-labels.json`)."""

import pytest

from talemate.world.dates import WorldDate
from talemate.world.repeats import (
    STOP,
    Disagreement,
    Repeat,
    content_words,
    disagreeing_dates,
    find_repeats,
    overlap,
)
from talemate.world.store import Source

# --- the probe's texts ----------------------------------------------------------

# Ashenmere 73412e8b: the 947 rediscovery, as the world held it at rev 21
REDISCOVERY = (
    "In the year 947, a party of Runeweavers from the Conclave in Stonehold "
    "rediscovered the Ashenmere rune dialect after following a trail of "
    "fragments preserved in marginal notes of surviving texts."
)
# The Law of Resonance 180a2c6a
LAW_947 = (
    "The Ashenmere rune dialect, rediscovered in 947, proposes a third "
    "resonance law that suggests material memory — how a substance has been "
    "treated in the past — also affects its compatibility with a rune, "
    "contradicting Aelberth's teaching that resonance depends only on "
    "inherent material nature."
)
# The Ashenmere Caves a9ade3ff (restates 73412e8b, labelled)
CAVES_947 = REDISCOVERY
# First Codex of Aelberth 0a931e69 (restates 180a2c6a, labelled)
CODEX_947 = (
    "Its teachings on resonance were directly challenged in 947 by the "
    "rediscovery of the Ashenmere rune dialect, which introduced a third "
    "resonance law accounting for material memory."
)
# Ashenmere 398e7d57 (restates 180a2c6a, labelled)
GLYPHS = (
    "The Ashenmere rune dialect uses glyphs and etching patterns that diverge "
    "significantly from the standard forms codified in the First Codex of "
    "Aelberth, employing a third resonance law that accounts for material "
    "memory — how a substance has been treated and shaped over time."
)
# Ashenmere 81ab957f (restates 180a2c6a and Deepcarving's 75ebb141, labelled)
DEBATE = (
    "The rediscovery sparked fierce academic debate within the Runeweavers' "
    "Conclave, as the Ashenmere dialect's third resonance law directly "
    "contradicted Aelberth's established teaching that resonance depends "
    "solely on a material's inherent nature."
)

# White Talon 4d85e893, labelled clean; its best match in the world is the
# Tsardom's army fact e22cdc76, at 0.353
TALON_ELITE = (
    "The White Talon is considered one of the most elite regiments in the "
    "Tsardom's military, recruited primarily from pure-line snowy Owl-folk of "
    "demonstrated courage and discipline."
)
TSARDOM_ARMY = (
    "The Tsardom maintains a standing army of Owl-folk warriors, trained in "
    "both aerial combat and ground tactics, organized into regiments with "
    "names like the White Talon and the Frosted Wing."
)

# the Codex's compiling: Runeweaving's timeline line e789e6b3 (217) and
# the Codex's own description a8907760 and history 094a94f6 (both 312)
CODEX_217 = (
    "The First Codex of Aelberth is compiled, standardizing 24 foundational runes."
)
CODEX_312 = (
    "The First Codex of Aelberth is the foundational compendium of "
    "Runeweaving, compiled to standardize the art and codify its governing "
    "principles."
)
CODEX_STONEHOLD = (
    "It was compiled in the city of Stonehold by the Runeweavers' Conclave "
    "following decades of scholarly debate about the nature and limits of "
    "runic power."
)


# --- the measure ------------------------------------------------------------------


def test_content_words_is_the_probes_tokenisation():
    # lower-cased, [a-z0-9]+ runs, the stop list and one-letter words out,
    # the crude stem (ing, ed, es, s, keeping 4 letters or more)
    assert content_words("The Runeweavers rediscovered 24 runes, a rune's glyph") == {
        "runeweaver",
        "rediscover",
        "24",
        "rune",
        "glyph",
    }
    assert "the" in STOP and "within" in STOP
    assert content_words("") == set()


def test_overlap_matches_probe_measure():
    # the share of the first text's content words the second holds
    assert overlap(CAVES_947, REDISCOVERY) == 1.0
    assert overlap(CODEX_947, LAW_947) >= 0.4
    assert overlap(GLYPHS, LAW_947) >= 0.4
    assert overlap(DEBATE, LAW_947) >= 0.4
    assert overlap(CODEX_947, GLYPHS) == pytest.approx(0.6)
    # a clean fact: the White Talon against its best match in the world
    assert overlap(TALON_ELITE, TSARDOM_ARMY) == pytest.approx(6 / 17)
    assert overlap(TALON_ELITE, TSARDOM_ARMY) < 0.4
    # one way: it reads the first text's words
    assert overlap("rune", CODEX_947) == 1.0
    assert overlap(CODEX_947, "rune") < 0.1
    assert overlap("", CODEX_947) == 0.0
    assert overlap("the of and", CODEX_947) == 0.0


# --- repeats ---------------------------------------------------------------------


def _owners(world):
    with world.revision(Source.manual()) as rev:
        ashenmere = rev.create_thing("place", fields={"name": "Ashenmere"})
        law = rev.create_thing("lore", fields={"name": "The Law of Resonance"})
        tsardom = rev.create_thing("place", fields={"name": "Tsardom of Moscavia"})
        f_rediscovery = rev.add_fact(ashenmere, "history", REDISCOVERY)
        f_glyphs = rev.add_fact(ashenmere, "general", GLYPHS)
        f_law = rev.add_fact(law, "general", LAW_947)
        f_army = rev.add_fact(tsardom, "general", TSARDOM_ARMY)
    return {
        "ashenmere": ashenmere,
        "law": law,
        "tsardom": tsardom,
        "rediscovery": f_rediscovery,
        "glyphs": f_glyphs,
        "law_947": f_law,
        "army": f_army,
    }


def test_find_repeats_picks_best_owner(world):
    ids = _owners(world)
    view = world.view()
    texts = [CAVES_947, DEBATE, TALON_ELITE]
    found = find_repeats(
        view, texts, [ids["ashenmere"], ids["law"], ids["tsardom"]], 0.4
    )
    assert found[0] == Repeat(
        index=0,
        fact_id=ids["rediscovery"],
        owner_id=ids["ashenmere"],
        score=1.0,
        text=found[0].text,
    )
    # the fact it repeats, as it reads
    assert found[0].text == CAVES_947
    # the debate line holds 6 of its 11 words in the Law's fact, fewer in
    # Ashenmere's glyph fact (0.32); the White Talon's is no repeat
    assert len(found) == 2
    assert (found[1].index, found[1].fact_id, found[1].owner_id) == (
        1,
        ids["law_947"],
        ids["law"],
    )
    assert found[1].score == pytest.approx(6 / 11)
    assert overlap(DEBATE, GLYPHS) < 0.4


def test_find_repeats_tie_goes_to_the_first_owner(world):
    ids = _owners(world)
    view = world.view()
    # the Codex's line holds 0.6 of its words in both the Law's fact and
    # Ashenmere's glyph fact
    assert overlap(CODEX_947, LAW_947) == overlap(CODEX_947, GLYPHS) == 0.6
    [first] = find_repeats(view, [CODEX_947], [ids["law"], ids["ashenmere"]], 0.4)
    assert first.fact_id == ids["law_947"]
    [first] = find_repeats(view, [CODEX_947], [ids["ashenmere"], ids["law"]], 0.4)
    assert first.fact_id == ids["glyphs"]


def test_find_repeats_only_reads_the_owners_given(world):
    ids = _owners(world)
    view = world.view()
    found = find_repeats(view, [CODEX_947], [ids["law"]], 0.4)
    assert [(r.fact_id, r.owner_id) for r in found] == [(ids["law_947"], ids["law"])]
    assert find_repeats(view, [CODEX_947], [ids["tsardom"]], 0.4) == []
    assert find_repeats(view, [CODEX_947], [], 0.4) == []
    assert find_repeats(view, [], [ids["law"]], 0.4) == []


def test_find_repeats_threshold_is_inclusive(world):
    ids = _owners(world)
    view = world.view()
    score = overlap(TALON_ELITE, TSARDOM_ARMY)
    assert find_repeats(view, [TALON_ELITE], [ids["tsardom"]], 0.4) == []
    [hit] = find_repeats(view, [TALON_ELITE], [ids["tsardom"]], score)
    assert hit.fact_id == ids["army"]


def test_find_repeats_reads_live_facts_only(world):
    ids = _owners(world)
    with world.revision(Source.manual()) as rev:
        rev.remove_fact(ids["rediscovery"])
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(ids["law"])
    view = world.view()
    # the rediscovery is gone, and the Law with it; the glyph fact still
    # holds some of the words, below the threshold
    assert find_repeats(view, [CAVES_947], [ids["ashenmere"], ids["law"]], 0.4) == []
    # at an earlier revision they were there
    old = world.view(rev=view.rev - 2)
    [hit] = find_repeats(old, [CAVES_947], [ids["ashenmere"]], 0.4)
    assert hit.fact_id == ids["rediscovery"]


def test_find_repeats_reads_every_story_date(world):
    """A restated fact that has ended, or holds only from a later date,
    is still in the world: a repeat whatever the view's date."""

    with world.revision(Source.manual()) as rev:
        ashenmere = rev.create_thing("place", fields={"name": "Ashenmere"})
        later = rev.add_fact(
            ashenmere, "history", REDISCOVERY, valid_from=WorldDate.of(947)
        )
        ended = rev.add_fact(
            ashenmere,
            "general",
            LAW_947,
            valid_from=WorldDate.of(947),
            valid_until=WorldDate.of(990),
        )
    before = world.view(at=WorldDate.of(500))
    [hit] = find_repeats(before, [CAVES_947], [ashenmere], 0.4)
    assert hit.fact_id == later
    after = world.view(at=WorldDate.of(999))
    [hit] = find_repeats(after, [CODEX_947], [ashenmere], 0.4)
    assert hit.fact_id == ended
    assert world.view(at=WorldDate.of(999)).thing(ashenmere).facts[0].fact_id == later


def test_find_repeats_renders_references(world):
    from talemate.world.refs import ref

    with world.revision(Source.manual()) as rev:
        stonehold = rev.create_thing("place", fields={"name": "Stonehold"})
        conclave = rev.create_thing("lore", fields={"name": "Conclave"})
        fact = rev.add_fact(
            conclave, "general", f"The Conclave keeps its archive in {ref(stonehold)}."
        )
    [hit] = find_repeats(
        world.view(), ["Its archive is in Stonehold."], [conclave], 0.9
    )
    assert hit.fact_id == fact


# --- dates that disagree -------------------------------------------------------


def _codex(world):
    with world.revision(Source.manual()) as rev:
        runeweaving = rev.create_thing("lore", fields={"name": "Runeweaving"})
        codex = rev.create_thing("item", fields={"name": "First Codex of Aelberth"})
        compiled_217 = rev.add_fact(
            runeweaving, "general", CODEX_217, valid_from=WorldDate.of(217)
        )
        compiled_312 = rev.add_fact(
            codex, "description", CODEX_312, valid_from=WorldDate.of(312)
        )
        stonehold = rev.add_fact(
            codex, "history", CODEX_STONEHOLD, valid_from=WorldDate.of(312)
        )
        undated = rev.add_fact(codex, "general", CODEX_217)
    return compiled_217, compiled_312, stonehold, undated


def test_disagreeing_dates_codex_217_vs_312(world):
    compiled_217, compiled_312, stonehold, undated = _codex(world)
    view = world.view()
    found = disagreeing_dates(
        view, [compiled_217, compiled_312, stonehold, undated], 0.4
    )
    # 217 against 312 on the compiling; the Stonehold line shares one word
    # with it, and agrees on 312 with the description; the undated copy is
    # never in a pair
    assert found == [Disagreement(a=compiled_217, b=compiled_312, years=(217, 312))]


def test_disagreeing_dates_reads_both_ways(world):
    compiled_217, compiled_312, _, _ = _codex(world)
    view = world.view()
    # the shorter line is the one mostly held: either order finds the pair
    assert disagreeing_dates(view, [compiled_312, compiled_217], 0.6) == [
        Disagreement(a=compiled_312, b=compiled_217, years=(312, 217))
    ]
    assert disagreeing_dates(view, [compiled_312, compiled_217], 0.7) == []


def test_disagreeing_dates_same_year_or_unknown_ids(world):
    compiled_217, _, _, _ = _codex(world)
    with world.revision(Source.manual()) as rev:
        other = rev.create_thing("lore", fields={"name": "Annals"})
        again = rev.add_fact(other, "general", CODEX_217, valid_from=WorldDate.of(217))
    view = world.view()
    assert disagreeing_dates(view, [compiled_217, again], 0.4) == []
    assert disagreeing_dates(view, [compiled_217, "0" * 32], 0.4) == []
    assert disagreeing_dates(view, [compiled_217, compiled_217], 0.4) == []
    assert disagreeing_dates(view, [], 0.4) == []


def test_disagreeing_dates_skips_removed_facts(world):
    compiled_217, compiled_312, _, _ = _codex(world)
    with world.revision(Source.manual()) as rev:
        rev.remove_fact(compiled_312)
    view = world.view()
    assert disagreeing_dates(view, [compiled_217, compiled_312], 0.4) == []
    old = world.view(rev=view.rev - 1)
    assert len(disagreeing_dates(old, [compiled_217, compiled_312], 0.4)) == 1
