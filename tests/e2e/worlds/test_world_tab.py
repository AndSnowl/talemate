"""The fantasymate world screens: the Worlds home, the World tab, thing
pages and the create box.

The worlds are seeded through `talemate.world` in the app's worlds folder
(`seed.seed_fm_world`). No model is asked anything: the create box's
preview comes from the fixed preview file (the `fixed_preview` fixture).
Every test seeds its own uniquely named world, since the app (and its
worlds folder) is shared by the session.
"""

from __future__ import annotations

import uuid

from e2e.seed import seed_fm_world

TIMEOUT_MS = 30_000

MAREN = {
    "kind": "character",
    "name": "Maren Vos",
    "born": 290,
    "facts": [
        {
            "category": "appearance",
            "text": "Heron tattoo on her left forearm.",
            "since": 304,
        },
        {
            "category": "relationship",
            "text": "Owes Oskar Dell a life-debt.",
            "since": 312,
        },
        {"category": "personality", "text": "Quick laugh, quicker knife."},
    ],
}


def _world_name(stem: str) -> str:
    return f"{stem} {uuid.uuid4().hex[:6]}"


def _open_world(page, name: str) -> None:
    """Open `name` from the Worlds home (the app's first screen)."""
    home = page.get_by_test_id("worlds-home")
    home.wait_for(state="visible", timeout=TIMEOUT_MS)
    # the page listed the worlds before the test seeded its own
    home.get_by_role("button", name="Refresh worlds").click()
    row = home.get_by_test_id("world-row").filter(has_text=name)
    row.get_by_role("button", name="Open").click()
    page.get_by_test_id("open-world").filter(has_text=name).wait_for(
        state="visible", timeout=TIMEOUT_MS
    )


def _world_tab(page) -> None:
    page.get_by_role("tab", name="World", exact=True).click()
    page.get_by_test_id("world-tab").wait_for(state="visible", timeout=TIMEOUT_MS)


def _open_thing(page, name: str):
    page.get_by_test_id("thing-card").filter(has_text=name).click()
    thing = page.get_by_test_id("thing-page")
    thing.get_by_test_id("thing-name").filter(has_text=name).wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    return thing


def _fact(thing, text: str):
    return thing.get_by_test_id("fact-row").filter(has_text=text)


def test_worlds_home_lists_and_opens(app, page):
    name = _world_name("Vael")
    seed_fm_world(
        app.root,
        name,
        present_year=312,
        things=[MAREN],
        scenes=[{"name": "The Ferryman", "start": 312, "player": "Maren Vos"}],
    )

    # the Worlds home is the first screen, and lists the seeded world
    page.get_by_role("tab", name="Worlds", exact=True, selected=True).wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    _open_world(page, name)

    # the open world's scenes, each with a Play button
    scene = page.get_by_test_id("world-scene").filter(has_text="The Ferryman")
    scene.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert scene.get_by_role("button", name="Play").is_visible()

    # the World tab shows the world's characters
    _world_tab(page)
    page.get_by_test_id("thing-card").filter(has_text="Maren Vos").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert page.get_by_test_id("kind-culture").get_by_text("via skill").is_visible()


def test_thing_page_shows_facts_and_date_view(app, page):
    name = _world_name("Sallow")
    seed_fm_world(app.root, name, present_year=318, things=[MAREN])
    _open_world(page, name)
    _world_tab(page)
    thing = _open_thing(page, "Maren Vos")

    # at the latest date, every fact shows, with its category
    debt = _fact(thing, "Owes Oskar Dell a life-debt.")
    debt.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "relationship" in debt.inner_text()
    assert _fact(thing, "Heron tattoo on her left forearm.").is_visible()

    # as of 310 the life-debt (from 312) hasn't started yet
    thing.get_by_test_id("as-of-button").click()
    picker = page.get_by_test_id("as-of-picker")
    picker.get_by_label("Year").fill("310")
    picker.get_by_role("button", name="View").click()

    thing.get_by_test_id("as-of-button").filter(has_text="310").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    debt.wait_for(state="hidden", timeout=TIMEOUT_MS)
    assert _fact(thing, "Heron tattoo on her left forearm.").is_visible()
    assert "age 20" in thing.get_by_test_id("field-born").inner_text()


def test_add_fact_updates_page(app, page):
    name = _world_name("Reedmarch")
    seed_fm_world(app.root, name, present_year=318, things=[MAREN])
    _open_world(page, name)
    _world_tab(page)
    thing = _open_thing(page, "Maren Vos")

    thing.get_by_role("button", name="Add fact").click()
    form = thing.get_by_test_id("fact-form")
    form.get_by_label("Fact", exact=True).fill("A pale scar along her jaw.")
    form.get_by_label("From year").fill("316")
    form.get_by_role("button", name="Save").click()

    scar = _fact(thing, "A pale scar along her jaw.")
    scar.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "316" in scar.inner_text()
    # the new fact is on the timeline strip too
    thing.get_by_test_id("timeline-strip").get_by_text("316").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )


def test_create_box_preview_accept(app, page, fixed_preview):
    name = _world_name("Lowmarsh")
    seed_fm_world(app.root, name, present_year=318, things=[MAREN])
    fixed_preview(
        {
            "name": "Oskar Dell",
            "facts": [
                {
                    "category": "background",
                    "text": "Has run the Sallow ferry for thirty years.",
                },
                {"category": "personality", "text": "Never forgets a debt."},
            ],
            "prose": {
                "description": "Oskar Dell is a weathered ferryman.",
                "personality": "He keeps a ledger of every favour.",
            },
        },
    )
    _open_world(page, name)
    _world_tab(page)

    box = page.get_by_test_id("create-box")
    box.get_by_label("Describe it").fill("A grizzled ferryman who owes the Wardens.")
    box.get_by_role("button", name="Create").click()

    preview = page.get_by_test_id("create-preview")
    preview.get_by_text("Oskar Dell is a weathered ferryman.").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert preview.get_by_text("Never forgets a debt.").is_visible()

    # switching kinds and back remounts the box; the preview keeps its name
    page.get_by_test_id("kind-place").click()
    preview.wait_for(state="hidden", timeout=TIMEOUT_MS)
    page.get_by_test_id("kind-character").click()
    preview.get_by_text("Oskar Dell is a weathered ferryman.").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert preview.get_by_label("Name").input_value() == "Oskar Dell"
    preview.get_by_role("button", name="Accept").click()

    # accepting opens the new thing's page, and it's listed with the others
    thing = page.get_by_test_id("thing-page")
    thing.get_by_test_id("thing-name").filter(has_text="Oskar Dell").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert _fact(thing, "Has run the Sallow ferry for thirty years.").is_visible()
    assert thing.get_by_text("He keeps a ledger of every favour.").is_visible()
    thing.get_by_role("button", name="Back").click()
    page.get_by_test_id("thing-card").filter(has_text="Oskar Dell").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )


def test_set_the_present_year(app, page):
    """A world made outside the Worlds home can sit at year 1; its present
    year is set from the open world."""

    name = _world_name("Tarn")
    seed_fm_world(app.root, name, present_year=1)
    _open_world(page, name)
    present = page.get_by_test_id("world-present")
    present.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert present.inner_text() == "1"

    page.get_by_test_id("edit-present").click()
    editor = page.get_by_test_id("present-editor")
    editor.get_by_label("Present year").fill("1200")
    editor.get_by_role("button", name="Set").click()
    present.filter(has_text="1200").wait_for(state="visible", timeout=TIMEOUT_MS)


def test_delete_a_thing_after_its_reference_check(app, page):
    """Deleting asks first: an unused thing goes on Delete; a thing a scene
    uses lists that scene in the dialog before anything is deleted."""

    name = _world_name("Ashfall")
    spare = {"kind": "character", "name": "Vasha Two", "facts": []}
    seed_fm_world(
        app.root,
        name,
        present_year=318,
        things=[MAREN, spare],
        scenes=[{"name": "The Ferryman", "start": 312, "player": "Maren Vos"}],
    )
    _open_world(page, name)
    _world_tab(page)

    # an unused thing: the dialog says what deleting does, and finds nothing
    thing = _open_thing(page, "Vasha Two")
    thing.get_by_test_id("delete-thing").click()
    dialog = page.get_by_test_id("delete-dialog")
    dialog.wait_for(state="visible", timeout=TIMEOUT_MS)
    ramifications = dialog.get_by_test_id("delete-ramifications").inner_text()
    assert "unknown" in ramifications
    # no undo in the app yet, so the dialog doesn't promise one
    assert "no way to restore it from the app yet" in ramifications
    assert dialog.get_by_test_id("delete-no-references").is_visible()
    dialog.get_by_role("button", name="Delete").click()

    # back on the kind list, without it
    dialog.wait_for(state="hidden", timeout=TIMEOUT_MS)
    page.get_by_test_id("thing-card").filter(has_text="Maren Vos").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    page.get_by_test_id("thing-card").filter(has_text="Vasha Two").wait_for(
        state="hidden", timeout=TIMEOUT_MS
    )

    # a thing a scene plays: the dialog lists the scene; Cancel keeps it
    thing = _open_thing(page, "Maren Vos")
    thing.get_by_test_id("delete-thing").click()
    dialog.wait_for(state="visible", timeout=TIMEOUT_MS)
    scenes = dialog.get_by_test_id("delete-ref-scenes")
    scenes.get_by_text("The Ferryman").wait_for(state="visible", timeout=TIMEOUT_MS)
    assert dialog.get_by_test_id("delete-referenced").is_visible()
    dialog.get_by_role("button", name="Cancel").click()
    dialog.wait_for(state="hidden", timeout=TIMEOUT_MS)
    assert thing.get_by_test_id("thing-name").inner_text() == "Maren Vos"
