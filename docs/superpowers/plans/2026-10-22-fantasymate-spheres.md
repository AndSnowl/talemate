# Spheres Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Religions, nations, orders, cultures and fields of knowledge become spheres: entries with typed, titled drawers; "part of" links; one people list made of character ties with "but…" exceptions; dated timelines; and branches. Generation runs in two steps, and spheres reach play under a capped context rule.

**Architecture:**
- **Data:** a new `sphere` kind, and sphere fields on places (`template`, `agent`, `drawers`). Every kind gains `part_of`; characters gain `ties`. Facts gain a readable `origin`. All of this lives in the strict `src/talemate/world/`.
- **Resolution:** a pure `world/spheres.py` resolves drawers, items (with branch inheritance), people, territory, timeline, ties and key facts.
- **Bridge:** `worldplay/spheres.py` handles the core, Fill, promotion and "End this…". Character creation proposes ties. Context assembly adds tie lines and sphere key facts.
- **Frontend:** a sphere page, a character's Ties section, and a "Part of" line on any entry.

**Tech stack:** Python 3.11, SQLite (the world store), pydantic 2, Jinja2 through `Prompt.request`, Vue 3 + Vuetify, Pinia, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-10-22-fantasymate-spheres-design.md` (approved by the owner on 2026-10-22). Earlier specs: the main spec, plan B, and Connections.

## Global Constraints

- **Guix:** run everything through `guix shell -m manifest.scm -- …` with `uv run --no-sync`. The plain suite stays at **0 failed**; the baseline on main 520d60a1 is 7054 passed, 6 skipped.
- **Testing (owner):**
  - focused tests while iterating, then the full plain suite once per task;
  - the browser suite (`pytest tests/e2e -m e2e -n 4`, never more than 4) once at the end of a UI task, after checking for orphaned apps;
  - `grep -rn` over `tests/ai` for changed UI ids.
- **Probes:** Skyfall probes need the owner's go-ahead; ask before Task 3 and Task 10. The model is koboldcpp at `http://192.168.0.5:5001`, one GPU, calls run one at a time. Plain tests use `MockClient` only. Probe docs are named with their run date, and raw output goes under `docs/superpowers/probes/raw/`.
- **`src/talemate/world/`** stays strict-mypy clean, with no imports from the rest of talemate.
- **Every world AI call** goes through `worldplay.ai.world_ai_call()`. Replies are parsed with the shared non-strict `create.json_objects`. No raw `[[thing:…]]` reaches a prompt.
- **No extra LLM calls** on ordinary turns or while typing.
- **Templates:** `religion`, `nation`, `order`, `culture`, `field`, `other`. Agent by template: religion, nation and order are agents; culture and field are not; other is not.
- **Drawer types:** `people`, `places`, `practices`, `beliefs`, `knowledge`, `structure`, `branches`, `events`.
- **People** is one drawer, built from character ties. Roles replace separate lists.
- **Nothing is generated behind the owner's back.** Expanding a child never creates its parent sphere.
- **Exceptions** are facts in the character category `ties`. The rejected item is referenced in their text.
- **Context:**
  - **always:** tie lines with their exceptions;
  - **a sphere's key facts, only when a scene touches it:** territory, named, or a member present;
  - **key facts:** the summary, then the top beliefs and practices items (structure for agents), then the latest 3 timeline facts, at most 8 lines per sphere;
  - **a nested sphere** brings its parent's summary only.
- **Fresh worlds only.** The old `culture` kind stays readable for old worlds, but is no longer created or guessed.
- **New screens:** theme roles and the Pinia store `stores/worlds.js`.

## Review Focus

1. **A branch whose parent is deleted, or a cycle of parents:** resolution terminates and the branch shows its own items (Task 2: `test_branch_of_deleted_parent`, `test_branch_parent_cycle`).
2. **A drawer deleted or retyped while items are part of it:** the items stay reachable under an "Unsorted" drawer rather than vanishing (Task 2: `test_items_of_removed_drawer_are_unsorted`).
3. **Ending a part-of link and then undoing the end:** the item returns to its drawer, and its timeline dates match (Task 6: `test_end_item_then_undo`).
4. **A tie to a sphere that is later deleted:** the character page and sheet show nothing broken, and the tie renders as plain text (Task 7: `test_tie_to_deleted_sphere`).
5. **A place that is a sphere, used as a scene location:** the scene's context includes its key facts exactly once, not twice through territory and naming (Task 7: `test_place_sphere_context_once`).

---

### Task 1: Sphere data in the world store

**Files:**
- Modify: `src/talemate/world/kinds.py`, `src/talemate/world/view.py` (`FactState.origin`).
- Test: `tests/world/test_kinds.py`, `tests/world/test_spheres_data.py` (new).

**Interfaces:**
- Produces:
  - **`SPHERE_TEMPLATES`, `TEMPLATE_AGENT: dict[str, bool]`, `DRAWER_TYPES`** in `kinds.py`, with the values from Global Constraints.
  - **Kind `sphere`:**
    - fields: `name: text`, `template: text`, `agent: json` (bool), `drawers: json`, `parent: thing` (branches, dated by `valid_from`), `drops: things`, `language: json` (legacy carrier), plus the shared fields;
    - categories: `["timeline", "about", "statement"]`.
  - **Kind `place`** gains `template`, `agent` and `drawers`, and category `statement`.
  - **Every kind gains `part_of: json`**: `{"sphere": <32-hex>, "drawer": <8-hex>}` or `null`. A dated `null` value ends it.
  - **`character` gains `ties: json`**: `list[{"sphere": <32-hex>, "role": str, "since": WorldDate|null, "until": WorldDate|null}]`. It also gains category `ties`.
  - **`drawers` values:** `list[{"id": <8-hex>, "type": DRAWER_TYPES, "title": non-blank str}]`, list order is display order, ids unique. All of these are validated in `validate_field`. `template` must be in `SPHERE_TEMPLATES`.
  - **A `statement` fact** carries `origin={"drawer": <8-hex>}`, so a plain-statement item belongs to a drawer.
  - **`FactState.origin: dict | None`**, read from `origin_json`.
  - **`LEGACY_KINDS = ("culture",)`:** these kinds stay in `KINDS` for reading old worlds; creation and guessing skip them (Task 4).

- [ ] **Step 1: Write the failing tests.**
  - `test_sphere_kind_fields`
  - `test_place_takes_sphere_fields`
  - `test_drawers_validated`: rejects a duplicate id, an unknown type, a blank title.
  - `test_template_validated`
  - `test_part_of_and_ties_shape`
  - `test_fact_origin_read_back`
- [ ] **Step 2: Run** `pytest tests/world/test_kinds.py tests/world/test_spheres_data.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/world -q`, strict mypy included. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(world): sphere kind, sphere fields on places, part-of links and ties`.

### Task 2: Resolving spheres

**Files:**
- Create: `src/talemate/world/spheres.py`.
- Modify: `src/talemate/world/heritage.py` (the culture layer leaves the lineage).
- Test: `tests/world/test_spheres.py` (new), `tests/world/test_heritage.py`.

**Interfaces:**
- Consumes: Task 1. Reuses `heritage`'s dominance-based override rule for branch facts.
- Produces:
  - **`class Drawer(BaseModel)`:** `id`, `type`, `title`. Plus `UNSORTED: Drawer` (`id="unsorted"`, `type="knowledge"`, `title="Unsorted"`).
  - **`class Item(BaseModel)`:** `thing_id: str | None`, `fact_id: str | None`, `name: str`, `text: str`, `drawer_id: str`, `source_id: str` (the sphere it comes from), `inherited: bool`, `stub: bool`.
  - **`class Tie(BaseModel)`:** `character_id`, `sphere_id`, `role`, `since: WorldDate | None`, `until: WorldDate | None`.
  - **`is_sphere(state: ThingState) -> bool`:** kind `sphere`, or a place with a `template`.
  - **`drawers(view, sphere_id) -> list[Drawer]`:** its own drawers, then a branch's inherited drawers that it lacks (matched by id).
  - **`items(view, sphere_id) -> list[Item]`:**
    - the things whose `part_of` points at it;
    - its `statement` facts;
    - for a branch, its parent chain's items minus its `drops`, and minus parent facts its own facts override.

    A drawer id that's missing maps to `UNSORTED`. Cycles are guarded, and deleted parents are skipped.
  - **`people(view, sphere_id) -> list[Tie]`:** the ties pointing at it that are live at `view.at`.
  - **`territory(view, sphere_id) -> list[str]`:** place ids. For a place sphere, itself and its descendants; plus the places that are `part_of` it in a places drawer.
  - **`timeline(view, sphere_id) -> list[FactState]`:** its `timeline` facts, plus, for a branch, the parent's timeline facts dated before the branch's `parent` `valid_from`. Sorted by date.
  - **`ties_of(view, character_id) -> list[Tie]`.**
  - **`exceptions(view, character_id, sphere_id) -> list[FactState]`:** the character's `ties` facts whose refs include the sphere or one of its items.
  - **`key_facts(view, sphere_id) -> list[str]`:** rendered text per the Global Constraints rule, capped at 8.
  - **`TEMPLATE_DRAWERS: dict[str, list[tuple[str, str]]]`:** the default `(type, title)` drawers per template, taken from the probe's menu results:
    - religion: beliefs "Doctrines", structure "Hierarchy", practices "Rites and Ceremonies", people "People", places "Holy Sites", events "Timeline";
    - nation: structure "Government", beliefs "Laws", people "People", places "Lands", events "Timeline";
    - order: structure "Ranks", knowledge "Fields of Study", practices "Practices", people "Members", places "Sites", events "Timeline";
    - culture: practices "Customs and Holidays", beliefs "Beliefs and Legends", people "People", events "Timeline";
    - field: knowledge "Principles", practices "Techniques", knowledge "Frontier", people "Practitioners", events "Timeline";
    - other: events "Timeline".
  - **`heritage.lineage` no longer follows a character's `culture`.** Update the plan B tests that expected the culture layer.

- [ ] **Step 1: Write the failing tests**, with a fixture of the White Dawn (religion), its Reformed Dawn branch, the Council of Elders `part_of` Hierarchy, the Tsardom (a place sphere with towns), and Vasha tied as a practitioner with one exception.
  - `test_items_by_drawer`
  - `test_branch_inherits_and_drops`
  - `test_branch_of_deleted_parent`
  - `test_branch_parent_cycle`
  - `test_items_of_removed_drawer_are_unsorted`
  - `test_people_from_ties_at_date`
  - `test_place_sphere_territory_includes_towns`
  - `test_branch_timeline_cut_at_split`
  - `test_exceptions_by_ref`
  - `test_key_facts_capped`
  - `test_lineage_has_no_culture_layer`
- [ ] **Step 2: Run** `pytest tests/world/test_spheres.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/world tests/worldplay -q`. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(world): resolve spheres: drawers, items, branches, people, territory, timeline, ties`.

### Task 3: Probes (owner-gated)

**Files:**
- Create: `scripts/dev/probe_spheres.py`, `docs/superpowers/probes/<run-date>-spheres.md`, and its raw JSON.

**Interfaces:**
- Produces: "Recommended prompt text" for these four, which Tasks 4, 5 and 7 copy:
  - (a) the core with its drawer outline;
  - (b) Fill;
  - (c) ties and exceptions at character creation;
  - (d) sphere key facts in the scene context.

- [ ] **Step 1: Ask the owner for the go-ahead.**
- [ ] **Step 2: Write the probe script.** Build on `docs/superpowers/probes/raw/2026-10-22-sphere-structure.py` and `scripts/dev/probe_connections_flow.py`, with Connections context (mentions, named entries). Run 2 times each:
  - **(1) The core:** for each template, the core plus an outline of drawers whose types come from `TEMPLATE_DRAWERS`. Retitling is allowed, with 2 to 4 named items each. Check for truncation and for sensible types and titles.
  - **(2) Fill:**
    - fill the White Dawn's Hierarchy when the Council of Elders already exists `part_of` it: no rival council;
    - expand the White Dawn after the council: it's written around the council.
  - **(3) A character created with a heritage and the White Dawn in context:** does the model propose ties and "but…" exceptions that link to the right items?
  - **(4) Three narrator turns in a scene at a White Dawn holy site,** with key facts against without: does it use them and stay on topic?
- [ ] **Step 3: Run, one call at a time.** Write the findings with a recommendation for each.
- [ ] **Step 4: Commit**: `docs(probe): sphere core, fill, ties and context`.

### Task 4: The core, Fill, promotion and stubs as spheres

**Files:**
- Create: `src/talemate/worldplay/spheres.py`, `src/talemate/prompts/templates/world/sphere-core.jinja2`, `src/talemate/prompts/templates/world/sphere-fill.jinja2`.
- Modify: `src/talemate/worldplay/create.py` (`CREATE_KINDS`/`NAME_KINDS` add `sphere`; `culture` guesses map to a sphere with template `culture`; legacy kinds aren't created).
- Test: `tests/worldplay/test_spheres_create.py` (new).

**Interfaces:**
- Consumes: Tasks 1-3, plus Connections' `make_stubs`, `link_text` and `mention_context`.
- Produces:
  - **`class SpherePreview(CreatePreview)`,** adding:
    - `template`, `agent`, `drawers`;
    - `items: list[{drawer_id, name, text, kind}]`: named items become stubs `part_of` the sphere on accept; nameless ones become `statement` facts;
    - `adopted: list[{thing_id, drawer_id}]`.
  - **`async preview_sphere(world, template, prompt, fields, client, *, stub_id=None, picks=None, new_names=None, promote_id=None) -> SpherePreview`:**
    - writes the core with Task 3 (a);
    - the context includes everything already `part_of` the stub (or the promoted thing), and those become `adopted`, filed into the matching drawer type;
    - with `promote_id`, the thing's existing facts are context and kept.
  - **`accept_sphere(world, preview) -> str`,** in one revision:
    - **a stub:** fills it, or, if its kind differs, uses `change_stub_kind` to `sphere`;
    - **promotion:** adds the template, agent and drawers to the promoted thing (a lore entry or a place), keeping its id and kind for places. A lore entry becomes kind `sphere` through a kind change. Write `Revision.promote_to_sphere(thing_id)`, allowed for lore and stubs only: it retires the thing row and re-inserts it with kind `sphere`, keeping facts, as `change_stub_kind` does;
    - **otherwise:** creates a new sphere.

    It then writes the drawers, and the items as stubs with `part_of` or as statements, and links the facts.
  - **`async fill_drawer(world, sphere_id, drawer_id, client) -> list[dict]`:** item previews from Task 3 (b), with no write. `accept_fill(world, sphere_id, drawer_id, items) -> None` writes them as above.
  - **Child-first expansion:** when `preview_thing` expands a stub whose mentions are all from inside one sphere's items, or whose prompt names a sphere stub, the preview carries `part_of={"sphere": <id>, "drawer": <guessed drawer of the matching type or UNSORTED>}`. Expanding never creates the parent.
  - **Stub kind guesses:** `NewName.kind == "sphere"` carries `template` (religion, nation, order, culture or field) from the reply. Task 3 (a)'s wording sets it.
- [ ] **Step 1: Write the failing tests,** with MockClient replies from Task 3's raw output:
  - `test_preview_sphere_outline_and_items`
  - `test_accept_sphere_makes_item_stubs_part_of`
  - `test_expand_sphere_adopts_existing_children`
  - `test_child_first_gets_part_of_stub_parent_untouched`
  - `test_promote_lore_keeps_id_and_facts`
  - `test_promote_place_keeps_kind`
  - `test_fill_drawer_no_write_until_accept`
  - `test_culture_guess_becomes_culture_sphere`
- [ ] **Step 2: Run** `pytest tests/worldplay/test_spheres_create.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/worldplay tests/world -q`, then the full plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit**: `feat(worldplay): spheres from a prompt in two steps, promotion and part-of adoption`.

### Task 5: Branches and "End this…"

**Files:**
- Modify: `src/talemate/worldplay/spheres.py`.
- Test: `tests/worldplay/test_spheres_create.py`.

**Interfaces:**
- Produces:
  - **`async preview_branch(world, parent_id, prompt, client) -> SpherePreview`:** a sphere with `parent=parent_id`, dated now. The prompt gets the parent's items labelled F1…, and the reply's `drops` and `overrides` labels map to item and fact ids, as Connections' override labels do.
  - **`end_item(world, sphere_id, item: Item, at: WorldDate, by: str | None) -> None`,** in one revision:
    - for a thing item, `part_of` is set to `null` at `at`;
    - for a statement, `end_fact` at `at`;
    - the item gets an `about` fact "Ended in <date>[ by [[thing:by]]]";
    - if `by` is a sphere, it gets a `timeline` fact linking the item.
- [ ] **Step 1: Write the failing tests:**
  - `test_branch_preview_maps_drops_and_overrides`
  - `test_end_item_links_both_sides`
  - `test_end_item_then_undo`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/worldplay -q`. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(worldplay): sphere branches and ending an item`.

### Task 6: Ties at character creation

**Files:**
- Modify: `src/talemate/worldplay/create.py`, `src/talemate/prompts/templates/world/create-thing.jinja2`.
- Test: `tests/worldplay/test_create.py`.

**Interfaces:**
- Produces:
  - **The character create prompt** lists the spheres in context. These come from Connections' named and mention context, plus spheres whose territory holds a picked place, each with its top items labelled S1…, using Task 3 (c)'s wording.
  - **The reply** may give `"ties": [{"sphere": "<name>", "role": "...", "since": YEAR, "exceptions": [{"text": "...", "rejects": "S3"}]}]`.
  - **`CreatePreview.ties`:** ties resolved only to existing spheres by name or other name; unknown ones are dropped. Each tie carries its exceptions, with each `rejects` label mapped to an item ref.
  - **On accept,** `ties` is written, and each exception becomes a `ties` fact whose text ends with a reference to the rejected item.
- [ ] **Step 1: Write the failing tests:**
  - `test_character_preview_proposes_ties_to_existing_spheres`
  - `test_unknown_sphere_tie_dropped`
  - `test_exception_links_rejected_item`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/worldplay -q`. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(worldplay): character creation proposes ties with exceptions`.

### Task 7: Spheres in play

**Files:**
- Modify: `src/talemate/worldplay/characters.py`, `src/talemate/worldplay/context.py`, `src/talemate/prompts/templates/world/scene-context.jinja2`.
- Test: `tests/worldplay/test_characters.py`, `tests/worldplay/test_context.py`.

**Interfaces:**
- Produces:
  - **The character sheet** (`character_from_world`) adds `base_attributes["ties"]`: one line per live tie, for example "Practitioner of the White Dawn (since 1010), but: doesn't believe snowy owl-folk are superior". A tie to a deleted sphere renders its stored name as plain text, or is left out if there's no name.
  - **`world_context_block`** adds one block per touched sphere (Global Constraints: territory holds the scene's place, the prompt or setup names it, or a member is present), each with its `key_facts` and the parent's summary for a nested sphere. Each sphere appears once, using Task 3 (d)'s wording.
- [ ] **Step 1: Write the failing tests:**
  - `test_sheet_has_tie_lines_with_exceptions`
  - `test_tie_to_deleted_sphere`
  - `test_context_touched_sphere_key_facts`
  - `test_place_sphere_context_once`
  - `test_untouched_sphere_not_in_context`
  - `test_no_extra_model_calls_on_turn`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit**: `feat(worldplay): ties on character sheets and touched spheres in scene context`.

### Task 8: Router

**Files:**
- Modify: `src/talemate/server/worlds.py`.
- Test: `tests/server/test_worlds_plugin.py`.

**Interfaces:**
- Produces:
  - **The thing payload gains:**
    - `sphere`: `null`, or `{template, agent, drawers: [{id, type, title, items: [{thing_id, fact_id, name, segments, inherited, stub}]}], people: [{character_id, name, role, since, until}], territory: [{id, name}], timeline: [{fact_id, date, segments}], branches: [{id, name}], parent: {id, name} | null}`;
    - `part_of`: `null`, or `{sphere_id, sphere_name, drawer_id, drawer_title}`;
    - `ties`, for characters: `[{sphere_id, sphere_name, role, since, until, exceptions: [{fact_id, segments}]}]`.
  - **New actions:**
    - `preview_sphere {template, prompt, fields, stub_id, picks, new_names, promote_id}` and `accept_sphere {preview}`;
    - `fill_drawer {sphere_id, drawer_id}` and `accept_fill {sphere_id, drawer_id, items}`;
    - `set_drawers {sphere_id, drawers}` (add, retitle, reorder, drop);
    - `set_part_of {thing_id, sphere_id|null, drawer_id}`;
    - `set_ties {character_id, ties}`;
    - `add_exception {character_id, sphere_id, text, rejects}`;
    - `preview_branch {parent_id, prompt}`;
    - `end_item {sphere_id, thing_id|fact_id, at, by}`.
  - **Writes** schedule prose only when rendered text changes (Connections' rule).
  - **`list_things`** accepts `sphere` and groups by `template`.
- [ ] **Step 1: Write the failing tests**, one per action plus `test_payload_sphere_part_of_ties`.
- [ ] **Step 2: Run** `pytest tests/server/test_worlds_plugin.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit**: `feat(worlds): sphere, drawer, tie and branch actions`.

### Task 9: Frontend

**Files:**
- Create in `talemate_frontend/src/components/worlds/`: `SpherePage.vue` (or sections inside ThingPage), `SphereDrawer.vue`, `TiesSection.vue`, `PartOfLine.vue`.
- Modify: `ThingPage.vue`, `WorldTab.vue`, `worldKinds.js` (a Spheres list grouped by template, with stubs dimmed), `CreateBox.vue` (a template picker for spheres, the sphere preview with its outline, Fill and promotion), and `stores/worlds.js`.
- Test: `tests/e2e/worlds/test_spheres.py` (new) and `talemate_frontend/checks/worlds.check.mjs`.

**Interfaces:**
- Consumes: Task 8.
- Produces, following the approved mockup (spec, "The pages"):
  - **The sphere page:** template and agent chips, the summary, and typed, titled drawers (each with a dashed type tag, items, Fill when empty, and "+ Add"). Also People with roles and dates, territory, the Timeline, Branches with "+ New branch", "+ Add a drawer", and drawer retitle, reorder and drop, plus "End this…" on items.
  - **The character page's Ties section:** a tie with its role, dates and "but…" exceptions, with "+ Add tie" and "+ Add exception".
  - **A "Part of" line** on every entry, which is editable.
  - **"Make it a sphere…"** on lore entries, stubs and places.
  - **Test ids:** `sphere-drawer`, `drawer-fill`, `sphere-people`, `sphere-timeline`, `ties-section`, `tie-exception`, `part-of`, `make-sphere`.
- [ ] **Step 1: Write the failing browser tests,** using fixed preview fixtures:
  - `test_sphere_page_drawers_and_fill`
  - `test_child_first_then_sphere_adopts`
  - `test_ties_with_exceptions`
  - `test_promote_lore_and_place`
  - `test_end_item`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full browser suite with `-n 4`, the node checks, and the `tests/ai` grep. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(worlds): sphere pages, ties and part-of`.

### Task 10: End to end, and a Skyfall session (owner-gated)

**Files:**
- Create: `tests/worldplay/test_spheres_end_to_end.py`, `scripts/dev/probe_spheres_flow.py`, `docs/superpowers/probes/<run-date>-spheres-flow.md` and its raw JSON.

- [ ] **Step 1: Write the end-to-end test** through the router, with MockClient:
  1. the Tsardom, whose religion stub is guessed as a religion sphere;
  2. the council expanded first, with `part_of` the stub;
  3. the White Dawn expanded, adopting the council;
  4. Fill Doctrines;
  5. a character with a tie and an exception;
  6. a scene at a holy site: the context holds the key facts once, and there are no extra calls on a turn.
- [ ] **Step 2: Run it,** then the full plain suite. Expected: 0 failed.
- [ ] **Step 3: Ask the owner, then run the same session on Skyfall.** Judge it against the spec's "How the owner will judge it". Fix prompt assembly in worldplay, with a test, if needed.
- [ ] **Step 4: Commit**: `test(worldplay): spheres end to end; docs(probe): spheres in a real session`.

### Task 11: The owner's acceptance run (owner-gated)

Start the isolated app on a fresh root with `--ai --lan`, and give the owner the URL. The owner runs the spec's session. Fix hiccups with root-caused, tested and reviewed fixes. Record the results in `docs/superpowers/probes/<run-date>-spheres-acceptance.md`.
