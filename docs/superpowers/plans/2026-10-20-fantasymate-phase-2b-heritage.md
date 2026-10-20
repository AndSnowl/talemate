# Phase 2, Plan B: Species, Races, Mixes and Inheritance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the owner make species, races and mixes. Characters (and races and mixes) inherit their facts, with explicit overrides. Creation, scene setup and play all use that inheritance, read as of the scene's date.

**Architecture:**
- **Data:** the new kinds and fields, plus one new link table for overrides, live in the strictly typed `src/talemate/world/`.
- **Resolution:** a new pure module, `src/talemate/world/heritage.py`, resolves lineage, inherited facts, numbers and life stage from a `WorldView`.
- **The bridge:** `src/talemate/worldplay/` feeds the resolved facts into prose, character sheets, create-from-prompt and scene setup. Inheritance is resolved in code, never with an LLM call during a turn.
- **Frontend:** the `worlds` router and its Pinia store gain species, race and mix pages, an Inherited section, a heritage picker and a mix-first create flow.

**Tech stack:** Python 3.11, SQLite (the world store), pydantic 2, Jinja2 templates through `Prompt.request`, Vue 3 + Vuetify, Pinia, Playwright e2e.

**Spec:**
- `docs/superpowers/specs/2026-10-20-fantasymate-phase-2b-heritage-design.md`, which this plan implements;
- the main spec, `docs/superpowers/specs/2026-10-18-fantasymate-world-data-model-design.md`;
- probe evidence in `docs/superpowers/probes/2026-10-20-heritage-blending.md`.

## Global Constraints

- **Running things on Guix:**
  - Run everything through `guix shell -m manifest.scm -- …` from the repo or worktree root, always with `uv run --no-sync`.
  - The plain suite must stay at **0 failed**. The baseline on main 4c3c66b7 is 6846 passed, 6 skipped, about 40 s.
- **Testing rule (owner):**
  - Run focused tests while iterating, and the full plain suite once per task.
  - Run the browser suite (`pytest tests/e2e -m e2e -n 4`, never more than 4) once at the end of a task that changes UI. Check for orphaned apps first.
  - A UI change that the AI tests drive needs `grep -rn` over `tests/ai`.
  - After a new frontend dependency, run `pnpm install` in `talemate_frontend`.
- **koboldcpp:** the owner granted access for this plan's probes (2026-10-20). The model is `http://192.168.0.5:5001`, Skyfall-31B-v4.2-i1-Q4_K_M. Plain tests use `MockClient` only. Commit raw probe output under `docs/superpowers/probes/raw/`.
- **`src/talemate/world/` stays under strict mypy** (`tests/world/test_typecheck.py`), with no imports from the rest of `talemate`.
- **Probe and acceptance doc names** use the date they're run (`<run-date>`, as YYYY-MM-DD).
- **Ids are 32-hex `uuid4().hex`.** Dates are `WorldDate`; format them with the world's `Calendar.format`.
- **Generated prose is never fed back into fact extraction.**
- **Ordinary turns get no extra LLM calls.** Inheritance is resolved in code.
- **New screens:**
  - colours use `rgb(var(--v-theme-<role>))` roles from `talemate_frontend/src/theme/roles.js`;
  - state lives in `talemate_frontend/src/stores/worlds.js`.
- **New world features are written in Python, not as nodes.**
- **Every world AI call goes through `worldplay.ai.world_ai_call()`.**
- **Model replies are parsed with the shared non-strict `create.json_objects`.**
- **Inheritance order, most specific first:**
  1. the thing's own facts;
  2. race or mix (a mix's own facts, then parent A's chain, then parent B's chain);
  3. species;
  4. culture.

  A fact is dropped from the inherited set when a more specific layer's fact lists it in `overrides`.
- **Life stage:**
  - adolescent from `0.75 × adult_age`, adult from `adult_age`, elder from `0.8 × lifespan`;
  - an age past `lifespan` is flagged, but never blocked.
- **A mix's unset number** is the average of its two parents' resolved numbers. If only one parent has it, that parent's value.
- **Two parents always go through a mix.** Picking two parents finds the mix whose `parents` are those two ids in either order, or sends the owner to draft one first. A character's `heritage` is always one thing id.

## Review Focus

1. **A cycle in mix parents** (mix A has mix B as a parent, and B has A): lineage must terminate, with each thing visited once (Task 2: `test_lineage_survives_a_parent_cycle`).
2. **A deleted ancestor.** After deleting a race, a character of that race resolves without it: no `KeyError` on the page, in prose or in play (Task 2: `test_inherited_skips_deleted_layer`; Task 5: `test_character_sheet_with_deleted_species`).
3. **A mix picked with its parents in reverse order** finds the existing mix rather than drafting a duplicate (Task 9: `test_find_mix_either_order`).
4. **A dated heritage change** (a heritage set from 400 to a different race) inherits the old race in a scene set in 350 (Task 2: `test_lineage_follows_dated_heritage`).
5. **An overridden fact that's later corrected** keeps its `fact_id`, so the override still applies. An override whose target was removed leaves the own fact standing alone (Task 1: `test_override_survives_correction`; Task 2: `test_override_of_removed_fact_is_harmless`).

---

### Task 1: New kinds, field types and override links in the world store

**Files:**
- Modify:
  - `src/talemate/world/kinds.py`;
  - `src/talemate/world/schema.py` (migration 2 → 3, `SCHEMA_VERSION = 3`);
  - `src/talemate/world/store.py` (`add_fact`, `correct_fact`);
  - `src/talemate/world/view.py` (`FactState.overrides`);
  - `src/talemate/world/undo.py` (copy override links like `fact_refs`).
- Test: `tests/world/test_kinds.py`, `tests/world/test_overrides.py` (new), `tests/world/test_undo.py`.

**Interfaces:**
- Produces:
  - `FieldType` adds `"number"` (an int or float, not a bool, ≥ 0) and `"things"` (a list of 32-hex ids, no duplicates);
  - new kinds: `species`, `race` and `mix`. Fields:
    - `species`: `name: text`, `origin: thing`, `lifespan: number`, `adult_age: number`, `measures: json`;
    - `race`: `name`, `species: thing`, `lifespan`, `adult_age`, `measures`;
    - `mix`: `name`, `parents: things` (exactly 2, distinct, enforced in `validate_field`), `lifespan`, `adult_age`, `measures`;
    - categories for all three: `["origin", "physical", "instinct", "variation", "general"]`;
  - `character` gains `heritage: thing`;
  - `HERITAGE_KINDS: tuple[str, ...] = ("species", "race", "mix")` in `kinds.py`;
  - `measures` holds `list[{"name": str, "min": float, "max": float, "unit": str}]`, validated in `validate_field` for the field named `measures`;
  - a `fact_overrides (row_id INTEGER NOT NULL REFERENCES facts, fact_id TEXT NOT NULL)` table, with an index on `fact_id`;
  - `Revision.add_fact(..., overrides: list[str] | None = None) -> str`, where each id must be a fact live at this revision (`ValueError` otherwise);
  - `Revision.correct_fact(..., overrides: list[str] | None = None)`, where `None` copies the live version's links;
  - `FactState.overrides: list[str]`.

- [ ] **Step 1: Write the failing tests**
  - `test_species_race_mix_kinds`: each kind exists with exactly the fields and categories above.
  - `test_number_field_rejects_bool_and_negative`: `True` and `-1` are rejected for `lifespan`.
  - `test_parents_needs_two_distinct`: one id, three ids, or two equal ids raise `ValueError`.
  - `test_measures_shape`: a measure missing `max` is rejected.
  - `test_add_fact_with_overrides`: `view.thing(c).facts[0].overrides == [species_fact_id]`.
  - `test_override_unknown_fact_rejected`.
  - `test_override_survives_correction`: correcting the *overridden* fact keeps its `fact_id`, and correcting the *overriding* fact without `overrides` keeps its links.
  - `test_undo_restores_override_links`: undoing a `remove_fact` of the overriding fact brings its links back.
  - `test_migration_2_to_3`: an existing v2 database opens with `user_version == 3` and an empty `fact_overrides`.
- [ ] **Step 2: Run them and see them fail**
  - Run: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/world/test_kinds.py tests/world/test_overrides.py tests/world/test_undo.py -q`
  - Expected: FAIL (unknown kind `species`, no `overrides` parameter).
- [ ] **Step 3: Implement**
  - The kinds, the migration, the store parameters and `FactState.overrides`.
  - The view reads overrides with one query per `_fetch_facts` call, joined on `row_id`.
  - Undo's `_apply` copies `fact_overrides` next to `fact_refs`.
- [ ] **Step 4: Run them, plus `tests/world/test_typecheck.py`.** Expected: PASS.
- [ ] **Step 5: Commit**: `feat(world): species, race and mix kinds, number/things fields, fact override links`.

### Task 2: Heritage resolution

**Files:**
- Create: `src/talemate/world/heritage.py`.
- Test: `tests/world/test_heritage.py`.

**Interfaces:**
- Consumes: Task 1's kinds, `FactState.overrides`, `WorldView`.
- Produces:
  - `class Layer(BaseModel)`: `thing_id: str`, `kind: str`, `name: str`, `depth: int` (0 for the thing itself).
  - `class InheritedFact(BaseModel)`: `fact: FactState`, `source_id: str`, `source_kind: str`, `source_name: str`, `overridden_by: str | None`, the overriding `fact_id`.
  - `class Range(BaseModel)`: `min: float`, `max: float`, `unit: str`.
  - `class Numbers(BaseModel)`: `lifespan: float | None`, `adult_age: float | None`, `measures: dict[str, Range]`.
  - `LifeStage = Literal["child", "adolescent", "adult", "elder"]`.
  - `def lineage(view: WorldView, thing_id: str) -> list[Layer]`: follows the thing's own layer, then `heritage`, `species`, `parents` and a character's `culture`, in the Global Constraints order. Each thing appears once. A missing or deleted target is skipped.
  - `def inherited(view: WorldView, thing_id: str) -> list[InheritedFact]`: every fact of layers with `depth > 0`, in layer order, with `overridden_by` set when any more specific layer's fact (the thing's own included) overrides it.
  - `def effective_facts(view: WorldView, thing_id: str) -> list[tuple[FactState, Layer]]`: own facts plus inherited facts not overridden, own first.
  - `def numbers(view: WorldView, thing_id: str) -> Numbers`: the first value set along the lineage, field by field and measure by measure. A mix layer with a value unset uses the average rule.
  - `def life_stage(age: int, numbers: Numbers) -> tuple[LifeStage | None, bool]`: `(stage, past_lifespan)`. The stage is `None` when `adult_age` and `lifespan` are both unset.
  - `def members(view: WorldView, thing_id: str) -> list[str]`: the character ids whose lineage includes `thing_id`.
  - `def species_of(view: WorldView, thing_id: str) -> list[str]`: the species ids a race or mix descends from (a species returns itself).
  - `def find_mix(view: WorldView, a: str, b: str) -> str | None`: the mix whose `parents` are `{a, b}`, in either order.

- [ ] **Step 1: Write the failing tests.** Use a fixture world: Human, Orc and Owl-folk species; Lowlander and Snowy races; a Half-orc mix of Lowlander and Orc; Human culture "Riverfolk" with a customs fact; characters Vasha (Snowy) and Brenna (Half-orc).
  - `test_lineage_order`: Brenna gives `[Brenna, Half-orc, Lowlander, Human, Orc, Riverfolk]`, with the depths ascending.
  - `test_lineage_survives_a_parent_cycle`.
  - `test_lineage_follows_dated_heritage`: Vasha's heritage is set to Barred from 400; `world.view(WorldDate.of(350))` lineage has Snowy.
  - `test_inherited_marks_overrides`: Vasha's own "blue eyes" fact overriding Snowy's "yellow eyes" sets `overridden_by` to that id, and `effective_facts` leaves out the yellow-eyes fact.
  - `test_mix_override_hides_parent_fact_for_members`: a Half-owl mix fact overriding Owl-folk's "wings in place of arms" hides it from a Half-owl character.
  - `test_inherited_skips_deleted_layer`.
  - `test_override_of_removed_fact_is_harmless`.
  - `test_dated_species_fact_reaches_only_later_views`: an Owl-folk fact `since 500` is inherited at 501, not at 499.
  - `test_numbers_fall_back_and_average`:
    - Snowy has wingspan 8.5–9 and the species 7–9, so Snowy resolves to 8.5–9;
    - Half-orc with no lifespan set averages Lowlander's resolved 75 with Orc's 60, giving 67.5.
  - `test_life_stage_bounds`: for adult 12 and lifespan 70:
    - age 8 is a child, and 9 is an adolescent (≥ 9.0);
    - 12 is an adult;
    - 56 is an elder;
    - 71 is past the lifespan.

    With no numbers at all, the result is `(None, False)`.
  - `test_members_and_species_of`: Owl-folk's members include Vasha, and `species_of(Half-orc) == [Human, Orc]`.
  - `test_find_mix_either_order`.
- [ ] **Step 2: Run** `pytest tests/world/test_heritage.py -q`. Expected: FAIL (no module).
- [ ] **Step 3: Implement** `heritage.py`. Reads go through `view.thing()` only, so dates and deletes follow the view. Fixtures go in `tests/world/conftest.py` as `heritage_world`.
- [ ] **Step 4: Run** the tests and `tests/world/test_typecheck.py`. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(world): heritage lineage, inherited facts, numbers and life stage`.

### Task 3: Prose staleness through inheritance

**Files:**
- Modify: `src/talemate/world/prose.py`.
- Test: `tests/world/test_prose.py`.

**Interfaces:**
- Produces:
  - `stretches(view_factory, thing_id, also: Sequence[str] = ()) -> list[tuple[WorldDate | None, WorldDate | None]]`, with the boundary dates merged from `thing_id`'s timeline and each id in `also`;
  - `ProseCache.stale(thing_id, section, at, also: Sequence[str] = ()) -> bool`, which is also true when any id in `also` changed in the stretch since the cached `rev`, by the same two checks as the thing's own. An id in `also` that no longer exists counts as changed.

  Callers pass the lineage ids (`depth > 0`) from Task 2.

- [ ] **Step 1: Write the failing tests**
  - `test_stale_when_species_fact_added`: a character's cached description goes stale after a fact is added to its species, and isn't stale with `also=()`.
  - `test_stretches_include_species_boundary`: a species fact `since 500` splits the character's stretches at 500.
  - `test_stale_when_ancestor_deleted`.
- [ ] **Step 2: Run** `pytest tests/world/test_prose.py -q`. Expected: FAIL (unexpected keyword `also`).
- [ ] **Step 3: Implement**, keeping the default behaviour identical when `also` is empty.
- [ ] **Step 4: Run** `pytest tests/world -q`. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(world): prose staleness follows a thing's lineage`.

### Task 4: Probes for creation with heritage

**Files:**
- Create:
  - `scripts/dev/probe_heritage_create.py`;
  - `docs/superpowers/probes/<run-date>-heritage-create.md`;
  - `docs/superpowers/probes/raw/<run-date>-heritage-create.json`.

**Interfaces:**
- Produces: two prompt bodies, validated against the model and recorded in the findings doc:
  - the **heritage create prompt**: species, race and mix drafting, with numbers;
  - the **inherited-background character prompt**: the inherited facts listed as `F1…Fn`, with the reply's facts carrying `"overrides": ["F2"]`.

  Tasks 6 and 7 copy their wording into the templates.

- [ ] **Step 1: Write the probe script.**
  - Follow the pattern of `docs/superpowers/probes/raw/2026-10-20-heritage-blending.py`: plain `urllib` to `/v1/chat/completions`, prefill `{`, temperature 0.8.
  - Measure it on the owner's species: owl-folk with the Snowy race, and humans with Lowlander and Highlander races.
  - **Cases, 3 runs each:**
    - a species from a one-line prompt (facts in the five categories, plus `lifespan`, `adult_age` and `measures`);
    - a race inside its species (does it stay consistent and narrow the measures?);
    - a Half-orc mix drafted from Lowlander and Orc, using the blending probe's guided rule;
    - a Snowy owl-folk character whose prompt says "blue eyes", given the inherited facts with ids. Does it write only unique facts, and does it mark F(yellow eyes) as overridden?
    - a Lowlander × Half-orc character, from that mix entry.
- [ ] **Step 2: Run it** against koboldcpp (access granted), saving the raw JSON.
- [ ] **Step 3: Write the findings.** For each case, record the parse rate, whether the numbers are sensible, the override accuracy (correct, missed or spurious), and any facts that restate inherited facts. Recommend the final prompt wording for each case.
- [ ] **Step 4: Commit**: `docs(probe): creating species, races, mixes and characters with heritage`.

### Task 5: Inheritance in prose and character sheets

**Files:**
- Modify: `src/talemate/worldplay/prose_gen.py`, `src/talemate/worldplay/characters.py`.
- Test: `tests/worldplay/test_prose_gen.py`, `tests/worldplay/test_characters.py`.

**Interfaces:**
- Consumes: `heritage.effective_facts`, `heritage.lineage`, `heritage.numbers` and `heritage.life_stage` (Task 2), and `stretches`/`stale(also=…)` (Task 3).
- Produces:
  - `prose_gen.inherited_categories(section: str) -> dict[str, tuple[str, ...]]`, with source kind mapping to categories:
    - for `description`: `{"species"|"race"|"mix": ("physical", "variation"), "culture": ("dress",)}`;
    - for `personality`: `{"species"|"race"|"mix": ("instinct",), "culture": ("customs", "belief")}`;
  - `generate_section` and `ensure_prose` build a character section from its own section facts plus those inherited facts, at `at`, and pass the lineage ids as `also`;
  - background: a race or mix section gets its inherited facts as background;
  - `characters.since_lines(world, thing_id, at)` also reports inherited `physical`/`variation` changes not yet in the cached prose, worded like own lines and prefixed with the source name, e.g. `"Since 500: Owl-folk: live to about 60 years."`. It skips overridden facts;
  - `character_from_world` puts `life_stage` into `base_attributes` when known, e.g. `"adult"`. It never raises for a deleted ancestor.

- [ ] **Step 1: Write the failing tests**
  - `test_character_description_includes_inherited_physical`: the render request's `facts` var contains Snowy's plumage fact and not the overridden yellow-eyes fact.
  - `test_personality_includes_instinct_and_customs`.
  - `test_since_line_for_species_change`.
  - `test_character_sheet_life_stage`.
  - `test_character_sheet_with_deleted_species`.
  - `test_species_page_prose_uses_all_facts`: a species has the single `description` section.
- [ ] **Step 2: Run** `pytest tests/worldplay/test_prose_gen.py tests/worldplay/test_characters.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/worldplay -q`. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(worldplay): characters inherit facts in prose and character sheets`.

### Task 6: Create from a prompt: species, races, mixes, and characters with heritage

**Files:**
- Modify:
  - `src/talemate/worldplay/create.py`;
  - `src/talemate/prompts/templates/world/create-thing.jinja2`.
- Create: `src/talemate/prompts/templates/world/create-mix.jinja2`.
- Test: `tests/worldplay/test_create.py`.

**Interfaces:**
- Consumes: Task 4's prompt wording, and `heritage.inherited`.
- Produces:
  - `CREATE_KINDS = ("character", "place", "lore", "species", "race", "mix")`.
  - `PreviewFact.overrides: list[str]` (real fact ids, mapped back from `F1…`; unknown labels dropped).
  - `CreatePreview.fields` carries `lifespan`, `adult_age` and `measures` for heritage kinds. Bad numbers from the reply are dropped, not raised.
  - `preview_thing(world, kind, prompt, fields, client)`:
    - for a character, a race or a mix, the template gets an `inherited` var of `[(label, source_name, category, text)]`, built from the lineage `fields` imply (`heritage`, `species` or `parents`);
    - a mix requires `fields["parents"]` and uses `world/create-mix`;
    - a `prompt` may be empty for a mix only.
  - `accept_preview` writes `overrides` through `add_fact`.

- [ ] **Step 1: Write the failing tests.** Use MockClient replies, and a real model reply from Task 4's raw output as a fixture in `tests/data/worldplay/`.
  - `test_preview_species_numbers`.
  - `test_preview_drops_bad_numbers`: an `"adult_age": "young"` is dropped.
  - `test_preview_character_maps_override_labels`.
  - `test_preview_unknown_override_label_dropped`.
  - `test_preview_mix_requires_two_parents`.
  - `test_preview_mix_empty_prompt_ok`.
  - `test_accept_writes_overrides`.
  - `test_preview_race_gets_species_as_inherited`.
- [ ] **Step 2: Run** `pytest tests/worldplay/test_create.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/worldplay -q`. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(worldplay): create species, races, mixes and characters with heritage from a prompt`.

### Task 7: Heritage for characters invented by scene setup

**Files:**
- Modify:
  - `src/talemate/worldplay/setup.py`;
  - `src/talemate/prompts/templates/world/scene-setup.jinja2`.
- Test: `tests/worldplay/test_setup.py`.

**Interfaces:**
- Produces:
  - `LocalThing.heritage_id: str | None = None`;
  - the setup prompt gets a `heritages: list[str]` var: species, race and mix names, with each race as "Snowy (Owl-folk)". The reply's invented characters may carry `"heritage": "<name>"`, matched case-insensitively against those names, with unknown names ignored;
  - in `start_scene`, an invented character with a heritage gets a description of its own facts followed by its effective inherited `physical`/`variation` facts. Its `base_attributes["personality"]` is the inherited `instinct` facts joined. The local data keeps `heritage_id` for a later make-real.

- [ ] **Step 1: Write the failing tests**
  - `test_setup_invented_character_heritage`: the reply gives `"heritage": "snowy"`. The resulting `LocalThing.heritage_id` is Snowy, and the started scene's local character description contains the plumage fact.
  - `test_setup_unknown_heritage_ignored`.
  - `test_setup_prompt_lists_heritages`.
- [ ] **Step 2: Run** `pytest tests/worldplay/test_setup.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/worldplay -q`. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(worldplay): invented scene characters carry a heritage`.

### Task 8: (dropped — cultures moved to the next slice, owner 2026-10-20)

No work. See the spec's "Cultures: moved to the next slice".

### Task 9: Router: heritage pages, overrides and the mix lookup

**Files:**
- Modify:
  - `src/talemate/server/worlds.py`;
  - `src/talemate/worldplay/references.py` (`_points_at` handles `"things"`).
- Test: `tests/server/test_worlds_plugin.py`, `tests/worldplay/test_references.py`.

**Interfaces:**
- Consumes: Tasks 2, 5 and 6.
- Produces:
  - **New keys in the `_thing_payload` reply:**
    - `"inherited"`: `[{fact_id, category, rendered, source_id, source_kind, source_name, overridden_by}]`;
    - `"numbers"`: `{lifespan, adult_age, measures: {name: {min, max, unit}}}`, resolved;
    - `"life_stage"`: `{stage, past_lifespan}` or `null`, for characters with `born`;
    - `"races"` and `"mixes"`: `[{id, name}]`, for species pages; a mix is listed on every species `species_of` returns;
    - `"referenced_in"`: `thing_references(...)` plus `"member_scenes"`: `[{id, name, start}]`, the scenes with a member character in them;
    - each own fact also gets `"overrides": [fact_id]`.
  - **New router actions:**
    - `override_fact {thing_id, overridden_fact_id, text, category, at}`: adds an own fact linked to the inherited one, then replies like `add_fact`;
    - `list_heritage {}` replies `[{id, kind, name, species_ids}]` for the picker;
    - `find_mix {parents: [a, b]}` replies `{mix_id: str | null}`;
  - `list_things` accepts the kinds `species`, `race` and `mix`.
  - The delete reference check counts a mix's `parents` and a character's `heritage`.

- [ ] **Step 1: Write the failing tests**
  - `test_thing_payload_inherited_and_numbers`.
  - `test_species_payload_lists_races_and_mixes`.
  - `test_override_fact_action`.
  - `test_find_mix_either_order`.
  - `test_list_heritage`.
  - `test_references_count_parents_and_heritage`.
  - `test_member_scenes_in_referenced_in`.
- [ ] **Step 2: Run** `pytest tests/server/test_worlds_plugin.py tests/worldplay/test_references.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit**: `feat(worlds): heritage payloads, override and mix lookup actions`.

### Task 10: Frontend: species, race and mix pages, and the Inherited section

**Files:**
- Modify:
  - `talemate_frontend/src/components/worlds/worldKinds.js`;
  - `ThingPage.vue`, `WorldTab.vue`;
  - `talemate_frontend/src/stores/worlds.js`.
- Create:
  - `talemate_frontend/src/components/worlds/ThingInherited.vue`;
  - `ThingNumbers.vue`;
  - `HeritageSections.vue` (Races and Mixes);
  - `ThingReferencedIn.vue`.
- Test: `tests/e2e/worlds/test_heritage_pages.py`, `talemate_frontend/checks/worlds.check.mjs`.

**Interfaces:**
- Consumes: Task 9's payload keys and actions.
- Produces, following the approved mockup (spec, "The pages"):
  - **`worldKinds.js`** adds Species (`mdi-dna`), Race and Mix. Races and mixes are not listed at the top level of the World tab; they're reached from their species page.
  - **`ThingNumbers.vue`:** lifespan, adulthood and measures, editable on species, race and mix pages through `set_field`. A race or mix page shows an unset value as the inherited value, dimmed.
  - **`ThingInherited.vue`:** on character, race and mix pages:
    - facts dimmed, with a source chip that links to the source page;
    - an **Override** button, which opens `ThingFactForm` pre-filled and sends `override_fact`;
    - an overridden fact shown struck through, with "replaced by its own fact".
  - **Character page:** Heritage as links, and the life stage next to the age, e.g. "age 48 · adult". An age past the lifespan shows a warning chip.
  - **`ThingReferencedIn.vue`:** entries and member scenes. It replaces the bare "Appears in" list on the new kinds.
  - Test ids for each: `numbers-<field>`, `inherited-fact`, `override-button`, `races-section`, `mixes-section`, `referenced-in`.

- [ ] **Step 1: Write the failing browser test** `test_species_page_and_inheritance`, seeded through `tests/e2e/seed.py` with Owl-folk, Snowy and Vasha:
  - the Owl-folk page shows its races and numbers;
  - Vasha's page shows inherited facts with source chips;
  - pressing Override on yellow eyes and saving "Blue eyes" strikes the inherited fact through.
- [ ] **Step 2: Run** `pytest tests/e2e/worlds/test_heritage_pages.py -m e2e -n 1`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `grep -rn` over `tests/ai` for changed test ids, then the full browser suite with `-n 4`. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(worlds): species, race and mix pages with inherited facts`.

### Task 11: Frontend: the heritage picker and mix-first creation

**Files:**
- Modify: `CreateBox.vue`, `talemate_frontend/src/stores/worlds.js`, `WorldTab.vue`.
- Create: `talemate_frontend/src/components/worlds/HeritagePicker.vue`.
- Test: `tests/e2e/worlds/test_heritage_create.py`.

**Interfaces:**
- Consumes: `list_heritage`, `find_mix`, and `preview_thing` with `fields.heritage`/`fields.parents`.
- Produces:
  - **`HeritagePicker.vue`:** one or two parents, each searchable over `list_heritage`. It sits above the prompt for characters. A world species named in the prompt pre-fills it, using `match_names` results filtered to heritage kinds.
  - **The mix-first flow:**
    - with two parents, `find_mix` runs first;
    - **a mix exists:** it becomes `heritage`;
    - **no mix:** the create box switches to drafting a mix of those parents, with a notice: "This heritage needs a mix entry first, so every character of it shares one body plan." Accepting the mix returns to the character create box, with the prompt kept and `heritage` set to the new mix. Cancelling returns there with the parents still picked.
  - **Race and mix creation:** from their species page ("+ New race" and "+ New mix"), which opens the create box with `species` or one parent pre-set.

- [ ] **Step 1: Write the failing browser tests**, using `TALEMATE_TEST_FIXED_PREVIEW` fixtures:
  - `test_two_parents_without_mix_drafts_mix_first`: picking Lowlander and Orc shows the mix draft, accepting it returns to the character box with Half-orc picked, and the prompt text is unchanged.
  - `test_two_parents_with_mix_uses_it`.
- [ ] **Step 2: Run** the tests. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full browser suite with `-n 4`. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(worlds): heritage picker and mix-first creation`.

### Task 12: End to end with the mock model, and the play probe

**Files:**
- Create:
  - `tests/worldplay/test_heritage_end_to_end.py`;
  - `scripts/dev/probe_heritage_play.py`;
  - `docs/superpowers/probes/<run-date>-heritage-play.md`, plus its raw JSON.

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Write the end-to-end test** with MockClient, through the real router:
  - create Owl-folk, Snowy and a Snowy character with an override;
  - start a scene with an invented owl-folk innkeeper;
  - assert the character sheet has inherited plumage, no yellow eyes, and a life stage;
  - assert the innkeeper's description has the inherited body;
  - pass time across a dated species fact and assert the since line.
- [ ] **Step 2: Run it.** Expected: PASS. Then run the full plain suite: 0 failed.
- [ ] **Step 3: Write and run the play probe** against koboldcpp:
  - build the character sheets with `character_from_world` and the scene context with `world_context_block`;
  - send 3 narrator-style and 3 conversation-style turns to the model;
  - check that owl-folk use wings and talons (no hands, no gloves) and act in keeping with their instincts, including the invented innkeeper.

  Record the findings and any prompt-assembly fix needed. Fix that in `worldplay`, not the schema.
- [ ] **Step 4: Commit**: `test(worldplay): heritage end to end; docs(probe): heritage in play`.

### Task 13: The owner's acceptance run (owner-gated)

Start the isolated app with `--ai` on a fresh root, and give the owner the URL. The owner runs the spec's session:
1. make the species;
2. add races;
3. generate characters, including a mix;
4. play a scene.

Fix any hiccups with root-caused, tested fixes, each reviewed. Record the results in `docs/superpowers/probes/<run-date>-heritage-acceptance.md`.
