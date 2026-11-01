"""Right-click naming from a language (languages 3a, Task 11)."""

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
            {"kind": "place", "name": "Free Provinces of Sorau"},
        ],
    )
    return name


def _place_box(page):
    page.get_by_test_id("kind-place").click()
    box = page.get_by_test_id("create-box").locator("textarea").first
    box.wait_for(state="visible", timeout=TIMEOUT_MS)
    return box


def _right_click(box, start=None, end=None):
    if start is not None:
        box.evaluate(f"(el) => {{ el.focus(); el.setSelectionRange({start}, {end}); }}")
    else:
        box.evaluate(
            "(el) => { el.focus(); el.setSelectionRange(el.value.length, el.value.length); }"
        )
    box.dispatch_event("contextmenu", {"clientX": 400, "clientY": 300, "button": 2})


def _pick_language(page, menu, language="Sorauan"):
    picker = menu.get_by_test_id("language-picker")
    picker.wait_for(state="visible", timeout=TIMEOUT_MS)
    picker.get_by_text(language, exact=True).click()


def _words(page, language):
    thing = _open_thing(page, language)
    thing.get_by_test_id("language-tab-lexicon").click()
    words = thing.get_by_test_id("language-words")
    words.get_by_test_id("language-word").first.wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    return [
        row.locator("td").first.inner_text().strip()
        for row in words.get_by_test_id("language-word").all()
    ]


def test_add_selected_word_with_definition(app, page, fixed_language):
    fixed_language({"definitions": {"Moscavia": "The nation's own name."}})
    name = _seed(app, "Name add")
    _open_world(page, name)
    _world_tab(page)
    box = _place_box(page)
    box.fill("Tsardom of Moscavia")
    _right_click(box, 11, 19)
    menu = page.get_by_test_id("reference-menu")
    menu.get_by_text('Add "Moscavia" to a language…').click()
    _pick_language(page, menu)
    meaning = menu.get_by_test_id("language-word-meaning").locator("input")
    expect(meaning).to_have_value("The nation's own name.", timeout=TIMEOUT_MS)
    menu.get_by_role("button", name="Save").click()
    assert "Moscavia" in _words(page, "Sorauan")


def test_name_it_in_other_language(app, page, fixed_language):
    fixed_language({"definitions": {}, "pick": "", "why": ""})
    name = _seed(app, "Name in")
    _open_world(page, name)
    _world_tab(page)
    sorau = _open_thing(page, "Free Provinces of Sorau")
    sorau.get_by_test_id("name-it-in").click()
    page.get_by_role("menuitem", name="Sorauan").click()
    review = page.get_by_test_id("name-in-review")
    # "Free" is the sample language's "sel"; the other words are rolled
    expect(review).to_contain_text("Sel", timeout=TIMEOUT_MS)
    proposed = review.get_by_test_id("name-in-name").inner_text()
    review.get_by_role("button", name="Keep it").click()
    names = sorau.get_by_test_id("thing-other-names")
    expect(names).to_contain_text(proposed, timeout=TIMEOUT_MS)
    expect(names).to_contain_text("Sorauan")


def test_add_a_word_with_no_meaning(app, page, fixed_language):
    # a word made only to be a name has no meaning, and that's allowed
    fixed_language({"definitions": {"Moscavia": ""}})
    name = _seed(app, "Name bare")
    _open_world(page, name)
    _world_tab(page)
    box = _place_box(page)
    box.fill("Tsardom of Moscavia")
    _right_click(box, 11, 19)
    menu = page.get_by_test_id("reference-menu")
    menu.get_by_text('Add "Moscavia" to a language…').click()
    _pick_language(page, menu)
    meaning = menu.get_by_test_id("language-word-meaning").locator("input")
    expect(meaning).to_have_attribute(
        "placeholder", "leave blank if it is only a name", timeout=TIMEOUT_MS
    )
    expect(meaning).to_have_value("")
    menu.get_by_role("button", name="Save").click()
    assert "Moscavia" in _words(page, "Sorauan")
    row = page.get_by_test_id("language-word").filter(has_text="Moscavia")
    expect(row.get_by_test_id("word-meaning")).to_have_count(0)


def test_make_a_phrase_inserts_once_and_closes(app, page):
    name = _seed(app, "Name phrase")
    _open_world(page, name)
    _world_tab(page)
    box = _place_box(page)
    box.fill("They cursed: ")
    _right_click(box)
    menu = page.get_by_test_id("reference-menu")
    menu.get_by_test_id("menu-make-phrase").click()
    _pick_language(page, menu)
    menu.get_by_test_id("language-phrase-pick").filter(has_text="Kor vel!").click()
    expect(box).to_have_value("They cursed: Kor vel!", timeout=TIMEOUT_MS)
    expect(page.get_by_test_id("reference-menu")).to_have_count(0, timeout=TIMEOUT_MS)


def test_name_it_in_lets_the_owner_type_the_name(app, page, fixed_language):
    fixed_language({"definitions": {}, "pick": "", "why": ""})
    name = _seed(app, "Name in typed")
    _open_world(page, name)
    _world_tab(page)
    sorau = _open_thing(page, "Free Provinces of Sorau")
    sorau.get_by_test_id("name-it-in").click()
    page.get_by_role("menuitem", name="Sorauan").click()
    review = page.get_by_test_id("name-in-review")
    field = review.get_by_test_id("name-in-edit").locator("input")
    field.wait_for(state="visible", timeout=TIMEOUT_MS)
    field.fill("Sel Provanna")
    review.get_by_role("button", name="Keep it").click()
    expect(sorau.get_by_test_id("thing-other-names")).to_contain_text(
        "Sel Provanna", timeout=TIMEOUT_MS
    )


def test_name_it_inserts_at_the_cursor_and_saves_the_word(app, page):
    """4a revised: Name it… replaces "Make a name…" in world boxes."""

    name = _seed(app, "Name it box")
    _open_world(page, name)
    _world_tab(page)
    box = _place_box(page)
    box.fill("Tsardom of ")
    _right_click(box)
    menu = page.get_by_test_id("reference-menu")
    expect(menu.get_by_test_id("menu-make-name")).to_have_count(0)
    menu.get_by_test_id("menu-name-it").click()
    panel = page.get_by_test_id("name-it")
    names = panel.get_by_test_id("name-it-name")
    expect(names.first).to_be_visible(timeout=TIMEOUT_MS)
    picked = names.first.inner_text().strip()
    names.first.click()
    expect(box).to_have_value(f"Tsardom of {picked}", timeout=TIMEOUT_MS)
    assert picked in _words(page, "Sorauan")


def test_name_it_replaces_the_selected_part(app, page):
    name = _seed(app, "Name it part")
    _open_world(page, name)
    _world_tab(page)
    box = _place_box(page)
    box.fill("Tsardom of Moscavia")
    _right_click(box, 11, 19)
    menu = page.get_by_test_id("reference-menu")
    expect(menu.get_by_test_id("menu-reroll-part")).to_have_count(0)
    menu.get_by_test_id("menu-name-it").click()
    panel = page.get_by_test_id("name-it")
    expect(panel).to_contain_text("Moscavia")
    names = panel.get_by_test_id("name-it-name")
    expect(names.first).to_be_visible(timeout=TIMEOUT_MS)
    picked = names.nth(1).inner_text().strip()
    names.nth(1).click()
    expect(box).to_have_value(f"Tsardom of {picked}", timeout=TIMEOUT_MS)
