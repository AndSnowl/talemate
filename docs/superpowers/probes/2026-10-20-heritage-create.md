# Probe: creating species, races, mixes and characters with heritage

Date: 2026-10-20. Model: koboldcpp, Skyfall-31B-v4.2-i1-Q4_K_M, temperature 0.8, prefill `{`, calls run one at a time (8–35 s each). Plan B, Task 4: settles the wording of the create templates for Tasks 6 and 7.

- Script: `scripts/dev/probe_heritage_create.py` (`--variant a|b|c|d`, `--only`, `--entries`).
- Raw output: `raw/2026-10-20-heritage-create.json`. It has all 72 calls, each with its variant, reply, label map and analysis. Each case's first run keeps the full prompt.

## Setup

**The world:** the blending probe's species and races, each fact with an id. Two facts were split out so an override can hit exactly one claim:

| Thing | Numbers | Facts that matter here |
|---|---|---|
| Human (species) | lifespan 75, adult 18, height 5–6.5 ft | hair "brown, black, fair or red", rounded ears, no tusks |
| Lowlander (race of Human) | height 5–5.7 ft | "olive to brown skin, dark brown or black hair and dark eyes" |
| Orc (species) | lifespan 60, adult 14, height 6–7 ft, tusk length 1.5–2.5 in | coarse black hair; yellow or amber eyes; tusks, brow, ears |
| Owl-folk (species) | lifespan 70, adult 12, height 3–4 ft, wingspan 7–9 ft | wings in place of arms; talons as hands; plumage "mottled brown and grey, for camouflage against bark" |
| Snowy (race of Owl-folk) | wingspan 8.5–9 ft | white plumage (overrides Owl-folk's plumage); "bright yellow eyes" |

**The prompts** mirror `world/create-thing.jinja2`: the same TASK and FORMAT sections, with section markers rendered as `## Task` and `## Format` the way Talemate's default sectioning does. They keep the "since" and inherent-trait rules and the same JSON shape, with `lifespan`, `adult_age` and `measures` added for heritage kinds. Inherited facts are listed as `- F3 (Snowy, physical): text`, numbered across the whole lineage, most specific first, with facts that a lineage layer overrides already dropped. Replies are read with the shared non-strict `create.json_objects`.

**The cases, 3 runs per variant:**
1. Owl-folk species, from "Owl-folk: small feathered people with wings instead of arms, who hunt at dusk in the old forests."
2. Races:
   - Snowy inside Owl-folk, from "the largest owl-folk, white-plumaged, from the frozen north". Expected override: Owl-folk plumage (F4).
   - Highlander inside Human, from "tall, pale, red-haired humans of the northern hills". Expected override: none, since Human's "brown, black, fair or red hair" allows red.
3. Mixes:
   - Half-orc from Lowlander × Orc, with no owner prompt and the blending probe's guided rule.
   - Quarter-orc from Lowlander × the Half-orc just drafted (the first parsed entry of the run), with the prompt "Mostly human to look at; the orc blood shows only a little."
4. A Snowy character, from "A Snowy owl-folk courier with blue eyes, twenty-two, …". Expected override: Snowy "bright yellow eyes".
5. A Quarter-orc character (Lowlander × Half-orc), from "A dockhand with red hair, thirty, …". Expected overrides: every surviving inherited fact that gives a dark hair colour without red. These are the Quarter-orc's own hair fact (the direct layer) and the Half-orc's, Lowlander's or Orc's where they survive (the deep layers).

**The variants:**
- **a:** the first wording. The examples carry real numbers (`"lifespan": 80`, height 5–6), the heritage kinds keep the full "since" rules, and the per-fact `"overrides": ["F1"]` sits in the example, with the rule "only when your fact and the inherited one can't both be true".
- **b:**
  - placeholder `0` numbers in the example, with a note that they are placeholders;
  - for heritage kinds, "Leave "since" out: these facts describe the species for as long as it has existed";
  - a stricter override rule, with a worked contradiction ("grey fur" vs black fur) and a worked non-contradiction ("scarred paws" fits "padded paws");
  - `"overrides": []` in the example.
- **c:** b, plus a step in the task section: "check every detail of the owner's prompt against the inherited facts … any layer, the species' facts at the bottom included". Applies to characters and races. Races also get "leave learned customs out, they belong to cultures".
- **d:** c, but overrides are asked as one top-level `"no_longer_true": ["F4"]` list after the facts, not per fact. Run for races, mixes and characters. Code would attach each label to the own fact that shares the most content words with it.

## Results

**Parse rate:** 71 of 72 calls parsed whole, and none were cut off. The one failure, variant d (Snowy character run 2), broke one fact object (`"text", "since": 812: "…"`). The shared parser still recovers 9 of its 10 fact objects, but the top-level `no_longer_true` list is lost with the wrapper. Fact counts mostly stayed inside the asked range. The exceptions were one variant-a species reply with 14 (the parser caps at 12) and four mix replies with 9 or 10 when 5–8 were asked.

### 1. Species (Owl-folk)

| | a | b |
|---|---|---|
| lifespan / adult | 45/10, 60/14, 45/10 | 45/8, 40/8, 40/8 |
| height | **5–6, 5–6**, 4–5 ft | 2.5–3.5, 2–3, 1–2 ft |
| wingspan | 8–11, 10–12, 7–9 ft | 6–8, 5–7, 3–5 ft |
| `since` | run 0: `"inherent"` on 12 facts, `"unknown"`, `400`; runs 1–2: origin dated `0` or `100` | none |

- **Variant a copied the example's height.** It gave 5–6 ft in 2 of 3 runs for "small feathered people". The placeholder `0`s of variant b were never copied, and every b run sized the owl-folk as small.
- **Variant a dated the origin facts.** That would hide them from any scene set before year 100 or 400. Variant b's plain "leave it out" stopped it: no `since` in any heritage run.
- **The facts were good in both variants.** All five categories were used, the instincts were inborn (crepuscular, ambush, territorial), and the variation facts were about plumage and size by region. Only nests and calls stood in for customs.

### 2. Races

**Overrides:**

| | a | b | c | d |
|---|---|---|---|---|
| Snowy: F4 marked | 0/3 | 2/3 | 1/3 | **3/3** |
| Snowy: spurious | 1 (facial disc) | 0 | 1 (instinct) | 0 |
| Highlander: spurious | 1 (hair/eyes) | 0 | 0 | 0 |

- **Per-fact overrides miss on races.** The model writes a plumage fact like "camouflage against snow rather than forest bark", which plainly replaces F4, then leaves `overrides` empty. The prompt check of variant c didn't help (1/3).
- **The top-level list caught it every time.** Asking "which species facts are now untrue?" after the facts got 3/3 with nothing spurious. The word-overlap attach put F4 on the race's plumage fact in all three runs, once heritage names ("owl", "folk") are left out of the overlap.

**Numbers:**
- **The race narrows or extends the measures sensibly.** Snowy came out at height 4–5 ft (the species is 3–4; "the largest") and wingspan 8–10 ft; Highlander at 6–6.5 ft against Human's 5–6.5.
- **But it often restates unchanged numbers.** Snowy repeated lifespan 70 and adult 12 in 2 runs of b, and one run gave height 3–4 and wingspan 7–9, the species' own ranges. Highlander gave 75/18 once.
- **Highlander invented a longer life three times:** 80/18 twice and 85/20. That's plausible, but nothing in the prompt asked for it.

**Consistency with the species:** every race kept the species' body: wings and no arms, talons, facial disc. Snowy facts added snowshoe-feathered feet, dense down and a shift toward daytime hunting.

**Culture leakage:** before the customs line (variants a and b), Highlander facts drifted into clan halls, governing elders, stone settlements and oral tradition. With the line (c and d), only one fact in six runs mentioned songs.

### 3. Mixes

**Numbers:** sensible every time for the Half-orc.

| | parents | a | b | d |
|---|---|---|---|---|
| lifespan | 75 / 60 | 65–68 | 65 | 67–68 |
| adult age | 18 / 14 | 16 | 16 | 16 |
| height | 5–5.7 / 6–7 ft | 5.5–6.5 | 5.5–6.5 | 5.5–6.3 |
| tusk length | – / 1.5–2.5 in | 0.5–1.5 | 0.5–1.5 | 0.5–1.5 |

- **The Quarter-orc's height and tusks always sat between its parents:** height 5–6.1 ft, tusks 0.2–0.9 in. Variant a's guided rule still produced the "half of a mix entry" result the blending probe found.
- **The Quarter-orc's lifespan sometimes did not:**
  - all 3 variant-b runs gave 60 when the parents are 75 and 65;
  - two variant-d runs gave 60 and 63 when the parents are 75 and 67;
  - the variant-a runs gave 71–72, between their parents.

**Overrides:**
- **Per fact, the mix marks the parents' facts it blends, densely and mostly rightly.** In variant b the skin fact overrode Lowlander's and Orc's skin, the tusk fact Human's "no tusks", the instinct fact both instincts, and the hair fact both hair facts. That's 8–9 of 11 facts per run, for 5 to 8 own facts.
- **A few labels were off by one or miss a part:** the tusk fact marked Orc's skin fact, not Orc's tusk fact (b run 0). The cost is small: the dropped fact is still covered by some blended fact.
- **The top-level list (d) was sparse,** at 1 to 3 labels per Half-orc run. It left Orc's skin, hair and tusk facts standing beside the blended ones, and the attach misplaced labels on multi-topic facts, about a third of the time. For example, Human's hair-and-eye fact went to the skin fact.

**Facts:** consistent, one body, both parents visible:
- grey-green to olive skin;
- tusks of half an inch to an inch and a half;
- a softened brow and moderately pointed ears;
- coarse dark hair;
- amber eyes;
- "sociable but territorial".

### 4. Snowy character, "blue eyes"

| | a | b | c | d |
|---|---|---|---|---|
| F3 (yellow eyes) marked | 2/3 | 2/3 | **3/3** | 3/3 (one reply lost the list with its wrapper) |
| spurious | 7, 0, 1 | 0 | 0, 0, 2 | 0 |

- **Variant a uses `overrides` as "related to".** Run 0 tagged 8 of 9 facts with whatever inherited fact they touched: its wingspan fact "overrode" F1 and F5, and its talon fact F7. That would have hidden most of the body.
- **b's misses came from dropping the prompt detail.** b run 2 never mentioned the blue eyes at all, and a run 1 wrote "not the bright yellow typical of Snowy owl-folk" without the label. The prompt check of variant c fixed both.
- **c's two spurious labels in run 2:**
  - a plumage fact over F2, which is harmless: the own fact describes the same plumage in more detail;
  - a head-tilting habit over F8 (hollow bones, head turning), which is harmful: it would hide the hollow bones.

### 5. Quarter-orc character, "red hair"

The inherited list ran to 12–27 facts. Overrides in the mix lineage drop some of them; see "A wrinkle" below.

| | a | b | c | d |
|---|---|---|---|---|
| direct layer (the Quarter-orc's hair fact) marked | 1/3 | 2/3 | **3/3** | 3/3 |
| deep layers (Half-orc, Lowlander or Orc hair) marked | 0/3 | 0/3 | **2/3** (Orc) | 1/3 (Lowlander), Half-orc and Orc never |
| spurious | 6, 0, 0 | 0, 0, 2 | 0, 3, 2 | 1, 1, 0 |

- **Most of c's spurious labels replace the same trait.** An own skin, eye or tusk fact overrode the Quarter-orc's range for that trait. One was harmful: a personality fact overrode the Quarter-orc's instinct fact.
- **d's spurious label was Human's hair-and-eye fact,** which also drops Human's eye-colour range.
- **Deep facts are where overrides get missed.** With four inherited facts saying "dark hair", the model reliably marks the nearest one and often skips the species fact at the bottom of the list.

### Facts that restate inherited ones

No reply restated an inherited fact outright in variants b, c or d.
- **Characters give individual detail inside the inherited ranges,** such as 3 ft 8 in, a wingspan of 8.5 ft, grey barring on the white plumage, or tusk buds a quarter-inch long. That's the "unique to this character" the prompt asks for.
- **Races restated the owner's prompt, not the species,** for example "the largest of all owl-folk".
- **Mixes restate the parents by design:** the blended version of each trait.

## A wrinkle in mix lineage (for Task 2's resolver)

In the Quarter-orc (Lowlander × Half-orc), the Lowlander is both parent A and an ancestor of the Half-orc. The Half-orc's overrides of Lowlander's facts therefore also drop those facts in the Quarter-orc's lineage. In variant b's world, every Lowlander and Human fact was gone from the Quarter-orc character's list.

`heritage._inherited_with_layers` does the same: an override applies when the overrider's layer inherits from the target's layer, and the Half-orc inherits from the Lowlander. That's arguably right, since the Quarter-orc's own facts restate the blend. But it means a "three-quarters Lowlander" inherits no Lowlander facts at all. I'm flagging it for the owner; it doesn't block anything.

## Recommendations

1. **Species:** variant b (placeholder `0`s, no `since`). A Task 6 parser should treat a `0` or a missing number as unset.
2. **Races:**
   - Use variant d: the prompt check and customs line in the task section, and overrides as a top-level `"no_longer_true"`.
   - The parser attaches each label to the own fact sharing the most content words with the inherited fact, leaving out the lineage's names and stop words and preferring the same category.
   - Drop a race number that equals its species' resolved value: it would only pin the inherited value.
3. **Mixes:**
   - Use per-fact `"overrides"`, with variant b's rule and its mix sentence ("A blended trait overrides the parent facts it replaces, on either side").
   - Clamp, or at least flag in the preview, a mix lifespan or adult age outside its parents' range.
4. **Characters:** per-fact `"overrides"` with variant c's prompt check. It got the direct override every time, and the deep one in 2 of 3 runs.
5. **One parser for both shapes, for every kind.**
   - Read per-fact `"overrides"` and the top-level `"no_longer_true"` from any reply, mapping labels back to fact ids. Drop unknown labels, and labels pointing at facts the lineage already overrides.
   - A per-fact label keeps its own fact; a top-level label is attached by word overlap.
   - If the wrapper is broken, the per-fact labels survive with their fact objects.
6. **Overrides will be missed, mostly on deep layers.** So:
   - the preview should show the inherited facts beside the drafted ones with an Override toggle (Task 10/11);
   - Task 5's character sheet should tell the agents "where the character's own facts and inherited facts disagree, the character's own facts are right". That covers an unmarked conflict in play at no cost.
7. **Mixes need a name source.** The probe always gave the mix's name ("Half-orc"). When the owner drafts a mix from two parents without one, the template must ask the model to invent it. That case is untested; see the `has_name` branch below.

## Recommended prompt text

Jinja for Tasks 6 and 7, matching `world/create-thing.jinja2`'s conventions:
- `{{ set_prepared_response('{') }}` at the end;
- the calendar line as today;
- `inherited` as `[(label, source_name, category, text)]`, the Task 6 interface;
- a numbers line built in code like `lifespan 70 years, adult at 12, height 3-4 ft, wingspan 8.5-9 ft`.

The text below is what the probe sent, with only the world-specific values replaced by variables.

### (a) Species and race creation

One template, `world/create-thing.jinja2`, branched on `kind`. `species_name`, `species_numbers` and `inherited` are set for a race.

```jinja
<|SECTION:TASK|>
{% if kind == "species" -%}
You create a new species for a fantasy world from the owner's short prompt. Treat the prompt as intent, not a spec: invent plausible detail generously to fill it out, turning a rough idea into a fleshed-out one. Keep everything the owner wrote.

Keep the facts consistent with each other and with the owner's prompt: an invented fact must never contradict the prompt or another fact.

A species' facts describe the whole species (typical traits and ranges), not one person. Instincts are inborn tendencies; leave learned customs out, they belong to cultures.

Owner's prompt:
{{ prompt }}
{%- else -%}
You create a new race of the {{ species_name }} species for a fantasy world from the owner's short prompt. Treat the prompt as intent, not a spec: invent plausible detail generously to fill it out. Keep everything the owner wrote.

Every member of the race already has the {{ species_name }} facts below. Write only what sets this race apart from other {{ species_name }}: never restate a species fact. Keep the race consistent with its species: it has the same kind of body, varied.

Instincts are inborn tendencies; leave learned customs out (settlements, government, crafts), they belong to cultures.

Before writing, check every detail of the owner's prompt against the species facts. Each detail a species fact contradicts (another colour, another size, a missing trait) gets a fact of its own, and that species fact goes in "no_longer_true".

Owner's prompt:
{{ prompt }}

{{ species_name }} numbers: {{ species_numbers }}.
{{ species_name }} facts (inherited):
{% for label, source, category, text in inherited -%}
- {{ label }} ({{ source }}, {{ category }}): {{ text }}
{% endfor %}
{%- endif %}

The world's calendar: it is now {{ now_label }}, year {{ now_year }}{% if era %} of the {{ era }}{% endif %}. The months are {{ month_names | join(", ") }}.
<|CLOSE_SECTION|>
<|SECTION:FORMAT|>
Reply with only one JSON object, shaped exactly like this example:
{% if kind == "species" -%}
{"name": "...", "lifespan": 0, "adult_age": 0, "measures": [{"name": "height", "min": 0, "max": 0, "unit": "ft"}], "facts": [{"category": "origin", "text": "One claim, in a full sentence."}, {"category": "general", "text": "Another claim."}]}

- "name": the species' name.{% if has_name %} Use the name already decided.{% else %} Invent one if the prompt doesn't give it.{% endif %}
- "lifespan": how long they typically live, in years, as a number.
- "adult_age": the age in years at which they are grown, as a number.
- "measures": their typical body ranges, each {"name", "min", "max", "unit"} with min and max as numbers: always height, plus any other measure that matters for this body (wingspan, tail length, tusk length...).
- The 0s in the example are placeholders: give real numbers that fit this species and the owner's prompt.
- "facts": between {{ min_facts }} and {{ max_facts }} facts, one claim each. "category" is one of: {{ categories | join(", ") }}. physical: the body; instinct: inborn tendencies; variation: how members differ from each other; origin: where they come from.
- Leave "since" out: these facts describe the species for as long as it has existed, and are never dated.
{%- else -%}
{"name": "...", "measures": [{"name": "{{ example_measure }}", "min": 0, "max": 0, "unit": "ft"}], "facts": [{"category": "physical", "text": "One claim, in a full sentence."}, {"category": "variation", "text": "Another claim."}], "no_longer_true": []}

- "name": the race's name.{% if has_name %} Use the name already decided.{% else %} Use the prompt's name if it gives one.{% endif %}
- "lifespan", "adult_age" and "measures": give each only where this race differs from {{ species_name }} (a measure narrower or outside the species' range); leave out any that is the same, it is inherited. lifespan and adult_age are years, as numbers; each measure is {"name", "min", "max", "unit"}, using the species' measure names.
- The 0s in the example are placeholders: give real numbers that fit this race and the owner's prompt.
- "facts": between 4 and 8 facts, one claim each, only what is specific to this race. "category" is one of: {{ categories | join(", ") }}.
- "no_longer_true": after the facts, the labels of the species facts that are untrue for this race now that your facts hold, such as ["F4"]. An inherited fact your facts only add detail to stays true and isn't listed; an empty list is fine when nothing changes.
- Leave "since" out: these facts describe the race for as long as it has existed, and are never dated.
{%- endif %}

No commentary, no markdown fences, just the JSON object.
<|CLOSE_SECTION|>
{{ set_prepared_response('{') }}
```

- `example_measure` is one of the species' own measure names. The probe used "wingspan" for Owl-folk; a species with only a height uses "height".
- The probe asked for 8–12 species facts, the slice's `MIN_FACTS`/`MAX_FACTS`, and 4–8 race facts.

### (b) Mix drafting from two parents

New template `world/create-mix.jinja2`:
- `parents` is `[(side, label_line, numbers, rows)]`, two entries. `label_line` reads like "Lowlander (a race of Human)" or "Orc (a species)", and `rows` are that parent's `(label, source, category, text)`.
- Labels run on from parent A into parent B, and a fact already listed under A isn't repeated under B.
- `prompt` may be empty.

```jinja
<|SECTION:TASK|>
You draft a new mix for a fantasy world: {% if has_name %}the {{ name }}s, {% endif %}people of mixed parentage from the two parents below. Its facts describe the mix as a whole (typical traits and ranges), not one person. Every member already inherits the parents' facts, except the ones you mark as overridden: write what the blend itself looks like, and don't restate a parent fact that holds unchanged.

Blend the two parents into ONE consistent kind of body, the way real mixed parentage looks:
- Show clear traits of both sides, each softened or in between (e.g. shorter tusks, a skin tone between the two).
- For the numbers, pick values in between the two parents'.
- Never list two traits that contradict each other.
- When the blend replaces a parent's trait (shorter tusks than the orc parent, tusks where the other parent has none), mark that parent fact as overridden.

{% if prompt %}Owner's prompt:
{{ prompt }}

{% endif %}{% for side, label_line, numbers, rows in parents -%}
Parent {{ side }}: {{ label_line }}. Numbers: {{ numbers }}.
{% for label, source, category, text in rows -%}
- {{ label }} ({{ source }}, {{ category }}): {{ text }}
{% endfor %}
{% endfor -%}
The world's calendar: it is now {{ now_label }}, year {{ now_year }}{% if era %} of the {{ era }}{% endif %}. The months are {{ month_names | join(", ") }}.
<|CLOSE_SECTION|>
<|SECTION:FORMAT|>
Reply with only one JSON object, shaped exactly like this example:
{"name": "{% if has_name %}{{ name }}{% else %}...{% endif %}", "lifespan": 0, "adult_age": 0, "measures": [{"name": "height", "min": 0, "max": 0, "unit": "ft"}], "facts": [{"category": "physical", "text": "One claim, in a full sentence.", "overrides": []}, {"category": "instinct", "text": "Another claim."}]}

- "name": {% if has_name %}"{{ name }}".{% else %}the mix's name, such as "Half-orc". Invent one if the prompt doesn't give it.{% endif %}
- "lifespan": how long they typically live, in years, as a number.
- "adult_age": the age in years at which they are grown, as a number.
- "measures": their typical body ranges, each {"name", "min", "max", "unit"} with min and max as numbers: always height, plus any other measure that matters for this body (wingspan, tail length, tusk length...). Use the parents' measure names.
- The 0s in the example are placeholders: give real numbers that fit this mix and the owner's prompt.
- "facts": between 5 and 8 facts, one claim each. "category" is one of: {{ categories | join(", ") }}.
- "overrides": the labels of the inherited facts this fact makes untrue for this mix, such as ["F4"]. Use it only for a real contradiction: if an inherited fact says "grey fur" and this mix has black fur, the black-fur fact overrides it. A fact that adds detail to an inherited fact, builds on it or simply fits with it overrides nothing: "scarred paws" fits "padded paws", so no label. A blended trait overrides the parent facts it replaces, on either side; a fact that fits both parents has an empty list.
- Leave "since" out: these facts describe the mix for as long as it has existed, and are never dated.

No commentary, no markdown fences, just the JSON object.
<|CLOSE_SECTION|>
{{ set_prepared_response('{') }}
```

- The probe always gave the name: the `has_name` branch above. The no-name wording ("such as "Half-orc". Invent one") is untested.
- The tusk examples in the blend rule come from the blending probe. They didn't visibly bias the human/orc mixes, but owl-folk mixes haven't been tried.

### (c) Character creation with an inherited block

This is `world/create-thing.jinja2`'s character branch when the character has a heritage (`heritage_label` such as "Snowy (a race of Owl-folk)", plus `heritage_numbers` and `inherited`). With no heritage, today's template stands unchanged.

```jinja
<|SECTION:TASK|>
You create a new character for a fantasy world from the owner's short prompt. Treat the prompt as intent, not a spec: invent plausible detail generously to fill it out, turning a rough idea into a fleshed-out one. Keep everything the owner wrote.

Keep the facts consistent with each other and with the owner's prompt: an invented fact must never contradict the prompt or another fact.

The character is {{ heritage_label }}, and already has every inherited fact below. Write only what is unique to this character: never restate an inherited fact. Where the owner's prompt differs from an inherited fact, the prompt wins: write the character's own fact and mark the inherited one it overrides.

Before writing, check every detail of the owner's prompt against the inherited facts. Each detail an inherited fact contradicts (another eye or hair colour, another size, a missing trait) gets a fact of its own, with that inherited fact's label in "overrides". Check the whole list: the contradicted fact may come from any layer of the heritage, the species' facts at the bottom included.

Owner's prompt:
{{ prompt }}
{% if known_fields %}
Already decided (use these as they are):
{% for label, value in known_fields -%}
- {{ label }}: {{ value }}
{% endfor %}{% endif %}
Heritage numbers: {{ heritage_numbers }}.
Inherited facts:
{% for label, source, category, text in inherited -%}
- {{ label }} ({{ source }}, {{ category }}): {{ text }}
{% endfor %}
The world's calendar: it is now {{ now_label }}, year {{ now_year }}{% if era %} of the {{ era }}{% endif %}. The months are {{ month_names | join(", ") }}.
<|CLOSE_SECTION|>
<|SECTION:FORMAT|>
Reply with only one JSON object, shaped exactly like this example:
{"name": "...", "age": 34, "facts": [{"category": "{{ categories[0] }}", "text": "One claim, in a full sentence.", "overrides": []}, {"category": "background", "text": "Another claim.", "since": "YEAR"}]}

- "name": the character's name.{% if has_name %} Use the name already decided.{% else %} Invent one if the prompt doesn't give it.{% endif %}
- "age": how old the character is now, in years, as a number.
- "facts": between {{ min_facts }} and {{ max_facts }} facts, one claim each. "category" is one of: {{ categories | join(", ") }}.
- "overrides": the labels of the inherited facts this fact makes untrue for this character, such as ["F4"]. Use it only for a real contradiction: if an inherited fact says "grey fur" and this character has black fur, the black-fur fact overrides it. A fact that adds detail to an inherited fact, builds on it or simply fits with it overrides nothing: "scarred paws" fits "padded paws", so no label. Most facts have an empty list; a reply usually overrides between none and two inherited facts.
- "since" is optional. Give it only when a fact started at a known time, and only as a year of this calendar, as a bare number no later than {{ now_year }}; "YEAR" in the example stands for that number. Leave it out otherwise: never a phrase like "childhood" or "ten years ago".
- Leave "since" out for an inherent trait that has always been true -- a species, the appearance someone is born with, a lifelong temperament -- rather than dating it to the present year.

No commentary, no markdown fences, just the JSON object.
<|CLOSE_SECTION|>
{{ set_prepared_response('{') }}
```

- The `known_fields` block is today's template's, kept in place. The probe sent no known fields.
- **For Task 7 (scene setup):** the probe didn't test the setup prompt. Its heritage handling is the `"heritage": "<name>"` match in code, not override labels, so none of the wording above is needed there. The finding that carries over: tell the agents that a character's own facts win over inherited ones (recommendation 6).
