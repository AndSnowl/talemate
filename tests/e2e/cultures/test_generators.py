"""Cultures runbook checks 11-13: the Generators tab's Roll button, editing
a pattern right before rolling, and a broken reject rule.

See docs/superpowers/plans/2026-10-17-cultures-foundation-followups.md,
"Manual checks" 11-13.
"""

from e2e.cultures._ui import (
    CULTURE_FILE,
    open_world_editor_cultures,
    wait_for_json,
    wait_until,
)
from e2e.seed import open_scene, place_culture, seed_world


def _open_generators_tab(page):
    open_world_editor_cultures(page)
    page.get_by_role("tab", name="Generators", exact=True).click()


def _generator_card(page, name):
    # Scoped to .generator-list: an unscoped ".v-card" also matches the
    # World Editor's own outermost root card (an ancestor of everything,
    # so its text contains every generator's name too); see task 4's
    # report. Scoping to a descendant of the generator list's own root div
    # rules that ancestor out entirely.
    return page.locator(".generator-list .v-card", has_text=name)


def _generator_names(card):
    return card.locator(".generator-out .v-chip")


def _rows_after_label(card, label_text):
    label = card.get_by_text(label_text, exact=True)
    return label.locator("xpath=following-sibling::div[contains(@class, 'd-flex')]")


def _pattern_input(card, index=0):
    return _rows_after_label(card, "Patterns").nth(index).locator("input")


def _reject_input(card, index=0):
    return _rows_after_label(card, "Reject rules").nth(index).locator("input")


def test_runbook_11_roll_on_two_cards_shows_only_its_own_names(app, page):
    world = seed_world(app.root, project="rb11")
    place_culture(world, CULTURE_FILE)
    open_scene(page, world.scene_path)
    _open_generators_tab(page)

    male_card = _generator_card(page, "Given names (male)")
    family_card = _generator_card(page, "Family names")
    male_card.wait_for(state="visible", timeout=15_000)
    family_card.get_by_text("Click Roll to preview names.").wait_for(
        state="visible", timeout=10_000
    )

    male_card.get_by_role("button", name="Roll").click()
    wait_until(
        lambda: _generator_names(male_card).count() > 0,
        timeout=15.0,
        message="no names rolled for Given names (male)",
    )
    # The other card is untouched: still just the placeholder hint, no chips.
    assert _generator_names(family_card).count() == 0
    family_card.get_by_text("Click Roll to preview names.").wait_for(
        state="visible", timeout=5_000
    )

    male_names = set(_generator_names(male_card).all_inner_texts())
    assert male_names

    family_card.get_by_role("button", name="Roll").click()
    wait_until(
        lambda: _generator_names(family_card).count() > 0,
        timeout=15.0,
        message="no names rolled for Family names",
    )
    # Rolling the second card left the first card's own result untouched.
    assert set(_generator_names(male_card).all_inner_texts()) == male_names


def test_runbook_12_edit_pattern_then_roll_immediately_returns_names(app, page):
    world = seed_world(app.root, project="rb12")
    place_culture(world, CULTURE_FILE)
    open_scene(page, world.scene_path)
    _open_generators_tab(page)

    card = _generator_card(page, "Family names")
    card.wait_for(state="visible", timeout=15_000)

    # Edit the first pattern, then click Roll straight away, without
    # leaving the field first. Clicking Roll blurs the pattern field
    # (which saves it via patch_culture) before its own click handler
    # fires, so the save reaches the server before the roll request does.
    _pattern_input(card, 0).fill("CVC[varn|dask]")
    card.get_by_role("button", name="Roll").click()

    wait_until(
        lambda: _generator_names(card).count() > 0,
        timeout=15.0,
        message="no names rolled right after editing a pattern",
    )
    assert not card.locator(".text-error").count()

    # The edit itself really did reach disk (not just "didn't crash").
    wait_for_json(
        world.world_dir / "cultures" / "taelrik.json",
        lambda c: c["language"]["generators"][1]["patterns"][0] == "CVC[varn|dask]",
        message="pattern edit never reached disk",
    )


def test_runbook_13_invalid_reject_rule_shows_error_and_roll_does_not_hang(app, page):
    world = seed_world(app.root, project="rb13")
    place_culture(world, CULTURE_FILE)
    open_scene(page, world.scene_path)
    _open_generators_tab(page)

    card = _generator_card(page, "Given names (male)")
    card.wait_for(state="visible", timeout=15_000)

    _reject_input(card, 0).fill("[")
    roll_button = card.get_by_role("button", name="Roll")
    roll_button.click()

    # Clicking Roll blurs the reject field first, saving it via
    # patch_culture -- which the server refuses (an invalid regex), and
    # reports as a readable, app-wide error.
    page.get_by_text("invalid reject rule").wait_for(state="visible", timeout=15_000)

    # The failed save left the generator unchanged on disk, so the roll
    # request (processed right after, on the same connection) still uses
    # the last *valid* reject rule and completes -- the button's own
    # spinner isn't left hanging. Bounded poll, not a fixed sleep.
    wait_until(
        lambda: roll_button.get_attribute("aria-busy") != "true",
        timeout=5.0,
        message="Roll button's spinner never cleared",
    )
