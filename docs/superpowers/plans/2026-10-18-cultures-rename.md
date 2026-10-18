# Cultures Rename Everywhere Implementation Plan (plan 4 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the owner fixes a name in the Cultures tab (by editing it, with Pick another, or by giving an unassigned name a proper one), a dialog lists every place the old name is used in this shared world, and **Rename everywhere** changes all the ticked places safely. Renaming a character's name also renames the character.

**Architecture:**
- **Matching (pure).** `src/talemate/cultures/rename_text.py` holds `NameMatcher`. It does whole-word, possessive-aware, case-aware matching and replacement.
- **Field allowlist (pure).** `src/talemate/cultures/rename_data.py` scans and rewrites plain scene dicts and shared-context dicts. It only touches an explicit list of fields, and it re-keys characters. Nothing outside the list is ever read or changed.
- **Engine (filesystem).** `src/talemate/cultures/rename.py`:
  - finds the project's scene files and sorts them into linked, not linked and other world
  - builds the preview without writing anything
  - on apply, re-checks mtimes, backs up every file to `<project>/.rename-backups/<timestamp>/`, writes each file atomically, and rolls back from the backup on any failure
  - other scenes are rewritten as JSON on disk; their memory is rebuilt by Talemate's own `load_scene` → `commit_to_memory` the next time they load
- **Open scene (live).** `src/talemate/cultures/rename_live.py` copies the engine's rewritten dict for the open scene back onto the live `Scene`. Messages go through `Scene.edit_message`. The plugin then rebuilds memory with `scene.commit_to_memory()` and saves with `Scene.save`, which records the changelog delta.
- **Plugin.** `src/talemate/server/cultures.py` gains `rename_preview` and `rename_apply`.
- **Frontend.**
  - a new `RenameDialog.vue`
  - `GlossaryDetail.vue` routes every name change (the Name field, Pick another, and a new "Give it a proper name" menu for unassigned names) through the dialog
- **Tests.**
  - TDD pytest on fixture project folders: an open scene, another linked scene, a fork, an other-world scene, a non-scene JSON and the shared context
  - Playwright browser tests of the dialog
  - no AI tests

**Tech Stack:** Python 3.11, pydantic 2, pytest (pytest-asyncio, `asyncio_mode=auto`), Vue 3 + Vuetify 3, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-17-cultures-and-languages-design.md`. Read:
- §8.2 "Rename everywhere"
- §4, the anti-goal "A rename silently damages saves"
- §5.6 "Where it's stored"
- §10, the core-edit rule
- §11, the shared-context bugs (the stale `scene_character` in `shared_context.py:114` is why a character key must never be left half-renamed)

This plan builds on plans 1–2 (`2026-10-17-cultures-foundation.md`, `2026-10-18-cultures-ai.md`): the models, `WorldStore`, `atomic_write_json`, the `cultures` plugin and the Cultures tab. Plan 3 (`2026-10-18-cultures-story.md`) is independent of this one. If plan 3 has been merged first, keep its `counts`/`story` pushes when you touch `server/cultures.py`.

**The four plans:**
1. *Foundation* (done)
2. *AI use* (done)
3. *In the story*
4. *Rename everywhere* (this plan)

**Branch.** Make a new branch, `feature/cultures-rename`, from the newest cultures branch: `feature/cultures-story` if plan 3 is done, otherwise `feature/cultures-ai`.

**Environment.** This is a Guix machine. Every command runs from the repo root through `guix shell -m manifest.scm -- …`. Always use `uv run --no-sync`; a plain `uv run` drops the dev extra.
- Plain suite: `guix shell -m manifest.scm -- uv run --no-sync pytest`. Add `-n0 -v` and a path to run one file. There are 141 known failures from missing NLTK `punkt_tab` data, so judge a run by "no new failures".
- Browser group: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e -m e2e -n0 -v`. Pass a file path instead of `tests/e2e` to run one file.
- Frontend build: `guix shell -m manifest.scm -- sh -c 'cd talemate_frontend && npx --yes corepack@0.34.0 pnpm run build'`
- Lint: `guix shell -m manifest.scm -- uv run --no-sync ruff check <paths>` and `… ruff format --check <paths>`
- No AI group, and never set `TALEMATE_AI_TESTS`.

## Global Constraints

- **No core edits.** The only files this plan may change are:
  - backend: `src/talemate/cultures/rename_text.py`, `rename_data.py`, `rename.py`, `rename_live.py` (all new), `src/talemate/cultures/store.py` (`atomic_write_text`), `src/talemate/server/cultures.py`
  - frontend: `talemate_frontend/src/components/cultures/RenameDialog.vue` (new), `GlossaryDetail.vue`
  - tests: `tests/cultures/_rename_fixtures.py`, `tests/cultures/test_rename_*.py`, `tests/server/test_cultures_rename_plugin.py`, `tests/e2e/seed.py`, `tests/e2e/cultures/test_rename.py`
  - docs: `docs/superpowers/plans/2026-10-17-cultures-foundation-followups.md`
- **Which scenes are touched (decided).** Scene files are the top-level `*.json` files in the open scene's project folder (`scene.save_dir`) whose JSON is a dict with a `history` list and an `archived_history` list.
  - A scene is **linked** when its `shared_context` equals the open scene's `scene.shared_context.filename`. Only linked scenes and the shared world are touched.
  - An empty or missing `shared_context` means the scene is a timeline fork or isn't linked; the reason is `"not_linked"`.
  - Any other value means it is linked to a different world; the reason is `"other_world"`.
  - Unreadable JSON and non-scene JSON are skipped silently and never written.
- **The field allowlist (my call).** Only these fields are ever read for matches or rewritten. Everything else in a file is copied through byte-for-byte in meaning: `intro`, `description`, `agent_state`, `game_state`, `intent_state`, memory ids, assets and so on.
  - **Scene areas:**
    - `messages`: `history[*].message`
    - `history`: `archived_history[*].text`, `layered_history[*][*].text`
    - `characters`, for each `character_data[*]`:
      - `description`, `greeting_text`, `dialogue_instructions`
      - each item of `example_dialogue`
      - each string value of `base_attributes` and of `details`
    - `world_entries`: `world_state.manual_context[*].text`
    - `world_state`:
      - `world_state.location`
      - `world_state.characters[*].snapshot`, `world_state.items[*].snapshot`, `world_state.places[*].snapshot`
      - the keys of `world_state.items` and `world_state.places`
      - `world_state.reinforce[*].question` and `.answer`
  - **Shared-context areas** (the shared context JSON file):
    - `characters`: `character_data[*]`, with the same fields as above
    - `world_entries`: `world_state.manual_context[*].text`
    - `static_history`: `static_history[*].text`
  - **World-file area** `places`: `places.json` → `places[*].name` and `.note`.
  - **The glossary** is always updated by Rename everywhere:
    - the entry's `text`, with `edited_by_owner = True`
    - `language`, when the request sets it
    - every entry's `character_name` that a character rename moves
- **Character renames (decided: renaming the name renames the character).**
  - A character rename `K → K'` exists for every character key `K` in any linked file, in the shared context or in the open scene whose text contains the old name (`NameMatcher.count(K) > 0`), with `K' = NameMatcher.replace(K)`. "Dorel" becomes "Kelrin", and "Dorel Ashby" becomes "Kelrin Ashby".
  - **My call:** each rename is **one** tick, `character:<K>`. When it is ticked, it applies in **every** linked scene, the open scene and the shared context that hold `K`, whatever the per-scene ticks are. A shared character must never be half-renamed.
  - It changes:
    - the `character_data` key, keeping key order, and `.name`
    - `active_characters`
    - the `world_state.characters` key
    - `world_state.reinforce[*].character` when it equals `K`
    - the `world_state.character_name_mappings` key
    - `history[*].meta.character` and `history[*].meta.arguments.character` when they equal `K`
    - the `"K: "` speaker prefix of each `typ == "character"` message, even when `messages` is unticked
  - **Blocked:** if `K'` is already a different character's key in any file that holds `K`, the preview carries `blocked = "There's already a character called {K'} in {group label}."`, and apply refuses.
- **Matching (decided: whole-word, possessives, never part of a longer word, case-aware).**
  - The variants of the old name `o` are:
    - `o` itself
    - `o.upper()`, when it differs
    - `o[0].upper() + o[1:]`, when `o` starts lowercase
  - A match of a variant is replaced by `n`, `n.upper()` or `n[0].upper() + n[1:]` respectively.
  - A lowercase form of a capitalised name is **never** matched, so the place "Marrow" leaves the word "marrow" alone.
  - In the pattern, `'` and `’` match each other, and a whitespace run in the name matches any whitespace run.
  - **Boundaries (my call):**
    - before the match: `(?<![^\W_])(?<![^\W_]['’-])`
    - after the match: `(?![^\W_]|-[^\W_]|['’](?!s(?![^\W_]))[^\W_])`
    - So "Dorel's", "Dorel’s", "Dorels'" (as `Dorels` + `'`), "DOREL!" and "(Dorel)" match.
    - "Dorelin", "Tal'dorel", "Dorel-born", "Khaz-Dorel" and "dorel" do not match.
    - `[^\W_]` is Unicode-aware, so "Ghûn" and "Ghûnmar" behave like ASCII.
- **Safety (required).**
  - The preview writes nothing: no file, no directory, no mtime change.
  - Apply re-checks each file's `st_mtime_ns` against the preview, and refuses on any mismatch or missing file, before it backs up or writes anything.
  - Every file the engine writes goes through `store.atomic_write_text` (temp file, fsync, `os.replace`).
  - Any failure while writing restores every file already written from the backup, and raises.
- **Backups (decided).** Before the first write, the engine copies every file that will change, including the open scene's file when it has one, to `<project>/.rename-backups/<YYYYmmdd-HHMMSS>/<path relative to the project>`. If that folder exists, it adds `-2`, `-3` and so on. It also writes `rename.json` there: `{"old","new","entry_id","ts","files":[relative paths]}`. A built-in undo is not built.
- **The open scene (decided: normal edit paths).** It is never rewritten from disk:
  1. The engine rewrites `json.loads(scene.json)` in memory.
  2. `apply_to_live_scene` copies the changes onto the live objects, using `Scene.edit_message` for messages.
  3. The plugin then:
     - reloads `scene.shared_context` from disk
     - calls `await scene.commit_to_memory()`, a full memory rebuild, the same as a load
     - calls `await scene.save(auto=True, force=True)` when `scene.filename` is set, which appends the changelog delta and commits the shared context
  - **My call:** `Scene.save`'s own write is Talemate's non-atomic write. Making it atomic would be a core edit. Its file is backed up first, and a failure restores every file from the backup.
  - A never-saved open scene (no `filename`) is renamed in memory only, and no file is created for it.
- **Other scenes' changelogs are not touched (my call).** Their next save diffs against `changelog/<file>.latest.json`, so the rename shows up as part of that delta.
- **No model calls** anywhere in this plan.
- **Copy, exactly:**
  - Area labels:
    - `messages` "Story messages"
    - `history` "History (archived and layered)"
    - `characters` "Character sheets"
    - `world_entries` "World entries"
    - `world_state` "World state"
    - `static_history` "Static history"
    - `places` "Places & regions"
  - Group labels:
    - a scene: its `title`, else its `name`, else its filename, plus " (open)" for the open scene
    - the shared world: "Shared world: {world name}"
  - Dialog:
    - title `Rename "{old}" to "{new}"`
    - intro "“{old}” is used in these places. Untick any you want to leave as they are."
    - character row "Rename the character {K} to {K'} (in every linked scene that has it)"
    - untouched lines:
      - "Not changed, forked from the timeline or not linked to a shared world: {titles}."
      - "Not changed, linked to a different shared world: {titles}."
    - backup note "Every file that changes is backed up first, to .rename-backups in the project folder."
    - buttons "Rename everywhere", "Glossary only", "Cancel", and "Check again" (shown after a refused apply)
  - Errors:
    - conflict "Something changed since this list was made: {paths}. Check the list again."
    - stale preview "This rename list is out of date. Check the list again."
    - failure "The rename failed and every file was restored from the backup: {error}"
    - open-scene failure: the failure message plus " Reload the scene without saving."
  - Warning: "The glossary already has an entry called {new}."
  - Unassigned menu:
    - button "Give it a proper name"
    - labels "Language" and "Generator"
    - button "Roll names"

## Review Focus

These are the inputs most likely to bite the owner, though no spec line names them. Each has a test in the task that owns the code.

1. **Look-alike text.** The rename must leave these alone:
   - a name inside a longer word ("Dorelin"), after an apostrophe ("Tal'dorel"), or in a hyphenated compound ("Dorel-born", "Khaz-Dorel")
   - the lowercase common-word form ("marrow" for "Marrow")

   It must handle:
   - a curly-apostrophe possessive ("Dorel’s")
   - shouted text ("DOREL!")
   - a non-ASCII name ("Ghûn" next to "Ghûnmar")
   - a two-word name split over a line break ("Grey\nGull")
   - a name with regex metacharacters ("St. Ives (old)")

   (Task 1)
2. **A character whose full name contains the renamed name** ("Dorel Ashby"). Its key, `.name`, `active_characters`, speaker prefixes and world-state key all become "Kelrin Ashby" together. (Task 2: `test_character_renames_detects_full_names`, `test_character_prefix_renamed_when_messages_unticked`)
3. **The new name is already a character** in a linked scene. The preview is blocked, apply refuses, and nothing is written. (Task 3: `test_character_collision_blocks`)
4. **Odd files in the project folder**: a half-written or invalid `.json`, a non-scene JSON (`notes.json`), or a scene file with no `shared_context` key at all. The preview doesn't crash, those files are never written, and a scene with no key counts as `not_linked`. (Task 3: `test_preview_skips_unreadable_and_non_scene_files`)
5. **The open scene was never saved** (no filename). It is renamed in memory, no new scene file appears, and the other linked scenes are still renamed. (Task 5: `test_apply_unsaved_open_scene_creates_no_file`)

---

### Task 1: Name matcher

**Files:**
- Create: `src/talemate/cultures/rename_text.py`
- Test: `tests/cultures/test_rename_text.py`

**Interfaces:**
- Produces:
  - `class NameMatcher`, built with `NameMatcher(old: str, new: str)`. It raises `ValueError("A name can't be empty")` when either is blank after `strip()`.
    - `.old: str`, `.new: str`
    - `count(text: str) -> int`
    - `replace(text: str) -> str`
    - `snippets(text: str, limit: int = 3) -> list[str]`: up to `limit` excerpts, each running from 30 characters before a match to 30 characters after it, collapsed to single spaces. An excerpt gets a leading or trailing `…` when it was cut.
  - It is built from one compiled regex: the variants and boundaries in Global Constraints. The replacement callback picks the variant by comparing the match, with `’` normalised to `'` and whitespace collapsed, against each normalised variant.

- [ ] **Step 1: Write the failing tests.** `m = NameMatcher("Dorel", "Kelrin")` unless a test says otherwise.
  - `test_whole_word_and_possessive`:
    - `replace("Dorel's boat, Dorel’s oar, (Dorel).") == "Kelrin's boat, Kelrin’s oar, (Kelrin)."`
    - `count` of that text is 3
  - `test_never_part_of_longer_word`:
    - `replace(text) == text` for `"Dorelin waved. Tal'dorel. Dorel-born. Khaz-Dorel. Dorels"`
    - `count` of that text is 0
  - `test_case_aware`:
    - `replace("DOREL! dorel Dorel") == "KELRIN! dorel Kelrin"`
    - with `NameMatcher("saervik", "dhaervik")`, `replace("Saervik and saervik") == "Dhaervik and dhaervik"`
    - with `NameMatcher("Marrow", "Brannoch")`, `replace("bone marrow in Marrow") == "bone marrow in Brannoch"`
  - `test_non_ascii_and_multiword`:
    - with `NameMatcher("Ghûn", "Ghaun")`, `replace("Ghûn and Ghûnmar") == "Ghaun and Ghûnmar"`
    - with `NameMatcher("Grey Gull", "Saelin")`, `replace("the Grey\nGull's mast") == "the Saelin's mast"`
  - `test_metacharacters_and_apostrophes`:
    - with `NameMatcher("St. Ives (old)", "Ivesby")`, `replace("to St. Ives (old) now") == "to Ivesby now"`
    - with `NameMatcher("Tal'dun", "Taldor")`, `replace("Tal’dun's gate") == "Taldor's gate"`
  - `test_snippets`: for `"x" * 50 + " Dorel " + "y" * 50`, `snippets(...)` is a one-item list that starts and ends with `"…"` and contains `" Dorel "`. `snippets("no match") == []`.
  - `test_empty_names_rejected`: `NameMatcher(" ", "x")` and `NameMatcher("x", "")` raise `ValueError`.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/cultures/test_rename_text.py -n0 -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** `NameMatcher` in `rename_text.py`.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit**: `git add src/talemate/cultures/rename_text.py tests/cultures/test_rename_text.py && git commit -m "feat(cultures): whole-word name matcher for renames"`

---

### Task 2: Field allowlist transforms (pure)

**Files:**
- Create: `src/talemate/cultures/rename_data.py`
- Create: `tests/cultures/_rename_fixtures.py`, which Tasks 3–5 share
- Test: `tests/cultures/test_rename_data.py`

**Interfaces:**
- Consumes: `NameMatcher` (Task 1).
- Produces, in `rename_data.py`:
  - `SCENE_AREAS = ("messages", "history", "characters", "world_entries", "world_state")`
  - `SHARED_AREAS = ("characters", "world_entries", "static_history")`
  - `AREA_LABELS: dict[str, str]`, which also covers `"places"`, using the exact copy in Global Constraints
  - `@dataclass class AreaHits: count: int; samples: list[str]`, where `samples` holds at most 3, taken in field order
  - `scan_scene(data: dict, m: NameMatcher) -> dict[str, AreaHits]`: only areas with `count > 0`, in `SCENE_AREAS` order
  - `scan_shared(data: dict, m: NameMatcher) -> dict[str, AreaHits]`: the same, over `SHARED_AREAS`
  - `character_keys(data: dict) -> list[str]`: the keys of `data.get("character_data", {})`
  - `character_renames(keys: Iterable[str], m: NameMatcher) -> dict[str, str]`: `{K: m.replace(K)}` for every `K` with `m.count(K) > 0`, in first-seen order
  - `rewrite_scene(data: dict, m: NameMatcher, areas: set[str], renames: dict[str, str]) -> dict`
  - `rewrite_shared(data: dict, m: NameMatcher, areas: set[str], renames: dict[str, str]) -> dict`
  - Both rewrites return a deep copy and never mutate the input. Dict key order is preserved; a re-keyed entry keeps its position. Character renames are applied as listed in Global Constraints. A rename whose key isn't in this file is ignored.
  - `rewrite_places(places: list[Place], m: NameMatcher) -> list[Place]`, plus `scan_places(places: list[Place], m: NameMatcher) -> AreaHits`
- Produces, in `tests/cultures/_rename_fixtures.py`:
  - `OLD = "Dorel"`, `NEW = "Kelrin"`
  - `scene_dict(title: str, *, shared_context: str | None, messages: list[str] = (), character_messages: list[str] = (), characters: dict[str, str] = {}, archived: list[str] = (), layered: list[list[str]] = (), manual_context: dict[str, str] = {}, location: str | None = None, items: dict[str, str] = {}, intro: str = "", agent_state: dict = {}) -> dict`:
    - `history` is `NarratorMessage(message=t).to_dict()` for each message, then `CharacterMessage(t).to_dict()` for each character message
    - `characters` maps name → description, giving `Character(name=…, description=…, details={"past": description}).model_dump()`
    - `manual_context` maps id → text, with `shared=True`
    - `world_state` is `WorldState(...).model_dump()`, with a `CharacterState(snapshot=…)` for each character, the `items` as `ObjectState(snapshot=…)`, and `location`
    - `active_characters` is the list of character names
    - `shared_context` is left out of the dict entirely when it is `None`
  - `shared_dict(*, characters: dict[str, str], manual_context: dict[str, str], static_history: list[str]) -> dict`, in the shape `SharedContext.model_dump()` writes
  - `@dataclass class Project` with these fields:
    - `project_dir`, `context_path`, `store: WorldStore`
    - `open_path`, `linked_path`, `fork_path`, `other_path`, `notes_path`, `broken_path`
    - `open_data: dict`
    - `entry_id: str`
  - `build_project(tmp_path) -> Project` writes `tmp_path/"proj"`:
    - `open.json` (linked; "Dorel waits at the ford.", character "Dorel")
    - `linked.json` (`shared_context="world.json"`), with:
      - messages "Dorel crossed the ford.", "They took Dorel's boat.", "Dorelin waved.", "the Dorel-born", "DOREL!", "bone dorel"
      - the character message "Dorel: Hello."
      - characters "Dorel" ("Dorel is a ferryman.") and "Dorel Ashby" ("Dorel's cousin.")
      - archived "Dorel arrived."; layered `[["Dorel left."]]`
      - manual_context `{"e1": "Dorel runs the ferry."}`
      - location "Dorel's Landing"
      - items `{"Dorel's oar": "Dorel's oar."}`
      - intro "Dorel intro" and `agent_state={"director": {"note": "Dorel"}}`
    - `fork.json`: the same content with `shared_context=""`
    - `other.json`: `shared_context="other.json"`
    - `notes.json`: `{"note": "Dorel"}`
    - `broken.json`: the text `{"history": [`
    - `shared-context/world.json`, from `shared_dict(characters={"Dorel": "Dorel is a ferryman."}, manual_context={"e1": "Dorel runs the ferry."}, static_history=["Dorel arrived."])`
    - in `shared-context/world.world/`:
      - a glossary entry `Dorel` (kind `person`, language `taelrik`, `character_name="Dorel"`, origin `ai` with candidates `["Dorel","Kelrin"]`)
      - a place "Dorel's Landing" (note "Dorel's ferry")
    - Each scene's `title` is its filename stem ("open", "linked", …).
    - It writes every scene with `json.dumps(data, indent=2)`, and sets `open_data` to the open scene's dict.

- [ ] **Step 1: Write the failing tests.** Load the dicts with `json.loads(project.linked_path.read_text())`, and so on.
  - `test_scan_scene_counts_per_area`: on the linked dict:
    - `scan_scene(...)` keys are `["messages","history","characters","world_entries","world_state"]`
    - `messages.count == 4`: "Dorel crossed", "Dorel's boat", "DOREL!" and the "Dorel:" prefix
    - `history.count == 2`
    - `world_entries.count == 1`
  - `test_rewrite_only_selected_areas`: `rewrite_scene(d, m, {"messages"}, {})`:
    - the first five messages become "Kelrin crossed the ford.", "They took Kelrin's boat.", "Dorelin waved.", "the Dorel-born", "KELRIN!"
    - "bone dorel" is unchanged
    - `archived_history[0]["text"] == "Dorel arrived."`
  - `test_rewrite_leaves_unlisted_fields`: with every area selected and the renames from `character_renames(character_keys(d), m)`:
    - `intro`, `agent_state`, `memory_id`, `game_state`, every message's `id`, and `world_state.manual_context["e1"]["meta"]` equal the input's
    - the input dict is unchanged; compare against a `copy.deepcopy` taken before
  - `test_character_renames_detects_full_names`:
    - `character_renames(["Dorel","Dorel Ashby","Dorelin"], m) == {"Dorel":"Kelrin","Dorel Ashby":"Kelrin Ashby"}`
    - after `rewrite_scene` with every area:
      - `list(out["character_data"]) == ["Kelrin","Kelrin Ashby"]`, and each `.name` matches
      - `out["active_characters"] == ["Kelrin","Kelrin Ashby"]`
      - the keys of `out["world_state"]["characters"]` are `{"Kelrin","Kelrin Ashby"}`
  - `test_character_prefix_renamed_when_messages_unticked`: `rewrite_scene(d, m, set(), {"Dorel":"Kelrin"})`:
    - the character message becomes `"Kelrin: Hello."`
    - the narrator message "Dorel crossed the ford." is unchanged
  - `test_character_meta_and_reinforce`:
    - first add `meta={"character":"Dorel","arguments":{"character":"Dorel"}}` to a history item, and a reinforce `{"question":"Where is Dorel?","character":"Dorel"}`
    - after a rewrite with only the renames: both meta values and `reinforce[0]["character"]` are "Kelrin", and the question is unchanged
    - with `"world_state"` also selected, the question becomes "Where is Kelrin?"
  - `test_world_state_keys_renamed`: with `{"world_state"}`, `out["world_state"]["items"]` has the key `"Kelrin's oar"`, and `location == "Kelrin's Landing"`.
  - `test_rewrite_shared`: on the shared dict, with every `SHARED_AREAS` area and the renames `{"Dorel":"Kelrin"}`:
    - the `character_data` key is "Kelrin"
    - the manual context text is "Kelrin runs the ferry."
    - `static_history[0]["text"] == "Kelrin arrived."`
  - `test_rewrite_places`: `rewrite_places(store.load_places(), m)[0]` has `name == "Kelrin's Landing"` and `note == "Kelrin's ferry"`; `scan_places(...).count == 2`.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/cultures/test_rename_data.py -n0 -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** `rename_data.py` and `_rename_fixtures.py`.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit**: `git add src/talemate/cultures/rename_data.py tests/cultures/_rename_fixtures.py tests/cultures/test_rename_data.py && git commit -m "feat(cultures): allowlisted rename transforms for scene and shared-context data"`

---

### Task 3: Rename engine (preview, apply, backups, rollback)

**Files:**
- Create: `src/talemate/cultures/rename.py`
- Modify: `src/talemate/cultures/store.py`. Add `atomic_write_text(path: Path, text: str) -> None` (the current temp-file, fsync, chmod 0o644 and `os.replace` body), and make `atomic_write_json` call it. Its output stays the same.
- Test: `tests/cultures/test_rename.py`, `tests/cultures/test_store.py` (extend)

**Interfaces:**
- Consumes: Tasks 1–2, `WorldStore`, `GlossaryEntry`.
- Produces, in `rename.py`:
  - `BACKUP_DIRNAME = ".rename-backups"`
  - `class RenameError(ValueError)`
  - `class RenameConflict(RenameError)`, with `.paths: list[str]`; its message is the conflict copy
  - `@dataclass class OpenScene: path: Path | None; title: str; data: dict`
  - The pydantic models, which are a JSON contract with the frontend:
    - `RenameItem`: `id: str` (`"{group_key}:{area}"`), `area: str`, `label: str`, `count: int`, `samples: list[str]`
    - `RenameGroup`: `key: str` (`"scene:{filename}"`, or `"scene:"` for a never-saved open scene, or `"shared"`), `kind: Literal["scene","shared"]`, `label: str`, `filename: str`, `open: bool = False`, `items: list[RenameItem]`
    - `CharacterRename`: `id: str` (`"character:{old}"`), `old: str`, `new: str`, `groups: list[str]` (the group keys that hold it)
    - `UntouchedScene`: `filename: str`, `title: str`, `reason: Literal["not_linked","other_world"]`
    - `RenamePreview`, with fields:
      - `preview_id: str` (`new_id()`), `entry_id`, `old`, `new`
      - `groups: list[RenameGroup]`, ordered open scene first, then linked scenes by filename, then `shared` last
      - `characters: list[CharacterRename]`
      - `untouched: list[UntouchedScene]`, sorted by filename
      - `blocked: str | None = None`, `warnings: list[str] = []`
      - `files: dict[str, int]`: each project-relative POSIX path → `st_mtime_ns`, for every linked scene file (open scene excluded), the shared-context file, `glossary.json` and `places.json` when it exists
      - `total: int`: the sum of the item counts
  - `@dataclass class RenameResult`, with fields:
    - `backup_dir: Path`
    - `written: list[str]`: relative paths
    - `open_scene_after: dict | None`: the rewritten open-scene dict, or `None` when it doesn't change
    - `renames: dict[str, str]`: the ticked character renames
  - `find_scenes(project_dir: Path) -> list[tuple[Path, dict]]`: the scene-file rule in Global Constraints, sorted by name
  - `preview_rename(*, project_dir: Path, context_path: Path, store: WorldStore, entry_id: str, new_text: str, open_scene: OpenScene | None) -> RenamePreview`:
    - `old` is the stored entry's `text`
    - It raises `RenameError` for:
      - an unknown entry: "unknown glossary entry: {id}"
      - an empty new text: "A name can't be empty"
      - a new text equal to the old one: "The new name is the same as the old one."
    - Groups with no items are left out. A group is kept if it holds a character rename even with no items.
    - The open scene's file (when `open_scene.path` is set) is excluded from `find_scenes`' results; its data comes from `open_scene.data`.
  - `apply_rename(preview: RenamePreview, *, selected: set[str], project_dir: Path, context_path: Path, store: WorldStore, open_scene: OpenScene | None, set_language: bool = False, language: str | None = None, now: datetime) -> RenameResult`. It does these steps in order:
    1. `preview.blocked` → `RenameError(blocked)`.
    2. The mtime check → `RenameConflict`. This happens before anything else touches the disk.
    3. It computes every new file content in memory:
       - areas: the selected ids
       - renames: the selected `character:` ids, applied to every file
       - the glossary update and places
       - files whose content is unchanged are dropped
    4. Backups and `rename.json`, including `open_scene.path` when `open_scene_after` is not `None` and the path exists.
    5. Atomic writes, in this order:
       - the linked scene files, by filename
       - the shared-context file
       - places, through `store.save_places`
       - the glossary last, through `store.save_glossary`

       JSON files go through `atomic_write_text(path, json.dumps(data, indent=2))`, imported into `rename.py` by name so tests can patch it. On any exception it calls `restore_backup`, then raises `RenameError` with the failure copy.
  - `restore_backup(backup_dir: Path, project_dir: Path) -> list[str]`: copies every file listed in `rename.json` back, each through its own `_atomic_copy(src, dst)` (`shutil.copyfile` to a temp file in the target's folder, then `os.replace`). It does not use `atomic_write_text`, so a patched writer can't break the rollback. Returns the relative paths.
  - **Warning:** another glossary entry whose `text.lower() == new.lower()` gives the warning copy.

- [ ] **Step 1: Write the failing tests** (fixtures: `build_project(tmp_path)`; `open_scene = OpenScene(path=p.open_path, title="open", data=p.open_data)`; `NOW = datetime(2026, 10, 18, 12, 0, 0)`).
  - `test_preview_lists_linked_scenes_and_shared_world`:
    - group keys `["scene:open.json","scene:linked.json","shared"]`, with `groups[0].open is True` and the label "open (open)"
    - the `shared` group's item areas are `["characters","world_entries","static_history","places"]`
    - `untouched == [("fork.json","not_linked"), ("other.json","other_world")]`, compared as `(filename, reason)` pairs
    - `{c.old: c.new for c in characters} == {"Dorel":"Kelrin","Dorel Ashby":"Kelrin Ashby"}`
    - `"linked.json" in preview.files`, and `"fork.json" not in preview.files`
  - `test_preview_writes_nothing`:
    - snapshot `{path: (bytes, st_mtime_ns)}` for every file under `project_dir`, before and after; they are equal
    - `not (project_dir / ".rename-backups").exists()`
  - `test_preview_skips_unreadable_and_non_scene_files`:
    - neither `notes.json` nor `broken.json` appears in groups, untouched or files
    - a scene dict written with no `shared_context` key is `not_linked`
  - `test_apply_everything`: apply with every item and character id selected. Then:
    - `linked.json` messages read "Kelrin crossed the ford.", "They took Kelrin's boat.", "Dorelin waved.", "the Dorel-born", "KELRIN!", "bone dorel", "Kelrin: Hello."
    - its `character_data` keys are `["Kelrin","Kelrin Ashby"]`
    - in the shared-context file, the `character_data` key is "Kelrin"
    - the glossary entry has `text == "Kelrin"`, `edited_by_owner is True` and `character_name == "Kelrin"`
    - the place name is "Kelrin's Landing"
    - `open.json` on disk is **unchanged**, and `result.open_scene_after["history"][0]["message"] == "Kelrin waits at the ford."`
  - `test_apply_leaves_untouched_files_byte_identical`: after apply, `fork.json`, `other.json`, `notes.json`, `broken.json` and `shared-context/other.json` (when present) have the same bytes as before.
  - `test_apply_respects_unticked_items`: select everything except `"scene:linked.json:messages"`. Then:
    - `linked.json`'s first message is still "Dorel crossed the ford."
    - its character message is "Kelrin: Hello.", because the character tick applies everywhere
    - its archived history text is "Kelrin arrived."
  - `test_apply_without_character_tick_keeps_keys`: no `character:` ids selected:
    - the `linked.json` key is still "Dorel", but its description is "Kelrin is a ferryman."
    - the glossary `character_name` is still "Dorel"
  - `test_backup_layout`:
    - `result.backup_dir == project_dir/".rename-backups"/"20261018-120000"`
    - it contains `linked.json`, `open.json`, `shared-context/world.json`, `shared-context/world.world/glossary.json`, `shared-context/world.world/places.json` and `rename.json`
    - the backed-up `linked.json` bytes equal the pre-apply bytes
    - `rename.json["files"]` lists exactly those 5 paths
    - a second preview and apply (Kelrin → Tovrin) with the same `now` gives `…/20261018-120000-2`
  - `test_apply_refuses_on_changed_mtime`:
    - after the preview, `os.utime(linked_path, ns=(t, t + 1_000_000))`
    - apply raises `RenameConflict` with `"linked.json" in exc.paths`
    - every file is byte-identical, and there is no `.rename-backups`
  - `test_apply_rolls_back_on_failed_write`:
    - monkeypatch `talemate.cultures.rename.atomic_write_text` so its 2nd call raises `OSError("disk full")`
    - apply raises `RenameError`, whose message starts "The rename failed and every file was restored from the backup"
    - every file under `project_dir`, excluding `.rename-backups`, has the same bytes as before
  - `test_character_collision_blocks`:
    - add the character "Kelrin" to `linked.json` before the preview
    - `preview.blocked == "There's already a character called Kelrin in linked."`
    - apply raises `RenameError`, and nothing changes
  - `test_apply_sets_language`: with `set_language=True, language=None`, the glossary entry's `language is None`.
  - `test_duplicate_glossary_text_warns`: add an entry "kelrin"; `preview.warnings == ["The glossary already has an entry called Kelrin."]`.
  - `test_restore_backup`: after an apply, `restore_backup(...)` returns the 5 paths, and every file's bytes are back to the pre-apply bytes.
  - In `test_store.py`, `test_atomic_write_text`: it writes `"ä"` as UTF-8, sets mode `0o644`, and leaves no `.tmp` file behind.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/cultures/test_rename.py tests/cultures/test_store.py -n0 -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** `rename.py` and `atomic_write_text`.
- [ ] **Step 4: Run** the same command, then `guix shell -m manifest.scm -- uv run --no-sync pytest tests/cultures -n0`. Expected: all pass.
- [ ] **Step 5: Commit**: `git add src/talemate/cultures/rename.py src/talemate/cultures/store.py tests/cultures/test_rename.py tests/cultures/test_store.py && git commit -m "feat(cultures): rename engine with preview, mtime check, backups and rollback"`

---

### Task 4: Apply the rename to the live open scene

**Files:**
- Create: `src/talemate/cultures/rename_live.py`
- Test: `tests/cultures/test_rename_live.py`

**Interfaces:**
- Consumes: `rewrite_scene`, `character_renames` (Task 2).
- Produces: `async def apply_to_live_scene(scene: Scene, before: dict, after: dict) -> None`. `before` is `json.loads(scene.json)` taken at preview or apply time, and `after` is the engine's rewrite of it. It does this:
  - **Messages:** for each index `i` where `after["history"][i]["message"]` differs, call `scene.edit_message(scene.history[i].id, new)`. Where `meta` differs, assign `scene.history[i].meta = after meta`.
  - **History:** assign `scene.archived_history` and `scene.layered_history` from `after` when they differ.
  - **Characters:**
    - Rebuild `scene.character_data` in order from `zip(before keys, after keys)`, keeping **the same `Character` objects**, so actors still point at them.
    - On each one, set `name`, `description`, `greeting_text`, `dialogue_instructions`, `example_dialogue`, `base_attributes` and `details` from `after`, and set `memory_dirty = True` when any of them changed.
    - Assign `scene.active_characters = after["active_characters"]`.
  - **World state:** on the live `scene.world_state`:
    - set `location`
    - rebuild `characters`, `items` and `places` with their models (`CharacterState`, `ObjectState`, `PlaceState`), in order
    - set `reinforce[*].question`, `.answer` and `.character`
    - re-key `character_name_mappings`
    - set `manual_context[*].text`
  - **Contract:** afterwards, `json.loads(scene.json) == after`.

- [ ] **Step 1: Write the failing tests.**
  - **Setup.** A real `Scene()`, as `isolated_scene` in `tests/server/test_cultures_plugin.py` builds it. Fill it with:
    - `NarratorMessage("Dorel crossed the ford.")`, `CharacterMessage("Dorel: Hello.")`, `NarratorMessage("Nothing here.")`
    - `character_data = {"Dorel": Character(name="Dorel", description="Dorel is a ferryman."), "Mara": Character(name="Mara")}`
    - `active_characters = ["Dorel","Mara"]`
    - `world_state.characters = {"Dorel": CharacterState(snapshot="Dorel rows.")}`
    - `world_state.manual_context = {"e1": ManualContext(id="e1", text="Dorel runs the ferry.")}`
    - `archived_history = [{"text": "Dorel arrived.", "ts": "PT1S"}]`
  - `test_live_scene_serializes_to_after`: `before = json.loads(scene.json)`, `after = rewrite_scene(before, m, set(SCENE_AREAS), {"Dorel":"Kelrin"})`. After the apply, `json.loads(scene.json) == after`.
  - `test_messages_edited_through_edit_message`: spy on `scene.edit_message` (wrap and record). The calls are exactly `[(id0, "Kelrin crossed the ford."), (id1, "Kelrin: Hello.")]`; "Nothing here." isn't edited.
  - `test_character_object_identity_kept`: `obj = scene.character_data["Dorel"]`; after the apply:
    - `scene.character_data["Kelrin"] is obj`, `obj.name == "Kelrin"` and `obj.memory_dirty is True`
    - `list(scene.character_data) == ["Kelrin","Mara"]`
    - `scene.character_data["Mara"].memory_dirty is False`
  - `test_world_state_rekeyed`: `scene.world_state.characters` has the key "Kelrin" holding a `CharacterState` whose snapshot is "Kelrin rows.", and `manual_context["e1"].text == "Kelrin runs the ferry."`.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/cultures/test_rename_live.py -n0 -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `apply_to_live_scene`.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit**: `git add src/talemate/cultures/rename_live.py tests/cultures/test_rename_live.py && git commit -m "feat(cultures): apply renames to the open scene through its edit paths"`

---

### Task 5: Plugin actions `rename_preview` and `rename_apply`

**Files:**
- Modify: `src/talemate/server/cultures.py`
- Test: `tests/server/test_cultures_rename_plugin.py`

**Interfaces:**
- Consumes: Tasks 3–4, plus `_require_store`, `_fail`, `_send_world` and `signal_operation_done` (existing).
- Produces:
  - `RenamePreviewPayload(entry_id: str, new_text: str, request_id: str | None = None)`
  - `RenameApplyPayload(preview_id: str, selected: list[str], set_language: bool = False, language: str | None = None, request_id: str | None = None)`
  - `CulturesPlugin._rename_preview: RenamePreview | None`. The plugin keeps **only the last** preview (my call). It is cleared after an apply, successful or not.
  - `CulturesPlugin._open_scene() -> OpenScene`: `OpenScene(path=Path(scene.full_path) if scene.filename else None, title=scene.title or scene.name or "", data=json.loads(scene.json))`
  - `handle_rename_preview(data)`:
    - on success it queues `{"type":"cultures","action":"rename_preview","data": {**preview.model_dump(mode="json"), "request_id": …}}`
    - errors go through `_fail(str(e), request_id)`
  - `handle_rename_apply(data)`:
    1. If the id isn't the stored preview's, it fails with the stale-preview copy.
    2. It calls `apply_rename(...)`, with `now=datetime.datetime.now()` and a fresh `_open_scene()`. A `RenameError` (including `RenameConflict`) goes to `_fail(str(e), request_id)`.
    3. When the shared context file was written, it runs `await scene.shared_context.init_from_file()`.
    4. When `result.open_scene_after` is not None:
       - `await apply_to_live_scene(scene, open.data, result.open_scene_after)`
       - `await scene.commit_to_memory()`
       - `if scene.filename: await scene.save(auto=True, force=True)`
       - `scene.world_state.emit()`
       - `scene.emit_status()`
       - it queues the `world_state_manager` `character_list` message exactly as `handle_get_character_list` builds it
    5. If anything in steps 3–4 raises, it calls `restore_backup(result.backup_dir, project_dir)` and fails with the failure copy plus " Reload the scene without saving."
    6. On success: `_send_world(store)`, then it queues `{"type":"cultures","action":"renamed","data":{"request_id","old","new","backup_dir": <path relative to project>,"written": result.written,"open_scene_saved": bool}}`, then `signal_operation_done(signal_only=True, emit_status_message=f"Renamed {old} to {new}")`.

- [ ] **Step 1: Write the failing tests.**
  - **Setup.** Reuse the `isolated_scene` / `_MockWebsocketHandler` patterns from `tests/server/test_cultures_plugin.py`.
    - `bootstrap_scene(scene)` from `conftest`.
    - Fill the open scene to match `_rename_fixtures`' `open.json`, with `scene.name = scene.title = "open"` and `scene.filename = "open.json"`, and save it once. `Scene.save(auto=True)` returns early without a name.
    - Write `linked.json` and `shared-context/world.json` into `scene.save_dir` with the fixture helpers, plus the glossary entry and place.
    - Monkeypatch `Scene.add_to_recent_scenes` to an async no-op.
    - Replace `scene.commit_to_memory` with an async spy.
  - `test_preview_reply`: `handle_rename_preview({"entry_id": eid, "new_text": "Kelrin", "request_id": "r1"})`. The last message has action `rename_preview`, with `data.request_id == "r1"`, the group keys `["scene:open.json","scene:linked.json","shared"]` and a non-empty `preview_id`.
  - `test_apply_renames_open_scene_saves_and_rebuilds_memory`: preview, then apply with every id. Then:
    - `"Kelrin" in scene.character_data`
    - `open.json` on disk has `character_data` key "Kelrin"
    - the spy was called once
    - the actions after the apply end with `["character_list","world","renamed","operation_done"]`, where `character_list` has type `world_state_manager`
    - `renamed.data.open_scene_saved is True`
    - `linked.json` has "Kelrin crossed the ford."
  - `test_apply_with_stale_preview_id_fails`: apply with `preview_id="nope"` gives an `operation_done` error equal to the stale copy, and nothing is written.
  - `test_apply_conflict_reports_and_writes_nothing`: touch `linked.json` after the preview. The error starts "Something changed since this list was made: linked.json", and `scene.character_data` still has "Dorel".
  - `test_apply_failure_in_open_scene_restores_files`: monkeypatch `scene.save` to raise `RuntimeError("boom")`. The error starts with the failure copy and ends with " Reload the scene without saving.", and `linked.json` and `glossary.json` have their original bytes.
  - `test_apply_unsaved_open_scene_creates_no_file`: with `scene.filename = ""`, before the preview:
    - after the apply, there is no new `*.json` in `save_dir`
    - `"Kelrin" in scene.character_data`
    - `linked.json` is renamed
    - `renamed.data.open_scene_saved is False`
  - `test_preview_errors`:
    - an empty `new_text` gives the error "A name can't be empty"
    - the same text gives "The new name is the same as the old one."
    - a scene without a shared context gives "This scene has no shared world linked."
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/server/test_cultures_rename_plugin.py -n0 -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the payloads and handlers.
- [ ] **Step 4: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/server/test_cultures_rename_plugin.py tests/server/test_cultures_plugin.py tests/cultures -n0 -v`. Expected: all pass.
- [ ] **Step 5: Commit**: `git commit -m "feat(cultures): rename_preview and rename_apply websocket actions"` (add the files first).

---

### Task 6: Rename dialog, wired into the Name field and Pick another

**Files:**
- Create: `talemate_frontend/src/components/cultures/RenameDialog.vue`
- Modify: `talemate_frontend/src/components/cultures/GlossaryDetail.vue`
- Modify: `tests/e2e/seed.py`
- Test: `tests/e2e/cultures/test_rename.py`

**Interfaces:**
- Consumes: the `rename_preview` / `renamed` / `operation_done` messages (Task 5), and the existing `send(action, data)` prop.
- Produces:
  - **`RenameDialog`** (my call: the dialog owns its own websocket messages, so `GlossaryDetail` stays small):
    - props: `entry: Object`, `newText: String`, `setLanguage: Boolean = false`, `language: String|null = null`, `send: Function`
    - emits: `done`, `glossary-only`, `cancel`
    - **On mount** it sends `rename_preview` `{entry_id, new_text, request_id}` and shows a spinner.
    - **On a preview whose `total === 0` with no `characters`**, it emits `glossary-only` at once, without showing anything (my call: there's nothing to tick).
    - **Otherwise** it renders a `v-dialog` (`data-testid="rename-dialog"`) containing:
      - the title and intro copy
      - an alert `data-testid="rename-blocked"` when `blocked` is set, and the warnings
      - one checkbox per character rename (`data-testid="rename-character"`, `data-item-id`)
      - per group, a `data-testid="rename-group"` block with `data-group-key`, holding the group label and one checkbox per item (`data-testid="rename-item"`, `data-item-id`). Each item shows "{label} · {count}" and its samples in a caption.
      - the untouched lines (`data-testid="rename-untouched"`)
      - the backup note
      - all boxes ticked by default
    - **Buttons:**
      - **Rename everywhere** (disabled when `blocked` is set or nothing is ticked) sends `rename_apply` `{preview_id, selected, set_language, language, request_id}`, with a spinner. On `renamed` it emits `done`.
      - **Glossary only** emits `glossary-only`.
      - **Cancel** emits `cancel`.
    - **On an `operation_done` error with its request id**, it shows the message in `data-testid="rename-error"` and offers **Check again**, which re-sends the preview.
  - **`GlossaryDetail`:**
    - `save()` now always sends `text: this.entry.text` (the stored text), so blurring any other field never renames.
    - The Name field calls `commitName(local.text)` on `@blur` and `@keyup.enter`.
    - `pickCandidate(c)` calls `commitName(c)`.
    - `commitName(text, { setLanguage = false, language = null } = {})`:
      - trims the text
      - empty → reset `local.text` to `entry.text`
      - equal to `entry.text` and not `setLanguage` → nothing
      - otherwise sets `renameTarget = {newText, setLanguage, language}`, which mounts `<RenameDialog v-if="renameTarget">`
    - **Dialog events:**
      - `glossary-only`: sends `save_glossary_entry` with `{...local, text: newText}`, plus `language` when `setLanguage`, then clears `renameTarget` and the local dirty state
      - `cancel`: resets `local.text = entry.text` and clears `renameTarget`
      - `done`: clears `renameTarget` and the local dirty state
- Produces, in `tests/e2e/seed.py`: `seed_extra_scene(world: SeededWorld, filename: str, *, link: Literal["world","none","other"], messages: list[dict] = (), characters: list[dict] = ()) -> Path`. It writes another scene into the same project:
  - `"world"` links it to the world's existing context file. The script loads it with `SharedContext(filepath=…).init_from_file()` and sets it on the scene, **without** writing it.
  - `"none"` has no shared context.
  - `"other"` creates `shared-context/other.json` from this scene.
  - It is implemented as two new optional `_SCENE_SCRIPT` spec keys, `filename` and `link_existing`. The existing callers keep their behaviour.

- [ ] **Step 1: Write the failing browser tests** in `tests/e2e/cultures/test_rename.py`, using the `_ui.py` helpers and the `_entry` pattern from `test_glossary.py`.
  - **Common setup.**
    - `seed_world(app.root, project=…, messages=[{"text":"Dorel crossed the ford."},{"text":"They took Dorel's boat. Dorelin waved."}], characters=[{"name":"Dorel","description":"Dorel is a ferryman.","shared":True}])`, then `place_culture`.
    - A glossary entry Dorel: person, by `ai`, generator `given_male`, candidates `["Dorel","Kelrin"]`, `character_name="Dorel"`.
    - `seed_extra_scene(world, "linked.json", link="world", messages=[{"text":"Dorel waits."}], characters=[{"name":"Dorel","description":"Dorel is a ferryman.","shared":True,"active":False}])`
    - `seed_extra_scene(world, "fork.json", link="none", messages=[{"text":"Dorel waits."}])`
    - `seed_extra_scene(world, "other.json", link="other", messages=[{"text":"Dorel waits."}])`
    - Record the bytes of `fork.json` and `other.json`.
  - `test_pick_another_renames_everywhere`:
    - Open the glossary, then Pick another → the chip "Kelrin".
    - `rename-dialog` is visible, with `rename-group` keys including `scene:<open filename>`, `scene:linked.json` and `shared`.
    - `rename-untouched` contains "fork" and "other".
    - The `rename-character` "character:Dorel" is checked.
    - Click **Rename everywhere**, and the dialog closes.
    - `wait_for_json(linked.json, …)` until its history has "Kelrin waits." and `character_data` has the key "Kelrin".
    - The open scene file has "Kelrin's boat. Dorelin waved.", and the `character_data` key "Kelrin".
    - The `.narrator-message` text on screen contains "Kelrin's boat".
    - The glossary row reads "Kelrin".
    - `fork.json` and `other.json` bytes are unchanged.
    - `world.scene_path.parent / ".rename-backups"` has exactly one subfolder, holding `linked.json` and `rename.json`.
  - `test_name_edit_cancel_and_glossary_only`:
    - Fill the Name field with "Varn" and press Tab; the dialog shows.
    - **Cancel**: the Name field reads "Dorel" again, and no file changed. Compare the bytes of the scene, `linked.json` and `glossary.json`.
    - Fill "Varn" again → **Glossary only**: `wait_for_json(glossary.json)` until the entry text is "Varn". The scene files are unchanged, and there is no `.rename-backups`.
  - `test_unticked_item_is_left_alone`:
    - Pick another → Kelrin.
    - Untick `rename-item` `scene:linked.json:messages`, then click **Rename everywhere**.
    - `linked.json` history still reads "Dorel waits.", while its `character_data` key is "Kelrin".
  - `test_changed_file_is_refused_then_rechecked`:
    - Pick another → Kelrin; the dialog shows.
    - Rewrite `linked.json` on disk with the same content and a newer mtime (`os.utime`).
    - Click **Rename everywhere**: `rename-error` contains "Something changed since this list was made", and `linked.json` still has "Dorel waits.".
    - Click **Check again**, then **Rename everywhere**: `linked.json` has "Kelrin waits.".
  - `test_unused_name_skips_dialog`: an entry "Ossa" (person, by `owner`), used nowhere. Name → "Ossan", then Tab. `glossary.json` gets "Ossan", `rename-dialog` never became visible, and there is no `.rename-backups`.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e/cultures/test_rename.py -m e2e -n0 -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `RenameDialog.vue`, the `GlossaryDetail` changes and `seed_extra_scene`.
- [ ] **Step 4: Run** the frontend build, then the same browser command, then `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e/cultures -m e2e -n0 -v`, so that `test_glossary.py`'s Pick-another checks still pass. Expected: all pass.
- [ ] **Step 5: Commit**: `git commit -m "feat(cultures): Rename everywhere dialog for name edits and Pick another"`

---

### Task 7: Unassigned names: give one a proper name

**Files:**
- Modify: `talemate_frontend/src/components/cultures/GlossaryDetail.vue`
- Test: `tests/e2e/cultures/test_rename.py` (extend)

**Interfaces:**
- Consumes: `commitName(text, {setLanguage, language})` (Task 6), and the `roll` action with its `request_id` (existing).
- Produces:
  - When `!entry.language`, a `v-menu` opened by **Give it a proper name** (`data-testid="proper-name-menu"`). It holds:
    - a **Language** `v-select` of the cultures
    - a **Generator** `v-select` of that culture's generators. The default is the first one whose `use` matches the entry's kind: `person` → `people`, `place` → `places`, otherwise `things`. If none matches, the first generator.
    - a **Roll names** button. It sends `roll` with its own pending request id, separate from Pick another's, and `count: 20`.
    - the rolled names as chips (`data-testid="proper-name-candidate"`)
  - Clicking a chip calls `commitName(chip, { setLanguage: true, language })`.
  - **Glossary only** from that dialog saves both the text and the language.
  - Keeping the name and only choosing a language stays the existing **Language** select. It is not a rename.

- [ ] **Step 1: Write the failing browser test** `test_unassigned_name_gets_proper_name`:
  - Seed the open scene with the message "Mirrow lay quiet." and an unassigned entry "Mirrow" (place, by `ai_free`, `language=None`).
  - Open **Unassigned names**, then **Give it a proper name** → Language "Taelrik" → **Roll names**.
  - Click the first `proper-name-candidate` and record its text `picked`.
  - In the dialog, click **Rename everywhere**.
  - The open scene file's history contains `f"{picked} lay quiet."`.
  - `glossary.json`'s entry has `text == picked` and `language == "taelrik"`.
  - The Unassigned names page no longer lists "Mirrow".
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e/cultures/test_rename.py -m e2e -n0 -v -k proper_name`. Expected: FAIL.
- [ ] **Step 3: Implement** the menu.
- [ ] **Step 4: Run** the frontend build and the whole `tests/e2e/cultures/test_rename.py` browser command. Expected: PASS.
- [ ] **Step 5: Commit**: `git commit -m "feat(cultures): give an unassigned name a proper one through Rename everywhere"`

---

### Task 8: Whole-branch check

- [ ] **Step 1:** Run `guix shell -m manifest.scm -- uv run --no-sync pytest`. Expected: no new failures beyond the 141 known `punkt_tab` ones.
- [ ] **Step 2:** Run `guix shell -m manifest.scm -- uv run --no-sync ruff check src/talemate/cultures src/talemate/server/cultures.py tests/cultures tests/server tests/e2e` and `… ruff format --check` on the same paths. Expected: clean.
- [ ] **Step 3:** Run the frontend build and the whole browser group. Expected: all succeed.
- [ ] **Step 4: Check the no-core-edit rule.** Run `git diff <base branch> --stat -- src/talemate talemate_frontend ':!src/talemate/cultures' ':!src/talemate/server/cultures.py' ':!talemate_frontend/src/components/cultures'`. It must print nothing.
- [ ] **Step 5: Update** `docs/superpowers/plans/2026-10-17-cultures-foundation-followups.md`:
  - Add a "Rename everywhere" line pointing at `tests/e2e/cultures/test_rename.py`.
  - Note that the open scene's own save uses Talemate's non-atomic `Scene.save`; it is backed up first.
  - Note that other scenes' changelogs pick the rename up on their next save.
  - Add any gap you found while building.
- [ ] **Step 6: Commit**: `git commit -m "chore(cultures): plan 4 branch check"`
