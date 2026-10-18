"""Cultures runbook checks 8, 9: glossary filters, the review flow, moving
an entry to Unassigned names, and that rolling new name candidates stays
scoped to the entry's own "Pick another" menu.

See docs/superpowers/plans/2026-10-17-cultures-foundation-followups.md,
"Manual checks" 8, 9.
"""

import json
import time
import uuid
from pathlib import Path

from e2e.seed import open_scene, place_culture, seed_world

APP_BAR = "header.v-app-bar"
CULTURE_FILE = (
    Path(__file__).resolve().parents[2] / "cultures" / "data" / "taelrik.culture.json"
)
CULTURE_ID = "taelrik"


def _entry(
    text,
    kind,
    status="unreviewed",
    by="owner",
    generator_id=None,
    candidates=None,
    language=CULTURE_ID,
):
    """A plain dict matching GlossaryEntry (src/talemate/cultures/models.py)."""
    return {
        "id": uuid.uuid4().hex[:12],
        "text": text,
        "language": language,
        "kind": kind,
        "meaning": "",
        "renderings": {},
        "true_name": "",
        "origin": {
            "by": by,
            "generator_id": generator_id,
            "candidates": candidates or [],
        },
        "first_used": "",
        "status": status,
        "edited_by_owner": False,
        "character_name": None,
        "place_id": None,
    }


def _seed_glossary_entries(world, entries) -> None:
    glossary_path = world.world_dir / "glossary.json"
    data = json.loads(glossary_path.read_text(encoding="utf-8"))
    data["entries"].extend(entries)
    glossary_path.write_text(json.dumps(data), encoding="utf-8")


def _open_cultures_glossary_tab(page):
    page.locator(f"{APP_BAR} .v-tab", has_text="World Editor").click()
    cultures_tab = page.locator(".v-tab", has_text="Cultures")
    cultures_tab.wait_for(state="visible", timeout=30_000)
    cultures_tab.click()
    # Not exact=True: the Glossary tab carries an unreviewed-count badge
    # ("Glossary 1"), so its accessible name isn't exactly "Glossary".
    glossary_tab = page.get_by_role("tab", name="Glossary")
    glossary_tab.wait_for(state="visible", timeout=30_000)
    glossary_tab.click()


def _wait_until(predicate, timeout: float = 10.0, message: str = "") -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting: {message}")


def test_runbook_8_glossary_filters_review_and_unassign(app, page):
    world = seed_world(app.root, project="rb8")
    place_culture(world, CULTURE_FILE)
    # The import gives 3 reviewed entries; add 2 unreviewed ones on top.
    _seed_glossary_entries(
        world,
        [
            _entry("Dorin", "person"),
            _entry("Marrow", "place"),
        ],
    )

    open_scene(page, world.scene_path)
    _open_cultures_glossary_tab(page)

    glossary = page.locator(".glossary-view")
    glossary.wait_for(state="visible", timeout=15_000)

    glossary.get_by_text("Not reviewed (2)").wait_for(state="visible", timeout=10_000)
    assert glossary.get_by_text("Reviewed (3)").count() == 1
    assert glossary.get_by_text("All (5)").count() == 1

    detail = page.get_by_test_id("glossary-detail")
    detail.wait_for(state="visible", timeout=10_000)
    assert "Dorin" in detail.inner_text()

    detail.get_by_role("button", name="Looks right").click()

    # The next unreviewed entry (Marrow) is selected automatically, and the
    # counts move: one fewer unreviewed, one more reviewed.
    detail.locator(".text-h6", has_text="Marrow").wait_for(
        state="visible", timeout=10_000
    )
    glossary.get_by_text("Not reviewed (1)").wait_for(state="visible", timeout=10_000)
    assert glossary.get_by_text("Reviewed (4)").count() == 1

    # Changing its language to "No language yet" moves it to Unassigned names.
    # force=True: a sibling selection-text span sits on top of the actual
    # <input role="combobox">, intercepting the pointer event.
    detail.get_by_role("combobox", name="Language").click(force=True)
    page.get_by_role("option", name="No language yet").click()

    glossary.locator(".glossary-row", has_text="Marrow").wait_for(
        state="hidden", timeout=10_000
    )

    # The drawer's own selectable list renders each entry as role="option".
    page.get_by_role("option", name="Unassigned names").click()
    # Not get_by_text: the Unassigned page's own detail panel also shows
    # "Marrow" (it auto-selects the only entry), so match the table row.
    page.locator(".glossary-row", has_text="Marrow").wait_for(
        state="visible", timeout=15_000
    )


def test_runbook_9_pick_another_rolls_only_in_that_menu(app, page):
    world = seed_world(app.root, project="rb9")
    place_culture(world, CULTURE_FILE)
    _seed_glossary_entries(
        world,
        [
            _entry(
                "Dorel",
                "person",
                by="ai",
                generator_id="given_male",
                candidates=["Dorel", "Kelrin", "Tomrek"],
            ),
            _entry(
                "Varnek",
                "person",
                by="ai",
                generator_id="family",
                candidates=["Varnek", "Daskor", "Thorlen"],
            ),
        ],
    )

    open_scene(page, world.scene_path)
    _open_cultures_glossary_tab(page)

    glossary = page.locator(".glossary-view")
    glossary.wait_for(state="visible", timeout=15_000)
    detail = page.get_by_test_id("glossary-detail")

    # Entry A (Dorel): open "Pick another" and roll new candidates.
    glossary.locator(".glossary-row", has_text="Dorel").click()
    # Scoped to the name heading: "Dorel" also appears as a candidate chip.
    detail.locator(".text-h6", has_text="Dorel").wait_for(
        state="visible", timeout=10_000
    )
    detail.get_by_role("button", name="Pick another").click()

    menu = page.locator(".v-overlay__content", has_text="Roll new")
    menu.wait_for(state="visible", timeout=10_000)
    chips = menu.locator(".v-chip")
    initial_count = chips.count()
    assert initial_count == 3

    menu.get_by_role("button", name="Roll new").click()
    _wait_until(
        lambda: chips.count() > initial_count,
        timeout=15.0,
        message="rolled candidates never appeared in Dorel's menu",
    )

    page.keyboard.press("Escape")

    # Entry B (Varnek): its own "Pick another" menu is unaffected.
    glossary.locator(".glossary-row", has_text="Varnek").click()
    detail.locator(".text-h6", has_text="Varnek").wait_for(
        state="visible", timeout=10_000
    )
    detail.get_by_role("button", name="Pick another").click()

    menu_b = page.locator(".v-overlay__content", has_text="Roll new")
    menu_b.wait_for(state="visible", timeout=10_000)
    assert set(menu_b.locator(".v-chip").all_inner_texts()) == {
        "Varnek",
        "Daskor",
        "Thorlen",
    }
