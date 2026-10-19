# Local app testing

A way to run a full, isolated copy of Talemate on the developer's own
machine — backend, frontend and (optionally) a real AI client — without
ever touching the checkout's own `config.yaml`, `scenes/`, `logs/`,
`chroma/`, `templates/` or `tts/`. Useful for driving the real app in a
browser, taking a quick screenshot, or running the browser and AI test
groups.

Everything below runs on a Guix machine, from the talemate repo root.

!!! warning "Ask before any AI run"
    A run started with `--ai`, or the `tests/ai` test group, makes real
    calls to a koboldcpp instance. **Always ask the owner first**, and name
    the model koboldcpp reports loaded (see
    [Owner's koboldcpp and the AI opt-in](#owners-koboldcpp-and-the-ai-opt-in)
    below) so they can say "not now" or switch presets. No automated or
    unattended session may set `TALEMATE_AI_TESTS=1` on its own.

## One-time setup

```bash
guix shell -m manifest.scm -- uv sync --extra dev
guix shell -m manifest.scm -- sh -c 'cd talemate_frontend && npx --yes corepack@0.34.0 pnpm install'
```

Both run from the repo root, where `manifest.scm` is. The `cd` happens
inside the shell because Corepack picks the pnpm version from the
`packageManager` field of the `package.json` in the *current* directory.
Run as `pnpm --dir talemate_frontend` from the root, it would miss that
field and use Corepack's own default pnpm instead of the pinned one (here,
a newer pnpm that `corepack@0.34.0` fails to start).

`manifest.scm` (repo root) pins the tools these commands need: `uv`,
`python@3.11`, `node`, `ruff`, `ungoogled-chromium`, `nss-certs`,
`font-dejavu`, `ffmpeg` (the memory agent's embeddings load FFmpeg's
libraries; without it no scene loads) and `zlib` (numpy, which chromadb
uses, dlopens `libz.so.1`). Every command on this page runs inside
`guix shell -m manifest.scm -- ...`.

## Starting, checking and stopping the local app

The runner is `scripts/dev/talemate_app.py`. `start` copies the working
tree (including uncommitted changes) into a temporary root, writes a
`config.yaml` for that run there, and starts the backend and the vite
frontend from the copy — the checkout's own data is never read or written.
It waits until the backend's websocket and the frontend are both ready,
then prints their URLs.

```bash
guix shell -m manifest.scm -- uv run --no-sync python scripts/dev/talemate_app.py \
    start [--ai] [--root DIR] [--backend-port N] [--frontend-port N]
guix shell -m manifest.scm -- uv run --no-sync python scripts/dev/talemate_app.py status
guix shell -m manifest.scm -- uv run --no-sync python scripts/dev/talemate_app.py stop
```

- The default root is `$TMPDIR/talemate-app` (`$CLAUDE_SCRATCHPAD/talemate-app`
  when `CLAUDE_SCRATCHPAD` is set). Pass `--root` to run more than one
  instance at once.
- `start` refuses to start over a live run in the same root — run `stop`
  first.
- `--ai` configures a single KoboldCpp client — see the opt-in rule above
  before ever passing it. `start --ai` refuses with "AI runs need
  TALEMATE_AI_TESTS=1 — ask the owner first" unless `TALEMATE_AI_TESTS=1`
  is set, so only an owner-approved run can start one.
- The run never touches the OS keyring: the backend runs with
  `TALEMATE_DISABLE_KEYRING=1`, and its encryption key is a file in
  `<root>/secrets`.
- `status` prints the running instance's URLs and PIDs, or exits non-zero
  with `not running`.
- `stop` stops exactly what `start` started (SIGTERM to each child's
  process group, then SIGKILL after a 10s grace) and removes the state
  file. Always stop a run you started.

## The three test groups

The plain suite, the browser (`e2e`) group and the AI group are run
separately and never mixed, so the everyday test run stays network- and
browser-free.

### Conventional (plain) suite

```bash
guix shell -m manifest.scm -- uv run --no-sync pytest
```

No browser, no AI, no network. `pyproject.toml`'s `addopts` already
excludes both other groups (`-m "not e2e and not ai"`) and distributes
across cores; add `-n0 -v` for serial, verbose output. The full suite is
expected to pass clean: 0 failed.

### Frontend logic checks

Pure JS logic (no Vue, no browser) that's fast enough to check with plain
node instead of a full Vitest/Jest setup — see
`talemate_frontend/checks/*.check.mjs`. Run directly:

```bash
guix shell -m manifest.scm -- sh -c 'cd talemate_frontend && node checks/culturesStory.check.mjs'
```

The plain suite also runs it, via `tests/dev/test_frontend_checks.py`,
which shells out to the same command and skips when `node` or the
frontend's installed dependencies (`talemate_frontend/node_modules`)
aren't available.

### Browser (`e2e`) group

```bash
guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e -m e2e -n 4 -v
```

Drives a real headless Chromium (via Playwright) against an isolated app
that the `app` fixture starts and stops for the session. No AI client is
configured, so these are safe to run freely. Outside the Guix shell (no
Chromium on PATH, no `TALEMATE_CHROMIUM`), every test here skips, keeping
the plain suite runnable without a browser.

Each xdist worker starts its own isolated app, so `-n 4` runs the full
suite in about 3.5 minutes. Don't go above 4 on this machine: each app
(backend, vite, Chromium) takes 2–3 GB, and `-n 8` ran out of memory.

### A fast loop while working

- While iterating, run only the tests for the area you changed, for
  example `tests/e2e/theme` or `tests/e2e/cultures`, plus the frontend
  checks (1 s) and the plain suite (about 40 s). Run the full browser
  suite once, at the end of a task, not after every fix.
- A change to UI that the AI tests drive, such as a selector, a class or
  a test id, also needs `grep -rn` over `tests/ai` for the old value. The
  AI group isn't run without the owner's go-ahead, so nothing else will
  catch it.
- Seeding goes through one long-lived worker per app (see
  `tests/e2e/seed.py`). Keep seed scripts free of state that leaks
  between calls, or reset it in the worker, as it already does for
  message ids.
- A killed run (a timeout, a cancelled agent, an out-of-memory kill)
  leaves its app running, because the app's children start in their own
  session. Before a big run, check for leftovers and stop them:

  ```bash
  ps -eo pid,etime,cmd | grep "[p]ytest-of-$USER/pytest-.*/app"
  pkill -f "pytest-of-$USER/pytest-<N>/app0"
  ```

The measurements behind these numbers are in
[dev-loop-optimizations.md](dev-loop-optimizations.md).

### AI (opt-in) group

Needs the owner's go-ahead every time (see the warning above). It is
opt-in twice over: every test under `tests/ai` is marked `ai` (excluded
from the plain suite's `addopts`), and a session-scoped fixture skips the
whole group unless `TALEMATE_AI_TESTS=1` is set.

```bash
TALEMATE_AI_TESTS=1 guix shell -m manifest.scm -- uv run --no-sync pytest tests/ai -m ai -n0 -v
```

Without `TALEMATE_AI_TESTS=1` every test here is skipped — no network call
is made just by collecting or running them. With it exported, a run that
doesn't select `-m ai` (a plain `pytest`, say) still makes no call: the
header's model-name probe only runs when `-m ai` is given.

### Cultures AI evaluation

An overnight measurement of how well the Culture agent works with the
loaded model, rather than a pass/fail test. It needs the same go-ahead
as the AI group.

```bash
TALEMATE_AI_TESTS=1 guix shell -m manifest.scm -- uv run --no-sync python scripts/dev/eval_cultures_ai.py [--runs 3] [--npcs 5] [--narrations 3] [--out DIR]
```

- It starts one isolated app with the KoboldCpp client. Then, for each
  run and each of the three cultures scenarios (`tests/ai/cultures/scenarios.py`),
  it seeds a fresh world, creates characters, asks for narrations and
  requests two snapshots.
- It writes `report.md` (plain tables, with a short note on what each
  number means, plus samples of the names, narration excerpts and
  glossary entries), `report.json` (every raw result) and `model.txt`
  to `--out`. The default is `.test-artifacts/cultures-eval-<YYYYmmdd-HHMMSS>/`.
- Both reports are rewritten after every step. A failed step is listed
  under `errors` and the run goes on.
- At the default size it takes about 1 to 2 hours on Skyfall-31B, and
  it prints a progress line with an estimate of the time left after
  each step.
- `--scenarios` limits a run to some scenarios, for a quick check (e.g.
  `--runs 1 --npcs 2 --narrations 1 --scenarios taelrik_town`).
- Without `TALEMATE_AI_TESTS=1` it exits at once with "AI runs need
  TALEMATE_AI_TESTS=1 — ask the owner first" and makes no network call.

## Owner's koboldcpp and the AI opt-in

The AI group's `ai_app` fixture, and a `start --ai` run, point at the
owner's GPU server koboldcpp by default: `http://192.168.0.5:5001`.
Override with `TALEMATE_TEST_KOBOLDCPP_URL`.

Before asking the owner to run anything AI, fetch the loaded model's name
(`GET <url>/api/v1/model`, wrapped by `scripts/dev/ai_helpers.py`'s
`koboldcpp_model`) and say it when asking — the owner shares that
koboldcpp with their own play, and may be running a model unsuited to the
test (a raw base model, an image-agent preset, or simply the wrong one).
There is no automatic capability check for this: the owner is told the
model name and decides whether to go ahead, wait, or switch presets. If
`tests/ai` is run and a test fails only because of an unsuitable loaded
model, treat it as "re-run on a suitable preset", not as a Talemate bug.
Each AI run records the model name it used alongside its results (see
below).

## Quick looks: `scripts/dev/look.py`

Opens a URL against a running app, optionally clicks, fills or waits on a
few selectors in order, then saves a full-page screenshot (and, if asked,
the browser's console log):

```bash
guix shell -m manifest.scm -- uv run --no-sync python scripts/dev/look.py \
    URL [--click SELECTOR]... [--fill SELECTOR TEXT]... [--wait SELECTOR] \
    --shot OUT.png [--console OUT.txt] [--timeout S] [--width W] [--height H]
```

`--click`, `--fill` and `--wait` run in the order given, after the page has
loaded. `--fill` takes the selector and the text as two separate arguments,
for example `--fill 'role=textbox[name="Title"]' 'My scene'`. Selectors are
Playwright selectors (CSS, `text=...`, `role=button[name="..."]`, ...).
Point `URL` at the `frontend` address a `start`/`status` call printed.

- `--timeout S`: how long each step waits for its element, in seconds
  (default 30).
- `--width W`, `--height H`: the browser viewport, in pixels (default
  1280 x 900). The screenshot is full page, so it can be taller.

The screenshot (and the console log) is saved even when a step fails or
times out, so you can see where it stuck.

## Failure artifacts

When a browser-group or AI-group test that used a page fails, a full-page
screenshot and the tail of that run's backend log are saved to:

```
.test-artifacts/<YYYYmmdd-HHMMSS>/<test-name>/
  screenshot.png
  backend.log.tail
```

One timestamp folder per test session. An AI run also writes, in that
folder, `model.txt` (the koboldcpp model name it used) and, at the end of
the session, `results.txt`: the model name and the passed, failed and
skipped counts. Neither is written when the AI group was skipped. `.test-artifacts/` is gitignored — nothing under it is ever
committed.

## Scripts that import chromadb

`scripts/dev/talemate_app.py`'s own `start` already puts `zlib`'s library
directory on the backend's `LD_LIBRARY_PATH` (see `backend_env`), but a
one-off script run directly — not through `start` — needs the same thing
done by hand, or numpy's `import chromadb` fails trying to dlopen
`libz.so.1`:

```bash
guix shell -m manifest.scm -- bash -c 'LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python …'
```

## Known environment facts

- This is a Guix machine: `uv`, `node` and `pytest` aren't on `PATH` on
  their own, hence `guix shell -m manifest.scm -- ...` in front of every
  command above.
- Always use `uv run --no-sync`, never a plain `uv run` — it re-syncs the
  project and drops the `dev` extra (and with it, `pytest`).
- The frontend's package manager is pnpm, run through Corepack:
  `npx --yes corepack@0.34.0 pnpm ...` (never `npm install`).
- The plain suite is expected to pass clean (0 failed); NLTK's `punkt_tab`
  English model is vendored under `tests/data/nltk_data` so sentence
  tokenization works with no `~/nltk_data` and no network.
