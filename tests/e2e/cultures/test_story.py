"""E2E: foreign-word highlights in the story, the unreviewed-name dot, and
the app-level World Editor badge (plan 3, task 5).

See .superpowers/sdd/2026-10-18-cultures-story/task-5-brief.md.
"""

from __future__ import annotations

from pathlib import Path

from e2e.cultures._ui import (
    CULTURE_FILE,
    open_cultures_tab,
    open_world_editor,
    wait_until,
)
from e2e.seed import (
    open_scene,
    place_culture,
    place_glossary,
    place_places,
    seed_scene_without_world,
    seed_world,
    send_backend,
)

GHUN_CULTURE_FILE = Path(__file__).resolve().parent / "data" / "ghun.culture.json"

M1 = (
    "The saervik ground against the shingle at Veldhaer, and Kethrun spat "
    "over the rail. Above the toll-house door someone had carved the old "
    "words: Dhun sa'ver, kaeth sa'ver. Far to the north, Khaz-Rull wore "
    "its collar of cloud."
)
M2 = (
    "“Rhok tal’dun!” Kethrun muttered at the knot. A lantern "
    "swung from the tal post near Quillister House."
)


def _seed_story(app, project, **overrides):
    """Seed a world matching task 5's brief: Veldhaer, Kethrun, two cultures
    (Taelrik, Ghûn), four places and seven fixed-id glossary entries.

    `unreviewed_total` ends up `2` (`g-kethrun`, `g-quillister`).
    """
    kwargs = dict(
        location="Veldhaer",
        messages=[{"text": M1}, {"text": M2}],
        world_state={
            "characters": {
                "Kethrun": {
                    "snapshot": "The ferryman.",
                    "emotion": "irritable",
                    "mentions": ["Kethrun"],
                },
            },
            "places": {
                "Veldhaer": {
                    "snapshot": "A grey river town at the ford.",
                    "mentions": ["Veldhaer"],
                },
                "Khaz-Rull": {
                    "snapshot": "A northern peak, lost in cloud.",
                    "mentions": ["Khaz-Rull"],
                },
                "Quillister House": {
                    "snapshot": "A toll-house by the river.",
                    "mentions": ["Quillister House"],
                },
            },
        },
        characters=[
            {
                "name": "Kethrun",
                "culture": {
                    "culture_id": "taelrik",
                    "set_by": "ai",
                    "unsure": False,
                    "reason": "picked from the Veldhaer mix",
                },
            },
        ],
    )
    kwargs.update(overrides)

    world = seed_world(app.root, project=project, **kwargs)

    place_culture(world, CULTURE_FILE)
    place_culture(world, GHUN_CULTURE_FILE)

    place_places(
        world,
        [
            {
                "id": "reach",
                "name": "The Taelrik Reach",
                "kind": "country",
                "cultures": [{"culture_id": "taelrik", "share": 100}],
            },
            {
                "id": "veldhaer",
                "name": "Veldhaer",
                "kind": "town",
                "parent_id": "reach",
            },
            {
                "id": "quillister",
                "name": "Quillister House",
                "kind": "building",
                "parent_id": "veldhaer",
            },
            {
                "id": "khaz",
                "name": "Khaz-Rull",
                "kind": "terrain",
                "cultures": [{"culture_id": "ghun", "share": 100}],
            },
        ],
    )

    place_glossary(
        world,
        [
            {
                "id": "g-kethrun",
                "text": "Kethrun",
                "language": "taelrik",
                "kind": "person",
                "meaning": "ford-born",
                "status": "unreviewed",
                "origin": {
                    "by": "ai",
                    "generator_id": "given_male",
                    "candidates": ["Kethrun", "Tovrin"],
                },
                "character_name": "Kethrun",
            },
            {
                "id": "g-veldhaer",
                "text": "Veldhaer",
                "language": "taelrik",
                "kind": "place",
                "meaning": "grey ford",
                "status": "reviewed",
                "origin": {"by": "import"},
                "place_id": "veldhaer",
            },
            {
                "id": "g-saervik",
                "text": "saervik",
                "language": "taelrik",
                "kind": "thing",
                "meaning": "river-runner; a flat ferry boat",
                "status": "reviewed",
                "origin": {"by": "import"},
            },
            {
                "id": "g-lantern",
                "text": "Lantern",
                "language": "taelrik",
                "kind": "word",
                "meaning": "a lamp",
                "status": "reviewed",
                "origin": {"by": "owner"},
            },
            {
                "id": "g-tal",
                "text": "tal",
                "language": "taelrik",
                "kind": "word",
                "meaning": "your (scornful)",
                "status": "reviewed",
                "origin": {"by": "owner"},
            },
            {
                "id": "g-quillister",
                "text": "Quillister House",
                "language": None,
                "kind": "place",
                "status": "unreviewed",
                "origin": {"by": "ai_free"},
            },
            {
                "id": "g-khaz",
                "text": "Khaz-Rull",
                "language": "ghun",
                "kind": "place",
                "true_name": "three falling hums ending in a tongue-click",
                "renderings": {"taelrik": "Khaz-Rull"},
                "status": "reviewed",
                "origin": {"by": "import"},
                "place_id": "khaz",
            },
        ],
    )

    return world


def test_foreign_words_highlighted_never_english(app, page):
    world = _seed_story(app, "story-foreign")
    open_scene(page, world.scene_path)

    foreign = page.locator(".scene-foreign")
    foreign.first.wait_for(state="visible", timeout=30_000)

    texts = {t.strip() for t in foreign.all_inner_texts()}
    assert texts == {"saervik", "Dhun sa'ver, kaeth sa'ver", "Rhok tal’dun"}

    for i in range(foreign.count()):
        font_style = foreign.nth(i).evaluate(
            "el => window.getComputedStyle(el).fontStyle"
        )
        assert font_style == "italic"

    assert "lantern" not in texts
    assert "Lantern" not in texts
    assert "tal" not in texts


def test_unreviewed_name_dot(app, page):
    world = _seed_story(app, "story-unreviewed-dot")
    open_scene(page, world.scene_path)

    unreviewed_kethrun = page.locator(
        '.scene-entity[data-entity-name="Kethrun"][data-entity-unreviewed]'
    )
    unreviewed_kethrun.first.wait_for(state="visible", timeout=30_000)
    assert unreviewed_kethrun.count() >= 1

    veldhaer = page.locator('.scene-entity[data-entity-name="Veldhaer"]').first
    veldhaer.wait_for(state="visible", timeout=30_000)
    assert veldhaer.get_attribute("data-entity-unreviewed") is None


def test_app_badge_before_cultures_tab_opened(app, page):
    world = _seed_story(app, "story-badge")
    open_scene(page, world.scene_path)

    badge = page.get_by_test_id("app-tab-badge-world")
    badge.wait_for(state="visible", timeout=30_000)
    assert badge.inner_text().strip() == "2"

    send_backend(
        page,
        {
            "type": "cultures",
            "action": "review_glossary_entry",
            "entry_id": "g-kethrun",
            "status": "reviewed",
        },
    )
    wait_until(
        lambda: badge.inner_text().strip() == "1",
        timeout=15.0,
        message="app World Editor badge to drop to 1",
    )

    open_world_editor(page)
    open_cultures_tab(page)

    cultures_tab = page.locator(".v-tab", has_text="Cultures")
    cultures_badge = cultures_tab.locator(".v-badge")
    cultures_badge.wait_for(state="visible", timeout=15_000)
    assert cultures_badge.inner_text().strip() == "1"


def test_no_world_no_highlights_or_badge(app, page):
    scene_path = seed_scene_without_world(
        app.root,
        project="story-no-world",
        messages=[{"text": M1}],
        world_state={
            "characters": {
                "Kethrun": {
                    "snapshot": "The ferryman.",
                    "emotion": "irritable",
                    "mentions": ["Kethrun"],
                },
            },
            "places": {
                "Veldhaer": {
                    "snapshot": "A grey river town at the ford.",
                    "mentions": ["Veldhaer"],
                },
            },
        },
    )

    open_scene(page, scene_path)

    page.get_by_text("Khaz-Rull wore its collar of cloud").wait_for(
        state="visible", timeout=30_000
    )

    assert page.locator(".scene-foreign").count() == 0
    assert page.get_by_test_id("app-tab-badge-world").count() == 0

    for error in page.console_errors:
        assert "TypeError" not in error
        assert "cultures" not in error
