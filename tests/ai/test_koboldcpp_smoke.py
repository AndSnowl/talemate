"""AI smoke test: a real KoboldCpp client connects and the narrator generates.

Opt-in only (see tests/ai/conftest.py): needs ``-m ai`` and
``TALEMATE_AI_TESTS=1``, and talks to a live koboldcpp (the one at
``TALEMATE_TEST_KOBOLDCPP_URL``, default the GPU server). Never run this
without the owner's go-ahead.
"""

import time

from e2e.seed import dismiss_onboarding, open_scene, seed_world

# How the "connected, not erroring" state reads in AIClient.vue's client
# row: a plain green dot (`v-icon color="green"` -> Vuetify's `text-green`
# class) in the status slot. Busy renders a spinner instead, warning an
# orange dot, error a red one, disabled a power button -- none of those
# match this selector, so waiting for it rules all of them out at once.
#
# This same icon/color scheme is reused verbatim by AIAgent.vue for every
# configured agent's own status dot, so it must be scoped to the client's
# own row (data-testid="ai-client") -- unscoped, it also matches every
# ready agent's dot (a real failure hit this: 11 matches, 1 client + 10
# agents, a Playwright strict-mode violation).
CONNECTED_DOT = ".mdi-checkbox-blank-circle.text-green"
# SceneTools.vue's narrator menu button (SceneToolsNarrator.vue): an
# icon-only v-btn with no accessible name, so it's found by its icon class
# instead, scoped to the scene's tools card to avoid any other mdi-script-text
# icon elsewhere on the page.
NARRATOR_MENU_BUTTON = ".hotbuttons-section-2 button:has(.mdi-script-text)"
NARRATOR_TEXT = ".narrator-text"


def _wait_until(predicate, timeout: float, message: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting: {message}")


def test_client_connects_and_narrator_generates(ai_app, browser_page):
    page = browser_page
    # browser_page (tests/e2e/conftest.py) already installs SOCKET_HOOK_JS
    # on the context, which open_scene below needs.
    page.goto(ai_app.frontend_url)
    # ai_app's config has a KoboldCpp client, so the onboarding wizard never
    # opens; dismiss_onboarding waits for the client to be listed instead.
    dismiss_onboarding(page)

    world = seed_world(ai_app.root, project="ai-smoke")
    open_scene(page, world.scene_path)

    # The client connects: its row in the Clients drawer shows the green
    # "idle" dot, not busy/warning/error/disabled. Scoped to the client's
    # own row -- see CONNECTED_DOT's comment.
    ai_client = page.get_by_test_id("ai-client")
    ai_client.locator(CONNECTED_DOT).wait_for(state="visible", timeout=60_000)

    # The narrator menu's actions are disabled while the app isn't ready
    # (SceneTools.vue: `:disabled="appBusy || !appReady"`) -- wait for that
    # to clear before using it.
    narrator_button = page.locator(NARRATOR_MENU_BUTTON)
    _wait_until(
        lambda: narrator_button.get_attribute("disabled") is None,
        timeout=60,
        message="narrator menu button stayed disabled",
    )

    baseline = page.locator(NARRATOR_TEXT).count()

    narrator_button.click()
    # "Narrate Environment" (SceneToolsNarrator.vue): a plain click (no
    # modifier) sends the narrator action immediately, no dialog. Scoped to
    # role=listitem (Vuetify's VListItem role for a non-selectable v-list)
    # so this can't match an ancestor container that also contains the text.
    page.get_by_role("listitem").filter(has_text="Narrate Environment").click()

    # Generous timeout: a real generation on real hardware.
    _wait_until(
        lambda: page.locator(NARRATOR_TEXT).count() > baseline
        and page.locator(NARRATOR_TEXT).last.inner_text().strip() != "",
        timeout=180,
        message="no new, non-empty narrator message appeared",
    )

    new_text = page.locator(NARRATOR_TEXT).last.inner_text().strip()
    assert new_text != ""
