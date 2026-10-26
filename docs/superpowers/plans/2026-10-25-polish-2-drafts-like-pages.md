# Polish 2: Drafts Edit Like Saved Pages — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A draft shows and edits everything its saved page does, using the same components. Race and mix drafts get the entry's full width. The In section becomes a clear section above Facts, on drafts and saved pages alike.

**Architecture:**
- **Two-mode components.** The saved-page components `ThingNumbers`, `ThingAka` and `EntryIn` become two-mode: a value comes in and a change goes out. ThingPage feeds them either the saved entry (writing through the store's `set_field` and filing actions) or the draft's `edited` state (writing through `editDraft`).
- **Server.** The draft payload resolves inherited numbers for heritage drafts. `PreviewFiling` gains `show_under`, written by accept.
- **Layout.** Layout moves happen in `ThingPage.vue`. `FactLine` gains an action mode so inherited facts and "+ Add facts" rows can share it.

**Tech Stack:** Vue 3, Vuetify 3, Pinia (`talemate_frontend`); Python 3.11 and pydantic (`src/talemate`); pytest; Playwright e2e (`tests/e2e`); node checks (`talemate_frontend/checks/worlds.check.mjs`).

**Spec:** `docs/superpowers/specs/2026-10-25-polish-2-drafts-like-pages-design.md`

## Global Constraints

- **Owner rule 1, controls sit next to what they act on.** Right-align a row's or heading's controls only in an area half the screen wide or less.
- **Owner rule 2, things that look the same are one component.** Never write a draft copy of a saved-page piece.
- **Owner rule 3, the screen the owner approved is the model.** Saved pages must look and behave exactly as before, apart from the In section's move and new layout (Task 6). Check this with before and after screenshots at 1280 and 1920 px, compared pixel for pixel wherever nothing was meant to change.
- **Nothing is written before Accept.** Every draft edit goes through `editDraft` and the draft's `edited` state.
- **The In section's copy:**
  - the heading is "In", with "+ In…" at its right;
  - rows read role first, as in "located in Novgrad", or just the place's name when there's no role;
  - the subtitle "the AI's suggestions come unticked, yours ticked" is removed;
  - the AI's suggested filings still arrive unticked.
- **Keep existing `data-testid`s** wherever the element survives. Grep `tests/e2e` and `tests/ai` for any id that changes.
- **Theme tokens only** for colour.
- **Running things:** use `guix shell -m manifest.scm -- …` from the repo root, and always `uv run --no-sync`.
  - Plain suite: `uv run --no-sync pytest`, with 0 failures.
  - Browser tests: `pytest tests/e2e -m e2e -n 4`, never more than 4 workers. While iterating, run only `tests/e2e/worlds`. Check for leftover apps first.
  - Never run `tests/ai`.

## Review Focus

1. **A draft edit to numbers or other names is lost on Regenerate or a version switch.** The owner expects their edits to stay with the version they made them on, as with ticks. Pinned in Task 2, the node check `draft numbers and other names are kept per version`.
2. **A race draft's inherited numbers.** An unset lifespan shows the species' value, dimmed, as on a saved race page. Pinned in Task 1, `test_heritage_draft_payload_inherits_numbers`.
3. **Show-under set on a draft names a tag that's gone or empty by accept time.** It's written only if valid (`edit_filing`'s checks); otherwise it's dropped with a note. Pinned in Task 1, `test_draft_filing_show_under_checked_at_accept`.
4. **The saved page changes where it shouldn't.** Screenshot diffs in Tasks 6, 7 and 8; the e2e suite stays green.
5. **"+ Add fact" on a draft is written before Accept.** It must only join `edited.facts`. Pinned in Task 4, the e2e test `test_draft_add_fact_by_hand_writes_on_accept`.

---

## File Structure

- **Server**
  - `src/talemate/server/worlds.py`: the draft payload's `numbers` (around lines 2915-2935) and the accept filing path.
  - `src/talemate/worldplay/create.py`: `PreviewFiling.show_under`, and the filing writer near `Filing(` (around line 3986).
- **Frontend** (`talemate_frontend/src/`)
  - `components/worlds/ThingNumbers.vue`, `ThingAka.vue`, `EntryIn.vue`: become two-mode.
  - `components/worlds/ThingPage.vue`: wiring, layout moves, "+ Add fact" on drafts.
  - `components/worlds/FactLine.vue`: gains an `actions` mode.
  - `components/worlds/ThingInherited.vue` and `EntryAddFacts.vue`: use `FactLine`.
  - `components/worlds/HeritageSections.vue`: unchanged inside; it is moved by ThingPage.
  - `stores/worlds.js`: the preview-lag fix.
  - `components/worlds/draftPage.js`: pure draft edits for numbers, aka and show-under.
- **Tests**
  - `tests/server/test_worlds_plugin.py`
  - `talemate_frontend/checks/worlds.check.mjs`
  - `tests/e2e/worlds/test_drafts.py`, `test_heritage_create.py`, `test_filing.py`

---

### Task 1: Server — inherited numbers on heritage drafts; show-under on draft filings

**Files:**
- Modify: `src/talemate/server/worlds.py` (the draft payload's `numbers`, around line 2925)
- Modify: `src/talemate/worldplay/create.py` (`PreviewFiling` around line 391; the filing writer around line 3986)
- Test: `tests/server/test_worlds_plugin.py`

**Interfaces:**
- **Produces:**
  - **Numbers on a heritage draft.** For a race or mix preview, the draft payload's `numbers` is what the saved page would show: own values from `preview.fields` (`lifespan`, `adult_age`, `measures`), and otherwise the values inherited along its parents (the species for a race; both parents for a mix), resolved as `heritage.numbers` resolves them for a saved entry. A species draft shows its own values only.
  - **A new field:** `PreviewFiling.show_under: str | None = None`.
  - **Accept writes it.** On accept, a ticked row's `show_under` is written onto the new `Filing`, but only if `edit_filing` would accept it (a tag in use, or one of the target's groups). Otherwise it's dropped with the note `shows under "<tag>" isn't a group on <target>, so it shows under its own tag`.

- [ ] **Step 1: Write failing tests:**
  - `test_heritage_draft_payload_inherits_numbers`:
    - Set up a species with lifespan 80 and adult_age 20.
    - Preview a race of it with no numbers. The draft's `numbers.lifespan == 80` and `adult_age == 20`.
    - Set `preview.fields.lifespan = 60` and render it (`draft_render`). The draft's `numbers.lifespan == 60`.
  - `test_draft_filing_show_under_written_on_accept`: a draft with a ticked filing into a town whose page has a "Natives" group, with `show_under="native"`. After accept, `filings_of(...)` shows that filing's `show_under == "native"`.
  - `test_draft_filing_show_under_checked_at_accept`: an invalid `show_under` is not written, and the reply's notes contain `isn't a group on`.
- [ ] **Step 2: Run** `uv run --no-sync pytest tests/server/test_worlds_plugin.py -k "heritage_draft_payload or show_under" -v` and confirm it fails.
- [ ] **Step 3: Implement.** Find how `add_filing` / `edit_filing` check `show_under` (around worlds.py:3478 and 3836) and reuse that check rather than writing it again.
- [ ] **Step 4: Run it and confirm it passes,** then the plain suite.
- [ ] **Step 5: Commit** with the message `feat(worlds): heritage drafts inherit numbers; draft filings show under a group`.

---

### Task 2: Draft edits for numbers, other names and show-under; the preview-lag fix

**Files:**
- Modify: `talemate_frontend/src/components/worlds/draftPage.js`
- Modify: `talemate_frontend/src/stores/worlds.js` (add `numbers`/`aka`/`filings` to `RENDERED_KEYS` if they change what the server renders; the `operation_done` error branch around line 2469)
- Test: `talemate_frontend/checks/worlds.check.mjs`

**Interfaces:**
- **Produces, in `draftPage.js` (pure):**
  - `setDraftNumber(edited, field, value) -> {fields}`, where `field` is one of `lifespan`, `adult_age`, `measures`, and `null` clears the value.
  - `setDraftAka(edited, aka) -> {aka}`, which reuses the list helpers `akaAdded`, `akaChanged`, `akaEveryday` and `akaRemoved` from `stores/worlds.js`.
  - `setFilingShowUnder(edited, key, tag) -> {filings}`, where `key` is `filingKey(row)` and `tag` may be `null`.
- **The preview-lag fix.** In the `operation_done` error branch, after a refused `accept_preview`, call `this.renderDraft()` when `draft.edited !== draft.base`.

- [ ] **Step 1: Write failing node checks:**
  - `draft numbers set and clear`;
  - `draft aka edits use the saved page's helpers`;
  - `filing show-under on a draft`;
  - `draft numbers and other names are kept per version`: set lifespan on version 1, switch to 2 and back, and the value is still there (the existing `draftEdits` keeping covers it, so the check pins it);
  - `a refused accept renders the draft again`.
- [ ] **Step 2: Run** `uv run --no-sync pytest tests/dev/test_frontend_checks.py -v` and confirm it fails.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run it and confirm it passes.**
- [ ] **Step 5: Commit** with the message `feat(worlds-ui): draft edits for numbers, other names, show-under; re-render after a refused accept`.

---

### Task 3: ThingNumbers and ThingAka edit drafts too

**Files:**
- Modify: `talemate_frontend/src/components/worlds/ThingNumbers.vue`, `ThingAka.vue`, `ThingPage.vue` (around lines 259-260: drop the `v-if="!draft"` guard around them; pass the props)
- Test: `tests/e2e/worlds/test_heritage_create.py`, `test_drafts.py`

**Interfaces:**
- **Consumes:** Task 1's draft `numbers`; Task 2's `setDraftNumber` and `setDraftAka`.
- **Produces:**
  - **`ThingNumbers`** takes the props `fields: Object` (own values), `numbers: Object` (resolved values) and `busy: Boolean`, and emits `set(field, value)`.
    - On a saved page, ThingPage passes `thing.fields` and `thing.numbers`, and `@set` calls `worlds.setField`.
    - On a draft, ThingPage passes `edited.fields` and `worlds.draft.page.numbers` (or the rendered page's), and `@set` calls `edit(setDraftNumber(...))`.
    - The "wait for the reply" watcher it has today applies only in saved mode.
  - **`ThingAka`** takes the props `aka: Array`, `mainName: String` and `busy: Boolean`, and emits `save(aka)`.
    - On a saved page, `@save` calls `worlds.setAka`.
    - On a draft, `@save` calls `edit(setDraftAka(edited, $event))`.
  - **The draft header's removable "also" chips** become the same read-only "usually called / also" line the saved page shows, because editing now lives in the Other names section.
  - **Shown for** all heritage kinds (species, race and mix), as `isHeritage` already decides.

- [ ] **Step 1: Write failing e2e tests:**
  - `test_race_draft_edits_numbers_and_other_names`:
    - On a race draft under a species with lifespan 80, Lifespan shows 80, dimmed as inherited.
    - Set Lifespan to 60, add the other name "Snowy Owls" as common, and Accept.
    - The saved race shows Lifespan 60 and "Snowy Owls".
  - `test_species_draft_edits_numbers`: a species draft's Adult at can be set before Accept.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.** The saved page must be visually unchanged: take screenshots of a species page before and after at 1280 and 1920 px, and they must be identical.
- [ ] **Step 4: Run** `tests/e2e/worlds` and confirm it passes.
- [ ] **Step 5: Commit** with the message `feat(worlds-ui): drafts edit numbers and other names with the saved page's editors`.

---

### Task 4: "+ Add fact" on drafts

**Files:**
- Modify: `talemate_frontend/src/components/worlds/ThingPage.vue` (around lines 270-271: the `v-if="!draft"` on "Add fact"; `startAdd` / `saveForm` / the draft form path)
- Modify: `talemate_frontend/src/components/worlds/draftPage.js`: `addDraftFact(edited, {category, text, valid_from, valid_until}) -> {facts}`, a ticked fact with `local: true`, its category from `categoryFor`
- Test: `tests/e2e/worlds/test_drafts.py`, plus a node check for `addDraftFact`

- [ ] **Step 1: Write failing tests:**
  - **Node check:** `addDraftFact appends a ticked local fact`.
  - **E2e, `test_draft_add_fact_by_hand_writes_on_accept`:**
    - On a page draft, "Add fact" opens the same form as on a saved page (`ThingFactForm`).
    - Save "It drills at dawn.". The fact appears as a ticked draft fact row, and the world head is unchanged (no `add_fact` was sent).
    - Accept. The saved page has the fact.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.** Use the same button as the saved page, in the same place in the Facts heading.
- [ ] **Step 4: Run them and confirm they pass,** together with `tests/e2e/worlds/test_drafts.py`.
- [ ] **Step 5: Commit** with the message `feat(worlds-ui): "Add fact" by hand on drafts`.

---

### Task 5: FactLine action modes; inherited facts and "+ Add facts" rows use it

**Files:**
- Modify: `talemate_frontend/src/components/worlds/FactLine.vue`: a prop `actions: String`, which is `'full'` (the default: ⋯, edit and end, as now), `'override'` (an "Override" button in that place, emitting `override`) or `'none'`
- Modify: `ThingInherited.vue` (use `FactLine` with `actions="override"`; keep the strike-through for an overridden fact and the source chip in its own extras), `EntryAddFacts.vue` (rows use `FactLine` with `actions="none"` inside their SuggestionRow)
- Test: `tests/e2e/worlds/test_heritage_pages.py` (inherited facts), `test_drafts.py`

- [ ] **Step 1: Write a failing e2e assertion.** On a race page, an inherited fact's text, category chip and date sit in the same positions as an own fact's. Compare `boundingBox().x` of the chip in both rows, and `actions="override"` shows the Override button.
- [ ] **Step 2: Run it and confirm it fails.**
- [ ] **Step 3: Implement.** The saved-page and page-draft fact rows must stay pixel-identical: screenshot a saved page and a page draft before and after, and diff them.
- [ ] **Step 4: Run** `tests/e2e/worlds` and confirm it passes.
- [ ] **Step 5: Commit** with the message `refactor(worlds-ui): inherited facts and added-fact rows share FactLine`.

---

### Task 6: The In section

**Files:**
- Modify: `talemate_frontend/src/components/worlds/EntryIn.vue` (rebuilt), `ThingPage.vue` (move `EntryIn` from around line 187 into the left column just above the Facts heading; move `SameThingAsk` from around line 196 to directly under the name row)
- Test: `tests/e2e/worlds/test_filing.py`, `test_drafts.py`

**Interfaces:**
- **Consumes:** Task 2's `setFilingShowUnder`.
- **The layout,** matching the approved mockup `.superpowers/brainstorm/13741-1792986504/content/in-section.html`:
  - **Heading:** "In", in the same style as the "Facts" heading (`text-overline`, muted), with "+ In…" at the heading's right (the column is half-width).
  - **Rows:**
    - The text is the same size as a fact (`text-body-2` or whatever FactLine's text uses; match it).
    - The text reads `<role> <target link>`, or just `<target link>` when there's no role.
    - It's followed by its date, the show-under chip, and on a draft its tick at the front.
    - Edit and delete sit at the row's right. Rows are separated like fact rows.
  - **No subtitle.**
- **The show-under `TagChip`** shows on drafts too, wired to `setFilingShowUnder`, in rows and in the "+ In" form.
- **Saved pages and drafts use this one component;** draft mode adds only the tick.

- [ ] **Step 1: Write failing e2e tests:**
  - `test_in_section_above_facts`:
    - On a saved page and on a draft, the In heading sits above the Facts heading (`boundingBox().y`) and inside the left column (`x` + `width` ≤ the Facts column's right edge).
    - "+ In…" is in the In heading's row.
    - A row's text reads "located in Novgrad".
    - The page has no "AI's suggestions" text.
  - `test_draft_in_row_show_under`: set "shows under" on a draft In row, then Accept. The filing has it (check through the saved page's chip).
  - **Update existing tests that select In rows** (`in-*` test ids; grep).
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.** Take saved-page screenshots before and after at 1280 and 1920 px. Only the In section's move and look may differ. Send the after shots in the report.
- [ ] **Step 4: Run** `tests/e2e/worlds` and confirm it passes.
- [ ] **Step 5: Commit** with the message `feat(worlds-ui): In is a section above Facts, on drafts and saved pages`.

---

### Task 7: Races and Mixes span the entry's width

**Files:**
- Modify: `talemate_frontend/src/components/worlds/ThingPage.vue` (move `HeritageSections` from the left column, around line 379, to directly after the two-column `v-row`, before `EntryConnected`)
- Test: `tests/e2e/worlds/test_heritage_create.py`

- [ ] **Step 1: Write a failing e2e assertion.** In `test_new_race_and_mix_from_species_page`, the race draft's width equals the species page's content width (± 2 px), and the race draft's Description column starts at the same `x` as the species page's Description column (± 2 px).
- [ ] **Step 2: Run it and confirm it fails.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `tests/e2e/worlds` and confirm it passes. Screenshot a species page with a race draft open, at 1280 and 1920 px.
- [ ] **Step 5: Commit** with the message `feat(worlds-ui): race and mix drafts span the entry's width`.

---

### Task 8: Whole-branch verification

- [ ] **Step 1:** Grep `tests/ai` for every test id and store action that changed. Fix the hits; don't run the AI tests.
- [ ] **Step 2:** Run the plain suite (0 failures), `tests/e2e -m e2e -n 4` and `ruff check` / `ruff format --check` on the changed Python.
- [ ] **Step 3:** Write the owner's acceptance checklist to `docs/superpowers/probes/2026-10-26-polish-2-acceptance.md`, in the style of the polish-1 one: try each goal in the spec, plus a "Changed on purpose" list. Collect the after screenshots in the scratchpad for the owner. Commit with the message `docs(polish-2): acceptance checklist`.
