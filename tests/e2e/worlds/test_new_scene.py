"""Starting a world scene from one prompt: the new-scene dialog's name
highlighting and re-picking, the setup step, Start, and "continue in a new
scene" from the loaded scene.

No model is asked anything: scene setups come from the fixed setup file
(the `fixed_setup` fixture), a scene-setup model reply whose names the
backend still resolves against the world, the owner's picks first. Every
test seeds its own uniquely named world, since the app (and its worlds
folder) is shared by the session.
"""

from __future__ import annotations

import json
import re
import uuid

from e2e.seed import seed_fm_world

TIMEOUT_MS = 30_000
# loading a scene starts its agents: slower than a worlds reply
LOAD_TIMEOUT_MS = 60_000

MAREN_VOS = {
    "kind": "character",
    "name": "Maren Vos",
    "born": 290,
    "facts": [{"category": "appearance", "text": "Heron tattoo on her forearm."}],
}
MAREN_HOLT = {"kind": "character", "name": "Maren Holt", "born": 288}
SALLOWFORD = {
    "kind": "place",
    "name": "Sallowford",
    "facts": [{"category": "description", "text": "A half-flooded river town."}],
}

SETUP_REPLY = {
    "player": "Maren",
    "characters": [{"name": "Old Tamsin", "facts": ["A hermit fungus-picker."]}],
    "place": {"name": "Sallowford"},
    "goal": "Find the bleakcap patch before dusk.",
    "intro": "Mist hangs low over the Sallowford reeds.",
}

# records every message the page sends on its websockets
SEND_SPY_JS = """
() => {
    window.__e2eSent = [];
    const send = WebSocket.prototype.send;
    WebSocket.prototype.send = function (data) {
        window.__e2eSent.push(data);
        return send.call(this, data);
    };
}
"""


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


def _new_scene_dialog(page, prompt: str):
    page.get_by_role("button", name="New scene").click()
    dialog = page.get_by_test_id("new-scene-dialog")
    dialog.wait_for(state="visible", timeout=TIMEOUT_MS)
    dialog.get_by_label("Storyline").fill(prompt)
    return dialog


def _sent(page, action: str) -> list[dict]:
    messages = [json.loads(m) for m in page.evaluate("() => window.__e2eSent")]
    return [
        m for m in messages if m.get("type") == "worlds" and m.get("action") == action
    ]


def _set_up_and_start(page, dialog) -> None:
    dialog.get_by_role("button", name="Set up scene").click()
    setup = page.get_by_test_id("scene-setup")
    setup.get_by_test_id("setup-who").filter(has_text="Maren").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    setup.get_by_role("button", name="Start").click()
    # the scene opens on the main tab, with the setup's intro
    page.get_by_text(SETUP_REPLY["intro"]).first.wait_for(
        state="visible", timeout=LOAD_TIMEOUT_MS
    )


def test_names_highlight_and_repick(app, page, fixed_setup):
    name = _world_name("Vael")
    world = seed_fm_world(
        app.root, name, present_year=314, things=[MAREN_VOS, MAREN_HOLT, SALLOWFORD]
    )
    fixed_setup(SETUP_REPLY)
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    dialog = _new_scene_dialog(
        page, "Maren went foraging near Sallowford for bleakcap mushrooms."
    )

    # both names are matched to world things (blue)
    maren = dialog.get_by_test_id("name-match").filter(has_text="Maren")
    maren.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "matched" in maren.get_attribute("class")
    assert dialog.get_by_test_id("name-match").filter(has_text="Sallowford").count()

    # hovering shows both Marens, the first one picked
    maren.hover()
    popover = page.get_by_test_id("name-popover")
    popover.wait_for(state="visible", timeout=TIMEOUT_MS)
    holt = popover.get_by_test_id("name-candidate").filter(has_text="Maren Holt")
    vos = popover.get_by_test_id("name-candidate").filter(has_text="Maren Vos")
    assert holt.get_attribute("aria-selected") == "true"
    assert popover.get_by_text("Treat as new").is_visible()

    # picking the other one is what the setup is planned with
    vos.click()
    popover.wait_for(state="hidden", timeout=TIMEOUT_MS)
    dialog.get_by_role("button", name="Set up scene").click()
    setup = page.get_by_test_id("scene-setup")
    setup.get_by_test_id("setup-who").filter(has_text="Maren Vos (you)").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    picks = _sent(page, "plan_scene")[-1]["picks"]
    assert picks["Maren"] == world.things["Maren Vos"]

    # the setup step: where, when, the goal and what was invented
    assert "Sallowford" in setup.get_by_test_id("setup-where").inner_text()
    assert "314" in setup.get_by_test_id("setup-when").inner_text()
    assert "bleakcap patch" in setup.get_by_test_id("setup-goal").inner_text()
    assert "Old Tamsin" in setup.get_by_test_id("setup-invented").inner_text()

    # Edit goes back to the prompt, keeping it
    setup.get_by_role("button", name="Edit").click()
    setup.wait_for(state="hidden", timeout=TIMEOUT_MS)
    assert "bleakcap" in dialog.get_by_label("Storyline").input_value()

    # treating a matched name as new turns it yellow, and it's invented
    sallowford = dialog.get_by_test_id("name-match").filter(has_text="Sallowford")
    sallowford.hover()
    popover = page.get_by_test_id("name-popover").filter(has_text="Treat as new")
    popover.get_by_text("Treat as new").click()
    popover.wait_for(state="hidden", timeout=TIMEOUT_MS)
    assert "new" in sallowford.get_attribute("class")
    dialog.get_by_role("button", name="Set up scene").click()
    setup.get_by_test_id("setup-where").filter(has_text="invented").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    sent = _sent(page, "plan_scene")[-1]
    assert sent["new_names"] == ["Sallowford"]
    assert "Sallowford" not in sent["picks"]


def test_setup_then_start_loads_scene(app, page, fixed_setup):
    name = _world_name("Reedmarch")
    seed_fm_world(app.root, name, present_year=314, things=[MAREN_VOS, SALLOWFORD])
    fixed_setup({**SETUP_REPLY, "player": "Maren Vos"})
    _open_world(page, name)
    dialog = _new_scene_dialog(page, "Maren Vos goes looking for bleakcap.")
    _set_up_and_start(page, dialog)

    # the world character and the invented one are the scene's characters,
    # as the World Editor lists them
    # the scene's own tab is selected once it has loaded; only then does the
    # World Editor tab stay selected when clicked
    app_tabs = page.locator("header.v-app-bar .v-tab")
    app_tabs.filter(has_text=SETUP_REPLY["goal"].rstrip(".")).and_(
        page.locator("[aria-selected=true]")
    ).wait_for(state="visible", timeout=TIMEOUT_MS)
    app_tabs.filter(has_text="World Editor").click()
    characters_tab = page.locator(".v-tab:visible", has_text="Characters")
    characters_tab.wait_for(state="visible", timeout=TIMEOUT_MS)
    characters_tab.click()
    titles = page.locator(".v-list-item-title")
    titles.filter(has_text=re.compile(r"^Maren Vos$")).wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert titles.filter(has_text=re.compile(r"^Old Tamsin$")).is_visible()


def test_continue_scene_offers_setup(app, page, fixed_setup):
    name = _world_name("Lowmarsh")
    seed_fm_world(app.root, name, present_year=314, things=[MAREN_VOS, SALLOWFORD])
    fixed_setup({**SETUP_REPLY, "player": "Maren Vos"})
    _open_world(page, name)
    dialog = _new_scene_dialog(page, "Maren Vos goes looking for bleakcap.")
    _set_up_and_start(page, dialog)

    # the loaded world scene offers to continue in a new scene
    fixed_setup(
        {
            **SETUP_REPLY,
            "player": "Maren Vos",
            "goal": "Get the bleakcap to market.",
            "intro": "Dawn finds Maren on the road to market.",
        }
    )
    tools = page.get_by_test_id("world-scene-tools")
    tools.get_by_role("button", name="Continue in a new scene").click()
    continuing = page.get_by_test_id("continue-scene-dialog")
    continuing.get_by_label("Next goal").fill("Sell the bleakcap at market")
    continuing.get_by_role("button", name="Set up next scene").click()

    setup = continuing.get_by_test_id("scene-setup")
    setup.get_by_test_id("setup-goal").filter(
        has_text="Get the bleakcap to market."
    ).wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "Maren Vos (you)" in setup.get_by_test_id("setup-who").inner_text()
    assert "Sallowford" in setup.get_by_test_id("setup-where").inner_text()
    assert setup.get_by_role("button", name="Start").is_visible()


def test_edit_scene_start_date(app, page):
    name = _world_name("Ashford")
    seed_fm_world(
        app.root,
        name,
        present_year=318,
        things=[MAREN_VOS],
        scenes=[{"name": "The Ferryman", "start": 312, "player": "Maren Vos"}],
    )
    _open_world(page, name)
    scene = page.get_by_test_id("world-scene").filter(has_text="The Ferryman")
    start = scene.get_by_test_id("scene-start-date")
    start.filter(has_text="312").wait_for(state="visible", timeout=TIMEOUT_MS)

    start.click()
    editor = page.get_by_test_id("scene-start-editor")
    editor.get_by_label("Year").fill("316")
    editor.get_by_role("button", name="Move").click()
    start.filter(has_text="316").wait_for(state="visible", timeout=TIMEOUT_MS)


def test_move_start_from_the_scene_view(app, page, fixed_setup):
    name = _world_name("Greywater")
    seed_fm_world(app.root, name, present_year=314, things=[MAREN_VOS, SALLOWFORD])
    fixed_setup({**SETUP_REPLY, "player": "Maren Vos"})
    _open_world(page, name)
    dialog = _new_scene_dialog(page, "Maren Vos goes looking for bleakcap.")
    _set_up_and_start(page, dialog)

    # the loaded world scene's start date is in its toolbar, and can move
    # (the Worlds home, kept in the page, lists the scene too)
    start = page.get_by_test_id("world-scene-tools").get_by_test_id("scene-start-date")
    start.filter(has_text="314").wait_for(state="visible", timeout=TIMEOUT_MS)
    start.click()
    editor = page.get_by_test_id("scene-start-editor")
    editor.get_by_label("Year").fill("320")
    editor.get_by_role("button", name="Move").click()
    start.filter(has_text="320").wait_for(state="visible", timeout=TIMEOUT_MS)

    # and so does the scene in the Worlds home
    page.locator("header.v-app-bar .v-tab", has_text="Worlds").click()
    scene = page.get_by_test_id("world-scene").filter(has_text="bleakcap")
    scene.get_by_test_id("scene-start-date").filter(has_text="320").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
