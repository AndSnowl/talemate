"""Cultures runbook checks 6, 7, 10: edits that must survive a reload, and
Keep/Drop on a play addition that must survive an unrelated edit.

See docs/superpowers/plans/2026-10-17-cultures-foundation-followups.md,
"Manual checks" 6, 7, 10.
"""

import json
import uuid

from e2e.cultures._ui import (
    CULTURE_FILE,
    open_world_editor_cultures as _open_world_editor_cultures,
    wait_for_json,
)
from e2e.seed import dismiss_onboarding, open_scene, place_culture, seed_world

CULTURE_ID = "taelrik"


def _reload_and_reopen(page, scene_path):
    page.reload()
    dismiss_onboarding(page)
    open_scene(page, scene_path)
    _open_world_editor_cultures(page)


def _wait_for_culture(
    world_dir, predicate, timeout: float = 15.0, message: str = ""
) -> dict:
    """Poll the culture's own file until `predicate(data)` is true; return it.

    The frontend gives no "saved" signal for a `patch_culture`/`addition`
    save, so this is the condition to wait on instead of a fixed sleep.
    """
    path = world_dir / "cultures" / f"{CULTURE_ID}.json"
    return wait_for_json(path, predicate, timeout=timeout, message=message)


def _add_addition(world, section: str, text: str) -> str:
    culture_path = world.world_dir / "cultures" / f"{CULTURE_ID}.json"
    data = json.loads(culture_path.read_text(encoding="utf-8"))
    addition_id = uuid.uuid4().hex[:12]
    data["additions"].append(
        {
            "id": addition_id,
            "section": section,
            "text": text,
            "source": "",
            "status": "unreviewed",
        }
    )
    culture_path.write_text(json.dumps(data), encoding="utf-8")
    return addition_id


def test_runbook_6_culture_and_language_edits_survive_reload(app, page):
    world = seed_world(app.root, project="rb6")
    place_culture(world, CULTURE_FILE)
    open_scene(page, world.scene_path)
    _open_world_editor_cultures(page)

    description = page.locator(".culture-overview textarea").first
    description.fill("River-folk, now with a note added in the test.")
    description.blur()
    _wait_for_culture(
        world.world_dir,
        lambda c: "note added in the test" in c["description"],
        message="description save",
    )

    page.get_by_role("tab", name="Language", exact=True).click()
    sound = page.locator(".language-overview textarea").first
    sound.wait_for(state="visible", timeout=15_000)
    sound.fill("A test-only note on how it sounds.")
    sound.blur()
    _wait_for_culture(
        world.world_dir,
        lambda c: "test-only note" in c["language"]["sound"],
        message="sound save",
    )

    _reload_and_reopen(page, world.scene_path)

    description = page.locator(".culture-overview textarea").first
    description.wait_for(state="visible", timeout=15_000)
    assert "note added in the test" in description.input_value()

    page.get_by_role("tab", name="Language", exact=True).click()
    sound = page.locator(".language-overview textarea").first
    sound.wait_for(state="visible", timeout=15_000)
    assert "test-only note" in sound.input_value()


def test_runbook_7_keep_survives_custom_edit(app, page):
    world = seed_world(app.root, project="rb7")
    place_culture(world, CULTURE_FILE)
    keep_id = _add_addition(world, "customs", "Keep this one.")
    drop_id = _add_addition(world, "customs", "Drop this one.")

    open_scene(page, world.scene_path)
    _open_world_editor_cultures(page)

    # `has_text` can't match a <textarea>'s value (Vue sets the DOM property,
    # not its text content), so the two boxes are addressed by position --
    # seeded in this order, and additionsFor() preserves culture.json order.
    addition_boxes = page.locator(".addition-box")
    addition_boxes.first.wait_for(state="visible", timeout=15_000)
    keep_box = addition_boxes.nth(0)
    drop_box = addition_boxes.nth(1)
    # `.first`: auto-grow textareas render a second, hidden "sizer" textarea.
    assert keep_box.locator("textarea").first.input_value() == "Keep this one."
    assert drop_box.locator("textarea").first.input_value() == "Drop this one."
    keep_box.get_by_text("Not reviewed").wait_for(state="visible", timeout=10_000)

    keep_box.get_by_role("button", name="Keep").click()
    _wait_for_culture(
        world.world_dir,
        lambda c: next(a for a in c["additions"] if a["id"] == keep_id)["status"]
        == "reviewed",
        message="keep save",
    )
    keep_box.get_by_text("Not reviewed").wait_for(state="hidden", timeout=10_000)

    drop_box.get_by_role("button", name="Drop").click()
    _wait_for_culture(
        world.world_dir,
        lambda c: all(a["id"] != drop_id for a in c["additions"]),
        message="drop save",
    )
    drop_box.wait_for(state="hidden", timeout=10_000)

    # Now edit an unrelated custom: the Keep/Drop above must not be undone.
    # `.last`: "Add custom" also matches the World Editor's outer root card
    # (an ancestor of everything); the innermost match is last in document
    # order, since a child's opening tag always comes after its parent's.
    customs_card = page.locator(".v-card", has_text="Add custom").last
    customs_card.get_by_role("button", name="Add custom").click()
    new_custom = customs_card.locator("input").last
    new_custom.fill("Added during the test.")
    new_custom.blur()

    final = _wait_for_culture(
        world.world_dir,
        lambda c: any("Added during the test." in text for text in c["customs"]),
        message="custom save",
    )
    assert (
        next(a for a in final["additions"] if a["id"] == keep_id)["status"]
        == "reviewed"
    )
    assert all(a["id"] != drop_id for a in final["additions"])

    # And the UI still agrees, without needing a reload.
    keep_box.get_by_text("Not reviewed").wait_for(state="hidden", timeout=5_000)
    assert drop_box.count() == 0


def test_runbook_10_dictionary_and_phrases_edits_survive_reload(app, page):
    world = seed_world(app.root, project="rb10")
    place_culture(world, CULTURE_FILE)
    open_scene(page, world.scene_path)
    _open_world_editor_cultures(page)

    # Dictionary: edit a word's meaning.
    page.get_by_role("tab", name="Dictionary", exact=True).click()
    table = page.locator(".dictionary-table table")
    table.wait_for(state="visible", timeout=15_000)
    first_row = table.locator("tbody tr").first
    meaning_input = first_row.locator("input").nth(1)
    meaning_input.fill("ford, river crossing (edited)")
    meaning_input.blur()
    _wait_for_culture(
        world.world_dir,
        lambda c: c["language"]["dictionary"][0]["meaning"]
        == "ford, river crossing (edited)",
        message="dictionary save",
    )

    # Phrases: add, edit and delete one.
    page.get_by_role("tab", name="Phrases", exact=True).click()
    phrase_list = page.locator(".phrase-list")
    phrase_list.wait_for(state="visible", timeout=15_000)

    toll_row = phrase_list.locator(".phrase-row", has_text="Dhun sa'ver")
    toll_row.get_by_role("button").first.click()
    edit_dialog = page.locator(".v-overlay__content", has_text="Edit phrase")
    edit_dialog.wait_for(state="visible", timeout=10_000)
    edit_dialog.locator("input").nth(2).fill(
        "EDITED: the river and the high ground are watched."
    )
    edit_dialog.get_by_role("button", name="Save").click()
    edit_dialog.wait_for(state="hidden", timeout=10_000)

    flood_row = phrase_list.locator(".phrase-row", has_text="Dhaer tal'skev")
    flood_row.get_by_role("button").nth(1).click()
    flood_row.wait_for(state="hidden", timeout=10_000)

    page.get_by_role("button", name="Add phrase").click()
    add_dialog = page.locator(".v-overlay__content", has_text="Add phrase")
    add_dialog.wait_for(state="visible", timeout=10_000)
    add_inputs = add_dialog.locator("input")
    add_inputs.nth(0).fill("greeting")
    add_inputs.nth(1).fill("Hae tal.")
    add_inputs.nth(2).fill("Hello, added during the test.")
    add_dialog.get_by_role("button", name="Save").click()
    add_dialog.wait_for(state="hidden", timeout=10_000)

    _wait_for_culture(
        world.world_dir,
        lambda c: (
            any(
                p["translation"].startswith("EDITED:") for p in c["language"]["phrases"]
            )
            and all(
                p["original"] != "Dhaer tal'skev." for p in c["language"]["phrases"]
            )
            and any(p["category"] == "greeting" for p in c["language"]["phrases"])
        ),
        message="phrases save",
    )

    _reload_and_reopen(page, world.scene_path)

    page.get_by_role("tab", name="Dictionary", exact=True).click()
    table = page.locator(".dictionary-table table")
    table.wait_for(state="visible", timeout=15_000)
    first_row = table.locator("tbody tr").first
    meaning_input = first_row.locator("input").nth(1)
    assert meaning_input.input_value() == "ford, river crossing (edited)"

    page.get_by_role("tab", name="Phrases", exact=True).click()
    phrase_list = page.locator(".phrase-list")
    phrase_list.wait_for(state="visible", timeout=15_000)
    phrase_list.get_by_text("EDITED:").wait_for(state="visible", timeout=10_000)
    phrase_list.get_by_text("Hae tal.").wait_for(state="visible", timeout=10_000)
    assert phrase_list.locator(".phrase-row", has_text="Dhaer tal'skev").count() == 0
