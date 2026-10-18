# Culture Import and Skill Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the problems found when the `culture-design` skill was run end to end overnight on 2026-10-18:
- Place shares drift when a culture is re-imported.
- The validator accepts common mistakes without saying anything.
- The skill's instructions have gaps.

**Architecture:** These are small changes to existing feature files only. They touch `src/talemate/cultures/exchange.py` (import rules), `src/talemate/cultures/cli.py` (validation warnings), `src/talemate/cultures/generator.py` (an optional lint helper), and the skill's Markdown. No core files change.

**Tech Stack:** Python 3.11, pydantic 2, pytest, run through `guix shell -m manifest.scm -- uv run --no-sync …`.

**Evidence:** /tmp/claude-1000/-home-skeleton-Projects-Web-talemate/0ddab8b2-7e3a-438e-af8b-816df8d51f0a/scratchpad/skill-eval/REPORT.md, plus the files and experiments in the same folder.

## Global Constraints

- Only these files change:
  - `src/talemate/cultures/exchange.py`
  - `src/talemate/cultures/cli.py`
  - `src/talemate/cultures/generator.py`
  - `.claude/skills/culture-design/SKILL.md`
  - `.claude/skills/culture-design/reference/rule-syntax.md`
  - their tests under `tests/cultures/`
- Re-import still never deletes owner data. That covers glossary entries, places and play additions.
- Every new check is a **warning** shown in the import preview and printed by `cli validate`. None of them is an error, except where a task says so. A file that was valid yesterday must still import.

## Review Focus

1. **Re-importing an unchanged file twice in a row** must leave every place's shares exactly as they were, and the preview must list no share changes. (Task 1: `test_reimport_unchanged_file_is_idempotent`)
2. **Import order** must not change the final shares of a place when each culture's file is imported once. (Task 1: `test_import_order_independent_for_new_shares`)

---

### Task 1: Re-imports never move an existing share

**Files:**
- Modify: `src/talemate/cultures/exchange.py` (the places merge in `apply_import` and the `share_changes` computation in `preview_import`)
- Test: `tests/cultures/test_exchange.py`

**The rule.** When a file's place matches an existing place:
- If the importing culture **already has a share** there, keep the current share. Don't call `set_share`. When the file declares a different value, the preview gains a note in `warnings`: `"<Place>: keeping <Culture> at <current>% (file says <file>%) — adjust it in Places & regions"`.
- If the importing culture **has no share** there yet, use `set_share(places, place_id, culture_id, file_share)` as today (other cultures scale to fill the rest).
- If the culture would be **alone** at the place, and the file's share is not 100, add a preview warning: `"<Place>: <Culture> is the only culture here, so it will be 100% (file says <n>%)"`. The share is still stored as 100, because the invariant is that shares sum to 100.
- `share_changes` lists only real changes under this rule.

- [ ] **Step 1: Write the failing tests:**
  - `test_reimport_unchanged_file_is_idempotent`: import Taelrik, then Vaskari (Dhunmouth 15%), then re-import both unchanged. The shares are identical after every step, and the second preview of each has `share_changes == []`.
  - `test_import_order_independent_for_new_shares`: import Taelrik then Vaskari into one store, and Vaskari then Taelrik into another. Each culture is new at Dhunmouth in its first import, so compare the final Dhunmouth shares between the two stores and document the expected values in the test. Under the rule, order still matters when both are new. So assert the weaker property: re-importing either file afterwards changes nothing. Name the test to match what it checks.
  - `test_sole_culture_warns_when_file_share_not_100`
  - `test_reimport_different_share_keeps_current_and_warns`
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/cultures/test_exchange.py -n0 -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement the rule** in `apply_import` and `preview_import`, sharing one helper so the preview and the apply always agree.
- [ ] **Step 4: Run** `tests/cultures` and `tests/server/test_cultures_plugin.py`. Expected: PASS. Update an existing test only where it asserted the old drift behaviour, and say so in the report.
- [ ] **Step 5: Commit** with the message `fix(cultures): re-imports never move an existing share`.

---

### Task 2: Validation warnings for common mistakes

**Files:**
- Modify: `src/talemate/cultures/exchange.py`: a `lint_culture_file(raw: dict, file: CultureFile) -> list[str]` helper whose warnings are added to `ImportPreview.warnings`.
- Modify: `src/talemate/cultures/cli.py`: `validate` prints every warning as `WARNING: …` and still exits 0.
- Modify: `src/talemate/cultures/generator.py` only if a small helper is needed to list the category letters a pattern uses.
- Test: `tests/cultures/test_exchange.py` and `tests/cultures/test_cli.py` (or wherever the CLI tests live)

**Warnings, with this exact wording:**
- `"Generator '<name>': '<X>' in pattern '<p>' is not a category, so it is written literally"`. Raise it for every uppercase letter in a pattern that isn't a defined category and isn't inside a choice literal the owner obviously meant. Keep it simple: any uppercase letter that isn't a category key.
- `"Unknown field '<path>' is ignored (typo?)"`. Raise it for keys in the raw JSON that the models don't define, at any depth inside `culture`, `language`, `generators[*]`, `glossary[*]` and `places[*]`. Example: `language.generators[0].rejects`.
- `"Language '<name>' is description-only but has generators; they will never be used"`
- `"Glossary '<text>' in <Language> doesn't fit its own generators"`. Raise it for a native glossary entry whose text doesn't `fits()` its own language, when that language has generators.

- [ ] **Step 1: Write the failing tests:** one per warning, using minimal inline culture files. Also check that the Taelrik fixture produces exactly the warnings you'd expect: `Kethrun` doesn't fit. Record that in the test as known.
- [ ] **Step 2: Run** the tests. Expected: FAIL.
- [ ] **Step 3: Implement** the warnings.
- [ ] **Step 4: Run** `tests/cultures`. Expected: PASS.
- [ ] **Step 5: Commit** with the message `feat(cultures): warn about likely culture-file mistakes`.

---

### Task 3: Skill instructions

**Files:**
- Modify: `.claude/skills/culture-design/SKILL.md`
- Modify: `.claude/skills/culture-design/reference/rule-syntax.md`

Apply the evaluation's suggested edits (REPORT.md, "Suggested SKILL.md edits"):
- **Interview.** Add a step covering where the culture lives (places, kind, parent, rough share), which generators to build, seed names already in play, and colour. For several cultures, design and import them in dependency order.
- **Shares.** Explain the Task 1 rule: a culture alone at a place is 100%; a re-import keeps existing shares; the owner adjusts mixed places in Places & regions.
- **Places vs glossary.** Places aren't glossary entries. To let neighbours render a place's name, add a `kind: "place"` glossary entry. A `foreign_renderings` entry whose target culture is imported later is dropped, so import the target first.
- **Unwritable languages.** `true_name` is a bracketed sound description, e.g. `⟨two low hums, one click⟩`. If a neighbour already renders the name, reuse that rendering's `name` exactly as `text`.
- **Sampling.**
  - The ✓ marks are almost always ✓ for a generator's own output, so read the names instead of trusting the marks.
  - An uppercase letter in the middle of a name means an undefined category; `validate` now warns about this.
  - Check `fits` against each neighbour language and aim for about 0%. A one-liner using `talemate.cultures.generator.roll`/`fits` is fine.
- **Commands.** Always use the `guix shell -m manifest.scm -- uv run --no-sync …` form.
- **The example's Kethrun.** Say it is a deliberately irregular legacy name that doesn't fit Taelrik's patterns, and that new native names should fit.

- [ ] **Step 1: Edit both files.** Keep SKILL.md under about 250 lines.
- [ ] **Step 2: Check:** run `guix shell -m manifest.scm -- uv run --no-sync python -m talemate.cultures.cli validate .claude/skills/culture-design/reference/example.culture.json`. Expected: exit 0, with the Kethrun warning shown.
- [ ] **Step 3: Commit** with the message `docs(cultures): skill guidance from the overnight evaluation`. The skill files are force-tracked, so use `git add -f` on exactly these two files.
