"""Throwaway probe: can the local model blend mixed heritage (half/quarter races and species)
consistently when creating a character? Mirrors world/create-thing.jinja2 plus a heritage block."""

import json
import sys
import urllib.request

URL = "http://192.168.0.5:5001/v1/chat/completions"

SPECIES = {
    "Human": [
        "Humans stand between five and six and a half feet tall, with smooth, nearly hairless skin and hair growing mainly on the head.",
        "Humans have rounded ears, small flat teeth and no tusks, claws or feathers.",
        "Humans live to about seventy-five years and reach adulthood around eighteen.",
        "Humans instinctively seek company and grow restless when kept alone for long.",
    ],
    "Orc": [
        "Orcs stand between six and seven feet tall, broad and heavily muscled, with grey-green skin.",
        "Orcs have a heavy brow ridge, pointed ears and two lower tusks that jut above the upper lip, often two inches long in adults.",
        "Orcs have coarse black hair and yellow or amber eyes that see well in dim light.",
        "Orcs live to about sixty years and reach adulthood around fourteen.",
        "Orcs have a strong territorial instinct and bristle when strangers enter their space uninvited.",
    ],
    "Owl-folk": [
        "Owl-folk stand between three and four feet tall, fully feathered, with a pair of wings spanning seven to nine feet in place of arms.",
        "Owl-folk have a round facial disc, a hooked beak, large forward-facing eyes and taloned feet that serve as hands for fine work.",
        "Owl-folk have light, hollow bones and can turn their heads nearly all the way around.",
        "Owl-folk live to about seventy years and reach adulthood around twelve.",
        "Owl-folk are instinctively crepuscular, most alert at dusk and dawn, and freeze motionless when startled.",
    ],
}

RACES = {
    "Lowlander": (
        "Human",
        [
            "Lowlanders are the shorter, stockier humans of the river plains, rarely over five foot eight.",
            "Lowlanders have olive to brown skin, dark brown or black hair and dark eyes.",
        ],
    ),
    "Highlander": (
        "Human",
        [
            "Highlanders are tall, rangy humans of the northern hills, often over six feet.",
            "Highlanders have pale, freckled skin, red or fair hair and grey or green eyes.",
        ],
    ),
    "Snowy": (
        "Owl-folk",
        [
            "Snowy owl-folk are the largest owl-folk, with wingspans near nine feet.",
            "Snowy owl-folk have white plumage flecked with grey or black and yellow eyes.",
        ],
    ),
}

PROMPT = "A blacksmith's apprentice in a frontier town, nineteen years old, quick-tempered but loyal to her master."

PLAIN_RULE = "The character's heritage is given below; build the character from it."
GUIDED_RULE = (
    "The character's heritage is given below, with the share of each. Blend the heritages in "
    "proportion into ONE consistent body, the way real mixed parentage looks:\n"
    "- A half shows clear traits of both sides, each softened or in between (e.g. shorter tusks, a "
    "skin tone between the two).\n"
    "- A quarter looks mostly like the larger share, with only one or two subtle traits of the "
    "smaller one.\n"
    "- For sizes and numbers (height, lifespan), pick one value in between, weighted by share.\n"
    "- Never list two traits that contradict each other.\n"
    "Describe only what the character inherits and what is unique to her."
)


def heritage_block(parts):
    lines = []
    for share, key in parts:
        if key in RACES:
            species, rfacts = RACES[key]
            lines.append(f"- {share} {species} ({key} race):")
            lines += [f"  - {f}" for f in SPECIES[species] + rfacts]
        else:
            lines.append(f"- {share} {key}:")
            facts = SPECIES[key] if key in SPECIES else MIXES[key]
            lines += [f"  - {f}" for f in facts]
    return "\n".join(lines)


MIXES: dict[str, list[str]] = {}


def chat(user, prefill, temperature=0.8, max_tokens=700):
    messages = [
        {"role": "system", "content": "You are a helpful worldbuilding assistant."},
        {"role": "user", "content": user},
        {"role": "assistant", "content": prefill},
    ]
    body = json.dumps({"messages": messages, "temperature": temperature, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        out = json.loads(r.read())["choices"][0]["message"]["content"]
    if "</think>" in out:
        out = out.split("</think>", 1)[1]
    return prefill + out


def create(parts, rule):
    user = (
        "You create a new character for a fantasy world from the owner's short prompt. Treat the prompt "
        "as intent, not a spec: invent plausible detail generously to fill it out. Keep everything the "
        "owner wrote.\n\n"
        f"Owner's prompt:\n{PROMPT}\n\n{rule}\n\nHeritage:\n{heritage_block(parts)}\n\n"
        'Reply with only one JSON object: {"name": "...", "age": 19, "facts": [{"category": "appearance", '
        '"text": "One claim, in a full sentence."}, ...]}\n'
        "- 6 to 9 facts, one claim each. category is one of: appearance, personality, background.\n"
        "- At least 4 appearance facts.\n"
        "No commentary, no markdown fences, just the JSON object."
    )
    return chat(user, "{")


def make_mix(name, parts):
    user = (
        f"Write the general reference facts for {name}s in a fantasy world: people of mixed parentage "
        "from the heritages below. These facts describe the group as a whole (ranges, typical traits), "
        "not one person. Blend the two sides sensibly into one consistent kind of body.\n\n"
        f"Heritage:\n{heritage_block(parts)}\n\n"
        'Reply with only one JSON object: {"name": "' + name + '", "facts": ["One claim, in a full sentence.", ...]}\n'
        "- 5 to 7 facts: appearance ranges, lifespan and age of maturity, instinctive tendencies.\n"
        "No commentary, no markdown fences, just the JSON object."
    )
    return chat(user, "{", temperature=0.7)


def main():
    out_path = sys.argv[1]
    runs = []

    def record(label, i, text):
        runs.append({"label": label, "run": i, "text": text})
        print(f"\n===== {label} #{i}\n{text}", flush=True)
        json.dump(runs, open(out_path, "w"), indent=2)

    cases = [
        ("half-orc / plain", [("1/2", "Lowlander"), ("1/2", "Orc")], PLAIN_RULE, 3),
        ("half-orc / guided", [("1/2", "Lowlander"), ("1/2", "Orc")], GUIDED_RULE, 3),
        ("quarter-orc / plain", [("3/4", "Lowlander"), ("1/4", "Orc")], PLAIN_RULE, 3),
        ("quarter-orc / guided", [("3/4", "Lowlander"), ("1/4", "Orc")], GUIDED_RULE, 3),
        ("half Lowlander half Highlander / guided", [("1/2", "Lowlander"), ("1/2", "Highlander")], GUIDED_RULE, 2),
        ("quarter Highlander / guided", [("3/4", "Lowlander"), ("1/4", "Highlander")], GUIDED_RULE, 2),
        ("human + owl-folk / plain", [("1/2", "Lowlander"), ("1/2", "Snowy")], PLAIN_RULE, 2),
        ("human + owl-folk / guided", [("1/2", "Lowlander"), ("1/2", "Snowy")], GUIDED_RULE, 2),
    ]
    for label, parts, rule, n in cases:
        for i in range(n):
            record(label, i, create(parts, rule))

    mix_text = make_mix("Half-orc", [("1/2", "Human"), ("1/2", "Orc")])
    record("AI-written Half-orc entry", 0, mix_text)
    try:
        MIXES["Half-orc"] = json.loads(mix_text, strict=False)["facts"]
    except Exception as e:  # noqa: BLE001
        print("mix parse failed:", e)
        return
    for i in range(3):
        record("from Half-orc entry", i, create([("all", "Half-orc")], PLAIN_RULE))


if __name__ == "__main__":
    main()
