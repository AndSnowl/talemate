"""Cultures runbook check 18: two browser tabs on the same shared world.

See docs/superpowers/plans/2026-10-17-cultures-foundation-followups.md,
"Manual checks" 18.

The backend accepts only one connected frontend at a time (see
``_active_frontend_websocket`` in ``src/talemate/server/api.py``: a second
connection attempt is rejected and closed outright). So "two tabs" here is
two separate browser contexts opening the *same* seeded world one after
the other -- tab A disconnects before tab B connects -- rather than two
live connections at once. That's also the only way two real browser tabs
against a local Talemate instance could ever work.
"""

from e2e.cultures._ui import CULTURE_FILE, open_world_editor_cultures, wait_for_json
from e2e.seed import (
    SOCKET_HOOK_JS,
    dismiss_onboarding,
    open_scene,
    place_culture,
    seed_world,
)


def test_runbook_18_two_tabs_on_the_same_world_dont_clobber_each_other(app, browser):
    world = seed_world(app.root, project="rb18")
    place_culture(world, CULTURE_FILE)
    culture_path = world.world_dir / "cultures" / "taelrik.json"

    # Tab A: edit the description, on the Culture tab, then disconnect.
    context_a = browser.new_context()
    context_a.add_init_script(SOCKET_HOOK_JS)
    try:
        page_a = context_a.new_page()
        page_a.goto(app.frontend_url)
        dismiss_onboarding(page_a)
        open_scene(page_a, world.scene_path)
        open_world_editor_cultures(page_a)

        description_a = page_a.locator(".culture-overview textarea").first
        description_a.fill("Edited from tab A, not undone by tab B.")
        description_a.blur()
        wait_for_json(
            culture_path,
            lambda c: "Edited from tab A" in c["description"],
            message="tab A's description edit never reached disk",
        )
    finally:
        context_a.close()

    # Tab B: open the same world fresh, and edit a *different* field,
    # Customs. `patch_culture` re-reads the culture from disk and replaces
    # only the field it names, so tab B's own (independently fetched, but
    # otherwise unrelated) edit must not revert tab A's description.
    context_b = browser.new_context()
    context_b.add_init_script(SOCKET_HOOK_JS)
    try:
        page_b = context_b.new_page()
        page_b.goto(app.frontend_url)
        dismiss_onboarding(page_b)
        open_scene(page_b, world.scene_path)
        open_world_editor_cultures(page_b)

        customs_card = page_b.locator(".v-card", has_text="Add custom").last
        customs_card.get_by_role("button", name="Add custom").click()
        new_custom = customs_card.locator("input").last
        new_custom.fill("Added from tab B, not undone by tab A.")
        new_custom.blur()

        final = wait_for_json(
            culture_path,
            lambda c: any("Added from tab B" in text for text in c["customs"]),
            message="tab B's custom edit never reached disk",
        )
    finally:
        context_b.close()

    # Neither tab's change was undone by the other's.
    assert "Edited from tab A" in final["description"]
    assert any("Added from tab B" in text for text in final["customs"])
