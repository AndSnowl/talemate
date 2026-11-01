"""Naming from a world scene's message box (languages 3a): its right-click
menu makes names and phrases, with the player character's languages first,
then the scene place's.

The scene setup comes from the fixed setup file and names from the fixed
language file, so no model is asked anything.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from e2e.seed import seed_fm_world
from e2e.worlds.test_languages_page import _language_fields
from e2e.worlds.test_new_scene import (
    LOAD_TIMEOUT_MS,
    SETUP_REPLY,
    TIMEOUT_MS,
    _new_scene_dialog,
    _open_world,
    _set_up_and_start,
    _world_name,
)

pytestmark = pytest.mark.e2e


def _seed(app, stem):
    from talemate.world.store import Source, World

    name = _world_name(stem)
    seeded = seed_fm_world(
        app.root,
        name,
        present_year=314,
        things=[
            {"kind": "language", "name": "Velskar", "fields": _language_fields()},
            {"kind": "language", "name": "Moscavian", "fields": _language_fields()},
            {"kind": "language", "name": "Sorauan", "fields": _language_fields()},
            {"kind": "character", "name": "Maren Vos", "born": 290},
            {"kind": "place", "name": "Sallowford"},
        ],
    )
    ids = seeded.things
    world = World.open(seeded.path)
    with world.revision(Source.manual(note="rows")) as rev:
        rev.set_field(
            ids["Maren Vos"],
            "languages",
            [{"language": ids["Velskar"], "role": "spoken", "fluency": "native"}],
            None,
        )
        rev.set_field(
            ids["Sallowford"],
            "languages",
            [{"language": ids["Moscavian"], "role": "official"}],
            None,
        )
    world.close()
    return name


# The e2e app has no AI client, so the app never counts as ready and keeps
# the message box disabled. This makes the page's readiness check say yes
# (it re-runs on every agent status) and sets the flag, the way a configured
# client would.
READY_JS = """
() => {
    let c = document.querySelector('.scene-message-input-root').__vueParentComponent;
    while (c && !('ready' in (c.data || {}))) c = c.parent;
    c.ctx.configurationRequired = () => false;
    c.proxy.ready = true;
}
"""


def _message_box(page):
    box = page.locator(".scene-message-input-root textarea").first
    box.wait_for(state="visible", timeout=LOAD_TIMEOUT_MS)
    page.evaluate(READY_JS)
    expect(box).to_be_enabled(timeout=TIMEOUT_MS)
    return box


def _right_click(box):
    box.evaluate(
        "(el) => { el.focus(); el.setSelectionRange(el.value.length, el.value.length); }"
    )
    box.dispatch_event("contextmenu", {"clientX": 400, "clientY": 300, "button": 2})


def test_the_scene_message_box_makes_names_in_the_speakers_languages(
    app, page, fixed_setup, fixed_language
):
    fixed_setup({**SETUP_REPLY, "player": "Maren Vos"})
    fixed_language({"definitions": {}})
    name = _seed(app, "Scene names")
    _open_world(page, name)
    dialog = _new_scene_dialog(page, "Maren Vos goes looking for bleakcap.")
    _set_up_and_start(page, dialog)

    box = _message_box(page)
    box.fill("I am ")
    _right_click(box)
    menu = page.get_by_test_id("reference-menu")
    expect(menu.get_by_text("Make a name…")).to_be_visible(timeout=TIMEOUT_MS)
    expect(menu.get_by_test_id("menu-make-phrase")).to_be_visible()
    expect(menu.get_by_text("Add reference")).to_have_count(0)

    menu.get_by_text("Make a name…").click()
    picker = menu.get_by_test_id("language-picker")
    picker.wait_for(state="visible", timeout=TIMEOUT_MS)
    # the speaker's language, then the place's, then the rest
    expect(picker.locator(".v-chip")).to_have_text(
        ["Velskar", "Moscavian", "Sorauan"], timeout=TIMEOUT_MS
    )
    candidates = menu.get_by_test_id("language-candidate")
    expect(candidates).to_have_count(4, timeout=TIMEOUT_MS)
    picked = candidates.first.get_by_test_id("language-candidate-name").inner_text()
    candidates.first.click()
    expect(box).to_have_value(f"I am {picked}", timeout=TIMEOUT_MS)


def test_the_scene_message_box_makes_a_phrase(app, page, fixed_setup):
    fixed_setup({**SETUP_REPLY, "player": "Maren Vos"})
    name = _seed(app, "Scene phrase")
    _open_world(page, name)
    dialog = _new_scene_dialog(page, "Maren Vos goes looking for bleakcap.")
    _set_up_and_start(page, dialog)

    box = _message_box(page)
    box.fill("Maren spat: ")
    _right_click(box)
    menu = page.get_by_test_id("reference-menu")
    menu.get_by_test_id("menu-make-phrase").click()
    menu.get_by_test_id("language-phrase-pick").filter(has_text="Kor vel!").click()
    expect(box).to_have_value("Maren spat: Kor vel!", timeout=TIMEOUT_MS)
