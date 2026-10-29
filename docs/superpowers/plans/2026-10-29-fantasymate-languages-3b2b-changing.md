# Languages 3b-2b: changing a language — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The owner asks for a change to a language in plain words, from the language's page ("Change it…"), from any entry ("Change a language to fit this…") or from a grammar chapter ("Change…"). It runs in the background on the chosen route and comes back as a review of what changed, which keeps the owner's own edits made meanwhile. Still to fill in shows what's missing, with **Fill in next**.

**Architecture:**
- A change is a make job with `kind: "change"` (or `"fill"`) and a `target_id`. Its brief carries the current language file and the request.
- The finished file comes back with the **base** it was briefed on. The review merges the change onto the language as it is now (a three-way merge: base, change, current), keeps the owner's own edits and words the world uses, and shows the differences by part.
- One panel component (`LanguageChange.vue`) serves the language page's header and any entry page. It reuses the review (`LanguageImport`) and a route-choice component extracted from the Make dialog.

**Tech Stack:** Python 3.11, pydantic, Vue 3 + Vuetify, pytest, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-10-29-fantasymate-languages-3b2-design.md`, section 2 and "How filling in moves along". Approved mockups:
- `docs/superpowers/mockups/2026-10-29-languages-3b2-change-it.html`: the panel and the review;
- `…-make-and-entry.html`, frame 2: from an entry;
- `…-language-chapters.html`: the Language tab in chapters, which superseded the grammar-tab mockup; the Change… link sits on each grammar chapter's card.

3b-2a is merged (94639569).

## Global Constraints

- **Nothing lands silently.** Every change and fill ends in the review, and nothing is written until **Accept the change**. An accepted change is one revision, so undo works on it (spec).
- **Words the world uses never change:** the existing `_keep_used` rule in `talemate/languages/importer.py`. A change that tries to is corrected, and the review lists it under "Kept as they are".
- **The owner's own edits made while a change ran are kept.** Where the owner and the change touched the same word, phrase, name rule or grammar section, the owner's version stays and the review lists it under "Kept your edit" (spec section 2, *my call*).
- **One job at a time** (3b-1). While a make or change runs, the other Make and Change buttons are disabled with the note "Something else is being made or changed; wait for it or cancel it" (spec section 2).
- **Routes:** the same three as 3b-2a, chosen in the panel for that run only (Claude Code with a model box, the agent's model, Copy the brief).
  - A change has no How much.
  - The 3b-1 Claude Code boundary is unchanged: the check by full path outside the work folder, `-P`, folder-only reads.
- **Owner's UI rules:**
  - controls sit right after what they act on;
  - the same look is one component, so the route row is shared by Make and Change;
  - screenshots at 1920×1080 and a small window;
  - never restart an isolated app the owner has used without saving its `worlds/` and `config.yaml` first.
- **No jargon** facing the owner (spec, Anti-goals).
- **Tests:** no real model or Claude Code; use the fake `tests/languages/data/fake-claude` and fixed replies. Commands as in `docs/dev/local-testing.md`.

## Review Focus

1. **The owner edits the language while a change runs**, for example adding a meaning to *kor* that the change also rewrote. The review lists "Kept your edit: kor", the owner's meaning stays, and the rest of the change applies. Task 1 and Task 5.
2. **The language is deleted, or another world opened, while its change runs.** The finished change can't be reviewed. The panel says "The language this was for is gone", and nothing is written. Task 4.
3. **A change that returns a different language name**, or drops its rule sets. The name stays the entry's own (3a). Rule sets the change dropped show as removed in the review, never removed silently. Task 1.
4. **A change asked while the language has no words at all** (a naming style), and Fill in next on a language with nothing missing. The fill button doesn't show when Still to fill in is empty. A change on a naming style works and shows no completeness. Task 3 and Task 5.
5. **Two quick clicks on Accept**, or Accept after the page re-rendered. The change is applied once: the second import finds no difference and writes nothing. Task 4.

---

### Task 1: Merging a change onto the language as it is now

**Files:**
- Create: `src/talemate/languages/changes.py`
- Modify: `src/talemate/languages/importer.py` (`LanguageDiff` grows; `preview_import` and `apply_import` take `base_text`)
- Test: `tests/languages/test_changes.py`

**Interfaces:**
- Produces:
  - `MergeResult(BaseModel)`: `language: Language`, `kept_edits: list[str]` (plain labels such as `"word kor"`, `"phrase greet-1"`, `"grammar Nouns"`, `"name rule people"`, `"how it sounds"`).
  - `merge_change(base: Language, change: Language, current: Language) -> MergeResult`.
    - Parts are matched by key:
      - words by lower-cased `word`;
      - phrases by `id`;
      - grammar sections by lower-cased `title`;
      - generators by `id`;
      - categories by key;
      - `sound`, `syllable_notes` and `flavour` as single values.
    - **For each key:**
      - if the change equals the base, keep current;
      - else if current equals the base, take the change, including additions and removals;
      - else (both changed) keep current, and add the key to `kept_edits`.
    - `name` and `level` always stay current's.
  - `LanguageDiff` gains `grammar_added`, `grammar_changed` and `grammar_removed` (`list[str]`, titles), `sound_before` and `sound_after` (`str | None`, set only when different), `rules_removed: list[str]` (generator names), and `kept_edits: list[str]`.
  - `preview_import(view, text, target_id=None, base_text: str | None = None)`. With `base_text`, the parsed text is merged with `merge_change(base, change, current)` before `_keep_used`, and the diff compares current with the merged result.
  - `apply_import(rev, view, preview, target_id)` is unchanged; the preview already holds the merged file.

- [ ] **Step 1: Write the failing tests:**
  - `test_a_change_applies_where_the_owner_did_nothing` (change adds the word *torg*, alters the phrase *greet*; current equals base; both land);
  - `test_the_owners_edit_is_kept_where_both_changed` (Review Focus 1: base *kor* = [river]; change → [river, road]; current → [river, stream]; the result keeps [river, stream]; `kept_edits == ["word kor"]`);
  - `test_the_owners_new_word_survives_a_change` (current added *sel*; the change didn't know it; *sel* stays);
  - `test_a_removal_in_the_change_lands_only_if_the_owner_left_it_alone`;
  - `test_the_name_stays_the_entrys_own` (Review Focus 3: the change renames the language; the merged name is current's);
  - `test_dropped_rule_sets_show_as_removed` (Review Focus 3: `diff.rules_removed == ["People"]`);
  - `test_grammar_and_sound_differences_are_listed` (a section added, one changed, the sound changed: titles in `grammar_added`/`grammar_changed`, `sound_before`/`sound_after` set);
  - `test_used_words_still_win_over_a_change` (a word naming an entry, which the change redefines, comes out with its old meanings and is listed in `kept_used`).
- [ ] **Step 2:** `… pytest tests/languages/test_changes.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement.** `_keep_used` runs after the merge, on (current, merged).
- [ ] **Step 4:** run `tests/languages tests/server/test_worlds_languages.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(languages): merge a change onto the language as it is now`.

### Task 2: Related entries to fit a change to

**Files:**
- Create: `src/talemate/languages/related.py`
- Modify: `src/talemate/server/worlds.py` (handler `language_related`)
- Test: `tests/languages/test_related.py`, `tests/server/test_worlds_language_make.py`

**Interfaces:**
- Produces:
  - `RelatedEntry(BaseModel)`: `id: str`, `name: str`, `kind: str`, `why: str`.
  - `related_entries(view: WorldView, language_id: str, limit: int = 12) -> list[RelatedEntry]`, in this order, each entry once, at most `limit`:
    1. entries whose own Languages rows name the language: why `"speaks it (official)"`, using the row's role;
    2. entries filed in those: why `"filed in <name>"`;
    3. entries whose facts use the language's dictionary words of 3+ letters as whole words, case-insensitive: why `'its facts use "dov", "zorin"'` (up to 3 words).
  - Handler `handle_language_related(data: {"language_id"})` replies `language_related {"language_id", "entries": [...]}`.

- [ ] **Step 1: Write the failing tests:**
  - `test_speakers_come_first_with_their_role`;
  - `test_entries_filed_in_a_speaker_follow`;
  - `test_entries_whose_facts_use_its_words_are_suggested` (*dov* in a fact; *on*, 2 letters, never matches);
  - `test_each_entry_once_and_at_most_the_limit`;
  - server `test_language_related_replies_with_entries`.
- [ ] **Step 2:** run. Expected: FAIL.
- [ ] **Step 3: Implement.** Use `languages_for`'s own-row reading (`talemate.languages.lookup._own_rows`, or the stored `languages` field) and `filing.filings_of`.
- [ ] **Step 4:** run. Expected: PASS.
- [ ] **Step 5: Commit** `feat(languages): suggest the entries a change should fit`.

### Task 3: Change and fill briefs, and the job

**Files:**
- Modify:
  - `src/talemate/languages/making.py`: `MakeRequest.kind: Literal["new", "change", "fill"] = "new"` and `target_id: str | None = None`;
  - `src/talemate/languages/brief.py`;
  - `src/talemate/server/worlds.py` (`handle_language_make_start`, `handle_language_brief`);
  - `.claude/skills/language-design/SKILL.md` (a change: return the whole file, keep used words, don't rename the language); add it with `git add -f`.
- Test: `tests/languages/test_brief.py`, `tests/server/test_worlds_language_make.py`

**Interfaces:**
- Consumes: `export_language`, `used_words`, `completeness` (3b-2a).
- Produces:
  - `fill_step(language: Language) -> Literal["words", "phrases", "grammar"] | None`: the first group with something missing, in that order. `None` when nothing is missing, or for a non-full language.
  - `write_brief(view, request, *, check_command=None, size="full", current: LanguageFile | None = None, used: list[str] = ())`:
    - for `change`, `## What to change` holds the request, then `## The language now` holds the current file in a ```json block. The rule lines are:
      - "Return the whole file with your changes";
      - "Keep the language's name";
      - "These words name things in the world: keep them exactly as they are: …" (the `used` list).
    - for `fill`, `## What to add` lists exactly what `completeness` says is missing for `fill_step`: the missing meanings (all of them), the missing phrase categories (3 phrases each), or the missing grammar topics (a section each, with tables where they have forms). Plus "Keep everything else as it is".
    - The file format section and the check section are as for a new language.
  - The server's `language_make_start` for `kind` `change`/`fill`:
    - needs `target_id` to be a live language, else `language_make_failed {"error": "The language this was for is gone"}`;
    - the brief carries `current = export_language(view, target_id)`;
    - the job remembers `base_text = current.model_dump_json()`;
    - `language_make_done` carries `{"text", "kind", "target_id", "base"}`.
  - `language_make_started` carries `{"route", "kind", "target_id"}`.
  - **The one-job rule:** the refusal error becomes "Something else is being made or changed; wait for it or cancel it".
  - **The Claude Code route for a change:** the scratch folder also gets `<slug>.language.json` (the current file) so Claude Code edits it in place. The brief says so. *My call, to keep the reply small.*

- [ ] **Step 1: Write the failing tests:**
  - `test_a_change_brief_carries_the_language_and_the_request`;
  - `test_a_change_brief_lists_the_used_words`;
  - `test_a_fill_brief_lists_what_is_missing` (`fill_step` "words": every missing meaning is in the brief);
  - `test_fill_step_order_and_none_when_complete` (Review Focus 4);
  - server `test_a_change_job_returns_its_base` (in-app with a fixed `language_file`; done carries `base` equal to the export taken at start, and `kind` "change");
  - server `test_a_change_for_a_gone_language_fails_plainly`;
  - server `test_a_change_with_claude_code_edits_the_file_in_place` (the fake finds `*.language.json` already in its folder before it writes: the fake's `ok` mode records the names of files present at start into `seen.json`; assert the current file was there).
- [ ] **Step 2:** run. Expected: FAIL.
- [ ] **Step 3: Implement.** Extend the fake: write `seen.json` (file names in its cwd at start) in every mode.
- [ ] **Step 4:** run `tests/languages tests/server`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(languages): briefs and jobs for changing and filling in a language`.

### Task 4: Reviewing and accepting a change

**Files:**
- Modify:
  - `src/talemate/server/worlds.py`: `LanguageTextPayload.base: str | None = None`, passed to `preview_import`/`apply_import`; the preview reply carries `kept_edits`, the grammar and sound differences, and `rules_removed`;
  - `talemate_frontend/src/components/worlds/LanguageImport.vue`: new prop `base: String`, sent with Check and Import; the diff block shows grammar, the sound before/after, rules removed, and a "Kept" note with *Kept as they are* (used words) and *Kept your edit*; the buttons read **Accept the change** / **Drop it** when `base` is set;
  - `talemate_frontend/src/stores/worlds.js`: `previewLanguage`/`importLanguage` take `base`.
- Test: `tests/server/test_worlds_language_make.py`, `tests/e2e/worlds/test_language_change.py` (created here, extended in Task 5)

**Interfaces:**
- Consumes: Tasks 1 and 3.
- Produces these test ids: `change-diff-grammar`, `change-diff-sound`, `change-kept`.

- [ ] **Step 1: Write the failing tests:**
  - server `test_a_change_preview_keeps_the_owners_edit` (import a language; take base; edit a word through `set_field`; preview a change touching that word with `base`; `kept_edits == ["word kor"]`);
  - server `test_accepting_a_change_is_one_undoable_revision` (after `language_import` with `base`, one revision; undo restores the old words);
  - server `test_accepting_twice_writes_once` (Review Focus 5: a second identical import leaves the revision count unchanged, because the diff is empty and the handler skips the write);
  - server `test_a_change_for_a_deleted_language_is_refused` (Review Focus 2: preview with the target removed answers `"The language this was for is gone"`).
- [ ] **Step 2:** run. Expected: FAIL.
- [ ] **Step 3: Implement.** In `handle_language_import`, an empty diff with `base` set writes nothing and still answers `language_import` with the id.
- [ ] **Step 4:** run. Expected: PASS.
- [ ] **Step 5: Commit** `feat(languages): review a change, keeping the owner's edits`.

### Task 5: Change it… on the language page, with Still to fill in

**Files:**
- Create:
  - `talemate_frontend/src/components/worlds/LanguageRouteChoice.vue`: the "Make it with" row and its model box, extracted from `LanguageMake.vue` (which then uses it);
  - `talemate_frontend/src/components/worlds/LanguageChange.vue`: the panel.
- Modify:
  - `ThingPage.vue`: a **Change it…** header button for language pages (`data-testid="language-change-open"`), before Regenerate prose. The panel opens under the header, across all three tabs;
  - `stores/worlds.js`: `languageChange: {targetId, originId, text, contextIds, route, claudeModel}` (the panel's draft) and `openLanguageChange({targetId, originId, prefill})`. The job state reuses `languageMake` with `kind` and `target_id`.
- Test: `tests/e2e/worlds/test_language_change.py`

**Interfaces:**
- Consumes: `language_related` (Task 2), the jobs (Task 3), the review (Task 4), and the page's `completeness` (3b-2a).
- **Layout (mockup change-it, frame 1):**
  - the request box (`change-request`);
  - **Fit it to:** the related entries, ticked by default, each with its why in muted text (`change-fit`), and "+ Add another entry…" (an autocomplete over the store's entries);
  - the route row (`LanguageRouteChoice`);
  - **Change it** (`change-start`), **Copy the brief** (`change-copy-brief`), **Discard** (`change-discard`);
  - below a divider, **Still to fill in** (`change-still`), listing the page's completeness lines, and **Fill in next: <words / phrases / grammar>** (`change-fill`). Hidden when nothing is missing (Review Focus 4).
  - With the route set to Copy the brief, **Fill in next** copies that step's fill brief instead of starting a job (spec: "each Fill in next on the page has its own Copy the brief"). Test: `test_fill_in_next_copies_its_brief_on_the_brief_route`.
  - While running: progress and Cancel, as in Make.
  - When done: the review (`LanguageImport` with `initialText`, `targetId` and `base`) in the panel (frame 2).
  - Accept closes the panel. Drop clears the result and keeps the request.
- **Disabled while another job runs**, with the note from the Global Constraints.

- [ ] **Step 1: Write the failing e2e tests** (fake Claude Code, fixed language files):
  - `test_change_it_runs_and_the_review_shows_what_changed` (the fake's `ok` returns the sample with a new word and a changed phrase; the review shows the new word; Accept; the Lexicon has it);
  - `test_the_owners_edit_during_a_change_is_kept` (fake `slow`, then `ok`: while it runs, add a meaning in the Lexicon; then the review shows `change-kept` "Kept your edit"). If driving `slow` then `ok` in one run isn't possible with the fake, use the in-app route with a fixed reply, editing between start and done through a held reply. Rule and ledger it;
  - `test_fit_it_to_suggests_speakers` (a place with a Languages row for the language appears ticked with "speaks it");
  - `test_fill_in_next_offers_the_first_gap` (the sample language: "Fill in next: words"; clicking starts a `fill` job);
  - `test_no_fill_button_when_nothing_is_missing`;
  - `test_drop_keeps_the_request`;
  - `test_the_route_row_is_the_same_component_in_make_and_change` (both carry `data-testid="route-choice"`).
- [ ] **Step 2:** run. Expected: FAIL.
- [ ] **Step 3: Implement.** Build, then screenshot at 1920×1080 and a small window against the change-it mockup.
- [ ] **Step 4:** run `test_language_change.py test_language_make.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(worlds-ui): Change it… on a language, with Still to fill in`.

### Task 6: Change… on a grammar chapter

**Files:**
- Modify: `talemate_frontend/src/components/worlds/LanguageGrammar.vue`, which gains a **Change…** text button (`grammar-change`) after a card's title, beside the pencil.
- Test: `tests/e2e/worlds/test_language_change.py`

- [ ] **Step 1: Write the failing e2e test** `test_a_grammar_chapters_change_opens_the_panel_aimed_at_it`: on the Verbs chapter, Change… opens the panel with the request prefilled "Change the Verbs section: ", focused at its end.
- [ ] **Step 2:** run. Expected: FAIL.
- [ ] **Step 3: Implement**, through `worlds.openLanguageChange({targetId, prefill})`.
- [ ] **Step 4:** run. Expected: PASS.
- [ ] **Step 5: Commit** `feat(worlds-ui): change one grammar chapter`.

### Task 7: Changing a language from an entry

**Files:**
- Modify:
  - `ThingPage.vue`: **Change a language to fit this…** (`entry-change-language`) as a text button after **Add fact** in the Facts heading, on any non-language page;
  - `ReferenceMenu.vue`: the same item in the right-click menu (`menu-change-language`), when the menu has a `contextThingId` whose kind isn't `language`;
  - `LanguageChange.vue`: with an `originId` and no `targetId`, it shows a language picker first. The picker uses chips, as in the naming menu: languages in reach of the entry first (pinned), from `language_menu`'s rows, then the rest. **Fit it to** starts with the entry itself, ticked, followed by the chosen language's related entries.
- Test: `tests/e2e/worlds/test_language_change.py`

- [ ] **Step 1: Write the failing e2e tests:**
  - `test_from_an_entry_the_panel_opens_in_place` (on a lore entry, the button opens the panel on that page; the entry is ticked under Fit it to; the language spoken there is first and picked);
  - `test_the_right_click_menu_offers_it` (right-click in a fact box shows `menu-change-language`);
  - `test_the_review_comes_back_on_the_entry` (fake `ok`: the review is on the entry page; Accept; the page stays on the entry).
- [ ] **Step 2:** run. Expected: FAIL.
- [ ] **Step 3: Implement.** Build, then screenshot against the make-and-entry mockup, frame 2.
- [ ] **Step 4:** run `tests/e2e/worlds/test_language_change.py tests/e2e/worlds/test_language_naming.py`, then the full plain and e2e suites. Expected: 0 failures.
- [ ] **Step 5: Commit** `feat(worlds-ui): change a language to fit an entry`.

### Task 8: Acceptance

**Files:** Create `docs/superpowers/probes/2026-10-29-languages-3b2b-acceptance.md`, a checklist in the 3b-2a shape.

- [ ] **Step 1:** write the checklist.
- [ ] **Step 2:** ask the owner before any real Claude Code run (their subscription). Then, with their go-ahead, on the saved Moscavian (`.superpowers/saved/2026-10-29-moscavian/moscavian.language.json`, imported into a fresh test world with a religion entry), run:
  - from the religion entry: "redo the blessings and farewells around the Owl Synod";
  - from the page: "they're traders: add words for trade and the river market".

  Record what changed, what was kept, and the time each took.
- [ ] **Step 3:** record the owner's verdict, and commit `docs(languages): 3b-2b acceptance`.
