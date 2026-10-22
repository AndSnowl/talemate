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

Every thing gets 8 facts, 3 of which reference a random thing; half the facts are dated. A final revision corrects 10% of the facts, which leaves retired rows behind.

| size | things | field_values | facts | fact_refs |
|---|---|---|---|---|
| 1,000 | 1,000 | 2,480 | 8,800 | 3,000 |
| 3,000 | 3,000 | 7,458 | 26,400 | 9,000 |

Timings come from 50 calls per row, each from a random start, on one view.

## Results

| size | view | median | p95 | max |
|---|---|---|---|---|
| 1,000 | latest | 13.0 ms | 15.2 ms | 15.6 ms |
| 1,000 | dated (year 500) | 12.2 ms | 12.9 ms | 13.3 ms |
| 3,000 | latest | 42.2 ms | 46.1 ms | 47.3 ms |
| 3,000 | dated (year 500) | 39.0 ms | 42.2 ms | 51.0 ms |

The first version was slower: 17.8 ms median at 1,000 and 58 ms at 3,000. Its p95 at 3,000 was 275 ms, from Python garbage collection on `sqlite3.Row` allocations. Profiling at 3,000 entries gave these costs:
- the windowed field-values query: 28 ms;
- the references query: 12 ms;
- live things: 2 ms.

Two changes fixed it:
- plain tuple rows instead of `sqlite3.Row`;
- picking the in-force field value in Python. The rule is unchanged from `WorldView._fetch_fields`: greatest `valid_from` (NULL lowest), then `row_id`. The window function cost three times as much.

These changes took away the GC spikes as well.

## Decision

**On demand, with no stored table.** At 1,000 entries the call takes 13 ms, about a quarter of the 50 ms budget. So no adjacency table is added, and nothing has to stay in step with revisions or undo.

The cost grows linearly, because every call reads the whole world's links. At 3,000 entries it is about 40 ms, still under the target. If worlds grow well past 3,000 entries, or one prompt needs several rankings, there are two options:
- cache the link graph per `(rev, at)` within a request;
- the stored adjacency table, which was the owner's alternative.
