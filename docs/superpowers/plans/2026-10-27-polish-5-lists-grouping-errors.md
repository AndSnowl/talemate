# Polish 5: Lists, grouping and errors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a side tree that folds, search with text modifiers, a full list on each kind's page, Connected ordered by kind, one pinned error message, dimmed offer rows, and two small fixes.

**Architecture:**
- **Pure helpers.** A new `worldTree.js` holds the tree, search and list logic, tested by node checks: it builds the tree, parses modifiers, matches entries, and groups and sorts the list. Vue components only draw.
- **Server.** `list_things` gains the fields the list and search need. `_connected_out` sorts by kind.
- **Errors.** One `WorldError.vue` replaces the in-page alerts.

**Tech Stack:** Vue 3, Vuetify 3.12, Pinia; Python websocket plugin; pytest, node checks (`talemate_frontend/checks/worlds.check.mjs`), Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-10-27-polish-5-lists-grouping-errors-design.md`

## Global Constraints

- **Owner rules:**
  - controls sit next to their content (right-align only in half-width areas);
  - one component, never a copy;
  - the approved screen is the model: check the rest against before and after screenshots;
  - move only the part that needs the room.
- **Execution is inline, with screenshots sent after each visible change** (`SendUserFile`).
- **Mockups the owner chose:** tree A, kind page 2, list row A, in `.superpowers/brainstorm/589-1793133581/content/`.
- **List row copy:**
  - "**name** · in Velikoye — summary";
  - "in Velikoye +1" when it's filed in more than one place;
  - a stub: "**name** · in Velikoye · not made yet";
  - "Nowhere" heads the no-home group, and "Other" the untagged group.
- **Kind order:** characters, species, races, mixes, places, events, items, lore, beings.
- **Search modifiers:** `tag:`, `in:` (quotes for spaces), `stub`, `when:`. Unknown modifiers are plain words.
- **Keep test ids.** Grep `tests/e2e` and `tests/ai` for any that change, and never run `tests/ai`.
- **Running things:**
  - use `guix shell -m manifest.scm -- uv run --no-sync …` from the worktree root;
  - e2e runs with `-n 4` at most;
  - `test_tags_rename_merge` is a known flake;
  - build with `guix shell -m manifest.scm -- sh -c 'cd talemate_frontend && npx --yes corepack@0.34.0 pnpm build'`.

## Review Focus

1. **Loops and cross-kind homes.** A place filed in a place that is filed back in it, or an item whose only home is a character. The tree shows each entry once and never hangs; "group by where" puts the item under the character. Pinned in Task 2, `sideTree survives a filing loop` and `groupList by where uses a home of any kind`.
2. **Malformed search.** `in:Nowhereville`, `when:abc`, `in:"Night Court` with no closing quote, `tag:` with nothing after it. None of these crash. A bad `when:` or `tag:` is searched as plain words, and an unknown `in:` place matches nothing. Pinned in Task 2, `parseSearch reads malformed modifiers as words`.
3. **Saved folds that no longer fit, and storage that throws.** Folds for deleted entries, a corrupt saved value, or `localStorage` that throws (private window). The tree still draws with defaults. Pinned in Task 3, `loadFolds survives bad storage`.
4. **The same error again, an error after scrolling, and switching world.** It shows "×2", stays in view, and closes on switching world. Pinned in Task 6, `test_error_pinned_counts_and_clears`.
5. **A world of 150 entries.** `list_things` must stay fast enough that the list doesn't lag (one timeline read per entry is acceptable; one per fact isn't). Pinned in Task 1, `test_list_things_extra_fields_cost`: list 150 entries in under 2 s.

---

### Task 1: The kind lists carry tag, line, date, span, change and connections

**Files:** `src/talemate/server/worlds.py` (`handle_list_things` ~2640); tests in `tests/server/test_worlds_plugin.py`.

**Interfaces — Produces** (each `list_things` entry gains):
- `tag: str | None` (`filing.tag_of`);
- `line: str`: the rendered text of `_line_fact(state)`, or `""` when there is none;
- `changed_rev: int`: the highest `source_rev` among `world.timeline(id)` entries;
- `connections: int`: `len(mentions(view, id))` plus the number of live entries filed in it;
- `span: {"from": int | None, "until": int | None}`, as years (`WorldDate.year`, or the instant's year):
  - a character: `from` is its born year, `until` is null;
  - an event: its `when` and `until` dates;
  - a being: its born year when it has one, as a character's; otherwise `null`. Its `existence` is a mode ("eternal"…), not a span, so the spec's "a being's existence holds then" reads as "always matches" (ruling for the ledger);
  - anything else: `null` instead of an object;
- `sort_date: int | None`: `span.from`, else the earliest `valid_from` year of its facts.

- [ ] **Write the failing tests:**
  - `test_list_things_carries_list_fields`. Seed Velikoye with tag "city" and a summary fact "The fortified capital."; Kerensk filed in Velikoye; a fact on Kerensk that mentions Velikoye; a character Maren born 1000; an event "The Thaw" with when 1010 and until 1012. Assert:
    - Velikoye's `tag == "city"`, `line == "The fortified capital."` and `connections == 2`;
    - Maren's `span == {"from": 1000, "until": None}` and `sort_date == 1000`;
    - The Thaw's `span == {"from": 1010, "until": 1012}`;
    - Velikoye's `span is None`;
    - after a later `set_tag` on Velikoye, its `changed_rev` grows.
  - `test_list_things_extra_fields_cost`: 150 places, each with 2 facts. `list_things` for places answers in under 2 s.
- [ ] Run them and confirm they fail with a KeyError on `tag`.
- [ ] Implement in `handle_list_things`. Update the exact-shape expectations in the existing tests that compare whole entries: `test_router_list_and_get_thing` and `test_list_things_carries_other_names`.
- [ ] Run `tests/server` and confirm it passes.
- [ ] Commit with the message `feat(worlds): kind lists carry tag, line, dates and connections`.

### Task 2: The tree, search and list logic (pure)

**Files:** create `talemate_frontend/src/components/worlds/worldTree.js`; node checks in `talemate_frontend/checks/worlds.check.mjs`.

**Interfaces — Consumes:** Task 1's entry fields, and `mostPreciseHome` (`entryPage.js`).

**Interfaces — Produces:**
- `KIND_ORDER = ['character','species','race','mix','place','event','item','lore','being']`.
- `parseSearch(text) -> {words: string, tag: string|null, inName: string|null, stub: boolean, when: number|null}`.
  - `tag:` with a word sets `tag`. `in:Name` or `in:"Two Words"` sets `inName`. A bare `stub` sets `stub`. `when:` with an integer sets `when`.
  - A malformed or unknown modifier stays in `words`.
- `matchesSearch(thing, search, {byName, filedIn}) -> boolean`.
  - Words match the name or any `aka`, any case.
  - `tag` matches the whole tag, any case.
  - `inName` resolves through `byName` (a lowercased name or aka mapped to an id). It matches if any of the thing's `filed_in`, followed upward through `filedIn(id)`, reaches that id. An unknown name matches nothing.
  - `stub` matches `!!thing.stub`.
  - `when`:
    - a character: `span.from <= when`;
    - an event: `from <= when <= (until ?? from)`;
    - `span === null`: true.
- `sideTree(things, {nest, search, folds, openPath, limit = 10}) -> [{thing, depth, folded, childCount, context, more?}]`.
  - Each thing appears once, nested by `mostPreciseHome` among same-kind things when `nest` is set. A filing loop has no top: each thing in the loop sits at the root.
  - `folds` is a `Set` of folded ids, folded by default. `openPath` is a `Set` of ids forced open.
  - With an active `search`:
    - only matches and their ancestors show, the ancestors with `context: true`;
    - everything shown is unfolded.
  - When more than `limit` children show, a row `{more: {parentId, count}}` follows the first `limit`.
- `groupList(things, {by: 'where'|'tag'|'none', sort: 'name'|'recent'|'connected'|'date', byId}) -> [{key, heading, rows: [thing]}]`.
  - `where` groups by `mostPreciseHome` of any kind, headed "In <name>". The no-home group is "Nowhere", last.
  - `tag` groups by tag, with "Other" last.
  - `none` returns one group with heading `null`.
  - Within a group the sort is:
    - `name`: by name;
    - `recent`: by `changed_rev`, highest first;
    - `connected`: by `connections`, highest first;
    - `date`: by `sort_date`, nulls last.
  - Ties go by name.
- `whereLabel(thing, byId) -> string`: "in Velikoye", or "in Velikoye +1" when it's filed in more than one place, or "" when it's filed nowhere.

- [ ] **Write the failing node checks**, named as below:
  - `parseSearch reads modifiers`: `parseSearch('owl tag:City in:"Night Court" stub when:1020')` equals `{words:'owl', tag:'city', inName:'night court', stub:true, when:1020}`.
  - `parseSearch reads malformed modifiers as words`: `when:abc`, `tag:`, `in:"Night` and `foo:bar` each end up in `words`.
  - `matchesSearch in: follows homes at any depth, any filing`.
  - `matchesSearch when: by kind`.
  - `sideTree folds by default and opens the path`.
  - `sideTree narrows to matches with their parents as context`.
  - `sideTree survives a filing loop`.
  - `sideTree shows ten children then more`.
  - `groupList by where uses a home of any kind`.
  - `groupList sorts recent, connected and date with nulls last`.
  - `whereLabel counts the other places`.
- [ ] Run them and confirm they fail on the missing module.
- [ ] Implement `worldTree.js`.
  - `kindList` in `entryPage.js` stays until Task 3 replaces its one caller. Then remove it and its checks, or keep it if another caller is found.
- [ ] Run the frontend checks and confirm they pass.
- [ ] Commit with the message `feat(worlds-ui): tree, search and list logic`.

### Task 3: The side tree folds, and search narrows it

**Files:** `talemate_frontend/src/components/worlds/WorldTab.vue`; a fold store in `worldTree.js` (`loadFolds(worldId)`, `saveFolds(worldId, folds)`); e2e in a new `tests/e2e/worlds/test_lists.py`.

**Interfaces — Consumes:** `sideTree`, `parseSearch`, `matchesSearch` (Task 2).

**Interfaces — Produces:**
- `loadFolds(worldId) -> {kinds: Set, entries: Set}`. It returns empty sets on any storage error or bad value. `saveFolds` swallows storage errors.

- [ ] **Write the failing tests:**
  - Node check `loadFolds survives bad storage`: storage that throws, and the value `"{bad"`, both give empty sets.
  - E2E `test_side_tree_folds_and_remembers`. Seed Moscavia > Velikoye > Night Court and Moscavia > Kerensk, plus a character. Then:
    - opening the world shows every kind folded;
    - opening Night Court shows Places, Moscavia and Velikoye unfolded, with Kerensk folded and showing its count;
    - folding Places with its ▸ and reloading keeps it folded;
    - clicking the "Places" name opens the kind's page and unfolds it;
    - the "+" opens the kind's page with the prompt focused.
  - E2E `test_side_search_modifiers`:
    - typing `in:Velikoye` shows Night Court with Moscavia and Velikoye as context;
    - `stub` shows only stubs;
    - clearing the search restores the folds.
  - E2E `test_stub_row_one_line`: a stub row has no "not made yet" text, and its `title` includes "not made yet".
- [ ] Run them and confirm they fail.
- [ ] **Implement:**
  - kind chevrons, and the name click and "+" as specified;
  - entry chevrons and the "+ N more" row;
  - the open path computed from `worlds.selectedThingId` on each page change;
  - folds saved per world;
  - a modifier hint under the search box when it's focused ("tag: in: stub when:");
  - nest every kind (`nest: true`).
- [ ] Run the tests and `tests/e2e/worlds -n 4`, and confirm they pass. Take before and after screenshots of the tree, folded and while searching, and send them.
- [ ] Commit with the message `feat(worlds-ui): the side tree folds; search narrows it`.

### Task 4: A kind's page lists its entries

**Files:** create `talemate_frontend/src/components/worlds/KindList.vue`; `WorldTab.vue` (it replaces the "Pick one of…" hint under `CreateBox`); e2e in `test_lists.py`.

**Interfaces — Consumes:** `groupList`, `whereLabel`, `parseSearch` and `matchesSearch` (Task 2); Task 1's fields; the side search's `query` (passed as a prop).

- [ ] **Write the failing e2e test** `test_kind_page_lists_entries`:
  - The Places page shows, under the create box, the heading "All places · 3", grouped by where by default.
  - A row reads "Night Court · in Velikoye — Where the Tsar's quiet business is done.", and the "· in Velikoye" sits within 40 px of the name's right edge.
  - Switching to "tag" shows "City · 2" then "Other".
  - Switching sort to "recent", then editing Kerensk's tag, puts Kerensk first.
  - A reload keeps "tag" and "recent".
  - Clicking a row opens the entry.
  - Typing `stub` in the side search filters this list too.
- [ ] Run it and confirm it fails.
- [ ] Implement `KindList.vue`. The default grouping is "where" for places and "tag" for every other kind; the default sort is name. Group and sort are `v-btn-toggle`s right after the heading. Rows use `whereLabel` and the line, cut with an ellipsis. Group and sort are saved per kind in `localStorage`, behind try/catch.
- [ ] Run the tests and `tests/e2e/worlds -n 4`, and confirm they pass. Take before and after screenshots of the Places and Characters pages, and send them.
- [ ] Commit with the message `feat(worlds-ui): a kind's page lists its entries`.

### Task 5: Connected sorts by kind

**Files:** `src/talemate/server/worlds.py` (`_connected_out` ~1801, or the grouping in `filing.connected`, whichever builds the order); tests in `tests/server/test_worlds_plugin.py`.

- [ ] **Write the failing test** `test_connected_groups_and_rows_by_kind`. Velikoye holds:
  - lore "Tsar's Edict", tag "noble";
  - character "Count Orlov", tag "noble";
  - place "The Ice Market", tag "market";
  - character "Ivan", tag "merchant";
  - untagged lore "Old Song".

  Assert:
  - the group order is merchant (characters only), noble (it holds a character), market (place), then Other;
  - within noble, Count Orlov comes before Tsar's Edict.
- [ ] Run it and confirm it fails.
- [ ] Implement:
  - order groups by the lowest `KIND_ORDER` index of their rows, then by heading, with Other last;
  - order rows by kind index, then by name.
  - Keep the Python kind order as one constant, matching Task 2's.
- [ ] Run `tests/server` and the Connected e2e tests in `test_filing.py`, and confirm they pass. Take a screenshot of Connected, and send it.
- [ ] Commit with the message `feat(worlds): Connected sorts by kind`.

### Task 6: One pinned error message

**Files:**
- create `talemate_frontend/src/components/worlds/WorldError.vue`;
- `WorldTab.vue` and `WorldsHome.vue` (the alerts go);
- `stores/worlds.js`, where an error carries `errorCount`; setting the same text again increments it; and it clears on `openWorld` or a different world, and on leaving the Worlds screens;
- `TalemateApp.vue`, where the snackbar skips a worlds `operation_done` error;
- `NameHighlightInput.vue`, which calls `grow()` from a `ResizeObserver` on its box;
- e2e in `test_lists.py`.

- [ ] **Write the failing tests:**
  - E2E `test_error_pinned_counts_and_clears`:
    - trigger a refused action twice (`make_stub_from_text` on a selection that cuts a link), after scrolling the page down;
    - the `world-error` element is in the viewport, reads the message with "×2", and has a "Copy" button;
    - no `.v-snackbar` with the same text is shown;
    - it stays visible after waiting 4 s;
    - switching to another world closes it.
  - E2E `test_prompt_box_survives_an_error`: with an error showing, switch world and open a kind. The create box's textarea is at least 40 px tall.
  - Node check `the same error again counts`.
- [ ] Run them and confirm they fail.
- [ ] Implement. Pin the message with `position: fixed`, top centre, under the app bar. Its text is selectable, it has a copy button and a × to close. Keep `MergeDialog`'s inline error.
- [ ] Run the tests, the frontend checks and `tests/e2e -n 4`, and confirm they pass. Take a screenshot of the message, and send it.
- [ ] Commit with the message `feat(worlds-ui): one pinned error message`.

### Task 7: Offers dim; dropped rows strike through

**Files:** `talemate_frontend/src/components/worlds/SuggestionRow.vue` (and `FactLine.vue` if it draws its own dropped style); e2e in `test_lists.py` or `test_drafts.py`.

**Interfaces — Produces:** `SuggestionRow` records `startedTicked` (the `ticked` it was first drawn with). An unticked row that started unticked gets `.suggestion-offer`: dimmed, with no line-through. An unticked row that started ticked keeps `.suggestion-dropped`.

- [ ] **Write the failing e2e test** `test_offer_rows_dim_dropped_rows_strike`. On a draft with a "Could move here" row and a ticked fact:
  - the offer's text has `text-decoration-line: none` and an opacity below 1;
  - tick it, then untick it: still no line-through;
  - untick the fact: line-through.
- [ ] Run it and confirm it fails.
- [ ] Implement it in `SuggestionRow`, once. Check that `FactLine`'s draft rows follow the same rule (the "started ticked" fact rows).
- [ ] Run the tests and `tests/e2e/worlds -n 4`, and confirm they pass. Take before and after screenshots of a draft's offers, and send them.
- [ ] Commit with the message `feat(worlds-ui): offers dim, dropped rows strike through`.

### Task 8: The small fixes

**Files:** `PreviewStubs.vue` (~50, the "same as" select); `ConnectedGroup.vue` (~7, the Other heading's `title`); e2e.

- [ ] **Write the failing e2e tests:**
  - `test_same_as_has_room`: the "same as" select's top sits at least 6 px below the kind select's bottom.
  - `test_other_tip_on_heading_only`: hovering a row in Other shows no "Drop" tooltip, and hovering the heading does.
- [ ] Run them and confirm they fail.
- [ ] Implement. Move the `title` from the group wrapper to its heading.
- [ ] Run the tests and confirm they pass. Take screenshots, and send them.
- [ ] Commit with the message `fix(worlds-ui): New stubs padding, Other's tooltip on its heading`.

### Task 9: Verification

- [ ] Grep `tests/ai` for every changed id or label.
- [ ] Run the plain suite, the frontend checks, the build and `tests/e2e -n 4`.
- [ ] Write the acceptance checklist, `docs/superpowers/probes/2026-10-27-polish-5-acceptance.md`, and commit it.
- [ ] Run the final whole-branch review (most capable model), then do one fix pass.
