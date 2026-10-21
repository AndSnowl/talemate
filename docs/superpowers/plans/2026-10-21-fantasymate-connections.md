# Connections Between Entries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Find important names in world text and link them. Turn names that don't exist yet into stubs the owner can follow. Give entries other names. Let context flow along the links, so a place is generated knowing who lives there.

**Architecture:**
- **Data:** references keep the words written (`[[thing:<id>|shown]]`); every kind gains an `aka` field (other names, tagged) and a `stub` marker. This lives in the strictly typed `src/talemate/world/`.
- **Name-finding:** a shared, model-free name index in a new `src/talemate/world/names.py` replaces scene setup's `match_names`.
- **The bridge:** new `src/talemate/worldplay/links.py` (linking text, making stubs) and `src/talemate/worldplay/mentions.py` (context from mentions, suggested prompts). These feed create-from-prompt, hand-written facts and scene setup.
- **Frontend:** a shared linked-text renderer with hover cards; a highlighted prompt input shared with the new-scene dialog; a Stubs tab; an editor for other names; a right-click "Add reference".

**Tech stack:** Python 3.11, SQLite (the world store), pydantic 2, Jinja2 templates through `Prompt.request`, Vue 3 + Vuetify, Pinia, Playwright e2e.

**Spec:**
- `docs/superpowers/specs/2026-10-21-fantasymate-connections-design.md`, which this plan implements;
- the main spec, `docs/superpowers/specs/2026-10-18-fantasymate-world-data-model-design.md` ("Connections between entries").

## Global Constraints

- **Running things on Guix:** everything runs through `guix shell -m manifest.scm -- …` with `uv run --no-sync`. The plain suite stays at **0 failed**; the baseline on main d1153a50 is 6935 passed, 6 skipped, about 40 s.
- **Testing (owner):** run focused tests while iterating and the full plain suite once per task. The browser suite (`pytest tests/e2e -m e2e -n 4`, never more than 4) runs once at the end of a UI task; check for orphaned apps first. A UI change the AI tests drive needs `grep -rn` over `tests/ai`.
- **koboldcpp:** the owner approved this plan's Skyfall tests (2026-10-21). The model is `http://192.168.0.5:5001`, Skyfall-31B-v4.2-i1-Q4_K_M, one GPU, so calls run one at a time. Plain tests use `MockClient` only. Raw probe output is committed under `docs/superpowers/probes/raw/`, and probe docs are named with the date they're run.
- **`src/talemate/world/`** stays under strict mypy (`tests/world/test_typecheck.py`), with no imports from the rest of `talemate`.
- **Every world AI call goes through `worldplay.ai.world_ai_call()`.** Replies are parsed with the shared non-strict `create.json_objects`.
- **No extra LLM calls on ordinary turns, and none while typing.** Name-finding is code. Context assembly runs at create, edit and scene setup only.
- **Proper names only** (owner): places, characters, named events and other named things count; "the postmaster", "a war" and "his mother" don't. "Yelena" in "his mother Yelena" counts.
- **Linking never changes wording.** A linked mention keeps its written text as the reference's shown text.
- **The owner's choices always win:** picks, "treat as new" and re-pointing beat automatic matches.
- **Other names (`aka`):** a list of `{"name": str, "tag": "proper" | "common", "everyday": bool}`, with at most one `everyday: true`, and that one must be tagged `common`. The main name is always the most proper.
- **New screens** use theme roles (`rgb(var(--v-theme-<role>))`) and the Pinia store `talemate_frontend/src/stores/worlds.js`.

## Review Focus

1. **An entry or stub whose name is a common word** ("Hope", "River") must not link the lowercase word in "I hope". Names match case-insensitively only when the written text starts with a capital letter, or when the name itself has an inner capital (Task 2: `test_common_word_name_needs_a_capital`).
2. **A rename.** A link whose shown text was the old main name follows the rename; "Moscavia" and "Yelena's" stay as written (Task 1: `test_rename_updates_full_name_links_only`).
3. **A deleted entry or stub** that facts link to renders the shown text as plain text, not "⟨unknown⟩", and expanding a deleted stub is refused (Task 1: `test_deleted_target_renders_shown_text`; Task 5: `test_expand_deleted_stub_refused`).
4. **One name invented by two generations** (Frosthollow named by Vasha and later by a place) gives one stub with two mentions, not two stubs (Task 4: `test_make_stubs_reuses_existing_name`).
5. **Expanding an ignored stub** keeps its id, clears both its stub marker and its ignored flag, and turns every mention into a normal link (Task 5: `test_expand_ignored_stub_keeps_id_and_revives`).

---

### Task 1: References with shown text, other names, and the stub marker

**Files:**
- Modify:
  - `src/talemate/world/refs.py`;
  - `src/talemate/world/kinds.py` (every kind gains `aka: json` and `stub: json`; `validate_field` checks both);
  - `src/talemate/world/view.py` (`render`; `ThingState.is_stub`);
  - `src/talemate/world/store.py` (`Revision.change_stub_kind`).
- Test: `tests/world/test_refs.py`, `tests/world/test_kinds.py`, `tests/world/test_stubs.py` (new).

**Interfaces:**
- Produces:
  - `REF_PATTERN` matches `[[thing:<32-hex>]]` and `[[thing:<32-hex>|<shown>]]`. A `shown` text holds no `]]`. `parse_refs(text)` is unchanged and still returns ids;
  - `ref(thing_id: str, shown: str | None = None) -> str`;
  - `WorldView.render(text) -> str`: a reference with no shown text renders as today. With shown text, it renders the shown text, unless that equals (case-insensitively) any main name the target has ever had on its timeline, in which case it renders the target's current name at `at`. A target that doesn't exist renders its shown text;
  - `WorldView.segments(text) -> list[Segment]`, where `Segment(BaseModel)` has `text: str` and `ref: str | None`. It splits rendered text into plain and linked runs, for the frontend;
  - `aka` values follow the Global Constraints shape, validated in `validate_field` for the field named `aka`;
  - `stub` values: `{"ignored": bool}`, validated for the field named `stub`;
  - `ThingState.is_stub -> bool` and `ThingState.stub_ignored -> bool` (properties read from `fields`);
  - `Revision.change_stub_kind(thing_id: str, kind: str) -> None`: allowed only while the thing is a stub (`ValueError` otherwise). It retires the thing row and inserts one with the new kind and the same id. Fields and facts are kept, and undo reverses it.

- [ ] **Step 1: Write the failing tests**
  - `test_ref_with_shown_text_roundtrip`: `parse_refs(ref(a, "Moscavia")) == [a]`.
  - `test_render_shown_text`: renders "Moscavia" for `[[thing:t|Moscavia]]` while t is named "Tsardom of Moscavia".
  - `test_rename_updates_full_name_links_only`: after t is renamed to "Moscavian Empire", `[[thing:t|Tsardom of Moscavia]]` renders "Moscavian Empire" and `[[thing:t|Moscavia]]` renders "Moscavia".
  - `test_deleted_target_renders_shown_text`.
  - `test_segments_split_links`.
  - `test_aka_shape_validated`: two `everyday` entries are rejected, an `everyday` entry tagged `proper` is rejected, and an unknown tag is rejected.
  - `test_stub_marker_and_kind_change`: a lore stub becomes a place, keeping its facts. Changing the kind of a non-stub raises. Undo restores the lore kind.
- [ ] **Step 2: Run** `pytest tests/world/test_refs.py tests/world/test_kinds.py tests/world/test_stubs.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** The store's `_check_refs` and the `fact_refs` writer accept the new form unchanged, because they work from `parse_refs`.
- [ ] **Step 4: Run** `pytest tests/world -q` (strict mypy included). Expected: PASS.
- [ ] **Step 5: Commit**: `feat(world): references keep their written text; other names and stubs on every kind`.

### Task 2: The shared name index

**Files:**
- Create: `src/talemate/world/names.py`.
- Modify: `src/talemate/worldplay/setup.py` (`match_names` delegates to the index; `NameMatch` and `NameCandidate` move to `names.py` and are re-exported).
- Test: `tests/world/test_names.py` (new); the existing `tests/worldplay/test_setup.py` match tests keep passing.

**Interfaces:**
- Produces:
  - `class NameCandidate(BaseModel)`: `id`, `name`, `kind`, `stub: bool`, `via: Literal["name", "aka", "first_name", "partial"]`;
  - `class NameMatch(BaseModel)`: `start`, `end`, `text`, `candidates: list[NameCandidate]`, `suggested: bool` (true when the only candidates are `partial`);
  - `class Unknown(BaseModel)`: `start`, `end`, `text`;
  - `def find_names(view: WorldView, text: str) -> list[NameMatch]`. It matches main names, every `aka` name and characters' first names (as today), longest first, with a trailing `'s` allowed. It skips ignored stubs. A partial match, meaning one capitalised word of a multi-word main name of 5 or more letters ("Moscavia" in "Tsardom of Moscavia"), gives a `suggested` match with a `partial` candidate;
  - `def unknown_proper_phrases(view: WorldView, text: str) -> list[Unknown]`: runs of capitalised words not covered by a match, ignoring a sentence-initial single word, words from the leading-word list (`setup._ARTICLES`, moved here), and lone pronouns;
  - `def everyday_name(state: ThingState) -> str | None`.

- [ ] **Step 1: Write the failing tests**
  - `test_aka_names_match`: "Moscavian Owls" matches the Owl-folk species through `aka`.
  - `test_partial_is_only_suggested`.
  - `test_common_word_name_needs_a_capital`: a stub named "Hope" matches "Hope" and not "I hope".
  - `test_ignored_stub_not_matched`.
  - `test_unknown_phrases`: "his mother Yelena and the Night of Feathers" gives "Yelena" and "Night of Feathers". "The postmaster said" gives nothing.
  - `test_everyday_name`.
- [ ] **Step 2: Run** `pytest tests/world/test_names.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement**, then switch `setup.match_names` to `find_names`.
- [ ] **Step 4: Run** `pytest tests/world tests/worldplay -q`. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(world): one name index for prompts and facts, with other names and stubs`.

### Task 3: Probes (Skyfall; the owner approved)

**Files:**
- Create:
  - `scripts/dev/probe_connections.py`;
  - `docs/superpowers/probes/<run-date>-connections.md`;
  - `docs/superpowers/probes/raw/<run-date>-connections.json`.

**Interfaces:**
- Produces: the wording that Tasks 5 and 7 copy into templates, recorded in the findings doc's "Recommended prompt text".

- [ ] **Step 1: Write the probe script.** Follow `scripts/dev/probe_heritage_play.py`: use the real KoboldCpp client and templates where they exist, or else plain chat calls mirroring `world/create-thing.jinja2`. Set up a world with Owl-folk (an origin fact naming the "Tsardom of Moscavia" in 994), the Snowy race, and Humans.
  - **(1) Names and kinds:** creation replies that also list `"names": [{"name", "kind", "aka": [...]}]` for the proper names their facts invent, and `"aka"` for the thing itself. Run 3 times each, for a country, a character and a species. Measure:
    - recall and precision of proper names, against a hand-made list per run;
    - kind accuracy;
    - generic nouns wrongly listed.

    Compare with `unknown_proper_phrases` on the same facts, and with the two combined.
  - **(2) Context from mentions:** expand the Tsardom stub 3 times each with (a) the mentioning fact only, (b) plus the owl-folk's key facts (physical, instinct and origin, capped at 8), and (c) plus all their facts. Judge each against the owner's measure: is it written for its owl-folk inhabitants?
  - **(3) Duplicates:** a place prompt "a river town where Moscavian Owls trade with barge crews", with and without Owl-folk matched into the context. Count replies that invent a new species.
  - **(4) Everyday names:** do suggested `aka` come back sensibly tagged? Then run 3 narrator turns with "Tsardom of Moscavia (usually called Moscavia)" and count full-name uses against everyday-name uses.
- [ ] **Step 2: Run it,** one call at a time.
- [ ] **Step 3: Write the findings** with a recommendation per probe: the reply shape for names, the mention-context rule and cap, whether matched context stops duplicates, and the everyday-name wording.
- [ ] **Step 4: Commit**: `docs(probe): names, mention context, duplicates and everyday names`.

### Task 4: Linking text and making stubs

**Files:**
- Create: `src/talemate/worldplay/links.py`, `src/talemate/worldplay/mentions.py`.
- Test: `tests/worldplay/test_links.py`, `tests/worldplay/test_mentions.py` (new).

**Interfaces:**
- Consumes: Task 1 (`ref`, `segments`, `aka`, `stub`) and Task 2 (`find_names`, `unknown_proper_phrases`).
- Produces:
  - `class NewName(BaseModel)`: `name: str`, `kind: str`, `aka: list[dict] = []`;
  - `def link_text(view: WorldView, text: str, *, picks: dict[str, str] | None = None, new_names: dict[str, str] | None = None) -> str`. Each match, pick or new-name mapping becomes `ref(id, written)`, where a pick maps written text to a thing id and a new name maps written text to a stub id. Suggested (partial) matches are left alone. Text already inside a reference isn't touched;
  - `def make_stubs(rev: Revision, view: WorldView, names: list[NewName]) -> dict[str, str]`: written name to stub id. It reuses an existing entry or stub with the same normalised main name or `aka` name (Review Focus 4). Otherwise it creates a thing of `kind` with `name`, `aka` and `stub={"ignored": false}`. An unknown kind falls back to `lore`;
  - `class Mention(BaseModel)`: `owner_id`, `owner_name`, `owner_kind`, `fact_id`, `text` (rendered);
  - `def mentions(view: WorldView, thing_id: str) -> list[Mention]` (from `view.referencing(any_date=True)`);
  - `def mention_context(view: WorldView, thing_id: str) -> list[tuple[str, list[str]]]`: one `(heading, facts)` group per mentioning entry, following Task 3's rule and cap;
  - `def suggested_prompt(view: WorldView, stub_id: str) -> str`: `"<name>: " + the mentioning facts, joined and rendered`, cut at 400 characters on a sentence end.

- [ ] **Step 1: Write the failing tests**
  - `test_link_text_keeps_words`: "Moscavia's border" becomes `[[thing:t|Moscavia's]] border`; rendering gives back the same string.
  - `test_link_text_respects_picks_and_skips_suggested`.
  - `test_make_stubs_reuses_existing_name`.
  - `test_make_stubs_unknown_kind_is_lore`.
  - `test_mentions_and_context_capped`.
  - `test_suggested_prompt_from_mentions`.
- [ ] **Step 2: Run** `pytest tests/worldplay/test_links.py tests/worldplay/test_mentions.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/worldplay -q`. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(worldplay): link names in text, make stubs, and gather mention context`.

### Task 5: Create from a prompt: names, stubs, expansion and context

**Files:**
- Modify:
  - `src/talemate/worldplay/create.py`;
  - `src/talemate/prompts/templates/world/create-thing.jinja2`;
  - `src/talemate/prompts/templates/world/create-mix.jinja2`.
- Test: `tests/worldplay/test_create.py`.

**Interfaces:**
- Consumes: Tasks 3 and 4.
- Produces:
  - `CREATE_KINDS` adds `"event"` and `"item"`;
  - `CreatePreview` gains:
    - `aka: list[dict]`;
    - `new_names: list[NewName]`, parsed from the reply per Task 3, then merged with `unknown_proper_phrases` on the facts as Task 3 recommends. Names already in the world are dropped;
    - `stub_id: str | None`;
    - `matching_stub_id: str | None`;
    - `context: list[tuple[str, list[str]]]`, the context shown to the owner;
  - `preview_thing(world, kind, prompt, fields, client, *, stub_id: str | None = None, picks: dict[str, str] | None = None)`:
    - **with a `stub_id`:** its name and kind are used, and `mention_context` is added;
    - **with `picks`:** the prompt's matched entries' facts are added under "Named in this prompt";
    - `matching_stub_id` is set when the preview's name matches a live stub of the same kind and no `stub_id` was given;
  - `accept_preview(world, preview, *, into_stub: str | None = None) -> str`, in one revision:
    - **making stubs:** it makes stubs for `new_names` and links every fact's text with `link_text`;
    - **filling a stub** (`stub_id` or `into_stub`): it writes into that thing. It removes its `stub` field, sets its fields and `aka`, and adds the facts, keeping the id. A deleted stub is refused with `ValueError`;
    - **a new thing:** otherwise it creates one;
  - when the context holds things with an everyday name, the template states "(usually called X)" and asks for that name in prose, worded as Task 3 recommends.

- [ ] **Step 1: Write the failing tests**, using MockClient replies built from Task 3's raw output:
  - `test_accept_makes_stubs_and_links_facts`;
  - `test_expand_stub_uses_mentions_as_context`;
  - `test_expand_ignored_stub_keeps_id_and_revives`;
  - `test_expand_deleted_stub_refused`;
  - `test_preview_offers_matching_stub`;
  - `test_picks_add_named_context`;
  - `test_event_and_item_creatable`.
- [ ] **Step 2: Run** `pytest tests/worldplay/test_create.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/worldplay -q`, then the full plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit**: `feat(worldplay): creation finds names, makes stubs and expands them with mention context`.

### Task 6: Router: links, stubs, other names and hand-written facts

**Files:**
- Modify: `src/talemate/server/worlds.py`.
- Test: `tests/server/test_worlds_plugin.py`.

**Interfaces:**
- Consumes: Tasks 1, 2, 4 and 5.
- Produces:
  - **`_thing_payload` gains:**
    - `segments` on each own and inherited fact, from `view.segments`;
    - `prose_segments` per section: `find_names` matches over the cached prose, turned into segments with `ref` set and never creating anything;
    - `aka`;
    - `stub` (`null` or `{"ignored": bool}`);
    - `mentions` (Task 4 `mentions`);
    - `named_stubs: [{id, name, kind}]`, the stubs this entry's facts link to;
  - **`match_names` reply** gains `unknown` (Task 2), and each candidate carries `stub` and `via`;
  - **`add_fact` / `correct_fact`** accept `picks: dict[str, str] = {}`. Before writing, the text is linked with `link_text` (existing names and stubs, plus the picks). Unknown phrases are not turned into stubs;
  - **new actions:**
    - `make_stub {thing_id, fact_id, text, kind}` makes a stub named `text` and links that phrase in that fact, then replies like `correct_fact`;
    - `list_stubs {include_ignored: bool}` replies `{"stubs": [{id, name, kind, first_mentioned: {thing_id, name}, mentions: int, ignored}]}`;
    - `ignore_stub {id, ignored}`;
    - `change_stub_kind {id, kind}`;
    - `stub_suggestion {id}` replies `{prompt, context}`;
  - **`preview_thing`** accepts `stub_id` and `picks`; **`accept_preview`** accepts `into_stub`;
  - **`list_things`** includes stubs with `stub` set and leaves out ignored stubs.

- [ ] **Step 1: Write the failing tests**
  - `test_payload_segments_and_stub_fields`;
  - `test_add_fact_links_known_names_and_picks`;
  - `test_make_stub_action`;
  - `test_list_stubs_counts_and_ignored`;
  - `test_ignore_and_change_kind`;
  - `test_stub_suggestion`;
  - `test_preview_with_stub_id_and_accept_into_stub`.
- [ ] **Step 2: Run** `pytest tests/server/test_worlds_plugin.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit**: `feat(worlds): links, stubs, other names and fact linking over the router`.

### Task 7: Scene setup fills stubs; everyday names in play

**Files:**
- Modify:
  - `src/talemate/worldplay/setup.py`;
  - `src/talemate/worldplay/context.py`;
  - `src/talemate/prompts/templates/world/scene-context.jinja2`;
  - `src/talemate/server/worlds.py` (the setup payload).
- Test: `tests/worldplay/test_setup.py`, `tests/worldplay/test_context.py`.

**Interfaces:**
- Produces:
  - `SceneSetup.stub_previews: list[CreatePreview]`. `plan_scene` adds a preview, with Task 5's `preview_thing(stub_id=...)`, for each stub the prompt picks or the setup pulls in. That covers a stub resolved as a character, the place or pulled-in lore, ignored stubs included. Each stub is previewed at most once;
  - `start_scene` accepts each stub preview first (Task 5 `accept_preview`), so the scene uses the full entries. Planning writes nothing; cancelling leaves the stubs as they were;
  - `world_context_block` names things with an everyday name as "<main> (usually called <everyday>)", with Task 3's instruction line;
  - the setup payload carries `stub_previews`, so the setup cards can show them.

- [ ] **Step 1: Write the failing tests**
  - `test_plan_scene_previews_named_stub`;
  - `test_start_scene_fills_stub_and_keeps_id`;
  - `test_cancelled_setup_leaves_stub`;
  - `test_ignored_stub_revived_by_setup`;
  - `test_context_block_uses_everyday_name`.
- [ ] **Step 2: Run** `pytest tests/worldplay/test_setup.py tests/worldplay/test_context.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit**: `feat(worldplay): scene setup fills the stubs it uses; everyday names in play`.

### Task 8: Frontend: linked text, stubs and other names

**Files:**
- Create in `talemate_frontend/src/components/worlds/`:
  - `LinkedText.vue` (renders `segments`, with links and stub styles and the stub hover card);
  - `StubsTab.vue`;
  - `ThingAka.vue`;
  - `NamedStubs.vue`.
- Modify:
  - `ThingPage.vue`, `WorldTab.vue`, `worldKinds.js` (Event and Item kinds; a Stubs tab);
  - `stores/worlds.js`;
  - `SceneSetupCards.vue` (stub previews).
- Test: `tests/e2e/worlds/test_connections_pages.py` (new), `talemate_frontend/checks/worlds.check.mjs`.

**Interfaces:**
- Consumes: Task 6's payload keys and actions, and Task 7's `stub_previews`.
- Produces, following the approved mockup (spec, "The screens"):
  - **Link styles:** a solid link (role `link`) for an entry, and a dashed underline in a second role (`warning` unless a better one fits) for a stub;
  - **The stub hover card:** "not made yet", the kind (a select that sends `change_stub_kind`), the mention count, Expand and Ignore;
  - **LinkedText** in facts, inherited facts, prose and create previews;
  - **The Stubs tab:** name, kind, first mentioned (linked), mentions, Expand and Ignore, with a "show ignored" toggle;
  - **Kind lists** show stubs dimmed under a "Stubs" heading;
  - **A stub's own page** shows its mentions, kind, Expand and Ignore;
  - **ThingAka:** add, edit, tag (proper or common), the everyday radio and remove, through `set_field "aka"`;
  - **NamedStubs** on a thing page;
  - **The setup cards** show each stub preview, marked "will be filled in";
  - **Culture stubs** show Expand disabled, with the note "Cultures arrive in the next slice";
  - test ids: `linked-ref`, `linked-stub`, `stub-card`, `stubs-tab`, `stub-row`, `aka-editor`, `named-stubs`.

- [ ] **Step 1: Write the failing browser test** `test_stub_links_tab_and_aka`, seeded with the Owl-folk origin fact linking a "Tsardom of Moscavia" stub:
  - the fact shows the stub style;
  - the hover card offers Expand and Ignore;
  - Ignore hides it from the fact and the tab, and "show ignored" lists it;
  - adding the other name "Moscavian Owls" saves and shows.
- [ ] **Step 2: Run it.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the `tests/ai` grep, then the full browser suite with `-n 4`. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(worlds): linked text, stubs tab, other names`.

### Task 9: Frontend: highlighted prompts, expanding stubs and Add reference

**Files:**
- Create in `talemate_frontend/src/components/worlds/`:
  - `NameHighlightInput.vue` (the highlight layer, picks and "treat as new" from `NewSceneDialog.vue`, factored out);
  - `ReferenceMenu.vue` (the right-click menu and its in-place search).
- Modify: `NewSceneDialog.vue` (uses `NameHighlightInput`), `CreateBox.vue`, `ThingFactForm.vue`, `stores/worlds.js`, `nameHighlights.js`.
- Test: `tests/e2e/worlds/test_connections_create.py` (new); the existing `tests/e2e/worlds/test_new_scene.py` keeps passing.

**Interfaces:**
- Consumes: `match_names` (with `unknown`), `stub_suggestion`, `preview_thing {stub_id, picks}`, `accept_preview {into_stub}`, `make_stub`, and `add_fact` / `correct_fact` with `picks`.
- Produces:
  - **Highlighted prompts:** `NameHighlightInput` in the create box prompt and the fact form. Suggested (partial) matches show a dotted underline with "did you mean …". Unknown phrases in the fact form offer "make a stub" on hover;
  - **Expanding a stub** opens the create box for its kind with `stub_id`. The prompt is prefilled from `stub_suggestion`, and a collapsible "Context the AI gets" panel shows the preview's `context`;
  - **Filling a stub instead:** a preview with `matching_stub_id` shows "Fill the stub *X* instead" and accepts with `into_stub`;
  - **Re-picking:** the owner's re-pick of a match adds the written name to that thing's `aka` as `common`, with no `everyday`;
  - **Add reference:** right-clicking in `NameHighlightInput` opens `ReferenceMenu`, which keeps cut, copy and paste and adds "Add reference…". The search covers entries and stubs, and the chosen name is inserted at the cursor with a pick recorded for it.
  - **Re-pointing a link in a fact:** a link's hover card in `LinkedText` offers "Re-point…". It opens the same search and sends `correct_fact` with the reference's id swapped and its shown text kept (the spec's "two of the same name").

- [ ] **Step 1: Write the failing browser tests**, with `TALEMATE_TEST_FIXED_PREVIEW` fixtures:
  - `test_expand_stub_prefills_and_fills_it`: the stub's id is kept and the fact now shows a link;
  - `test_prompt_names_highlight_and_repick_adds_aka`;
  - `test_fill_stub_instead`;
  - `test_add_reference_menu_inserts_pick`;
  - `test_repoint_link_keeps_words`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full browser suite with `-n 4`. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(worlds): highlighted prompts, expanding stubs and Add reference`.

### Task 10: End to end, and the owner's measure on Skyfall

**Files:**
- Create:
  - `tests/worldplay/test_connections_end_to_end.py`;
  - `scripts/dev/probe_connections_flow.py`;
  - `docs/superpowers/probes/<run-date>-connections-flow.md`, plus its raw JSON.

- [ ] **Step 1: Write the end-to-end test** with MockClient, through the real router:
  1. create Owl-folk, whose origin reply names the Tsardom, so a stub is made;
  2. expand the stub (the context includes the origin fact; the id is kept), and its reply names Kalmara, so another stub is made;
  3. a place prompt saying "Moscavian Owls" with an `aka` match links to Owl-folk;
  4. a scene prompt naming Kalmara gets a stub preview, which is filled at start.

  Assert that no model call is made on an ordinary turn.
- [ ] **Step 2: Run it,** then the full plain suite. Expected: 0 failed.
- [ ] **Step 3: Run the owner's session on Skyfall** through the same code path: owl-folk, then the Tsardom from its stub, then two stubs the Tsardom names. Judge the result against the owner's measure, and record the stubs made, false stubs and duplicates. Fix prompt assembly in `worldplay`, with a test, if needed.
- [ ] **Step 4: Commit**: `test(worldplay): connections end to end; docs(probe): connections in a real session`.

### Task 11: The owner's acceptance run (owner-gated)

Start the isolated app with `--ai` on a fresh root and give the owner the URL. The owner runs the spec's session: the owl species with its origin, humans, then places by following stubs. Fix hiccups with root-caused, tested and reviewed fixes. Record the results in `docs/superpowers/probes/<run-date>-connections-acceptance.md`.
