# Polish 1: One Way to Review Suggestions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every place the AI hands the owner suggestions to tick uses one shared row, one shared bar, and server-held versioned drafts. That gives "+ Add facts", "+ Add event" and Connected's "+ Add" a page draft's feature set.

**Architecture:**
- **Server.** A small-draft store (`server/world_drafts.py`) keeps versions for fact, event, group-add and nested drafts, next to the page drafts that `worlds.py` already keeps.
- **Repeat choices.** Keep new and Move existing here are written by one shared function in `worldplay/create.py`, which page-draft accept, `accept_facts` and elsewhere rows all call.
- **Frontend.** `SuggestionBar`, `SuggestionRow` and a generalised `PreviewRepeats` replace the hand-built tick lists. The store keeps every small draft in one map with the page draft's shape.

**Tech Stack:** Python 3.11 with pydantic; a websocket plugin (`src/talemate/server/worlds.py`); Vue 3, Vuetify 3 and Pinia (`talemate_frontend`); pytest; Playwright e2e (`tests/e2e`); node checks (`talemate_frontend/checks/worlds.check.mjs`).

**Spec:** `docs/superpowers/specs/2026-10-25-polish-1-suggestion-lists-design.md`

## Global Constraints

- Nothing is written to the world before an explicit Write, Add or Accept.
- Repeat choice labels are exactly **Keep new**, **Keep existing**, **Keep both** and **Move existing here**.
- A choice that can't apply is shown disabled with its reason (`title`), never hidden. An elsewhere row's Move existing here has the reason `already on that page`.
- While a nested fact draft is open or pending, the page draft's Accept, Regenerate and version switch are off, with the reason `write or discard the added facts first`. Discard stays on and takes the nested draft with it.
- Versions per draft: `DRAFT_VERSIONS` (5), shared with page drafts. Small drafts are limited by their own least-recently-used cap, `SMALL_DRAFTS_KEPT = 20`, separate from `DRAFTS_KEPT`.
- Small drafts allowed: one fact or event draft per page (key `facts:<thing_id>`), one group-add draft per page and group (key `group:<thing_id>:<tag or "">`), and one nested draft per page draft (key `nested:<page draft key>`). They survive navigating away, and are dropped on reload or a world switch.
- Placement controls ("→ page ▾", "+ also here") go on a second line under the row's text (owner, mockup B).
- Use theme tokens for colour (`rgb(var(--v-theme-…))`), never hard-coded colours.
- Keep the existing `data-testid`s wherever the element survives. Grep `tests/ai` and `tests/e2e` for any test id that changes or goes.
- Run everything through `guix shell -m manifest.scm -- …` from the repo root, and always use `uv run --no-sync`.
  - Plain suite: `uv run --no-sync pytest`, with 0 failures.
  - Browser tests: `pytest tests/e2e -m e2e -n 4`, never more than 4 workers. While iterating, run only `tests/e2e/worlds`.
  - AI tests (`tests/ai`) only after asking the owner.

## Review Focus

1. **A reply arrives after its draft was discarded or replaced.** The owner presses Discard or Regenerate while a fact or group-add draft is pending. The late reply must add no version, and it must not bring back a discarded draft. Pinned in Task 2, `test_small_draft_late_reply_after_discard_is_dropped`.
2. **Switching worlds with a small draft open.** The owner opens world B and expects no fact or group-add draft from world A to show or be acceptable there. Pinned in Task 6, the node check `small drafts reset with the world`.
3. **Keep new on a repeat whose existing fact changed since.** The repeat's existing fact was edited, moved or removed in the meantime. Accept writes the new fact, leaves the world's fact alone, and adds a note. It never removes some other fact. Pinned in Task 3, `test_accept_facts_keep_new_existing_gone_since`.
4. **A forged repeat choice from the client.** A `replaces_repeat` or a `repeat` move row that names a fact the held draft versions never flagged removes or moves nothing, and adds a note. This applies to fact drafts and to elsewhere rows. Pinned in Task 3, `test_accept_facts_refuses_forged_repeat`, and Task 5, `test_elsewhere_keep_new_forged_is_refused`.
5. **Accepting the page draft while a nested draft is held.** If the client gating is bypassed, the server refuses `accept_preview`, `use_version`, and `preview_thing` with that draft key, and writes nothing. Pinned in Task 4, `test_page_draft_refuses_while_nested_held`.

---

## File Structure

**Server**
- Create `src/talemate/server/world_drafts.py`: `SmallDrafts`, the versioned store for small drafts. It's pure, with no world access.
- Modify `src/talemate/server/worlds.py`:
  - handlers for fact, event, group-add and nested drafts;
  - `use_small_version`, `discard_small_draft` and `write_nested_facts`;
  - the nested-draft gates;
  - the generalised `_check_repeat_moves`.
- Modify `src/talemate/worldplay/create.py`:
  - `write_repeat_choices` is shared by every accept;
  - `ElsewhereFact.replaces_repeat` is added;
  - `_write_keep_new` and the repeat branch of `_write_move_here` fold into `write_repeat_choices`.
- Modify `src/talemate/worldplay/facts.py`: `FactDraft` gains `move_here` and an optional `thing_id`; `accept_facts` writes the repeat choices.
- Modify `src/talemate/worldplay/groups.py`: no model change. Only `GroupAddDraft` is added, for holding.

**Frontend** (`talemate_frontend/src/`)
- Create `components/worlds/smallDrafts.js`: pure helpers for keys, version rows and per-version edits. Node-checked.
- Create `components/worlds/SuggestionBar.vue`, `components/worlds/SuggestionRow.vue` and `components/worlds/suggestions.css`. The CSS holds the shared `.suggestion-dropped`, `.suggestion-heading` and `.suggestion-match` styles.
- Modify `components/worlds/PreviewRepeats.vue`: add an `unavailable` prop.
- Modify `stores/worlds.js`: `smallDrafts` and `smallEdits` replace `factDraft` and `groupAdds`; the page-draft prompt goes into the bar; `draftShown`, `editPrompt` and `showDraft` are removed.
- Rebuild on the shared pieces: `DraftBar.vue`, `EntryAddFacts.vue`, `GroupAddForm.vue`, `PreviewElsewhere.vue`, `PreviewStubs.vue`, `MoveHere.vue` and `FactRow.vue` (draft mode), plus the inline File into and Inherited lists in `ThingPage.vue`, and `CreateBox.vue` ("Back to the draft" goes).
- Modify `components/worlds/draftPage.js`: add `settleElsewhereRepeat` and `elsewhereRepeatChoice`.

**Tests**
- Create `tests/server/test_world_drafts.py`.
- Extend:
  - `tests/server/test_worlds_plugin.py`;
  - `tests/worldplay/test_facts_names.py`;
  - `talemate_frontend/checks/worlds.check.mjs`;
  - `tests/e2e/worlds/test_drafts.py`, `test_filing.py` and `test_curation.py`.

---

### Task 1: The small-draft store

**Files:**
- Create: `src/talemate/server/world_drafts.py`
- Test: `tests/server/test_world_drafts.py`

**Interfaces:**
- Produces:
  - `SmallDrafts(limit: int = SMALL_DRAFTS_KEPT, versions: int = DRAFT_VERSIONS)`, a generic container of pydantic models. Its members:
    - `.add(key: str, value: BaseModel) -> int` appends a version and makes it current, dropping the oldest past `versions`. It returns the 0-based current index and moves the key to most recently used, evicting the least recently used past `limit`.
    - `.current(key) -> BaseModel` raises `KeyError("no such draft: <key>")`.
    - `.use(key, version: int) -> BaseModel` takes a 1-based version and raises `ValueError(f"the draft has no version {version}")`.
    - `.versions(key) -> list[BaseModel]`, `.index(key) -> int`, and `.held(key) -> bool`.
    - `.discard(key) -> None`; a missing key is a no-op.
    - `.clear() -> None`.
  - Constants `SMALL_DRAFTS_KEPT = 20`, plus `DRAFT_VERSIONS` imported from `worlds.py` or moved here. If it moves here, `worlds.py` imports it from this module.
  - Key helpers: `facts_key(thing_id) -> "facts:<id>"`, `group_key(thing_id, tag) -> "group:<id>:<tag or ''>"` and `nested_key(page_key) -> "nested:<page_key>"`.

- [ ] **Step 1: Write failing tests**, all in `tests/server/test_world_drafts.py`:
  - `test_add_and_current`: two adds under one key, so `index == 1`, `current` is the second, and `versions` has length 2.
  - `test_versions_capped`: seven adds with `versions=5` leave the last five, oldest dropped first.
  - `test_use_restores_and_refuses_unknown`: `use(key, 1)` makes the first current. `use(key, 9)` raises `ValueError`. `current("nope")` raises `KeyError`.
  - `test_lru_eviction`: with `limit=2`, adding keys a, b and c evicts a. Touching a key with `add` or `use` keeps it.
  - `test_discard_and_clear`: `discard` removes one key, `held` is False afterwards, and `clear` empties the store.
  - `test_keys`: `group_key("x", None) == "group:x:"`, `nested_key("stub:1") == "nested:stub:1"`.
- [ ] **Step 2: Run them and confirm they fail.** `uv run --no-sync pytest tests/server/test_world_drafts.py -v` fails with an ImportError.
- [ ] **Step 3: Implement `SmallDrafts`** on an `OrderedDict[str, list]` plus a `dict[str, int]` of current indexes, mirroring `_new_version` and `_touch` in `worlds.py`.
- [ ] **Step 4: Run the tests and confirm they pass.**
- [ ] **Step 5: Commit** with the message `feat(worlds): a versioned store for small drafts`.

---

### Task 2: Fact, event and group-add drafts are held and versioned

**Files:**
- Modify: `src/talemate/server/worlds.py`. The relevant code is the `_drafts` init (around line 1885), the world-switch clear (around 1913), `_draft_facts` (around 3741), `_fact_draft_out` (around 3830), `handle_accept_facts` (around 3887), `handle_group_add` and `handle_accept_group_add` (around 3675–3737), and the payload models.
- Modify: `src/talemate/worldplay/groups.py`, adding `class GroupAddDraft(BaseModel): thing_id: str; tag: str | None; prompt: str; show_under: bool = False; rows: list[GroupAddRow]`.
- Test: `tests/server/test_worlds_plugin.py`.

**Interfaces:**
- Consumes: Task 1's `SmallDrafts`, `facts_key` and `group_key`.
- Produces (wire):
  - **A new ask replaces the slot, unless it's a Regenerate.** `add_facts` / `add_event` with `thing_id` (no `draft_key`) normally discards that page's slot first. With `regenerate: true` it adds a version to the existing slot instead. The reply is `_fact_draft_out` plus `draft_key` (`facts:<id>`), `version` (1-based) and `versions: [{version, prompt, year}]`.
  - **The same applies to group-add.** `group_add` with `regenerate: true` adds a version. Its reply gains `draft_key`, `version` and `versions: [{version, prompt}]`.
  - **`use_small_version {draft_key, version}`** answers `use_small_version` with the same payload the slot's own reply would have (fact or group shape), plus `kind: "facts" | "group" | "nested"`.
  - **`discard_small_draft {draft_key}`** answers `discard_small_draft {draft_key}` and writes nothing.
  - **`accept_facts`** takes an optional `draft_key`. On success it discards that slot.
  - **`accept_group_add`** takes an optional `draft_key`, with the same effect.
  - **Late replies are dropped.** A reply whose key was discarded while it was out adds nothing and answers nothing. This follows the `on_done` guard in `handle_preview_thing`.
  - **Switching worlds clears the small-draft store too.**

- [ ] **Step 1: Write failing tests.** Follow the existing `test_add_facts` and `test_versions_restore` style: `_act`, `_last`, `MockClientContext`, `client_responses`.
  - `test_add_facts_versions_and_use`:
    - The first `add_facts` gives version 1.
    - The second, with `regenerate=True` and a new prompt, gives version 2, and `versions` lists both prompts.
    - `use_small_version` back to 1 returns version 1's facts.
    - The world head is unchanged.
  - `test_add_facts_new_ask_replaces_slot`: a second `add_facts` without `regenerate` answers `version == 1` and `len(versions) == 1`.
  - `test_accept_facts_drops_its_slot`: after `accept_facts` with `draft_key`, `use_small_version` errors with "no such draft".
  - `test_group_add_versions`: the same flow for `group_add` with `regenerate=True` and `use_small_version`. Then `accept_group_add` with `draft_key` drops the slot.
  - `test_small_draft_late_reply_after_discard_is_dropped`: start `add_facts` without draining, call `discard_small_draft`, then drain. There's no `add_facts` reply and the slot isn't held. Mirror `test_drafts_are_bounded_and_a_late_result_after_discard_is_dropped`.
  - `test_small_drafts_cleared_on_world_switch`: open another world, and `use_small_version` on the old key errors.
- [ ] **Step 2: Run them and confirm they fail.** Use `uv run --no-sync pytest tests/server/test_worlds_plugin.py -k "small or versions_and_use or replaces_slot or drops_its_slot or group_add_versions" -v`.
- [ ] **Step 3: Implement.**
  - Add `self._small = SmallDrafts()` next to `_drafts`.
  - Write `_small_out(world, key) -> dict`, which dispatches on the held model type (`FactDraft` → `_fact_draft_out`, `GroupAddDraft` → the group reply) and adds `draft_key`, `version` and `versions`.
  - Add `regenerate: bool = False` to `AddFactsPayload`, `AddEventPayload` and `GroupAddPayload`, and `draft_key: str | None = None` to `AcceptFactsPayload` and `AcceptGroupAddPayload`.
  - Keep `failure_data` carrying `thing_id` (and `tag`) as today, so the client can match failures.
- [ ] **Step 4: Run the tests and confirm they pass,** together with the existing `-k "add_facts or group_add or fact_draft"` tests.
- [ ] **Step 5: Commit** with the message `feat(worlds): fact, event and group-add drafts keep versions`.

---

### Task 3: One function settles repeats for every accept

**Files:**
- Modify: `src/talemate/worldplay/create.py`. The relevant code is `_write_move_here` (around 4063), `_write_keep_new` (around 4144) and their two call sites (around 3884 and 4581).
- Modify: `src/talemate/worldplay/facts.py`. `FactDraft` gains `move_here: list[MoveHereFact] = []`, and `accept_facts` and `_write_facts` change.
- Modify: `src/talemate/server/worlds.py`. `_check_repeat_moves` is generalised and called from `handle_accept_facts`.
- Test: `tests/worldplay/test_facts_names.py` (or a new `tests/worldplay/test_fact_draft_repeats.py`), and `tests/server/test_worlds_plugin.py`.

**Interfaces:**
- Produces:
  - **`write_repeat_choices(rev, before: WorldView, rows: Sequence[Any], move_here: Sequence[MoveHereFact], thing_id: str, notes: list[str]) -> tuple[list[tuple[str, FactState]], list[tuple[str, FactState]]]`** in `create.py`. It returns `(moved, removed)`.
    - `rows` is any rows with `ticked`, `replaces_repeat` and `repeat_of`: `PreviewFact` or `ElsewhereFact`.
    - It moves each ticked `repeat` move row's fact onto `thing_id`, then removes each ticked `replaces_repeat` row's repeated fact.
    - It does both with today's checks and note wording: gone since, summary, not a repeat of these rows, already moved.
    - `_write_move_here` keeps only the non-repeat "Could move here" rows and calls this for the repeat ones. `_write_keep_new` is deleted.
  - **`WorldsPlugin._check_repeat_moves(rows, move_here, held_rows, notes) -> list[MoveHereFact]`** is generalised from today's version. `held_rows` is every row of every held version, and it returns the kept `move_here`. The page-draft call passes `preview.facts`, `preview.move_here` and the held versions' facts. The fact-draft call passes the held small-draft versions' facts.
  - **`accept_facts(world, draft, notes)`** writes `write_repeat_choices(rev, view, kept_facts, draft.move_here, draft.thing_id, notes)` in its revision. A ticked fact with `replaces_repeat` is written, and its repeat removed.

- [ ] **Step 1: Write failing tests:**
  - `test_accept_facts_keep_new_replaces_repeat`:
    - Set up a fact draft whose fact repeats another entry's fact, with `ticked=True` and `replaces_repeat=True`.
    - After `accept_facts`, the new fact is on the page and the repeated fact is gone from its owner, in one revision (head + 1).
  - `test_accept_facts_move_existing_here`:
    - Set up a draft fact unticked, plus `move_here=[MoveHereFact(fact_id, from_id, text, ticked=True, repeat=True)]`.
    - The existing fact moves onto the page, and the draft fact isn't written.
  - `test_accept_facts_keep_new_existing_gone_since`: remove the repeated fact before accepting. The new fact is written, nothing else is removed, and `notes` contains `"was moved or removed since the preview"`.
  - `test_accept_facts_refuses_forged_repeat` (plugin level): `accept_facts` with `draft_key` and a `replaces_repeat` naming a fact that no held version flagged. Nothing is removed, and the reply's notes contain `"isn't a fact this draft repeats"`.
  - All the existing repeat tests must still pass: `test_repeat_move_that_one_here`, `test_repeat_choices` (e2e), and everything under `-k "repeat or keep_new"` in `tests/server` and `tests/worldplay`.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement** as in Interfaces. `handle_accept_facts` sends notes back in its reply (`"notes": notes`), as `accept_preview` does.
- [ ] **Step 4: Run** `uv run --no-sync pytest tests/worldplay tests/server -k "repeat or keep_new or accept_facts or move_here" -v` and confirm it passes.
- [ ] **Step 5: Commit** with the message `refactor(worlds): one writer for repeat choices; fact drafts settle repeats`.

---

### Task 4: Nested fact drafts on a draft page

**Files:**
- Modify: `src/talemate/server/worlds.py`. The relevant code is `_draft_facts` (the `draft_key` branch), `_draft_added`, `handle_discard_preview`, `handle_accept_preview`, `handle_use_version` and `handle_preview_thing`.
- Modify: `src/talemate/worldplay/facts.py`. `FactDraft.thing_id` becomes `str | None = None`, and `accept_facts` raises `ValueError("a page draft's facts are written into the draft")` when it's None.
- Test: `tests/server/test_worlds_plugin.py`.

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces (wire):
  - **Asking for facts on a draft.** `add_facts` / `add_event` with `draft_key` (a page draft) no longer append to the draft. They hold a `FactDraft(thing_id=None, prompt, year, facts, new_names, move_here=[])` under `nested_key(draft_key)`, built from `draft_facts_for`'s `DraftAddition` (names as `DraftName`).
    - They answer `add_facts` / `add_event` with the fact-draft payload plus `draft_key` (the nested key), `version`, `versions`, and `nested_in: <page key>`.
    - `regenerate: true` adds a version.
    - The existing stale-version guard (`worlds.facts_stale`) stays for replies that land after the page draft's version changed.
  - **`write_nested_facts {draft_key: <page key>, draft: FactDraft}`** does the writing.
    - It checks repeats against the held nested versions (`_check_repeat_moves`).
    - Then it appends the ticked facts (with `replaces_repeat` kept) and the ticked `new_names` to a **copy** of the page draft's current version, and its kept `move_here` repeat rows to the copy's `move_here`.
    - It holds that copy as a **new page-draft version** (`_new_version`), discards the nested slot, and answers `write_nested_facts` with `_draft_out` for the page draft.
    - It writes nothing to the world.
  - **Discard cascades:** `discard_preview` also discards `nested_key(key)`.
  - **Gate:** while `self._small.held(nested_key(key))`, `accept_preview`, `use_version` and `preview_thing` with that `draft_key` raise `ValueError("write or discard the added facts first")`.

- [ ] **Step 1: Write failing tests.** Rewrite `test_add_facts_and_event_on_a_draft` and `test_added_facts_on_a_draft_join_its_new_names` for the new flow, and add:
  - `test_nested_facts_write_into_a_new_version`:
    - After `add_facts` on a draft, the page draft's `preview.facts` are unchanged.
    - After `write_nested_facts`, with one fact unticked, the reply's version is `previous + 1`, and the facts are the old ones plus only the ticked one.
    - The world head is unchanged.
  - `test_nested_regenerate_and_use`: a version 2 with `regenerate=True`; `use_small_version` back to 1.
  - `test_page_draft_refuses_while_nested_held`:
    - `accept_preview`, `use_version` and `preview_thing` with the key each error with `"write or discard the added facts first"`.
    - After `discard_small_draft` on the nested key, `accept_preview` works.
  - `test_discard_page_draft_discards_nested`.
  - `test_draft_facts_for_a_version_left_join_none` must still pass, adjusted for the nested flow.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement** as in Interfaces. Delete `_draft_added`.
- [ ] **Step 4: Run** `uv run --no-sync pytest tests/server/test_worlds_plugin.py -k "draft" -v` and confirm it passes.
- [ ] **Step 5: Commit** with the message `feat(worlds): "+ Add facts" on a draft is its own nested draft`.

---

### Task 5: Keep new on "For other pages" rows

**Files:**
- Modify: `src/talemate/worldplay/create.py` (`ElsewhereFact` gains `replaces_repeat: bool = False`; both accept paths call `write_repeat_choices` with the elsewhere rows, grouped by target)
- Modify: `src/talemate/server/worlds.py` (`_check_repeat_moves` also checks `preview.elsewhere` rows' `replaces_repeat` against the held versions' elsewhere `repeat_of`)
- Test: `tests/server/test_worlds_plugin.py`

**Interfaces:**
- Consumes: Task 3's `write_repeat_choices`.
- Produces: an elsewhere row that is ticked, has `replaces_repeat=True` and has a `repeat_of` is written to its target. Its repeated fact on the target is removed in the accept's revision. Elsewhere rows never produce move rows.

- [ ] **Step 1: Write failing tests:**
  - `test_elsewhere_keep_new_replaces_targets_fact`: a page draft whose elsewhere row repeats its target's fact, accepted with `replaces_repeat=True`. The target ends up with the new text and without the old fact.
  - `test_elsewhere_keep_new_forged_is_refused`: `replaces_repeat` with a `repeat_of` that no held version has. The target's fact stays, and the notes say `"isn't a fact this draft repeats"`.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `-k "elsewhere"` and confirm it passes.
- [ ] **Step 5: Commit** with the message `feat(worlds): "Keep new" on other pages' repeats`.

---

### Task 6: The store keeps small drafts in one shape

**Files:**
- Create: `talemate_frontend/src/components/worlds/smallDrafts.js` (pure; no Vue, no `@/` imports)
- Modify: `talemate_frontend/src/stores/worlds.js` (state around 616–683, actions around 1417–1520, message cases around 1934–1975, failure reset around 2250–2260, module comment around 95–140)
- Test: `talemate_frontend/checks/worlds.check.mjs`

**Interfaces:**
- Consumes: Task 2's and Task 4's wire.
- Produces:
  - **`smallDrafts.js`:**
    - `factsKey(thingId)`, `groupDraftKey(thingId, tag)` and `nestedKey(pageKey)`, all matching the server's keys;
    - `smallVersionRows(versions, current) -> [{version, label, prompt, current}]`, which reuses `versionRows`' label style;
    - `keepSmallEdits(smallEdits, draft) -> smallEdits`;
    - `restoredEdited(smallEdits, key, version, base) -> edited`, which returns the kept `edited` when its `base` deep-equals the new `base`, and `base` otherwise.
  - **Store state** (inside `worldState()`, so `resetWorld` clears it):
    - `smallDrafts: { [key]: { key, kind: 'facts'|'event'|'group'|'nested', thingId, tag, showUnder, prompt, year, version, versions, base, edited, rows, pending, accepting, error } }`. `base` and `edited` hold the `FactDraft` or `GroupAddDraft` JSON. `rows` holds the server's rendered rows (fact `facts` with segments).
    - `smallEdits: {}`.
    - `factDraft` and `groupAdds` are removed.
  - **Store actions:**
    - `askFacts(mode, prompt, year)` and `askGroupAdd(thingId, tag, prompt, { showUnder })`;
    - `askNestedFacts(prompt, year)`, available only while `draft` is open and no nested draft is held or pending;
    - `regenerateSmall(key)`, which re-asks with `regenerate: true` and the draft's current `prompt` and `year`;
    - `setSmallPrompt(key, prompt, year?)`;
    - `useSmallVersion(key, version)`, which keeps the edits first;
    - `editSmall(key, changes)`, which merges into `edited`;
    - `discardSmall(key)`, which sends `discard_small_draft`;
    - `acceptSmall(key)`, which sends `accept_facts`, `accept_group_add` or `write_nested_facts` according to `kind`, each with `draft_key`;
    - `nestedHeld` (getter): true while `smallDrafts[nestedKey(draft.key)]` exists.
  - **Message cases:** `add_facts`, `add_event`, `group_add`, `use_small_version`, `discard_small_draft`, `write_nested_facts` and their `_failed` forms update `smallDrafts`. `write_nested_facts` calls `draftTaken(data, 'new')` and deletes the nested slot.
  - **Removed:** `addFacts`, `addEvent`, `tickDraftFact`, `changeFactDraftName`, `discardFacts`, `acceptFacts`, `groupAdd`, `editGroupAdd`, `discardGroupAdd`, `acceptGroupAdd` and `addDraftFacts`. Update their callers in the later tasks. Until those tasks land, the components can call the new actions directly.

- [ ] **Step 1: Write failing node checks** in `worlds.check.mjs`, in the file's existing style:
  - `small draft keys match the server`;
  - `use small version keeps and restores edits`: tick a row, switch to version 1, back to 2, and the tick is back;
  - `regenerate sends regenerate:true with the edited prompt`;
  - `small drafts reset with the world`: after `resetWorld`, `smallDrafts` is `{}`;
  - `nested draft gates the page draft`: `nestedHeld` is true after a nested `add_facts` reply.
- [ ] **Step 2: Run them and confirm they fail.** Use `uv run --no-sync pytest tests/dev/test_frontend_checks.py -v`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them and confirm they pass.**
- [ ] **Step 5: Commit** with the message `refactor(worlds-ui): small drafts in one versioned store shape`.

---

### Task 7: SuggestionRow, SuggestionBar and the shared styles

**Files:**
- Create: `talemate_frontend/src/components/worlds/SuggestionRow.vue`, `SuggestionBar.vue` and `suggestions.css`
- Modify: `talemate_frontend/src/components/worlds/PreviewRepeats.vue`
- Test: the e2e coverage arrives with Tasks 8–11, which put these components on screen.

**Interfaces:**
- Produces:
  - **`SuggestionRow`:**
    - Props: `ticked: Boolean` (default true), `tickLabel: String` (the checkbox aria-label, keeping each list's existing wording), `tickable: Boolean` (default true), `disabled: Boolean`, `testid: String` (put on the root), `dropped: Boolean` (default `!ticked`).
    - Emits `tick(Boolean)`.
    - Slots:
      - `default`: the text, rendered with `.suggestion-dropped` when dropped;
      - `end`: the category chip and date, on the right of the first line;
      - `under`: the second line, starting at the text's left edge, for placement controls and notes;
      - `match`: the repeat block, indented to the text with a left rule;
      - `after`: forms.
    - The dashed separator is on the root's bottom edge, after `match` and `after`.
  - **`SuggestionBar`:**
    - Props: `label: String` (the chip), `versions: Array` (from `smallVersionRows` or `versionRows`), `version: Number`, `prompt: String`, `year: Number|null` (`undefined` hides the year field), `promptLabel: String`, `busy: Boolean`, `locked: String|null` (a reason; when set, Regenerate, the version menu and the primary button are disabled with it as `title`), `primaryLabel: String`, `canPrimary: Boolean`, `primaryLoading: Boolean`, `testid: String`.
    - Emits `update:prompt`, `update:year`, `regenerate`, `use-version(n)`, `discard` and `primary`.
    - Slot `status`: the line under the bar.
    - The prompt is a `v-textarea` with `auto-grow`, `rows="2"`, `density="compact"`, `variant="outlined"` and `hide-details`, and keeps the `add-prompt` / `group-add-prompt` test ids through a `promptTestid` prop.
    - It also exports a foot mode. With `foot: Boolean`, it renders only the primary and Discard buttons, for the end of a list.
  - **`PreviewRepeats`:** a new prop `unavailable: Object` (`{ [how]: reason }`), whose reasons are added to `refusal()`.
  - **`suggestions.css`:** `.suggestion-dropped` (line-through and muted), `.suggestion-heading` (today's `.heading`: 12px uppercase, muted) and `.suggestion-match` (today's `.match`). It's imported unscoped from `SuggestionRow.vue`.

- [ ] **Step 1: Build the three files and the `PreviewRepeats` prop.** Nothing uses them yet, so the build is the check.
- [ ] **Step 2: Run** `uv run --no-sync pytest tests/dev/test_frontend_checks.py -v` and confirm it passes. It includes the frontend build and lint checks.
- [ ] **Step 3: Commit** with the message `feat(worlds-ui): SuggestionRow and SuggestionBar`.

---

### Task 8: The page draft's bar holds its prompt

**Files:**
- Modify: `DraftBar.vue` (rebuilt on `SuggestionBar`), `CreateBox.vue` (remove "Back to the draft"; when a draft exists for the box, its own prompt form isn't shown), `ThingPage.vue` (the bar's `locked` comes from `worlds.nestedHeld`) and `stores/worlds.js` (add `setDraftPrompt(prompt)`, which sets `previewRequest.prompt`; `regeneratePreview` uses it; remove `draftShown`, `editPrompt` and `showDraft`)
- Test: `tests/e2e/worlds/test_drafts.py`

**Interfaces:**
- Consumes: Task 7's `SuggestionBar` and Task 6's `nestedHeld`.

- [ ] **Step 1: Write failing e2e tests:**
  - `test_draft_prompt_in_bar_regenerates`:
    - Make a page draft. The bar shows the prompt in a textarea, and the page has no "Edit prompt" button.
    - Edit the prompt and click Regenerate. The sent `preview_thing` carries the edited prompt and the draft key, and the bar says "Version 2 of 2".
  - Update `test_draft_versions_and_discard` and any test that clicks "Edit prompt" or "Back to the draft". Grep `tests/e2e` and `tests/ai` for `Edit prompt`, `Back to the draft`, `editPrompt` and `draftShown`.
- [ ] **Step 2: Run** `pytest tests/e2e/worlds/test_drafts.py -m e2e -n 4` and confirm the new test fails.
- [ ] **Step 3: Implement.** The create box's pickers stay as the request's `fields`, and Regenerate reuses them (spec: "my call").
- [ ] **Step 4: Run** `tests/e2e/worlds` and confirm it passes.
- [ ] **Step 5: Commit** with the message `feat(worlds-ui): the draft's prompt lives in its bar`.

---

### Task 9: "+ Add facts" and "+ Add event" on saved and draft pages

**Files:**
- Modify: `EntryAddFacts.vue`, rebuilt on `SuggestionBar`, `SuggestionRow`, `PreviewRepeats` and `PreviewStubs`. It also renders the nested draft when `onDraft`.
- Modify: `ThingPage.vue`, removing the `draft-adding` spinner block; the nested draft renders under the Facts heading, indented.
- Test: `tests/e2e/worlds/test_filing.py` (`test_added_facts_bring_new_names`) and `tests/e2e/worlds/test_drafts.py`.

**Interfaces:**
- Consumes: Task 6's actions and Task 7's components. Use `settleRepeat` and `repeatChoice` from `draftPage.js` on `edited` (a `FactDraft` has `facts` and `move_here`, so they apply unchanged).
- Keeps these test ids: `add-facts`, `add-event`, `add-prompt`, `add-year`, `add-draft`, `fact-draft`, `fact-draft-row`, `fact-draft-accept`, `fact-draft-discard`, `fact-draft-error`, `fact-draft-repeat` (now on the match block), `draft-new-names`.

- [ ] **Step 1: Write failing e2e tests,** using `fixed_facts` and rewriting the file between asks to serve a different reply:
  - `test_add_facts_regenerate_and_versions` (saved page):
    - Ask, untick a row, edit the prompt, and Regenerate. The new rows show, and "Version 2 of 2" is visible.
    - Switch to version 1. The unticked row is unticked again.
    - Write. The sent `accept_facts` has `draft_key == "facts:<id>"`.
  - `test_add_facts_repeat_keep_new` (saved page): a fixed reply whose fact repeats another entry's fact. The match shows under its row with the four labels. Click Keep new and then Write; the other entry's page no longer has the old fact.
  - `test_nested_add_facts_on_draft`:
    - On a page draft, "+ Add facts". A nested bar shows under Facts, and the page bar's Accept is disabled with the title `write or discard the added facts first`.
    - Untick one row and Write. The page draft's facts gain only the ticked one, the version counter goes up by one, and Accept is enabled again.
  - `test_add_facts_prompt_box_is_roomy`: the prompt is a textarea that grows, and its rendered height is at least two lines (`boundingBox().height >= 40`).
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.** "Write N" goes in the bar and again in the foot. An event draft shows the year beside the prompt.
- [ ] **Step 4: Run `tests/e2e/worlds` and confirm it passes.**
- [ ] **Step 5: Commit** with the message `feat(worlds-ui): "+ Add facts" is a versioned draft everywhere`.

---

### Task 10: Connected's "+ Add" on the shared pieces

**Files:**
- Modify: `GroupAddForm.vue`, rebuilt on `SuggestionBar` and `SuggestionRow`. Its editable name goes in the default slot, and its kind and tag chips plus "shows under …" in `under`.
- Modify: `ConnectedGroup.vue` and `EntryConnected.vue`, for the new store actions.
- Modify: `entryPage.js`, removing `groupKey` if nothing else uses it (use `groupDraftKey`).
- Test: `tests/e2e/worlds/test_filing.py`.

**Interfaces:**
- Consumes: Task 6 and Task 7.
- Keeps these test ids: `group-add`, `group-add-prompt`, `group-add-draft`, `group-add-row`, `group-add-accept`, `group-add-discard`, `group-add-error`, `group-add-row-show-under`.

- [ ] **Step 1: Write a failing e2e test,** `test_group_add_regenerate_keeps_prompt`:
  - "+ Add" a group, then edit a row's name.
  - Edit the prompt and Regenerate with a new fixed reply. "Version 2 of 2" is visible.
  - Go back to version 1. The edited name is back.
  - Add. The sent `accept_group_add` carries `draft_key`.

  The existing `test_group_add_rows` and `test_add_and_drag_into_a_show_under_group` must still pass. Change `.draft-name input` there only if the selector changes.
- [ ] **Step 2: Run it and confirm it fails.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run `tests/e2e/worlds/test_filing.py` and confirm it passes.**
- [ ] **Step 5: Commit** with the message `feat(worlds-ui): Connected "+ Add" is a versioned draft`.

---

### Task 11: The page draft's sections on SuggestionRow

**Files:**
- Modify: `FactRow.vue`. In `draft` mode its root becomes a `SuggestionRow`: the existing content goes in the default and `end` slots, `held by` and `added here` go in `under`, and the `PreviewRepeats` slot from ThingPage goes in `match`. Saved-page `FactRow` is unchanged, since that's area 3.
- Modify: `PreviewElsewhere.vue`:
  - "→ page ▾" and "+ also here" move into `under`;
  - the category select stays in `end`;
  - the repeat caption becomes `PreviewRepeats` with `:unavailable="{ move: 'already on that page' }"`, emitting `settle` through `settleElsewhereRepeat`.
- Modify: `PreviewStubs.vue`, `MoveHere.vue` and the inline File into and Inherited lists in `ThingPage.vue`, which all go on `SuggestionRow`. Inherited's "Replaced by" select goes in `under`, and its replaced look becomes `.suggestion-dropped`.
- Modify: `draftPage.js`. Add `settleElsewhereRepeat(edited, index, how) -> {elsewhere}` ('new': ticked and `replaces_repeat`; 'existing': unticked; 'both': ticked and not `replaces_repeat`; 'move' is never produced) and `elsewhereRepeatChoice(row)`.
- Delete the `.dropped`, `.heading` and `.match` copies in `EntryAddFacts`, `MoveHere`, `PreviewElsewhere`, `GroupAddForm`, `FactRow`, `PreviewStubs`, `ThingPage` and `PreviewRepeats`, and use the shared classes. `MergeDialog.vue` and `EntryIn.vue` (`.thing-link.dropped`) are the builder's call:
  - MergeDialog's rows move to `SuggestionRow` only if they're tick-to-keep rows;
  - EntryIn is area 3.
- Test: `talemate_frontend/checks/worlds.check.mjs`, `tests/e2e/worlds/test_drafts.py` and `test_curation.py`.

**Interfaces:**
- Consumes: Tasks 5, 7 and 9.

- [ ] **Step 1: Write failing tests:**
  - A node check, `settleElsewhereRepeat sets replaces_repeat and ticks`, covering the three ways.
  - An e2e test, `test_elsewhere_row_controls_under_text_and_repeat_choices`:
    - In a draft with an elsewhere row, `elsewhere-target` and `elsewhere-also` are below the text: their `boundingBox().y` is greater than the text's.
    - A repeating elsewhere row shows the four choices, with Move existing here disabled and titled `already on that page`.
    - Keep new, then Accept: the target loses its old fact.
  - An e2e test, `test_repeat_match_sits_above_separator`: in a draft whose fact has a repeat, the `fact-match` block is inside the same `draft-fact` element as its fact, and the next `draft-fact` starts after it.
  - Update `test_retarget_other_page_and_also_here` and `test_repeat_choices` if any selector moved.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `tests/e2e/worlds` and the node checks, and confirm they pass. Confirm that `grep -rn "^\.dropped\|^\.heading\|^\.match" talemate_frontend/src/components/worlds` finds only `suggestions.css`, plus any copies the builder deliberately kept in MergeDialog or EntryIn.
- [ ] **Step 5: Commit** with the message `refactor(worlds-ui): draft sections share SuggestionRow; one dropped style`.

---

### Task 12: The whole branch, verified

**Files:** no new ones.

- [ ] **Step 1:** Grep `tests/ai` for every test id, action name and store action that was changed or removed: `addDraftFacts`, `factDraft`, `groupAdds`, `editPrompt`, `draftShown`, `draft-adding`, `Edit prompt`. Update the hits. Don't run the AI tests without asking the owner.
- [ ] **Step 2:** Check for apps left over from earlier test runs (`ps -eo pid,etime,cmd | grep "[p]ytest-of-$USER/pytest-.*/app"`), then run the plain suite (`uv run --no-sync pytest`), expecting 0 failures.
- [ ] **Step 3:** Run `pytest tests/e2e -m e2e -n 4` and expect it to pass. If there are load flakes, rerun them with `--lf` and record which ones.
- [ ] **Step 4:** Run `ruff check` and `ruff format --check` on the changed Python, using the manifest's ruff.
- [ ] **Step 5:** Write the owner's acceptance checklist into the ledger, from the spec's "How the owner will judge it", and commit with the message `docs(polish-1): acceptance checklist`.
