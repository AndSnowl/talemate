"""Facts move to a more specific entry.

A create preview's "Could move here" (Filing, Task 4, replacing the
create move-in): the facts on entries near the new one whose text names
it, found by code with no model call, offered unticked; accept moves the
ticked ones (ruling R1: a copy with a new id, the original removed,
overrides re-pointed) in its one revision, checking each row again.

`move_fact` moves one fact by hand ("Move to...").

The Zakonnik and Architecture replies are raw Skyfall output from the
curation probe (docs/superpowers/probes/raw/2026-10-22-curation.json,
probe 2), copied verbatim but for their `"move_in"` labels, which are
this world's (and ignored by a create preview now); the broader entry's
facts are the probe's own lines."""

import json
from typing import NamedTuple

import pytest

from talemate.world.dates import WorldDate
from talemate.world.refs import parse_refs, ref
from talemate.world.store import Source
from talemate.worldplay import prose_gen
from talemate.worldplay.create import (
    MoveHereFact,
    accept_preview,
    preview_thing,
)
from talemate.worldplay.repoint import move_fact, repoint_stub

from conftest import MockClient, MockClientContext, client_responses

# Zakonnik (a stub in the Tsardom), run 2: it moved M11 in and wrote it
# again as its second fact (overlap 0.78)
ZAKONNIK_REPLY = '{ "name": "Zakonnik", "aka": [], "facts": [ { "category": "general", "text": "The Zakonnik is the comprehensive legal code of the Tsardom of Moscavia, revised in the years following the Illumination of 994 to address the practical and legal needs of a society of Owl-folk.", "since": "994" }, { "category": "general", "text": "The revised Zakonnik governs matters of roosting rights, territorial disputes over nesting spaces, and the regulation of nighttime commerce—the economic norm in a kingdom of nocturnal beings.", "since": "996" }, { "category": "general", "text": "The code establishes clear legal frameworks for property disputes involving elevated nesting platforms, which Owl-folk instinctively seek out and fiercely defend as territory.", "since": "996" }, { "category": "general", "text": "Nighttime trade is regulated under the Zakonnik to ensure fair commerce, with markets mandated to remain open from dusk to dawn across all towns and cities within the Tsardom.", "since": "996" }, { "category": "general", "text": "The Zakonnik includes provisions for the construction and legal recognition of roosting platforms in public buildings, workplaces, and residential structures, with minimum size requirements based on the occupant\'s wingspan.", "since": "997" }, { "category": "general", "text": "Disputes over nesting rights are adjudicated by local magistrates appointed under the Zakonnik, with appeals available to regional courts presided over by Owl-folk judges.", "since": "996" }, { "category": "general", "text": "The code addresses the unique legal challenges of Owl-folk society, including noise regulations during daylight hours when the majority of the population sleeps, and liability for disturbances to roosting neighbors.", "since": "996" }, { "category": "general", "text": "The Zakonnik was drafted by a council of legal scholars convened by the Tsar in the years immediately following the Illumination, drawing upon pre-994 Moscavian law while adapting it for the transformed population.", "since": "995" }, { "category": "general", "text": "Public buildings constructed before the Illumination have been retrofitted under Zakonnik mandates to include wider doorways, taller ceilings, and structural reinforcements to support roosting platforms weighing several hundred pounds.", "since": "996" }, { "category": "general", "text": "The Zakonnik also regulates the trade of materials essential to Owl-folk life, including furs, timber for nesting, and candles—staples of the nocturnal economy.", "since": "997" }, { "category": "general", "text": "Copies of the revised Zakonnik are maintained in every parish church in Moscavia, where they are read aloud in the dim, candlelit interiors that suit Owl-folk eyes, ensuring the code is accessible to all citizens.", "since": "998" } ], "names": [ { "name": "Tsardom of Moscavia", "kind": "place", "aka": [] }, { "name": "Owl-folk", "kind": "species", "aka": [] }, { "name": "Moscavian Owl-folk", "kind": "species", "aka": [] }, { "name": "Snowy Owl-folk", "kind": "race", "aka": [] } ], "elsewhere": [ { "entry": "Tsardom of Moscavia", "text": "The Zakonnik serves as the legal backbone of the Tsardom of Moscavia, ensuring that the vast northern kingdom\'s governance adapts seamlessly to the transformed Owl-folk population.", "held_by": null } ], "part_of": { "entry": "Tsardom of Moscavia", "drawer": "Doctrines & Laws" }, "move_in": ["M11"] }'

# a summary fact's origin (`entries.is_summary_fact`)
SUMMARY_ORIGIN = {"summary": True}

# the probe's Tsardom lines (M2, M4, M11, M8), verbatim
CAPITAL = (
    "Its capital city of Moskov stands at the confluence of the Volga and "
    "Moskva rivers, a sprawling fortress-city of stone and timber dominated by "
    "the gilded onion domes of its churches and the towering spires of the "
    "Tsar's palace."
)
TRANSFORMATION = (
    "In the year 994, every human being within Moscavia's borders who could "
    "trace at least one grandparent to Moscavian bloodline was seized by a "
    "sudden, blinding transformation that reshaped their bodies entirely into "
    "those of large owls, while preserving their full human minds."
)
LAW_CODE = (
    "The Tsardom's legal code, {}, was revised in the years following the "
    "transformation to address matters of roosting rights, territorial "
    "disputes over elevated nesting spaces, and the regulation of nighttime "
    "commerce, which has become the economic norm."
)
ARCHITECTURE = (
    "The Tsardom's architecture has gradually adapted to its changed "
    "population, with wider doorways, taller ceilings, and roosting platforms "
    "incorporated into public buildings, though many pre-transformation "
    "structures remain in use."
)
SUMMARY = "The Tsardom of Moscavia is a vast northern kingdom of Owl-folk."


class Tsardom(NamedTuple):
    church: str
    tsardom: str
    zakonnik: str
    moskov: str
    summary: str
    capital: str
    transformation: str
    law_code: str
    architecture: str
    waiver: str
    cathedral: str
    light: str


@pytest.fixture
def tsardom(world):
    """Present 1000. The Tsardom of Moscavia, a place with its summary and
    four of the probe's lines (the 994 transformation on its timeline,
    held by the Church; the law code naming the Zakonnik, a lore stub
    filed in it); Moskov, a city filed in it, whose waiver overrides the
    law code; and the Church of the Eternal Light, lore whose belief it
    holds (marked: nothing holds a fact implicitly but its own belief)."""

    world.set_present(WorldDate.of(1000))
    with world.revision(Source.manual(note="tsardom")) as rev:
        church = rev.create_thing(
            "lore", {"name": "Church of the Eternal Light", "hint": "religion"}
        )
        tsardom = rev.create_thing("place", {"name": "Tsardom of Moscavia"})
        zakonnik = rev.create_thing(
            "lore",
            {
                "name": "Zakonnik",
                "stub": {"ignored": False},
                "filings": [{"target": tsardom}],
            },
        )
        moskov = rev.create_thing(
            "place",
            {"name": "Moskov", "tag": "city", "filings": [{"target": tsardom}]},
        )
        summary = rev.add_fact(tsardom, "about", SUMMARY, origin=SUMMARY_ORIGIN)
        capital = rev.add_fact(tsardom, "about", CAPITAL)
        transformation = rev.add_fact(
            tsardom,
            "timeline",
            TRANSFORMATION,
            valid_from=WorldDate.of(994),
            origin={"held_by": church},
        )
        law_code = rev.add_fact(
            tsardom, "about", LAW_CODE.format(ref(zakonnik, "the Zakonnik"))
        )
        architecture = rev.add_fact(tsardom, "about", ARCHITECTURE)
        waiver = rev.add_fact(
            moskov,
            "law",
            "In Moskov the code's roosting rules are waived within the Kremlin.",
            overrides=[law_code],
        )
        cathedral = rev.add_fact(
            moskov,
            "description",
            f"The cathedral of {ref(church, 'the Church')} stands at its heart.",
        )
        light = rev.add_fact(
            church,
            "belief",
            f"The Light chose the Tsars of {ref(tsardom, 'Moscavia')} to rule.",
            origin={"held_by": church},
        )
    return Tsardom(
        church=church,
        tsardom=tsardom,
        zakonnik=zakonnik,
        moskov=moskov,
        summary=summary,
        capital=capital,
        transformation=transformation,
        law_code=law_code,
        architecture=architecture,
        waiver=waiver,
        cathedral=cathedral,
        light=light,
    )


def _queue(*responses: str) -> None:
    for response in responses:
        client_responses.get().append(response)


async def _preview(world, kind, prompt, fields, reply, **kwargs):
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply)
        preview = await preview_thing(world, kind, prompt, fields, client, **kwargs)
    return preview, str(client.prompt_history[0]["prompt"])


def _live_ids(world, thing_id):
    return [f.fact_id for f in world.live_facts(thing_id)]


def _fact(world, thing_id, text):
    view = world.view()
    found = [f for f in world.live_facts(thing_id) if view.render(f.text) == text]
    assert len(found) == 1, (
        text,
        [view.render(f.text) for f in world.live_facts(thing_id)],
    )
    return found[0]


# --- could move here (Filing, Task 4: by code, replacing move-in) -----------------


# a short reply of the Zakonnik's own: none of its facts repeats the law
# code (the probe's replies write it again, see below)
ZAKONNIK_OWN = json.dumps(
    {
        "name": "Zakonnik",
        "aka": [],
        "facts": [
            {
                "category": "general",
                "text": "Copies of the Zakonnik are read aloud in every parish church.",
            }
        ],
        "names": [],
        "move_in": ["M3"],
    }
)


async def _zakonnik_here(world, t, reply=None):
    """The Zakonnik stub expanded: the Tsardom's law code names it, so it
    could move here."""

    return await _preview(
        world,
        "lore",
        "The Zakonnik: the Tsardom's legal code.",
        {},
        reply if reply is not None else ZAKONNIK_OWN,
        stub_id=t.zakonnik,
    )


def _tick_moves(preview):
    for row in preview.move_here:
        row.ticked = True
    return preview


async def test_move_here_offers_facts_that_name_it(world, tsardom):
    """A stub's "Could move here" rows are the facts near it that name it
    (the Tsardom's law code, linking the Zakonnik), unticked; the reply's
    `"move_in"` labels are ignored and the prompt lists no broader entry's
    facts. Facts that don't name it (the capital, the 994 transformation)
    aren't offered."""

    t = tsardom
    preview, prompt = await _zakonnik_here(world, t)
    assert [(m.fact_id, m.from_id, m.ticked) for m in preview.move_here] == [
        (t.law_code, t.tsardom, False)
    ]
    assert preview.move_here[0].text == LAW_CODE.format("the Zakonnik")
    assert "is the broader entry" not in prompt
    assert '"move_in"' not in prompt


async def test_move_here_leaves_out_what_the_reply_repeats(world, tsardom):
    """The probe's verbatim reply wrote the law code again (its second
    fact, overlap 0.78): that fact is flagged a repeat of the law code, so
    the law code isn't offered to move here too -- the repeat's own row
    offers it (the claim isn't lost either way)."""

    t = tsardom
    preview, _prompt = await _zakonnik_here(world, t, ZAKONNIK_REPLY)
    again = preview.facts[1]
    assert again.text.startswith("The revised Zakonnik governs matters of roosting")
    assert again.repeat_of["fact_id"] == t.law_code
    assert preview.move_here == []


async def test_move_here_copies_and_removes(world, tsardom):
    """The ticked fact goes onto the entry as a new fact, in the accept's
    one revision: its link to the entry itself becomes its words, and it's
    gone from the Tsardom, whose prose read it."""

    t = tsardom
    preview, _prompt = await _zakonnik_here(world, t)
    _tick_moves(preview)
    head = world.head_rev()
    prose: list[str] = []
    thing_id = accept_preview(world, preview, prose=prose)
    assert thing_id == t.zakonnik
    assert world.head_rev() == head + 1

    assert t.law_code not in _live_ids(world, t.tsardom)
    for kept in (t.summary, t.capital, t.transformation, t.architecture):
        assert kept in _live_ids(world, t.tsardom)
    moved = _fact(world, t.zakonnik, LAW_CODE.format("the Zakonnik"))
    assert moved.fact_id != t.law_code
    assert moved.text == LAW_CODE.format("the Zakonnik")
    assert moved.category == "general"
    assert t.tsardom in prose


async def test_move_here_keeps_dates_origin_held_by(world, tsardom):
    t = tsardom
    with world.revision(Source.manual(note="sealed")) as rev:
        sealed = rev.add_fact(
            t.tsardom,
            "timeline",
            f"The Church sealed {ref(t.zakonnik, 'the Zakonnik')} in 995.",
            valid_from=WorldDate.of(995),
            origin={"held_by": t.church},
        )
    preview, _prompt = await _zakonnik_here(world, t)
    assert sealed in [m.fact_id for m in preview.move_here]
    accept_preview(world, _tick_moves(preview))
    moved = _fact(world, t.zakonnik, "The Church sealed the Zakonnik in 995.")
    assert moved.fact_id != sealed
    assert moved.valid_from == WorldDate.of(995)
    assert moved.valid_until is None
    assert moved.origin == {"held_by": t.church}
    # a lore entry has no timeline: its general category, as dated
    assert moved.category == "general"


async def test_move_here_repoints_overrides(world, tsardom):
    """Moskov's waiver overrode the law code: it overrides the copy now."""

    t = tsardom
    preview, _prompt = await _zakonnik_here(world, t)
    accept_preview(world, _tick_moves(preview))
    moved = _fact(world, t.zakonnik, LAW_CODE.format("the Zakonnik"))
    waiver = next(f for f in world.live_facts(t.moskov) if f.fact_id == t.waiver)
    assert waiver.overrides == [moved.fact_id]


async def test_move_here_owner_ticks_and_rows_checked_again(world, tsardom):
    """The owner's ticks win: an unticked row stays. A row whose fact was
    removed since, or one forged for a fact that doesn't name the entry,
    moves nothing, with a note."""

    t = tsardom
    preview, _prompt = await _zakonnik_here(world, t)
    assert [m.ticked for m in preview.move_here] == [False]
    accept_preview(world, preview.model_copy(deep=True))
    assert t.law_code in _live_ids(world, t.tsardom)

    with world.revision(Source.manual(note="stub again")) as rev:
        # filed in Moskov, so Moskov stays near it whatever its facts say
        zakonnik = rev.create_thing(
            "lore",
            {
                "name": "Code of Roosts",
                "stub": {"ignored": False},
                "filings": [{"target": t.moskov}],
            },
        )
        named = rev.add_fact(
            t.moskov, "law", f"Moskov keeps {ref(zakonnik, 'the Code of Roosts')}."
        )
    reply = json.dumps(
        {
            "name": "Code of Roosts",
            "facts": [
                {"category": "general", "text": "Its pages are bound in birch bark."}
            ],
        }
    )
    preview, _prompt = await _preview(
        world, "lore", "The Code of Roosts.", {}, reply, stub_id=zakonnik
    )
    assert [m.fact_id for m in preview.move_here] == [named]
    preview.move_here[0].ticked = True
    preview.move_here.append(
        MoveHereFact(fact_id=t.cathedral, from_id=t.moskov, text="x", ticked=True)
    )
    with world.revision(Source.manual(note="gone")) as rev:
        rev.remove_fact(named)
    notes: list[str] = []
    accept_preview(world, preview, notes=notes)
    assert t.cathedral in _live_ids(world, t.moskov)
    assert any("since the preview" in note for note in notes)
    assert any("doesn't name Code of Roosts" in note for note in notes)


async def test_moved_source_prose_goes_stale(world, tsardom):
    """The Tsardom's cached description reads stale once a fact it's
    written from moves out."""

    t = tsardom
    cache = world.prose()
    start, end = prose_gen.stretch_containing(world, t.tsardom, None)
    for section in prose_gen.sections_for("place"):
        cache.put(t.tsardom, section, start, end, "Old prose.")

    def stale() -> bool:
        return cache.stale(
            t.tsardom,
            "description",
            None,
            prose_gen.staleness_also(world, t.tsardom, "description", None),
            prose_gen.unread_categories("place", "description"),
        )

    assert stale() is False
    preview, _prompt = await _zakonnik_here(world, t)
    accept_preview(world, _tick_moves(preview))
    assert stale() is True


async def test_moved_here_fact_puts_the_new_entry_in_prose(world, tsardom):
    """Final review I2, since languages 4a: a draft has no prose, so with a
    fact moved here the new entry goes in `prose` to be written, from its
    own facts and the moved one."""

    t = tsardom
    preview, _prompt = await _zakonnik_here(world, t)
    _tick_moves(preview)
    for fact in preview.facts:
        fact.ticked = True
    assert preview.prose == {}
    prose: list[str] = []
    thing_id = accept_preview(world, preview, prose=prose)
    _fact(world, thing_id, LAW_CODE.format("the Zakonnik"))
    assert thing_id in prose


async def test_no_move_here_moves_no_other_entrys_prose(world, tsardom):
    """With nothing moved here, only the new entry itself is in `prose`
    (to be written: a draft has no prose since languages 4a); no entry a
    fact would have left is."""

    t = tsardom
    preview, _prompt = await _zakonnik_here(world, t)
    for fact in preview.facts:
        fact.ticked = True
    prose: list[str] = []
    thing_id = accept_preview(world, preview, prose=prose)
    assert prose == [thing_id]


async def test_undo_redo_move_here(world, tsardom):
    t = tsardom
    before = {thing: _live_ids(world, thing) for thing in (t.tsardom, t.moskov)}
    preview, _prompt = await _zakonnik_here(world, t)
    accept_preview(world, _tick_moves(preview))
    rev = world.head_rev()
    moved = _fact(world, t.zakonnik, LAW_CODE.format("the Zakonnik")).fact_id

    undone = world.undo([rev])
    assert undone.conflicts == []
    assert {thing: _live_ids(world, thing) for thing in before} == before
    waiver = next(f for f in world.live_facts(t.moskov) if f.fact_id == t.waiver)
    assert waiver.overrides == [t.law_code]
    assert world.view().thing(t.zakonnik).is_stub

    redone = world.undo([undone.undo_rev])
    assert redone.conflicts == []
    assert t.law_code not in _live_ids(world, t.tsardom)
    assert moved in _live_ids(world, t.zakonnik)
    waiver = next(f for f in world.live_facts(t.moskov) if f.fact_id == t.waiver)
    assert waiver.overrides == [moved]


# --- one fact, by hand -------------------------------------------------------------


def test_move_fact_single(world, tsardom):
    """One fact moved in one revision: a new id, the original gone, the
    override re-pointed, a link to the target made its words; a category
    the target lacks becomes its default, with a note; prose for both,
    where it reads the fact."""

    t = tsardom
    head = world.head_rev()
    notes: list[str] = []
    prose: list[str] = []
    new_id = move_fact(world, t.law_code, t.zakonnik, notes=notes, prose=prose)
    assert world.head_rev() == head + 1
    assert t.law_code not in _live_ids(world, t.tsardom)
    moved = next(f for f in world.live_facts(t.zakonnik) if f.fact_id == new_id)
    assert moved.text == LAW_CODE.format("the Zakonnik")
    assert moved.category == "general"
    assert len(notes) == 1 and "general" in notes[0]
    waiver = next(f for f in world.live_facts(t.moskov) if f.fact_id == t.waiver)
    assert waiver.overrides == [new_id]
    assert prose == [t.tsardom, t.zakonnik]

    # a link to another thing stays a link
    notes = []
    new_id = move_fact(world, t.cathedral, t.tsardom, notes=notes)
    moved = next(f for f in world.live_facts(t.tsardom) if f.fact_id == new_id)
    assert parse_refs(moved.text) == [t.church]
    assert moved.category == "description"
    assert notes == []

    # a belief its owner holds stays held, away from its owner
    notes, prose = [], []
    new_id = move_fact(world, t.light, t.tsardom, notes=notes, prose=prose)
    moved = next(f for f in world.live_facts(t.tsardom) if f.fact_id == new_id)
    assert moved.category == "general"
    assert len(notes) == 1 and "general" in notes[0]
    assert moved.origin == {"held_by": t.church}
    assert moved.text == "The Light chose the Tsars of Moscavia to rule."
    assert prose == [t.church, t.tsardom]

    # an ended fact keeps its end
    with world.revision(Source.manual(note="ended")) as rev:
        ended = rev.add_fact(
            t.tsardom,
            "timeline",
            f"The cathedral of {ref(t.moskov, 'Moskov')} burned.",
            valid_from=WorldDate.of(950),
            valid_until=WorldDate.of(960),
        )
    notes = []
    new_id = move_fact(world, ended, t.moskov, notes=notes)
    moved = next(f for f in world.live_facts(t.moskov) if f.fact_id == new_id)
    # no note when the category fits
    assert notes == []
    assert (moved.valid_from, moved.valid_until) == (
        WorldDate.of(950),
        WorldDate.of(960),
    )
    assert moved.category == "timeline"
    assert moved.text == "The cathedral of Moskov burned."


def test_move_fact_refusals_write_nothing(world, tsardom):
    t = tsardom
    with world.revision(Source.manual(note="gone")) as rev:
        gone = rev.create_thing("lore", {"name": "Gone"})
        rev.remove_thing(gone)
        rev.remove_fact(t.capital)
    head = world.head_rev()
    for fact_id, target_id, why in (
        (t.capital, t.moskov, "removed"),
        ("0" * 32, t.moskov, "no such fact"),
        (t.law_code, gone, "no such"),
        (t.law_code, t.tsardom, "already"),
        (t.summary, t.moskov, "summary"),
    ):
        with pytest.raises(ValueError, match=why):
            move_fact(world, fact_id, target_id)
    assert world.head_rev() == head


# --- repoint's fallback, shared with moving --------------------------------------


@pytest.mark.parametrize(
    ("kind", "category"), [("place", "history"), ("character", "background")]
)
def test_repoint_dated_fact_lands_in_default_category(world, kind, category):
    """A stub's dated fact in a category the target lacks goes where
    `default_category` puts a dated fact: a place's history (not its plain
    general), a character's background."""

    with world.revision(Source.manual(note="stub")) as rev:
        target = rev.create_thing(kind, {"name": "Target"})
        stub = rev.create_thing(
            "event", {"name": "The Thaw", "stub": {"ignored": False}}
        )
        rev.add_fact(stub, "summary", "The ice broke.", valid_from=WorldDate.of(990))
    repoint_stub(world, stub, target)
    moved = [f for f in world.live_facts(target) if f.text == "The ice broke."]
    assert [(f.category, f.valid_from) for f in moved] == [
        (category, WorldDate.of(990))
    ]
