"""Code only, no model: the repeat detector (Task 2's `find_repeats`, 0.4)
on probe 1's runs (curation probe), against the after-run judgments.

- each elsewhere item, against its target and the target's reach-1
  neighbours (12 at most): which judged items it would untick;
- each create run's own facts, against the stub's reach-2 neighbours (12).

Writes `repeats` into the raw JSON and prints the counts.

    guix shell -m manifest.scm -- bash -c 'cd scripts/dev && HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python \\
        probe_curation_repeats.py'
"""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path

import probe_curation as probe
from talemate.world.nearness import near
from talemate.world.repeats import find_repeats

THRESHOLD = 0.4


def main() -> None:
    raw = probe.REPO / "docs/superpowers/probes/raw/2026-10-22-curation.json"
    d = json.loads(raw.read_text())
    j = d["judged"]
    labels = json.loads(probe.LABELS.read_text())
    elsewhere, own = Counter(), Counter()
    with tempfile.TemporaryDirectory() as root:
        worlds = probe.Worlds(Path(root))
        cache = {}
        for r in d["p1"]:
            jj = j.get(f"{r['case']}|{r['variant']}|{r['n']}")
            if not jj or jj.get("failed"):
                continue
            spec = labels["probe1"]["cases"][r["case"]]
            if spec["world"] not in cache:
                cache[spec["world"]] = worlds.open(spec["world"])
            view = cache[spec["world"]].view()
            prompt = r["case"].split(":")[0]
            for e, code in zip(r["elsewhere"], jj["else"]):
                if not e["target_id"]:
                    elsewhere[f"{prompt}|{code}|new"] += 1
                    continue
                owners = [e["target_id"]] + [
                    n.thing_id for n in near(view, e["target_id"], reach=1, limit=12)
                ]
                hit = find_repeats(view, [e["text"] or ""], owners, THRESHOLD)
                elsewhere[f"{prompt}|{code}|{'repeat' if hit else 'fresh'}"] += 1
            if prompt == "create":
                focus = probe.by_name(view, spec["stub"]).id
                owners = [n.thing_id for n in near(view, focus, reach=2, limit=12)]
                texts = [f["text"] or "" for f in r["facts"]]
                hits = {h.index for h in find_repeats(view, texts, owners, THRESHOLD)}
                for i, code in enumerate(jj["own"]):
                    own[f"{r['case']}|{code}|{'repeat' if i in hits else 'fresh'}"] += 1
        for w in cache.values():
            w.close()
    d["repeats"] = {
        "note": __doc__.split("\n\n")[0],
        "threshold": THRESHOLD,
        "elsewhere": dict(sorted(elsewhere.items())),
        "own_create_facts": dict(sorted(own.items())),
    }
    raw.write_text(json.dumps(d, indent=1, ensure_ascii=False, default=str) + "\n")
    print(json.dumps(d["repeats"], indent=1))


if __name__ == "__main__":
    main()
