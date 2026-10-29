"""A language's Grammar tab (languages 3b-2a, Task 5): topics, cards,
tables and word-by-word examples; old text grammar still shows and edits."""

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
                "breakdown": [["zorin", "bright"], ["doven", "shrine-the"], ["stoi", "stands"]],
                "translation": "The bright shrine stands.",
            }
        ],
    },
    {"title": "Articles live on the noun", "topic": "other", "text": "There's no word for 'the'."},
]


def _grammar_tab(app, page, stem, grammar):
    fields = _language_fields()
    fields["rules"] = {**fields["rules"], "grammar": grammar}
    name = _world_name(stem)
    seed_fm_world(app.root, name, things=[{"kind": "language", "name": "Velskar", "fields": fields}])
    _open_world(page, name)
    _world_tab(page)
    thing = _open_thing(page, "Velskar")
    thing.get_by_test_id("language-tab-grammar").click()
    return thing


def test_the_grammar_tab_lists_topics_and_cards(app, page):
    thing = _grammar_tab(app, page, "Grammar tab", SECTIONS)
    topics = thing.get_by_test_id("grammar-topics")
    expect(topics).to_contain_text("Nouns", timeout=TIMEOUT_MS)
    expect(topics).to_contain_text("Articles live on the noun")
    # one topic at a time: the first is shown, and picking another shows it
    cards = thing.get_by_test_id("grammar-section")
    expect(cards).to_have_count(1)
    expect(cards).to_contain_text("Nouns are masculine or feminine.")
    topics.get_by_test_id("grammar-topic").filter(has_text="Articles live on the noun").click()
    expect(cards).to_have_count(1)
    expect(cards).to_contain_text("There's no word for 'the'.", timeout=TIMEOUT_MS)
    expect(cards).not_to_contain_text("Nouns are masculine")


def test_a_table_with_a_ragged_row_renders(app, page):
    thing = _grammar_tab(app, page, "Grammar ragged", SECTIONS)
    table = thing.get_by_test_id("grammar-table").first
    expect(table).to_contain_text("dov (shrine)", timeout=TIMEOUT_MS)
    rows = table.locator("tbody tr")
    expect(rows).to_have_count(2)
    expect(rows.nth(1).locator("td, th")).to_have_count(3)


def test_an_example_shows_word_over_meaning(app, page):
    thing = _grammar_tab(app, page, "Grammar example", SECTIONS)
    example = thing.get_by_test_id("grammar-example").first
    expect(example).to_contain_text("shrine-the", timeout=TIMEOUT_MS)
    expect(example).to_contain_text("The bright shrine stands.")


def test_an_old_text_grammar_shows_as_one_card_and_can_be_edited(app, page):
    thing = _grammar_tab(app, page, "Grammar old", "Verbs come last.")
    card = thing.get_by_test_id("grammar-section")
    expect(card).to_have_count(1, timeout=TIMEOUT_MS)
    expect(card).to_contain_text("Verbs come last.")
    # an older language's grammar isn't "unusual": it's just its grammar
    expect(card).not_to_contain_text("unusual")
    expect(thing.get_by_test_id("grammar-topics")).not_to_contain_text("Unusual")
    card.get_by_test_id("grammar-edit-text").click()
    card.locator("textarea").first.fill("Verbs come last, always.")
    card.get_by_role("button", name="Save").click()
    expect(card).to_contain_text("Verbs come last, always.", timeout=TIMEOUT_MS)
    # the saved text is still there when the page is opened again
    thing.get_by_test_id("language-tab-about").click()
    thing.get_by_test_id("language-tab-grammar").click()
    expect(thing.get_by_test_id("grammar-section")).to_contain_text(
        "Verbs come last, always.", timeout=TIMEOUT_MS
    )


def test_the_language_tab_no_longer_shows_grammar_notes(app, page):
    thing = _grammar_tab(app, page, "Grammar moved", SECTIONS)
    thing.get_by_test_id("language-tab-language").click()
    expect(thing.get_by_test_id("language-grammar")).to_have_count(0)
    expect(thing.get_by_text("Nouns are masculine or feminine.")).to_have_count(0)


def test_the_side_column_keeps_its_height_whatever_the_page(app, page):
    long_text = "A long explanation. " * 300
    sections = [
        {"title": "Nouns", "topic": "nouns", "text": "Short."},
        {"title": "Verbs", "topic": "verbs", "text": long_text},
    ]
    thing = _grammar_tab(app, page, "Grammar height", sections)
    side = page.get_by_test_id("world-list")
    expect(thing.get_by_test_id("grammar-section")).to_contain_text("Short.", timeout=TIMEOUT_MS)
    short = side.bounding_box()["height"]
    thing.get_by_test_id("grammar-topic").filter(has_text="Verbs").click()
    expect(thing.get_by_test_id("grammar-section")).to_contain_text("A long explanation.")
    page.wait_for_timeout(300)
    assert side.bounding_box()["height"] == short
