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


# --- people's names (languages 4b-2, Task 8) --------------------------------


def test_people_names_card_shows_and_edits_address(app, page):
    from _people_names_helpers import DRASSONAIS

    thing = _names_chapter(app, page, "People names card", language=DRASSONAIS)
    card = thing.get_by_test_id("people-names-card")
    expect(card.get_by_test_id("people-names-choice")).to_have_count(
        2, timeout=TIMEOUT_MS
    )
    expect(card.get_by_test_id("people-names-kept")).to_contain_text("Tsar")
    family = card.get_by_test_id("people-names-address").filter(has_text="family")
    expect(family.get_by_test_id("people-names-address-example")).to_contain_text(
        "ette", timeout=TIMEOUT_MS
    )
    family.get_by_test_id("people-names-address-edit").click()
    uses = card.get_by_test_id("people-names-address-uses").locator("input")
    uses.fill("given")
    card.get_by_test_id("people-names-address-save").click()
    expect(
        card.get_by_test_id("people-names-address")
        .filter(has_text="family")
        .get_by_test_id("people-names-address-example")
    ).not_to_contain_text("ette", timeout=TIMEOUT_MS)


def test_a_language_without_people_names_offers_fill(app, page):
    thing = _names_chapter(app, page, "People names none")
    card = thing.get_by_test_id("people-names-card")
    expect(card.get_by_test_id("people-names-fill")).to_be_visible(timeout=TIMEOUT_MS)


def test_rule_chips_show_connection_and_english(app, page):
    from _people_names_helpers import DRASSONAIS

    thing = _names_chapter(app, page, "People rule chips", language=DRASSONAIS)
    rule = (
        thing.get_by_test_id("language-generator").filter(has_text="noble-women").first
    )
    expect(rule.get_by_test_id("rule-for-person")).to_have_text(
        "for: woman · noble", timeout=TIMEOUT_MS
    )
    chips = rule.get_by_test_id("rule-part")
    expect(chips.nth(1)).to_have_text("di → “of”")
    expect(chips.nth(2)).to_have_text("from father, then mother · house")


# --- main rules and pieces (languages 4c, Task 2) ----------------------------


def test_pieces_are_folded_below_the_main_rules(app, page):
    from _people_names_helpers import DRASSONAIS

    thing = _names_chapter(app, page, "Rules pieces", language=DRASSONAIS)
    rules = thing.get_by_test_id("language-generator")
    head = thing.get_by_test_id("language-pieces")
    expect(head).to_contain_text("Pieces (", timeout=TIMEOUT_MS)
    noble = rules.filter(has_text="noble-women").first
    piece = rules.filter(has_text="women-given").first
    expect(noble).to_be_visible()
    expect(piece).to_be_hidden()
    head.locator("span").first.click()
    expect(piece).to_be_visible(timeout=TIMEOUT_MS)
    expect(piece.get_by_test_id("rule-main")).to_have_text("piece")


def test_a_rule_description_is_edited_in_place(app, page):
    from _people_names_helpers import DRASSONAIS

    thing = _names_chapter(app, page, "Rules description", language=DRASSONAIS)
    noble = (
        thing.get_by_test_id("language-generator").filter(has_text="noble-women").first
    )
    noble.get_by_test_id("rule-description-edit").click()
    field = noble.get_by_test_id("rule-description-input").locator("input")
    field.fill("nobles of a house")
    field.press("Enter")
    expect(noble.get_by_test_id("rule-description")).to_contain_text(
        "nobles of a house", timeout=TIMEOUT_MS
    )
