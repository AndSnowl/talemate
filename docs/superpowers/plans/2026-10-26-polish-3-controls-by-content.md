# Polish 3: Controls Sit Next to What They Act On — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every heading and row control sits next to what it acts on. The summary heads the left column. Connected and Mentioned in move under "Appears in". "+ Add event…" follows the Timeline's dropdown. "Fill stub X" sits by Accept. "Add fact" never drops an open edit. Any other far-edge controls the sweep finds are fixed.

**Architecture:** Frontend only (`talemate_frontend/src/components/worlds/`). The layout moves happen in `ThingPage.vue`. `SuggestionBar` gains a slot for extra primary-side buttons, so "Fill stub" lives in the bar.

**Tech Stack:** Vue 3, Vuetify 3, Pinia; Playwright e2e (`tests/e2e/worlds`); node checks.

**Spec:** `docs/superpowers/specs/2026-10-26-polish-3-controls-by-content-design.md`

## Global Constraints

- **Owner rule 1:** a title and its control are left-aligned together. Right-align controls only in an area half the screen wide or less.
- **Owner rule 2:** things that look the same are one component, never a copy.
- **Owner rule 3:** the approved screen is the model. Change only what the spec lists, and check everything else against screenshots taken before the change, at 1280 and 1920 px, with a pixel diff. Name every difference in the report.
- **Owner rule 4:** move only the part that needs the room.
- **Copy:**
  - the button reads "Fill stub X";
  - the counts line reads "a stub named X exists";
  - the "Add fact" title while an edit is open reads "save or cancel the edit first".
- **Test ids:** keep every one that survives (`entry-summary`, `fill-stub-instead`, `entry-connected`, `timeline-filter`, `add-event`, …). Grep `tests/e2e` and `tests/ai` for any that change.
- **Theme tokens only** for colour.
- **Running things:** use `guix shell -m manifest.scm -- …` from the repo root, and always `uv run --no-sync`.
  - Browser tests: `pytest tests/e2e -m e2e -n 4`, never more than 4 workers. Check for leftover apps first. `test_tags_rename_merge` is a known flake.
  - Never run `tests/ai`.
- **Screenshots:** take "before" shots from a temporary git worktree at the task's base commit, with a real `pnpm install`, and remove it afterwards. Keep temporary screenshot tests out of `tests/e2e/worlds` when running the whole suite.

## Review Focus

1. **A long summary fact in the narrower column.** It wraps inside the column, and its buttons stay at the column's right, without overflowing. Pinned in Task 1, `test_summary_heads_left_column`, using a two-line summary.
2. **Connected with many groups in the right column.** The groups stack and stay inside the column, and "+ Add" stays at the heading's right. Pinned in Task 2, `test_connected_in_right_column`.
3. **A stub draft whose name matches a stub, with a nested "+ Add facts" open.** "Fill stub X" is disabled with the lock reason, exactly as Accept is. Pinned in Task 4, `test_fill_stub_by_accept`.
4. **Editing the summary fact while clicking "Add fact".** "Add fact" is off as soon as any fact's form is open, including the summary's. Pinned in Task 5, `test_add_fact_off_while_editing`.
5. **A saved page with no summary and no Connected entries.** The column order still reads correctly, with no empty gap. Pinned in Task 1 and Task 2 by asserting the page with no summary is unchanged (pixel diff).

---

### Task 1: The summary row heads the left column

**Files:**
- Modify: `talemate_frontend/src/components/worlds/ThingPage.vue`. Move the `entry-summary` block (around lines 197-212) to be the first child of the left `v-col`, above the field rows, the existence toggle and `ThingNumbers`.
- Test: `tests/e2e/worlds/test_world_tab.py`, or whichever existing e2e file covers the saved entry page's facts (grep for `entry-summary`).

- [ ] **Step 1: Write a failing e2e test, `test_summary_heads_left_column`.**
  - On a saved place with a summary fact two lines long, `entry-summary` sits inside the left column: its x and right edge are within `facts-heading`'s, and its top is above the "Other names" heading.
  - Its buttons (`fact-row` actions) sit within the column's right edge.
  - Its text keeps the `summary-text` class.
  - Clicking its edit button opens `ThingFactForm` in place.
- [ ] **Step 2: Run it and confirm it fails.**
- [ ] **Step 3: Implement.** The row stays the same `FactRow` it is today; only its place changes.
- [ ] **Step 4: Run** `tests/e2e/worlds -m e2e -n 4` and confirm it passes. Take before and after screenshots of a saved place, a character with a born date, and a species, at 1280 and 1920 px. Only the summary's position may differ, plus the content it pushes down. A page with no summary must be pixel-identical.
- [ ] **Step 5: Commit** with the message `feat(worlds-ui): the summary heads the left column`.

---

### Task 2: Connected and Mentioned in move under "Appears in"

**Files:**
- Modify: `ThingPage.vue`. Move `EntryConnected` and `EntryMentionedIn` from the full-width area (around lines 545-546) into the right `v-col`, after Description and Appears in / Referenced in. On drafts, they go after Description. They render on the same conditions as today (`!draft || thing.id`).
- Modify: `EntryConnected.vue` and `ConnectedGroup.vue`. Groups stack one per row in the column, where today they flow in two columns.
- Test: `tests/e2e/worlds/test_filing.py`.

- [ ] **Step 1: Write a failing e2e test, `test_connected_in_right_column`.**
  - On a saved place with 3 or more Connected groups, `entry-connected` sits in the right column: its x is at least the Description heading's x, and its top is below Appears in.
  - Each group's right edge is within the column.
  - The "+ Add" button (`connected-add`) sits on the heading row, inside the column.
  - "Mentioned in" sits directly below Connected.
  - On a stub draft, `entry-connected` sits under the draft's Description.
- [ ] **Step 2: Run it and confirm it fails.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `tests/e2e/worlds -m e2e -n 4` and confirm it passes. Take screenshots before and after, including a stub draft. Only Connected and Mentioned in may move, plus the content shift that follows. Groups that used to sit two to a row now stack.
- [ ] **Step 5: Commit** with the message `feat(worlds-ui): Connected and Mentioned in sit under Appears in`.

---

### Task 3: "+ Add event…" follows the Timeline's dropdown

**Files:**
- Modify: `talemate_frontend/src/components/worlds/EntryTimeline.vue`. Remove the `v-spacer` before `<slot name="actions">` (around line 14), so the actions follow "Events ▾".
- Test: `tests/e2e/worlds/test_filing.py` (the Timeline / "+ Add event" tests).

- [ ] **Step 1: Write a failing assertion.** On a saved page, `add-event`'s left x is within 24 px of `timeline-filter`'s right edge.
- [ ] **Step 2: Run it and confirm it fails.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the worlds e2e tests and confirm they pass. Take screenshots before and after; only the Timeline heading's controls may differ.
- [ ] **Step 5: Commit** with the message `fix(worlds-ui): "+ Add event…" sits by the Timeline dropdown`.

---

### Task 4: "Fill stub X" sits next to Accept

**Files:**
- Modify: `SuggestionBar.vue`. Add a slot `primary-extra`, rendered right before the primary button in both the bar and foot modes.
- Modify: `DraftBar.vue` and `ThingPage.vue`.
  - Remove the `matching-stub` banner (`ThingPage.vue` lines 6-20).
  - Put a button in the bar's `primary-extra` slot, and in the foot bar's: the text "Fill stub X", test id `fill-stub-instead` (bar) and `fill-stub-instead-foot` (foot). It keeps today's click, `acceptDraft(matchingStub.id)`, and today's disabled and title rules (the same as Accept's, including `draftLocked`).
  - The counts line gets the suffix ` · a stub named X exists` while `matchingStub` is set.
- Test: `tests/e2e/worlds/test_drafts.py`. Update the existing tests that use `matching-stub` / `fill-stub-instead`.

**Interfaces:**
- Produces: the `SuggestionBar` slot `primary-extra`.

- [ ] **Step 1: Write a failing e2e test, `test_fill_stub_by_accept`.**
  - A page draft named like an existing stub shows `fill-stub-instead` in the draft bar, its right edge within 16 px of Accept's left edge.
  - There is no `matching-stub` banner, and the counts line contains "a stub named".
  - Clicking it fills the stub, as today's test checks.
  - With a nested "+ Add facts" draft open, it is disabled with the title "write or discard the added facts first".
- [ ] **Step 2: Run it and confirm it fails.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `tests/e2e/worlds -m e2e -n 4` and confirm it passes. Take screenshots of a draft with a matching stub, at 1280 and 1920 px.
- [ ] **Step 5: Commit** with the message `feat(worlds-ui): "Fill stub" sits by Accept`.

---

### Task 5: "Add fact" never drops an open edit

**Files:**
- Modify: `ThingPage.vue` (the "Add fact" button, around line 285, and `startAdd`).
- Test: `tests/e2e/worlds/test_drafts.py` and the saved-page facts tests.

- [ ] **Step 1: Write a failing e2e test, `test_add_fact_off_while_editing`.**
  - On a saved page, open a fact's edit form, then the summary's. "Add fact" is disabled with the title "save or cancel the edit first".
  - Cancel, and it is enabled again.
  - On a page draft, the same holds while a draft fact's form is open.
- [ ] **Step 2: Run it and confirm it fails.**
- [ ] **Step 3: Implement.**
  - The button stays visible, but is disabled while `form && (form.factId || form.index != null)`.
  - `startAdd` returns early in the same state.
- [ ] **Step 4: Run** the worlds e2e tests and confirm they pass.
- [ ] **Step 5: Commit** with the message `fix(worlds-ui): "Add fact" waits for an open edit`.

---

### Task 6: The sweep

**Files:** the components marked **FIX** in the table below.

Sweep results (2026-10-26, read from the markup and the container widths; worlds home screenshotted). The owner can strike any row while reading:

| Component | Element | File | Width | Verdict | Fix |
|---|---|---|---|---|---|
| StubsTab | "Stubs" heading → "show ignored" checkbox | `StubsTab.vue:6` | full-width main area | **FIX** | the checkbox follows the heading |
| TagsTab | tag row (name and count) → rename/merge buttons | `TagsTab.vue:45` | full-width main area | **FIX** | the buttons follow the tag's name and count |
| CreateBox | picker row → Create/Cancel | `CreateBox.vue:78` | full-width main area | **FIX** | Create and Cancel follow the pickers |
| CreateBox | heading ("New {kind}" + chip + ×) | `CreateBox.vue:7-12` | full width | fine as is | already left-aligned |
| DraftBar (SuggestionBar) | version menu → Regenerate/Discard/Accept | `SuggestionBar.vue:44` | full width at the top of a draft | fine as is | the owner approved this bar in area 1 (rule 3); Task 4 adds "Fill stub" beside Accept |
| WorldsHome | Worlds title → refresh; world → New scene/Browse; scene → Play | `WorldsHome.vue:11,76,118` | half-width columns | fine as is | the half-width case |
| Dialogs | ContinueSceneButton, MergeDialog, ThingDeleteDialog, ExpandAskDialog, NewSceneDialog | various | narrow dialogs (480-900 px) | fine as is | narrow |

- [ ] **Step 1:** For each FIX row, write an e2e assertion that the control's left x is within 24 px of its title's right edge, or that it sits within a half-width column. Run them and confirm they fail.
- [ ] **Step 2: Implement** each fix in the smallest way: remove the spacer, or place the element in the existing half-width column.
- [ ] **Step 3: Run** `tests/e2e/worlds -m e2e -n 4` and confirm it passes. Take before and after screenshots of every fixed screen at 1280 and 1920 px, and name the differences.
- [ ] **Step 4: Commit** with the message `fix(worlds-ui): sweep controls next to their titles`.

---

### Task 7: Whole-branch verification

- [ ] **Step 1:** Grep `tests/ai` for every test id that changed. Fix the hits; don't run the AI tests.
- [ ] **Step 2:** Run the plain suite (0 failures), the frontend checks, the build and `tests/e2e -m e2e -n 4`.
- [ ] **Step 3:** Write `docs/superpowers/probes/2026-10-26-polish-3-acceptance.md` in the polish-2 style: one item per spec goal, plus "Changed on purpose" and the after-screenshot folders. Commit with the message `docs(polish-3): acceptance checklist`.
