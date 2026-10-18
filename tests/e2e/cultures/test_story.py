"""E2E: foreign-word highlights in the story, the unreviewed-name dot, and
the app-level World Editor badge (plan 3, task 5).

See .superpowers/sdd/2026-10-18-cultures-story/task-5-brief.md.
"""

from __future__ import annotations

from pathlib import Path

from e2e.cultures._ui import (
    APP_BAR,
    CULTURE_FILE,
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

# Mirrors e2e.seed._BACKEND_SOCKET_JS: the app's own backend socket (open,
# not vite's HMR socket), already live by the time a test runs (installed
# by seed.SOCKET_HOOK_JS before the page's own code runs).
_BACKEND_SOCKET_JS = (
    "() => (window.__e2eSockets || []).filter("
    "(s) => s.readyState === WebSocket.OPEN && s.protocol !== 'vite-hmr'"
    ").pop()"
)


def _watch_cultures_story_frames(page) -> None:
    """Start recording every `{"type":"cultures","action":"story"}` frame
    the backend socket receives into `window.__e2eCulturesStoryFrames`.

    Must be called before `open_scene` (which reuses the same socket): the
    story reply for "no shared world" produces no visible DOM change (no
    highlights, no badge), so a test asserting their *absence* needs a
    positive sign the reply actually arrived and was processed — otherwise
    it can pass before the cultures plugin has said anything at all.
    """
    page.wait_for_function(f"!!({_BACKEND_SOCKET_JS})()", timeout=30_000)
    page.evaluate(
        f"""() => {{
            window.__e2eCulturesStoryFrames = [];
            const sock = ({_BACKEND_SOCKET_JS})();
            sock.addEventListener('message', (event) => {{
                try {{
                    const data = JSON.parse(event.data);
                    if (data && data.type === 'cultures' && data.action === 'story') {{
                        window.__e2eCulturesStoryFrames.push(data);
                    }}
                }} catch (e) {{ /* not JSON, or not a cultures frame */ }}
            }});
        }}"""
    )


def _wait_for_cultures_story_frame(page, timeout: float = 15.0) -> None:
    """Block until `_watch_cultures_story_frames` has recorded at least one
    `story` frame, then give Vue's reactive render queue a brief settle."""
    wait_until(
        lambda: page.evaluate("() => (window.__e2eCulturesStoryFrames || []).length")
        > 0,
        timeout=timeout,
        message="a cultures 'story' websocket frame to arrive",
    )
    page.wait_for_timeout(250)


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

# Pulled out of `_seed_story` (task 7) so `test_review_jump_to_missing_entry_is_harmless`
# can re-place the same seed minus one entry, without the frontend being told
# (no `review_glossary_entry`/`get_story` push accompanies a direct `place_glossary` call).
_SEED_GLOSSARY_ENTRIES = [
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
]


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

    place_glossary(world, _SEED_GLOSSARY_ENTRIES)

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

    # Open the World Editor only — its tab bar renders every sub-tab's
    # header eagerly, so the Cultures tab's badge should already read "1"
    # here without ever clicking into the Cultures tab (which would mount
    # WorldStateManagerCultures and could otherwise mask a regression to
    # the old per-tab counts mechanism).
    open_world_editor(page)

    cultures_tab = page.locator(".v-tab", has_text="Cultures")
    cultures_tab.wait_for(state="visible", timeout=15_000)
    cultures_badge = cultures_tab.locator(".v-badge")
    cultures_badge.wait_for(state="visible", timeout=15_000)
    assert cultures_badge.inner_text().strip() == "1"


def test_foreign_bubble_curse(app, page):
    world = _seed_story(app, "story-foreign-bubble-curse")
    open_scene(page, world.scene_path)

    curse_span = page.locator(".scene-foreign", has_text="Rhok tal’dun")
    curse_span.first.wait_for(state="visible", timeout=30_000)
    curse_span.first.click()

    card = page.get_by_test_id("foreign-word-card")
    card.wait_for(state="visible", timeout=15_000)
    card_text = card.inner_text()
    assert "curse" in card_text
    assert "Taelrik" in card_text

    translation = card.get_by_test_id("foreign-translation")
    assert translation.inner_text().strip() == "Rot your roots!"

    breakdown_text = card.get_by_test_id("foreign-breakdown").inner_text()
    assert "rhok" in breakdown_text and "rot" in breakdown_text
    assert "dun" in breakdown_text and "roots" in breakdown_text

    assert "Common, coarse. Spat, not said." in card_text

    card.get_by_role("button", name="Open in Taelrik").wait_for(
        state="visible", timeout=5_000
    )


def test_foreign_bubble_word_has_no_breakdown(app, page):
    world = _seed_story(app, "story-foreign-bubble-word")
    open_scene(page, world.scene_path)

    word_span = page.locator(".scene-foreign", has_text="saervik")
    word_span.first.wait_for(state="visible", timeout=30_000)
    word_span.first.click()

    card = page.get_by_test_id("foreign-word-card")
    card.wait_for(state="visible", timeout=15_000)

    translation = card.get_by_test_id("foreign-translation")
    assert translation.inner_text().strip() == "river-runner; a flat ferry boat"
    assert "word" in card.inner_text()
    assert card.get_by_test_id("foreign-breakdown").count() == 0


def test_name_bubble_language_section(app, page):
    world = _seed_story(app, "story-name-bubble-language")
    open_scene(page, world.scene_path)

    kethrun = page.locator('.scene-entity[data-entity-name="Kethrun"]')
    kethrun.first.wait_for(state="visible", timeout=30_000)
    kethrun.first.click()

    snapshot = page.locator(".entity-tooltip-snapshot")
    snapshot.wait_for(state="visible", timeout=15_000)
    assert "The ferryman." in snapshot.inner_text()

    section = page.get_by_test_id("name-language-section")
    section.wait_for(state="visible", timeout=15_000)
    section_text = section.inner_text()
    assert "Taelrik" in section_text
    assert "“ford-born”" in section_text

    culture_row = page.get_by_test_id("name-culture-row")
    assert "Worked out by the AI · picked from the Veldhaer mix" in culture_row.inner_text()

    review_note = page.get_by_test_id("name-unreviewed-note")
    assert "Picked from Given names (male)." in review_note.inner_text()

    page.get_by_test_id("name-review-button").wait_for(state="visible", timeout=5_000)


def test_unwritable_name_bubble(app, page):
    world = _seed_story(app, "story-unwritable-name-bubble")
    open_scene(page, world.scene_path)

    khaz_rull = page.locator('.scene-entity[data-entity-name="Khaz-Rull"]')
    khaz_rull.first.wait_for(state="visible", timeout=30_000)
    khaz_rull.first.click()

    true_name = page.get_by_test_id("name-true-name")
    true_name.wait_for(state="visible", timeout=15_000)
    true_name_text = true_name.inner_text()
    assert "three falling hums ending in a tongue-click" in true_name_text
    # The rendering row's culture-name label is uppercased by CSS
    # (the mockup's `.langline .k` style), so match case-insensitively.
    assert "taelrik" in true_name_text.lower()
    assert "Khaz-Rull" in true_name_text


def test_place_bubble_inherited_culture(app, page):
    world = _seed_story(app, "story-place-bubble-inherited")

    # Veldhaer's place chip comes from `world_state` (independent of the
    # cultures `story` reply), so a race could let the absence check below
    # pass before the cultures plugin has said anything at all — watch for
    # the frame and wait for it before asserting an absence.
    _watch_cultures_story_frames(page)
    open_scene(page, world.scene_path)
    _wait_for_cultures_story_frame(page)

    veldhaer = page.locator('.scene-entity[data-entity-name="Veldhaer"]')
    veldhaer.first.wait_for(state="visible", timeout=30_000)
    veldhaer.first.click()

    culture_row = page.get_by_test_id("name-culture-row")
    culture_row.wait_for(state="visible", timeout=15_000)
    assert "From The Taelrik Reach" in culture_row.inner_text()

    assert page.get_by_test_id("name-unreviewed-note").count() == 0


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

    _watch_cultures_story_frames(page)
    open_scene(page, scene_path)

    page.get_by_text("Khaz-Rull wore its collar of cloud").wait_for(
        state="visible", timeout=30_000
    )
    _wait_for_cultures_story_frame(page)

    assert page.locator(".scene-foreign").count() == 0
    assert page.get_by_test_id("app-tab-badge-world").count() == 0

    for error in page.console_errors:
        assert "TypeError" not in error
        assert "cultures" not in error


def test_review_button_opens_glossary_entry(app, page):
    world = _seed_story(app, "story-kethrun-review")
    open_scene(page, world.scene_path)

    kethrun = page.locator('.scene-entity[data-entity-name="Kethrun"]')
    kethrun.first.wait_for(state="visible", timeout=30_000)
    kethrun.first.click()

    page.get_by_test_id("name-review-button").click()

    cultures_tab = page.locator(".v-tab", has_text="Cultures")
    cultures_tab.wait_for(state="visible", timeout=15_000)
    assert cultures_tab.get_attribute("aria-selected") == "true"

    glossary_sub_tab = page.locator(".v-tab", has_text="Glossary")
    glossary_sub_tab.wait_for(state="visible", timeout=15_000)
    assert glossary_sub_tab.get_attribute("aria-selected") == "true"

    selected_row = page.locator(".glossary-row-selected")
    selected_row.wait_for(state="visible", timeout=15_000)
    assert "Kethrun" in selected_row.inner_text()


def test_review_unassigned_name(app, page):
    world = _seed_story(app, "story-review-unassigned")
    open_scene(page, world.scene_path)

    quillister = page.locator('.scene-entity[data-entity-name="Quillister House"]')
    quillister.first.wait_for(state="visible", timeout=30_000)
    quillister.first.click()

    page.get_by_test_id("name-review-button").click()

    unassigned_card = page.get_by_text("Unassigned names").first
    unassigned_card.wait_for(state="visible", timeout=15_000)

    selected_row = page.locator(".glossary-row-selected")
    selected_row.wait_for(state="visible", timeout=15_000)
    assert "Quillister House" in selected_row.inner_text()


def test_open_in_culture_phrase_and_word(app, page):
    world = _seed_story(app, "story-open-in-culture")
    open_scene(page, world.scene_path)

    curse_span = page.locator(".scene-foreign", has_text="Rhok tal’dun")
    curse_span.first.wait_for(state="visible", timeout=30_000)
    curse_span.first.click()

    curse_card = page.get_by_test_id("foreign-word-card")
    curse_card.wait_for(state="visible", timeout=15_000)
    curse_card.get_by_role("button", name="Open in Taelrik").click()

    phrase_focus = page.locator(".phrase-focus")
    phrase_focus.wait_for(state="visible", timeout=15_000)
    assert "Rhok tal'dun!" in phrase_focus.inner_text()

    # Back on the scene tab (always first among the app bar's tabs while a
    # scene is active, whatever the scene's own title is).
    page.locator(f"{APP_BAR} .v-tab").first.click()

    saervik_span = page.locator(".scene-foreign", has_text="saervik")
    saervik_span.first.wait_for(state="visible", timeout=30_000)
    saervik_span.first.click()

    word_card = page.get_by_test_id("foreign-word-card")
    word_card.wait_for(state="visible", timeout=15_000)
    word_card.get_by_role("button", name="Open in Taelrik").click()

    selected_row = page.locator(".glossary-row-selected")
    selected_row.wait_for(state="visible", timeout=15_000)
    assert "saervik" in selected_row.inner_text()

    all_filter_chip = page.locator(".v-chip", has_text="All (").first
    assert "v-chip--variant-flat" in (all_filter_chip.get_attribute("class") or "")


def test_change_culture_opens_people(app, page):
    world = _seed_story(app, "story-change-culture-people")
    open_scene(page, world.scene_path)

    kethrun = page.locator('.scene-entity[data-entity-name="Kethrun"]')
    kethrun.first.wait_for(state="visible", timeout=30_000)
    kethrun.first.click()

    culture_row = page.get_by_test_id("name-culture-row")
    culture_row.wait_for(state="visible", timeout=15_000)
    culture_row.get_by_role("button", name="Change").click()

    focus_row = page.locator(".people-row-focus")
    focus_row.wait_for(state="visible", timeout=15_000)
    assert "Kethrun" in focus_row.inner_text()


def test_review_jump_to_missing_entry_is_harmless(app, page):
    world = _seed_story(app, "story-review-missing-entry")
    open_scene(page, world.scene_path)

    kethrun = page.locator('.scene-entity[data-entity-name="Kethrun"]')
    kethrun.first.wait_for(state="visible", timeout=30_000)
    kethrun.first.click()

    review_button = page.get_by_test_id("name-review-button")
    review_button.wait_for(state="visible", timeout=15_000)

    # Remove g-kethrun on disk only — no push accompanies a direct
    # `place_glossary` call, so the still-open bubble and its Review
    # button stay exactly as they were.
    remaining = [e for e in _SEED_GLOSSARY_ENTRIES if e["id"] != "g-kethrun"]
    place_glossary(world, remaining)

    review_button.click()

    # No culture got selected by the (failed) jump, so the Cultures tab
    # falls back to its own default: the first culture's own page.
    page.locator(".culture-overview").wait_for(state="visible", timeout=30_000)

    for error in page.console_errors:
        assert "TypeError" not in error
        assert "cultures" not in error

    # No stale pending target is left over: a later, valid jump still works.
    page.locator(f"{APP_BAR} .v-tab").first.click()

    saervik_span = page.locator(".scene-foreign", has_text="saervik")
    saervik_span.first.wait_for(state="visible", timeout=30_000)
    saervik_span.first.click()

    word_card = page.get_by_test_id("foreign-word-card")
    word_card.wait_for(state="visible", timeout=15_000)
    word_card.get_by_role("button", name="Open in Taelrik").click()

    selected_row = page.locator(".glossary-row-selected")
    selected_row.wait_for(state="visible", timeout=15_000)
    assert "saervik" in selected_row.inner_text()


def test_world_panel_character_chip_and_dot(app, page):
    world = _seed_story(app, "story-panel-character-chip")
    open_scene(page, world.scene_path)

    chip = page.locator('[data-chip-for="character:Kethrun"]')
    chip.wait_for(state="visible", timeout=30_000)
    assert "Taelrik" in chip.inner_text()

    panel_title = page.locator(".v-expansion-panel-title", has_text="Kethrun").first
    assert panel_title.get_attribute("aria-expanded") == "false"

    dot = chip.locator(".culture-review-dot")
    dot.wait_for(state="visible", timeout=5_000)
    dot.click()

    page.locator(".glossary-row-selected", has_text="Kethrun").wait_for(
        state="visible", timeout=15_000
    )

    # The click opened the Cultures tab (a separate top-level tab), not an
    # accordion toggle on the character's own row.
    assert panel_title.get_attribute("aria-expanded") == "false"


def test_world_panel_place_chips(app, page):
    world = _seed_story(app, "story-panel-place-chips")
    open_scene(page, world.scene_path)

    veldhaer_chip = page.locator('[data-chip-for="place:Veldhaer"]')
    veldhaer_chip.wait_for(state="visible", timeout=30_000)
    assert "Taelrik" in veldhaer_chip.inner_text()

    khaz_chip = page.locator('[data-chip-for="place:Khaz-Rull"]')
    khaz_chip.wait_for(state="visible", timeout=15_000)
    assert "Ghûn" in khaz_chip.inner_text()

    quillister_chip = page.locator('[data-chip-for="place:Quillister House"]')
    quillister_chip.wait_for(state="visible", timeout=15_000)
    assert "Taelrik" in quillister_chip.inner_text()

    dot = quillister_chip.locator(".culture-review-dot")
    dot.wait_for(state="visible", timeout=5_000)
    dot.click()

    unassigned_card = page.get_by_text("Unassigned names").first
    unassigned_card.wait_for(state="visible", timeout=15_000)

    selected_row = page.locator(".glossary-row-selected")
    selected_row.wait_for(state="visible", timeout=15_000)
    assert "Quillister House" in selected_row.inner_text()


def test_culture_focus_does_not_leak_to_a_later_culture(app, page):
    """Fix round 1 (review Important 1): a glossary jump's `cultureFocus`
    must not survive past its own CulturePage — otherwise an unrelated,
    later visit to a *different* culture (after a detour through Places)
    would open on the stale sub-tab, with a selected id that isn't even
    that culture's own.
    """
    world = _seed_story(app, "story-focus-no-leak")
    open_scene(page, world.scene_path)

    kethrun = page.locator('.scene-entity[data-entity-name="Kethrun"]')
    kethrun.first.wait_for(state="visible", timeout=30_000)
    kethrun.first.click()

    page.get_by_test_id("name-review-button").click()
    page.locator(".glossary-row-selected", has_text="Kethrun").wait_for(
        state="visible", timeout=15_000
    )

    # Unrelated navigation within the Cultures tab: Places, then a
    # different culture (Ghûn, not Taelrik).
    page.get_by_role("option", name="Places & regions").click()
    page.locator(".place-row").first.wait_for(state="visible", timeout=15_000)

    page.get_by_role("option", name="Ghûn").click()

    # Ghûn must open on its own default sub-tab (Culture) — not Taelrik's
    # stale `focus` (Glossary, with an id that belongs to Taelrik).
    page.locator(".culture-overview").wait_for(state="visible", timeout=15_000)
    assert page.locator(".glossary-row-selected").count() == 0
