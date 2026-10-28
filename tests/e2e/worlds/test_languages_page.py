"""The language page and importing a language (languages 3a, Task 9)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import expect

from e2e.seed import seed_fm_world
from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)

pytestmark = pytest.mark.e2e

SAMPLE = Path(__file__).resolve().parents[2] / "languages" / "data" / "sample.language.json"


def _sample_text(**changes) -> str:
    data = json.loads(SAMPLE.read_text())
    data["language"].update(changes)
    return json.dumps(data)


def _language_fields() -> dict:
    """The sample language as entry fields (`languages.entry.fields_of`)."""
    lang = json.loads(SAMPLE.read_text())["language"]
    return {
        "depth": lang["level"],
        "flavour": lang["flavour"],
        "sound": lang["sound"],
        "rules": {
            "categories": lang["categories"],
            "generators": lang["generators"],
            "grammar": lang["grammar"],
        },
        "words": lang["dictionary"],
        "phrases": lang["phrases"],
    }


def _open_languages(page):
    page.get_by_test_id("kind-language").click()
    box = page.get_by_test_id("language-import")
    box.wait_for(state="visible", timeout=TIMEOUT_MS)
    return box


def test_import_pasted_language_and_see_its_page(app, page):
    name = _world_name("Lang import")
    seed_fm_world(app.root, name)
    _open_world(page, name)
    _world_tab(page)
    box = _open_languages(page)

    box.get_by_test_id("language-paste").locator("textarea").first.fill(
        "Here's your language:\n```json\n" + _sample_text() + "\n```\nEnjoy!"
    )
    box.get_by_role("button", name="Check").click()
    preview = box.get_by_test_id("language-preview")
    expect(preview).to_contain_text("Velskar", timeout=TIMEOUT_MS)
    expect(preview.get_by_test_id("language-samples")).to_be_visible()
    box.get_by_role("button", name="Import").click()

    thing = page.get_by_test_id("thing-page")
    expect(thing.get_by_test_id("thing-name")).to_have_text("Velskar", timeout=TIMEOUT_MS)
    words = thing.get_by_test_id("language-words")
    expect(words).to_contain_text("veltasun")
    expect(words).to_contain_text("the great fort")


def test_blocking_problem_disables_import(app, page):
    name = _world_name("Lang blocked")
    seed_fm_world(app.root, name)
    _open_world(page, name)
    _world_tab(page)
    box = _open_languages(page)

    data = json.loads(SAMPLE.read_text())
    data["language"]["generators"][0]["reject"] = ["("]
    box.get_by_test_id("language-paste").locator("textarea").first.fill(json.dumps(data))
    box.get_by_role("button", name="Check").click()
    report = box.get_by_test_id("language-report")
    expect(report).to_contain_text("must be fixed", timeout=TIMEOUT_MS)
    expect(box.get_by_role("button", name="Import")).to_be_disabled()
    expect(report.get_by_role("button", name="Copy note")).to_be_visible()


def test_new_version_shows_kept_used_words(app, page):
    name = _world_name("Lang version")
    seed_fm_world(
        app.root,
        name,
        things=[
            {"kind": "language", "name": "Velskar", "fields": _language_fields()},
            {"kind": "place", "name": "Veltasun"},
        ],
    )
    _open_world(page, name)
    _world_tab(page)
    thing = _open_thing(page, "Velskar")
    expect(thing.get_by_test_id("language-samples")).to_be_visible(timeout=TIMEOUT_MS)

    data = json.loads(SAMPLE.read_text())
    data["language"]["dictionary"] = [
        w for w in data["language"]["dictionary"] if w["word"] != "veltasun"
    ]
    thing.get_by_role("button", name="Import a new version").click()
    box = thing.get_by_test_id("language-import")
    box.get_by_test_id("language-paste").locator("textarea").first.fill(json.dumps(data))
    box.get_by_role("button", name="Check").click()
    expect(box.get_by_test_id("language-diff")).to_contain_text("veltasun", timeout=TIMEOUT_MS)
    expect(box.get_by_test_id("language-diff")).to_contain_text("kept because")
