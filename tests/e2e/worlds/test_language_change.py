"""Changing a language (languages 3b-2b): Change it… on its page, the
review of what changed, the owner's edits kept, Still to fill in and Fill
in next. Claude Code is the fake (`change` mode edits the language file it
finds: one more meaning on the first word, and the word "torg")."""

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

LONG_MS = 60_000


def _language_page(app, page, stem, *, depth="full", speaker=False):
    fields = _language_fields()
    fields["depth"] = depth
    name = _world_name(stem)
    seeded = seed_fm_world(
        app.root,
        name,
        things=[
            {"kind": "language", "name": "Velskar", "fields": fields},
            {"kind": "place", "name": "Sorau"},
        ],
    )
    if speaker:
        from talemate.world.store import Source, World

        world = World.open(seeded.path)
        with world.revision(Source.manual(note="rows")) as rev:
            rev.set_field(
                seeded.things["Sorau"],
                "languages",
                [{"language": seeded.things["Velskar"], "role": "official"}],
                None,
            )
        world.close()
    _open_world(page, name)
    _world_tab(page)
    return _open_thing(page, "Velskar")


def _open_panel(page, thing):
    thing.get_by_test_id("language-change-open").click()
    panel = page.get_by_test_id("language-change")
    panel.wait_for(state="visible", timeout=TIMEOUT_MS)
    return panel


def test_change_it_runs_and_the_review_shows_what_changed(app, page, fake_claude_mode):
    fake_claude_mode("change")
    thing = _language_page(app, page, "Change runs")
    panel = _open_panel(page, thing)
    panel.get_by_test_id("change-request").locator("textarea").first.fill("add words for trade")
    panel.get_by_test_id("change-start").click()
    diff = panel.get_by_test_id("language-diff")
    expect(diff).to_contain_text("torg", timeout=LONG_MS)
    panel.get_by_test_id("language-accept").click()
    expect(page.get_by_test_id("language-change")).to_have_count(0, timeout=TIMEOUT_MS)
    thing.get_by_test_id("language-tab-lexicon").click()
    expect(thing.get_by_test_id("language-words")).to_contain_text("torg", timeout=TIMEOUT_MS)


def test_the_owners_edit_during_a_change_is_kept(app, page, fake_claude_mode):
    fake_claude_mode("change:12")
    thing = _language_page(app, page, "Change kept")
    panel = _open_panel(page, thing)
    panel.get_by_test_id("change-request").locator("textarea").first.fill("more")
    panel.get_by_test_id("change-start").click()
    expect(panel.get_by_test_id("change-progress")).to_be_visible(timeout=TIMEOUT_MS)
    # while it runs, the owner adds a meaning to the same first word
    thing.get_by_test_id("language-tab-lexicon").click()
    row = thing.get_by_test_id("language-word").first
    row.get_by_test_id("add-meaning").click()
    row.get_by_label("new meaning").fill("mighty")
    row.get_by_label("new meaning").press("Enter")
    expect(row.get_by_test_id("word-meaning")).to_contain_text(["mighty"], timeout=TIMEOUT_MS)
    expect(panel.get_by_test_id("change-kept")).to_contain_text("Kept your edit", timeout=LONG_MS)


def test_fit_it_to_suggests_speakers(app, page):
    thing = _language_page(app, page, "Change fit", speaker=True)
    panel = _open_panel(page, thing)
    fit = panel.get_by_test_id("change-fit").filter(has_text="Sorau")
    expect(fit).to_contain_text("speaks it (official)", timeout=TIMEOUT_MS)
    expect(fit.locator("input[type=checkbox]")).to_be_checked()


def test_fill_in_next_offers_the_first_gap(app, page, fake_claude_mode):
    fake_claude_mode("change")
    thing = _language_page(app, page, "Change fill")
    panel = _open_panel(page, thing)
    expect(panel.get_by_test_id("change-still")).to_contain_text("missing", timeout=TIMEOUT_MS)
    fill = panel.get_by_test_id("change-fill")
    expect(fill).to_contain_text("Fill in next: words")
    fill.click()
    expect(panel.get_by_test_id("language-diff")).to_contain_text("torg", timeout=LONG_MS)


def test_no_fill_button_when_nothing_is_missing(app, page):
    thing = _language_page(app, page, "Change naming", depth="naming")
    panel = _open_panel(page, thing)
    expect(panel.get_by_test_id("change-request")).to_be_visible(timeout=TIMEOUT_MS)
    expect(panel.get_by_test_id("change-fill")).to_have_count(0)
    expect(panel.get_by_test_id("change-still")).to_have_count(0)


def test_drop_keeps_the_request(app, page, fake_claude_mode):
    fake_claude_mode("change")
    thing = _language_page(app, page, "Change drop")
    panel = _open_panel(page, thing)
    request = panel.get_by_test_id("change-request").locator("textarea").first
    request.fill("add words for trade")
    panel.get_by_test_id("change-start").click()
    expect(panel.get_by_test_id("language-diff")).to_contain_text("torg", timeout=LONG_MS)
    panel.get_by_test_id("language-drop").click()
    expect(panel.get_by_test_id("language-diff")).to_have_count(0, timeout=TIMEOUT_MS)
    expect(request).to_have_value("add words for trade")


def test_the_route_row_is_the_same_component_in_make_and_change(app, page):
    thing = _language_page(app, page, "Change route")
    panel = _open_panel(page, thing)
    expect(panel.get_by_test_id("route-choice")).to_have_count(1, timeout=TIMEOUT_MS)
    page.get_by_test_id("kind-language").click()
    make = page.get_by_test_id("language-make")
    expect(make.get_by_test_id("route-choice")).to_have_count(1, timeout=TIMEOUT_MS)


def test_fill_in_next_copies_its_brief_on_the_brief_route(app, page):
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    thing = _language_page(app, page, "Change fill brief")
    panel = _open_panel(page, thing)
    panel.get_by_test_id("change-route-brief").click()
    panel.get_by_test_id("change-fill").click()
    expect(panel.get_by_test_id("change-copied")).to_be_visible(timeout=TIMEOUT_MS)
    copied = page.evaluate("() => navigator.clipboard.readText()")
    assert "## What to add" in copied


def test_a_grammar_chapters_change_opens_the_panel_aimed_at_it(app, page):
    fields = _language_fields()
    fields["rules"] = {
        **fields["rules"],
        "grammar": [{"title": "Verbs", "topic": "verbs", "text": "Verbs change for who acts."}],
    }
    name = _world_name("Change chapter")
    seed_fm_world(app.root, name, things=[{"kind": "language", "name": "Velskar", "fields": fields}])
    _open_world(page, name)
    _world_tab(page)
    thing = _open_thing(page, "Velskar")
    thing.get_by_test_id("language-tab-language").click()
    thing.get_by_test_id("language-chapters").get_by_test_id("language-chapter").filter(has_text="Verbs").click()
    thing.get_by_test_id("grammar-section").get_by_test_id("grammar-change").click()
    panel = page.get_by_test_id("language-change")
    request = panel.get_by_test_id("change-request").locator("textarea").first
    expect(request).to_have_value("Change the Verbs section: ", timeout=TIMEOUT_MS)
    expect(request).to_be_focused()
    assert request.evaluate("(el) => el.selectionStart") == len("Change the Verbs section: ")
