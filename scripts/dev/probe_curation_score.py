"""Scores for the curation probe (`probe_curation.py`), against the hand
labels and the after-run judgments (`judged` in the raw JSON, made by hand,
not blind, as in the fact placement probe's `b_judged`).

    guix shell -m manifest.scm -- bash -c 'cd scripts/dev && HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python \\
        probe_curation_score.py [RAW.json]'

Writes `scores` into the raw JSON and prints the summary.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from talemate.world.repeats import content_words, overlap
from talemate.world.store import World

import probe_curation as probe

RAW = probe.REPO / "docs/superpowers/probes/raw/2026-10-22-curation.json"


def pct(a: int, b: int) -> str:
    return f"{a}/{b} ({round(100 * a / b) if b else 0}%)"


def cost(rows: list[dict]) -> dict:
    secs = [r["seconds"] for r in rows if r.get("seconds") is not None]
    pt = [r["prompt_tokens"] for r in rows if r.get("prompt_tokens")]
    rt = [r["reply_tokens"] for r in rows if r.get("reply_tokens")]
    return {
        "calls": len(rows),
        "seconds_mean": round(mean(secs), 1) if secs else None,
        "seconds_range": [min(secs), max(secs)] if secs else None,
        "prompt_tokens_mean": round(mean(pt)) if pt else None,
        "prompt_tokens_max": max(pt) if pt else None,
        "reply_tokens_mean": round(mean(rt)) if rt else None,
        "reply_tokens_max": max(rt) if rt else None,
    }


# --- probe 3 -------------------------------------------------------------------


def score_p3(rows: list[dict], labels: dict) -> dict:
    cases = labels["probe3"]["cases"]
    right = total = false = clean = 0
    per_case = {}
    for key, spec in cases.items():
        contra = spec["contradictions"]
        bonus = spec.get("bonus", [])
        in_contra = {x for c in contra for x in c["a"] + c["b"]}
        in_bonus = {x for c in bonus for x in c["a"] + c["b"]}
        runs = [r for r in rows if r["case"] == key]
        case_right = case_false = 0
        for run in runs:
            pairs = [(p["a"], p["b"]) for p in run["pairs"] if p["a"] and p["b"]]
            for c in contra:
                total += 1
                if any(a in c["a"] and b in c["b"] for a, b in pairs):
                    right += 1
                    case_right += 1
            facts = set(run["a_labels"].values()) | set(run["b_labels"].values())
            clean_facts = facts - in_contra - in_bonus
            clean += len(clean_facts)
            flagged = set()
            for a, b in pairs:
                hit = any(a in c["a"] and b in c["b"] for c in contra + bonus)
                if not hit:
                    flagged |= {a, b} & clean_facts
            false += len(flagged)
            case_false += len(flagged)
        per_case[key] = {
            "found": f"{case_right}/{len(contra) * len(runs)}",
            "false_facts": case_false,
            "bonus_found": sum(
                1
                for run in runs
                for c in bonus
                if any(p["a"] in c["a"] and p["b"] in c["b"] for p in run["pairs"])
            ),
        }
    return {
        "right": pct(right, total),
        "right_share": right / total if total else 0,
        "false": pct(false, clean),
        "false_share": false / clean if clean else 0,
        "per_case": per_case,
        "cost": cost(rows),
    }


def p3_texts(view, spec: dict) -> dict[str, tuple[str, int | None]]:
    """`label value -> (text, start year)` of a probe 3 side."""

    out = {}
    if "entry" in spec:
        state = probe.by_name(view, spec["entry"])
        for f in state.facts:
            year = f.valid_from.to_datetime().year if f.valid_from else None
            out[f.fact_id[:8]] = (view.render(f.text), year)
    elif "facts" in spec:
        for prefix in spec["facts"]:
            _, f = probe.fact_by_prefix(view, prefix)
            year = f.valid_from.to_datetime().year if f.valid_from else None
            out[prefix] = (view.render(f.text), year)
    else:
        for key, text in spec["texts"].items():
            out[key] = (text, None)
    return out


def score_p3_code(world: World, labels: dict, threshold: float = 0.4) -> dict:
    """The spec's fallback: every A-B pair with high word overlap shown side
    by side, no model; and Task 2's date rule (same words, different
    years) on its own."""

    view = world.view()
    shown = found = total = dated_found = dated_total = dated_false = 0
    per_case = {}
    for key, spec in labels["probe3"]["cases"].items():
        a = p3_texts(view, spec["a"])
        b = p3_texts(view, spec["b"])
        pairs = []
        for ka, (ta, ya) in a.items():
            for kb, (tb, yb) in b.items():
                score = max(overlap(ta, tb), overlap(tb, ta))
                if score >= threshold:
                    pairs.append((ka, kb, ya, yb))
        hits = sum(
            1
            for c in spec["contradictions"]
            if any(x in c["a"] and y in c["b"] for x, y, _, _ in pairs)
        )
        dated = [(x, y) for x, y, ya, yb in pairs if ya and yb and ya != yb]
        d_hits = sum(
            1
            for c in spec["contradictions"]
            if any(x in c["a"] and y in c["b"] for x, y in dated)
        )
        d_false = sum(
            1
            for x, y in dated
            if not any(x in c["a"] and y in c["b"] for c in spec["contradictions"])
        )
        shown += len(pairs)
        found += hits
        total += len(spec["contradictions"])
        dated_found += d_hits
        dated_false += d_false
        dated_total += len(dated)
        per_case[key] = {
            "pairs_shown": len(pairs),
            "of_all_pairs": len(a) * len(b),
            "contradictions_among_them": f"{hits}/{len(spec['contradictions'])}",
            "dated_disagreements": len(dated),
            "dated_hits": d_hits,
        }
    return {
        "threshold": threshold,
        "contradictions_shown": pct(found, total),
        "pairs_shown": shown,
        "date_rule": {
            "found": pct(dated_found, total),
            "flagged": dated_total,
            "false": dated_false,
        },
        "per_case": per_case,
    }


# --- same thing ----------------------------------------------------------------------


def score_same(rows: list[dict]) -> dict:
    right = sum(1 for r in rows if (r["verdict"] == "same") == (r["truth"] == "same"))
    not_same = [r for r in rows if r["truth"] != "same"]
    false = sum(1 for r in not_same if r["verdict"] == "same")
    same_rows = [r for r in rows if r["truth"] == "same"]
    by_pair = defaultdict(list)
    for r in rows:
        by_pair[r["pair"]].append(r["verdict"])
    return {
        "right": pct(right, len(rows)),
        "right_share": right / len(rows) if rows else 0,
        "same_called_same": pct(sum(r["verdict"] == "same" for r in same_rows), len(same_rows)),
        "false_same": pct(false, len(not_same)),
        "false_share": false / len(not_same) if not_same else 0,
        "by_pair": dict(by_pair),
        "stable": sum(1 for v in by_pair.values() if len(set(v)) == 1),
        "cost": cost(rows),
    }


# --- probe 2 ----------------------------------------------------------------------------


def score_p2(rows: list[dict], labels: dict) -> dict:
    right = total = false = stays = 0
    per_case = {}
    for key, spec in labels["probe2"]["cases"].items():
        runs = [r for r in rows if r["case"] == key]
        moved_all = []
        for run in runs:
            moved = {m for m in run.get("move_in_ids") or [] if m}
            moved_all.append(sorted(moved))
            right += len(moved & set(spec["move"]))
            total += len(spec["move"])
            false += len(moved & set(spec["stay"]))
            stays += len(spec["stay"])
        per_case[key] = {
            "move": spec["move"],
            "either": spec["either"],
            "picked": moved_all,
            "kept_out_of_facts": [
                not any(
                    max(overlap(f["text"] or "", t), 0) >= 0.6
                    for f in run["facts"]
                    for _, t in (run.get("broader") or [])
                    if run.get("broader_labels")
                )
                for run in runs
            ],
        }
    return {
        "right": pct(right, total),
        "right_share": right / total if total else 0,
        "false": pct(false, stays),
        "false_share": false / stays if stays else 0,
        "per_case": per_case,
        "cost": cost([r for r in rows if "p2" in r["probes"]]),
    }


# --- probe 5 ------------------------------------------------------------------------------


def _names(run: dict) -> list[dict]:
    return [n for n in run.get("names") or [] if isinstance(n, dict)]


def chain(run: dict, view) -> dict:
    """What the reply proposes: its own part_of, and each new body (a
    sphere name not in the world) something is put inside."""

    names = _names(run)
    own = run.get("part_of") if isinstance(run.get("part_of"), dict) else None
    new_bodies = {}
    for n in names:
        if n.get("kind") == "sphere" and probe.resolve(view, n.get("name")) is None:
            new_bodies[probe.name_key(n.get("name") or "")] = n
    inside = []
    targets = [own] + [n.get("part_of") for n in names if isinstance(n.get("part_of"), dict)]
    for t in targets:
        if isinstance(t, dict):
            key = probe.name_key(str(t.get("entry") or ""))
            if key in new_bodies:
                inside.append(new_bodies[key])
    return {"own": own, "new_bodies": list(new_bodies.values()), "used_as_outer": inside}


def score_p5(
    rows: list[dict], p1_rows: list[dict], labels: dict, world: World, prefix: str = ""
) -> dict:
    view = world.view()
    positives = [prefix + key for key in labels["probe5"]["positives"]]
    pos_right = pos_total = 0
    per = {}
    for key in positives:
        for run in [r for r in rows if r["case"] == key]:
            c = chain(run, view)
            ok = False
            body = None
            own = c["own"] or {}
            key_own = probe.name_key(str(own.get("entry") or ""))
            for b in c["new_bodies"]:
                if probe.name_key(b.get("name") or "") == key_own:
                    body = b
            if body is not None:
                po = body.get("part_of") if isinstance(body.get("part_of"), dict) else {}
                ok = (
                    (body.get("template") in ("order", None) or True)
                    and probe.resolve(view, po.get("entry")) is not None
                    and probe.name_key(po.get("entry")) == probe.name_key("Tsardom of Moscavia")
                    and "military" in str(po.get("drawer") or "").lower()
                )
            pos_total += 1
            pos_right += ok
            per.setdefault(key, []).append(
                {
                    "ok": ok,
                    "own_part_of": c["own"],
                    "body": body,
                    "new_spheres": [b.get("name") for b in c["new_bodies"]],
                }
            )
    negatives = [r for r in rows if r["case"] in labels["probe5"]["negatives"]]
    negatives += [r for r in p1_rows if r["case"].startswith("create:")]
    invented = []
    for run in negatives:
        c = chain(run, view)
        if c["used_as_outer"]:
            invented.append(
                {
                    "case": run["case"],
                    "variant": run.get("variant"),
                    "n": run["n"],
                    "bodies": [b.get("name") for b in c["used_as_outer"]],
                }
            )
    neg_parts = defaultdict(list)
    for run in [r for r in rows if r["case"] in labels["probe5"]["negatives"]]:
        neg_parts[run["case"]].append(run.get("part_of"))
    return {
        "right": pct(pos_right, pos_total),
        "right_share": pos_right / pos_total if pos_total else 0,
        "false": pct(len(invented), len(negatives)),
        "false_share": len(invented) / len(negatives) if negatives else 0,
        "positives": per,
        "invented": invented,
        "negative_part_of": dict(neg_parts),
    }


# --- probes 1 and 4 (hand judgments) ---------------------------------------------------------


def own_items(run: dict) -> list[str]:
    """A probe 1 run's own texts, in the order the judgments index them."""

    if run["case"].startswith("create:"):
        return [f.get("text") or "" for f in run.get("facts") or []]
    if run["case"].startswith("core:"):
        texts = [run.get("summary") or ""]
        texts += [
            t.get("text") or "" for t in run.get("timeline") or [] if isinstance(t, dict)
        ]
        texts += [
            (f"{i.get('name')}: " if i.get("name") else "") + (i.get("text") or "")
            for i in run.get("items") or []
            if isinstance(i, dict)
        ]
        return texts
    return [
        (f"{i.get('name')}: " if i.get("name") else "") + (i.get("text") or "")
        for i in run.get("new_items") or []
        if isinstance(i, dict)
    ]


def run_key(run: dict) -> str:
    return f"{run['case']}|{run.get('variant', 'r2')}|{run['n']}"


def score_p1(rows: list[dict], judged: dict, lists: list[dict], labels: dict) -> dict:
    by = defaultdict(lambda: Counter())
    by_variant = defaultdict(lambda: Counter())
    for run in rows:
        j = judged.get(run_key(run))
        if j is None:
            continue
        prompt = run["case"].split(":")[0]
        key = (run["case"], run["variant"])
        own = j.get("own", "")
        for code in own:
            for c in (by[key], by_variant[(prompt, run["variant"])], by_variant[(prompt, "all")]):
                c["own"] += 1
                c["on"] += code == "o"
        for code in j.get("else", ""):
            for c in (by[key], by_variant[(prompt, run["variant"])], by_variant[(prompt, "all")]):
                c["else"] += 1
                c["right"] += code in "rn"
                c["false"] += code == "f"
                c["wrong"] += code == "w"
                c["new_bad"] += code == "x"
                c["new_ok"] += code == "n"
        for c in (by[key], by_variant[(prompt, run["variant"])], by_variant[(prompt, "all")]):
            c["runs"] += 1
            c["prompt_tokens"] += run.get("prompt_tokens") or 0
            c["nearby_tokens"] += 0
    def summary(c: Counter) -> dict:
        return {
            "runs": c["runs"],
            "own_on_topic": pct(c["on"], c["own"]),
            "on_share": c["on"] / c["own"] if c["own"] else 0,
            "elsewhere_items": c["else"],
            "elsewhere_right": pct(c["right"], c["else"]),
            "right_share": c["right"] / c["else"] if c["else"] else 0,
            "false_moves": pct(c["false"], c["else"]),
            "false_share": c["false"] / c["else"] if c["else"] else 0,
            "false_over_all_facts": pct(c["false"], c["own"] + c["else"]),
            "wrong_entry": c["wrong"],
            "to_new_ok": c["new_ok"],
            "to_new_bad": c["new_bad"],
            "prompt_tokens_mean": round(c["prompt_tokens"] / c["runs"]) if c["runs"] else None,
        }
    # expected targets missing from each candidate list
    missing = {}
    for entry in lists:
        if entry["same_as"]:
            continue
        spec = labels["probe1"]["cases"][entry["case"]]
        names = {c["name"] for c in entry["candidates"]}
        missing[f"{entry['case']}|{entry['variant']}"] = [
            t for t in spec["expected_targets"] if t not in names
        ]
    return {
        "per_case_variant": {f"{k[0]}|{k[1]}": summary(v) for k, v in by.items()},
        "per_prompt_variant": {f"{k[0]}|{k[1]}": summary(v) for k, v in by_variant.items()},
        "expected_targets_missing": missing,
        "cost": {
            prompt: cost([r for r in rows if r["case"].startswith(prompt + ":")])
            for prompt in ("create", "core", "fill")
        },
    }


def score_p4(p1_rows: list[dict], creates: list[dict], judged: dict) -> dict:
    """`judged[key]["held"]`: per own fact (create runs) a code: b belief,
    a attributed, p plain; `["else_held"]` the same per elsewhere item."""

    stats = defaultdict(Counter)
    church = {"church of the eternal light", "the church", "the light"}
    for run in [r for r in p1_rows if r["case"].startswith("create:")] + [
        r for r in creates if "p4" in r["probes"]
    ]:
        j = judged.get(run_key(run))
        if not j:
            continue
        groups = [("facts", run.get("facts") or [], j.get("held", ""))]
        groups.append(("elsewhere", run.get("elsewhere") or [], j.get("else_held", "")))
        for where, items, codes in groups:
            for item, code in zip(items, codes):
                holder = item.get("held_by")
                marked = isinstance(holder, str) and holder.strip() != ""
                right_holder = marked and str(holder).strip().casefold() in church
                for key in (run["case"], f"all {where}", "all"):
                    s = stats[key]
                    if code == "b":
                        s["belief"] += 1
                        s["belief_right"] += right_holder
                        s["belief_wrong_holder"] += marked and not right_holder
                    elif code == "p":
                        s["plain"] += 1
                        s["plain_marked"] += marked
                    elif code == "a":
                        s["attributed"] += 1
                        s["attributed_marked"] += marked
    out = {}
    for key, s in stats.items():
        out[key] = {
            "beliefs_marked_right": pct(s["belief_right"], s["belief"]),
            "right_share": s["belief_right"] / s["belief"] if s["belief"] else 0,
            "wrong_holder": s["belief_wrong_holder"],
            "plain_marked": pct(s["plain_marked"], s["plain"]),
            "false_share": s["plain_marked"] / s["plain"] if s["plain"] else 0,
            "attributed_marked": pct(s["attributed_marked"], s["attributed"]),
        }
    return out


def main(raw_path: Path) -> None:
    labels = json.loads(probe.LABELS.read_text())
    results = json.loads(raw_path.read_text())
    judged = results.get("judged", {})
    with tempfile.TemporaryDirectory() as root:
        worlds = probe.Worlds(Path(root))
        head = worlds.open("head")
        w5 = worlds.open("w5")
        scores = {
            "p3": score_p3(results["p3"], labels),
            "p3v2": score_p3(results["p3v2"], labels) if results.get("p3v2") else None,
            "p3_code": score_p3_code(head, labels),
            "same": score_same(results["same"]),
            "p2": score_p2([r for r in results["creates"] if "p2" in r["probes"]], labels),
            "p5": score_p5(
                [r for r in results["creates"] if "p5" in r["probes"]],
                results["p1"],
                labels,
                w5,
            ),
            "p5v2_positives": score_p5(
                [r for r in results["creates"] if "p5v2" in r["probes"]],
                [],
                labels,
                w5,
                "v2:",
            )["positives"],
            "p1": score_p1(results["p1"], judged, results["p1_lists"], labels),
            "p1v3": score_p1(
                results.get("p1v3", []),
                {k[3:]: v for k, v in judged.items() if k.startswith("v3:")},
                [],
                labels,
            ),
            "p4": score_p4(results["p1"], results["creates"], judged),
            "p4_v3": score_p4(
                results.get("p1v3", []),
                [],
                {k[3:]: v for k, v in judged.items() if k.startswith("v3:")},
            ),
            "creates_cost": cost(results["creates"]),
        }
        head.close()
        w5.close()
    results["scores"] = scores
    raw_path.write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str) + "\n")
    print(json.dumps(scores, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else RAW)
