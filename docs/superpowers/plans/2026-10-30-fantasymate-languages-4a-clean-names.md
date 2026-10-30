# Languages 4a: clean names in drafts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Where a language is in reach, AI text waiting for the owner's review arrives with real names, AI stock names and stock titles already replaced by names from that language. Names it can't be sure of are marked as suspect. A hover card on each mark offers undo, reroll and "never" actions, and one Names page in the world's Settings holds the lists.

**Architecture:**
- A new `talemate.languages.cleaning` package does the work in three steps:
  1. **find** the names in the texts and judge them, using the lists, one model flag call (probe 4's V2 prompt), the real-words list and the fit check;
  2. **replace** the bad ones: names rolled from the language, a model pick among them (plus a meaning), stock titles rewritten around a `{name}` slot, then plain substitution;
  3. return **marks**.
- Each review screen runs that step on its texts after the model's reply is parsed.
- Marks become two new segment kinds in the existing `LinkedText`, with one hover card. Mark actions work on the client: each mark carries its spare rolled names, and only the lists need the server.
- The draft gains a Languages section, found from the owner's words by a name match, with roles and shares from one model call. The description is written on accept instead of in the draft.

**Tech Stack:** Python 3.11, pydantic, jinja2 prompt templates, Vue 3 + Vuetify, pytest, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-10-30-fantasymate-languages-4-design.md`, part 4a. Probe: `docs/superpowers/probes/2026-10-30-clean-names.md` (owner's verdict: matches their runs). Approved mockup: `docs/superpowers/mockups/2026-10-30-languages-4-clean-names.html` (frame 1, and layout 2A for the Names page).

## Global Constraints

- **Where no language is in reach, nothing is replaced** (spec). Names that would be replaced are marked suspect ("no language picked"), and the draft offers **Pick a language for this draft**.
- **Never replaced** (spec):
  - words the owner typed in the prompt;
  - names of entries that already exist;
  - words in the language's dictionary;
  - the world's language names and their country form;
  - title and kind words inside a name ("Tsar", "House of", "River");
  - names on a keep list.
- **Only the bad part of a name is replaced.** In "Tsar Dmitri II", only "Dmitri" is (spec).
- **The fit check only marks suspect** (owner). The model flag, the lists and the real-words list replace.
- **The languages come from a name match** of the owner's words. The model gives roles and shares only for the matched languages, and never adds one (probe 4, finding 4).
- **Swapping is plain substitution.** The model only picks among rolled names; a pick that isn't one of them falls back to the first (probe 4, finding 3).
- **Accepting forgets the old names** (owner). Nothing records Novgorod → Sovyetsk after accept.
- **Each new name still in the accepted text is saved to its language as a word,** with a meaning when one was given (owner).
- **Descriptions are not generated in the draft;** they're generated on accept (owner).
- **Lists:** real names, AI clichés and stock titles to replace, plus one keep list. There are two levels: the app's (config) and the world's (world meta). A world can turn an app row off, make its own row global, or remove an app row everywhere behind a confirm (spec).
- **Owner's UI rules:**
  - controls sit right after what they act on;
  - right-align only in half-width areas;
  - the same look is one component (one marked-text component, one hover card);
  - screenshots at 1920×1080 and a small window;
  - never restart an isolated app the owner has used without saving its `worlds/` and `config.yaml` first.
- **No jargon facing the owner.**
- **Tests:** no real model. Use queued `MockClient` replies (`tests/conftest.py:317`) and a fixed-reply file for e2e. Commands as in `docs/dev/local-testing.md`.
- **Real runs** (Task 10) need the owner's go-ahead: they use koboldcpp.

## Not in this plan

Each of these is in the spec, but left for after 4a's acceptance. They reach the owner in the final message:
- **The app suggests a cliché** when the same name keeps turning up across the world (spec, *my call*).
- **"Mark as AI cliché" from a name's right-click menu.** For now, names reach the lists from the hover card and the Names page.
- **Timelines and stubs made from a new connection** aren't cleaned, because no model writes their text (code map, 2026-10-30).
- **Group synopses** aren't cleaned: they're cached prose, like descriptions.

## Review Focus

1. **The same bad name several times in a draft,** including a possessive ("Novgorod's") and in another fact. All of them get the same new name ("Sovyetsk's"), and reroll or undo changes them together. Task 4.
2. **A rolled name that is already an entry's name, or already picked for another name in the same draft.** It's never used: candidates exclude both. Task 4.
3. **The language in reach has no name rule for the kind** (a description-only language, or one with only word rules). Nothing crashes: the names are marked suspect with "Moscavian has no name rules for this", and nothing is replaced. Task 4.
4. **The flag call fails or returns something unreadable** (empty reply, broken JSON, a timeout). The draft still arrives, cleaned by the lists and the real-words list only, and a log line records it. Task 3.
5. **The owner edits or deletes a fact holding a replaced name before accepting.** Accept saves to the language only the new names still in the accepted text, and a mark whose name is gone disappears. Task 6 and Task 7.

---

### Task 1: The name lists

**Files:**
- Create: `src/talemate/languages/cleaning/__init__.py`, `src/talemate/languages/cleaning/lists.py`, `src/talemate/languages/data/name_lists.json`
- Modify: `src/talemate/config/schema.py` (`Config.name_lists`), `src/talemate/world/store.py` (`World.name_lists` / `set_name_lists`, beside `curation`, :882), `src/talemate/server/worlds.py` (handlers)
- Test: `tests/languages/test_name_lists.py`, `tests/server/test_worlds_name_lists.py`

**Interfaces:**
- Produces:
  - `LIST_KINDS = ("real", "cliche", "title", "keep")`.
  - `NameLists(BaseModel)`: `real: list[str]`, `cliche: list[str]`, `title: list[str]`, `keep: list[str]` (all `[]` by default).
  - `WorldNameLists(NameLists)`: adds `off: list[str]`, app rows turned off here, each as `"<kind>:<name>"`.
  - `ListRow(BaseModel)`: `name: str`, `kind: str`, `scope: Literal["app", "world"]`, `off: bool`.
  - `app_lists() -> NameLists`: `Config.name_lists` when set; else the shipped `name_lists.json`.
  - `effective(world) -> NameLists`: the app's rows minus the world's `off`, plus the world's.
  - `rows(world) -> list[ListRow]`: for the Names page.
  - `match(lists: NameLists, kind: str, name: str) -> bool`. Matching is case-insensitive and ignores a leading "the" and a trailing "'s". `title` entries may hold `*` as a wildcard ("Free Cities of the *"), matched with `fnmatch`.
  - `edit(world, action: str, kind: str, name: str) -> None`. `action` is one of `add` (world), `remove` (world), `make_global` (world → app), `turn_off`, `turn_on`, `remove_everywhere` (app; also clears `off`). App edits write `Config.name_lists` and save the config.
  - Server: `get_name_lists` → `{rows}`; `name_list_edit {action, kind, name}` → `{rows}`. An unknown action or kind is refused, writing nothing.
- **The shipped file's starting contents:**
  - `real`: probe 2's 20 real names, plus the real places probe 4's drafts used (Volga, Don, Moskva, Dnepr, Kolyma, Kholmogory, Velikiy Ustyug, White Sea, Volhynia, Sokolniki, Rus, Moskovgrad, Moskov, Moskovia);
  - `cliche`: Maren, Elara, Thornwood, Kael, Lyra, Aldric;
  - `title`: probe 2's 15 stock titles, plus "Frostfang Mountains", "Frostspine Mountains", "Shivering Coast", "Shivering Sea", "Free Cities of the *", "Festival of the Longest Night", "Court of Owls", "Night Watch", "Council of Elders";
  - `keep`: empty.

- [ ] **Step 1: Write the failing tests.**
  - `test_app_lists_ship_with_the_probes_names`: "Novgorod" in `real`, "Elara" in `cliche`, "Free Cities of the *" in `title`.
  - `test_match_ignores_case_article_and_possessive`: `match(l, "real", "the volga's")` is true.
  - `test_title_shapes_match_with_a_wildcard`: "Free Cities of the Southern Coast" matches.
  - `test_a_world_row_adds_and_an_off_row_hides`: `effective` has the world's "Yelena" and lacks the turned-off "Moscow".
  - `test_make_global_moves_a_world_row_to_the_app`.
  - `test_remove_everywhere_drops_an_app_row_and_its_off_marks`.
  - Server: `test_name_list_edit_answers_with_rows`, and `test_an_unknown_kind_is_refused`.
- [ ] **Step 2: Run them.** Run: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/languages/test_name_lists.py tests/server/test_worlds_name_lists.py -q -p no:cacheprovider`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement the interfaces above.** App edits go through `talemate.config.state` (`get_config`, `save_config`).
- [ ] **Step 4: Run them again.** Expected: PASS.
- [ ] **Step 5: Commit** (`feat(languages): name lists for cleaning, app and world`).

### Task 2: The draft's languages from the owner's words

**Files:**
- Create: `src/talemate/languages/cleaning/languages.py`, `src/talemate/prompts/templates/world/language-roles.jinja2`
- Test: `tests/languages/test_clean_languages.py`

**Interfaces:**
- Produces:
  - `named_languages(view, prompt: str) -> list[str]`: language entry ids, in prompt order, whose name, other names, or name's first five letters appear in the prompt. Matching is case-insensitive and on word starts, so "Tsardom of Moscavia" finds Moscavian.
  - `async language_rows(client, view, prompt: str, ids: list[str]) -> list[dict]`: rows `{language, role, share}` (the `languages` field's row shape, `LANGUAGE_ROW_KEYS`, `kinds.py:487`).
    - One model call (`world.language-roles`, prompt kind `analyze`) asks for roles and shares for these languages only. The prompt is probe 4's `LANGUAGES_SYSTEM` (`scripts/dev/probe_clean_names.py`), limited to the given languages.
    - A row for a language not in `ids` is dropped; a role not in `LANGUAGE_ROLES` becomes `spoken`.
    - Shares are normalised to sum to 1. A failed or unreadable call gives each language `spoken` with an even share.
    - No `ids`: no call, `[]`.

- [ ] **Step 1: Write the failing tests:**
  - `test_the_country_form_finds_its_language` ("Tsardom of Moscavia" → Moscavian);
  - `test_no_language_named_means_none` ("a mountain village of herders" → `[]`, and no model call: the queue is untouched);
  - `test_two_languages_in_prompt_order`;
  - `test_the_model_cannot_add_a_language` (the queued reply adds Brelovan; the rows hold only the matched);
  - `test_a_broken_reply_gives_even_spoken_rows`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the interfaces above.** The template follows the `world.language-define` pattern (`language-define.jinja2`: an AsIsExtractor header and a `{` prefill).
- [ ] **Step 4: Run them again.** Expected: PASS.
- [ ] **Step 5: Commit** (`feat(languages): a draft's languages from the owner's words`).

### Task 3: Finding bad names

**Files:**
- Create: `src/talemate/languages/cleaning/find.py`, `src/talemate/prompts/templates/world/name-flags.jinja2`
- Test: `tests/languages/test_clean_find.py`

**Interfaces:**
- Consumes: `NameLists` and `match` (Task 1).
- Produces:
  - `Spot(BaseModel)`: `name: str` (the part to judge), `full: str` (as written), `kind: str` (an entry kind, or `"title"`), `person: Literal["man", "woman", ""]`, `texts: list[int]` (indexes of the texts it appears in).
  - `spots(texts: list[str], listed: list[tuple[str, str]], protected: set[str]) -> list[Spot]`.
    - `listed` holds the draft's own name and new names, with their kinds.
    - Capitalised runs in the texts that the list doesn't hold are added with kind `"place"` (*my call*: most unlisted real names in probe 4 were places).
    - Sentence-start words, months and weekdays are skipped. The probe's noise was "In", "The", "May".
    - A trailing "'s" is stripped.
    - Title and kind words are removed with `talemate.world.names.TITLE_WORDS` (`names.py:58`), plus kind words (River, Lake, Mountains, Sea, Coast, Isles, Forest, Marsh, Steppe, Pass), which may be extended.
    - A person's multi-word name gives one spot per word of at least 3 letters (only the bad part is replaced).
    - Names in `protected` are skipped.
  - `protected_names(view, prompt: str, language) -> set[str]`, lower-cased: the prompt's capitalised words and runs, every entry name and other name, the dictionary's words, the world's language names and their `named_languages` forms, and the keep list.
  - `Verdict(BaseModel)`: `spot: Spot`, `action: Literal["replace", "rewrite", "suspect"]`, `why: str`.
  - `async judge(client, spots: list[Spot], lists: NameLists, language: Language | None) -> list[Verdict]`. Only spots something judges bad come back. In order:
    1. `title` list match → `rewrite`, "a stock title";
    2. `real` or `cliche` match → `replace`, "on Real places" / "an AI cliché";
    3. the flag call (`world.name-flags`, probe 4's `FLAG_SYSTEM_V2` text, one call for all spots) says `real` → `replace` with its `why`, and `stock-title` → `rewrite`;
    4. a real-words hit for the language's flavour (`check._real_words`, `check.py:80`) → `replace`, "a real word";
    5. `name_fits` false (`generator.py:554`) → `suspect`, "doesn't sound like <language>".
  - A failed or unreadable flag call is skipped (logged as `languages.clean_flag_failed`); the other steps still run.
  - With `language=None`, every `replace` and `rewrite` becomes `suspect`, "no language picked".

- [ ] **Step 1: Write the failing tests:**
  - `test_sentence_starts_and_months_are_not_spots`;
  - `test_title_words_stay_and_only_the_part_is_judged` ("Tsar Dmitri II" gives a spot "Dmitri");
  - `test_a_persons_name_is_judged_word_by_word` ("Aleksei Voronov" gives two spots);
  - `test_prompt_words_and_existing_entries_are_protected` ("Tsardom of Moscavia" in the prompt; an entry named "Kolvagorsk");
  - `test_the_lists_replace_without_asking_the_model` (an empty queue);
  - `test_the_flag_call_replaces_with_its_reason` (queued V2 reply: "Velikograd" is real, "Russian 'great city'");
  - `test_a_misfit_is_only_suspect`;
  - `test_a_broken_flag_reply_still_cleans_by_the_lists` (Review Focus 4);
  - `test_no_language_makes_everything_suspect`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the interfaces above.**
- [ ] **Step 4: Run them again.** Expected: PASS.
- [ ] **Step 5: Commit** (`feat(languages): finding real names, clichés and stock titles`).

### Task 4: Replacing them, and the marks

**Files:**
- Create: `src/talemate/languages/cleaning/replace.py`, `src/talemate/prompts/templates/world/name-picks.jinja2`, `src/talemate/prompts/templates/world/title-rewrites.jinja2`
- Test: `tests/languages/test_clean_replace.py`

**Interfaces:**
- Consumes: `Verdict`, `Spot` (Task 3); `naming.roll_names` (`naming.py:70`), `generator_for` (:55).
- Produces:
  - `Mark(BaseModel)`:
    - `id: str`, `kind: Literal["replaced", "suspect"]`, `name: str` (now in the text), `was: str`, `why: str`, `meaning: str = ""`;
    - `language_id: str | None`;
    - `spares: list[str]`, the other rolled names, for reroll and **Replace it**;
    - `entry_kind: str`.
  - `Cleaned(BaseModel)`: `texts: list[str]`, `marks: list[Mark]`.
  - `async clean_texts(client, view, texts: list[str], listed: list[tuple[str, str]], prompt: str, rows: list[dict], lists: NameLists) -> Cleaned`. This is the one entry point every screen calls.
    - `rows` are the draft's Languages rows (Task 2) or the inherited ones.
    - The language per spot is the row with the largest share (*my call*). It's a row named in the same sentence when one is ("the Sorauan town of …", matched by `named_languages` on that sentence).
    - Candidates: 6 from `roll_names(language, entry_kind, count=6, exclude=…)`. `exclude` holds every entry name, every protected name, and every name already picked in this draft (Review Focus 2).
    - **One pick call** (`world.name-picks`) for all `replace` verdicts: probe 4's `SWAP_SYSTEM`, batched. For each it gives the sentence, the candidates and the person (man or woman, from the facts), and asks for `{"pick", "meaning"}`. A pick not among the candidates becomes the first candidate. A failed call takes the first candidate for each, with an empty meaning.
    - **One rewrite call** (`world.title-rewrites`) for all `rewrite` verdicts: probe 2's `REWRITE_SYSTEM_V2` (`scripts/dev/probe_name_flags.py:85`), batched, plus "keep the kind of thing". `{Name}` is accepted as the slot. A reply with no slot keeps the title and marks it `suspect`, "a stock title".
    - **Substitution** is plain and whole-word in every text. "'s" stays, and all occurrences of one name share one mark (Review Focus 1).
    - A spot whose language has no name rule for its kind (`generator_for` raises) becomes `suspect` with "<language> has no name rules for this" (Review Focus 3).
  - `apply_mark(texts: list[str], mark: Mark, new: str) -> list[str]`: whole-word swap of `mark.name` for `new`, possessives kept. Used by the client mirror in Task 7 and by tests.

- [ ] **Step 1: Write the failing tests:**
  - `test_a_real_place_is_swapped_in_every_text_with_one_mark` ("Novgorod" and "Novgorod's" in two facts → "Sovyetsk", "Sovyetsk's"; one mark);
  - `test_a_pick_outside_the_candidates_falls_back_to_the_first`;
  - `test_candidates_never_reuse_an_entry_or_an_earlier_pick`;
  - `test_the_pick_brings_a_meaning`;
  - `test_a_stock_title_keeps_its_frame` ("the Iron Council" → "the Iron Bench of Zizhigrad");
  - `test_a_rewrite_without_a_slot_stays_suspect`;
  - `test_a_language_without_name_rules_leaves_names_suspect`;
  - `test_the_named_language_in_a_sentence_wins`;
  - `test_a_failed_pick_call_takes_the_first_candidate`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the interfaces above.**
- [ ] **Step 4: Run them again.** Expected: PASS.
- [ ] **Step 5: Commit** (`feat(languages): replacing bad names, with marks`).

### Task 5: Cleaning the new-entry draft

**Files:**
- Modify: `src/talemate/worldplay/create.py` (`CreatePreview` :455, `preview_thing` :2873), `src/talemate/server/worlds.py` (`handle_preview_thing` :2998, `_fixed_preview` :1266, new `handle_draft_languages`)
- Test: `tests/worldplay/test_create_cleaning.py`, `tests/server/test_worlds_plugin.py` (additions)

**Interfaces:**
- Consumes: `clean_texts`, `Mark`, `Cleaned` (Task 4); `named_languages`, `language_rows` (Task 2); `effective` (Task 1).
- Produces:
  - `CreatePreview` gains `languages: list[dict] = []` (the draft's Languages rows, with `"from_words": true` on found ones) and `marks: list[Mark] = []`.
  - **In `preview_thing`:**
    - before the model call, `named_languages` runs on the prompt;
    - right after `parse_create_reply` (~:3147), and before `_new_names`, `repeat_flags` and `parse_elsewhere`'s writes, one `clean_texts` call cleans together the name, the facts, the summary and the elsewhere texts.
    - The rows used are the found rows (`language_rows`), else the inherited ones (`languages_for` on the filing target). With no rows and no inherited languages, `judge` runs with `language=None`.
  - **Every `replaced` mark is added to `new_names`** as a stub of its `entry_kind`, ticked. `NewName` gains `replaced: str = ""` (`links.py:103`), shown as "replaced Novgorod".
  - **The draft's prose isn't generated:** the `_preview_prose` call at :3303 is removed, and `prose` stays `{}` (Task 6 writes it on accept).
  - **`draft_languages {draft_key, rows}`** sets a draft's rows and cleans the draft's current texts again (marks rerolled). Answers like `preview_thing`.
  - **e2e hook:** `FIXED_CLEAN_ENV = "TALEMATE_TEST_FIXED_CLEAN"`, a JSON file of canned replies `{flags, picks, rewrites, roles}`. When it's set, the cleaning calls answer from it instead of the client, and `_fixed_preview` runs the cleaning too. Add `fixed_clean` to `tests/e2e/conftest.py`, following `_fixed_reply_fixture`.

- [ ] **Step 1: Write the failing tests:**
  - `test_a_draft_with_a_language_in_reach_arrives_cleaned` (queued: the create reply with "Novgorod" in a fact, then flags, then picks; the facts say "Sovyetsk", with one mark and a new name "replaced Novgorod");
  - `test_the_draft_finds_its_language_from_the_prompt` (languages == [Moscavian official]);
  - `test_a_draft_with_no_language_replaces_nothing` (the existing preview tests' queues still pass unchanged: no extra calls without a language);
  - `test_the_draft_has_no_prose`;
  - `test_changing_the_drafts_languages_cleans_it_again`;
  - `test_the_fixed_clean_file_answers_the_cleaning`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the interfaces above.**
- [ ] **Step 4: Run them, then the whole plain suite** (`… pytest -q -p no:cacheprovider`). Expected: PASS. Fix any existing test that counted prose calls in the queue: the draft no longer makes them.
- [ ] **Step 5: Commit** (`feat(languages): drafts arrive with names cleaned`).

### Task 6: Accepting a cleaned draft

**Files:**
- Modify: `src/talemate/worldplay/create.py` (`accept_preview` :3477, `_accept_new` ~:3618), `src/talemate/server/worlds.py` (`handle_accept_preview` :3670)
- Test: `tests/worldplay/test_create_cleaning.py`

**Interfaces:**
- Consumes: `CreatePreview.languages`, `.marks`.
- Produces:
  - **On accept:**
    - the preview's `languages` rows are written as the new entry's own `languages` field (without `from_words`);
    - every `replaced` mark whose `name` is still in the accepted name or facts is saved to its language with `naming.add_word(rev, language_id, name, meaning)` (`naming.py:173`), in the same revision (Review Focus 5);
    - suspect marks and marks whose name is gone save nothing.
  - **The description is generated after accept:** the new thing's id goes into the reply's `prose` list, and `handle_accept_preview` passes it to `_schedule_prose` (:2619).
  - Nothing stores `was`.

- [ ] **Step 1: Write the failing tests:**
  - `test_accept_writes_the_drafts_languages`;
  - `test_accept_saves_each_new_name_as_a_word` (meaning kept);
  - `test_a_name_edited_out_before_accept_is_not_saved`;
  - `test_the_description_is_scheduled_on_accept`;
  - `test_accept_is_one_revision` (undo removes the entry and the words together).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the interfaces above.**
- [ ] **Step 4: Run them again.** Expected: PASS.
- [ ] **Step 5: Commit** (`feat(languages): accepting saves languages, words and the description`).

### Task 7: Marks and the hover card on the draft page

**Files:**
- Create: `talemate_frontend/src/components/worlds/NameMarkCard.vue`, `talemate_frontend/src/components/worlds/nameMarks.js`
- Modify:
  - `LinkedText.vue` (two segment kinds);
  - `draftPage.js` (`previewSegments` :79);
  - `worlds.py` `_draft_payload` (:3223), which emits mark segments;
  - `ThingPage.vue` (the draft's Languages section; `EntryLanguages` is hidden on drafts at :294);
  - `PreviewStubs.vue` ("replaced X");
  - `stores/worlds.js` (`draftLanguages`, `nameListEdit`).
- Test: `tests/e2e/worlds/test_clean_names.py`

**Interfaces:**
- Consumes: `CreatePreview.marks` and `.languages` (Task 5); `name_list_edit` (Task 1).
- Produces:
  - **Segments** `{kind: "replaced" | "suspect", text, mark_id}`. In `LinkedText`:
    - a replaced name has a dotted underline in the `link` role;
    - a suspect one has a wavy underline in the `warning` role.
    
    Both open `NameMarkCard` on hover, the same way `StubCard` opens.
  - **`NameMarkCard`:**
    - **replaced:** "<name> · was <s>old</s>", the why, the meaning. Actions:
      - **Reroll:** the next spare;
      - **Keep <old> here:** back to the old name, mark dropped;
      - **Never replace <old> in this world:** `name_list_edit add keep` plus keep here.
    - **suspect:** the name, the why. Actions:
      - **Replace it:** the first spare, which becomes a replaced mark;
      - **Keep it:** mark dropped;
      - **Never flag it in this world:** `add keep`, mark dropped.
    
    Test ids: `name-mark`, `mark-reroll`, `mark-keep-here`, `mark-never`, `mark-replace`, `mark-keep`.
  - **`nameMarks.js`:** `applyMark(texts, mark, newName)`, mirroring Task 4's `apply_mark`, and `markAction(draft, markId, action)`. They edit the draft's name, facts, new names and marks on the client, then re-render as a fact edit does (`draft_render`).
  - **The draft's Languages section:** `EntryLanguages` shown on drafts, editable, with "from your words" on found rows. A change calls `draft_languages`.
  - **With no language in reach,** the section shows **Pick a language for this draft** (the right-click's language picker).

- [ ] **Step 1: Write the failing e2e tests** (with `fixed_preview` and `fixed_clean`):
  - `test_a_replaced_name_shows_its_card` (hover "Sovyetsk"; the card says "was Novgorod");
  - `test_reroll_changes_every_occurrence`;
  - `test_keep_here_puts_the_old_name_back`;
  - `test_never_replace_adds_to_the_keep_list` (the Names rows hold it, Task 9's handler);
  - `test_a_suspect_name_can_be_replaced_or_kept`;
  - `test_the_draft_shows_its_language_from_your_words`;
  - `test_no_language_offers_pick_a_language`;
  - `test_accept_keeps_only_the_new_names` (the entry's facts say "Sovyetsk", and the language's Lexicon has "Sovyetsk").
- [ ] **Step 2: Run them.** Run: `… pytest tests/e2e/worlds/test_clean_names.py -m e2e -n 4 -q -p no:cacheprovider`. Expected: FAIL.
- [ ] **Step 3: Implement the interfaces above, and build the frontend.**
- [ ] **Step 4: Run them again.** Expected: PASS. Take screenshots at 1920×1080 and 1280×800, and compare them with mockup frame 1. **The suspect mark and its card are new to the owner: show them before going on** (spec).
- [ ] **Step 5: Commit** (`feat(worlds-ui): replaced and suspect names, with their card, on drafts`).

### Task 8: Cleaning Add facts, Add event and group + Add

**Files:**
- Modify:
  - `src/talemate/worldplay/facts.py` (`draft_facts` :245, `draft_facts_for` :307; `FactDraft` :109 gains `marks`, `languages`);
  - `src/talemate/worldplay/groups.py` (`group_add` :481; `GroupAddDraft` gains `marks`);
  - `src/talemate/server/worlds.py` (`handle_accept_facts` :4656, `handle_write_nested_facts` :4493, `handle_accept_group_add` :4184; fixed paths);
  - `EntryAddFacts.vue`, `GroupAddForm.vue` (the line through `LinkedText`), `draftPage.js` (`factDraftSegments`).
- Test: `tests/worldplay/test_facts_cleaning.py`, `tests/worldplay/test_groups_cleaning.py`, `tests/e2e/worlds/test_clean_names.py` (additions)

**Interfaces:**
- Consumes: `clean_texts` (Task 4), `NameMarkCard` and `nameMarks.js` (Task 7), Task 6's word saving (extract it as `save_mark_words(rev, marks, texts)` in `cleaning/replace.py` and use it in all three accepts).
- Produces:
  - **Each of these drafts runs `clean_texts`** on its texts right after its reply is parsed.
  - **Rows:** the entry's own languages (`languages_for` on the entry, or on the group's entry for group add). The owner's words in the request also count (`named_languages`).
  - **On accept,** the words are saved as in Task 6.
  - **The same card and actions** as Task 7.
  - Scene setup's stub previews come through `preview_thing` and are cleaned by Task 5 with no extra work; their cards use `previewSegments`.

- [ ] **Step 1: Write the failing tests:**
  - `test_add_facts_cleans_real_names` (an entry speaking Moscavian; "Novgorod" in a drafted fact);
  - `test_add_facts_without_a_language_marks_suspect_only`;
  - `test_group_add_cleans_its_lines`;
  - `test_accepting_added_facts_saves_the_words`;
  - e2e: `test_add_facts_shows_marks_and_the_card`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the interfaces above.**
- [ ] **Step 4: Run them, and the whole plain suite.** Expected: PASS.
- [ ] **Step 5: Commit** (`feat(languages): Add facts and group add are cleaned too`).

### Task 9: The Names page in the world's Settings

**Files:**
- Create: `talemate_frontend/src/components/worlds/NamesSettings.vue`
- Modify: `WorldTab.vue` (:137, the Settings tab gains General | Names tabs; General is today's `CurationSettings.vue`), `stores/worlds.js` (`nameLists`, `loadNameLists`)
- Test: `tests/e2e/worlds/test_names_settings.py`

**Interfaces:**
- Consumes: `get_name_lists` and `name_list_edit` (Task 1).
- Produces:
  - **Mockup 2A:** a "Replace" panel with Real names | AI clichés | Stock titles tabs, beside a "Keep as they are" panel.
  - **Each row** shows its name and a scope chip: "all worlds" (`link` role) or "this world".
  - **Actions right after each row:**
    - world rows: **Make it global**, **Remove**;
    - app rows: **Turn off here** or **Turn on here**, and **Remove everywhere**, behind a confirm.
  - **+ Add** after each panel's heading adds a world row.
  - The note under the title, and "The model also catches real names that aren't on any list", as in the mockup.
  - Test ids: `names-tab`, `names-replace`, `names-keep`, `names-row`, `names-add`, `names-global`, `names-remove`, `names-off`, `names-remove-everywhere`.

- [ ] **Step 1: Write the failing e2e tests:**
  - `test_the_settings_tab_has_general_and_names`;
  - `test_the_names_page_shows_app_and_world_rows`;
  - `test_add_then_make_it_global`;
  - `test_turn_off_here_keeps_it_for_other_worlds` (a second world still shows it on);
  - `test_remove_everywhere_asks_first`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the interfaces above, and build the frontend.**
- [ ] **Step 4: Run them again.** Expected: PASS. Take screenshots at both sizes and compare them with mockup 2A.
- [ ] **Step 5: Commit** (`feat(worlds-ui): the Names page`).

### Task 10: Acceptance

**Files:**
- Create: `docs/superpowers/probes/2026-10-30-languages-4a-acceptance.md`

- [ ] **Step 1: Write the checklist:** each spec goal, what the owner looks at, and the tests that prove it (as in the 3b-2b checklist).
- [ ] **Step 2: Real runs, with the owner's go-ahead (koboldcpp).** Start a fresh test app with the saved Moscavian imported. Then:
  - make the Moscavia starter and a noble-house draft;
  - run **Add facts** on the noble house.

  Record:
  - what was replaced, what was marked suspect, and what slipped through;
  - how long cleaning added to a draft (probe 4: drafts take about 36 s);
  - whether the swapped sentences read right.
- [ ] **Step 3: The owner looks in the test app.** Record their verdict.
- [ ] **Step 4: Commit** (`docs(languages): 4a acceptance`).
