"""The Names chapter's grammar for names and composed rules (languages
4b-1, Task 5; mockup docs/superpowers/mockups/2026-11-02-languages-4b1-names-chapter.html)."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from talemate.languages.entry import fields_of
from talemate.languages.models import (
    DictionaryEntry,
    FormChange,
    GeneratorDef,
    GrammarSection,
    GrammarTable,
    Language,
    NameGrammar,
    NamePart,
    NameShape,
)

from e2e.seed import seed_fm_world
from e2e.worlds.test_languages_page import _chapter
from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)

pytestmark = pytest.mark.e2e

GRAMMAR = NameGrammar(
    describing="before",
    the=[
        FormChange(when="after_vowel", kind="ending", text="k"),
        FormChange(kind="ending", text="ek"),
    ],
    more_than_one=[FormChange(kind="ending", text="i")],
)
VAROVNI = Language(
    name="Varovni",
    level="full",
    categories={"C": "k v d z", "V": "a e i o u"},
    generators=[
        GeneratorDef(id="men", name="Men's names", use="character", patterns=["CVCVk"]),
        GeneratorDef(
            id="owl",
            name="Owl-names",
            use="character",
            shapes=[
                NameShape(
                    parts=[
                        NamePart(kind="rule", rule="men"),
                        NamePart(kind="word", word="Ul"),
                        NamePart(kind="meaning", forms=["more_than_one"]),
                    ]
                )
            ],
        ),
    ],
    dictionary=[
        DictionaryEntry(word="skelt", meanings=["stone"], part="noun"),
        DictionaryEntry(word="ulkha", meanings=["owl"], part="noun"),
        DictionaryEntry(word="ilvo", meanings=["white"], part="adjective"),
    ],
    grammar=[
        GrammarSection(
            title="Nouns",
            topic="nouns",
            text="Nouns take -ek for the.",
            tables=[GrammarTable(caption="skelt (stone)", columns=[], rows=[])],
        )
    ],
    name_grammar=GRAMMAR,
)


def _names_chapter(app, page, stem, language=VAROVNI):
    name = _world_name(stem)
    seed_fm_world(
        app.root,
        name,
        things=[
            {
                "kind": "language",
                "name": language.name,
                "fields": {"name": language.name, **fields_of(language)},
            }
        ],
    )
    _open_world(page, name)
    _world_tab(page)
    thing = _open_thing(page, language.name)
    thing.get_by_test_id("language-tab-language").click()
    _chapter(thing, "Name rules")
    return thing


def test_names_chapter_shows_the_grammar_rows(app, page):
    thing = _names_chapter(app, page, "Names grammar rows")
    card = thing.get_by_test_id("name-grammar")
    row = card.get_by_test_id("name-grammar-row").filter(has_text='"the"')
    expect(row).to_contain_text("skelt → skeltek", timeout=TIMEOUT_MS)


def test_editing_a_row_rebuilds_its_example(app, page):
    thing = _names_chapter(app, page, "Names grammar edit")
    card = thing.get_by_test_id("name-grammar")
    row = card.get_by_test_id("name-grammar-row").filter(has_text="Describing words")
    expect(row).to_contain_text("ilvo skelt", timeout=TIMEOUT_MS)
    row.get_by_test_id("name-grammar-edit").click()
    row.get_by_test_id("name-grammar-describing").click()
    page.get_by_role("option", name="after the noun").click()
    row.get_by_role("button", name="Save").click()
    expect(row).to_contain_text("skelt ilvo", timeout=TIMEOUT_MS)


def test_a_language_without_grammar_offers_fill_them_in(app, page):
    thing = _names_chapter(
        app,
        page,
        "Names grammar none",
        VAROVNI.model_copy(update={"name_grammar": None}),
    )
    card = thing.get_by_test_id("name-grammar")
    expect(card).to_contain_text(
        "No grammar for names yet: names are built in your word order",
        timeout=TIMEOUT_MS,
    )
    expect(card.get_by_test_id("name-grammar-fill")).to_be_visible()


def test_a_composed_rule_shows_its_parts(app, page):
    thing = _names_chapter(app, page, "Names composed parts")
    rule = thing.get_by_test_id("language-generator").filter(has_text="Owl-names")
    parts = rule.get_by_test_id("rule-part")
    expect(parts).to_have_text(
        ["Men's names", "Ul", "a meaning · plural"], timeout=TIMEOUT_MS
    )
