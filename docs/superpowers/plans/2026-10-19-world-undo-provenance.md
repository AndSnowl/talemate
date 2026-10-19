# World Undo Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make undo by source exact. Every undo records which revisions it reverses and which row each restored copy came from, and the planner follows those links instead of matching content.

**Architecture:** This uses the reversing-entry pattern, the same one as accounting reversals and `git revert`, on top of the existing append-only, two-clock store in `src/talemate/world/`.
- An undo revision records the revisions it reverses in a new `revision_reverts` table.
- Every row an undo writes as a restored copy records the `row_id` of the row it copies, in a new `restored_from` column.
- Whether a change is "in effect" is worked out from those links. Content matching (`_follow`, `_follow_added` in `undo.py`) is removed.

**Tech stack:** Python 3.11+, stdlib `sqlite3`, pydantic 2, pytest.

**Spec:** `docs/superpowers/specs/2026-10-18-fantasymate-world-data-model-design.md` ("Undo by source": undo reverts only what it needs to, and anything changed again afterwards is listed for the owner instead of being reverted silently).

**Background:** this closes the residual finding F4 from the world-store plan. Its ledger is in the main checkout at `.superpowers/sdd/2026-10-18-fantasymate-world-store/progress.md`. Content matching let a re-undo silently revert an unrelated later change, whenever another undo had restored identical content into the same slot.

## Global Constraints

- **Running things on Guix.** Run everything through `guix shell -m manifest.scm -- …` from the worktree root, and always use `uv run --no-sync`. About 141 failures in the plain suite are environment-only (NLTK), and they are not regressions. The baseline on `main` (e0db245) is 141 failed / 6513 passed.
- **Schema.** Change schema version 1 in place, so `SCHEMA_VERSION` stays 1. No world exists outside tests yet.
- **Rows are never updated in place.** Retiring a row sets `rev_removed` only.
- **The existing rulings hold**, with R5 now made exact:
  - **R5:** re-undoing an already-undone revision is a quiet no-op.
  - **R6:** a thing created in the targets that has later outside rows stays, with one conflict.
  - **F1:** `"referenced in a later revision"` keeps a thing that is referenced later.

## Review Focus

1. **Re-undo after an unrelated undo restored identical content** must not change anything. This is the reviewer's field case and fact case:
   - P;
   - T sets "A";
   - undo(T);
   - a manual edit sets "A";
   - N sets "C";
   - undo(N);
   - undo(T) must give `undo_rev is None` and leave the value "A".
2. **Two undos of different targets restoring into one slot** must not be confused for each other.
3. **A manual correction back to the old value after a redo** gives a CHANGED_LATER conflict, with no state change.
4. **A reference brought back by an undo** blocks un-creating the thing it references, when the original reference came from outside the targets.
5. **Undo, then redo, then undo again** returns the touched slots to their state before the target, for facts, fields and things.

---

### Task 1: Reversal links and link-based planning

**Files:**
- Modify: `src/talemate/world/schema.py`, `src/talemate/world/undo.py`, `src/talemate/world/store.py` (`RevisionInfo`, `World.revisions`)
- Test: `tests/world/test_undo.py`, `tests/world/test_invariants.py`

**Interfaces:**
- **Schema (version 1, in place):**
  - a new table `revision_reverts(undo_rev INTEGER NOT NULL REFERENCES revisions, target_rev INTEGER NOT NULL REFERENCES revisions, PRIMARY KEY (undo_rev, target_rev))`;
  - a new nullable column `restored_from INTEGER` on `things`, `field_values` and `facts`. It holds the `row_id`, in the same table, of the row this one is a copy of. It is NULL for every normal write.
- **`RevisionInfo`** gains `reverts: list[int]`: the target revs for an undo revision, `[]` otherwise. `World.revisions()` fills it in.
- **`undo_revisions` / `World.undo`:** the signatures and the `UndoReport` / `UndoConflict` shapes don't change.
  - The undo revision writes one `revision_reverts` row per target rev.
  - Every restored copy gets `restored_from` set.

**Planning rules.** Define two things first:
- **The origin of a row:** follow `restored_from` until it is NULL.
- **A row's current copy:** a live row in the same table whose `restored_from` chain reaches it, or the row itself when it's live.

The rules:
1. **A row the targets added** (`rev_added` in the targets). Take its current copy.
   - If there is no live copy, the change is already reverted. Skip it quietly (R5, exact).
   - If the live copy is the row itself, or a copy that an undo added, retire that live copy, unless the slot was changed later by a non-undo revision outside the targets. In that case, report CHANGED_LATER as today.
2. **A row the targets retired** (`rev_removed` in the targets, `rev_added` not in them).
   - If a live row whose origin is the same as this row's origin exists, it has already been restored. Skip it quietly.
   - Otherwise, apply today's restore and conflict logic, and write the copy with `restored_from = row_id`.
3. **Things follow the same two rules**, keeping today's per-id grouping and R6.
4. **The referenced-later check (F1)** counts a live reference row whose origin was added by a non-undo revision outside the targets. That makes a reference brought back by an undo block un-creation (Review Focus 4).
5. **Remove the content-matching helpers** (`_follow`, `_follow_added` and their content comparisons). No planning decision may compare text or values.

- [ ] **Step 1: Write the failing tests** in `tests/world/test_undo.py`:
  - `test_reundo_after_unrelated_restore_of_same_value_is_noop`: the field case from Review Focus 1. The result is `undo_rev is None`, and the name stays "A".
  - `test_reundo_after_unrelated_restore_of_same_fact_text_is_noop`: the same sequence with `correct_fact` texts c → d → (manual) d → e.
  - `test_two_undos_into_one_slot_not_confused`: Review Focus 2.
    - U1 = undo(T);
    - M sets d;
    - N;
    - U2 = undo(N) restores d;
    - undo([T]) is a no-op, and d stays.
  - `test_manual_revert_after_redo_is_conflict`: Review Focus 3. The result has one conflict and no state change.
  - `test_undo_restored_reference_blocks_uncreation`: Review Focus 4.
    - T creates Maren;
    - F adds Oskar's referencing fact;
    - undo([T, F]);
    - redo it;
    - undo([T]) gives one `"referenced in a later revision"` conflict, and Maren stays live.
  - `test_undo_records_reversal_links`: after `undo([2, 3])`, `world.revisions()` shows `reverts == [2, 3]` on the undo revision, and every restored row has a non-NULL `restored_from`. Check that with a raw read.
- [ ] **Step 2: Run them to make sure they fail**
  Run: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/world/test_undo.py -v -n0`
  Expected: at least the first four FAIL on the current content-matching code.
- [ ] **Step 3: Implement the schema change and link-based planning;** remove the content matching.
- [ ] **Step 4: Extend `tests/world/test_invariants.py`.**
  - Add the operation "manual write of a value some earlier revision wrote" to the random mix, so identical-content histories show up.
  - Add the property: "re-undoing a revision that's already undone changes no live row".
  - Keep the run at a few seconds.
- [ ] **Step 5: Run the tests to make sure they pass.**
  Run: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/world -n0`, then the full plain suite.
  Expected: everything in `tests/world` passes (the existing undo tests unchanged, apart from mechanical updates for the new columns), and the full suite shows only the known 141.
- [ ] **Step 6: Run ruff** (`ruff check` and `ruff format --check`) on `src/talemate/world tests/world`. Expected: clean.
- [ ] **Step 7: Commit** with the message `fix(world): undo follows reversal links instead of matching content`.
