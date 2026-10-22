"""Throwaway probe: what structure does Skyfall propose for a 'sphere' (religion, academy,
field of knowledge, culture)? Free drawers (A) vs a menu of drawer types (B)."""

import json
import sys
import urllib.request

URL = "http://192.168.0.5:5001/v1/chat/completions"

WORLD = """World context (year 1020):
- Owl-folk: a people of owl-like humanoids, fully feathered, wings in place of arms, taloned feet used as hands. Origin: in 994, everyone in the Tsardom of Moscavia was transformed into owl-folk overnight; some humans elsewhere were untouched.
- Tsardom of Moscavia: a northern realm ruled by a Tsar from Moskov; since the transformation, mostly owl-folk; tense relations with human neighbours.
- Humans: the other intelligent people of the world."""

SPHERES = [
    ("religion", "The White Dawn: the state church of Moscavia, which teaches that the transformation was a purification."),
    ("academy", "The Imperial Academy of Runecraft in Moskov, where owl-folk scholars study runic magic."),
    ("field", "Runic magic: magic worked by carving runes, as practised in Moscavia."),
    ("culture", "Moscavian culture: the customs and ways of life of the owl-folk of Moscavia."),
]

FREE = """Design the reference entry for this {kind} in a fantasy world, as a structured entry like a wiki page.

{world}

Entry: {prompt}

Decide which sections (lists) this entry needs. Choose and title them yourself to suit this {kind}; a list holds named items (each could become its own entry) or plain statements.

Reply with only one JSON object:
{{"name": "...", "summary": "two or three sentences", "agent": true|false, "sections": [{{"title": "...", "items": [{{"name": "a proper name, or empty if the item is a statement", "text": "one sentence"}}]}}], "people": [{{"name": "a proper name", "role": "their relationship to this {kind}"}}], "timeline": [{{"year": 1015, "text": "what happened, or what it said or did"}}]}}
- "agent": true if this {kind} acts in the world (it decides, rules, declares, teaches); false if it is a body of knowledge or custom that is acted upon.
- 3 to 6 sections, 2 to 5 items each. 2 to 5 people. 2 to 5 timeline entries, years no later than 1020.
No commentary, no markdown fences."""

MENU = """Design the reference entry for this {kind} in a fantasy world, as a structured entry like a wiki page.

{world}

Entry: {prompt}

Build it from these section types. Pick only the types that fit this {kind}, give each a title that suits it (for a religion, "Practices" might be titled "Rites and Ceremonies"), and fill it:
- people: who belongs to or shapes it, each with their relationship (role)
- places: where it is, holds or acts
- practices: rites, ceremonies, customs, techniques, holidays
- beliefs: teachings, values, attitudes, myths
- knowledge: what is known, studied or still unknown (its frontier)
- structure: ranks, offices, councils, divisions
- branches: sub-groups, schools, sects or denominations
- events: what it has done or said, or what happened to it, by year

Reply with only one JSON object:
{{"name": "...", "summary": "two or three sentences", "agent": true|false, "sections": [{{"type": "one of the types above", "title": "...", "items": [{{"name": "a proper name, or empty", "text": "one sentence", "year": null}}]}}]}}
- "agent": true if it acts in the world; false if it is a body of knowledge or custom that is acted upon.
- 3 to 7 sections, 2 to 5 items each; give "year" (no later than 1020) only for events.
No commentary, no markdown fences."""


def chat(user, temperature=0.8, max_tokens=1600):
    messages = [
        {"role": "system", "content": "You are a worldbuilding assistant that replies in JSON."},
        {"role": "user", "content": user},
        {"role": "assistant", "content": "{"},
    ]
    body = json.dumps({"messages": messages, "temperature": temperature, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        out = json.loads(r.read())["choices"][0]["message"]["content"]
    if "</think>" in out:
        out = out.split("</think>", 1)[1]
    return "{" + out


def main():
    out_path = sys.argv[1]
    runs = []
    for kind, prompt in SPHERES:
        for style, template in (("A free", FREE), ("B menu", MENU)):
            for i in range(2):
                text = chat(template.format(kind=kind, prompt=prompt, world=WORLD))
                runs.append({"kind": kind, "style": style, "run": i, "text": text})
                print(f"\n===== {kind} / {style} #{i}\n{text}", flush=True)
                json.dump(runs, open(out_path, "w"), indent=2)


if __name__ == "__main__":
    main()
