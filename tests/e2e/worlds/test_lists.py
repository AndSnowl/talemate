"""Lists, grouping and errors (polish area 5): the side tree folds and
remembers, search narrows it with text modifiers, a kind's page lists its
entries, and one error message stays in view.

The worlds are seeded through `talemate.world` (`seed.seed_fm_world`). No
model is asked anything.
"""

from __future__ import annotations

import re

from playwright.sync_api import expect

from e2e.seed import dismiss_onboarding, seed_fm_world, send_backend
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
    # every kind starts folded, but the one whose page is open (a world
    # opens on its characters)
    expect(_names(page)).to_have_text(["Maren"])

    # opening the Night Court opens the path to it, and only that
    _open_thing(page, "Night Court")
    expect(_names(page)).to_have_text(
        ["Moscavia", "Kerensk", "Velikoye", "Night Court"]
    )
    kerensk = _cards(page).filter(has_text="Kerensk")
    expect(kerensk.get_by_test_id("fold-count")).to_have_text("1")

    # the way to a page opens only while it's open: reloaded, with no page
    # open, the tree is folded again (final review I2)
    page.reload()
    dismiss_onboarding(page)
    _open_world(page, name)
    _world_tab(page)
    expect(_names(page)).to_have_text(["Maren"])
    _open_thing(page, "Night Court")

    # folded with its ▸, Places stays folded after a reload (the Night
    # Court's page is open, so no other kind is)
    page.get_by_test_id("kind-fold-place").click()
    expect(_cards(page)).to_have_count(0)
    page.reload()
    dismiss_onboarding(page)
    _open_world(page, name)
    _world_tab(page)
    expect(_names(page)).to_have_text(["Maren"])

    # the kind's name opens its page and unfolds it; what was only the way
    # to a page isn't kept open
    page.get_by_test_id("kind-place").click()
    expect(_names(page)).to_have_text(["Moscavia"])
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

    # while searching, a fold arrow waits (final review M7)
    search.fill("in:Velikoye")
    _cards(page).filter(has_text="Moscavia").get_by_test_id("entry-fold").click()
    # cleared: the folds come back, as they were
    search.fill("")
    expect(_names(page)).to_have_text(["Maren"])
    page.get_by_test_id("kind-fold-place").click()
    expect(_names(page)).to_have_text(["Maren", "Moscavia"])


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
    # counted as the side tree counts (entries; a stub apart), final review M8
    expect(lst.get_by_test_id("kind-list-title")).to_have_text(
        "All places · 5 · 1 not made yet"
    )
    expect(page.get_by_test_id("kind-place")).to_contain_text("5")

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


def _fail(page):
    """A request the backend refuses: a thing that isn't there."""

    send_backend(page, {"type": "worlds", "action": "get_thing", "id": "0" * 32})


def test_error_pinned_counts_and_clears(app, page):
    name, _ = _seeded(app, page, "Errors")
    other = _world_name("ErrorsToo")
    seed_fm_world(app.root, other, present_year=1026, things=TREE[:1])
    _open_thing(page, "Night Court")
    page.mouse.wheel(0, 2000)
    _fail(page)
    error = page.get_by_test_id("world-error")
    expect(error).to_contain_text("no such thing")
    _fail(page)
    expect(error).to_contain_text("×2")
    # in view, however far the page is scrolled
    box = error.bounding_box()
    assert 0 <= box["y"] < page.viewport_size["height"]
    expect(error.get_by_role("button", name="Copy")).to_be_visible()
    # one message: no popup repeats it
    expect(page.get_by_text("no such thing")).to_have_count(1)
    # it stays until closed
    page.wait_for_timeout(4000)
    expect(error).to_be_visible()

    # another world: it no longer applies
    page.get_by_role("tab", name="Worlds", exact=True).click()
    _open_world(page, other)
    expect(error).to_have_count(0)


def test_prompt_box_survives_an_error(app, page):
    name, _ = _seeded(app, page, "Squash")
    other = _world_name("SquashToo")
    seed_fm_world(app.root, other, present_year=1026, things=TREE[:1])
    _fail(page)
    page.get_by_test_id("world-error").wait_for(state="visible", timeout=TIMEOUT_MS)
    page.get_by_role("tab", name="Worlds", exact=True).click()
    _open_world(page, other)
    # the World tab drew its create box while hidden, behind the Worlds tab
    # (the owner's squashed prompt box, hubs item 19): shown now, it's
    # measured again
    _world_tab(page)
    box = page.get_by_test_id("create-box").locator("textarea").first
    box.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert box.bounding_box()["height"] >= 40


def _decoration(locator) -> str:
    return locator.evaluate("(el) => getComputedStyle(el).textDecorationLine")


def _colour(locator) -> str:
    return locator.evaluate("(el) => getComputedStyle(el).color")


def test_offer_rows_dim_dropped_rows_strike(app, page, fixed_preview):
    from e2e.worlds.test_drafts import _draft, _draft_fact, _host
    from e2e.worlds.test_drafts import _seeded as _drafts_world

    _drafts_world(app, page, "Offers")
    fixed_preview(
        _host(
            "It flies at night.",
            file_into=[{"entry": "The White Talon", "role": "regiment"}],
        )
    )
    draft = _draft(page, "lore", "The Tsar's winged army.")

    # an offer (it came unticked): dimmed, not struck through
    talon = draft.get_by_test_id("file-into-row").filter(has_text="The White Talon")
    text = talon.locator(".suggestion-text")
    assert _decoration(text) == "none"
    dim = _colour(text)
    talon.get_by_role("checkbox").check()
    expect(text).not_to_have_css("color", dim)
    talon.get_by_role("checkbox").uncheck()
    expect(text).to_have_css("color", dim)
    assert _decoration(text) == "none"

    # a fact that came ticked, unticked: struck through
    fact = _draft_fact(draft, "It flies at night.")
    fact.get_by_role("checkbox").uncheck()
    expect(fact.locator(".fact-text").first).to_have_css(
        "text-decoration-line", "line-through"
    )
    assert page.console_errors == []


def test_same_as_has_room(app, page, fixed_facts):
    from e2e.worlds.test_filing import _open_velikoye

    _, thing = _open_velikoye(page, app, _world_name("SameRoom"))
    fixed_facts(
        {
            "facts": [
                {"category": "general", "text": "Tsar Ivan III rebuilt its walls."}
            ],
            "names": [{"name": "Tsar Ivan III", "kind": "character", "tag": "ruler"}],
        }
    )
    thing.get_by_test_id("add-facts").click()
    thing.get_by_test_id("add-facts-form").get_by_label("What to add").fill("its Tsars")
    thing.get_by_test_id("add-draft").click()
    row = thing.get_by_test_id("fact-draft").get_by_test_id("new-name-row").first
    same = row.get_by_test_id("stub-same")
    same.wait_for(state="visible", timeout=TIMEOUT_MS)
    kind = row.get_by_test_id("new-name-kind").bounding_box()
    assert same.bounding_box()["y"] >= kind["y"] + kind["height"] + 6


def test_other_tip_on_heading_only(app, page):
    _seeded(app, page, "OtherTip")
    vel = _open_thing(page, "Velikoye")
    other = vel.get_by_test_id("connected-group").filter(has_text="Other")
    other.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert other.get_attribute("title") is None
    assert "Dropped here" in (
        other.locator(".group-head").first.get_attribute("title") or ""
    )


def test_new_entry_path_opens(app, page, fixed_preview):
    """Final review I3: a new entry's page opens before the lists know it;
    the way to it in the tree opens once they do."""

    from e2e.worlds.test_drafts import _draft, _host
    from e2e.worlds.test_drafts import _seeded as _drafts_world

    _drafts_world(app, page, "NewPath")
    fixed_preview(_host("It stands guard.", **{"in": [{"entry": "Velikoye"}]}))
    draft = _draft(page, "place", "A watchtower in the capital.")
    draft.get_by_test_id("draft-in-row").filter(has_text="Velikoye").get_by_role(
        "checkbox"
    ).check()
    draft.get_by_test_id("draft-bar").get_by_role("button", name="Accept").click()
    page.get_by_test_id("thing-page").get_by_test_id("thing-name").filter(
        has_text="The Frostwing Host"
    ).wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(_names(page).filter(has_text="The Frostwing Host")).to_be_visible()


def test_error_under_dialogs(app, page):
    """Final review M2: an open dialog covers the error message, not the
    other way round."""

    _seeded(app, page, "ErrorDialog")
    velikoye = _open_thing(page, "Velikoye")
    _fail(page)
    error = page.get_by_test_id("world-error")
    error.wait_for(state="visible", timeout=TIMEOUT_MS)
    velikoye.get_by_role("button", name="Delete").click()
    page.locator(".v-overlay--active .v-overlay__scrim").first.wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    box = error.bounding_box()
    on_top = page.evaluate(
        "([x, y]) => !!document.elementFromPoint(x, y)?.closest('[data-testid=\"world-error\"]')",
        [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2],
    )
    assert not on_top
