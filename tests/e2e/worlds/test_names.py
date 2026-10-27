"""Names and pickers (polish area 4): every entry search finds an entry by
its other names, and says which one matched.

The worlds are seeded through `talemate.world` (`seed.seed_fm_world`). No
model is asked anything.
"""

from __future__ import annotations

from playwright.sync_api import expect

from e2e.seed import seed_fm_world
from e2e.worlds.test_connections_create import _wait_sent
from e2e.worlds.test_drafts import _select
from e2e.worlds.test_new_scene import SEND_SPY_JS
from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _fact,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)

# selects `words` in `element` across its text nodes (over a link), then
# right-clicks the selection, as `test_drafts.SELECT_JS` does in one node
SELECT_ACROSS_JS = """
([element, words]) => {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let all = '';
    while (walker.nextNode()) {
        nodes.push([walker.currentNode, all.length]);
        all += walker.currentNode.textContent;
    }
    const at = all.indexOf(words);
    if (at < 0) {
        return false;
    }
    const place = (offset, end) => {
        for (const [node, from] of nodes) {
            const to = from + node.textContent.length;
            if (end ? offset <= to && offset > from : offset < to) {
                return [node, offset - from];
            }
        }
        return null;
    };
    const range = document.createRange();
    range.setStart(...place(at, false));
    range.setEnd(...place(at + words.length, true));
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    const box = range.getBoundingClientRect();
    range.startContainer.parentElement.dispatchEvent(new MouseEvent('contextmenu', {
        bubbles: true, cancelable: true, button: 2,
        clientX: box.left + 2, clientY: box.top + 2,
    }));
    return true;
}
"""

OWL_FOLK = {
    "kind": "species",
    "name": "Moscavian Owl-folk",
    "fields": {"aka": [{"name": "Moscavian Owls", "tag": "common", "everyday": True}]},
}
NOVGRAD = {
    "kind": "place",
    "name": "Novgrad",
    "facts": [{"category": "history", "text": "The owls of the north road nest here."}],
}


def _seeded(app, page, label: str):
    name = _world_name(label)
    world = seed_fm_world(app.root, name, present_year=1026, things=[OWL_FOLK, NOVGRAD])
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-place").click()
    return world, _open_thing(page, "Novgrad")


def _found(page, results):
    """The result for the Owl-folk, found by its other name: its own name,
    and the other name small beneath it."""

    row = results.filter(has_text="Moscavian Owl-folk")
    row.first.wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(row.first.get_by_test_id("entry-matched")).to_have_text("Moscavian Owls")
    return row.first


def test_pickers_find_other_names(app, page):
    _, novgrad = _seeded(app, page, "OtherNames")

    # Link to an entry… (the selection menu's search)
    _select(page, _fact(novgrad, "north road"), "north road")
    page.get_by_test_id("selection-menu").get_by_test_id("selection-link").click()
    search = page.get_by_test_id("reference-search")
    search.wait_for(state="visible", timeout=TIMEOUT_MS)
    search.get_by_role("textbox").fill("Moscavian Owls")
    _found(page, page.get_by_test_id("reference-result"))
    page.keyboard.press("Escape")

    # + In…: the inline field
    novgrad.get_by_test_id("in-add").click()
    form = novgrad.get_by_test_id("in-add-form")
    form.get_by_test_id("in-target").locator("input").fill("Moscavian Owls")
    _found(page, page.get_by_test_id("entry-result"))
    # an entry goes by that name already: no new stub of it is offered
    expect(
        page.get_by_test_id("entry-result").filter(has_text="Make a stub")
    ).to_have_count(0)
    form.get_by_role("button", name="Cancel").click()

    # Move to… (a fact's menu)
    _fact(novgrad, "north road").get_by_test_id("fact-menu-button").click()
    page.get_by_test_id("fact-menu").get_by_test_id("fact-move").click()
    menu = page.get_by_test_id("fact-move-menu")
    menu.get_by_test_id("move-target").locator("input").fill("Moscavian Owls")
    _found(page, page.get_by_test_id("entry-result"))
    assert page.console_errors == []


SOLARIUS = {"kind": "character", "name": "Solarius"}
ACADEMY = {
    "kind": "place",
    "name": "Academy of Northern Lights",
    "facts": [
        {
            "category": "history",
            "text": "Its five houses include the House of [[@Solarius|Solarius]].",
        }
    ],
}


def test_house_of_solarius_stub(app, page):
    name = _world_name("Solarius")
    seed_fm_world(app.root, name, present_year=1026, things=[SOLARIUS, ACADEMY])
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-place").click()
    academy = _open_thing(page, "Academy of Northern Lights")

    fact = _fact(academy, "five houses")
    fact.wait_for(state="visible", timeout=TIMEOUT_MS)
    text = fact.locator(".fact-text").first
    assert page.evaluate(SELECT_ACROSS_JS, [text.element_handle(), "House of Solarius"])
    menu = page.get_by_test_id("selection-menu")
    menu.get_by_test_id("selection-kind").locator(".v-field").click()
    page.get_by_role("option", name="lore entry", exact=True).click()
    menu.get_by_test_id("selection-stub").click()

    # the longer name wins: one stub link over the words, Solarius's gone
    stub = fact.get_by_test_id("linked-stub")
    expect(stub).to_have_text("House of Solarius")
    expect(fact.get_by_test_id("linked-ref")).to_have_count(0)
    assert page.console_errors == []


SNOW_OWLS = {"kind": "species", "name": "Snow Owls"}
OWL_MARSH = {
    "kind": "place",
    "name": "Owl Marsh",
    "facts": [{"category": "history", "text": "The Pure-line Moscavians nest here."}],
}


def test_repoint_renames_the_entry_to_the_words(app, page):
    name = _world_name("Retitle")
    seed_fm_world(app.root, name, present_year=1026, things=[SNOW_OWLS, OWL_MARSH])
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-place").click()
    marsh = _open_thing(page, "Owl Marsh")

    _select(page, _fact(marsh, "nest here"), "Pure-line Moscavians")
    page.get_by_test_id("selection-menu").get_by_test_id("selection-link").click()
    search = page.get_by_test_id("reference-search")
    search.get_by_role("textbox").fill("Snow")
    page.get_by_test_id("reference-result").filter(has_text="Snow Owls").click()
    chooser = page.get_by_test_id("name-mode")
    chooser.get_by_test_id("mode-retitle").click()

    # the words link the entry, which now goes by them, its old name kept
    link = _fact(marsh, "nest here").get_by_test_id("linked-ref")
    expect(link).to_have_text("Pure-line Moscavians")
    page.get_by_test_id("kind-species").click()
    owls = _open_thing(page, "Pure-line Moscavians")
    expect(owls.get_by_test_id("aka-editor").get_by_test_id("aka-row")).to_contain_text(
        ["Snow Owls"]
    )
    expect(page.get_by_test_id("accept-notes")).to_have_count(0)
    assert page.console_errors == []


MOSCAVIA_STUB = {
    "kind": "place",
    "name": "Tsardom of Moscavia",
    "stub": "live",
    "fields": {"tag": "nation"},
}
OWL_FOLK_NAMING = {
    "kind": "species",
    "name": "Owl-folk",
    "facts": [
        {
            "category": "origin",
            "text": "Everyone in the [[@Tsardom of Moscavia|Tsardom of Moscavia]]"
            " became owl-folk one day in 994.",
        }
    ],
}


def _card_parts(page, link):
    link.hover()
    card = page.get_by_test_id("stub-card")
    card.wait_for(state="visible", timeout=TIMEOUT_MS)
    parts = {
        "tag": card.get_by_test_id("stub-tag").inner_text(),
        "kind": card.get_by_test_id("stub-kind").inner_text().split("\n")[0],
        "mentions": card.get_by_test_id("stub-mentions").inner_text(),
        "repoint": card.get_by_role("button", name="Re-point…").count(),
    }
    page.mouse.move(0, 0)
    card.wait_for(state="hidden", timeout=TIMEOUT_MS)
    return parts


def test_named_stubs_card_is_full_without_stubs_page(app, page):
    name = _world_name("StubCard")
    seed_fm_world(
        app.root,
        name,
        present_year=1026,
        things=[MOSCAVIA_STUB, OWL_FOLK_NAMING, {"kind": "place", "name": "Moscavy"}],
    )
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-species").click()
    owl = _open_thing(page, "Owl-folk")

    named = owl.get_by_test_id("named-stubs").get_by_test_id("linked-stub")
    in_fact = _fact(owl, "became owl-folk").get_by_test_id("linked-stub")
    from_named = _card_parts(page, named)
    assert from_named == {
        "tag": "nation",
        "kind": "place",
        "mentions": "1 mention",
        "repoint": 1,
    }
    assert _card_parts(page, in_fact) == from_named

    # its Re-point… re-points the whole stub, as on the Stubs page
    named.hover()
    card = page.get_by_test_id("stub-card")
    card.get_by_role("button", name="Re-point…").click()
    search = page.get_by_test_id("reference-search")
    search.get_by_role("textbox").fill("Mosc")
    page.get_by_test_id("reference-result").filter(has_text="Moscavy").click()
    page.get_by_test_id("name-mode").get_by_test_id("mode-link-only").click()
    expect(owl.get_by_test_id("named-stubs")).to_have_count(0)
    assert page.console_errors == []


def test_connected_stub_has_the_stub_card(app, page):
    name = _world_name("ConnStub")
    seed_fm_world(
        app.root,
        name,
        present_year=1026,
        things=[
            {"kind": "place", "name": "Velikoye"},
            {
                "kind": "place",
                "name": "Wattle Row",
                "stub": "live",
                "fields": {"tag": "street"},
                "filings": [{"target": "Velikoye"}],
            },
        ],
    )
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-place").click()
    vel = _open_thing(page, "Velikoye")
    row = vel.get_by_test_id("connected-row").filter(has_text="Wattle Row")
    parts = _card_parts(page, row.get_by_test_id("linked-stub"))
    assert parts == {
        "tag": "street",
        "kind": "place",
        "mentions": "0 mentions",
        "repoint": 1,
    }


VELIKOYE = {"kind": "place", "name": "Velikoye"}
MAREN = {
    "kind": "character",
    "name": "Maren",
    "filings": [{"target": "Velikoye"}],
}


def _highlights(box, name: str) -> None:
    """`name` shows as a known name in the prompt `box`."""

    expect(box.get_by_test_id("name-match").filter(has_text=name)).to_have_count(
        1, timeout=TIMEOUT_MS
    )


def test_prompts_highlight_names(app, page, fixed_preview):
    name = _world_name("Prompts")
    world = seed_fm_world(app.root, name, present_year=1026, things=[VELIKOYE, MAREN])
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-character").click()
    maren = _open_thing(page, "Maren")

    # an In row's "but…"
    entry_in = maren.get_by_test_id("entry-in")
    entry_in.get_by_test_id("in-row").filter(has_text="Velikoye").get_by_test_id(
        "in-add-but"
    ).click()
    but = entry_in.get_by_test_id("in-but-form")
    but.get_by_label("How they differ").fill("Rarely sleeps in Velikoye.")
    _highlights(but, "Velikoye")
    # Enter adds it, with the names as picked (its request takes them)
    but.locator("textarea").first.press("Enter")
    sent = _wait_sent(page, "add_exception")
    assert sent["text"] == "Rarely sleeps in Velikoye."
    assert sent["picks"] == {"Velikoye": world.things["Velikoye"]}

    # "+ Add facts…"
    maren.get_by_test_id("add-facts").click()
    form = maren.get_by_test_id("add-facts-form")
    form.get_by_test_id("add-prompt").locator("textarea").first.fill(
        "Her days in Velikoye"
    )
    _highlights(form, "Velikoye")
    form.get_by_role("button", name="Cancel").click()

    # Connected's "+ Add"
    page.get_by_test_id("kind-place").click()
    vel = _open_thing(page, "Velikoye")
    vel.get_by_test_id("connected-add").click()
    group = vel.get_by_test_id("group-add")
    group.get_by_test_id("group-add-prompt").locator("textarea").first.fill(
        "friends of Maren"
    )
    _highlights(group, "Maren")

    # a page draft's prompt
    fixed_preview(
        {
            "name": "Ilya",
            "facts": [{"category": "background", "text": "A ferryman."}],
            "prose": {"appearance": "", "personality": "", "background": ""},
        }
    )
    page.get_by_test_id("kind-character").click()
    box = page.get_by_test_id("create-box")
    box.get_by_label("Describe it").fill("a ferryman")
    box.get_by_role("button", name="Create").click()
    bar = page.get_by_test_id("draft-page").get_by_test_id("draft-bar")
    prompt = bar.get_by_test_id("draft-prompt")
    prompt.locator("textarea").first.fill("a ferryman who knows Maren")
    _highlights(prompt, "Maren")
    assert page.console_errors == []


def test_but_on_a_page_viewed_at_a_date_sends_its_names(app, page):
    """Final review M4: on a page viewed as of a date, the "but…" box
    looks its names up at that date, and sends them."""

    name = _world_name("ButAt")
    world = seed_fm_world(app.root, name, present_year=1026, things=[VELIKOYE, MAREN])
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-character").click()
    maren = _open_thing(page, "Maren")
    maren.get_by_test_id("as-of-button").click()
    picker = page.get_by_test_id("as-of-picker")
    picker.get_by_label("Year").fill("1020")
    picker.get_by_role("button", name="View").click()
    maren.get_by_test_id("as-of-button").filter(has_text="1020").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )

    entry_in = maren.get_by_test_id("entry-in")
    entry_in.get_by_test_id("in-row").filter(has_text="Velikoye").get_by_test_id(
        "in-add-but"
    ).click()
    but = entry_in.get_by_test_id("in-but-form")
    but.get_by_label("How they differ").fill("Rarely sleeps in Velikoye.")
    _highlights(but, "Velikoye")
    but.locator("textarea").first.press("Enter")
    sent = _wait_sent(page, "add_exception")
    assert sent["picks"] == {"Velikoye": world.things["Velikoye"]}


def test_highlight_only_prompts_offer_no_picks(app, page):
    """Final review M5: a prompt whose request takes no picks highlights
    its names without a menu to re-pick them, since a pick there would do
    nothing."""

    name = _world_name("NoPicks")
    seed_fm_world(app.root, name, present_year=1026, things=[VELIKOYE, MAREN])
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-character").click()
    maren = _open_thing(page, "Maren")
    maren.get_by_test_id("add-facts").click()
    form = maren.get_by_test_id("add-facts-form")
    form.get_by_test_id("add-prompt").locator("textarea").first.fill(
        "Her days in Velikoye"
    )
    _highlights(form, "Velikoye")
    form.get_by_test_id("name-match").hover()
    page.wait_for_timeout(600)
    expect(page.get_by_test_id("name-popover")).to_have_count(0)
