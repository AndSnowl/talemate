# Languages 4b-1: the grammar engine for names — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Languages carry grammar rules for names. Name rules can be composed of parts. Every name built from a meaning follows the language's word order and word forms. The Name it panel builds composed names part by part, and the Names chapter shows and edits the rules.

**Architecture:**
- A pure-Python engine in `talemate.languages` with no model calls: `name_grammar.py` holds the rules model, forms and phrase building; `composed.py` rolls composed rules part by part.
- A separate model layer, `naming_meaning.py`, turns an English meaning or an entry's facts into phrase structures. The engine then builds the words.
- The server adds three Name it actions and one Names-chapter action.
- On the frontend, the Name it panel gains a builder, and the language page's Names chapter gains a Grammar for names card.

**Tech Stack:**
- Python 3.11 and pydantic (backend); Vue 3, Vuetify and Pinia (frontend);
- tests: pytest, Playwright e2e, and `talemate_frontend/checks/worlds.check.mjs`.

**Spec:** `docs/superpowers/specs/2026-11-02-fantasymate-languages-4b1-grammar-engine-design.md`. Mockups: `docs/superpowers/mockups/2026-11-02-languages-4b1-name-it-builder.html` (option **B**) and `docs/superpowers/mockups/2026-11-02-languages-4b1-names-chapter.html`.

## Global Constraints

- **Branch:** `feature/languages-4b1` from `main`, worktree `.worktrees/languages-4b1`.
- **Environment:** guix, `guix shell -m manifest.scm -- uv run --no-sync pytest … -q -p no:cacheprovider`.
  - e2e: `pytest tests/e2e -m e2e -n 4` (about 7 min).
  - frontend checks: `guix shell -m ../manifest.scm -- node checks/worlds.check.mjs`, with new checks placed **before** the summary block at the end of the file.
  - frontend build: `npx --yes corepack@0.34.0 pnpm build`.
- **No new dependencies.**
- **No model call** on Reroll, pin, pick, or building from a known structure (spec, Anti-goals).
- **The model never does the grammar:** it picks meanings only, and the engine builds forms and order (spec, Anti-goals).
- **Old language files** (no `name_grammar`, no composed rules) load and behave exactly as in 4a.
- **AI runs:** koboldcpp and Claude Code runs only with the owner's go-ahead. Ask before the probe (Task 4) and before acceptance runs (Task 9).
- **The owner's test app** holds their worlds. Never restart it with `talemate_app.py stop/start`: that wipes its root. Restart the backend process alone, after backing up `worlds/` and `config.yaml`, and ask first.
- **UI rules:** controls sit by their content; the same look means the same component (4a's `NameRolls.vue` chips with pins are reused); screenshots at 1920×1080.

## Review Focus

1. **A composed rule that names a missing rule, or itself, directly or through another rule.** The roll shows that part as "(missing rule)" and never loops. Task 3: `test_a_part_naming_a_missing_or_looping_rule_does_not_hang`.
2. **Pins when Reroll changes the rule's shape** (a rule with two shapes of different lengths). A pin holds when its part kind still exists at that index; otherwise it's dropped, with no stale text shown. Task 3: `test_pins_survive_only_where_the_shape_has_that_part`.
3. **A row edited in the Names chapter into something the engine can't apply** (an empty ending, an unknown condition). The card shows "can't build: …" in that row's example; the page doesn't break, and other rows keep their examples. Task 5: `test_a_row_that_cannot_build_says_so`.
4. **Elision and capitals:** Drassonais "lo" before a vowel is "l'", so "the water" is "l'auvre", capitalised "L'Auvre", not "L'auvre" or "Lo Auvre". Task 2: `test_a_word_before_elides_and_capitalises`.
5. **A meaning that's both a dictionary word and another word's meaning,** or that several words mean. Lookup order: an exact word first, then the first entry whose meanings include it. It's stable across calls, never random. Task 2: `test_meaning_lookup_is_stable_and_word_first`.

---

## File structure

- **Create** `src/talemate/languages/name_grammar.py`:
  - the rules model (`FormChange`, `Ending`, `OfRule`, `NameGrammar`, `MeaningPhrase`, `Built`);
  - conditions;
  - `apply_form`, `apply_ending`, `lookup_word`, `build_phrase`;
  - plain-words rows with built examples (`grammar_rows`).
- **Create** `src/talemate/languages/composed.py`: the composed-rule model use (`NamePart`, `NameShape` live in `models.py`), plus `roll_parts`, `roll_composed` and `random_phrase`.
- **Create** `src/talemate/languages/naming_meaning.py`: model calls `split_meaning` and `suggest_phrases`, prompt templates, and fixed replies for tests.
- **Create** prompt templates `src/talemate/prompts/templates/world/name-meaning-split.jinja2` and `name-suggest.jinja2`.
- **Modify** `src/talemate/languages/models.py`: `Language.name_grammar`, `GeneratorDef.shapes`, and `patterns` defaulting empty when `shapes` is set.
- **Modify:**
  - `src/talemate/languages/entry.py`: fields round trip, `rules["name_grammar"]`;
  - `generator.py`: `roll`/`fits` with composed rules;
  - `naming.py`: `generator_for` prefers plain; `translate_text` grammatical;
  - `naming_panel.py`: `rules_of` with parts;
  - `check.py`: validate; samples;
  - `changes.py`: merge `name_grammar`;
  - `completeness.py`: "grammar for names";
  - `brief.py`, `making.py`: kind `names`;
  - `language.schema.json`;
  - `.claude/skills/language-design/SKILL.md`, plus `reference/rule-syntax.md`.
- **Modify** `src/talemate/server/worlds.py` with the actions `name_it_parts`, `name_it_meaning` (rule-aware), `name_it_suggest`, `language_name_grammar`, and `language_make_start` accepting kind `names`.
- **Frontend:**
  - **Create** `talemate_frontend/src/components/worlds/NameBuilder.vue` (mockup B) and `NameGrammarCard.vue` (Names chapter).
  - **Modify** `NameItPanel.vue`, `LanguageSections.vue` (Name rules card: composed rules as part chips, parts editor), `LanguageBook.vue` (mounts the card), and `stores/worlds.js`.

---

### Task 1: The rules in the file

**Files:**
- Create: `src/talemate/languages/name_grammar.py`, with only the models and `parse_condition` in this task.
- Modify: `models.py`, `entry.py`, `changes.py`, `completeness.py`, `check.py`, `language.schema.json`.
- Test: `tests/languages/test_name_grammar_model.py`.

**Interfaces — Produces:**
- `FormChange(BaseModel)`:
  - `when: str = ""`;
  - `kind: Literal["ending", "swap", "word_before", "word_after", "double"]`;
  - `text: str = ""`;
  - `drop: str = ""`.
- **Conditions (`when`):**
  - `""` always;
  - `"after_vowel"`, `"after_consonant"`: the word's end;
  - `"before_vowel"`: the word's start, for `word_before`;
  - `"ends:a|o"`: the word ends with one of the given letters.
- `parse_condition(when: str) -> Callable[[str, frozenset[str]], bool]`. It raises `ValueError("unknown condition: …")`. The second argument is the language's vowels.
- `Ending(BaseModel)`: `ending: str`, `meaning: str`, `example: str = ""`, `changes: list[FormChange] = []`. An empty `changes` means one plain `ending` change with `text=ending`.
- `OfRule(BaseModel)`:
  - `how: Literal["word", "ending"] = "word"`;
  - `text: str`;
  - `word_side: Literal["before", "after"] = "before"`: the of-word before or after its noun;
  - `place: Literal["before", "after"] = "after"`: the of-phrase before or after the owned thing;
  - `the: bool = False`.
- `NameGrammar(BaseModel)`:
  - `describing: Literal["before", "after"] = "before"`;
  - `of: OfRule | None = None`;
  - `joining: Literal["describing_first", "main_first"] = "describing_first"`;
  - `clip_first: bool = False`;
  - `the: list[FormChange] = []`;
  - `more_than_one: list[FormChange] = []`;
  - `endings: list[Ending] = []`.
- `NamePart(BaseModel)`, in `models.py`:
  - `kind: Literal["rule", "word", "meaning"]`;
  - `rule: str = ""`;
  - `word: str = ""`;
  - `slot: Literal["noun", "describing_noun"] = "noun"`;
  - `forms: list[Literal["the", "more_than_one"]] = []`;
  - `of: bool = False`;
  - `joined: bool = False`;
  - `ending: str = ""`: an ending's meaning, such as "land of";
  - `hint: str = ""`;
  - `optional: bool = False`;
  - `label: str = ""`.
- `NameShape(BaseModel)`: `parts: list[NamePart]`, `weight: int = 1`.
- `GeneratorDef.shapes: list[NameShape] = []`. A generator with `shapes` may have `patterns == []`.
- `Language.name_grammar: NameGrammar | None = None`, stored in the entry's `rules["name_grammar"]`.

- [ ] **Step 1: Write the failing tests** in `tests/languages/test_name_grammar_model.py`:
  - `test_a_language_round_trips_name_grammar_and_shapes`: `language_of(fields_of(lang))` keeps `name_grammar` and a generator's `shapes` (the Varovni owl-name: `[rule men, word "Ul", meaning noun more_than_one]`).
  - `test_an_old_language_loads_without_them`: a language dict without either loads; `name_grammar is None`; `shapes == []`.
  - `test_conditions_parse`:
    - `parse_condition("after_vowel")("zvesta", V)` is True;
    - `("ends:a|o")("dervo", V)` is True;
    - `parse_condition("sideways")` raises `ValueError`.
  - `test_check_reports_a_part_naming_no_rule`: `check_language` on a shape naming rule `"nobody"` gives a problem mentioning `nobody`.
  - `test_merge_keeps_the_owners_name_grammar_edit`: `merge_change` with the owner's `describing="after"` and an unchanged base keeps `"after"`.
  - `test_still_to_fill_in_lists_grammar_for_names`: `completeness(lang_without_grammar)` lists `"grammar for names"` under what's missing; with `name_grammar` set it doesn't.
- [ ] **Step 2: Run them.** `…pytest tests/languages/test_name_grammar_model.py -q`. Expected: FAIL (import errors).
- [ ] **Step 3: Implement the interfaces above.**
  - `changes.merge_change` treats `name_grammar` as one value (`_pick`).
  - `check_language` adds problems for:
    - unparseable conditions;
    - shape parts naming unknown rules;
    - a generator with neither patterns nor shapes.
  - `language.schema.json` gains both fields.
  - The vowel set for conditions comes from `Language.categories["V"]` when present, else `aeiouy`.
- [ ] **Step 4: Run them again.** Expected: PASS. Then run `tests/languages` to confirm nothing broke.
- [ ] **Step 5: Commit** (`feat(languages): grammar for names and composed rules in the language file`).

### Task 2: The grammar engine

**Files:**
- Modify: `src/talemate/languages/name_grammar.py`.
- Test: `tests/languages/test_name_grammar.py`, with fixtures for the six owner languages' relevant rules, written by hand from their grammar sections (listed in the spec's Why).

**Interfaces — Produces:**
- `apply_form(grammar: NameGrammar, vowels: frozenset[str], word: str, form: Literal["the", "more_than_one"]) -> str`: the first change whose condition holds; no match leaves the word as it is.
- `apply_ending(grammar, vowels, word: str, meaning: str) -> str`. It raises `KeyError` for an ending meaning the grammar lacks.
- `lookup_word(language: Language, meaning: str) -> DictionaryEntry | None`: an exact word first, then the first entry (in dictionary order) whose `meanings` include it, case-insensitively.
- `MeaningPhrase(BaseModel)`:
  - `noun: str`;
  - `describing: list[str] = []`;
  - `of: bool = False`;
  - `the: bool = False`;
  - `more_than_one: bool = False`;
  - `joined: bool = False`;
  - `ending: str = ""`.
  These are all English meanings.
- `Built(BaseModel)`:
  - `text: str`;
  - `parts: list[dict]`: each `{word, meaning, new: bool, steps: list[str]}`, where `steps` reads like `"-i more than one"`.
- `build_phrase(language: Language, phrase: MeaningPhrase, words: dict[str, str], new: frozenset[str] = frozenset()) -> Built`. `words` maps each English meaning to its language word, already resolved; `new` lists coined words.
  - **The algorithm** is not determined by the signature:
    1. The noun's word, with an ending if `phrase.ending`, then `more_than_one`, then `the` (`the` applied after the plural, as Varovni says).
    2. The describing words, in the order `grammar.describing` puts them. With `joined`, they're glued to the noun in `joining` order, the first clipped to its first syllable if `clip_first`.
    3. If `of`: the of-word set on its `word_side` of the result, or the of-ending appended. With `of.the`, `the` is applied to the noun first.
    4. Each space-separated word is capitalised; an elided prefix keeps its apostrophe ("L'Auvre").
  - A language with `name_grammar is None` builds in the given order: describing words first, "of" is the English-less plain join of the words, no forms. That's 4a's behaviour.
- `GrammarRow(BaseModel)`: `key: str`, `label: str`, `rule: str` (plain words), `example: str`, `error: str = ""`.
- `grammar_rows(language: Language) -> list[GrammarRow]`, one row each for adjectives, "of", joined words, "the", more than one, and each ending. The example comes from the grammar tables' first noun when a section has a table, else the first dictionary noun. It never raises: a failing row gets `error` and an empty `example`.

- [ ] **Step 1: Write the failing tests:**
  - `test_varovni_the_and_plural`: `skelt` → `skeltek` (the), `skelti` (more than one); `ulkha` → `ulkhani` (more than one, after a vowel), and → `ulkhanik` (more than one, then the).
  - `test_tsevrani_swap`: `zhelva`, `dervo` → `zhelvy`, `dervy` (`ends:a|o`, swap `drop` one letter, `text "y"`).
  - `test_bumbagoo_double`: `bumpa` → `bubumpa`.
  - `test_a_word_before_elides_and_capitalises` (Review Focus 4): Drassonais the, with `word_before "l'"` when `before_vowel` and else `"lo"`. `auvre` → `l'auvre`; the built name of `MeaningPhrase(noun="water", the=True)` is `"L'Auvre"`; `chinou` → `"Lo Chinou"`.
  - `test_varovni_of_the_stars`: `MeaningPhrase(noun="star", of=True, more_than_one=True)` with of `{word "ul", word_side before}` and `words={"star": "zvesk"}` builds `"Ul Zveski"`. Its parts show `zvesk "star"` with the steps `-i more than one`.
  - `test_describing_order`:
    - Varovni `white owl` → `"Ilvo Ulkha"`;
    - Drassonais (after) `white lake` with `{"white": "blanchic", "lake": "aunfoimtte"}` → `"Aunfoimtte Blanchic"`.
  - `test_joined_with_clip`: Tsevrani joined `white road` with `clip_first` gives `"Beldorvesh"` from `belesh` (clipped to `bel`) + `dorvesh`.
  - `test_ending_by_meaning`: Varsenyk `"land of"` with changes `[ending "enya" when after_consonant, swap drop "a" text "enya" when ends:a]`, `varsa` → `varsenya`.
  - `test_no_grammar_builds_in_the_given_order`: with `name_grammar=None`, `white lake` → `"Blanchic Aunfoimtte"`.
  - `test_meaning_lookup_is_stable_and_word_first` (Review Focus 5): a dictionary with `sol` meaning "sun", and `aster` meaning "sun" and "star". `lookup_word(lang, "sun")` is `sol` on every call; a word `star` that's also a word spelled "star" returns the word entry.
  - `test_grammar_rows_build_examples`: Varovni rows include `GrammarRow(label='"the"', example="skelt → skeltek")` and the endings row; a language without grammar gives `[]`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the interfaces above.**
- [ ] **Step 4: Run them again.** Expected: PASS.
- [ ] **Step 5: Commit** (`feat(languages): the grammar engine builds forms and name phrases`).

### Task 3: Composed rules roll

**Files:**
- Create: `src/talemate/languages/composed.py`.
- Modify: `generator.py` (`roll`, `fits`, `name_fits`), `naming.py` (`generator_for`, `roll_names`), `naming_panel.py` (`rules_of`, `batch`), `check.py` (samples).
- Test: `tests/languages/test_composed.py`.

**Interfaces:**
- **Consumes:** Task 1 models; Task 2 `build_phrase`, `lookup_word`, `apply_form`.
- **Produces:**
  - `PartRoll(BaseModel)`:
    - `index: int`;
    - `kind: str`;
    - `label: str`: "man's name", "fixed" or "a meaning · plural";
    - `rolls: list[Built]`;
    - `pinned: bool = False`.
  - `roll_parts(language: Language, rule_id: str, *, count: int = 8, pinned: dict[int, str] | None = None, shape: int | None = None, rng: random.Random | None = None, exclude: frozenset[str] = frozenset()) -> tuple[int, list[PartRoll]]`:
    - It returns the shape index used, and each part's rolls.
    - A pinned or typed part's only roll is its text, and that part is marked `pinned`.
    - `shape=None` picks a shape by weight.
    - A pin holds only when the chosen shape has a part of the same `kind` at that index (Review Focus 2).
  - `random_phrase(language, part: NamePart, rng) -> tuple[MeaningPhrase, dict[str, str]]`:
    - It picks a random dictionary entry whose `part` is `noun` (or has no part) for the noun, and adjectives for describing words when the slot is `describing_noun`.
    - It sets the part's forms, `of`, `joined` and `ending`.
    - The dictionary map is from each meaning (the entry's first meaning) to its word.
  - `roll_composed(language, generator: GeneratorDef, count, rng, exclude) -> list[str]`: whole names, each part's first roll joined by spaces, optional parts kept half the time, unique.
  - `generator.roll` delegates to `roll_composed` when `generator.shapes`.
  - `naming.generator_for` prefers a generator with `patterns` over one with only `shapes` for the same `use`.
  - `rules_of` gives each rule `parts: list[str]` (labels, for display) beside `patterns`.
  - `fits` and `name_fits` count a word as fitting when it's:
    - a dictionary word;
    - a dictionary word with a form or ending applied, checked by applying each form to each dictionary word, cached per language key;
    - a fixed word of any shape.

- [ ] **Step 1: Write the failing tests:**
  - `test_owl_names_roll_from_parts`: Varovni with `men` (pattern `[dorvak|zemol]`) and owl-names `[rule men, word "Ul", meaning noun more_than_one]`, and dictionary `zvesk "star"`, `skelt "stone"`. `roll(lang, "owl", 5)` gives names matching `^(Dorvak|Zemol) Ul (Zveski|Skelti)$`.
  - `test_a_pin_keeps_its_part`: `roll_parts(lang, "owl", pinned={0: "Dorvak"})` gives part 0 rolls `["Dorvak"]` with `pinned=True`; part 2 has up to 8 distinct rolls.
  - `test_pins_survive_only_where_the_shape_has_that_part` (Review Focus 2): a rule with shapes `[rule men, word "Ul", meaning]` and `[meaning]`. A pin at index 2 with `shape=1` is dropped: no part is `pinned`.
  - `test_a_part_naming_a_missing_or_looping_rule_does_not_hang` (Review Focus 1):
    - rule A's part names B, and B's names A;
    - `roll(lang, "A", 3)` returns within 1 s;
    - that part's text is `"(missing rule)"`, and the same goes for a part naming `"gone"`.
  - `test_the_plain_rule_stays_the_default`: with plain `men` and composed `owl` both `use="character"`, `generator_for(lang, "character").id == "men"`.
  - `test_a_built_name_fits`: `name_fits(lang, "Dorvak Ul Zveski")` is True, and `name_fits(lang, "Dorvak Ul Xqzt")` is False.
  - `test_samples_include_composed_rules`: `check_language(lang).samples["owl"]` is non-empty.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the interfaces above.** Cycle guard: a depth limit of 4 when a rule part rolls another composed rule.
- [ ] **Step 4: Run them again,** then all of `tests/languages`. Expected: PASS.
- [ ] **Step 5: Commit** (`feat(languages): composed name rules roll part by part`).

### Task 4: Probe 4b-1 (ask the owner before any run)

**Files:**
- Create: `scripts/probes/probe_4b1.py`.
- Create: `docs/superpowers/probes/2026-11-02-languages-4b1.md`.

- [ ] **Step 1: Write the harness and its labels before any call** (as probe 4 did). There are two parts:
  - **(a) Fill them in.** For each of the six languages in the owner's test-app worlds, read-only: `.worktrees/languages-4a/.superpowers/sdd/2026-11-01-fantasymate-languages-4a-revised-name-it/app/worlds`.
    - Write a Claude Code (agent route) brief: "write `name_grammar` from this language's grammar sections and tables", with the schema section that Task 7's brief adds. The harness carries a draft of it.
    - Score each returned grammar by whether `apply_form` reproduces the language's own noun tables ("skelt → skeltek, skelti"). Record misses.
  - **(b) Split and suggest** on Skyfall (koboldcpp, world model):
    - 20 meanings, labelled with their expected `MeaningPhrase`: "of the Stars", "white lake", "the old grey stones", "lakeland", "Owl-of-Frost", "the sun's daughter"…
    - 10 entries' facts from Test3 for Suggest, scored by hand for fit.
- [ ] **Step 2: Ask the owner for the go-ahead.** Then run (a) and (b). Record the results and a decision in the probe report:
  - which client splits (world model, or the language agent's client, per the spec's fallback);
  - the prompts' final wording.
- [ ] **Step 3: Commit** (`probe(languages): probe 4b-1, filling in grammar and splitting meanings`).

### Task 5: The Names chapter: Grammar for names

**Files:**
- Create: `talemate_frontend/src/components/worlds/NameGrammarCard.vue`.
- Modify: `LanguageBook.vue` (mount under the Names chapter's rules), `LanguageSections.vue` (Name rules card: composed rules as part chips; a parts editor in the rule's edit form), `stores/worlds.js`, `src/talemate/server/worlds.py`.
- Test: `tests/server/test_worlds_name_grammar.py`, `tests/e2e/worlds/test_names_chapter.py`, checks.

**Interfaces:**
- **Consumes:** `grammar_rows` (Task 2), `rules_of` parts (Task 3).
- **Produces:**
  - action `language_name_grammar {thing_id}` → `{thing_id, rows: [GrammarRow], has_grammar: bool}`;
  - edits save through the existing `set_field("rules", …)` path, with `rules.name_grammar` replaced;
  - store `nameGrammar[thingId]` and `loadNameGrammar(thingId)`.
- **Copy (spec):**
  - card title **Grammar for names**;
  - missing: "No grammar for names yet: names are built in your word order", with the button **Fill them in from the grammar** (`data-testid="name-grammar-fill"`; wired in Task 7);
  - the composed rule row shows its parts as chips: rule parts plain, fixed words dashed, meaning parts outlined, as in the mockup.

- [ ] **Step 1: Write the failing tests:**
  - **Server:**
    - `test_language_name_grammar_answers_rows`: Varovni seeded with grammar → rows with built examples.
    - `test_a_row_that_cannot_build_says_so` (Review Focus 3): an ending with `text=""` kind `ending`, or `when="sideways"`, gives that row an `error`, and the other rows keep their examples.
  - **e2e:**
    - `test_names_chapter_shows_the_grammar_rows`: opening Varovni's Names chapter shows the "the" row with "skelt → skeltek".
    - `test_editing_a_row_rebuilds_its_example`: change "describing" to after; the adjective row's example flips to "ulkha ilvo".
    - `test_a_language_without_grammar_offers_fill_them_in`: the missing note and the button are shown.
    - `test_a_composed_rule_shows_its_parts`: the owl-name row shows the chips "Men's names", "Ul", "a meaning · plural".
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Row edits use small per-row forms:
  - order rows: a select;
  - form rows: a list of changes, each with a condition select (always / after a vowel / after a consonant / before a vowel / ends with…) plus text, and kind;
  - endings: ending, meaning and changes.

  The parts editor lists the parts with kind, a rule select, a word, the slot, form checkboxes, and optional. No free-form editing of the whole file (spec, *my call*).
- [ ] **Step 4: Run them again,** and the checks. Screenshot the chapter at 1920×1080. Expected: PASS.
- [ ] **Step 5: Commit** (`feat(languages): the Names chapter shows and edits the grammar for names`).

### Task 6: The model layer: give a meaning, suggest

**Files:**
- Create: `src/talemate/languages/naming_meaning.py` and the two templates.
- Modify: `naming.py` (`translate_text` builds through the engine when the language has `name_grammar`), `naming_panel.py` (`from_meaning` → `give_meaning`), `src/talemate/server/worlds.py`.
- Test: `tests/languages/test_naming_meaning.py`, `tests/server/test_worlds_name_it.py`.

**Interfaces:**
- **Consumes:** Task 2 (`MeaningPhrase`, `build_phrase`, `lookup_word`), Task 3 (`roll_parts`, `PartRoll`), Task 4's decision on the client.
- **Produces:**
  - `split_meaning(client, language: Language, text: str, slots: list[NamePart], *, reply: str | None = None) -> tuple[list[MeaningPhrase], dict[str, list[str]]]`:
    - one phrase per meaning part (an empty `noun` for a part the meaning leaves out);
    - for each meaning the dictionary lacks, its coin options (the model's pick first, then up to 7 other rolls of the word rule);
    - one model call. `slots == []` means one phrase for the whole text.
    - The owner's words win over a slot's settings (spec, *my call*).
  - `suggest_phrases(client, language, rule: GeneratorDef, facts: list[str], *, reply=None) -> list[MeaningPhrase]`: one phrase per meaning part, from the entry's facts. For a rule with no meaning parts, it's `[]`, and the caller asks the model to pick from a batch with `naming.pick`.
  - `give_meaning(view, client, language_id, text, *, rule_id: str | None = None, reply=None) -> dict`:
    - with `rule_id`: `{shape, parts: [PartRoll]}`, its meaning parts' rolls built from the phrases (the coin options as the rolls of each new word);
    - without: `{candidates: [{name, built_from}]}`, built by the engine, joined and separate forms as in 4a.
  - **Server:**
    - `name_it_parts {language_id, rule_id, pinned: {index: text}, shape?}` → `{language_id, rule_id, shape, parts}`, no model;
    - `name_it_meaning {language_id, text, rule_id?}` (extended), with a model call;
    - `name_it_suggest {language_id, rule_id, thing_id}` → like `name_it_parts`, with suggested phrases built; a model call.
  - Fixed replies for e2e come from `TALEMATE_TEST_FIXED_LANGUAGE`, as `fixed_language` already provides.

- [ ] **Step 1: Write the failing tests** (fixed model replies):
  - `test_split_of_the_stars_builds_ul_zveski`: the reply `{"phrases":[{"noun":"star","of":true,"more_than_one":true}]}` with Varovni gives `"Ul Zveski"`.
  - `test_the_owners_words_win_over_the_slot`: the slot `noun more_than_one`, a typed "white lake", and a reply with describing `["white"]` give a built name with both words in Varovni order.
  - `test_a_missing_meaning_is_coined_with_options`: "frost", missing from the dictionary, gives a new part with `options` of length 8, saved nowhere.
  - `test_suggest_fills_meaning_parts_from_facts`: a reply phrase `{"noun":"star"}` → part 2's first roll `"Zveski"`; the prompt contains the entry's facts and the part's hint.
  - `test_name_in_is_grammatical`: `translate_text` on Drassonais with a split reply for "white lake" gives `"Aunfoimtte Blanchic"`.
  - `test_name_it_parts_answers_without_a_model` (server): no client; pinned `{0: "Dorvak"}` is kept.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Prompts follow probe 4b-1's final wording, and the client follows its decision.
- [ ] **Step 4: Run them again,** then `tests/languages tests/server`. Expected: PASS.
- [ ] **Step 5: Commit** (`feat(languages): names from a meaning or an entry's facts, built by the engine`).

### Task 7: Fill them in from the grammar; the skill and the brief

**Files:**
- Modify: `making.py` (`MakeRequest.kind` gains `"names"`), `brief.py` (`name_grammar` and composed rules in the file section; a `"names"` request section), `completeness.py` / `check.py` (Still to fill in), `.claude/skills/language-design/SKILL.md` and `reference/rule-syntax.md` (commit with `git add -f`), `LanguageChange.vue` and `NameGrammarCard.vue` (the button starts a `names` run in the Change it panel), and the review (show `name_grammar` rows before and after with examples).
- Test: `tests/languages/test_brief.py`, `tests/e2e/worlds/test_language_change.py`.

**Interfaces:**
- **Consumes:** `grammar_rows` (Task 2), the Task 1 models.
- **Produces:**
  - `MakeRequest(kind="names")`. Its brief says: "Write the grammar for names (`name_grammar`) from this language's grammar sections and tables. Change nothing else. Every rule must build the examples the tables give."
  - The review lists the new grammar rows with their examples.

- [ ] **Step 1: Write the failing tests:**
  - `test_a_names_brief_asks_for_name_grammar_only`: `write_brief(MakeRequest(kind="names"), current=lang)` contains `name_grammar`, the language's noun table, and "Change nothing else".
  - `test_the_full_brief_describes_name_grammar_and_composed_rules`: the Full brief's file section mentions `name_grammar` and `shapes`.
  - e2e `test_fill_them_in_starts_a_names_change` (fixed language reply carrying `name_grammar`): click `name-grammar-fill` on a language without grammar → the review shows the "the" row's example; accept → the Names chapter card shows rows.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Update the skill's example language with a `name_grammar` and one composed rule, and add rules text in the skill's style.
- [ ] **Step 4: Run them again.** Expected: PASS.
- [ ] **Step 5: Commit** (`feat(languages): Fill them in from the grammar, and the skill writes name grammar`).

### Task 8: The Name it builder (mockup B)

**Files:**
- Create: `talemate_frontend/src/components/worlds/NameBuilder.vue`.
- Modify: `NameItPanel.vue`, `stores/worlds.js`.
- Test: checks, `tests/e2e/worlds/test_name_it.py`.

**Interfaces:**
- **Consumes:** `name_it_parts`, `name_it_meaning` with `rule_id`, `name_it_suggest` (Task 6); `rules_of` parts (Task 3); `NameRolls.vue`.
- **Produces:**
  - store state `nameItParts: {shape, parts: PartRoll[]}`, `nameItPartChosen: {index: text}`, `nameItPartPinned: {index: text}`;
  - actions:
    - `nameItRollParts(languageId, ruleId)`: sends pinned;
    - `nameItChoosePart(index, text)`;
    - `nameItPinPart(index, text)`;
    - `nameItTypePart(index, text)`: typing pins;
    - `nameItSuggest(languageId, ruleId, thingId)`;
  - getter `nameItBuilt`: the chosen texts joined by spaces, optional parts left out when empty.

**The builder's layout** (mockup B):
- One column per part, each with its label, a pin, a text box to type a word, and its rolls as a `NameRolls` list, the chosen roll marked `current`.
- Fixed parts show their word only.
- Below the columns:
  - the built name;
  - **Use this name** (it goes through `pickNameIt`, so renaming everywhere and saving coined words on pick work as in 4a);
  - the working: each meaning part's `built_from` with its steps.
- **Reroll unpinned** and **✨ Suggest from its facts** sit beside the rule select. Suggest is only shown when the request has a `thingId`.
- **Give a meaning** fills the builder's meaning parts when a composed rule is picked. Without one, it shows 4a's candidates, now grammatical.
- **A plain rule** keeps 4a's ten-name batch.

- [ ] **Step 1: Write the failing tests:**
  - **checks:**
    - `the builder joins chosen parts and drops empty optional ones`;
    - `typing a part pins it`;
    - `reroll sends the pinned parts`.
  - **e2e:**
    - `test_the_builder_rolls_unpinned_parts` (Varovni owl-names): pin part 0, reroll, and part 0 is unchanged while part 2's rolls change;
    - `test_typing_a_part_pins_it`: type "Dorvak";
    - `test_use_this_name_renames_the_entry`;
    - `test_give_a_meaning_fills_the_meaning_part` (fixed reply "of the Stars" → "Dorvak Ul Zveski");
    - `test_suggest_fills_from_facts` (fixed reply);
    - `test_a_plain_rule_keeps_the_batch`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Screenshot the panel at 1920×1080.
- [ ] **Step 4: Run them again,** then the full e2e suite (`-n 4`) and the plain suite. Expected: PASS. If `tests/ai` names any changed selector, update it (`grep -rn` the test ids).
- [ ] **Step 5: Commit** (`feat(languages): Name it builds composed names part by part`).

### Task 9: Acceptance

**Files:**
- Create: `docs/superpowers/probes/2026-11-02-languages-4b1-acceptance.md`.

- [ ] **Step 1: Write the checklist:** each spec goal, what the owner looks at, and the proving tests.
- [ ] **Step 2: Update the owner's fresh test app**, which holds Test3 (http://127.0.0.1:52357/, root `.worktrees/languages-4a/.superpowers/sdd/2026-11-01-…-revised-name-it/app`):
  - Copy the changed `src/` and `talemate_frontend/src/` files into it.
  - Back up `worlds/` and `config.yaml`, and restart **only the backend process** on its port. Ask the owner first.
- [ ] **Step 3: Real runs, with the owner's go-ahead:**
  - **Fill them in** on Varovni and Tsevrani (agent route), and check the built examples against their tables.
  - **Give a meaning** "of the Stars" on an owl-name rule.
  - **Suggest** on a Test3 character.
  - **Reroll with a pin.**

  Record the results.
- [ ] **Step 4: Get the owner's verdict,** record it, and commit (`docs(languages): 4b-1 acceptance`).
