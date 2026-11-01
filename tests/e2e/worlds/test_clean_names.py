"""Flagged names in drafts (languages 4a revised, Task 2; first built in
4a's Task 7): a draft made where a
language is in reach arrives with real names replaced, each marked; the
hover card undoes, rerolls or keeps them; a suspect name can be replaced
or kept; the draft shows its language from the owner's words. The model
is the fixed preview and the fixed cleaning replies."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

from talemate.languages.entry import fields_of
from talemate.languages.models import GeneratorDef, Language

from e2e.seed import seed_fm_world
from e2e.worlds.test_drafts import HOLD_ASKS_JS, _draft, _draft_fact, _wait_sent
from e2e.worlds.test_new_scene import SEND_SPY_JS, _sent
from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)

pytestmark = pytest.mark.e2e

PLACES = ["Zizhigrad", "Sovyetsk", "Lezhograd"]
MOSCAVIAN = Language(
    name="Moscavian",
    level="naming",
    categories={"C": "k", "V": "a"},
    generators=[
        GeneratorDef(
            id="places", name="Places", use="place", patterns=[f"[{'|'.join(PLACES)}]"]
        ),
    ],
)
DRAFT = {
    "name": "Tsardom of Moscavia",
    "facts": [
        {
            "category": "description",
            "text": "Fur caravans trade with Novgorod and Velkora.",
        },
        {"category": "history", "text": "The tsars once ruled from the Volga's banks."},
    ],
    "names": [{"name": "Novgorod", "kind": "place"}],
    "prose": {},
}
CLEAN = {
    "language-roles": {"languages": [{"language": "Moscavian", "role": "official"}]},
    "name-flags": {"names": []},
}


def _world(app, page, stem):
    name = _world_name(stem)
    seed_fm_world(
        app.root,
        name,
        things=[
            {
                "kind": "language",
                "name": "Moscavian",
                "fields": {"name": "Moscavian", **fields_of(MOSCAVIAN)},
            }
        ],
    )
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)


def _cleaned_draft(
    app,
    page,
    fixed_preview,
    fixed_clean,
    stem,
    prompt="Tsardom of Moscavia, a cold realm",
):
    _world(app, page, stem)
    fixed_preview(DRAFT)
    fixed_clean(CLEAN)
    return _draft(page, "place", prompt)


def _flag(draft, name):
    return (
        draft.get_by_test_id("name-flag")
        .filter(has_text=re.compile(rf"^{name}$"))
        .first
    )


def _card(page, draft, name):
    _flag(draft, name).hover()
    card = page.get_by_test_id("flag-card")
    expect(card).to_be_visible(timeout=TIMEOUT_MS)
    return card


def test_a_draft_arrives_unchanged_with_flags(app, page, fixed_preview, fixed_clean):
    draft = _cleaned_draft(app, page, fixed_preview, fixed_clean, "Flag unchanged")
    fact = _draft_fact(draft, "Fur caravans")
    expect(fact).to_contain_text(
        "Fur caravans trade with Novgorod and Velkora.", timeout=TIMEOUT_MS
    )
    expect(_flag(draft, "Novgorod")).to_be_visible()
    expect(_flag(draft, "Velkora")).to_be_visible()
    expect(_flag(draft, "Volga")).to_be_visible()


def test_a_flagged_new_stub_keeps_its_stub_look_and_one_card(
    app, page, fixed_preview, fixed_clean
):
    draft = _cleaned_draft(app, page, fixed_preview, fixed_clean, "Flag stub look")
    novgorod = _flag(draft, "Novgorod")
    expect(novgorod).to_have_class(
        re.compile(r"linked-stub.*fresh|fresh.*linked-stub"), timeout=TIMEOUT_MS
    )
    expect(novgorod).to_have_class(re.compile(r"flagged"))
    card = _card(page, draft, "Novgorod")
    expect(card).to_contain_text("Flagged: A real name, on the Real names list")
    expect(card).to_contain_text("a new stub")
    expect(card.get_by_test_id("flag-name-it")).to_be_visible()


def test_keeping_a_flagged_stub_keeps_the_stub(app, page, fixed_preview, fixed_clean):
    draft = _cleaned_draft(app, page, fixed_preview, fixed_clean, "Flag keep stub")
    _card(page, draft, "Novgorod").get_by_test_id("flag-keep").click()
    expect(draft.get_by_test_id("name-flag").filter(has_text="Novgorod")).to_have_count(
        0, timeout=TIMEOUT_MS
    )
    expect(
        draft.get_by_test_id("linked-new").filter(has_text="Novgorod").first
    ).to_be_visible()
    draft.get_by_test_id("draft-bar").get_by_role("button", name="Accept").click()
    expect(page.get_by_test_id("draft-page")).to_have_count(0, timeout=TIMEOUT_MS)
    expect(
        page.get_by_test_id("linked-stub").filter(has_text="Novgorod").first
    ).to_be_visible(timeout=TIMEOUT_MS)


def test_never_flag_adds_to_the_keep_list(app, page, fixed_preview, fixed_clean):
    draft = _cleaned_draft(app, page, fixed_preview, fixed_clean, "Flag never")
    _card(page, draft, "Velkora").get_by_test_id("flag-never").click()
    expect(draft.get_by_test_id("name-flag").filter(has_text="Velkora")).to_have_count(
        0, timeout=TIMEOUT_MS
    )
    edits = _sent(page, "name_list_edit")
    assert [(m.get("edit"), m.get("kind"), m.get("name")) for m in edits] == [
        ("add", "keep", "Velkora")
    ]


def test_new_stubs_say_why_a_name_is_flagged(app, page, fixed_preview, fixed_clean):
    draft = _cleaned_draft(app, page, fixed_preview, fixed_clean, "Flag stubs why")
    row = draft.get_by_test_id("new-name-row").filter(has_text="Novgorod")
    expect(row.get_by_test_id("new-name-flagged")).to_contain_text(
        "flagged: a real name", timeout=TIMEOUT_MS
    )


def test_the_draft_shows_its_language_from_your_words(
    app, page, fixed_preview, fixed_clean
):
    draft = _cleaned_draft(app, page, fixed_preview, fixed_clean, "Flag language")
    languages = draft.get_by_test_id("entry-languages")
    expect(languages).to_contain_text("Moscavian", timeout=TIMEOUT_MS)
    expect(languages).to_contain_text("from your words")


def test_no_language_offers_pick_a_language(app, page, fixed_preview, fixed_clean):
    draft = _cleaned_draft(
        app,
        page,
        fixed_preview,
        fixed_clean,
        "Flag none",
        prompt="a cold northern realm",
    )
    expect(draft.get_by_test_id("draft-pick-language")).to_be_visible(
        timeout=TIMEOUT_MS
    )
    expect(_flag(draft, "Novgorod")).to_be_visible()


# hold the `draft_languages` sends while `window.__e2eHold` is set (a slow
# model's marking), and send them on `window.__e2eRelease()`
HOLD_LANGUAGES_JS = HOLD_ASKS_JS.replace("'add_facts'", "'draft_languages'")


def _pick_held(app, page, fixed_preview, fixed_clean, stem):
    page.evaluate(HOLD_LANGUAGES_JS)
    draft = _cleaned_draft(
        app, page, fixed_preview, fixed_clean, stem, prompt="a cold northern realm"
    )
    draft.get_by_test_id("draft-pick-language").click()
    page.evaluate("() => { window.__e2eHold = true; }")
    form = draft.get_by_test_id("languages-form")
    form.get_by_test_id("languages-language").click()
    page.get_by_role("option", name="Moscavian", exact=True).click()
    form.get_by_role("button", name="Save").click()
    return draft.get_by_test_id("entry-languages")


def test_a_picked_language_shows_at_once(app, page, fixed_preview, fixed_clean):
    """Task 7: the row shows while the draft is marked again, saying so."""

    section = _pick_held(app, page, fixed_preview, fixed_clean, "Lang at once")
    row = section.get_by_test_id("languages-row").filter(has_text="Moscavian")
    expect(row).to_have_count(1, timeout=TIMEOUT_MS)
    expect(section.get_by_test_id("languages-saving")).to_be_visible()
    page.evaluate("() => window.__e2eRelease()")
    expect(section.get_by_test_id("languages-saving")).to_have_count(
        0, timeout=TIMEOUT_MS
    )
    expect(row).to_have_count(1)


def test_adding_twice_is_not_possible_while_saving(
    app, page, fixed_preview, fixed_clean
):
    section = _pick_held(app, page, fixed_preview, fixed_clean, "Lang twice")
    expect(section.get_by_test_id("languages-row")).to_have_count(1, timeout=TIMEOUT_MS)
    expect(section.get_by_test_id("languages-add")).to_be_disabled()
    page.evaluate("() => window.__e2eRelease()")
    expect(section.get_by_test_id("languages-add")).to_be_enabled(timeout=TIMEOUT_MS)


def test_a_stub_draft_shows_the_language_it_inherits(
    app, page, fixed_preview, fixed_clean
):
    """Task 7: expanding a stub filed in a page with a language, the draft
    shows that language as inherited and asks for none."""

    name = _world_name("Lang inherit")
    seed_fm_world(
        app.root,
        name,
        things=[
            {
                "kind": "language",
                "name": "Moscavian",
                "fields": {"name": "Moscavian", **fields_of(MOSCAVIAN)},
            },
            {
                "kind": "place",
                "name": "Tsarvenya",
                "languages": [{"language": "Moscavian", "role": "official"}],
            },
            {
                "kind": "place",
                "name": "Khyagovsk",
                "stub": "live",
                "filings": [{"target": "Tsarvenya"}],
            },
        ],
    )
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-stubs").click()
    tab = page.get_by_test_id("stubs-tab")
    tab.get_by_test_id("stub-row").filter(has_text="Khyagovsk").get_by_role(
        "button", name="Expand"
    ).click()
    box = page.get_by_test_id("create-box")
    box.get_by_test_id("from-stub").filter(has_text="Khyagovsk").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    fixed_preview({**DRAFT, "name": "Khyagovsk"})
    fixed_clean(CLEAN)
    box.get_by_role("button", name="Create").click()
    draft = page.get_by_test_id("draft-page")
    languages = draft.get_by_test_id("entry-languages")
    expect(languages.get_by_test_id("languages-inherited")).to_contain_text(
        "From Tsarvenya: Moscavian (official)", timeout=TIMEOUT_MS
    )
    expect(draft.get_by_test_id("draft-pick-language")).to_have_count(0)


def test_a_flagged_own_name_shows_under_the_heading(
    app, page, fixed_preview, fixed_clean
):
    """Final review 6: the draft's own name on a list is flagged where the
    owner sees it, and Name it… renames the draft."""

    _world(app, page, "Own name flag")
    fixed_preview(
        {
            "name": "Novgorod",
            "facts": [{"category": "description", "text": "Novgorod trades furs."}],
            "names": [],
            "prose": {},
        }
    )
    fixed_clean(CLEAN)
    draft = _draft(page, "place", "Tsardom of Moscavia's fur town")
    flag = draft.get_by_test_id("draft-name-flag")
    expect(flag).to_contain_text("Novgorod", timeout=TIMEOUT_MS)
    flag.get_by_test_id("draft-name-flag-name-it").click()
    panel = page.get_by_test_id("name-it")
    first = panel.get_by_test_id("name-it-name").first
    expect(first).to_be_visible(timeout=TIMEOUT_MS)
    picked = first.inner_text().strip()
    first.click()
    expect(draft.get_by_test_id("draft-name").locator("input")).to_have_value(
        picked, timeout=TIMEOUT_MS
    )
    expect(draft.get_by_test_id("draft-name-flag")).to_have_count(0)


# --- Add facts ----------------------------------------------------------------


def test_add_facts_shows_marks_and_the_card(app, page, fixed_facts, fixed_clean):
    name = _world_name("Clean facts")
    seeded = seed_fm_world(
        app.root,
        name,
        things=[
            {
                "kind": "language",
                "name": "Moscavian",
                "fields": {"name": "Moscavian", **fields_of(MOSCAVIAN)},
            },
            {"kind": "place", "name": "Sorau"},
        ],
    )
    from talemate.world.store import Source, World

    world = World.open(seeded.path)
    with world.revision(Source.manual(note="rows")) as rev:
        rev.set_field(
            seeded.things["Sorau"],
            "languages",
            [{"language": seeded.things["Moscavian"], "role": "official"}],
            None,
        )
    world.close()
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    thing = _open_thing(page, "Sorau")
    fixed_facts(
        {
            "facts": [
                {"category": "general", "text": "Its traders winter in Novgorod."}
            ],
            "names": [],
        }
    )
    fixed_clean({"name-flags": {"names": []}})
    thing.get_by_test_id("add-facts").click()
    thing.get_by_test_id("add-facts-form").get_by_label("What to add").fill("its trade")
    thing.get_by_test_id("add-draft").click()
    draft = thing.get_by_test_id("fact-draft")
    expect(_flag(draft, "Novgorod")).to_be_visible(timeout=TIMEOUT_MS)
    _card(page, draft, "Novgorod").get_by_test_id("flag-keep").click()
    expect(draft.get_by_test_id("name-flag")).to_have_count(0, timeout=TIMEOUT_MS)
    expect(draft).to_contain_text("Its traders winter in Novgorod.")


def test_names_the_ai_did_not_list_come_unticked(app, page, fixed_preview, fixed_clean):
    """Task 7: a reply that lists no names (every race draft of the
    owner's) still offers its facts' unknown names, unticked; ticking one
    makes it a stub on accept."""

    _world(app, page, "Unlisted names")
    fixed_preview(
        {
            "name": "Tsardom of Otsyenya",
            "facts": [
                {
                    "category": "history",
                    "text": "It borders Velmora and the Duchies of the Greywash Coast.",
                }
            ],
            "names": [],
            "prose": {},
        }
    )
    fixed_clean(CLEAN)
    draft = _draft(page, "place", "Tsardom of Otsyenya, a cold realm")
    rows = draft.get_by_test_id("new-name-row")
    velmora = rows.filter(has_text="Velmora")
    expect(velmora.get_by_test_id("new-name-plain")).to_contain_text(
        "didn’t list it", timeout=TIMEOUT_MS
    )
    expect(rows.filter(has_text="Duchies of the Greywash Coast")).to_have_count(1)
    velmora.get_by_test_id("new-name-tick").click()
    expect(velmora.get_by_test_id("new-name-plain")).to_have_count(0)
    draft.get_by_test_id("draft-accept-foot").click()
    sent = _wait_sent(page, "accept_preview")
    ticked = {n["name"]: n["ticked"] for n in sent["preview"]["new_names"]}
    assert ticked == {"Velmora": True, "Duchies of the Greywash Coast": False}
