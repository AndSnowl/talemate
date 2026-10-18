# Cultures AI Implementation Plan (plan 2 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the story use the cultures built in plan 1. A new **Culture agent** puts a compact culture section into the narrator's and actors' prompts, names new characters from their culture's generators before the rest of the character is written, records every name in the glossary, and after each world state snapshot spots new names, new places and new customs. Everything it adds is used at once and marked for review.

**Architecture:**
- **Pure logic** in new modules under `src/talemate/cultures/`: word rules, scene-culture resolution, naming choices, the prompt section builder, post-snapshot detection, and a `cultures.event` signal. No LLM calls in these modules, so they're tested without a model.
- **The agent** in a new package `src/talemate/agents/culture/` (agent type `culture`). It connects to five signals in `connect(scene)` and makes three kinds of small model call: picking a name, inferring new places, finding culture additions. Its prompts are new templates under `src/talemate/prompts/templates/culture/`.
- **Four small core edits** (listed in Global Constraints): a `culture` field on `Character`, a pre-naming hook in the creator, a post-snapshot signal, and the agent's import line.
- **The existing `cultures` websocket plugin** (plan 1) forwards the agent's events and pushes fresh `world` data to the open Cultures tab. It also gains character-culture review. The frontend gains a People view, a "doesn't fit" flag, and a fix for additions that arrive while you're editing.
- **Testing:** stubbed-LLM unit tests that the implementer runs; browser tests for the frontend; an opt-in AI test group plus an overnight evaluation script, both run only by the controller.

**Tech Stack:** Python 3.11, pydantic 2, pytest (pytest-asyncio, `asyncio_mode=auto`), Jinja2 prompt templates, `websockets` (sync client) for the AI driver, Vue 3 + Vuetify 3, Playwright for the e2e group.

**Spec:** `docs/superpowers/specs/2026-10-17-cultures-and-languages-design.md`. Read sections 5.4, 7 and 8.1 before starting, and section 10 for the core-edit rule. This plan builds on plan 1, `docs/superpowers/plans/2026-10-17-cultures-foundation.md`; its Interfaces blocks describe the existing `talemate.cultures` API (`roll`, `fits`, `WorldStore`, `effective_mix`, `describe_mix`, `set_shares`). Testing setup: `docs/dev/local-testing.md`.

**The four plans:** 1 *Foundation* (done) · 2 *AI use* (this plan) · 3 *In the story*: highlights, bubbles, World panel chips, app-level badge · 4 *Rename everywhere*. Nothing in this plan highlights text in the story or renames anything.

**Environment.** This is a Guix machine. Every command runs from the repo root through `guix shell -m manifest.scm -- …`, always with `uv run --no-sync` (a plain `uv run` drops the dev extra). The commands:
- Plain suite: `guix shell -m manifest.scm -- uv run --no-sync pytest` (add `-n0 -v` and a path for one file). The plain suite has 141 known failures from missing NLTK `punkt_tab` data. Judge a run by "no new failures".
- Browser group: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e -m e2e -n0 -v`
- AI group (**controller only**): `TALEMATE_AI_TESTS=1 guix shell -m manifest.scm -- uv run --no-sync pytest tests/ai -m ai -n0 -v`
- Frontend build: `guix shell -m manifest.scm -- sh -c 'cd talemate_frontend && npx --yes corepack@0.34.0 pnpm run build'`
- Lint: `guix shell -m manifest.scm -- uv run --no-sync ruff check <paths>` and `… ruff format --check <paths>`

## Global Constraints

- **Core edits: exactly these four, and nothing else in existing non-cultures files.**
  1. `src/talemate/character.py`:
     - add the field `culture: CharacterCulture | None = None` to `Character`
     - in `Character.update()`, add a `culture` branch that validates a dict into `CharacterCulture` (like the existing `voice` branch)
     - in `apply_shared_context()`, add `self.culture = other_character.culture.model_copy() if other_character.culture else None` next to the existing explicit `folder` line
  2. `src/talemate/agents/creator/character.py`:
     - register the signal `agent.creator.before_name_character`
     - add the class `CharacterNamingEmission` and the helper `CreatorAgent._pre_name_character`
     - call it in `generate_character_aspects` when `"name"` is in the aspects
     - call it in `determine_character_name` behind a new `culture_hook: bool = True` keyword
     - make `_fill_aspect_name` pass `culture_hook=False`
  3. `src/talemate/agents/world_state/snapshot.py`: register `world_state.snapshot.after`, add `WorldStateSnapshotEmission`, and send it at the end of a successful `apply_snapshot_update`, after `world_state.emit()`.
  4. `src/talemate/agents/__init__.py`: one line, `from .culture import CultureAgent  # noqa: F401`.
- **Plan-1 files this plan may change (feature files, not core):** `src/talemate/cultures/models.py`, `src/talemate/server/cultures.py`, the components under `talemate_frontend/src/components/cultures/`, and `tests/e2e/seed.py`.
- **Nothing blocks or breaks play.**
  - Every signal handler in the Culture agent catches `Exception` (re-raising `GenerationCancelled`), logs it with `structlog`, and returns. A scene with no shared world, or a world with no cultures, gets no section, no naming and no detection. Behaviour is then exactly as before.
  - Disk errors (`OSError`, `WorldFileError`) are caught the same way.
- **No extra model calls per turn** (spec anti-goal 1).
  - The prompt section is built from files and rules only.
  - Model calls happen only:
    - on character naming: one call
    - after a snapshot: at most one place call and at most one additions call
  - The additions call runs only when a culture is present in the scene and new messages exist since the last check.
- **Existing names are never replaced.** The hook pre-supplies a name only when the creator was about to invent one. A name that `looks_like_name()` or appears capitalised mid-sentence in the scene's messages is kept. It goes to the glossary instead, with `doesnt_fit` set when `fits()` is false.
- **Owner-set cultures are final.** The AI never changes a `CharacterCulture` with `set_by == "owner"`. It never edits an existing place's cultures, whoever set them. It only creates new places, with `set_by="ai"`.
- **Glossary writes from the AI:**
  - `status="unreviewed"`.
  - Generator picks use `origin.by="ai"`, with `generator_id` and every candidate.
  - A spare name the narrator was offered and then used also counts as a generator pick (Task 8).
  - Every other AI-recorded name uses `origin.by="ai_free"`.
  - Glossary text matching is case-insensitive across all languages, so a name is never added twice.
- **Single-loop safety.** Agent code never `await`s between a `WorldStore.load_*` and the matching `save_*` of the same file. Everything runs on one asyncio loop, so this keeps owner edits from being lost.
- **The section** is one `DynamicInstruction` with the title `"Cultures and names"`. It is never larger than the `context_budget` config value (default 400 tokens, counted with `talemate.util.count_tokens`). The spare-names line starts with exactly `"If you need a new name, use one of these:"` (the constant `SPARE_NAMES_PREFIX`).
- **Candidate count** comes from the `candidates` config value (default 20). Rolls exclude every glossary text and every name in `scene.all_character_names`.
- **New templates** live in `src/talemate/prompts/templates/culture/`. Every `<|SECTION:…|>` is closed by `<|CLOSE_SECTION|>` (`tests/prompts/test_template_section_validation.py` checks all templates).
- **AI tests are opt-in.** They live under `tests/ai/`, check outcomes and never wording, and are run only by the controller. Implementers never set `TALEMATE_AI_TESTS=1`; they only confirm the group skips without it.

## Review Focus

These inputs are likely to bite the owner, though no spec line names them. Each has a test in the task that owns the code.

1. **No shared world, no cultures, or an unreadable culture file** (including a file whose generator is invalid, plan 1's known gap). Narration and character creation must behave exactly as before, with no exception reaching the user. (Task 6: `test_hooks_noop_without_world`; Task 3: `test_invalid_generator_returns_none`)
2. **The model answers the name pick off-list.** It might be empty, quoted, followed by an explanation, or a name that isn't a candidate. Creation must still get a candidate name, never fail. (Task 3: `test_match_candidate_variants`; Task 7: `test_pick_off_list_uses_first_candidate`)
3. **Snapshot keys that are descriptions or carry punctuation**: "the old ferryman", "a rusty lantern", "Lantern", "Tovrin's", "Brannoch.". Descriptions are skipped; names are cleaned before the glossary lookup. (Task 2: `test_clean_name_and_looks_like_name`; Task 8: `test_snapshot_skips_descriptions_and_normalizes`)
4. **The owner changed a culture, then play continued.** Later snapshots and character saves must not touch it. (Task 8: `test_owner_culture_never_overwritten`)
5. **A big world against a small budget**: 300 customs, 1,000 glossary entries, budget 120. The section must still fit, and it keeps the place line first. (Task 4: `test_section_respects_budget_with_large_world`)

---

### Task 1: Character culture field and glossary "doesn't fit" flag

**Files:**
- Modify: `src/talemate/cultures/models.py` (add `CharacterCulture`; add `GlossaryEntry.doesnt_fit`; export both in `__all__` and `talemate/cultures/__init__.py`)
- Modify (core edit 1): `src/talemate/character.py`
- Test: `tests/cultures/test_character_culture.py`

**Interfaces:**
- Produces:
  - `CharacterCulture(BaseModel, extra="ignore")`, with fields:
    - `culture_id: str | None = None` (`None` means the owner said "no culture")
    - `set_by: Literal["ai","owner"] = "ai"`
    - `unsure: bool = False`
    - `reason: str = ""` (a short why, e.g. "picked from the Dhunmouth mix")
  - `GlossaryEntry.doesnt_fit: bool = False`
  - `Character.culture: CharacterCulture | None = None`

- [ ] **Step 1: Write the failing tests**
  - `test_character_culture_round_trip`: `Character(name="Kethrun", culture={"culture_id":"taelrik","unsure":True})` gives a `CharacterCulture`. `Character(**c.model_dump())` returns an equal culture.
  - `test_update_validates_culture_dict`: `c.update(culture={"culture_id":"elsiri","set_by":"owner"})` gives `isinstance(c.culture, CharacterCulture)` and `c.culture.set_by == "owner"`. `c.update(culture=None)` gives `c.culture is None`.
  - `test_apply_shared_context_copies_culture`:
    - other has culture taelrik, the local character has none → after `await local.apply_shared_context(other)`, `local.culture.culture_id == "taelrik"`, and the two objects are not the same instance.
    - other has `culture=None`, local has one → local's becomes `None`.
  - `test_shared_context_file_restores_culture`: build a `SharedContext(filepath=tmp_path/"w.json")` with a shared character carrying a culture, `write_to_file()`, then a new `SharedContext(filepath=…).init_from_file()` gives a `CharacterCulture`.
  - `test_glossary_entry_doesnt_fit_defaults_false`
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/cultures/test_character_culture.py -n0 -v`. Expected: FAIL (`ImportError: CharacterCulture`).
- [ ] **Step 3: Implement** the models and the three `character.py` edits named in Global Constraints. `character.py` imports `CharacterCulture` from `talemate.cultures.models`, which imports only pydantic, so there is no import cycle.
- [ ] **Step 4: Run** the same command, then `guix shell -m manifest.scm -- uv run --no-sync pytest tests/test_character.py tests/cultures -n0`. Expected: all pass.
- [ ] **Step 5: Commit**: `git add src/talemate/cultures src/talemate/character.py tests/cultures/test_character_culture.py && git commit -m "feat(cultures): culture field on characters"`

---

### Task 2: Word rules and the scene's cultures

**Files:**
- Create: `src/talemate/cultures/words.py`, `src/talemate/cultures/data/common_words.txt`, `src/talemate/cultures/scene_context.py`
- Test: `tests/cultures/test_words.py`, `tests/cultures/test_scene_context.py`

**Interfaces:**
- Consumes: `Place`, `Culture`, `CultureShare`, `effective_mix`, `describe_mix` (plan 1).
- Produces, in `words.py`:
  - `COMMON_WORDS: frozenset[str]`: lowercase. Loaded once from `data/common_words.txt` with `importlib.resources`. The file holds about 1,500 words, one per line: English stop words, then common nouns for people's roles (innkeeper, ferryman, guard…), objects, materials, buildings, terrain, colours and adjectives.
  - `clean_name(text: str) -> str`: strips whitespace, straight and curly quotes, trailing `.,;:!?`, and a trailing possessive `'s` / `’s`.
  - `looks_like_name(text: str) -> bool`. The text is cleaned first, and every rule below must hold:
    - it has 1–4 words
    - the first word is not one of `the a an some his her their my our your this that these those`
    - every word starts uppercase, except the connectors `of the de du van von al el la le`, which are allowed mid-name
    - not all non-connector words are in `COMMON_WORDS`
  - `mid_sentence_occurrence(name: str, text: str) -> bool`: an exact-case, whole-word occurrence whose preceding text, with trailing spaces stripped, is non-empty and doesn't end in `. ! ? : " “ ” ‘ '` or a newline.
  - `is_proper_item_name(name: str, texts: list[str]) -> bool`: true when `mid_sentence_occurrence` holds in any text, and the name is not a single word in `COMMON_WORDS`.
  - `first_mention(name: str, messages: list) -> object | None`: the first message whose `.message` contains `name` as a whole word (case-sensitive).
- Produces, in `scene_context.py`:
  - `@dataclass SceneCultures`, with fields:
    - `place: Place | None`
    - `mix: list[CultureShare]`
    - `mix_source: Place | None`
    - `description: str`: from `describe_mix`
    - `cultures: list[Culture]`: present cultures, in mix order (share descending) and then character cultures not already listed
  - `match_place(places: list[Place], location: str | None, snapshot_places: list[str]) -> Place | None`:
    - First: places whose name, or the name without a leading "The ", occurs whole-word and case-insensitively in `location`. If several match, the deepest place (most ancestors) wins.
    - Otherwise: an exact case-insensitive match against `snapshot_places`, deepest first.
    - Otherwise `None`.
  - `resolve_scene_cultures(cultures: dict[str, Culture], places: list[Place], location: str | None, snapshot_places: list[str], characters: list, fallback_place_id: str | None = None) -> SceneCultures`. When nothing matches, the place falls back to `fallback_place_id`. `characters` are `Character` objects; their `culture.culture_id` values that are in `cultures` are appended.

- [ ] **Step 1: Write the failing tests.**
  - In `test_words.py`:
    - `test_clean_name_and_looks_like_name`:
      - `clean_name("“Tovrin’s”") == "Tovrin"`; `clean_name("Brannoch.") == "Brannoch"`
      - `looks_like_name` is true for `"Tovrin"`, `"Hadrik Tolvar"` and `"Ilsa of the Birches"`
      - it is false for `"the ferryman"`, `"Innkeeper"`, `"a rusty lantern"`, `"Grey Gull"` and `""`
    - `test_mid_sentence_occurrence`: `("Grey Gull", "They boarded the Grey Gull at dawn.")` is true; `("Grey Gull", "Grey Gull sails tonight.")` and `("Grey Gull", "He said. Grey Gull…")` are false.
    - `test_is_proper_item_name`:
      - true: "Grey Gull" in "the Grey Gull"; "Saervik" in "He drew Saervik from its sheath."
      - false: "lantern" in "lifted the lantern"; "Lantern" in "lifted the Lantern"; "Rusty Sword" in "held a rusty sword"
    - `test_common_words_loaded`: `{"innkeeper","lantern","the"} <= COMMON_WORDS`; `len(COMMON_WORDS) >= 1000`.
  - In `test_scene_context.py`, use plan 1's fixture tree from `tests/cultures/test_places.py`:
    ```
    reach (country) taelrik 100
    ├── veldhaer (town)
    ├── dhunmouth (city) taelrik 55 / elsiri 30 / vaskari 15
    └── birch (region) elsiri 90 / taelrik 10
        └── ilsara (village)
    ```
    Copy the fixture builder into a shared `tests/cultures/_fixtures.py` and import it from both files.
    - `test_match_place_word_boundary_and_depth`:
      - `"The tavern in Veldhaer"` gives veldhaer
      - `"Ilsara, on the Birch Coast"` gives ilsara (deeper than birch)
      - `"Veldhaerton market"` gives `None`
      - `"Taelrik Reach border"` gives reach (its name without "The ")
    - `test_match_place_falls_back_to_snapshot_places`: `location=None` with `snapshot_places=["dhunmouth"]` gives dhunmouth.
    - `test_resolve_orders_mix_then_characters`: at dhunmouth, with a character whose culture is `ghun`, `[c.id for c in sc.cultures] == ["taelrik","elsiri","vaskari","ghun"]`.
    - `test_resolve_uses_fallback_place`: no match, `fallback_place_id="ilsara"` → `sc.place.id == "ilsara"`, and `sc.mix_source.id == "birch"`.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/cultures/test_words.py tests/cultures/test_scene_context.py -n0 -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** both modules and write `common_words.txt`. Compile regexes with `re.escape(name)` and `\b`.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit**: `git add src/talemate/cultures tests/cultures && git commit -m "feat(cultures): word rules and scene culture resolution"`

---

### Task 3: Naming choices (culture guess, generator, candidate match)

**Files:**
- Create: `src/talemate/cultures/naming.py`
- Test: `tests/cultures/test_naming.py`

**Interfaces:**
- Consumes: `SceneCultures` (Task 2), `roll`, `fits`, `GeneratorError` (plan 1), `clean_name`.
- Produces:
  - `@dataclass CultureGuess(culture_id: str | None, unsure: bool, reason: str)`
  - `guess_culture(cultures: dict[str, Culture], scene: SceneCultures, text: str, rng: random.Random) -> CultureGuess`, for a new character being named. Its rules, in order:
    1. A culture's name or its language's name occurs whole-word (case-insensitive) in `text` → that culture, `unsure=False`, reason `"named in the description"`.
    2. `scene.mix` is non-empty → weighted pick by share. `unsure` is true when the picked share < 70. Reason: `"picked from the <mix_source.name> mix"`.
    3. Otherwise, the most common culture among the character cultures in `scene.cultures` → `unsure=True`, reason `"from the people around them"`.
    4. Otherwise `CultureGuess(None, True, "no culture here")`.
  - `guess_culture_for_name(cultures, scene: SceneCultures, name: str) -> CultureGuess`, for a name that already exists. Only cultures with generators count. Its rules, in order:
    1. Exactly one present culture's language `fits` the name → that one, `unsure=False`.
    2. Several fit → the one with the highest share in `scene.mix`, `unsure=True`.
    3. None fit → the dominant culture of `scene.mix`, `unsure=True`.
    4. No mix → rule 3 of `guess_culture`.
    5. Otherwise `None`.
  - `infer_gender(text: str) -> Literal["female","male"] | None`: counts whole-word hits from two fixed lists (`she her woman girl daughter mother wife lady queen widow sister fishwife priestess` / `he his man boy son father husband lord king brother`). Returns the larger side, or `None` on a tie or zero.
  - `choose_generator(language: Language, gender, rng) -> GeneratorDef | None`:
    - **Candidates:** generators with `use == "people"` whose `id` or `name` contains neither "family" nor "surname".
    - **female:** the first whose id or name contains "female".
    - **male:** the first containing "male" but not "female".
    - **gender is None, or the wanted gender has no match:** a neutral one, i.e. containing neither "male" nor "female".
    - **gender is None and there's no neutral one:** `rng.choice` among the candidates.
    - **A known gender with no gendered or neutral match:** `None`.
  - `roll_candidates(language, generator: GeneratorDef, count: int, exclude: set[str], rng) -> list[str]`: returns `[]` on `GeneratorError` instead of raising.
  - `match_candidate(response: str, candidates: list[str]) -> str | None`:
    1. `clean_name` of the response's first line, matched case-insensitively against the candidates.
    2. Otherwise, the candidate whose whole-word occurrence in the response comes first.
    3. Otherwise `None`.
    It returns the candidate's own spelling.

- [ ] **Step 1: Write the failing tests.**
  - **Fixture language.** Plan 1's Taelrik (`tests/cultures/data/taelrik.culture.json`), plus an in-test copy of its language with a `given_female` generator added. Use the Task 2 places fixture for `SceneCultures`.
  - **Tests:**
    - `test_guess_named_in_description`: text `"an Elsiri net-mender"` at veldhaer gives elsiri, `unsure is False`.
    - `test_guess_weighted_by_mix`: at birch, 200 guesses with `random.Random(7)` give elsiri between 160 and 195 times. Each elsiri guess has `unsure is False` (share 90); each taelrik guess has `unsure is True`.
    - `test_guess_no_place_uses_characters_then_none`
    - `test_guess_for_name_fits_one`: a rolled Taelrik name gives taelrik, `unsure is False`. `"Xylophone"` at veldhaer gives taelrik, `unsure is True`.
    - `test_infer_gender`
    - `test_choose_generator_by_gender`: female gives `given_female`; male gives `given_male`; "family" is never chosen. Female on plan 1's original Taelrik (male-only) gives `None`.
    - `test_invalid_generator_returns_none`: a language whose generator has a bad reject rule `"["` → `roll_candidates(...) == []`.
    - `test_roll_candidates_excludes`: excluded names (in any case) never appear.
    - `test_match_candidate_variants`, with candidates `["Kethrun","Tovrin"]`:
      - `"Tovrin"`, `"\"tovrin.\""` and `"Tovrin — fits a ferryman"` give `"Tovrin"`
      - `"I pick Kethrun because…"` gives `"Kethrun"`
      - `""` and `"Marigold"` give `None`
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/cultures/test_naming.py -n0 -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `naming.py`.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit**: `git commit -m "feat(cultures): naming choices"` (add the new files first).

---

### Task 4: The prompt section builder

**Files:**
- Create: `src/talemate/cultures/context.py`
- Test: `tests/cultures/test_context.py`

**Interfaces:**
- Consumes: `SceneCultures`, `roll_candidates`, `Culture`, `Phrase`, `GlossaryEntry`, `talemate.util.count_tokens`.
- Produces:
  - `SECTION_TITLE = "Cultures and names"`; `SPARE_NAMES_PREFIX = "If you need a new name, use one of these:"`
  - `@dataclass LanguageTrait(character_name: str, culture_id: str, stem: str | None, verb: str)`
  - `TRAIT_VERBS: dict[str, tuple[str, ...]]`:
    - `"curse"`: curse, curses, cursing, swear, swears, swearing, cuss, cusses
    - `"saying"`: bless, blesses, pray, prays, proverb, proverbs, saying, sayings
    - `"greet"`: greet, greets, greeting, greetings
  - `language_traits(character, cultures: dict[str, Culture]) -> list[LanguageTrait]`:
    - Scans `description`, `dialogue_instructions`, and the values of `base_attributes` and `details`.
    - Pattern: `\b(<verb>)\b[^.\n]{0,24}?\bin (<language name>|<culture name>)\b`, case-insensitive.
    - `speaks <language name>` gives `stem=None`.
  - `pick_phrases(culture: Culture, stem: str | None, limit: int = 3) -> list[Phrase]`: phrases whose `category.lower()` starts with `stem` (so `curse` matches both `curse` and `curses`). With `stem=None`, the first phrase of each category, up to `limit`.
  - `@dataclass SpareName(text: str, culture_id: str, generator_id: str)`
  - `@dataclass CultureSection(text: str, tokens: int, spares: list[SpareName])`
  - `build_culture_section(*, scene: SceneCultures, cultures: dict[str, Culture], glossary: list[GlossaryEntry], characters: list, recent_text: str, budget: int, rng: random.Random, count_tokens=count_tokens) -> CultureSection`

**Section parts**, in priority order. Each part is a list of lines.
1. **Place:**
   - with a place: `"The scene is in {place.name}. {scene.description}"`
   - with no place but cultures present: `"Cultures here: {names}."`
   - with no cultures at all: return `CultureSection("", 0, [])`.
2. **Unwritable languages.** For each present culture with `writable == False`: `"{Culture} speech can't be written in letters. Describe how it sounds ({first sentence of sound}) and never spell it out."` Then `"Call {Culture} things by these names: {true_name or text} → {rendering in the local culture}, …"`, from glossary entries of that language that have a rendering for the local culture (the first of `scene.cultures`).
3. **Language traits.** For each present character with traits, at most 2 characters: `"{name} {verb}s in {Language}. Use these exact phrases: “{original}” ({translation}); …"`.
4. **Spare names.** `SPARE_NAMES_PREFIX`, then `"People ({Culture}): A, B, C. Places ({Culture}): D, E, F."` They come from cultures in `scene.mix` with share ≥ 25, at most 2 of them, 3 names per generator (`choose_generator(..., None, rng)` for people; the first `use == "places"` generator), excluding glossary texts.
5. **Names in use.** `"Names already in use, keep them exactly: Kethrun (Taelrik, person), Veldhaer (place), …"`. These are glossary entries whose `character_name` is a present character, or whose `place_id` is `scene.place` or one of its ancestors. At most 12.
6. **Culture notes.** Per present culture: `"{Culture}: {first sentence of description} Their language, {Language}, {first sentence of sound}"`, plus:
   - the 2 customs with the most word overlap with `recent_text` (or the first 2 on a tie at zero)
   - `food`, only if `recent_text` holds a word from `eat ate food meal dish drink supper breakfast feast tavern inn kitchen`
   - each holiday whose `name` or `when` appears in `recent_text`

**Trimming.**
- Add parts in order. When a part doesn't fit, drop its lines from the end until it fits; if no line fits, skip the part.
- Part 1 is always kept. If it alone exceeds the budget, cut it to the budget by words.
- `spares` is returned only for the names that made it into the text.

- [ ] **Step 1: Write the failing tests.** Fixtures: Task 2's tree, plan 1's Taelrik, and a small Elsiri culture built in-test. Add an unwritable `ghun` culture (`writable=False`, a glossary entry with `true_name="three falling hums"` and `renderings={"taelrik":"Khaz-Rull"}`). Add a character `Hadrik` whose description says "He curses in Taelrik when angry."
  - `test_section_contains_place_mix_and_spares`: at veldhaer, the text contains `"The scene is in Veldhaer."` and `SPARE_NAMES_PREFIX`. Every spare `fits` Taelrik, and every spare appears in the text.
  - `test_traits_insert_exact_curses`: with Hadrik present, both Taelrik curse originals appear verbatim, and no saying appears.
  - `test_unwritable_instruction_and_rendering`: with `ghun` present, the text contains `"never spell it out"` and `"Khaz-Rull"`.
  - `test_food_only_when_relevant`: the Taelrik `food` text is absent for `recent_text="They crossed the bridge."` and present for `"They sat down to supper at the inn."`.
  - `test_names_in_use_listed`: a glossary entry with `character_name="Kethrun"` and Kethrun present gives `"Kethrun (Taelrik, person)"`.
  - `test_section_respects_budget_with_large_world`: Taelrik with 300 customs, 1,000 glossary entries, 3 present characters with traits, `budget=120`. `count_tokens(text) <= 120`, and the text starts with `"The scene is in"`.
  - `test_empty_without_cultures`: no cultures gives `text == ""`.
  - `test_language_traits_patterns`: "swears in Taelrik" gives stem `curse`; "speaks Elsiri" gives stem `None`; "travelled in Taelrik lands" gives nothing.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/cultures/test_context.py -n0 -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `context.py`.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit**: `git commit -m "feat(cultures): prompt section builder"`

---

### Task 5: Core hooks: pre-naming and post-snapshot signals

**Files:**
- Modify (core edit 2): `src/talemate/agents/creator/character.py`
- Modify (core edit 3): `src/talemate/agents/world_state/snapshot.py`
- Test: `tests/test_culture_core_hooks.py`

**Interfaces:**
- Produces, in `creator/character.py`:
  ```python
  async_signals.register("agent.creator.before_name_character")

  class CharacterNamingEmission(AgentEmission):
      name: str = ""            # the request's current or descriptive name
      content: str = ""
      description: str = ""
      chosen_name: str | None = None   # set by a receiver to pre-supply the name
      dynamic_instructions: list[DynamicInstruction] = pydantic.Field(default_factory=list)
  ```
  - `CreatorAgent._pre_name_character(name: str, content: str, description: str) -> CharacterNamingEmission`: sends the signal and returns the emission.
  - In `generate_character_aspects`, before `one_shot` is computed:
    - when `"name" in request.aspects`, call `_pre_name_character(request.name, request.content, request.description)`.
    - When `chosen_name` is set, replace `request` with a `model_copy` where:
      - `name=chosen_name`
      - `"name"` is removed from `aspects`
      - `dynamic_instructions=(request.dynamic_instructions or []) + emission.dynamic_instructions`
    - Set `result.name = chosen_name` just before the final `log.debug`/`return`. Every later step, including example-dialogue normalisation, then uses the chosen name.
  - In `determine_character_name(..., culture_hook: bool = True)`: when `culture_hook and not group and not allowed_names`, call the hook first, and return `chosen_name` without an LLM call when it's set. `_fill_aspect_name` passes `culture_hook=False`.
- Produces, in `world_state/snapshot.py`:
  ```python
  talemate.emit.async_signals.register("world_state.snapshot.after")

  class WorldStateSnapshotEmission(AgentEmission):
      world_state: Any
      anchor_message_ids: list = pydantic.Field(default_factory=list)
  ```
  It is sent at the very end of `apply_snapshot_update`, after `world_state.emit()`, only on the success path (not after cancel, error or an empty response).

- [ ] **Step 1: Write the failing tests.** Use `MockScene` + `bootstrap_scene` (from `tests/conftest.py`), the `isolate_signals` and `connect_recorder` fixtures, and `patch_prompt_request_in` (`tests/_director_test_helpers.py`).
  - `test_split_name_presupplied_skips_llm`:
    - Connect a receiver that sets `chosen_name="Tovrin"`.
    - `await creator.generate_character_aspects(CharacterGenerationRequest(aspects=["name"], name="the ferryman", unified=False))` gives `result.name == "Tovrin"`.
    - No call to template `creator.determine-character-name` is recorded.
  - `test_fast_name_presupplied_removes_name_aspect`:
    - Use `unified=True` and `aspects=["name","description"]`.
    - The queued `creator.generate-character` response holds only `<DESCRIPTION>`.
    - The recorded call's `vars["aspects"] == ["description"]` and `vars["character_name"] == "Tovrin"`; `result.name == "Tovrin"`.
    - The receiver's `DynamicInstruction` appears in `vars["dynamic_instructions"]`.
  - `test_no_receiver_keeps_existing_behaviour`: with no receiver, the determine-name template is called and its `<NAME>` is used.
  - `test_determine_character_name_hook_and_opt_out`:
    - With the receiver, `determine_character_name("the ferryman")` returns `"Tovrin"`.
    - With `allowed_names=["A"]`, `group=True` or `culture_hook=False`, the receiver is not called (the `connect_recorder` list stays empty).
  - `test_fill_aspect_name_does_not_rehook`: in a split request where the receiver leaves `chosen_name=None`, the receiver is called exactly once.
  - `test_snapshot_after_signal_sent_on_success_only`:
    - Stub `request_world_state` to return a `WorldStateResponse(world_state={"characters":{},"items":{},"places":{},"location":"Veldhaer"}, anchor_message_ids=[1])`.
    - After `apply_snapshot_update`, one emission is recorded, with `.world_state.location == "Veldhaer"`.
    - With a stub that raises `RuntimeError`, none is recorded.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/test_culture_core_hooks.py -n0 -v`. Expected: FAIL.
- [ ] **Step 3: Implement** both core edits exactly as above. Nothing else in these files changes.
- [ ] **Step 4: Run** the same command, then `guix shell -m manifest.scm -- uv run --no-sync pytest tests/test_creator_character.py tests/test_director_character_management.py tests/test_world_state_agent.py tests/test_creator_nodes.py -n0`. Expected: all pass, no regressions.
- [ ] **Step 5: Commit**: `git commit -m "feat(core): pre-naming and post-snapshot hooks for the culture agent"`

---

### Task 6: Culture agent, events and context injection

**Files:**
- Create: `src/talemate/cultures/signals.py`, `src/talemate/agents/culture/__init__.py`
- Modify (core edit 4): `src/talemate/agents/__init__.py`
- Modify: `src/talemate/server/cultures.py` (forward events)
- Test: `tests/test_culture_agent.py`, `tests/server/test_cultures_plugin.py` (extend)

**Interfaces:**
- Produces, in `signals.py`:
  - `class CulturesEvent(pydantic.BaseModel)`, with fields:
    - `kind: Literal["context_injected","name_chosen","snapshot_processed"]`
    - `world_dir: str`
    - `data: dict = {}`
    - `changed: bool = False` (true when world files were written)
  - The signal `cultures.event`, registered at import.
  - `async def send_event(kind, world_dir: Path, data: dict, changed: bool = False) -> None`, which stores `str(world_dir)` in the event
- Produces, in `agents/culture/__init__.py`, `@register() class CultureAgent(CultureNamingMixin, CultureSnapshotMixin, Agent)`. Task 6 creates the mixins in `naming.py` and `snapshot.py` as stubs whose handlers (`on_before_name_character`, `on_after_persist_character`, `on_snapshot_after`) are async no-ops; Tasks 7–8 fill them.
  - Class attributes: `agent_type = "culture"`, `verbose_name = "Culture"`, `essential = False`.
  - `__init__(self, client=None, **kwargs)` sets `client`, `is_enabled=True`, `actions`, `rng = random.Random()` and `_pending: dict[str, CharacterCulture] = {}`. It must construct with no arguments, because `bootstrap_engine` calls it that way.
  - `enabled` / `has_toggle`: the HelpAgent pattern.
  - `init_actions()` returns `{"culture": AgentAction(enabled=True, container=True, label="Cultures", icon="mdi-account-group-outline", description=…, config=…)}`. Its config:
    - `context_budget`: number, value 400, min 100, max 1500, step 50, label "Context budget (tokens)"
    - `candidates`: number, value 20, min 5, max 50, step 1, label "Name candidates"
  - Properties `context_budget -> int` and `candidate_count -> int`, both through `resolve_config("culture", …)`.
  - `@dataclass LoadedWorld(store: WorldStore, world_dir: Path, cultures: dict[str, Culture], places: list[Place], glossary: list[GlossaryEntry])`
  - `load_world() -> LoadedWorld | None`: `None` when disabled, when there's no shared context, or on any load error (logged).
  - `scene_cultures(world: LoadedWorld) -> SceneCultures`: calls `resolve_scene_cultures` with `scene.world_state.location`, the keys of `scene.world_state.places`, `list(scene.characters)`, and `fallback_place_id=self.get_scene_state("current_place_id")`. Stores the matched place id back with `set_scene_states(current_place_id=…)`.
  - `recent_text(limit_messages: int = 6) -> str`: joins the `.message` of the last N `scene.history` messages of type narrator, character or context investigation.
  - `connect(scene)`: `super().connect(scene)`, then connect:
    - `agent.narrator.inject_instructions` and `agent.conversation.inject_instructions` → `on_inject_instructions`
    - `agent.creator.before_name_character` → `on_before_name_character` (Task 7)
    - `agent.director.character_management.after_persist_character` → `on_after_persist_character` (Task 7)
    - `world_state.snapshot.after` → `on_snapshot_after` (Task 8)
  - `on_inject_instructions(emission)`:
    - Characters: for a `ConversationAgentEmission`, just `[emission.character]`; for a narrator emission, `list(scene.characters)`.
    - Builds the section, appends `DynamicInstruction(title=SECTION_TITLE, content=section.text)` when the text is non-empty, and records the spares in scene state `offered_spares` (a dict keyed by lowercase text → `{"culture_id","generator_id"}`, at most 60 entries, oldest dropped).
    - Sends a `context_injected` event: `{"agent": "narrator"|"conversation", "text", "tokens", "spares": [...]}`.
- Modifies `CulturesPlugin`:
  - `connect()` connects `cultures.event` to `on_cultures_event`; `disconnect()` disconnects it.
  - `on_cultures_event(event)` acts only when `str(world_dir_for_scene(self.scene)) == event.world_dir`:
    - if `event.changed`, `await self._send_world(self._store())`
    - then `queue_put({"type":"cultures","action":event.kind,"data":event.data})`

- [ ] **Step 1: Write the failing tests.**
  - **Setup.** Use `MockScene` + `bootstrap_scene`. Give the scene a shared context in `tmp_path`, using plan 1's server-test pattern from `tests/server/test_cultures_plugin.py`. Import the Taelrik fixture with `apply_import`, write the Task 2 places, and set `scene.world_state.location = "The Quillister inn in Veldhaer"`.
  - **In `tests/test_culture_agent.py`:**
    - `test_agent_registered_and_defaults`: `instance.get_agent("culture")` exists; `context_budget == 400`; `candidate_count == 20`; `has_toggle is True`.
    - `test_narrator_emission_gets_section`: `await agent.on_inject_instructions(NarratorAgentEmission(agent=narrator))` appends one instruction titled `"Cultures and names"` whose content contains `"Veldhaer"` and `SPARE_NAMES_PREFIX`. Scene state `offered_spares` is non-empty.
    - `test_conversation_emission_uses_speaker_traits`: the speaker's description has "curses in Taelrik"; a `ConversationAgentEmission(agent=conv, actor=None, character=char, response="")` section contains a Taelrik curse original.
    - `test_hooks_noop_without_world`:
      - The scene has no shared context: the emission's `dynamic_instructions` stays empty, and `on_before_name_character` leaves `chosen_name is None`.
      - The same holds for a world with zero cultures.
      - The same holds for a `cultures/taelrik.json` overwritten with `"{"`. No exception is raised.
    - `test_disabled_agent_does_nothing`
    - `test_context_injected_event_sent`: `connect_recorder(async_signals.get("cultures.event"))` receives `kind == "context_injected"` with `tokens > 0`.
  - **In the plugin tests:**
    - `test_event_for_this_world_pushes_world_and_forwards`: sending `CulturesEvent(kind="snapshot_processed", world_dir=<this world>, data={"x":1}, changed=True)` queues a `world` message and then `{"action":"snapshot_processed","data":{"x":1}}`.
    - `test_event_for_other_world_ignored`
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/test_culture_agent.py tests/server/test_cultures_plugin.py -n0 -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the agent, the signals module, the mixin stubs, the plugin forwarding and core edit 4.
- [ ] **Step 4: Run** the same command, then `guix shell -m manifest.scm -- uv run --no-sync pytest tests/test_agents_base.py tests/test_instance.py tests/test_global_state_isolation.py -n0`. Expected: all pass. The agent-sweep tests there iterate over every registered agent.
- [ ] **Step 5: Commit**: `git commit -m "feat(cultures): culture agent with prompt section"`

---

### Task 7: Naming a new character

**Files:**
- Create: `src/talemate/agents/culture/naming.py` (fill `CultureNamingMixin`), `src/talemate/prompts/templates/culture/pick-name.jinja2`
- Test: `tests/test_culture_naming.py`

**Interfaces:**
- Consumes: `CharacterNamingEmission` (Task 5), `PersistCharacterEmission` (director), `guess_culture`, `guess_culture_for_name`, `infer_gender`, `choose_generator`, `roll_candidates`, `match_candidate` (Task 3), `looks_like_name`, `mid_sentence_occurrence`, `first_mention` (Task 2), `send_event` (Task 6).
- Produces:
  - **`on_before_name_character(emission)`.** Runs only with a loaded world that has cultures.
    1. **Existing names.** `name = clean_name(emission.name)`. If `looks_like_name(name)` is true, or `name` occurs mid-sentence in any `scene.history` message, return without setting a name.
    2. **Culture.** `guess = guess_culture(cultures, sc, f"{emission.name} {emission.content} {emission.description}", self.rng)`. With no culture → return.
    3. **Generator.** `choose_generator(language, infer_gender(same text), self.rng)`. With none → return; the after-persist step records whatever name the creator picks.
    4. **Candidates.** `roll_candidates(…, count=self.candidate_count, exclude=glossary texts ∪ scene.all_character_names)`. If empty → return.
    5. **Pick.** `name, why, by_model = await self.pick_name(candidates, culture, emission)`.
    6. **Record.**
       - Set `emission.chosen_name = name`.
       - Append `DynamicInstruction(title="Culture", content=f"{name} is {culture.name}. {first sentence of culture.description} Their language, {language.name}, {first sentence of language.sound}")`.
       - Add the glossary entry: `kind="person"`, `language=culture.id`, `origin=GlossaryOrigin(by="ai", generator_id=gen.id, candidates=candidates)`, `character_name=name`, `first_used=f"{scene.title or scene.name}, character creation"`, unreviewed.
       - Set `_pending[name.lower()] = CharacterCulture(culture_id=culture.id, set_by="ai", unsure=guess.unsure, reason=guess.reason)`.
       - `await send_event("name_chosen", world_dir, {"name","culture_id","generator_id","candidates","by_model","why","ms"}, changed=True)`, where `ms` is the hook's wall time.
  - **`@set_processing async def pick_name(candidates, culture, emission) -> tuple[str, str, bool]`.**
    - Calls `Prompt.request("culture.pick-name", self.client, "analyze_freeform_medium_short", vars={…}, response_spec=ResponseSpec(extractors={"name": AnchorExtractor(left="<NAME>", right="</NAME>"), "why": AnchorExtractor(left="<WHY>", right="</WHY>")}))`.
    - Vars: `scene`, `max_tokens`, `candidates`, `culture`, `language`, `character_hint=emission.name`, `content`, `description`, `recent_text=self.recent_text(3)`.
    - Returns `(match_candidate(...), why, True)`. If there's no match, or the call raises a non-cancel exception, it returns `(candidates[0], "", False)`.
  - **`on_after_persist_character(emission)`.**
    - `c = emission.character`. If `c.culture` is set by the owner → return.
    - If `_pending` has `c.name.lower()` → pop it and set `c.culture`.
    - Otherwise, if `c.culture is None`:
      - `guess = guess_culture_for_name(...)`; set `c.culture = CharacterCulture(culture_id=guess.culture_id, set_by="ai", unsure=guess.unsure, reason=guess.reason)` when `guess.culture_id`.
      - If no glossary entry has this text, add one: `kind="person"`, `origin.by="ai_free"`, `language=guess.culture_id`, `doesnt_fit = guess.culture_id is not None and not fits(language, c.name)`, `character_name=c.name`, and `first_used` from `first_mention` (`"{story}, message {id}"`) or `"{story}, character creation"`.
    - Send `name_chosen` with `changed=True` when anything was written.
- **Template `pick-name.jinja2`.**
  - A `<|SECTION:TASK|>`: you name a new character in the culture `{{ culture.name }}`, whose language sounds like `{{ language.sound }}`. Give the character hint, content and description, and the last lines of the scene.
  - "Choose exactly one name from this list, spelled as given: {{ candidates|join(', ') }}."
  - "Answer with <NAME>name</NAME> and then <WHY>one short sentence</WHY>."
  - Close the section, then `{{ set_prepared_response("<NAME>") }}`.

- [ ] **Step 1: Write the failing tests.** Same setup as Task 6. Stub `Prompt.request` with `patch_prompt_request_in`.
  - `test_description_name_gets_generator_pick`: emission `name="the ferryman"`, `content="a gruff old man"`; the stub returns `("Tovrin", {"name": <a rolled candidate>, "why": "sounds old"})`.
    - `emission.chosen_name` is that candidate.
    - The glossary has one entry with `origin.by == "ai"`, `generator_id == "given_male"`, the text in `origin.candidates`, `len(origin.candidates) == 20`, and `status == "unreviewed"`.
    - `emission.dynamic_instructions[0].title == "Culture"`.
  - `test_existing_name_not_replaced`:
    - `name="Marigold"` → `chosen_name is None`, and no LLM call is made.
    - `name="the Rook"` with a scene message "…said the Rook." → also `None`.
  - `test_pick_off_list_uses_first_candidate`: the stub returns `{"name": "Bob"}` → `chosen_name == candidates[0]`. The `name_chosen` event has `by_model is False`.
  - `test_candidates_exclude_glossary_and_scene_names`: seed the glossary and scene characters with names the seeded rng would roll (roll once with the same seed to find them). None of them appears in `origin.candidates`.
  - `test_after_persist_sets_pending_culture`: after the hook picked "X", sending `PersistCharacterEmission(agent=director, character=Character(name="X"))` gives `character.culture.culture_id == "taelrik"`, `set_by == "ai"`.
  - `test_after_persist_existing_name_recorded_with_fit_flag`: `Character(name="Marigold")` gives a glossary entry with `language == "taelrik"`, `doesnt_fit is True`, `origin.by == "ai_free"`.
  - `test_owner_culture_kept_on_persist`: a character with an owner culture of elsiri keeps it, and no glossary entry is written.
  - `test_end_to_end_through_persist_character`:
    - `await director.persist_character(PersistCharacterRequest(name="the ferryman", content="a gruff old man", narrate_entry=False, assign_voice=False, generate_attributes=False))`, in split mode.
    - Queue stub responses for `culture.pick-name` and the creator's description and dialogue-instructions templates.
    - The created character's name is a Taelrik candidate, and `character.culture.culture_id == "taelrik"`.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/test_culture_naming.py -n0 -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the mixin and the template.
- [ ] **Step 4: Run** the same command, then `guix shell -m manifest.scm -- uv run --no-sync pytest tests/prompts/test_template_section_validation.py -n0`. Expected: PASS.
- [ ] **Step 5: Commit**: `git commit -m "feat(cultures): name new characters from their culture"`

---

### Task 8: After a snapshot: names, places, character cultures, additions

**Files:**
- Create: `src/talemate/cultures/detect.py`, `src/talemate/agents/culture/snapshot.py` (fill `CultureSnapshotMixin`), `src/talemate/prompts/templates/culture/infer-places.jinja2`, `src/talemate/prompts/templates/culture/find-additions.jinja2`
- Test: `tests/cultures/test_detect.py`, `tests/test_culture_snapshot.py`

**Interfaces:**
- Produces, in `detect.py` (pure):
  - `@dataclass NameFinding(text: str, kind: Literal["person","place","thing"], culture_id: str | None, doesnt_fit: bool, first_used: str, character_name: str | None, place_id: str | None, origin: GlossaryOrigin)`
  - `new_place_names(location: str | None, snapshot_places: list[str], places: list[Place], character_names: list[str]) -> list[str]`:
    - From `location`: runs of capitalised words (connectors allowed inside) that pass `looks_like_name`.
    - From `snapshot_places`: keys that pass `looks_like_name` after `clean_name`.
    - Minus existing place names and character names (case-insensitive), deduplicated, in first-seen order.
  - `find_new_names(*, characters: list[str], items: list[str], places_found: list[tuple[str, str]], glossary, cultures, scene: SceneCultures, scene_characters: dict[str, Character], messages: list, offered_spares: dict[str, dict], story: str) -> list[NameFinding]`.
    - `places_found` holds (name, place_id) pairs for this run's new and matched places.
    - **Persons:** snapshot character keys passing `looks_like_name`.
      - Culture: the character's own `culture.culture_id` if it's in the scene; otherwise `guess_culture_for_name`.
      - Origin: `ai` with that generator and the offered list if the lowercase text is in `offered_spares`; otherwise `ai_free`.
    - **Things:** item keys passing `is_proper_item_name` against the message texts. Culture: the dominant culture of `scene.mix`.
    - **Places:** `places_found` not already in the glossary. Culture: that place's dominant effective culture.
    - Every finding: skip it if its cleaned text is in the glossary (case-insensitive). Set `doesnt_fit = culture_id is not None and not fits(language, text)`. Take `first_used` from `first_mention`, as `"{story}, message {id}"`, or `story`.
  - `parse_places_reply(text: str, names: list[str], places: list[Place], cultures: dict[str, Culture], current_place: Place | None) -> list[Place]`:
    - Line format: `Name | kind | parent name or none | Culture share, Culture share or inherit | sure|unsure`.
    - Unknown kind → `"poi"` and unsure.
    - Unknown or missing parent → `current_place.id` and unsure.
    - Shares go through `set_shares`, then `model_copy(update={"set_by":"ai","unsure":…})`.
    - A name with no line → created under the current place, inheriting, unsure.
    - Every place gets `new_id()`. Lines for names not in `names` are ignored.
  - `parse_additions_reply(text: str, cultures_present: list[Culture], source: str, limit: int = 3) -> list[tuple[str, PlayAddition]]`:
    - Lines: `Culture | customs|food|holidays | text`. `NONE` or empty → `[]`.
    - Culture names are matched case-insensitively among those present.
    - Drops texts that, after normalising (lowercase, punctuation removed), equal or contain an existing custom, `food`, holiday name or addition text of that culture, or are contained in one.
    - Returns `(culture_id, PlayAddition(id=new_id(), section, text, source, status="unreviewed"))`.
- Produces, in `CultureSnapshotMixin`:
  - **`on_snapshot_after(emission)`.** With a loaded world, it runs these steps in this order:
    1. `sc = self.scene_cultures(world)`.
    2. **Places.** If cultures exist and `new_place_names(...)` is non-empty, run one `infer_places(names, world, sc)`. Append the result to places and save.
    3. **Names.** Run `find_new_names(...)` with `places_found` = this run's new places plus the matched current place, if not yet in the glossary. Append the findings as `GlossaryEntry` (unreviewed) and save.
    4. **Character cultures.** For each `scene.characters` without a culture: run `guess_culture_for_name`, and set an AI culture when the guess has a `culture_id`.
    5. **Additions.**
       - Run only if `sc.cultures` is non-empty and some `scene.history` message has an id greater than scene state `additions_checked_id` (default -1).
       - `find_additions(world, sc, text of those messages, last 8)` → append to each culture's `additions`, and `save_culture`.
       - Set `additions_checked_id` to the newest message id.
    6. **Event.** Always `send_event("snapshot_processed", world_dir, {"place": sc.place.name|None, "new_places": [...], "new_names": [{"text","kind","culture_id","doesnt_fit","origin"}], "cultures_set": [{"name","culture_id","unsure"}], "additions": [{"culture_id","section","text"}], "ms": int}, changed=<anything written>)`.
  - `@set_processing async def infer_places(names, world, sc) -> list[Place]`: calls `Prompt.request("culture.infer-places", self.client, "analyze_freeform", vars={known places as "name (kind, in parent)", cultures with their places, current place, names, recent_text}, response_spec=… AnchorExtractor("<PLACES>","</PLACES>"))`, then `parse_places_reply`. On a non-cancel error it returns places parsed from `""` (all unsure).
  - `@set_processing async def find_additions(world, sc, text) -> list[tuple[str, PlayAddition]]`: calls the template `culture.find-additions`, kind `"analyze_freeform"`, with the `<ADDITIONS>` anchor. Vars: present cultures with their customs, food and holiday names; the text. On error it returns `[]`.
- **Templates.**
  - Both state the exact line format, end with a close section, and prepare `<PLACES>` / `<ADDITIONS>`.
  - `find-additions` says: "Only facts that are new and lasting about how a whole culture lives (a custom, a dish, a holiday). Not one person's habits, not events. If none, answer NONE."

- [ ] **Step 1: Write the failing tests.**
  - **In `tests/cultures/test_detect.py`:**
    - `test_new_place_names`: location `"Kesterholm, a fishing hamlet on the Birch Coast"` with birch known → `["Kesterholm"]`. Snapshot keys `["the docks","Kesterholm"]` add nothing more.
    - `test_snapshot_skips_descriptions_and_normalizes`:
      - characters `["the old ferryman","Brannoch.","Tovrin's"]` → persons `{"Brannoch","Tovrin"}`
      - items `["a rusty lantern","Lantern","Grey Gull"]`, with the message "They tied up beside the Grey Gull." → things `{"Grey Gull"}`
    - `test_spare_name_gets_generator_origin`: `offered_spares={"kethvar":{"culture_id":"taelrik","generator_id":"given_male"}}` → `origin.by == "ai"`, `generator_id == "given_male"`.
    - `test_known_names_skipped_case_insensitive`
    - `test_doesnt_fit_flag`: "Marigold" at veldhaer → `culture_id == "taelrik"`, `doesnt_fit is True`.
    - `test_parse_places_reply`:
      - `"Kesterholm | village | Birch Coast | inherit | sure"` gives parent birch, `cultures == []`, `set_by == "ai"`, `unsure is False`.
      - `"Kesterholm | castle | Nowhere | Elsiri 70, Taelrik 30 | sure"` gives kind `poi`, parent = current place, shares 70/30, `unsure is True`.
      - an empty reply gives one unsure place
    - `test_parse_additions_reply_dedupes`: a line repeating an existing custom is dropped. `"Taelrik | customs | Ferrymen spit over the rail before landing."` is kept, as section customs. `"NONE"` gives `[]`.
  - **In `tests/test_culture_snapshot.py`.** Use the Task 6 setup. Seed `scene.history` with `NarratorMessage` texts, and drive the handler with `WorldStateSnapshotEmission(agent=world_state, world_state=scene.world_state)`.
    - `test_snapshot_adds_names_places_and_event`:
      - location "Kesterholm, on the Birch Coast"; snapshot characters `{"Brannoch":…}`, items `{"Grey Gull":…}`
      - stub `culture.infer-places` → `"Kesterholm | village | Birch Coast | inherit | sure"`; stub `culture.find-additions` → `"NONE"`
      - result: places.json has Kesterholm under birch with `set_by == "ai"`; the glossary has Brannoch (person), Grey Gull (thing) and Kesterholm (place, with `place_id`); one `snapshot_processed` event with `changed is True`
    - `test_no_place_call_without_new_places`: only names → no `culture.infer-places` call is recorded.
    - `test_additions_once_per_new_messages`:
      - The first run with a culture present calls `culture.find-additions` and stores the addition as unreviewed.
      - A second run with no new messages makes no call.
      - A run in a world with no cultures makes no call.
    - `test_owner_culture_never_overwritten`: a scene character has an owner culture of elsiri, and a place is owner-set. After a snapshot, both are unchanged, and the place's `cultures` are equal to before.
    - `test_scene_characters_without_culture_get_ai_guess`
    - `test_handler_errors_are_swallowed`: make `WorldStore.save_glossary` raise `OSError`; the handler returns without raising.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/cultures/test_detect.py tests/test_culture_snapshot.py -n0 -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `detect.py`, the mixin and the two templates.
- [ ] **Step 4: Run** the same command plus `tests/prompts/test_template_section_validation.py`. Expected: PASS.
- [ ] **Step 5: Commit**: `git commit -m "feat(cultures): post-snapshot names, places and additions"`

---

### Task 9: Review in the Cultures tab (backend, frontend, browser tests)

**Files:**
- Modify: `src/talemate/server/cultures.py`; `tests/e2e/seed.py`; `tests/e2e/cultures/_ui.py` and `tests/e2e/cultures/test_editing.py` (move `_add_addition` into `_ui.py`); in `talemate_frontend/src/components/cultures/`: `WorldStateManagerCultures.vue`, `WorldStateManagerMenuCulturesTools.vue`, `GlossaryDetail.vue`, `GlossaryView.vue`, `CultureOverview.vue`
- Create: `talemate_frontend/src/components/cultures/PeopleView.vue`, `tests/e2e/cultures/test_ai_review.py`
- Test: `tests/server/test_cultures_plugin.py` (extend), `tests/e2e/test_fixtures.py` (extend)

**Interfaces:**
- **The plugin.**
  - `_send_world` adds `data["characters"] = [{"name","is_player","active","shared","culture": dump|None}]`, one per `scene.character_data`, sorted by name.
  - It adds `counts["unsure_characters"]`: AI-set cultures with `unsure`.
  - It adds `unsure_characters` to `counts["unreviewed_total"]`.
  - New handlers:
    - `handle_set_character_culture({"character_name", "culture_id": str|None})` sets `CharacterCulture(culture_id, set_by="owner", unsure=False)`.
    - `handle_review_character_culture({"character_name"})` sets `unsure=False` and keeps `set_by`.
    - Both reply `world`, then `signal_operation_done()`. An unknown name → `signal_operation_failed`.
- **The seed** (`tests/e2e/seed.py`):
  - `seed_world(root, project="e2e-world", context="world", *, intro: str = "", location: str | None = None, messages: list[dict] = (), characters: list[dict] = ())`.
    - `messages` items are `{"text": str}`, appended as `NarratorMessage(message=text)` to `scene.history`.
    - `characters` items are `{"name", "description"="", "culture": dict|None, "active": bool=True, "shared": bool=False}`.
    - Active characters are added the way `tests/_director_test_helpers.add_character_to_scene` does, with `commit_to_memory=False`. Inactive ones go only in `scene.character_data`.
  - `place_places(world, places: list[dict]) -> None`: `WorldStore.save_places` of validated `Place`s.
  - `place_glossary(world, entries: list[dict]) -> None`
  - `send_backend(page, payload: dict) -> None`: sends on the page's backend socket (the `_BACKEND_SOCKET_JS` used by `open_scene`).
- **The frontend.**
  - **`PeopleView`.**
    - Props: `characters`, `cultures`, `send`.
    - A table: Name, Culture (a `v-select` of the cultures plus "No culture"), "Who set it" (`Worked out by the AI · {reason}` / `Set by you · the AI won't change it`), and an amber dot plus **Looks right** when AI-set and unsure.
    - Changing the select sends `set_character_culture`; Looks right sends `review_character_culture`.
    - The drawer gets an item **People** under "Where they live", with a badge of `counts.unsure_characters`. `WorldStateManagerCultures` handles `selected.type === "people"`.
  - **`GlossaryDetail`.**
    - When `doesnt_fit`, show a tonal warning alert: "Doesn't fit {language name}: it doesn't follow the language's sound rules."
    - The `ai_free` origin copy, when a language is set: "Not picked from a generator. It was already in the story, or was typed in." The existing copy stays for no language.
    - `GlossaryView` rows show `mdi-alert-outline` (`color="warning"`, size x-small) next to the name when `doesnt_fit`.
  - **`CultureOverview` (fixes plan 1's known gap).**
    - Keep `additionBase: {[id]: text}`, the last server text per addition.
    - Watch `culture.additions` (deep). For each addition:
      - if `additionEdits[id]` is undefined, or equals `additionBase[id]` (untouched), set it to the new text
      - always update `additionBase[id]`
    - Delete the ids that are gone.
    - `onLocalReset` keeps its current behaviour.

- [ ] **Step 1: Write the failing backend tests** (plugin):
  - `test_world_lists_characters_and_unsure_count`: a scene character with `CharacterCulture(culture_id="taelrik", unsure=True)` → `characters[0]["culture"]["culture_id"] == "taelrik"`, `counts["unsure_characters"] == 1`, and `unreviewed_total` includes it.
  - `test_set_character_culture_marks_owner`
  - `test_review_character_culture_clears_unsure`
  - `test_set_character_culture_unknown_name_fails`
- [ ] **Step 2: Write the failing seed tests** in `tests/e2e/test_fixtures.py`. These run in the e2e group:
  - `test_seed_world_with_messages_location_and_characters`: the saved scene JSON has the message text in its history, `world_state.location` set, the character in `character_data` with its culture, and the active character's name in `active_characters`.
  - `test_place_places_and_glossary`
- [ ] **Step 3: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/server/test_cultures_plugin.py -n0 -v`. Expected: the new tests FAIL.
- [ ] **Step 4: Implement** the plugin, the seed helpers and the frontend changes.
- [ ] **Step 5: Write the browser tests** in `tests/e2e/cultures/test_ai_review.py`:
  - `test_people_view_review_and_change`:
    - Seed Taelrik and the character Kethrun with an unsure AI culture.
    - The People item shows badge 1, and the row shows the amber dot.
    - **Looks right** removes the dot, and the badge disappears.
    - Choosing "No culture" shows "Set by you".
  - `test_doesnt_fit_flag_shown`: seed a glossary entry `{"text":"Marigold","language":"taelrik","kind":"person","doesnt_fit":true,"origin":{"by":"ai_free"}}`. Its detail shows "Doesn't fit Taelrik" and the "Not picked from a generator" copy.
  - `test_addition_arriving_while_editing`:
    - Seed one addition A, and type "half-typed" into A's box without leaving it.
    - Write addition B into the culture file on disk (the `_add_addition` helper from `test_editing.py`; move it to `_ui.py` and import it in both places).
    - Then `send_backend(page, {"type":"cultures","action":"get_world"})`.
    - A's box still reads "half-typed", and B's box shows B's text.
- [ ] **Step 6: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/server/test_cultures_plugin.py -n0 -v`, then `guix shell -m manifest.scm -- sh -c 'cd talemate_frontend && npx --yes corepack@0.34.0 pnpm run build'`, then `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e -m e2e -n0 -v`. Expected: all pass, the build succeeds, and the existing e2e tests stay green.
- [ ] **Step 7: Commit**: `git commit -m "feat(cultures): review AI cultures and flags in the Cultures tab"`

---

### Task 10: AI test driver and AI world fixtures

**Files:**
- Create: `scripts/dev/talemate_ws.py`, `tests/dev/test_talemate_ws.py`, `tests/ai/data/taelrik.culture.json`, `tests/ai/data/elsiri.culture.json`, `tests/ai/cultures/__init__.py`, `tests/ai/cultures/scenarios.py`, `tests/cultures/test_ai_fixtures.py`

**Interfaces:**
- Produces, in `scripts/dev/talemate_ws.py`, `class BackendSession`. It is a context manager over `websockets.sync.client.connect(ws_url, max_size=None)`. Every received message is appended to `self.messages`.
  - `send(payload: dict) -> None`
  - `wait_for(predicate: Callable[[dict], bool], timeout: float) -> dict`: reads until the predicate holds, otherwise raises `TimeoutError`, naming the last 10 message types.
  - `load_scene(path: Path, timeout: float = 180) -> None`: sends `{"type":"load_scene","file_path":str(path)}` and waits for `{"type":"system","id":"scene.loaded"}`.
  - `persist_character(name: str, content: str = "", timeout: float = 600, **fields) -> None`:
    - sends `{"type":"director","action":"persist_character","name":name,"content":content,"narrate_entry":False,**fields}`
    - waits for `{"type":"director","action":"character_persisted"}`
    - raises `RuntimeError` on a `director` `operation_done` carrying an `error`
  - `narrate(action: Literal["narrate_environment","progress"] = "narrate_environment", direction: str = "", timeout: float = 600) -> str`: sends `{"type":"narrator","action":action,"narrative_direction":direction}` and returns the next `narrator` message's `message`.
  - `request_snapshot(timeout: float = 600) -> dict`: sends `{"type":"world_state_agent","action":"request_update"}` and returns the `data` of the next `{"type":"cultures","action":"snapshot_processed"}`.
  - `get_world(timeout: float = 30) -> dict`: sends `cultures.get_world` and returns the next `world` data.
  - `prompts(agent_type: str | None = None, start: int = 0) -> list[dict]`: the `prompt_sent` data from index `start` of `self.messages`.
  - `events(kind: str, start: int = 0) -> list[dict]`: `cultures` messages with `action == kind`.
- **AI fixtures.**
  - `tests/ai/data/taelrik.culture.json`: plan 1's fixture plus a generator `given_female` ("Given names (female)").
  - `tests/ai/data/elsiri.culture.json`:
    - a `naming`-level Elsiri culture, colour `#4FC3F7`, a short description and sound, 3 customs
    - generators `given_female`, `given_male`, `place_names`, with sounds clearly unlike Taelrik's (soft liquids and long vowels, no `kh`/`dh`/`th`)
    - 2 glossary entries: Ilsara, Saelin
- **`tests/ai/cultures/scenarios.py`.**
  - `PLACES`: a list of `Place` dicts with fixed ids:
    - `reach`: The Taelrik Reach, country, taelrik 100
    - `veldhaer`: town, under reach, inherits
    - `dhunmouth`: city, under reach, taelrik 60 / elsiri 40
    - `birch`: Birch Coast, region, under reach, elsiri 90 / taelrik 10
    - `ilsara`: village, under birch, inherits
  - `@dataclass Scenario(key, place_id, intro, location, expected: dict[str,int])`, and `SCENARIOS`:
    - `taelrik_town`: veldhaer, location "The Quillister inn in Veldhaer", expected `{"taelrik":100}`
    - `elsiri_pocket`: ilsara, location "The fish market in Ilsara, on the Birch Coast", expected `{"elsiri":90,"taelrik":10}`
    - `mixed_city`: dhunmouth, location "The harbour of Dhunmouth", expected `{"taelrik":60,"elsiri":40}`
  - `NPC_ROLES`: 10 `(hint, content)` pairs, alternating female and male. For example `("the fishwife", "A loud woman selling eels from a barrow.")` and `("the ferryman", "A gruff old man who works the river ferry.")`. No role names a culture.
  - `TRAIT_CHARACTER = {"name": "Hadrik", "description": "A broad-shouldered dockhand. He curses in Taelrik whenever something goes wrong.", "culture": {"culture_id": "taelrik", "set_by": "owner"}}`
  - `KNOWN_NAMES_MESSAGE = "Old Brannoch waved from the deck of the Grey Gull, a battered river barge."`
  - `ADDITION_MESSAGE = "As every Taelrik ferryman does, Brannoch spat over the rail before landing."`
  - `seed_scenario(root: Path, project: str, scenario: Scenario, *, with_trait_character: bool = False, messages: list[str] = ()) -> SeededWorld`: calls `seed_world` (Task 9) with the intro, location, messages and characters; `place_culture` for both AI fixtures; `place_places(PLACES)`.

- [ ] **Step 1: Write the failing tests.**
  - **In `tests/dev/test_talemate_ws.py`.** Start a local `websockets.sync.server.serve` stub on a free port, in a thread. It answers scripted messages per received `type`/`action`. No network.
    - `test_load_scene_waits_for_loaded`
    - `test_persist_character_raises_on_error`
    - `test_request_snapshot_returns_processed_data`
    - `test_wait_for_timeout_names_last_types`
    - `test_prompts_filter_by_agent`
  - **In `tests/cultures/test_ai_fixtures.py`:**
    - `test_ai_fixtures_validate`: both files pass `CultureFile.model_validate_json`.
    - `test_ai_fixtures_distinct`: 20 rolled Elsiri given names include at most 3 that `fits` Taelrik, and vice versa. Every generator rolls at least 10 names.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/dev/test_talemate_ws.py tests/cultures/test_ai_fixtures.py -n0 -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the driver, the fixtures and `scenarios.py`. Tune the Elsiri rules until the distinctness test passes, checking with `guix shell -m manifest.scm -- uv run --no-sync python -m talemate.cultures.cli sample tests/ai/data/elsiri.culture.json`.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit**: `git commit -m "test(cultures): AI driver and AI world fixtures"`

---

### Task 11: AI tests (opt-in, the controller runs them)

**Files:**
- Create: `tests/ai/cultures/conftest.py`, `tests/ai/cultures/test_naming_ai.py`, `tests/ai/cultures/test_context_ai.py`, `tests/ai/cultures/test_snapshot_ai.py`

**Interfaces:**
- Consumes: `ai_app` (`tests/ai/conftest.py`), `BackendSession`, `seed_scenario`, `SCENARIOS`, `fits`, `Culture`.
- `tests/ai/cultures/conftest.py` provides a function-scoped `session(ai_app)`: a `BackendSession(ai_app.backend_ws_url)`, closed after the test. It also provides `load_cultures(world) -> dict[str, Culture]`, which reads the world folder with `WorldStore`. Every test uses its own project name, so tests never share a world.

The tests check outcomes, not wording.
- `test_naming_ai.py`:
  - `test_new_npc_in_taelrik_town_gets_fitting_name`:
    - Seed `taelrik_town`, load the scene, then `persist_character("the ferryman", "A gruff old man who works the river ferry.")`.
    - The world's glossary has exactly one new person entry with `language == "taelrik"`, `status == "unreviewed"`, `origin.by == "ai"`, `origin.generator_id == "given_male"`, `len(origin.candidates) >= 10`, and its text in `origin.candidates`.
    - `fits(taelrik.language, text)`.
    - `get_world()["characters"]` has that name with `culture.culture_id == "taelrik"`.
  - `test_npc_in_elsiri_pocket_named_from_its_culture`: in `elsiri_pocket`, `"the fishwife"` gets a glossary entry whose `language` is `elsiri` or `taelrik`, with `generator_id == "given_female"` and `fits` true for that language.
  - `test_typed_name_is_kept`: `persist_character("Marigold", "A halfling baker.")` creates a character named exactly "Marigold". Its glossary entry has `origin.by == "ai_free"` and `doesnt_fit is True`.
- `test_context_ai.py`:
  - `test_narrator_prompt_contains_culture_section`:
    - Seed `taelrik_town` with the trait character, then `narrate()`.
    - At least one `context_injected` event with `agent == "narrator"`, whose text contains "Veldhaer".
    - The next `prompts("narrator")` entry's `prompt` contains `SPARE_NAMES_PREFIX` and each of that event's spare names.
- `test_snapshot_ai.py`:
  - `test_snapshot_adds_new_names`: seed `taelrik_town` with `messages=[KNOWN_NAMES_MESSAGE]`, then `request_snapshot()`. The glossary contains "Brannoch" (any case, kind person) and an entry for "Grey Gull" (kind thing).
  - `test_snapshot_creates_unknown_place`:
    - Seed `elsiri_pocket`, but with location "Kesterholm, a fishing hamlet on the Birch Coast" and a message describing arriving at Kesterholm.
    - After `request_snapshot()`, places.json holds "Kesterholm" with `set_by == "ai"` and `parent_id` in `{"birch","ilsara"}`.
  - `test_snapshot_records_culture_addition`: seed `taelrik_town` with `messages=[ADDITION_MESSAGE]`. After `request_snapshot()`, culture `taelrik` has at least one unreviewed addition with `section == "customs"`.

- [ ] **Step 1: Write the tests.**
- [ ] **Step 2: Verify they skip without opt-in.** Run `guix shell -m manifest.scm -- uv run --no-sync pytest tests/ai -m ai -n0 -v`. Expected: every test is SKIPPED with "AI tests need TALEMATE_AI_TESTS=1". Also run `guix shell -m manifest.scm -- uv run --no-sync pytest --collect-only -q tests/ai`, which must collect with no errors. Don't set `TALEMATE_AI_TESTS`.
- [ ] **Step 3: Commit**: `git commit -m "test(cultures): opt-in AI tests for naming, context and snapshots"`
- [ ] **Step 4: (Controller only, pre-approved for this run.)**
  - Fetch the model name with `guix shell -m manifest.scm -- uv run --no-sync python -c "import sys; sys.path.insert(0,'scripts/dev'); import ai_helpers; print(ai_helpers.koboldcpp_model(ai_helpers.koboldcpp_url()))"`.
  - Then run `TALEMATE_AI_TESTS=1 guix shell -m manifest.scm -- uv run --no-sync pytest tests/ai -m ai -n0 -v`.
  - Expected: all pass. If a test fails because of the model's output rather than the code (e.g. the snapshot never extracted "Grey Gull"), record it with the model name from `.test-artifacts/<stamp>/model.txt` and treat it as an evaluation finding, not a bug. Fix real bugs and re-run.

---

### Task 12: Overnight AI evaluation script

**Files:**
- Create: `scripts/dev/eval_cultures_ai.py`, `scripts/dev/cultures_eval_metrics.py`, `tests/dev/test_cultures_eval_metrics.py`
- Modify: `docs/dev/local-testing.md` (a short "Cultures AI evaluation" section with the command below)

**Interfaces:**
- Consumes: `talemate_app.start/stop`, `BackendSession`, `scenarios.py` (imported after `sys.path.insert(0, str(REPO_ROOT / "tests"))`), `talemate.cultures.generator.fits`, `talemate.util.count_tokens`, `ai_helpers.koboldcpp_model`.
- Produces, in `cultures_eval_metrics.py` (pure functions, with unit tests):
  - `share_from_generator(npcs: list[dict]) -> float`: the share of NPCs whose glossary entry has `origin.by == "ai"` and whose `generator_id` belongs to the NPC's assigned culture.
  - `share_fitting(npcs) -> float`: the share whose name `fits` its assigned culture's language.
  - `culture_distance(observed: dict[str,int], expected: dict[str,int]) -> float`: total variation distance between the observed culture counts (normalised) and the expected shares. 0 is perfect.
  - `narration_name_use(prompt: str, response: str, spares: list[str], language) -> dict`: returns `{"used_spare": bool, "new_names": [...], "invented_fit": int, "invented_misfit": int}`. New names are capitalised mid-sentence words (`mid_sentence_occurrence`) in the response that are absent from the prompt and not in `COMMON_WORDS`. A spare counts as used when it occurs whole-word in the response.
  - `verbatim_phrases(response: str, phrases: list[str]) -> int`: counts phrases found after normalising quotes, apostrophes and case.
  - `summarise(results: dict) -> dict`, plus `render_markdown(summary: dict, model: str) -> str`.
- **The script.** Run it as `TALEMATE_AI_TESTS=1 guix shell -m manifest.scm -- uv run --no-sync python scripts/dev/eval_cultures_ai.py [--runs 3] [--npcs 5] [--narrations 3] [--out DIR]`.
  - Its default `--out` is `.test-artifacts/cultures-eval-<YYYYmmdd-HHMMSS>/`.
  - **Startup:** one `talemate_app.start(ai=True)`. It writes `model.txt`, refuses to run if the model probe returns `None`, and always calls `stop` in `finally`.
  - **Per run and scenario:**
    1. `seed_scenario(...)` with a fresh project `eval-<scenario>-<run>`, the trait character, and `messages=[KNOWN_NAMES_MESSAGE, ADDITION_MESSAGE]`.
    2. Load the scene, then for K roles from `NPC_ROLES`, `persist_character`. Record, per NPC:
       - the resulting `name_chosen` event data (name, culture, generator, candidates, `by_model`, hook `ms`)
       - the wall time of the whole `persist_character`
       - the summed `time` of `prompts("culture")` within that window
       - the glossary entry
    3. M times `narrate("progress", "Hadrik drops a crate on his foot.")`. Each odd-numbered one uses `narrate("narrate_environment")` instead. Record the `context_injected` event, the matching narrator prompt (`prompt_tokens`, `prompt`) and the response.
    4. `request_snapshot()` twice. Record the `snapshot_processed` data and its `ms`.
  - **Report metrics,** in `report.json` and `report.md`, per scenario and overall:
    - share of AI-named NPCs from the right culture's generator (`share_from_generator`)
    - share that fit their culture (`share_fitting`)
    - culture-guess distance against the place mix (`culture_distance`), plus the raw counts
    - narrator spare-name use: narrations with a new name, using a spare, inventing a fitting name, inventing a misfit
    - curse or saying verbatim rate: responses containing at least one of Hadrik's Taelrik curses ÷ responses where Hadrik was present
    - culture section size: mean and max `tokens`, and mean `tokens / prompt_tokens`
    - latency added per creation: mean and p90 of the culture prompt seconds, and mean hook `ms`; also the mean `persist_character` wall time
    - snapshot glossary yield:
      - the new names per snapshot
      - the share correctly attributed (a person's language equals its character's culture, otherwise `not doesnt_fit`)
      - the recall of the seeded "Brannoch" and "Grey Gull"
      - the snapshot culture `ms`
  - **Robustness:** a failed scenario step is logged into `report.json["errors"]`, and the run continues.

- [ ] **Step 1: Write the failing metric tests** in `tests/dev/test_cultures_eval_metrics.py`:
  - `test_culture_distance`: `({"taelrik":9,"elsiri":1}, {"elsiri":90,"taelrik":10})` gives `0.8`; identical shares give `0.0`.
  - `test_narration_name_use`: spares `["Kethvar"]`; the response "Kethvar the smith waved to Zorblax." with "Zorblax" absent from the prompt gives `used_spare=True` and `new_names == ["Zorblax"]` (`"Kethvar"` is a spare, so it's not new).
  - `test_verbatim_phrases_normalises_quotes`: `"Rhok tal’dun!"` matches `"Rhok tal'dun!"`.
  - `test_share_from_generator_and_fitting`
  - `test_render_markdown_has_all_metric_headings`: the eight headings from the list above are present.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/dev/test_cultures_eval_metrics.py -n0 -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the metrics module, the script (argparse, with `--help`) and the docs section.
- [ ] **Step 4: Run** the same command, then `guix shell -m manifest.scm -- uv run --no-sync python scripts/dev/eval_cultures_ai.py --help`. Expected: tests PASS, and the help prints. Without `TALEMATE_AI_TESTS=1`, the script exits non-zero with talemate_app's "AI runs need TALEMATE_AI_TESTS=1 — ask the owner first".
- [ ] **Step 5: Commit**: `git commit -m "feat(dev): overnight cultures AI evaluation script"`
- [ ] **Step 6: (Controller only, overnight.)** Run `TALEMATE_AI_TESTS=1 guix shell -m manifest.scm -- uv run --no-sync python scripts/dev/eval_cultures_ai.py --runs 3 --npcs 5 --narrations 3`. Report the `report.md` numbers and the model name to the owner.

---

### Task 13: Whole-branch check

- [ ] **Step 1:** Run `guix shell -m manifest.scm -- uv run --no-sync pytest`. Expected: no new failures beyond the 141 known `punkt_tab` ones.
- [ ] **Step 2:** Run `guix shell -m manifest.scm -- uv run --no-sync ruff check` and `… ruff format --check`, both on `src/talemate/cultures src/talemate/agents/culture src/talemate/server/cultures.py src/talemate/character.py src/talemate/agents/creator/character.py src/talemate/agents/world_state/snapshot.py scripts/dev tests/cultures tests/ai tests/dev tests/e2e tests/test_culture_*.py`. Expected: clean.
- [ ] **Step 3:** Run the frontend build and then the browser group, using the commands in Environment. Expected: success.
- [ ] **Step 4:** Check the core-edit list with `git diff main --stat -- src/talemate ':!src/talemate/cultures' ':!src/talemate/agents/culture' ':!src/talemate/prompts/templates/culture' ':!src/talemate/server/cultures.py'`. Expected: exactly `character.py`, `agents/__init__.py`, `agents/creator/character.py` and `agents/world_state/snapshot.py`.
- [ ] **Step 5:** Update the "Known gaps" list in `docs/superpowers/plans/2026-10-17-cultures-foundation-followups.md`:
  - mark the addition-editing gap as fixed (Task 9)
  - add any gap found while building this plan
- [ ] **Step 6: Commit**: `git commit -m "chore(cultures): plan 2 branch check"`
