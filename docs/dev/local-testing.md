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
cd talemate_frontend
guix shell -m manifest.scm -- npx --yes corepack@0.34.0 pnpm install
cd ..
```

`manifest.scm` (repo root) pins the tools these commands need: `uv`,
`python@3.11`, `node`, `ruff`, `ungoogled-chromium`, `nss-certs` and
`font-dejavu`. Every command on this page runs inside
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
  before ever passing it.
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
across cores; add `-n0 -v` for serial, verbose output. The full suite
currently has 141 pre-existing failures, all from missing NLTK
`punkt_tab` data (`test_dedupe`, the prompts editor baselines,
`test_tts_util`, `test_editor_revision`) — judge a run by "no new
failures", not by a clean suite.

### Browser (`e2e`) group

```bash
guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e -m e2e -n0 -v
```

Drives a real headless Chromium (via Playwright) against an isolated app
that the `app` fixture starts and stops for the session. No AI client is
configured, so these are safe to run freely. Outside the Guix shell (no
Chromium on PATH, no `TALEMATE_CHROMIUM`), every test here skips, keeping
the plain suite runnable without a browser.

### AI (opt-in) group

Needs the owner's go-ahead every time (see the warning above). It is
opt-in twice over: every test under `tests/ai` is marked `ai` (excluded
from the plain suite's `addopts`), and a session-scoped fixture skips the
whole group unless `TALEMATE_AI_TESTS=1` is set.

```bash
TALEMATE_AI_TESTS=1 guix shell -m manifest.scm -- uv run --no-sync pytest tests/ai -m ai -n0 -v
```

Without `TALEMATE_AI_TESTS=1` every test here is skipped — no network call
is made just by collecting or running them.

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
    URL [--click SELECTOR]... [--fill SELECTOR=TEXT]... [--wait SELECTOR] \
    --shot OUT.png [--console OUT.txt]
```

`--click`, `--fill` and `--wait` run in the order given, after the page has
loaded; `--fill` takes `SELECTOR=TEXT`. Selectors are Playwright selectors
(CSS, `text=...`, `role=button[name="..."]`, ...). Point `URL` at the
`frontend` address a `start`/`status` call printed.

## Failure artifacts

When a browser-group or AI-group test that used a page fails, a full-page
screenshot and the tail of that run's backend log are saved to:

```
.test-artifacts/<YYYYmmdd-HHMMSS>/<test-name>/
  screenshot.png
  backend.log.tail
```

One timestamp folder per test session. An AI run also writes
`.test-artifacts/<YYYYmmdd-HHMMSS>/model.txt`, the koboldcpp model name it
used. `.test-artifacts/` is gitignored — nothing under it is ever
committed.

## Known environment facts

- This is a Guix machine: `uv`, `node` and `pytest` aren't on `PATH` on
  their own, hence `guix shell -m manifest.scm -- ...` in front of every
  command above.
- Always use `uv run --no-sync`, never a plain `uv run` — it re-syncs the
  project and drops the `dev` extra (and with it, `pytest`).
- The frontend's package manager is pnpm, run through Corepack:
  `npx --yes corepack@0.34.0 pnpm ...` (never `npm install`).
- The plain suite's 141 failures (missing NLTK `punkt_tab` data) predate
  this work and aren't something a local run is expected to fix — only
  watch for *new* failures.
