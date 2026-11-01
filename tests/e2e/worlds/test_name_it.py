"""Name it… (languages 4a revised, Task 5; mockup frames 2 and 3): a
panel with the rule shown, a batch of ten with Reroll, one pattern, and
From a meaning; from a flag, a draft's selection, and an entry's name."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

from talemate.languages.entry import fields_of
from talemate.languages.models import DictionaryEntry, GeneratorDef, Language

from e2e.seed import seed_fm_world
from e2e.worlds.test_clean_names import _card
from e2e.worlds.test_drafts import _draft, _draft_fact, _select
from e2e.worlds.test_new_scene import SEND_SPY_JS
from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)

pytestmark = pytest.mark.e2e

OTSYENYAN = Language(
    name="Otsyenyan",
    level="full",
    categories={"C": "k v r s l d z n", "V": "a o e i u"},
    generators=[
        GeneratorDef(id="words", name="Words", use="words", patterns=["CVCV"]),
        GeneratorDef(
            id="places",
            name="Place names",
            use="place",
            patterns=["CVCVgrad", "[kolva|syev]insk"],
        ),
    ],
    dictionary=[
        DictionaryEntry(word="syev", meanings=["grey"]),
        DictionaryEntry(word="kolva", meanings=["hill"]),
    ],
)
DRAFT = {
    "name": "Tsardom of Otsyenya",
    "facts": [
        {"category": "description", "text": "Fur caravans trade with Novgorod."},
        {
            "category": "history",
            "text": "It borders the Duchies of the Greywash Coast.",
        },
    ],
    "names": [
        {"name": "Novgorod", "kind": "place"},
        {"name": "Duchies of the Greywash Coast", "kind": "place"},
    ],
    "prose": {},
}
CLEAN = {
    "language-roles": {"languages": [{"language": "Otsyenyan", "role": "official"}]},
    "name-flags": {"names": []},
}


def _world(app, page, stem, things=()):
    name = _world_name(stem)
    seeded = seed_fm_world(
        app.root,
        name,
        things=[
            {
                "kind": "language",
                "name": "Otsyenyan",
                "fields": {"name": "Otsyenyan", **fields_of(OTSYENYAN)},
            },
            *things,
        ],
    )
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    return seeded


def _draft_page(app, page, fixed_preview, fixed_clean, stem):
    _world(app, page, stem)
    fixed_preview(DRAFT)
    fixed_clean(CLEAN)
    return _draft(page, "place", "Tsardom of Otsyenya, a cold realm")


def _panel(page):
    panel = page.get_by_test_id("name-it")
    expect(panel.get_by_test_id("name-it-name").first).to_be_visible(timeout=TIMEOUT_MS)
    return panel


def _names(panel):
    return [n.strip() for n in panel.get_by_test_id("name-it-name").all_inner_texts()]


def test_name_it_from_a_flag_renames_every_place_in_the_draft(
    app, page, fixed_preview, fixed_clean
):
    draft = _draft_page(app, page, fixed_preview, fixed_clean, "Name it flag")
    _card(page, draft, "Novgorod").get_by_test_id("flag-name-it").click()
    panel = _panel(page)
    picked = _names(panel)[0]
    panel.get_by_test_id("name-it-name").first.click()
    expect(_draft_fact(draft, "Fur caravans")).to_contain_text(
        f"trade with {picked}.", timeout=TIMEOUT_MS
    )
    rows = draft.get_by_test_id("new-name-row")
    expect(rows.filter(has_text=picked)).to_have_count(1)
    expect(rows.filter(has_text="Novgorod")).to_have_count(0)


def test_reroll_gives_a_new_batch_each_click(app, page, fixed_preview, fixed_clean):
    draft = _draft_page(app, page, fixed_preview, fixed_clean, "Name it reroll")
    _card(page, draft, "Novgorod").get_by_test_id("flag-name-it").click()
    panel = _panel(page)
    first = _names(panel)
    assert len(first) == 10
    panel.get_by_test_id("name-it-reroll").click()
    # the whole batch changes (one name may come round again by chance)
    for _ in range(60):
        if _names(panel) != first:
            break
        page.wait_for_timeout(250)
    assert _names(panel) != first


def test_one_pattern_narrows_the_batch(app, page, fixed_preview, fixed_clean):
    draft = _draft_page(app, page, fixed_preview, fixed_clean, "Name it pattern")
    _card(page, draft, "Novgorod").get_by_test_id("flag-name-it").click()
    panel = _panel(page)
    panel.get_by_test_id("name-it-pattern").click()
    page.get_by_role("option", name="[kolva|syev]insk").click()
    expect(panel.get_by_test_id("name-it-name")).to_have_count(2, timeout=TIMEOUT_MS)
    assert sorted(_names(panel)) == ["Kolvainsk", "Syevinsk"]
    expect(panel).to_contain_text("kolva “hill”")


def test_from_a_meaning_shows_what_it_is_built_from(
    app, page, fixed_preview, fixed_clean, fixed_language
):
    fixed_language({})
    draft = _draft_page(app, page, fixed_preview, fixed_clean, "Name it meaning")
    _card(page, draft, "Novgorod").get_by_test_id("flag-name-it").click()
    panel = _panel(page)
    panel.get_by_test_id("name-it-meaning").locator("input").fill("grey hill")
    panel.get_by_test_id("name-it-find").click()
    candidate = panel.get_by_test_id("name-it-candidate").first
    expect(candidate).to_contain_text("Syevkolva", timeout=TIMEOUT_MS)
    expect(candidate).to_contain_text("syev “grey”")


def test_name_it_on_part_of_a_name(app, page, fixed_preview, fixed_clean):
    draft = _draft_page(app, page, fixed_preview, fixed_clean, "Name it part")
    fact = _draft_fact(draft, "It borders")
    _select(page, fact.locator(".fact-text").first, "Greywash")
    page.get_by_test_id("selection-name-it").click()
    panel = _panel(page)
    expect(panel).to_contain_text("Greywash")
    picked = _names(panel)[0]
    panel.get_by_test_id("name-it-name").first.click()
    expect(fact).to_contain_text(
        f"the Duchies of the {picked} Coast", timeout=TIMEOUT_MS
    )
    expect(
        draft.get_by_test_id("new-name-row").filter(
            has_text=f"Duchies of the {picked} Coast"
        )
    ).to_have_count(1)


def test_name_it_on_an_entry_renames_it_and_keeps_the_old_name(app, page):
    _world(app, page, "Name it entry", things=[{"kind": "place", "name": "Tsargrad"}])
    thing = _open_thing(page, "Tsargrad")
    thing.get_by_test_id("name-it-thing").click()
    panel = _panel(page)
    expect(panel.get_by_test_id("name-it-effect")).to_contain_text(
        "stays as another name"
    )
    picked = _names(panel)[0]
    panel.get_by_test_id("name-it-name").first.click()
    expect(page.get_by_test_id("thing-name")).to_have_text(picked, timeout=TIMEOUT_MS)
    expect(page.get_by_test_id("thing-other-names")).to_contain_text("Tsargrad")


def test_name_it_on_a_stub_forgets_the_old_name(app, page):
    _world(
        app,
        page,
        "Name it stub",
        things=[{"kind": "place", "name": "Novgorod", "stub": "live"}],
    )
    page.get_by_test_id("kind-stubs").click()
    tab = page.get_by_test_id("stubs-tab")
    tab.get_by_test_id("stub-row").filter(has_text="Novgorod").locator(
        ".stub-name"
    ).click()
    expect(page.get_by_test_id("thing-name")).to_have_text(
        "Novgorod", timeout=TIMEOUT_MS
    )
    page.get_by_test_id("name-it-thing").click()
    panel = _panel(page)
    expect(panel.get_by_test_id("name-it-effect")).to_contain_text("is forgotten")
    picked = _names(panel)[0]
    panel.get_by_test_id("name-it-name").first.click()
    expect(page.get_by_test_id("thing-name")).to_have_text(picked, timeout=TIMEOUT_MS)
    expect(page.get_by_test_id("thing-other-names")).to_have_count(0)


def test_the_reference_menu_offers_name_it_not_make_a_name(app, page):
    _world(app, page, "Name it menu")
    page.get_by_test_id("kind-place").click()
    box = page.get_by_test_id("create-box").locator("textarea").first
    box.wait_for(state="visible", timeout=TIMEOUT_MS)
    box.fill("Tsardom of ")
    box.evaluate(
        "(el) => { el.focus(); el.setSelectionRange(el.value.length, el.value.length); }"
    )
    box.dispatch_event("contextmenu", {"clientX": 400, "clientY": 300, "button": 2})
    menu = page.get_by_test_id("reference-menu")
    expect(menu.get_by_test_id("menu-name-it")).to_be_visible(timeout=TIMEOUT_MS)
    expect(menu.get_by_test_id("menu-make-name")).to_have_count(0)
    expect(menu.get_by_text(re.compile("Reroll this part"))).to_have_count(0)
