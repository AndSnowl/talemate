"""The World tab's back arrow, and re-pointing a stub from the Stubs page.

The back arrow on a thing page returns to the page before it (a thing
page, the Stubs page or a kind's list), not the section home. "Re-point…"
on the Stubs page moves every link to a stub onto an entry, which takes
the stub's names as other names.

The worlds are seeded through `talemate.world` (`seed.seed_fm_world`), the
facts' references written as `[[@Name|shown]]`. No model is asked
anything.
"""

from __future__ import annotations

from e2e.seed import seed_fm_world
from e2e.worlds.test_connections_create import _choose_mode, _search_and_pick
from e2e.worlds.test_connections_pages import _stubs_tab
from e2e.worlds.test_heritage_pages import OWL_FOLK, SNOWY
from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _fact,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)

# A links B, B links C
C_LORE = {
    "kind": "lore",
    "name": "Tidewater Pact",
    "facts": [{"category": "general", "text": "Signed on a drowned altar."}],
}
B_LORE = {
    "kind": "lore",
    "name": "Salt Oath",
    "facts": [
        {
            "category": "general",
            "text": "Sworn under the [[@Tidewater Pact|Tidewater Pact]].",
        }
    ],
}
A_LORE = {
    "kind": "lore",
    "name": "Brine Covenant",
    "facts": [
        {"category": "general", "text": "Older than the [[@Salt Oath|Salt Oath]]."}
    ],
}


def _on_page(page, name: str):
    thing = page.get_by_test_id("thing-page")
    thing.get_by_test_id("thing-name").filter(has_text=name).wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    return thing


def _back(page):
    page.get_by_test_id("thing-page").get_by_test_id("thing-back").click()


def test_back_arrow_returns_to_the_page_before(app, page):
    name = _world_name("Saltmere")
    seed_fm_world(
        app.root,
        name,
        present_year=1026,
        things=[OWL_FOLK, SNOWY, C_LORE, B_LORE, A_LORE],
    )
    _open_world(page, name)
    _world_tab(page)

    # a race opened from its species page goes back to the species page
    page.get_by_test_id("kind-species").click()
    owl = _open_thing(page, "Owl-folk")
    owl.get_by_test_id("races-section").get_by_text("Snowy").click()
    _on_page(page, "Snowy")
    _back(page)
    _on_page(page, "Owl-folk")
    # and from there to the Species list
    _back(page)
    page.get_by_test_id("thing-page").wait_for(state="detached", timeout=TIMEOUT_MS)
    page.get_by_test_id("thing-card").filter(has_text="Owl-folk").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )

    # a link chain A -> B -> C, then back twice lands on A
    page.get_by_test_id("kind-lore").click()
    a = _open_thing(page, "Brine Covenant")
    _fact(a, "Older than").get_by_test_id("linked-ref").click()
    b = _on_page(page, "Salt Oath")
    _fact(b, "Sworn under").get_by_test_id("linked-ref").click()
    _on_page(page, "Tidewater Pact")
    _back(page)
    _on_page(page, "Salt Oath")
    _back(page)
    _on_page(page, "Brine Covenant")


MOSCAVIA = {
    "kind": "place",
    "name": "Tsardom of Moscavia",
    "stub": "live",
}
MOSCAVY = {"kind": "place", "name": "Moscavy"}
EAGLE_FOLK = {
    "kind": "species",
    "name": "Eagle-folk",
    "facts": [
        {
            "category": "origin",
            "text": "First hatched in the"
            " [[@Tsardom of Moscavia|Tsardom of Moscavia]].",
        },
        {
            "category": "general",
            "text": "Still nest along [[@Tsardom of Moscavia|the Tsardom]]'s cliffs.",
        },
    ],
}


def test_stubs_page_repoints_a_stub_onto_an_entry(app, page):
    name = _world_name("Moscavy")
    seed_fm_world(
        app.root, name, present_year=1026, things=[MOSCAVIA, MOSCAVY, EAGLE_FOLK]
    )
    _open_world(page, name)
    _world_tab(page)

    tab = _stubs_tab(page)
    row = tab.get_by_test_id("stub-row").filter(has_text="Tsardom of Moscavia")
    row.wait_for(state="visible", timeout=TIMEOUT_MS)
    row.get_by_test_id("stub-repoint").click()
    _search_and_pick(page, "mosc", "Moscavy")
    _choose_mode(page)

    # the stub is gone; a note says where its links went and what names
    # Moscavy took
    note = tab.get_by_test_id("stub-repointed")
    note.wait_for(state="visible", timeout=TIMEOUT_MS)
    text = note.inner_text()
    assert "2 links" in text and "Moscavy" in text
    assert "Tsardom of Moscavia" in text and "the Tsardom" in text
    row.wait_for(state="detached", timeout=TIMEOUT_MS)

    # the links now open Moscavy, keeping their words
    page.get_by_test_id("kind-species").click()
    eagle = _open_thing(page, "Eagle-folk")
    origin = _fact(eagle, "First hatched").get_by_test_id("linked-ref")
    origin.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert origin.inner_text() == "Tsardom of Moscavia"
    assert _fact(eagle, "cliffs").get_by_test_id("linked-stub").count() == 0
    origin.click()
    moscavy = _on_page(page, "Moscavy")

    # Moscavy's other names: the stub's name and each shown text, common
    rows = moscavy.get_by_test_id("aka-editor").get_by_test_id("aka-row")
    rows.filter(has_text="the Tsardom").wait_for(state="visible", timeout=TIMEOUT_MS)
    names = rows.all_inner_texts()
    assert any("Tsardom of Moscavia" in r and "common" in r for r in names)
    assert any("the Tsardom" in r and "common" in r for r in names)

    # back goes to Eagle-folk; the stub's page was never visited
    _back(page)
    _on_page(page, "Eagle-folk")
