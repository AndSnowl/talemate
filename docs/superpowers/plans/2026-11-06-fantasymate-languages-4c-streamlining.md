# Languages 4c: streamlining people's names — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
- Main rules come first and pieces are folded.
- Main rules carry Claude's descriptions, and the model picks a person's rule from them when Name it opens.
- Every draft goes through one cleaning pipeline that only marks.
- Name it renames a whole name, keeping narrator words (titles, kind words, regnal numbers).

**Architecture:**
- **Language file:** gains `main` and `description` on a rule, plus an `is_main` helper; the rule lists and the Names chapter sort by it.
- **Picking:** a new model call, `pick_person_rule`, behind a `name_it_pick` server action. Name it calls it when it opens on a person with no stored rule, and the pick is stored with the draft or the person.
- **Cleaning:** the three cleaning entry points become thin callers of one `clean_draft`.
- **Whole names:**
  - person marks cover the whole proper part;
  - `name_parts` gains `regnal`;
  - Name it composes the result with a pure `personRename`, which keeps narrator words and drops an English title the rule's own word stands for.

**Tech Stack:** Python 3.11 and pydantic; Vue 3, Vuetify and Pinia; pytest, Playwright e2e, `talemate_frontend/checks/worlds.check.mjs`.

**Spec:** `docs/superpowers/specs/2026-11-06-fantasymate-languages-4c-streamlining-design.md`. It builds on 4b-2: spec `2026-11-04-fantasymate-languages-4b2-people-names-design.md`, code `src/talemate/languages/{person_names,composed,naming_panel}.py`, `src/talemate/worldplay/{cleaning,people}.py`.

## Global Constraints

- **Branch and worktree:** branch `feature/languages-4c` from `main`, worktree `.worktrees/languages-4c`.
  - A new worktree needs `uv sync --frozen --extra dev`, `pnpm install --frozen-lockfile` in `talemate_frontend`, and `scripts/dev/browser.py ensure_driver_node()`.
- **Environment:** `guix shell -m manifest.scm -- uv run --no-sync pytest … -q -p no:cacheprovider`.
  - e2e: `-m e2e -n 4`, about 8.5 min.
  - checks: `guix shell -m ../manifest.scm -- node checks/worlds.check.mjs`, with new checks placed before the `if (failures.length)` block.
  - build: `npx --yes corepack@0.34.0 pnpm build`.
- **No new dependencies. No migration code:** languages without `main` or descriptions use the defaults.
- **Drafts only mark; nothing is renamed automatically** (owner, 2026-11-06).
- **The rule is picked when Name it opens** on a person, never ahead of time. Once made, it's kept, and the model isn't asked twice.
- **No model call** on Reroll, pin, pick or the builder. `name_it_pick` is the only new model call.
- **Regnal numbers are narrator words:** always Roman numerals, never built in the language, never counted (that's the future governance generator's job).
- **Epithets stay.** "Zochar the White" keeps "the White". An "of ⟨place⟩" stays unless the picked rule builds "of ⟨house⟩".
- **Titles:** only the English title the rule's own word stands for is dropped ("Tsar" for "Gosmar"); "Lady" and "Captain" stay.
- **AI runs:** ask the owner before the probe (Task 3) and before acceptance runs (Task 7).
  - The owner's test app is `.worktrees/languages-4b2/.superpowers/test-app`. Back up `worlds/` and `config.yaml` and ask before restarting it. Never use `talemate_app.py start` on it, because that wipes its root.
- **UI rules:** controls by content; the same look means the same component; screenshots at 1920×1080.

## Review Focus

1. **A language with no main rule, or only pieces, for people.** Name it still offers a rule (falls back to `pick_rule`), and the dropdown never comes up empty. Task 1: `test_rules_of_never_leaves_people_without_a_main_rule`.
2. **The model answers with an unknown rule id, a piece, or nothing.** The pick falls back to today's matching, and Name it doesn't hang on "picking…". Task 4: `test_a_bad_pick_falls_back_to_matching`.
3. **Name it closed or switched to another person before the pick returns.** A late pick is ignored and never lands on the wrong person. Task 4: check `a late pick for another request is dropped`.
4. **A name with two titles, a number and an epithet** ("Grand Prince Tsar Aleksi III the Bold"). Only the matching English title goes; the number and the epithet stay in place. Task 6: check `personRename keeps every narrator word but the one the rule says`.
5. **Owner-typed regnal text that isn't a numeral** ("the Third"). It's refused with a clear message in Name it rather than stored. Task 6: `test_regnal_must_be_a_roman_numeral` and the matching check.

---

## File structure

- **Modify:**
  - `src/talemate/languages/models.py` (`GeneratorDef.main`, `description`);
  - `person_names.py` (`is_main`);
  - `naming_panel.py` (`RuleInfo.main`, `description`, ordering);
  - `check.py`, `brief.py`, the skill files, `language.schema.json`.
- **Create:**
  - `src/talemate/languages/rule_pick.py`: `pick_person_rule`, its reply parsing, and `RulePick`;
  - `src/talemate/prompts/templates/world/name-pick.jinja2`.
- **Modify:**
  - `src/talemate/worldplay/cleaning.py` (`clean_draft`);
  - `people.py` (`store_pick`, `regnal`);
  - `world/kinds.py` (`regnal` in `name_parts`);
  - `languages/cleaning/mark.py` and `find.py` (`proper_part`, person marks);
  - `server/worlds.py` (`name_it_pick`; `name_it_parts` returns `title_words` and `builds_of`).
- **Frontend:**
  - `NameItPanel.vue` (dropdown order and divider, opening on the pick, the regnal field);
  - `LanguageSections.vue` (main first, pieces folded, description and main/piece on a row);
  - `nameParts.js` (`personRename`);
  - `stores/worlds.js`.

---

### Task 1: Main rules, pieces and descriptions in the language

**Files:** modify `models.py`, `person_names.py`, `naming_panel.py`, `check.py`, `brief.py`, `language.schema.json`, `.claude/skills/language-design/SKILL.md` (`git add -f`; `.claude` is ignored but these files are tracked) and `reference/rule-syntax.md`. Tests: `tests/languages/test_main_rules.py`, `tests/languages/test_brief.py`.

**Interfaces — Produces:**
- **`GeneratorDef`** gains `main: bool | None = None` (None means the default) and `description: str = ""`.
- **`is_main(language, generator) -> bool`** in `person_names.py`:
  - `generator.main` when it's set;
  - otherwise False when the rule is a building block (`_building_blocks`) or its `use` is `"words"` or `"pet names"`;
  - otherwise True.
- **`RuleInfo`** gains `main: bool` and `description: str`. `rules_of` returns the main rules first, in the file's order, then the pieces in the file's order.
- **Brief and skill:** they ask for `main` (only where the default is wrong) and a one-line `description` on every main people rule, the kind of person it's for, in plain English.

- [ ] **Step 1: Write the failing tests.**

```python
def test_a_building_block_is_a_piece_and_can_be_overridden():
    lang = ZHELVAN_LIKE  # given (used by men's names), men's names, words, pet names, places
    assert [is_main(lang, g) for g in lang.generators] == [False, True, False, False, True]
    lang.generators[0].main = True
    assert is_main(lang, lang.generators[0]) is True

def test_rules_of_puts_main_rules_first_with_descriptions():
    infos = rules_of(ZHELVAN_LIKE)
    assert [i.main for i in infos] == [True, True, False, False, False]
    assert infos[0].description == "ordinary men of the towns"

def test_rules_of_never_leaves_people_without_a_main_rule():
    only_pieces = ZHELVAN_LIKE.model_copy(deep=True)
    for g in only_pieces.generators: g.main = False
    infos = rules_of(only_pieces)
    assert infos and any(i.use in ("character", "people") for i in infos)

def test_names_brief_asks_for_main_and_descriptions():
    brief = write_brief(None, MakeRequest(kind="names", target_id="x", text=""), current=SAMPLE_FILE)
    assert "`main`" in brief and "`description`" in brief
```

- [ ] **Step 2: Run them to make sure they fail.**
- [ ] **Step 3: Implement** as in Interfaces. Regenerate the schema (command in `schema.py`). The check warns on a description over 120 characters.
- [ ] **Step 4: Run `tests/languages` to make sure they pass.**
- [ ] **Step 5: Commit** `feat(languages): main rules, pieces and descriptions`.

---

### Task 2: Main rules first in the Names chapter and Name it

**Files:** modify `LanguageSections.vue`, `NameItPanel.vue`, `nameParts.js`. Tests: checks, plus e2e in `tests/e2e/worlds/test_names_chapter.py` and `test_name_it.py`.

**Interfaces — Consumes:** Task 1's `RuleInfo.main` and `description`, and the rule's `main` and `description` in the language entry.

**Interfaces — Produces:**
- **`nameParts.js`:** `ruleMenuItems(rules)` returns the main rules as `{title, value}` items, then a `{type: 'subheader', title: 'Pieces'}` item, then the pieces. It leaves out the subheader when there are no pieces.
- **Names chapter:**
  - main rules first;
  - the pieces in a section folded by default, "Pieces (n)" (`language-pieces`);
  - each rule row shows its description under its name, editable in place (`rule-description`), and a main/piece switch (`rule-main`), saved through the rules field like other row edits.
- **Name it:** the rule dropdown uses `ruleMenuItems`.

- [ ] **Step 1: Write the failing check and e2e tests:**
  - check `ruleMenuItems puts main rules first, then a Pieces header`;
  - e2e `test_pieces_are_folded_below_the_main_rules`;
  - e2e `test_a_rule_description_is_edited_in_place`;
  - e2e `test_name_it_lists_main_rules_before_pieces`.
- [ ] **Step 2: Run them to make sure they fail.**
- [ ] **Step 3: Implement.** Take a screenshot at 1920×1080.
- [ ] **Step 4: Run the checks, the build and those e2e files to make sure they pass.**
- [ ] **Step 5: Commit** `feat(languages): main rules first, pieces folded`.

---

### Task 3: Probe the pick (AI; ask the owner first)

**Files:**
- Create `scripts/dev/probe_4c.py`, `docs/superpowers/probes/raw/2026-11-06-languages-4c-labels.json` (committed before any call) and `docs/superpowers/probes/2026-11-06-languages-4c.md`.

**What it runs.** Use a read-only copy of the owner's test-app world (Zhelvan, Drassonais). First fill in Zhelvan's descriptions with Fill them in on Claude Code, using Task 1's brief. Then on Skyfall, 15 person prompts, including "the tsar's youngest son", "a fisherman's daughter", "the duke's heir", "an owl-folk hunter" and "the old smith":
- **A, in the draft call:** the `create-thing` prompt's `person` block also asks for `"rule": "<one of the listed ids>"`. This variant is in a scratch copy only.
- **B, when Name it opens:** `pick_person_rule` (Task 4's prompt, drafted here first) on the finished draft.

**Score:** pick against the labels; other names in the draft (`aka` count, epithets); time for A's call and B's call.

**Go/no-go:**
- If B picks right on at least 12 of 15 and beats today's `pick_rule` on the same prompts, build Task 4 as written.
- If A is clearly better than B (3 or more more right), ledger it and ask the owner.
- If neither beats `pick_rule`, stop and ask the owner (spec).

- [ ] Write the labels and commit them; write the probe; run both variants; write up the results; ledger the ruling; commit `docs(languages): 4c probe`.

---

### Task 4: Name it opens on the model's pick

**Files:**
- Create `rule_pick.py` and `templates/world/name-pick.jinja2`.
- Modify `worldplay/people.py`, `server/worlds.py`, `NameItPanel.vue`, `stores/worlds.js`.
- Tests: `tests/languages/test_rule_pick.py`, `tests/server/test_worlds_person_names.py`, checks, e2e `tests/e2e/worlds/test_person_name.py`.

**Interfaces — Consumes:** Task 1's `is_main`, `GeneratorDef.description`, `pick_rule`, `choose`.

**Interfaces — Produces:**
- **`RulePick(BaseModel)`:** `rule_id: str`, `built_as: dict[str, str]`, `why: str` (the picked rule's description), `fallback: bool`.
- **`async pick_person_rule(client, language, text: str, *, reply: str | None = None) -> RulePick`:**
  - The model sees the main people rules (id, name, description, `for_person` as a hint) and `text`. It answers `{"rule": id, "sex": …, "rank": …}`.
  - An unknown id, a piece or no answer gives `pick_rule(language, choose(language, read))` with `fallback=True`.
- **`store_pick(rev, world, thing_id, language_id, pick) -> None`** in `people.py`: writes `rule` and `built_as` into the person's `name_parts`, creating `{language, rule, shape: 0, built_as, parts: []}` when there's none. A stored rule is never overwritten by a pick.
- **Server `name_it_pick {language_id, thing_id | draft: {prompt, facts}}`:**
  - runs in the background and replies `name_it_pick {language_id, thing_id?, draft_key?, rule_id, built_as, why, fallback}`;
  - on a page, stores the pick with `store_pick`; for a draft it doesn't store it, and the client edits the draft (`fields.name_parts.rule`, `built_as`).
- **Store and panel:**
  - Opening Name it on a person with no stored rule (`request.ruleId === ''`) sends `name_it_pick` and shows "picking…" next to the rule dropdown, while the builder shows today's matched rule.
  - When the pick arrives, if it's for the open request, the panel switches to it and shows `why` under the dropdown ("picked: ordinary men of the towns").
  - A pick for another request, or after the panel closed, is dropped.
  - Use this name stores the rule in use (4b-2's `name_it_rename` with parts, unchanged).

- [ ] **Step 1: Write the failing tests:**

```python
async def test_the_model_picks_a_main_rule_with_built_as():
    pick = await pick_person_rule(None, ZHELVAN_LIKE, "the tsar's youngest son", reply='{"rule": "sovereign", "sex": "man", "rank": "royal"}')
    assert (pick.rule_id, pick.built_as["sex"], pick.fallback) == ("sovereign", "man", False)
    assert pick.why == "the tsar and his heirs"

async def test_a_bad_pick_falls_back_to_matching():
    for reply in ('{"rule": "nobody"}', '{"rule": "given"}', 'no json'):
        pick = await pick_person_rule(None, ZHELVAN_LIKE, "a smith", reply=reply)
        assert pick.fallback is True and pick.rule_id == pick_rule(ZHELVAN_LIKE, pick.built_as).id

async def test_a_page_pick_is_stored_once(plugin):  # server; fixed reply via _language_reply
    ... # first name_it_pick stores rule "sovereign"; a second with another reply leaves it
```

  Also:
  - checks: `opening Name it on an unpicked person asks for a pick`; `a late pick for another request is dropped`; `a pick on a draft edits the draft's name_parts`;
  - e2e `test_name_it_opens_on_the_models_pick` (fixed language reply).
- [ ] **Step 2: Run them to make sure they fail.**
- [ ] **Step 3: Implement.** Apply Task 3's ruling.
- [ ] **Step 4: Run the tests, checks, build and e2e file to make sure they pass.**
- [ ] **Step 5: Commit** `feat(languages): Name it opens on the model's pick`.

---

### Task 5: One draft pipeline

**Files:** modify `worldplay/cleaning.py` and its callers in `server/worlds.py` if their signatures change. Tests: `tests/worldplay/test_clean_draft.py`; existing `test_create_cleaning.py`, `test_facts_cleaning.py` and `test_groups_cleaning.py` stay green.

**Interfaces — Produces:**
- **`async clean_draft(world, client, *, texts: list[str], listed: list[tuple[str, str]], prompt: str, rows: list, keep: set[str] = frozenset(), person: CreatePreview | None = None) -> tuple[list[Mark], CreatePreview | None]`:**
  - It marks the names (`mark_texts`).
  - With `person` (a drafted person), it runs `name_person` on it.
  - It never changes text.
  - It returns `([], person)` unchanged when the world has no languages, or when there's no client and no fixed replies.
- **The callers are thin.** `clean_preview`, `clean_fact_draft` and `clean_group_draft` each work out their own `texts`, `listed`, `prompt` and `rows` (how languages are found stays per kind, as the spec says), call `clean_draft`, and put the marks back. No marking or person logic is left in them.
- **Behaviour change (spec, "all or none"):** `clean_preview` with no client and no fixed replies now returns the preview as it is, as the other two already do.

- [ ] **Step 1: Write the failing tests:**
  - `test_every_draft_kind_marks_through_clean_draft`: monkeypatch `cleaning.clean_draft` with a spy, run the three entry points, and assert three calls;
  - `test_a_new_entry_with_no_model_is_left_alone`.
- [ ] **Step 2: Run them to make sure they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run `tests/worldplay tests/server -k "clean or draft or group or facts"` and then the full plain suite to make sure they pass.**
- [ ] **Step 5: Commit** `refactor(worlds): one cleaning pipeline for every draft`.

---

### Task 6: Whole names and narrator words

**Files:** modify `languages/cleaning/find.py`, `mark.py`, `world/kinds.py`, `worldplay/people.py`, `languages/person_names.py` (`stored_written`), `server/worlds.py`, `nameParts.js`, `NameItPanel.vue`, `PersonName.vue`. Tests: `tests/languages/test_clean_find.py`, `tests/worldplay/test_person_name_store.py`, `tests/server/test_worlds_person_names.py`, checks, e2e.

**Interfaces — Produces:**
- **`proper_part(full: str) -> str`** in `find.py`: a person's words up to the first `NAME_STOPS` word, leaving out title words and Roman numerals. "Tsar Aleksi Romanov III" gives "Aleksi Romanov"; "Zochar the White" gives "Zochar".
- **Person marks:**
  - `name` and `part` are `proper_part(spot.full)` (today they're the one judged word);
  - several flagged words of one name make one mark.
- **`name_parts` gains `regnal: str` (optional).** The validator accepts `^[IVXLCDM]+$` or an empty string. `stored_written` and the page's written name append it after the parts.
- **`name_it_parts`** replies with:
  - `title_words`: the English words the rule's own title part stands for (a word part labelled "title", or a word in `kept_titles`, mapped through its `english` and the kept title's `meaning`);
  - `builds_of`: true when the shape has a word part written "of" in English followed by a connection part.
- **`nameParts.js`: `personRename(fullName, properPart, built, {titleWords, buildsOf, regnal}) -> string`:**
  - The proper part is replaced by the built name.
  - Title words in `titleWords` are dropped (case-insensitive).
  - With `buildsOf`, an "of ⟨…⟩" right after the proper part is dropped (the built name has its own).
  - Other narrator words and epithets stay where they were.
  - The regnal number goes at the end: `regnal` when given, else any numeral already in the name.
- **Name it:**
  - On a person, it uses `personRename` instead of `composeName`.
  - It shows a small "number" field after the built name (`name-it-regnal`), prefilled from the name's numeral, refusing anything but Roman numerals.
  - Use this name sends `regnal` with the parts.
- **The Name section** (`PersonName.vue`) shows the number after the parts as a narrator field (`person-regnal`), editable on drafts and pages alike. On a page it saves with a `person_regnal {thing_id, regnal}` action that renames everywhere; on a draft it edits the draft (`draftNameEdit`, `{regnal}`).

- [ ] **Step 1: Write the failing tests:**

```python
def test_proper_part_leaves_narrator_words_and_epithets():
    assert proper_part("Tsar Aleksi Romanov III") == "Aleksi Romanov"
    assert proper_part("Zochar the White") == "Zochar"

def test_regnal_must_be_a_roman_numeral():
    validate_field(CHARACTER, "name_parts", {**GOOD_PARTS, "regnal": "III"})
    with pytest.raises(ValueError):
        validate_field(CHARACTER, "name_parts", {**GOOD_PARTS, "regnal": "the Third"})
```

  Checks:

```js
check('personRename keeps every narrator word but the one the rule says', () => {
    const out = personRename('Grand Prince Tsar Aleksi III the Bold', 'Aleksi', 'Gosmar Zochar Vekhal', { titleWords: ['tsar'], buildsOf: false, regnal: '' });
    assert.equal(out, 'Grand Prince Gosmar Zochar Vekhal III the Bold');
});
check('personRename replaces an of-place the rule builds', () => {
    assert.equal(personRename('Maëlis of Sauvaire', 'Maëlis', 'Ysolde of Drassone', { titleWords: [], buildsOf: true, regnal: '' }), 'Ysolde of Drassone');
});
```

  Also:
  - `test_a_persons_mark_covers_the_whole_proper_part`, in the mark tests;
  - server `test_name_it_parts_says_the_rules_title_words`;
  - e2e `test_name_it_on_tsar_aleksi_iii_gives_the_whole_name`.
- [ ] **Step 2: Run them to make sure they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests, checks, build and e2e to make sure they pass.**
- [ ] **Step 5: Commit** `feat(languages): whole names in Name it, narrator words kept`.

---

### Task 7: Acceptance (AI; ask the owner first)

- [ ] Run the full plain suite, the checks and the full e2e suite.
- [ ] **Real runs on a throwaway copy of the owner's test-app world** (Skyfall, and Claude Code for Fill them in): Fill them in on Zhelvan for descriptions; then a "+ Add facts" naming a new tsar's son, a new-entry draft, and Name it on each (pick, whole name, number). Record the picks, timings and screenshots.
- [ ] Write `docs/superpowers/probes/2026-11-06-languages-4c-acceptance.md` and hand it to the owner for their verdict. Ask before updating their test app.
