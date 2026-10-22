"""Scoring for the fact placement probe (`probe_fact_placement.py --only
score`): the model's replies against the hand labels, and the code-side
checks (a token-overlap restatement detector, name overlap for
same-thing candidates). No model call."""

from __future__ import annotations

import re
import statistics
from collections import Counter
from typing import Any

from talemate.world.store import World

STOP = set(
    """a an the of and or in on at to for from by with as is are was were be been
    its it their his her this that these those which who whom into over under
    than then so such not no nor but if all any each every some most more many
    much one two can could may might would will shall should has have had do does
    did also only even both either very own same other another within without
    through about after before since while where when there here what how""".split()
)
THRESHOLDS = (0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.7, 0.8)
RETRIEVE_K = 10


# --- text -----------------------------------------------------------------------


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {_stem(w) for w in words if w not in STOP and len(w) > 1}


def containment(new: set[str], old: set[str]) -> float:
    """How much of the new fact's words the old fact holds."""

    return len(new & old) / len(new) if new else 0.0


def norm_name(name: str) -> str:
    name = re.sub(r"^the\s+", "", name.strip().lower())
    return re.sub(r"[^a-z0-9 ]", "", name).strip()


def _names_match(a: str, b: str) -> bool:
    """Loose: one name inside the other (for names of entries not made yet)."""

    a, b = norm_name(a), norm_name(b)
    return bool(a) and bool(b) and (a == b or a in b or b in a)


def _same_name(a: str, b: str) -> bool:
    """Strict: the same name, bar "the", case and punctuation."""

    return bool(norm_name(a)) and norm_name(a) == norm_name(b)


# --- A -----------------------------------------------------------------------------


def _label_index(labels: dict) -> dict[str, tuple[str, dict]]:
    return {
        f["fact"]: (entry, f)
        for entry, spec in labels["entries"].items()
        for f in spec["facts"]
    }


def _home_of(p: dict, e_labels: dict, view, self_id: str) -> tuple[str, str | None]:
    """("this" | "entry" | "new" | "none", name)."""

    home = p.get("home")
    if isinstance(home, dict):
        return "new", str(home.get("new") or home.get("name") or "")
    if not isinstance(home, str) or not home.strip():
        return "none", None
    home = home.strip()
    if home.lower() == "this":
        return "this", None
    thing_id = e_labels.get(home)
    if thing_id is None:  # a name written out (A2)
        if self_id and _same_name(home, view.name_of(self_id) or ""):
            return "this", None
        return "entry", home
    if thing_id == self_id:
        return "this", None
    return "entry", view.name_of(thing_id)


def _gt_homes(entry: str, gt: dict, labels: dict) -> tuple[set[str], list[str]]:
    """The acceptable existing-entry names (the entry and its same-thing
    twin standing for "this") and the acceptable new names."""

    names, new = set(), []
    same = labels["entries"][entry].get("same_as")
    for home in gt["home"]:
        if home == "this":
            names.add(entry)
            if same:
                names.add(same)
        elif home.startswith("new:"):
            new.append(home.split(":")[1])
        else:
            names.add(home)
    return names, new


def home_ok(kind: str, name: str | None, entry: str, gt: dict, labels: dict) -> bool:
    names, new = _gt_homes(entry, gt, labels)
    if kind == "this":
        return entry in names
    if kind in ("entry", "new") and name:
        if any(_same_name(name, n) for n in names):
            return True
        return any(_names_match(name, n) for n in new)
    return False


def _restated_id(p: dict, f_labels: dict) -> tuple[bool, str | None]:
    value = p.get("restates")
    if isinstance(value, list):
        value = value[0] if value else None
    if not value or not isinstance(value, str) or value.lower() == "null":
        return False, None
    return True, f_labels.get(value.strip())


def _timeline_names(p: dict, e_labels: dict, view, entry: str) -> list[str]:
    value = p.get("timeline")
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    out = []
    for label in value:
        if not isinstance(label, str):
            continue
        if label.lower() == "this":
            out.append(entry)
        elif label in e_labels:
            out.append(view.name_of(e_labels[label]) or label)
        else:
            out.append(label)
    return out


def _gt_timeline(entry: str, gt: dict) -> list[str] | None:
    if gt.get("timeline") is None:
        return None
    return [
        entry if t == "this" else t.split(":")[1] if t.startswith("new:") else t
        for t in gt["timeline"]
    ]


def score_a_run(run: dict, world: World, labels: dict) -> dict:
    entry = run["entry"]
    view = world.view(world.present(), rev=run["rev_before"])
    self_id = next(
        (t for t in run["e_labels"].values() if view.name_of(t) == entry), None
    )
    placements = {str(p.get("fact")): p for p in run.get("placements") or []}
    index = _label_index(labels)
    f_ids = set(run["f_labels"].values())
    rows = []
    for n_label, fact_id in run["new"].items():
        _, gt = index[fact_id[:8]]
        p = placements.get(n_label)
        row: dict[str, Any] = {
            "fact": fact_id[:8],
            "n": n_label,
            "placed": p is not None,
        }
        strict = {x for x in gt["restates"]}
        partial = set(gt.get("partial", []))
        row["gt_this"] = "this" in gt["home"]
        row["gt_restates"] = bool(strict)
        row["gt_partial"] = bool(partial) and not strict
        row["covered"] = any(fid[:8] in strict for fid in f_ids) if strict else None
        if p is None:
            row.update(
                home_ok=False, restate="missing", timeline_ok=False, false_move=False
            )
            rows.append(row)
            continue
        kind, name = _home_of(p, run["e_labels"], view, self_id)
        row["home"] = "this" if kind == "this" else f"{kind}:{name}"
        row["home_ok"] = home_ok(kind, name, entry, gt, labels)
        primary = gt["home"][0]
        row["primary_ok"] = (
            kind == "this"
            if primary == "this"
            else bool(name)
            and (
                _names_match(name, primary.split(":")[1])
                if primary.startswith("new:")
                else _same_name(name, primary)
            )
        )
        flagged, restated = _restated_id(p, run["f_labels"])
        row["restated"] = (
            restated[:8] if restated else (p.get("restates") if flagged else None)
        )
        if strict:
            if not flagged:
                row["restate"] = "missed"
            elif restated and restated[:8] in strict | partial:
                row["restate"] = "caught"
            else:
                row["restate"] = "caught_other_F"
        elif partial:
            row["restate"] = "partial_flagged" if flagged else "partial_unflagged"
        else:
            row["restate"] = "false_flag" if flagged else "ok_null"
        # a fact that belongs where it was written, sent elsewhere (not dropped)
        row["false_move"] = (
            row["gt_this"] and kind != "this" and not row["home_ok"] and not flagged
        )
        row["moved_off_topic"] = (not row["gt_this"]) and kind != "this"
        tl = _timeline_names(p, run["e_labels"], view, entry)
        gt_tl = _gt_timeline(entry, gt)
        row["timeline"] = tl or None
        if gt_tl is None:
            row["timeline_ok"] = not tl
            row["timeline_case"] = "false_timeline" if tl else "ok_null"
        else:
            hit = any(_same_name(a, b) for a in tl for b in gt_tl)
            required = gt.get("timeline_required", True)
            row["timeline_ok"] = hit or (not required and not tl)
            row["timeline_case"] = (
                "hit"
                if hit
                else (
                    "missed_required"
                    if required
                    else ("ok_null" if not tl else "wrong_target")
                )
            )
            if hit and gt.get("year") is not None:
                row["year_ok"] = p.get("year") == gt["year"] or str(
                    p.get("year")
                ) == str(gt["year"])
        rows.append(row)
    return {
        "entry": entry,
        "n": run["n"],
        "parsed": run.get("placements") is not None,
        "rows": rows,
    }


def _sum_rows(rows: list[dict]) -> dict:
    c = Counter()
    for r in rows:
        c["facts"] += 1
        c["home_ok"] += bool(r.get("home_ok"))
        c["primary_ok"] += bool(r.get("primary_ok"))
        c["restate_" + str(r.get("restate"))] += 1
        c["false_move"] += bool(r.get("false_move"))
        c["gt_this"] += r["gt_this"]
        c["gt_off_topic"] += not r["gt_this"]
        c["moved_off_topic"] += bool(r.get("moved_off_topic"))
        c["timeline_ok"] += bool(r.get("timeline_ok"))
        c["timeline_" + str(r.get("timeline_case"))] += 1
        c["gt_restates"] += r["gt_restates"]
        c["covered"] += bool(r.get("covered"))
        if "year_ok" in r:
            c["year_checked"] += 1
            c["year_ok"] += r["year_ok"]
    return dict(c)


def score_a(results: dict, world: World, labels: dict, key: str = "A") -> dict:
    runs = [score_a_run(run, world, labels) for run in results.get(key, [])]
    by_entry: dict[str, list] = {}
    for run in runs:
        by_entry.setdefault(run["entry"], []).append(run)
    per_entry = {}
    for entry, entry_runs in by_entry.items():
        per_entry[entry] = [_sum_rows(r["rows"]) for r in entry_runs]
        if len(entry_runs) >= 2:
            a, b = entry_runs[0]["rows"], entry_runs[1]["rows"]
            same_home = sum(x.get("home") == y.get("home") for x, y in zip(a, b))
            same_flag = sum(
                (
                    x.get("restate")
                    in ("caught", "caught_other_F", "false_flag", "partial_flagged")
                )
                == (
                    y.get("restate")
                    in ("caught", "caught_other_F", "false_flag", "partial_flagged")
                )
                for x, y in zip(a, b)
            )
            per_entry[entry].append(
                {"agree_home": same_home, "agree_restate_flag": same_flag, "of": len(a)}
            )
    total = Counter()
    for run in runs:
        total.update(_sum_rows(run["rows"]))
    return {
        "runs": runs,
        "per_entry": per_entry,
        "total": dict(total),
        "n_runs": len(runs),
    }


# --- the detector ----------------------------------------------------------------------


def detector(world: World, labels: dict, results: dict) -> dict:
    """Normalised token containment of each labelled new fact against
    (a) A's candidate facts (the first A run's F list) and (b) every live
    fact the revision before; precision and recall per threshold, and
    whether the best match is a labelled one. Also: does the top-k by
    overlap over the whole world hold a restated fact (retrieval as the
    candidate rule)?"""

    f_lists = {}
    for run in results.get("A", []):
        f_lists.setdefault(run["entry"], set(run["f_labels"].values()))
    head = world.view(world.present())
    rows = []
    for entry, spec in labels["entries"].items():
        before = world.view(world.present(), rev=spec["rev"] - 1)
        world_facts = [
            (fact.fact_id, tokens(before.render(fact.text)))
            for thing in before.things()
            for fact in thing.facts
        ]
        state = next(t for t in head.things() if head.name_of(t.id) == entry)
        texts = {f.fact_id[:8]: head.render(f.text) for f in state.facts}
        for gt in spec["facts"]:
            new = tokens(texts[gt["fact"]])
            scored = sorted(
                ((containment(new, toks), fid) for fid, toks in world_facts),
                reverse=True,
            )
            cands = f_lists.get(entry, set())
            in_f = [(s, fid) for s, fid in scored if fid in cands]
            strict, partial = set(gt["restates"]), set(gt.get("partial", []))
            rows.append(
                {
                    "entry": entry,
                    "fact": gt["fact"],
                    "strict": bool(strict),
                    "partial": bool(partial) and not strict,
                    "best_world": round(scored[0][0], 3) if scored else 0.0,
                    "best_world_hit": bool(scored)
                    and scored[0][1][:8] in strict | partial,
                    "best_f": round(in_f[0][0], 3) if in_f else 0.0,
                    "best_f_hit": bool(in_f) and in_f[0][1][:8] in strict | partial,
                    "topk_holds": any(
                        fid[:8] in strict for _, fid in scored[:RETRIEVE_K]
                    )
                    if strict
                    else None,
                    "f_holds": any(fid[:8] in strict for fid in cands)
                    if strict
                    else None,
                }
            )
    sweep = {}
    for source in ("world", "f"):
        for t in THRESHOLDS:
            tp = fp = fn = partial_flag = exact = 0
            for r in rows:
                flagged = r[f"best_{source}"] >= t
                if r["strict"]:
                    tp += flagged
                    fn += not flagged
                    exact += flagged and r[f"best_{source}_hit"]
                elif r["partial"]:
                    partial_flag += flagged
                else:
                    fp += flagged
            sweep[f"{source}@{t}"] = {
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "partial_flagged": partial_flag,
                "pointer_right": exact,
                "precision": round(tp / (tp + fp), 2) if tp + fp else None,
                "recall": round(tp / (tp + fn), 2) if tp + fn else None,
            }
    strict_rows = [r for r in rows if r["strict"]]
    return {
        "rows": rows,
        "sweep": sweep,
        "strict": len(strict_rows),
        "partial": sum(r["partial"] for r in rows),
        "clean": sum(not r["strict"] and not r["partial"] for r in rows),
        "coverage_name_rule": sum(bool(r["f_holds"]) for r in strict_rows),
        "coverage_top10_overlap": sum(bool(r["topk_holds"]) for r in strict_rows),
    }


# --- same thing, kinds, cost ----------------------------------------------------------


def _side_name(spec: dict) -> str:
    return spec.get("entry") or spec.get("name") or spec.get("mention") or ""


def same_thing(world: World, labels: dict, results: dict) -> dict:
    pairs = labels["same_thing"]
    rows = results.get("same", [])
    scored = [r for r in rows if r["truth"] != "ambiguous"]
    right = sum(r["relation"] == r["truth"] for r in scored)
    # binary: one thing (merge) or not
    pos = [r for r in scored if r["truth"] == "same"]
    neg = [r for r in scored if r["truth"] != "same"]
    stubby = [r for r in neg if "no facts of its own yet" in r["a"] + r["b"]]
    confusion = Counter((r["truth"], r["relation"]) for r in scored)
    by_pair: dict[int, list] = {}
    for r in rows:
        by_pair.setdefault(r["pair"], []).append(r["relation"])
    stable = sum(len(set(v)) == 1 for v in by_pair.values())
    # code: candidates by shared name words, and a containment classifier
    head = world.view(world.present())
    names = [head.name_of(t.id) or "" for t in head.things() if not t.stub_ignored]
    names += ["the Conclave", "Aelberth"]
    for t in head.things():
        for f in t.facts:
            m = re.match(r"^([A-Z][^:]{2,60}):\s", head.render(f.text))
            if f.category == "statement" and m:
                names.append(m.group(1))

    def words(n: str) -> set[str]:
        return {
            w for w in re.findall(r"[a-z]+", n.lower()) if w not in STOP and len(w) > 2
        }

    cand = set()
    uniq = sorted(set(names))
    for i, a in enumerate(uniq):
        for b in uniq[i + 1 :]:
            if words(a) & words(b):
                cand.add((a, b))
    found = 0
    code_right = 0
    code_rows = []
    for pair in pairs:
        a, b = _side_name(pair["a"]), _side_name(pair["b"])
        hit = (min(a, b), max(a, b)) in cand or bool(words(a) & words(b))
        found += hit
        wa, wb = words(a), words(b)
        code_says = "same" if wa and wb and (wa <= wb or wb <= wa) else "different"
        if pair["relation"] != "ambiguous":
            truth = "same" if pair["relation"] == "same" else "different"
            code_right += code_says == truth
        code_rows.append(
            {
                "a": a,
                "b": b,
                "truth": pair["relation"],
                "shared_words": hit,
                "code_says": code_says,
            }
        )
    return {
        "model_right": right,
        "binary_same_right": sum(r["relation"] == "same" for r in pos),
        "binary_same_of": len(pos),
        "binary_not_same_right": sum(r["relation"] != "same" for r in neg),
        "binary_not_same_of": len(neg),
        "false_same_with_factless_stub": sum(r["relation"] == "same" for r in stubby),
        "false_same_total": sum(r["relation"] == "same" for r in neg),
        "model_scored": len(scored),
        "confusion": {f"{t}->{p}": n for (t, p), n in confusion.items()},
        "pairs_stable_across_runs": stable,
        "pairs": len(by_pair),
        "per_pair": {i: v for i, v in by_pair.items()},
        "code_candidates_all_names": len(cand),
        "code_names_considered": len(uniq),
        "code_finds_labelled_pairs": found,
        "code_containment_right": code_right,
        "code_rows": code_rows,
    }


def kinds(results: dict) -> dict:
    out = {}
    for r in results.get("kinds", []):
        truth = r["truth"]
        kind_ok = r["kind"] == truth["kind"]
        template_ok = (r.get("template") or None) == truth["template"]
        part = r.get("part_of")
        part_ok = any(
            (p is None and not part) or (p and part and _same_name(p, part))
            for p in truth["part_of"]
        )
        out.setdefault(r["case"], []).append(
            {
                "kind": r["kind"],
                "template": r.get("template"),
                "part_of": part,
                "kind_ok": kind_ok,
                "template_ok": template_ok,
                "part_of_ok": part_ok,
            }
        )
    return out


def cost(results: dict) -> dict:
    out = {}
    for key in ("A", "A2", "B", "combine", "same", "kinds"):
        rows = [r for r in results.get(key, []) if r.get("seconds") is not None]
        if not rows:
            continue
        secs = [r["seconds"] for r in rows]
        p_tok = [r["prompt_tokens"] for r in rows if r.get("prompt_tokens")]
        r_tok = [r["reply_tokens"] for r in rows if r.get("reply_tokens")]
        out[key] = {
            "calls": len(rows),
            "seconds_mean": round(statistics.mean(secs), 1),
            "seconds_min": min(secs),
            "seconds_max": max(secs),
            "prompt_tokens_mean": round(statistics.mean(p_tok)) if p_tok else None,
            "prompt_tokens_max": max(p_tok) if p_tok else None,
            "reply_tokens_mean": round(statistics.mean(r_tok)) if r_tok else None,
            "reply_tokens_max": max(r_tok) if r_tok else None,
        }
    return out


YEAR = re.compile(r"\b\d{3,4}s?\b")


def timeline_code(world: World, labels: dict) -> dict:
    """The code rule "a year in the text makes a timeline candidate",
    against the labelled timelines (any non-null label counts)."""

    head = world.view(world.present())
    tp = fp = fn = tn = 0
    misses, false = [], []
    for entry, spec in labels["entries"].items():
        state = next(t for t in head.things() if head.name_of(t.id) == entry)
        texts = {f.fact_id[:8]: head.render(f.text) for f in state.facts}
        for gt in spec["facts"]:
            dated = bool(YEAR.search(texts[gt["fact"]]))
            event = gt.get("timeline") is not None
            tp += dated and event
            fp += dated and not event
            fn += event and not dated
            tn += not dated and not event
            if event and not dated:
                misses.append(gt["fact"])
            if dated and not event:
                false.append(gt["fact"])
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "missed": misses, "false": false}


def b_restatement(world: World, labels: dict, results: dict, threshold: float) -> dict:
    """The detector over B's facts (and the stored originals), against
    every live fact the revision before the expansion; with the hand
    judgments of on-topic (`b_judged`, made after the run)."""

    head = world.view(world.present())
    out: dict[str, Any] = {}
    judged = results.get("b_judged", {}).get("runs", [])
    for entry in {r["entry"] for r in results.get("B", [])}:
        rev = labels["entries"][entry]["rev"]
        before = world.view(world.present(), rev=rev - 1)
        world_facts = [
            tokens(before.render(f.text)) for t in before.things() for f in t.facts
        ]

        def restated(text: str) -> bool:
            new = tokens(text)
            return (
                max((containment(new, old) for old in world_facts), default=0)
                >= threshold
            )

        state = next(t for t in head.things() if head.name_of(t.id) == entry)
        spec = labels["entries"][entry]
        texts = {f.fact_id[:8]: head.render(f.text) for f in state.facts}
        stored = [texts[g["fact"]] for g in spec["facts"]]
        out[entry] = {
            "stored": {
                "facts": len(stored),
                "on_topic_labelled": sum("this" in g["home"] for g in spec["facts"]),
                "restates_labelled": sum(bool(g["restates"]) for g in spec["facts"]),
                "restates_detector": sum(restated(t) for t in stored),
            }
        }
        for i, run in enumerate(results["B"]):
            if run["entry"] != entry:
                continue
            facts = [f["text"] for f in run["facts"] if f.get("text")]
            hand = judged[i] if i < len(judged) else None
            tags = Counter(str(f.get("subject")) for f in run["facts"])
            out[entry][f"{run['variant']}-{run['n']}"] = {
                "facts": len(facts),
                "on_topic_hand": sum(hand) if hand else None,
                "subject_tags": dict(tags),
                "elsewhere": len(run.get("elsewhere") or []),
                "restates_detector": sum(restated(t) for t in facts),
            }
    return out


def score(world: World, labels: dict, results: dict) -> dict:
    a = score_a(results, world, labels)
    a2 = score_a(results, world, labels, key="A2")
    det = detector(world, labels, results)
    same = same_thing(world, labels, results)
    kind = kinds(results)
    costs = cost(results)
    best = max(
        (k for k in det["sweep"] if k.startswith("f@")),
        key=lambda k: (det["sweep"][k]["tp"] - det["sweep"][k]["fp"]),
    )
    summary = {
        "A_total": a["total"],
        "A_runs": a["n_runs"],
        "A2_total": a2["total"],
        "A2_runs": a2["n_runs"],
        "detector_best_on_F": {best: det["sweep"][best]},
        "detector_counts": {
            k: det[k]
            for k in (
                "strict",
                "partial",
                "clean",
                "coverage_name_rule",
                "coverage_top10_overlap",
            )
        },
        "same_model": f"{same['model_right']}/{same['model_scored']}",
        "same_code_containment": f"{same['code_containment_right']}/{sum(p['relation'] != 'ambiguous' for p in labels['same_thing'])}",
        "kinds": {
            c: [(r["kind"], r["template"], r["part_of"]) for r in rs]
            for c, rs in kind.items()
        },
        "cost": costs,
    }
    summary["timeline_code_year_rule"] = timeline_code(world, labels)
    summary["B"] = b_restatement(world, labels, results, 0.4)
    summary["B_at_0.5"] = b_restatement(world, labels, results, 0.5)
    return {
        "summary": summary,
        "A": a,
        "A2": a2,
        "detector": det,
        "same": same,
        "kinds": kind,
    }
