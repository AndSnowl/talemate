"""A language's Language tab, in chapters (languages 3b-2a, Task 5 and the
owner's merge): Overview, Sounds, Names, then the grammar topics, one at
a time; cards with tables and word-by-word examples; old text grammar still
shows and edits."""

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

SECTIONS = [
    {
        "title": "Nouns",
        "topic": "nouns",
        "text": "Nouns are masculine or feminine.",
        "tables": [
            {
                "caption": "dov (shrine)",
                "columns": ["", "one", "more than one"],
                "rows": [["a", "dov", "dovy"], ["the", "doven"]],
            }
        ],
        "examples": [
            {
                "original": "Zorin doven stoi",
                "breakdown": [
                    ["zorin", "bright"],
                    ["doven", "shrine-the"],
                    ["stoi", "stands"],
                ],
                "translation": "The bright shrine stands.",
            }
        ],
    },
    {
        "title": "Articles live on the noun",
        "topic": "other",
        "text": "There's no word for 'the'.",
    },
]


SOUNDS = {
    "title": "Sounds and stress",
    "topic": "sounds",
    "text": "Stress falls on the last syllable.",
}
NAMES = {
    "title": "How names are built",
    "topic": "names",
    "text": "A father's name ends in -ovik.",
}


def _language_tab(app, page, stem, grammar):
    fields = _language_fields()
    fields["rules"] = {**fields["rules"], "grammar": grammar}
    name = _world_name(stem)
    seed_fm_world(
        app.root,
        name,
        things=[{"kind": "language", "name": "Velskar", "fields": fields}],
    )
    _open_world(page, name)
    _world_tab(page)
    thing = _open_thing(page, "Velskar")
    thing.get_by_test_id("language-tab-language").click()
    return thing


def _chapter(thing, title):
    chapters = thing.get_by_test_id("language-chapters")
    chapters.get_by_test_id("language-chapter").filter(has_text=title).first.click()


def test_the_language_tab_is_in_chapters(app, page):
    thing = _language_tab(app, page, "Lang chapters", [SOUNDS, NAMES, *SECTIONS])
    expect(thing.get_by_test_id("language-tab-grammar")).to_have_count(0)
    chapters = thing.get_by_test_id("language-chapters").get_by_test_id(
        "language-chapter"
    )
    expect(chapters).to_have_text(
        ["Overview", "Sounds", "Name rules", "Nouns", "Articles live on the noun"],
        timeout=TIMEOUT_MS,
    )
    # Overview first: how it sounds, and no grammar card
    expect(thing.get_by_test_id("language-sound-text")).to_be_visible()
    expect(thing.get_by_test_id("grammar-section")).to_have_count(0)
    # one grammar topic at a time
    _chapter(thing, "Nouns")
    cards = thing.get_by_test_id("grammar-section")
    expect(cards).to_have_count(1)
    expect(cards).to_contain_text("Nouns are masculine or feminine.")
    _chapter(thing, "Articles live on the noun")
    expect(cards).to_contain_text("There's no word for 'the'.", timeout=TIMEOUT_MS)
    expect(cards).not_to_contain_text("Nouns are masculine")


def test_sounds_and_names_hold_their_grammar(app, page):
    thing = _language_tab(app, page, "Lang sounds names", [SOUNDS, NAMES, *SECTIONS])
    _chapter(thing, "Sounds")
    expect(thing.get_by_test_id("language-inventory")).to_be_visible(timeout=TIMEOUT_MS)
    expect(thing.get_by_test_id("grammar-section")).to_contain_text(
        "Stress falls on the last syllable."
    )
    _chapter(thing, "Name rules")
    expect(thing.get_by_test_id("language-generator").first).to_be_visible(
        timeout=TIMEOUT_MS
    )
    expect(thing.get_by_test_id("grammar-section")).to_contain_text(
        "A father's name ends in -ovik."
    )
    expect(thing.get_by_test_id("language-inventory")).to_have_count(0)


def test_a_table_with_a_ragged_row_renders(app, page):
    thing = _language_tab(app, page, "Grammar ragged", SECTIONS)
    _chapter(thing, "Nouns")
    table = thing.get_by_test_id("grammar-table").first
    expect(table).to_contain_text("dov (shrine)", timeout=TIMEOUT_MS)
    rows = table.locator("tbody tr")
    expect(rows).to_have_count(2)
    expect(rows.nth(1).locator("td, th")).to_have_count(3)


def test_an_example_shows_word_over_meaning(app, page):
    thing = _language_tab(app, page, "Grammar example", SECTIONS)
    _chapter(thing, "Nouns")
    example = thing.get_by_test_id("grammar-example").first
    expect(example).to_contain_text("shrine-the", timeout=TIMEOUT_MS)
    expect(example).to_contain_text("The bright shrine stands.")


def test_an_old_text_grammar_shows_as_one_card_and_can_be_edited(app, page):
    thing = _language_tab(app, page, "Grammar old", "Verbs come last.")
    chapters = thing.get_by_test_id("language-chapters")
    # an older language's grammar isn't "unusual": it's just its grammar
    expect(chapters).not_to_contain_text("Unusual", timeout=TIMEOUT_MS)
    _chapter(thing, "Grammar")
    card = thing.get_by_test_id("grammar-section")
    expect(card).to_have_count(1, timeout=TIMEOUT_MS)
    expect(card).to_contain_text("Verbs come last.")
    expect(card).not_to_contain_text("unusual")
    card.get_by_test_id("grammar-edit-text").click()
    card.locator("textarea").first.fill("Verbs come last, always.")
    card.get_by_role("button", name="Save").click()
    expect(card).to_contain_text("Verbs come last, always.", timeout=TIMEOUT_MS)
    # the saved text is still there when the page is opened again
    thing.get_by_test_id("language-tab-about").click()
    thing.get_by_test_id("language-tab-language").click()
    _chapter(thing, "Grammar")
    expect(thing.get_by_test_id("grammar-section")).to_contain_text(
        "Verbs come last, always.", timeout=TIMEOUT_MS
    )


def test_the_side_column_keeps_its_height_whatever_the_page(app, page):
    long_text = "A long explanation. " * 300
    sections = [
        {"title": "Nouns", "topic": "nouns", "text": "Short."},
        {"title": "Verbs", "topic": "verbs", "text": long_text},
    ]
    thing = _language_tab(app, page, "Grammar height", sections)
    side = page.get_by_test_id("world-list")
    _chapter(thing, "Nouns")
    expect(thing.get_by_test_id("grammar-section")).to_contain_text(
        "Short.", timeout=TIMEOUT_MS
    )
    short = side.bounding_box()["height"]
    _chapter(thing, "Verbs")
    expect(thing.get_by_test_id("grammar-section")).to_contain_text(
        "A long explanation."
    )
    page.wait_for_timeout(300)
    assert side.bounding_box()["height"] == short


def test_the_names_chapter_uses_the_full_width(app, page):
    page.set_viewport_size({"width": 1920, "height": 1080})
    thing = _language_tab(app, page, "Names wide", [NAMES, *SECTIONS])
    _chapter(thing, "Name rules")
    expect(thing.get_by_test_id("language-generator").first).to_be_visible(
        timeout=TIMEOUT_MS
    )
    assert page.get_by_test_id("language-book").bounding_box()["width"] > 1240
    _chapter(thing, "Overview")
    page.wait_for_timeout(200)
    assert page.get_by_test_id("language-book").bounding_box()["width"] <= 1240
