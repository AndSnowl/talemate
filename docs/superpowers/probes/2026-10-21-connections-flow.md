# Probe: the owner's connections session on Skyfall

Date: 2026-10-21. Model: koboldcpp, Skyfall-31B-v4.2-i1-Q4_K_M, through Talemate's own KoboldCpp client (the `--ai` app's config, default agent settings). Calls ran one at a time. Connections, Task 10: the owner's measure from the spec ("How the owner will judge it"), run through the same code path the world screens use.

- Script: `scripts/dev/probe_connections_flow.py`. It drives the real `worlds` router (`WorldsPlugin`: `preview_thing`, `accept_preview`, `list_stubs`, `stub_suggestion`, `match_names`, `get_thing`, `list_things`) with the real client on the creator agent. Nothing is stubbed out: each create is one create call plus its section prose.
- Raw output: `raw/2026-10-21-connections-flow.json`. It holds:
  - `runs`: two runs of the script, each with every call (prompt, reply, seconds), each step's preview (facts, aka, new names, mention context), the accepted thing with its links, and the stubs after each step;
  - `judged`: the hand judging below, with fact indices.
- Run 1 was made before the one fix in this task, and run 2 after it (see "Fix made").

## The session

The world is fresh, with the present in 1000.

1. **Owl-folk**, a species. The prompt is the owner's plan B wording: "Owl-folk: owl people. Everyone in the Tsardom of Moscavia became this race suddenly one day 6 years ago."
2. **The Tsardom**, expanded from its stub. The prompt is the stub's suggested prompt (`stub_suggestion`), and it's accepted into the stub.
3. **Two stubs the Tsardom's facts name**, places first, each expanded the same way.
4. **"a river town where Moscavian Owls trade with barge crews"**. `match_names` runs first, then the owner's pick of the species is passed as `"Moscavian Owls"`.

Timing:
- each create call took 25–41 s;
- each prose call took 5–6 s;
- `list_stubs`, `match_names`, `get_thing` and linking made no model call.

## What happened

| | Run 1 | Run 2 |
|---|---|---|
| Species name | "Owl-folk of Moscavia" (the model's choice) | "Owl-folk" |
| Species' other names | Owls (common, everyday), Sovi (proper) | Moscavian Owl-folk (proper), sova (common, everyday) |
| Tsardom stub from the origin fact | yes | yes |
| Tsardom's other names | Moscavia (everyday) | Moscavia (everyday) |
| Stubs followed | Velikiy Novgorod (place), Tsar Alexei II (character): the Tsardom named only one place | Moskov (place), Northern Sea (place) |
| "Moscavian Owls" in `match_names` | "Owls" alone matched the species through its everyday name; "Moscavian" was left as an unknown word | not matched (the other name is "Moscavian Owl-folk"); the whole phrase was an unknown phrase |
| Town | Solnitsa | Velikostok |
| Stubs made in all | 25, of which 3 were filled by the session | 13, of which 3 were filled |

### Does the country reflect the owl-folk?

Each fact was judged by hand the way Task 3's probe 2 was:
- **built around:** something about the place depends on an owl-folk body or instinct;
- **specific:** built on a trait only this run's Owl-folk facts give;
- **restates:** a fact that mostly re-describes the species.

| Entry | Facts | Built around | Specific | Restates |
|---|---|---|---|---|
| Run 1 Tsardom | 12 | 4 (rebuilt for taloned feet and wings, an edict on flight corridors and night commerce, farming re-shaped for bodies without human hands, life at night in tower nests) | 1 | 2 |
| Run 2 Tsardom | 12 | 4 (human-built things unfit for taloned feet, the capital's towers made roosts, trade at twilight, roost-halls and treehouses) | 1 | 3 |
| Run 1 Velikiy Novgorod | 11 | **8** (dawn curfew of the streets, night court, building codes, steep landing roofs, flight galleries, a night market, streets for talons, roosting lofts in churches) | 1 | 0 |
| Run 1 Tsar Alexei II | 11 | 4 (silver-wired boots for taloned feet, wingspan, grieving lost touch, night-long sessions) | 1 | 0 |
| Run 2 Moskov | 12 | 6 | 1 (gliding between settlements) | 0 |
| Run 2 Northern Sea | 11 | 1 (ice fishing on talons) | 1 | 0 |
| Run 1 Solnitsa (the town) | 12 | 4 | 1 | 0 |
| Run 2 Velikostok (the town) | 12 | 6 | **4** (gravel squares for talons, marsh plumage, gliding, watchmen using the "listening silence") | 0 |

- **Both Tsardoms are built on the origin.** The 994 change runs through their laws, buildings, trade and faith. By count, though, they sit at the low end of Task 3's (b) runs: 4 built-around facts each, against 4–6 there.
- **"Specific" is low because the species was generic.** This time the model wrote the species with mostly generic owl traits (nocturnal, night vision, wings, plumage colours), whereas Task 3's probe used a hand-made species with particular ones (talons used as hands, crepuscular, head-turning). A country can only build on what the species gives it.
- **The places found by following stubs were the strongest result.** Velikiy Novgorod (8 of 11) and Moskov (6 of 12) are written for their owl-folk people throughout. They got the Tsardom's facts as mention context, so the owl-folk reached them second-hand.
- **Run 1's Tsardom contradicted the species.** The species' second origin fact said Moscavia was "ruled by Grand Prince Vladimir II from his capital in Moscow". The Tsardom put its capital in Velikiy Novgorod and named other rulers. That origin fact never reached the Tsardom's prompt: the "About those" cap of 8 key facts filled up with 5 physical and 3 instinct facts first. This is fixed now (see "Fix made").

### Stubs, false stubs and duplicates

**Run 1: 25 stubs made.** Most are proper names:
- Tsardom of Moscavia, Velikiy Novgorod, Tsar Alexei II, Grand Prince Dmitri I, Grand Prince Vladimir II;
- Edict of Feathered Citizenship, Church of the Holy Radiance, God of Light;
- Torzhok, Volkhov River, Lake Ilmen, Pyotr Volk, Solnitsa Accord, Volga Barge Captains' Association;
- the real-world places Moscow, Lithuania, Poland, Volga and Kazan. Task 3 saw these leak in too; they are named things, so they become stubs the owner can ignore.

The problems in run 1:
- **False stubs:**
  - 1 clear: "Bulgarian successor states", a description;
  - 2 borderline: "Kremlin tower" ("the Kremlin" would be the name) and "Moscavian Owl merchants' guild" (a lowercase description).
- **Duplicates:**
  - **"Owl-folk", a species stub, beside the species "Owl-folk of Moscavia".** The Tsardom's reply listed "Owl-folk". Containment reuse only covers a new name that *contains* an existing heritage name ("Moscavian Owl-folk" → Owl-folk), not one that is *part of* it. Now one Tsardom fact links "owl-folk of Moscavia" to the species, and another links "Owl-folk" to the duplicate stub.
  - "the Transformation" (from the species) and "the Great Change" (from Novgorod) name one event. Code can't tell these are the same; the owner can re-point the links.
- **False links:** "Grand", in "Court of the Grand Owl" and in "the first Grand Prince", linked to the stub "Grand Prince Dmitri I". It was matched as that character's first name.
- **Not seen:** sentence openers and titles as stubs. "Tsar" was never stubbed.

**Run 2: 13 stubs made.**
- Proper names: Tsardom of Moscavia, Moskov, Northern Sea, the Transformation (one stub, with 10 mentions across four entries), the Kremlin, the Moscow River, Volga, Oka River, Volga Barge Festival.
- **False stubs:**
  - 2 clear:
    - **"Tsardom"** (lore) has 0 mentions: an orphan. The reply listed it. The merge rule found "Tsardom" written with a capital, but only inside the entry's own name "Tsardom of Moscavia". Linking then gave that text to the entry itself, so the stub links nowhere.
    - **"Moscavian"** (culture), a demonym adjective ("the Moscavian populace", "Moscavian lowlands").
  - 2 borderline: "Aurelian" (culture, "distant Aurelian merchants") and "Hanseatic coast".
- No duplicates and no false links.

**"Moscavian Owls" never became a duplicate** in either run. With the owner's pick, the prompt's "Named in this prompt" block showed the species ("\"Moscavian Owls\" means Owl-folk (species, usually called sova)"), and the result was:
- in both towns, the facts treat Moscavian Owls as the world's owl-folk;
- run 2's town uses that species' own traits (the "listening silence", gliding, marsh plumage);
- the reply's names never stubbed "Moscavian Owls".

The automatic match only found it when the species' everyday name ("Owls") sat inside the phrase. In the create box, the owner's pick then covers "Owls" alone.

### Everyday names suggested

| Run 1 | Run 2 |
|---|---|
| Owls (species): fine | sova (species): an invented common noun. The Tsardom then called its people "the sova" throughout, so the everyday name carried into later generations. |
| Moscavia: right | Moscavia: right |
| Novgorod (Velikiy Novgorod): right | Moscow (Moskov): a real-world name; plausible |
| Alexei (Tsar Alexei II): fine | Morskoye More (Northern Sea): an invented translation, odd as an everyday name |
| Sol (Solnitsa): an invented nickname, taken from the facts' own etymology | The Great Port (Velikostok): an invented nickname |

That's 3 questionable everyday picks out of 10. They are the kind Task 3 saw (invented nicknames), and the preview shows them for review.

## Fix made

**Heritage origin facts outlast the key-fact cap** (`worldplay/mentions._key_facts`):
- A species', race's or mix's origin facts are now always in the "About those" block, after the first 8 key facts.
- Origin facts are history, often of the very place being expanded. Run 1 lost the "capital in Moscow" fact to the cap, and the country contradicted it.
- The cap still applies to everything else.
- Test: `tests/worldplay/test_mentions.py::test_heritage_origin_facts_outlast_the_cap`.
- Run 2 can't show the effect: its species had only 2 origin facts, so the cap never cut one. The cost is at most a few more facts in the prompt.

## Recommendations (not made: they are name-matching rules, not prompt assembly)

1. **Reuse a heritage name the listed name is part of.** A listed species, race or mix name that is a whole-word part of an existing heritage entry's name ("Owl-folk" in "Owl-folk of Moscavia") should be that entry, not a new stub. This is the reverse of the containment reuse in `links._reuse` and `create._known_in_view` (ruling P6). It is the one duplicate code could have caught.
2. **Don't make a stub nothing links to.** Drop a listed name whose only capitalised occurrences are inside the entry's own names, or inside other names that get linked ("Tsardom" inside "Tsardom of Moscavia"). Or skip, at accept, any stub `link_text` gives no span.
3. **A character's "first name" is never a title word** (Grand, Prince, Tsar, King, Queen, Lord, Lady, Sir, Saint, Duke and so on), in `world/names.find_names`' first-name rule. "Grand" linked to "Grand Prince Dmitri I" twice. While there, the rule could also require the first name to be unambiguous: both "Grand Prince …" stubs start with "Grand".
4. **Store a stub's name without a lowercase leading article.** Make "the Transformation", "the Moscow River" and "the Kremlin" into "Transformation", "Moscow River" and "Kremlin", and keep "the …" as a written form. The link keeps its words either way. A capitalised "The" ("The Night of Feathers") stays.
5. **Demonym adjectives as culture names** ("Moscavian", "Aurelian"): the names rule in `create-thing.jinja2` could add "nor a people's adjective on its own, such as 'Moscavian merchants'". This wording is unprobed; check it in the next acceptance run.

## The owner's measure

- **The country, created from its stub, reflects the owl-folk's origin and nature.** Yes on origin, in both runs. On nature it's moderate (4 of 12 facts each), limited by a generic species. Run 1's contradiction of the species' history is fixed by the origin-facts change.
- **Invented names show up as stubs, and following them is natural.** Yes. The followed places were the best-integrated entries. False stubs were 1–2 clear ones per run, plus a few borderline. There was one code-catchable duplicate (recommendation 1) and one orphan (recommendation 2).
- **Naming an existing entry links to it rather than inventing a duplicate.** Yes, for "Moscavian Owls" with the owner's pick. The automatic match is partial.
- **No slower turns, no hidden context.** Lookups and linking made no model calls. The end-to-end test asserts that a scene turn's only call is the conversation.
