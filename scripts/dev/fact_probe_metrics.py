"""Metrics for the fact round-trip probe (Phase 0 of the world-store work).

Pure functions, no network: a probe script (Task 2) drives a local LLM
through description -> facts -> prose -> facts -> ... round trips and
collects raw results; this module turns them into numbers (``summarise``)
and a plain-language report (``render_markdown``). Tested in
``tests/dev/test_fact_probe_metrics.py``.

The raw ``results`` dict the script writes (and ``summarise`` reads)::

    {"model", "started", "finished",
     "samples": [{"name",
                  "rounds": [{"facts": [{"category", "text"}],
                              "prose", "invented": [...], "dropped": [...]}]}],
     "errors": [{"sample", "round", "step", "error"}]}

Round 0's ``facts`` come from the source description; round N's come from
round N-1's prose. ``invented`` lists prose claims with no backing in that
round's facts; ``dropped`` lists facts the prose left out.
"""

from __future__ import annotations

import re
from itertools import zip_longest

__all__ = ["summarise", "render_markdown"]


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _drift(rounds: list[dict]) -> float:
    """Share of round-0 facts with no exact (normalised) match in the last round."""
    if not rounds:
        return 0.0
    first = [_normalise(f.get("text")) for f in rounds[0].get("facts") or []]
    if not first:
        return 0.0
    last = {_normalise(f.get("text")) for f in rounds[-1].get("facts") or []}
    missing = sum(1 for text in first if text not in last)
    return missing / len(first)


def _sample_summary(sample: dict) -> dict:
    rounds = sample.get("rounds") or []
    return {
        "facts_per_round": [len(r.get("facts") or []) for r in rounds],
        "invented_per_round": [len(r.get("invented") or []) for r in rounds],
        "dropped_per_round": [len(r.get("dropped") or []) for r in rounds],
        "drift": _drift(rounds),
    }


def _sum_lists(lists: list[list[int]]) -> list[int]:
    return [sum(values) for values in zip_longest(*lists, fillvalue=0)]


def summarise(results: dict) -> dict:
    """Compute per-sample and total metrics from a probe's raw ``results``."""
    samples = {
        sample.get("name"): _sample_summary(sample)
        for sample in results.get("samples") or []
    }
    totals = {
        "facts_per_round": _sum_lists([s["facts_per_round"] for s in samples.values()]),
        "invented_per_round": _sum_lists(
            [s["invented_per_round"] for s in samples.values()]
        ),
        "dropped_per_round": _sum_lists(
            [s["dropped_per_round"] for s in samples.values()]
        ),
    }
    return {
        "model": results.get("model"),
        "started": results.get("started"),
        "finished": results.get("finished"),
        "samples": samples,
        "totals": totals,
        "errors": list(results.get("errors") or []),
    }


# --- markdown ----------------------------------------------------------------


def _table(header: list[str], rows: list[list]) -> list[str]:
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" for _ in header) + "|",
    ]
    lines += [
        "| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |"
        for row in rows
    ]
    return lines


def _pct(value) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def render_markdown(results: dict, summary: dict) -> str:
    """A plain-language report of a probe's ``results``, using its ``summary``."""
    out = [
        "# Fact probe: round-trip metrics",
        "",
        f"- **Model:** {summary.get('model') or results.get('model') or 'n/a'}",
        f"- **Started:** {summary.get('started') or 'n/a'}",
        f"- **Finished:** {summary.get('finished') or 'not finished (partial report)'}",
        "",
        "Round 0's facts come from the source description; round N's facts "
        "come from round N-1's prose. `invented` lists prose claims with no "
        "backing in that round's facts; `dropped` lists facts the prose "
        "left out. `drift` is the share of round-0 facts with no exact "
        "(case- and whitespace-insensitive) match in the last round.",
        "",
    ]

    samples = {sample.get("name"): sample for sample in results.get("samples") or []}
    for name, sample_summary in summary.get("samples", {}).items():
        sample = samples.get(name) or {}
        rounds = sample.get("rounds") or []
        out += [f"## Sample: {name}", ""]
        out += [
            f"- **Drift (round 0 -> last round):** {_pct(sample_summary['drift'])}",
            "",
        ]
        out += _table(
            ["Round", "Facts", "Invented", "Dropped"],
            [
                [i, facts, invented, dropped]
                for i, (facts, invented, dropped) in enumerate(
                    zip_longest(
                        sample_summary["facts_per_round"],
                        sample_summary["invented_per_round"],
                        sample_summary["dropped_per_round"],
                        fillvalue=0,
                    )
                )
            ],
        )
        out.append("")

        invented_claims = [
            (i, claim)
            for i, round_ in enumerate(rounds)
            for claim in round_.get("invented") or []
        ]
        out += ["### Invented claims", ""]
        if invented_claims:
            out += _table(
                ["Round", "Claim"],
                [[i, claim] for i, claim in invented_claims],
            )
        else:
            out.append("None.")
        out.append("")

    out += ["## Totals", ""]
    totals = summary.get("totals") or {}
    out += _table(
        ["Round", "Facts", "Invented", "Dropped"],
        [
            [i, facts, invented, dropped]
            for i, (facts, invented, dropped) in enumerate(
                zip_longest(
                    totals.get("facts_per_round") or [],
                    totals.get("invented_per_round") or [],
                    totals.get("dropped_per_round") or [],
                    fillvalue=0,
                )
            )
        ],
    )
    out.append("")

    errors = summary.get("errors") or results.get("errors") or []
    if errors:
        out += ["## Errors", ""]
        out += _table(
            ["Sample", "Round", "Step", "Error"],
            [
                [
                    e.get("sample"),
                    e.get("round"),
                    e.get("step"),
                    (e.get("error") or "").splitlines()[0][:300]
                    if e.get("error")
                    else "",
                ]
                for e in errors
            ],
        )
        out.append("")

    return "\n".join(out)
