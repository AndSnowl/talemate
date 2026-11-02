"""Name it… (languages 4a revised, Task 5; mockup frames 2 and 3): a
panel with the rule shown, a batch of ten with Reroll, one pattern, and
From a meaning; from a flag, a draft's selection, and an entry's name."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

from talemate.languages.entry import fields_of
from talemate.languages.models import (
    DictionaryEntry,
    FormChange,
    GeneratorDef,
    Language,
    NameGrammar,
    NamePart,
    NameShape,
    OfRule,
)

from e2e.seed import seed_fm_world
from e2e.worlds.test_clean_names import _card
from e2e.worlds.test_drafts import _draft, _draft_fact, _select, _wait_sent
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


def test_name_it_on_linked_words_renames_that_entry(
    app, page, fixed_preview, fixed_clean
):
    """Final review 4: Name it… on part of a linked name in a draft renames
    the entry, the rest of its name kept, and the draft's words follow."""

    _world(
        app,
        page,
        "Name it linked",
        things=[{"kind": "place", "name": "Duchies of the Greywash Coast"}],
    )
    fixed_preview(
        {
            "name": "Tsardom of Otsyenya",
            "facts": [
                {
                    "category": "history",
                    "text": "It borders the Duchies of the Greywash Coast.",
                }
            ],
            "names": [],
            "prose": {},
        }
    )
    fixed_clean(CLEAN)
    draft = _draft(page, "place", "Tsardom of Otsyenya, a cold realm")
    fact = _draft_fact(draft, "It borders")
    _select(page, fact.locator(".fact-text").first, "Greywash")
    page.get_by_test_id("selection-name-it").click()
    panel = _panel(page)
    expect(panel.get_by_test_id("name-it-effect")).to_contain_text(
        "Duchies of the Greywash Coast"
    )
    picked = _names(panel)[0]
    panel.get_by_test_id("name-it-name").first.click()
    expect(fact).to_contain_text(
        f"the Duchies of the {picked} Coast", timeout=TIMEOUT_MS
    )
    sent = _wait_sent(page, "name_it_rename")
    assert sent["name"] == f"Duchies of the {picked} Coast"


def test_a_pinned_name_stays_through_a_reroll(app, page):
    """Owner's run (Test3): a name that intrigues stays while rolling on."""

    _world(app, page, "Name it pin", things=[{"kind": "place", "name": "Tsargrad"}])
    _open_thing(page, "Tsargrad").get_by_test_id("name-it-thing").click()
    panel = _panel(page)
    kept = _names(panel)[0]
    panel.get_by_test_id("name-it-pin").first.click()
    before = _names(panel)
    panel.get_by_test_id("name-it-reroll").click()
    for _ in range(60):
        if _names(panel) != before:
            break
        page.wait_for_timeout(250)
    after = _names(panel)
    assert after != before
    assert after[0] == kept and len(after) == 10


def test_name_it_renames_only_the_words_picked(app, page):
    """Owner's run (Test3): rename only "Vorogovik" in "Cathedral of Saint
    Vorogovik", the rest kept."""

    _world(
        app,
        page,
        "Name it part",
        things=[{"kind": "place", "name": "Cathedral of Saint Vorogovik"}],
    )
    _open_thing(page, "Cathedral of Saint Vorogovik").get_by_test_id(
        "name-it-thing"
    ).click()
    panel = _panel(page)
    panel.get_by_test_id("name-it-part").filter(has_text="Vorogovik").click()
    # the name shows once, as chips: only the word chosen is renamed
    expect(panel.locator(".part-chosen")).to_have_text("Vorogovik")
    expect(panel.locator(".words")).to_have_count(0)
    picked = _names(panel)[0]
    panel.get_by_test_id("name-it-name").first.click()
    expect(page.get_by_test_id("thing-name")).to_have_text(
        f"Cathedral of Saint {picked}", timeout=TIMEOUT_MS
    )


def test_a_meanings_new_word_shows_other_rolls(
    app, page, fixed_preview, fixed_clean, fixed_language
):
    """Owner's run (Test3): each new word of a meaning rolls as the batch
    does, once for both forms of the name: picking a roll builds the names
    again, and a pinned roll stays through a reroll."""

    fixed_language({})
    draft = _draft_page(app, page, fixed_preview, fixed_clean, "Name it word rolls")
    _card(page, draft, "Novgorod").get_by_test_id("flag-name-it").click()
    panel = _panel(page)
    panel.get_by_test_id("name-it-meaning").locator("input").fill("grey lake")
    panel.get_by_test_id("name-it-find").click()
    expect(panel.get_by_test_id("name-it-candidate")).to_have_count(
        2, timeout=TIMEOUT_MS
    )
    rolls = panel.get_by_test_id("name-it-word-rolls")
    expect(rolls).to_have_count(1)
    expect(rolls).to_contain_text("“lake”")
    options = rolls.get_by_test_id("name-it-word-option")
    other = options.nth(1).inner_text().strip()
    options.nth(1).click()
    names = panel.get_by_test_id("name-it-candidate-name")
    expect(names.first).to_have_text("Syev" + other)
    expect(names.nth(1)).to_have_text("Syev " + other.capitalize())
    rolls.get_by_test_id("name-it-word-pin").nth(1).click()
    before = [o.strip() for o in options.all_inner_texts()]
    rolls.get_by_test_id("name-it-word-reroll").click()
    for _ in range(60):
        if [o.strip() for o in options.all_inner_texts()] != before:
            break
        page.wait_for_timeout(250)
    after = [o.strip() for o in options.all_inner_texts()]
    assert after != before and after[0] == other


# --- the builder (languages 4b-1, mockup B) ------------------------------------

VAROVNI = Language(
    name="Varovni",
    level="full",
    categories={"C": "k v d z", "V": "a e i o u"},
    generators=[
        GeneratorDef(id="words", name="Words", use="words", patterns=["CVCV"]),
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
                        NamePart(
                            kind="meaning",
                            forms=["more_than_one"],
                            hint="something in the sky",
                        ),
                    ]
                )
            ],
        ),
    ],
    dictionary=[
        DictionaryEntry(word="zvesk", meanings=["star"], part="noun"),
        DictionaryEntry(word="skelt", meanings=["stone"], part="noun"),
        DictionaryEntry(word="varsa", meanings=["snow"], part="noun"),
        DictionaryEntry(word="luna", meanings=["moon"], part="noun"),
    ],
    name_grammar=NameGrammar(
        of=OfRule(text="ul"),
        more_than_one=[
            FormChange(when="after_vowel", kind="ending", text="ni"),
            FormChange(kind="ending", text="i"),
        ],
    ),
)


def _builder(app, page, stem):
    """Dorvak's page in a world whose one language has the owl-name rule;
    Name it… open on it, the owl-name rule picked."""

    name = _world_name(stem)
    seed_fm_world(
        app.root,
        name,
        things=[
            {
                "kind": "language",
                "name": "Varovni",
                "fields": {"name": "Varovni", **fields_of(VAROVNI)},
            },
            {
                "kind": "character",
                "name": "Dorvak",
                "facts": [
                    {"category": "personality", "text": "Dorvak watches the stars."}
                ],
            },
        ],
    )
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    _open_thing(page, "Dorvak").get_by_test_id("name-it-thing").click()
    panel = page.get_by_test_id("name-it")
    panel.get_by_test_id("name-it-rule").click()
    page.get_by_role("option", name="Owl-names").click()
    expect(panel.get_by_test_id("name-builder-part")).to_have_count(
        3, timeout=TIMEOUT_MS
    )
    return panel


def _rolls(part):
    return [
        r.strip() for r in part.get_by_test_id("name-builder-roll").all_inner_texts()
    ]


def test_the_builder_rolls_unpinned_parts(app, page):
    panel = _builder(app, page, "Builder reroll")
    parts = panel.get_by_test_id("name-builder-part")
    first = parts.nth(0)
    kept = panel.get_by_test_id("name-it-built").inner_text().split()[0]
    first.get_by_test_id("name-builder-pin").click()
    meaning_before = _rolls(parts.nth(2))
    for _ in range(10):
        panel.get_by_test_id("name-it-reroll").click()
        page.wait_for_timeout(300)
        if _rolls(parts.nth(2)) != meaning_before:
            break
    assert panel.get_by_test_id("name-it-built").inner_text().split()[0] == kept
    assert _rolls(first) == [kept]


def test_typing_a_part_pins_it(app, page):
    panel = _builder(app, page, "Builder type")
    box = (
        panel.get_by_test_id("name-builder-part")
        .nth(0)
        .get_by_test_id("name-builder-type")
    )
    box.locator("input").fill("Dorvak")
    box.locator("input").press("Enter")
    box.locator("input").blur()
    expect(panel.get_by_test_id("name-it-built")).to_contain_text(
        "Dorvak Ul", timeout=TIMEOUT_MS
    )
    panel.get_by_test_id("name-it-reroll").click()
    page.wait_for_timeout(500)
    expect(panel.get_by_test_id("name-it-built")).to_contain_text("Dorvak Ul")


def test_use_this_name_renames_the_entry(app, page):
    panel = _builder(app, page, "Builder use")
    built = panel.get_by_test_id("name-it-built").inner_text().strip()
    panel.get_by_test_id("name-it-use").click()
    expect(page.get_by_test_id("thing-name")).to_have_text(built, timeout=TIMEOUT_MS)


def test_give_a_meaning_fills_the_meaning_part(app, page):
    panel = _builder(app, page, "Builder meaning")
    panel.get_by_test_id("name-it-meaning").locator("input").fill("of the Stars")
    panel.get_by_test_id("name-it-find").click()
    expect(panel.get_by_test_id("name-it-built")).to_contain_text(
        "Ul Zveski", timeout=TIMEOUT_MS
    )
    expect(panel.get_by_test_id("name-it-working")).to_contain_text("zvesk “star”")


def test_suggest_fills_from_facts(app, page, fixed_language):
    fixed_language({"noun": "snow", "why": "white plumage"})
    panel = _builder(app, page, "Builder suggest")
    panel.get_by_test_id("name-it-suggest").click()
    expect(panel.get_by_test_id("name-it-built")).to_contain_text(
        "Ul Varsani", timeout=TIMEOUT_MS
    )
    sent = _wait_sent(page, "name_it_suggest")
    assert sent["rule_id"] == "owl"


def test_a_plain_rule_keeps_the_batch(app, page):
    panel = _builder(app, page, "Builder plain")
    panel.get_by_test_id("name-it-rule").click()
    page.get_by_role("option", name="Men's names").click()
    expect(panel.get_by_test_id("name-builder")).to_have_count(0, timeout=TIMEOUT_MS)
    expect(panel.get_by_test_id("name-it-name")).to_have_count(10, timeout=TIMEOUT_MS)
