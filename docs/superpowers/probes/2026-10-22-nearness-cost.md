# Probe 6: nearness cost

Date: 2026-10-22. Code only, no model. This is curation probe 6 (Curation Task 1). It decides whether `world.nearness.near()` can be computed on demand per prompt, or needs a stored adjacency list. The target is under 50 ms per prompt at 1,000 entries.

- Script: `scripts/dev/nearness_bench.py` (`--sizes`, `--runs`, `--seed`; defaults 1000 and 3000, 50 runs, seed 7).
- Machine: AMD Ryzen 7 5800X, SQLite file in a temp dir (WAL), run through `guix shell -m manifest.scm -- uv run --no-sync`.
- Knobs: the `CurationSettings` defaults, so `reach=2` and `limit=entries=12`.

## The synthetic worlds

Each world is built over about 20 revisions, so the tables hold history:
- about 2% spheres with one drawer (30% of them branch from an earlier sphere);
- a few species;
- 20% places in a random `parent` tree (30% of them also filed `part_of` a sphere);
- 40% characters, each with a heritage and 0–2 ties;
- the rest items and lore, each `part_of` a sphere.

Things are padded with fields that aren't links:
- characters get `born` and `color`;
- places get `kind`;
- 30% of things get another name (`aka`).

Every thing gets 8 facts, 3 of which reference a random thing; half the facts are dated. A final revision leaves retired and superseded rows behind:
- it corrects 10% of the facts;
- it corrects 20% of names at the same date, which retires the old row;
- it gives 10% of things a later name from year 600;
- it re-parents 10% of places from year 700.

| size | things | field_values | facts | fact_refs |
|---|---|---|---|---|
| 1,000 | 1,000 | 4,138 | 8,800 | 3,000 |
| 3,000 | 3,000 | 12,326 | 26,400 | 9,000 |

The "latest" and "dated" rows are 50 calls each, every one from a random start, on one view. The "first call after reopen" row is 10 runs. Each run closes the world, reopens it with a fresh connection and no SQLite page cache, and times a single call. The bench also times every full (generation 2) Python garbage collection during a run.

## Results

This is the fix-round 1 run, with padded fields and field corrections.

| size | view | median | p95 | max | full GCs in the run |
|---|---|---|---|---|---|
| 1,000 | latest | 12.8 ms | 14.9 ms | 18.6 ms | 0 |
| 1,000 | dated (year 500) | 12.0 ms | 15.0 ms | 237.0 ms | 1 (223 ms) |
| 1,000 | first call after reopen | 14.7 ms | 16.9 ms | 16.9 ms | 0 |
| 3,000 | latest | 43.6 ms | 53.8 ms | 273.7 ms | 1 (224 ms) |
| 3,000 | dated (year 500) | 42.1 ms | 48.0 ms | 277.4 ms | 2 (217, 227 ms) |
| 3,000 | first call after reopen | 46.9 ms | 50.7 ms | 50.7 ms | 0 |

Each max outlier is one full garbage collection, and the GC pause matches its size: about 220 ms, on Python 3.11 with thresholds (700, 10, 10). That pause scales with the whole process heap, most of which is talemate's imports, not with `near()`'s own work. `near()` only allocates enough to trigger a full GC about once every 50–100 calls at 3,000 entries. Outside those calls the max stays within a few ms of the p95.

The first call after a reopen costs about the same as a warm call, so `near()` needs no warm-up.

The first run, before the padding, gave 13.0 ms median at 1,000 and 42.2 ms at 3,000. The padding, about 1.6 times as many field values, barely moves the median, because the link query filters on `field`.

The very first version was slower: 17.8 ms median at 1,000 and 58 ms at 3,000. Profiling at 3,000 entries gave these costs:
- the windowed field-values query: 28 ms;
- the references query: 12 ms;
- live things: 2 ms.

Two changes cut the time:
- plain tuple rows instead of `sqlite3.Row`;
- picking the in-force field value in Python. The rule is unchanged from `WorldView._fetch_fields`: greatest `valid_from` (NULL lowest), then `row_id`. The window function cost three times as much.

## Decision

**On demand, with no stored table.** At 1,000 entries the call takes 13 ms, about a quarter of the 50 ms budget, and 15 ms cold after a reopen. A rare full GC pause is the process's cost, and a stored table wouldn't remove it. So no adjacency table is added, and nothing has to stay in step with revisions or undo.

The cost grows linearly, because every call reads the whole world's links. At 3,000 entries it is about 43 ms, still under the target; the p95 is close to 50 ms. If worlds grow well past 3,000 entries, or one prompt needs several rankings, there are two options:
- cache the link graph per `(rev, at)` within a request;
- the stored adjacency table, which was the owner's alternative.
