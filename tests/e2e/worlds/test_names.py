"""Names and pickers (polish area 4): every entry search finds an entry by
its other names, and says which one matched.

The worlds are seeded through `talemate.world` (`seed.seed_fm_world`). No
model is asked anything.
"""

from __future__ import annotations

from playwright.sync_api import expect

from e2e.seed import seed_fm_world
from e2e.worlds.test_drafts import _select
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
