# Development loop: what's slow and what helps

Measured overnight on 2026-10-18 and 2026-10-19, on the dev machine (16 cores, 31 GB, Guix), at commit e875264 of `feature/fantasymate-appearance`. The experiment branch is `exp/devloop`, in the worktree `.worktrees/devloop-exp`.

## Where a full browser-test run spent its time (baseline: 61 tests, 20 min 26 s)

| Phase | Total | Count | Average |
|---|---|---|---|
| Seeding a scene (`e2e.seed._run_in_copy`) | **806 s (66%)** | 134 | 6.0 s |
| Opening a page (`page` fixture: new context, load, dismiss onboarding) | 175 s | 53 | 3.3 s |
| Loading a scene (`open_scene`) | 109 s | 45 | 2.4 s |
| Starting the app (session fixture) | 18 s | 1 | 18 s |
| Everything else (the tests' own steps) | about 120 s | | |

There are no fixed sleeps in the tests. Seeding dominates because every seed call starts a fresh Python process that spends about 5–6 s importing `talemate` (`python -X importtime`: `talemate.instance` alone takes about 4 s, mostly the client and agent modules).

Other things that turned out to be cheap:

| Step | Time |
|---|---|
| Starting a `guix shell` | 0.05 s |
| Frontend build | 10 s |
| Node checks | 1 s |
| Plain Python suite (already parallel) | 44 s |

## Results, most effective first

### 1. Seed through one long-lived worker per app (done on `exp/devloop`, commit 04a0ba8)

`_run_in_copy` now sends each seed script to one Python process per app root. That process imports talemate once and `exec`s each script in a fresh namespace. It resets the message-id counter per seed, so the seeded files come out identical to what a fresh process wrote. The first try without the reset broke 9 tests, which shows how much that detail matters.

| | Before | After |
|---|---|---|
| Seeding, total | 806 s | 11.5 s |
| Full e2e suite | 20:26 | **7:09** |
| `tests/e2e/cultures/test_story.py` | about 10 min | 2:25 |

All 61 tests pass. The change touches one function in `tests/e2e/seed.py`, and its callers are unchanged.

### 2. Run the browser tests on 4 workers (no code change needed)

`pytest tests/e2e -m e2e -n 4` works today, because each xdist worker starts its own isolated app on free ports. Together with item 1, the full suite takes **3:33** (61/61), down from 20:26. That is a 5.7× speedup.

- `-n 8` runs out of memory: each worker's app (backend, vite, Chromium) needs about 2–3 GB, and the run was killed. **4 is the ceiling on this machine.**
- Done on `exp/devloop`: the documented command in `tests/e2e/conftest.py` and `docs/dev/local-testing.md` is now `-n 4`.

### 3. Clean up orphaned test apps

The isolated app starts its children with `start_new_session=True` so that `talemate_app.py start` can detach. As a side effect, when a pytest run is killed (a timeout, a cancelled agent, an out-of-memory kill), its backend and vite keep running.

- Tonight I found one left over from 8 hours earlier (about 1.5 GB). I stopped it.
- A second one, started about 12.5 hours earlier from the main checkout, is still running (`/tmp/pytest-of-skeleton/pytest-384/app0`). I left it alone because I didn't start it.

These orphans are what make memory tight. The fix:

- Have the `app` fixture write the pytest PID into the app root.
- At session start, stop any app under `/tmp/pytest-of-$USER/*/app*` whose recorded pytest PID is gone.
- Or add a `talemate_app.py reap` command that does the same.

### 4. Run only the tests a task touches, and save the full suite for the end

With items 1 and 2 the full suite is only 3.5 min, so this matters less than it did, but it still adds up across fix rounds. The rule is short:

| A change touching | Runs |
|---|---|
| theme or appearance | `tests/e2e/theme` (9 tests) |
| the worlds screens | `tests/e2e/worlds` |
| anything else | the node checks and the plain suite |

Run the full suite once per task, at its end, not in every fix round.

### 5. AI tests: slow because of the model, and they belong in every plan's final pass

I timed the AI group on koboldcpp with `Skyfall-31B-v4.2-i1-Q4_K_M` loaded: 9 tests in **7:18**.

- About 46 s per test is generation time on the GPU server. Seeding (0.3 s per call with the worker) and app start-up (20 s once) barely register.
- One GPU means parallel workers won't help. The only levers are fewer, shorter generations: lower `max_tokens` in tests that only check structure, and one shared generated scene reused by the tests that only read it.
- **The more important finding:** 2 of the 9 tests failed on the fantasymate branch. They waited for `text-green` on the client status dot, and the colour sweep had changed it to `text-success`. Nobody ran the AI group during the plan, because that needs your go-ahead, so the regression went unnoticed. It's fixed on the feature branch (87bbddf), and 2/2 pass on a re-run.
- Lesson: any plan that touches UI the AI tests drive should end with one AI run, or at least a grep of `tests/ai` for the selectors it changes.

## The agent process (from this session's ledger)

The theme/rebrand plan ran as 10 tasks with a builder and a reviewer per task, plus 9 fix rounds and a final review with a fix wave: about 45 agent dispatches, all in sequence.

- **Builders:** about 9–10 hours in total. The two sweep builders took 80 and 55 minutes.
- **Reviewers:** about 1.5 hours in total.
- **Browser tests inside builders:** the builders ran the full or large browser suites at least 12 times, at 17–20 min each. That is roughly 3.5–4 hours of tonight's builder time. With items 1 and 2 the same runs would take about 45 min.
- **Fix rounds:** about half came from things the plan never mentioned: the second message-render path, Vuetify dropping its own colours on a runtime theme swap, CodeMirror, and a duplicate package. Each round cost 30–60 min, mostly re-running tests.

Changes that would have saved the most:

1. **Items 1 and 2 above.** Expected saving: about 3 hours of tonight's run.
2. **Spike risky integrations before writing a plan.** A 15-minute throwaway test of "swap a Vuetify theme at runtime, recolour LiteGraph and CodeMirror" would have exposed all three framework traps up front, and the plan would have named them. Expected saving: 4–5 fix rounds, about 3 hours.
3. **Give mechanical work one builder and one review.** The colour sweep spanned about 120 files across 3 tasks and 4 builders; one builder with one review would have done. Spend the full per-task review on logic: the engine, config, settings, and data-colour safety. Expected saving: about 6 dispatches, about 1 hour.
4. **Give builders a ready-made screenshot command.** Builders spent a lot of turns working out how to seed a scene, set a theme and take screenshots, and two of them couldn't reach the node editor. A `scripts/dev/shots.py` that takes `--presets gruvbox-dark,gruvbox-light --screens home,scene,world,settings,node-editor` and writes a contact sheet would turn that into a single call. (Not built tonight.)
5. **Run independent tasks in parallel worktrees.** The rebrand could have run alongside the theme engine from the start. This is a small win, and it costs coordination.
