# Pre-Phase-2 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Before phase 2 starts reworking scenes and characters, get the test suite fully passing, make chromadb load outside pytest on Guix, record today's scene behaviour in a golden test, put `talemate.world` under strict typing, and harden the world view that phase 2 builds on.

**Architecture:** Five independent, small tasks. Nothing changes app behaviour. The changes are test infrastructure, the dev environment, and one internal query rewrite in `src/talemate/world/view.py`.

**Tech stack:** Python 3.11, pytest (with xdist), NLTK, mypy 2.x (already a dev dependency), Guix `manifest.scm`, SQLite.

**Spec:** `docs/superpowers/specs/2026-10-18-fantasymate-world-data-model-design.md`, section "Code health" → "Before phase 2".

## Global Constraints

- **Running things on Guix.** Run everything through `guix shell -m manifest.scm -- …` from the repo root (or the worktree), and always use `uv run --no-sync`.
- **The baseline on `main`** (e0db245) is 141 failed / 6513 passed. All 141 are NLTK `punkt_tab` failures. After Task 1, the plain suite must report **0 failed**.
- **Tests in the plain suite never touch the network.**
- **Don't edit code that phase 2 deletes:** `shared_context.py`, name-keyed character maps, history ranges stored as list positions, and `changelog.py`.
- **The undo provenance fix may still be in flight** on `fix/world-undo-provenance` (it touches `src/talemate/world/undo.py`, `schema.py`, `store.py` and `tests/world/test_undo.py` / `test_invariants.py`). Task 5 must not edit those files. If Task 4's typing work needs changes in them, start Task 4 only after that branch is merged.

## Review Focus

1. **Offline NLTK.** A machine with no `~/nltk_data` and no network still tokenizes sentences in tests (Task 1: `test_sent_tokenize_works_offline`).
2. **Golden test stability.** Running the golden test twice in a row, and under xdist, gives identical recordings: no timestamps, uuids or dict-order noise (Task 3: `test_golden_scene_is_deterministic`).
3. **mypy noise.** Third-party packages with no type stubs (chromadb, isodate) must not fail the type check, and other `talemate` modules must not be checked strictly (Task 4: `test_world_package_typechecks`).
4. **SQLite's bound-variable limit.** `view.things()` and `index_documents` must work with more things than SQLite allows as bound variables (Task 5: `test_things_beyond_variable_limit`).
5. **The dev app's environment when Guix isn't active.** Without `GUIX_ENVIRONMENT`, `backend_env` must behave exactly as before (Task 2: `test_backend_env_without_guix_environment_unchanged`).

---

### Task 1: The test suite passes with no network

**Files:**
- Create: `tests/data/nltk_data/tokenizers/punkt_tab/english/` containing the four files from NLTK's `punkt_tab` English model: `abbrev_types.txt`, `collocations.tab`, `ortho_context.tab`, `sent_starters.txt` (about 244 KB). Also copy `tests/data/nltk_data/tokenizers/punkt_tab/README` from the same download, plus a `SOURCE.md` with one paragraph saying where the files came from (nltk_data `punkt_tab`, Apache-2.0) and how to refresh them.
- Modify: `tests/conftest.py`. At import time, before any test module loads, prepend `tests/data/nltk_data` to `nltk.data.path`.
- Modify: `docs/dev/local-testing.md` (lines 89-90 and 265). Replace "141 pre-existing failures" with the new expectation, which is none.
- Test: `tests/test_nltk_data.py`

Get the files by copying an existing download (one exists at `/tmp/talemate-app/nltk_data/tokenizers/punkt_tab/` on the dev machine), or by fetching once with `python -m nltk.downloader -d <tmpdir> punkt_tab`. Only English is vendored.

- [ ] **Step 1: Write the failing test.** Add `test_sent_tokenize_works_offline`. It sets `NLTK_DATA` to an empty tmp dir with monkeypatch, and asserts `nltk.sent_tokenize("Hello there. How are you?") == ["Hello there.", "How are you?"]`.
- [ ] **Step 2: Run it to make sure it fails** (`LookupError` for `punkt_tab`).
  Run: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/test_nltk_data.py -v -n0`
- [ ] **Step 3: Vendor the data and add the conftest path.**
- [ ] **Step 4: Run the full plain suite.** Run: `guix shell -m manifest.scm -- uv run --no-sync pytest`. Expected: **0 failed**. If any failures remain, they are not NLTK failures; report them, and don't mark the task done.
- [ ] **Step 5: Commit** with the message `test: vendor NLTK punkt_tab English so the suite runs offline`.

### Task 2: chromadb loads outside pytest on Guix

**Files:**
- Modify: `manifest.scm`. Add `"zlib"` to the package list, with a comment line explaining that numpy, which chromadb uses, dlopens `libz.so.1`.
- Modify: `scripts/dev/talemate_app.py`, `backend_env(root: Path) -> dict`. When `GUIX_ENVIRONMENT` is set and `$GUIX_ENVIRONMENT/lib` is a directory, append that directory to `LD_LIBRARY_PATH`, after the ffmpeg lib dir it already adds.
- Modify: `docs/dev/local-testing.md`. Add a short "Scripts that import chromadb" note giving the command `guix shell -m manifest.scm -- bash -c 'LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python …'`.
- Test: `tests/dev/test_talemate_app.py`

- [ ] **Step 1: Write the failing tests.**
  - `test_backend_env_adds_guix_environment_lib`: monkeypatch `GUIX_ENVIRONMENT` to a tmp dir that contains `lib/`. Assert that `str(tmp/"lib")` is one of the `LD_LIBRARY_PATH` entries.
  - `test_backend_env_without_guix_environment_unchanged` (Review Focus 5): with `GUIX_ENVIRONMENT` unset, `LD_LIBRARY_PATH` holds only what it held before. Compare it against the ffmpeg-derived value computed the same way, or against the absence of any `GUIX_ENVIRONMENT`-derived entry.
- [ ] **Step 2: Run them to make sure they fail.**
  Run: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/dev/test_talemate_app.py -v -n0`
- [ ] **Step 3: Implement the change and edit the manifest.**
- [ ] **Step 4: Verify.**
  - The tests pass.
  - Run `guix shell -m manifest.scm -- bash -c 'LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python -c "import chromadb; chromadb.EphemeralClient()"'`. Expected: exit code 0.
- [ ] **Step 5: Commit** with the message `dev: zlib in the Guix shell so chromadb loads outside pytest`.

### Task 3: A golden scene test that records today's behaviour

The point is to see exactly what phase 2 changes. The test records what the AI is sent and what gets saved for a short, scripted scene, and compares both against a committed recording. Phase 2 tasks will update the recording on purpose, and each update is reviewed.

**Files:**
- Create: `tests/characterization/__init__.py`
- Create: `tests/characterization/test_scene_golden.py`
- Create, by running with `--update-baselines`: `tests/data/characterization/scene_golden.json`
- Reuse: `tests/conftest.py` (`MockScene`, `bootstrap_scene`, `client_responses`, the `update_baselines` fixture). Reuse `tests/data/scenes/talemate-laboratory/talemate-lab.json` as the starting scene, loaded the way `tests/test_graphs.py` loads it.

**Interfaces:**
- The recording is one JSON object, `{"prompts": [{"step": str, "kind": str, "prompt": str}], "scene": dict}`.
  - `prompts` is taken from `MockClient.prompt_history`, in order, each entry tagged with the script step that produced it.
  - `scene` is `scene.serialize()` after the script, normalised.
- Normalisation: `normalise(obj) -> obj`.
  - Drop these keys: `id`, `memory_id`, `memory_session_id`, `saved_memory_session_id`, and any key whose value is a wall-clock timestamp.
  - Replace hex runs of 8 or more characters that look like uuids with `<id>`.
  - Sort dict keys.

  The key list is final once the determinism test passes. Record any key you add in the test's docstring.
- The script, with canned mock responses queued through `client_responses`:
  1. A character's dialogue turn, from the conversation agent.
  2. A narrator "progress story" turn.
  3. A time passage of `P1D`.
  4. A second dialogue turn after the time passage, so the time and history context shows up in a prompt.

  If a step can't be driven without the websocket server, replace it with the nearest agent-level call. Name the substitution in the docstring.

- [ ] **Step 1: Write the tests.**
  - `test_golden_scene_matches_recording`: compares against the baseline; with `--update-baselines` it writes the baseline instead.
  - `test_golden_scene_is_deterministic` (Review Focus 2): runs the script twice in fresh scenes and asserts the two normalised recordings are equal.
- [ ] **Step 2: Create the recording.**
  Run: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/characterization -v -n0 --update-baselines`.
  Check that `scene_golden.json` has 4+ prompt entries and contains the canned responses' text in the saved scene history.
- [ ] **Step 3: Run both without the flag, and also under xdist.**
  Run: `… pytest tests/characterization -v -n0`, then `… pytest tests/characterization -v -n 4`. Expected: PASS both times.
- [ ] **Step 4: Document the recording in `docs/dev/local-testing.md`.** Explain that a phase-2 change to scene or context code is expected to change it, that the update is regenerated with `--update-baselines`, and that the diff is reviewed in the same commit.
- [ ] **Step 5: Commit** with the message `test: golden scene recording ahead of the phase-2 rework`.

### Task 4: Strict typing for `talemate.world`, enforced by the suite

**Files:**
- Modify: `pyproject.toml`. Add a `[tool.mypy]` section with:
  - `python_version = "3.11"`;
  - `follow_imports = "silent"`;
  - `ignore_missing_imports = true`;
  - a `[[tool.mypy.overrides]]` table with `module = ["talemate.world", "talemate.world.*"]` and `strict = true`.
- Modify: `src/talemate/world/*.py`, only where strict mypy needs it (annotations, narrowing). No behaviour changes.
- Test: `tests/world/test_typecheck.py`

**Interfaces:**
- `test_world_package_typechecks` (Review Focus 3) calls `mypy.api.run(["--config-file", <repo>/pyproject.toml, "-p", "talemate.world"])` and asserts exit status 0. On failure it prints the report.
- Point `cache_dir` at a tmp dir, so parallel xdist workers don't share `.mypy_cache`.

- [ ] **Step 1: Write the test.**
- [ ] **Step 2: Run it** and record the errors in your report.
  Run: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/world/test_typecheck.py -v -n0`
- [ ] **Step 3: Fix the reported typing errors in `src/talemate/world/`.**
  - Annotations only. Use `cast` or narrowing where SQLite rows are untyped.
  - Never change behaviour.
  - Only add `# type: ignore[code]` with a reason comment.
- [ ] **Step 4: Run `tests/world` and the full suite.** Expected: all pass, and the full suite shows 0 failed. Note how long the typecheck test takes in your report.
- [ ] **Step 5: Commit** with the message `test(world): strict mypy for talemate.world, enforced by the suite`.

### Task 5: World view hardening

**Files:**
- Modify: `src/talemate/world/view.py`. Replace each `IN ({placeholders})` list of thing ids with a join, or an `IN (SELECT …)` subquery, that repeats the same live-at-rev filter on `things`. Query shapes and results stay the same, and there is still one query per table per call.
- Modify: `src/talemate/world/view.py` `_decode_field_value`. Use the kind spec's existing field lookup (`kinds.py`) instead of a bare `next(...)`, so an unknown field raises a clear `KeyError` rather than `StopIteration`.
- Test: `tests/world/test_view.py`

The tests to add:
- **`test_things_beyond_variable_limit`** (Review Focus 4):
  - create 30 things;
  - call `world._conn.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 10)`;
  - assert that `len(world.view().things()) == 30` and that `index_documents(world)` returns a header for each.
- **`test_fields_at_date`:** with the `maren` fixture, `view(at=of(312)).thing(m).fields == {"name": "Maren", "born": WorldDate.of(290)}`, and `born` is a `WorldDate` with YEAR precision.
- **`test_no_fields_before_valid_from`:** `view(at=of(289)).thing(m).fields == {}`.
- **`test_fact_order`:** at `of(315)`, the list `[f.fact_id for f in facts]` starts with the open-start "laugh" fact, followed by the dated facts in `valid_from` order.
- **`test_referencing_drops_ended_and_removed`:** a referencing fact that has ended disappears from `referencing()` after its end date, and a removed one disappears at later revs.

- [ ] **Step 1: Write the tests;** `test_things_beyond_variable_limit` must fail on the current code.
  Run: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/world/test_view.py -v -n0`
- [ ] **Step 2: Implement the query change and the lookup fix.**
- [ ] **Step 3: Run `tests/world` and the full suite.** Expected: all pass.
- [ ] **Step 4: Commit** with the message `fix(world): view queries survive SQLite's variable limit; pin field and order behaviour`.
