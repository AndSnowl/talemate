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

OWL_FOLK = {
    "kind": "species",
    "name": "Moscavian Owl-folk",
    "fields": {
        "aka": [{"name": "Moscavian Owls", "tag": "common", "everyday": True}]
    },
}
NOVGRAD = {
    "kind": "place",
    "name": "Novgrad",
    "facts": [
        {"category": "history", "text": "The owls of the north road nest here."}
    ],
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
    expect(page.get_by_test_id("entry-result").filter(has_text="Make a stub")).to_have_count(0)
    form.get_by_role("button", name="Cancel").click()

    # Move to… (a fact's menu)
    _fact(novgrad, "north road").get_by_test_id("fact-menu-button").click()
    page.get_by_test_id("fact-menu").get_by_test_id("fact-move").click()
    menu = page.get_by_test_id("fact-move-menu")
    menu.get_by_test_id("move-target").locator("input").fill("Moscavian Owls")
    _found(page, page.get_by_test_id("entry-result"))
    assert page.console_errors == []
