"""Metrics for the overnight cultures AI evaluation (``eval_cultures_ai.py``).

Pure functions, no network: the script collects raw results from a live
backend, and this module turns them into numbers (``summarise``) and a
plain-language report (``render_markdown``). Tested in
``tests/dev/test_cultures_eval_metrics.py``.

The raw ``results`` dict the script writes (and ``summarise`` reads)::

    {"model", "started", "finished", "config",
     "cultures": {culture_id: {"name", "language": <Language as a dict>}},
     "trait_phrases": {"curse": [...], "saying": [...]},
     "scenarios": {key: {"expected": {culture_id: share}, "runs": [run, ...]}},
     "errors": [{"scenario", "run", "step", "error"}]}

    run = {"run", "project",
           "npcs": [{"role", "name", "culture_id", "event", "wall_s",
                     "culture_prompt_s", "pick_prompt_s", "entry"}],
           "narrations": [{"index", "action", "context", "prompt_tokens",
                           "prompt", "response"}],
           "snapshots": [{"data", "wall_s"}],
           "characters": [<get_world characters>],
           "glossary_new": [<glossary entries the run created>]}
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

from talemate.cultures.generator import fits
from talemate.cultures.models import Language
from talemate.cultures.words import COMMON_WORDS, clean_name, mid_sentence_occurrence

__all__ = [
    "HEADINGS",
    "SEEDED_NAMES",
    "TRAIT_CHARACTER",
    "hadrik_present",
    "share_from_generator",
    "share_fitting",
    "culture_distance",
    "narration_name_use",
    "verbatim_phrases",
    "summarise",
    "render_markdown",
]

TRAIT_CHARACTER = "Hadrik"
# Names the seeded scene messages contain, that a snapshot should pick up.
SEEDED_NAMES = ("Brannoch", "Grey Gull")

HEADINGS = {
    "naming": "Name generator accuracy",
    "fitting": "Names that fit their culture",
    "culture_guess": "Culture guesses vs the place mix",
    "narration": "Narrator spare-name use",
    "verbatim": "Curses and sayings used verbatim",
    "section": "Culture section size",
    "latency": "Latency added per creation",
    "snapshots": "Snapshot glossary yield",
}

EXCERPT_WIDTH = 160
SAMPLE_LIMIT = 40

# Always capitalised in English but never a name the narrator invented.
_CALENDAR_WORDS = frozenset(
    "monday tuesday wednesday thursday friday saturday sunday january "
    "february march april may june july august september october november "
    "december".split()
)

# A capitalised word, allowing inner apostrophes and hyphens ("Vel'dhaer").
_CAPITALISED = re.compile(r"\b[A-Z][\w'’-]*")
_QUOTES = str.maketrans(
    {
        "’": "'",
        "‘": "'",
        "ʼ": "'",
        "`": "'",
        "´": "'",
        "“": '"',
        "”": '"',
        "„": '"',
    }
)


# --- small helpers -----------------------------------------------------------


def _as_language(language) -> Language | None:
    if language is None or isinstance(language, Language):
        return language
    return Language.model_validate(language)


def _languages(language) -> list[Language]:
    if language is None:
        return []
    if isinstance(language, (Language, dict)):
        return [_as_language(language)]
    return [_as_language(item) for item in language if item is not None]


def _share(hits: int, total: int) -> float:
    return hits / total if total else 0.0


def _mean(values: Iterable[float]) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _p90(values: Iterable[float]) -> float | None:
    """Nearest-rank 90th percentile."""
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    rank = max(1, math.ceil(0.9 * len(values)))
    return values[rank - 1]


def _whole_word(word: str, text: str, *, ignore_case: bool = True) -> bool:
    flags = re.IGNORECASE if ignore_case else 0
    return (
        re.search(r"(?<![\w'’])" + re.escape(word) + r"(?![\w'’])", text, flags)
        is not None
    )


def _normalise(text: str) -> str:
    text = text.translate(_QUOTES).lower()
    return re.sub(r"\s+", " ", text).strip()


def _excerpt(text: str, word: str, width: int = EXCERPT_WIDTH) -> str:
    """About ``width`` characters of ``text`` around the first ``word``."""
    flat = re.sub(r"\s+", " ", text or "").strip()
    match = re.search(re.escape(word), flat, re.IGNORECASE)
    if match is None:
        return flat[:width] + ("…" if len(flat) > width else "")
    start = max(0, match.start() - width // 2)
    end = min(len(flat), match.end() + width // 2)
    return ("…" if start else "") + flat[start:end] + ("…" if end < len(flat) else "")


# --- the metric functions ----------------------------------------------------


def _from_generator(npc: dict) -> bool:
    entry = npc.get("entry") or {}
    origin = entry.get("origin") or {}
    language = _as_language(npc.get("language"))
    if origin.get("by") != "ai" or language is None:
        return False
    generator_ids = {generator.id for generator in language.generators}
    # Both cultures have e.g. "given_male", so the entry's language must
    # also be the NPC's culture.
    return origin.get("generator_id") in generator_ids and entry.get(
        "language"
    ) == npc.get("culture_id")


def share_from_generator(npcs: list[dict]) -> float:
    """Share of ``npcs`` named by the AI from their own culture's generator.

    Each NPC dict has ``culture_id`` (its assigned culture), ``language``
    (that culture's `Language`, or its dict) and ``entry`` (its glossary
    entry as a dict, or None). Counts NPCs whose entry has ``origin.by ==
    "ai"``, a ``generator_id`` of that language, and that language.
    """
    return _share(sum(1 for npc in npcs if _from_generator(npc)), len(npcs))


def _fits_culture(npc: dict) -> bool:
    language = _as_language(npc.get("language"))
    name = npc.get("name") or ""
    return bool(language is not None and name and fits(language, name))


def share_fitting(npcs: list[dict]) -> float:
    """Share of ``npcs`` whose ``name`` fits their assigned culture's language."""
    return _share(sum(1 for npc in npcs if _fits_culture(npc)), len(npcs))


def culture_distance(observed: dict[str, int], expected: dict[str, int]) -> float:
    """Total variation distance between observed counts and expected shares.

    Both are normalised to sum to 1. 0 is a perfect match, 1 is no overlap.
    No observations at all give 1.0.
    """
    observed_total = sum(observed.values())
    expected_total = sum(expected.values())
    if not observed_total or not expected_total:
        return 1.0
    keys = set(observed) | set(expected)
    return 0.5 * sum(
        abs(observed.get(k, 0) / observed_total - expected.get(k, 0) / expected_total)
        for k in keys
    )


def narration_name_use(prompt: str, response: str, spares: list[str], language) -> dict:
    """How a narration used names: a spare it was offered, or new ones.

    New names are capitalised words found mid-sentence in ``response``
    (`mid_sentence_occurrence`) that don't appear in ``prompt`` (whole
    word, any case), aren't in `COMMON_WORDS` (nor a weekday or month) and
    aren't a spare. Each one
    counts as fitting when it fits ``language`` (a `Language`, a dict, or a
    list of either: fitting any of them counts).
    """
    spare_keys = {spare.lower() for spare in spares}
    new_names: list[str] = []
    for match in _CAPITALISED.finditer(response or ""):
        word = clean_name(match.group(0)).strip("-'’")
        if not word or not word[:1].isupper():
            continue
        key = word.lower()
        if key in COMMON_WORDS or key in _CALENDAR_WORDS or key in spare_keys:
            continue
        if word in new_names:
            continue
        if _whole_word(word, prompt or ""):
            continue
        if not mid_sentence_occurrence(word, response):
            continue
        new_names.append(word)

    languages = _languages(language)
    invented_fit = sum(
        1 for name in new_names if any(fits(lang, name) for lang in languages)
    )
    return {
        "used_spare": any(_whole_word(spare, response or "") for spare in spares),
        "new_names": new_names,
        "invented_fit": invented_fit,
        "invented_misfit": len(new_names) - invented_fit,
    }


def _phrase_key(phrase: str) -> str:
    return _normalise(phrase).strip(" .!?,;:\"'")


def verbatim_phrases(response: str, phrases: list[str]) -> int:
    """Count ``phrases`` found in ``response``.

    Quotes, apostrophes, case and whitespace are normalised first, and a
    phrase's own end punctuation is optional ("Rhok tal'dun!" matches
    "Rhok tal’dun," too).
    """
    text = _normalise(response or "")
    return sum(
        1 for phrase in phrases if _phrase_key(phrase) and _phrase_key(phrase) in text
    )


# --- summarising -------------------------------------------------------------


def _npc_views(npcs: list[dict], languages: dict[str, Language]) -> list[dict]:
    return [{**npc, "language": languages.get(npc.get("culture_id"))} for npc in npcs]


def _naming(npcs: list[dict], languages: dict[str, Language]) -> dict:
    views = _npc_views(npcs, languages)
    ai_named = [
        npc
        for npc in npcs
        if ((npc.get("entry") or {}).get("origin") or {}).get("by") == "ai"
    ]
    return {
        "npcs": len(npcs),
        "ai_named": len(ai_named),
        "from_generator": sum(1 for v in views if _from_generator(v)),
        "share_from_generator": share_from_generator(views),
        "fitting": sum(1 for v in views if _fits_culture(v)),
        "share_fitting": share_fitting(views),
    }


def _culture_guess(npcs: list[dict], expected: dict[str, int]) -> dict:
    observed = Counter(npc.get("culture_id") or "(none)" for npc in npcs)
    return {
        "observed": dict(observed),
        "expected": dict(expected),
        "distance": culture_distance(dict(observed), expected) if npcs else None,
    }


def hadrik_present(narration: dict) -> bool:
    return _whole_word(
        TRAIT_CHARACTER, narration.get("response") or "", ignore_case=False
    )


def _narration(narrations: list[dict], languages: list[Language]) -> dict:
    counts = {"narrations": len(narrations), "with_new_name": 0, "used_spare": 0}
    counts["invented_fit"] = counts["invented_misfit"] = 0
    counts["offered_spares"] = 0
    for narration in narrations:
        use = narration.get("name_use") or {}
        spares = (narration.get("context") or {}).get("spares") or []
        counts["offered_spares"] += 1 if spares else 0
        counts["with_new_name"] += 1 if use.get("new_names") else 0
        counts["used_spare"] += 1 if use.get("used_spare") else 0
        counts["invented_fit"] += 1 if use.get("invented_fit") else 0
        counts["invented_misfit"] += 1 if use.get("invented_misfit") else 0
    return counts


def _verbatim(narrations: list[dict]) -> dict:
    present = [n for n in narrations if hadrik_present(n)]
    with_curse = sum(1 for n in present if n.get("curses_found"))
    with_saying = sum(1 for n in narrations if n.get("sayings_found"))
    return {
        "hadrik_present": len(present),
        "with_curse": with_curse,
        "rate": _share(with_curse, len(present)) if present else None,
        "with_saying": with_saying,
        "narrations": len(narrations),
    }


def _section(narrations: list[dict]) -> dict:
    tokens = [
        (n.get("context") or {}).get("tokens")
        for n in narrations
        if (n.get("context") or {}).get("tokens") is not None
    ]
    ratios = [
        n["context"]["tokens"] / n["prompt_tokens"]
        for n in narrations
        if (n.get("context") or {}).get("tokens") is not None and n.get("prompt_tokens")
    ]
    return {
        "injected": len(tokens),
        "narrations": len(narrations),
        "mean_tokens": _mean(tokens),
        "max_tokens": max(tokens) if tokens else None,
        "mean_ratio": _mean(ratios),
    }


def _latency(npcs: list[dict]) -> dict:
    prompt_s = [npc.get("culture_prompt_s") for npc in npcs]
    hook_ms = [
        (npc.get("event") or {}).get("ms")
        for npc in npcs
        if (npc.get("event") or {}).get("generator_id")
    ]
    pick_s = [
        npc.get("pick_prompt_s") for npc in npcs if npc.get("pick_prompt_s") is not None
    ]
    return {
        "creations": len(npcs),
        "mean_culture_prompt_s": _mean(prompt_s),
        "p90_culture_prompt_s": _p90(prompt_s),
        "mean_pick_prompt_s": _mean(pick_s),
        "pick_n": len(pick_s),
        "mean_hook_ms": _mean(hook_ms),
        "hook_n": len([ms for ms in hook_ms if ms is not None]),
        "mean_persist_s": _mean(npc.get("wall_s") for npc in npcs),
    }


def _attributed(name: dict, character_cultures: dict[str, str]) -> bool:
    if name.get("kind") == "person":
        culture = character_cultures.get((name.get("text") or "").lower())
        if culture is not None:
            return name.get("culture_id") == culture
    return not name.get("doesnt_fit")


def _character_cultures(characters: list[dict]) -> dict[str, str]:
    return {
        (c.get("name") or "").lower(): (c.get("culture") or {}).get("culture_id")
        for c in characters or []
        if (c.get("culture") or {}).get("culture_id")
    }


def _found(target: str, run: dict) -> bool:
    texts = [e.get("text") or "" for e in run.get("glossary_new") or []]
    for snapshot in run.get("snapshots") or []:
        texts += [
            n.get("text") or ""
            for n in (snapshot.get("data") or {}).get("new_names") or []
        ]
    return any(target.lower() in text.lower() for text in texts)


def _snapshots(runs: list[dict]) -> dict:
    counts, ms, attributed, total = [], [], 0, 0
    for run in runs:
        cultures = _character_cultures(run.get("characters") or [])
        for snapshot in run.get("snapshots") or []:
            data = snapshot.get("data") or {}
            names = data.get("new_names") or []
            counts.append(len(names))
            if data.get("ms") is not None:
                ms.append(data["ms"])
            total += len(names)
            attributed += sum(1 for name in names if _attributed(name, cultures))
    background = sum(
        max(
            0,
            len(run.get("all_snapshot_events") or []) - len(run.get("snapshots") or []),
        )
        for run in runs
    )
    return {
        "snapshots": len(counts),
        "background": background,
        "new_names": total,
        "mean_new_names": _mean(counts),
        "attributed": attributed,
        "attributed_share": _share(attributed, total) if total else None,
        "recall": {
            target: _share(sum(1 for run in runs if _found(target, run)), len(runs))
            if runs
            else None
            for target in SEEDED_NAMES
        },
        "mean_ms": _mean(ms),
    }


def _samples(key: str, runs: list[dict]) -> dict:
    names, excerpts = [], []
    for run in runs:
        for npc in run.get("npcs") or []:
            event = npc.get("event") or {}
            names.append(
                {
                    "scenario": key,
                    "run": run.get("run"),
                    "role": npc.get("role"),
                    "name": npc.get("name"),
                    "culture_id": npc.get("culture_id"),
                    "generator_id": event.get("generator_id"),
                    "by_model": event.get("by_model"),
                    "why": event.get("why"),
                    "candidates": event.get("candidates") or [],
                }
            )
        for narration in run.get("narrations") or []:
            use = narration.get("name_use") or {}
            response = narration.get("response") or ""
            spares = [
                s.get("text")
                for s in (narration.get("context") or {}).get("spares") or []
            ]
            reasons = []
            for spare in spares:
                if spare and _whole_word(spare, response):
                    reasons.append(("spare", spare))
            for name in use.get("new_names") or []:
                reasons.append(("new name", name))
            for phrase in narration.get("curses_found") or []:
                reasons.append(("curse", phrase))
            for phrase in narration.get("sayings_found") or []:
                reasons.append(("saying", phrase))
            for kind, word in reasons:
                excerpts.append(
                    {
                        "scenario": key,
                        "run": run.get("run"),
                        "narration": narration.get("index"),
                        "kind": kind,
                        "word": word,
                        "excerpt": _excerpt(
                            response,
                            word.rstrip(".!?") if kind in ("curse", "saying") else word,
                        ),
                    }
                )
    glossary = [
        {"scenario": key, "run": run.get("run"), **entry}
        for run in runs
        for entry in run.get("glossary_new") or []
    ]
    return {"names": names, "excerpts": excerpts, "glossary": glossary}


def _annotate(
    narrations: list[dict], languages: list[Language], phrases: dict
) -> list[dict]:
    """Add ``name_use``, ``curses_found`` and ``sayings_found`` to each narration."""
    out = []
    for narration in narrations:
        response = narration.get("response") or ""
        spares = [
            s.get("text") for s in (narration.get("context") or {}).get("spares") or []
        ]
        out.append(
            {
                **narration,
                "name_use": narration_name_use(
                    narration.get("prompt") or "",
                    response,
                    [s for s in spares if s],
                    languages,
                ),
                "curses_found": [
                    p
                    for p in phrases.get("curse", [])
                    if verbatim_phrases(response, [p])
                ],
                "sayings_found": [
                    p
                    for p in phrases.get("saying", [])
                    if verbatim_phrases(response, [p])
                ],
            }
        )
    return out


def _block(
    key: str,
    runs: list[dict],
    expected: dict[str, int],
    languages: dict[str, Language],
    phrases: dict,
) -> dict:
    scene_languages = [languages[c] for c in expected if c in languages]
    npcs = [npc for run in runs for npc in run.get("npcs") or []]
    annotated_runs = [
        {
            **run,
            "narrations": _annotate(
                run.get("narrations") or [], scene_languages, phrases
            ),
        }
        for run in runs
    ]
    narrations = [n for run in annotated_runs for n in run["narrations"]]
    naming = _naming(npcs, languages)
    return {
        "runs": len(runs),
        "naming": naming,
        "culture_guess": _culture_guess(npcs, expected),
        "narration": _narration(narrations, scene_languages),
        "verbatim": _verbatim(narrations),
        "section": _section(narrations),
        "latency": _latency(npcs),
        "snapshots": _snapshots(runs),
        "samples": _samples(key, annotated_runs),
        "_npcs": npcs,
        "_narrations": narrations,
    }


def summarise(results: dict) -> dict:
    """Compute every metric per scenario and overall from raw ``results``."""
    languages = {
        culture_id: _as_language(info.get("language"))
        for culture_id, info in (results.get("cultures") or {}).items()
        if info.get("language")
    }
    phrases = results.get("trait_phrases") or {}
    scenarios = {
        key: _block(
            key, data.get("runs") or [], data.get("expected") or {}, languages, phrases
        )
        for key, data in (results.get("scenarios") or {}).items()
    }

    all_npcs = [npc for block in scenarios.values() for npc in block.pop("_npcs")]
    all_narrations = [
        n for block in scenarios.values() for n in block.pop("_narrations")
    ]
    all_runs = [
        run
        for data in (results.get("scenarios") or {}).values()
        for run in data.get("runs") or []
    ]
    distances = [
        block["culture_guess"]["distance"]
        for block in scenarios.values()
        if block["culture_guess"]["distance"] is not None
    ]
    overall = {
        "runs": len(all_runs),
        "naming": _naming(all_npcs, languages),
        "culture_guess": {"mean_distance": _mean(distances)},
        "narration": _narration(all_narrations, list(languages.values())),
        "verbatim": _verbatim(all_narrations),
        "section": _section(all_narrations),
        "latency": _latency(all_npcs),
        "snapshots": _snapshots(all_runs),
    }
    return {
        "model": results.get("model"),
        "started": results.get("started"),
        "finished": results.get("finished"),
        "config": results.get("config") or {},
        "scenarios": scenarios,
        "overall": overall,
        "errors": list(results.get("errors") or []),
    }


# --- markdown ------------------------------------------------------------------


def _pct(value) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def _num(value, digits: int = 1, unit: str = "") -> str:
    return "n/a" if value is None else f"{value:.{digits}f}{unit}"


def _frac(hits, total) -> str:
    return f"{hits} of {total}" if total else "none"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" for _ in header) + "|",
    ]
    lines += [
        "| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |"
        for row in rows
    ]
    return lines


def _rows(summary: dict):
    """(label, block) for each scenario, then "All scenarios"."""
    for key, block in summary["scenarios"].items():
        yield key, block
    yield "**All scenarios**", summary["overall"]


def _mix(counts: dict) -> str:
    return (
        ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
        or "none"
    )


def render_markdown(summary: dict, model: str) -> str:
    """A plain-language report of ``summary``, for a non-technical reader."""
    config = summary.get("config") or {}
    out = [
        "# Cultures AI evaluation",
        "",
        f"- **Model:** {model}",
        f"- **Started:** {summary.get('started') or 'n/a'}",
        f"- **Finished:** {summary.get('finished') or 'not finished (partial report)'}",
        f"- **Size:** {config.get('runs', '?')} run(s) of each scenario, "
        f"{config.get('npcs', '?')} new characters and "
        f"{config.get('narrations', '?')} narrations per run, then 2 snapshots.",
        f"- **Errors:** {len(summary.get('errors') or [])} (listed at the end)",
        "",
        "Each run seeds a fresh test world with two made-up cultures: the "
        "Taelrik river-folk and the Elsiri coast-folk. The three scenarios "
        "put the scene in a Taelrik town (`taelrik_town`), an Elsiri "
        "village (`elsiri_pocket`, 90% Elsiri) and a mixed city "
        "(`mixed_city`, 60% Taelrik, 40% Elsiri). A dockhand called Hadrik "
        "is always present; his description says he curses in Taelrik.",
        "",
    ]

    out += [f"## {HEADINGS['naming']}", ""]
    out += [
        "When a new character is created, the Culture agent rolls candidate "
        "names from the right culture's name generator and asks the model to "
        "pick one. This counts the characters whose name came from their own "
        "culture's generator. Higher is better; 100% means every new "
        "character got a generator name from its own culture.",
        "",
    ]
    out += _table(
        [
            "Scenario",
            "New characters",
            "Named by the AI",
            "From the right generator",
            "Share",
        ],
        [
            [
                label,
                b["naming"]["npcs"],
                b["naming"]["ai_named"],
                b["naming"]["from_generator"],
                _pct(b["naming"]["share_from_generator"])
                if b["naming"]["npcs"]
                else "n/a",
            ]
            for label, b in _rows(summary)
        ],
    )

    out += ["", f"## {HEADINGS['fitting']}", ""]
    out += [
        "Whether each new character's name follows the sound rules of the "
        "culture it was given (checked by the name generator's own pattern "
        "test). Higher is better.",
        "",
    ]
    out += _table(
        ["Scenario", "New characters", "Name fits its culture", "Share"],
        [
            [
                label,
                b["naming"]["npcs"],
                b["naming"]["fitting"],
                _pct(b["naming"]["share_fitting"]) if b["naming"]["npcs"] else "n/a",
            ]
            for label, b in _rows(summary)
        ],
    )

    out += ["", f"## {HEADINGS['culture_guess']}", ""]
    out += [
        "The culture each new character was given, against the mix of the "
        "place the scene is in. The distance is 0 when the counts match the "
        "place's mix exactly and 1 when they don't overlap at all. With only "
        "a few characters per scenario, some distance is expected by chance "
        "in the mixed places.",
        "",
    ]
    out += _table(
        ["Scenario", "Cultures given", "Place mix (%)", "Distance"],
        [
            [
                key,
                _mix(b["culture_guess"]["observed"]),
                _mix(b["culture_guess"]["expected"]),
                _num(b["culture_guess"]["distance"], 2),
            ]
            for key, b in summary["scenarios"].items()
        ]
        + [
            [
                "**All scenarios (mean)**",
                "",
                "",
                _num(summary["overall"]["culture_guess"]["mean_distance"], 2),
            ]
        ],
    )

    out += ["", f"## {HEADINGS['narration']}", ""]
    out += [
        "The narrator's prompt offers a few spare names (\"If you need a new "
        'name, use one of these: …"). For each narration this checks whether '
        "it used a spare, or invented a new name of its own (a capitalised "
        "word mid-sentence that wasn't in the prompt), and whether invented "
        "names still fit the scene's cultures. Using a spare or inventing a "
        "fitting name is good; an invented misfit is what the feature is "
        "meant to prevent. Counts are narrations, not names.",
        "",
    ]
    out += _table(
        [
            "Scenario",
            "Narrations",
            "Offered spares",
            "With a new name",
            "Used a spare",
            "Invented a fitting name",
            "Invented a misfit",
        ],
        [
            [
                label,
                b["narration"]["narrations"],
                b["narration"]["offered_spares"],
                b["narration"]["with_new_name"],
                b["narration"]["used_spare"],
                b["narration"]["invented_fit"],
                b["narration"]["invented_misfit"],
            ]
            for label, b in _rows(summary)
        ],
    )

    out += ["", f"## {HEADINGS['verbatim']}", ""]
    out += [
        "Hadrik curses in Taelrik, and the prompt gives the narrator his "
        "exact Taelrik curses. The rate is the narrations that contain at "
        "least one of those curses word for word, out of the narrations "
        "where Hadrik appears. Case, the kind of quote marks and a curse's "
        'own end punctuation are ignored, so "Rhok tal’dun," counts for '
        '"Rhok tal\'dun!". Sayings are counted over all narrations, for '
        "information.",
        "",
    ]
    out += _table(
        [
            "Scenario",
            "Narrations with Hadrik",
            "With a curse",
            "Curse rate",
            "With a saying",
        ],
        [
            [
                label,
                b["verbatim"]["hadrik_present"],
                b["verbatim"]["with_curse"],
                _pct(b["verbatim"]["rate"]),
                _frac(b["verbatim"]["with_saying"], b["verbatim"]["narrations"]),
            ]
            for label, b in _rows(summary)
        ],
    )

    out += ["", f"## {HEADINGS['section']}", ""]
    out += [
        'How much room the "Cultures and names" section takes in the '
        "narrator's prompt, in tokens (the budget is 400). The share is the "
        "section's tokens divided by the whole prompt's tokens: lower means "
        "less overhead.",
        "",
    ]
    out += _table(
        [
            "Scenario",
            "Prompts with the section",
            "Mean tokens",
            "Max tokens",
            "Share of the prompt",
        ],
        [
            [
                label,
                _frac(b["section"]["injected"], b["section"]["narrations"]),
                _num(b["section"]["mean_tokens"], 0),
                b["section"]["max_tokens"]
                if b["section"]["max_tokens"] is not None
                else "n/a",
                _num(
                    None
                    if b["section"]["mean_ratio"] is None
                    else b["section"]["mean_ratio"] * 100,
                    1,
                    "%",
                ),
            ]
            for label, b in _rows(summary)
        ],
    )

    out += ["", f"## {HEADINGS['latency']}", ""]
    out += [
        "Extra waiting time the Culture agent adds when a character is "
        'created. "Culture model time" is all Culture-agent model calls '
        "during the creation (the name pick, plus any place or custom check "
        'a background snapshot ran at the same time); "name pick" is the '
        'name-pick call alone. "Hook time" is the whole naming step as '
        'the agent measured it. "p90" is the time that 9 out of 10 '
        "creations stayed under, so it shows the slow cases the mean hides. "
        "The name pick and the hook time only exist for creations where the "
        "agent picked a name from a generator, so those two columns give "
        "their own count (n), which can be smaller than the creations "
        "count. The full creation time includes the creator's own model "
        "calls, which happen with or without cultures.",
        "",
    ]
    out += _table(
        [
            "Scenario",
            "Creations",
            "Culture model time (mean)",
            "Culture model time (p90)",
            "Name pick (mean, n)",
            "Hook time (mean, n)",
            "Full creation (mean)",
        ],
        [
            [
                label,
                b["latency"]["creations"],
                _num(b["latency"]["mean_culture_prompt_s"], 1, " s"),
                _num(b["latency"]["p90_culture_prompt_s"], 1, " s"),
                _num(b["latency"]["mean_pick_prompt_s"], 1, " s")
                + f" (n={b['latency']['pick_n']})",
                _num(
                    None
                    if b["latency"]["mean_hook_ms"] is None
                    else b["latency"]["mean_hook_ms"] / 1000,
                    1,
                    " s",
                )
                + f" (n={b['latency']['hook_n']})",
                _num(b["latency"]["mean_persist_s"], 1, " s"),
            ]
            for label, b in _rows(summary)
        ],
    )

    out += ["", f"## {HEADINGS['snapshots']}", ""]
    out += [
        "After the narrations, two world-state snapshots are requested. The "
        "Culture agent then adds new names it finds to the glossary. "
        '"Correctly attributed" means a character\'s name was filed under '
        "that character's culture, and any other name wasn't flagged as not "
        'fitting its language. The seeded scene text mentions "Old '
        'Brannoch" and the barge "Grey Gull": recall is the share of runs '
        "where each one reached the glossary (from any snapshot). Talemate "
        "also runs snapshots by itself, e.g. while a character is created; "
        'those are counted as "background" and their names are in the '
        "glossary samples below, but not in the per-snapshot numbers.",
        "",
    ]
    out += _table(
        [
            "Scenario",
            "Snapshots (background)",
            "New names (mean per snapshot)",
            "Correctly attributed",
            "Brannoch found",
            "Grey Gull found",
            "Snapshot culture time (mean)",
        ],
        [
            [
                label,
                f"{b['snapshots']['snapshots']} ({b['snapshots']['background']})",
                _num(b["snapshots"]["mean_new_names"], 1),
                _pct(b["snapshots"]["attributed_share"]),
                _pct(b["snapshots"]["recall"]["Brannoch"]),
                _pct(b["snapshots"]["recall"]["Grey Gull"]),
                _num(
                    None
                    if b["snapshots"]["mean_ms"] is None
                    else b["snapshots"]["mean_ms"] / 1000,
                    1,
                    " s",
                ),
            ]
            for label, b in _rows(summary)
        ],
    )

    out += _render_samples(summary)

    out += ["", "## Errors", ""]
    errors = summary.get("errors") or []
    if not errors:
        out.append("None.")
    else:
        out += _table(
            ["Scenario", "Run", "Step", "Error"],
            [
                [
                    e.get("scenario"),
                    e.get("run"),
                    e.get("step"),
                    (e.get("error") or "").splitlines()[0][:300]
                    if e.get("error")
                    else "",
                ]
                for e in errors
            ],
        )
        out += ["", "Full tracebacks are in report.json."]
    out.append("")
    return "\n".join(out)


def _render_samples(summary: dict) -> list[str]:
    names = [n for b in summary["scenarios"].values() for n in b["samples"]["names"]]
    excerpts = [
        e for b in summary["scenarios"].values() for e in b["samples"]["excerpts"]
    ]
    glossary = [
        g for b in summary["scenarios"].values() for g in b["samples"]["glossary"]
    ]
    out = ["", "## Samples to read", ""]
    out += [
        "The numbers above are easier to judge with the actual output in "
        "front of you. All of it is also in report.json.",
        "",
        "### Names chosen",
        "",
    ]
    if names:
        out += _table(
            [
                "Scenario",
                "Run",
                "Role",
                "Name",
                "Culture",
                "Generator",
                "Picked by the model",
                "First candidates",
            ],
            [
                [
                    n["scenario"],
                    n["run"],
                    n["role"],
                    n["name"] or "(none)",
                    n["culture_id"] or "(none)",
                    n["generator_id"] or "-",
                    "yes" if n["by_model"] else "no",
                    ", ".join(n["candidates"][:8])
                    + (" …" if len(n["candidates"]) > 8 else ""),
                ]
                for n in names[: SAMPLE_LIMIT * 2]
            ],
        )
    else:
        out.append("None.")

    out += ["", "### Narration excerpts (spare names, new names, curses, sayings)", ""]
    if excerpts:
        out += _table(
            ["Scenario", "Run", "Narration", "What", "Word", "Excerpt"],
            [
                [
                    e["scenario"],
                    e["run"],
                    e["narration"],
                    e["kind"],
                    e["word"],
                    e["excerpt"],
                ]
                for e in excerpts[: SAMPLE_LIMIT * 2]
            ],
        )
    else:
        out.append("None.")

    out += ["", "### Glossary entries the runs created", ""]
    if glossary:
        out += _table(
            [
                "Scenario",
                "Run",
                "Text",
                "Kind",
                "Language",
                "Origin",
                "Doesn't fit",
                "Character",
            ],
            [
                [
                    g["scenario"],
                    g["run"],
                    g.get("text"),
                    g.get("kind"),
                    g.get("language") or "-",
                    (g.get("origin") or {}).get("by"),
                    "yes" if g.get("doesnt_fit") else "no",
                    g.get("character_name") or "-",
                ]
                for g in glossary
            ],
        )
    else:
        out.append("None.")
    return out
