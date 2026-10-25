# Probe: "+ Add facts" names and stubs (2026-10-25)

**Why.** In acceptance run 2 the owner used "+ Add facts…" on the Tsardom of Moscavia. The facts named "Tsar Ivan III" and "Tsar Alexei II", but no stubs were made. `world/add-facts.jinja2` never asked for `names`, and `accept_facts` made no stubs. Ruling H8 fixes this: the prompt now copies create-thing's names line and reply shape verbatim, and accept makes the stubs.

**The setup.**
- **Model:** Skyfall-31B-v4.2-i1-Q4_K_M, at http://192.168.0.5:5001, one call at a time (approved).
- **Harness:** `scripts/dev/probe_add_facts_names.py`.
- **Labels:** `raw/2026-10-25-add-facts-names-labels.json`, committed before any call (8c40b189).
- **Raw output:** `raw/2026-10-25-add-facts-names.json`, runs `before` and `after`, with every prompt and reply.
- **The world:** the owner's acceptance world `78d0ebd6…`, copied with the sqlite backup API. The live file was never written. The owner's add-facts revision and the two hand stubs made after it (revs 12–14) were undone on the copy, so the Tsardom has the 14 facts it had when the owner asked.
- **The prompt:** "the current Tsar and how he came to the throne". The owner's own prompt wasn't logged: `backend.log` at 11:39:57 has only `action=add_facts`.
- **The calls:** 3 per run, through the app's own `worldplay.facts.draft_facts`. "Before" ran at 8c40b189 (the template as e6d05849 had it); "after" ran at 303019ca.

**The wording added** to add-facts, all copied verbatim from create-thing's generic branch:
- the example's `"names": [{"name": "...", "kind": "place", "tag": "...", "in": null, "aka": []}]`;
- the `- "names": after the facts, every proper name your facts use…` rule;
- the `- Only named things become entries…` rule.

## Results

A "new name" is a proper name a fact writes that the world doesn't have. It is counted by hand, by the labels' rule: titles, offices, adjectives and the entry's own names don't count, and a titled person counts once.

| Call | New names in the facts | Stubs proposed | Covered | False stubs |
|---|---|---|---|---|
| before 1 | Aldric V, Tsar Vasily IV, Temple of the Pale Light (3) | 0 | 0 | 0 |
| before 2 | Tsar Vsevolod III, Tsar Dmitri II, Prince Yaroslav (3) | 0 | 0 | 0 |
| before 3 | Tsar Aldric, the Transformation (2) | 0 | 0 | 0 |
| after 1 | Aldric III, Aldric II, House of Novogrudok (3) | 3 | 3 | 0 |
| after 2 | Aldric Whitefeather, Boris the Elder, Transformation of 994, White Citadel (4) | 3 | 3 | 0 |
| after 3 | Tsar Aldric Vane, Tsar Konstantin IV, Lady Maren Ashkova, Vane dynasty, Free Cities of the Southern Reach (5) | 5 | 5 | 0 |

**Totals:**
- **Before:** 8 new names, 0 stubs. This is the owner's bug, every time.
- **After:** 12 new names, 11 stubs proposed. All 11 are real names, so there are no false stubs. One name was missed: "White Citadel", in after 2.
- **F5 held:** no title or office became a row. "Commander" (after 1) and "the Tsar" stayed plain.
- **Accepted offline:** each after draft was written, as returned, onto a fresh undone copy. Each made one revision. Every stub was made and linked from the facts, with none left unlinked.

**What the rows looked like:**
- **Kinds:** all right. The people are characters, the dynasties lore, the Transformation an event and the Free Cities a place.
- **Tags:** right in after 3 ("ruler", "former ruler", "noble", "dynasty", "foreign territory"). In after 1 and 2 they were long phrases: "tsar of moscavia", "the previous tsar of moscavia", and "the cataclysmic event that created the moscavian owl-folk". The names line says the tag is "what it is, as for the {{ kind }}". In create-thing that points at its `"tag"` rule ("one or two words…"), but add-facts has no such rule. The owner can edit the tag on the row.
- **"in":** nearly every row was filed in the Tsardom ("this entry"), dead former Tsars included. The row shows this, and it can be removed.
- **"same as…" offers:** the Tsar names were offered "Tsar's Council of Feathers", through the shared word "Tsar". This is create's existing offer rule. It is never the default.

**The verdict.** The fix works on the owner's case. Before it, 0 of 8 names became stubs; after it, 11 of 12 did, with no false stubs and no titles. Three calls per run is too few to measure a rate. Long tags are the one thing left. Create-thing's own tag rule, copied as well, would likely fix them, but that is new add-facts wording and would need its own probe.

## Follow-up: create's tag rule (ruling H9)

Create-thing's `"tag"` rule is now copied verbatim into add-facts: "one or two words for what the {{ kind }} is…", with the kind-name line only for a lore or event entry. The Tsardom is a place, so it doesn't get that line. The same 3 calls were re-run as `after-h9` at ae76bd70. The long-tag label was committed before the calls, in f070fef5.

| Call | New names in the facts | Stubs proposed | Covered | False stubs | Tags |
|---|---|---|---|---|---|
| after-h9 1 | Alexei III, Dmitri II (2) | 2 | 2 | 0 | ruler, ruler |
| after-h9 2 | Tsar Aldric, House Vostok, Tsarina Yelena, Pale Light Cathedral (4) | 3 | 3 | 0 | ruler, dynasty, former ruler |
| after-h9 3 | Tsar Aldric Winterborn, Transition Period, Transformation of 994 (3) | 3 | 3 | 0 | ruler, historical era, cataclysm |

**Tags longer than 2 words:** 5 of 11 in `after` (H8), and 0 of 8 in `after-h9`.

**False stubs:** still 0. 8 of the 9 new names were proposed; the one missed was "Pale Light Cathedral".

**The verdict:** the tag rule fixes the long tags, and nothing else moved.
