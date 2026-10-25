"""The draft page (mockup v2 screens 3 and 4, v3 screen C) and the menus
every page shares.

A new or expanded entry opens as its real page, marked as a draft, and
nothing is written until Accept: the draft bar (its prompt, always on
screen and editable; Version n of m ▾, ↻ Regenerate, Discard, Accept),
its "In" rows and "File into
this" (the model's unticked, ruling F7; the owner's own ticked), its
facts (linked as accept will link them, P6) with a repeat's four choices
(Keep new, Keep existing, Keep both, Move existing here, P8), "For other
pages" with a target to change and "+ also here", "Could move here", and
New names. The
fact menu (⋯ or right-click: Move to…, Copy to…, Held by…, Edit, Change
dates, End this, Remove) and the selection menu (Make a stub, Make a stub
and expand now, Link to an entry…, "Ask about this" for later) work on
accepted pages and drafts alike; on a draft a selection is keyed by name
(ruling F16). Re-pointing and linking choose how the words go (P4): another
name of the entry, or renamed to one of its names.

The worlds are seeded through `talemate.world` (`seed.seed_fm_world`). No
model is asked anything: drafts come from the fixed preview file, a
draft's "+ Add facts…" from the fixed facts file. What the page sends is
read back from a websocket spy.
"""

from __future__ import annotations

import re

from playwright.sync_api import expect

from talemate.world.dates import WorldDate

from e2e.seed import seed_fm_world
from e2e.worlds.test_connections_create import (
    _choose_mode,
    _opened,
    _search_and_pick,
    _wait_sent,
)
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


def test_header_lists_the_other_names_and_a_draft_drops_one(app, page, fixed_preview):
    """Final review M8: the header lists the other names, on a draft and
    on the accepted page; on the draft one can be removed before accept
    (accepted, an other name becomes a link word)."""

    _seeded(app, page, "Names")
    fixed_preview(
        _host(
            "It flies at night.",
            aka=[
                {"name": "the Frostwings", "tag": "common", "everyday": False},
                {"name": "the Winged", "tag": "common", "everyday": False},
            ],
        )
    )
    draft = _draft(page, "lore", "The Tsar's winged army.")
    names = draft.get_by_test_id("thing-other-name")
    expect(names).to_have_count(2)
    expect(draft.get_by_test_id("thing-other-names")).to_contain_text("the Winged")
    draft.get_by_role("button", name="Remove other name the Winged").click()
    expect(names).to_have_count(1)
    draft.get_by_role("button", name="Accept").click()
    sent = _wait_sent(page, "accept_preview")
    assert [entry["name"] for entry in sent["preview"]["aka"]] == ["the Frostwings"]
    thing = page.get_by_test_id("thing-page")
    thing.get_by_test_id("thing-name").filter(has_text="The Frostwing Host").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    expect(thing.get_by_test_id("thing-other-name")).to_have_text(["the Frostwings"])


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

    # the bar holds the prompt, editable directly; Regenerate makes version 3
    assert bar.get_by_role("button", name="Edit prompt").count() == 0
    prompt = bar.get_by_test_id("draft-prompt").locator("textarea").first
    expect(prompt).to_have_value("The Tsar's winged army.")
    prompt.fill("The Tsar's winged army, at night.")
    fixed_preview(_host("It sleeps by day."))
    bar.get_by_role("button", name="Regenerate").click()
    expect(versions).to_contain_text("Version 3 of 3")
    sent = _sent(page, "preview_thing")[-1]
    assert sent["draft_key"] == "new:lore:frostwing host"
    assert sent["prompt"] == "The Tsar's winged army, at night."

    # Discard: the draft goes, nothing is written; the create box's form
    # comes back with the (edited) prompt as it was left in the bar
    bar.get_by_test_id("draft-discard").click()
    sent = _wait_sent(page, "discard_preview")
    assert sent["draft_key"] == "new:lore:frostwing host"
    expect(page.get_by_test_id("draft-page")).to_have_count(0)
    box = page.get_by_test_id("create-box")
    box.wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(box.get_by_label("Describe it")).to_have_value(
        "The Tsar's winged army, at night."
    )
    expect(
        page.get_by_test_id("thing-card").filter(has_text="Frostwing")
    ).to_have_count(0)
    assert _sent(page, "accept_preview") == []
    assert page.console_errors == []


def test_draft_prompt_in_bar_regenerates(app, page, fixed_preview):
    """The page draft's bar holds its prompt directly (no "Edit prompt",
    no separate box to swap to): editing it there and clicking Regenerate
    sends the edited prompt back with the draft's key."""

    _seeded(app, page, "PromptInBar")
    fixed_preview(_host("It flies at night."))
    draft = _draft(page, "lore", "The Tsar's winged army.")
    bar = draft.get_by_test_id("draft-bar")
    versions = bar.get_by_test_id("draft-versions")
    expect(versions).to_contain_text("Version 1 of 1")

    prompt = bar.get_by_test_id("draft-prompt").locator("textarea").first
    expect(prompt).to_have_value("The Tsar's winged army.")
    assert bar.get_by_role("button", name="Edit prompt").count() == 0

    prompt.fill("The Tsar's winged army, at dusk.")
    fixed_preview(_host("It hunts by moonlight."))
    bar.get_by_role("button", name="Regenerate").click()
    sent = _wait_sent(page, "preview_thing")
    assert sent["draft_key"] == "new:lore:frostwing host"
    assert sent["prompt"] == "The Tsar's winged army, at dusk."
    expect(versions).to_contain_text("Version 2 of 2")
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

    # "In" (the page's own, in its draft mode): the model's suggestions,
    # which come unticked (ruling F7)
    filed = draft.get_by_test_id("draft-in")
    rows = filed.get_by_test_id("draft-in-row")
    expect(rows).to_have_count(2)
    tsardom = rows.filter(has_text="Tsardom of Moscavia")
    # read the entry's way: "<Role> of <Target>"
    expect(tsardom.get_by_test_id("in-role-text")).to_have_text("The realm's army of")
    for row in rows.all():
        assert not row.get_by_role("checkbox").is_checked()
    tsardom.get_by_role("checkbox").check()

    # the owner's own "+ in…" comes ticked, with the role given, as on a page
    filed.get_by_test_id("in-add").click()
    form = filed.get_by_test_id("in-add-form")
    form.get_by_test_id("in-target").locator("input").fill("Night Court")
    page.get_by_role("option", name="The Night Court").click()
    form.get_by_label("Role (optional)").fill("answers")
    form.get_by_role("button", name="File it").click()
    court = rows.filter(has_text="The Night Court")
    court.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert court.get_by_role("checkbox").is_checked()
    # and its role edited as a page's is
    court.get_by_test_id("in-edit").click()
    edit = filed.get_by_test_id("in-edit-form")
    edit.get_by_label("Role").fill("answers to")
    edit.get_by_role("button", name="Save").click()
    expect(court.get_by_test_id("in-role-text")).to_have_text("Answers to")

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
    assert "Answers to" in in_rows.filter(has_text="The Night Court").inner_text()
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

    # a repeat shows its match, with four ways to settle it
    freeze = _draft_fact(draft, "November to April")
    match = freeze.get_by_test_id("fact-match")
    assert "≈ already on Velikoye" in match.inner_text()
    assert FREEZES in match.inner_text()
    assert not freeze.get_by_role("checkbox").is_checked()

    bells = _draft_fact(draft, "Bells ring")
    bells.get_by_role("button", name="Keep both").click()
    assert bells.get_by_role("checkbox").is_checked()
    expect(counts).to_have_text("writes 2 facts here")
    bells.get_by_role("button", name="Keep existing").click()
    assert not bells.get_by_role("checkbox").is_checked()

    freeze.get_by_role("button", name="Move existing here").click()
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
    # ruling H2: plain words aren't a name, so they link only
    _choose_mode(page, default="link")
    sent = _wait_sent(page, "link_text")
    assert (sent["start"], sent["end"]) == (29, 39)
    assert sent["target_id"] == world.things["Tsardom of Moscavia"]
    assert sent["mode"] == "link"
    _fact(vel, "north road").get_by_test_id("linked-ref").filter(
        has_text="north road"
    ).wait_for(state="visible", timeout=TIMEOUT_MS)
    # and the Tsardom doesn't go by "north road"
    page.get_by_test_id("kind-place").click()
    tsardom = _open_thing(page, "Tsardom of Moscavia")
    expect(tsardom.get_by_test_id("thing-other-names")).to_have_count(0)
    page.get_by_test_id("kind-place").click()
    vel = _open_thing(page, "Velikoye")

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
    # on a draft, renaming waits for the accept
    chooser = page.get_by_test_id("name-mode")
    chooser.wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(chooser.get_by_test_id("mode-rename-later")).to_have_count(1)
    expect(chooser.get_by_test_id("mode-rename-option")).to_have_count(0)
    _choose_mode(page, default="link")
    sent = _wait_sent(page, "link_text")
    assert sent["mode"] == "link"
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

    # Remove on a draft fact: gone from the draft, nothing sent
    _draft_fact(draft, "It flies at night.").get_by_test_id("fact-menu-button").click()
    page.get_by_test_id("fact-menu").get_by_test_id("fact-remove").click()
    expect(_draft_fact(draft, "It flies at night.")).to_have_count(0)
    expect(draft.get_by_test_id("fact-form")).to_have_count(0)
    expect(draft.get_by_test_id("accept-counts")).to_have_text(
        "writes 0 facts here, 1 elsewhere"
    )
    assert _sent(page, "remove_fact") == []
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
    expect(stub_page.get_by_test_id("stub-repoint")).to_have_count(1)

    # the Stubs page: "Rename to…", one of the target's names for every
    # link's words
    page.get_by_test_id("kind-stubs").click()
    tab = page.get_by_test_id("stubs-tab")
    row = tab.get_by_test_id("stub-row").filter(has_text="the Old Capital")
    row.get_by_test_id("stub-repoint").click()
    _search_and_pick(page, "veli", "Velikoye")
    chooser = page.get_by_test_id("name-mode")
    chooser.wait_for(state="visible", timeout=TIMEOUT_MS)
    options = chooser.get_by_test_id("mode-rename-option")
    expect(options).to_have_text(["Velikoye", "the capital"])
    _choose_mode(page, rename_to="the capital", default="name")
    sent = _wait_sent(page, "repoint_stub")
    assert sent == {
        "type": "worlds",
        "action": "repoint_stub",
        "stub_id": world.things["the Old Capital"],
        "target_id": world.things["Velikoye"],
        "mode": "rename",
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


GENERAL = "It flies at night."


def test_draft_in_new_name_and_kind(app, page, fixed_preview):
    """ "+ in…" on a draft makes a stub of a typed name, as on a page; the
    draft's kind can be changed, its facts' categories following."""

    _seeded(app, page, "Kinds")
    fixed_preview(_host(GENERAL))
    draft = _draft(page, "lore", "The Tsar's winged army.")
    filed = draft.get_by_test_id("draft-in")
    filed.get_by_test_id("in-add").click()
    form = filed.get_by_test_id("in-add-form")
    form.get_by_test_id("in-target").locator("input").fill("The Owl Legion")
    page.get_by_role("option", name="Make a stub “The Owl Legion”").click()
    form.get_by_test_id("in-new-tag").locator("input").fill("Army")
    form.get_by_role("button", name="File it").click()
    legion = filed.get_by_test_id("draft-in-row").filter(has_text="The Owl Legion")
    legion.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert legion.get_by_role("checkbox").is_checked()
    assert "new stub" in legion.inner_text()

    # a character, not lore: "general" becomes a character's category
    fact = _draft_fact(draft, GENERAL)
    expect(fact.locator(".v-chip")).to_have_text("general")
    draft.get_by_test_id("draft-kind").locator(".v-field").click()
    page.get_by_role("option", name="character", exact=True).click()
    expect(fact.locator(".v-chip")).to_have_text("appearance")

    draft.get_by_role("button", name="Accept").click()
    host = _opened(page, "The Frostwing Host")
    accepted = _sent(page, "accept_preview")[-1]["preview"]
    assert accepted["kind"] == "character"
    assert [f["category"] for f in accepted["facts"]] == ["appearance"]
    (row,) = [r for r in accepted["filings"] if r.get("new_name")]
    assert row["new_name"] == {"name": "The Owl Legion", "kind": "lore", "tag": "army"}
    assert row["ticked"] is True
    expect(host.get_by_test_id("thing-kind")).to_have_text("character")
    expect(host.get_by_test_id("entry-in").get_by_test_id("in-row")).to_contain_text(
        ["The Owl Legion"]
    )
    page.get_by_test_id("stub-item").filter(has_text="The Owl Legion").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert page.console_errors == []


ROW = {"kind": "place", "name": "Wattle Row", "stub": "live"}
WATTLERS = {
    "kind": "lore",
    "name": "The Wattlers' Guild",
    "fields": {"tag": "guild"},
    "filings": [{"target": "Wattle Row", "role": "meets in"}],
    "facts": [{"category": "general", "text": "The wattlemakers' guild."}],
}
NAMER = {
    "kind": "place",
    "name": "Old Market",
    "facts": [{"category": "general", "text": "Next to [[@Wattle Row|Wattle Row]]."}],
}


def test_stub_draft_shows_connected_and_mentioned(app, page, fixed_preview):
    """A stub's draft is its page: what's filed in it (Connected) and what
    names it (Mentioned in) show, read-only, before anything is written."""

    name = _world_name("Wattle")
    seed_fm_world(app.root, name, present_year=1020, things=[ROW, WATTLERS, NAMER])
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("stub-item").filter(has_text="Wattle Row").click()
    stub = _opened(page, "Wattle Row")
    stub.get_by_test_id("stub-panel").get_by_role("button", name="Expand").click()
    box = page.get_by_test_id("create-box")
    box.get_by_test_id("from-stub").wait_for(state="visible", timeout=TIMEOUT_MS)
    fixed_preview(
        {
            "name": "Wattle Row",
            "facts": [{"category": "description", "text": "A street of wattlemakers."}],
            "prose": {"description": "A street."},
        }
    )
    box.get_by_role("button", name="Create").click()
    draft = page.get_by_test_id("draft-page")
    connected = draft.get_by_test_id("entry-connected")
    expect(connected.get_by_test_id("connected-row")).to_contain_text(
        ["The Wattlers' Guild"]
    )
    expect(connected.get_by_test_id("connected-add")).to_have_count(0)
    expect(connected.get_by_test_id("group-synopsis-button")).to_have_count(0)
    expect(connected.get_by_test_id("group-add-button")).to_have_count(0)
    expect(connected.get_by_test_id("connected-move")).to_have_count(0)
    mentioned = draft.get_by_test_id("entry-mentioned")
    mentioned.get_by_test_id("mentioned-toggle").click()
    expect(mentioned.get_by_test_id("mentioned-row")).to_contain_text(["Old Market"])
    assert page.console_errors == []


def test_draft_fact_end_and_dates(app, page, fixed_preview):
    """ "End this" and "Change dates" on a draft fact (its since and until,
    written on accept); on a page, Change dates opens a dates-only form."""

    _seeded(app, page, "Dates")
    page.get_by_test_id("kind-place").click()
    vel = _open_thing(page, "Velikoye")
    _fact(vel, BELLS).get_by_test_id("fact-menu-button").click()
    page.get_by_test_id("fact-menu").get_by_test_id("fact-dates").click()
    form = vel.get_by_test_id("fact-form")
    form.wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(form.get_by_label("Fact", exact=True)).to_have_count(0)
    form.get_by_label("From year").fill("990")
    form.get_by_role("button", name="Save").click()
    sent = _wait_sent(page, "correct_fact")
    assert set(sent) >= {"valid_from"} and "text" not in sent
    expect(_fact(vel, BELLS)).to_contain_text("990")

    fixed_preview(_host(GENERAL))
    draft = _draft(page, "lore", "The Tsar's winged army.")
    fact = _draft_fact(draft, GENERAL)
    fact.get_by_test_id("fact-menu-button").click()
    page.get_by_test_id("fact-menu").get_by_test_id("fact-dates").click()
    form = draft.get_by_test_id("fact-form")
    form.get_by_label("From year").fill("990")
    form.get_by_role("button", name="Save").click()
    fact.get_by_test_id("fact-menu-button").click()
    page.get_by_test_id("fact-menu").get_by_test_id("fact-end").click()
    form = draft.get_by_test_id("fact-form")
    form.get_by_label("Until year").fill("1010")
    form.get_by_role("button", name="End").click()
    expect(fact).to_contain_text("990")
    expect(fact).to_contain_text("1010")
    draft.get_by_role("button", name="Accept").click()
    _opened(page, "The Frostwing Host")
    (written,) = _sent(page, "accept_preview")[-1]["preview"]["facts"]
    assert written["since"]["instant"] < written["until"]["instant"]
    assert page.console_errors == []


def test_create_another_kind_asks_first(app, page, fixed_preview):
    """Creating in another kind's box while a draft is open asks before
    discarding it."""

    _seeded(app, page, "Ask")
    fixed_preview(_host(GENERAL))
    _draft(page, "lore", "The Tsar's winged army.")
    page.get_by_test_id("kind-place").click()
    box = page.get_by_test_id("create-box")
    box.get_by_label("Describe it").fill("A ford on the Khorol.")
    box.get_by_role("button", name="Create").click()
    ask = page.get_by_test_id("discard-ask")
    ask.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "The Frostwing Host" in ask.inner_text()
    ask.get_by_role("button", name="Keep the draft").click()
    ask.wait_for(state="hidden", timeout=TIMEOUT_MS)
    assert _sent(page, "discard_preview") == []
    page.get_by_test_id("kind-lore").click()
    page.get_by_test_id("draft-page").wait_for(state="visible", timeout=TIMEOUT_MS)

    page.get_by_test_id("kind-place").click()
    box.get_by_label("Describe it").fill("A ford on the Khorol.")
    box.get_by_role("button", name="Create").click()
    page.get_by_test_id("discard-ask").get_by_role(
        "button", name="Discard and create"
    ).click()
    assert _wait_sent(page, "discard_preview")["draft_key"] == "new:lore:frostwing host"
    _wait_sent(page, "preview_thing")
    page.get_by_test_id("draft-page").get_by_test_id("draft-bar").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert _sent(page, "preview_thing")[-1]["kind"] == "place"
    assert page.console_errors == []


MARSH = {
    "kind": "place",
    "name": "Owl Marsh",
    "facts": [
        {
            "category": "general",
            "text": "Pure-line Moscavians nest by [[@The Night Court|the court]].",
        },
        {"category": "general", "text": "Herons fish at [[@Old Weir|the weir]]."},
    ],
}

WEIR = {"kind": "place", "name": "Old Weir", "stub": "live"}


def test_repoint_mode_picker(app, page):
    """P4 and ruling H2: once a link's target is picked, the owner chooses
    how it takes the words -- "Link only", "Add as another name" or
    "Rename to…" one of its names -- on a selection's "Link to an entry…"
    and a link card's "Re-point…" alike. "Add as another name" is the
    default for words that look like a proper name and for a stub's link
    (whose "Link only" warns the name is lost); other words default to
    "Link only"."""

    name = _world_name("Modes")
    world = seed_fm_world(
        app.root, name, present_year=1020, things=[*WORLD, WEIR, MARSH]
    )
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-place").click()
    marsh = _open_thing(page, "Owl Marsh")

    # plain words linked: the default teaches the entry them
    _select(page, _fact(marsh, "nest by"), "Pure-line Moscavians")
    page.get_by_test_id("selection-menu").get_by_test_id("selection-link").click()
    _search_and_pick(page, "tsar", "Tsardom of Moscavia")
    chooser = page.get_by_test_id("name-mode")
    chooser.wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(chooser.get_by_test_id("mode-add-name")).to_contain_text(
        "Add “Pure-line Moscavians” as another name"
    )
    expect(chooser.get_by_test_id("mode-link-only")).to_have_count(1)
    expect(chooser.get_by_test_id("mode-rename-option")).to_have_text(
        ["Tsardom of Moscavia"]
    )
    # a proper name ("Moscavians" isn't capitalised for the sentence):
    # "Add as another name" is the default
    _choose_mode(page, default="name")
    sent = _wait_sent(page, "link_text")
    assert sent["target_id"] == world.things["Tsardom of Moscavia"]
    assert sent["mode"] == "name"
    assert "use_name" not in sent
    expect(page.get_by_test_id("accept-notes")).to_contain_text(
        "Added as another name: Pure-line Moscavians"
    )
    _fact(marsh, "nest by").get_by_test_id("linked-ref").filter(
        has_text="Pure-line Moscavians"
    ).wait_for(state="visible", timeout=TIMEOUT_MS)

    # a link re-pointed, renamed to one of the new entry's names
    link = (
        _fact(marsh, "nest by")
        .get_by_test_id("linked-ref")
        .filter(has_text="the court")
    )
    link.hover()
    card = page.get_by_test_id("link-card")
    card.wait_for(state="visible", timeout=TIMEOUT_MS)
    card.get_by_role("button", name="Re-point…").click()
    _search_and_pick(page, "veli", "Velikoye")
    _choose_mode(page, rename_to="the capital", default="link")
    sent = _wait_sent(page, "repoint_ref")
    assert (sent["to_id"], sent["use_name"]) == (
        world.things["Velikoye"],
        "the capital",
    )
    expect(
        _fact(marsh, "nest by the capital.").get_by_test_id("linked-ref")
    ).to_have_text(["Pure-line Moscavians", "the capital"])

    # a stub's link: its words are a name, so adding one is the default,
    # and "Link only" says the name would be lost
    _fact(marsh, "Herons fish").get_by_test_id("linked-stub").hover()
    stub_card = page.get_by_test_id("stub-card")
    stub_card.wait_for(state="visible", timeout=TIMEOUT_MS)
    stub_card.get_by_role("button", name="Re-point…").click()
    _search_and_pick(page, "veli", "Velikoye")
    chooser = page.get_by_test_id("name-mode")
    chooser.wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(chooser.get_by_test_id("mode-link-only")).to_contain_text(
        "“the weir” won't be known as a name of Velikoye"
    )
    _choose_mode(page, default="name")
    sent = _wait_sent(page, "repoint_ref")
    assert (sent["to_id"], sent["mode"]) == (world.things["Velikoye"], "name")

    # the Tsardom goes by the words now
    page.get_by_test_id("kind-place").click()
    tsardom = _open_thing(page, "Tsardom of Moscavia")
    expect(tsardom.get_by_test_id("thing-other-names")).to_contain_text(
        "Pure-line Moscavians"
    )
    assert page.console_errors == []


COUNCIL = "It answers to the Boyar Council."
RAISED = "It was raised in winter."


def test_draft_edit_keeps_highlights(app, page, fixed_preview):
    """P6: the draft shows what accept will write. Its new names are
    highlighted in its facts and prose (one written with a lowercase
    "the" too); a fact rewritten on the draft keeps its highlights, the
    world's names linked as accept will link them; the timeline follows
    the facts' words, dates and ticks; and accept links what the draft
    showed."""

    _seeded(app, page, "Highlights")
    fixed_preview(
        {
            "name": "The Frostwing Host",
            "facts": [
                {"category": "general", "text": COUNCIL},
                {
                    "category": "general",
                    "text": RAISED,
                    "since": WorldDate.of(990).model_dump(mode="json"),
                },
            ],
            "names": [{"name": "The Boyar Council", "kind": "lore"}],
            "elsewhere": [
                {
                    "entry": "Velikoye",
                    "text": "Velikoye pays the Frostwing Host for the Boyar Council.",
                }
            ],
            "prose": {"description": "A host sworn to the Boyar Council."},
        }
    )
    draft = _draft(page, "lore", "The Tsar's winged army.")
    # "For other pages" as accept will link it onto Velikoye: the new
    # name, and this entry itself
    other = draft.get_by_test_id("elsewhere-row").filter(has_text="pays the")
    expect(other.get_by_test_id("linked-new")).to_have_text(
        ["the Frostwing Host", "the Boyar Council"]
    )
    council = _draft_fact(draft, COUNCIL)
    expect(council.get_by_test_id("linked-new")).to_have_text("the Boyar Council")
    prose = draft.get_by_test_id("draft-prose")
    expect(prose.get_by_test_id("linked-new")).to_contain_text("Boyar Council")

    # rewritten on the draft: the world's name it now writes links, the
    # new name stays a new name
    council.get_by_test_id("fact-menu-button").click()
    page.get_by_test_id("fact-menu").get_by_test_id("fact-edit").click()
    form = draft.get_by_test_id("fact-form")
    form.get_by_label("Fact", exact=True).fill(
        "It guards Velikoye for the Boyar Council."
    )
    form.get_by_role("button", name="Save").click()
    guards = _draft_fact(draft, "It guards Velikoye")
    expect(guards.get_by_test_id("linked-ref")).to_have_text("Velikoye")
    expect(guards.get_by_test_id("linked-new")).to_have_text("the Boyar Council")
    assert "It guards Velikoye for the Boyar Council." in [
        fact["text"] for fact in _sent(page, "draft_render")[-1]["preview"]["facts"]
    ]

    # the timeline follows the facts: a new date, then unticked, gone
    timeline = draft.get_by_test_id("entry-timeline")
    row = timeline.get_by_test_id("timeline-row").filter(has_text=RAISED)
    expect(row).to_contain_text("990")
    raised = _draft_fact(draft, RAISED)
    raised.get_by_test_id("fact-menu-button").click()
    # the first fact's menu, closed, may still be in the page
    page.get_by_test_id("fact-menu").get_by_test_id("fact-dates").locator(
        "visible=true"
    ).click()
    form = draft.get_by_test_id("fact-form")
    form.get_by_label("From year").fill("995")
    form.get_by_role("button", name="Save").click()
    expect(row).to_contain_text("995")
    raised.get_by_role("checkbox").click()
    expect(row).to_have_count(0)
    raised.get_by_role("checkbox").click()
    expect(row).to_contain_text("995")

    draft.get_by_role("button", name="Accept").click()
    host = _opened(page, "The Frostwing Host")
    fact = _fact(host, "It guards Velikoye")
    expect(fact.get_by_test_id("linked-ref")).to_have_text("Velikoye")
    expect(fact.get_by_test_id("linked-stub")).to_have_text("the Boyar Council")
    assert page.console_errors == []


def test_repeat_choices(app, page, fixed_preview):
    """P8: a repeat offers four choices, each named by the fact it keeps,
    under its fact as one pair (no separator between them): Keep new
    (this one written, the existing one removed on accept), Keep
    existing, Keep both and Move existing here."""

    world = _seeded(app, page, "Choices")
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
                {
                    "category": "description",
                    "text": "The Ashen Gate guards the road north.",
                    "ticked": False,
                    "repeat_of": {**repeat_of(GATE), "summary": True},
                },
            ],
            "prose": {"description": "The winter road."},
        }
    )
    draft = _draft(page, "place", "The road over the frozen river.")
    counts = draft.get_by_test_id("accept-counts")
    # a summary is edited on its page: never replaced or moved (H4)
    gate = _draft_fact(draft, "guards the road north")
    for name in ("Keep new", "Move existing here"):
        button = gate.get_by_role("button", name=name)
        expect(button).to_be_disabled()
        assert "summary of Velikoye" in (button.get_attribute("title") or "")
    expect(gate.get_by_role("button", name="Keep both")).to_be_enabled()

    freeze = _draft_fact(draft, "November to April")
    choices = freeze.get_by_test_id("repeat-choice")
    expect(choices).to_have_text(
        ["Keep new", "Keep existing", "Keep both", "Move existing here"]
    )
    # unticked at the threshold: it keeps the existing one
    pressed = freeze.locator("[data-testid=repeat-choice][aria-pressed=true]")
    expect(pressed).to_have_text("Keep existing")

    # the pair is one row: the separator runs under the match, not
    # between the fact and its match
    borders = freeze.evaluate(
        """host => [
            getComputedStyle(host).borderBottomStyle,
            getComputedStyle(host.querySelector('.fact')).borderBottomStyle,
        ]"""
    )
    assert borders == ["dashed", "none"]

    freeze.get_by_role("button", name="Keep new").click()
    assert freeze.get_by_role("checkbox").is_checked()
    expect(freeze.get_by_test_id("repeat-removing")).to_be_visible()
    expect(counts).to_have_text("writes 2 facts here, replaces 1")

    bells = _draft_fact(draft, "Bells ring")
    bells.get_by_role("button", name="Keep both").click()
    assert bells.get_by_role("checkbox").is_checked()
    bells.get_by_role("button", name="Keep existing").click()
    assert not bells.get_by_role("checkbox").is_checked()
    bells.get_by_role("button", name="Move existing here").click()
    expect(bells.get_by_test_id("repeat-moving")).to_be_visible()
    expect(counts).to_have_text("writes 2 facts here, moves 1 in, replaces 1")

    draft.get_by_role("button", name="Accept").click()
    road = _opened(page, "Khorol Ice Road")
    accepted = _sent(page, "accept_preview")[-1]["preview"]
    assert [f.get("replaces_repeat", False) for f in accepted["facts"]] == [
        False,
        True,
        False,
        False,
    ]
    _fact(road, "November to April").wait_for(state="visible", timeout=TIMEOUT_MS)
    _fact(road, BELLS).wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(_fact(road, FREEZES)).to_have_count(0)
    page.get_by_test_id("kind-place").click()
    vel = _open_thing(page, "Velikoye")
    _fact(vel, GATE).wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(_fact(vel, FREEZES)).to_have_count(0)
    expect(_fact(vel, BELLS)).to_have_count(0)
    assert page.console_errors == []


# --- "+ Add facts" as a versioned small draft (polish-1, Task 9) ------------


def _velikoye(app, page, stem: str):
    world = _seeded(app, page, stem)
    page.get_by_test_id("kind-place").click()
    return world, _open_thing(page, "Velikoye")


def _ask_facts(scope, prompt: str):
    """ "+ Add facts…", `prompt` asked: the fact draft, once it shows."""

    scope.get_by_test_id("add-facts").click()
    scope.get_by_test_id("add-facts-form").get_by_label("What to add").fill(prompt)
    scope.get_by_test_id("add-draft").click()
    found = scope.get_by_test_id("fact-draft")
    found.get_by_test_id("fact-draft-bar").wait_for(state="visible", timeout=TIMEOUT_MS)
    return found


def _facts_reply(*texts) -> dict:
    return {"facts": [{"category": "general", "text": text} for text in texts]}


def test_add_facts_regenerate_and_versions(app, page, fixed_facts):
    """ "+ Add facts" on a saved page has a page draft's feature set: the
    prompt kept in its bar, Regenerate from it as edited, "Version n of
    m", and each version's ticks kept; Write sends its key."""

    world, thing = _velikoye(app, page, "AddVersions")
    fixed_facts(_facts_reply("Its walls are white.", "Its market sells furs."))
    found = _ask_facts(thing, "its walls")
    rows = found.get_by_test_id("fact-draft-row")
    expect(rows).to_have_count(2)
    versions = found.get_by_test_id("fact-draft-versions")
    expect(versions).to_contain_text("Version 1 of 1")
    rows.nth(1).get_by_role("checkbox").uncheck()
    expect(found.get_by_test_id("fact-draft-accept")).to_have_text("Write 1")
    # "Write N" again at the foot of the list
    expect(found.get_by_test_id("fact-draft-foot")).to_contain_text("Write 1")

    # the prompt, kept and edited in the bar, then Regenerate
    prompt = found.get_by_test_id("add-prompt").locator("textarea").first
    expect(prompt).to_have_value("its walls")
    prompt.fill("its walls at dusk")
    fixed_facts(_facts_reply("Its walls glow at dusk."))
    found.get_by_test_id("fact-draft-regenerate").click()
    expect(versions).to_contain_text("Version 2 of 2")
    expect(rows).to_have_count(1)
    expect(rows.nth(0)).to_contain_text("Its walls glow at dusk.")
    sent = _sent(page, "add_facts")[-1]
    assert sent["regenerate"] is True
    assert sent["prompt"] == "its walls at dusk"

    # version 1 again, as the owner left it
    versions.click()
    page.get_by_test_id("fact-draft-version").filter(has_text="v1").click()
    expect(versions).to_contain_text("Version 1 of 2")
    expect(rows).to_have_count(2)
    expect(rows.nth(1).get_by_role("checkbox")).not_to_be_checked()
    expect(rows.nth(0).get_by_role("checkbox")).to_be_checked()

    found.get_by_test_id("fact-draft-accept").click()
    sent = _wait_sent(page, "accept_facts")
    assert sent["draft_key"] == f"facts:{world.things['Velikoye']}"
    assert [f["ticked"] for f in sent["draft"]["facts"]] == [True, False]
    _fact(thing, "Its walls are white.").wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(_fact(thing, "Its market sells furs.")).to_have_count(0)
    expect(thing.get_by_test_id("fact-draft")).to_have_count(0)
    assert page.console_errors == []


def test_add_facts_repeat_keep_new(app, page, fixed_facts):
    """A drafted fact that repeats one the world holds shows its match
    under its row with the four choices; Keep new writes it and removes
    the existing one. (The add-facts ask flags repeats of the page's own
    facts: `draft_facts` checks against `owners=[thing_id]`.)"""

    _world, thing = _velikoye(app, page, "AddRepeat")
    again = "The Khorol freezes solid every winter, bank to bank."
    fixed_facts(_facts_reply(again, "Its market sells furs."))
    found = _ask_facts(thing, "the river")
    row = found.get_by_test_id("fact-draft-row").filter(has_text="bank to bank")
    match = row.get_by_test_id("fact-draft-repeat")
    expect(match).to_contain_text(FREEZES)
    expect(match.get_by_test_id("repeat-choice")).to_have_text(
        ["Keep new", "Keep existing", "Keep both", "Move existing here"]
    )
    match.get_by_role("button", name="Keep new").click()
    expect(row.get_by_role("checkbox")).to_be_checked()
    expect(match.get_by_test_id("repeat-removing")).to_be_visible()
    found.get_by_test_id("fact-draft-accept").click()
    sent = _wait_sent(page, "accept_facts")
    assert sent["draft"]["facts"][0]["replaces_repeat"] is True
    _fact(thing, again).wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(_fact(thing, FREEZES)).to_have_count(0)
    assert page.console_errors == []


def test_nested_add_facts_on_draft(app, page, fixed_preview, fixed_facts):
    """On a draft page, "+ Add facts" is its own small draft nested under
    Facts: the page draft waits for it (Accept off, with why), and its
    Write puts only the ticked facts into a new version of the page
    draft."""

    _seeded(app, page, "Nested")
    fixed_preview(_host("It flies at night."))
    draft = _draft(page, "lore", "The Tsar's winged army.")
    bar = draft.get_by_test_id("draft-bar")
    versions = bar.get_by_test_id("draft-versions")
    expect(versions).to_contain_text("Version 1 of 1")
    fixed_facts(
        _facts_reply("It roosts in the bell towers.", "Its captains wear white.")
    )
    nested = _ask_facts(draft, "where it sleeps")
    expect(nested.get_by_test_id("fact-draft-row")).to_have_count(2)
    # under the Facts heading, indented
    heading = draft.get_by_test_id("facts-heading").bounding_box()
    box = nested.bounding_box()
    assert box["y"] > heading["y"] and box["x"] > heading["x"]
    accept = bar.get_by_role("button", name="Accept")
    expect(accept).to_be_disabled()
    expect(accept).to_have_attribute("title", "write or discard the added facts first")

    nested.get_by_test_id("fact-draft-row").nth(1).get_by_role("checkbox").uncheck()
    nested.get_by_test_id("fact-draft-accept").click()
    sent = _wait_sent(page, "write_nested_facts")
    assert [f["ticked"] for f in sent["draft"]["facts"]] == [True, False]
    expect(versions).to_contain_text("Version 2 of 2")
    _draft_fact(draft, "It roosts in the bell towers.").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    expect(_draft_fact(draft, "Its captains wear white.")).to_have_count(0)
    expect(_draft_fact(draft, "It flies at night.")).to_have_count(1)
    expect(draft.get_by_test_id("fact-draft")).to_have_count(0)
    expect(accept).to_be_enabled()
    assert page.console_errors == []


def test_add_facts_prompt_box_is_roomy(app, page):
    """ "+ Add facts"'s prompt is a textarea, two lines tall at least,
    that grows with what's typed."""

    _world, thing = _velikoye(app, page, "Roomy")
    thing.get_by_test_id("add-facts").click()
    field = thing.get_by_test_id("add-facts-form").get_by_test_id("add-prompt")
    box = field.locator("textarea").first
    assert box.evaluate("e => e.tagName") == "TEXTAREA"
    height = box.bounding_box()["height"]
    assert height >= 40
    box.fill("its laws\nwho keeps them\nhow they are judged\nwhat they forbid")
    page.wait_for_function(
        "([e, h]) => e.getBoundingClientRect().height > h",
        arg=[box.element_handle(), height],
        timeout=TIMEOUT_MS,
    )
    assert page.console_errors == []
