"""Code only, no model: which expected elsewhere targets each candidate
ranking would put in probe 1's lists (curation probe, fix round 1).

Schemes, each at the probe's four variants (reach 1/2/3 at 12, reach 3 at 24):
- `as_run`: `near()` as it is (score, then name);
- `tie`: score ties broken by fewer steps, then more direct references
  between the pair, then name;
- `sib07`: the part_of weight lowered to 0.7 (a sibling through a shared
  sphere then scores 0.49, under a direct reference's 0.6);
- `cap3`: at most 3 structural entries (siblings through the focus's sphere,
  or parts of the focus itself) beyond the first-listed context;
- combinations of these.

Writes `ranking` into the raw JSON and prints a table.

    guix shell -m manifest.scm -- bash -c 'cd scripts/dev && HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python \\
        probe_curation_ranking.py'
"""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path

import probe_curation as probe
from talemate.world import nearness

# targets the probe saw cut that the labels' expected_targets don't hold
WATCH = {
    "fill:Tsardom of Moscavia/Governance & Military": ["White Talon"],
    "create:The Illumination": ["Moskov"],
}


def ranked(view, setup, reach, cap, *, tie, part_of_weight, sibling_cap):
    old = nearness.WEIGHTS["part_of"]
    nearness.WEIGHTS["part_of"] = part_of_weight
    try:
        best: dict[str, tuple[float, int]] = {}
        for focus in setup["focus"]:
            for hit in nearness.near(view, focus, reach=reach, limit=1000):
                if hit.score > best.get(hit.thing_id, (0.0, 0))[0]:
                    best[hit.thing_id] = (hit.score, hit.steps)
    finally:
        nearness.WEIGHTS["part_of"] = old
    links: Counter = Counter()
    focus = set(setup["focus"])
    for owner, target in nearness._references(view):
        if owner in focus:
            links[target] += 1
        if target in focus:
            links[owner] += 1
    name = lambda t: (view.name_of(t) or "").casefold()  # noqa: E731
    if tie:
        key = lambda t: (-best[t][0], best[t][1], -links[t], name(t), t)  # noqa: E731
    else:
        key = lambda t: (-best[t][0], name(t), t)  # noqa: E731
    order = sorted(best, key=key)
    spheres_of_focus = set()
    for f in setup["focus"]:
        st = view.thing(f)
        link = probe.part_of_of(view, st) if st else None
        if link:
            spheres_of_focus.add(link[0])

    def structural(t):
        st = view.thing(t)
        link = probe.part_of_of(view, st) if st else None
        return bool(link) and (link[0] in spheres_of_focus or link[0] in focus)

    out, structural_n = [], 0
    for t in [*setup["first"], *order]:
        st = view.thing(t)
        if t in out or t in setup["exclude"] or st is None or st.stub_ignored:
            continue
        if sibling_cap is not None and t not in setup["first"] and structural(t):
            if structural_n >= sibling_cap:
                continue
            structural_n += 1
        out.append(t)
    return [view.name_of(t) for t in out[:cap]]


SCHEMES = {
    "as_run": dict(tie=False, part_of_weight=1.0, sibling_cap=None),
    "tie": dict(tie=True, part_of_weight=1.0, sibling_cap=None),
    "sib07": dict(tie=False, part_of_weight=0.7, sibling_cap=None),
    "sib07+tie": dict(tie=True, part_of_weight=0.7, sibling_cap=None),
    "cap3": dict(tie=False, part_of_weight=1.0, sibling_cap=3),
    "cap3+tie": dict(tie=True, part_of_weight=1.0, sibling_cap=3),
}


def main() -> None:
    labels = json.loads(probe.LABELS.read_text())
    raw = probe.REPO / "docs/superpowers/probes/raw/2026-10-22-curation.json"
    results = json.loads(raw.read_text())
    table = {}
    with tempfile.TemporaryDirectory() as root:
        worlds = probe.Worlds(Path(root))
        for key, spec in labels["probe1"]["cases"].items():
            world, setup = probe.case_setup(worlds, key, spec)
            view = world.view()
            wanted = list(dict.fromkeys(spec["expected_targets"] + WATCH.get(key, [])))
            for variant, knobs in labels["probe1"]["variants"].items():
                row = {}
                for scheme, kw in SCHEMES.items():
                    names = ranked(view, setup, knobs["reach"], knobs["entries"], **kw)
                    row[scheme] = [t for t in wanted if t not in names]
                table[f"{key}|{variant}"] = {"wanted": wanted, "missing": row}
            world.close()
    totals = Counter()
    for entry in table.values():
        for scheme, missing in entry["missing"].items():
            totals[scheme] += len(missing)
    results["ranking"] = {"note": __doc__.split("\n\n")[0], "cases": table, "missing_total": dict(totals)}
    raw.write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str) + "\n")
    for k, v in table.items():
        if any(v["missing"].values()):
            print(k, {s: m for s, m in v["missing"].items()})
    print("missing totals:", dict(totals))


if __name__ == "__main__":
    main()
