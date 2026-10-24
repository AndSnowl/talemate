"""The draft page (mockup v2 screens 3 and 4, v3 screen C) and the menus
every page shares.

A new or expanded entry opens as its real page, marked as a draft, and
nothing is written until Accept: the draft bar (Version n of m ▾,
↻ Regenerate, Edit prompt, Discard, Accept), its "In" rows and "File into
this" (the model's unticked, ruling F7; the owner's own ticked), its
facts with a repeat's "Move that one here", "For other pages" with a
target to change and "+ also here", "Could move here", and New names. The
fact menu (⋯ or right-click: Move to…, Copy to…, Held by…, Edit, Change
dates, End this, Remove) and the selection menu (Make a stub, Make a stub
and expand now, Link to an entry…, "Ask about this" for later) work on
accepted pages and drafts alike; on a draft a selection is keyed by name
(ruling F16). A stub's Re-point gains "use the name…".

The worlds are seeded through `talemate.world` (`seed.seed_fm_world`). No
model is asked anything: drafts come from the fixed preview file, a
draft's "+ Add facts…" from the fixed facts file. What the page sends is
read back from a websocket spy.
"""

from __future__ import annotations

import re

from playwright.sync_api import expect

from e2e.seed import seed_fm_world
from e2e.worlds.test_connections_create import _opened, _search_and_pick, _wait_sent
from e2e.worlds.test_new_scene import SEND_SPY_JS, _sent
from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _fact,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)

# select `words` (the first time they're written) inside `selector`'s
# element, then right-click the selection, as the owner would
SELECT_JS = """
([element, words, nth]) => {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    let seen = 0;
    while (walker.nextNode()) {
        const node = walker.currentNode;
        let at = node.textContent.indexOf(words);
        while (at >= 0) {
            if (seen === nth) {
                const range = document.createRange();
                range.setStart(node, at);
                range.setEnd(node, at + words.length);
                const selection = window.getSelection();
                selection.removeAllRanges();
                selection.addRange(range);
                const box = range.getBoundingClientRect();
                node.parentElement.dispatchEvent(new MouseEvent('contextmenu', {
                    bubbles: true, cancelable: true, button: 2,
                    clientX: box.left + 2, clientY: box.top + 2,
                }));
                return true;
            }
            seen += 1;
            at = node.textContent.indexOf(words, at + 1);
        }
    }
    return false;
}
"""

TSARDOM = {
    "kind": "place",
    "name": "Tsardom of Moscavia",
    "fields": {"tag": "nation"},
    "facts": [{"category": "description", "text": "A cold realm of the north."}],
}

FREEZES = "The Khorol freezes solid every winter."
BELLS = "Velikoye rings its bells at dusk."
GATE = "🦉 The Ashen Gate guards the north road."

VELIKOYE = {
    "kind": "place",
    "name": "Velikoye",
    "fields": {
        "tag": "capital",
        "aka": [{"name": "the capital", "tag": "common", "everyday": True}],
    },
    "filings": [{"target": "Tsardom of Moscavia", "since": 412}],
    "facts": [
        {"category": "description", "text": FREEZES},
        {"category": "general", "text": BELLS},
        {"category": "general", "text": GATE},
    ],
}

COURT = {
    "kind": "lore",
    "name": "The Night Court",
    "fields": {"tag": "institution"},
    "facts": [{"category": "general", "text": "The nocturnal council."}],
}

TALON = {
    "kind": "lore",
    "name": "The White Talon",
    "fields": {"tag": "regiment"},
    "facts": [{"category": "general", "text": "A regiment of the north."}],
}

WORLD = [TSARDOM, VELIKOYE, COURT, TALON]

PROSE = {"description": "A host of winged soldiers."}


def _host(*facts, **extra) -> dict:
    return {
        "name": "The Frostwing Host",
        "facts": [{"category": "general", "text": text} for text in facts],
        "prose": PROSE,
        **extra,
    }


def _seeded(app, page, stem: str):
    name = _world_name(stem)
    world = seed_fm_world(app.root, name, present_year=1020, things=WORLD)
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    return world


def _draft(page, kind: str, prompt: str):
    """Describe a `kind` and Create: its draft page, once it shows."""

    page.get_by_test_id(f"kind-{kind}").click()
    box = page.get_by_test_id("create-box")
    box.wait_for(state="visible", timeout=TIMEOUT_MS)
    box.get_by_label("Describe it").fill(prompt)
    box.get_by_role("button", name="Create").click()
    draft = page.get_by_test_id("draft-page")
    draft.get_by_test_id("draft-bar").wait_for(state="visible", timeout=TIMEOUT_MS)
    return draft


def _draft_fact(draft, text: str):
    return draft.get_by_test_id("draft-fact").filter(has_text=text)


def _select(page, locator, words: str, nth: int = 0) -> None:
    locator.wait_for(state="visible", timeout=TIMEOUT_MS)
    found = page.evaluate(SELECT_JS, [locator.element_handle(), words, nth])
    assert found, f"{words!r} not found"


def test_draft_versions_and_discard(app, page, fixed_preview):
    _seeded(app, page, "Versions")
    fixed_preview(_host("It flies at night."))
    draft = _draft(page, "lore", "The Tsar's winged army.")
    bar = draft.get_by_test_id("draft-bar")
    versions = bar.get_by_test_id("draft-versions")
    expect(versions).to_contain_text("Version 1 of 1")
    assert "Nothing is written until you accept" in bar.inner_text()
    key = _sent(page, "preview_thing")[-1].get("draft_key")
    assert key is None
    night = _draft_fact(draft, "It flies at night.")
    night.get_by_role("checkbox").uncheck()

    # Regenerate: a second version of the same draft (its key sent back)
    fixed_preview(_host("It hunts by moonlight."))
    bar.get_by_role("button", name="Regenerate").click()
    expect(versions).to_contain_text("Version 2 of 2")
    _draft_fact(draft, "It hunts by moonlight.").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    sent = _sent(page, "preview_thing")[-1]
    assert sent["draft_key"] == "new:lore:frostwing host"
    expect(_draft_fact(draft, "It flies at night.")).to_have_count(0)

    # version 1 again, as the owner left it: its fact still unticked
    versions.click()
    page.get_by_test_id("draft-version").filter(has_text="v1").click()
    sent = _wait_sent(page, "use_version")
    assert (sent["draft_key"], sent["version"]) == ("new:lore:frostwing host", 1)
    expect(versions).to_contain_text("Version 1 of 2")
    night = _draft_fact(draft, "It flies at night.")
    night.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert not night.get_by_role("checkbox").is_checked()
    expect(draft.get_by_test_id("accept-counts")).to_have_text("writes 0 facts here")

    # Edit prompt: back to the box, the prompt kept; Create makes version 3
    bar.get_by_role("button", name="Edit prompt").click()
    box = page.get_by_test_id("create-box")
    prompt = box.get_by_label("Describe it")
    expect(prompt).to_have_value("The Tsar's winged army.")
    prompt.fill("The Tsar's winged army, at night.")
    fixed_preview(_host("It sleeps by day."))
    box.get_by_role("button", name="Create").click()
    expect(versions).to_contain_text("Version 3 of 3")
    sent = _sent(page, "preview_thing")[-1]
    assert sent["draft_key"] == "new:lore:frostwing host"
    assert sent["prompt"] == "The Tsar's winged army, at night."

    # Discard: the draft goes, nothing is written
    bar.get_by_test_id("draft-discard").click()
    sent = _wait_sent(page, "discard_preview")
    assert sent["draft_key"] == "new:lore:frostwing host"
    expect(page.get_by_test_id("draft-page")).to_have_count(0)
    page.get_by_test_id("create-box").wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(
        page.get_by_test_id("thing-card").filter(has_text="Frostwing")
    ).to_have_count(0)
    assert _sent(page, "accept_preview") == []
    assert page.console_errors == []


def test_draft_in_and_file_into_accept(app, page, fixed_preview):
    world = _seeded(app, page, "Filing")
    fixed_preview(
        _host(
            "The Host is entirely owl-folk.",
            tag="military",
            **{
                "in": [
                    {"entry": "Tsardom of Moscavia", "role": "the realm's army"},
                    {"entry": "Velikoye", "role": "garrisoned here"},
                ],
                "file_into": [{"entry": "The White Talon", "role": "regiment"}],
            },
        )
    )
    draft = _draft(page, "lore", "The Tsar's winged army.")

    # "In": the model's suggestions, which come unticked (ruling F7)
    filed = draft.get_by_test_id("draft-in")
    rows = filed.get_by_test_id("draft-in-row")
    expect(rows).to_have_count(2)
    tsardom = rows.filter(has_text="Tsardom of Moscavia")
    expect(tsardom.get_by_label("Role")).to_have_value("the realm's army")
    for row in rows.all():
        assert not row.get_by_role("checkbox").is_checked()
    tsardom.get_by_role("checkbox").check()

    # the owner's own "+ in…" comes ticked, with the role given
    filed.get_by_test_id("draft-in-add").click()
    _search_and_pick(page, "night", "The Night Court")
    court = rows.filter(has_text="The Night Court")
    court.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert court.get_by_role("checkbox").is_checked()
    court.get_by_label("Role").fill("answers to")

    # "File into this": unticked too
    into = draft.get_by_test_id("draft-file-into")
    talon = into.get_by_test_id("file-into-row").filter(has_text="The White Talon")
    assert not talon.get_by_role("checkbox").is_checked()
    talon.get_by_role("checkbox").check()

    draft.get_by_role("button", name="Accept").click()
    host = _opened(page, "The Frostwing Host")
    accepted = _sent(page, "accept_preview")[-1]
    assert accepted["draft_key"] == "new:lore:frostwing host"
    filings = [
        (row["target_id"], row["ticked"], row["role"])
        for row in accepted["preview"]["filings"]
    ]
    assert filings == [
        (world.things["Tsardom of Moscavia"], True, "the realm's army"),
        (world.things["Velikoye"], False, "garrisoned here"),
        (world.things["The Night Court"], True, "answers to"),
    ]
    assert [(r["thing_id"], r["ticked"]) for r in accepted["preview"]["file_into"]] == [
        (world.things["The White Talon"], True)
    ]

    # written: the ticked rows only, and the Talon filed into it
    in_rows = host.get_by_test_id("entry-in").get_by_test_id("in-row")
    expect(in_rows).to_have_count(2)
    expect(in_rows.filter(has_text="Velikoye")).to_have_count(0)
    assert "answers to" in in_rows.filter(has_text="The Night Court").inner_text()
    page.get_by_test_id("kind-lore").click()
    talon_page = _open_thing(page, "The White Talon")
    expect(
        talon_page.get_by_test_id("entry-in").get_by_test_id("in-row")
    ).to_contain_text(["The Frostwing Host"])
    assert page.console_errors == []


def test_repeat_move_that_one_here(app, page, fixed_preview):
    world = _seeded(app, page, "Repeats")
    velikoye = world.things["Velikoye"]

    def repeat_of(text):
        return {
            "fact_id": world.facts[text],
            "owner_id": velikoye,
            "owner_name": "Velikoye",
            "text": text,
            "score": 0.8,
        }

    fixed_preview(
        {
            "name": "Khorol Ice Road",
            "facts": [
                {"category": "description", "text": "Carts cross the ice in winter."},
                {
                    "category": "description",
                    "text": "The Khorol freezes from November to April.",
                    "ticked": False,
                    "repeat_of": repeat_of(FREEZES),
                },
                {
                    "category": "description",
                    "text": "Bells ring over the ice at dusk.",
                    "ticked": False,
                    "repeat_of": repeat_of(BELLS),
                },
            ],
            "prose": {"description": "The winter road."},
        }
    )
    draft = _draft(page, "place", "The road over the frozen river.")
    counts = draft.get_by_test_id("accept-counts")
    expect(counts).to_have_text("writes 1 fact here")

    # a repeat shows its match, with three ways to settle it
    freeze = _draft_fact(draft, "November to April")
    match = freeze.get_by_test_id("fact-match")
    assert "≈ already on Velikoye" in match.inner_text()
    assert FREEZES in match.inner_text()
    assert not freeze.get_by_role("checkbox").is_checked()

    bells = _draft_fact(draft, "Bells ring")
    bells.get_by_role("button", name="Keep both").click()
    assert bells.get_by_role("checkbox").is_checked()
    expect(counts).to_have_text("writes 2 facts here")
    bells.get_by_role("button", name="Drop this").click()
    assert not bells.get_by_role("checkbox").is_checked()

    freeze.get_by_role("button", name="Move that one here").click()
    expect(freeze.get_by_test_id("fact-match")).to_contain_text("moves here")
    assert not freeze.get_by_role("checkbox").is_checked()
    expect(counts).to_have_text("writes 1 fact here, moves 1 in")

    draft.get_by_role("button", name="Accept").click()
    road = _opened(page, "Khorol Ice Road")
    accepted = _sent(page, "accept_preview")[-1]["preview"]
    assert [f["ticked"] for f in accepted["facts"]] == [True, False, False]
    moves = [r for r in accepted["move_here"] if r.get("repeat")]
    assert [(r["fact_id"], r["from_id"], r["ticked"]) for r in moves] == [
        (world.facts[FREEZES], velikoye, True)
    ]

    # Velikoye's fact moved here; the draft's own copy wasn't written
    _fact(road, FREEZES).wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(_fact(road, "November to April")).to_have_count(0)
    page.get_by_test_id("kind-place").click()
    vel = _open_thing(page, "Velikoye")
    expect(_fact(vel, FREEZES)).to_have_count(0)
    _fact(vel, BELLS).wait_for(state="visible", timeout=TIMEOUT_MS)
    assert page.console_errors == []


ON_VELIKOYE = "Velikoye closes its bridges in spring."
ON_TSARDOM = "The Tsardom pays the Host in silver."


def test_retarget_other_page_and_also_here(app, page, fixed_preview):
    world = _seeded(app, page, "Elsewhere")
    fixed_preview(
        _host(
            "The Host is entirely owl-folk.",
            elsewhere=[
                {"entry": "Velikoye", "text": ON_VELIKOYE},
                {"entry": "Tsardom of Moscavia", "text": ON_TSARDOM},
            ],
        )
    )
    draft = _draft(page, "lore", "The Tsar's winged army.")
    other = draft.get_by_test_id("preview-elsewhere")
    assert "for other pages" in other.inner_text().lower()

    # its target is changed: the row goes with the entry picked
    bridges = other.get_by_test_id("elsewhere-row").filter(has_text=ON_VELIKOYE)
    bridges.get_by_test_id("elsewhere-target").click()
    _search_and_pick(page, "night", "The Night Court")
    expect(other.get_by_test_id("elsewhere-entry")).to_have_text(
        ["The Night Court", "Tsardom of Moscavia"]
    )
    court = other.get_by_test_id("elsewhere-group").filter(has_text="The Night Court")
    expect(court.get_by_test_id("elsewhere-row")).to_contain_text([ON_VELIKOYE])

    # "+ also here": the Tsardom's fact is one of this page's too
    silver = other.get_by_test_id("elsewhere-row").filter(has_text=ON_TSARDOM)
    silver.get_by_test_id("elsewhere-also").click()
    own = _draft_fact(draft, ON_TSARDOM)
    own.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert own.get_by_role("checkbox").is_checked()
    expect(draft.get_by_test_id("accept-counts")).to_have_text(
        "writes 2 facts here, 2 elsewhere"
    )

    draft.get_by_role("button", name="Accept").click()
    host = _opened(page, "The Frostwing Host")
    accepted = _sent(page, "accept_preview")[-1]["preview"]
    assert [(e["target_id"], e["text"]) for e in accepted["elsewhere"]] == [
        (world.things["The Night Court"], ON_VELIKOYE),
        (world.things["Tsardom of Moscavia"], ON_TSARDOM),
    ]
    _fact(host, ON_TSARDOM).wait_for(state="visible", timeout=TIMEOUT_MS)

    page.get_by_test_id("kind-lore").click()
    court_page = _open_thing(page, "The Night Court")
    _fact(court_page, ON_VELIKOYE).wait_for(state="visible", timeout=TIMEOUT_MS)
    page.get_by_test_id("kind-place").click()
    vel = _open_thing(page, "Velikoye")
    expect(_fact(vel, ON_VELIKOYE)).to_have_count(0)
    page.get_by_test_id("kind-place").click()
    tsardom = _open_thing(page, "Tsardom of Moscavia")
    _fact(tsardom, ON_TSARDOM).wait_for(state="visible", timeout=TIMEOUT_MS)
    assert page.console_errors == []


PATROL = (
    "Riders of the Pale Wing guard the north pass, and the Pale Wing answers"
    " to the Tsar."
)


def test_selection_make_stub_and_link(app, page, fixed_preview):
    world = _seeded(app, page, "Words")
    velikoye = world.things["Velikoye"]
    page.get_by_test_id("kind-place").click()
    vel = _open_thing(page, "Velikoye")

    # on an accepted page: the words' UTF-16 offsets (the owl is two units)
    gate = _fact(vel, "Ashen Gate")
    _select(page, gate, "Ashen Gate")
    menu = page.get_by_test_id("selection-menu")
    menu.wait_for(state="visible", timeout=TIMEOUT_MS)
    ask = menu.get_by_test_id("selection-ask")
    assert "later" in ask.inner_text()
    expect(ask).to_have_class(re.compile(r"v-list-item--disabled"))
    assert menu.get_by_test_id("selection-draft-note").count() == 0
    menu.get_by_test_id("selection-kind").locator(".v-field").click()
    page.get_by_role("option", name="place", exact=True).click()
    menu.get_by_test_id("selection-stub").click()
    sent = _wait_sent(page, "make_stub_from_text")
    assert (sent["fact_id"], sent["start"], sent["end"], sent["kind"]) == (
        world.facts[GATE],
        7,
        17,
        "place",
    )
    _fact(vel, "Ashen Gate").get_by_test_id("linked-stub").filter(
        has_text="Ashen Gate"
    ).wait_for(state="visible", timeout=TIMEOUT_MS)

    # Link to an entry…
    _select(page, _fact(vel, "north road"), "north road")
    page.get_by_test_id("selection-menu").get_by_test_id("selection-link").click()
    _search_and_pick(page, "tsar", "Tsardom of Moscavia")
    sent = _wait_sent(page, "link_text")
    assert (sent["start"], sent["end"]) == (29, 39)
    assert sent["target_id"] == world.things["Tsardom of Moscavia"]
    _fact(vel, "north road").get_by_test_id("linked-ref").filter(
        has_text="north road"
    ).wait_for(state="visible", timeout=TIMEOUT_MS)

    # Make a stub and expand now: its kind's box opens from the new stub
    _select(page, _fact(vel, BELLS), "bells")
    menu = page.get_by_test_id("selection-menu")
    menu.get_by_test_id("selection-kind").locator(".v-field").click()
    page.get_by_role("option", name="item", exact=True).click()
    menu.get_by_test_id("selection-expand").click()
    box = page.get_by_test_id("create-box")
    box.get_by_test_id("from-stub").filter(has_text="bells").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )

    # on a draft: keyed by name, so every "Pale Wing" goes (ruling F16)
    fixed_preview(_host(PATROL))
    draft = _draft(page, "lore", "The Tsar's winged army.")
    patrol = _draft_fact(draft, "Riders of the")
    _select(page, patrol, "Pale Wing")
    menu = page.get_by_test_id("selection-menu")
    menu.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "every" in menu.get_by_test_id("selection-draft-note").inner_text()
    menu.get_by_test_id("selection-stub").click()
    sent = _wait_sent(page, "make_stub_from_text")
    assert sent["draft_key"] == "new:lore:frostwing host"
    assert (sent["index"], sent["start"], sent["end"]) == (0, 14, 23)
    expect(patrol.get_by_test_id("linked-new")).to_have_count(2)
    names = draft.get_by_test_id("draft-new-names")
    expect(names.get_by_test_id("new-name-row")).to_contain_text(["Pale Wing"])
    rename = names.get_by_test_id("new-name-rename").first
    assert "later" in rename.inner_text().lower()
    assert rename.is_disabled()

    _select(page, patrol, "the north pass")
    page.get_by_test_id("selection-menu").get_by_test_id("selection-link").click()
    _search_and_pick(page, "veli", "Velikoye")
    sent = _wait_sent(page, "link_text")
    assert sent["draft_key"] == "new:lore:frostwing host"
    assert sent["target_id"] == velikoye
    patrol.get_by_test_id("linked-ref").filter(has_text="the north pass").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )

    draft.get_by_role("button", name="Accept").click()
    host = _opened(page, "The Frostwing Host")
    row = _fact(host, "Riders of the")
    expect(row.get_by_test_id("linked-stub")).to_have_count(2)
    expect(row.get_by_test_id("linked-ref")).to_have_text(["the north pass"])
    assert page.console_errors == []


def test_fact_move_and_copy(app, page, fixed_preview):
    world = _seeded(app, page, "Menus")
    page.get_by_test_id("kind-place").click()
    vel = _open_thing(page, "Velikoye")

    # ⋯ opens the fact menu; so does a right-click on the row
    bells = _fact(vel, BELLS)
    bells.get_by_test_id("fact-menu-button").click()
    menu = page.get_by_test_id("fact-menu")
    menu.wait_for(state="visible", timeout=TIMEOUT_MS)
    for item in [
        "Move to…",
        "Copy to…",
        "Held by…",
        "Edit",
        "Change dates",
        "End this",
        "Remove",
        "Cut",
        "Copy",
        "Paste",
        "Select all",
        "Undo",
        "Redo",
    ]:
        expect(menu.get_by_role("menuitem", name=item, exact=True)).to_have_count(1)
    assert "Spell check" in menu.inner_text()
    page.keyboard.press("Escape")
    expect(page.get_by_test_id("fact-menu")).to_have_count(0)
    bells.locator(".fact-date").click(button="right")
    menu = page.get_by_test_id("fact-menu")
    menu.wait_for(state="visible", timeout=TIMEOUT_MS)

    # Copy to…: it stays here, and the Tsardom has it too
    menu.get_by_test_id("fact-copy").click()
    _pick_in(page, page.get_by_test_id("copy-target"), "Tsardom of Moscavia")
    page.get_by_test_id("fact-copy-menu").get_by_role("button", name="Copy").click()
    sent = _wait_sent(page, "copy_fact")
    assert (sent["fact_id"], sent["target_id"]) == (
        world.facts[BELLS],
        world.things["Tsardom of Moscavia"],
    )
    expect(page.get_by_test_id("accept-notes")).to_contain_text(
        "Copied to Tsardom of Moscavia"
    )
    _fact(vel, BELLS).wait_for(state="visible", timeout=TIMEOUT_MS)

    # Move to…: it leaves this page
    _fact(vel, FREEZES).get_by_test_id("fact-menu-button").click()
    page.get_by_test_id("fact-menu").get_by_test_id("fact-move").click()
    _pick_in(page, page.get_by_test_id("move-target"), "The Night Court")
    page.get_by_test_id("fact-move-menu").get_by_role("button", name="Move").click()
    sent = _wait_sent(page, "move_fact")
    assert sent["target_id"] == world.things["The Night Court"]
    expect(_fact(vel, FREEZES)).to_have_count(0)

    page.get_by_test_id("kind-place").click()
    tsardom = _open_thing(page, "Tsardom of Moscavia")
    _fact(tsardom, BELLS).wait_for(state="visible", timeout=TIMEOUT_MS)
    page.get_by_test_id("kind-lore").click()
    court = _open_thing(page, "The Night Court")
    _fact(court, FREEZES).wait_for(state="visible", timeout=TIMEOUT_MS)

    # on a draft the same menu: Move to… makes it a fact for that page
    fixed_preview(_host("It flies at night.", "The Night Court pays its riders."))
    draft = _draft(page, "lore", "The Tsar's winged army.")
    pays = _draft_fact(draft, "pays its riders")
    pays.get_by_test_id("fact-menu-button").click()
    page.get_by_test_id("fact-menu").get_by_test_id("fact-move").click()
    _pick_in(page, page.get_by_test_id("move-target"), "The Night Court")
    page.get_by_test_id("fact-move-menu").get_by_role("button", name="Move").click()
    expect(_draft_fact(draft, "pays its riders")).to_have_count(0)
    other = draft.get_by_test_id("preview-elsewhere")
    expect(
        other.get_by_test_id("elsewhere-group").filter(has_text="The Night Court")
    ).to_contain_text("pays its riders")
    expect(draft.get_by_test_id("accept-counts")).to_have_text(
        "writes 1 fact here, 1 elsewhere"
    )
    assert _sent(page, "move_fact")[-1]["target_id"] == world.things["The Night Court"]
    assert len(_sent(page, "move_fact")) == 1
    assert page.console_errors == []


def _pick_in(page, field, option: str) -> None:
    field.locator(".v-field").click()
    page.get_by_role("option", name=option).first.click()


STUB = {"kind": "place", "name": "the Old Capital", "stub": "live"}

OWL = {
    "kind": "species",
    "name": "Owl-folk",
    "facts": [
        {
            "category": "origin",
            "text": "First hatched in [[@the Old Capital|the Old Capital]].",
        },
        {
            "category": "general",
            "text": "They still roost in [[@the Old Capital|the old capital]].",
        },
    ],
}


def test_hard_repoint(app, page):
    name = _world_name("Repoint")
    world = seed_fm_world(app.root, name, present_year=1020, things=[*WORLD, STUB, OWL])
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)

    # the stub's own card offers it too
    page.get_by_test_id("stub-item").filter(has_text="the Old Capital").click()
    stub_page = _opened(page, "the Old Capital")
    expect(stub_page.get_by_test_id("stub-repoint-name")).to_have_count(1)

    # the Stubs page: "use the name…", one of the target's names for every
    # link's words
    page.get_by_test_id("kind-stubs").click()
    tab = page.get_by_test_id("stubs-tab")
    row = tab.get_by_test_id("stub-row").filter(has_text="the Old Capital")
    row.get_by_test_id("stub-repoint-name").click()
    _search_and_pick(page, "veli", "Velikoye")
    names = page.get_by_test_id("repoint-names")
    names.wait_for(state="visible", timeout=TIMEOUT_MS)
    options = names.get_by_test_id("repoint-name-option")
    expect(options).to_have_text(["Velikoye", "the capital"])
    options.filter(has_text="the capital").click()
    sent = _wait_sent(page, "repoint_stub")
    assert sent == {
        "type": "worlds",
        "action": "repoint_stub",
        "stub_id": world.things["the Old Capital"],
        "target_id": world.things["Velikoye"],
        "use_name": "the capital",
    }
    tab.get_by_test_id("stub-repointed").wait_for(state="visible", timeout=TIMEOUT_MS)

    # every link's words are now that name
    page.get_by_test_id("kind-species").click()
    owl = _open_thing(page, "Owl-folk")
    for text in ["First hatched", "still roost"]:
        expect(_fact(owl, text).get_by_test_id("linked-ref")).to_have_text(
            ["the capital"]
        )
    assert page.console_errors == []
