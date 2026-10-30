"""Clean names in drafts (languages 4a, Task 7): a draft made where a
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
        {"category": "history", "text": "The tsars once ruled from Novgorod's walls."},
    ],
    "prose": {},
}
CLEAN = {
    "language-roles": {"languages": [{"language": "Moscavian", "role": "official"}]},
    "name-flags": {"names": []},
    "name-picks": {"picks": [{"n": 1, "pick": "Sovyetsk", "meaning": "owl town"}]},
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


def _mark(draft, name):
    return (
        draft.get_by_test_id("name-mark")
        .filter(has_text=re.compile(rf"^{name}$"))
        .first
    )


def _card(page, draft, name):
    _mark(draft, name).hover()
    card = page.get_by_test_id("name-mark-card")
    expect(card).to_be_visible(timeout=TIMEOUT_MS)
    return card


def test_a_replaced_name_shows_its_card(app, page, fixed_preview, fixed_clean):
    draft = _cleaned_draft(app, page, fixed_preview, fixed_clean, "Clean card")
    expect(_draft_fact(draft, "Fur caravans")).to_contain_text(
        "Sovyetsk", timeout=TIMEOUT_MS
    )
    card = _card(page, draft, "Sovyetsk")
    expect(card).to_contain_text("was Novgorod")
    expect(card).to_contain_text("owl town")
    expect(draft.get_by_test_id("draft-new-names")).to_contain_text("replaced Novgorod")


def test_reroll_changes_every_occurrence(app, page, fixed_preview, fixed_clean):
    draft = _cleaned_draft(app, page, fixed_preview, fixed_clean, "Clean reroll")
    _card(page, draft, "Sovyetsk").get_by_test_id("mark-reroll").click()
    first = _draft_fact(draft, "Fur caravans")
    expect(first).not_to_contain_text("Sovyetsk", timeout=TIMEOUT_MS)
    rerolled = next(p for p in PLACES if p != "Sovyetsk" and p in first.inner_text())
    expect(_draft_fact(draft, "tsars once ruled")).to_contain_text(
        f"{rerolled}'s walls"
    )


def test_keep_here_puts_the_old_name_back(app, page, fixed_preview, fixed_clean):
    draft = _cleaned_draft(app, page, fixed_preview, fixed_clean, "Clean keep")
    _card(page, draft, "Sovyetsk").get_by_test_id("mark-keep-here").click()
    expect(_draft_fact(draft, "Fur caravans")).to_contain_text(
        "Novgorod", timeout=TIMEOUT_MS
    )
    expect(_draft_fact(draft, "tsars once ruled")).to_contain_text("Novgorod's walls")
    # the stub cleaning made goes with it
    expect(draft.get_by_test_id("new-name-replaced")).to_have_count(0)


def test_never_replace_adds_to_the_keep_list(app, page, fixed_preview, fixed_clean):
    draft = _cleaned_draft(app, page, fixed_preview, fixed_clean, "Clean never")
    _card(page, draft, "Sovyetsk").get_by_test_id("mark-never").click()
    expect(_draft_fact(draft, "Fur caravans")).to_contain_text(
        "Novgorod", timeout=TIMEOUT_MS
    )
    edits = _sent(page, "name_list_edit")
    assert [(m.get("edit"), m.get("kind"), m.get("name")) for m in edits] == [
        ("add", "keep", "Novgorod")
    ]


def test_a_suspect_name_can_be_replaced_or_kept(app, page, fixed_preview, fixed_clean):
    draft = _cleaned_draft(app, page, fixed_preview, fixed_clean, "Clean suspect")
    card = _card(page, draft, "Velkora")
    expect(card).to_contain_text("Doesn't sound like Moscavian")
    card.get_by_test_id("mark-replace").click()
    fact = _draft_fact(draft, "Fur caravans")
    expect(fact).not_to_contain_text("Velkora", timeout=TIMEOUT_MS)
    expect(draft.get_by_test_id("draft-new-names")).to_contain_text("replaced Velkora")


def test_keeping_a_suspect_name_drops_its_mark(app, page, fixed_preview, fixed_clean):
    draft = _cleaned_draft(app, page, fixed_preview, fixed_clean, "Clean suspect keep")
    _card(page, draft, "Velkora").get_by_test_id("mark-keep").click()
    expect(_draft_fact(draft, "Fur caravans")).to_contain_text(
        "Velkora", timeout=TIMEOUT_MS
    )
    expect(draft.get_by_test_id("name-mark").filter(has_text="Velkora")).to_have_count(
        0
    )


def test_the_draft_shows_its_language_from_your_words(
    app, page, fixed_preview, fixed_clean
):
    draft = _cleaned_draft(app, page, fixed_preview, fixed_clean, "Clean language")
    languages = draft.get_by_test_id("entry-languages")
    expect(languages).to_contain_text("Moscavian", timeout=TIMEOUT_MS)
    expect(languages).to_contain_text("from your words")


def test_no_language_offers_pick_a_language(app, page, fixed_preview, fixed_clean):
    draft = _cleaned_draft(
        app,
        page,
        fixed_preview,
        fixed_clean,
        "Clean none",
        prompt="a cold northern realm",
    )
    expect(draft.get_by_test_id("draft-pick-language")).to_be_visible(
        timeout=TIMEOUT_MS
    )
    expect(_mark(draft, "Novgorod")).to_be_visible()


def test_accept_keeps_only_the_new_names(app, page, fixed_preview, fixed_clean):
    draft = _cleaned_draft(app, page, fixed_preview, fixed_clean, "Clean accept")
    expect(_draft_fact(draft, "Fur caravans")).to_contain_text(
        "Sovyetsk", timeout=TIMEOUT_MS
    )
    draft.get_by_test_id("draft-bar").get_by_role("button", name="Accept").click()
    expect(page.get_by_test_id("draft-page")).to_have_count(0, timeout=TIMEOUT_MS)
    thing = _open_thing(page, "Moscavian")
    thing.get_by_test_id("language-tab-lexicon").click()
    expect(thing.get_by_test_id("language-words")).to_contain_text(
        "Sovyetsk", timeout=TIMEOUT_MS
    )


# --- Add facts (Task 8) -------------------------------------------------------


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
    fixed_clean(
        {
            "name-flags": {"names": []},
            "name-picks": {"picks": [{"n": 1, "pick": "Sovyetsk", "meaning": ""}]},
        }
    )
    thing.get_by_test_id("add-facts").click()
    thing.get_by_test_id("add-facts-form").get_by_label("What to add").fill("its trade")
    thing.get_by_test_id("add-draft").click()
    draft = thing.get_by_test_id("fact-draft")
    expect(draft).to_contain_text("Sovyetsk", timeout=TIMEOUT_MS)
    card = _card(page, draft, "Sovyetsk")
    card.get_by_test_id("mark-keep-here").click()
    expect(draft).to_contain_text("Its traders winter in Novgorod.", timeout=TIMEOUT_MS)
