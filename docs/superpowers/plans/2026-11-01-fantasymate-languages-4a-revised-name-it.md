# Languages 4a revised: mark, don't replace; Name it… — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
- Drafts arrive exactly as the model wrote them, with flagged names marked.
- The owner names things deliberately with **Name it…**, a panel that rolls from a visible rule or pattern with fast rerolls, or makes a name from a meaning, on any selected words, stubs and entries.
- The owner's bugs from the test run are fixed.

**Architecture:**
- The first 4a build is on this branch: lists, the flag call, the fit check, languages from the owner's words, marks and their card, the Names page, and descriptions on accept. Most of it stays.
- **Cleaning keeps only its finding half.** Picks, rewrites, spare names and word-saving on accept go.
- **A new `languages/naming_panel.py`** serves the panel:
  - a batch of names from a rule, or from one of its patterns;
  - a meaning, where a name splits into dictionary words;
  - candidates for a typed meaning, built on `name_in`'s word-by-word translation.
- **One Vue component, `NameItPanel.vue`,** is opened from:
  - the flag card;
  - a draft's selection menu;
  - the right-click reference menu (replacing "Make a name" and "Reroll this part");
  - an entry's or stub's name.

**Tech Stack:** Python 3.11, pydantic, jinja2 prompt templates, Vue 3 + Vuetify, pytest, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-10-30-fantasymate-languages-4-design.md`, section "4a revised (owner, 2026-11-01)". Where it disagrees with the older 4a sections, it wins. Approved mockup: `docs/superpowers/mockups/2026-11-01-languages-4a-name-it.html` (frames 1–3). The first build's plan and ledger: `docs/superpowers/plans/2026-10-30-fantasymate-languages-4a-clean-names.md`, `.superpowers/sdd/2026-10-30-fantasymate-languages-4a-clean-names/progress.md`.

## Global Constraints

- **The narrator rule:**
  - the world is written in English;
  - foreign words are only names and flavour;
  - descriptive words stay English ("the Court of Lakes");
  - a stock English title is never made into a foreign phrase.
- **Nothing in a draft is changed by cleaning.** Flagged names are only marked: from a list (real, cliché, title), from the model's flag, or misfits of the language. The card offers **Name it…**, **Keep it** and **Never flag it in this world**.
- **One mark style:** a thin wavy underline in the `warning` role. A flagged name that's also a new stub keeps its stub look plus the underline, and one card holds both.
- **Name it…:**
  - **The panel shows:** the language, the rule, an optional single pattern, a batch of **10**, **Reroll** (a fresh batch on each click, no hover, never cycling), and **From a meaning**.
  - **Rolled names make no model call.** A rolled name built from dictionary words shows that meaning.
  - **Picking in a draft** changes every place the draft writes those words. A flagged name that wasn't a stub becomes a ticked new stub.
  - **Renaming:** a saved entry is renamed with `repoint.retitle`, so the old name becomes a common other name. A stub or draft forgets its old name.
  - **On words linking an entry,** Name it… renames that entry, and the panel says so.
  - **The picked word is added to the language** (`naming.add_word`) with its meaning, or none.
  - **It replaces the right-click "Make a name…" and "Reroll this part…" items.** "Name it in…" stays.
- **Prompts:** with a language in reach, the create and Add facts prompts say to keep descriptive words English and to use the language only for names. Hover meanings across all text are **later** (scene rework).
- **The owner's UI rules:**
  - controls sit right after what they act on;
  - right-align only in half-width areas;
  - the same look is one component;
  - the approved mockup is the model;
  - screenshots at 1920×1080 and a small window.
- **The owner's test app** (`.superpowers/sdd/2026-10-30-fantasymate-languages-4a-clean-names/app`, worlds Test and Test2) **is never restarted** without first copying `worlds/` and `config.yaml` out and back.
- **Tests:** no real model (queued `MockClient` replies, fixed-reply files). Real runs need the owner's go-ahead (koboldcpp).

## Review Focus

1. **Name it… on words that appear in a draft's text and in a new stub row with different case or a possessive** ("Greywash's"). Every place is changed, and the stub row is renamed, not duplicated. Task 4.
2. **Rerolling when a rule's pattern space is small** (a rule with three literal names). A batch shows what exists (fewer than 10), Reroll never errors, and names already in the world are left out. Task 3.
3. **From a meaning with words the dictionary lacks.** New words are coined with their meaning and saved only when the owner picks. Cancelling saves nothing. Task 3.
4. **Renaming a saved entry to a name another entry has.** It's refused with the existing "name in use" message, and nothing changes. Task 4.
5. **The flag card on a name that's both a new stub and flagged, after the owner keeps it.** The stub look stays, only the underline goes, and the stub is still made on accept. Task 2.

---

### Task 1: Cleaning marks, never replaces

**Files:**
- Modify:
  - `src/talemate/languages/cleaning/replace.py` (rename to `mark.py`, keeping a `replace.py` shim only if imports need it);
  - `src/talemate/languages/cleaning/marks.py`;
  - `src/talemate/worldplay/cleaning.py`;
  - `src/talemate/worldplay/create.py` (accept no longer saves words);
  - `src/talemate/worldplay/facts.py`, `src/talemate/worldplay/groups.py`;
  - `src/talemate/server/worlds.py`.
- Delete: `src/talemate/prompts/templates/world/name-picks.jinja2`, `title-rewrites.jinja2`.
- Test:
  - `tests/languages/test_clean_mark.py` (from `test_clean_replace.py`; replacing tests removed);
  - `tests/worldplay/test_create_cleaning.py`, `test_facts_cleaning.py`, `test_groups_cleaning.py`, `tests/server/test_worlds_cleaning.py`.

**Interfaces:**
- **Produces:**
  - `Mark(BaseModel)`: `id: str`, `name: str` (as written), `why: str`, `language_id: str | None`, `entry_kind: str`. The `kind`, `was`, `meaning` and `spares` fields are removed.
  - `async mark_texts(client, view, texts, listed, prompt, rows, lists, keep=frozenset()) -> list[Mark]`. The texts are untouched. It uses `find.spots` and `find.judge` as now, and every verdict (replace, rewrite or suspect) becomes a `Mark` with its `why`.
  - `clean_preview`, `clean_fact_draft` and `clean_group_draft` set `marks` only. They no longer change texts or `new_names`.
  - `unclean_preview` and `save_mark_words` are deleted. `NewName.replaced` and `from_cleaning` are removed. `draft_languages` re-marks (keeps owner-kept names via `owner_kept`, which reads the marks the owner dropped).
- **Removed:** the pick and title calls, spares, `in_use`, and the whole-form swapping. `_swap` stays in `nameMarks.js`'s Python twin only if Task 4 needs it (it doesn't).

- [ ] **Step 1: Rewrite the cleaning tests for marking.**
  - `test_a_real_place_is_marked_not_changed` (texts unchanged; one mark, why "a real name, on the Real names list");
  - `test_a_stock_title_is_marked_not_rewritten`;
  - `test_a_misfit_is_marked`;
  - `test_no_language_marks_list_hits_only`;
  - `test_a_draft_arrives_unchanged_with_marks` (create);
  - `test_accept_saves_no_words` (the dictionary unchanged after accept);
  - `test_changing_languages_remarks_and_keeps_kept_names`.

  Delete the tests that assert replacement: the picks, spares, titles, whole-form and frame-swap ones. Keep the frame and title-word tests in `test_clean_find.py` as they are.
- [ ] **Step 2: Run them.** Run: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/languages tests/worldplay/test_create_cleaning.py tests/worldplay/test_facts_cleaning.py tests/worldplay/test_groups_cleaning.py tests/server/test_worlds_cleaning.py -q -p no:cacheprovider`. Expected: FAIL.
- [ ] **Step 3: Implement the interfaces above.**
- [ ] **Step 4: Run them again, then the whole plain suite.** Expected: PASS.
- [ ] **Step 5: Commit** (`refactor(languages): cleaning marks names, never replaces them`).

### Task 2: One mark, and the flag on stubs

**Files:**
- Modify:
  - `talemate_frontend/src/components/worlds/LinkedText.vue` (a `flag` on a run, not a separate run kind);
  - `nameMarks.js` (`markSegments` sets `flag: markId` on plain and fresh runs; `markEdit` keeps only `keep` and `never_flag`);
  - `NameMarkCard.vue` → `FlagCard.vue`;
  - `StubCard.vue` (a slot for the flag line);
  - `PreviewStubs.vue` ("flagged: why" instead of "replaced X");
  - `stores/worlds.js` (`markAction` keeps `keep` and `never_flag`).
- Test: `tests/e2e/worlds/test_clean_names.py` (rewritten), `talemate_frontend/checks/worlds.check.mjs`.

**Interfaces:**
- **Consumes:** `Mark` (Task 1).
- **Produces:**
  - Segments carry `flag: <mark id>` beside their own kind: plain, `fresh` (a new stub) or `stub`.
  - In `LinkedText`, a flagged run gets class `flagged` (a wavy underline in the `warning` role) on top of its own look.
  - **Hovering a flagged run opens one card:**
    - a fresh or stub run shows `StubCard` with the flag line in its slot;
    - a plain run shows `FlagCard`.
  - **The flag line:** "Flagged: <why>", with **Name it…** (`flag-name-it`, emits `name-it {markId, words}`, wired in Task 5), **Keep it** (`flag-keep`) and **Never flag it in this world** (`flag-never`). Test ids: `name-flag` on the run, `flag-card`.
  - **`markEdit(edited, markId, action)`:** `keep` drops the mark; `never_flag` drops it and returns `{keep: name}`.
- **Review Focus 5:** keeping a flagged new stub drops only the flag; its `fresh` look and the stub on accept stay.

- [ ] **Step 1: Write the failing checks and e2e tests.**
  - Check `markSegments keeps a fresh run fresh and adds its flag`.
  - Check `keep and never_flag drop only the mark`.
  - E2E (fixed preview with Novgorod listed as a new name, and Volga only in text):
    - `test_a_draft_arrives_unchanged_with_flags`;
    - `test_a_flagged_new_stub_keeps_its_stub_look_and_one_card`;
    - `test_keeping_a_flagged_stub_keeps_the_stub` (accept makes the Novgorod stub);
    - `test_never_flag_adds_to_the_keep_list`;
    - `test_new_stubs_say_why_a_name_is_flagged`.
- [ ] **Step 2: Run them.** Run: `(cd talemate_frontend && guix shell -m ../manifest.scm -- node checks/worlds.check.mjs)`, and `… pytest tests/e2e/worlds/test_clean_names.py -m e2e -n 4 -q -p no:cacheprovider`. Expected: FAIL.
- [ ] **Step 3: Implement the interfaces above, and build the frontend.**
- [ ] **Step 4: Run them again.** Expected: PASS. Take screenshots at 1920×1080 and 1280×800, and compare them with mockup frame 1.
- [ ] **Step 5: Commit** (`feat(worlds-ui): one flag mark, on stubs too`).

### Task 3: Names for the panel: batches, patterns, meanings

**Files:**
- Create: `src/talemate/languages/naming_panel.py`
- Modify: `src/talemate/languages/generator.py` (`roll` gains `pattern: int | None = None`), `src/talemate/server/worlds.py` (handlers)
- Test: `tests/languages/test_naming_panel.py`, `tests/server/test_worlds_name_it.py`

**Interfaces:**
- **Produces:**
  - `roll(language, generator_id, count=20, rng=None, exclude=frozenset(), pattern: int | None = None)`: with `pattern`, only that pattern (an index into `generator.patterns`) is used.
  - `RuleInfo(BaseModel)`: `id`, `name`, `use`, `patterns: list[str]` (weights stripped).
  - `rules_of(language) -> list[RuleInfo]`: the name rules, word rules included.
  - `meaning_of(language, name) -> str`. When `name` (lower-cased) splits into dictionary words and the rule endings (as `check._compound` splits), it gives their meanings joined with " + ", e.g. "hill + town". Otherwise "".
  - `batch(language, rule_id, *, pattern=None, count=10, exclude=frozenset(), seed=None) -> list[dict]`: `[{name, meaning}]`, fewer when the pattern space is small, with no model call.
  - `async from_meaning(view, client, language_id, text, *, reply=None) -> list[dict]`: `[{name, built_from: [{word, meaning, new: bool}]}]`, up to 3 candidates.
    - It goes word by word as `naming.name_in` does: dictionary words are kept, function words dropped, coinage is rolled and picked by the model.
    - **Nothing is saved.**
  - **Server:**
    - `name_it_rules {language_id}` → `{language_id, rules}`;
    - `name_it_batch {language_id, rule_id, pattern?, count?}` → `{language_id, rule_id, pattern, names}`;
    - `name_it_meaning {language_id, text}` → `{language_id, text, candidates}`.

    The fixed reply for e2e is `FIXED_LANGUAGE_ENV`, as language naming uses today.
- **Review Focus 2:** a rule of three literal names gives at most 3, never errors, and leaves out existing entry names.
- **Review Focus 3:** `from_meaning` saves nothing.

- [ ] **Step 1: Write the failing tests:**
  - `test_roll_from_one_pattern_only`;
  - `test_batch_gives_ten_with_meanings_where_built_from_words`;
  - `test_a_small_rule_gives_what_it_has`;
  - `test_batch_leaves_out_entry_names`;
  - `test_meaning_of_splits_into_dictionary_words`;
  - `test_from_meaning_translates_and_coins_without_saving` (queued pick reply);
  - server: `test_name_it_actions_answer`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the interfaces above.**
- [ ] **Step 4: Run them again.** Expected: PASS.
- [ ] **Step 5: Commit** (`feat(languages): batches, patterns and meanings for Name it`).

### Task 4: Using a picked name: drafts, words, renames

**Files:**
- Modify:
  - `talemate_frontend/src/components/worlds/nameMarks.js` (`pickName`);
  - `src/talemate/server/worlds.py` (`name_it_rename`);
  - `src/talemate/worldplay/repoint.py` (uses `retitle`).
- Test: `talemate_frontend/checks/worlds.check.mjs`, `tests/server/test_worlds_name_it.py`

**Interfaces:**
- **Consumes:** Task 3's actions; `naming.add_word`.
- **Produces:**
  - **`pickName(edited, words, name) -> changes`** (client, for a page or small draft). It swaps `words` as a whole word, case-sensitive, possessive kept, in the name, facts, summary, "for other pages" rows and group rows.
    - A `new_names` row equal to `words` is renamed. When none is, and `words` was flagged, a ticked row `{name, kind: entry_kind}` is added.
    - A mark on `words` is dropped.
  - **The picked word goes to the language** through `language_add_word` (meaning from the panel, or "").
  - **`name_it_rename {thing_id, name}`:**
    - a saved entry → `retitle` (the old name becomes a common other name);
    - a stub → `set_field name` (the old name forgotten);
    - a name in use → refused with the existing message, nothing changed.
    - Answers with the thing's payload.
- **Review Focus 1:** "Greywash's" and the stub row "Duchies of the Greywash Coast" are both changed, with no duplicate row.
- **Review Focus 4:** a name in use is refused.

- [ ] **Step 1: Write the failing tests.**
  - Checks: `pickName changes every place and renames the stub row`, `pickName adds a stub row for a flagged name`.
  - Server tests:
    - `test_renaming_an_entry_keeps_the_old_name_as_another_name`;
    - `test_renaming_a_stub_forgets_the_old_name`;
    - `test_a_name_in_use_is_refused`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the interfaces above.**
- [ ] **Step 4: Run them again.** Expected: PASS.
- [ ] **Step 5: Commit** (`feat(languages): a picked name goes where it was asked, and into the language`).

### Task 5: The Name it… panel, everywhere

**Files:**
- Create: `talemate_frontend/src/components/worlds/NameItPanel.vue`
- Modify:
  - `stores/worlds.js` (`nameIt` state and actions for Task 3's requests and replies);
  - `FlagCard.vue` and `StubCard.vue`'s flag line;
  - the draft selection menu (where "Make a stub" and "Link to…" live, `draftSelection`);
  - `ReferenceMenu.vue` ("Name it…" replaces "Make a name…" and "Reroll this part…");
  - `ThingPage.vue` (a **Name it…** button right after the name's pencil, for entries and stubs).
- Delete: `LanguageNameMenu.vue`'s roll and reroll parts, which Name it… covers.
- Test: `tests/e2e/worlds/test_name_it.py`

**Interfaces:**
- **Consumes:** Task 3's actions; Task 4's `pickName` and `name_it_rename`.
- **Produces:**
  - **`NameItPanel` (mockup frames 2 and 3)** takes props `words`, `languageId` (or null: it asks which language, from the world's), `kind` (the rule's starting use), and `target` (`{draftKey}`, `{smallKey}`, `{thingId}` or `{input}`). It shows:
    - the language select, the rule select (`name-it-rule`) and the pattern select (`name-it-pattern`, "any" first);
    - ten chips (`name-it-name`) with **Reroll** (`name-it-reroll`, asks a new batch on each click);
    - a "From a meaning" field (`name-it-meaning`) with **Find**, its candidates (`name-it-candidate`) each with what it's built from;
    - a note of what a pick does ("renames Tsargrad everywhere; Tsargrad stays as another name");
    - picking calls Task 4 and closes.
  - **The rule starts from the target's kind** (`generator_for`), and the language from the draft's or entry's languages, else the panel asks.
- **Removed:** "Make a name…" and "Reroll this part…" from the reference menu. In a text box, Name it… with nothing selected names at the cursor.

- [ ] **Step 1: Write the failing e2e tests** (with fixed languages and replies):
  - `test_name_it_from_a_flag_renames_every_place_in_the_draft`;
  - `test_reroll_gives_a_new_batch_each_click`;
  - `test_one_pattern_narrows_the_batch`;
  - `test_from_a_meaning_shows_what_it_is_built_from`;
  - `test_name_it_on_part_of_a_name` (select "Greywash");
  - `test_name_it_on_an_entry_renames_it_and_keeps_the_old_name`;
  - `test_name_it_on_a_stub_forgets_the_old_name`;
  - `test_the_reference_menu_offers_name_it_not_make_a_name`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the interfaces above, and build the frontend.**
- [ ] **Step 4: Run them, then the whole e2e suite.** Expected: PASS. Take screenshots at both sizes and compare them with mockup frames 2 and 3. Grep `tests/ai` for "Make a name" and "Reroll this part".
- [ ] **Step 5: Commit** (`feat(worlds-ui): Name it…`).

### Task 6: Languages the model knows, and the narrator rule in prompts

**Files:**
- Modify:
  - `src/talemate/languages/importer.py` (`apply_import` writes a fact on creation);
  - `src/talemate/prompts/templates/world/create-thing.jinja2`, `add-facts.jinja2`, `src/talemate/worldplay/create.py` (template vars at ~3140), `src/talemate/worldplay/facts.py`;
  - `.claude/skills/language-design/SKILL.md` (commit with `git add -f`).
- Test: `tests/languages/test_importer.py`, `tests/worldplay/test_create.py`, `tests/worldplay/test_facts.py`

**Interfaces:**
- **Produces:**
  - **A new language entry gets one `general` fact:** "<Name> is a language of this world." When the import's file names what speaks it (its `description`), its first sentence follows.
  - **The template var `language_names: list[str]`** holds the languages in reach (from the owner's words, or inherited). With any, the prompt adds one rule: "Write in plain English. Titles and descriptions stay English (the Court of Lakes, the Tsardom of X); only proper names may sound foreign. <names> are languages, not things." It is absent with none.
  - **The skill's people rules are two by default:** `men` and `women` (use `character`). `generator_for` prefers the one matching a drafted person's sex when known; else the first.
- [ ] **Step 1: Write the failing tests:**
  - `test_importing_a_language_writes_a_fact_about_it`;
  - `test_the_create_prompt_carries_the_narrator_rule_with_a_language`;
  - `test_no_rule_without_a_language`;
  - `test_add_facts_prompt_carries_it_too`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the interfaces above. Update the skill's example and rules text.**
- [ ] **Step 4: Run them again.** Expected: PASS.
- [ ] **Step 5: Commit** (`feat(languages): the model knows the languages, and keeps descriptions English`).

### Task 7: The owner's bugs

**Files:** found by each step; mostly `EntryLanguages.vue`, `stores/worlds.js`, `worldplay/cleaning.py`, `languages/cleaning/find.py`, `worldplay/create.py`
**Test:** `tests/e2e/worlds/test_clean_names.py`, `tests/worldplay/test_create_cleaning.py`, `tests/languages/test_clean_find.py`

- [ ] **Step 1: Missing stubs (world Test, "Eared Owl-folk").** The accepted fact "…countries of Velmora, Ashenmark, and the Duchies of the Greywash Coast…" was written unlinked.
  - **The owner's order:** the language first, then the owl-folk (species, then races), then the Tsardom.
  - The Eared Owl-folk **race** draft failed to stub the countries. The Tsardom's draft, which had the owls as context, stubbed them later; those are the unlinked stubs the world holds now.
  - So start from a **race** draft: heritage kinds may treat new names differently (`NAME_KINDS`, `_new_names`, the race prompt's names rule).
  - Reproduce with a fixed preview that lists those three names under `names` and cleaning on. Then reproduce again with them unlisted.
  - Use superpowers:systematic-debugging to find whether the marks dropped the `fresh` runs or rows, or whether the model didn't list them.
  - Write a test for the cause, watch it fail, fix it. If the cause is that the model didn't list them, ledger a ruling. Flagged unlisted names then come as unticked New stubs rows, so the owner can tick them.
- [ ] **Step 2: Picking a language is slow and allows double adds.** The added row shows at once, with a busy indicator, until the reply comes. While a save is out, Save is disabled. Tests: `test_a_picked_language_shows_at_once`, `test_adding_twice_is_not_possible_while_saving`.
- [ ] **Step 3: A stub's draft ignores the language it inherits.**
  - `CreatePreview` gains `inherited_languages: list[dict]` (`{language, role, from: <entry name>}`), filled from `inherited_rows`.
  - The draft's Languages section shows them ("from Tsarvenya"), and **Pick a language** only shows with none.
  - Tests: `test_a_stub_draft_shows_the_language_it_inherits` (e2e), `test_preview_lists_inherited_languages`.
- [ ] **Step 4: "Duchies of the Greywash" was judged as one name.**
  - Plural frame and kind words (duchies, kingdoms, provinces, isles, coasts…) are recognised.
  - A name whose kind word ends it ("…Greywash Coast") keeps it in the judged part's whole form.
  - Test: `test_a_plural_frame_name_judges_only_its_name` ("Duchies of the Greywash Coast" judges "Greywash").
- [ ] **Step 5: Run the plain suite and the e2e suite, then commit** (`fix(languages): the owner's test-run bugs`).

### Task 8: Acceptance

- [ ] **Step 1: Update the acceptance checklist** `docs/superpowers/probes/2026-10-30-languages-4a-acceptance.md` with a "Revised" table: each spec point, what the owner looks at, and the proving tests.
- [ ] **Step 2: Update the owner's test app's frontend.** Copy the changed `talemate_frontend/src` files into the app's copy (`app/talemate_frontend/src/…`) if the app runs from its own copy. A backend change needs a restart: first copy `worlds/` and `config.yaml` out, then restart, then copy them back. Ask the owner before restarting.
- [ ] **Step 3: Real runs, with the owner's go-ahead (koboldcpp).**
  - Make a draft in Test: confirm the marks.
  - Name a lake with Name it…: rolls, rerolls and a pattern.
  - Name something from a meaning ("lakeland").
  - Rename a stub and an entry.

  Record what happens.
- [ ] **Step 4: The owner looks in the test app.** Record their verdict, and commit (`docs(languages): 4a revised acceptance`).
