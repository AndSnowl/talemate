"""AI test (opt-in): a narrated Taelrik curse is highlighted in the story,
and its bubble shows the matching translation.

Opt-in only (see tests/ai/conftest.py): needs ``-m ai`` and
``TALEMATE_AI_TESTS=1``, and talks to a live koboldcpp (the one at
``TALEMATE_TEST_KOBOLDCPP_URL``, default the GPU server). Never run this
without the owner's go-ahead.
"""

from __future__ import annotations

import json
import time

from ai.cultures.scenarios import SCENARIOS, TAELRIK_FILE, seed_scenario
from ai.test_koboldcpp_smoke import CONNECTED_DOT
from e2e.seed import dismiss_onboarding, open_scene, send_backend

# Both kinds of story message, scoped to the scene's own message list (see
# CharacterMessage.vue's ".character-text" and NarratorMessage.vue's
# ".narrator-text").
STORY_MESSAGE_SELECTOR = (
    ".message-container .narrator-text, .message-container .character-text"
)
CURSE_SPAN_SELECTOR = '.message-container .scene-foreign[data-foreign-kind="curse"]'

NARRATE_PAYLOAD = {
    "type": "narrator",
    "action": "progress",
    "narrative_direction": (
        "Hadrik drops a heavy crate on his foot and curses loudly in Taelrik."
    ),
}

MAX_ATTEMPTS = 3
NARRATION_TIMEOUT = 600.0


def _wait_until(predicate, timeout: float, message: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting: {message}")


def _load_taelrik_curses() -> dict[str, str]:
    """Taelrik's curse phrases, keyed by the lexicon id the frontend uses
    (``phrase:taelrik:{phrase id}``), mapped to their translation."""
    data = json.loads(TAELRIK_FILE.read_text(encoding="utf-8"))
    phrases = data["culture"]["language"]["phrases"]
    return {
        f"phrase:taelrik:{p['id']}": p["translation"]
        for p in phrases
        if p["category"] == "curse"
    }


def test_narrated_curse_is_highlighted_with_translation(ai_app, browser_page):
    page = browser_page
    world = seed_scenario(
        ai_app.root,
        "ai-story-curse",
        SCENARIOS["taelrik_town"],
        with_trait_character=True,
    )

    page.goto(ai_app.frontend_url)
    dismiss_onboarding(page)
    open_scene(page, world.scene_path)

    ai_client = page.get_by_test_id("ai-client")
    ai_client.locator(CONNECTED_DOT).wait_for(state="visible", timeout=60_000)

    curses = _load_taelrik_curses()

    curse_spans = page.locator(CURSE_SPAN_SELECTOR)
    story_messages = page.locator(STORY_MESSAGE_SELECTOR)

    narrations: list[str] = []
    grew = False
    for attempt in range(1, MAX_ATTEMPTS + 1):
        baseline_curse_count = curse_spans.count()
        baseline_message_count = story_messages.count()

        send_backend(page, NARRATE_PAYLOAD)

        _wait_until(
            lambda: story_messages.count() > baseline_message_count
            and story_messages.last.inner_text().strip() != "",
            timeout=NARRATION_TIMEOUT,
            message=f"a new, non-empty story message to render (attempt {attempt})",
        )
        narrations.append(
            f"attempt {attempt}: {story_messages.last.inner_text().strip()!r}"
        )

        if curse_spans.count() > baseline_curse_count:
            grew = True
            break

    assert grew, (
        "no narrated curse was highlighted after "
        f"{MAX_ATTEMPTS} attempts (a model finding if the model never used "
        "a stored curse) -- narrations:\n" + "\n".join(narrations)
    )

    curse_span = curse_spans.last
    curse_span.scroll_into_view_if_needed()
    curse_span.click()

    card = page.get_by_test_id("foreign-word-card")
    card.wait_for(state="visible", timeout=15_000)

    foreign_id = curse_span.get_attribute("data-foreign-id")
    translation = card.get_by_test_id("foreign-translation")
    assert translation.inner_text().strip() == curses[foreign_id], narrations
