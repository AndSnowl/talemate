# Phase 2, Plan A: Playable Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the owner make a world, create characters, places and lore from prompts, start a scene from one storyline prompt, and play a few turns on their local model. The AI's context comes from the world as of the scene's in-world date.

**Architecture:**
- **The game loop stays as it is.** Talemate's existing node game loop, agents and prompt templates are kept. What changes is underneath them.
- **Scenes are stored in the world database.** A new `src/talemate/world/scenes.py` holds them, in the same strictly typed package as the rest of the world store.
- **A new `src/talemate/worldplay/` package bridges the two.**
  - It turns world things into the `Character` objects the agents read, as of the scene's date.
  - It injects the place, the goal and lore through the agents' existing `inject_instructions` signals, following the Culture agent's pattern.
  - It saves and loads a world-backed `Scene` through the world database.
  - It runs create-from-prompt and scene setup.
- **The frontend:** a `worlds` websocket router serves new Vue screens. The screens share one Pinia store.

**Tech stack:** Python 3.11, SQLite (the existing world store), pydantic 2, Jinja2 prompt templates through `Prompt.request`, Vue 3 + Vuetify, Pinia (new), Playwright e2e.

**Spec:**
- `docs/superpowers/specs/2026-10-19-fantasymate-phase-2-slice-design.md`. This plan implements it.
- `docs/superpowers/specs/2026-10-18-fantasymate-world-data-model-design.md` is the main spec, and the authority for the data model.

## Global Constraints

- **Running things on Guix:**
  - Run everything through `guix shell -m manifest.scm -- …` from the repo or worktree root.
  - Always `uv run --no-sync`.
  - The plain suite must stay at **0 failed** (baseline on main 7d463079: 6692 passed) and about 40 s.
- **Testing rule (owner, `docs/dev/dev-loop-optimizations.md`):**
  - While iterating, run only the area's tests.
  - Run the full plain suite once per task.
  - Run the browser suite (`pytest tests/e2e -m e2e -n 4`, never more than 4) once at the end of a task that changes UI. Check for orphaned apps first.
  - A UI change that the AI tests drive needs `grep -rn` over `tests/ai`.
- **AI probes and AI tests need the owner's go-ahead.** They call koboldcpp (currently `Skyfall-31B-v4.2-i1-Q4_K_M`). Plain tests use `MockClient` only.
- **The slice reuses the existing game loop, agents and templates.** Don't rewrite `scene-loop.json` or `process-input.json`. The `@` action must keep working unchanged.
- **New world features are written in Python, not as nodes** (main spec, "Scene runners").
- **`src/talemate/world/` stays under strict mypy** (`tests/world/test_typecheck.py`), with no imports from the rest of `talemate`.
- **`src/talemate/worldplay/` may import `talemate`.** It isn't strict.
- **Ids are 32-hex `uuid4().hex`.** Dates are `WorldDate`; format them with the world's `Calendar.format`.
- **Generated prose is never fed back into fact extraction** (phase-0 probe finding).
- **Ordinary turns get no extra LLM calls.** Prose generation happens only at creation, after a fact edit (in the background), and at scene setup.
- **New screens:**
  - colours use `rgb(var(--v-theme-<role>))` theme roles from `talemate_frontend/src/theme/roles.js`;
  - state lives in the Pinia store `talemate_frontend/src/stores/worlds.js`, which registers one websocket handler for the `worlds` router.
- **Cultures stay hidden:** no culture picker in the slice. The Culture agent's features stay as they are today, and they don't run for world scenes.

## Review Focus

1. **Crossing a fact's date mid-scene.** After time passage takes a scene past a fact's start date, the character's context shows the fact as a "since" line, with no LLM call (Task 5: `test_since_lines_after_time_passage`).
2. **A world scene survives save and reload.** It comes back with the same history, `ts`, characters, player, goal and start date (Task 6: `test_world_scene_roundtrip`).
3. **Names in the scene prompt overlap and vary.** "Maren" against "Maren Vos", any case, and the possessive "Maren's" all match the longest name, once (Task 8: `test_match_names_longest_and_possessive`).
4. **A cancelled create preview leaves the world unchanged.** `head_rev` doesn't move (Task 7: `test_preview_does_not_write`).
5. **A world scene's save never writes a scene JSON file, shared context or changelog** (Task 6: `test_world_save_writes_no_files_outside_world`).

---

### Task 1: A richer golden recording

**Files:**
- Modify: `tests/characterization/test_scene_golden.py` and `tests/data/characterization/scene_golden.json` (regenerated)

The recording has to cover the context the slice will change. Extend the script setup, before the existing four steps:
- set `scene.description` to a premise ("Two rivermen wait out a storm in a flooded tavern.");
- set `scene.world_state.location`, if it exists on `scene.world_state`, to "The Drowned Stag tavern";
- give Alice `description`, `base_attributes` and `dialogue_instructions`, and give Bob a `description`;
- leave memory off, as today (that ruling stands).

- [ ] **Step 1: Make the setup change** in `_setup_lab_scene` or the script builder. Keep the four existing steps.
- [ ] **Step 2: Regenerate:** `… pytest tests/characterization -n0 --update-baselines`. Check that `scene_golden.json` now contains the premise text, Alice's description and the location in at least one prompt.
- [ ] **Step 3: Check it's stable:** `… pytest tests/characterization -n0` and `-n 4`. Expected: PASS.
- [ ] **Step 4: Commit** with `test: richer golden scene (premise, place, character sheets)`.

### Task 2: Probe scripts (create-from-prompt, scene setup)

**Files:**
- Create: `scripts/dev/probe_world_create.py`
- Create: `scripts/dev/probe_scene_setup.py`
- Create: `scripts/dev/probe_data/world_prompts.json`. It holds:
  - 3 character prompts, 2 place prompts and 2 lore prompts. Include "a riverside smuggling town that's been half-flooded for a generation" and "a grizzled ferryman who owes the Wardens more than money";
  - 3 storyline prompts, against a tiny world of 2 characters, 1 place and 1 lore entry.
- Test: `tests/dev/test_probe_world.py` (stub server, as in `tests/dev/test_probe_fact_roundtrip.py`)

**Interfaces:**
- **Reuse the client helpers:** `chat(url, system, user, *, max_tokens, timeout) -> str` and the `<think>` stripping. Import them from `probe_fact_roundtrip.py`; don't copy them.
- **`probe_world_create.py`** asks the model for a JSON fact list. Each fact is `{"category": <one of the kind's categories>, "text", "since": optional year}`, followed by prose from those facts. It records, per prompt:
  - `facts`;
  - `prose`;
  - `kept_intent`: each owner phrase checked as present in the facts or not, judged by a second chat call;
  - `invented`: the count of facts not drawn from the prompt.
- **`probe_scene_setup.py`** asks the model for JSON `{"player", "characters": [{"name", "world": bool}], "place": {"name", "world": bool}, "goal", "intro"}`, given the prompt plus the tiny world rendered as text. It records whether named world things were used, and what was invented.
- **Both scripts:**
  - exit with code 2 without `TALEMATE_AI_TESTS=1`, and code 3 when koboldcpp is unreachable;
  - write `report.json` and `report.md` to `.test-artifacts/<name>-<stamp>/`, rewritten after every step.
- **Prompt wording is the builder's.** It becomes the seed for Tasks 7 and 8's templates, so keep it in one constant per script.

- [ ] **Step 1: Write the failing tests:**
  - `test_create_probe_refuses_without_opt_in`;
  - `test_create_probe_against_stub`: one prompt gives facts and prose in the report;
  - `test_setup_probe_against_stub`;
  - `test_setup_probe_records_world_use`: stub output naming a world character gives `world: true`.
- [ ] **Step 2: Run them; expect FAIL.** `… pytest tests/dev/test_probe_world.py -v -n0`
- [ ] **Step 3: Implement both scripts and the data file.**
- [ ] **Step 4: Run the tests; expect PASS.** Then run the full plain suite once.
- [ ] **Step 5: Commit** with `feat(probe): world create and scene setup probes`.

### Task 3: Run the probes (owner-gated)

- [ ] **Step 1: Ask the owner for the go-ahead.** Stop until they say yes.
- [ ] **Step 2: Run both scripts** with `TALEMATE_AI_TESTS=1`. Expected: exit code 0.
- [ ] **Step 3: Write `docs/superpowers/probes/2026-10-19-world-create-and-setup.md`.** Include:
  - the numbers;
  - three representative outputs, quoted;
  - the prompt changes that Tasks 7 and 8 should adopt.
- [ ] **Step 4: Commit** with `docs(probe): world create and scene setup findings`.

### Task 4: Scene tables, and prose stretches, in the world store

**Files:**
- Modify: `src/talemate/world/schema.py`. This is **migration 2**: append it to `MIGRATIONS` and set `SCHEMA_VERSION = 2`. Worlds may now exist outside tests, so no in-place edit.
- Create: `src/talemate/world/scenes.py`
- Create: `src/talemate/world/prose.py`
- Modify: `src/talemate/world/store.py` (accessors) and `src/talemate/world/__init__.py` (exports)
- Test: `tests/world/test_scenes.py`, `tests/world/test_prose_cache.py`

**Interfaces (the package stays strict and imports nothing from `talemate`):**

**Tables added by migration 2:**
- `scenes`: `id TEXT PRIMARY KEY`, `name TEXT NOT NULL`, `start_instant INTEGER NOT NULL`, `start_precision TEXT NOT NULL`, `premise TEXT NOT NULL DEFAULT ''`, `goal TEXT NOT NULL DEFAULT ''`, `player_thing_id TEXT`, `state_json TEXT NOT NULL DEFAULT '{}'`, `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`, `continued_from TEXT REFERENCES scenes`.
- `scene_messages`: `id TEXT PRIMARY KEY`, `scene_id TEXT NOT NULL REFERENCES scenes`, `branch_id TEXT NOT NULL DEFAULT 'main'`, `seq INTEGER NOT NULL`, `kind TEXT NOT NULL`, `data_json TEXT NOT NULL`, `elapsed TEXT NOT NULL DEFAULT 'PT0S'`.
  - `elapsed` is the ISO duration since the scene's start, at that message.
  - Add a UNIQUE constraint on `(scene_id, branch_id, seq)`.
- `scene_things`: `scene_id`, `local_id TEXT`, `kind TEXT`, `data_json TEXT`, with the primary key `(scene_id, local_id)`. It holds the scene-local, invented things.
- `prose_cache`: `thing_id TEXT NOT NULL`, `section TEXT NOT NULL`, `stretch_start INTEGER`, `stretch_end INTEGER`, `rev INTEGER NOT NULL`, `text TEXT NOT NULL`, `edited INTEGER NOT NULL DEFAULT 0`, with the primary key `(thing_id, section, stretch_start)`.
  - NULL `stretch_start` means "always"; NULL `stretch_end` means "open".

Scenes are **not** world things. They're not part of replay or undo.

**`world/scenes.py`:**
- `class SceneRecord(BaseModel)` mirrors the `scenes` columns, with `start: WorldDate` and `state: dict[str, object]`.
- `class MessageRecord(BaseModel)`: `id`, `seq`, `kind`, `data: dict[str, object]`, `elapsed: str`.
- `class SceneStore`, made through `World.scenes() -> SceneStore`:
  - `create(name, start: WorldDate, *, premise="", goal="", player_thing_id=None, continued_from=None) -> str`
  - `get(scene_id) -> SceneRecord | None`
  - `list() -> list[SceneRecord]`, newest `updated_at` first
  - `update(scene_id, **fields) -> None`
  - `replace_messages(scene_id, messages: list[MessageRecord]) -> None`: rewrites the `main` branch in one transaction.
  - `messages(scene_id) -> list[MessageRecord]`, in `seq` order
  - `set_local_things(scene_id, things: list[dict]) -> None` and `local_things(scene_id) -> list[dict]`
  - `latest_end() -> WorldDate | None`: the latest `start.plus(last elapsed)` over all scenes.

  All writes go through plain transactions, not `World.revision`.

**`world/prose.py`:**
- `stretches(view_factory, thing_id) -> list[tuple[WorldDate | None, WorldDate | None]]` returns the boundaries between consecutive changes to that thing. A boundary is any field value or fact start/end, taken from `World.timeline`.
- `class ProseCache`, made through `World.prose() -> ProseCache`:
  - `get(thing_id, section, at: WorldDate | None) -> CachedProse | None`, where `CachedProse` has `text`, `stretch_start`, `stretch_end`, `rev`, `edited`;
  - `put(thing_id, section, stretch_start, stretch_end, text, *, edited=False) -> None`;
  - `stale(thing_id, section, at) -> bool`: True when there's no entry for the stretch containing `at`, or when the entry's `rev` is older than the newest timeline change inside that stretch.

**Tests:**
- `test_migration_2_from_v1`: a v1 world opened by new code gains the tables, and `user_version == 2`.
- `test_scene_create_get_list`
- `test_replace_messages_is_atomic`: a bad record (missing `kind`) rolls back, and the old messages stay.
- `test_latest_end`
- `test_stretches_from_timeline`: on the `maren` fixture, the stretch boundaries are exactly the timeline dates.
- `test_prose_cache_get_by_date`
- `test_stale_after_new_fact`
- `test_typecheck_still_passes`: the existing typecheck test covers this, so just run it.

- [ ] **Step 1: Write the tests;** expect FAIL. `… pytest tests/world -n0`
- [ ] **Step 2: Implement migration 2, `scenes.py`, `prose.py` and the accessors.**
- [ ] **Step 3: tests/world passes, including `test_typecheck.py`.** Then run the full plain suite once.
- [ ] **Step 4: Commit** with `feat(world): scene tables and prose cache (schema v2)`.

### Task 5: World things as agents see them

**Files:**
- Create: `src/talemate/worldplay/__init__.py`, `src/talemate/worldplay/characters.py`, `src/talemate/worldplay/context.py`, `src/talemate/worldplay/prose_gen.py`
- Create the templates `src/talemate/prompts/templates/world/thing-prose.jinja2` (prose for one section from facts) and `src/talemate/prompts/templates/world/scene-context.jinja2` (the injected block)
- Test: `tests/worldplay/__init__.py`, `tests/worldplay/test_characters.py`, `tests/worldplay/test_context.py`

**Interfaces:**
- **Sections:** a character's prose has two sections, `description` and `personality`.
  - `description` is generated from the appearance and background facts.
  - `personality` is generated from the personality facts.
  - Speech facts become `dialogue_instructions`. Facts that read like example lines (they start with a quote mark) become `example_dialogue`.
- **`prose_gen.py`:**
  - `async def generate_section(world, thing_id, section, at, client) -> str`: calls `Prompt.request("world.thing-prose", client, "create", vars={facts, kind, section, name})`, then `ProseCache.put` for the stretch containing `at`.
  - `async def ensure_prose(world, thing_id, at, client) -> None`: generates every section that's stale at `at`.
- **`characters.py`:**
  - `def character_from_world(world, thing_id, at: WorldDate, *, is_player: bool) -> Character`. It never calls the LLM. It builds:
    - `name`: the name at `at`;
    - `description`: the cached description prose, plus `since_lines`;
    - `base_attributes`: `{"age": <years from born>, "born": Calendar.format(born)}`, when born is set, plus `"personality"` with the cached personality prose;
    - `dialogue_instructions` and `example_dialogue` from the speech facts;
    - a `world_thing_id` attribute recording which thing it came from. Add `world_thing_id: str | None = None` to `Character` in `src/talemate/character.py` as a normal field, so it round-trips.
  - `def since_lines(world, thing_id, at) -> list[str]`: for each fact that started or ended after the start of the cached stretch, a line such as `"Since 314: lost her left eye."` or `"Until 316: member of the Wardens."`, formatted with the calendar's year.
- **`context.py`:**
  - `def scene_date(record: SceneRecord, scene_ts: str) -> WorldDate` returns `record.start.plus(scene_ts)`.
  - `def world_context_block(world, record, at) -> str` renders `world/scene-context.jinja2` with:
    - the scene goal;
    - the current place's name and facts at `at`, where the place is `record.state["place_thing_id"]`;
    - the lore entries listed in `record.state["pulled_in"]`, with their facts at `at`.
  - `class WorldSceneContext` is attached as `scene.world_context` for world scenes. It holds `world`, `record` and `refresh_characters()`, which rebuilds every active character from the world at `scene_date(...)` and replaces it on the scene, keeping the actor bindings.
  - `def connect(scene) -> None` connects to `agent.conversation.inject_instructions` and `agent.narrator.inject_instructions`. It appends one `DynamicInstruction(title="World", content=world_context_block(...))`, the same pattern as `agents/culture/__init__.py:246-266`. It also connects to the `agent.world_state.time` signal so that `refresh_characters()` runs after each time passage.

**Tests:**
- `test_character_from_world_fields`: name, age at the date, description from the cache, and speech facts in `dialogue_instructions`.
- `test_character_before_and_after_fact`: a lost-eye fact from 314. At 312 the description has no "eye"; at 315 a since line mentions it, when the cached prose is from 312's stretch.
- `test_since_lines_after_time_passage` (Review Focus 1): a scene at 313-12 with time passage `P30D` into 314. After `refresh_characters()`, the character's description holds the since line. The MockClient has no queued responses, which proves no LLM call was made.
- `test_world_context_block_has_goal_place_lore`
- `test_inject_adds_world_instruction`: emitting `agent.conversation.inject_instructions` adds exactly one "World" instruction.

- [ ] **Step 1: Write the tests;** expect FAIL. `… pytest tests/worldplay -n0`
- [ ] **Step 2: Implement the modules, the templates and the `Character.world_thing_id` field.**
- [ ] **Step 3: tests/worldplay passes.** Then run the full plain suite once. The golden test must still pass unchanged; nothing here is wired into normal scenes yet.
- [ ] **Step 4: Commit** with `feat(worldplay): characters and context from the world at a scene date`.

### Task 6: World-backed scenes, saved and loaded

**Files:**
- Create: `src/talemate/worldplay/persistence.py`
- Modify:
  - `src/talemate/tale_mate.py`: `Scene.save` and the `save_dir` property, adding the world-backed branch;
  - `src/talemate/load/__init__.py`: add `load_world_scene`;
  - `src/talemate/server/websocket_server.py`: `load_scene` accepts a world target.
- Test: `tests/worldplay/test_persistence.py`

**Interfaces:**
- `Scene` gains `world_ref: WorldSceneRef | None = None`. `WorldSceneRef` is `{world_path: str, scene_id: str}` and is defined in `persistence.py`.
  - When it is set, `save_dir` returns `<world_path>/scenes/<scene_id>`, which holds assets and nodes.
  - `Scene.save(...)` then calls `persistence.save_world_scene(self)` and returns, skipping the JSON write, the changelog and shared context. It still calls `add_to_recent_scenes`.
- `def save_world_scene(scene) -> None` writes:
  - `SceneStore.update` with `state` = the `serialize` keys, minus `history`, `character_data`, `shared_context`, `nodes_filename` and `creative_nodes_filename`;
  - the `goal`, `premise` and `player_thing_id`;
  - `replace_messages` from `scene.history`. Each message's `to_dict()` goes into `data`, `kind` comes from the message type, and `elapsed` comes from `calc_time(0, idx + 1)` or `"PT0S"`.
  - Stable message ids: add `world_id: str | None = None` to the base `SceneMessage`, persisted by `to_dict`/`from_dict`. It is assigned (uuid hex) the first time the message is saved.
  - Characters that aren't world-backed (invented in the scene) are saved through `set_local_things`.
- `async def load_world_scene(scene, world_path, scene_id) -> Scene` is called by `load_scene` when `file_path` starts with `"world://"` (`world://<world_path>|<scene_id>`). It:
  1. fills the scene from `state` and the messages, using the existing `_load_history` path;
  2. builds characters with `character_from_world` at `scene_date`, for `state["characters"]`, a list of `{thing_id | local_id, active}`, and for local things;
  3. calls `add_actor` for each active one, with the player from `player_thing_id`;
  4. attaches a `WorldSceneContext` and calls `connect(scene)`;
  5. calls `fix_time()`;
  6. sets `scene.world_ref`.

  The node graph is the default `scene-loop.json`.

**Tests:**
- `test_world_scene_roundtrip` (Review Focus 2): build a scene with two world characters, three messages including a time passage, and a goal, then save it. Load it into a fresh `MockScene`. Equal: the history texts and types, `ts`, the active character names, the player, `world_context.record.goal` and the start date.
- `test_world_save_writes_no_files_outside_world` (Review Focus 5): after a save, nothing new exists under `scenes_dir()`, and no changelog or shared-context file exists.
- `test_message_ids_stable_across_saves`
- `test_local_character_roundtrip`

- [ ] **Step 1: Write the tests;** expect FAIL.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: tests/worldplay passes and the full plain suite passes,** including the golden test, unchanged.
- [ ] **Step 4: Commit** with `feat(worldplay): world-backed scenes save and load through the world database`.

### Task 7: Create from a prompt, and the `worlds` router (world and thing actions)

**Files:**
- Create: `src/talemate/worldplay/create.py` and the template `src/talemate/prompts/templates/world/create-thing.jinja2`. Seed its wording from Task 3's findings.
- Create: `src/talemate/server/worlds.py`, a `Plugin` with `router = "worlds"`, registered in `WebsocketHandler.routes` (`websocket_server.py:61-90`).
- Test: `tests/worldplay/test_create.py`, `tests/server/test_worlds_plugin.py`

**Interfaces:**
- `class CreatePreview(BaseModel)`: `kind`, `prompt`, `fields: dict`, `name: str`, `facts: list[{category, text, since: WorldDate | None}]`, `prose: dict[section, str]`.
- `async def preview_thing(world, kind, prompt, fields, client) -> CreatePreview`:
  - calls `Prompt.request("world.create-thing", …)` with the kind's categories and the `@`-style instruction to treat the prompt as intent and invent plausible detail;
  - parses the JSON facts;
  - generates prose from the facts with `world/thing-prose`, without writing anything.
  - Kinds in the slice: `character`, `place`, `lore`.
- `def accept_preview(world, preview) -> str` writes one `Source.manual(note="created from prompt")` revision: `create_thing`, `add_fact`s, and `ProseCache.put` for the current stretch. It returns the thing id.
- **Router actions** (request `{type:"worlds", action, ...}`, reply `{type:"worlds", action, data}`):
  - `list_worlds`, `create_world {name}`, `open_world {path}`
  - `list_things {kind}`, `get_thing {id, at}`: returns fields, facts, prose, timeline and appears-in
  - `preview_thing {kind, prompt, fields}`, `accept_preview {preview}`
  - `add_fact`, `correct_fact`, `end_fact`, `set_field`: each followed by a background `ensure_prose` task that emits `prose_updated {id}`
  - `regenerate_prose {id, at}`

  The open world is held on the handler, one per connection.
- AI calls use the agent client the creator agent already uses, `instance.get_agent("creator").client`.

**Tests:**
- `test_preview_parses_facts` (MockClient)
- `test_preview_does_not_write` (Review Focus 4): `head_rev` doesn't change.
- `test_accept_writes_one_revision`
- `test_add_fact_schedules_prose`
- `test_router_list_and_get_thing`: through the plugin's `handle`, with a fake `websocket_handler.queue_put` collector.

- [ ] **Step 1: Write the tests;** expect FAIL.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Run the area's tests, then the full plain suite.**
- [ ] **Step 4: Commit** with `feat(worldplay): create things from a prompt; worlds websocket router`.

### Task 8: Scene setup, starting a scene and continuing one (backend)

**Files:**
- Create: `src/talemate/worldplay/setup.py` and the template `src/talemate/prompts/templates/world/scene-setup.jinja2`. Seed it from Task 3's findings.
- Modify: `src/talemate/server/worlds.py` (scene actions)
- Test: `tests/worldplay/test_setup.py`

**Interfaces:**
- `class NameMatch(BaseModel)`: `start: int`, `end: int`, `text: str`, `candidates: list[{id, name, kind}]` (best first).
- `def match_names(world, text, at) -> list[NameMatch]`:
  - case-insensitive whole-word matching against every thing's name at `at`;
  - also matches the first word of a multi-word name;
  - tries the longest name first, so overlapping matches are never doubled;
  - allows a trailing `'s`.
- `class SceneSetup(BaseModel)`:
  - `player: {thing_id | local}`;
  - `characters: list[{thing_id | local}]`, where a local entry is `{name, facts}`;
  - `place: {thing_id | local}`;
  - `start: WorldDate`, `goal: str`, `intro: str`;
  - `pulled_in: list[thing_id]`, `invented: list[str]`.
- `async def plan_scene(world, prompt, picks: dict[str, str], player: str | None, start: WorldDate | None, client) -> SceneSetup`:
  - `picks` maps a `NameMatch.text` to the chosen thing id.
  - It gives the LLM the prompt, the picked things rendered at the date, and the top `WorldIndex.query(prompt, at=start, n=8)` hits.
  - The template returns JSON (the shape used in the Task 2 probe), which it parses.
  - `start` defaults to `SceneStore.latest_end()`, or to `WorldDate.of(1)` when the world has no scenes.
  - **The index:** `WorldIndex(world, embedding_function=instance.get_agent("memory").embedding_function)`. Before querying, rebuild it when `built_rev()` is not `head_rev()`. Tests pass the deterministic fake embedding function from `tests/world/test_index.py`, moved into a shared helper under `tests/world/`.
- `async def start_scene(world, setup, client) -> str`:
  1. `ensure_prose` for the world characters at `start`;
  2. `SceneStore.create`, with the intro as the first narrator message, the goal, the player and `state.characters`/`place_thing_id`/`pulled_in`;
  3. `set_local_things` for the invented things.

  It returns the scene id.
- `async def continue_setup(world, scene_id, goal_prompt, client) -> SceneSetup`:
  - the start is the old scene's start plus its last `elapsed`;
  - it keeps the same place and the characters that were active;
  - the summary comes from the existing `SummarizeAgent.summarize_events` over that scene's history, and becomes part of the intro context;
  - it sets `continued_from`.
- **Router actions:**
  - `match_names {text, at}`
  - `plan_scene {prompt, picks, player, start}`
  - `start_scene {setup}`: replies with `world://…`, which the frontend then sends to `load_scene`
  - `list_scenes`
  - `continue_scene {scene_id, goal_prompt}`

**Tests:**
- `test_match_names_longest_and_possessive` (Review Focus 3): with things "Maren Vos" and "Maren Holt", "maren's boat" gives one match with both as candidates; "Maren Vos left" gives one match, "Maren Vos" first.
- `test_plan_scene_uses_picks_and_index` (MockClient returns setup JSON; the picked ids are present)
- `test_start_scene_writes_scene_and_intro`
- `test_continue_setup_carries_date_place_people`

- [ ] **Step 1: Write the tests;** expect FAIL.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Run the area's tests, then the full plain suite.**
- [ ] **Step 4: Commit** with `feat(worldplay): scene setup from a prompt; start and continue scenes`.

### Task 9: Frontend — the Worlds home, the World tab, thing pages and the create box

**Files:**
- Modify: `talemate_frontend/package.json` (add `pinia`) and `talemate_frontend/src/main.js` (`app.use(createPinia())`)
- Create: `talemate_frontend/src/stores/worlds.js`. It's a Pinia store: state `worlds`, `currentWorld`, `things[kind]`, `thing`, `preview` and `scenes`. Its actions send `worlds` router messages. One `registerMessageHandler`, hooked up from `TalemateApp.vue`, fills the state.
- Create in `talemate_frontend/src/components/worlds/`:
  - `WorldsHome.vue`: list and create worlds; open a world; that world's scenes with a Play button.
  - `WorldTab.vue`: the kind list (Characters, Places, Lore; Cultures shown disabled, "via skill"), the create box, and cards.
  - `CreateBox.vue`: the prompt and the optional field pickers (born, and the parent place for places). Create shows a preview, with Accept, Regenerate and Edit (edit the prompt and retry).
  - `ThingPage.vue`:
    - core fields;
    - dated facts with category tags and add, edit and end;
    - generated prose with Regenerate;
    - the "viewing as of" date picker;
    - the timeline strip;
    - appears-in.

  The layout follows the 2026-10-19 mockup.
- Modify `talemate_frontend/src/components/TalemateApp.vue`: add the tabs `worlds` (Worlds) and `fmworld` (World), since the value `world` is already taken by the World Editor. Make `worlds` the home after onboarding.
- Test: `tests/e2e/worlds/test_world_tab.py`. Add a seed helper to `tests/e2e/seed.py` that creates a world with things through `talemate.world`.

**Tests (e2e; the AI is mocked by seeding, so no generation happens in e2e):**
- `test_worlds_home_lists_and_opens`
- `test_thing_page_shows_facts_and_date_view`: switching the date hides a fact that starts later.
- `test_add_fact_updates_page`
- `test_create_box_preview_accept`: the backend's preview is stubbed through a test-only setting that makes `preview_thing` return a fixed preview. Add `TALEMATE_TEST_FIXED_PREVIEW` handling to the plugin, used only by e2e.

Then:
- [ ] **Step 1:** write the e2e tests and the seed helper, and run them; expect FAIL. `… pytest tests/e2e/worlds -m e2e -n0`
- [ ] **Step 2:** implement the store, the components and the tabs. Run the frontend checks (`npx --yes corepack@0.34.0 pnpm` lint/build from `talemate_frontend`).
- [ ] **Step 3:** the area's e2e tests pass. Run `grep -rn` over `tests/ai` for any selectors changed in TalemateApp's tabs. Run the full browser suite once (`-n 4`) and the full plain suite once.
- [ ] **Step 4:** commit with `feat(ui): Worlds home, World tab, thing pages and create-from-prompt`.

### Task 10: Frontend — the new-scene dialog, name highlighting, setup and continue

**Files:**
- Create in `talemate_frontend/src/components/worlds/`:
  - `NewSceneDialog.vue`:
    - the prompt editor with live highlighting from `match_names`, debounced by 300 ms;
    - blue for matched names, with a hover popover to pick another candidate or "treat as new";
    - the player and start pickers;
    - "Set up scene", which calls `plan_scene`;
    - the setup cards (Who, Where, When, Goal, Pulled in, Invented), with Start, Regenerate and Edit;
    - Start calls `start_scene`, then `load_scene` with the returned `world://` path.
  - `ContinueSceneButton.vue`: shown in the scene view for world scenes. It asks for the next goal, calls `continue_scene`, and then shows the same setup step.
- Modify: `stores/worlds.js` (scene actions), `WorldsHome.vue` (the New scene button), and the scene toolbar component (to mount the continue button for world scenes)
- Test: `tests/e2e/worlds/test_new_scene.py`, using `TALEMATE_TEST_FIXED_SETUP` handling like Task 9's.

**Tests:**
- `test_names_highlight_and_repick`: typing "Maren went…" highlights it, and the hover shows both Marens; picking the other one is sent in `picks`.
- `test_setup_then_start_loads_scene`: the scene opens, with the intro message and the world characters in the character list.
- `test_continue_scene_offers_setup`

Then:
- [ ] **Steps:** write the failing e2e tests, implement, run the area's tests, grep `tests/ai`, run the full browser suite (`-n 4`) and the plain suite once each, then commit with `feat(ui): new scene from a prompt with name highlighting; continue in a new scene`.

### Task 11: The slice end to end, with the mock model

**Files:**
- Test: `tests/worldplay/test_slice_end_to_end.py`

This is an automated mirror of the owner's acceptance tests, with `MockClient` responses queued:
1. Create a world. Accept a preview for "Maren", with a lost-left-eye fact from `WorldDate.of(314)`.
2. Set up and start scene A at 313. Play a `@` action turn through `conversation.converse(..., instruction=...)`. Assert that the conversation prompt recorded in `prompt_history` has **no** "eye" fact or since line.
3. Start scene B at 315. Assert that the conversation prompt **has** the eye information: either the prose was regenerated for the new stretch, or the since line is there.
4. Save scene B, reload it, and play one more turn. Assert that the prompt still holds the World instruction (goal and place).
5. Assert that the run made no LLM calls during turns beyond the turn generations themselves. Count the `prompt_history` entries by `kind`.

- [ ] **Step 1: Write the test;** it should pass on the finished slice. If it fails, the fix goes in the task that owns that code, recorded in the ledger.
- [ ] **Step 2: Run the full plain suite once.**
- [ ] **Step 3: Commit** with `test(worldplay): slice end to end with the mock model`.

### Task 12: The owner's acceptance run (owner-gated)

- [ ] **Step 1:** Ask the owner to run acceptance tests 1–3 from the slice design on their model, with a stock upstream install as the baseline. Offer `scripts/dev/talemate_app.py start` for the fantasymate side.
- [ ] **Step 2:** Record their findings in `docs/superpowers/probes/2026-10-19-slice-acceptance.md`, along with the AI-handoff changes they lead to, which go in follow-up tasks.
