"""Browser tests for task 9: reviewing AI-set cultures and flags in the
Cultures tab (the People view, the glossary "doesn't fit" flag, and the
addition-arriving-while-editing fix).

See .superpowers/sdd/2026-10-18-cultures-ai/task-9-brief.md.
"""

from e2e.cultures._ui import (
    CULTURE_FILE,
    _add_addition,
    open_world_editor as _open_world_editor,
    open_cultures_tab as _open_cultures_tab,
    open_world_editor_cultures as _open_world_editor_cultures,
    wait_until,
)
from e2e.seed import open_scene, place_culture, place_glossary, seed_world, send_backend


def _open_cultures_glossary_tab(page):
    _open_world_editor(page)
    _open_cultures_tab(page)
    # Not exact=True: the Glossary tab carries an unreviewed-count badge.
    glossary_tab = page.get_by_role("tab", name="Glossary")
    glossary_tab.wait_for(state="visible", timeout=30_000)
    glossary_tab.click()


def test_people_view_review_and_change(app, page):
    world = seed_world(
        app.root,
        project="ai-review-people",
        characters=[
            {
                "name": "Kethrun",
                "culture": {
                    "culture_id": "taelrik",
                    "set_by": "ai",
                    "unsure": True,
                    "reason": "spoke with a river-folk lilt",
                },
            },
        ],
    )
    place_culture(world, CULTURE_FILE)

    open_scene(page, world.scene_path)
    _open_world_editor_cultures(page)

    people_option = page.get_by_role("option", name="People")
    people_option.wait_for(state="visible", timeout=15_000)
    people_option.locator(".v-badge__badge", has_text="1").wait_for(
        state="visible", timeout=15_000
    )

    people_option.click()
    people_view = page.locator(".people-view")
    people_view.wait_for(state="visible", timeout=15_000)

    row = people_view.locator(".people-row", has_text="Kethrun")
    row.wait_for(state="visible", timeout=15_000)
    row.locator(".unsure-dot").wait_for(state="visible", timeout=10_000)

    row.get_by_role("button", name="Looks right").click()
    row.locator(".unsure-dot").wait_for(state="hidden", timeout=10_000)
    wait_until(
        lambda: people_option.locator(".v-badge__badge").count() == 0,
        timeout=10.0,
        message="People badge clears after Looks right",
    )

    # force=True: a sibling selection-text span sits on top of the actual
    # <input role="combobox">, intercepting the pointer event (same as the
    # glossary's language select, see test_glossary.py).
    row.get_by_role("combobox").first.click(force=True)
    page.get_by_role("option", name="No culture").click()
    row.get_by_text("Set by you").wait_for(state="visible", timeout=10_000)


def test_doesnt_fit_flag_shown(app, page):
    world = seed_world(app.root, project="ai-review-doesnt-fit")
    place_culture(world, CULTURE_FILE)
    place_glossary(
        world,
        [
            {
                "text": "Marigold",
                "language": "taelrik",
                "kind": "person",
                "doesnt_fit": True,
                "origin": {"by": "ai_free"},
            }
        ],
    )

    open_scene(page, world.scene_path)
    _open_cultures_glossary_tab(page)

    glossary = page.locator(".glossary-view")
    glossary.wait_for(state="visible", timeout=15_000)

    detail = page.get_by_test_id("glossary-detail")
    detail.wait_for(state="visible", timeout=10_000)
    detail.get_by_text("Doesn't fit Taelrik").wait_for(state="visible", timeout=10_000)
    detail.get_by_text("Not picked from a generator").wait_for(
        state="visible", timeout=10_000
    )

    row = glossary.locator(".glossary-row", has_text="Marigold")
    row.locator(".mdi-alert-outline").wait_for(state="visible", timeout=10_000)


def test_addition_arriving_while_editing(app, page):
    world = seed_world(app.root, project="ai-review-addition")
    place_culture(world, CULTURE_FILE)
    _add_addition(world, "customs", "Addition A original text.")

    open_scene(page, world.scene_path)
    _open_world_editor_cultures(page)

    addition_boxes = page.locator(".addition-box")
    addition_boxes.first.wait_for(state="visible", timeout=15_000)
    assert addition_boxes.count() == 1

    box_a = addition_boxes.nth(0)
    # `.first`: auto-grow textareas render a second, hidden "sizer" textarea.
    textarea_a = box_a.locator("textarea").first
    textarea_a.fill("half-typed")
    # Deliberately no blur: the box is left mid-edit while addition B
    # arrives, below.

    _add_addition(world, "customs", "Addition B text.")
    send_backend(page, {"type": "cultures", "action": "get_world"})

    wait_until(
        lambda: addition_boxes.count() == 2,
        timeout=15.0,
        message="addition B's box appears",
    )

    box_b = addition_boxes.nth(1)
    textarea_b = box_b.locator("textarea").first
    # Textarea values aren't visible to text locators: read them directly.
    assert textarea_b.input_value() == "Addition B text."
    assert textarea_a.input_value() == "half-typed"
