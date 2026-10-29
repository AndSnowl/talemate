# Languages 3b-2a: fuller languages and the Grammar tab — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A newly made language comes back complete enough to use and to read: grammar in sections with tables and examples, shown on its own Grammar tab; a full vocabulary and phrase set; a report of what's still missing. The Make dialog lets the owner pick the route, the model and how much the first run does.

**Architecture:**
- `Language.grammar` changes from one text to a list of `GrammarSection` (text, tables, examples). Old text still loads as one section.
- The app ships a list of core meanings and the usual phrase categories and grammar topics. A new `completeness()` check reports gaps as "Still to fill in", never blocking and never triggering a repair.
- The brief asks for the full set (or a quick core).
- `MakeRequest` carries a per-run route, model and size, which override the Language agent's defaults.
- The page gains a Grammar tab (mockup A).

**Tech Stack:** Python 3.11, pydantic, Vue 3 + Vuetify, pytest, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-10-29-fantasymate-languages-3b2-design.md`, sections 1 and 3. The approved mockups:
- `docs/superpowers/mockups/2026-10-29-languages-3b2-grammar-layout.html`, **option A**;
- `docs/superpowers/mockups/2026-10-29-languages-3b2-make-and-entry.html`, frame 1.

**Out of scope, plan 3b-2b:**
- Change it…;
- changing from an entry;
- the bigger review;
- Fill in next;
- the Still to fill in panel;
- each grammar card's Change… link.

Here, Still to fill in shows only in the import review's report.

## Global Constraints

- **No jargon without a plain word** facing the owner (spec, Anti-goals). Topic titles are plain: "Nouns", "How words are built", "Questions and 'not'".
- **Nothing blocks for completeness:** missing meanings, phrase categories or grammar topics are reported, never blocking. `needs_repair` ignores them (spec 1, "the completeness warnings aren't sent back automatically").
- **Old languages keep working:**
  - a grammar text loads as one section titled "Grammar" (topic `other`);
  - a file with `version: 1` and text grammar imports as before.
- **The 3b-1 Claude Code boundary is unchanged:** `talemate.languages.claude_code` invocation, the check outside the work folder, `-P`, and folder-only reads.
- **The route chosen in the dialog applies to that run only.** It never changes the Language agent's setting (spec 1).
- **Defaults for How much:** `full` for Claude Code and Copy the brief; `quick` for the agent's model (spec 1).
- **UI:**
  - mockup A is the model;
  - controls sit right after what they act on;
  - screenshots at 1920×1080 and a small window;
  - never restart an isolated app the owner has used without saving its `worlds/` and `config.yaml` first.
- **Tests:** no real model or Claude Code; use the fake `tests/languages/data/fake-claude` and fixed replies. Commands as in `docs/dev/local-testing.md`.

## Review Focus

1. **An old language with text grammar** (all four languages made so far). It shows one "Grammar" card on the Grammar tab, its text can still be edited, and saving keeps it. Tasks 1 and 5.
2. **A table whose rows have fewer or more cells than it has columns,** or a section with no tables or examples. It renders padded or trimmed, never crashes, and loads and saves unchanged. Tasks 1 and 5.
3. **Meanings matched loosely:** "to be" vs "be", "Water" vs "water", a word whose second meaning is "hand", a meaning "great fort" vs the core "fort". The completeness count is right and doesn't count the multi-word meaning. Task 2.
4. **A full-size language** (300+ words, 12 sections, 40 phrases). The check, import preview and Lexicon stay quick: the check takes under 2 s on that file. Task 2.
5. **The dialog's route set to Copy the brief.** Make it gives way to Copy the brief, the copied brief follows the chosen How much, and switching the route back restores Make it. Task 6.

---

### Task 1: Grammar sections in the language model

**Files:**
- Modify:
  - `src/talemate/languages/models.py`;
  - `src/talemate/languages/entry.py` (`fields_of` and `language_of` write and read `rules["grammar"]` as a list);
  - `src/talemate/languages/check.py` (the real-word scan also reads the grammar examples' original words);
  - `src/talemate/languages/language.schema.json`, regenerated as the existing schema test says.
- Test: `tests/languages/test_grammar_sections.py`

**Interfaces:**
- Produces, in `talemate.languages.models`:
  - `GrammarTable(BaseModel)`: `caption: str = ""`, `columns: list[str] = []`, `rows: list[list[str]] = []`.
  - `GrammarExample(BaseModel)`: `original: str`, `breakdown: list[tuple[str, str]] = []`, `translation: str = ""`.
  - `GrammarSection(BaseModel)`: `title: str`, `topic: str = "other"`, `text: str = ""`, `tables: list[GrammarTable] = []`, `examples: list[GrammarExample] = []`. All are `extra="ignore"`.
  - `GRAMMAR_TOPICS: tuple[tuple[str, str], ...]`: the ids and plain titles, in this order:

    ```
    ("sounds", "Sounds and stress"), ("word_order", "Word order"),
    ("nouns", "Nouns"), ("pronouns", "Pronouns"), ("verbs", "Verbs"),
    ("adjectives", "Adjectives"), ("questions", "Questions and \"not\""),
    ("numbers", "Numbers"), ("word_building", "How words are built"),
    ("names", "How names are built"), ("politeness", "Politeness and registers")
    ```

    Anything else is `"other"`.
  - `Language.grammar: list[GrammarSection]`, with a `mode="before"` validator: `""`/`None` becomes `[]`, and a non-empty str becomes `[GrammarSection(title="Grammar", topic="other", text=value)]`.
- `LanguageFile.version` stays `Literal[1]`. *Ruling to ledger:* the grammar change is read both ways, so no version bump is needed.

- [ ] **Step 1: Write the failing tests**:
  - `test_old_grammar_text_is_one_section`;
  - `test_empty_grammar_is_no_sections`;
  - `test_sections_round_trip_through_an_entry`: `fields_of` then `language_of`, equal sections, and `_validate_rules` accepts it;
  - `test_a_ragged_table_loads_as_written` (Review Focus 2): rows of 2 and 4 cells under 3 columns load unchanged; padding happens only in the UI;
  - `test_real_words_in_grammar_examples_are_flagged`: a `russian`-flavoured language whose example has `"voda"` in its original (on the Russian list) gives a `real_hits` entry;
  - `test_the_schema_has_grammar_sections`: the generated schema's `Language.grammar` is an array of `GrammarSection`.
- [ ] **Step 2:** `… pytest tests/languages/test_grammar_sections.py -q`. Expected: FAIL (no `GrammarSection`).
- [ ] **Step 3: Implement.** Regenerate the schema the way `tests/languages` checks it (grep for `language.schema.json` in tests).
- [ ] **Step 4:** run `tests/languages tests/world tests/server/test_worlds_languages.py`. Expected: PASS. Fix the callers that read `language.grammar` as a str (grep `\.grammar`), including `export_language` and the 3a importer diff.
- [ ] **Step 5: Commit** `feat(languages): grammar as sections with tables and examples`.

### Task 2: The completeness check

**Files:**
- Create: `src/talemate/languages/completeness.py`, `src/talemate/languages/data/core_meanings.txt`
- Modify:
  - `src/talemate/languages/check.py`: `CheckReport.completeness`, filled by `check_language`;
  - `repair_note`, which adds a "Still to fill in" block after the warnings;
  - `src/talemate/languages/__main__.py`, which prints it.
- Test: `tests/languages/test_completeness.py`

**Interfaces:**
- Produces:
  - `Completeness(BaseModel)`:
    - `meanings_total: int`;
    - `meanings_missing: list[str]` (in list order);
    - `structural_missing: list[str]` (the structural group's part of that);
    - `phrase_categories_missing: list[str]`;
    - `grammar_topics_missing: list[str]` (topic titles).
  - `completeness(language: Language) -> Completeness`.
  - `PHRASE_CATEGORIES = ("greeting", "farewell", "blessing", "curse", "oath", "saying", "toast", "insult", "endearment")`.
  - `CORE_MEANINGS: dict[str, list[str]]`, read from `core_meanings.txt`: the group name, from `# structural` / `# everyday` lines, maps to its meanings.
  - `CheckReport.completeness: Completeness | None = None`.
- **`core_meanings.txt`:**
  - The `# structural` group: the, a, be, am, are, is, was, were, have, has, had, with, of, in, on, at, to, from, for, and, or, but, not, no, yes, I, you, he, she, it, we, they, this, that, here, there, who, what, where, when, why, how, all, many, some, one, two, three, four, five, six, seven, eight, nine, ten, twenty, hundred.
  - The `# everyday` group: the Swadesh 207 list, minus what's already in structural (about 190).
  - Meanings are lower-case, one per line.
- **The matching rule:** a core meaning counts as present when any dictionary meaning equals it exactly, case-insensitively, with a leading "to " dropped from both sides. A multi-word meaning such as "great fort" does not count for "fort".
- A **language of level `naming`** gets `completeness = None`. A naming style isn't a full language.

- [ ] **Step 1: Write the failing tests**:
  - `test_a_word_with_the_meaning_counts` ("Water" → water present; "to be" → be present);
  - `test_a_second_meaning_counts`;
  - `test_a_multi_word_meaning_does_not_count_for_its_parts` (Review Focus 3);
  - `test_missing_phrase_categories_and_grammar_topics` (a language with only greeting phrases and a nouns section reports the other eight categories and ten topics);
  - `test_completeness_never_blocks_or_repairs`: a language missing everything is `report.ok` and `not needs_repair(report)`;
  - `test_the_repair_note_lists_still_to_fill_in`;
  - `test_a_naming_style_has_no_completeness`;
  - `test_a_full_size_language_checks_quickly` (Review Focus 4): build a language with 400 words, 12 sections and 40 phrases; `check_language` takes under 2.0 s.
- [ ] **Step 2:** run them. Expected: FAIL (module missing).
- [ ] **Step 3: Implement.** The Swadesh 207 meanings are public domain; write them as plain English glosses.
- [ ] **Step 4:** run `tests/languages`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(languages): what a language is still missing`.

### Task 3: The brief asks for a full language, or a quick core

**Files:**
- Modify:
  - `src/talemate/languages/making.py`: `MakeRequest` gains `size: Literal["full", "quick"] | None = None`, `route: Route | None = None` and `claude_model: str | None = None`;
  - `src/talemate/languages/brief.py`;
  - `.claude/skills/language-design/SKILL.md`: the grammar sections shape, the topics, the phrase categories, the sizes; add the file with `git add -f`.
- Test: `tests/languages/test_brief.py`

**Interfaces:**
- Consumes: `GRAMMAR_TOPICS`, `PHRASE_CATEGORIES`, `CORE_MEANINGS` (Tasks 1 and 2).
- Produces:
  - `effective_size(request: MakeRequest, route: Route) -> Literal["full", "quick"]`: the request's size, else `quick` for `in_app` and `full` otherwise.
  - The brief gains a section `## What to make`, after "What the owner asked for".
- **For `full`:**
  - every structural meaning;
  - every everyday meaning, listed in full;
  - words for the chosen entries;
  - at least 3 phrases in each of the nine categories;
  - one grammar section for each of the eleven topics, with a table where the topic has forms (nouns, pronouns, verbs, adjectives, numbers) and at least one example each;
  - sections for anything unusual the language does;
  - name rules for characters, places, items and groups, plus a demonym rule.
- **For `quick`:**
  - every structural meaning;
  - about 40 everyday meanings, the first 40 of the list;
  - 1 phrase in each of greeting, farewell, blessing and curse;
  - the eleven topics as short sections, tables only for pronouns and verbs;
  - name rules for characters and places.
  - Plus the line: "The owner will fill in the rest later, so keep to this."
- **For both:** the brief says how a grammar section is shaped (title, topic id, text, tables of caption, columns and rows, examples with a breakdown), and that the text explains things plainly, with any grammar term followed by a plain explanation.

- [ ] **Step 1: Write the failing tests**:
  - `test_a_full_brief_lists_every_core_meaning` (every `CORE_MEANINGS` entry appears);
  - `test_a_quick_brief_keeps_to_the_core` (all structural, at most 40 everyday, "fill in the rest later");
  - `test_both_briefs_describe_grammar_sections_and_topics` (all eleven topic ids appear);
  - `test_effective_size_follows_the_route`;
  - `test_the_brief_still_has_no_jargon` (the existing jargon test, run on a full brief).
- [ ] **Step 2:** run. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** run `tests/languages`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(languages): the brief asks for a full language or a quick core`.

### Task 4: The route, model and size chosen per run

**Files:**
- Modify:
  - `src/talemate/server/worlds.py`;
  - in `handle_language_make_start` and `handle_language_brief`: `MakeSettings` from the agent, overridden by the request's `route` and `claude_model` when set, and the brief written with `effective_size`;
  - `handle_language_make_route`, which also returns `{"route", "claude_model", "sizes": {route: default size}}`;
  - `_thing_payload`: a language page carries `completeness` (`model_dump`, or null);
  - `src/talemate/languages/making.py`: `make_language` passes the size into `write_brief`.
- Test: `tests/server/test_worlds_language_make.py`, `tests/server/test_worlds_languages.py`

**Interfaces:**
- Consumes: `effective_size`, `completeness` (Tasks 2 and 3).
- Produces:
  - `language_make_route` data: `{"route": str, "claude_model": str, "sizes": {"claude_code": "full", "in_app": "quick", "brief": "full"}}`.
  - Page payload: `completeness`.

- [ ] **Step 1: Write the failing tests**:
  - `test_a_run_can_choose_its_route`: the agent says `claude_code`, the request says `in_app` with a fixed `language_file`; it runs in-app and `language_make_started.route == "in_app"`;
  - `test_a_run_can_choose_its_claude_model`: the fake records its args in `args.json`; assert `--model opus`;
  - `test_the_agents_setting_is_unchanged_after_a_run`;
  - `test_the_route_reply_gives_the_default_sizes`;
  - `test_a_language_page_carries_its_completeness`.
- [ ] **Step 2:** run. Expected: FAIL.
- [ ] **Step 3: Implement.** To read `args.json`, the test keeps the scratch folder, by monkeypatching `Scratch.remove`.
- [ ] **Step 4:** run `tests/server tests/languages`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(languages): choose the route, model and size for each run`.

### Task 5: The Grammar tab

**Files:**
- Create: `talemate_frontend/src/components/worlds/LanguageGrammar.vue`
- Modify:
  - `talemate_frontend/src/components/worlds/ThingPage.vue`: `LANGUAGE_TABS` becomes About · Language · **Grammar** · Lexicon;
  - `talemate_frontend/src/components/worlds/LanguageSections.vue`: the "Grammar notes" block leaves the Language tab;
  - `talemate_frontend/checks/` if a check lists the tabs.
- Test: `tests/e2e/worlds/test_language_grammar.py`

**Interfaces:**
- Consumes: the page's `fields.rules.grammar` (a list of sections, Task 1).
- Produces these test ids:
  - `language-tab-grammar`;
  - `grammar-topics` (the topic list);
  - `grammar-topic` (each entry);
  - `grammar-section` (each card);
  - `grammar-table`;
  - `grammar-example`;
  - `grammar-edit-text` (a card's pencil).
- **Layout, mockup A:**
  - The topic list is on the left (about 220px), with the eleven standard topics in `GRAMMAR_TOPICS` order and then an "Unusual" group for `other` sections. A topic with no section is dim, and the list shows only what exists.
  - Cards are on the right. Clicking a topic scrolls to its card.
  - A card shows its title, a topic chip, the text, the tables, then the examples.
  - **Tables:** a ragged row is padded with empty cells to the column count; extra cells are shown under an empty heading (Review Focus 2).
  - **Examples:** word over meaning from `breakdown`, then the translation.
  - **Editing:** a card's text can be edited in place (pencil → textarea → Save), and saves the whole `rules.grammar` list with only that section's text changed. Tables and examples aren't edited by hand this round (3b-2b changes them).
- **The empty state:** "No grammar yet." with a hint that making the language fills it in.

- [ ] **Step 1: Write the failing e2e tests**, seeding a language whose `rules.grammar` has a nouns section (a 3-column table with one ragged row, and an example) and an `other` section:
  - `test_the_grammar_tab_lists_topics_and_cards`;
  - `test_a_table_with_a_ragged_row_renders`;
  - `test_an_example_shows_word_over_meaning`;
  - `test_an_old_text_grammar_shows_as_one_card_and_can_be_edited` (Review Focus 1: seed `rules.grammar` as a str, edit, reload the page; the text is kept);
  - `test_the_language_tab_no_longer_shows_grammar_notes`.
- [ ] **Step 2:** run. Expected: FAIL.
- [ ] **Step 3: Implement.** Build the frontend, then screenshot at 1920×1080 and a small window, against mockup A.
- [ ] **Step 4:** run `tests/e2e/worlds/test_language_grammar.py tests/e2e/worlds/test_languages_page.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(worlds-ui): a Grammar tab of sections, tables and examples`.

### Task 6: Route, model and size in the Make dialog; Still to fill in in the review

**Files:**
- Modify:
  - `talemate_frontend/src/components/worlds/LanguageMake.vue`;
  - `talemate_frontend/src/stores/worlds.js`: the draft gains `route`, `claudeModel` and `size`, seeded from `language_make_route` when the draft is empty;
  - `talemate_frontend/src/components/worlds/LanguageCheckReport.vue`: a "Still to fill in" block from `report.completeness`.
- Test: `tests/e2e/worlds/test_language_make.py`

**Interfaces:**
- Consumes: the `language_make_route` data (Task 4), and `report.completeness` in `language_preview` (Task 2).
- Produces these test ids:
  - `make-route` (the row), with `make-route-claude_code`, `make-route-in_app` and `make-route-brief`;
  - `make-model`;
  - `make-size-full`, `make-size-quick`;
  - `make-size-note`;
  - `check-still-to-fill`.
- **Layout, mockup frame 1:**
  - **Make it with:** three segmented choices, the agent's model marked "(API tokens)"; the model field appears beside Claude Code only.
  - **How much:** Full: everything in one go, or Quick, then fill in. Picking a route resets How much to that route's default, unless the owner picked one.
  - **The note line:** for Full on Claude Code, "About 300 words, phrases in every category, all the grammar topics. Runs on your subscription and takes about 10–15 minutes." The other combinations get their own plain lines.
  - With route `brief`, **Make it** gives way to **Copy the brief** as the main button (as 3b-1 did for the agent's setting).
- **The review's Still to fill in:** for example "Everyday words: 118 of 200 missing (water, hand, …) · Phrases: no oaths, insults · Grammar: Numbers not written". It's styled as information, not a warning.

- [ ] **Step 1: Write the failing e2e tests**:
  - `test_the_dialog_offers_route_model_and_size` (defaults from the route reply: Claude Code, full);
  - `test_choosing_the_agents_model_switches_to_quick`;
  - `test_a_chosen_route_is_used_for_the_run` (choose the agent's model with a fixed `language_file`; progress says "Asking the model");
  - `test_copy_the_brief_route_makes_copy_the_main_button` (Review Focus 5: then switch back, and Make it returns);
  - `test_the_copied_brief_follows_how_much` (Quick, so the clipboard has "fill in the rest later");
  - `test_the_review_shows_still_to_fill_in` (the fake's sample language is small, so `check-still-to-fill` lists missing everyday words).
- [ ] **Step 2:** run. Expected: FAIL.
- [ ] **Step 3: Implement.** Build, then screenshot against mockup frame 1.
- [ ] **Step 4:** run `tests/e2e/worlds/test_language_make.py`, then the full plain and e2e suites. Expected: 0 failures.
- [ ] **Step 5: Commit** `feat(worlds-ui): pick the route, model and how much for each language`.

### Task 7: Acceptance

**Files:** Create `docs/superpowers/probes/2026-10-29-languages-3b2a-acceptance.md`, a checklist in the 3b-1 shape: each step, what the owner looks at, and the test that proves it.

- [ ] **Step 1:** write the checklist.
- [ ] **Step 2:** ask the owner before any real Claude Code run. It's on their subscription; Full on Opus takes about 10–15 minutes.
  - Then, with their go-ahead, make "a unique but recognizably Russian language for the Tsardom of Moscavia", Full, on Opus, and record:
    - words;
    - Still to fill in;
    - sections;
    - phrases per category;
    - time.
  - Save the isolated app's `worlds/` before any restart.
- [ ] **Step 3:** record the owner's verdict, and commit `docs(languages): 3b-2a acceptance`.
