"""Species, race and mix pages, and what a character inherits.

The world is seeded through `talemate.world` (`seed.seed_fm_world`): the
Owl-folk species, its Snowy race, Vasha, a Snowy character, and Old
Moss, an owl-folk past the species' lifespan. No model is asked anything.
"""

from __future__ import annotations

import re

from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _fact,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)
from e2e.seed import seed_fm_world
from e2e.worlds.test_heritage_create import HALF_ORC, HUMAN, LOWLANDER, ORC


def _measure(name: str, low: float, high: float) -> dict:
    return {"name": name, "min": low, "max": high, "unit": "ft"}


OWL_FOLK = {
    "kind": "species",
    "name": "Owl-folk",
    "fields": {
        "lifespan": 70,
        "adult_age": 12,
        "measures": [_measure("height", 3, 4), _measure("wingspan", 7, 9)],
    },
    "facts": [
        {
            "category": "physical",
            "text": "Wings in place of arms; taloned feet serve as hands.",
        },
        {"category": "instinct", "text": "Most alert at dusk and dawn."},
    ],
}

SNOWY = {
    "kind": "race",
    "name": "Snowy",
    "links": {"species": "Owl-folk"},
    "fields": {"measures": [_measure("wingspan", 8.5, 9)]},
    "facts": [
        {"category": "physical", "text": "White plumage flecked with grey."},
        {"category": "physical", "text": "Yellow eyes."},
    ],
}

VASHA = {
    "kind": "character",
    "name": "Vasha",
    "born": 978,
    "links": {"heritage": "Snowy"},
    "facts": [{"category": "personality", "text": "Quiet and observant."}],
}


# past the Owl-folk lifespan of 70 in 1026: flagged, never refused
OLD_MOSS = {
    "kind": "character",
    "name": "Old Moss",
    "born": 940,
    "links": {"heritage": "Owl-folk"},
}


def _inherited(thing, text: str):
    return thing.get_by_test_id("inherited-fact").filter(has_text=text)


def test_species_page_and_inheritance(app, page):
    name = _world_name("Frosthollow")
    seed_fm_world(
        app.root, name, present_year=1026, things=[OWL_FOLK, SNOWY, VASHA, OLD_MOSS]
    )
    _open_world(page, name)
    _world_tab(page)

    # races and mixes aren't listed at the top level, only species
    assert page.get_by_test_id("kind-species").is_visible()
    assert page.get_by_test_id("kind-race").count() == 0
    assert page.get_by_test_id("kind-mix").count() == 0

    # the species page: its numbers, and its races
    page.get_by_test_id("kind-species").click()
    owl = _open_thing(page, "Owl-folk")
    lifespan = owl.get_by_test_id("numbers-lifespan")
    lifespan.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "70 years" in lifespan.inner_text()
    assert "12" in owl.get_by_test_id("numbers-adult_age").inner_text()
    measures = owl.get_by_test_id("numbers-measures").inner_text()
    assert "wingspan" in measures.lower() and "7–9 ft" in measures
    races = owl.get_by_test_id("races-section")
    assert owl.get_by_test_id("mixes-section").is_visible()

    # a race page: its unset lifespan is the species', shown as inherited;
    # its own wingspan wins over the species'
    races.get_by_text("Snowy").click()
    snowy = page.get_by_test_id("thing-page")
    snowy.get_by_test_id("thing-name").filter(has_text="Snowy").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    race_lifespan = snowy.get_by_test_id("numbers-lifespan")
    assert "70 years" in race_lifespan.inner_text()
    assert "inherited" in race_lifespan.inner_text()
    assert "8.5–9 ft" in snowy.get_by_test_id("numbers-measures").inner_text()
    # who uses the race: Vasha, through his heritage
    assert "Vasha" in snowy.get_by_test_id("referenced-in").inner_text()

    # setting the race's own lifespan replaces the inherited one
    race_lifespan.get_by_role("button", name="Edit lifespan").click()
    race_lifespan.get_by_label("Lifespan").fill("65")
    race_lifespan.get_by_role("button", name="Save").click()
    race_lifespan.filter(has_text="65 years").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert "inherited" not in race_lifespan.inner_text()

    # Vasha's page: heritage links, his life stage, inherited facts dimmed
    # with where they came from
    snowy.get_by_role("button", name="Back").click()
    page.get_by_test_id("kind-character").click()
    vasha = _open_thing(page, "Vasha")
    assert "age 48 · adult" in vasha.get_by_test_id("field-born").inner_text()
    assert vasha.get_by_test_id("past-lifespan").count() == 0
    heritage = vasha.get_by_test_id("field-heritage")
    assert "Owl-folk" in heritage.inner_text() and "Snowy" in heritage.inner_text()

    wings = _inherited(vasha, "Wings in place of arms")
    wings.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert wings.get_by_test_id("inherited-source").inner_text() == "Owl-folk"
    eyes = _inherited(vasha, "Yellow eyes.")
    assert eyes.get_by_test_id("inherited-source").inner_text() == "Snowy"

    # Override opens the fact form filled in; saving strikes the inherited
    # fact through
    eyes.get_by_test_id("override-button").click()
    form = vasha.get_by_test_id("fact-form")
    text = form.get_by_label("Fact", exact=True)
    assert text.input_value() == "Yellow eyes."
    text.fill("Blue eyes")
    form.get_by_role("button", name="Save").click()

    _fact(vasha, "Blue eyes").wait_for(state="visible", timeout=TIMEOUT_MS)
    eyes.get_by_text("replaced by its own fact").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert eyes.locator("s").inner_text() == "Yellow eyes."
    assert eyes.get_by_test_id("override-button").count() == 0
    assert _inherited(vasha, "White plumage").get_by_test_id("override-button").count()

    # a source chip opens the page the fact comes from
    wings.get_by_test_id("inherited-source").click()
    page.get_by_test_id("thing-name").filter(
        has_text=re.compile("^Owl-folk$")
    ).wait_for(state="visible", timeout=TIMEOUT_MS)

    # an age past the lifespan shows a warning chip by the life stage
    page.get_by_role("button", name="Back").click()
    page.get_by_test_id("kind-character").click()
    moss = _open_thing(page, "Old Moss")
    born = moss.get_by_test_id("field-born")
    assert "age 86 · elder" in born.inner_text()
    assert born.get_by_test_id("past-lifespan").is_visible()


def test_deleted_heritage_shows_as_deleted(app, page):
    """A character whose race was deleted shows its heritage as "(deleted)",
    plain text rather than a link to a page that's gone."""

    name = _world_name("Ashgrove")
    tawny = {"kind": "race", "name": "Tawny", "links": {"species": "Owl-folk"}}
    pip = {"kind": "character", "name": "Pip", "links": {"heritage": "Tawny"}}
    seed_fm_world(app.root, name, present_year=1026, things=[OWL_FOLK, tawny, pip])
    _open_world(page, name)
    _world_tab(page)

    page.get_by_test_id("kind-species").click()
    owl = _open_thing(page, "Owl-folk")
    owl.get_by_test_id("races-section").get_by_text("Tawny").click()
    race = page.get_by_test_id("thing-page")
    race.get_by_test_id("thing-name").filter(has_text="Tawny").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    race.get_by_test_id("delete-thing").click()
    dialog = page.get_by_test_id("delete-dialog")
    dialog.wait_for(state="visible", timeout=TIMEOUT_MS)
    dialog.get_by_role("button", name="Delete").click()
    dialog.wait_for(state="hidden", timeout=TIMEOUT_MS)

    # back to the race's species page, without the race
    owl.get_by_test_id("thing-name").filter(has_text="Owl-folk").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    owl.get_by_test_id("races-section").get_by_text("No races yet.").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )

    page.get_by_test_id("kind-character").click()
    character = _open_thing(page, "Pip")
    heritage = character.get_by_test_id("field-heritage")
    heritage.get_by_text("(deleted)").wait_for(state="visible", timeout=TIMEOUT_MS)
    assert heritage.locator("a").count() == 0


def test_rename_a_race_shows_everywhere(app, page):
    """A race renamed on its page shows by its new name on its species
    page and in a character's heritage links."""

    name = _world_name("Rimeholt")
    seed_fm_world(app.root, name, present_year=1026, things=[OWL_FOLK, SNOWY, VASHA])
    _open_world(page, name)
    _world_tab(page)

    page.get_by_test_id("kind-species").click()
    owl = _open_thing(page, "Owl-folk")
    owl.get_by_test_id("races-section").get_by_text("Snowy").click()
    race = page.get_by_test_id("thing-page")
    race.get_by_test_id("thing-name").filter(has_text="Snowy").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    race.get_by_role("button", name="Rename").click()
    field = race.get_by_test_id("rename-field").get_by_label("Name")
    field.fill("Frostwing")
    race.get_by_test_id("rename-field").get_by_role("button", name="Save").click()
    race.get_by_test_id("thing-name").filter(has_text="Frostwing").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )

    # its species page lists it by the new name
    race.get_by_test_id("field-species").get_by_text("Owl-folk").click()
    species = page.get_by_test_id("thing-page")
    species.get_by_test_id("thing-name").filter(has_text="Owl-folk").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    races = species.get_by_test_id("races-section")
    races.get_by_text("Frostwing").wait_for(state="visible", timeout=TIMEOUT_MS)
    assert races.get_by_text("Snowy").count() == 0

    # and a character of it links to it by the new name
    page.get_by_test_id("kind-character").click()
    vasha = _open_thing(page, "Vasha")
    heritage = vasha.get_by_test_id("field-heritage")
    heritage.get_by_text("Frostwing").wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "Snowy" not in heritage.inner_text()


def test_deleting_a_mix_goes_back_to_its_species(app, page):
    """A mix deleted from its page goes back to the species page it was
    opened from (here its second parent, Orc), not to the species list."""

    name = _world_name("Ironmere")
    seed_fm_world(
        app.root, name, present_year=1000, things=[HUMAN, LOWLANDER, ORC, HALF_ORC]
    )
    _open_world(page, name)
    _world_tab(page)

    page.get_by_test_id("kind-species").click()
    orc = _open_thing(page, "Orc")
    orc.get_by_test_id("mixes-section").get_by_text("Half-orc").click()
    mix = page.get_by_test_id("thing-page")
    mix.get_by_test_id("thing-name").filter(has_text="Half-orc").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    mix.get_by_test_id("delete-thing").click()
    dialog = page.get_by_test_id("delete-dialog")
    dialog.wait_for(state="visible", timeout=TIMEOUT_MS)
    dialog.get_by_role("button", name="Delete").click()
    dialog.wait_for(state="hidden", timeout=TIMEOUT_MS)

    back = page.get_by_test_id("thing-page")
    back.get_by_test_id("thing-name").filter(has_text="Orc").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    mixes = back.get_by_test_id("mixes-section")
    mixes.get_by_text("No mixes yet.").wait_for(state="visible", timeout=TIMEOUT_MS)
