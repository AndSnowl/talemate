"""Making a language from the Languages page (languages 3b-1, Task 7):
questions, Claude Code (a fake), progress, cancel, the brief, and the
result landing in the import review."""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import expect

from e2e.seed import seed_fm_world
from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _open_world,
    _world_name,
    _world_tab,
)

pytestmark = pytest.mark.e2e

REQUEST = "a unique but recognizably Russian language"


def _make_box(app, page, stem):
    name = _world_name(stem)
    seed_fm_world(app.root, name)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-language").click()
    box = page.get_by_test_id("language-make")
    box.wait_for(state="visible", timeout=TIMEOUT_MS)
    box.get_by_test_id("make-request").locator("textarea").first.fill(REQUEST)
    return box


def test_make_a_language_with_claude_code_lands_in_the_review(
    app, page, fake_claude_mode
):
    fake_claude_mode("ok")
    box = _make_box(app, page, "Make cc")
    box.get_by_test_id("make-start").click()
    expect(box.get_by_test_id("make-done")).to_contain_text(
        "Claude Code", timeout=TIMEOUT_MS
    )
    review = page.get_by_test_id("language-import")
    preview = review.get_by_test_id("language-preview")
    expect(preview).to_contain_text("Velskar", timeout=TIMEOUT_MS)
    # the made file is folded away, a click from view
    expect(review.get_by_test_id("language-paste")).to_be_hidden()
    review.get_by_test_id("language-show-file").click()
    expect(review.get_by_test_id("language-paste")).to_be_visible()
    review.get_by_role("button", name="Import").click()
    expect(page.get_by_test_id("thing-name")).to_have_text(
        "Velskar", timeout=TIMEOUT_MS
    )


def test_progress_shows_while_it_runs(app, page, fake_claude_mode):
    fake_claude_mode("slow")
    box = _make_box(app, page, "Make slow")
    box.get_by_test_id("make-start").click()
    expect(box.get_by_test_id("make-progress")).to_contain_text(
        "Reading the language guide", timeout=TIMEOUT_MS
    )
    box.get_by_test_id("make-cancel").click()


def test_questions_then_decide_for_me(app, page, fixed_language, fake_claude_mode):
    fixed_language({"questions": "1. Grand or earthy?\n2. Old or modern?"})
    fake_claude_mode("ok")
    box = _make_box(app, page, "Make ask")
    box.get_by_test_id("make-ask").click()
    expect(box.get_by_test_id("make-answer")).to_have_count(2, timeout=TIMEOUT_MS)
    expect(box).to_contain_text("Grand or earthy?")
    box.get_by_test_id("make-decide").click()
    expect(page.get_by_test_id("language-preview")).to_contain_text(
        "Velskar", timeout=TIMEOUT_MS
    )


def test_copy_the_brief_copies_text(app, page):
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    box = _make_box(app, page, "Make brief")
    box.get_by_test_id("make-copy-brief").click()
    expect(box.get_by_test_id("make-copied")).to_be_visible(timeout=TIMEOUT_MS)
    copied = page.evaluate("() => navigator.clipboard.readText()")
    assert copied.startswith("# Make a language for a fantasy world")
    assert REQUEST in copied


def test_cancel_returns_to_idle(app, page, fake_claude_mode):
    fake_claude_mode("slow")
    box = _make_box(app, page, "Make cancel")
    box.get_by_test_id("make-start").click()
    expect(box.get_by_test_id("make-cancel")).to_be_visible(timeout=TIMEOUT_MS)
    box.get_by_test_id("make-cancel").click()
    expect(box.get_by_test_id("make-progress")).to_have_count(0, timeout=TIMEOUT_MS)
    expect(box.get_by_test_id("make-start")).to_be_enabled()


def test_a_failed_run_shows_why(app, page, fake_claude_mode):
    fake_claude_mode("error")
    box = _make_box(app, page, "Make fail")
    box.get_by_test_id("make-start").click()
    expect(box.get_by_test_id("make-error")).to_contain_text(
        "Claude Code stopped", timeout=TIMEOUT_MS
    )
    expect(box.get_by_test_id("make-copy-brief")).to_be_visible()


def test_the_draft_stays_until_discarded(app, page, fixed_language):
    fixed_language({"questions": "1. Grand or earthy?"})
    box = _make_box(app, page, "Make draft")
    box.get_by_test_id("make-ask").click()
    expect(box.get_by_test_id("make-answer")).to_have_count(1, timeout=TIMEOUT_MS)
    box.get_by_test_id("make-answer").locator("input").fill("Grand")

    # away to Places and back: the request, questions and answers are kept
    page.get_by_test_id("kind-place").click()
    page.get_by_test_id("kind-language").click()
    box = page.get_by_test_id("language-make")
    request = box.get_by_test_id("make-request").locator("textarea").first
    expect(request).to_have_value(REQUEST, timeout=TIMEOUT_MS)
    expect(box.get_by_test_id("make-answer").locator("input")).to_have_value("Grand")

    box.get_by_test_id("make-discard").click()
    expect(request).to_have_value("")
    expect(box.get_by_test_id("make-answer")).to_have_count(0)


# --- 3b-2a: route, model and size in the dialog -----------------------------


def test_the_dialog_offers_route_model_and_size(app, page):
    box = _make_box(app, page, "Make choices")
    route = box.get_by_test_id("make-route")
    expect(route.get_by_test_id("make-route-claude_code")).to_have_attribute(
        "aria-pressed", "true", timeout=TIMEOUT_MS
    )
    expect(box.get_by_test_id("make-model")).to_be_visible()
    expect(box.get_by_test_id("make-size-full")).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(box.get_by_test_id("make-size-note")).to_contain_text("subscription")


def test_choosing_the_agents_model_switches_to_quick(app, page):
    box = _make_box(app, page, "Make quick")
    box.get_by_test_id("make-route-in_app").click()
    expect(box.get_by_test_id("make-size-quick")).to_have_attribute(
        "aria-pressed", "true", timeout=TIMEOUT_MS
    )
    expect(box.get_by_test_id("make-model")).to_have_count(0)
    # the test app has no clients: beside the buttons and the note say so
    expect(box.get_by_test_id("make-route-in_app")).to_contain_text("Language agent")
    expect(box.get_by_test_id("make-client")).to_contain_text("no client set")
    expect(box.get_by_test_id("make-size-note")).to_contain_text(
        "pick one under Agents"
    )


def _route_reply(page, client):
    """The server's route reply, as if the Language agent had `client`."""

    page.evaluate(
        """(client) => {
            const pinia = document.querySelector('#app').__vue_app__.config.globalProperties.$pinia;
            const worlds = pinia._s.get('worlds');
            worlds.languageMakeRoute = { ...worlds.languageMakeRoute, in_app_client: client };
        }""",
        client,
    )


def test_the_agents_model_is_named_and_a_hosted_one_spends_tokens(app, page):
    box = _make_box(app, page, "Make named hosted")
    expect(box.get_by_test_id("make-route-in_app")).to_be_visible(timeout=TIMEOUT_MS)
    _route_reply(
        page,
        {
            "agent": "Language",
            "name": "Anthropic",
            "model": "claude-sonnet-5",
            "hosted": True,
        },
    )
    button = box.get_by_test_id("make-route-in_app")
    expect(button).to_contain_text("Language agent")
    expect(button).to_contain_text("(API tokens)")
    button.click()
    expect(box.get_by_test_id("make-client")).to_have_text(
        "Anthropic · claude-sonnet-5"
    )
    expect(box.get_by_test_id("make-size-note")).to_contain_text("Spends API tokens")


def test_a_self_hosted_model_spends_no_tokens(app, page):
    box = _make_box(app, page, "Make named local")
    expect(box.get_by_test_id("make-route-in_app")).to_be_visible(timeout=TIMEOUT_MS)
    _route_reply(
        page,
        {
            "agent": "Creator",
            "name": "KoboldCpp",
            "model": "Mistral-Small-24B",
            "hosted": False,
        },
    )
    button = box.get_by_test_id("make-route-in_app")
    # the Language agent has none: the Creator's stands in, and says so
    expect(button).to_contain_text("Creator agent")
    expect(button).not_to_contain_text("API tokens")
    button.click()
    expect(box.get_by_test_id("make-client")).to_have_text(
        "KoboldCpp · Mistral-Small-24B"
    )
    expect(box.get_by_test_id("make-size-note")).not_to_contain_text("API tokens")


def test_a_chosen_route_is_used_for_the_run(app, page, fixed_language):
    sample = (
        Path(__file__).resolve().parents[2] / "languages/data/sample.language.json"
    ).read_text()
    fixed_language({"language_file": sample})
    box = _make_box(app, page, "Make in app")
    box.get_by_test_id("make-route-in_app").click()
    box.get_by_test_id("make-start").click()
    expect(page.get_by_test_id("language-preview")).to_contain_text(
        "Velskar", timeout=TIMEOUT_MS
    )
    expect(box.get_by_test_id("make-done")).to_contain_text(
        "the Language agent's model"
    )


def test_copy_the_brief_route_makes_copy_the_main_button(app, page):
    box = _make_box(app, page, "Make brief route")
    box.get_by_test_id("make-route-brief").click()
    expect(box.get_by_test_id("make-start")).to_have_count(0, timeout=TIMEOUT_MS)
    expect(box.get_by_test_id("make-copy-brief")).to_be_visible()
    box.get_by_test_id("make-route-claude_code").click()
    expect(box.get_by_test_id("make-start")).to_be_visible(timeout=TIMEOUT_MS)


def test_the_copied_brief_follows_how_much(app, page):
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    box = _make_box(app, page, "Make brief size")
    box.get_by_test_id("make-size-quick").click()
    box.get_by_test_id("make-copy-brief").click()
    expect(box.get_by_test_id("make-copied")).to_be_visible(timeout=TIMEOUT_MS)
    assert "fill in the rest later" in page.evaluate(
        "() => navigator.clipboard.readText()"
    )


def test_the_review_shows_still_to_fill_in(app, page, fake_claude_mode):
    fake_claude_mode("ok")
    box = _make_box(app, page, "Make still")
    box.get_by_test_id("make-start").click()
    still = page.get_by_test_id("check-still-to-fill")
    expect(still).to_contain_text("missing", timeout=TIMEOUT_MS)
    expect(still).to_contain_text("Phrases")
