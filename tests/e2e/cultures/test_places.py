"""Cultures runbook checks 14-17: place nesting, the culture-share slider,
the parent select's cycle guard, and deleting a place with children.

See docs/superpowers/plans/2026-10-17-cultures-foundation-followups.md,
"Manual checks" 14-17.

All four checks share one seeded tree (The Taelrik Reach -> Birch Coast ->
Ilsara) and a second culture, Elsiri, which the fixture culture file
doesn't include -- both are written straight to the shared world's files
before ``open_scene``, the same technique checks 7-9 use for play
additions and glossary entries that the fixture has none of.
"""

import json

from e2e.cultures._ui import CULTURE_FILE, open_places_view, wait_for_json, wait_until
from e2e.seed import open_scene, place_culture, seed_world

ELSIRI_CULTURE = {
    "id": "elsiri",
    "name": "Elsiri",
    "color": "#4FC3F7",
    "description": "",
    "language": {"name": "Elsiri", "level": "naming"},
    "customs": [],
    "food": "",
    "holidays": [],
    "additions": [],
    "source_file": "",
    "imported_at": "",
}


def _seed_elsiri(world) -> None:
    path = world.world_dir / "cultures" / "elsiri.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ELSIRI_CULTURE), encoding="utf-8")


def _place(place_id, name, kind, parent_id=None, cultures=None) -> dict:
    """A plain dict matching Place (src/talemate/cultures/models.py)."""
    return {
        "id": place_id,
        "name": name,
        "kind": kind,
        "parent_id": parent_id,
        "cultures": cultures or [],
        "world_entry_id": None,
        "set_by": "owner",
        "unsure": False,
        "note": "",
    }


# The Taelrik Reach (country, 100% Taelrik) -> Birch Coast (region, a
# 90/10 Elsiri/Taelrik pocket) -> Ilsara (village, no cultures of its
# own -- inherits Birch Coast's mix). Matches tests/cultures/test_places.py.
REACH_BIRCH_ILSARA = [
    _place(
        "reach",
        "The Taelrik Reach",
        "country",
        cultures=[{"culture_id": "taelrik", "share": 100}],
    ),
    _place(
        "birch",
        "Birch Coast",
        "region",
        parent_id="reach",
        cultures=[
            {"culture_id": "elsiri", "share": 90},
            {"culture_id": "taelrik", "share": 10},
        ],
    ),
    _place("ilsara", "Ilsara", "village", parent_id="birch"),
]


def _seed_places(world, places) -> None:
    path = world.world_dir / "places.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"format_version": 1, "places": places}), encoding="utf-8"
    )


def _seed_tree(world) -> None:
    place_culture(world, CULTURE_FILE)
    _seed_elsiri(world)
    _seed_places(world, REACH_BIRCH_ILSARA)


def _place_row(page, name):
    # Ilsara's own row also contains the text "Birch Coast" (its "Cultures"
    # column reads "from Birch Coast", since it has no cultures of its
    # own) -- has_text against the whole row would match both. The name
    # itself only ever appears in a row's first cell, so filter on that.
    return page.locator("tr.place-row").filter(
        has=page.locator("td:nth-child(1)", has_text=name)
    )


def test_runbook_14_birch_coast_and_ilsara_read_the_mix(app, page):
    world = seed_world(app.root, project="rb14")
    _seed_tree(world)
    open_scene(page, world.scene_path)
    open_places_view(page)

    _place_row(page, "Birch Coast").click()
    meaning = page.locator(".meaning-box")
    meaning.wait_for(state="visible", timeout=15_000)
    # Birch Coast has cultures of its own, so there's no "takes them from" box.
    assert page.locator(".origin-box").count() == 0
    text = meaning.inner_text()
    assert "about 9 in 10 Elsiri" in text
    assert "Most also speak Taelrik, the language of The Taelrik Reach." in text

    _place_row(page, "Ilsara").click()
    origin = page.locator(".origin-box")
    origin.wait_for(state="visible", timeout=15_000)
    assert "Takes them from Birch Coast." in origin.inner_text()
    ilsara_text = page.locator(".meaning-box").inner_text()
    assert "about 9 in 10 Elsiri" in ilsara_text
    assert "Most also speak Taelrik, the language of The Taelrik Reach." in ilsara_text


def test_runbook_15_dragging_a_share_slider_and_releasing_sums_to_100(app, page):
    world = seed_world(app.root, project="rb15")
    _seed_tree(world)
    open_scene(page, world.scene_path)
    open_places_view(page)

    _place_row(page, "Birch Coast").click()
    elsiri_row = page.locator("div.d-flex.align-center.ga-3.mb-1", has_text="Elsiri")
    elsiri_row.wait_for(state="visible", timeout=15_000)
    share_value = elsiri_row.locator(".share-value")
    assert share_value.inner_text().strip() == "90%"

    # The slider's own mousedown/mousemove/mouseup listeners are on
    # .v-slider__container specifically (not the whole .v-slider wrapper).
    slider = elsiri_row.locator(".v-slider__container")
    box = slider.bounding_box()
    y = box["y"] + box["height"] / 2
    start_x = box["x"] + box["width"] * 0.1
    end_x = box["x"] + box["width"] * 0.5
    # A real drag-and-release (mousedown, mousemove, mouseup), not a click:
    # the slider's @end handler (which saves) fires only on release, not
    # from a plain click or from keyboard adjustment.
    page.mouse.move(start_x, y)
    page.mouse.down()
    page.mouse.move(end_x, y, steps=10)
    page.mouse.up()

    places_path = world.world_dir / "places.json"

    def _birch(data):
        return next(p for p in data["places"] if p["id"] == "birch")

    saved = wait_for_json(
        places_path,
        lambda data: sum(cs["share"] for cs in _birch(data)["cultures"]) == 100
        and any(
            cs["culture_id"] == "elsiri" and cs["share"] != 90
            for cs in _birch(data)["cultures"]
        ),
        message="slider drag never saved a changed, normalised mix",
    )
    shares = {cs["culture_id"]: cs["share"] for cs in _birch(saved)["cultures"]}
    assert sum(shares.values()) == 100
    assert shares != {"elsiri": 90, "taelrik": 10}

    # The UI reflects the saved mix too, without a reload.
    wait_until(
        lambda: share_value.inner_text().strip() != "90%",
        timeout=10.0,
        message="share label never updated after the drag",
    )


def test_runbook_16_taelrik_reach_parent_select_excludes_its_own_descendant(app, page):
    world = seed_world(app.root, project="rb16")
    _seed_tree(world)
    open_scene(page, world.scene_path)
    open_places_view(page)

    _place_row(page, "The Taelrik Reach").click()
    parent_select = page.get_by_role("combobox", name="Parent")
    parent_select.wait_for(state="visible", timeout=15_000)
    # force=True: a sibling selection-text span sits on top of the actual
    # <input role="combobox">, intercepting the pointer event.
    parent_select.click(force=True)

    page.get_by_role("option", name="No parent (root)").wait_for(
        state="visible", timeout=10_000
    )
    assert page.get_by_role("option", name="Ilsara", exact=True).count() == 0


def test_runbook_17_deleting_a_place_with_children_asks_where_they_go(app, page):
    world = seed_world(app.root, project="rb17")
    _seed_tree(world)
    open_scene(page, world.scene_path)
    open_places_view(page)

    _place_row(page, "Birch Coast").click()
    page.locator(".actions-row").get_by_role("button", name="Delete").click()

    menu = page.locator(".v-overlay__content", has_text="Delete Birch Coast?")
    menu.wait_for(state="visible", timeout=10_000)
    assert "1 place nested under it need a new parent" in menu.inner_text()

    menu.get_by_role("button", name="Confirm").click()

    places_path = world.world_dir / "places.json"
    wait_for_json(
        places_path,
        lambda data: not any(p["id"] == "birch" for p in data["places"])
        and next(p for p in data["places"] if p["id"] == "ilsara")["parent_id"]
        == "reach",
        message="delete never moved Ilsara under The Taelrik Reach",
    )

    # The UI agrees without a reload: Birch Coast is gone, Ilsara remains.
    _place_row(page, "Birch Coast").wait_for(state="hidden", timeout=10_000)
    _place_row(page, "Ilsara").wait_for(state="visible", timeout=10_000)
