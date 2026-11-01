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
from e2e.worlds.test_drafts import _draft, _draft_fact
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
