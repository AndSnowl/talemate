"""Lists, grouping and errors (polish area 5): the side tree folds and
remembers, search narrows it with text modifiers, a kind's page lists its
entries, and one error message stays in view.

The worlds are seeded through `talemate.world` (`seed.seed_fm_world`). No
model is asked anything.
"""

from __future__ import annotations

import re

from playwright.sync_api import expect

from e2e.seed import dismiss_onboarding, seed_fm_world
from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)

TREE = [
    {"kind": "place", "name": "Moscavia", "fields": {"tag": "nation"}},
    {
        "kind": "place",
        "name": "Velikoye",
        "fields": {"tag": "city"},
        "filings": [{"target": "Moscavia"}],
        "facts": [{"category": "description", "text": "The fortified capital."}],
    },
    {
        "kind": "place",
        "name": "Kerensk",
        "fields": {"tag": "city"},
        "filings": [{"target": "Moscavia"}],
    },
    {"kind": "place", "name": "Kerensk Docks", "filings": [{"target": "Kerensk"}]},
    {
        "kind": "place",
        "name": "Night Court",
        "fields": {"tag": "court"},
        "filings": [{"target": "Velikoye"}],
        "facts": [
            {
                "category": "description",
                "text": "Where the Tsar's quiet business is done.",
            }
        ],
    },
    {
        "kind": "place",
        "name": "Wattle Row",
        "stub": "live",
        "filings": [{"target": "Velikoye"}],
    },
    {"kind": "character", "name": "Maren", "filings": [{"target": "Velikoye"}]},
]


def _tree(page):
    return page.get_by_test_id("world-list")


def _cards(page):
    return _tree(page).get_by_test_id("thing-card")


def _names(page):
    return _tree(page).get_by_test_id("thing-card").locator(".card-name")


def _seeded(app, page, label):
    name = _world_name(label)
    world = seed_fm_world(app.root, name, present_year=1026, things=TREE)
    _open_world(page, name)
    _world_tab(page)
    return name, world


def test_side_tree_folds_and_remembers(app, page):
    name, _ = _seeded(app, page, "Folds")
    # every kind starts folded
    expect(_cards(page)).to_have_count(0)

    # opening the Night Court opens the path to it, and only that
    _open_thing(page, "Night Court")
    expect(_names(page)).to_have_text(
        ["Moscavia", "Kerensk", "Velikoye", "Night Court"]
    )
    kerensk = _cards(page).filter(has_text="Kerensk")
    expect(kerensk.get_by_test_id("fold-count")).to_have_text("1")

    # folded with its ▸, Places stays folded after a reload
    page.get_by_test_id("kind-fold-place").click()
    expect(_cards(page)).to_have_count(0)
    page.reload()
    dismiss_onboarding(page)
    _open_world(page, name)
    _world_tab(page)
    expect(_cards(page)).to_have_count(0)

    # the kind's name opens its page and unfolds it, the way to the Night
    # Court still open as it was left
    page.get_by_test_id("kind-place").click()
    expect(_names(page)).to_have_text(
        ["Moscavia", "Kerensk", "Velikoye", "Night Court"]
    )
    page.get_by_test_id("create-box").wait_for(state="visible", timeout=TIMEOUT_MS)

    # its "+" opens the page with the prompt ready to type
    page.get_by_test_id("kind-new-character").click()
    box = page.get_by_test_id("create-box")
    expect(box.locator("textarea").first).to_be_focused()
    assert page.console_errors == []


def test_side_search_modifiers(app, page):
    _seeded(app, page, "Modifiers")
    search = page.get_by_test_id("world-search").locator("input")
    search.fill("in:Velikoye")
    # characters come before places, as the side list has them
    expect(_names(page)).to_have_text(["Maren", "Moscavia", "Velikoye", "Night Court"])
    expect(_cards(page).filter(has_text="Moscavia")).to_have_class(
        re.compile("context")
    )
    expect(_tree(page).locator(".stub-name")).to_have_text(["Wattle Row"])

    search.fill("stub")
    expect(_tree(page).locator(".stub-name")).to_have_text(["Wattle Row"])
    expect(_cards(page).filter(has_text="Night Court")).to_have_count(0)

    # cleared: the folds come back
    search.fill("")
    expect(_cards(page)).to_have_count(0)


def test_stub_row_one_line(app, page):
    _seeded(app, page, "StubRow")
    page.get_by_test_id("world-search").locator("input").fill("Wattle")
    row = _tree(page).get_by_test_id("stub-item")
    expect(row.locator(".stub-name")).to_have_text("Wattle Row")
    expect(row).not_to_contain_text("not made yet")
    assert "not made yet" in (row.get_attribute("title") or "")
