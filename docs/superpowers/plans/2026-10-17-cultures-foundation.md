# Cultures Foundation Implementation Plan (plan 1 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data and editing side of the culture system. The owner designs a culture with a Claude Code skill, imports it, and can browse and edit its culture, language, glossary and places in a new World Editor **Cultures** tab.

**Architecture:**
- **Backend.** A self-contained package, `src/talemate/cultures/`, holds:
  - pydantic models
  - a rule-based name generator
  - file storage in a folder next to the Shared World context file
  - place-mix resolution
  - import/export with a JSON schema
- **Server.** One websocket plugin (router `cultures`) exposes the package to the frontend.
- **Frontend.** New Vue components under `talemate_frontend/src/components/cultures/`, plus a drawer tools component, wired into the World Editor the same way the existing tabs are.
- **Not in this plan.** No LLM calls and no agent; the AI side is plan 2.

**Tech Stack:** Python 3 + pydantic 2 + pytest (pytest-asyncio, `asyncio_mode=auto`), run through `uv`; Vue 3 + Vuetify 3 (vite build); a Claude Code skill (Markdown).

**Spec:** `docs/superpowers/specs/2026-10-17-cultures-and-languages-design.md`. Read sections 5, 6.1 and 9 before starting. The mockup linked in its header is the visual reference for every frontend task.

**The four plans:**
1. *Foundation* (this plan)
2. *AI use*: Culture agent, context injection, naming hook, snapshot → glossary, character culture field, play additions
3. *In the story*: highlights, bubbles, review markers, app-level badge
4. *Rename everywhere*

Each plan ships working software on its own.

**Prerequisite:** `uv` and `node`/`npm` must be on PATH. The dev machine currently has neither; install them or use the project's usual environment before Task 1. The test command is `uv run pytest`. The frontend check is `cd talemate_frontend && npm run build`.

## Global Constraints

- **Self-contained.** New code lives in new files. The only edits to existing files are:
  - `src/talemate/server/websocket_server.py` (one route)
  - `talemate_frontend/src/components/WorldStateManager.vue` (tab, window item, tool ref, tab-count badge)
  - `talemate_frontend/src/components/WorldStateManagerMenu.vue` (one drawer branch)
- **Storage location.** World data lives in `scenes/<project>/shared-context/<context-name>.world/`, where `<context-name>` is the shared context file name without `.json`. Inside it:
  - `cultures/<culture-id>.json`: one culture plus its language
  - `places.json`
  - `glossary.json`
- **No shared world.** A scene with no shared context has no cultures. The plugin answers `available: false`, and the tab shows a prompt to link or create a Shared World.
- **Safe writes.** Every write goes to a temp file in the same directory, then `os.replace` moves it into place. Writes happen immediately on each edit, not on scene save.
- **Generators are rule-based** (Lexifer/Vulgarlang style), never Markov chains. One roll returns 20 candidates by default.
- **Three language levels**, with exactly these values: `description`, `naming`, `full`.
- **Places are keyed by a stable id**, never by name. A place's cultures are an optional list of `(culture_id, share)` pairs whose shares sum to 100. A place with none takes its parent's (nearest ancestor with cultures).
- **Place kinds**, exactly: `country`, `region`, `city`, `town`, `village`, `building`, `poi`, `terrain`.
- **Glossary entry kinds**: `person`, `place`, `thing`, `word`. Status: `unreviewed` / `reviewed`. Origin `by`: `ai`, `ai_free`, `import`, `owner`.
- **Re-import rules:**
  - It replaces a culture's and language's core sections.
  - It never deletes glossary entries, places or play additions that exist only in Talemate.
  - For a glossary entry present in both, Talemate's copy wins if it is `reviewed` or was edited by the owner.
  - Play additions stay a separate tagged list for good, even after Keep.
- **Law & governance** is not a culture field. Countries only show a "later" placeholder.
- **UI copy** uses the owner's words from the mockup: "Cultures", "Import culture", "Places & regions", "Unassigned names", "Not reviewed", "Looks right", "Pick another", "Re-import", "Roll". Colours come from the Vuetify theme in `talemate_frontend/src/plugins/vuetify.js`. Foreign words use `highlight7` (blue), names use `highlight5` (amber).

## Review Focus

These are the inputs most likely to break things for the owner even though no spec line names them. Each has a test in the task that owns the code.

1. **A hand-edited or older culture file with missing or unknown keys.** It must still load, using defaults for missing keys and ignoring extras, never crashing the tab. (Task 1: `test_culture_file_ignores_unknown_and_defaults_missing`)
2. **A generator whose reject rules or pattern can't produce enough distinct names.** It must return fewer candidates, not loop forever. (Task 2: `test_roll_terminates_when_space_is_small`)
3. **Two edits arriving at once, or a crash mid-write.** The data file must never end up truncated or half-written. (Task 3: `test_atomic_write_leaves_old_file_on_failure`)
4. **A place re-parented under its own descendant.** This must be refused, not create a loop that hangs mix resolution. (Task 4: `test_reparent_into_descendant_rejected`)
5. **Importing a file with the same name as an existing culture but a different id, or a name colliding with an unassigned glossary entry in different case.** Matching is case-insensitive, and the preview must say what will happen. (Task 5: `test_preview_matches_unassigned_case_insensitive`, `test_preview_flags_name_clash_with_other_id`)

---

### Task 1: Data models

**Files:**
- Create: `src/talemate/cultures/__init__.py`, `src/talemate/cultures/models.py`
- Test: `tests/cultures/__init__.py`, `tests/cultures/test_models.py`

**Interfaces:**
- Produces (all pydantic `BaseModel`, `model_config = ConfigDict(extra="ignore")`):
  - `GeneratorDef(id: str, name: str, use: Literal["people","places","things"], patterns: list[str], reject: list[str] = [], capitalize: bool = True, min_length: int = 2, max_length: int = 24)`
  - `Phrase(id: str, category: str, original: str, translation: str, breakdown: list[tuple[str, str]] = [], usage: str = "")`
  - `DictionaryEntry(word: str, meaning: str, part: str = "", notes: str = "")`
  - `Language`, with fields:
    - `name: str`
    - `level: Literal["description","naming","full"]`
    - `writable: bool = True`
    - `sound: str = ""`
    - `categories: dict[str, str] = {}`
    - `syllable_notes: list[str] = []`
    - `generators: list[GeneratorDef] = []`
    - `grammar: str = ""`
    - `dictionary: list[DictionaryEntry] = []`
    - `phrases: list[Phrase] = []`
  - `Holiday(name: str, when: str = "", description: str = "")`
  - `PlayAddition(id: str, section: Literal["customs","food","holidays"], text: str, source: str = "", status: Literal["unreviewed","reviewed"] = "unreviewed")`. Keep sets `reviewed`; Edit changes the text.
  - `Culture`, with fields:
    - `id: str`
    - `name: str`
    - `color: str = "#9E9E9E"`
    - `description: str = ""`
    - `language: Language`
    - `customs: list[str] = []`
    - `food: str = ""`
    - `holidays: list[Holiday] = []`
    - `additions: list[PlayAddition] = []`
    - `source_file: str = ""`
    - `imported_at: str = ""` (ISO date)
  - `CultureShare(culture_id: str, share: int)`
  - `Place`, with fields:
    - `id: str`
    - `name: str`
    - `kind: Literal["country","region","city","town","village","building","poi","terrain"] = "town"`
    - `parent_id: str | None = None`
    - `cultures: list[CultureShare] = []`
    - `world_entry_id: str | None = None`
    - `set_by: Literal["ai","owner"] = "owner"`
    - `unsure: bool = False`
    - `note: str = ""`
  - `GlossaryOrigin(by: Literal["ai","ai_free","import","owner"], generator_id: str | None = None, candidates: list[str] = [])`
  - `GlossaryEntry`, with fields:
    - `id: str`
    - `text: str`
    - `language: str | None` (culture id; `None` means unassigned)
    - `kind: Literal["person","place","thing","word"]`
    - `meaning: str = ""`
    - `renderings: dict[str, str] = {}` (culture id → rendering)
    - `true_name: str = ""` (description, for unwritable languages)
    - `origin: GlossaryOrigin`
    - `first_used: str = ""`
    - `status: Literal["unreviewed","reviewed"] = "unreviewed"`
    - `edited_by_owner: bool = False`
    - `character_name: str | None = None`
    - `place_id: str | None = None`
  - `PlacesFile(format_version: int = 1, places: list[Place] = [])`
  - `GlossaryFile(format_version: int = 1, entries: list[GlossaryEntry] = [])`
  - `new_id() -> str`, returning `uuid4().hex[:12]`
  - `slugify(name: str) -> str`: lowercase ASCII, with runs of non-alphanumerics turned into `-` and the ends stripped. `"Ghûn"` → `"ghun"`, using `unicodedata` NFKD.

- [ ] **Step 1: Write the failing tests** in `tests/cultures/test_models.py`:
  - `test_slugify_strips_diacritics`: `slugify("Ghûn") == "ghun"`, `slugify("Hollow Choir") == "hollow-choir"`.
  - `test_culture_file_ignores_unknown_and_defaults_missing`: `Culture.model_validate({"id":"t","name":"Taelrik","language":{"name":"Taelrik","level":"full"},"law":"x"})` succeeds; `.customs == []`, `.language.generators == []`, and there is no `law` attribute.
  - `test_level_rejects_unknown_value`: `Language(name="x", level="partial")` raises `ValidationError`.
  - `test_place_kind_values`: each of the 8 kinds validates, and `"castle"` raises.
- [ ] **Step 2: Run** `uv run pytest tests/cultures/test_models.py -n0 -v`. Expected: FAIL (`ModuleNotFoundError: talemate.cultures`).
- [ ] **Step 3: Implement** `models.py` exactly as in Interfaces. `__init__.py` re-exports the models.
- [ ] **Step 4: Run** the same command. Expected: 4 passed.
- [ ] **Step 5: Commit**: `git add src/talemate/cultures tests/cultures && git commit -m "feat(cultures): data models"`

---

### Task 2: Rule-based name generator and "fits" check

**Files:**
- Create: `src/talemate/cultures/generator.py`
- Test: `tests/cultures/test_generator.py`

**Interfaces:**
- Consumes: `Language`, `GeneratorDef` (Task 1).
- Produces:
  - `parse_categories(categories: dict[str, str]) -> dict[str, list[tuple[str, int]]]`
  - `roll(language: Language, generator_id: str, count: int = 20, rng: random.Random | None = None, exclude: set[str] = frozenset()) -> list[str]`
  - `fits(language: Language, name: str) -> bool`
  - `class GeneratorError(ValueError)`

**Rule syntax.** This syntax is the import format's, so document it in the module docstring; Task 7's skill copies it.
- **Categories:** single uppercase letters mapping to space-separated options. An option can carry a weight suffix `*n`, e.g. `{"C": "k kh t th dh r*2", "V": "a ae e o u i"}`. Options may be multi-letter.
- **Pattern tokens:**
  - an uppercase letter that is a defined category means one weighted pick from it
  - `(...)` is optional, included with 50% chance, and may nest
  - `[a|b|c]` is an equal-chance choice between sub-patterns
  - anything else is literal text, including lowercase letters, spaces, `'`, `-` and other uppercase letters that aren't categories
- **Pattern weight:** a pattern may end in `*n` to weight it among the generator's patterns.
- **Output:**
  - `reject` regexes (case-insensitive, `re.search`) drop matching results
  - `min_length` / `max_length` count letters only
  - `capitalize` uppercases the first letter of each space-separated word
  - results are unique, and none is in `exclude` (compared case-insensitively)
- **`fits`:**
  - Compile each pattern of every generator of the language into an anchored, case-insensitive regex: categories become alternations sorted longest first, `(...)` becomes `(?:...)?`, and `[a|b]` becomes `(?:a|b)`.
  - A name fits when, after lowercasing, every space-separated word fully matches at least one compiled pattern and no reject rule matches.
  - Languages with no generators return `True`, so they're never flagged.

- [ ] **Step 1: Write the failing tests.** Use a fixture language with `categories={"C":"k t r*3","V":"a e"}`, generator `g1` with patterns `["CV(C)"]` and `reject=["rr"]`.
  - `test_roll_is_deterministic_with_seed`: two `roll(..., rng=random.Random(1))` calls return the same list.
  - `test_roll_respects_pattern_shape`: every result matches `^[KTR][ae][ktr]?$` (capitalised), and none contains `rr`.
  - `test_roll_excludes_names`: with `exclude={"ka","Ta"}`, neither `"Ka"` nor `"Ta"` appears.
  - `test_roll_terminates_when_space_is_small`: generator `patterns=["Ca"]` with `categories={"C":"k t"}` and `count=20` returns exactly `{"Ka","Ta"}` as a set, within 1s. Cap attempts at `count * 50`.
  - `test_optional_and_choice_tokens`: pattern `"[ka|to](n)"` only produces values in `{"Ka","Kan","To","Ton"}`.
  - `test_fits_accepts_generated_and_rejects_foreign`: each rolled name `fits`; `fits(lang, "Xylophone") is False`; `fits(lang, "Karr") is False` (reject rule).
  - `test_fits_true_without_generators`: a `description`-level language returns `True` for anything.
  - `test_unknown_generator_raises`: `roll(lang, "nope")` raises `GeneratorError`.
- [ ] **Step 2: Run** `uv run pytest tests/cultures/test_generator.py -n0 -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement `generator.py`.** Write a small recursive-descent parser that turns a pattern string into a token tree (sequence / optional / choice / category / literal). The same tree serves `roll` (walk with `rng`) and `fits` (emit a regex). Cache compiled regexes per language with `functools.lru_cache` keyed on a JSON dump of the generators and categories.
- [ ] **Step 4: Run** the same command. Expected: 8 passed.
- [ ] **Step 5: Commit**: `git commit -am "feat(cultures): rule-based name generator"` (add the new files first).

---

### Task 3: World store (files next to the shared context)

**Files:**
- Create: `src/talemate/cultures/store.py`
- Test: `tests/cultures/test_store.py`

**Interfaces:**
- Consumes: the models from Task 1.
- Produces:
  - `world_dir_for(shared_context_path: str | Path) -> Path`: for `.../shared-context/world.json` it returns `.../shared-context/world.world/`.
  - `world_dir_for_scene(scene) -> Path | None`: returns `None` when `scene.shared_context` is `None`; otherwise `world_dir_for(scene.shared_context.filepath)`.
  - `atomic_write_json(path: Path, data: dict) -> None`
  - `class WorldStore`, constructed with `WorldStore(root: Path)`. Its methods:
    - `load_cultures() -> dict[str, Culture]`: skips unreadable files with a `structlog` warning
    - `save_culture(c: Culture)`
    - `delete_culture(culture_id: str)`
    - `load_places() -> list[Place]`
    - `save_places(places: list[Place])`
    - `load_glossary() -> list[GlossaryEntry]`
    - `save_glossary(entries: list[GlossaryEntry])`
    - `snapshot() -> dict`: returns `{"cultures": [...], "places": [...], "glossary": [...], "counts": {...}}`, all `model_dump(mode="json")`
  - The `counts` in `snapshot()` contain:
    - `unreviewed_total`
    - `unreviewed_by_culture: dict[str, int]`
    - `unreviewed_unassigned`
    - `unsure_places`
    - `unreviewed_additions_by_culture: dict[str, int]`
- Directories are created on first save. Missing files load as empty.

- [ ] **Step 1: Write the failing tests** (use `tmp_path`):
  - `test_world_dir_for`: `world_dir_for(tmp_path/"shared-context"/"grey-river.json") == tmp_path/"shared-context"/"grey-river.world"`.
  - `test_world_dir_for_scene_none_without_shared_context`: a `Scene()` with `shared_context=None` gives `None`.
  - `test_round_trip`: save a culture, places and a glossary, then load them back equal; the files exist at `cultures/<id>.json`, `places.json` and `glossary.json`.
  - `test_missing_files_load_empty`
  - `test_bad_culture_file_skipped`: write `"{not json"` to `cultures/bad.json`; `load_cultures()` returns the other cultures and doesn't raise.
  - `test_atomic_write_leaves_old_file_on_failure`: write valid data, then monkeypatch `json.dump` to raise mid-write. The old content is intact and no `*.tmp` file is left behind.
  - `test_snapshot_counts`:
    - glossary: 2 unreviewed in culture `taelrik`, 1 reviewed, and 1 unreviewed with `language=None`
    - places: 1 place with `unsure=True`
    - culture `taelrik` has 1 unreviewed addition
    - expected counts: `unreviewed_total == 5` (3 glossary + 1 unsure place + 1 addition), `unreviewed_by_culture == {"taelrik": 2}`, `unreviewed_unassigned == 1`, `unsure_places == 1`, `unreviewed_additions_by_culture == {"taelrik": 1}`
- [ ] **Step 2: Run** `uv run pytest tests/cultures/test_store.py -n0 -v`. Expected: FAIL.
- [ ] **Step 3: Implement `store.py`.** `atomic_write_json` uses `tempfile.NamedTemporaryFile(dir=path.parent, delete=False, suffix=".tmp")`, then `json.dump`, `flush`, `os.fsync`, `os.replace`, and unlinks the temp file in `finally` if it still exists.
- [ ] **Step 4: Run** the same command. Expected: 7 passed.
- [ ] **Step 5: Commit**: `git commit -m "feat(cultures): world store with atomic writes"`

---

### Task 4: Places: nesting, effective mix, edits

**Files:**
- Create: `src/talemate/cultures/places.py`
- Test: `tests/cultures/test_places.py`

**Interfaces:**
- Consumes: `Place`, `CultureShare`.
- Produces:
  - `class PlaceError(ValueError)`
  - `effective_mix(places: list[Place], place_id: str) -> tuple[list[CultureShare], Place | None]`: returns the mix and the place it came from. Walks to the nearest ancestor that has cultures; returns `([], None)` if none.
  - `country_of(places, place_id) -> Place | None`: the nearest ancestor (or self) of kind `country`.
  - `children(places, place_id) -> list[Place]`
  - `reparent(places, place_id, new_parent_id: str | None) -> list[Place]`: raises `PlaceError` on a cycle or unknown id.
  - `set_shares(places, place_id, shares: list[CultureShare]) -> list[Place]`: normalises to integers summing to 100 (largest remainder), drops zero shares, and sets `set_by="owner"` and `unsure=False`.
  - `delete_place(places, place_id, move_children_to: str | None) -> list[Place]`: children get `parent_id = move_children_to`.
  - `describe_mix(places, cultures: dict[str, Culture], place_id) -> str`: the plain-language sentence used in the Places detail panel.
- All functions are pure and return new lists. They don't mutate their input.

The `describe_mix` copy follows the mockup:
- Single culture: `"New people here are {Culture}, named from {Language}."`
- Several cultures: `"New people here are drawn from the mix: about {n} in 10 {Culture}, …. Each is named from their own culture's language."` Here `n = round(share/10)`, ordered by share descending.
- If the dominant culture differs from the dominant culture of the parent's effective mix, append `" Most also speak {ParentLanguage}, the language of {parent-source place name}."`

- [ ] **Step 1: Write the failing tests.** The fixture tree:

  ```
  reach (country) taelrik 100
  ├── veldhaer (town, no cultures)
  │   └── quillister (building, no cultures)
  ├── dhunmouth (city) taelrik 55 / elsiri 30 / vaskari 15
  └── birch (region) elsiri 90 / taelrik 10
      └── ilsara (village, no cultures)
  khaz (terrain) ghun 100, no parent
  ```

  Tests:
  - `test_inherits_from_nearest_ancestor`: `effective_mix(places,"quillister")` returns `[taelrik 100]` with source `reach`.
  - `test_pocket_overrides_parent`: `ilsara` takes its mix from `birch`.
  - `test_root_without_cultures`: a lone root with no cultures returns `([], None)`.
  - `test_country_of`: `country_of(.., "ilsara").id == "reach"`; `country_of(.., "khaz") is None`.
  - `test_reparent_into_descendant_rejected`: `reparent(.., "reach", "ilsara")` raises `PlaceError`.
  - `test_set_shares_normalises`: shares `[(a,1),(b,1),(c,1)]` become `[34,33,33]` (sum 100); a zero share is dropped; `set_by == "owner"`.
  - `test_delete_moves_children`: deleting `veldhaer` with `move_children_to="reach"` gives `quillister.parent_id == "reach"`.
  - `test_describe_mix_pocket`: for `birch` the text contains `"about 9 in 10 Elsiri"`, `"1 in 10 Taelrik"` and `"Most also speak Taelrik, the language of The Taelrik Reach."`
  - `test_inputs_not_mutated`: after `set_shares`, the original list's place is unchanged.
- [ ] **Step 2: Run** `uv run pytest tests/cultures/test_places.py -n0 -v`. Expected: FAIL.
- [ ] **Step 3: Implement `places.py`.** Ancestor walks keep a visited set, so even corrupt files can't loop.
- [ ] **Step 4: Run** the same command. Expected: 9 passed.
- [ ] **Step 5: Commit**: `git commit -m "feat(cultures): place nesting and culture mix"`

---

### Task 5: Culture file format, import preview, import, export

**Files:**
- Create: `src/talemate/cultures/exchange.py`, `src/talemate/cultures/culture.schema.json` (generated), `src/talemate/cultures/cli.py`
- Test: `tests/cultures/test_exchange.py`, `tests/cultures/data/taelrik.culture.json` (fixture)

**Interfaces:**
- Consumes: the models, `WorldStore`, `slugify`, `new_id`, `generator.roll`, `generator.fits`.
- Produces:
  - `CultureFileGlossary(text: str, kind, meaning: str = "", true_name: str = "", renderings: dict[str,str] = {})`
  - `CultureFilePlace(name: str, kind, parent: str | None = None, share: int = 100)`: a place where this culture lives. `parent` is matched by name.
  - `ForeignRendering(name: str, rendering: str)`: this culture's rendering of a name that belongs to another culture.
  - `CultureFile(format_version: Literal[1] = 1, culture: Culture, glossary: list[CultureFileGlossary] = [], places: list[CultureFilePlace] = [], foreign_renderings: list[ForeignRendering] = [])`. Inside the file, `culture.additions` holds any play additions exported earlier.
  - `ImportPreview(culture_id: str, culture_name: str, is_update: bool, counts: dict[str,int], claimed_unassigned: list[str], places_existing: list[str], places_new: list[str], conflicts: list[str], name_clash: str | None, warnings: list[str])`
  - `preview_import(store: WorldStore, raw: str) -> ImportPreview`: raises `ImportFormatError(ValueError)`, with a readable message listing pydantic errors, on bad JSON or bad schema.
  - `apply_import(store: WorldStore, raw: str, today: str) -> Culture`
  - `export_culture(store: WorldStore, culture_id: str) -> str`: pretty JSON with `indent=2`.
  - `write_schema(path: Path) -> None`, which writes `CultureFile.model_json_schema()`.
  - In `cli.py` (`python -m talemate.cultures.cli`), for the skill:
    - `validate <file>`: exit 0 or print errors and exit 1
    - `sample <file> [--generator ID] [--count N]`: print rolled names per generator, each with `fits` = ✓/✗
    - `schema`: print the schema

Import rules (spec 9.2):
- **New culture.** The id is `culture.id` or `slugify(culture.name)`. The culture is written with `source_file` and `imported_at=today`.
- **Re-import of an existing id.**
  - Replace every field except `additions`.
  - Additions: Talemate's list is kept. Additions in the file whose `id` isn't in Talemate's list are appended.
- **Glossary entries from the file**, matched to existing entries by `text`, case-insensitively, within the same culture:
  - no match: add with `origin.by="import"` and `status="reviewed"`
  - match where the existing entry is `reviewed` or `edited_by_owner`: keep Talemate's copy and list it in `conflicts` if any field differs
  - otherwise: update from the file
- **Claiming unassigned names.** A file glossary entry whose text matches an *unassigned* entry, case-insensitively, moves that entry to this culture with `status="unreviewed"`, filling in the meaning. It is listed in `claimed_unassigned`.
- **Foreign renderings.** Find the glossary entry with that `name`, case-insensitively, in any culture, and set `renderings[this culture id]`. Names not found go in `warnings`.
- **Places.**
  - A file place matching an existing place's name, case-insensitively, adds or replaces this culture's share, then re-normalises with `set_shares`. It is listed in `places_existing`.
  - An unknown place is created with `set_by="owner"` under its matched parent (or as a root). It is listed in `places_new`.
- **Name clash.** Another culture with the same name but a different id goes in `name_clash`, and the preview shows it. Apply still imports under the file's id.
- **Generator warnings.** Every generator is test-rolled with `count=5`. One that yields 0 names adds a warning `"Generator '<name>' produced no names"`.
- **Export.** Writes the culture (with additions), its glossary entries, its shares on places (as `CultureFilePlace`) and its renderings of other cultures' names (as `foreign_renderings`). Exporting a culture and importing the result into an empty world reproduces the same culture, glossary texts and shares.

- [ ] **Step 1: Write the fixture** `tests/cultures/data/taelrik.culture.json`. Use the mockup's Taelrik:
  - the categories and generators from the mockup's "Given names (male)", "Family names" and "Place names", with patterns valid in Task 2's syntax
  - 4 dictionary entries
  - the 4 phrases (2 sayings, 2 curses), with breakdowns
  - customs, food, 2 holidays
  - glossary: Veldhaer, Kethrun, saervik
  - places: The Taelrik Reach (country) at 100, Dhunmouth (city, parent The Taelrik Reach) at 55
  - foreign_renderings: Kasrool → "Khaz-Rull"
- [ ] **Step 2: Write the failing tests** in `test_exchange.py`:
  - `test_preview_new_culture`: on an empty store, `is_update is False`; `counts` equals `{"words":4,"phrases":4,"generators":3,"glossary":3,"places":2}`.
  - `test_preview_matches_unassigned_case_insensitive`: store has unassigned `"veldhaer"`; the preview has `claimed_unassigned == ["veldhaer"]`. After apply, that entry has `language == "taelrik"` and `status == "unreviewed"`.
  - `test_preview_flags_name_clash_with_other_id`: store has a culture `id="river-folk"` named `"Taelrik"`; `preview.name_clash == "river-folk"`.
  - `test_bad_json_and_bad_schema`: `"{"` and `{"culture":{"name":1}}` both raise `ImportFormatError`, and the message mentions `culture`.
  - `test_reimport_keeps_additions_and_reviewed_entries`: import, then add a kept addition, then mark Kethrun reviewed with a changed meaning. Re-import the original file. The addition is still present, Kethrun's meaning is still the edited one, `"Kethrun"` is in the preview's `conflicts`, and a dictionary change from the file is applied.
  - `test_reimport_never_deletes_talemate_only_entries`: an entry added in Talemate survives a re-import that lacks it.
  - `test_foreign_rendering_applied`: store has an Elsiri glossary entry "Kasrool"; after import, `renderings["taelrik"] == "Khaz-Rull"`. An unknown name produces a warning.
  - `test_places_shares_merged`: store has Dhunmouth at elsiri 100; after import its shares are taelrik 55 / elsiri 45; The Taelrik Reach is created as a country.
  - `test_export_round_trip`: `export_culture`, then import into a fresh store; the cultures are equal ignoring `imported_at`, and the glossary texts and shares match.
  - `test_schema_file_up_to_date`: the committed `culture.schema.json` equals `CultureFile.model_json_schema()`.
  - `test_cli_validate_and_sample`: `subprocess.run([sys.executable,"-m","talemate.cultures.cli","validate",fixture])` returns 0; `sample` prints lines containing `✓`.
- [ ] **Step 3: Run** `uv run pytest tests/cultures/test_exchange.py -n0 -v`. Expected: FAIL.
- [ ] **Step 4: Implement** `exchange.py` and `cli.py` (argparse). Generate the schema with `uv run python -m talemate.cultures.cli schema > src/talemate/cultures/culture.schema.json`.
- [ ] **Step 5: Run** the same command. Expected: 11 passed.
- [ ] **Step 6: Commit**: `git commit -m "feat(cultures): culture file format, import and export"`

---

### Task 6: Websocket plugin `cultures`

**Files:**
- Create: `src/talemate/server/cultures.py`
- Modify: `src/talemate/server/websocket_server.py`. Import the module next to the other `talemate.server` imports, and add `cultures.CulturesPlugin.router: cultures.CulturesPlugin(self)` to `self.routes` (around lines 60-88).
- Test: `tests/server/test_cultures_plugin.py`

**Interfaces:**
- Consumes: `WorldStore`, `world_dir_for_scene`, `places.*`, `exchange.*`, `generator.roll`.
- Produces `CulturesPlugin(Plugin)` with `router = "cultures"`.
- **Reply shape.** Every handler that changes data replies with a `world` message: `{"type":"cultures","action":"world","data": {"available": bool, "world_name": str, **store.snapshot()}}`. With no shared context it sends only `{"available": False}`. Errors go through `signal_operation_failed(msg)`.
- **The store is re-opened from disk on each request**, so edits from another scene are never shadowed by a stale cache.
- **Handlers.** The `data` fields named are pydantic payload models in the same file.
  - `handle_get_world({})`
  - `handle_save_culture({"culture": Culture-dict})`: also used to edit the description, customs, food, holidays and language
  - `handle_delete_culture({"culture_id"})`: the culture's glossary entries become unassigned, and its shares are removed from places
  - `handle_addition({"culture_id","addition_id","op": "keep"|"edit"|"drop","text"?})`
  - `handle_save_place({"place": Place-dict})`: create if the id is empty (`new_id()`); a changed `parent_id` goes through `reparent`; a changed `cultures` goes through `set_shares`
  - `handle_delete_place({"place_id","move_children_to"?})`
  - `handle_save_glossary_entry({"entry": GlossaryEntry-dict})`: sets `edited_by_owner=True` when text, meaning or language changed; create if the id is empty with `origin.by="owner"` and `status="reviewed"`
  - `handle_review_glossary_entry({"entry_id","status"})`
  - `handle_delete_glossary_entry({"entry_id"})`
  - `handle_roll({"culture_id","generator_id","count"?=20})`, which replies `{"type":"cultures","action":"rolled","data":{"generator_id","names":[...]}}`. Names already in the glossary are excluded.
  - `handle_import_preview({"content": str})`, which replies `{"action":"import_preview","data": ImportPreview}`
  - `handle_import_apply({"content": str})`, which replies with `world`, then `signal_operation_done(emit_status_message="Imported <name> into <world>")`
  - `handle_export({"culture_id"})`, which replies `{"action":"exported","data":{"filename":"<id>.culture.json","content":str}}`

- [ ] **Step 1: Write the failing tests.**
  - **Setup.** Reuse the `_MockWebsocketHandler` pattern from `tests/server/test_scene_message.py`. Build a `Scene()` whose `scenes_dir` is monkeypatched to `tmp_path` (the `isolated_scene` pattern from `tests/test_scene_methods.py`), with `scene.shared_context = SharedContext(filepath=<save_dir>/shared-context/world.json)`. Import `SharedContext` from `talemate.shared_context`.
  - `test_no_shared_context_reports_unavailable`
  - `test_get_world_empty`: `available is True`; `cultures == []`.
  - `test_import_apply_then_world_has_culture`: use the Task 5 fixture. Files appear under `shared-context/world.world/`.
  - `test_save_place_rejects_cycle`: the reply is `operation_done` with an error, and the file is unchanged.
  - `test_save_glossary_entry_marks_owner_edit`
  - `test_roll_excludes_glossary_names`: monkeypatch `generator.roll` to return names including one already in the glossary; the reply's names exclude it.
  - `test_delete_culture_unassigns_entries`
  - `test_addition_keep_edit_drop`
  - `test_export_returns_content`: the content parses with `CultureFile.model_validate_json`.
- [ ] **Step 2: Run** `uv run pytest tests/server/test_cultures_plugin.py -n0 -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the plugin and register the route.
- [ ] **Step 4: Run** the same command, then the whole suite with `uv run pytest`. Expected: all pass, no regressions.
- [ ] **Step 5: Commit**: `git commit -m "feat(cultures): websocket plugin"`

---

### Task 7: The `culture-design` Claude Code skill

**Files:**
- Create: `.claude/skills/culture-design/SKILL.md`, `.claude/skills/culture-design/reference/rule-syntax.md`, `.claude/skills/culture-design/reference/example.culture.json` (copy of the Task 5 fixture)

**Interfaces:**
- Consumes: `culture.schema.json`, `python -m talemate.cultures.cli validate|sample`, and the rule syntax from Task 2.

The skill must:
1. Name its trigger in its front-matter `description`: designing or extending a culture or language for a Talemate world.
2. Interview the owner, one question at a time, about the culture's people, place and feel, and the language level (`description` / `naming` / `full`).
3. Read existing cultures. Either ask for the world folder path (`scenes/<project>/shared-context/<name>.world/`) or for exported files. Use them to keep neighbouring languages distinct and to write `foreign_renderings`. For an unwritable language, write `glossary[].true_name` plus `renderings` per existing culture.
4. When extending an exported culture, keep `additions` and existing glossary entries. It may claim names the owner lists from "Unassigned names" by adding glossary entries with the same text.
5. Build the culture:
   - description, customs, food, holidays
   - language: sound, categories and generators (people, places and things as fits). For `full` also grammar, dictionary and phrases grouped as `sayings`, `curses`, `greetings`, with breakdowns.
6. Before finishing, run `uv run python -m talemate.cultures.cli validate <file>` and `sample <file>`. Show the owner the sample names and revise generators until they're happy.
7. Write `<id>.culture.json` where the owner asks, then tell them to import it via World Editor → Cultures → Import culture.
8. State its non-goals: no translation of long passages, and no law or governance fields.

- [ ] **Step 1: Write** `SKILL.md` (under ~250 lines) and the two reference files.
- [ ] **Step 2: Verify** that `uv run python -m talemate.cultures.cli validate .claude/skills/culture-design/reference/example.culture.json` exits 0.
- [ ] **Step 3: Commit**: `git commit -m "feat(cultures): culture-design skill"`

---

### Task 8: Cultures tab shell, drawer and culture page (frontend)

**Files:**
- Create:
  - `talemate_frontend/src/components/cultures/WorldStateManagerCultures.vue`: main tab and "tool"; owns websocket state
  - `talemate_frontend/src/components/cultures/WorldStateManagerMenuCulturesTools.vue`: drawer
  - `talemate_frontend/src/components/cultures/CulturePage.vue`: header and sub-tabs
  - `talemate_frontend/src/components/cultures/CultureOverview.vue`: Culture sub-tab
  - `talemate_frontend/src/components/cultures/LanguageOverview.vue`: Language sub-tab
  - `talemate_frontend/src/components/cultures/CultureNoWorld.vue`: the "link a Shared World" prompt
- Modify:
  - `talemate_frontend/src/components/WorldStateManager.vue`:
    - Add a `tabs` entry `{name:"cultures", title:"Cultures", icon:"mdi-account-group-outline"}` after suggestions.
    - Add a `<v-window-item value="cultures">` with `<WorldStateManagerCultures ref="cultures" @world-state-manager-navigate="show" />`.
    - Add `else if (tab === 'cultures') tool = this.$refs.cultures;` in the tool selection (~line 377).
    - Render a count badge on the Cultures tab: change the `v-tab` to use its default slot for `cultures` and show a `v-badge inline color="amber-lighten-2"` with `unreviewed_total` when it's above 0. The count comes from `this.$refs.cultures.counts`, through a `cultures-counts` event the tab emits that sets a `culturesUnreviewed` data field.
  - `talemate_frontend/src/components/WorldStateManagerMenu.vue`: add the `v-else-if="tab === 'cultures'"` branch rendering `WorldStateManagerMenuCulturesTools` with `:tool="tool"`. Register the component.

**Interfaces:**
- Consumes: the `cultures` router messages from Task 6, plus the injected `getWebsocket`, `registerMessageHandler` and `unregisterMessageHandler` (pattern: `WorldStateManagerSceneSharedWorld.vue:191-230,422-425`).
- Produces the main tab's state and methods, which the drawer reads through `tool`:
  - **State:** `world` (the last `world` payload), `selected` (`{type: "culture"|"places"|"unassigned", id?: string}`), `counts`
  - **Methods:**
    - `select(type, id)`
    - `send(action, data)`: sends `{type:'cultures', action, ...data}`
    - `openImport()`
    - `shareState(meta)`, a no-op hook, like other tools
- The main tab requests `get_world` when it becomes visible (watch the parent `tab` the way `requestWorld` is triggered in `WorldStateManager.vue:280-300`) and on every `world` message.

Drawer layout (mockup):
- **Create**: "Import culture" (`mdi-file-upload-outline`, primary)
- **Cultures (n)**: one `v-list-item` per culture
  - a 10px colour square in `prepend`
  - the title is the culture name
  - the subtitle is `speaks <language> · <level>`, plus `, can't be written` when `writable` is false
  - an amber `v-badge inline` with that culture's unreviewed count (glossary plus additions)
- **Where they live**: "Places & regions", with a badge of `unsure_places`
- **Not yet in a language**: "Unassigned names", with a badge of `unreviewed_unassigned`
- a muted caption naming the shared world

Culture page:
- **Header.** The colour square and name; a primary tonal `x-small` label chip `Speaks <language> · <level>`; a grey chip `<source_file> · <imported_at>`; a **Re-import** button (opens import, Task 10). Also an **Export** button that triggers a browser download of the `exported` content using a Blob URL.
- **Sub-tabs.** Culture / Language / Glossary / Dictionary / Phrases / Generators.
  - Naming-level languages hide Dictionary and Phrases.
  - Description-level languages also hide Generators.
  - The Glossary tab shows a badge.
- **Culture sub-tab.** Cards: Who they are (editable textarea); Where they live (places carrying this culture, with share mix bars, and an "All places" link); Language summary with an "Open language" button; Customs (list editor); Food & dress (textarea); Holidays (name / when / description rows, with the caption "“When” is plain text for now; real dates arrive with the world calendar."). Play additions show inside their section with Keep / Edit / Drop, which call `addition`. Edits save on blur through `save_culture`.
- **Language sub-tab.**
  - For writable languages: how it sounds, the counts (words, phrases, generators, glossary names), the category inventory as monospace chips, syllable notes and grammar notes.
  - For unwritable languages: the description, and a table of glossary entries showing `true_name` and each culture's rendering.
  - Fields are editable and save through `save_culture`.
- **No shared world.** When `available` is false, show `CultureNoWorld`: an outlined info alert explaining that cultures belong to a Shared World, with a button that emits `world-state-manager-navigate('scene', 'shared')`. Check in `WorldStateManagerScene.vue` how a sub-tab is selected from navigation, and use that.

- [ ] **Step 1: Implement** the components and the edits above, following existing component idioms (Options API, `inject`, `v-list density="compact" slim`, `v-card` panels, `MAX_CONTENT_WIDTH` from `constants/layout.js`).
- [ ] **Step 2: Build** with `cd talemate_frontend && npm run build`. Expected: build succeeds with no new errors or warnings from these files.
- [ ] **Step 3: Manual check** (`start.sh`, open a scene linked to a Shared World):
  - The Cultures tab appears after Suggestions.
  - Without a shared world, the prompt shows and its button opens Scene → Shared World.
  - The drawer lists the sections.
  - After importing via `cli` files placed by hand (or after Task 10), the culture page shows its sub-tabs as described.
  - Editing a custom and reloading the scene keeps the edit.
- [ ] **Step 4: Commit**: `git commit -m "feat(cultures): World Editor Cultures tab and culture page"`

---

### Task 9: Glossary, dictionary, phrases, generators and unassigned names (frontend)

**Files:**
- Create in `talemate_frontend/src/components/cultures/`: `GlossaryView.vue` (filters, table and detail; used for a culture and for Unassigned names), `GlossaryDetail.vue`, `DictionaryTable.vue`, `PhraseList.vue`, `GeneratorList.vue`
- Modify: `CulturePage.vue` and `WorldStateManagerCultures.vue` (mount them)

**Interfaces:**
- Consumes: the `world.glossary` entries, plus the `save_glossary_entry`, `review_glossary_entry`, `delete_glossary_entry` and `roll` actions (Task 6).
- `GlossaryView` props: `entries: Array`, `cultures: Array`, `cultureId: String|null` (null = unassigned), `selectedId: String|null`. Emits: `select(id)`.

Behaviour (mockup Glossary tab):
- **Filter chips:** `Not reviewed (n)` (the default), `Reviewed (n)`, `All (n)`, plus a text filter over text and meaning.
- **Table columns:** Name (with an amber dot when unreviewed; `thing` and `word` entries in italic `highlight7`), Kind chip (person primary / place teal / thing amber / word blue), Meaning, First used in, Added by (AI / import / you).
- **Detail panel:**
  - **Origin box.** For `ai` entries: "The AI needed a name and rolled **<generator name>**. It picked one from:" followed by candidate chips, with the chosen one filled. For `ai_free`: "Made up by the AI with no language behind it. Assign it to a language once one exists." For `import`: "Came in with <source_file>." For `owner`: "Added by you."
  - **Fields:** Name, Language select (cultures plus "No language yet"), Meaning, and for unwritable languages True name.
  - **"What other cultures call it":** one editable row per other culture.
  - **First used.**
  - **Actions:**
    - **Looks right** saves edits and sets the status to reviewed. Only when unreviewed; otherwise it shows "Mark not reviewed".
    - **Pick another** appears only for `origin.by == "ai"` and opens a small menu of the other candidates plus "Roll new" (calls `roll` with `origin.generator_id`). Choosing one sets the text. In this plan it changes the glossary only; rename-everywhere is plan 4.
    - **Remove** asks for confirmation inline. `confirm()` isn't usable, so use a `v-menu` with Confirm.
  - After a review while the filter is "Not reviewed", select the next unreviewed entry.
- **Unassigned names page:** a heading card with the mockup's explanation text, then `GlossaryView` with `cultureId=null`.
- **Dictionary:** a searchable `v-table` (word in italic `highlight7`, meaning, part), with add, edit and delete rows saved through `save_culture`.
- **Phrases:** cards per category, showing the original (italic `highlight7`), the translation, the usage note, and the breakdown as small chips. Add and edit happen in a dialog.
- **Generators:** one card per generator, showing its use icon, its name, its patterns as monospace text, a **Roll** button showing 5 names from the `rolled` reply, and editable patterns and reject rules. Below them sits the mockup's info hint explaining how the AI uses generators.

- [ ] **Step 1: Implement** the components.
- [ ] **Step 2: Build** with `cd talemate_frontend && npm run build`. Expected: success.
- [ ] **Step 3: Manual check**, with the imported Taelrik fixture plus one hand-added unassigned entry:
  - The filters' counts are correct.
  - Looks right moves the entry to Reviewed and the badge counts drop.
  - Changing Language to "No language yet" moves the entry to Unassigned names.
  - Roll shows new names each click.
  - A dictionary edit survives a scene reload.
- [ ] **Step 4: Commit**: `git commit -m "feat(cultures): glossary, dictionary, phrases and generators views"`

---

### Task 10: Places & regions view and import dialog (frontend)

**Files:**
- Create in `talemate_frontend/src/components/cultures/`: `PlacesView.vue`, `PlaceDetail.vue`, `CultureMixBar.vue`, `ImportCultureDialog.vue`
- Modify: `WorldStateManagerCultures.vue` (mount PlacesView and the dialog)

**Interfaces:**
- Consumes: `world.places` and `world.cultures`; the actions `save_place`, `delete_place`, `import_preview` and `import_apply`.
- `CultureMixBar` props: `mix: Array<{culture_id, share}>`, `cultures: Array`, `height: Number = 8`. It renders a stacked bar in each culture's `color`, with a tooltip per segment.
- **Mix in the frontend.** The frontend needs the effective mix and the plain-language text without its own copy of the rules. Add `effective` to each place in the `snapshot()` payload (Task 3/4): `{"mix": [...], "source_id": str | None, "description": describe_mix(...), "country_id": str | None}`. Add the field in `WorldStore.snapshot()` using `places.effective_mix`, `describe_mix` and `country_of`. Extend `test_snapshot_counts`'s sibling test, `test_snapshot_includes_effective_mix`, in `tests/cultures/test_store.py`.

Behaviour (mockup Places & regions):
- **Places table.** A nested table ordered as a depth-first tree, indented 20px per level. Columns: Place (name plus a muted kind, with an amber dot when `unsure`), Cultures (own culture chips in each culture's colour, or a muted `from <source name>`), Mix (`CultureMixBar` of `effective.mix`).
- **Toolbar:** "Add place" (name, kind, parent).
- **Detail panel:**
  - name, kind and parent (a select that excludes self and descendants); the server still refuses cycles
  - per-culture share sliders, applied on `change`, not on every input. The server normalises the shares, and the UI shows the returned values.
  - "Add culture" (a select of cultures not yet present)
  - "Set its own", shown when the place inherits. It copies the inherited mix.
  - a box "What this means in a scene here" with `effective.description`
  - the note; the AI-unsure alert ("The AI wasn't sure about this place…") with a "Looks right" that clears `unsure`
  - who set it ("Worked out by the AI · change it any time" / "Set by you · the AI won't change it")
  - for `kind == "country"`: the dashed "Law & governance … Coming in a later stage." hint; for others, "Law & governance: from <country>" when `country_id` is set
  - Delete. When there are children, it asks where they go (the parent or another place).
- **Import dialog**, opened from the drawer's "Import culture" and from **Re-import**:
  - A `v-file-input` accepting `.json`. It reads the file text with `FileReader`, then sends `import_preview`.
  - The preview shows the culture name, a level chip, the counts as small stats, and check lines in the mockup's icons: new or updating; claimed unassigned names; existing and new places; conflicts kept from Talemate; name clash; warnings.
  - "Import <name>" sends `import_apply`. On a format error, show the error message in a red tonal alert and keep the dialog open.

- [ ] **Step 1: Write the failing backend test** `test_snapshot_includes_effective_mix`: for the Task 4 fixture tree, `snapshot()["places"]` entry `ilsara` has `effective.source_id == "birch"` and `effective.country_id == "reach"`.
- [ ] **Step 2: Run** `uv run pytest tests/cultures/test_store.py -n0 -v`. Expected: the new test fails.
- [ ] **Step 3: Implement** the snapshot field, then the components.
- [ ] **Step 4: Run** `uv run pytest tests/cultures tests/server/test_cultures_plugin.py -n0` and `cd talemate_frontend && npm run build`. Expected: all pass; build succeeds.
- [ ] **Step 5: Manual check:**
  - Import `tests/cultures/data/taelrik.culture.json` through the dialog. The preview counts match, and after import the culture appears.
  - Re-importing shows "updating".
  - Build the mockup's tree. Birch Coast shows "about 9 in 10 Elsiri…".
  - Dragging a slider re-normalises to 100.
  - Re-parenting Reach under Ilsara isn't offered.
- [ ] **Step 6: Commit**: `git commit -m "feat(cultures): places view and import dialog"`

---

### Task 11: Whole-branch check

- [ ] **Step 1:** Run `uv run pytest`. Expected: whole suite green.
- [ ] **Step 2:** Run `uv run ruff check src/talemate/cultures src/talemate/server/cultures.py tests/cultures tests/server/test_cultures_plugin.py` and `uv run ruff format --check` on the same paths. Expected: clean.
- [ ] **Step 3:** Run `cd talemate_frontend && npm run build`. Expected: success.
- [ ] **Step 4: End-to-end manual pass.**
  - Design a small culture with the `culture-design` skill.
  - Import it.
  - Edit it in every sub-tab.
  - Export it.
  - Re-import it.
  - Check that nothing owner-made was lost and that a second scene linked to the same Shared World sees the same data.
- [ ] **Step 5: Commit** any fixes: `git commit -m "fix(cultures): end-to-end fixes"`
