# Local app testing: design

Date: 2026-10-17
Status: draft for review
Repos:
- `AndSnowl/talemate` (this repo, checkout `~/Projects/Web/talemate`)
- the owner's `home` repo (`~/Projects/Web/home`, folder `gpu-server/`)

Markings used below:
- **Decided** means the owner said so.
- **My call** means the designer chose and the owner hasn't confirmed it.
- Anything else is left to the builder.

## 1. Intent

For the cultures foundation, Claude could only check the frontend by building it and reading the code. The 19-step browser runbook fell to the owner, and two real UI bugs were found only by careful reading. Plan 2 of the cultures feature puts the AI in the loop: naming characters, injecting context, and adding names to the glossary after each world-state snapshot. Without a way to run the app against a real model, Claude can't check any of that.

This work lets Claude, on the owner's desktop:
1. start Talemate locally from this checkout and drive its frontend in a real browser, and
2. connect that local Talemate to the koboldcpp running on the GPU server, so AI-dependent features can be exercised without deploying anything and without the owner stepping in.

Separately, it lets the owner deploy a named branch, not only `main`, to the GPU server for a final check in the real setup before merging.

## 2. Goals

1. Claude can start and stop a local Talemate (backend and frontend) from this checkout with one command each. Starting waits until the app is ready.
2. Claude can drive that frontend in a headless browser for quick looks, such as screenshots it reads back, and for saved tests.
3. There are three test groups, run separately (**decided**):
   - **Conventional:** the existing pytest suite. No browser, no AI.
   - **Browser:** the real app in a browser, with no AI calls. Claude runs these freely.
   - **AI:** the real app plus calls to koboldcpp on the GPU server. Kept separate from the other two, and **Claude asks the owner before running them** (**decided**). The owner shares that koboldcpp with their own play.
4. The first browser tests turn the cultures runbook (`docs/superpowers/plans/2026-10-17-cultures-foundation-followups.md`, "Manual checks") into automated tests (**decided**), so the cultures work stays covered from now on.
5. A local test run never touches the owner's real data. The owner's worlds live on the GPU server. Locally, the checkout has no `config.yaml`, and `scenes/` holds only Talemate's bundled examples.
6. `gpu-server/talemate-deploy` can deploy a named branch of the fork (**decided**). It still runs only when the owner runs it, because it needs credentials (**decided**).

## 3. Non-goals

- Claude doesn't push to GitHub or run `deploy` or `talemate-deploy`. Those need the owner's credentials (**decided**).
- No CI service. Everything runs on the owner's desktop.
- No change to how Talemate runs on the GPU server, apart from which branch it builds.
- AI tests don't check exact model wording.

## 4. Anti-goals

- **A test run damages or alters the developer's own state**: the checkout's `config.yaml`, any scene it didn't create, or committed files.
- **An AI call goes out without the owner having said yes for that run.** That covers automated AI tests and also manual sessions where Claude makes the app generate text.
- **The conventional suite gets slower, starts needing a browser or network, or starts failing without them.** Browser and AI tests must be skipped, not failed, when their tools aren't present.
- **Flaky tests.** A browser test that sometimes fails is worse than none. Waits must be on real conditions, never on fixed sleeps.
- **A branch deploy that leaves the server unable to recover.** For example, a typo'd branch name that stops Talemate from starting, or no way back to `main`.

## 5. What exists today (facts found)

- **Machine.** The desktop runs Guix:
  - No `uv`, `node` or `pytest` on PATH. They come from `guix shell uv node python@3.11`.
  - `uv run` needs `--no-sync`; otherwise it re-syncs without the `dev` extra and removes pytest.
  - The frontend uses pnpm, run as `npx --yes corepack@0.34.0 pnpm …`.
  - Playwright's bundled Chromium won't start on Guix.
  - The full suite currently has 141 environment-only failures, caused by missing NLTK `punkt_tab` data.
- **Prior art: `~/Projects/Web/rootmap`.** It has a working Playwright setup on this machine:
  - `manifest.scm` lists `node`, `ungoogled-chromium`, `nss-certs` and `font-dejavu`.
  - `tests/ui/conftest.py` points Playwright's driver at the Guix `node` when the bundled one can't run, finds Chromium on PATH or through an environment variable, skips UI tests when there's no Chromium, and starts a live server on a free port with an isolated data directory.
- **Talemate paths are fixed** to the repo root (`src/talemate/path.py`): `config.yaml`, `scenes/`, `templates/`, `tts/`, `logs/`. There is no environment override.
- **How Talemate starts:**
  - Backend: `start-backend.sh` runs `uv run src/talemate/server/run.py runserver --host 0.0.0.0 --port ${TALEMATE_BACKEND_PORT:-5050} --backend-only`.
  - Frontend: `start-frontend.sh` runs `pnpm run serve --port ${TALEMATE_FRONTEND_PORT:-8082}`.
  - The frontend's backend address comes from `VITE_TALEMATE_BACKEND_WEBSOCKET_URL` (see `talemate_frontend/example.env.development.local`).
- **GPU server koboldcpp.** It answers from the desktop at `http://192.168.0.5:5001`. On 2026-10-17 it served `koboldcpp/Skyfall-31B-v4.2-i1-Q4_K_M` with 16K context. The model can change whenever the owner switches presets.
- **Deploying to the GPU server** (`home/gpu-server/`):
  - `talemate-deploy` reads the head of `main` from GitHub, then runs `ssh gpu-admin 'sudo -n systemctl restart talemate'`. It reads `/opt/talemate/last-update.log` and `/opt/talemate/VERSION` and reports whether the new commit is running and stays up. It takes no arguments.
  - The restart runs `talemate-update` (the unit's `ExecStartPre`). That script sets `BRANCH=main` and calls `update_main` from `frontend-update-lib.sh`, which already supports a `BRANCH` (it installs the newest commit of that branch).
  - `sudoers-talemate` lets the admin login run only `systemctl restart talemate`.
  - Tests for all of this are in `home/tests/test_gpu_server_files.py`, e.g. `test_talemate_deploy_rejects_arguments`, which has to change.

## 6. The design

### 6.1 Local app runner

Two scripts, for Claude and for test fixtures. Names and location are the builder's choice; under `scripts/dev/` is a reasonable default.
- **Start:** start the backend and frontend from this checkout on free ports, or on given ports. Then wait until the websocket accepts connections and the frontend serves its page. Print the URLs. Write a small state file (PIDs, ports, data location) so stop and status can find it.
- **Stop:** stop exactly what start started.
- All commands go through the Guix wrapper, so they work from a plain shell.

**Isolated data (my call).** Each run gets its own `config.yaml`, `scenes/`, `chroma`, `logs`, `templates` and `tts`, separate from the checkout's. Talemate's paths are fixed, so the builder picks one of these:
- run the app from a temporary copy (for example a git worktree) whose `.venv` and `talemate_frontend/node_modules` are symlinked from the main checkout, or
- add a small environment override for the data root in `src/talemate/path.py`, defaulting to today's behaviour. That would be one of the few edits to an upstream file, and it could be offered upstream.

Either way, the checkout's own `config.yaml` and `scenes/` are never written to.

**The run's config** is generated from a template:
- Browser runs and conventional runs get no LLM client.
- AI runs get one KoboldCpp client at `http://192.168.0.5:5001` (address overridable by environment variable), with `max_token_length` 16384, matching `home/gpu-server/talemate-config.yaml`.
- No other external service (TTS, image generation, cloud clients) is configured.

### 6.2 Browser tooling

- **Guix manifest.** A manifest in this repo, modelled on rootmap's, adds `ungoogled-chromium`, `nss-certs` and fonts to the shell the commands already use.
- **Playwright** for Python is added to the `dev` extra in `pyproject.toml` (**my call**; rootmap does the same), with `uv.lock` updated. The `uv sync --extra dev` the owner's machine already uses then picks it up.
- **Driver.** Reuse rootmap's driver-node fix and its "find Chromium or skip" fixture rather than reinventing them.
- **Quick looks.** A small helper lets Claude open a page of the running app, optionally click through a few steps, save a screenshot under the scratchpad, and read it back. It also saves the browser console log, so frontend errors are visible. The format is up to the builder; a short Python script taking steps as arguments is enough.

### 6.3 Test groups

- **Locations:** browser tests in `tests/e2e/` and AI tests in `tests/ai/`, or pytest markers. Builder's choice, as long as:
  - the plain `uv run --no-sync pytest` skips both groups, by default and without network;
  - each group runs with one documented command;
  - the AI group refuses to run unless an explicit opt-in is set, e.g. `TALEMATE_AI_TESTS=1`. The command Claude uses always sets it on purpose, after asking.
- **Fixtures** start the app through 6.1 for a test session, and stop it afterwards, even when tests fail.
- **Waits** are on observable conditions: an element appearing, a websocket message, text changing. Never on fixed sleeps.
- **AI tests** check outcomes, not wording. For example:
  - a new NPC in a Taelrik place gets a name that `fits()` Taelrik;
  - the name appears in the glossary as unreviewed, with its generator and candidates;
  - the narrator's prompt contains the culture section.

  Each AI test gets a generous timeout. When koboldcpp is unreachable it skips with a clear message rather than failing.
- **Wrong model loaded (my call).** koboldcpp can be up but serving a model unsuited to the test, such as a raw base model or an image-agent preset. There is no automatic capability probe. Instead:
  - When Claude asks the owner before an AI run, it names the model koboldcpp reports at `/api/v1/model`, so the owner can say "not now" or switch presets.
  - Each AI run records that model name with its results.
  - A failing AI test on an unsuitable model is treated as "re-run on a suitable preset", not as a Talemate bug.
- **Recording what ran.** Browser and AI runs save screenshots of failures, plus the backend log, to a known folder so the owner can look.

### 6.4 First browser tests: the cultures runbook

Automate the runbook's checks as browser tests, using the Taelrik fixture at `tests/cultures/data/taelrik.culture.json`. A few runbook checks need setup that is awkward to do through the UI. Those may prepare data through the websocket API or by writing world files into the isolated data directory before the page loads. Checks 18 (two tabs on the same world) and 19 (the skill end to end) are covered as follows:
- Check 18 becomes a two-browser-context test.
- Check 19 stays manual, because it needs a Claude Code session.

The builder states which runbook checks became tests, and keeps the runbook file up to date (marking which ones are automated).

### 6.5 Branch deploys (`home` repo)

- `talemate-deploy [BRANCH]`: with no argument it deploys `main` as today; with an argument it deploys that branch of `AndSnowl/talemate`. It checks the branch exists on GitHub before touching the server. It keeps the existing "unpushed commits" warning, applied to that branch. On success it reports which branch and commit are running.
- The branch reaches the server's `talemate-update` without widening `sudoers-talemate` beyond restarting Talemate. One way: the admin login writes the requested branch into a file the update script reads, readable by the service and writable by the admin login. The builder picks the exact mechanism within that constraint.
- **Validation.** The update script accepts only branch names matching a strict pattern (letters, digits, `/`, `-`, `_`, `.`). Anything else, or an unreadable file, falls back to `main` with a logged warning.
- **Persistence (my call).** The server stays on the last deployed branch across reboots and restarts, and running `talemate-deploy` with no argument returns it to `main`. `last-update.log` and the deploy output name the branch.
- Tests in `home/tests/test_gpu_server_files.py` are updated and extended: `test_talemate_deploy_rejects_arguments` changes, and new tests cover a branch argument, a missing branch, invalid names, the fallback to `main`, and the sudoers file staying restart-only.
- The `home/gpu-server/README.md` section "Deploy a Talemate change" is updated to match.

### 6.6 Documentation and memory

- A short `docs/dev/` page in this repo explains how to start and stop the local app, run each test group, take a quick look, and what the AI opt-in means.
- The owner's rule "ask before AI test runs" is already saved in Claude's memory. The page states it too, so any session sees it.

## 7. Left to the builder

- Script names, file locations, the state-file format.
- Temporary-copy versus environment-override isolation (6.1), within its constraints.
- Markers versus folders for test groups (6.3).
- The exact branch-file mechanism on the server (6.5), within its constraints.
- Which runbook checks need data prepared outside the UI.
