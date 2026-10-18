"""Shared Playwright/polling helpers for the cultures runbook tests.

Pulled out of the individual ``test_*.py`` files (task 4's review flagged
the poll-with-timeout helper as duplicated across them): the generic
boolean-predicate poll (``wait_until``), the JSON-file poll built on top of
it (``wait_for_json``), and the World Editor navigation steps every check
starts with.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

APP_BAR = "header.v-app-bar"

CULTURE_FILE = (
    Path(__file__).resolve().parents[2] / "cultures" / "data" / "taelrik.culture.json"
)


def wait_until(predicate, timeout: float = 10.0, message: str = "") -> None:
    """Poll `predicate()` (a zero-arg callable) until it's true, or raise.

    The condition to wait on where the frontend gives no other visible
    signal (no spinner, no success indicator) that a save/roll/etc. is
    done -- never a fixed sleep.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting: {message}")


def wait_for_json(
    path: Path, predicate, timeout: float = 15.0, message: str = ""
) -> dict:
    """Poll a JSON file on disk until `predicate(data)` is true; return it.

    Raises with the last-seen content on timeout, to make a failure
    readable.
    """
    last = None

    def _check() -> bool:
        nonlocal last
        if not path.exists():
            return False
        try:
            last = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        return predicate(last)

    try:
        wait_until(_check, timeout=timeout, message=message)
    except AssertionError:
        raise AssertionError(
            f"timed out waiting for {path} ({message})\nlast seen: {last}"
        ) from None
    return last


def open_world_editor(page) -> None:
    page.locator(f"{APP_BAR} .v-tab", has_text="World Editor").click()


def open_cultures_tab(page) -> None:
    cultures_tab = page.locator(".v-tab", has_text="Cultures")
    cultures_tab.wait_for(state="visible", timeout=30_000)
    cultures_tab.click()


def open_world_editor_cultures(page) -> None:
    """Open World Editor -> Cultures, and wait for the auto-selected culture's page.

    Only valid when exactly one culture is in the shared world (as every
    test here seeds): ``WorldStateManagerCultures`` auto-selects the first
    one.
    """
    open_world_editor(page)
    open_cultures_tab(page)
    page.locator(".culture-overview").wait_for(state="visible", timeout=30_000)


def open_places_view(page) -> None:
    """Open World Editor -> Cultures -> Places & regions, and wait for its table.

    Only valid when at least one place is already seeded.
    """
    open_world_editor(page)
    open_cultures_tab(page)
    page.get_by_role("option", name="Places & regions").click()
    page.locator(".place-row").first.wait_for(state="visible", timeout=15_000)
