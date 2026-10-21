# Probe: names, mention context, duplicates and everyday names

Date: 2026-10-21. Model: koboldcpp, Skyfall-31B-v4.2-i1-Q4_K_M, through Talemate's own KoboldCpp client (the `--ai` app's config, default agent settings). Calls ran one at a time: creates took 16–36 s each, narrator turns 10–15 s. Connections, Task 3: settles the reply shape for names, the mention-context rule and cap, and the everyday-name wording for Tasks 4, 5 and 7.

- Script: `scripts/dev/probe_connections.py` (`--only 1 2 3 4 4b 5`, `--score`, `--dry`).
- Raw output: `raw/2026-10-21-connections.json`, with all 48 calls (prompt and reply), each create's parsed facts, `aka`, `names` and `unknown_proper_phrases`, the hand labels' scores (`probe1_scores`, `probe1_totals`) and the World blocks.
- Probes 4b and 5 are follow-ups added after the first pass. In probe 4 the narrator almost never named the country, so 4b asks for its name outright. Probe 5 tests the everyday name in a create prompt, which the first pass didn't cover.

## Setup

**The world** (present 1020):
- **Owl-folk**, a species with 12 facts:
  - origin: "In 994, every person in the Tsardom of Moscavia awoke as owl-folk overnight, in what Moscavians call the Night of Feathers." and "…children have hatched from eggs ever since";
  - physical (4): wings in place of arms, talons used as hands, yellow eyes, beak and silent feathers;
  - instinct (3): crepuscular, turns the whole head, goes still when startled;
  - variation (1): plumage;
  - general (2): 4–5 ft with hollow bones; the oldest remember their human lives and mourn their hands.
- **Snowy**, a race of Owl-folk, and **Humans**.

**Creates** run through the real `create.preview_thing`, with a copy of `world/create-thing.jinja2` placed in front by `PrependTemplateDirectories`. Section prose is stubbed out, so each create is one call. The copy adds:
- `"aka"` (after the name) and `"names"` (after the facts) to every branch's example object;
- two rule lines before "No commentary…" (the wording is in "Recommended prompt text" (a));
- the probe's context block, if any, just before the calendar line.

The reply that `parse_create_reply` reads is the one recorded.

## Probe 1: names and kinds

Three prompts, 3 runs each:
- a country: "a cold southern kingdom of salt marshes and lighthouses, ruled by a council of bishops";
- a character, a Human: "a retired river pilot who lost her husband in a flood and now raises her grandson";
- a species: "otter-folk who live in floating villages on great inland lakes".

Each run's proper names were labelled by hand after the run (`LABELS` in the script): 39 distinct names over the 9 runs, the thing's own name excluded. Labels allow other spellings ("Tobias" / "Tobias Solvik"). Two phrases, "the Church" and "Saint Maren" (inside "Drowning of Saint Maren"), are neutral and count neither way.

Three ways of finding names were scored:
- **model:** the reply's `names`;
- **code:** `unknown_proper_phrases` over the facts, minus the thing's own name and its words;
- **both:** the union of the two.

| | Found | Recall | Wrong | Precision |
|---|---|---|---|---|
| **model** `names` | 37 of 39 | **0.95** | 2 | **0.95** |
| **code** `unknown_proper_phrases` | 37 of 39 | 0.95 | 7 | 0.84 |
| **both** (union) | 39 of 39 | 1.00 | 8 | 0.83 |

- **The model's misses:** River Sere and the Saltmarch clans (country 1). The code caught both.
- **The model's wrong entries:** "High Bishop", a title, listed as lore, and "halivas", a lowercase word for a kind of village, listed as a place.
- **The code's misses:** "Cairn's Bend", split at the possessive into "Cairn" and "Bend", and "Alderwick", a river that shares the character's surname, so the self filter drops it.
- **The code's wrong phrases:**
  - "Bishops" and "Council" (split from "Bishops' Council");
  - "Cairn" and "Bend";
  - "High Bishop";
  - "Some Lakewood" and "Some Lakewardens": "Some" isn't one of the sentence openers.
- **Kinds:** 37 of 37 right for the names the model listed that are in the labels. Places, characters, events and lore (synods, churches) were all correct.
- **Generic nouns wrongly listed:** 2 of 41 model entries (High Bishop, halivas). "His mother"-style descriptions never appeared. The model gave first names ("Tobias", "Edric") a full name ("Tobias Solvik") or added a title ("Tsar Alexei III the Feathery" for "Alexei III the Feathery"). Of the 169 model names in probes 1–3, 10 don't appear verbatim in the facts: 7 of those are such fuller names, and 3 aren't in the facts at all (see the merge rule).

**The same pattern in probes 2, 3 and 5** (not hand-scored):
- The model's lists stayed clean. The rare wrong entries were lowercase coined words ("grenniki", "gnezdovias", "feather-envy"), a title ("Tsar", once with the invalid kind `"title"`), the thing's own name (twice in probe 5), and one context name its facts never used ("Tsardom of Moscavia" in probe 3, "matched" run 1).
- Documents and scripts came back as `item` ("Code of Talons", "Zakonnik", "Kladovik"); `lore` fits them better.
- The code rule added the same kinds of noise:
  - titles: "Tsar", "Tsars", "Kremlin", "Great Hall", "Elders";
  - demonyms: "Moscavian", "Slavic", "Scandinavian";
  - "AM" and "PM";
  - "Cathedral of St" (the run cut at the full stop);
  - sentence-initial "On the Night of Feathers".

**One parse failure (1 of 30 creates):** probe 5's "everyday" run 2 closed its `names` list but never closed the wrapper object. `json_objects` then fell back to the inner objects, and `_raw_facts` read the `aka` entry `{"name": "Sunny City", "tag": "common", …}` as a fact with the text "common". The `names` entries were cut off only by the 12-fact cap. Task 5's parser must:
- not read `aka` and `names` entries as facts (skip objects with `tag`, `everyday` or `kind` keys);
- recover both lists from a broken wrapper by decoding `"aka": [...]` and `"names": [...]` on their own.

## Probe 2: context from mentions

The Tsardom expanded from its stub (name decided as "Tsardom of Moscavia"), with the suggested prompt "The Tsardom of Moscavia: the country where, in 994, everyone turned into owl-folk overnight." Each variant ran 3 times:
- **(a)** "Mentioned elsewhere" only: the origin fact.
- **(b)** plus "About those": the Owl-folk's key facts in the order physical, instinct, origin, capped at 8, with the mentioning fact left out. That's 4 physical, 3 instinct and the eggs fact.
- **(c)** plus all 11 of the Owl-folk's other facts.

**Measured by the owner's standard** (is the place written for its owl-folk inhabitants?), all 9 runs pass at a basic level. The mention itself says the whole population turned into owl-folk, so every Tsardom is a country of owl-folk. What changes is how much of the species shapes the country:

| | Distinct owl-folk traits used (of 7 themes, keyword scan, per run) | What the facts do with them |
|---|---|---|
| (a) mention only | 1, 4, 4 | Owl texture is generic: "luminous eyes", "hooting resonance", "nighttime gatherings", "flight competitions". It contradicts the species once: wings "folded against their backs" (run 2). |
| (b) key facts, cap 8 | 5, 4, 6 | Traits become institutions: "talon-grip writing is the standard for all official documents", courts held at dusk, "midday courts and councils are forbidden, as drowsiness renders decisions unreliable", round doorways for wingspans, eggs and communal nesting houses, temples "designed so that owl-folk can turn their heads freely". |
| (c) all facts | 7, 5, 6 | As (b), plus the general facts: hollow bones ("light enough that hollow-boned families can roost…"), the oldest mourning their hands ("the Starši, or 'the Elders'"), the old generation teaching farming. It restated the species' body in 2 of 3 runs; (a) did in all 3, (b) in none. |

- **(b) is the step that matters:** it's where the country starts being built around the body and instincts, which is the owner's measure. (c) adds a little texture from the `general` facts at the cost of 3 more facts in the prompt and more restating than (b).
- **Not caused by context:** two (b)/(c) runs invented a sub-group, "Frostowls" (b, run 2), a race-like population. Real-world names leaked in every variant (Volga, Velikiy Novgorod, Perun, the Rurikids, a "Great Mosque"), because a Russian-flavoured name invites them. They are named things, so they would become stubs, which the owner can ignore.

**The Tsardom's own `aka`:** "Moscavia", tagged common and everyday, in 9 of 9 runs. One run added "The Owl Kingdom" as another common name.

## Probe 3: duplicates

"A river town where Moscavian Owls trade with barge crews", 3 runs without context and 3 with the Owl-folk matched into a "Named in this prompt" block ("Moscavian Owls" means Owl-folk, all 12 facts).

| | Facts treat Moscavian Owls as a new kind of being | Reply lists them in `names` as |
|---|---|---|
| **no context** | **3 of 3** a separate entity, 1 explicitly a new species ("a nocturnal species of anthropomorphic owls", "amber eyes"); another calls them "the birds" | "Moscavian Owls" lore, "Moscavian Owl traders" lore, "Moscavian Owls" species |
| **matched** | **0 of 3**: all say "Moscavian Owl-folk" and use the species' traits (trading at dawn and dusk, "going utterly still and silent when startled", "wide yellow eyes", taloned feet) | "Moscavian Owl-folk" species, species, race |

- **Matched context stops the duplicate in the facts.** Without context the model always invents something.
- **The `names` list still names "Moscavian Owl-folk"** as a species or race in all 3 matched runs. The merge rule has to link it to Owl-folk rather than stub it. `find_names` matches "Owl-folk" inside it, which is enough.
- **The matched runs also listed "Tsardom of Moscavia"**, from the Owl-folk's origin fact in the context, as a *culture* in 2 runs. One of those runs never mentioned it in its facts. A model name has to appear in the facts to count, and the kind of a name already in the world comes from the world, not the reply.

## Probe 4: everyday names

**The suggested `aka`** (all 30 creates, 35 entries):
- Every create gave exactly one `everyday: true` entry, and it was always tagged `common`: "Moscavia" 9 of 9, "Maren", "Maggie" for Margaret, "Solotsk", "Vostok", "Solenka", "Rostov".
- **27 of 35 are sensible and correctly tagged.** The 8 that aren't:
  - invented nicknames picked as the everyday name: "Bargehaven" for Bargash, "The Bargeway" for Velkovo, "Sunny" for Solnechnyy;
  - names that don't fit: "River Otterfolk" and "Riverfolk" for lake otters, "Rostov Velikiy" (a real place);
  - wrong tags: "Otterkind" tagged proper, "Velkovo-on-the-Sernaya" tagged common;
  - "The Salted Throne", a metonym tagged proper.
- **The main name was the most proper one in 29 of 30.** Velkovo's longer "Velkovo-on-the-Sernaya" came back as a common other name instead.

So the owner gets usually-right suggestions that need a glance. A wrong `everyday` pick is the one that matters (3 of 30), because it changes what narration says.

**Narration.** A scene in Barrowford, "a river town on the Vesna in the south of the Tsardom of Moscavia", with the Tsardom pulled in as lore (4 facts, which use the full name). The cast was Ilse (human, the player) and Brannoc (owl-folk). There were three World blocks:
- **plain:** the heading "Tsardom of Moscavia";
- **everyday:** the heading "Tsardom of Moscavia (usually called Moscavia)";
- **everyday+line:** that heading plus a line at the top of the block (the wording is in "Recommended prompt text" (d)).

Each block got 3 `progress_story` turns, all from the same history.

| Directions | Block | Full name "Tsardom of Moscavia" | "Moscavia" alone | Other |
|---|---|---|---|---|
| open (news, the Night of Feathers, the view north) | plain | 0 | 0 | "the Tsardom" 1 |
| | everyday | 0 | 1 | |
| | everyday+line | 0 | 0 | |
| ask for the country's name (welcome, a herald, a letter home) | plain | **3** | 0 | |
| | everyday | 2 | 1 | "Moscavian waters" 1 |
| | everyday+line | **1** (the herald's proclamation) | **2** | |

- **Unprompted, the narrator rarely names the country at all.** It says "the Tsar", "Kremova" and "the whole country".
- **When it does name the country:**
  - with the plain heading, it uses the full name every time, even in Brannoc's casual welcome and Ilse's letter;
  - the parenthetical alone moves one of three to "Moscavia";
  - the parenthetical plus the line leaves the full name only in the herald's formal proclamation, which is the use the line allows.

**In create prompts** (probe 5): "an amber market town on a lake in Moscavia", with the Tsardom matched to "Moscavia" and shown as "Tsardom of Moscavia (place, usually called Moscavia)", 3 runs each:

| | Full name in facts | "Moscavia" alone |
|---|---|---|
| parenthetical only | 1 | 3 |
| parenthetical + a line asking for everyday names in facts | 2 | 3 |

The line made no difference. Facts already prefer "Moscavia", and use the full name for jurisdiction ("falls under the jurisdiction of the Tsardom of Moscavia"). Either way the name gets linked.

**An aside for the owner, outside this probe's scope:** the narrator gave Brannoc wings "folded against his back" in 4 of 18 turns, and one owl-folk "slammed a fist". This is the heritage drift from plan B's play probe; the cast lines hold up the rest of the time.

## Recommendations

1. **Names come from the reply, and the code rule only suggests.**
   - The model's `names` were the more precise of the two at the same recall (0.95 / 0.95).
   - The code rule's extra recall (River Sere, Saltmarch) came with 7 noise phrases in 9 runs.
   - So accepted names become stubs automatically. Capitalised phrases the code finds that the model didn't list are shown only as "make a stub" suggestions, the same as in facts written by hand.
2. **Merge rule** (Task 4), for each accepted entry's facts:
   1. Take each `names` item. Keep it only if its name, or the name without a leading article, appears in the facts (case-insensitively) and the written text starts with a capital letter. Otherwise:
      - if the item's name contains one of `unknown_proper_phrases`, or a capitalised run of the facts' text ("Tobias" in "Tobias Solvik", "Alexei III the Feathery" in "Tsar Alexei III the Feathery"), link that written text to a stub named with the model's full name;
      - otherwise drop it. That covers names echoed from context and lowercase coined words ("halivas", "grenniki").
   2. Drop an item that is the entry's own name or one of its `aka`, or whose kind isn't one of the listed kinds (`"title"`).
   3. Run `find_names` first. An item that a match covers, or that contains a match ("Moscavian Owl-folk" contains Owl-folk), links to that existing entry or stub and isn't stubbed again. The owner's picks and "treat as new" win.
   4. The kind comes from the item. For a name already in the world, the world's kind wins over the item's (the "culture" Tsardom). With no usable kind, guess `lore`.
   5. Read an item's `aka` as strings or `{"name", …}` objects. A tag other than proper or common (seen: "former name") becomes `proper`.
   6. `unknown_proper_phrases` left uncovered by kept items and the entry's own names are suggestions only.
   7. **Small code-rule fixes in `names.py`**, for less noise in the suggestions:
      - treat "On", "In", "At", "By", "From", "Some", "Every", "Each", "Most", "Many" and "All" as sentence openers;
      - let a run continue across an inner possessive into another capitalised word ("Cairn's Bend", "Bishops' Council");
      - never start a run with "AM" or "PM";
      - keep "St." inside a run ("Cathedral of St. Sophia").
3. **Mention context: "Mentioned elsewhere" plus "About those", with key facts capped at 8 per mentioning entry** (variant b).
   - **Key facts of a species, race or mix:** its physical, instinct and origin facts, in that order, then variation and general to fill up to 8. The mentioning fact is already shown above, so it's left out.
   - **Not probed, my call:** for a character, place or lore entry that mentions the stub, its facts in its kind's category order, up to 8. "About those" covers at most 3 mentioning entries (most mentions first), and "Mentioned elsewhere" at most 12 facts.
4. **"Named in this prompt" stops duplicates** when the match is in the context (3/3 duplicates down to 0/3). Show every fact of each matched entry, as scene setup does.
5. **Everyday names:**
   - In create prompts, show every named entry as "Name (kind, usually called X)", with no extra line.
   - In the scene World block, give place and lore headings "Name (usually called X)" and add the everyday-name line at the top.
6. **The parser** (Task 5) must keep `aka` and `names` entries out of the facts, and recover both lists from a reply whose wrapper isn't closed.
7. **The owner reviews `aka` suggestions.** In 3 of 30 creates the everyday pick was an invented nickname. The preview should show the suggested other names, with the everyday one marked, so a bad pick is easy to fix before accepting.

## Recommended prompt text

**(a) The create reply's `aka` and `names`** (`world/create-thing.jinja2`, every branch; also the mix template).

In each branch's example object, insert this right before `"facts": [`:

```
"aka": [{"name": "...", "tag": "common", "everyday": true}], 
```

and at the end of the object, before the closing `}`, add:

```
, "names": [{"name": "...", "kind": "place", "aka": []}]
```

The rules go after the branch's own rules, just before "No commentary, no markdown fences…". This is the probed wording, plus the two clauses in square brackets (the brackets aren't part of the text). They target the probe's two wrong-kind patterns and weren't run; Task 4's acceptance run checks them.

```
- "aka": other names for this {{ kind }} itself, if it has any, each {"name", "tag", "everyday"}. "tag" is "proper" for another formal name, or "common" for what people in the world actually call it day to day (a short form, a nickname). Set "everyday" true on the one common name people use most, false on the rest. "name" stays the most formal name. An empty list is fine.
- "names": after the facts, every proper name your facts use, other than this {{ kind }}'s own: people, places, peoples and species, named events, named groups and named objects, new or already in the world. Each is {"name", "kind", "aka"}: "name" in full, as your facts write it; "kind" one of character, place, species, race, culture, event, item, lore (a group, order or faction is lore[; so is a law, code, script or language]); "aka" any other names your facts use for the same thing. Proper names only: never a description such as "the postmaster", "a war" or "his mother"[, nor a title on its own such as "the Tsar" or "the High Bishop"] -- but "Yelena" in "his mother Yelena" is a name. An empty list is fine.
```

**(b) The mention context**, in the TASK section after the prompt and "Already decided", before the calendar line. Each source name carries its everyday name as in (d), and the inner bracket lists the source's kind and the mentioning fact's category.

```
Mentioned elsewhere in the world (keep these true):
{% for m in mentions -%}
- {{ m.source }} ({{ m.source_kind }}, {{ m.category }}): {{ m.text }}
{% endfor %}
{%- if about %}
About those (they already exist in the world; let the {{ kind }} reflect them{% if kind == "place" %} -- a place is shaped by the people who live there{% endif %}):
{% for entry in about -%}
{{ entry.name }} ({{ entry.kind }}):
{% for text in entry.facts -%}
- {{ text }}
{% endfor %}
{%- endfor %}
{%- endif %}
```

**The caps:**
- `about` holds up to 3 mentioning entries, most mentions first.
- Each entry gets up to **8** key facts. For a species, race or mix those are physical, then instinct, then origin, then variation and general, without the mentioning fact; for other kinds, the kind's category order.
- `mentions` holds up to 12 facts.

The probed text was `About those (they already exist in the world; let the place reflect them -- a place is shaped by the people who live there):`.

**(c) "Named in this prompt"**, in the same place, after the mention context when both are present:

```
Named in this prompt (these already exist in the world: use them as they are, and never invent a new one in their place):
{% for entry in named -%}
"{{ entry.written }}" means {{ entry.name }} ({{ entry.kind }}{% if entry.everyday %}, usually called {{ entry.everyday }}{% endif %}):
{% for text in entry.facts -%}
- {{ text }}
{% endfor %}
{%- endfor %}
```

Probed as `"Moscavian Owls" means Owl-folk (species):`, followed by all 12 facts, and as `"Moscavia" means Tsardom of Moscavia (place, usually called Moscavia):`.

**(d) Everyday names.**
- **Create prompts:** wherever an entry with an everyday name is shown in (b) or (c), the parenthetical carries it, as in `Tsardom of Moscavia (place, usually called Moscavia)` or `Owl-folk (species, usually called …)`. No rule line: probe 5 found it changed nothing.
- **The scene World block** (`world/scene-context.jinja2`): the place line and each lore heading carry `{{ name }} (usually called {{ everyday }})` when the entry has an everyday name. When any entry in the block has one, this line goes first, right after `[world]`:

```
In narration and dialogue, call things by their everyday names: where a name is followed by "usually called ...", use that name, and keep the full name for formal moments.
```
