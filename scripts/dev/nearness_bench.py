"""Time `world.nearness.near()` on synthetic worlds (curation probe 6).

Builds worlds of 1,000 and 3,000 things -- spheres with drawers, a tree of
places, characters with ties and heritage, items and lore filed with
`part_of` -- with about 8 facts and 3 references per thing, spread over
several revisions with some corrections (so retired rows are in the
tables too), then times `near()` with the default curation knobs from
random starting things, at the latest telling and at a dated view.

No model is called. Run from the repo root:

    guix shell -m manifest.scm -- uv run --no-sync python scripts/dev/nearness_bench.py
"""

from __future__ import annotations

import argparse
import random
import statistics
import tempfile
import time
from pathlib import Path

from talemate.world.dates import WorldDate
from talemate.world.nearness import CurationSettings, near
from talemate.world.refs import ref
from talemate.world.store import Source, World

DRAWER = "d0000001"
FACTS_PER_THING = 8
REFS_PER_THING = 3
REVISIONS = 10


def build(root: Path, size: int, seed: int) -> tuple[World, list[str]]:
    rng = random.Random(seed)
    world = World.create(f"bench {size}", root=root)
    ids: list[str] = []
    kinds: dict[str, str] = {}

    n_spheres = max(5, size // 50)
    n_species = max(3, size // 200)
    n_places = size // 5
    n_characters = size * 2 // 5
    plan: list[str] = (
        ["sphere"] * n_spheres
        + ["species"] * n_species
        + ["place"] * n_places
        + ["character"] * n_characters
    )
    plan += ["item", "lore"] * ((size - len(plan)) // 2 + 1)
    plan = plan[:size]

    spheres: list[str] = []
    species: list[str] = []
    places: list[str] = []
    chunk = len(plan) // REVISIONS + 1
    for start in range(0, len(plan), chunk):
        with world.revision(Source.manual(note="bench build")) as rev:
            for index in range(start, min(start + chunk, len(plan))):
                kind = plan[index]
                name = f"{kind.title()} {index}"
                fields: dict[str, object] = {"name": name}
                if kind == "sphere":
                    fields["template"] = "order"
                    fields["drawers"] = [
                        {"id": DRAWER, "type": "knowledge", "title": "All"}
                    ]
                    if spheres and rng.random() < 0.3:
                        fields["parent"] = rng.choice(spheres)
                elif kind == "place":
                    if places:
                        fields["parent"] = rng.choice(places)
                    if spheres and rng.random() < 0.3:
                        fields["part_of"] = {
                            "sphere": rng.choice(spheres),
                            "drawer": DRAWER,
                        }
                elif kind == "character":
                    if species:
                        fields["heritage"] = rng.choice(species)
                    fields["ties"] = [
                        {
                            "sphere": rng.choice(spheres),
                            "role": "member",
                            "since": None,
                            "until": None,
                        }
                        for _ in range(rng.randint(0, 2))
                    ]
                elif kind in ("item", "lore") and spheres:
                    fields["part_of"] = {
                        "sphere": rng.choice(spheres),
                        "drawer": DRAWER,
                    }
                thing_id = rev.create_thing(kind, fields=fields)
                ids.append(thing_id)
                kinds[thing_id] = kind
                {"sphere": spheres, "species": species, "place": places}.get(
                    kind, []
                ).append(thing_id)

    category = {
        "sphere": "about",
        "species": "general",
        "place": "general",
        "character": "background",
        "item": "general",
        "lore": "general",
    }
    fact_ids: list[str] = []
    chunk = len(ids) // REVISIONS + 1
    for start in range(0, len(ids), chunk):
        with world.revision(Source.manual(note="bench facts")) as rev:
            for thing_id in ids[start : start + chunk]:
                with_refs = set(rng.sample(range(FACTS_PER_THING), REFS_PER_THING))
                for n in range(FACTS_PER_THING):
                    text = f"Fact {n} about this thing."
                    if n in with_refs:
                        text = f"Fact {n}, tied to {ref(rng.choice(ids))}."
                    year = rng.choice([None, rng.randint(1, 1000)])
                    fact_ids.append(
                        rev.add_fact(
                            thing_id,
                            category[kinds[thing_id]],
                            text,
                            valid_from=WorldDate.of(year) if year else None,
                        )
                    )

    with world.revision(Source.manual(note="bench corrections")) as rev:
        for fact_id in rng.sample(fact_ids, len(fact_ids) // 10):
            rev.correct_fact(fact_id, text="A corrected fact.")

    return world, ids


def time_near(
    world: World, ids: list[str], at: WorldDate | None, runs: int, seed: int
) -> list[float]:
    knobs = CurationSettings()
    rng = random.Random(seed)
    view = world.view(at=at)
    near(view, ids[0], reach=knobs.reach, limit=knobs.entries)  # warm up
    timings: list[float] = []
    for _ in range(runs):
        start_id = rng.choice(ids)
        began = time.perf_counter()
        near(view, start_id, reach=knobs.reach, limit=knobs.entries)
        timings.append((time.perf_counter() - began) * 1000)
    return timings


def report(label: str, timings: list[float]) -> str:
    ordered = sorted(timings)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    return (
        f"{label}: median {statistics.median(ordered):.1f} ms, "
        f"p95 {p95:.1f} ms, max {ordered[-1]:.1f} ms (n={len(ordered)})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sizes", type=int, nargs="+", default=[1000, 3000])
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    knobs = CurationSettings()
    print(f"knobs: reach={knobs.reach}, limit (entries)={knobs.entries}")
    with tempfile.TemporaryDirectory() as tmp:
        for size in args.sizes:
            began = time.perf_counter()
            world, ids = build(Path(tmp), size, args.seed)
            built = time.perf_counter() - began
            try:
                rows = {
                    table: world._conn.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                    for table in ("things", "field_values", "facts", "fact_refs")
                }
                print(f"\n{size} things (built in {built:.1f} s): {rows}")
                print(report("  latest", time_near(world, ids, None, args.runs, 1)))
                print(
                    report(
                        "  dated (year 500)",
                        time_near(world, ids, WorldDate.of(500), args.runs, 2),
                    )
                )
            finally:
                world.close()


if __name__ == "__main__":
    main()
