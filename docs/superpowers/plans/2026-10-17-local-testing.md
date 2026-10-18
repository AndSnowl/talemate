# Local App Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Claude start Talemate locally in isolation, drive its frontend in a headless browser, run separated browser and AI test groups, with the AI group pointed at the GPU server's koboldcpp. Also let the owner deploy a named branch to the GPU server.

**Architecture:**
- **Runner.** A Python runner (`scripts/dev/talemate_app.py`) copies the working tree into a temporary root, so uncommitted changes are included. It symlinks `.venv` and `talemate_frontend/node_modules` into the copy and writes a config for that run. It then starts the backend and the vite dev server from the copy. `PYTHONPATH=<copy>/src` makes the copy's `talemate` package shadow the editable install, so `TALEMATE_ROOT` (and with it config, scenes and logs) resolves inside the copy.
- **Tests.** Pytest markers `e2e` and `ai`, deselected by default, mark the browser and AI groups. Their fixtures drive Guix's ungoogled-chromium through Playwright, reusing rootmap's pattern.
- **Branch deploys.** In the `home` repo, a branch file that `install.sh` creates (writable by the admin login, readable by the service) carries the requested branch to `talemate-update`. `sudoers-talemate` stays restart-only.

**Tech Stack:**
- Python 3.11, pytest (+xdist) and Playwright (sync API), run through uv
- Vue 3 / vite (pnpm via corepack)
- Guix manifests
- bash and systemd (`home` repo)

**Spec:** `docs/superpowers/specs/2026-10-17-local-testing-design.md`. Read it fully first.

**Repos and branches:**
- Tasks 1–8 are in this repo (`~/Projects/Web/talemate`), on branch `feature/local-testing`, created from `main`.
- Tasks 9–10 are in `~/Projects/Web/home`, on branch `feature/talemate-branch-deploy`, created from `master`.

## Global Constraints

- **Running commands.** Every Python and Node command runs inside Guix. After Task 1: `guix shell -m manifest.scm -- <cmd>`. Before that: `guix shell uv node python@3.11 -- <cmd>`.
  - Always use `uv run --no-sync`, and never a plain `uv run`.
  - Run pnpm as `npx --yes corepack@0.34.0 pnpm`.
- **Checkout data.** A test run never writes to the checkout's `config.yaml`, `scenes/`, `logs/`, `chroma/`, `templates/` or `tts/`, nor to any file outside the run's temporary root and `.test-artifacts/`.
- **The plain suite.** `uv run --no-sync pytest` (no `-m`) runs neither `e2e` nor `ai` tests, needs no network or browser, and keeps today's result: only the 141 pre-existing NLTK failures.
- **AI tests are opt-in twice.** They need both `-m ai` and the environment variable `TALEMATE_AI_TESTS=1`, and skip otherwise. An implementer never runs them; the controller asks the owner first.
- **The koboldcpp address** defaults to `http://192.168.0.5:5001`, overridable with `TALEMATE_TEST_KOBOLDCPP_URL`. The client config is type `koboldcpp`, name `KoboldCpp`, `max_token_length: 16384`.
- **Waits.** No fixed `sleep`s in tests or the runner. Wait on conditions, with timeouts.
- **Branch names** accepted by the server: `^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$`, without `..`. Anything else falls back to `main` with a logged warning.
- **sudoers.** `sudoers-talemate` is unchanged, byte for byte.
- **Commit attribution.** Commit messages end with the Co-Authored-By trailer from the implementer's own session reminder.

## Review Focus

The cases a person is most likely to hit that no task's main tests cover. Each one has its test in the owning task.

1. **A run that crashes or is killed.** The next `start` must not reuse stale ports or PIDs, and `stop` must not kill unrelated processes. Covered in Task 2 by `test_stop_ignores_pid_not_started_by_runner` and `test_start_replaces_stale_state`.
2. **Port already in use.** Free ports are picked at start, and a port clash gives a clear error, not a hang. Task 2: `test_explicit_busy_port_errors_fast`.
3. **Uncommitted edits must be what's tested.** Task 2: `test_copy_includes_uncommitted_and_untracked_files_but_not_ignored`.
4. **A backend that fails to start** (for example a syntax error) must surface the error quickly with the log's tail, not after a long silent timeout. Task 2: `test_start_reports_backend_crash_with_log_tail`.
5. **A branch file holding garbage or a hostile name** (`../x`, `main;rm`, empty, CRLF). The server falls back to `main`. Task 9: `test_update_rejects_bad_branch_names`.

---

### Task 1: Guix manifest, Playwright and test-group markers

**Files:**
- Create: `manifest.scm`
- Modify: `pyproject.toml` (add `playwright>=1.40` to `[project.optional-dependencies].dev`; add markers; change `addopts`) and `uv.lock` (regenerated)
- Create: `tests/e2e/__init__.py`, `tests/e2e/conftest.py`, `tests/e2e/test_browser_smoke.py`
- Create: `tests/ai/__init__.py`, `tests/ai/conftest.py`
- Modify: `.gitignore` (add `.test-artifacts/`)

**Interfaces:**
- Produces, in `tests/e2e/conftest.py`:
  - `chromium_path() -> str`, a session fixture: `TALEMATE_CHROMIUM`, else `shutil.which("chromium")`, else `pytest.skip("No Chromium — run inside guix shell -m manifest.scm")`.
  - `browser`, a session fixture: Playwright sync Chromium launched with `executable_path=chromium_path`, `args=["--no-sandbox","--disable-dev-shm-usage"]`.
  - `ensure_driver_node()`: rootmap's fix, which symlinks `.venv/lib/python*/site-packages/playwright/driver/node` to the Guix `node` when the bundled one can't run.
- Markers: `e2e` (browser, no AI) and `ai` (calls koboldcpp). Every test under `tests/e2e/` is marked `e2e` automatically, and every test under `tests/ai/` is marked `ai`, by `pytest_collection_modifyitems` in each folder's conftest.
- `addopts` becomes `-n auto --dist worksteal -m "not e2e and not ai"`. Commands for the groups:
  - browser tests: `pytest tests/e2e -m e2e -n0`
  - AI tests: `TALEMATE_AI_TESTS=1 pytest tests/ai -m ai -n0`
- In `tests/ai/conftest.py`, an autouse fixture skips with "AI tests need TALEMATE_AI_TESTS=1 (ask the owner first)" unless that variable is `1`.

- [ ] **Step 1: Write `manifest.scm`.** Packages: `uv`, `python@3.11`, `node`, `ruff`, `ungoogled-chromium`, `nss-certs`, `font-dejavu`. Add a header comment explaining why each is there, as rootmap's does.
- [ ] **Step 2: Add Playwright to the dev extra and refresh the lock.** Run `guix shell -m manifest.scm -- sh -c 'uv lock && uv sync --extra dev'`. Expected: `playwright` is installed, and `uv.lock` changes only by Playwright and its dependencies (check `git diff --stat uv.lock`; no other package versions move).
- [ ] **Step 3: Write `tests/e2e/test_browser_smoke.py::test_browser_renders_a_data_url`.** It opens `data:text/html,<h1 id=t>ok</h1>`, then asserts `page.locator("#t").inner_text() == "ok"` and that `page.screenshot()` returns non-empty bytes.
- [ ] **Step 4: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e -m e2e -n0 -v`. Expected first: FAIL or ERROR (no fixtures yet). After writing the conftests and markers: 1 passed.
- [ ] **Step 5: Run the plain suite** with `guix shell -m manifest.scm -- uv run --no-sync pytest -q`. Expected: the smoke test is deselected, and the failures are the same 141 NLTK ones (no new ones). Also run without a browser: `guix shell uv python@3.11 -- uv run --no-sync pytest tests/e2e -m e2e -n0` must skip, not fail.
- [ ] **Step 6: Commit** with message `test: add Guix manifest, Playwright and e2e/ai test groups`.

---

### Task 2: Isolated local app runner

**Files:**
- Create: `scripts/dev/talemate_app.py`, `scripts/dev/test_config.example.yaml`
- Test: `tests/dev/test_talemate_app.py` (conventional, no browser) and `tests/e2e/test_runner.py` (e2e)

**Interfaces** (all in `scripts/dev/talemate_app.py`; importable as a module and run as `python scripts/dev/talemate_app.py start|stop|status [--ai] [--root DIR] [--backend-port N] [--frontend-port N]`):
- `copy_tree(src: Path, dest: Path) -> list[str]`
  - Copies `git -C src ls-files -z --cached --others --exclude-standard`, minus deleted files, into `dest`.
  - Symlinks `dest/.venv` → `src/.venv` and `dest/talemate_frontend/node_modules` → `src/talemate_frontend/node_modules`.
  - Returns the copied relative paths.
- `render_config(ai: bool, koboldcpp_url: str) -> str`
  - Returns YAML text based on `config.example.yaml`.
  - With `ai=False`: `clients: {}`.
  - With `ai=True`: exactly one client, `KoboldCpp: {type: koboldcpp, name: KoboldCpp, api_url: <url>, max_token_length: 16384}`.
- `start(root: Path | None = None, ai: bool = False, backend_port: int | None = None, frontend_port: int | None = None, timeout: float = 180) -> AppInfo`
- `stop(root: Path | None = None) -> None`
- `status(root: Path | None = None) -> AppInfo | None`
- `AppInfo` is a dataclass: `root: Path, backend_port: int, frontend_port: int, backend_pid: int, frontend_pid: int, frontend_url: str, backend_ws_url: str, log_dir: Path`.
- **State file.** `<root>/.talemate-app.json`. The default root is `$TMPDIR/talemate-app` (or the scratchpad when `CLAUDE_SCRATCHPAD` is set).
- **How the backend starts.**
  - Command: `uv run --no-sync python src/talemate/server/run.py runserver --host 127.0.0.1 --port <bp> --backend-only`.
  - Working directory: the copy.
  - Environment: `PYTHONPATH=<copy>/src`.
  - Output goes to `<root>/logs/backend.log`.
- **How the frontend starts.**
  - Command: `npx --yes corepack@0.34.0 pnpm run serve --host 127.0.0.1 --port <fp>`.
  - Working directory: `<copy>/talemate_frontend`.
  - Environment: `VITE_TALEMATE_BACKEND_WEBSOCKET_URL=ws://127.0.0.1:<bp>` and `COREPACK_ENABLE_DOWNLOAD_PROMPT=0`.
  - Output goes to `<root>/logs/frontend.log`.
- **Readiness.** The app is ready when a websocket handshake to `ws://127.0.0.1:<bp>/ws` succeeds and the frontend's HTTP GET `/` returns 200. Check the backend's actual websocket path in `src/talemate/server/run.py`. Both checks poll with short timeouts. If a child process exits before the app is ready, raise `AppStartError` with the last 40 lines of its log.
- **Stopping.** Each child runs in its own process group (`start_new_session=True`). `stop` sends SIGTERM to the group, then SIGKILL after 10 s. It only signals PIDs whose `/proc/<pid>/cmdline` still contains the copy's path, so a reused PID is never killed.

- [ ] **Step 1: Write the conventional tests** in `tests/dev/test_talemate_app.py`:
  - `test_copy_includes_uncommitted_and_untracked_files_but_not_ignored`: in a temp git repo, a committed file, a modified tracked file, an untracked file and an ignored `config.yaml` → the copy has the first three with their current contents and no `config.yaml`.
  - `test_copy_symlinks_venv_and_node_modules`
  - `test_render_config_without_ai_has_no_clients`
  - `test_render_config_with_ai_has_only_koboldcpp`: asserts the exact client dict above, and that the URL override is used.
  - `test_stop_ignores_pid_not_started_by_runner`: the state file points at a PID whose cmdline lacks the root path → `stop` doesn't signal it. Use a real `sleep` subprocess started outside the root, and assert it's still alive.
  - `test_start_replaces_stale_state`: a state file with dead PIDs → `status` returns None and the stale file is removed.
  - `test_explicit_busy_port_errors_fast`: bind a port, then `start(backend_port=that)` raises `AppStartError` mentioning the port within 5 s. Monkeypatch the process launch so this stays a unit test.
  - `test_start_reports_backend_crash_with_log_tail`: monkeypatch the backend command to `python -c "import sys; print('boom'); sys.exit(3)"` → `AppStartError` contains `boom`.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/dev -n0 -v`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement `scripts/dev/talemate_app.py`** per the Interfaces block, using `importlib` or a `sys.path` insert so the tests can import it. Use the `websockets` package, already a dependency, for the handshake check, and `httpx` or `urllib` for the HTTP check.
- [ ] **Step 4: Run the conventional tests again.** Expected: 8 passed.
- [ ] **Step 5: Write the e2e test** `tests/e2e/test_runner.py::test_runner_starts_isolated_app`:
  - `start()` into `tmp_path`.
  - Assert that `<copy>/config.yaml` exists and that the checkout's `config.yaml` and `scenes/` mtimes and contents are unchanged.
  - Assert that the frontend URL loads in the browser with the Talemate app bar (the `v-app-bar` element) visible.
  - Assert that `<copy>/logs/backend.log` mentions the copy's path, proving `TALEMATE_ROOT` resolved to the copy. If the log doesn't print it, add one `log.info("talemate root", path=...)` line at server start: a one-line edit to `src/talemate/server/run.py`.
  - `stop()`, then assert that both PIDs are gone.
- [ ] **Step 6: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e/test_runner.py -m e2e -n0 -v`. Expected: PASS.
- [ ] **Step 7: Commit** with message `test: isolated local Talemate runner`.

---

### Task 3: E2E fixtures, world seeding, quick-look tool, failure artifacts

**Files:**
- Modify: `tests/e2e/conftest.py`
- Create: `tests/e2e/seed.py`, `scripts/dev/look.py`
- Test: `tests/e2e/test_fixtures.py`

**Interfaces:**
- `app`: a session fixture, `talemate_app.start(root=tmp_path_factory.mktemp("app"))`. Yields `AppInfo` and stops it in `finally`.
- `page`: a function fixture. A new browser context and page on `app.frontend_url`. It collects console messages of type `error` into `page.console_errors: list[str]`.
- **Failure artifacts.** On test failure, a `pytest_runtest_makereport` hook saves a full-page screenshot and the backend log's tail to `.test-artifacts/<YYYYmmdd-HHMMSS>/<test-name>/`.
- In `tests/e2e/seed.py`:
  - `seed_world(root: Path, project: str = "e2e-world", context: str = "world") -> SeededWorld` creates a minimal scene file linked to a Shared World context under `<root>/scenes/<project>/`. `SeededWorld` is a dataclass with fields `scene_path: Path, shared_context_path: Path, world_dir: Path`; `world_dir` is the cultures `<context>.world/` folder.
    - Build the files with Talemate's own classes in a subprocess that runs with `PYTHONPATH=<copy>/src`: create a `Scene`, a `SharedContext` and `save`. Don't hand-write JSON that might drift.
  - `seed_scene_without_world(root, project="e2e-plain") -> Path`
  - `place_culture(world: SeededWorld, culture_file: Path) -> None`: imports a culture file through `talemate.cultures.exchange.apply_import` into `world.world_dir`.
  - `open_scene(page, scene_path: Path) -> None` loads the scene in the UI the way the app's Load Scene path does (the websocket `load_scene` action, see `src/talemate/server/websocket_server.py` near line 203), then waits until the scene title is shown.
- `scripts/dev/look.py`:
  - Usage: `look.py URL [--click SELECTOR]... [--fill SELECTOR=TEXT]... [--wait SELECTOR] --shot OUT.png [--console OUT.txt]`.
  - It runs those steps in order and writes the screenshot and the console log.
  - It reuses `chromium_path` / `ensure_driver_node`, moved into a shared module `scripts/dev/browser.py`, which `tests/e2e/conftest.py` then imports.

- [ ] **Step 1: Write the tests** in `tests/e2e/test_fixtures.py`:
  - `test_app_loads_without_console_errors`: `page.console_errors == []` after the app bar is visible.
  - `test_seeded_world_opens_with_cultures_tab`: `seed_world` then `open_scene`; the World Editor has a "Cultures" tab, and on that tab the "link a Shared World" prompt is not shown.
  - `test_failure_artifacts_written`: run a deliberately failing inner test with `pytester`, or call the hook helper directly, and assert that the screenshot file exists.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e/test_fixtures.py -m e2e -n0 -v`. Expected: FAIL.
- [ ] **Step 3: Implement the fixtures, `seed.py`, `browser.py` and `look.py`.**
- [ ] **Step 4: Run** the e2e folder: all pass. Then smoke-test the tool: `guix shell -m manifest.scm -- uv run --no-sync python scripts/dev/look.py <frontend_url> --shot /tmp/x.png` against a runner started by hand. Expected: a PNG that shows the app.
- [ ] **Step 5: Commit** with message `test: e2e fixtures, world seeding and quick-look tool`.

---

### Task 4: Cultures runbook as browser tests, part 1 (checks 1–10)

The runbook is the "Manual checks" list in `docs/superpowers/plans/2026-10-17-cultures-foundation-followups.md`. The fixture culture is `tests/cultures/data/taelrik.culture.json`.

**Files:**
- Create: `tests/e2e/cultures/__init__.py`, `test_tab_and_import.py` (checks 1–5), `test_editing.py` (checks 6, 7, 10), `test_glossary.py` (checks 8, 9)

**Interfaces:**
- Consumes: Task 3's `app`, `page`, `seed_world`, `seed_scene_without_world`, `place_culture`, `open_scene`.
- Use stable selectors: visible text and roles first. Add `data-testid` attributes in `talemate_frontend/src/components/cultures/*.vue` only where text is ambiguous, and keep them few.

- [ ] **Step 1: Write one test per runbook check**, each named `test_runbook_<n>_<short>` and asserting what the runbook line says. For example:
  - `test_runbook_3_import_preview_counts_then_culture_listed`: the preview shows words 4, phrases 4, generators 3, glossary 3, places 2; after import, "Taelrik" is in the drawer.
  - `test_runbook_7_keep_survives_custom_edit`
  - `test_runbook_9_pick_another_rolls_only_in_that_menu`: seed a glossary entry with `origin.by="ai"`, `generator_id="given_male"` and candidates by editing `glossary.json` before `open_scene`.
  - Reload checks reload the page and re-open the scene, then read the value back.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e/cultures -m e2e -n0 -v`. If a test fails because of a real UI bug, stop and report it as DONE_WITH_CONCERNS with the failure and a screenshot; don't change product code beyond `data-testid`s. Otherwise, all pass.
- [ ] **Step 3: Commit** with message `test: cultures runbook checks 1-10 as browser tests`.

---

### Task 5: Cultures runbook as browser tests, part 2 (checks 11–18)

**Files:**
- Create in `tests/e2e/cultures/`: `test_generators.py` (11–13), `test_places.py` (14–17), `test_two_tabs.py` (18)
- Modify: `docs/superpowers/plans/2026-10-17-cultures-foundation-followups.md`. Mark checks 1–18 "(automated: tests/e2e/cultures/…)" and check 19 "(manual: needs a Claude Code session)".

**Interfaces:**
- Consumes the same fixtures as Task 4.
- Check 18 uses two separate browser contexts on the same seeded world.

- [ ] **Step 1: Write the tests** `test_runbook_11` … `test_runbook_18`. Check 13 asserts that a readable error appears and that no spinner is still visible 5 s later (the wait must be a condition, not a sleep). Check 14 asserts the exact phrases from the runbook.
- [ ] **Step 2: Run** the cultures e2e folder: all pass, with the same failure rule as Task 4.
- [ ] **Step 3: Update the runbook file**, then commit with message `test: cultures runbook checks 11-18 as browser tests`.

---

### Task 6: AI test group and koboldcpp smoke test

**Files:**
- Modify: `tests/ai/conftest.py`
- Create: `tests/ai/test_koboldcpp_smoke.py`

**Interfaces:**
- `koboldcpp_url() -> str` returns `TALEMATE_TEST_KOBOLDCPP_URL` or `http://192.168.0.5:5001`.
- `koboldcpp_model(url: str, timeout: float = 5) -> str | None` returns the `result` field of `GET <url>/api/v1/model`, or None when unreachable.
- `ai_app` is a session fixture. It skips with "koboldcpp unreachable at <url>" when `koboldcpp_model` is None. Otherwise it starts the runner with `ai=True` and writes `model.txt` (the model name) into this run's `.test-artifacts/<timestamp>/` folder. It also prints the model name in the pytest header (`pytest_report_header`).

- [ ] **Step 1: Write the conventional tests** in `tests/dev/test_ai_helpers.py`. They run in the plain suite and need no network:
  - `test_koboldcpp_model_parses_result`, against a local stub HTTP server.
  - `test_koboldcpp_model_none_when_unreachable`, against a closed port.
  - `test_ai_tests_skip_without_opt_in`: with `pytester`, an AI test run without `TALEMATE_AI_TESTS` is skipped with the opt-in message.
- [ ] **Step 2: Write the smoke test** `tests/ai/test_koboldcpp_smoke.py::test_client_connects_and_narrator_generates`. It opens a seeded world scene with the `ai_app`, waits until the KoboldCpp client chip in the system bar shows connected (not an error state), triggers one narrator generation from the scene tools, and asserts that a new narrator message with non-empty text appears within 180 s. It checks only that the text is non-empty, never the wording.
- [ ] **Step 3: Run** the conventional tests (expect PASS), then `guix shell -m manifest.scm -- uv run --no-sync pytest tests/ai -m ai -n0`. Expect every AI test to be skipped, because the variable isn't set. **Do not set `TALEMATE_AI_TESTS`.** The controller asks the owner before the first real AI run.
- [ ] **Step 4: Commit** with message `test: opt-in AI test group with koboldcpp smoke test`.

---

### Task 7: Developer docs

**Files:**
- Create: `docs/dev/local-testing.md`

The page covers:
- the one-time setup (`guix shell -m manifest.scm -- uv sync --extra dev`, and pnpm install as in `env` notes)
- how to start, stop and check status of the local app
- the three test groups and their commands
- the quick-look tool
- where failure artifacts land
- the rule: **ask the owner before any AI run, and name the loaded model when asking**
- that the default koboldcpp is the GPU server's, and how to override it

- [ ] **Step 1: Write the page.** Check every command in it by running the non-AI ones once.
- [ ] **Step 2: Commit** with message `docs: local app testing guide`.

---

### Task 8: Whole-branch check (talemate repo)

- [ ] **Step 1:** Run `guix shell -m manifest.scm -- uv run --no-sync pytest -q`. Expected: the same 141 NLTK failures and no new ones; e2e and ai tests deselected.
- [ ] **Step 2:** Run `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e -m e2e -n0`. Expected: all pass.
- [ ] **Step 3:** Run `ruff check` and `ruff format --check` on `scripts/dev tests/e2e tests/ai tests/dev`. Expected: clean.
- [ ] **Step 4:** Run `git status`. Expected: the checkout's `config.yaml` doesn't exist and `scenes/` is unchanged.

---

### Task 9: Server-side branch file (`home` repo)

All paths in this task are relative to `~/Projects/Web/home`.

**Files:**
- Modify: `gpu-server/install.sh`, `gpu-server/talemate-update`
- Test: `tests/test_gpu_server_files.py`

**Interfaces:**
- **Branch file.** `/var/lib/talemate-deploy/branch`, overridable in tests with `TALEMATE_BRANCH_FILE`. `install.sh` creates the directory as `root:sudo` with mode `2775` and the file (if missing) as `root:sudo` with mode `664`, containing `main`. The admin login, a member of `sudo`, can then write it over ssh without sudo, and the service user `ai` can read it.
- **`talemate-update`.** It reads the first line of the branch file, strips CR and whitespace, and validates it against `^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$` with no `..`. A valid name becomes `BRANCH`. A missing or unreadable file, or an invalid name, means `BRANCH=main`, logging `warn "ignoring branch file: <reason>; using main"`. The installed tag stays the 12-character commit, as today. The log line `installed <tag>` gains ` from <branch>`.

- [ ] **Step 1: Write the tests**, following the file's existing stub style:
  - `test_update_uses_branch_from_file`: the file holds `feature/x` → the stubbed GitHub API is called at `commits/feature/x`.
  - `test_update_rejects_bad_branch_names`, parametrized over `../x`, `main;rm -rf /`, an empty string, `-x`, `a..b`, and `feature/x\r\n` (this last one is valid after stripping) → each invalid one leads to `commits/main` and the warning.
  - `test_update_defaults_to_main_without_branch_file`
  - `test_install_creates_branch_file_group_writable_by_sudo`: a static check of the `install.sh` text for the `install -d … -g sudo -m 2775` and file-creation lines.
  - `test_sudoers_talemate_unchanged`: compare against the committed bytes. An existing test may already cover this; keep it.
- [ ] **Step 2: Run** `pytest tests/test_gpu_server_files.py -k "branch or sudoers" -v` with the home repo's usual test command (see its README or pyproject). Expected: the new tests FAIL.
- [ ] **Step 3: Implement** the changes in `install.sh` and `talemate-update`.
- [ ] **Step 4: Run** the whole `tests/test_gpu_server_files.py`. Expected: all pass.
- [ ] **Step 5: Commit** with message `gpu-server: talemate-update follows a deployable branch file`.

---

### Task 10: `talemate-deploy [BRANCH]` and README (`home` repo)

**Files:**
- Modify: `gpu-server/talemate-deploy`, `gpu-server/README.md` (section "Deploy a Talemate change")
- Test: `tests/test_gpu_server_files.py`

**Interfaces:**
- Usage: `gpu-server/talemate-deploy [BRANCH]`. No argument means `main`.
- The script validates `BRANCH` locally with the same pattern as Task 9 (exit 2 with usage on an invalid name). It reads `refs/heads/<BRANCH>` with `git ls-remote`; if the branch is missing, it exits 1 with "branch <BRANCH> not found on <url>" before any ssh.
- The unpushed-commits warning compares the local `<BRANCH>`, not `main`.
- It writes the branch over ssh, in the same ssh call as the restart and before the restart: `printf '%s\n' <BRANCH> > /var/lib/talemate-deploy/branch`. Use proper quoting, since the name has already been validated.
- On success the last line is `Talemate is running <12-char> (<BRANCH>).`

- [ ] **Step 1: Update the tests:**
  - `test_talemate_deploy_rejects_arguments` becomes `test_talemate_deploy_rejects_extra_or_invalid_arguments`: two arguments, `--now` and `../x` each give exit 2 with no ssh.
  - Add `test_talemate_deploy_branch_reports_branch`: the fork fixture gets a `feature/x` branch → the last line is `Talemate is running <head12> (feature/x).`, and the ssh log contains the branch-file write before `systemctl restart`.
  - Add `test_talemate_deploy_missing_branch_stops_before_ssh`.
  - Add `test_talemate_deploy_without_argument_writes_main`.
  - The existing `main` tests keep passing.
- [ ] **Step 2: Run** the deploy tests. Expected: the new ones FAIL.
- [ ] **Step 3: Implement** the changes and update the README section: deploying a branch, returning to `main`, and how the branch persists across reboots until the next deploy.
- [ ] **Step 4: Run** the whole `tests/test_gpu_server_files.py`. Expected: all pass.
- [ ] **Step 5: Commit** with message `gpu-server: talemate-deploy can deploy a named branch`.
