"""Making a language from the Languages page (languages 3b-1, Task 7):
questions, Claude Code (a fake), progress, cancel, the brief, and the
result landing in the import review."""

from __future__ import annotations

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


def test_make_a_language_with_claude_code_lands_in_the_review(app, page, fake_claude_mode):
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
    expect(page.get_by_test_id("thing-name")).to_have_text("Velskar", timeout=TIMEOUT_MS)


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
