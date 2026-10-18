"""Cultures runbook checks 1-5: the tab itself, and import/re-import.

See docs/superpowers/plans/2026-10-17-cultures-foundation-followups.md,
"Manual checks" 1-5.
"""

from pathlib import Path

from e2e.cultures._ui import (
    CULTURE_FILE,
    open_cultures_tab as _open_cultures_tab,
    open_world_editor as _open_world_editor,
    wait_for_json,
)
from e2e.seed import open_scene, place_culture, seed_scene_without_world, seed_world


def _import_dialog(page):
    # ImportCultureDialog is mounted for the page's lifetime, so this
    # locator resolves whether the dialog is open or not.
    return page.locator(".v-overlay__content", has_text="Import culture")


def _open_import_dialog(page):
    # The drawer's "Create" list ("Import culture") renders plain
    # `role="listitem"` entries, unlike the selectable culture/places list
    # below it (`role="option"`) -- this is the only "Import culture"
    # listitem on the page.
    page.get_by_role("listitem").filter(has_text="Import culture").click()
    dialog = _import_dialog(page)
    dialog.wait_for(state="visible", timeout=10_000)
    return dialog


def _upload(dialog, file_path: Path):
    dialog.locator('input[type="file"]').set_input_files(str(file_path))


def _stat_counts(dialog) -> dict:
    stats = dialog.locator("div.d-flex.flex-wrap.ga-6 > div")
    counts = {}
    for i in range(stats.count()):
        lines = [
            ln.strip() for ln in stats.nth(i).inner_text().splitlines() if ln.strip()
        ]
        value, label = lines[0], lines[1]
        counts[label] = value
    return counts


def test_runbook_1_cultures_tab_after_suggestions(app, page):
    scene_path = seed_scene_without_world(app.root, project="rb1")
    open_scene(page, scene_path)

    _open_world_editor(page)

    # Vuetify's v-tabs has role="tablist"; scope to the Suggestions tab's own
    # tablist ancestor, since the page has several (the app bar, the Scene
    # sub-tabs, ...).
    suggestions_tab = page.get_by_role("tab", name="Suggestions", exact=True)
    suggestions_tab.wait_for(state="visible", timeout=30_000)
    tablist = suggestions_tab.locator("xpath=ancestor::*[@role='tablist']").first
    # innerText reflects the tabs' CSS text-transform (upper-case), so
    # compare case-insensitively.
    names = [
        name.strip().lower() for name in tablist.get_by_role("tab").all_inner_texts()
    ]
    suggestions_index = names.index("suggestions")
    assert names[suggestions_index + 1] == "cultures"


def test_runbook_2_no_shared_world_shows_link_prompt(app, page):
    scene_path = seed_scene_without_world(app.root, project="rb2")
    open_scene(page, scene_path)

    _open_world_editor(page)
    _open_cultures_tab(page)

    page.get_by_text("Link this scene to a Shared World").wait_for(
        state="visible", timeout=30_000
    )
    page.get_by_role("button", name="Go to Shared World").click()

    # The button navigates to Scene -> Shared World: a page unique to that
    # sub-tab becomes visible, and its sub-tab is the selected one.
    page.get_by_text("Episodes", exact=True).wait_for(state="visible", timeout=30_000)
    page.get_by_role("tab", name="Shared World", selected=True).wait_for(
        state="visible", timeout=10_000
    )


def test_runbook_3_import_preview_counts_then_culture_listed(app, page):
    world = seed_world(app.root, project="rb3")
    open_scene(page, world.scene_path)

    _open_world_editor(page)
    _open_cultures_tab(page)
    page.get_by_text("No cultures yet.").wait_for(state="visible", timeout=30_000)

    dialog = _open_import_dialog(page)
    _upload(dialog, CULTURE_FILE)

    dialog.locator(".v-chip", has_text="New").wait_for(state="visible", timeout=15_000)
    assert _stat_counts(dialog) == {
        "words": "4",
        "phrases": "4",
        "generators": "3",
        "glossary names": "3",
        "places": "2",
    }

    dialog.get_by_role("button", name="Import Taelrik").click()
    dialog.wait_for(state="hidden", timeout=15_000)

    # The culture list in the drawer is a selectable `v-list` (role="option"
    # per entry), unlike the plain "Import culture" listitem above it.
    page.get_by_role("option", name="Taelrik").wait_for(state="visible", timeout=15_000)


def test_runbook_4_reimport_shows_updating_and_will_be_replaced(app, page):
    world = seed_world(app.root, project="rb4")
    place_culture(world, CULTURE_FILE)
    open_scene(page, world.scene_path)

    _open_world_editor(page)
    _open_cultures_tab(page)

    # Edit a field the file would replace on re-import (see
    # exchange.REPLACEABLE_SECTIONS: "description" is one).
    description = page.locator(".culture-overview textarea").first
    description.wait_for(state="visible", timeout=30_000)
    description.fill("Edited in Talemate, before re-import.")
    description.blur()

    # Wait for the edit to actually reach disk before re-importing, so the
    # preview's diff is never computed against the old description.
    culture_path = world.world_dir / "cultures" / "taelrik.json"
    wait_for_json(
        culture_path,
        lambda c: "Edited in Talemate" in c.get("description", ""),
        message="description edit never reached disk",
    )

    dialog = _open_import_dialog(page)
    _upload(dialog, CULTURE_FILE)

    dialog.locator(".v-chip", has_text="Updating").wait_for(
        state="visible", timeout=15_000
    )
    dialog.get_by_text("Will be replaced:").wait_for(state="visible", timeout=15_000)
    assert "description" in dialog.inner_text()


def test_runbook_5_broken_json_shows_error_dialog_stays_open(app, page, tmp_path):
    world = seed_world(app.root, project="rb5")
    open_scene(page, world.scene_path)

    broken_file = tmp_path / "broken.json"
    broken_file.write_text("{ this is not valid json", encoding="utf-8")

    _open_world_editor(page)
    _open_cultures_tab(page)

    dialog = _open_import_dialog(page)
    _upload(dialog, broken_file)

    alert = dialog.locator(".v-alert")
    alert.wait_for(state="visible", timeout=15_000)
    assert alert.inner_text().strip() != ""
    assert dialog.is_visible()
