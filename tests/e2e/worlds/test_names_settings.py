"""The Names page in the world's Settings (languages 4a, Task 9; mockup
2A): the app's rows and this world's together, each marked; Make it
global, Remove, Turn off here, and Remove everywhere behind a confirm.
App-wide edits use made-up names: the app's config is shared by the
tests on a worker."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from e2e.seed import seed_fm_world
from e2e.worlds.test_world_tab import TIMEOUT_MS, _open_world, _world_name, _world_tab

pytestmark = pytest.mark.e2e


def _names_page(app, page, stem):
    name = _world_name(stem)
    seed_fm_world(app.root, name)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-settings").click()
    page.get_by_test_id("names-tab").click()
    return page.get_by_test_id("names-settings")


def _row(panel, name):
    return panel.get_by_test_id("names-row").filter(has_text=name).first


def _add(panel, name):
    panel.get_by_test_id("names-add").click()
    field = panel.get_by_test_id("names-add-field").locator("input")
    field.fill(name)
    field.press("Enter")


def test_the_settings_tab_has_general_and_names(app, page):
    names = _names_page(app, page, "Names tabs")
    expect(names).to_be_visible(timeout=TIMEOUT_MS)
    page.get_by_test_id("general-tab").click()
    expect(page.get_by_test_id("curation-settings")).to_be_visible(timeout=TIMEOUT_MS)


def test_the_names_page_shows_app_and_world_rows(app, page):
    names = _names_page(app, page, "Names rows")
    replace = names.get_by_test_id("names-replace")
    expect(_row(replace, "Novgorod")).to_contain_text("all worlds", timeout=TIMEOUT_MS)
    _add(replace, "Yelena")
    expect(_row(replace, "Yelena")).to_contain_text("this world", timeout=TIMEOUT_MS)


def test_add_then_make_it_global(app, page):
    names = _names_page(app, page, "Names global")
    keep = names.get_by_test_id("names-keep")
    _add(keep, "Zorvanikgrad")
    row = _row(keep, "Zorvanikgrad")
    expect(row).to_contain_text("this world", timeout=TIMEOUT_MS)
    row.get_by_test_id("names-global").click()
    expect(_row(keep, "Zorvanikgrad")).to_contain_text("all worlds", timeout=TIMEOUT_MS)
    # tidy: the app's config is shared
    _row(keep, "Zorvanikgrad").get_by_test_id("names-remove-everywhere").click()
    page.get_by_test_id("names-confirm-remove").click()
    expect(
        keep.get_by_test_id("names-row").filter(has_text="Zorvanikgrad")
    ).to_have_count(0, timeout=TIMEOUT_MS)


def test_turn_off_here_keeps_it_for_other_worlds(app, page):
    names = _names_page(app, page, "Names off")
    replace = names.get_by_test_id("names-replace")
    _row(replace, "Moscow").get_by_test_id("names-off").click()
    expect(_row(replace, "Moscow").get_by_test_id("names-off-chip")).to_be_visible(
        timeout=TIMEOUT_MS
    )
    page.get_by_role("tab", name="Worlds", exact=True).click()
    other = _names_page(app, page, "Names off other")
    row = _row(other.get_by_test_id("names-replace"), "Moscow")
    expect(row).to_be_visible(timeout=TIMEOUT_MS)
    expect(row.get_by_test_id("names-off-chip")).to_have_count(0)


def test_remove_everywhere_asks_first(app, page):
    names = _names_page(app, page, "Names everywhere")
    keep = names.get_by_test_id("names-keep")
    _add(keep, "Kvelmorask")
    _row(keep, "Kvelmorask").get_by_test_id("names-global").click()
    expect(_row(keep, "Kvelmorask")).to_contain_text("all worlds", timeout=TIMEOUT_MS)
    _row(keep, "Kvelmorask").get_by_test_id("names-remove-everywhere").click()
    page.get_by_test_id("names-cancel-remove").click()
    expect(_row(keep, "Kvelmorask")).to_be_visible()
    _row(keep, "Kvelmorask").get_by_test_id("names-remove-everywhere").click()
    page.get_by_test_id("names-confirm-remove").click()
    expect(
        keep.get_by_test_id("names-row").filter(has_text="Kvelmorask")
    ).to_have_count(0, timeout=TIMEOUT_MS)
