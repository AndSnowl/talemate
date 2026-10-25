# Filing, Tags and Draft Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace sphere drawers, part-of, ties, the place parent and branches with one connection, filing, plus one tag per entry. Each page groups what is filed in it by tag. The preview becomes the entry page, in draft.

**Architecture:**
- **World store:** a pure `world/filing.py` holds the model (`Filing`, `connected`, `mentioned_in`, tags). `world/` readers (nearness, timelines, held-by, summaries) move onto it, and the old fields and the `sphere` kind are removed once every consumer is ported.
- **Writing:** one writer (`create-thing.jinja2` plus a prompt hint) returns the tag, "In", "File into this" and tagged names.
- **The router** serves one page payload for both draft and accepted entries.
- **The frontend** renders that one page with two panes, versions, Discard and the shared menus.

**Tech Stack:** Python 3.11, SQLite (the world store), pydantic 2, Jinja2 through `Prompt.request`, Vue 3 + Vuetify, Pinia, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-10-23-fantasymate-filing-design.md` (c8db0d74). The mockups are `.superpowers/sdd/mockups/redesign-v2.html` and `redesign-v3.html` (v1 is superseded). The spec builds on the Curation spec and on the rulings Q1–Q2 and C1–C35 in `.superpowers/sdd/2026-10-22-fantasymate-curation/progress.md`.

## Global Constraints

- **Branch:** work on `feature/spheres` in `.worktrees/spheres`, starting from HEAD c8db0d74.
- **Plain suite:** the baseline is 7517 passed and 6 skipped. It must end every task at **0 failed**. Tests for removed features are deleted or rewritten in the task that removes them, never skipped.
- **Guix:** run everything through `guix shell -m manifest.scm -- …` with `uv run --no-sync`.
- **Browser tests:**
  - run `pytest tests/e2e -m e2e -n 4` once at the end of each UI task, never with more than 4 workers;
  - while iterating, run `tests/e2e/worlds` only;
  - check for orphaned pytest apps first;
  - grep `tests/ai` for every changed UI id or prompt wording.
- **Skyfall probes and runs** need the owner's go-ahead, so ask before Task 1 and Task 12.
  - Model calls run one at a time against `http://192.168.0.5:5001`.
  - Plain tests use `MockClient` only.
  - Commit the labels before any model call.
  - Raw output goes under `docs/superpowers/probes/raw/`.
- **`src/talemate/world/`** stays strict-mypy clean and imports nothing from the rest of talemate.
- **World AI calls** go through `worldplay.ai.world_ai_call()` and are parsed with `create.json_objects`. No raw `[[thing:…]]` text may reach a prompt or a page.
- **Revisions:** every multi-write action is one revision and undoes exactly.
  - Fact moves copy with a new id and remove the original (R1), going through `repoint.copy_facts`.
  - The client's rows are recomputed on the server.
- **The owner's tick:**
  - suggested "In" filings arrive **ticked**;
  - "File into this", "Could move here" and repeats ≥ `repeat_untick_threshold` arrive **unticked**;
  - nothing is moved, filed or written without passing through the draft.
- **Fresh worlds only:** no migration.
- **The tag** is one per entry, on every kind, stored as the field `tag` (text). Tags are lowercase and singular ("river", "custom"). The group heading on a page is the tag, capitalised and pluralised by `tag_heading(tag)`.
- **A filing** is `{"target": <32-hex>, "role": str | None, "since": WorldDate | None, "until": WorldDate | None, "within": <32-hex> | None, "exceptions": [fact_id…]}`. A thing's filings are the field `filings` (json list), dated and versioned like any field.
- **Prompt hints** are the files `src/talemate/prompts/templates/world/hints/{religion,nation,order,culture,field}.txt`.
- **Pass bars** stay as in Curation: at least 80% right and at most 5% false. A failure falls back to "shown, unticked" (suggestions) or off (synopsis).

## Review Focus

1. **A filing cycle** (A in B, B in A, or a place in its own district): it is refused up front with a clear message, nothing is written, and Connected, nearness and timelines never loop. This belongs to Task 2 (`test_filing_cycle_refused`) and Task 3 (`test_timeline_and_near_survive_a_cycle`).
2. **An entry whose tag is removed or renamed while it is filed in ten places:** every page regroups at once, and no group is left empty or stale. This belongs to Task 6 (`test_rename_tag_regroups_everywhere`).
3. **Discarding a draft after Regenerate:** no stub, filing or fact is written, and the earlier versions are gone. This belongs to Task 6 (`test_discard_writes_nothing`) and Task 10 (`test_draft_versions_and_discard`).
4. **A filing whose target is deleted:** it is hidden but kept, so undoing the delete restores it (as P12). The person's exceptions are kept too. This belongs to Task 2 (`test_filing_to_deleted_target_hidden_then_back`).
5. **A big Connected list (50 entries, one tag):** it folds to a filter, then the synopsis, then the first rows, then "show all", and stays readable. This belongs to Task 9 (`test_big_group_folds`).

---

### Task 1: Probes on Skyfall (owner-gated)

**Files:**
- Create: `scripts/dev/probe_filing.py`
- Create: `docs/superpowers/probes/<run-date>-filing.md`
- Create: `docs/superpowers/probes/raw/<run-date>-filing.json` and `…-filing-labels.json`

**Interfaces:**
- Consumes:
  - the copy of the owner's acceptance world at `/tmp/fantasymate-acceptance-curation`; work on a copy;
  - the curation probe harness (`scripts/dev/probe_curation.py`).
- Produces the findings doc. For each probe it gives the exact wording as Jinja blocks with named variables, the reply shape, the scores against the bar, and PASS or FALLBACK. Tasks 4, 5 and 8 copy this wording verbatim.
  1. **The create reply:**
     - Shape: `{"tag": "…", "in": [{"entry": "<name>", "role": "…"|null}], "file_into": [{"entry": "<name>", "role": "…"|null}], "names": [{"name","kind","tag","in": "<name>"|null}]}`, plus facts and elsewhere as today, minus `move_in`.
     - Score:
       - tag reuse against the tags in use;
       - "In" accuracy: the river in the Tsardom and Velikoye; the Academy in Velikoye and Runic Magic; Plumage Signaling in the Owl-folk and the Night Court;
       - the thin-stub rate under the rule "only named things become entries".
  2. **"File into":** the military made after the White Talon and the Frosted Wing. It must offer them and offer nothing false.
  3. **Group synopsis:** a nation's rulers and officials, and a city's institutions. Score accuracy, and count anything invented.
  4. **Prompt hints:** does a nation or religion hint draw out rulers, doctrine and rites without drawers? Under the religion hint, are belief-category facts written as beliefs?
  5. **The scene world block** built from filings (spec "Scene context"): is it used without flooding?
  6. **Group "+ Add":** 1–3 new entries from a prompt, tagged and filed in the page's entry.
- [ ] **Step 1:** Ask the owner for the go-ahead.
- [ ] **Step 2:** Commit the hand labels.
- [ ] **Step 3:** Run each probe twice at the app's temperatures, writing the JSON after every call.
- [ ] **Step 4:** Write the findings doc with PASS or FALLBACK per probe, plus the hint texts.
- [ ] **Step 5:** Commit: `docs(probe): filing, tags and hints on Skyfall`.

### Task 2: Tags and filings in the world store

**Files:**
- Create: `src/talemate/world/filing.py`
- Modify: `src/talemate/world/kinds.py` (add `tag` and `filings` to every kind; validate them)
- Modify: `src/talemate/world/view.py`, if a helper is needed
- Test: `tests/world/test_filing.py`

**Interfaces:**
- Produces, all in `world/filing.py`:
  - `class Filing(BaseModel)`:
    - `target: str`
    - `role: str | None`
    - `since: WorldDate | None`
    - `until: WorldDate | None`
    - `within: str | None`
    - `exceptions: list[str]`
  - `filings_of(view, thing_id, *, live=True) -> list[Filing]`
    - With `live`, the result hides filings whose target is deleted or whose dates don't cover the view's date.
  - `filed_in(view, target_id, *, things=None) -> list[tuple[ThingState, Filing]]`
    - Direct filings only.
    - A filing with `within` also lists the person under the `within` entry.
  - `class Group(BaseModel)`:
    - `tag: str | None`
    - `heading: str`
    - `rows: list[tuple[str, Filing]]`
  - `connected(view, target_id, *, things=None) -> list[Group]`
    - Groups by each entry's `tag`; an untagged entry goes in the group "Other".
    - Groups are ordered by size descending, then heading.
    - Rows are ordered by role, then since, then name.
  - `mentioned_in(view, thing_id) -> list[str]`: things whose live facts reference `thing_id` and that are not filed in it.
  - `tags_in_use(view) -> list[tuple[str, int]]`
  - `tag_heading(tag: str) -> str`: "river" becomes "Rivers", "custom" becomes "Customs", "capital" becomes "Capitals".
  - `sits_in(view, start_id, thing_id) -> bool`: follows filings upward, cycle-safe.
- Validation in `kinds.py`:
  - `within` must sit in `target` (checked when written, through a hook in the store, or a check in `filing.py` that writers call).
  - A filing may not target the thing itself.
  - `filings` must not contain the same target twice.
- [ ] **Step 1: Write the failing tests:**
  - `test_filings_round_trip_dated`
  - `test_connected_groups_by_tag`
  - `test_untagged_goes_to_other`
  - `test_within_lists_person_under_both`
  - `test_filing_cycle_refused`
  - `test_filing_to_deleted_target_hidden_then_back`
  - `test_mentioned_in_excludes_filed`
  - `test_tags_in_use_counts`
  - `test_tag_heading_plurals`
- [ ] **Step 2: Run them:** `pytest tests/world/test_filing.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** This is additive; the old fields stay for now.
- [ ] **Step 4: Run** `pytest tests/world -q`, mypy on `src/talemate/world`, and the plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit:** `feat(world): tags and filings`.

### Task 3: World readers move onto filings

**Files:**
- Modify:
  - `src/talemate/world/nearness.py`: one filing weight replaces the `part_of`, parent and tie weights, starting at 1.0;
  - `src/talemate/world/timelines.py`: gathers from `filed_in`, recursively, up to `timeline_reach`;
  - `src/talemate/world/sameness.py`, `curation.py` and `kinds.py`: `kinds_can_be_one` drops the sphere rule;
  - held-by: move `held_by`, `with_held_by`, `acts_in_world`, `summary` and `is_summary_fact` out of `world/spheres.py` into a new `src/talemate/world/entries.py`.
- Test: `tests/world/test_nearness.py`, `tests/world/test_timelines.py`, `tests/world/test_entries.py`

**Interfaces:**
- Consumes: Task 2.
- Produces:
  - `world/entries.py`, with the same names and behaviour as before;
  - `held_by(view, fact, owner)`, now explicit-only, plus the belief rule: a fact in category `belief` is held by its owner;
  - `acts_in_world(state)`: unchanged.
- Nearness and timelines read filings, and nothing in `world/` reads `part_of`, `ties` or `parent` any more. `world/spheres.py` keeps only what Task 7 deletes.
- [ ] **Step 1: Write the failing tests:**
  - `test_near_follows_filings_both_ways`
  - `test_timeline_gathers_from_filed_entries`
  - `test_timeline_and_near_survive_a_cycle`
  - `test_belief_fact_is_held_by_owner`
  - `test_held_by_explicit_still_wins`

  Then rewrite the old nearness and timeline tests that relied on `part_of` or ties, so they use filings.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/world -q`, mypy, and the plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit:** `feat(world): nearness, timelines and held-by read filings`.

### Task 4: One writer: tag, In, File into this, tagged names, hints

**Files:**
- Modify:
  - `src/talemate/worldplay/create.py`: `CreatePreview`, `preview_thing` and `accept_preview`;
  - `src/talemate/prompts/templates/world/create-thing.jinja2`, using Task 1's wording.
- Create: `src/talemate/prompts/templates/world/hints/*.txt` (Task 1's texts)
- Test: `tests/worldplay/test_filing_preview.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces:
  - **`CreatePreview` gains:**
    - `tag: str | None`
    - `hint: str | None`
    - `filings: list[{target_id, target_name, role, ticked=True}]`, the "In" rows
    - `file_into: list[{thing_id, name, role, ticked=False}]`
    - `versions: list[CreatePreview]`, filled by the router (Task 6)
  - **`NewName` gains** `tag: str | None` and `filing: {target_id|name, role, ticked=True} | None`.
  - **`CreatePreview` drops** `part_of`, `ties`, `move_in`, `refile` and `same_as`-for-sphere.
  - **"Could move here"** is `move_here: list[{fact_id, from_id, text, ticked=False}]`. It holds live facts on `near()` entries whose text names the new entry (through `names.find_names` on the preview's name and aka), excluding facts already repeated by own facts. No model call is involved.
  - **`preview_thing(world, kind, prompt, fields, client, *, hint=None, …)`:** the `hint` text goes into the prompt. With the religion, culture or order hints, the categories include `belief`.
  - **On accept, in one revision,** it writes:
    - the tag;
    - the ticked filings;
    - the ticked "File into this" rows, as filings on those things with `target = new id`;
    - the ticked `move_here` rows, through `copy_facts`;
    - names as stubs with their tag and ticked filing.
  - **The rule "only named things become entries"** is in the template, as Task 1 worded it.
  - **Character ties in the create reply become filings.** The ties block is replaced by the "In" rows; their exceptions stay as Task 6 of Spheres had them, now attached to the filing.
- [ ] **Step 1: Write the failing tests** (MockClient replies from Task 1's raw output):
  - `test_reply_tag_and_in_parsed`
  - `test_accept_writes_tag_filings_file_into`
  - `test_names_get_tag_and_filing`
  - `test_move_here_is_code_only`
  - `test_hint_adds_belief_category_and_marks_held`
  - `test_character_in_rows_carry_exceptions`
  - `test_undo_redo_accept_with_filings`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/worldplay -q` and the plain suite. Expected: 0 failed. Grep `tests/ai` for the template wording.
- [ ] **Step 5: Commit:** `feat(worldplay): one writer that tags and files`.

### Task 5: Play, setup, Re-point and merge on filings

**Files:**
- Modify:
  - `src/talemate/worldplay/context.py` and `src/talemate/prompts/templates/world/scene-context.jinja2` (Task 1's probe 5 wording);
  - `worldplay/setup.py`, `worldplay/characters.py` (tie lines become filing lines), `worldplay/repoint.py`, `worldplay/merge.py`, `worldplay/references.py` and `worldplay/mentions.py`.
- Test: `tests/worldplay/test_context.py`, `test_setup.py`, `test_characters.py`, `test_merge.py`, `test_repoint.py`

**Interfaces:**
- Consumes: Tasks 2–4.
- Produces:
  - **Touched entries for a scene:**
    - what the scene's place is filed in, upward to the reach;
    - what each present character is filed in;
    - what the prompt names.

    Each touched entry gets its summary, up to 5 own facts (most-linked first), and its latest 3 timeline lines, at most 8 lines. Held facts are worded as held. The agent flag no longer changes context.
  - **A character sheet line per filing with a role,** for example "Practitioner of the White Dawn (since 1010), but: …", keeping the Spheres tie-line format and its C6, C12 and C18 rules.
  - **Re-point and merge** rewrite filings (target and within) instead of `part_of`, ties and parent. Re-point's fixes are part of this task:
    - Re-point now adds the stub's name and the link words as aka on the target. The current bug is that it doesn't.
    - A new parameter, `repoint_stub(world, stub_id, target_id, *, use_name: str | None = None)`, is the "hard re-point": the links' shown words become `use_name`, one of the target's names.
  - **`change_stub_kind` works for every kind;** the sphere error goes with the kind.
  - **`event.place` and `item.owner`** become filings with the roles "took place in" and "owned by".
- [ ] **Step 1: Write the failing tests:**
  - `test_scene_touched_by_filings`
  - `test_scene_block_wording`
  - `test_sheet_filing_lines`
  - `test_repoint_adds_other_names`
  - `test_hard_repoint_uses_chosen_name`
  - `test_merge_rewrites_filings`
  - `test_change_stub_kind_any_kind`

  Then rewrite the existing tests that used ties, `part_of` or parent, so they use filings.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/worldplay tests/world -q` and the plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit:** `feat(worldplay): scenes, sheets, Re-point and merge on filings`.

### Task 6: Router: one page payload, drafts, filings and tags

**Files:**
- Modify: `src/talemate/server/worlds.py`
- Test: `tests/server/test_worlds_plugin.py`

**Interfaces:**
- Consumes: Tasks 2–5.
- Produces:
  - **The thing payload** (the same shape for drafts):
    - `tag`
    - `hint`
    - `in: [{target_id, target_name, role, since, until, within_id, within_name, exceptions: [{fact_id, segments}]}]`
    - `connected: [{tag, heading, synopsis: str|null, rows: [{id, name, stub, line_segments, role, since, until}]}]`
    - `mentioned_in: [{id, name}]`
    - plus facts and `entry_timeline` as now.
    - The sphere, ties and `part_of` payload keys are removed.
  - **Drafts:**
    - `preview_thing` replies with the draft as a page payload plus `preview` (the data to accept) and `version: n`.
    - The router keeps up to 5 versions per draft key, in memory per session. `use_version {n}` restores one.
    - `discard_preview` drops every version and writes nothing.
  - **New actions:**
    - `add_filing {thing_id, target_id|new_name, role, since, until, within}`, `edit_filing {…}`, `remove_filing {thing_id, target_id}`
    - `set_tag {thing_id, tag}`, `rename_tag {old, new}`, `merge_tag {from, into}`
    - `group_synopsis {thing_id, tag}`, built in Task 8
    - `group_add {thing_id, tag|null, prompt}`, which returns draft rows (Task 8)
    - `add_facts {thing_id, prompt}`, which returns a small fact draft
    - `add_event {thing_id, prompt, year}`
    - `make_stub_from_text {fact_id, start, end, kind, tag}` and `link_text {fact_id, start, end, target_id}`
    - `repoint_stub` gains `use_name`
  - **Removed actions:**
    - `set_part_of`, `set_ties`, `set_drawers`, `add_statement`, `add_outer_body`
    - `fill_drawer`/`accept_fill` and `preview_sphere`/`accept_sphere`/`preview_branch`
    - `end_item`, which becomes ending a filing through `edit_filing`'s `until`
  - **Fixed-reply hooks** (`TALEMATE_TEST_FIXED_PREVIEW`) carry tag, in, file_into and names with tag and filing.
- [ ] **Step 1: Write the failing tests:**
  - one per new action;
  - `test_payload_in_connected_mentioned`
  - `test_discard_writes_nothing`
  - `test_versions_restore`
  - `test_rename_tag_regroups_everywhere`
  - `test_forged_filing_rows_refused`

  Delete the tests for the removed actions.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit:** `feat(worlds): filing, tag and draft actions; one page payload`.

### Task 7: Remove the old structure

**Files:**
- Delete:
  - `src/talemate/world/spheres.py` (whatever Task 3 didn't move);
  - `src/talemate/worldplay/spheres.py` and `worldplay/bodies.py`;
  - `prompts/templates/world/sphere-core.jinja2`, `sphere-fill.jinja2` and `sphere-branch.jinja2`;
  - the tests that cover only these.
- Modify `src/talemate/world/kinds.py`:
  - remove the `sphere` and `culture` kinds;
  - remove the fields `part_of`, `ties`, `parent`, `cultures`, `culture`, `language`, `template`, `drawers`, `agent` (re-added as a plain field on every kind), `owner` and `place`;
  - drop the drawer constants and `PART_OF_KINDS`.
- Sweep `worldplay/` and `server/` for the dead imports.
- Test: the whole suite.

**Interfaces:**
- Produces: a codebase with no sphere or drawer code. `agent: bool` is a field on every kind, and the prompt hint sets its default.
- [ ] **Step 1:** Grep for every reader of the removed names. Each must be gone, or ported in Tasks 3–6.
- [ ] **Step 2:** Delete the code, then run mypy and the plain suite. Expected: 0 failed. Fix only by deleting dead code or finishing the port; never by restoring the old fields.
- [ ] **Step 3:** Run `rg -n "part_of|drawer|sphere|ties\b" src/` and list any remaining hits in the report. Each must be intentional, for example the word "sphere" in hint prose.
- [ ] **Step 4: Commit:** `refactor(world): remove spheres, drawers, part-of, ties and the place parent`.

### Task 8: Group synopses and group "+ Add"

**Files:**
- Create:
  - `src/talemate/worldplay/groups.py`
  - `src/talemate/prompts/templates/world/group-synopsis.jinja2`
  - `src/talemate/prompts/templates/world/group-add.jinja2` (wording from Task 1, probes 3 and 6)
- Modify: `src/talemate/world/prose.py`, to cache synopses as the prose section `synopsis:<tag>`, stale when the group's members or their summaries change.
- Test: `tests/worldplay/test_groups.py`

**Interfaces:**
- Consumes: Tasks 2, 4 and 6.
- Produces:
  - `async group_synopsis(world, thing_id, tag, client) -> str`, which is cached.
  - `async group_add(world, thing_id, tag, prompt, client) -> list[{name, kind, tag, line, ticked=True}]`.
  - `accept_group_add(world, thing_id, rows) -> list[str]`, which writes stubs filed in `thing_id` with the row's tag and the line as their first fact, in one revision.
- [ ] **Step 1: Write the failing tests:**
  - `test_synopsis_cached_and_stale_on_change`
  - `test_group_add_rows_tagged_and_filed`
  - `test_group_add_accept_one_revision`
  - `test_synopsis_off_when_probe_fallback`, which is honoured if Task 1 says FALLBACK.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/worldplay -q` and the plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit:** `feat(worldplay): group synopses and adding to a group`.

### Task 9: Frontend: the entry page

**Files:**
- Create in `talemate_frontend/src/components/worlds/`:
  - `EntryIn.vue`
  - `EntryConnected.vue`
  - `ConnectedGroup.vue`
  - `EntryMentionedIn.vue`
  - `TagChip.vue`
  - `TagsTab.vue`
- Modify:
  - `ThingPage.vue`, which becomes the single entry page;
  - `WorldTab.vue`, which becomes two panes: the list with search, then Stubs and Tags;
  - `stores/worlds.js` and `worldKinds.js`.
- Delete:
  - `SpherePage.vue`, `SphereDrawer.vue`, `SphereFactAdd.vue`, `SphereFactRow.vue`, `SphereTimeline.vue`, `SpherePreviewCard.vue`;
  - `DrawerAddForm.vue`, `DrawerForm.vue`, `FillPreview.vue`;
  - `PartOfLine.vue`, `OuterBodyForm.vue`, `TiesSection.vue`, `TieForm.vue`, `CharacterTiesPreview.vue`.
- Test: `tests/e2e/worlds/test_filing.py` and `talemate_frontend/checks/worlds.check.mjs`

**Interfaces:**
- Consumes: Task 6's payload and actions.
- Produces mockup v3 screens A, B, D and E:
  - **"In"** rows, with the role, dates, within and exceptions, plus "+ in… 🔎" (which can make a stub);
  - **Connected,** grouped by tag:
    - one line per row;
    - a fold;
    - long groups show a filter, then the synopsis, then the first 5 rows, then "show all";
    - "✎ Synopsis" and "+ Add" (Task 8 rows);
    - dragging a row to another group changes its tag;
  - **Mentioned in,** folded;
  - **The timeline,** with "Events ▾" (all, or events only);
  - **"+ Add facts…" and "+ Add event…"** with prompts;
  - **The tag chip and picker,** and the Tags tab with rename and merge.
- Test ids:
  - `entry-in`
  - `entry-connected`
  - `connected-group`
  - `group-synopsis`
  - `group-add`
  - `entry-mentioned`
  - `tag-chip`
  - `tags-tab`
- [ ] **Step 1: Write the failing browser tests:**
  - `test_velikoye_connected_by_tag`
  - `test_add_filing_and_role`
  - `test_change_tag_moves_group`
  - `test_big_group_folds`
  - `test_group_add_rows`
  - `test_tags_rename_merge`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full browser suite (`-n 4`), the node checks, vite build and the `tests/ai` grep. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(worlds): entry page with In, Connected by tag and tags`.

### Task 10: Frontend: the draft page and the shared menus

**Files:**
- Modify:
  - `CreateBox.vue`, which only takes the prompt, then opens the draft page;
  - `ThingPage.vue`, which gains its draft mode;
  - `FactRowActions.vue`, `LinkedText.vue` (the selection menu), `SameThingAsk.vue`, `MoveInSection.vue` (renamed `MoveHere.vue`), `PreviewElsewhere.vue`, `PreviewRepeats.vue`, `PreviewStubs.vue`, `StubCard.vue` and `stores/worlds.js`.
- Test: `tests/e2e/worlds/test_drafts.py` and the node checks

**Interfaces:**
- Consumes: Tasks 6 and 9.
- Produces mockup v2 screens 3 and 4, plus v3 screen C:
  - **The draft bar:** Version n of m ▾, ↻ Regenerate, Edit prompt, Discard and Accept;
  - **The sections, in the spec's order:**
    1. In (ticked)
    2. "Same thing?" (a search; leave it empty for new)
    3. Facts (repeat matches with Move that one here, Keep both or Drop this)
    4. For other pages (the target can be changed; "+ also here")
    5. Could move here (unticked, with names highlighted)
    6. New names (kind, tag, same as… 🔎, in…, rename disabled with "later")
    7. File into this (unticked)
  - **The fact menu:** Move to… 🔎, Copy to… 🔎, Held by… 🔎, Edit, Change dates, End this, Remove, plus the system edit items;
  - **The selection menu:** Make a stub (kind and tag), Make a stub and expand now, Link to an entry… 🔎, and "Ask about this" shown disabled with the hint "later";
  - **Re-point** on the Stubs page and the stub card gains "use the name…" (hard re-point).
- Test ids:
  - `draft-bar`
  - `draft-versions`
  - `draft-discard`
  - `draft-in`
  - `draft-file-into`
  - `move-here`
  - `selection-menu`
  - `fact-menu`
- [ ] **Step 1: Write the failing browser tests:**
  - `test_draft_versions_and_discard`
  - `test_draft_in_and_file_into_accept`
  - `test_repeat_move_that_one_here`
  - `test_retarget_other_page_and_also_here`
  - `test_selection_make_stub_and_link`
  - `test_fact_move_and_copy`
  - `test_hard_repoint`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full browser suite (`-n 4`), the node checks, vite build and the `tests/ai` grep. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(worlds): the draft page and the shared menus`.

### Task 11: End to end with MockClient

**Files:**
- Create: `tests/worldplay/test_filing_end_to_end.py`
- Replace: `tests/worldplay/test_curation_end_to_end.py` and `test_spheres_end_to_end.py`, which are removed or rewritten.

- [ ] **Step 1: Write the test.** It goes through the router in a fresh world and covers this session:
  1. the owl-folk;
  2. the Tsardom with the nation hint;
  3. Velikoye and the river, filed in both;
  4. the Night Court with no thin stubs, plus the Tsar filed in it as "presides";
  5. the Academy, in Velikoye and Runic Magic;
  6. the military made after the White Talon ("File into this");
  7. a custom in two places;
  8. a group synopsis;
  9. a merge, then Re-point with a chosen name;
  10. a discard after regenerate;
  11. a scene that uses the filings.
- [ ] **Step 2: Run it,** then the plain suite. Expected: 0 failed.
- [ ] **Step 3: Commit:** `test(worldplay): filing end to end`.

### Task 12: A Skyfall session (owner-gated)

**Files:**
- Create:
  - `scripts/dev/probe_filing_flow.py`
  - `docs/superpowers/probes/<run-date>-filing-flow.md`, with its raw JSON and labels

- [ ] **Step 1: Ask the owner.**
- [ ] **Step 2: Run Task 11's session on Skyfall.** Score, against the hand labels:
  - tag reuse;
  - "In" accuracy;
  - thin stubs;
  - "File into this";
  - synopsis accuracy;
  - repeats;
  - how the scene uses its context.

  Compare it with the 2026-10-23 curation world.
- [ ] **Step 3: Fix prompt assembly if needed,** with tests and with this run's evidence.
- [ ] **Step 4: Commit:** `docs(probe): filing in a real session`.

### Task 13: The owner's acceptance run (owner-gated)

- Start the isolated app on a fresh root with `--ai --lan`, and give the owner the URL.
- The owner runs the spec's session and judges it by the reference questions ("What's in Velikoye? … who runs it?"), by how readable large lists are, and by acting in place.
- Fix any hiccups with root-caused, tested and reviewed fixes.
- Record the results in `docs/superpowers/probes/<run-date>-filing-acceptance.md`.
