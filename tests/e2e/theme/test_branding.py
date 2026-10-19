"""Task 10 (fantasymate rebrand/appearance): the app presents itself as fantasymate.

See .superpowers/sdd/2026-10-18-fantasymate-rebrand-and-appearance/task-10-brief.md.

This is a visual-only rebrand — the Python package, config, websocket
messages, CLI, scene file format and log names all stay Talemate (see the
global constraints doc). Only what the user reads in the title bar, the app
bar and the home screen changes.

No scene/world seeding is needed here — the ``page`` fixture alone gives a
connected app with its app config already loaded and onboarding dismissed
(see tests/e2e/theme/test_apply.py for the same pattern).

``test_no_talemate_on_home`` excludes the What's New panel's changelog
entries list (``[data-testid="whats-new-entries"]`` in WhatsNew.vue) from its
text check: those entry bodies are upstream changelog data and legitimately
still say "Talemate" (controller ruling R2). The panel's own chrome (title,
tabs, buttons) carries no such text, so nothing else needs excluding.
"""


def test_title_is_fantasymate(page):
    assert page.title() == "fantasymate"


def test_wordmark_in_app_bar(page):
    wordmark = page.locator("header.v-app-bar .fm-wordmark")
    assert "fantasymate" in wordmark.inner_text()
    font_family = wordmark.evaluate("(el) => getComputedStyle(el).fontFamily")
    assert font_family.startswith("Alegreya")


def test_no_talemate_on_home(page):
    body_text = page.inner_text("body")

    # Defensive: if the What's New entries list is ever rendered (e.g. the
    # dialog is open), its changelog bodies legitimately say "Talemate"
    # (upstream data, not chrome) — strip that subtree's text before the
    # page-wide check (ruling R2).
    entries = page.locator('[data-testid="whats-new-entries"]')
    if entries.count() and entries.is_visible():
        body_text = body_text.replace(entries.inner_text(), "")

    assert "Talemate" not in body_text
