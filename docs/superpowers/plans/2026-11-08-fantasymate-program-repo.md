# Fantasymate program repo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `~/Projects/fantasymate/fantasymate`, a fresh repo that does everything the fork's worlds and languages features do today. It has no node system, no Talemate agents, no scenes and no Talemate baggage, and fantasymate names throughout.

**Architecture:** A subtractive port *(my call)*. The repo starts as an exact copy of the fork's tracked files at the frozen commit, which is green on day one. Each task then removes one layer or replaces one seam, and the plain suite, frontend checks and e2e stay green after every task. Renaming the package comes late, once there's far less code to rename. This was chosen over an additive copy that chases imports because the carried code (`world`, `languages`, `worldplay`) hardly imports Talemate, while the client layer and prompts are tangled with agents and scenes. Removing things with the tests running shows each tangle as it appears.

**Tech Stack:** Python 3.11 (uv, pytest with xdist, pydantic, structlog), Vue 3 + Vuetify + Pinia (pnpm, vite), Playwright e2e, SQLite, Guix (`manifest.scm`).

**Spec:** `docs/superpowers/specs/2026-11-07-fantasymate-vision-and-fresh-start-design.md` (in the fork, `~/Projects/Web/talemate`; also copied into `~/Projects/fantasymate/docs/specs/`), section "Project 2: the program repo".

## Global Constraints

- New repo: `~/Projects/fantasymate/fantasymate`, fresh git history. The first commit message names the source: `Import from AndSnowl/talemate at <sha>`.
- The fork is frozen from Task 1 on. Nothing new lands on its main. Fixes go into the new repo.
- The new app starts empty. On-disk formats (world DB schema, folder layout, `.language.json`, config keys) may change freely. No migration code.
- Fantasymate names everywhere. The only "talemate" left is the credit in `NOTICE` and `README.md`. License stays AGPL-3.0.
- Dev environment: every command runs as `guix shell -m manifest.scm -- uv run --no-sync …` from the repo root (`docs/dev/local-testing.md`).
- Tests:
  - plain suite: `guix shell -m manifest.scm -- uv run --no-sync pytest -q`, about 40 s;
  - frontend checks: `tests/dev/test_frontend_checks.py`;
  - e2e: `pytest -m e2e -n 4`, at most 4 workers, about 3.5 min. Run it once per task, at the end.
- **Never** run `tests/ai` or `start --ai` without asking the owner and naming the loaded koboldcpp model. A Claude Code language run also needs the owner's go-ahead, because it spends their Claude usage.
- The dev app runner wipes a root it made on `start`. That's harmless here, since all worlds are test data.
- Commit trailer lines as given in the session's attribution reminder.

## Review Focus

1. **A fresh install with no `config.yaml` and no clients.** The backend starts and the Worlds home shows. A world AI action (Make from a prompt) fails with a readable "no client is set for the world agent" error in the world's error bar, not a traceback or a hung spinner. Tested in Task 3.
2. **The Claude Code language route after the rename.** `SKILL_SOURCE` resolves to `<repo>/.claude/skills/language-design`, and the scratch folder's check command runs `python -m fantasymate.languages`. A stale `talemate.languages` would fail only on a real run, after minutes of waiting. Tested in Task 6.
3. **The AI-test opt-in guard survives the rename.** `fantasymate_app.py start --ai` refuses without `FANTASYMATE_AI_TESTS=1`, and `tests/ai` skips without it. Tested in Task 6.
4. **A stale browser tab** that still sends removed websocket types (`scene_*`, `node_editor`, `tts`, `visual`). The backend logs the unknown type and keeps the connection open. Tested in Task 4.
5. **Worlds survive a backend restart in the new data folder:** `WORLDS_DIR == FANTASYMATE_ROOT / "worlds"`, and a world created, then reloaded after a restart, is still there. Tested in Task 6.

---

### Task 1: Bootstrap the repo from the frozen fork

**Files:**
- Create: `~/Projects/fantasymate/fantasymate/` (the whole tree)

**Interfaces:**
- Produces: a repo identical to the fork's tracked files at `<sha>`, plus `BASELINE.md` (temporary, deleted in Task 7) recording the baseline test counts.

- [ ] **Step 1:** In the fork, record `git rev-parse HEAD` as `<sha>` and check `git status --porcelain` for tracked changes. Expect none; if there are any, stop and ask the owner.
- [ ] **Step 2:** `mkdir -p ~/Projects/fantasymate/fantasymate && git -C ~/Projects/Web/talemate archive <sha> | tar -x -C ~/Projects/fantasymate/fantasymate`. This takes tracked files only: no `.worktrees/`, `feedback/`, `.superpowers/` or `docs/ideas/`.
- [ ] **Step 3:** Set up with `uv sync --extra dev` and the pnpm install from `docs/dev/local-testing.md` "One-time setup".
- [ ] **Step 4: Baseline.**
  - Run the plain suite. Expect 0 failures.
  - Run the frontend checks. Expect PASS.
  - Run e2e with `-n 4`. Expect 0 failures.

  Write the pass counts to `BASELINE.md`. A failure here is a fork problem: stop and report it, don't fix it.
- [ ] **Step 5:** `git init`, add everything, and commit with `Import from AndSnowl/talemate at <sha>`.

### Task 2: Remove the baggage

**Files** (deleting each one's tests with it):
- Delete:
  - `src/talemate/agents/tts/`, `tts/`, `src/talemate/server/tts.py`
  - `src/talemate/agents/visual/`, `src/talemate/scene_assets.py`, `src/talemate/server/scene_assets*.py`, `templates/comfyui-workflows/`
  - `src/talemate/load/character_card.py`, `src/talemate/server/character_importer.py`
  - `src/talemate/agents/help/`, `src/talemate/server/assistant.py`, `src/talemate/server/package_manager.py`
  - `Dockerfile`, `docker-compose*.yml`, `docker-entrypoint.sh`, `install*.{sh,bat}`, `install-utils/`, `start*.{sh,bat}`, `update.{sh,bat}`, `frontend_wsgi.py`, `tests/test_docker_compose.py`
  - the empty `src/talemate/cultures/` and `src/talemate/agents/culture/`, and `tests/cultures`, `tests/e2e/cultures` if they test nothing that still exists
- Modify: whatever imports them. Typical spots are `client/base.py` (its TTS and visual imports), `server/websocket_server.py` routes, `config/schema.py`, `instance.py`, message rendering.
- Frontend delete: Voice*/TTS*/Audio*, Visual*/Cover*/Asset*, CharacterCardImport/CharacterImporter, HelpChat, PackageManager*, Templates*, OnboardingWizard, WhatsNew, plus their mounts in `TalemateApp.vue`.

- [ ] **Step 1:** Delete them and fix the imports until `python -c "import talemate.server.run"` succeeds and `pytest --collect-only -q` collects with no errors.
- [ ] **Step 2:** Run the plain suite and the frontend checks. Expect 0 failures. Every count drop must match tests deleted on purpose; note the drops in the commit message.
- [ ] **Step 3:** Run e2e (`-n 4`). Expect 0 failures.
- [ ] **Step 4:** Commit with "remove TTS, images, character cards, help, packages, installers".

### Task 3: The AI seam: a world agent, and clients that don't need a scene

**Files:**
- Create: `src/talemate/agents/world/__init__.py`, a minimal `Agent` subclass with `agent_type = "world"`, `verbose_name = "World"`, holding only a client. It is the creative model for drafts, prose and decisions.
- Modify: `src/talemate/worldplay/ai.py`. `world_ai_call()` makes `instance.get_agent("world")` active, not `"creator"`. Delete `_WorldAgent`.
- Modify: `src/talemate/server/worlds.py`. Every `instance.get_agent("creator").client` becomes `"world"`.
- Modify: `src/talemate/client/context.py` and `client/base.py`. `requires_active_scene` defaults to `False`. The cancel polling and the scene reads in `base.py` run only when a scene is active, and become no-ops otherwise.
- Test: `tests/worldplay/test_world_ai.py` (create or extend), `tests/test_client_base.py`

**Interfaces:**
- Produces:
  - `world_ai_call() -> ContextManager[None]`, with the same name and use as today;
  - the agent name `"world"` in `config.yaml` (`agents: {world: {client: <name>}, language: {...}}`);
  - `NoWorldClient(Exception)` in `worldplay/ai.py`, raised when the world agent has no client. Its message: `"No client is set for the world agent. Pick one in Settings → Agents."`

- [ ] **Step 1: Write the failing tests.**
  - `test_world_ai_call_uses_world_agent`: inside `world_ai_call()`, `active_agent.get().agent.agent_type == "world"`.
  - `test_world_ai_call_without_client_raises`: with no client on the world agent, entering the call raises `NoWorldClient` with the message above.
  - `test_send_prompt_without_scene`: a stub `ClientBase` subclass sends with no `active_scene` set and no `ClientContext`, and returns the stub's reply.
  - Server test `test_preview_without_world_client_reports_error`: the worlds router's preview handler answers with an error payload carrying that message, not an exception.
- [ ] **Step 2:** Run them and expect FAIL: there's no world agent yet, and the scene is required.
- [ ] **Step 3:** Implement as in Files. The frontend's world error bar already shows router errors; check it shows this one.
- [ ] **Step 4:** Run the new tests, the plain suite and the frontend checks. Expect all to PASS.
- [ ] **Step 5:** Commit with "world agent; clients run without a scene".

### Task 4: Remove the scene stack and the node system (backend)

**Files:**
- Delete:
  - `src/talemate/game/` (the node engine, `scene_loop.py`, `focal/`);
  - every agent in `src/talemate/agents/` except `base.py`, `context.py`, `registry.py` (or equivalent), `world/` and `language/`;
  - `tale_mate.py`, `scene_message.py`, `history.py`, `world_state/`, `load/`, `save.py`, `export.py`, `regenerate.py`, `commands/`, `scene_agent_settings.py`, `shared_context.py`, `character.py`, `status.py` (if only scenes use it), `thematic_generators.py`;
  - `server/` handlers other than the websocket shell, `api.py`, `config.py`, `agent_config.py`, `quick_settings.py` (if it doesn't touch scenes), `ux.py`, `prompts.py`, `devtools.py` (prompt log only), `worlds.py`, `world_drafts.py`;
  - `scenes/`, and `templates/` except what `world` templates include;
  - `src/talemate/prompts/templates/*` except `world/` and `common/`;
  - `worldplay/characters.py`, `context.py`, `setup.py`, `persistence.py`; `world/scenes.py` unless the store's schema needs it; `world/index.py` (the chromadb index, used only by scene setup) and the `chromadb` dependency if nothing else needs it;
  - the tests of everything deleted.
- Move: `DEPARTS_FROM`, `DEPARTS_FROM_TEACHING` and `age_in_years` from `worldplay/characters.py` into `worldplay/people.py`. Update the imports in `create.py` and `server/worlds.py`.
- Modify:
  - `agents/base.py`: drop `GraphState`, `FunctionWrapper`, the node registry and every `active_scene` use. Keep config, actions and the client binding.
  - `prompts/base.py`: drop the imports of `tale_mate`, `agents.editor`, `agents.summarize` and `thematic_generators`. Template functions that only scenes used go too.
  - `server/worlds.py`: remove the scene handlers (scene setup, continue, new scene, scene start date) and the `world://` load target.
  - `server/websocket_server.py`: keep only the routes that remain. An unknown `type` logs `unknown_message_type` at warning and is ignored.
  - `config/schema.py`: drop `Game`, `WorldState`, `CreatorConfig` and any agent config for deleted agents. Pydantic must ignore unknown keys in an old `config.yaml` (`extra="ignore"`).
  - `instance.py`: register only the `world` and `language` agents.
- Test: `tests/server/test_websocket_unknown_type.py`

**Interfaces:**
- Consumes: Task 3's `"world"` agent.
- Produces: a backend with no `active_scene` references (`grep -rn active_scene src/` is empty) and no `game.engine` imports.

- [ ] **Step 1: Write the failing test.** `test_unknown_message_type_is_ignored`: send `{"type": "scene_message", "action": "x"}` and then a valid `worlds` list request over a test websocket connection. The second gets its normal reply, and the log has `unknown_message_type`.
- [ ] **Step 2:** Run it. Expect FAIL, or PASS for the wrong reason if `scene_message` still exists. If it passes, re-run it after the deletions.
- [ ] **Step 3:** Delete and modify as listed. Iterate on `python -c "import talemate.server.run"`, `pytest --collect-only -q` and the area tests.
- [ ] **Step 4: Verify.**
  - `grep -rn "active_scene\|game.engine\|tale_mate" src/` → no hits.
  - The plain suite passes with 0 failures, and the drops match the deleted tests.
  - Frontend checks pass.
  - e2e may fail only in the scene tests that Task 5 removes. List them in the commit message.
- [ ] **Step 5:** Commit with "remove the node system, Talemate agents and the scene stack".

### Task 5: The frontend shell

**Files:**
- Create: `talemate_frontend/src/components/AppShell.vue`, replacing `TalemateApp.vue`. It holds:
  - the websocket connection and the `provide` of `getWebsocket` and `registerMessageHandler`, with the same names, so the worlds components don't change;
  - the theme apply;
  - the wordmark header;
  - two tabs, Worlds (`WorldsHome`, then `WorldTab` when a world is open, with `WorldError` pinned) and Settings;
  - the client list with `ClientModal`;
  - the agent settings (`AIAgent`, `AgentModal`) for the world and language agents;
  - the status, rate-limit, auto-retry, generation-error and version-mismatch alerts;
  - the prompt log debug view *(my call: it's the main tool for tuning prompts)*.
- Modify: `App.vue` mounts `AppShell`.
- Delete:
  - `TalemateApp.vue` and Scene*, Message*, CharacterMessage, Director*, WorldState*, WorldStateManager*, NodeEditor*, the litegraph/graph utils, SceneTimeline, AgentActivityBar, the other DebugTool* views, AppSettingsGameplay, AppSettingsPlayerCharacter, AppConfigAppearanceScene;
  - in `components/worlds/`: `ContinueSceneButton`, `NewSceneDialog`, `SceneSetupCards`, `SceneStartDate`, `WorldSceneTools`, and their uses in `WorldTab`, `WorldsHome` and `stores/worlds.js`;
  - frontend dependencies only those deleted files used (litegraph and similar). Run `pnpm install` after.
- Test: e2e under `tests/e2e/worlds/` and `tests/e2e/theme/`. Delete the scene e2e tests. Add `tests/e2e/test_app_shell.py`.

- [ ] **Step 1: Write the failing e2e test.** `test_shell_has_worlds_and_settings_only`: the top bar's tabs are exactly Worlds and Settings, with no scene, director or node editor controls. Also `test_world_page_has_no_scene_tools`: an open world shows no New scene, Continue or scene setup cards.
- [ ] **Step 2:** Run it and expect FAIL.
- [ ] **Step 3:** Build `AppShell.vue` and delete the rest. Follow the UI rules (controls sit by their content; same look means one component). Screenshot the Worlds home, a world page and Settings at 1920×1080 and look at them.
- [ ] **Step 4:** Run the frontend checks, then e2e (`-n 4`). Expect 0 failures, with drops only in deleted scene tests.
- [ ] **Step 5:** Commit with "new app shell; scene UI removed".

### Task 6: Rename to fantasymate

**Files:**
- Rename:
  - `src/talemate/` → `src/fantasymate/`
  - `talemate_frontend/` → `frontend/`
  - `scripts/dev/talemate_app.py` → `fantasymate_app.py`, `talemate_ws.py` → `fantasymate_ws.py`
- Modify:
  - every `talemate` import and string;
  - `pyproject.toml` (`name = "fantasymate"`, `version = "0.1.0"`, authors, the coverage source, scripts);
  - `frontend/package.json` name;
  - every `TALEMATE_*` environment variable → `FANTASYMATE_*`;
  - `path.py` (`TALEMATE_ROOT` → `FANTASYMATE_ROOT`; drop `SCENES_DIR`, `TTS_DIR`; keep `WORLDS_DIR`, `LOGS_DIR`, `CONFIG_FILE`, `TEMPLATES_DIR` if still used);
  - structlog logger names;
  - websocket `type` strings that say talemate;
  - the pytest markers' text;
  - `manifest.scm` comments.
- Test: `tests/test_paths.py`, `tests/languages/test_claude_code_paths.py`, `tests/dev/test_app_runner_guard.py` (create or extend existing)

**Interfaces:**
- Produces: the package `fantasymate`; `fantasymate.path.FANTASYMATE_ROOT`, `WORLDS_DIR`; the env vars `FANTASYMATE_AI_TESTS` and `FANTASYMATE_TEST_*`.

- [ ] **Step 1: Write the failing tests.**
  - `test_worlds_dir_under_root`: `WORLDS_DIR == FANTASYMATE_ROOT / "worlds"`.
  - `test_skill_source_exists`: `fantasymate.languages.claude_code.SKILL_SOURCE == FANTASYMATE_ROOT / ".claude/skills/language-design"`, and it holds `SKILL.md`.
  - `test_check_command_module`: the check command written into the scratch folder contains `-m fantasymate.languages` and runs `--help` with exit 0.
  - `test_ai_start_refuses_without_opt_in`: `fantasymate_app.py start --ai` exits non-zero with "AI runs need FANTASYMATE_AI_TESTS=1 — ask the owner first".
  - e2e `test_world_survives_restart`: create a world, restart the backend with the runner's `_launch` (not `start`, which wipes the root), reload, and the world is listed.
- [ ] **Step 2:** Run them and expect FAIL (no such module).
- [ ] **Step 3:** Do the rename as one mechanical sweep: `git mv`, then `sed` over `*.py *.js *.vue *.json *.toml *.yaml *.md *.jinja2 *.scm`. Then fix the stragglers by hand.
- [ ] **Step 4: Verify.**
  - `grep -rli talemate . --exclude-dir={.git,node_modules,.venv}` returns only the files Task 7 replaces or deletes: `README.md`, `docs/` outside `docs/dev/`, `CHANGELOG.*`, `mkdocs.yml`.
  - Plain suite, frontend checks and e2e all pass with 0 failures.
- [ ] **Step 5:** Commit with "rename to fantasymate".

### Task 7: Split the worlds router, then docs and license

**Files:**
- Create: `src/fantasymate/server/worlds/` as a package, replacing the 7k-line `worlds.py` and `world_drafts.py`. Split it by area, keeping each module under about 1.2k lines, with one `Plugin` routing to them. Expected areas: `worlds` (list/create/open/delete), `entries`, `drafts`, `facts`, `tags` (filing), `calendar`, `languages`, `naming`, `merge`.
- Modify: imports in `tests/server/test_worlds_*`. The websocket actions and payloads stay byte-identical.
- Create:
  - `README.md`: what fantasymate is, two paragraphs from the vision; how to run it (Guix); credit "Derived from Talemate (https://github.com/vegu-ai/talemate), AGPL-3.0";
  - `NOTICE`: the same credit.
- Keep and update: `docs/dev/local-testing.md` and `docs/dev/dev-loop-optimizations.md`, with the new names and Talemate-only sections removed.
- Delete: `mkdocs.yml`, `docs/` except `docs/dev/` (the user guide, img and snippets are Talemate's), `CHANGELOG.*`, `src/fantasymate/changelog.py` if nothing world-side uses it, `docs/dev/nodes-glossary.md`, `docs/dev/agents/`, `templates.md`, `BASELINE.md`, and probe scripts in `scripts/dev/` that import deleted modules.

- [ ] **Step 1:** Split the router. Run `tests/server` after each module moves; expect PASS throughout.
- [ ] **Step 2:** Write the docs, delete the rest, and run the Task 6 grep again. Expect only `NOTICE` and `README.md`.
- [ ] **Step 3:** Run the plain suite, frontend checks and e2e. Expect 0 failures.
- [ ] **Step 4:** Commit with "split worlds router; README, NOTICE, dev docs".

### Task 8: Owner acceptance, push, and the move

- [ ] **Step 1:** Run the final whole-branch review (see the execution skill).
- [ ] **Step 2:** Start a fresh app with `fantasymate_app.py start`. Hand the owner the URL and a checklist to walk through, by eye:
  - make a world;
  - each entry kind, drafts, + Add facts, group adds;
  - Name it, people's names;
  - make, change, import and export a language;
  - tags and filings, calendar, merge;
  - the theme switch.

  Ask the owner before any koboldcpp or Claude Code run.
- [ ] **Step 3:** Fix what the owner finds, one commit per fix, and run the suites each round.
- [ ] **Step 4:** On approval, ask for the GitHub repo names and visibility for both repos, then create and push only when they say so.
- [ ] **Step 5:** Moving the fork is the last step, at the end of a session, on the owner's go:
  1. Stop the test app in `.worktrees/languages-4b2`.
  2. Ask the owner which worktrees to keep, and remove the rest.
  3. `mv ~/Projects/Web/talemate ~/Projects/fantasymate/talemate`.
  4. `git worktree repair`.
  5. Copy the memories that still apply into the new projects' memory folders, with their paths updated.
