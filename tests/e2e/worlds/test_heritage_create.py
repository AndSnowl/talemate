"""The create box's heritage picker, and creating a mix first.

Two parents always go through a mix entry: picking two parents with a mix
of them uses it as the heritage; with none yet, the create box drafts the
mix first and comes back to the character with its prompt kept. Races and
mixes are also created from their species page. Previews come from the
fixed preview file (the `fixed_preview` fixture), rewritten before each
Create; no model is asked anything.
"""

from __future__ import annotations

from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)
from e2e.seed import seed_fm_world

HUMAN = {
    "kind": "species",
    "name": "Human",
    "fields": {"lifespan": 75, "adult_age": 18},
    "facts": [
        {"category": "physical", "text": "Humans have rounded ears and no tusks."},
        {"category": "instinct", "text": "Humans seek company."},
    ],
}

LOWLANDER = {
    "kind": "race",
    "name": "Lowlander",
    "links": {"species": "Human"},
    "facts": [{"category": "physical", "text": "Lowlanders are short and stocky."}],
}

ORC = {
    "kind": "species",
    "name": "Orc",
    "fields": {"lifespan": 60, "adult_age": 14},
    "facts": [{"category": "physical", "text": "Orcs have two lower tusks."}],
}

HALF_ORC = {
    "kind": "mix",
    "name": "Half-orc",
    "links": {"parents": ["Lowlander", "Orc"]},
    "facts": [{"category": "physical", "text": "Half-orcs have small tusks."}],
}

MIX_PREVIEW = {
    "name": "Half-orc",
    "facts": [
        {"category": "physical", "text": "Half-orcs have tusks of half an inch."},
        {"category": "physical", "text": "Half-orcs are broad-shouldered."},
    ],
    "prose": {"description": "Half-orcs are broad and short-tusked."},
}

GORRA_PREVIEW = {
    "name": "Gorra",
    "facts": [{"category": "personality", "text": "Quick to anger."}],
    "prose": {"description": "Gorra is broad.", "personality": "Gorra is quick."},
}

NOTICE = (
    "This heritage needs a mix entry first, so every character of it shares "
    "one body plan."
)


def _pick(page, box, label: str, name: str) -> None:
    """Pick `name` in the heritage picker's `label` field."""
    field = box.get_by_label(label, exact=True)
    field.click()
    field.fill(name)
    page.get_by_role("option").filter(has_text=name).first.click()


def _parent(box, n: int):
    return box.get_by_test_id(f"heritage-parent-{n}")


def _open_mix(page, species: str, mix: str):
    page.get_by_test_id("kind-species").click()
    _open_thing(page, species)
    thing = page.get_by_test_id("thing-page")
    thing.get_by_test_id("mixes-section").get_by_text(mix).click()
    thing.get_by_test_id("thing-name").filter(has_text=mix).wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    return thing


def test_two_parents_without_mix_drafts_mix_first(app, page, fixed_preview):
    name = _world_name("Ironmere")
    seed_fm_world(app.root, name, present_year=1000, things=[HUMAN, LOWLANDER, ORC])
    _open_world(page, name)
    _world_tab(page)

    box = page.get_by_test_id("create-box")
    prompt = "A Lowlander smith with an orc mother, quick to anger."
    box.get_by_label("Describe it").fill(prompt)
    # the prompt names a race the world has: the picker is pre-filled
    _parent(box, 1).filter(has_text="Lowlander").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    _pick(page, box, "Second parent", "Orc")

    fixed_preview(MIX_PREVIEW)
    box.get_by_role("button", name="Create").click()

    # no Lowlander x Orc mix yet: the box drafts one first
    draft = box.get_by_test_id("mix-draft")
    draft.get_by_text(NOTICE).wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "Lowlander" in _parent(draft, 1).inner_text()
    assert "Orc" in _parent(draft, 2).inner_text()
    draft.get_by_role("button", name="Create").click()

    preview = draft.get_by_test_id("create-preview")
    preview.get_by_text("Half-orcs are broad and short-tusked.").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    # the preview lists what the mix inherits; the owner marks Human's
    # "no tusks" as replaced, which the model missed
    ears = preview.get_by_test_id("preview-inherited").filter(
        has_text="rounded ears and no tusks"
    )
    assert "Human" in ears.inner_text()
    ears.get_by_role("checkbox", name="Overridden").check()
    replaced_by = ears.get_by_test_id("override-by")
    assert "tusks of half an inch" in replaced_by.inner_text()
    preview.get_by_role("button", name="Accept").click()

    # back to the character, with the new mix as its heritage and the
    # prompt as it was
    draft.wait_for(state="hidden", timeout=TIMEOUT_MS)
    _parent(box, 1).filter(has_text="Half-orc").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert _parent(box, 2).count() == 0 or "Orc" not in _parent(box, 2).inner_text()
    assert box.get_by_label("Describe it").input_value() == prompt

    fixed_preview(GORRA_PREVIEW)
    box.get_by_role("button", name="Create").click()
    gorra = box.get_by_test_id("create-preview")
    gorra.get_by_text("Gorra is broad.").wait_for(state="visible", timeout=TIMEOUT_MS)
    gorra.get_by_role("button", name="Accept").click()
    thing = page.get_by_test_id("thing-page")
    thing.get_by_test_id("thing-name").filter(has_text="Gorra").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert "Half-orc" in thing.get_by_test_id("field-heritage").inner_text()

    # the mix's page: its unset numbers average its parents', and the fact
    # marked in the preview is replaced
    thing.get_by_role("button", name="Back").click()
    mix = _open_mix(page, "Human", "Half-orc")
    lifespan = mix.get_by_test_id("numbers-lifespan")
    lifespan.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "67.5 years" in lifespan.inner_text()
    assert "inherited" in lifespan.inner_text()
    assert "16" in mix.get_by_test_id("numbers-adult_age").inner_text()
    ears = mix.get_by_test_id("inherited-fact").filter(has_text="rounded ears")
    assert ears.get_by_text("replaced by its own fact").is_visible()
    tusks = mix.get_by_test_id("inherited-fact").filter(has_text="two lower tusks")
    assert tusks.get_by_test_id("inherited-source").inner_text() == "Orc"


def test_two_parents_with_mix_uses_it(app, page, fixed_preview):
    name = _world_name("Ironmere")
    seed_fm_world(
        app.root, name, present_year=1000, things=[HUMAN, LOWLANDER, ORC, HALF_ORC]
    )
    _open_world(page, name)
    _world_tab(page)

    box = page.get_by_test_id("create-box")
    box.get_by_label("Describe it").fill("A blacksmith, quick to anger.")
    # the parents in the other order than the mix lists them
    _pick(page, box, "Heritage", "Orc")
    _pick(page, box, "Second parent", "Lowlander")

    fixed_preview(GORRA_PREVIEW)
    box.get_by_role("button", name="Create").click()
    preview = box.get_by_test_id("create-preview")
    preview.get_by_text("Gorra is broad.").wait_for(state="visible", timeout=TIMEOUT_MS)
    assert box.get_by_test_id("mix-draft").count() == 0
    assert "Half-orc" in _parent(box, 1).inner_text()
    # it inherits the mix's facts, then both parents'
    inherited = preview.get_by_test_id("preview-inherited")
    assert inherited.filter(has_text="Half-orcs have small tusks.").count() == 1
    assert inherited.filter(has_text="Lowlanders are short").count() == 1

    preview.get_by_role("button", name="Accept").click()
    thing = page.get_by_test_id("thing-page")
    thing.get_by_test_id("thing-name").filter(has_text="Gorra").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert "Half-orc" in thing.get_by_test_id("field-heritage").inner_text()


def test_new_race_and_mix_from_species_page(app, page, fixed_preview):
    name = _world_name("Ironmere")
    seed_fm_world(
        app.root, name, present_year=1000, things=[HUMAN, LOWLANDER, ORC, HALF_ORC]
    )
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-species").click()

    # "+ New mix" starts from this species; parents the world already
    # mixes are found, not drafted twice
    orc = _open_thing(page, "Orc")
    orc.get_by_role("button", name="New mix").click()
    mix_box = orc.get_by_test_id("create-box")
    assert "Orc" in _parent(mix_box, 1).inner_text()
    _pick(page, mix_box, "Second parent", "Lowlander")
    mix_box.get_by_role("button", name="Create").click()
    existing = mix_box.get_by_test_id("mix-exists")
    existing.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "Half-orc" in existing.inner_text()
    assert mix_box.get_by_test_id("create-preview").count() == 0
    mix_box.get_by_role("button", name="Cancel").click()
    mix_box.wait_for(state="hidden", timeout=TIMEOUT_MS)

    # "+ New race" makes a race of this species
    orc.get_by_role("button", name="Back").click()
    page.get_by_test_id("kind-species").click()
    human = _open_thing(page, "Human")
    human.get_by_role("button", name="New race").click()
    race_box = human.get_by_test_id("create-box")
    assert "Race of Human" in race_box.inner_text()
    race_box.get_by_label("Describe it").fill("Highlanders: tall, from the hills.")
    fixed_preview(
        {
            "name": "Highlander",
            "facts": [{"category": "physical", "text": "Highlanders are tall."}],
            "prose": {"description": "Tall hill people."},
        }
    )
    race_box.get_by_role("button", name="Create").click()
    race_preview = race_box.get_by_test_id("create-preview")
    race_preview.get_by_text("Tall hill people.").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    race_preview.get_by_role("button", name="Accept").click()

    # accepting opens the new race, of Human
    human.get_by_test_id("thing-name").filter(has_text="Highlander").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert "Human" in human.get_by_test_id("field-species").inner_text()
