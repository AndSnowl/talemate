"""Scores for the filing probe (`probe_filing.py`), from its raw JSON and
the hand labels. Code scores what the labels fix in advance (tags against
the tags in use, "in" and "file into" against expected / either / false);
the judgements made by hand after the run (role sanity, thin names,
synopsis claims, belief facts, "+ Add" fit, the scene turns) are read
from the raw JSON's `judged` object and only tallied here::

    python scripts/dev/probe_filing_score.py RAW.json [--write]

`--write` stores the tallies under `scores` in the raw JSON.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

LABELS = Path(__file__).resolve().parents[2] / "docs/superpowers/probes/raw/2026-10-23-filing-labels.json"


def key(name: str | None) -> str:
    name = (name or "").strip().casefold()
    return re.sub(r"^(the|a|an) ", "", name)


def tag_score(row: dict, label: dict) -> dict:
    tag = key(row["parse"].get("tag"))
    in_use = {key(t.rsplit(" (", 1)[0]) for t in row.get("tags") or []}
    fits = [key(t) for t in label["tag"]["fits_in_use"] if key(t) in in_use]
    ok_new = [key(t) for t in label["tag"]["acceptable_new"]]
    if fits:
        verdict = "reused" if tag in fits else ("other in use" if tag in in_use else "coined, should reuse")
        good = tag in fits
    else:
        verdict = "reused" if tag in in_use else "coined"
        good = tag in ok_new
    return {"tag": tag, "verdict": verdict, "good": good, "should_reuse": bool(fits)}


def filing_score(items: list[dict], label: dict) -> dict:
    expected = {key(n) for n in label.get("expected", [])}
    either = {key(n) for n in label.get("either", [])}
    any_of = {key(n) for n in label.get("expected_any", [])}
    offered = []
    for item in items:
        name = key(item.get("target") or item.get("entry"))
        if name and name not in offered:
            offered.append(name)
    found = [n for n in offered if n in expected]
    false = [n for n in offered if n not in expected | either | any_of]
    need = len(expected) + (1 if any_of else 0)
    got = len(found) + (1 if any_of and any(n in any_of for n in offered) else 0)
    return {"offered": offered, "found": got, "need": need, "false": false}


def main(raw_path: Path, write: bool) -> None:
    raw = json.loads(raw_path.read_text())
    labels = json.loads(LABELS.read_text())
    judged = raw.get("judged", {})
    scores: dict = {}
    for probe, label_key in (("p1", "probe1"), ("p2", "probe2"), ("p1v2", "probe1"), ("p2v2", "probe2")):
        rows = raw.get(probe) or []
        totals = defaultdict(int)
        per_case = []
        for row in rows:
            case = labels[label_key]["cases"][row["case"]]
            entry = {"case": row["case"], "run": row["run"], "error": row.get("error"), "parsed": row["parse"]["parsed"]}
            # code-side: an existing name the reply files in this entry is
            # offered as "file into" too
            this = key(case.get("entry") or case.get("new"))
            merged = list(row["parse"]["file_into"]) + [
                {"entry": n["name"], "target": n["exists"]}
                for n in row["parse"]["names"]
                if n.get("exists") and key(n.get("in")) == this
            ]
            for field, items, label_field in (("in", row["parse"]["in"], "in"), ("file_into", row["parse"]["file_into"], "file_into"), ("file_into_merged", merged, "file_into")):
                s = filing_score(items, case[label_field])
                entry[field] = s
                totals[f"{field}_found"] += s["found"]
                totals[f"{field}_need"] += s["need"]
                totals[f"{field}_offered"] += len(s["offered"])
                totals[f"{field}_false"] += len(s["false"])
            if probe in ("p1", "p1v2"):
                t = tag_score(row, case)
                entry["tag"] = t
                totals["tag_good"] += t["good"]
                totals["tag_n"] += 1
                if t["should_reuse"]:
                    totals["reuse_n"] += 1
                    totals["reuse_ok"] += t["verdict"] == "reused"
            names = row["parse"]["names"]
            entry["names"] = len(names)
            entry["names_tagged"] = sum(bool(n.get("tag")) and key(n.get("tag")) not in ("proper", "common") for n in names)
            entry["names_with_in"] = sum(bool(n.get("in")) for n in names)
            entry["names_new"] = sum(not n.get("exists") for n in names)
            totals["names"] += len(names)
            totals["names_tagged"] += entry["names_tagged"]
            totals["names_with_in"] += entry["names_with_in"]
            totals["names_new"] += entry["names_new"]
            entry["facts"] = len(row["parse"]["facts"])
            entry["seconds"] = row.get("seconds")
            entry["prompt_tokens"] = row.get("prompt_tokens")
            entry["reply_tokens"] = row.get("reply_tokens")
            per_case.append(entry)
        scores[probe] = {"cases": per_case, "totals": dict(totals)}
    scores["judged"] = judged
    print(json.dumps({k: v["totals"] for k, v in scores.items() if isinstance(v, dict) and "totals" in v}, indent=1))
    for probe in ("p1", "p2", "p1v2", "p2v2"):
        for e in scores.get(probe, {}).get("cases", []):
            print(probe, e["case"], e["run"], "tag:", e.get("tag", {}).get("tag"), e.get("tag", {}).get("verdict"),
                  "| in", e["in"]["found"], "/", e["in"]["need"], "false", e["in"]["false"],
                  "| into", e["file_into"]["found"], "/", e["file_into"]["need"], "offered", e["file_into"]["offered"], "false", e["file_into"]["false"], "merged", e["file_into_merged"]["offered"],
                  "| names", e["names"], "tagged", e["names_tagged"], "in", e["names_with_in"], "new", e["names_new"],
                  "|", e["seconds"], "s", e["prompt_tokens"], "/", e["reply_tokens"], "tok")
    if write:
        raw["scores"] = scores
        raw_path.write_text(json.dumps(raw, indent=1, ensure_ascii=False, default=str) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("raw", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    main(args.raw, args.write)
