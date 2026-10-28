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


def _kind_list(page):
    return page.get_by_test_id("kind-list")


def _headings(page):
    return _kind_list(page).get_by_test_id("kind-list-heading")


def _row_names(page):
    return _kind_list(page).get_by_test_id("kind-list-row").locator(".row-name")


def test_kind_page_lists_entries(app, page):
    name, _ = _seeded(app, page, "KindList")
    page.get_by_test_id("kind-place").click()
    page.get_by_test_id("create-box").wait_for(state="visible", timeout=TIMEOUT_MS)
    lst = _kind_list(page)
    expect(lst.get_by_test_id("kind-list-title")).to_have_text("All places · 6")

    # places group by where they are, by default; nowhere comes last
    expect(_headings(page)).to_have_text(
        ["In Kerensk · 1", "In Moscavia · 2", "In Velikoye · 2", "Nowhere · 1"]
    )
    court = lst.get_by_test_id("kind-list-row").filter(has_text="Night Court")
    expect(court).to_have_text(
        "Night Court · in Velikoye — Where the Tsar's quiet business is done."
    )
    name_box = court.locator(".row-name").bounding_box()
    where_box = court.locator(".row-where").bounding_box()
    assert where_box["x"] - (name_box["x"] + name_box["width"]) < 40
    stub = lst.get_by_test_id("kind-list-row").filter(has_text="Wattle Row")
    expect(stub).to_have_text("Wattle Row · in Velikoye · not made yet")

    # by tag: Connected's headings, Other last
    lst.get_by_test_id("group-tag").click()
    expect(_headings(page)).to_have_text(
        ["Cities · 2", "Courts · 1", "Nations · 1", "Other · 2"]
    )

    # sorted by recent change: Kerensk, just re-tagged, comes first
    lst.get_by_test_id("group-none").click()
    lst.get_by_test_id("sort-recent").click()
    kerensk = _open_thing(page, "Kerensk")
    kerensk.get_by_test_id("tag-chip").first.click()
    picker = page.get_by_test_id("tag-picker")
    picker.get_by_test_id("tag-search").locator("input").fill("port")
    picker.get_by_test_id("tag-new").click()
    expect(kerensk.get_by_test_id("tag-chip").first).to_have_text("port")
    page.get_by_test_id("kind-place").click()
    expect(_row_names(page).first).to_have_text("Kerensk")

    # the choice is kept
    page.reload()
    dismiss_onboarding(page)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-place").click()
    expect(_headings(page)).to_have_count(0)
    expect(_row_names(page).first).to_have_text("Kerensk")

    # the side search filters it too
    page.get_by_test_id("world-search").locator("input").fill("stub")
    expect(_row_names(page)).to_have_text(["Wattle Row"])
    page.get_by_test_id("world-search").locator("input").fill("")

    # a row opens its entry
    _kind_list(page).get_by_test_id("kind-list-row").filter(
        has=page.locator(".row-name", has_text=re.compile("^Velikoye$"))
    ).click()
    page.get_by_test_id("thing-page").get_by_test_id("thing-name").filter(
        has_text="Velikoye"
    ).wait_for(state="visible", timeout=TIMEOUT_MS)
    assert page.console_errors == []
