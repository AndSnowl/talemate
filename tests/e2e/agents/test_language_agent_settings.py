"""The language agent's settings (languages 3b-1, Task 1): they open with
no AI client configured, and show the route and the guidance."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

TIMEOUT_MS = 30_000


def test_the_language_agents_settings_open_without_a_client(app, page):
    page.locator(".v-list-item", has_text="Language").first.click()
    dialog = page.locator(".v-dialog").filter(has_text="Making languages")
    expect(dialog).to_be_visible(timeout=TIMEOUT_MS)
    dialog.get_by_role("tab", name="Making languages").click()
    expect(dialog).to_contain_text("needs a strong model")
    expect(dialog).to_contain_text("Claude Code on this computer")
