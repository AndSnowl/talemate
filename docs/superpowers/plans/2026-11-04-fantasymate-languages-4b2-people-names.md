# Languages 4b-2: people's names — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A person's name is built from their language's rules. Parts are inherited from real connections, forms follow sex and rank, and the rest is made up. The name is stored in labelled, editable parts, together with collected titles, pet names, and what others call the person. Forms of address live in the language.

**Architecture:**
- **Engine.** A new pure-Python module, `talemate.languages.person_names`, reads a person's connections and picks the rule for their sex and rank. It builds the name through 4b-1's `roll_parts`, extended with a person context. It also writes the name with each fixed word's English switch.
- **Storage.**
  - A character keeps a `name_parts` field.
  - Titles and pet names are other names (`aka`), extended with `kind`, `by`, `meaning`, `rule` and `shown`.
  - The language gains `people_names`, holding choices, kept titles and address rows.
- **Model use.** The draft's existing call also returns a small `person` block (sex, rank, a meaning, a title). No new call per draft.
- **Frontend.** A person page gets a Name section and "calls her" lines on relationship facts (mockup B). Name it on a person pins inherited parts. The Names chapter gains People-name cards.

**Tech Stack:**
- Python 3.11 and pydantic (backend); Vue 3, Vuetify and Pinia (frontend);
- tests: pytest, Playwright e2e, and `talemate_frontend/checks/worlds.check.mjs`.

**Spec:** `docs/superpowers/specs/2026-11-04-fantasymate-languages-4b2-people-names-design.md`. Mockup: `docs/superpowers/mockups/2026-11-04-languages-4b2-person-name.html` (frame **B**). It builds on 4b-1: spec `2026-11-02-fantasymate-languages-4b1-grammar-engine-design.md`, code in `src/talemate/languages/{models,name_grammar,composed,naming_meaning}.py`.

## Global Constraints

- **Branch and worktree:** branch `feature/languages-4b2` from `main`, in worktree `.worktrees/languages-4b2`.
  - A new worktree needs `uv sync --frozen --extra dev`, `pnpm install --frozen-lockfile` (in `talemate_frontend`), and `scripts/dev/browser.py ensure_driver_node()`.
- **Environment:** run everything with guix: `guix shell -m manifest.scm -- uv run --no-sync pytest … -q -p no:cacheprovider`.
  - e2e: `-m e2e -n 4`, about 8.5 min, at most 4 workers.
  - frontend checks: `guix shell -m ../manifest.scm -- node checks/worlds.check.mjs`. New checks go **before** the `if (failures.length)` summary block.
  - build: `npx --yes corepack@0.34.0 pnpm build`.
- **No new dependencies.**
- **No migration code** (owner): existing people with one name string get no parts. Old language files without `people_names` or person parts load, and behave as in 4b-1.
- **No model call** on Reroll, pin, pick, editing a part, reading inherited parts, or building from a known structure. The model's only new work rides on the draft's existing call (spec, "On the draft").
- **The model never does the grammar.** It returns sex, rank, a meaning and a title in words; the engine builds every form.
- **Written in English unless kept** (owner): fixed words carry a switch that writes them in English. Titles are English unless the language keeps a word for them.
- **Only what differs shows** (owner): a relationship row shows a "calls her" line only for a name that differs from the language's address default.
- **AI runs:** the owner gave express permission (2026-11-04) to run every AI-dependent part of this plan (koboldcpp and Claude Code): the probe in Task 4 and the acceptance runs in Task 9. Still record each run's raw output.
- **The owner's test app** is at `.worktrees/languages-4a/.superpowers/sdd/2026-11-01-fantasymate-languages-4a-revised-name-it/app`, port 52357, backend 37249.
  - Never restart it with `talemate_app.py stop/start`, which wipes its root.
  - Before an update, back up `worlds/` and `config.yaml`, and **ask before restarting**: the AI permission doesn't cover restarting the app.
  - Kill only exact PIDs, never with a pattern kill.
  - The app allows one frontend connection at a time.
- **UI:**
  - controls sit by their content;
  - the same look means the same component: 4a's pin chips (`NameRolls.vue`) and 4b-1's builder grid (`NameBuilder.vue`);
  - fixed grids that don't resize with their contents;
  - screenshots at 1920×1080.

## Review Focus

1. **A parent connection that points at a stub, a deleted entry, or the person itself** (a typo in role words). The inherited part falls back to its rule's roll and never raises. A part never reads its own entry. Task 2: `test_a_bad_parent_falls_back_to_a_roll`.
2. **A hand rename after a built name, followed by Name it on the same person.** The parts are cleared by the rename, so Name it starts fresh with only live connections pinned. Nothing stale ever reappears. Task 3: `test_a_hand_rename_clears_parts_and_name_it_starts_fresh`.
3. **A name the owner wrote in the prompt** ("Ysolde, daughter of Eilhaud"). The draft keeps it word for word and never rebuilds it. Its parts are filled only where its words line up with the rule. Task 5: `test_a_name_from_the_prompt_is_never_rebuilt`.
4. **A model reply with no `person` block, or with sex and rank values the language doesn't list.** The draft still gets a built name, using the language's default choices, and "built as" shows those defaults. Task 5: `test_a_missing_or_unknown_person_block_uses_defaults`.
5. **A pet name or title whose `by` names an entry that's later deleted or merged.** The page drops the line rather than showing a dead link, and the stored aka is still valid. Task 6: e2e `test_calls_her_skips_a_deleted_caller`; Task 3: `test_akas_with_by_survive_validation`.

---

## File structure

- **Create:**
  - `src/talemate/languages/person_names.py`: the person context (connections, choices), rule picking, name building with inherited parts, the written form, pet names, address lookup and kept-title lookup.
  - `talemate_frontend/src/components/worlds/PersonName.vue`: the Name section (parts grid, built as, titles, pet name), mockup B.
  - `talemate_frontend/src/components/worlds/CallsLine.vue`: the folded "calls her" line on a relationship fact.
  - `talemate_frontend/src/components/worlds/PeopleNamesCard.vue`: the Names chapter's People-name card (choices, kept titles, address).
  - `talemate_frontend/src/components/worlds/personName.js`: pure helpers (`writtenName`, `callsFor`, `partSourceLine`).
- **Modify:**
  - `src/talemate/languages/models.py`: the new language models.
  - `composed.py`: person context in `roll_parts`.
  - `naming.py`: `generator_for` with a person.
  - `check.py`, `changes.py`, `completeness.py`, `brief.py`, `language.schema.json`.
  - `src/talemate/world/kinds.py`: `name_parts`, AKA keys.
  - `src/talemate/worldplay/repoint.py`: a rename clears parts that no longer match.
  - `src/talemate/worldplay/create.py`, `cleaning.py`, and `prompts/templates/world/create-thing.jinja2`: the person block, and building on the draft.
  - `src/talemate/server/worlds.py`: the actions.
  - `ThingPage.vue`, `NameItPanel.vue`, `NameBuilder.vue`, `FactRow.vue`, `LanguageBook.vue`, `LanguageSections.vue`, `stores/worlds.js`.
  - `.claude/skills/language-design/SKILL.md` and `reference/rule-syntax.md`.

---

### Task 1: The language file learns people's names

**Files:**
- Modify: `src/talemate/languages/models.py`, `check.py`, `changes.py`, `completeness.py`, `src/talemate/languages/language.schema.json`.
- Test: `tests/languages/test_people_names_model.py`.

**Interfaces — Produces:**
- **`NamePart` gains:**
  - `kind: Literal["rule", "word", "meaning", "connection", "own"]`;
  - `roles: list[str] = []`: for `connection`, role words in order of preference ("mother", "father");
  - `take: str = ""`: for `connection` and `own`, the label of the source person's part to take; `""` means the whole name;
  - `person_forms: list[PersonForm] = []`: changes applied to the part's text by who the person is;
  - `english: str = ""`: for `word`, how it's written in English ("of"); `""` means it's written as the word.
- **Fallback for a `connection` part:** the existing `rule` field names the rule it rolls from when the connection is missing. Empty means the part is dropped if optional, and otherwise rolls from `generator_for(language, "character")`.
- **`own`** takes this person's own part by label (used by pet-name rules: given + "-ette").
- **`PersonForm(BaseModel)`:** `when: dict[str, str]` (for example `{"sex": "woman"}`); `changes: list[FormChange]`. The first whose `when` all match wins.
- **`GeneratorDef` gains `for_person: dict[str, str] = {}`**, for example `{"sex": "woman", "rank": "noble"}`. Empty means for anyone.
- **`PeopleNames(BaseModel)`:**
  - `choices: dict[str, list[str]] = {}`: the first value of each list is the default. Example: `{"sex": ["man", "woman"], "rank": ["common", "noble"]}`.
  - `kept_titles: list[KeptTitle] = []`.
  - `address: list[AddressRow] = []`.
- **`KeptTitle(BaseModel)`:** `word: str`, `meaning: str` (English, "emperor").
- **`AddressRow(BaseModel)`:**
  - `kind: str` ("family");
  - `roles: list[str] = []`: role words that map onto it;
  - `uses: list[str]`: part labels, `"title"`, or `"pet name"`;
  - `default: bool = False`: the row for anyone unmatched, "strangers".
- **`Language` gains** `people_names: PeopleNames | None = None`.
- **`check.py`:**
  - `connection` parts need `roles`;
  - `own` parts need `take`;
  - `for_person` and `person_forms` keys and values must be in `choices`, unless `choices` is empty;
  - `uses` must name a part label the language's people rules have, or `"title"`, or `"pet name"`;
  - each problem is a warning line, matching 4b-1's `check.py` style.
- **`changes.py`:** a change that carries `people_names` merges it as `name_grammar` does.
- **`completeness.py`:** "people's names" counts as filled when the language has `people_names` with `choices`, and at least one rule with a `connection` part or `for_person`.

- [ ] **Step 1: Write the failing tests**

```python
def test_old_language_loads_without_people_names(varovni_file):
    lang = Language.model_validate(varovni_file)
    assert lang.people_names is None

def test_people_names_round_trip():
    lang = _lang(people_names={"choices": {"sex": ["man", "woman"], "rank": ["common", "noble"]},
                               "kept_titles": [{"word": "Tsar", "meaning": "emperor"}],
                               "address": [{"kind": "family", "roles": ["mother", "brother"], "uses": ["pet name"]},
                                           {"kind": "strangers", "uses": ["title", "house"], "default": True}]})
    again = Language.model_validate(lang.model_dump())
    assert again.people_names.address[1].default is True

def test_connection_part_and_person_forms_validate():
    part = NamePart(kind="connection", roles=["mother", "father"], take="family", rule="family",
                    person_forms=[{"when": {"sex": "woman"}, "changes": [{"kind": "ending", "text": "a"}]}])
    assert part.person_forms[0].when == {"sex": "woman"}

def test_check_warns_on_a_connection_without_roles_and_an_unknown_choice():
    lines = check_language(_lang_with_rule(parts=[{"kind": "connection"}], for_person={"caste": "x"}))
    assert any("roles" in l for l in lines) and any("caste" in l for l in lines)

def test_completeness_counts_people_names():
    assert "people's names" in missing(_lang())
    assert "people's names" not in missing(_lang_with_people())
```

- [ ] **Step 2: Run them to make sure they fail.**
Run: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/languages/test_people_names_model.py -q -p no:cacheprovider`
Expected: FAIL (`people_names` unknown, `NamePart` kind rejected).

- [ ] **Step 3: Implement the models, check, merge, completeness and schema** as in Interfaces. Add `people_names` to the `RULES_KEYS` whitelist wherever `name_grammar` is listed (`entry.py` and `stores/worlds.js`; 4b-1 missed this once).

- [ ] **Step 4: Run the tests, plus `tests/languages`, to make sure they pass.**
Expected: PASS, with no other language test broken.

- [ ] **Step 5: Commit** `feat(languages): people's names in the language file`.

---

### Task 2: The person-name engine

**Files:**
- Create: `src/talemate/languages/person_names.py`.
- Modify: `composed.py` (person context in `roll_parts` and `_roll_part`), `naming.py` (`generator_for(language, kind, person=None)`).
- Test: `tests/languages/test_person_names.py`.

**Interfaces — Consumes:** Task 1's models; `roll_parts`, `PartRoll`, `Built`, `apply_form`, `MISSING_RULE`.

**Interfaces — Produces:**
- **`Connection(BaseModel)`:** `role: str` (the words, as written); `thing_id: str`; `name: str`; `parts: dict[str, str] = {}` (the connected person's labelled parts, if any); `built_as: dict[str, str] = {}`.
- **`PersonContext(BaseModel)`:**
  - `thing_id: str | None`;
  - `built_as: dict[str, str]`;
  - `connections: list[Connection]`;
  - `own: dict[str, str] = {}`: the person's own parts, for `own` parts.
- **`connections_of(view, thing_id: str | None, filings: list[tuple[str, str | None]], facts: list[tuple[str, list[str]]]) -> list[Connection]`:**
  - Inputs are the entry's `(target_id, role)` filings and its relationship facts as `(text, refs)`.
  - A fact counts once for each ref, with the fact text as its role.
  - It skips the person themself, and refs that aren't live entries.
  - A connected entry's `parts` come from its `name_parts` field.
- **`choose(language, read: dict[str, str]) -> dict[str, str]`:** each choice the language lists. A read value counts if it's in the list (case-insensitive); otherwise the list's first value is used. A language with no `choices` returns `read` as given.
- **`pick_rule(language, built_as) -> GeneratorDef`:**
  - Among the people rules (bucket "people"), take the one whose `for_person` matches the most keys, with no key contradicted.
  - Ties go to plain before composed (as `generator_for` does).
  - If none matches, use `generator_for(language, "character")`.
- **`role_matches(role_words: list[str], connection: Connection) -> bool`:** a whole-word, case-insensitive match of any role word in `connection.role`. "mother" matches "Daughter of Aurande, her mother", and "mother" matches the role "mother".
- **`parent_for(part: NamePart, ctx: PersonContext) -> Connection | None`**, by the spec's order:
  1. role words, tried in the order the part lists them;
  2. then, for a role word naming a sex ("mother" → `{"sex": "woman"}`, "father" → `{"sex": "man"}`; the list lives in this module as `ROLE_SEX`), a parent-like connection ("son of", "daughter of", "child of", "parent") whose `built_as` sex matches;
  3. then the first parent-like connection.
- **`roll_parts(..., person: PersonContext | None = None)`:**
  - A `connection` part with a parent gives one roll: the parent's `take` part, or its whole name, or its last word when `take` is set but the parent has no parts. The roll is marked `source="inherited"` with `from_id` and `from_role`, and pinned by default.
  - With no parent, it rolls from the part's fallback.
  - An `own` part takes `person.own[take]`.
  - `person_forms` apply to every part's text (rolled, inherited, own), via `apply_form`'s change machinery.
- **`PartRoll` gains** `source: Literal["rolled", "typed", "meaning", "inherited", "word"] = "rolled"`, `from_id: str = ""`, `from_role: str = ""`.
- **`MissingParent(BaseModel)`:** `role: str`; `label: str`; `text: str` (the rolled part); `name: str` (the stub's full name, built by `pick_rule(language, {"sex": ROLE_SEX[role]})` with that part pinned at its label's index when the rule has it); `sex: str`.
- **`PersonName(BaseModel)`:**
  - `rule_id: str`; `shape: int`;
  - `parts: list[NamedPart]`, where `NamedPart{label, text, source, from_id="", from_role="", working: list = []}`;
  - `built_as: dict[str, str]`;
  - `name: str`, the written name;
  - `missing: list[MissingParent]`.
- **`build_person_name(language, ctx: PersonContext, *, rule_id: str | None = None, shape=None, pinned=None, meaning: str = "", rng=None) -> PersonName`:**
  - It takes each part's first roll.
  - `meaning` fills the first meaning part through 4b-1's `build_phrase` from `read_english`'s structure. This is the no-model path; a meaning with words missing from the dictionary takes a random dictionary word instead (the draft has no model turn for coining).
  - It has no model call.
- **`written(language, rule_id, shape, texts: list[str]) -> str`:** the parts joined by spaces, a `word` part written as its `english` when set. A part of `MISSING_RULE` is skipped.
- **`roll_pet_name(language, own: dict[str, str], rng) -> tuple[str, str] | None`:** `(name, rule_id)` from the first rule with `use == "pet names"`, or `None`.
- **`address_row(language, role: str) -> AddressRow | None`:** the first row whose `roles` match (`role_matches`), else the `default` row.
- **`kept_title(language, english: str) -> KeptTitle | None`:** a case-insensitive match on `meaning`.

- [ ] **Step 1: Write the failing tests.** Use a Drassonais-like fixture:
  - a noble women's rule: `given · word "di" english "of" · connection roles ["father","mother"] take "house"`;
  - a commoner's rule: `given · word "daughter of" · connection roles ["father"] take "given"`;
  - a Varovni-like family part with `person_forms` `{sex: woman} → ending "a"`.

```python
def test_inherited_part_comes_from_the_real_parent(world_with_eilhaud):
    ctx = PersonContext(thing_id=None, built_as={"sex": "woman", "rank": "noble"},
                        connections=[Connection(role="daughter of", thing_id=EILHAUD, name="Eilhaud of Drassone",
                                                parts={"given": "Eilhaud", "house": "Drassone"}, built_as={"sex": "man"})])
    named = build_person_name(DRASSONAIS, ctx, rng=random.Random(1))
    assert named.parts[2].text == "Drassone" and named.parts[2].source == "inherited"
    assert named.parts[2].from_id == EILHAUD
    assert named.name.endswith(" of Drassone")          # "di" written in English

def test_woman_form_applies_to_the_inherited_family_part():
    named = build_person_name(VAROVNI, _ctx(sex="woman", parent_parts={"family": "Kesterovsk"}), rng=random.Random(1))
    assert "Kesterovska" in named.name

def test_rank_picks_the_rule():
    assert pick_rule(DRASSONAIS, {"sex": "woman", "rank": "common"}).id == "common-women"
    assert pick_rule(DRASSONAIS, {"sex": "woman", "rank": "noble"}).id == "noble-women"

def test_mother_then_father_by_role_words_then_built_as_then_first():
    mother = Connection(role="child of", thing_id="m", name="Aurande", built_as={"sex": "woman"})
    father = Connection(role="child of", thing_id="f", name="Eilhaud", built_as={"sex": "man"})
    part = NamePart(kind="connection", roles=["mother", "father"], take="")
    assert parent_for(part, _ctx_with([father, mother])).thing_id == "m"
    plain = Connection(role="child of", thing_id="x", name="Someone")
    assert parent_for(part, _ctx_with([plain])).thing_id == "x"

def test_missing_parent_is_rolled_and_offered_as_a_full_name():
    named = build_person_name(DRASSONAIS, _ctx(sex="woman", rank="noble"), rng=random.Random(2))
    assert named.parts[2].source == "rolled"
    assert named.missing and named.missing[0].role == "father"
    assert named.missing[0].name.endswith(named.parts[2].text) and named.missing[0].sex == "man"

def test_a_bad_parent_falls_back_to_a_roll(view_with_stub_and_deleted):
    conns = connections_of(view_with_stub_and_deleted, SELF, [(SELF, "daughter of"), (DELETED, "daughter of")], [])
    assert all(c.thing_id not in (SELF, DELETED) for c in conns)
    named = build_person_name(DRASSONAIS, PersonContext(thing_id=SELF, built_as={}, connections=conns), rng=random.Random(3))
    assert named.parts[2].source == "rolled"

def test_unknown_choices_fall_back_to_the_first():
    assert choose(DRASSONAIS, {"sex": "female", "rank": "duke"}) == {"sex": "man", "rank": "common"}

def test_pet_name_address_and_kept_title():
    assert roll_pet_name(DRASSONAIS, {"given": "Maëlis"}, random.Random(1))[0].endswith("ette")
    assert address_row(DRASSONAIS, "her mother").kind == "family"
    assert address_row(DRASSONAIS, "a passing guard").kind == "strangers"
    assert kept_title(MOSCAVIAN, "Emperor").word == "Tsar"

def test_old_rules_roll_as_before():
    assert roll_parts(VAROVNI_4B1, "owl-names", rng=random.Random(5)) == roll_parts(VAROVNI_4B1, "owl-names", rng=random.Random(5), person=None)
```

The fixture `_ctx(sex="woman", parent_parts=...)` builds a `PersonContext` with one "daughter of" connection.

- [ ] **Step 2: Run them to make sure they fail.**
Run: `… pytest tests/languages/test_person_names.py -q -p no:cacheprovider`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `person_names.py`** and the `composed.py` and `naming.py` changes, as in Interfaces. `ROLE_SEX = {"mother": "woman", "father": "man", "daughter": "woman", "son": "man"}`. The parent-like words are `("son of", "daughter of", "child of", "parent", "mother", "father")`.

- [ ] **Step 4: Run them, plus `tests/languages`, to make sure they pass.**
Expected: PASS. 4b-1's `test_composed.py` is unchanged and green.

- [ ] **Step 5: Commit** `feat(languages): build people's names from connections, sex and rank`.

---

### Task 3: A person's name parts, titles and pet names, stored and edited

**Files:**
- Modify: `src/talemate/world/kinds.py`, `src/talemate/worldplay/repoint.py`, `src/talemate/server/worlds.py`.
- Test: `tests/worldplay/test_person_name_store.py`, `tests/server/test_worlds_person_names.py`.

**Interfaces — Consumes:** Task 2's `PersonContext`, `connections_of`, `build_person_name`, `written`, `roll_pet_name`, `kept_title`, `choose`.

**Interfaces — Produces:**
- **Character kind field `name_parts`** (json): `{language: <32-hex>, rule: str, shape: int, built_as: {str: str}, parts: [{label, text, source, from_id?, from_role?, working?}]}`. A validator `_validate_name_parts` checks those keys and types.
- **`AKA_KEYS`** becomes `("name", "tag", "everyday", "language", "kind", "by", "meaning", "rule", "shown")`, where:
  - `kind ∈ {"pet", "title", "own"}`, or absent;
  - `by`: a 32-hex id, or absent (everyone);
  - `meaning`: str;
  - `rule`: str;
  - `shown ∈ {"before", "after"}`, title only, at most one per entry.
- **`rename_everywhere`** (`repoint.py`): after renaming, if the entry has `name_parts` and `written(...)` of them no longer equals the new name, it removes `name_parts`.
- **Server actions.** Each replies with the thing payload (`_thing_payload`), as `name_it_rename` does:
  - `name_it_rename` accepts optional `parts` (a list of `{label, text, source, from_id?, from_role?}`), `rule_id`, `shape`, `language_id` and `built_as`, and writes `name_parts` in the same revision as the rename.
  - `person_name_part {thing_id, index, text}`: sets one part's text (source `"typed"`), rebuilds the written name, and renames everywhere.
  - `person_built_as {thing_id, built_as}`: stores it through `choose`; the name is not rebuilt.
  - `person_title_add {thing_id, name, language_id?, meaning?, by?, shown?}` and `person_title_remove {thing_id, name}`. A second `shown` title clears the first title's `shown`.
  - `person_kept_title {thing_id, english}` → `{english, word, language_id} | {english, word: null}`, using the person's language from `name_parts`, or else `language_of`. Offered, never applied.
  - `person_pet_name {thing_id, mode: "roll" | "set", name?, by?}`. Roll uses `roll_pet_name` on the person's parts and replaces the rule pet name (aka `kind: "pet"` with no `by`). Set with a `by` writes or replaces the per-person aka `{kind: "own", by}`.
  - `name_it_parts` accepts `thing_id` (or `draft: {filings, facts, built_as}`). It builds the `PersonContext` and passes it to `roll_parts`. Each part in the reply carries `source`, `from_id` and `from_role`, and inherited parts come back `pinned: true`.
- **The thing payload** gains `name_parts` (as stored, or null), and `calls`: `[{name, kind, by, by_name, rule, meaning}]` for akas with a `kind`. Rows whose `by` is no longer a live entry are dropped.

- [ ] **Step 1: Write the failing tests**

```python
def test_name_parts_validate_and_reject_garbage():
    validate_field("character", "name_parts", GOOD_PARTS)
    with pytest.raises(ValueError):
        validate_field("character", "name_parts", {"parts": "Maëlis"})

def test_akas_with_by_survive_validation():
    validate_field("character", "aka", [{"name": "Lisette", "tag": "proper", "everyday": False, "kind": "pet", "rule": "pets"},
                                        {"name": "Maë", "tag": "proper", "everyday": False, "kind": "own", "by": HEX}])
    with pytest.raises(ValueError):
        validate_field("character", "aka", [{"name": "A", "tag": "proper", "everyday": False, "kind": "title", "shown": "before"},
                                            {"name": "B", "tag": "proper", "everyday": False, "kind": "title", "shown": "after"}])

async def test_name_it_rename_writes_parts(server_with_drassonais):
    await server.handle_name_it_rename({"thing_id": MAELIS, "name": "Maëlis of Drassone", "language_id": DRASS,
                                        "rule_id": "noble-women", "shape": 0, "built_as": {"sex": "woman", "rank": "noble"},
                                        "parts": [{"label": "given", "text": "Maëlis", "source": "rolled"},
                                                  {"label": "of", "text": "di", "source": "word"},
                                                  {"label": "house", "text": "Drassone", "source": "inherited", "from_id": EILHAUD}]})
    assert reply()["name_parts"]["parts"][2]["from_id"] == EILHAUD

async def test_editing_a_part_renames_everywhere(server_with_maelis):
    await server.handle_person_name_part({"thing_id": MAELIS, "index": 0, "text": "Ysolde"})
    assert thing(MAELIS).fields["name"] == "Ysolde of Drassone"
    assert "Ysolde of Drassone" in fact_text_naming(MAELIS)

def test_a_hand_rename_clears_parts_and_name_it_starts_fresh(world_with_maelis):
    rename_everywhere(rev, world, MAELIS, "Maëlis the Red")
    assert "name_parts" not in thing(MAELIS).fields
    parts = name_it_parts_for(MAELIS)          # the server action's reply
    assert [p["pinned"] for p in parts] == [False, False, True]   # only the live father's house

async def test_a_shown_title_replaces_the_last(server_with_maelis):
    await server.handle_person_title_add({"thing_id": MAELIS, "name": "Lady", "shown": "before"})
    await server.handle_person_title_add({"thing_id": MAELIS, "name": "Warden", "shown": "after"})
    titles = [a for a in thing(MAELIS).fields["aka"] if a.get("kind") == "title"]
    assert [t.get("shown") for t in titles] == [None, "after"]

async def test_kept_title_is_offered_not_applied(server_with_moscavian_person):
    await server.handle_person_kept_title({"thing_id": IVAN, "english": "Emperor"})
    assert reply() == {"english": "Emperor", "word": "Tsar", "language_id": MOSC}
    assert not any(a.get("kind") == "title" for a in thing(IVAN).fields.get("aka", []))

async def test_calls_drop_a_deleted_caller(server_with_maelis_and_tiboud):
    delete(TIBOUD)
    assert all(c["by"] != TIBOUD for c in thing_payload(MAELIS)["calls"])
```

- [ ] **Step 2: Run them to make sure they fail.**
Run: `… pytest tests/worldplay/test_person_name_store.py tests/server/test_worlds_person_names.py -q -p no:cacheprovider`
Expected: FAIL.

- [ ] **Step 3: Implement** the field validators, the `rename_everywhere` clearing, the actions, and the payload keys, as in Interfaces. Add each action to the module docstring's action list, as the file does for every action.

- [ ] **Step 4: Run them, plus `tests/worldplay tests/server -k "name or aka or rename or repoint"`, to make sure they pass.**
Expected: PASS.

- [ ] **Step 5: Commit** `feat(worlds): a person's name parts, titles and pet names`.

---

### Task 4: Probe (AI, permitted by the owner)

**Files:**
- Create: `scripts/dev/probe_4b2.py` and `docs/superpowers/probes/2026-11-04-languages-4b2.md`.

**Runs:**
1. **The draft's person block** on the world model (Skyfall on koboldcpp, the test app's client settings). Use 15 person prompts across the owner's languages; at least 5 should only hint at rank or sex ("the duke's heir", "a fisherman's girl", "the old smith"). Render the Task 5 prompt addition, `create-thing.jinja2` with its `person` request, and parse with `parse_person_block`. Write the prompt text first in a scratch copy, so the probe runs before Task 5 lands.
   - Score: the JSON parses; sex is right; rank is plausible; the meaning is a short English phrase that fits the facts; the title is English or empty.
2. **Fill them in for people's names** on the agent route (Claude Code, `claude_code.py`), on the six languages in the test app's worlds. Use the Task 8 brief text, drafted here first in scratch. For each language, score:
   - whether the rules it writes build the examples in its own naming prose: Moscavian patronymics, Varovni owl-names and -ovsk/-ovska, Drassonais di + place;
   - whether `check.py` passes;
   - what it missed.

**Decision rules:**
- **The person block.** If it parses in at least 13 of 15 and sex is right in at least 13 of 15, keep it on the draft call. Otherwise, rule on a fallback and record it: a separate small call on the language agent's client, made only when the person's language has people rules.
- **Fill them in.** If it fails on a language, record what the owner must fill by hand. No fallback is built.

- [ ] **Step 1:** Write `probe_4b2.py`, modelled on `scripts/dev/probe_4b1.py`, with raw replies saved as JSON next to the write-up.
- [ ] **Step 2:** Run both stages and record the raw output and the scores in the probe doc.
- [ ] **Step 3:** Ledger a ruling for each decision rule, then commit `docs(languages): 4b-2 probe`.

---

### Task 5: The draft builds the person's name

**Files:**
- Modify: `prompts/templates/world/create-thing.jinja2`, `src/talemate/worldplay/create.py`, `src/talemate/worldplay/cleaning.py`, and the fixed-preview path in `server/worlds.py` (`_fixed_preview`, so e2e fixtures can carry a `person` block).
- Test: `tests/worldplay/test_create_person_name.py`.

**Interfaces — Consumes:** Task 2 (`connections_of`, `choose`, `build_person_name`, `roll_pet_name`) and Task 3 (`name_parts`, AKA keys).

**Interfaces — Produces:**
- **The prompt, for kind `character` only,** asks for `"person": {"sex": "man|woman|…", "rank": "<one word>", "name_meaning": "<a short English meaning that fits them, or empty>", "title": "<an English title they hold, or empty>"}`, inside the wrapper object.
- **`parse_person_block(reply: str) -> dict[str, str]`** (in `create.py`): the four keys, each stripped; a missing block is `{}`.
- **`CreatePreview` gains `person: dict[str, str] = {}`.**
- **`name_person(view, preview: CreatePreview, language_id: str) -> CreatePreview`** (in `cleaning.py`), called at the end of `clean_preview` for `kind == "character"` when the used language has people rules: a rule with `for_person`, or a `connection` part. It does this:
  1. **The owner's own name.** If the prompt contains `preview.name` (case-insensitive, whole words), the name is the owner's: keep it. `name_parts` is filled only when its word count equals the picked rule's part count (the sources are `typed`). Otherwise there are no parts.
  2. **Otherwise, build it.** The context comes from the draft's filings (ticked and model rows, `(target_id, role)`) and its relationship facts (text plus the refs its linked names resolve to through `entry_names`). Sex and rank come from `choose(language, preview.person)`. Then `build_person_name(..., meaning=preview.person.get("name_meaning", ""))`.
  3. **Rename the draft.** The draft's name, fact texts, prose and elsewhere texts are renamed from the old name to the new one. Use the same whole-word replacement `pickName` does client-side, in a new `rename_in_preview(preview, old, new) -> CreatePreview`.
  4. **Record the name.**
     - Set `preview.fields["name_parts"]`.
     - Add a `Mark` on the new name, with `why = "built from <Language>'s rules"` and `language_id`, so the name stays marked.
  5. **Titles and pet names.**
     - A non-empty `person.title` becomes an aka `{kind: "title", shown: "before"}`. A kept title is never substituted.
     - A rule pet name becomes an aka `{kind: "pet", rule}`.
  6. **Missing parents.** Each `MissingParent` becomes a `NewName` (kind character, unticked), plus an unticked `PreviewFiling` from the person to that new name with role `"<daughter|son|child> of"`, worked out from the person's sex.
- **Accept** writes `fields["name_parts"]` like any field (`_write_preview` already writes `fields`). After accept, a `MissingParent` stub that was ticked gets its own `name_parts`, built with the sex from `ROLE_SEX`.

- [ ] **Step 1: Write the failing tests**

```python
def test_person_block_parses_and_tolerates_absence():
    assert parse_person_block('{"name": "X", "person": {"sex": "woman", "rank": "noble", "name_meaning": "", "title": "Lady"}, "facts": []}')["title"] == "Lady"
    assert parse_person_block('{"name": "X", "facts": []}') == {}

async def test_daughter_of_eilhaud_gets_the_house_and_a_built_given_name(world_test3_like):
    preview = await clean_preview(world, _preview("a daughter of Eilhaud of Drassone", name="Elise",
                                                  filings=[(EILHAUD, "daughter of")],
                                                  person={"sex": "woman", "rank": "noble", "title": "Lady"}), None)
    assert preview.name.endswith("of Drassone") and preview.name != "Elise"
    assert "Elise" not in " ".join(f.text for f in preview.facts)
    assert preview.fields["name_parts"]["parts"][-1]["from_id"] == EILHAUD
    assert any(m.name == preview.name and "rules" in m.why for m in preview.marks)
    assert any(a.get("kind") == "title" and a["name"] == "Lady" for a in preview.aka)

def test_a_name_from_the_prompt_is_never_rebuilt(world_test3_like):
    preview = run(clean_preview(world, _preview("Ysolde, daughter of Eilhaud", name="Ysolde", filings=[(EILHAUD, "daughter of")]), None))
    assert preview.name == "Ysolde"

def test_a_missing_or_unknown_person_block_uses_defaults(world_test3_like):
    preview = run(clean_preview(world, _preview("a girl of the house", name="Elise", person={"sex": "female", "rank": "??"}), None))
    assert preview.fields["name_parts"]["built_as"] == {"sex": "man", "rank": "common"}   # the fixture's first choices

def test_a_missing_father_is_offered_unticked(world_without_parent):
    preview = run(clean_preview(world, _preview("a noble daughter", name="Elise", person={"sex": "woman", "rank": "noble"}), None))
    stub = next(n for n in preview.new_names if n.kind == "character")
    assert stub.ticked is False
    assert any(f.new_name and f.new_name.name == stub.name and not f.ticked and f.role == "daughter of" for f in preview.filings)

def test_a_world_without_people_rules_is_left_alone(world_varovni_4b1_only):
    preview = run(clean_preview(world, _preview("a hunter", name="Dorvak"), None))
    assert preview.name == "Dorvak" and "name_parts" not in preview.fields
```

- [ ] **Step 2: Run them to make sure they fail.**
Run: `… pytest tests/worldplay/test_create_person_name.py -q -p no:cacheprovider`
Expected: FAIL.

- [ ] **Step 3: Implement** the prompt addition, the parser, `name_person`, `rename_in_preview`, the stub naming on accept, and the fixed-preview `person` key. Apply Task 4's ruling if the person block moved to its own call.

- [ ] **Step 4: Run them, plus `tests/worldplay tests/prompts -k "create or clean"`, to make sure they pass.**
Expected: PASS. Existing create prompt snapshot tests are updated only for the `character` branch.

- [ ] **Step 5: Commit** `feat(worlds): a drafted person's name built from their language`.

---

### Task 6: The person's page: Name section and "calls her" (mockup B)

**Files:**
- Create: `PersonName.vue`, `CallsLine.vue`, `personName.js`.
- Modify: `ThingPage.vue` (mounts `PersonName` above `EntryIn` for kind `character` with `name_parts` or a language), `FactRow.vue` (a `CallsLine` under a `relationship` fact), `stores/worlds.js` (actions for Task 3's requests).
- Test: `talemate_frontend/checks/worlds.check.mjs`; e2e `tests/e2e/worlds/test_person_name.py`.

**Interfaces — Consumes:** the payload's `name_parts` and `calls`; Task 3's actions.

**Interfaces — Produces:**
- **`personName.js`:**
  - `writtenName(parts, english)`;
  - `callsFor(calls, fact)`: the calls whose `by` is in `fact.refs`, minus `kind: "pet"` without a `by`;
  - `partSourceLine(part)`: "from her father Eilhaud" from `from_role` and `by_name`, else "rolled", "typed" or "from a meaning".
- **`PersonName.vue`** (test ids `person-name`, `person-name-part`, `person-name-part-edit`, `person-built-as`, `person-titles`, `person-title-add`, `person-pet-name`):
  - a line with the language and rule;
  - a fixed grid of parts, one column per part, with no reflow while editing;
  - inherited parts are outlined, with a link to the source;
  - "built as" chips that open a select per choice;
  - a titles list with "+ Title": type English, or give a meaning and a language, which opens Name it with `target: {titleOf: thingId}` and no rule; while typing English, the `person_kept_title` offer shows as a chip;
  - the pet name line "pet name: Lisette · used by family", with ↻ and ✎.
- **`CallsLine.vue`** (`calls-line`): folded by default, it shows "calls her: Maë" when folded. Opened, each name gets its source tag and ✎; rule names also get ↻.
- **The pronoun** "her", "him" or "them" comes from `built_as.sex` (woman → her, man → him, otherwise them).

- [ ] **Step 1: Write the failing checks.** Add to `worlds.check.mjs`:
  - `writtenName` writes `english`;
  - `callsFor` keeps only refs and drops the rule pet name;
  - `partSourceLine` reads "from her father Eilhaud".

  Add the e2e tests to `test_person_name.py`, using a seeded world with Eilhaud, Aurande, Tiboud and Maëlis with `name_parts`:
  - `test_name_section_shows_parts_and_their_source`;
  - `test_editing_a_part_renames_the_page`;
  - `test_calls_her_shows_only_what_differs`: Tiboud's row shows "Maë" and Aurande's row shows none;
  - `test_calls_her_skips_a_deleted_caller`;
  - `test_title_from_a_meaning_opens_name_it_and_saves_a_title`, which uses the fixed meaning reply as 4b-1's e2e tests do.
- [ ] **Step 2: Run them to make sure they fail.**
- [ ] **Step 3: Implement** the components and store actions. Take a screenshot at 1920×1080 and compare it with mockup B.
- [ ] **Step 4: Run the checks, `pnpm build`, and the new e2e file to make sure they pass.**
- [ ] **Step 5: Commit** `feat(worlds): a person's name in parts, and what others call them`.

---

### Task 7: Name it on a person, and the draft

**Files:**
- Modify: `NameItPanel.vue`, `NameBuilder.vue`, `nameParts.js`, `stores/worlds.js`.
- Test: `checks/worlds.check.mjs`; e2e `tests/e2e/worlds/test_name_it.py` (new cases).

**Interfaces — Consumes:** Task 3's `name_it_parts` with `thing_id` or `draft`, and `name_it_rename` with `parts`.

**Interfaces — Produces:**
- **On a person, or a person draft,** the builder sends `thing_id`, or `draft: {filings, facts, built_as}`, with `name_it_parts`.
- **Inherited parts** arrive pinned, with a source line under their chips ("from her father Eilhaud"). Unpinning lets them roll.
- **The current parts** (`name_parts`) pre-fill as typed pins on open.
- **The rule picker** defaults to `name_parts.rule`, or else the server's `pick_rule` result, which `name_it_parts` returns as `rule_id` when none is sent.
- **Use this name** sends `parts`, `rule_id`, `shape`, `language_id` and `built_as`, with the rename. On a draft it sets `edited.fields.name_parts` alongside `pickName`.
- **The `titleOf` target:** picking adds a title (`person_title_add` with `language_id` and `meaning`) instead of renaming.

- [ ] **Step 1: Write the failing tests.**
  - check: `composeName` skips `MISSING_RULE` and writes `english`;
  - e2e `test_name_it_on_a_person_pins_the_inherited_house`;
  - e2e `test_reroll_keeps_inherited_parts`;
  - e2e `test_use_this_name_stores_parts` (the page's Name section shows them after);
  - e2e `test_draft_shows_the_built_name_marked`, with a fixed preview that has a `person` block and a filing to Eilhaud.
- [ ] **Step 2: Run them to make sure they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the checks, the build, and the e2e file to make sure they pass.**
- [ ] **Step 5: Commit** `feat(languages): Name it on a person keeps what's inherited`.

---

### Task 8: The Names chapter, the skill, and Fill them in

**Files:**
- Create: `PeopleNamesCard.vue`.
- Modify: `LanguageBook.vue` (mount it under the Grammar for names card), `LanguageSections.vue` (rule chips for `connection`, `own`, `english` and `for_person`), `src/talemate/server/worlds.py` (`language_people_names {language_id, people_names}`, a row-by-row save through the same merge as `language_name_grammar`), `brief.py`, `making.py`, `.claude/skills/language-design/SKILL.md`, `reference/rule-syntax.md`.
- Test: `tests/languages/test_brief.py` (new cases), `tests/server/test_worlds_name_grammar.py` (new cases), e2e `tests/e2e/worlds/test_names_chapter.py` (new cases).

**Interfaces — Produces:**
- **The People-name card** (`people-names-card`) has three blocks, each editable row by row:
  - **Choices:** sex and rank lists, with the first marked as the default.
  - **Kept titles:** word, then "emperor".
  - **Address:** kind, role words, uses, with an example built from a sample person. The sample person comes from the language's people rule rolled with the default choices, and its pet name from `roll_pet_name`.

  A language with none shows "No people's-name rules yet: people get 4b-1 names. **Fill them in from the grammar**".
- **Rule chips:**
  - `[from mother, then father · house]`;
  - `[own given]`;
  - a fixed word shows its English: `[di → "of"]`;
  - a rule's `for_person` shows as "for: woman · noble" next to its name.
- **Fill them in:** `MakeRequest(kind="names")`'s brief also asks for:
  - `people_names` (choices, kept titles, address);
  - connection and own parts, `person_forms` and `for_person`, written from the naming prose;
  - fixed words of the "of" kind marked with `english`, unless the prose says the native word is used in speech.

  The skill and `rule-syntax.md` describe the same, with Drassonais and Varovni examples.

- [ ] **Step 1: Write the failing tests:**
  - `test_names_brief_asks_for_people_names`;
  - `test_language_people_names_saves_a_row_and_merges`;
  - e2e `test_people_names_card_shows_and_edits_address`;
  - e2e `test_rule_chips_show_connection_and_english`.
- [ ] **Step 2: Run them to make sure they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them to make sure they pass, then run the full plain suite and the checks.**
- [ ] **Step 5: Commit** `feat(languages): people's names in the Names chapter, skill and brief`.

---

### Task 9: Acceptance (AI, permitted by the owner; ask before restarting the test app)

**Files:**
- Create: `docs/superpowers/probes/2026-11-04-languages-4b2-acceptance.md` and `real_runs_4b2.py` (in the plan's sdd workspace, modelled on the 4a and 4b-1 runs).

- [ ] **Step 1:** Run the full e2e suite (`-m e2e -n 4`) and the plain suite. Both green.
- [ ] **Step 2:** Ask the owner before updating and restarting the test app. Then back up `worlds/` and `config.yaml`, copy `src` and `talemate_frontend/src`, and restart the backend only.
- [ ] **Step 3: Real runs on Skyfall** in the owner's worlds, with the owner's tab closed (one frontend):
  1. **Fill them in** on Drassonais and Varovni (Claude Code route).
  2. **A daughter of Eilhaud of Drassone** in Test3: the built name, its parts, its title, and its missing-parent stubs.
  3. **A Varovni hunter's son** with a meaning-based owl-name.
  4. **Name it** on the drafted person: reroll keeps the house.
  5. **A title from a meaning** ("chief of chiefs").

  Record the screenshots, the timings and the raw replies.
- [ ] **Step 4:** Write up the acceptance doc and hand it to the owner for their verdict and feedback rounds.
