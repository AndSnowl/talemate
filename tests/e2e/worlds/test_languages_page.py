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
    # About (facts and connections) is the default tab
    expect(thing.get_by_test_id("language-tab-about")).to_have_attribute("aria-selected", "true")
    thing.get_by_test_id("language-tab-lexicon").click()
    words = thing.get_by_test_id("language-words")
    expect(words.get_by_test_id("language-word")).to_have_count(8, timeout=TIMEOUT_MS)
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
    thing.get_by_test_id("language-tab-language").click()
    expect(thing.get_by_test_id("language-generator").first).to_contain_text(
        "Words", timeout=TIMEOUT_MS
    )
    thing.get_by_test_id("language-tab-language").click()
    expect(thing.get_by_test_id("language-inventory")).to_contain_text("C")

    data = json.loads(SAMPLE.read_text())
    data["language"]["dictionary"] = [
        w for w in data["language"]["dictionary"] if w["word"] != "veltasun"
    ]
    thing.get_by_role("button", name="Import a new version").click()
    # the import box sits on the Language tab
    box = thing.get_by_test_id("language-import")
    box.get_by_test_id("language-paste").locator("textarea").first.fill(json.dumps(data))
    box.get_by_role("button", name="Check").click()
    expect(box.get_by_test_id("language-diff")).to_contain_text("veltasun", timeout=TIMEOUT_MS)
    expect(box.get_by_test_id("language-diff")).to_contain_text("kept because")

    # importing it keeps the word the world uses, with its meaning
    box.get_by_role("button", name="Import").click()
    expect(thing.get_by_test_id("language-import")).to_have_count(0, timeout=TIMEOUT_MS)
    thing.get_by_test_id("language-tab-lexicon").click()
    row = thing.get_by_test_id("language-word").filter(has_text="veltasun")
    expect(row.get_by_test_id("word-meaning")).to_have_text(["the great fort"], timeout=TIMEOUT_MS)
    expect(row.get_by_test_id("word-names")).to_have_text("name")


def test_phrases_tab_shows_breakdown_and_adds_a_phrase(app, page):
    name = _world_name("Lang phrases")
    seed_fm_world(
        app.root,
        name,
        things=[{"kind": "language", "name": "Velskar", "fields": _language_fields()}],
    )
    _open_world(page, name)
    _world_tab(page)
    thing = _open_thing(page, "Velskar")
    thing.get_by_test_id("language-tab-lexicon").click()
    phrases = thing.get_by_test_id("language-phrases")
    expect(phrases).to_contain_text("Kor vel!", timeout=TIMEOUT_MS)
    phrases.get_by_role("button", name="Add phrase").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Category (greeting, curse, saying…)").fill("blessing")
    dialog.get_by_label("In the language").fill("Sel kor.")
    dialog.get_by_label("Translation").fill("A free river.")
    dialog.get_by_role("button", name="Save").click()
    expect(phrases).to_contain_text("A free river.", timeout=TIMEOUT_MS)


def test_a_word_shows_its_meanings_and_what_it_names(app, page):
    name = _world_name("Lang meanings")
    fields = _language_fields()
    fields["words"] = [
        *fields["words"],
        {"word": "soru", "meanings": ["wind", "breath"]},
        # an older row carrying both keys: the old meaning still shows
        {"word": "brin", "meanings": [], "meaning": "stone"},
    ]
    seed_fm_world(
        app.root,
        name,
        things=[
            {"kind": "language", "name": "Velskar", "fields": fields},
            {"kind": "character", "name": "Soru", "born": 990},
        ],
    )
    _open_world(page, name)
    _world_tab(page)
    thing = _open_thing(page, "Velskar")
    thing.get_by_test_id("language-tab-lexicon").click()
    row = thing.get_by_test_id("language-word").filter(has_text="soru")
    expect(row.get_by_test_id("word-meaning")).to_have_text(["wind", "breath"], timeout=TIMEOUT_MS)
    expect(row.get_by_test_id("word-names")).to_have_text("name")
    expect(row.get_by_test_id("word-names")).to_have_attribute("title", "Soru (character)")
    brin = thing.get_by_test_id("language-word").filter(has_text="brin")
    expect(brin.get_by_test_id("word-meaning")).to_have_text(["stone"])

    # + adds a meaning beside the others
    row.get_by_test_id("add-meaning").click()
    row.get_by_label("new meaning").fill("gale")
    row.get_by_label("new meaning").press("Enter")
    expect(row.get_by_test_id("word-meaning")).to_have_text(["wind", "breath", "gale"], timeout=TIMEOUT_MS)

    # × removes one
    row.get_by_label("Remove meaning breath").click()
    expect(row.get_by_test_id("word-meaning")).to_have_text(["wind", "gale"], timeout=TIMEOUT_MS)

    # clicking a meaning edits it
    row.get_by_test_id("word-meaning").filter(has_text="gale").click()
    row.get_by_label("meaning", exact=True).fill("storm")
    row.get_by_label("meaning", exact=True).press("Enter")
    expect(row.get_by_test_id("word-meaning")).to_have_text(["wind", "storm"], timeout=TIMEOUT_MS)

    # and it's saved: leaving the page and coming back rebuilds it from the store
    _open_thing(page, "Soru")
    thing = _open_thing(page, "Velskar")
    thing.get_by_test_id("language-tab-lexicon").click()
    row = thing.get_by_test_id("language-word").filter(has_text="soru")
    expect(row.get_by_test_id("word-meaning")).to_have_text(["wind", "storm"], timeout=TIMEOUT_MS)


def test_a_rule_sets_roll_rolls_only_its_own_names(app, page):
    name = _world_name("Lang roll one")
    seed_fm_world(
        app.root, name, things=[{"kind": "language", "name": "Velskar", "fields": _language_fields()}]
    )
    _open_world(page, name)
    _world_tab(page)
    thing = _open_thing(page, "Velskar")
    thing.get_by_test_id("language-tab-language").click()
    cards = thing.get_by_test_id("language-generator")
    expect(cards.first.get_by_test_id("language-samples")).not_to_have_text(
        "Roll to see names.", timeout=TIMEOUT_MS
    )
    first_before = cards.nth(0).get_by_test_id("language-samples").inner_text()
    second_before = cards.nth(1).get_by_test_id("language-samples").inner_text()
    cards.nth(0).get_by_role("button", name="Roll").click()
    expect(cards.nth(0).get_by_test_id("language-samples")).not_to_have_text(
        first_before, timeout=TIMEOUT_MS
    )
    page.wait_for_timeout(500)
    assert cards.nth(1).get_by_test_id("language-samples").inner_text() == second_before
