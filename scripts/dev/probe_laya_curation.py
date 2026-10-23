"""Throwaway probe: can Laya (a small local non-generative decision model)
make the curation probe's judgement calls better than Skyfall did?

It re-uses the curation probe's own cases (`2026-10-22-curation-labels.json`
and the texts recorded in `raw/2026-10-22-curation.json`), so no world is
opened and no app code runs. Laya lives in its own venv, outside the
project (never the project's .venv):

    guix shell -m manifest.scm -- bash -c 'export LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib \\
        HF_HOME=<scratch>/hf USE_TF=0; <scratch>/laya-venv/bin/python \\
        scripts/dev/probe_laya_curation.py [--only same contra held movein elsewhere names]'

Writes `docs/superpowers/probes/raw/2026-10-22-laya-curation.json`.

Judgements (numbered as in the findings doc):
1. same   - same / part / different, names plus first facts (probe 5b's pairs)
2. contra - does fact A contradict fact B (probe 3's merge pairs, every A x B)
3. held   - bare belief vs plain world truth (probe 4's judged facts)
4. movein - does the broader entry's fact belong on the new entry (probe 2)
5. elsewhere - is an elsewhere item mainly about the entry being written
   (or, in Fill, one of the reply's own new items), about the target, or both
6. names  - the same-thing check by name alone

Truncation: every text is cut at a word boundary (`cut`, 220 characters
for facts, 160 for descriptions) and the same-thing state takes the first
3 facts per side (the app's summary fact comes first). Every state is
checked against the checkpoint's 512-token limit: `usage.truncated` and
`state_tokens_dropped` are recorded per call.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RAW_IN = REPO / "docs/superpowers/probes/raw/2026-10-22-curation.json"
LABELS = REPO / "docs/superpowers/probes/raw/2026-10-22-curation-labels.json"
RAW_OUT = REPO / "docs/superpowers/probes/raw/2026-10-22-laya-curation.json"


# --- text helpers ----------------------------------------------------------------


def cut(text: str, n: int = 220) -> str:
    text = " ".join((text or "").split())
    if len(text) <= n:
        return text
    head = text[:n].rsplit(" ", 1)[0]
    return head.rstrip(",;:") + "…"


# the curation probe's overlap measure (src/talemate/world/repeats.py), ported
# unchanged so the code baseline can be recomputed without the app
STOP = set(
    """a an the of and or in on at to for from by with as is are was were be been
    its it their his her this that these those which who whom into over under
    than then so such not no nor but if all any each every some most more many
    much one two can could may might would will shall should has have had do does
    did also only even both either very own same other another within without
    through about after before since while where when there here what how""".split()
)
_WORDS = re.compile(r"[a-z0-9]+")


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def content_words(text: str) -> set[str]:
    return {_stem(w) for w in _WORDS.findall(text.lower()) if w not in STOP and len(w) > 1}


def overlap(a: str, b: str) -> float:
    wa, wb = content_words(a), content_words(b)
    return len(wa & wb) / len(wa) if wa else 0.0


def strip_year(text: str) -> str:
    return re.sub(r"^\((In|Since) -?\d+\)\s*", "", text)


# --- datasets ---------------------------------------------------------------------


def parse_sides(prompt: str) -> tuple[dict[str, str], dict[str, str]]:
    a = dict(re.findall(r"^- (A\d+): (.*)$", prompt, re.M))
    b = dict(re.findall(r"^- (B\d+): (.*)$", prompt, re.M))
    return a, b


def build_contra(raw: dict, labels: dict) -> list[dict]:
    out = []
    seen = set()
    for run in raw["p3"]:
        if run["case"] in seen:
            continue
        seen.add(run["case"])
        spec = labels["probe3"]["cases"][run["case"]]
        a_txt, b_txt = parse_sides(raw["calls"][run["call"]]["prompt"])
        a_name, b_name = run["case"].split(" + ")
        contra = spec["contradictions"]
        bonus = spec.get("bonus", [])
        for la, ida in run["a_labels"].items():
            for lb, idb in run["b_labels"].items():
                hits = [k for k, c in enumerate(contra) if ida in c["a"] and idb in c["b"]]
                is_c = bool(hits)
                is_b = any(ida in c["a"] and idb in c["b"] for c in bonus)
                ta, tb = a_txt[la], b_txt[lb]
                out.append(
                    {
                        "case": run["case"],
                        "a_name": a_name,
                        "b_name": b_name,
                        "a": ida,
                        "b": idb,
                        "a_text": ta,
                        "b_text": tb,
                        "truth": "contradict" if is_c else ("bonus" if is_b else "clean"),
                        "cidx": hits[0] if hits else None,
                        "overlap": max(overlap(strip_year(ta), strip_year(tb)), overlap(strip_year(tb), strip_year(ta))),
                    }
                )
    return out


def build_same(raw: dict, labels: dict) -> list[dict]:
    out, seen = [], set()
    for r in raw["same"]:
        if r["pair"] in seen:
            continue
        seen.add(r["pair"])
        p = raw["calls"][r["call"]]["prompt"]
        m = re.search(r"A, the new entry: (.*)\n((?:- .*\n)*)\nB, already in the world: (.*)\n((?:- .*\n)*)", p)
        a_facts = [x[2:] for x in m.group(2).splitlines()]
        b_facts = [x[2:] for x in m.group(4).splitlines()]
        out.append(
            {
                "pair": r["pair"],
                "truth": r["truth"],
                "a": m.group(1),
                "b": m.group(3),
                "a_facts": a_facts,
                "b_facts": b_facts,
                "skyfall": [x["verdict"] for x in raw["same"] if x["pair"] == r["pair"]],
            }
        )
    return out


def run_key(run: dict) -> str:
    return f"{run['case']}|{run.get('variant', 'r2')}|{run['n']}"


def build_held(raw: dict) -> list[dict]:
    """Probe 4's set as Skyfall was scored on it: probe 1's create runs and
    the being runs, facts and elsewhere items, with the hand codes (b bare
    belief, a attributed, p plain)."""

    J = raw["judged"]
    runs = [r for r in raw["p1"] if r["case"].startswith("create:")]
    runs += [r for r in raw["creates"] if "p4" in r["probes"]]
    out = []
    for run in runs:
        j = J.get(run_key(run))
        if not j:
            continue
        entry = run["case"].split(":", 1)[1]
        for where, items, codes in (
            ("facts", run.get("facts") or [], j.get("held", "")),
            ("elsewhere", run.get("elsewhere") or [], j.get("else_held", "")),
        ):
            for i, (item, code) in enumerate(zip(items, codes)):
                holder = item.get("held_by")
                out.append(
                    {
                        "run": run_key(run),
                        "where": where,
                        "i": i,
                        "entry": entry if where == "facts" else (item.get("target") or item.get("entry")),
                        "text": item.get("text") or "",
                        "code": code,
                        "skyfall_marked": isinstance(holder, str) and holder.strip() != "",
                    }
                )
    return out


def build_movein(raw: dict, labels: dict) -> list[dict]:
    out, seen = [], set()
    for r in raw["creates"]:
        if "p2" not in r["probes"] or r["case"] in seen:
            continue
        seen.add(r["case"])
        spec = labels["probe2"]["cases"][r["case"]]
        name, desc = r["prompt_text"].split(": ", 1)
        desc = re.sub(r" Part of .*$", "", desc)
        picks = defaultdict(int)
        for x in raw["creates"]:
            if x["case"] == r["case"] and "p2" in x["probes"]:
                for m in x.get("move_in_ids") or []:
                    picks[m] += 1
        for label, text in r["broader"]:
            fid = r["broader_labels"][label]
            truth = "move" if fid in spec["move"] else ("either" if fid in spec["either"] else "stay")
            out.append(
                {
                    "case": r["case"],
                    "new": name,
                    "new_desc": desc,
                    "broader": spec["broader"],
                    "id": fid,
                    "text": text,
                    "truth": truth,
                    "skyfall_picked": picks[fid],
                }
            )
    return out


LOOSE_FALSE = {
    ("create:The Divine Right of the Tsar|r2|0", 0),
    ("create:The Illumination|r3w|1", 3),
}
BORDERLINE = {("create:The Divine Right of the Tsar|r1|1", 0)}


def nearby_desc(run: dict, name: str | None) -> str:
    if not name:
        return ""
    for line in run.get("nearby") or []:
        if line.startswith(name + " (") and "): " in line:
            return line.split("): ", 1)[1]
    return ""


def build_elsewhere(raw: dict) -> list[dict]:
    J = raw["judged"]
    out = []
    for src, pre in (("p1", ""), ("p1v3", "v3:")):
        for run in raw.get(src, []):
            j = J.get(pre + run_key(run))
            if not j:
                continue
            prompt = run["case"].split(":")[0]
            if prompt == "create":
                a_name = run["case"].split(":", 1)[1]
                own = [f.get("text") or "" for f in run.get("facts") or []]
                a_desc = own[0] if own else ""
                new_items = []
            elif prompt == "core":
                a_name = run["case"].split(":", 1)[1]
                a_desc = run.get("summary") or ""
                new_items = []
            else:
                a_name = run["case"].split(":", 1)[1].split("/")[0]
                a_desc = ""
                new_items = [
                    (i.get("name") or "", i.get("text") or "")
                    for i in run.get("new_items") or []
                    if isinstance(i, dict)
                ]
            for i, (item, code) in enumerate(zip(run.get("elsewhere") or [], j.get("else", ""))):
                key = (run_key(run), i)
                if code in "wx":
                    truth = "wrong_entry"
                elif prompt == "fill" and code == "f":
                    truth = "false"  # a detail of the reply's own new item
                elif pre == "" and key in LOOSE_FALSE:
                    truth = "false"
                elif code == "f":
                    truth = "relation"  # strict false move, right under 'either side'
                else:
                    truth = "right"
                target = item.get("target") or item.get("entry")
                out.append(
                    {
                        "run": pre + run_key(run),
                        "prompt": prompt,
                        "i": i,
                        "code": code,
                        "truth": truth,
                        "borderline": pre == "" and key in BORDERLINE,
                        "text": item.get("text") or "",
                        "a_name": a_name,
                        "a_desc": a_desc,
                        "new_items": new_items,
                        "target": target,
                        "target_desc": nearby_desc(run, target),
                    }
                )
    return out


# --- phrasings ----------------------------------------------------------------------
# each phrasing: (state, questions) for a case; the question id is always "q".
# `pos` names the positive answer (for choice), or None for noul (P(true)).

SAME_CRIT = {
    "same": "A and B are one and the same thing under two names",
    "part": "one is a part of the other, such as a hall inside a city or a chapter of a guild",
    "different": "two distinct things, even if closely tied, such as a saint and her shrine or a battle and its field",
}


def same_state(c: dict, n_facts: int) -> str:
    lines = [f"Entry A: {c['a']}"]
    lines += [f"- {cut(t)}" for t in c["a_facts"][:n_facts]]
    lines += [f"Entry B: {c['b']}"]
    lines += [f"- {cut(t)}" for t in c["b_facts"][:n_facts]]
    return "\n".join(lines)


def ph_same(c: dict, variant: str):
    if variant == "S1":
        q = {"type": "choice", "instructions": "How does entry A relate to entry B?", "criteria": SAME_CRIT}
        return same_state(c, 3), q, "same"
    if variant == "S2":
        q = {
            "type": "noul",
            "instructions": "Do entries A and B describe one and the same thing under two names?",
            "criteria": {"true": "A and B are the same thing", "false": "A and B are different things, or one is part of the other"},
        }
        return same_state(c, 3), q, None
    if variant == "S3":
        q = {"type": "choice", "instructions": "What is entry A, compared with entry B?", "criteria": {
            "the same thing": "the same thing as B, described twice",
            "a part": "a part of B, or B is a part of A",
            "a different thing": "a different thing from B, perhaps one named after it or found in it",
        }}
        return same_state(c, 2), q, "the same thing"
    if variant == "S4":
        # round 2: the summary fact only, as a yes/no
        q = {"type": "noul", "instructions": "Do entries A and B describe one and the same thing under two names?"}
        return same_state(c, 1), q, None
    if variant == "S5":
        q = {"type": "choice", "instructions": "Are A and B the same thing?", "criteria": {
            "same": "yes: A and B are one thing written up twice",
            "not the same": "no: A and B are two things, though one may contain, serve or be named after the other",
        }}
        return same_state(c, 2), q, "same"
    raise KeyError(variant)


def ph_names(c: dict, variant: str):
    state = f"Entry A: {c['a']}\nEntry B: {c['b']}"
    if variant == "N1":
        q = {"type": "choice", "instructions": "Going by their names, how does entry A relate to entry B?", "criteria": SAME_CRIT}
        return state, q, "same"
    if variant == "N2":
        q = {"type": "noul", "instructions": "Do the names A and B name one and the same thing?"}
        return state, q, None
    raise KeyError(variant)


CONTRA_CRIT = {
    "agree": "both say the same thing, or one adds a detail the other leaves out",
    "contradict": "they give a different year, holder, place, colour, number or name for the same thing, or one says it stands and the other that it is gone",
    "unrelated": "they are about different things",
}


def ph_contra(c: dict, variant: str):
    if variant == "C1":
        state = f"Fact A: {cut(c['a_text'])}\nFact B: {cut(c['b_text'])}"
        q = {"type": "choice", "instructions": "How do fact A and fact B relate?", "criteria": CONTRA_CRIT}
        return state, q, "contradict"
    if variant == "C2":
        state = f"Fact A: {cut(c['a_text'])}\nFact B: {cut(c['b_text'])}"
        q = {
            "type": "noul",
            "instructions": "Do fact A and fact B contradict each other, so that both cannot be true?",
            "criteria": {"true": "they cannot both be true", "false": "both can be true at once"},
        }
        return state, q, None
    if variant == "C3":
        state = (
            f"Two records of one thing, {c['a_name']} and {c['b_name']}, are being merged.\n"
            f"From {c['a_name']}: {cut(c['a_text'])}\nFrom {c['b_name']}: {cut(c['b_text'])}"
        )
        q = {"type": "choice", "instructions": "How do the two statements relate?", "criteria": CONTRA_CRIT}
        return state, q, "contradict"
    if variant in ("C4", "C5"):
        # round 2: the year comparison done in code and handed over in words
        ya = re.match(r"^\((?:In|Since) (-?\d+)\)", c["a_text"])
        yb = re.match(r"^\((?:In|Since) (-?\d+)\)", c["b_text"])
        note = ""
        if ya and yb:
            note = "\nThe two facts give the same year." if ya.group(1) == yb.group(1) else "\nThe two facts give different years."
        state = f"Fact A: {cut(c['a_text'])}\nFact B: {cut(c['b_text'])}{note}"
        if variant == "C4":
            q = {"type": "choice", "instructions": "How do fact A and fact B relate?", "criteria": CONTRA_CRIT}
            return state, q, "contradict"
        q = {
            "type": "noul",
            "instructions": "Do fact A and fact B contradict each other, so that both cannot be true?",
            "criteria": {"true": "they cannot both be true", "false": "both can be true at once"},
        }
        return state, q, None
    if variant == "C6":
        state = f"Fact A: {cut(c['a_text'])}\nFact B: {cut(c['b_text'])}"
        q = {"type": "choice", "instructions": "How do fact A and fact B relate?", "criteria": {
            "same claim": "they say the same thing in other words",
            "added detail": "one adds or narrows a detail the other leaves open",
            "conflict": "they give a different year, holder, place, colour, number or name for the same thing, or one says it stands and the other that it is gone",
            "unrelated": "they are about different things",
        }}
        return state, q, "conflict"
    raise KeyError(variant)


def ph_held(c: dict, variant: str):
    state = f"A statement from the entry {c['entry']}, in a fantasy world's records:\n{cut(c['text'], 300)}"
    if variant == "H1":
        q = {"type": "choice", "instructions": "What kind of claim does the statement make?", "criteria": {
            "belief": "it states as fact a god's will, nature, blessing or acts, or divine favour",
            "attributed": "it says a church, faith, doctrine or people teach, hold or believe something",
            "plain": "it states an event, law, rite, custom, place, office, or what a thing is or does",
        }}
        return state, q, "belief"
    if variant == "H2":
        q = {
            "type": "noul",
            "instructions": "Does the statement present a religious belief about a god's will, acts or favour as plain fact, without saying who believes it?",
        }
        return state, q, None
    if variant == "H3":
        q = {"type": "choice", "instructions": "What is the statement about?", "criteria": {
            "divine": "what a god wills, is, does, grants or blesses",
            "worldly": "people, places, events, laws, rites, offices or customs",
        }}
        return state, q, "divine"
    if variant == "H4":
        q = {"type": "noul", "instructions": "Does the statement say, as plain fact, what a god did, wants, chose or blessed?"}
        return state, q, None
    if variant == "H5":
        bare = cut(c["text"], 300)
        q = {
            "type": "noul",
            "instructions": "Does the statement present a religious belief about a god's will, acts or favour as plain fact, without saying who believes it?",
        }
        return bare, q, None
    raise KeyError(variant)


def ph_movein(c: dict, variant: str):
    new, br = c["new"], c["broader"]
    fact = cut(strip_year(c["text"]), 260)
    state = f"{new}: {cut(c['new_desc'], 160)}\nA fact from the entry {br}: {fact}"
    if variant == "M1":
        q = {"type": "choice", "instructions": f"How does the fact relate to {new}?", "criteria": {
            "mainly about it": f"the fact is mainly about {new} itself",
            "in passing": f"the fact is about something else and touches {new} only in passing",
            "not about it": f"the fact does not concern {new}",
        }}
        return state, q, "mainly about it"
    if variant == "M2":
        q = {"type": "noul", "instructions": f"Is the fact mainly about {new}?"}
        return state, q, None
    if variant == "M3":
        q = {"type": "choice", "instructions": "What is the fact mainly about?", "criteria": {
            "the new entry": f"{new}: {cut(c['new_desc'], 80)}",
            "the broader entry": f"{br} as a whole, or another part of it",
        }}
        return state, q, "the new entry"
    if variant == "M4":
        q = {"type": "noul", "instructions": f"Is the fact mainly about {new}?"}
        return f"A fact from the entry {br}: {fact}", q, None
    if variant == "M5":
        q = {"type": "noul", "instructions": f"Is the fact mainly about {new}, rather than about {br} as a whole?"}
        return state, q, None
    raise KeyError(variant)


def else_state(c: dict) -> str:
    if c["new_items"]:
        a = "; ".join(f"{n} ({cut(t, 90)})" for n, t in c["new_items"])
        a_line = f"New items just written for {c['a_name']}: {a}"
    else:
        a_line = f"A, the entry being written: {c['a_name']}: {cut(c['a_desc'], 160)}"
    b_line = f"B, the entry it is filed on: {c['target']}"
    if c["target_desc"]:
        b_line += f": {cut(c['target_desc'], 160)}"
    return f"Sentence: {cut(c['text'], 260)}\n{a_line}\n{b_line}"


def ph_elsewhere(c: dict, variant: str):
    a_short = "one of the new items" if c["new_items"] else c["a_name"]
    state = else_state(c)
    if variant == "E1":
        q = {"type": "choice", "instructions": "What is the sentence mainly about?", "criteria": {
            "A": f"{a_short} itself",
            "B": f"{c['target']} itself",
            "both": f"how {a_short} and {c['target']} are tied to each other",
        }}
        return state, q, "A"
    if variant == "E2":
        q = {"type": "noul", "instructions": f"Is the sentence mainly a description of {a_short} rather than of {c['target']}?"}
        return state, q, None
    if variant == "E3":
        q = {"type": "choice", "instructions": "Whose page does the sentence describe?", "criteria": {
            "A": f"{a_short}: it tells what {a_short} is, has or does",
            "B": f"{c['target']}: it tells what {c['target']} is, has or does",
        }}
        return state, q, "A"
    if variant == "E4":
        subj = "one of the new items" if c["new_items"] else c["a_name"]
        q = {"type": "noul", "instructions": f"Is the subject of the sentence {subj}?"}
        return state, q, None
    if variant == "E5":
        # every candidate home by name as its own option
        opts = {}
        homes = [n for n, _ in c["new_items"]] if c["new_items"] else [c["a_name"]]
        for n in homes:
            opts[cut(n, 60)] = f"the sentence describes {cut(n, 60)}"
        opts.setdefault(cut(c["target"] or "B", 60), f"the sentence describes {cut(c['target'] or 'B', 60)}")
        q = {"type": "choice", "instructions": "Which entry does the sentence describe?", "criteria": opts}
        return f"Sentence: {cut(c['text'], 260)}", q, [cut(n, 60) for n in homes]
    raise KeyError(variant)


JUDGEMENTS = {
    "same": (ph_same, ["S1", "S2", "S3", "S4", "S5"]),
    "names": (ph_names, ["N1", "N2"]),
    "contra": (ph_contra, ["C1", "C2", "C3", "C4", "C5", "C6"]),
    "held": (ph_held, ["H1", "H2", "H3", "H4", "H5"]),
    "movein": (ph_movein, ["M1", "M2", "M3", "M4", "M5"]),
    "elsewhere": (ph_elsewhere, ["E1", "E2", "E3", "E4", "E5"]),
}


def positive(judgement: str, c: dict) -> bool | None:
    """Ground truth as a binary flag; None = not scored."""

    if judgement in ("same", "names"):
        return c["truth"] == "same"
    if judgement == "contra":
        return None if c["truth"] == "bonus" else c["truth"] == "contradict"
    if judgement == "held":
        return {"b": True, "p": False}.get(c["code"])
    if judgement == "movein":
        return None if c["truth"] == "either" else c["truth"] == "move"
    if judgement == "elsewhere":
        return {"false": True, "right": False, "relation": False}.get(c["truth"])
    raise KeyError(judgement)


# --- running --------------------------------------------------------------------------


def ask(agent, state: str, q: dict, pos: str | None) -> dict:
    t = time.perf_counter()
    res = agent.predict(state, {"q": q})
    secs = time.perf_counter() - t
    a = res["answers"]["q"]
    usage = res.get("usage", {})
    if q["type"] == "noul":
        p = float(a["noul"])
        answer = p >= 0.5
        probs = {"true": p, "false": 1 - p}
    else:
        probs = {k: float(v) for k, v in a["probabilities"].items()}
        p = sum(probs[x] for x in pos) if isinstance(pos, list) else probs[pos]
        answer = a["choice"]
        if isinstance(pos, list):
            answer = answer in pos
    return {
        "p_pos": round(p, 4),
        "answer": answer,
        "probs": {k: round(v, 4) for k, v in probs.items()},
        "top": round(max(probs.values()), 4),
        "confidence": a.get("confidence"),
        "act": (a.get("action") or {}).get("act_probability"),
        "seconds": round(secs, 4),
        "input_tokens": usage.get("input_tokens"),
        "state_tokens": usage.get("state_tokens"),
        "dropped": usage.get("state_tokens_dropped"),
        "truncated": usage.get("truncated"),
        "truncated_questions": usage.get("truncated_questions"),
    }


# --- scoring --------------------------------------------------------------------------


def pct(a: int, b: int) -> str:
    return f"{a}/{b} ({round(100 * a / b) if b else 0}%)"


def flag_of(r: dict, pos: str | None) -> bool:
    """The argmax decision, as a binary flag."""

    return bool(r["answer"]) if pos is None or isinstance(pos, list) else r["answer"] == pos


def cascade(ps: list[float], ys: list[bool], miss: float = 0.0, precision: float = 0.9) -> dict:
    """Two thresholds chosen on the data. Auto-clear (answer no) when
    p <= lo, auto-flag (answer yes) when p >= hi, escalate to the owner
    between. lo is the highest value that auto-clears at most `miss` of the
    positives; hi is the lowest value whose auto-flags are at least
    `precision` right (none if no value gets there). Fit on the test set, so
    optimistic: see `cascade_loco` for the held-out version."""

    n = len(ps)
    pos = sorted(p for p, y in zip(ps, ys) if y)
    allowed = int(miss * len(pos))
    # lo: just under the (allowed+1)-th lowest positive
    if pos:
        bound = pos[allowed] if allowed < len(pos) else 2.0
        below = [p for p in ps if p < bound]
        lo = max(below) if below else -1.0
    else:
        lo = max(ps) if ps else -1.0
    hi = 2.0
    for t in sorted(set(ps)):
        sel = [y for p, y in zip(ps, ys) if p >= t]
        if sel and sum(sel) / len(sel) >= precision and t > lo:
            hi = t
            break
    return apply_cascade(ps, ys, lo, hi) | {"miss_allowed": miss, "precision_target": precision}


def apply_cascade(ps: list[float], ys: list[bool], lo: float, hi: float) -> dict:
    n = len(ps)
    yes = [y for p, y in zip(ps, ys) if p >= hi]
    no = [y for p, y in zip(ps, ys) if p <= lo and p < hi]
    esc = [y for p, y in zip(ps, ys) if lo < p < hi]
    auto = len(yes) + len(no)
    right = sum(yes) + sum(not y for y in no)
    return {
        "lo": lo,
        "hi": hi,
        "auto": pct(auto, n),
        "auto_share": auto / n if n else 0,
        "escalated": pct(len(esc), n),
        "auto_accuracy": round(right / auto, 4) if auto else None,
        "positives": {"auto_yes": sum(yes), "escalated": sum(esc), "auto_no (missed)": sum(no)},
        "negatives": {"auto_no": len(no) - sum(no), "escalated": len(esc) - sum(esc), "auto_yes (false)": len(yes) - sum(yes)},
    }


def group_of(judgement: str, c: dict) -> str:
    if judgement in ("same", "names"):
        return c["pair"]
    if judgement in ("held",):
        return c["run"].split("|")[0]
    if judgement == "elsewhere":
        return c["run"].split("|")[0].removeprefix("v3:")
    return c["case"]


def cascade_loco(ps: list[float], ys: list[bool], groups: list[str], miss: float = 0.0, precision: float = 0.9) -> dict:
    """The cascade with its thresholds fit on every other case group and
    applied to the held-out one (leave one case out): an honest estimate of
    what thresholds chosen in advance would do on a new case."""

    tot = Counter()
    n = len(ps)
    for g in sorted(set(groups)):
        train = [(p, y) for p, y, gg in zip(ps, ys, groups) if gg != g]
        test = [(p, y) for p, y, gg in zip(ps, ys, groups) if gg == g]
        fit = cascade([p for p, _ in train], [y for _, y in train], miss, precision)
        res = apply_cascade([p for p, _ in test], [y for _, y in test], fit["lo"], fit["hi"])
        for side in ("positives", "negatives"):
            for k, v in res[side].items():
                tot[(side, k)] += v
    auto = n - tot[("positives", "escalated")] - tot[("negatives", "escalated")]
    right = tot[("positives", "auto_yes")] + tot[("negatives", "auto_no")]
    return {
        "groups": len(set(groups)),
        "auto": pct(auto, n),
        "auto_share": auto / n if n else 0,
        "escalated": pct(n - auto, n),
        "auto_accuracy": round(right / auto, 4) if auto else None,
        "positives": {k: v for (side, k), v in tot.items() if side == "positives"},
        "negatives": {k: v for (side, k), v in tot.items() if side == "negatives"},
    }


def top_split(rows: list[dict], ys: list[bool], pos: str | None, t: float) -> dict:
    """The guide's rule: act when the top option's probability >= t."""

    conf = [(flag_of(r, pos) == y) for r, y in zip(rows, ys) if r["top"] >= t]
    return {"threshold": t, "confident": pct(len(conf), len(rows)), "right_when_confident": pct(sum(conf), len(conf))}


def best_auc(ps: list[float], ys: list[bool]) -> float | None:
    pos = [p for p, y in zip(ps, ys) if y]
    neg = [p for p, y in zip(ps, ys) if not y]
    if not pos or not neg:
        return None
    wins = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg)
    return round(wins / (len(pos) * len(neg)), 3)


def score_variant(judgement: str, cases: list[dict], rows: list[dict], pos: str | None) -> dict:
    idx = [i for i, c in enumerate(cases) if positive(judgement, c) is not None]
    rs = [rows[i] for i in idx]
    ys = [positive(judgement, cases[i]) for i in idx]
    gs = [group_of(judgement, cases[i]) for i in idx]
    ps = [r["p_pos"] for r in rs]
    flags = [flag_of(r, pos) for r in rs]
    tp = sum(f and y for f, y in zip(flags, ys))
    fp = sum(f and not y for f, y in zip(flags, ys))
    npos = sum(ys)
    nneg = len(ys) - npos
    out = {
        "scored": len(ys),
        "accuracy": pct(sum(f == y for f, y in zip(flags, ys)), len(ys)),
        "accuracy_share": sum(f == y for f, y in zip(flags, ys)) / len(ys),
        "recall": pct(tp, npos),
        "false_flags": pct(fp, nneg),
        "auc": best_auc(ps, ys),
        "seconds_mean": round(statistics.mean(r["seconds"] for r in rows), 4),
        "seconds_median": round(statistics.median(r["seconds"] for r in rows), 4),
        "state_tokens_max": max((r["state_tokens"] or 0) for r in rows),
        "input_tokens_max": max((r["input_tokens"] or 0) for r in rows),
        "truncated_calls": sum(1 for r in rows if r["truncated"] or r["dropped"]),
        "cascade": cascade(ps, ys, 0.0, 0.9),
        "cascade_loco": cascade_loco(ps, ys, gs, 0.0, 0.9),
        "cascade_miss10": cascade(ps, ys, 0.1, 0.9),
        "cascade_miss10_loco": cascade_loco(ps, ys, gs, 0.1, 0.9),
        "top_prob_split": [top_split(rs, ys, pos, t) for t in (0.6, 0.7, 0.8, 0.9)],
    }
    if pos is not None:
        out["answers"] = dict(Counter(str(r["answer"]) for r in rows))
    return out


def extra_scores(judgement: str, cases: list[dict], rows_by_v: dict, pos_by_v: dict) -> dict:
    """Skyfall-comparable numbers per judgement."""

    ex = {}
    if judgement == "contra":
        # the curation probe's measure: contradictions found, and clean facts
        # that appear in a flagged non-labelled pair, over clean facts
        for v, rows in rows_by_v.items():
            by_case = defaultdict(list)
            for c, r in zip(cases, rows):
                by_case[c["case"]].append((c, r))
            found = total = false = clean = 0
            pairs_flagged = 0
            for case, items in by_case.items():
                contra_ids = {x for c, _ in items if c["truth"] in ("contradict", "bonus") for x in (c["a"], c["b"])}
                facts = {c["a"] for c, _ in items} | {c["b"] for c, _ in items}
                clean_facts = facts - contra_ids
                clean += len(clean_facts)
                flagged_facts = set()
                # one labelled contradiction may list alternative pairs: count it once
                labelled = defaultdict(bool)
                for c, r in items:
                    f = flag_of(r, pos_by_v[v])
                    pairs_flagged += f
                    if c["truth"] == "contradict":
                        labelled[c["cidx"]] |= f
                    elif c["truth"] == "clean" and f:
                        flagged_facts |= {c["a"], c["b"]} & clean_facts
                found += sum(labelled.values())
                total += len(labelled)
                false += len(flagged_facts)
            ex[v] = {"contradictions_found": pct(found, total), "clean_facts_flagged": pct(false, clean), "pairs_flagged": pairs_flagged}
        # code baseline, and code then Laya (only pairs the overlap shows)
        shown = [c["overlap"] >= 0.4 for c in cases]
        ex["code_overlap_0.4"] = {
            "pairs_shown": sum(shown),
            "of_pairs": len(cases),
            "labelled_pairs_shown": sum(1 for c, s in zip(cases, shown) if s and c["truth"] == "contradict"),
            "labelled_pairs": sum(1 for c in cases if c["truth"] == "contradict"),
        }
        # the same review budget as the code: per case, show Laya's top-k
        # pairs where k is how many pairs the overlap rule shows there
        by_case = defaultdict(list)
        for i, c in enumerate(cases):
            by_case[c["case"]].append(i)
        n_contra = len({(c["case"], c["cidx"]) for c in cases if c["truth"] == "contradict"})
        code_found = {(cases[i]["case"], cases[i]["cidx"]) for i in range(len(cases)) if shown[i] and cases[i]["truth"] == "contradict"}
        ex["code_overlap_0.4"]["contradictions_shown"] = pct(len(code_found), n_contra)
        for v, rows in rows_by_v.items():
            found, union, k_total = set(), set(code_found), 0
            for case, ids in by_case.items():
                k = max(1, sum(shown[i] for i in ids))
                k_total += k
                top = sorted(ids, key=lambda i: rows[i]["p_pos"], reverse=True)[:k]
                for i in top:
                    if cases[i]["truth"] == "contradict":
                        found.add((case, cases[i]["cidx"]))
                        union.add((case, cases[i]["cidx"]))
            ex[f"top_k_{v}"] = {
                "pairs_shown": k_total,
                "contradictions_shown": pct(len(found), n_contra),
                "union_with_code": pct(len(union), n_contra),
            }
        for v, rows in rows_by_v.items():
            sub = [(c, r) for c, r in zip(cases, rows) if c["overlap"] >= 0.4 and c["truth"] != "bonus"]
            ys = [c["truth"] == "contradict" for c, _ in sub]
            ex[f"code_then_{v}"] = {
                "pairs": len(sub),
                "auc": best_auc([r["p_pos"] for _, r in sub], ys),
                "cascade": cascade([r["p_pos"] for _, r in sub], ys),
                "cascade_loco": cascade_loco([r["p_pos"] for _, r in sub], ys, [c["case"] for c, _ in sub]),
            }
    if judgement == "elsewhere":
        for v, rows in rows_by_v.items():
            t = Counter()
            for c, r in zip(cases, rows):
                f = flag_of(r, pos_by_v[v])
                t[(c["prompt"], c["truth"], f)] += 1
            ex[v] = {f"{p}|{tr}|{'flagged' if f else 'kept'}": n for (p, tr, f), n in sorted(t.items())}
            if pos_by_v[v] is not None:
                ans = Counter((c["truth"], r["answer"]) for c, r in zip(cases, rows))
                ex[v]["answers_by_truth"] = {f"{a}|{b}": n for (a, b), n in sorted(ans.items())}
            ex[v]["borderline"] = [r["p_pos"] for c, r in zip(cases, rows) if c["borderline"]]
            ex[v]["false_items"] = [
                {"run": c["run"], "i": c["i"], "p": r["p_pos"], "answer": str(r["answer"]), "text": c["text"][:120]}
                for c, r in zip(cases, rows)
                if c["truth"] == "false"
            ]
    if judgement == "held":
        for v, rows in rows_by_v.items():
            att = [flag_of(r, pos_by_v[v]) for c, r in zip(cases, rows) if c["code"] == "a"]
            ex[v] = {"attributed_flagged": pct(sum(att), len(att))}
        b = [c for c in cases if c["code"] == "b"]
        p = [c for c in cases if c["code"] == "p"]
        ex["skyfall_on_this_set"] = {
            "beliefs_marked": pct(sum(c["skyfall_marked"] for c in b), len(b)),
            "plain_marked": pct(sum(c["skyfall_marked"] for c in p), len(p)),
        }
    if judgement == "movein":
        for v, rows in rows_by_v.items():
            ex[v] = {
                "either_flagged": [r["p_pos"] for c, r in zip(cases, rows) if c["truth"] == "either"],
                "moves": [(c["case"], c["id"], r["p_pos"]) for c, r in zip(cases, rows) if c["truth"] == "move"],
                "top_stays": sorted(
                    [(r["p_pos"], c["case"], c["id"], c["text"][:90]) for c, r in zip(cases, rows) if c["truth"] == "stay"],
                    reverse=True,
                )[:6],
            }
    if judgement in ("same", "names"):
        for v, rows in rows_by_v.items():
            ex[v] = {c["pair"]: {"truth": c["truth"], "answer": str(r["answer"]), "p_same": r["p_pos"], "probs": r["probs"]} for c, r in zip(cases, rows)}
    return ex


# --- main -----------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=list(JUDGEMENTS))
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--variants", nargs="*", default=None, help="only these phrasings (merged into saved rows)")
    ap.add_argument("--dry", action="store_true", help="build the cases and print one state per phrasing")
    ap.add_argument("--rescore", action="store_true", help="re-score the saved rows, no model")
    args = ap.parse_args()

    raw = json.loads(RAW_IN.read_text())
    labels = json.loads(LABELS.read_text())
    same = build_same(raw, labels)
    datasets = {
        "same": same,
        "names": same,
        "contra": build_contra(raw, labels),
        "held": build_held(raw),
        "movein": build_movein(raw, labels),
        "elsewhere": build_elsewhere(raw),
    }
    for k, v in datasets.items():
        print(k, len(v), dict(Counter(str(positive(k, c)) for c in v)), file=sys.stderr)
    if args.dry:
        for j in args.only:
            fn, variants = JUDGEMENTS[j]
            for v in variants:
                s, q, pos = fn(datasets[j][0], v)
                print(f"--- {j} {v}\n{s}\n{json.dumps(q)}\n")
        return

    if args.rescore:
        out = json.loads(RAW_OUT.read_text())
        for j, block in out["judgements"].items():
            fn, variants = JUDGEMENTS[j]
            cases = block["cases"]
            pos_by_v = {v: fn(cases[0], v)[2] for v in block["rows"]}
            block["scores"] = {v: score_variant(j, cases, rows, pos_by_v[v]) for v, rows in block["rows"].items()}
            block["extra"] = extra_scores(j, cases, block["rows"], pos_by_v)
        RAW_OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str) + "\n")
        return

    import torch
    import laya

    torch.set_num_threads(args.threads)
    t0 = time.perf_counter()
    agent = laya.load("convaiinnovations/laya", device="cpu")
    load_s = time.perf_counter() - t0
    # warm-up: one call per phrasing shape
    def chosen(j):
        return [v for v in JUDGEMENTS[j][1] if args.variants is None or v in args.variants]

    for j in args.only:
        fn = JUDGEMENTS[j][0]
        for v in chosen(j):
            s, q, _ = fn(datasets[j][0], v)
            for _ in range(2):
                agent.predict(s, {"q": q})

    out = json.loads(RAW_OUT.read_text()) if RAW_OUT.exists() else {}
    out.update(
        {
            "probe": "laya-curation",
            "date": "2026-10-22",
            "model": "convaiinnovations/laya (English checkpoint)",
            "laya_version": getattr(laya, "__version__", None),
            "torch": torch.__version__,
            "device": "cpu",
            "threads": torch.get_num_threads(),
            "load_seconds": round(load_s, 1),
            "temperature": list(agent.temperature) if hasattr(agent, "temperature") else None,
            "temperature_by_options": getattr(agent, "temperature_by_options", None),
        }
    )
    out.setdefault("judgements", {})
    for j in args.only:
        fn = JUDGEMENTS[j][0]
        variants = chosen(j)
        if not variants:
            continue
        cases = datasets[j]
        prev = out["judgements"].get(j, {})
        rows_by_v = dict(prev.get("rows", {}))
        pos_by_v, scores = {}, {}
        for v in variants:
            rows = []
            pos = None
            for c in cases:
                s, q, pos = fn(c, v)
                rows.append(ask(agent, s, q, pos))
            rows_by_v[v], pos_by_v[v] = rows, pos
            scores[v] = score_variant(j, cases, rows, pos)
            print(j, v, scores[v]["accuracy"], "recall", scores[v]["recall"], "false", scores[v]["false_flags"],
                  "auc", scores[v]["auc"], "auto", scores[v]["cascade"]["auto"], "loco", scores[v]["cascade_loco"]["auto"], scores[v]["cascade_loco"]["positives"], scores[v]["cascade_loco"]["negatives"], f"{scores[v]['seconds_mean']}s",
                  "trunc", scores[v]["truncated_calls"], file=sys.stderr)
        order = [v for v in JUDGEMENTS[j][1] if v in rows_by_v]
        rows_by_v = {v: rows_by_v[v] for v in order}
        pos_by_v = {v: fn(cases[0], v)[2] for v in order}
        out["judgements"][j] = {
            "cases": cases,
            "phrasings": {v: {"example_state": fn(cases[0], v)[0], "question": fn(cases[0], v)[1]} for v in order},
            "rows": rows_by_v,
            "scores": {v: score_variant(j, cases, rows_by_v[v], pos_by_v[v]) for v in order},
            "extra": extra_scores(j, cases, rows_by_v, pos_by_v),
        }
        RAW_OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str) + "\n")
    print(json.dumps({j: {v: {k: s[k] for k in ("accuracy", "recall", "false_flags", "auc")} for v, s in out["judgements"][j]["scores"].items()} for j in args.only}, indent=1))


if __name__ == "__main__":
    main()
