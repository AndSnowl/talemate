"""Languages sections on entries (languages 3a, Task 10)."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from e2e.seed import seed_fm_world
from e2e.worlds.test_languages_page import _language_fields
from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)

pytestmark = pytest.mark.e2e


def _seed(app, stem):
    name = _world_name(stem)
    seed_fm_world(
        app.root,
        name,
        things=[
            {"kind": "language", "name": "Sorauan", "fields": _language_fields()},
            {"kind": "language", "name": "Moscavian", "fields": _language_fields()},
            {"kind": "place", "name": "Free Provinces of Sorau"},
            {
                "kind": "place",
                "name": "Thornfield",
                "filings": [{"target": "Free Provinces of Sorau"}],
            },
            {
                "kind": "character",
                "name": "Mira",
                "born": 990,
                "filings": [{"target": "Free Provinces of Sorau"}],
            },
        ],
    )
    return name


def _add_row(page, section, language, role, share=None, fluency=None):
    section.get_by_test_id("languages-add").click()
    form = section.get_by_test_id("languages-form")
    form.get_by_test_id("languages-language").click()
    page.get_by_role("option", name=language, exact=True).click()
    form.get_by_test_id("languages-role").click()
    page.get_by_role("option", name=role, exact=True).click()
    if share is not None:
        form.get_by_test_id("languages-share").locator("input").fill(str(share))
    if fluency is not None:
        form.get_by_test_id("languages-fluency").click()
        page.get_by_role("option", name=fluency, exact=True).click()
    form.get_by_role("button", name="Save").click()


def test_add_rows_then_inherit_and_set_its_own(app, page):
    name = _seed(app, "Lang rows")
    _open_world(page, name)
    _world_tab(page)

    sorau = _open_thing(page, "Free Provinces of Sorau")
    section = sorau.get_by_test_id("entry-languages")
    _add_row(page, section, "Sorauan", "official")
    expect(section.get_by_test_id("languages-row").filter(has_text="Sorauan")).to_contain_text(
        "official", timeout=TIMEOUT_MS
    )
    _add_row(page, section, "Moscavian", "spoken", share=25)
    expect(section.get_by_test_id("languages-row").filter(has_text="Moscavian")).to_contain_text(
        "25%", timeout=TIMEOUT_MS
    )

    town = _open_thing(page, "Thornfield")
    section = town.get_by_test_id("entry-languages")
    inherited = section.get_by_test_id("languages-inherited")
    expect(inherited).to_contain_text("From Free Provinces of Sorau", timeout=TIMEOUT_MS)
    expect(inherited).to_contain_text("Sorauan")
    section.get_by_role("button", name="Set its own").click()
    expect(section.get_by_test_id("languages-row")).to_have_count(2, timeout=TIMEOUT_MS)
    expect(section.get_by_test_id("languages-inherited")).to_have_count(0)


def test_character_fluency(app, page):
    name = _seed(app, "Lang fluency")
    _open_world(page, name)
    _world_tab(page)
    mira = _open_thing(page, "Mira")
    section = mira.get_by_test_id("entry-languages")
    _add_row(page, section, "Sorauan", "spoken", fluency="native")
    expect(section.get_by_test_id("languages-row")).to_contain_text("native", timeout=TIMEOUT_MS)
