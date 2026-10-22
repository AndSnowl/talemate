# Probe: fact placement ("one fact, one home") and the same-thing check

Date: 2026-10-22. Model: koboldcpp, Skyfall-31B-v4.2-i1-Q4_K_M, through Talemate's own KoboldCpp client (the `--ai` app's config). Every prompt went through `Prompt.request` inside `world_ai_call`, one call at a time. Nothing in `src/` was changed.

The owner's acceptance session found good facts filed badly:
- the 947 rediscovery of the Ashenmere rune dialect in five entries, and not on Runeweaving's timeline;
- a doctrine whose expansion was mostly about the Tsardom;
- Ashenmere and The Ashenmere Caves as two entries;
- a god made as a field sphere;
- Aelberth never becoming a stub.

This probe measures what the model, and plain code, can do about it before anything is designed.

- Script: `scripts/dev/probe_fact_placement.py` (`--only labels kinds same A A2 B combine score`, `--dry`). Scoring: `scripts/dev/probe_fact_placement_score.py`.
- Labels: `raw/2026-10-22-fact-placement-labels.json`. These are hand labels, committed in 9a246e75 before any model call.
- Raw output: `raw/2026-10-22-fact-placement.json`. It holds 108 recorded calls (prompt, reply, seconds, KoboldCpp token counts), each probe's parsed results, `b_judged` (my on-topic calls on B's facts, made after the run, so not blind) and `scores`.
- World: a copy of the owner's acceptance snapshot (present year 1000, 25 revisions), opened from a temp folder. Neither the snapshot nor the live app was written.

**Temperature, as the app uses it:** the app's create, sphere core and Fill calls use `creative_instruction_*` kinds (the creative_instruction preset, temperature 0.85). Its prose call uses `analyze` (the analytical preset, 0.7), for less invention. A placement or same-thing call is a judgement, like prose, so A, A2, same and kinds used `analyze_long` / `analyze` (0.7, confirmed in the client log). B used the app's own create path and kind (0.85). Every variant ran twice.

## Ground truth

The labels cover the nine expanded children. Each entry was judged **at accept time**: the world as it stood the revision before its expansion (`World.view(rev=...)`), so a fact can only restate what existed then. The new facts are the ones the expansion added; the stub's own line (the drawer line) counts as an existing fact.

| Entry | Accepted at rev | New facts | Belong here (any acceptable home) | Here is the primary home | Restate an existing fact | Partly restate | Dated event |
|---|---|---|---|---|---|---|---|
| The Divine Right of the Tsar | 6 | 11 | 1 | 1 | 11 | 0 | 2 |
| The Illumination | 8 | 12 | 2 | 2 | 11 | 1 | 1 |
| White Talon (the military division) | 9 | 12 | 12 | 11 | 0 | 2 | 1 |
| Deepcarving | 18 | 11 | 11 | 10 | 2 | 1 | 1 |
| The Law of Resonance | 20 | 9 | 9 | 9 | 1 | 4 | 1 |
| Ashenmere | 21 | 11 | 9 | 8 | 3 | 4 | 3 |
| The Ashenmere Caves | 22 | 12 | 11 | 9 | 12 | 0 | 3 |
| The Unwritten Rune | 23 | 12 | 12 | 12 | 2 | 5 | 0 |
| First Codex of Aelberth | 24 | 11 | 11 | 9 | 3 | 5 | 2 |
| **Total** | | **101** | **78** | **71** | **45** | **22** | **14** |

The labels in short:
- **The Church set is the problem.** 21 of the 23 new Divine Right and Illumination facts belong to the Tsardom, the Church, the species and races, Moskov or the Zakonnik. 22 of the 23 restate a fact already in the world.
- **The Runeweaving set is mostly on topic.** The Ashenmere Caves is the exception: written one revision after Ashenmere, all 12 of its facts restate Ashenmere.
- **The White Talon is clean.** 12 of 12 facts are about the regiment, and none restates anything.
- **Restates** means the claim is already in the world, even with an example or a small detail added. **Partly restates** means the fact overlaps an existing fact but adds a real claim; catching or missing one is not scored as right or wrong.
- **Timelines:** 14 facts touch a dated event. Only one is a must: Ashenmere's "In the year 947, a party of Runeweavers… rediscovered the Ashenmere rune dialect" belongs on Runeweaving's timeline. The others restate an event already there, or give no year, so null is also accepted for them.
- **Homes:** a list of acceptable homes, primary first. Ashenmere and The Ashenmere Caves count as one place.

## Variant A: placement after generation

There was one call per entry: 9 entries, 2 runs, 18 calls. The prompt held:
- **E list:** every live, unignored entry at accept time, with name, kind, sphere template, everyday name, part of, stub flag and one line (a sphere's summary fact, otherwise its first fact, cut at 130 characters). That was 24 to 58 entries.
- **F list:** the existing facts of the candidate homes, 21 to 71 facts.
- **N list:** the new facts.

The reply files each N as `{"fact", "home": "this" | "E5" | {"new", "kind"}, "restates": "F12" | null, "timeline": ["E2"] | null, "year"}`. The kinds for a new entry include **being** (a god, spirit or legendary creature).

**The candidate rule.** The candidate homes were:
- the entry itself;
- the sphere it is part of;
- that sphere's other items (siblings);
- the entries whose facts link to it (`mentions`, its back-links);
- every entry whose name or other name a new fact writes (whole word) or links.

The back-link part was added after the dry run. Without it, Ashenmere's F list was one fact (Stonehold), because no Ashenmere fact names Runeweaving. With it, the rule covers **45 of 45** restatements: for every restating fact, at least one fact it restates is in the F list. A top-10 by token overlap over the whole world also covers 45 of 45 (see Code instead of model).

**A2** is A again, changed after A's first results:
- homes and timelines are written as entry names, not E labels;
- the example holds placeholders only (`"<an entry's name>"`).

A's example values `"E5"`, `"E2"` and `"F12"` were real labels, and E2 is Valdmark. **Valdmark was named as a timeline 9 times** in A, which was the example being copied. E labels also slipped. One Illumination run sent the Church's and the Tsardom's facts to "The Festival of the Solstice Flame", "The Dawn Vigil" and "The Synod of Lanterns", and a Codex run gave the fact label "F35" as a home.

### Scores

202 placements per variant (101 facts × 2 runs):

| | A (E labels) | A2 (names) |
|---|---|---|
| Home acceptable | 170/202 (84%) | **191/202 (95%)** |
| Home = the labelled primary | 151 | 171 |
| Off-topic facts moved off the entry | 43/46 | 44/46 |
| **False moves** (belonged here, sent elsewhere, not dropped) | 12/156 (8%) | **5/156 (3%)** |
| Restating facts flagged | 82/90 (91%) | 77/90 (86%) |
| … with an F it really restates | 77/90 (86%) | 70/90 (78%) |
| Restatements missed | 8 | 13 |
| **False restatement flags** (clean facts) | 9/68 (13%) | 5/68 (7%) |
| Partial restatements flagged | 20/44 | 13/44 |
| The 947 rediscovery on Runeweaving's (or the Conclave's) timeline | 1/2 | 2/2 |
| Timeline-labelled facts placed on a right timeline | 9/28 | 9/28 |
| **Timeline on a non-event** | 22/174 (13%) | 24/174 (14%) |
| Year right, where a timeline hit had one | 7/7 | 4/5 |
| Same home in both runs | 74/101 | 90/101 |

Per entry, A2, both runs together:

| Entry | Facts | Home OK | Restatements flagged (with the right F) | False flags / clean | False moves | Off-topic moved | Non-event timelines |
|---|---|---|---|---|---|---|---|
| Divine Right | 22 | 22 | 16/22 (14) | 0/0 | 0/2 | 20/20 | 8 |
| Illumination | 24 | 24 | 20/22 (18) | 0/0 | 0/4 | 20/20 | 1 |
| White Talon | 24 | 24 | 0/0 | 4/20 | 0/24 | – | 1 |
| Deepcarving | 22 | 22 | 2/4 (2) | 0/16 | 0/22 | – | 4 |
| Law of Resonance | 18 | 18 | 2/2 (2) | 0/8 | 0/18 | – | 3 |
| Ashenmere | 22 | 19 | 6/6 (5) | 1/8 | 1/18 | 4/4 | 0 |
| Ashenmere Caves | 24 | 22 | 23/24 (23) | 0/0 | 0/22 | 0/2 | 0 |
| Unwritten Rune | 24 | 20 | 2/4 (2) | 0/10 | 4/24 | – | 7 |
| First Codex | 22 | 20 | 6/6 (4) | 0/6 | 0/22 | – | 0 |

### What it got right

**It knows a fact's subject.** Every Divine Right and Illumination fact about the Tsardom, the Church, the races or the Zakonnik went to that entry: 20/20 and 20/20 in A2. For example:
- "The Tsardom of Moscavia is a vast northern kingdom…" went to the Tsardom, restating its description fact;
- "Pure-line Moscavians… resemble snowy owls" went to Pure-line Moscavians, restating the Tsardom's fact.

**The Ashenmere Caves' 12 restatements of Ashenmere** were caught 23 of 24 times, pointing at the right Ashenmere fact.

**The missing Aelberth stub was proposed 4 of 4 times.** "The compiler, Aelberth, is regarded as the most important figure…" got `{"new": "Aelberth", "kind": "character"}` in every A and A2 run.

**A2 put the 947 rediscovery on Runeweaving's timeline** both times, year 947. A2 run 1 also made it a new event entry, "Rediscovery of the Ashenmere Rune Dialect".

### Where it failed

**False moves are mostly invented entries.** Over its 2 runs, A sent six Law of Resonance placements to entries that don't exist ("Material resonance chart", "Resonance measurement scale", "Ritual material preparation", "Runeweaver terminology", "Runeweaving Material Affinities", "Runeweaving Preparation Techniques"). It sent "A few rogue weavers… have reportedly sought the rune" to "Rogue Weavers" in all four A and A2 runs. A2 did this less, but "new entry" is where moves go wrong.

**Restatement flags miss the subtle cases, and one run dropped them.** Misses were:
- the drawer line said again with an example (the Law of Resonance's "a rune of enduring heat…");
- facts restating a sibling's fact.

A2's Divine Right run 0 missed its first two restatements. False flags were "same topic" rather than "same claim". In A, the White Talon's "established in the years following the Illumination" was flagged twice against the army fact (the Illumination's retelling of the Tsardom's).

**Timelines are unreliable in every form.**
- Hits are 9 of 28, and non-events get timelines 13–14% of the time.
- A2's Divine Right run 0 put 8 of 11 facts on their home's timeline: "The Tsardom of Moscavia is a vast northern kingdom" went on the Tsardom's.
- The Ashenmere Caves' Burning of Greyholm fact went to the Burning of Greyholm stub's timeline (an event, not a sphere) rather than Runeweaving's, which already holds it, in all four runs.
- "Compiled in the city of Stonehold" went on Stonehold's and the Conclave's timelines.

**It is not stable.** A2 gave the same home in both runs for 90 of 101 facts, A for 74 of 101. Ashenmere managed 5 of 11 in both.

## Variant B: placement at generation time

The Divine Right of the Tsar and Deepcarving were re-expanded through the real `create.preview_thing`, on a copy of the world undone (`World.undo`) back to the revision before each expansion. That leaves the stub with its drawer line and the same Mentioned/About/Named context the app builds. The owner's original prompts aren't stored, so the prompt was the stub's `suggested_prompt`. Prose was off. Two variants, 2 runs each:
- **control:** the app's `create-thing.jinja2`, unchanged;
- **tagged:** the same template with three changes:
  - the E list is added before the calendar line;
  - each fact gets `"subject": "this" | "E5"`;
  - facts about other entries go in a separate `"elsewhere": [{"entry", "text"}]` list.

On-topic was judged by hand after the run, so it is not blind; the calls are in `b_judged`. "Restates" is the code detector below (containment ≥ 0.4 against every fact in the world at accept time).

| | Facts | On topic | Restating (detector) | Elsewhere items |
|---|---|---|---|---|
| Divine Right, stored original | 11 | 1 | 11 | – |
| Divine Right, control run 1 | 12 | 1 | 12 | – |
| Divine Right, control run 2 | 12 | 1 | 12 | – |
| Divine Right, **tagged** run 1 | 12 | **10** | 3 | 5 |
| Divine Right, **tagged** run 2 | 10 | **10** | 4 | 3 |
| Deepcarving, stored original | 11 | 11 | 1 | – |
| Deepcarving, control (2 runs) | 11, 10 | 11, 10 | 1, 1 | – |
| Deepcarving, tagged (2 runs) | 11, 11 | 11, 11 | 1, 3 | 4, 5 |

**The control reproduces the owner's problem exactly.** Both control runs of Divine Right wrote one fact about the doctrine and eleven retellings of the Tsardom, the capital, the army, the Zakonnik, the transformation and the Church. It was close to word for word: 12 of 12 restate, both times.

**The tagged prompt fixed it.** Its facts were about the doctrine itself:
- "to resist the Tsar's rule is to resist the Light itself";
- "No Tsar has ever been formally deposed… a fact the Church cites";
- "The doctrine holds that the Eternal Light chooses the Tsar through a combination of bloodline, piety, and the Church's formal investiture".

Its remaining restatements are mostly the drawer line said again. The two off-topic facts in run 1 were a new body, the "Council of Feathers", and the throne.

**On an entry that was already on topic, it changed nothing.** Deepcarving was 11/11 either way.

**The `subject` tag carries no information: 44 of 44 tags are `"this"`.** The tagged prompt works because of the **`elsewhere` list**: the model has somewhere to put the rest. But `elsewhere` items need the same checks as any new fact:
- many are relations ("Deepcarved runes are governed by the Law of Resonance…");
- some restate their target ("…their effectiveness depends on the material's natural affinity with the glyph's meaning" is the Law of Resonance's own line);
- both Divine Right runs filed one item under the entry itself (E17).

**Cost.** The E list adds about 1.0k prompt tokens (24 entries) to 2.3k (55 entries), on a 1.2–1.8k-token create prompt. Reply length and time are about the same: 28–44 s tagged, 22–44 s control. There is no extra call.

**Combine** (A on each tagged run's own facts, 4 calls, 11–15 s each):
- **Restatements:** A flagged the drawer line restated in all 4 runs (N1 → F1), plus Runeweaving's doctrine (F7), the latent signature (F2) and the Ashenmere inscriptions (F9) in the Deepcarving runs. The "Ashenmere rune dialect… third resonance law" fact went to the Law of Resonance as a restatement of Runeweaving's Frontier line.
- **Moves:** 11 facts were moved, and 2 were clearly wrong. In Divine Right run 1 it sent "the Divine Right is taught… from their Baptism by Candlelight" and the throne fact to The Dawn Vigil, which was an E-label slip. The other moves were defensible: the Zakonnik fact to the Zakonnik ×2, the coronation to the Cathedral, the Patriarch's blessing to the Patriarch, the oldest deepcarvings to the Ashenmere Caves ×2, and the dialect fact to the Law of Resonance.

So the two variants combine. B removes the off-topic bulk at the source; a check after generation still catches the restated drawer line and sibling material.

**Seen in passing (not scored):** the Deepcarving control runs dated the Burning of Greyholm 782 and 784. The world holds 888 for the Greyholm Archive's destruction. Contradiction is a separate problem from placement.

## Same-thing check

There were 23 labelled pairs, one of them ambiguous and not scored, at 2 runs each. Each side was shown as name, kind, part of and up to four facts. A stub with no facts was shown with what mentions it; a name only mentioned (Aelberth, "the Conclave") was shown with the facts that write it. The reply is one of same, part_of, contains or different.

| | Right |
|---|---|
| Exact relation | 25/44 (57%) |
| **Same or not (merge or not)** | **37/44 (84%)** |
| Pairs that are one thing, called same | **19/20** |
| Pairs that aren't, called not same | 18/24 |
| … where both sides have facts of their own | **10/10** |
| … where one side is a fact-less stub, shown by its mentions | 8/14 |
| Same answer in both runs | 17/23 pairs |

**The five pairs the owner raised:**
- **Ashenmere / The Ashenmere Caves:** same, 2/2.
- **Moskov / the Tsardom's "Moskov: The capital stands…" Lands & Sites line:** same, 2/2.
- **Eternal Light / Church of the Eternal Light:** not same, 2/2 (once different, once part_of).
- **"the Conclave" / Runeweavers' Conclave:** same, 2/2.
- **"Aelberth" / First Codex of Aelberth:** not same 2/2, but called part_of both times.

The others found: the two Cathedral entries, the Patriarch entries, The Holy Synod / The Synod of Lanterns (no shared name but "Synod"), and the White Talon, Baptism by Candlelight and Monastic Scriptoria entries against their statement lines. Of these 7 pairs, 13 of 14 judgments said same; one Monastic Scriptoria run said different.

**All 6 false "same" calls involve a fact-less stub:**
- Moskva River / Moskov, 2/2;
- The Greyholm Archive / Greyholm, 2/2;
- Burning of Greyholm / Greyholm, 1/2;
- Great Synod of Moskov / The Holy Synod, 1/2.

A stub is shown by the facts that mention it. Those facts are about the other thing ("Moskov… at the confluence of the Volga and Moskva rivers"), so the model judges the wrong subject.

**The exact relation is weak.** The model reaches for part_of: a feast is "part of" the event it marks, the Codex's author is "part of" the Codex, and the Cathedral is "part of" the god.

## Kinds

There were 7 cases at 2 runs each. The kinds offered were character, place, species/race, item, event, lore, **being** (a god, spirit or legendary creature), and sphere with a template (religion, nation, order, culture, field), plus what it is part of.

| Case | Expected | Picks |
|---|---|---|
| Eternal Light, as a stub (only its mentions) | being | sphere: religion ×2 |
| Eternal Light, with its present facts | being | **being** (part of the Church), sphere: religion |
| White Talon, as a stub (the Tsardom's army fact) | sphere: order, part of the Tsardom | lore, part of the Tsardom ×2 |
| White Talon, with its facts | sphere: order, part of the Tsardom | **sphere: order, part of the Tsardom ×2** |
| Church of the Eternal Light (control) | sphere: religion | sphere: religion, part of the Tsardom ×2 |
| Runeweaving (control) | sphere: field | field, order |
| Patriarch (control) | lore (an office) | sphere: order ×2 |

**The god was called a being in 1 of 4 runs.** As a stub, its mentions say "declared the Eternal Light the patron deity of the realm" and "an event the Church interprets as the ultimate revelation of the Eternal Light". The model calls it the religion, which is the Eternal Light field sphere's own mistake made again.

**The regiment becomes an order sphere, part of the Tsardom, only once it has facts.** As a stub it is lore, which matches the create prompt's rule "any other group or faction is lore".

**An office became an order sphere 2 of 2 times.** The kind call is too unreliable to apply without the owner.

## Cost

| Call | Calls | Seconds (mean, range) | Prompt tokens (mean, max) | Reply tokens (mean, max) |
|---|---|---|---|---|
| A placement | 18 | 14.9 (11.7–19.6) | 4923 (6228) | 438 (519) |
| A2 placement | 18 | 14.7 (9.8–19.9) | 4923 (6228) | 431 (501) |
| B create, control | 4 | 31 (22.5–44.0) | 1166–1819 | 767–1493 |
| B create, tagged | 4 | 33 (28.1–43.6) | 2865–3473 | 976–1467 |
| Combine (A on B's facts) | 4 | 12.8 (10.7–14.8) | 3779 (3846) | 371 (399) |
| Same-thing (one pair) | 46 | 2.3 (1.3–4.3) | 382 (532) | 72 (135) |
| Kind | 14 | 2.1 (1.6–2.8) | 651 (843) | 60 (83) |

**A placement call adds about 15 s to every accept.** That is roughly half again on a 22–44 s create. Its prompt grows with the world: the E list is one line per entry (58 entries ≈ 2k tokens), and the F list grows with siblings. On a 16k-context model, a world of a few hundred entries would need the E list cut to the candidates.

**A same-thing check costs about 2 s per candidate pair.** Tagging at generation (B) costs no call: 1–2k more prompt tokens.

## Code instead of model

**Restatements: a token-overlap detector beats the model.** For each new fact it takes the share of its content words (lower-cased, stop words out, a crude stem) that a single existing fact holds. The best match is taken over every fact in the world at accept time, with no candidate rule needed.

| Threshold | Restatements caught (of 45) | False flags (of 34 clean) | Partials flagged (of 22) | Best match is a labelled one |
|---|---|---|---|---|
| 0.30 | 45 | 5 | 12 | 41 |
| 0.35 | 44 | 4 | 9 | 40 |
| **0.40** | **43** | **1** | 7 | 39 |
| 0.45 | 39 | 0 | 4 | 35 |
| 0.50 | 37 | 0 | 3 | 34 |
| 0.60 | 27 | 0 | 3 | 25 |

At 0.4 it catches 43/45 with 1 false flag. The model, given the candidates, catches 77–82 of 90 (two runs) with 5–9 false flags of 68. The detector costs nothing and gives the same answer every time.

**It flatters itself here.** The threshold was picked on the same 101 facts, with no held-out set. In this world the restatements are near-copies, because the expansion copies its context sentences. Paraphrased restatements will score lower. A top-10 by the same overlap holds a restated fact for 45 of 45. As a candidate rule for a model call, it covers as much as the name, link and sibling rule.

**Same-thing candidates.** Pairs of entry names sharing a content word: 63 names give 63 candidate pairs, which find all 10 true "same" pairs. A name-containment classifier (one name's words inside the other's means same) gets only 12/22. It calls Eternal Light / Church of the Eternal Light, Aelberth / First Codex of Aelberth, Greyholm / Burning of Greyholm and the Feast / the Illumination "same", and misses The Patriarch of Moskov / of Moscavia and the two Synods. So code finds candidates and the model judges.

**A statement line that is an entry:** "Moskov: …", "The White Talon: …", "Baptism by candlelight is…" and "Monastic scriptoria preserve…" all open with an existing entry's name, matched exactly bar "The" and case. That is a code match, no model needed.

**Timelines:** "a year in the text" as the rule for a dated event finds 8 of the 14 labelled events, with 5 false (for example "By the year 1000, the White Talon has earned a reputation…" and "mid-800s"). It is about as good as the model's 9 of 28 hits with 22–24 false, and free. Neither is good enough to apply without the owner.

## Recommendation

**1. Fix it where it starts: an "elsewhere" list in the create (and Fill) reply.**

This is the biggest effect in the probe at no extra call. The same create prompt with the world's entry list and a separate `elsewhere` list took the Divine Right from 1 of 12 facts about the doctrine (and 12 of 12 restating) to 10 of 12 and 10 of 10 (3–4 restating), on 2 runs each. Drop the per-fact `subject` tag: it was always "this".

`elsewhere` items carry their target entry, so they are "offered as an addition there" (b) for free. Show them on the target entry for the owner to accept, after the restatement check.

**2. Restatements: code, not a model call.**

Run the overlap detector on every new fact and every `elsewhere` item, against the whole world. Use a threshold of about 0.4–0.5: here 0.4 gave 43/45 caught with 1 false flag, and 0.5 gave 37/45 with 0. Show a fact over it in the preview as "Already in the world: <fact> (<entry>)", unticked, with one click to keep it.

Don't drop silently: the threshold is tuned on this world's near-copies. It covers (c), the sphere-drawer line said again, and the Ashenmere Caves case.

**3. A placement call after generation: as a suggestion, and only where it adds something.**

A2's wording (homes as names, placeholder example) placed 95% of facts acceptably. It moved 44/46 off-topic facts and 5 of 156 that belonged (3%). That is good enough to suggest "this fact is mostly about the Tsardom: offer it there?", not good enough to move facts unasked. It is unstable (same home in 90/101 between runs) and its false moves are mostly invented new entries.

At about 15 s and 5k prompt tokens per accept, it is worth it only if (1) leaves too much off topic. I'd first ship (1) and (2), and measure again on the owner's next session. If a call is used, write homes as names, never as labels from an example.

**4. Timelines: don't let the model place them.**

The model hit 9 of 28 and put non-events on timelines 13–14% of the time. Two cheaper options:
- a code rule (a year in the text) to offer "Add to <its sphere>'s timeline?", where the sphere is the one the entry is part of;
- a separate `events` list in the create reply, the way the sphere core writes its timeline.

The second is untested and needs its own probe.

**5. Same thing: code finds the candidates, the model judges, the owner merges.**

Use a shared content word in the names to find candidates (it found all 10 true pairs), then a 2-second call per pair. Calls between entries that both have facts were right 29 of 30 (19 of 20 same, 10 of 10 not same). When one side is a fact-less stub, the model is wrong 6 of 14 times, so show those to the owner without a verdict. Read only "same or not": the exact relation (part_of) is wrong half the time.

Ask before a new entry or stub is made. Ashenmere and The Ashenmere Caves were both stubs from the same core, at rev 14. Also link statement lines that open with an existing entry's exact name to that entry, by code.

**6. Kinds: offer "being", let the owner choose.**

The god was called a being 1 of 4 times (never from its stub), and an office was called an order sphere 2 of 2 times. The model's kind can preselect a choice, never decide. A keyword hint ("god", "goddess", "deity", "spirit" in what mentions the name) would have flagged the Eternal Light. A military body became an order sphere, part of the Tsardom, only with facts (2 of 2), not as a stub (lore, 2 of 2).

**7. Missing stubs come for free.** Both placement variants proposed Aelberth as a new character in 4 of 4 runs. An `elsewhere` list, or a names check on the elsewhere items, should surface such names too.
