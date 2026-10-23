# Probe: curation in a real session (Task 13)

Date: 2026-10-23. Model: koboldcpp, Skyfall-31B-v4.2-i1-Q4_K_M, through Talemate's own KoboldCpp client. Calls ran one at a time. The owner approved Skyfall for this task.

- **Script:** `scripts/dev/probe_curation_flow.py`. It drives the real `worlds` router (`WorldsPlugin`) in a fresh world (present year 1000), as the world screens do. Every create, core, Fill, prose call, verdict, plan and turn came from the model. `--merge` merged one pair in the kept world afterwards, and `--score` produced the counts below.
- **Raw output:** `raw/2026-10-23-curation-flow.json`. It holds each run's steps (previews by section, accepts, world changes per step), every call's prompt and reply, `scores` (old and new world) and `run_notes`.
- **Baseline:** the owner's 2026-10-22 acceptance world, opened from a temp copy of the snapshot and never written. Its per-entry on-topic counts are the placement probe's hand labels (`raw/2026-10-22-fact-placement-labels.json`).
- **MockClient end-to-end test:** `tests/worldplay/test_curation_end_to_end.py`. It covers the whole flow through the router (see the end of this doc).

## Fixed after the run

Every score below is from **before** these fixes. They were made after the run, in Task 13's fix round 1, from the controller's rulings. None of them changes model-facing wording, so the session was not run again.

- **C24: move-in picks arrive unticked.** The model's picks are marked `picked`, come first and show as "suggested"; the owner ticks them. An own fact that restates a pick is flagged as its repeat, but stays ticked unless the owner ticks the move. (Concern 1.)
- **C25: scene planning's stub previews write only their own facts.** Their elsewhere, move-in and re-file rows are unticked, and no same-thing verdict is asked. A test checks that starting a scene leaves every other entry's facts as they were. (Concern 2.)
- **C26: a core reply whose outline can't be read no longer fails the preview.** It falls back to the template's drawers, with its name, summary, timeline and items read from the parts that parse. Items in a drawer the template lacks go to Unsorted. Run 4's reply is the test fixture. (Concern 3.)
- **C27: held text that already attributes itself is left as it is.** This covers an opening clause with "holds that", "teaches", "believes" or "maintains that", whoever the subject is. "The doctrine holds that…" no longer becomes "Church … holds that the doctrine holds that…". (Concern 6.)

Fix round 2 followed a review of round 1, with more tests:
- **C27:** the verb must directly follow the opening noun phrase, with no "who", "which" or "that" between; "hold that" counts; "teach" and "maintain" count only with "that". So "Heretics who teach otherwise…", "Owls taught to read…" and "The Collegium teaches runeweaving…" are wrapped as before, and "The faithful hold that…" isn't.
- **C26:** the salvaged core keeps the reply's own drawer outline (all 15 of run 4's items land in their drawers, none in Unsorted), its first-key name and its listed names. It needs an item or a timeline entry. The preview is marked `salvaged`, and the sphere preview says part of the reply couldn't be read.
- **C24, the other half:** ticking a move-in pick unticks the own facts repeating it in the preview, and unticking it gives them back. At accept, an own fact still ticked that repeats a ticked move isn't written twice; a note says so.
- **C29:** candidate lines say "part of Y" without the drawer it's filed in (run 5's facts took up "the Techniques drawer").

## The runs

Run 5 is the scored session. Runs 1 to 4 stopped or went off the owner's path because of the harness, not the app. Each fix is in the script, and each run is kept in the raw JSON.

| Run | What happened |
|---|---|
| 1 | The harness followed "Goddess Veil", a god the Tsardom's reply had listed as a `religion` sphere, instead of the Tsardom's church mention ("Church of the Veil", listed as a lore item). It then stopped on a harness bug. |
| 2 | A replay of run 1. Stopped by hand because it made the same wrong pick. |
| 3 | Complete, but the regiment pick caught a rite ("The Talon Oath"), and Runeweaving had no codex. |
| 4 | The church core reply was malformed JSON (items written as a list of lists), and the router answered "no drawer outline". The owner would press the button again, so the harness now does. |
| 5 | Scored (42 calls, 9.4 minutes of model time). The merge ran after it on the kept world. |

Run 5, step by step:
1. **Owl-folk**, from the spheres probe's prompt. **The Tsardom**, a `nation` sphere from its stub, with "It has a state church." Its core named the Church of the Eternal Vigil (a lore item in "Church & Doctrine"). It named no regiment.
2. **The church:** the Church of the Eternal Vigil, expanded from that lore stub as a `religion` sphere.
3. **The Divine Right of the Tsar:** the church's core named no such doctrine. The owner made it in the church's Doctrines drawer from a one-line prompt.
4. **The army:** the Tsardom named no regiment, so the owner wrote the old run's line into the Tsardom ("…regiments such as the White Talon and the Frosted Wing"). He made both regiments stubs, filed them in "Throne & Hierarchy", and expanded the White Talon. `add_outer_body` put "The Tsar's Army" (`order`) around it. The re-file rows were the Frosted Wing, the Tsar and the Nocturnal Council, all unticked. The owner ticked the Frosted Wing only.
5. **Runeweaving**, a `field` sphere from a prompt. Then its children: Deepcarving (technique), the Collegium of Aeltham (site) and the First Codex. The owner wrote the codex in, because the core named none. Then a Fill of Sites, and the Deep Inscription Chambers, a place inside the Collegium (`parent`), where facts could move in.
6. **The timeline:** Runeweaving's page.
7. **The scene:** the owner marked one of the Divine Right's facts as held by the Church. Then he planned a scene ("A young runeweaver is summoned at the Temple of the First Changing, where a priest … questions her about the Divine Right"), started it and played two narrator turns.
8. **The merge** (after the session): Runeweavers' Collegium into the Collegium of Aeltham.

At every other tick, the preview's defaults were accepted:
- elsewhere items ticked;
- repeats at 0.7 or more unticked;
- move-in picks ticked;
- same-thing offers left as "new".

## Scores

All of these are from run 5, before the fixes above.

**How the labels differ.** The old world's labels are the placement probe's. They were strict (a fact belongs where it's primarily about) and committed before any model call. Run 5's labels were judged after the run, under the owner's either-side reading. They are in `raw/2026-10-23-curation-flow-labels.json`, one row per own fact, elsewhere item and ticked move-in row. Read the new figures with that in mind: the either-side reading is the more forgiving one.

### Own facts on topic

**Like for like, the 5 entries both runs expanded: 56/57 against 44/56.** These are the model's own facts in each preview, ticked or not.

| Entry | New world | Old world (labels) |
|---|---|---|
| The Divine Right of the Tsar | 11/12 | 1/11 |
| White Talon | 11/11 | 12/12 |
| Deepcarving | 12/12 (one arrived unticked, a repeat of its own drawer line) | 11/11 |
| The site (Collegium of Aeltham / Ashenmere) | 12/12 | 9/11 |
| The First Codex | 11/11 | 11/11 |
| **The 5 comparable entries** | **56/57 (98%)** | **44/56 (79%)** |
| The inner place (Deep Inscription Chambers) | 12/12 | (none) |
| The Ashenmere Caves | (merged away) | 11/12, all restating |
| The Illumination, the Law of Resonance, the Unwritten Rune | (not made) | 23/33 |
| **All own facts** | 68/69 | 78/101 (77%) |

The one miss, on the Divine Right: "No secular law enacted by the Tsar may contradict Church doctrine". That is a law, which belongs to the Tsardom or the Church.

**Page level, at the run's defaults: 70/89 (79%) against 77%.** This counts what the accepts actually wrote onto these six pages: their 69 ticked own facts (68 on topic) plus the 20 facts move-in brought in with its ticks (2 on topic). The old world had no move-in. On this measure the two runs are about level, and move-in is what holds the new run back (see below).

The doctrine was the old run's worst case, and it's fixed: its relation claims stayed on it, and only 3 items went elsewhere (the Church, the Patriarch and the Tsardom). Moskov and the army got none: the army didn't exist yet, and the model kept the Moskov material as the doctrine's own relation claims.

**The capital, Moskov, was never expanded** in run 5. It's a stub in the Tsardom's Lands, so the spec's "its capital" check (the Sites line linking to an existing entry) wasn't exercised. In the old world, Moskov's 12 facts were among the most repeated.

### Moved in (new, ticked by default then): 2 right of 20, both written by the harness

| Entry | Picks ticked | Right |
|---|---|---|
| Divine Right ← the Church | 6 of the Church's 7 facts: its stub line, 2 statements, 3 timeline facts | 0 |
| Deep Inscription Chambers ← the Collegium | 8 of 16 | 0 |
| Deepcarving ← Runeweaving | 2 (the apprenticeship statement, the Collegium's founding) | 0 |
| The Collegium ← Runeweaving | 1 ("Deepcarving is classified under the Techniques drawer…") | 0 |
| The First Codex ← Runeweaving | 2 | 1 |
| White Talon ← the Tsardom | 1 | 1 |

**Both right picks were lines the harness wrote** for the owner: the Codex line on Runeweaving, and the regiments line on the Tsardom. The model's picks among what the model itself had written were right **0 of 18** times.

The labels map correctly: the prompt's M list and the reply's picks were checked against the facts that moved. The Task 3 probe found 10/10 picked with 7% false. In a live session, where the broader entry is the new entry's own sphere or parent, the model picks most of what the broader entry says.

The Church ended the session with **3 facts**, against 8 after its core. The doctrine took 6, and the scene start took 2 more. Both are now fixed: C24 and C25.

### Elsewhere items: 16 of 17 under either side, 7 of 17 strictly

| Entry | Items | Targets |
|---|---|---|
| Divine Right | 3 | the Church, the Patriarch, the Tsardom |
| White Talon | 1 | the Tsardom |
| Deepcarving | 6 | |
| The Collegium | 2 | |
| The Codex | 2 | |
| The Chambers | 3 | |

**16/17 holds only under the either-side reading.** One item is wrong under both: from Deepcarving, "The permanent, irreversible nature of deepcarving has made it a subject of ethical debate…" went to Runeweaving.

Strictly, where the target must be the claim's primary home, 9 more miss. Each is a relation claim mainly about its source:
- Divine Right → the Church: "…one of the three pillars of Church doctrine";
- Divine Right → the Tsardom: "The Divine Right Doctrine is the foundational principle…";
- Deepcarving → Runeweaving: "Deepcarving is classified under the Techniques drawer…";
- Collegium → Deepcarving: "Deepcarving is taught exclusively in the Collegium…";
- Collegium → Runeweaving: "The Collegium of Aeltham serves as the governing body…";
- Codex → Runeweaving: "The First Codex is the foundational written record…";
- Chambers → the Collegium: "…the Deep Inscription Chambers house the oldest rune inscriptions…";
- Chambers → Deepcarving: "The Deep Inscription Chambers display the full range…";
- Chambers → the Codex: "Several of the inscriptions in the Deep Inscription Chambers predate the First Codex…".

The 7 strict hits went to the Patriarch, the Tsardom (the army line), the Ashenmothers' Ruins, the Rune Gardens, the Collegium (certification), Living Transmutation Theory and the Collegium (the Codex's archive).

The either-side items are allowed, but each one is also a repeat: the same relation sits on both pages.

### Repeats

The counter flags a fact when another fact holds most of its words (`world.repeats.overlap` at or above the threshold). At 0.7 it also groups facts into restatement clusters, linked when either one's words are mostly in the other.

| | Old world | New world |
|---|---|---|
| Facts | 229 | 190 |
| Flagged at 0.7 | 76 (33%) | 16 (8%) |
| Redundant copies at 0.7 (clusters, hand-checked) | 58 (25%) | 17 (9%) |
| Flagged at 0.5 | 133 (58%) | 50 (26%) |
| Real in a sample of 15 at 0.5 | 14 | 13 |
| Estimated restating facts at 0.5 | ~124 (54%) | ~43 (23%) |
| Flagged at 0.4 | 163 (71%) | 71 (37%) |

- **The 0.7 comparison is partly true by construction.** The new pipeline unticks a fact that overlaps a nearby fact at 0.7 or more, so restatements at that level mostly never got written. **The 0.5 and 0.4 rows are the fairer test.** There the new world still restates at less than half the old world's rate.
- **Hand checks:**
  - At 0.7, the chain and mention rule was applied to both worlds the same way. A cluster that chains two claims counts each claim once. A link that only mentions the other fact's subject is dropped.
  - Old world: C0 chains two claims (−1), and three links were mentions (C21, C37, C38; −3), giving 62 to 58.
  - New world: the 13 clusters were checked against the same rule and none was dropped. Two are close calls kept as restatements: "Deepcarving is governed by the Law of Willing Stone, meaning…" restates the Law's line, and the Chambers' ethics code restates the Covenant's line, as the old world's C36 was kept.
  - At 0.5, a seeded sample of 15 flagged facts per world (seed 7) was judged under the same rule. Old world: 14 real; the miss was the Patriarch leading the Vigils, a mention. New world: 13 real; the misses were the Sanctity of Night against the Council declaring the night sacred, and the Shattered Anvil against Aldric's fusion, both mentions.
  - At 0.4, chaining makes clusters meaningless (the biggest has 63 facts), so only the flag counts are given.
- **Where the old repeats were:** the Caves restating Ashenmere (12 facts), the doctrine and the Illumination restating the Tsardom and the Church, and the 947 rediscovery in several places.
- **Where the new repeats are:** these are new kinds of repeat.
  - Facts moved in sit beside the same claim written again by a later expansion. One example is the First Ecumenical Council, on the Divine Right and on the Ecumenical Council.
  - Elsewhere relation claims sit on both sides: Deepcarving and the Collegium on certification, and the Codex and the Collegium on the archive.

### Duplicate entries: 5 against 5 before the merge, 4 after it

The pairs below were checked by hand from `same_candidates` over the whole world. Both worlds are counted at the same point, before any merge.

**New world (5):**
- Weaver Aldric / Aldric of Dunmore: offered as same-thing on Deepcarving's row, and left "new" by default;
- Ashenmothers / Ashenmothers of Karrath: offered on the Codex's row;
- Tsar / The Tsar of Moscavia: offered on the Divine Right's row;
- the Veined Halls / the Deep Inscription Chambers: not offered. It is the chambers' own nickname, listed as a new name;
- Runeweavers' Collegium / the Collegium of Aeltham: offered at the top of the Collegium's preview ("Is this Runeweavers' Collegium?") and left "new".

**The harness ran the merge, not the owner.** After the session, `--merge` merged Runeweavers' Collegium into the Collegium of Aeltham through the router. It made one revision, re-pointed 1 link, added the old name as an "also known as" and made no model call. That leaves **4**.

If the owner had taken each offer, **1** duplicate would be left: the Veined Halls, which was never offered.

Two more pairs are debatable and not counted: the Codex Vault and the Deep Inscription Chambers, and the Dawn Vigil and the Nocturnal Vigil. The second was offered on the Church core's item row.

**Old world (5):**
- Ashenmere / The Ashenmere Caves;
- Cathedral of the Eternal Light / The Cathedral of the Eternal Light, Moskov;
- Patriarch / The Patriarch of Moscavia;
- The Patriarch of Moscavia / The Patriarch of Moskov;
- The Holy Synod / The Synod of Lanterns;
- also the Eternal Light, a god made as a field sphere that retold the Church.

**What came back:** run 1's Tsardom listed its god as a `religion` sphere again ("Goddess Veil"). Run 3's listed "The Eastern Star" as a beliefs item. Run 5's had no god entry.

### Timeline: the key events are gathered, but it's crowded at 945

Runeweaving's timeline has 16 lines (after the merge).

- **Gathered:** its own events (247, 512, 789), plus events from its parts: Deepcarving's 850, the Collegium's 945 founding and the Codex's 247 compiling. Every key dated event of the Runeweaving set is on it. In the old run the 947 rediscovery was missing from Runeweaving's timeline.
- **Crowded:** **10 of the 16 lines sit at 945**: 1 from Deepcarving, 2 from the Collegium, 3 from the Codex and 4 from the Chambers. **8 of those are states, not events**, dated "since 945" because the model dates a new entry's plain facts at its founding year. Examples: "The walls of the chambers are lined with veins of quartz…", "Access … is restricted…".
- **Duplicates:** the Collegium's founding appears twice in 945. One copy is Runeweaving's own timeline fact, which move-in carried to Deepcarving and is still shown from there. The other is the Collegium's history fact. A third line, from the Codex, mentions the founding. None is flagged, because disagreeing dates need different years.
- **The Church's timeline is worse.** Its page now has 19 lines, 12 of them the Ecumenical Council's facts, each dated 994. The council was expanded silently at the scene start; that is now fixed (C25).

### The scene: the held fact is in play

- The World block tells the doctrine's held facts as "Church of the Eternal Vigil holds that …". Two of them were statements the doctrine moved in from the Church, and they kept their holder.
- Both turns are a priest reciting the doctrine as the Church's teaching, and a runeweaver who answers carefully. The narration never states it as truth.
- **Minor:** the owner's held fact already read "The doctrine holds that …", so it rendered as "… holds that the doctrine holds that …". This is now fixed (C27).
- The World block's Divine Right section also carries the facts move-in put there, such as "The state church of Moscavia, which teaches …" and "All sacraments are administered …". The narrator sees them as the doctrine's.

## Cohesion: what the owner will notice

What the model writes is far more cohesive than last time:
- every expansion's own facts are about the entry, the Divine Right included (56/57 against 44/56 on the entries both runs made, judged more leniently this time);
- restatements happen at under half the old rate even below the filter's threshold (about 23% of facts against 54% at 0.5);
- sub-parts feed their sphere's timeline instead of retelling it.

Counting what the run's defaults actually wrote onto the pages, though, the two runs are level (79% against 77%), and the duplicate entries are level too (5 against 5 before the merge).

The owner will notice two things that work against that:
- **Move-in, at its default ticks, scatters more than the old run did.** A new entry inside a sphere takes most of the sphere's page with it. The Church was hollowed out to 3 facts, and the doctrine and the inner chambers became grab bags of their parent's facts. Ticked moves landed off topic 18 times, against the old run's 23 off-topic facts. They are worse than off-topic facts, because they also leave a hole where they came from.
- **Starting a scene silently rewrites the world.** Planning fills its stubs and accepts their previews with every elsewhere and move-in tick in place.

Both are now fixed (C24, C25). With them, the session should read as the cohesive world the spec asks for, though this hasn't been re-run on the model. The remaining noise would be:
- the dated-state clutter on timelines (10 of Runeweaving's 16 lines at 945);
- relation claims written on both sides;
- one in four same-thing offers being pure word noise ("The First Codex" against "The Temple of the First Changing").

## Concerns, for the controller

As raised after the run. Concerns 1, 2, 3 and 6 are fixed (C24, C25, C26, C27), and so is part of 4 (C29). 5 and 7 stand.

1. **Move-in picks are ticked by default (ruling C2), and in the session they were right 2 times of 20.** The spec's probe-2 fallback is "list all the broader entry's facts, unticked". *Recommendation:* untick model picks by default (keep them sorted first), or show them only as a hint. This is a code default, not wording. No wording change was made, so no step was re-run.
2. **Scene planning's stub previews accept elsewhere and move-in silently.** `worldplay/setup.py`, `_stub_previews` and then `_accept_stub_previews` call `accept_preview` with the preview's defaults. In run 5 the scene start:
   - wrote 5 elsewhere facts onto 4 other entries (the Church, Moskov, the Divine Right, the Patriarch);
   - moved 2 of the Church's facts into the Temple (its Priests statement, and the Divine Right's elsewhere fact);
   - asked a same-thing verdict nobody sees.

   The MockClient test shows the verdict call too. Run 3's start moved a Church statement into a new stub. This breaks "Nothing is moved … without the owner's tick". *Recommendation:* when accepting a stub preview at scene start, untick elsewhere and move-in, and skip the verdict.
3. **A sphere core with malformed JSON fails whole** ("no drawer outline in it") even when the drawers are there. That happened 1 time in 10 live sphere-core calls across runs 1 to 5. Lenient parsing, or a retry, would hide it.
4. **Candidate-list structure words leak into facts.** Two facts and one prose paragraph said "the Techniques drawer" or "the Frontier drawer" (0 in the old world). The candidate line's "in its Techniques drawer; drawers: …" format was probe-mandated. Ruling C29 dropped the "in its … drawer" part; the sphere's own "drawers: …" list is still in the line, so "the Frontier drawer" could still come from there.
5. **The god-as-religion guess comes back.** Run 1's Tsardom listed its god as a `religion` sphere, and the stub kind lists for names stay probe-mandated (C5).
6. **Held render:** a fact that already says "X holds that…" becomes "holds that the doctrine holds that…".
7. **Timeline clutter:**
   - "since" states show as dated lines, by design ("a since 947 state … shows as 947");
   - the model dates most facts of a new entry at its founding year;
   - a duplicate founding (same year) isn't flagged.

## MockClient end-to-end test

`tests/worldplay/test_curation_end_to_end.py` covers the whole flow through the router with queued replies:
- the Tsardom as a nation sphere;
- the White Talon with "The Tsar's Army" put around it by `add_outer_body`, and the Frosted Wing re-filed;
- the Church, and the Divine Right's elsewhere items landing on Moskov, the army and the Tsardom;
- a held-by mark;
- Runeweaving, Ashenmere and the Codex, with the Ashenmere Caves marked as the same as Ashenmere and "The Conclave" left new;
- the Deep Galleries, whose move-in pick arrives unticked and moves once the owner ticks it;
- the merge;
- an entry-level "Is this X?": the Ashenmere Hollows' top candidate, Ashenmere, has facts, so the model's verdict is asked once and shown as a hint, and the owner says yes;
- Runeweaving's timeline gathering the 947 rediscovery once;
- a scene whose World block and narrator prompt tell the doctrine and the held fact as what the Church holds.

The call counts are asserted too: one verdict call, the Hollows'. Scene planning asks none (C25).
