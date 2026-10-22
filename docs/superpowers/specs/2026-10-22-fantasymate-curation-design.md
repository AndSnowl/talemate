# Fantasymate: Curation

Date: 2026-10-22. Status: design, awaiting the owner's approval.

This continues the Spheres slice on the same branch (`feature/spheres`). Owner: "let's continue on this branch until we have a feature that feels right and complete." It is built before Spheres merges, and before languages.

It builds on:
- the Spheres spec, `2026-10-22-fantasymate-spheres-design.md`, with its rulings P1–P23 and R1 in the plan ledger;
- Connections (`2026-10-21-fantasymate-connections-design.md`): names, stubs, other names, mention context, Re-point.

Evidence:
- The owner's Spheres acceptance run (2026-10-22), recorded in the ledger.
- The placement test on Skyfall, `docs/superpowers/probes/2026-10-22-fact-placement.md`, with raw output in `probes/raw/2026-10-22-fact-placement.json`.
- The owner approved the mockup at `.superpowers/brainstorm/18418-1792707061/content/curation-preview.html` (not committed); "The pages" below describes it. The owner corrected one part of it, the White Talon, as described under "Bodies within bodies".

## Intent

In the acceptance run the facts were good but the world felt scattered:
- **The same event, five times over.** The 947 rediscovery of the Ashenmere dialect was written into five entries, and it was missing from Runeweaving's timeline.
- **A doctrine full of other entries' facts.** "The Divine Right of the Tsar" got 12 facts, and only 1 was about the doctrine. The rest were about Moskov, the Tsardom's army, its law code and the transformation.
- **Two entries for one thing.** "Ashenmere" and "The Ashenmere Caves" were separate entries, and so were the capital and a plain line under the Tsardom's Sites.
- **A god conflated with its church.** "The Eternal Light", the Church's god, was made as a field sphere, and its Fill retold the Church.
- **An inner part with no home.** A military division was expanded into an entry with no "part of".

The cause: every expansion writes a new page, and nothing decides where each fact belongs.

Curation gives every fact one home:
- A fact lives on the entry it is mostly about.
- Everything else (timelines, drawers, context) shows it from there, without copying it.
- Information flows both ways. Inner generations feed the outer sphere and their siblings, and a newer, more specific entry can take facts from a broader one.

Owner: "I would want to see it has an addition to Moskov, and if there was later an entry dedicated to the architecture of Moskov, I'd like to see it there instead."

It has to keep working with hundreds and then thousands of entries. Owner: "the links that we have between entries can serve as the basis for what context is brought in … And then we have knobs we can tune for how much related items it brings in."

## How the owner will judge it

The same kind of session as last time, in a fresh world: owl-folk, the Tsardom, its church and capital, a field like runic magic, and a few expansions down into their parts.

**Passing means** (owner): "Facts landing in the right places, and less duplicates with a more cohesive feeling overall vs. how scattered things felt in my previous run."

## Goals

### 1. Facts go where they belong

Create, expand and Fill replies gain an **"elsewhere" list**: facts about other entries, each naming the entry it is about. The prompt lists candidate entries, chosen as described under "Connections decide what's near".
- **The test's evidence:** with the list, Divine Right's facts that were on topic went from 1 of 12 to 10 of 12 and 10 of 10. It costs no extra call.
- **The per-fact "subject" tag carried nothing** in the test ("this" 44 of 44 times), so it is not used.

In the preview, these facts are grouped by the entry they're for. On Accept, the ticked ones are written onto those entries, in the same revision as the new entry.

**Prompts that get the list.** *My call:* the list goes into `create-thing.jinja2` (which covers characters and plain entries), the sphere core and Fill. Probe 1 covers all three.

**Categories.** The probe's elsewhere items were just an entry and a text, so code picks the category. *My call:*
- **The default:** the target kind's plain category. That is `general` for most kinds, `about` for spheres and `history` for places when the fact is dated.
- **Dated facts:** a dated fact on a sphere becomes a `timeline` fact.
- **No inheritance by accident:** an elsewhere fact is never given a heritage category that passes down to members.
- **The owner can change it:** each elsewhere row in the preview shows its category, which the owner can change.
- **Spheres:** a fact for a sphere goes in as an `about` fact, not as a drawer statement. The owner can file it in a drawer afterwards.

**A fact about something that doesn't exist yet** proposes a stub, with its kind and its "part of" (see "Bodies within bodies").

**A fact that's off topic and missed by the list** can still be moved by hand from any fact row ("Move to…"). The test's second pass ("A2", about 15 s per accept, 95% of facts placed acceptably) is **not** part of the default path. *My call:* it can be added later behind a setting, if the elsewhere list leaves too much off topic in the owner's run.

### 2. Facts move in when a more specific entry appears

When a new entry is made that is part of an existing one ("The Architecture of Moskov", part of Moskov), the preview offers to move facts from the broader entry that belong on the new one. They are **moved, not copied**: they leave Moskov's page.
- This needs a model judgement of which of Moskov's facts belong to the new entry. It is **untested** (see Probes).
- *My call:* the candidates are the broader entry's own facts only, not its relatives'.

### 3. Repeats are caught by code

A fact the world already holds arrives in the preview **unticked**, under "Already in the world", with where it already is. It is never dropped silently.
- **The detector:** content-word overlap against the facts of nearby entries. The test's threshold was 0.4: it caught 43 of 45 restatements with 1 false flag in 34. The threshold was tuned on the same data and the restatements were near-copies, so paraphrases will slip through more often.
- *My call:* the threshold is a setting, starting at 0.4.
- **It also runs on Fill items, on facts moved in (goal 2), and in a merge (goal 5).**

### 4. "Same thing?" before anything new is made

Before a new entry or stub is created, code finds existing entries it may be the same as:
- **The candidates:** a shared name word ("Ashenmere" and "The Ashenmere Caves", "the Conclave" and "Runeweavers' Conclave"), a name inside a name, or a matching other name. Only nearby entries count, plus any that match by name across the whole world.
- **The question:** the owner is asked "Is this X?". If yes:
  - the new material becomes additions to X, through goal 1's preview;
  - the new name becomes an "also known as" of X;
  - nothing new is created.
- **The model's verdict is offered only when both sides have facts of their own.** In the test it was right 29 of 30 times then, and every one of its 6 mistakes involved a stub with no facts. With a bare stub, the code just asks.
- **This also covers promotion.** When a place becomes a sphere, a Sites line naming an existing place (the capital) becomes a link to that entry, not a second entry.
- **What gets checked** (*my call*): the entry being created, and every new stub the preview would make (from the elsewhere list, from names in the facts, from Fill items and from goal 9's chain).
- **What the preview shows** (*my call*):
  - **The entry being created:** one question at the top, as in the mockup. The model's verdict for it runs after the preview reply when both sides have facts, about 2 s.
  - **New stubs:** a stub with a candidate gets a small "same as X?" choice on its row. The default is "new", and no model call is made for it.
  - **A cap:** at most 5 candidates are shown, ranked by name overlap and nearness. Very common name words ("Tsar", "the") don't count as a shared word.

### 5. Merge, for when it slips through

Any entry has "Merge into…". The owner picks the other entry, and the merge screen shows:
- **the name:** the owner picks the main name, and the other becomes an "also known as";
- **the facts:** combined, with repeats unticked ("already there") by goal 3's detector;
- **disagreements:** facts that seem to contradict each other are shown as a pair, and the owner picks one, or keeps both. Owner: "show me both and let me pick which one is right." Finding them needs a model call while the merge screen is built, which is **untested** (see Probes);
- **the links:** every reference, "part of", tie, parent and other field moves over. This reuses the machinery behind Re-point (`worldplay/repoint.py`), extended from stubs to full entries. It is one revision, so one undo reverses it.

### 6. Every dated fact is on a timeline

Owner: "I'd like to see anything dated on a time line."
- **Every entry gets a Timeline section:** characters, places, lore and items, as well as spheres. It lists its dated facts (any fact with a start date, and timeline facts) in date order.
- **A sphere's timeline also gathers dated facts from its parts and from entries tied to it.** Each line says where it's from. It's shown, not copied, so the 947 rediscovery lives on Ashenmere and appears on Runeweaving's timeline.
- **What a sphere gathers** (*my call*):
  - **Its parts:** the dated facts of its parts, meaning entries filed under it (part of, at any drawer) and, for a place sphere, the places inside it. This goes as many steps down as the "how far out" setting allows.
  - **Facts naming it:** any dated fact anywhere that references the sphere itself or one of those parts.
  - **Members, narrowly:** tied characters contribute only their dated facts that reference the sphere, not their births and postings.
  - **Not by nearness alone:** an entry that is merely near (through mentions) doesn't feed the timeline unless one of its facts references the sphere or a part.

  This keeps a nation's timeline about the nation.
- **Dates that disagree are flagged** (*my call*), for example two years given for the Codex's compiling, 217 and 312. This is done by code with no model call:
  - **The test:** two dated facts on one timeline, with high word overlap (the repeat detector's measure) and different years;
  - **Nothing is stored:** it's computed when the timeline is shown, so nothing needs undoing or updating;
  - **Picking:** the owner picks one as in goal 5. The other is ended or removed, as the owner chooses.
- **The model never chooses timelines.** The test scored 9 of 28. A timeline is a view of dated facts, so nothing is placed.
- *My call:* a "since 947" state and an "in 947" event both show as "947: …".

### 7. Held by: beliefs as distinct from truth

A fact can be **held by** a sphere (or a character), not simply true. "The Church holds that the Light caused the transformation."
- **On a page,** a held fact is tagged "held by the Church".
- **In a scene,** a held fact goes to the narrator as belief: the faithful speak of it as fact, but the narration doesn't confirm it.
- **A sphere's beliefs-drawer statements count as held by that sphere,** without being marked, but only for the `religion` and `culture` templates (*my call*). A nation's beliefs drawer is its Laws, which are true as laws, and a field's theories stay plain claims.
- **Entries filed under a beliefs drawer** (a doctrine like the Divine Right) don't inherit held-by. Their own facts are marked one by one, by the model or the owner.
- **Generation:** create and Fill replies can mark a fact as held by an entry from the candidate list. The owner can set or clear the tag on any fact row. The model doing this is **untested** (see Probes).

This answers the Eternal Light. A god people believe in is an entry whose facts are mostly held by its faith, so the Church's claims stop reading as the god's own truth.

### 8. Beings: gods, spirits, legendary creatures

A new kind, `being`, with an **existence** setting:
- **real:** it acts in the world like a character, and can be cast in scenes and hold ties;
- **believed:** it appears in scenes only as something spoken of;
- **undecided:** treated as believed until the owner decides.

A real person who became a legend stays a character, with held facts beside the true ones (goal 7). The model's kind pick, `being` included, only pre-selects. In the test it picked `being` for the god 1 of 4 times.

### 9. Bodies within bodies

From the owner's correction about the White Talon:
- **The army is its own sphere** (template `order`, for example "the Tsar's Army"). It is related to the Tsardom but distinct from it, as the Church is, and it is part of the Tsardom under a Military (structure) drawer.
- **The White Talon is one of its divisions:** an item in the army's divisions (structure) drawer, alongside the Frosted Wing. It gets its own entry when expanded, as the Council of Elders does in the Church.
- **Belonging is a role.** A tie can carry an optional **within**: an item of that sphere. For example "Trooper in the Tsar's Army, within the White Talon, since 1012".
- **When only the inner part has been mentioned** ("regiments such as the White Talon"), placement proposes the whole chain as stubs:
  - the White Talon, part of the army, under Divisions;
  - the army, an order sphere, part of the Tsardom, under Military.

  The model names the outer body and the owner can rename it in the preview. Proposing a body that was never named is **untested** (see Probes).
- **Existing items are re-filed too** (*my call*, the owner's exact case). When the White Talon and the Frosted Wing already sit in the Tsardom's Military drawer and the army is proposed, the preview offers ticked rows that:
  - move them into the army's Divisions drawer;
  - file the army in their place under Military.

  This uses `set_part_of`'s path and dating rule.

### 10. Connections decide what's near

One **nearness ranking** is computed from the links already in the world:
- references in facts (both directions);
- "part of", parent and child, ties, heritage, mentions.

**It is used by:** the elsewhere list's candidates (goal 1), repeat detection (goal 3), same-thing candidates (goal 4), timeline gathering (goal 6), and the context for create, Fill and scenes.

**The knobs** are world settings:
- **how far out:** steps through links, 1 to 3;
- **how many entries:** a cap per prompt;
- **how many facts per entry.**

*My call:* defaults are tuned in the probe. Today's fixed context rules (named in prompt, mentions, the scene's place, members present) become the ranking's strongest links, so behaviour at small sizes stays close to today's.

**Cost:** the links are already database rows. *My call:* compute the ranking on demand per prompt, and measure it on a synthetic world of 1,000 and of 3,000 entries before deciding whether to keep a stored list, which was the owner's alternative. Target: under 50 ms per prompt at 1,000 entries. A stored list is the fallback if it's slower.

### The pages (approved mockup)

1. **The create, expand and Fill preview** has three sections:
   - **Its facts**, ticked, with "held by" tags;
   - **Already in the world**, unticked, each with where it already is;
   - **Belongs on other entries**, grouped by entry, each ticked, with new stubs showing their kind and "part of". A group can be unticked all at once.

   A "same thing?" question sits at the top when it applies. Accept says what it will write: "3 facts here, 4 elsewhere, 1 new stub".
2. **A new entry that's part of another** also shows "Move here from where they are now": facts from the broader entry, ticked, moved rather than copied.
3. **The merge screen** has: the main name choice, facts with repeats unticked, disagreements as pick-one pairs (or keep both), and a summary of the links that move, ending in a Merge button. One undo reverses it.
4. **Timelines** show where each line comes from, and flag disagreeing dates.
5. **A fact row** gains "Move to…" and "Held by…".

## Non-goals

- No automatic fact moves without the owner's tick.
- No second placement pass by default (A2; see goal 1).
- No rewriting of existing worlds. The owner starts fresh each milestone.
- Languages, connections in scenes, a world-aware spell check and the scene-runner items stay where the main spec put them.
- No graph view of the world.

## Anti-goals

- **Silent loss:** a fact that disappears because code thought it was a repeat, or a merge that drops a link.
- **More scattering:** "elsewhere" facts that land on the wrong entry more often than the old way kept them off topic. The owner judges by cohesion.
- **A preview so busy it slows creation down.** Sections can collapse; *my call:* "Already in the world" starts collapsed when every fact in it is unticked.
- **A world that gets slower as it grows.** The nearness ranking must stay cheap.

## Constraints

Everything in the Spheres spec still holds:
- `world/` stays pure, strict mypy, and imports nothing from talemate;
- every multi-write action is one revision, so it can be undone;
- probe-mandated prompt wording changes only with new probe evidence;
- no raw `[[thing:…]]` text in prompts or pages;
- browser tests run with at most 4 workers;
- the owner is asked before AI tests.

A fact moved between entries is **copied with a new id and removed from the old entry** (ruling R1). No store primitive moves a fact across entries.

## Probes (before the features they serve)

The owner approves each probe. Each one tests on a copy of an acceptance world, against hand labels made before any model call. The placement probe already covers the elsewhere list (B), the repeat detector, same-thing and kinds.

1. **Elsewhere with nearness candidates:** the elsewhere list where candidates come from the nearness ranking, not the whole world, at a few knob settings. Measure what gets placed on topic, and the prompt size.
2. **Facts moving in:** given a new, more specific entry, does the model pick the right facts from its broader entry?
3. **Contradictions:** does the model find disagreeing pairs in a merge and on a timeline, without flagging facts that only differ?
4. **Held by:** does the model mark beliefs, for the church and its god, without marking world facts?
5. **The outer body:** given "regiments such as the White Talon", does the model propose the White Talon inside a new order sphere inside the Tsardom, with sensible names?
6. **Nearness cost:** measured on synthetic worlds of 1,000 and 3,000 entries (code only, no model).

**Pass bars and fallbacks** (*my call*):
- **The bar:** a probe passes when at least 80% of its labelled cases are right and at most 5% are false moves or false flags.
- **When one fails,** its fallback is built and the owner is told at acceptance:
  - **2. Facts moving in:** list all the broader entry's facts, unticked.
  - **3. Contradictions:** in a merge, show facts with high word overlap side by side for picking, with no model.
  - **4. Held by:** tagging by hand only, plus the religion and culture beliefs drawers.
  - **5. The outer body:** the preview asks the owner to name it, and pre-fills "<inner part>'s parent".
  - **1. Elsewhere with nearness:** fall back to the whole-world list for small worlds, and stop to rethink with the owner.

## Left to the builder

- **The scoring weights** for the nearness ranking, and how to store it if on-demand is too slow.
- **The exact preview layout** within the mockup's shape.
- **How "held by" is stored:** a fact field or an origin entry. It must survive correction and undo, and work through the scene context.
- **The merge's move order and refusals,** extending `repoint.py`'s.
- **How the `being` kind's fields map onto the character machinery when real.**
- **Which existing context paths the ranking replaces,** and in what order. The owner's next run is the judge.
