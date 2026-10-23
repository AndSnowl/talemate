"""Facts move in to a more specific entry (curation Task 8, spec goal 2).

When a new entry is part of a broader one (a sphere it's filed in, a
place's parent, or the outer body the owner names), the create prompt
lists the broader entry's facts, labelled M1..., and the reply picks the
ones that belong on the new entry (`"move_in"`, ruling Q1: the same
call). The curation probe's probe 2 found every move and wrongly picked
7% of the stays, so (ruling C2) every fact is listed, the picks ticked and
first, the rest unticked. Accept moves the ticked ones (ruling R1: a copy
with a new id, the original removed, overrides re-pointed) in its own
revision. `move_fact` moves one fact by hand ("Move to...").

The MockClient replies are raw Skyfall output from the probe
(docs/superpowers/probes/raw/2026-10-22-curation.json, probe 2), copied
verbatim but for their `"move_in"` labels, which are this world's; the
broader entry's facts are the probe's own lines."""

import json
from typing import NamedTuple

import pytest

from talemate.world.dates import WorldDate
from talemate.world.kinds import UNSORTED_DRAWER_ID
from talemate.world.curation import CurationSettings
from talemate.world.refs import parse_refs, ref
from talemate.world.store import Source
from talemate.worldplay import prose_gen
from talemate.worldplay.bodies import OuterBody, add_outer_body
from talemate.worldplay.create import (
    MOVE_IN_SHOWN,
    MoveInFact,
    PreviewFact,
    accept_preview,
    preview_thing,
    untick_moved_repeats,
)
from talemate.worldplay.repoint import move_fact, repoint_stub
from talemate.worldplay.spheres import SUMMARY_ORIGIN

from conftest import MockClient, MockClientContext, client_responses

# Zakonnik (a stub in the Tsardom), run 2: it moved M11 in and wrote it
# again as its second fact (overlap 0.78)
ZAKONNIK_REPLY = '{ "name": "Zakonnik", "aka": [], "facts": [ { "category": "general", "text": "The Zakonnik is the comprehensive legal code of the Tsardom of Moscavia, revised in the years following the Illumination of 994 to address the practical and legal needs of a society of Owl-folk.", "since": "994" }, { "category": "general", "text": "The revised Zakonnik governs matters of roosting rights, territorial disputes over nesting spaces, and the regulation of nighttime commerce—the economic norm in a kingdom of nocturnal beings.", "since": "996" }, { "category": "general", "text": "The code establishes clear legal frameworks for property disputes involving elevated nesting platforms, which Owl-folk instinctively seek out and fiercely defend as territory.", "since": "996" }, { "category": "general", "text": "Nighttime trade is regulated under the Zakonnik to ensure fair commerce, with markets mandated to remain open from dusk to dawn across all towns and cities within the Tsardom.", "since": "996" }, { "category": "general", "text": "The Zakonnik includes provisions for the construction and legal recognition of roosting platforms in public buildings, workplaces, and residential structures, with minimum size requirements based on the occupant\'s wingspan.", "since": "997" }, { "category": "general", "text": "Disputes over nesting rights are adjudicated by local magistrates appointed under the Zakonnik, with appeals available to regional courts presided over by Owl-folk judges.", "since": "996" }, { "category": "general", "text": "The code addresses the unique legal challenges of Owl-folk society, including noise regulations during daylight hours when the majority of the population sleeps, and liability for disturbances to roosting neighbors.", "since": "996" }, { "category": "general", "text": "The Zakonnik was drafted by a council of legal scholars convened by the Tsar in the years immediately following the Illumination, drawing upon pre-994 Moscavian law while adapting it for the transformed population.", "since": "995" }, { "category": "general", "text": "Public buildings constructed before the Illumination have been retrofitted under Zakonnik mandates to include wider doorways, taller ceilings, and structural reinforcements to support roosting platforms weighing several hundred pounds.", "since": "996" }, { "category": "general", "text": "The Zakonnik also regulates the trade of materials essential to Owl-folk life, including furs, timber for nesting, and candles—staples of the nocturnal economy.", "since": "997" }, { "category": "general", "text": "Copies of the revised Zakonnik are maintained in every parish church in Moscavia, where they are read aloud in the dim, candlelit interiors that suit Owl-folk eyes, ensuring the code is accessible to all citizens.", "since": "998" } ], "names": [ { "name": "Tsardom of Moscavia", "kind": "place", "aka": [] }, { "name": "Owl-folk", "kind": "species", "aka": [] }, { "name": "Moscavian Owl-folk", "kind": "species", "aka": [] }, { "name": "Snowy Owl-folk", "kind": "race", "aka": [] } ], "elsewhere": [ { "entry": "Tsardom of Moscavia", "text": "The Zakonnik serves as the legal backbone of the Tsardom of Moscavia, ensuring that the vast northern kingdom\'s governance adapts seamlessly to the transformed Owl-folk population.", "held_by": null } ], "part_of": { "entry": "Tsardom of Moscavia", "drawer": "Doctrines & Laws" }, "move_in": ["M11"] }'

# The Architecture of Moskov (new), run 1
ARCHITECTURE_REPLY = '{ "name": "Architecture of Moskov", "aka": [{"name": "Moskovian Architecture", "tag": "common", "everyday": true}], "facts": [{"category": "general", "text": "The buildings of Moskov are constructed primarily from fieldstone and oak timber, materials chosen for their durability against the harsh northern winters and their availability from the surrounding forests of the upper Volga basin.", "held_by": null}, {"category": "general", "text": "Onion domes, gilded or painted in deep reds and golds, crown the city\'s churches and monastic buildings, their distinctive rounded forms visible across the skyline and serving as landmarks for Owl-folk navigating home through fog or darkness.", "held_by": null}, {"category": "general", "text": "Roofs throughout the city are steeply pitched with overhanging eaves, designed to shed heavy snowfalls that would otherwise collapse flatter structures, and they are traditionally painted in dark reds and greens with gold trim.", "held_by": null}, {"category": "general", "text": "Windows in Moskovian buildings are large and numerous, set high in walls to allow moonlight and candlelight to penetrate deep into interior spaces, accommodating the nocturnal habits of the Owl-folk who inhabit them.", "held_by": null}, {"category": "general", "text": "Many structures feature wide, elevated porches and open galleries along their facades, providing sheltered perches where Owl-folk can rest, socialize, or survey the streets below in safety.", "held_by": null}, {"category": "general", "text": "The Kremlin\'s walls are built from massive blocks of local limestone quarried from the banks of the Volga, with towers rising at each corner and along the curtain walls at regular intervals, each tower topped with a pointed roof and weather vane.", "held_by": null}, {"category": "general", "text": "Interior spaces are designed with high, vaulted ceilings to accommodate the tallest of the Owl-folk, and rooms are organized around large central hearths or stove-hearths that serve as both heat sources and communal gathering points during winter nights.", "held_by": null}, {"category": "general", "text": "Wooden lattice screens and decorated shutters, carved with geometric patterns and religious motifs, are fitted to windows and balconies throughout the city, allowing ventilation while maintaining privacy.", "held_by": null}, {"category": "general", "text": "The Tsar\'s palace within the Kremlin combines stone foundations with elaborate timber construction above, its halls hung with icon screens and illuminated by chandeliers of wrought iron holding dozens of beeswax candles.", "held_by": null}, {"category": "general", "text": "Market stalls and trade halls in the merchant quarters are built with open-air ground floors shaded by canvas awnings and enclosed upper galleries, allowing nighttime commerce to proceed even during summer rainstorms.", "held_by": null}, {"category": "general", "text": "Bridges across the Moskva and Volga within the city are reinforced with stone piers and timber decks, wide enough for carts and laden birds to cross side by side, and lit by rows of iron lantern brackets carrying oil lamps from dusk until dawn.", "held_by": null}], "names": [{"name": "Kremlin", "kind": "place", "aka": []}, {"name": "Tsar\'s Palace", "kind": "place", "aka": []}, {"name": "Volga", "kind": "place", "aka": []}, {"name": "Moskva River", "kind": "place", "aka": []}, {"name": "Owl-folk", "kind": "race", "aka": []}, {"name": "Tsar", "kind": "lore", "aka": []}], "elsewhere": [{"entry": "Moskov", "text": "The radial street plan of Moskov means that the city\'s concentric neighborhoods each have a character shaped by proximity to the Kremlin, with stone fortifications giving way to timber merchant halls and residential quarters in the outer rings.", "held_by": null}, {"entry": "Cathedral of the Eternal Light", "text": "The Cathedral\'s interior is designed with a cavernous, candlelit nave where the light of thousands of flames reflects off gilded icon screens and the polished surfaces of its onion domes, creating an atmosphere intended to evoke the Eternal Light itself.", "held_by": null}, {"entry": "Baptism by Candlelight", "text": "The rite\'s architecture demands shallow stone font basins built into church floors, wide enough for a young Owl to stand in while surrounded by water, with tall candelabras positioned at each corner to cast flickering light across the ceremony.", "held_by": null}, {"entry": "Zakonnik", "text": "The Zakonnik includes specific building codes governing the minimum dimensions of roosting spaces in all residential structures, ensuring compliance with the physical needs of Owl-folk tenancy as defined by law.", "held_by": null}], "part_of": {"entry": "Moskov", "drawer": "Lands & Sites"}, "move_in": ["M2", "M3", "M4", "M11"] }'

LAWS, LANDS, DOCTRINES = "1a5a0001", "1a4d0001", "d0c70001"

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
    """Present 1000. The Tsardom of Moscavia, a nation sphere with its
    summary and four of the probe's lines (the 994 transformation on its
    timeline, held by the Church; the law code naming the Zakonnik, a lore
    stub in its Doctrines & Laws); Moskov, a city in its Lands & Sites, whose
    waiver overrides the law code; and the Church of the Eternal Light, a
    religion whose Doctrines statement it holds unmarked."""

    world.set_present(WorldDate.of(1000))
    with world.revision(Source.manual(note="tsardom")) as rev:
        church = rev.create_thing(
            "sphere",
            {
                "name": "Church of the Eternal Light",
                "template": "religion",
                "drawers": [{"id": DOCTRINES, "type": "beliefs", "title": "Doctrines"}],
            },
        )
        tsardom = rev.create_thing(
            "sphere",
            {
                "name": "Tsardom of Moscavia",
                "template": "nation",
                "drawers": [
                    {"id": LAWS, "type": "beliefs", "title": "Doctrines & Laws"},
                    {"id": LANDS, "type": "places", "title": "Lands & Sites"},
                ],
            },
        )
        zakonnik = rev.create_thing(
            "lore",
            {
                "name": "Zakonnik",
                "stub": {"ignored": False},
                "part_of": {"sphere": tsardom, "drawer": LAWS},
            },
        )
        moskov = rev.create_thing(
            "place",
            {
                "name": "Moskov",
                "kind": "city",
                "part_of": {"sphere": tsardom, "drawer": LANDS},
            },
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
            "statement",
            f"The Light chose the Tsars of {ref(tsardom, 'Moscavia')} to rule.",
            origin={"drawer": DOCTRINES},
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


def _with_move_in(reply: str, labels: list[str]) -> str:
    """The probe's reply with this world's labels in its `"move_in"`."""

    obj = json.loads(reply)
    obj["move_in"] = labels
    return json.dumps(obj)


async def _preview(world, kind, prompt, fields, reply, **kwargs):
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply)
        preview = await preview_thing(world, kind, prompt, fields, client, **kwargs)
    return preview, str(client.prompt_history[0]["prompt"])


async def _zakonnik(world, t, labels=("M3",)):
    """The Zakonnik stub expanded with the probe's reply: M3 is the law
    code."""

    return await _preview(
        world,
        "lore",
        "The Zakonnik: the Tsardom's legal code.",
        {},
        _with_move_in(ZAKONNIK_REPLY, list(labels)),
        stub_id=t.zakonnik,
    )


def _tick_picks(preview):
    """The owner ticks the model's picks (they arrive unticked, ruling
    C24), and unticks each own fact flagged as repeating one of them."""

    picked = {m.fact_id for m in preview.move_in if m.picked}
    for row in preview.move_in:
        row.ticked = row.ticked or row.picked
    for fact in preview.facts:
        if (fact.repeat_of or {}).get("fact_id") in picked:
            fact.ticked = False
    return preview


def _block(prompt: str) -> list[str]:
    head = (
        "Tsardom of Moscavia is the broader entry this lore is part of. What "
        "Tsardom of Moscavia says now, labelled M1, M2...:\n"
    )
    assert head in prompt
    block = prompt.split(head, 1)[1].split("\n\n", 1)[0]
    return block.splitlines()


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


# --- the preview ---------------------------------------------------------------


async def test_move_in_offered_for_part_of_new_entry(world, tsardom):
    """A new entry filed in a sphere is shown the sphere's facts (not its
    summary), labelled M1..., with the probe's wording; the Tsardom isn't
    "Named in this prompt" too. Every fact is offered unticked
    (ruling C24): the model's pick marked `picked` and first, an unknown
    label dropped, the rest in order."""

    t = tsardom
    preview, prompt = await _preview(
        world,
        "lore",
        "The Architecture of Moskov, in the Tsardom of Moscavia.",
        {"part_of": {"sphere": t.tsardom, "drawer": LAWS}},
        _with_move_in(ARCHITECTURE_REPLY, ["M4", "M9"]),
    )
    assert _block(prompt) == [
        f"- M1: {CAPITAL}",
        f"- M2: (In 994) {TRANSFORMATION}",
        f"- M3: {LAW_CODE.format('the Zakonnik')}",
        f"- M4: {ARCHITECTURE}",
    ]
    assert SUMMARY not in prompt.split("Entries near this one", 1)[0]
    assert '"Tsardom of Moscavia" means' not in prompt
    assert ', "move_in": ["<an M label>"]' in prompt
    assert (
        '- "move_in": the labels of Tsardom of Moscavia\'s facts above that are '
        "mainly about this lore, so they belong on its page rather than on "
        "Tsardom of Moscavia's. They move here: don't write them again in "
        '"facts". A fact that only mentions the lore in passing stays where '
        "it is. An empty list is fine."
    ) in prompt

    assert [(m.fact_id, m.from_id, m.picked) for m in preview.move_in] == [
        (t.architecture, t.tsardom, True),
        (t.capital, t.tsardom, False),
        (t.transformation, t.tsardom, False),
        (t.law_code, t.tsardom, False),
    ]
    assert not any(m.ticked for m in preview.move_in)
    assert preview.move_in[0].text == ARCHITECTURE
    assert preview.move_in[3].text == LAW_CODE.format("the Zakonnik")


async def test_no_move_in_block_without_a_broader_entry(world, tsardom):
    preview, prompt = await _preview(
        world,
        "lore",
        "The Architecture of Moskov.",
        {},
        _with_move_in(ARCHITECTURE_REPLY, ["M4"]),
    )
    assert "is the broader entry" not in prompt
    assert '"move_in"' not in prompt
    assert preview.move_in == []


async def test_move_in_for_a_stub_in_a_sphere_flags_its_repeat(world, tsardom):
    """The Zakonnik stub, filed in the Tsardom, picks the law code to move
    in; its reply wrote the code again as its second fact (the probe's
    duplicate). The pick arrives unticked (ruling C24), so nothing moves
    unless the owner ticks it. The copy restates the law code the Tsardom
    still has, so it arrives unticked as already in the world, a repeat of
    it: the claim isn't lost either way."""

    t = tsardom
    preview, _prompt = await _zakonnik(world, t)
    assert [(m.fact_id, m.picked, m.ticked) for m in preview.move_in] == [
        (t.law_code, True, False),
        (t.capital, False, False),
        (t.transformation, False, False),
        (t.architecture, False, False),
    ]
    again = preview.facts[1]
    assert again.text.startswith("The revised Zakonnik governs matters of roosting")
    assert again.ticked is False
    assert again.repeat_of["fact_id"] == t.law_code
    assert again.repeat_of["owner_id"] == t.tsardom
    assert again.repeat_of["score"] >= 0.7


def test_untick_moved_repeats(world, tsardom):
    """The duplicate rule on its own: an own fact nearly the same as a
    ticked move is unticked (at the world's untick threshold, with enough
    words); one like an unticked move, or a short one, isn't; one like a
    pick the owner hasn't ticked is flagged but stays ticked."""

    t = tsardom
    view = world.view()
    facts = [
        PreviewFact(category="general", text=CAPITAL.replace("Its", "The Tsardom's")),
        PreviewFact(category="general", text=ARCHITECTURE),
        PreviewFact(category="general", text="Moskov."),
    ]
    moves = [
        MoveInFact(fact_id=t.capital, from_id=t.tsardom, text=CAPITAL, ticked=True),
        MoveInFact(
            fact_id=t.architecture,
            from_id=t.tsardom,
            text=ARCHITECTURE,
            ticked=False,
        ),
        MoveInFact(fact_id=t.law_code, from_id=t.tsardom, text="Moskov.", ticked=True),
    ]
    untick_moved_repeats(view, facts, moves, CurationSettings())
    assert [f.ticked for f in facts] == [False, True, True]
    assert facts[0].repeat_of["fact_id"] == t.capital
    assert facts[0].repeat_of["owner_name"] == "Tsardom of Moscavia"
    assert facts[1].repeat_of is None

    # a pick the owner hasn't ticked (ruling C24): the copy is flagged as
    # repeating it, and stays ticked
    facts = [PreviewFact(category="general", text=ARCHITECTURE)]
    picked = MoveInFact(
        fact_id=t.architecture,
        from_id=t.tsardom,
        text=ARCHITECTURE,
        ticked=False,
        picked=True,
    )
    untick_moved_repeats(view, facts, [picked], CurationSettings())
    assert facts[0].ticked is True
    assert facts[0].repeat_of["fact_id"] == t.architecture

    # the world's threshold: every word of it is in the move, or it stays
    facts = [PreviewFact(category="general", text=CAPITAL.replace("Its", "The"))]
    untick_moved_repeats(
        view, facts, moves[:1], CurationSettings(repeat_untick_threshold=1.0)
    )
    assert facts[0].ticked is False
    facts = [PreviewFact(category="general", text=CAPITAL + " Owls nest there.")]
    untick_moved_repeats(
        view, facts, moves[:1], CurationSettings(repeat_untick_threshold=1.0)
    )
    assert facts[0].ticked is True


async def test_move_in_for_a_place_in_its_parent(world, tsardom):
    """A new place's parent is its broader entry."""

    t = tsardom
    reply = json.dumps(
        {
            "name": "The Kremlin",
            "aka": [],
            "facts": [
                {"category": "description", "text": "The fortified heart of Moskov."}
            ],
            "names": [],
            "move_in": ["M1"],
        }
    )
    preview, prompt = await _preview(
        world, "place", "The Kremlin of Moskov.", {"parent": t.moskov}, reply
    )
    assert "Moskov is the broader entry this place is part of." in prompt
    assert [(m.fact_id, m.from_id, m.picked) for m in preview.move_in] == [
        (t.waiver, t.moskov, True),
        (t.cathedral, t.moskov, False),
    ]


async def test_move_in_shows_at_most_its_cap(world, tsardom):
    """A broader entry with more facts than fit: the first
    `MOVE_IN_SHOWN` are labelled, and every one is still offered, the
    unshown ones unticked."""

    t = tsardom
    with world.revision(Source.manual(note="more")) as rev:
        extra = [
            rev.add_fact(t.tsardom, "about", f"The Tsardom keeps custom number {n}.")
            for n in range(MOVE_IN_SHOWN)
        ]
    labels = [f"M{MOVE_IN_SHOWN}", f"M{MOVE_IN_SHOWN + 1}"]
    preview, prompt = await _zakonnik(world, t, labels)
    block = _block(prompt)
    assert len(block) == MOVE_IN_SHOWN
    assert block[-1].startswith(f"- M{MOVE_IN_SHOWN}: The Tsardom keeps custom")
    assert len(preview.move_in) == MOVE_IN_SHOWN + 4
    # M30 is the 26th extra fact; M31 was never shown
    assert [m.fact_id for m in preview.move_in if m.picked] == [
        extra[MOVE_IN_SHOWN - 5]
    ]


async def test_outer_body_changes_what_moves_in(world, tsardom):
    """The entry put into an outer body (rulings C11, C13): it still sits
    in its home, the Tsardom, through the body, so the model's picks from
    the Tsardom stay, unless the owner files the body somewhere else. A
    body the world has adds its own facts, unticked (the model never saw
    them); a new one has none."""

    t = tsardom
    before = [(t.law_code, True), (t.capital, False)]
    before += [(t.transformation, False), (t.architecture, False)]
    tsardom_rows = [(fact_id, t.tsardom, picked) for fact_id, picked in before]

    preview, _prompt = await _zakonnik(world, t)
    add_outer_body(
        world, preview, "Zakonnik", OuterBody(name="The Codes", template="field")
    )
    rows = [(m.fact_id, m.from_id, m.picked) for m in preview.move_in]
    assert rows == tsardom_rows

    # filed in the Church instead: no longer inside the Tsardom
    preview, _prompt = await _zakonnik(world, t)
    add_outer_body(
        world,
        preview,
        "Zakonnik",
        OuterBody(
            name="The Codes",
            template="field",
            part_of={"sphere": t.church, "drawer": UNSORTED_DRAWER_ID},
        ),
    )
    assert preview.move_in == []

    preview, _prompt = await _zakonnik(world, t)
    add_outer_body(
        world,
        preview,
        "Zakonnik",
        OuterBody(name="Church of the Eternal Light", template="religion"),
        as_sphere=True,
    )
    rows = [(m.fact_id, m.from_id, m.picked) for m in preview.move_in]
    assert rows == [*tsardom_rows, (t.light, t.church, False)]

    # a body the world has that sits in the Tsardom keeps its rows too
    with world.revision(Source.manual(note="courts")) as rev:
        courts = rev.create_thing(
            "sphere",
            {
                "name": "The Courts",
                "template": "order",
                "part_of": {"sphere": t.tsardom, "drawer": UNSORTED_DRAWER_ID},
            },
        )
        ruling = rev.add_fact(courts, "about", "The Courts sit in Moskov.")
    preview, _prompt = await _zakonnik(world, t)
    add_outer_body(
        world,
        preview,
        "Zakonnik",
        OuterBody(
            name="The Courts",
            template="order",
            part_of={"sphere": t.church, "drawer": UNSORTED_DRAWER_ID},
        ),
        as_sphere=True,
    )
    rows = [(m.fact_id, m.from_id, m.picked) for m in preview.move_in]
    assert rows == [*tsardom_rows, (ruling, courts, False)]


# --- accept ----------------------------------------------------------------


async def test_move_in_copies_and_removes(world, tsardom):
    """The ticked fact goes onto the new entry as a new fact, in the
    accept's one revision: its link to the entry itself becomes its words,
    and it's gone from the Tsardom. Unticked ones stay, and the duplicate
    own fact the owner unticked isn't written."""

    t = tsardom
    preview, _prompt = await _zakonnik(world, t)
    _tick_picks(preview)
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
    texts = [f.text for f in world.live_facts(t.zakonnik)]
    assert not any(text.startswith("The revised Zakonnik") for text in texts)
    # the Tsardom lost a fact its prose reads
    assert t.tsardom in prose


async def test_accept_skips_an_own_fact_repeating_a_ticked_move(world, tsardom):
    """The safety net behind the preview (ruling C24): an own fact still
    ticked that says again what a ticked move brings in (the Zakonnik's
    copy of the law code, ticked by a client that didn't untick it) isn't
    written twice. The move brings the claim; a note says so."""

    t = tsardom
    preview, _prompt = await _zakonnik(world, t)
    for row in preview.move_in:
        row.ticked = row.picked
    again = preview.facts[1]
    assert again.text.startswith("The revised Zakonnik")
    again.ticked = True
    notes: list[str] = []
    accept_preview(world, preview, notes=notes)
    texts = [f.text for f in world.live_facts(t.zakonnik)]
    assert not any(text.startswith("The revised Zakonnik") for text in texts)
    _fact(world, t.zakonnik, LAW_CODE.format("the Zakonnik"))
    assert any("moved in" in note for note in notes)


async def test_move_in_keeps_dates_origin_held_by(world, tsardom):
    t = tsardom
    preview, _prompt = await _zakonnik(world, t, ["M2"])
    accept_preview(world, _tick_picks(preview))
    moved = _fact(world, t.zakonnik, TRANSFORMATION)
    assert moved.fact_id != t.transformation
    assert moved.valid_from == WorldDate.of(994)
    assert moved.valid_until is None
    assert moved.origin == {"held_by": t.church}
    # a lore entry has no timeline: its general category, as dated
    assert moved.category == "general"


async def test_move_in_repoints_overrides(world, tsardom):
    """Moskov's waiver overrode the law code: it overrides the copy now."""

    t = tsardom
    preview, _prompt = await _zakonnik(world, t)
    accept_preview(world, _tick_picks(preview))
    moved = _fact(world, t.zakonnik, LAW_CODE.format("the Zakonnik"))
    waiver = next(f for f in world.live_facts(t.moskov) if f.fact_id == t.waiver)
    assert waiver.overrides == [moved.fact_id]


async def test_move_in_owner_unticks_and_ticks(world, tsardom):
    """The owner's ticks win: a pick left unticked stays, a ticked other
    row moves. A row whose fact was removed since is left, with a note."""

    t = tsardom
    preview, _prompt = await _zakonnik(world, t)
    rows = {m.fact_id: m for m in preview.move_in}
    rows[t.law_code].ticked = False
    rows[t.architecture].ticked = True
    rows[t.capital].ticked = True
    with world.revision(Source.manual(note="gone")) as rev:
        rev.remove_fact(t.capital)
    notes: list[str] = []
    accept_preview(world, preview, notes=notes)
    assert t.law_code in _live_ids(world, t.tsardom)
    assert t.architecture not in _live_ids(world, t.tsardom)
    _fact(world, t.zakonnik, ARCHITECTURE)
    assert any("Tsardom of Moscavia" in note and "since" in note for note in notes)


async def test_broader_prose_goes_stale(world, tsardom):
    """The Tsardom's cached description reads stale once a fact it's
    written from moves out."""

    t = tsardom
    cache = world.prose()
    start, end = prose_gen.stretch_containing(world, t.tsardom, None)
    for section in prose_gen.sections_for("sphere"):
        cache.put(t.tsardom, section, start, end, "Old prose.")

    def stale() -> bool:
        return cache.stale(
            t.tsardom,
            "description",
            None,
            prose_gen.staleness_also(world, t.tsardom, "description", None),
            prose_gen.unread_categories("sphere", "description"),
        )

    assert stale() is False
    preview, _prompt = await _zakonnik(world, t)
    accept_preview(world, _tick_picks(preview))
    assert stale() is True


async def test_undo_redo_move_in(world, tsardom):
    t = tsardom
    before = {thing: _live_ids(world, thing) for thing in (t.tsardom, t.moskov)}
    preview, _prompt = await _zakonnik(world, t)
    accept_preview(world, _tick_picks(preview))
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
    assert moved.category == "about"
    assert notes == [
        "a sphere has no description facts: it's under about on Tsardom of Moscavia"
    ]

    # a belief its owner held unmarked stays held, away from its drawer
    prose = []
    new_id = move_fact(world, t.light, t.tsardom, prose=prose)
    moved = next(f for f in world.live_facts(t.tsardom) if f.fact_id == new_id)
    assert moved.category == "statement"
    # the Tsardom has no such drawer: the statement is in none there
    assert moved.origin == {"held_by": t.church}
    assert moved.text == "The Light chose the Tsars of Moscavia to rule."
    # a statement is no input to either sphere's prose
    assert prose == []

    # an ended fact keeps its end
    with world.revision(Source.manual(note="ended")) as rev:
        ended = rev.add_fact(
            t.church,
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


def test_move_fact_keeps_a_drawer_the_target_has(world, tsardom):
    """A statement moved onto a sphere with a drawer of the same id stays
    in it."""

    t = tsardom
    with world.revision(Source.manual(note="chapel")) as rev:
        chapel = rev.create_thing(
            "sphere",
            {
                "name": "The Chapel",
                "template": "religion",
                "drawers": [{"id": DOCTRINES, "type": "beliefs", "title": "Creed"}],
            },
        )
    new_id = move_fact(world, t.light, chapel)
    moved = next(f for f in world.live_facts(chapel) if f.fact_id == new_id)
    assert moved.origin == {"drawer": DOCTRINES, "held_by": t.church}


# --- repoint's fallback, shared with moving --------------------------------------


@pytest.mark.parametrize(
    ("kind", "category"), [("place", "history"), ("sphere", "timeline")]
)
def test_repoint_dated_fact_lands_in_default_category(world, kind, category):
    """A stub's dated fact in a category the target lacks goes where
    `default_category` puts a dated fact: a place's history, a sphere's
    timeline (not their plain general or about)."""

    fields = {"name": "Target"} | ({"template": "nation"} if kind == "sphere" else {})
    with world.revision(Source.manual(note="stub")) as rev:
        target = rev.create_thing(kind, fields)
        stub = rev.create_thing(
            "event", {"name": "The Thaw", "stub": {"ignored": False}}
        )
        rev.add_fact(stub, "summary", "The ice broke.", valid_from=WorldDate.of(990))
    repoint_stub(world, stub, target)
    moved = [f for f in world.live_facts(target) if f.text == "The ice broke."]
    assert [(f.category, f.valid_from) for f in moved] == [
        (category, WorldDate.of(990))
    ]
