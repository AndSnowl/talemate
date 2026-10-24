"""One writer that tags and files (Filing plan, Task 4): the create reply's
tag, "In" rows and "File into this" rows, tagged new names with their own
filing, "Could move here" found by code, and the prompt hints.

The MockClient replies are raw Skyfall output from the filing probe
(docs/superpowers/probes/raw/2026-10-23-filing.json), read from that file
so they stay verbatim: probe 2's Frostwing Host (run 0), probe 4 v2's
Church of the White Dawn (religion hint, run 0) and probe 1's Vasha
(run 0). The probe dropped the old ties block, so no reply carries an
exception; the character test adds one to Vasha's real "in" list (the
spheres probe's exception shape, `{"text", "rejects"}`). The worlds are
small copies of the probe's."""

import json
from pathlib import Path
from typing import NamedTuple

import pytest

from talemate.world.entries import held_by
from talemate.world.filing import filings_of
from talemate.world.dates import WorldDate
from talemate.world.refs import ref
from talemate.world.store import Source
from talemate.worldplay import create
from talemate.worldplay.create import (
    CreatePreview,
    PreviewFact,
    accept_preview,
    preview_thing,
)

from conftest import MockClient, MockClientContext, client_responses

RAW = (
    Path(__file__).resolve().parents[2]
    / "docs/superpowers/probes/raw/2026-10-23-filing.json"
)


def _probe_reply(probe: str, case: str, run: int) -> str:
    data = json.loads(RAW.read_text(encoding="utf-8"))
    return next(
        r["reply"] for r in data[probe] if r["case"] == case and r["run"] == run
    )


def _queue(*responses: str) -> None:
    for response in responses:
        client_responses.get().append(response)


def _filed(*targets, role=None):
    return [
        {"target": target, "role": role, "since": None, "until": None}
        for target in targets
    ]


class Moscavia(NamedTuple):
    tsardom: str
    velikoye: str
    khorol: str
    talon: str
    talon_fact: str
    frosted: str
    host: str
    vigil: str
    blinding: str
    court: str
    tsar: str
    grounds: str
    church: str
    teaches: str
    vigil_rite: str
    dawnsingers: str


@pytest.fixture
def moscavia(world):
    """The probe's world, small, present year 1000: the Tsardom with
    Velikoye, the Khorol, the Blinding, the Night Court, the Tsar and the
    Frostmere Training Grounds filed in it; the White Talon (whose fact
    names the Frostwing Host stub) and the Frosted Wing (which doesn't),
    both regiments filed in the Tsardom; and the Church of the Eternal
    Light (not the probe's White Dawn, which the religion reply writes),
    filed in the Tsardom, with a belief, a rite and the Dawnsingers filed
    in it."""

    world.set_present(WorldDate.of(1000))
    with world.revision(Source.manual(note="moscavia")) as rev:
        tsardom = rev.create_thing(
            "place",
            {
                "name": "Tsardom of Moscavia",
                "tag": "nation",
                "aka": [{"name": "Moscavia", "tag": "common", "everyday": True}],
            },
        )
        rev.add_fact(
            tsardom,
            "description",
            "A sovereign northern realm transformed six years ago when millions "
            "of its human inhabitants became Owl-folk in a single night.",
        )
        velikoye = rev.create_thing(
            "place",
            {"name": "Velikoye", "tag": "capital", "filings": _filed(tsardom)},
        )
        rev.add_fact(
            velikoye,
            "description",
            "The fortified capital city on the banks of the Khorol River.",
        )
        khorol = rev.create_thing(
            "place",
            {
                "name": "Khorol River",
                "tag": "river",
                "filings": [
                    *_filed(tsardom),
                    *_filed(velikoye, role="runs through"),
                ],
            },
        )
        rev.add_fact(
            khorol,
            "description",
            "The primary waterway running through Velikoye, frozen eight months "
            "of the year.",
        )
        host = rev.create_thing(
            "lore", {"name": "Frostwing Host", "stub": {"ignored": False}}
        )
        talon = rev.create_thing(
            "lore",
            {"name": "The White Talon", "tag": "regiment", "filings": _filed(tsardom)},
        )
        talon_fact = rev.add_fact(
            talon,
            "general",
            f"The White Talon is the {ref(host, 'Frostwing Host')}'s heavy "
            "regiment, its ranks drawn only from pure-line Snowy Owl-folk.",
        )
        grounds = rev.create_thing(
            "place",
            {
                "name": "Frostmere Training Grounds",
                "stub": {"ignored": False},
                "filings": _filed(tsardom),
            },
        )
        frosted = rev.create_thing(
            "lore",
            {"name": "The Frosted Wing", "tag": "regiment", "filings": _filed(tsardom)},
        )
        rev.add_fact(
            frosted,
            "general",
            "The Frosted Wing is a regiment of Eared archers on the glacier "
            f"edge, raised from the {ref(grounds, 'Frostmere Training Grounds')}.",
        )
        vigil = rev.create_thing(
            "event",
            {
                "name": "The Winter Solstice Vigil",
                "tag": "festival",
                "stub": {"ignored": False},
                "filings": _filed(tsardom, velikoye),
            },
        )
        blinding = rev.create_thing(
            "event",
            {"name": "The Blinding", "tag": "cataclysm", "filings": _filed(tsardom)},
        )
        rev.add_fact(
            blinding,
            "summary",
            "On a single day in the year 994 every human of Moscavian blood "
            "became Owl-folk.",
        )
        court = rev.create_thing(
            "lore",
            {"name": "The Night Court", "tag": "council", "filings": _filed(tsardom)},
        )
        rev.add_fact(
            court, "general", "The supreme governing body of the Tsardom, by night."
        )
        tsar = rev.create_thing(
            "character",
            {
                "name": "Tsar Dmitry IV",
                "tag": "ruler",
                "filings": _filed(tsardom, role="sovereign"),
            },
        )
        rev.add_fact(
            tsar, "background", "Tsar Dmitry IV rules from his palace in Velikoye."
        )
        church = rev.create_thing(
            "lore",
            {
                "name": "Church of the Eternal Light",
                "tag": "religion",
                "filings": _filed(tsardom),
            },
        )
        teaches = rev.add_fact(
            church,
            "belief",
            "The White Dawn will return in the fullness of time to finish the "
            "transformation of the world.",
        )
        vigil_rite = rev.add_fact(
            church,
            "general",
            "Its faithful keep the Winter Solstice Vigil with white candles in "
            "every window.",
        )
        dawnsingers = rev.create_thing(
            "lore",
            {"name": "Dawnsingers", "tag": "clerical order", "filings": _filed(church)},
        )
        rev.add_fact(dawnsingers, "general", "The Dawnsingers lead public worship.")
    return Moscavia(
        tsardom=tsardom,
        velikoye=velikoye,
        khorol=khorol,
        talon=talon,
        talon_fact=talon_fact,
        frosted=frosted,
        host=host,
        vigil=vigil,
        blinding=blinding,
        court=court,
        tsar=tsar,
        grounds=grounds,
        church=church,
        teaches=teaches,
        vigil_rite=vigil_rite,
        dawnsingers=dawnsingers,
    )


HOST_PROMPT = "The Frostwing Host: the Tsardom of Moscavia's all-Owl-folk army."


async def _host_preview(world, moscavia):
    client = MockClient("test")
    async with MockClientContext():
        _queue(_probe_reply("p2", "host", 0))
        preview = await preview_thing(
            world, "lore", HOST_PROMPT, {}, client, stub_id=moscavia.host
        )
    return preview, client


def _create_prompt(client) -> str:
    return str(client.prompt_history[0]["prompt"])


def _targets(view, thing_id):
    return [f.target for f in filings_of(view, thing_id)]


# --- the reply ----------------------------------------------------------------


async def test_reply_tag_and_in_parsed(world, moscavia):
    preview, client = await _host_preview(world, moscavia)
    prompt = _create_prompt(client)

    assert preview.tag == "regiment"
    # the "In" rows, resolved by name, arrive unticked (ruling F7)
    assert [(f.target_id, f.target_name, f.role) for f in preview.filings] == [
        (moscavia.tsardom, "Tsardom of Moscavia", "primary military arm"),
        (moscavia.khorol, "Khorol River", "patrols its frozen surface"),
    ]
    assert not any(f.ticked for f in preview.filings)
    # "File into this": the White Talon, an existing name whose "in" is the
    # Host, and (by code) an entry whose fact names it -- once, unticked
    assert [(r.thing_id, r.name, r.ticked) for r in preview.file_into] == [
        (moscavia.talon, "The White Talon", False)
    ]
    # the candidate list is filing nearness: what mentions the stub first,
    # then reaching siblings -- the Frosted Wing is filed beside the White
    # Talon in the Tsardom, and no link of its own reaches the Host
    assert "- The White Talon (lore, regiment; in Tsardom of Moscavia)" in prompt
    assert "- The Frosted Wing (lore, regiment; in Tsardom of Moscavia)" in prompt
    # the tags in use, most used first; the move-in block is gone
    assert "Tags in use in the world" in prompt
    assert "regiment (2)" in prompt
    assert "M1" not in prompt and "move_in" not in prompt
    assert "Only named things become entries." in prompt


async def test_accept_writes_tag_filings_file_into(world, moscavia):
    preview, _client = await _host_preview(world, moscavia)
    for row in preview.filings:
        row.ticked = True
    for row in preview.file_into:
        row.ticked = True
    before = world.head_rev()

    thing_id = accept_preview(world, preview)

    assert thing_id == moscavia.host
    assert world.head_rev() == before + 1
    view = world.view()
    state = view.thing(thing_id)
    assert state.fields.get("tag") == "regiment"
    assert not state.is_stub
    host_filings = filings_of(view, thing_id)
    assert [(f.target, f.role) for f in host_filings] == [
        (moscavia.tsardom, "primary military arm"),
        (moscavia.khorol, "patrols its frozen surface"),
    ]
    # the White Talon keeps the Tsardom and is filed in the Host too
    assert _targets(view, moscavia.talon) == [moscavia.tsardom, thing_id]
    # never the old structure
    for field in ("part_of", "ties", "parent"):
        assert field not in state.fields


async def test_accept_leaves_unticked_rows_unwritten(world, moscavia):
    preview, _client = await _host_preview(world, moscavia)
    thing_id = accept_preview(world, preview)
    view = world.view()
    assert filings_of(view, thing_id) == []
    assert _targets(view, moscavia.talon) == [moscavia.tsardom]


async def test_names_get_tag_and_filing(world, moscavia):
    preview, _client = await _host_preview(world, moscavia)
    by_name = {n.name: n for n in preview.new_names}

    # a title is never a stub (ruling F5); names the world has aren't new
    assert "Wing Commander" not in by_name
    assert "Khorol River" not in by_name and "The White Talon" not in by_name
    citadel = by_name["Citadel of the Northern Watch"]
    assert (citadel.kind, citadel.tag) == ("place", "fortification")
    assert citadel.filing is not None
    assert (citadel.filing.target_id, citadel.filing.ticked) == (
        moscavia.tsardom,
        True,
    )
    ceremony = by_name["Silent Wings ceremony"]
    assert (ceremony.kind, ceremony.tag, ceremony.filing) == ("event", "ritual", None)

    accept_preview(world, preview)
    view = world.view()
    made = {view.name_of(t.id): t for t in view.things() if t.is_stub}
    assert made["Citadel of the Northern Watch"].fields.get("tag") == "fortification"
    assert _targets(view, made["Citadel of the Northern Watch"].id) == [
        moscavia.tsardom
    ]
    assert made["Silent Wings ceremony"].fields.get("tag") == "ritual"
    assert filings_of(view, made["Silent Wings ceremony"].id) == []
    assert "Wing Commander" not in made


async def test_name_filed_in_the_entry_itself(world, moscavia):
    """The church's clerical orders are filed in the church being written
    (`NameFiling.this_entry`, so renaming the draft keeps them there); an
    unticked name filing is left unwritten."""

    client = MockClient("test")
    async with MockClientContext():
        _queue(_probe_reply("p4v2", "religion", 0))
        preview = await preview_thing(
            world,
            "lore",
            "The Church of the White Dawn: the state church of Moscavia, seated "
            "at the Cathedral of the White Dawn in Velikoye.",
            {},
            client,
            hint="religion",
        )
    by_name = {n.name: n for n in preview.new_names}
    assert "High Bishop of the White Dawn" not in by_name
    assert by_name["Frostwalkers"].kind == "lore"
    assert by_name["Frostwalkers"].tag == "clerical order"
    assert by_name["Frostwalkers"].filing.this_entry is True
    by_name["Archivists"].filing.ticked = False

    # the owner renames the draft: the names filed in it follow
    preview.name = "Church of the Dawn Reborn"
    thing_id = accept_preview(world, preview)
    view = world.view()
    assert view.name_of(thing_id) == "Church of the Dawn Reborn"
    made = {view.name_of(t.id): t.id for t in view.things() if t.is_stub}
    assert _targets(view, made["Frostwalkers"]) == [thing_id]
    assert filings_of(view, made["Archivists"]) == []


# --- could move here -------------------------------------------------------------


async def test_move_here_is_code_only(world, moscavia):
    preview, client = await _host_preview(world, moscavia)

    # one model call for the reply (the rest are prose); no move-in labels
    assert "move_in" not in _create_prompt(client)
    assert [(r.fact_id, r.from_id, r.ticked) for r in preview.move_here] == [
        (moscavia.talon_fact, moscavia.talon, False)
    ]
    assert "Frostwing Host's heavy regiment" in preview.move_here[0].text

    # a forged row (a fact that doesn't name the Host) moves nothing
    view = world.view()
    frosted_fact = view.thing(moscavia.frosted).facts[0]
    forged = preview.move_here[0].model_copy(
        update={"fact_id": frosted_fact.fact_id, "from_id": moscavia.frosted}
    )
    preview.move_here[0].ticked = True
    forged.ticked = True
    preview.move_here.append(forged)
    notes: list[str] = []

    thing_id = accept_preview(world, preview, notes=notes)

    view = world.view()
    assert view.fact(moscavia.talon_fact) is None
    texts = [view.render(f.text) for f in view.thing(thing_id).facts]
    assert any("heavy regiment, its ranks drawn only" in t for t in texts)
    assert view.fact(frosted_fact.fact_id) is not None
    assert any("doesn't move" in note for note in notes)


async def test_move_here_leaves_out_what_an_own_fact_repeats(world, moscavia):
    with world.revision(Source.manual()) as rev:
        rev.add_fact(
            moscavia.court,
            "general",
            "The Frostwing Host is the primary military arm of the Tsardom of "
            "Moscavia, its all-Owl-folk composition reflecting the fundamental "
            "transformation of the realm's population since the Blinding of 994.",
        )
    preview, _client = await _host_preview(world, moscavia)
    assert preview.facts[0].repeat_of is not None
    assert [r.from_id for r in preview.move_here] == [moscavia.talon]


# --- prompt hints ------------------------------------------------------------


async def test_hint_adds_belief_category_and_marks_held(world, moscavia):
    client = MockClient("test")
    async with MockClientContext():
        _queue(_probe_reply("p4v2", "religion", 0))
        preview = await preview_thing(
            world,
            "lore",
            "The Church of the White Dawn: the state church of Moscavia, seated "
            "at the Cathedral of the White Dawn in Velikoye.",
            {},
            client,
            hint="religion",
        )
    prompt = _create_prompt(client)

    assert preview.hint == "religion"
    assert (
        "Prompt hint, picked by the owner: For a religion, consider what it "
        "worships" in prompt
    )
    assert '"category" is one of: belief, general.' in prompt
    assert '- "belief": every fact that says what the lore teaches' in prompt
    # "lore, religion": a kind name is no tag, the next part is (ruling F8)
    assert preview.tag == "religion"
    beliefs = [f for f in preview.facts if f.category == "belief"]
    assert len(beliefs) == 2

    thing_id = accept_preview(world, preview)
    view = world.view()
    state = view.thing(thing_id)
    written = [f for f in state.facts if f.category == "belief"]
    assert len(written) == 2
    assert all(held_by(view, fact, state) == thing_id for fact in written)
    plain = [f for f in state.facts if f.category == "general"]
    assert all(held_by(view, fact, state) is None for fact in plain)


async def test_no_hint_no_belief_category(world, moscavia):
    client = MockClient("test")
    async with MockClientContext():
        _queue(_probe_reply("p4v2", "religion", 0))
        preview = await preview_thing(
            world,
            "lore",
            "The Church of the White Dawn: the state church of Moscavia.",
            {},
            client,
        )
    prompt = _create_prompt(client)
    assert "Prompt hint" not in prompt
    assert '"category" is one of: general.' in prompt
    assert preview.hint is None
    assert {f.category for f in preview.facts} == {"general"}


def _wardens_world(world):
    """The Tsardom; Velikoye filed in it; the Khorol filed in Velikoye;
    the Tsardom's and the Khorol's facts both name the Lantern Wardens;
    and the Wardens' stub, filed in the Old Gate, whose fact names it too."""

    world.set_present(WorldDate.of(1000))
    with world.revision(Source.manual(note="wardens")) as rev:
        tsardom = rev.create_thing("place", {"name": "Tsardom of Moscavia"})
        rev.add_fact(
            tsardom, "general", "The Lantern Wardens patrol the realm's roads."
        )
        velikoye = rev.create_thing(
            "place", {"name": "Velikoye", "filings": _filed(tsardom)}
        )
        rev.add_fact(velikoye, "general", "The capital on the Khorol.")
        khorol = rev.create_thing(
            "place", {"name": "Khorol River", "filings": _filed(velikoye)}
        )
        rev.add_fact(khorol, "general", "The Lantern Wardens light the Khorol's fords.")
    return tsardom, velikoye, khorol


WARDENS_REPLY = json.dumps(
    {
        "name": "The Lantern Wardens",
        "tag": "guild",
        "facts": [{"category": "general", "text": "They keep the lanterns lit."}],
        "names": [],
        "in": [{"entry": "Velikoye", "role": "based in"}],
        "file_into": [],
    }
)


async def test_file_into_code_never_offers_where_the_draft_sits(world):
    """Ruling F32: "File into this"'s code source (near entries whose facts
    name the draft) never offers an entry the draft would itself sit in --
    an "In" target or what that sits in (the Tsardom, above Velikoye). A
    near entry that sits under it stays offered (the Khorol, as the Host
    draft's own regiments did in the Task 12 session)."""

    tsardom, velikoye, khorol = _wardens_world(world)
    client = MockClient("test")
    async with MockClientContext():
        _queue(WARDENS_REPLY)
        preview = await preview_thing(
            world,
            "lore",
            "The Lantern Wardens of Velikoye",
            {},
            client,
            picks={"Velikoye": velikoye},
        )
    assert [f.target_id for f in preview.filings] == [velikoye]
    assert [r.thing_id for r in preview.file_into] == [khorol]


async def test_file_into_code_never_offers_the_stubs_own_home(world):
    """Ruling F32, for a stub: what the stub is filed in (and above) is
    never offered into it, though its facts name the stub."""

    tsardom, velikoye, khorol = _wardens_world(world)
    with world.revision(Source.manual(note="stub")) as rev:
        stub = rev.create_thing(
            "lore",
            {
                "name": "The Lantern Wardens",
                "stub": {"ignored": False},
                "filings": _filed(khorol),
            },
        )
    reply = json.loads(WARDENS_REPLY)
    reply["in"] = []
    client = MockClient("test")
    async with MockClientContext():
        _queue(json.dumps(reply))
        preview = await preview_thing(
            world, "lore", "The Lantern Wardens", {}, client, stub_id=stub
        )
    offered = [r.thing_id for r in preview.file_into]
    assert khorol not in offered and tsardom not in offered


async def test_tag_rule_without_entries_near(world):
    """The reply's tag is asked of every entry the generic branch writes,
    with or without "Entries near this one": the Skyfall session (Task 12,
    docs/superpowers/probes/2026-10-24-filing-flow.md) wrote Runic Magic
    and the Order from prompts that named no entry in full, so their
    prompts had no near list, hence no tag rule, and none of their 6
    replies wrote a fitting tag ("lore", a kind, for Runic Magic 2 of 2)."""

    client = MockClient("test")
    async with MockClientContext():
        _queue(
            json.dumps(
                {
                    "name": "Wattles",
                    "tag": "custom",
                    "facts": [{"category": "general", "text": "Wattles are woven."}],
                    "names": [],
                }
            )
        )
        preview = await preview_thing(
            world, "lore", "Wattles, a custom of the owl-folk", {}, client
        )
    prompt = _create_prompt(client)
    assert "Entries near this one" not in prompt
    assert '- "tag": one or two words for what the lore is' in prompt
    # "in" and "file_into" still need a list to pick from
    assert '- "in": the entries listed above' not in prompt
    assert preview.tag == "custom"


async def test_unknown_hint_refused(world, moscavia):
    with pytest.raises(ValueError, match="no such prompt hint"):
        await preview_thing(
            world, "lore", "A faith.", {}, MockClient("test"), hint="cult"
        )


# --- a character's In rows ---------------------------------------------------------


VASHA_PROMPT = (
    "Vasha: a young Snowy Owl-folk mail courier of the Church of the Eternal "
    "Light's parish in Velikoye, who keeps its rites but doubts that the White "
    "Dawn will return."
)


def _vasha_reply() -> str:
    reply = json.loads(_probe_reply("p1", "vasha", 0))
    reply["in"] = [
        {"entry": "Velikoye", "role": "based here"},
        {
            "entry": "Church of the Eternal Light",
            "role": "parishioner",
            "exceptions": [
                {
                    "text": "She doubts that the White Dawn will ever return.",
                    "rejects": "S1",
                },
                {"text": "An exception to nothing shown.", "rejects": "S99"},
            ],
        },
    ]
    return json.dumps(reply)


async def test_character_in_rows_carry_exceptions(world, moscavia):
    client = MockClient("test")
    async with MockClientContext():
        _queue(_vasha_reply())
        preview = await preview_thing(world, "character", VASHA_PROMPT, {}, client)
    prompt = _create_prompt(client)

    # the entries it may belong in, each with what it holds, labelled
    assert (
        # a belief is told as held (ruling C33)
        "- S1: Church of the Eternal Light holds that the White Dawn will "
        "return in the fullness of time to finish the transformation of the "
        "world." in prompt
    )
    assert '"exceptions": [{"text": "One sentence.", "rejects": "S1"}]' in prompt
    church_row = next(f for f in preview.filings if f.target_id == moscavia.church)
    assert church_row.role == "parishioner"
    # the unknown label is dropped; the known one maps to the church's fact
    assert [(e.text, e.fact_id) for e in church_row.exceptions] == [
        ("She doubts that the White Dawn will ever return.", moscavia.teaches)
    ]

    church_row.ticked = True
    thing_id = accept_preview(world, preview)
    view = world.view()
    (filing,) = [f for f in filings_of(view, thing_id) if f.target == moscavia.church]
    assert filing.role == "parishioner"
    (exception_id,) = filing.exceptions
    found = view.fact(exception_id)
    assert found is not None and found[0] == thing_id
    fact = found[1]
    assert fact.category == "ties"
    assert (fact.origin or {}).get("tie") == moscavia.church
    assert (fact.origin or {}).get("rejects_fact") == moscavia.teaches
    assert "ties" not in view.thing(thing_id).fields


# --- undo ----------------------------------------------------------------------


async def test_undo_redo_accept_with_filings(world, moscavia):
    preview, _client = await _host_preview(world, moscavia)
    for rows in (preview.filings, preview.file_into, preview.move_here):
        for row in rows:
            row.ticked = True
    view = world.view()
    before = {
        thing.id: (thing.fields, sorted(f.fact_id for f in thing.facts))
        for thing in view.things()
    }

    thing_id = accept_preview(world, preview)
    rev = world.head_rev()
    assert _targets(world.view(), moscavia.talon) == [moscavia.tsardom, thing_id]

    undone = world.undo([rev])
    assert undone.conflicts == []
    view = world.view()
    after = {
        thing.id: (thing.fields, sorted(f.fact_id for f in thing.facts))
        for thing in view.things()
    }
    assert after == before

    redone = world.undo([undone.undo_rev])
    assert redone.conflicts == []
    view = world.view()
    assert view.thing(thing_id).fields.get("tag") == "regiment"
    assert _targets(view, moscavia.talon) == [moscavia.tsardom, thing_id]
    assert _targets(view, thing_id) == [moscavia.tsardom, moscavia.khorol]
    assert view.fact(moscavia.talon_fact) is None


# --- the candidate list ---------------------------------------------------------


def test_candidates_reach_siblings_and_parts_within(world, moscavia):
    """Ruling F6's list from a person filed in the Tsardom `within` the
    White Talon: the Talon (the part it's within) is one link away, and
    what's filed in the Talon (Boris) is reached as a sibling, as is what
    shares the Tsardom; the person itself never."""

    with world.revision(Source.manual(note="riders")) as rev:
        ivan = rev.create_thing(
            "character",
            {
                "name": "Ivan",
                "filings": [{"target": moscavia.tsardom, "within": moscavia.talon}],
            },
        )
        boris = rev.create_thing(
            "character", {"name": "Boris", "filings": _filed(moscavia.talon)}
        )
    view = world.view()
    found = create.filing_candidates(view, [ivan], [], {ivan})
    assert found[:2] == [moscavia.talon, moscavia.tsardom]
    assert boris in found and moscavia.frosted in found
    assert ivan not in found
    assert create.filing_candidates(view, [ivan], [], {ivan}, limit=2) == found[:2]


def test_home_exceptions_follow_a_fold(world):
    """Task 4 review, M4: an "In" row's exceptions are checked against the
    entry the filing goes to, as the revision has it. Under a fold (the
    folded stub's facts moved onto the one being filled, as `copies`, and
    the stub itself `redirect`ed), a fact item is its moved copy and a
    thing item the one it now is; one its entry no longer holds is
    dropped."""

    from talemate.worldplay.create import (
        PreviewException,
        PreviewFiling,
        _live_home_exceptions,
    )

    with world.revision(Source.manual(note="homes")) as rev:
        dawn = rev.create_thing("lore", {"name": "The White Dawn"})
        fast = rev.add_fact(dawn, "general", "The faithful fast at midwinter.")
        old = rev.add_fact(dawn, "general", "An old rule.")
        filled = rev.create_thing("lore", {"name": "The Vigil"})
        rev.set_field(filled, "filings", [{"target": dawn}], None)
        folded = rev.create_thing(
            "lore", {"name": "the vigil", "stub": {"ignored": False}}
        )
    row = PreviewFiling(
        target_id=folded,
        target_name="the vigil",
        role="believer",
        exceptions=[
            PreviewException(text="Eats at midwinter.", item="fast", fact_id="f" * 32),
            PreviewException(
                text="Skips the vigil.", item="the vigil", thing_id=folded
            ),
            PreviewException(text="Keeps no rule.", item="old", fact_id=old),
        ],
    )
    found = _live_home_exceptions(
        world.view(), row, dawn, {folded: filled}, {"f" * 32: fast}
    )
    assert [(e.text, e.fact_id, e.thing_id) for e in found] == [
        ("Eats at midwinter.", fast, None),
        ("Skips the vigil.", None, filled),
        ("Keeps no rule.", old, None),
    ]
    # checked against the row's own entry, the stub holds none of them
    assert _live_home_exceptions(world.view(), row) == []


def test_event_place_and_item_owner_are_filings(world, moscavia):
    """An event's `place` and an item's `owner` are filings, "took place
    in" and "owned by" (filing spec, "Other fields"): sent in a preview's
    fields they're filed, never written as the field."""

    event = accept_preview(
        world,
        CreatePreview(
            kind="event",
            prompt="the flood",
            name="The Great Flood",
            fields={"place": moscavia.khorol},
            facts=[PreviewFact(category="summary", text="The river rose.")],
            prose={},
        ),
    )
    item = accept_preview(
        world,
        CreatePreview(
            kind="item",
            prompt="a lantern",
            name="The Ferry Lantern",
            fields={"owner": moscavia.khorol},
            facts=[PreviewFact(category="description", text="It never goes out.")],
            prose={},
        ),
    )
    view = world.view()
    assert "place" not in view.thing(event).fields
    assert "owner" not in view.thing(item).fields
    assert [(f.target, f.role) for f in filings_of(view, event)] == [
        (moscavia.khorol, "took place in")
    ]
    assert [(f.target, f.role) for f in filings_of(view, item)] == [
        (moscavia.khorol, "owned by")
    ]
