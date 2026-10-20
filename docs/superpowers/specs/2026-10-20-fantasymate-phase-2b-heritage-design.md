# Fantasymate phase 2, plan B: species, races, mixes and inheritance

Date: 2026-10-20. Status: design, awaiting the owner's approval.

This is the second plan of phase 2 in `2026-10-18-fantasymate-world-data-model-design.md` (the "main spec"), following plan A, the playable slice (`2026-10-19-fantasymate-phase-2-slice-design.md`, merged 2026-10-20). The main spec stays the authority for the data model; this document widens it where the owner decided more on 2026-10-20.

Evidence used:
- **Heritage probe:** `docs/superpowers/probes/2026-10-20-heritage-blending.md`, run at the owner's request during this brainstorm.
- **Slice acceptance results:** `docs/superpowers/probes/2026-10-19-slice-acceptance.md`.
- **Mockup:** the owner approved the species page and the inherited-facts character page. The file is `.superpowers/brainstorm/13616-1792534161/content/species-page.html`, which is not committed; "The pages" below describes it.

## Intent

A character should only need what makes them unique. What they share with their people comes from their species and race, and later their culture. The owner's finished-product picture is a world with two or more intelligent species (humans being one), races within each, and characters made from them. Plan B makes that possible:
- the owner makes species and races, and mixes between them;
- characters inherit their facts;
- creation and play use the inheritance.

**The owner's rule still holds:** it must work on the local model (koboldcpp, currently Skyfall-31B). The probe shows the model blends two parents well on the spot, and blends most consistently from a written mix entry, so every mixed heritage goes through one. It does not handle fractions like "a quarter" on its own.

## How the owner will judge plan B

The owner will run a session like the slice's acceptance run, in a **fresh world**:
1. Make owl-folk, humans and perhaps a third species.
2. Set up a race or two.
3. Generate several characters, including at least one of mixed heritage, and judge how they come out.
4. Play a scene with them.

**Passing means:**
- created characters carry their heritage plausibly without the owner restating it;
- the character pages show clearly what's inherited and from where;
- in play, the AI uses inherited traits (an owl-folk character has wings and talons, not hands) and characters behave in keeping with their species' instincts;
- the anti-goals of plan A still hold: no worse than stock, and no slower turns.

## Goals

### Species

A new kind, `species`, with its own page in the World tab.
- **Origin.** An optional core field pointing at a thing (usually a lore entry, such as the god or event that made them), plus origin facts. The origin shows as a link, and the species appears in that thing's **Referenced in** list.
- **Numbers as core fields,** with timelines like every other core field, so they can change over story time:
  - `lifespan`: years, typical;
  - `adult_age`: years;
  - `measures`: a small set of named ranges such as height 3–4 ft or wingspan 7–9 ft, free-named per species. *My call:* a species defines its own measure names rather than a fixed list, because "wingspan" only makes sense for some species.
- **Fact categories:** `origin`, `physical`, `instinct`, `variation` (where the races differ), `general`.
- **Instincts are a species matter; learned behaviour is culture.** The owner: "Culture mostly, but species could have instinctive tendencies".
- **Facts are dated like any other.** For example, "lifespan fell after the plague of 500" applies only to scenes set after 500.
- **Generated prose** (a description), produced the same way as for other kinds.
- **Referenced in:**
  - other things that point at it through fields or fact references;
  - the scenes that include a character of this species.

  Detecting the species named in message text waits for mention records (plan D).

### Races

A new kind, `race`, with a core field `species`. It lives inside its species' page, in a **Races** section, and has its own page too.
- **Facts:** the same categories as a species. They hold what's specific to the race: coat or plumage, size, wingspan.
- **Numbers** narrow or override the species' numbers, field by field and measure by measure. For example, Snowy wingspan 8.5–9 ft. A number the race leaves unset falls back to the species.
- **Referenced in,** the same as species.

### Mixes

A new kind, `mix`, with core fields `parents` (exactly two) and `species` (derived from the parents, for listing).
- **Parents:** each is a species, a race or another mix. That's how a quarter-orc's parent can be a Half-orc mix.
- **Placement:** a mix is listed on **both** parent species' pages, in a **Mixes** section next to Races in the same area. The owner chose a separate section to keep them organised.
- **Facts and numbers,** the same as a race. A mix's facts describe the blend itself (for example, Half-orcs have tusks of half an inch to an inch).
- **AI drafting:** a mix can be drafted by the AI from its two parents (probe finding 4) and then accepted, edited or regenerated, like any create preview.

### Heritage on a character

Characters get a `heritage` core field instead of the main spec's separate `species` and `race` fields. It points at **one** thing: a species, a race or a mix. A character's culture stays the existing `culture` field.
- **One parent:** an ordinary character, such as Owl-folk · Snowy.
- **Two parents always go through a mix entry** (owner, 2026-10-20). The heritage picker lets the owner pick two parents, each a species, a race or a mix. If the world already has a mix of exactly those two, the character's heritage is that mix. If not, the owner is taken to draft, review, edit and accept the new mix entry first, and only then continues to the character, with their prompt kept.
  - **Why:** every character of a given mixed heritage then shares one settled entry. There's never a case of a mix entry made after three characters were already generated without it.
  - This applies to any two parents: two races of one species, two species, or a race and a mix.
- **Quarters** are half of a mix entry. A quarter-orc is a mix of Lowlander and Half-orc, so it's drafted the same way. There are no free-form fractions (probe findings 3 and 5).

### Inheritance

- **Order:** the character's own facts first, then their race or mix, then their species, then their culture. Within a mix, the mix's own facts come before its parents'. The character's own fact always wins. *My call:* the order between race, species and culture follows "the more specific wins".
- **Overrides are explicit links, not guesses.** An own fact can mark the inherited facts it replaces: Vasha's "blue eyes" replaces Snowy's "yellow eyes". Overrides come from two places:
  - the **Override** button on an inherited fact, which starts a new own fact pre-filled from it and linked to it;
  - **creation from a prompt,** where the AI is shown the inherited facts and marks any it contradicts. That needs a probe; see "Probes".

  Spotting conflicts automatically after the fact belongs to the decision model (plan F). *My call:* until then, an unmarked conflict shows both facts, and the AI sees both.
- **Every layer can override the one above it,** not just characters (*my call*, following "the more specific wins"):
  - a race's fact can override its species' fact, such as Snowy "white plumage" over a species-wide plumage fact;
  - a mix's fact can override either parent's, such as Half-owl's settled body over Owl-folk's "wings in place of arms" and Human's hands.

  Race and mix pages get the same **Inherited** section and **Override** button as character pages. Drafting a race or mix from a prompt marks overrides the same way character creation does (probe 1 covers it). A character inherits through a mix with the mix's overrides already applied, so a Half-owl never carries both bodies.
- **Dates apply through inheritance:** what a character inherits is read as of the scene's date. A species fact dated 500 reaches a character only in scenes set after 500.
- **Stale prose:**
  - a character's prose goes stale when anything it inherits changes, not just its own facts;
  - "since" lines cover inherited changes too, such as "since 500: owl-folk live to about 60".

### Life stage from numbers

A character's page shows their life stage, worked out from their age and their heritage's numbers: child, adolescent, adult or elder. The app also flags an age past the lifespan; this is a warning, not a block.

*My call:* elder starts at 80% of the lifespan, and adolescent at 75% of the adult age. A mix that leaves a number unset uses the average of its two parents.

### The pages

These follow the approved mockup.
- **Species page:**
  - the fields: origin link, lifespan, adulthood and measures;
  - the facts, with categories and dates;
  - the **Races** and **Mixes** sections, each with "+ New";
  - the generated description;
  - **Referenced in**, for entries and scenes.
- **Character page:**
  - the **Heritage** field as links, with the life stage beside the age;
  - the character's own facts;
  - an **Inherited** section below them: facts dimmed, each tagged with its source, each with **Override**. An inherited fact an own fact replaces is shown struck through, with a note.
- **Delete:** deleting a species, race or mix uses the existing reference check, which already lists fields that point at it.

### Create from a prompt

Every new kind can be created from a short prompt, the way characters, places and lore already are.
- **Species:** from a prompt. It produces facts and numbers. *My call:* it doesn't produce races automatically; the owner adds those from the species page.
- **Race:** from inside the species page. The species' facts are background, and the race fills in what's specific.
- **Mix:** from the two parents, plus an optional prompt. This is also the step the character create box sends the owner to when they pick two parents with no mix yet. Accepting returns them to the character's create box, with the mix as the heritage.
- **Character:** pick the heritage first, then write the prompt. The AI gets the inherited facts as background:
  - it writes only what's unique to the character;
  - it marks overrides.

  The prompt's own wording still wins, as today. *My call:* the heritage picker sits above the prompt in the create box. When the prompt names a species the world has, it pre-fills the picker, using the same name matching as scene setup.

### Cultures: moved to the next slice

The owner decided on 2026-10-20 to move cultures out of plan B. Species already show inheritance working from species to race, mix and character, and culture-to-character inheritance comes in the next slice. The owner's direction for that slice:
- **Cultures become ordinary fact-based entries,** created from a description in the World tab like species. The local model (Skyfall) writes their customs, beliefs, food and dress facts and their prose, which it does well.
- **The culture-file import handles only the language.** The language is the technical artifact: sounds, word rules and the lexicon. A precise instruction-following model is better at it, whether Claude outside the app or a local instruct model such as Qwen. The owner wants Qwen tested before the design settles, and accepts the friction of switching models for that step.

Plan B keeps what's already built: the lineage code treats a character's `culture` field as the last layer, so cultures slot in without rework.

### Characters invented by scene setup

Scene setup's invented characters (scene-local things) can carry a heritage too (*my call*). Otherwise an invented innkeeper in an owl-folk town would need its body spelled out, which is the "restated heritage" anti-goal.
- The setup prompt lists the world's species, races and mixes by name.
- Its reply gains an optional heritage per invented character, matched by name like other world things.
- `characters.py` resolves inheritance for scene-local characters the same way as for world characters.
- When make-real (promoting a scene-local character into the world) arrives, it carries the heritage over.

Probe 3 includes an invented character.

### Play

- The character sheet the agents read (`worldplay/characters.py`) is built from the character's facts plus their inherited facts, as of the scene's date, with overrides applied.
- **Prose sections map the categories:**
  - the character's `description` takes their own appearance and background facts, plus inherited `physical` and `variation` facts;
  - `personality` takes their own personality facts plus inherited `instinct` facts, together with the culture's customs once cultures arrive (the code path is ready in plan B).

  *My call:* culture customs go in `personality` and not `description`, because they shape behaviour.
- **No extra LLM calls on ordinary turns.** Inheritance is resolved in code.

## Non-goals (later)

- **Names:** the repeated-name problem (Maren and Brenna everywhere) waits for the cultures' name pool in phase 4. The owner noted it doesn't show up in scenes, only in isolated creation.
- **Cultures:** fact-based cultures, the language-only import and culture-to-character inheritance in the UI are the next slice (see "Cultures: moved to the next slice"). The glossary, naming and the culture review stay in phase 4.
- **Automatic conflict detection** between own and inherited facts: the decision model, in plan F.
- **More than two parents,** and free-form fractions.
- **Detecting a species named in a story message:** mention records, in plan D.
- **Layering for places** (a tavern inheriting from its town): the main spec records it as a direction, and it isn't in this plan.
- **Upgrading worlds from plan A:** worlds in the old format aren't upgraded. The owner will start a fresh world.
- **Scene titles:** still deferred to the scene-runner port.

## Anti-goals

- **Heritage that has to be restated:** if the owner must write "she has wings" in a Snowy owl-folk character's prompt for the wings to show up, inheritance has failed.
- **Hidden inheritance:** an inherited fact the AI uses but the character page doesn't show.
- **Slower turns,** or extra LLM calls on an ordinary turn.
- **Contradictory bodies:** for example, a character with both wings-for-arms and gloved hands because an override wasn't applied.

## Constraints

- **Everything in the main spec and in plan A's constraints holds:**
  - Guix and `uv run --no-sync`;
  - the fast testing loop: focused tests while iterating, the full plain suite once per task, browser tests at `-n 4` at the end of a task that changes UI;
  - strict mypy and no talemate imports in `src/talemate/world/`;
  - theme roles for colours, the Pinia worlds store and world-store ids;
  - generated prose is never fed back into fact extraction.
- **AI probes and AI tests need the owner's go-ahead.**
- **New world features are written in Python, not as nodes.**

## Probes (before the features they serve; ask the owner first)

1. **Species, race and mix creation from a prompt:** does it produce plausible facts and sensible numbers, and does a race stay consistent with its species?
2. **Character creation with inherited background:** does the AI write only what's unique, and does it mark overrides correctly as ids? Test a race heritage and a mix heritage.
3. **Play with inherited facts:** a short scene check that the narrator and conversation agents honour the inherited body (wings, not hands) and instincts.

The heritage-blending probe already covers on-the-spot blending and mix drafting.

## Left to the builder

- The schema and storage of `heritage`, `parents`, `measures` and override links. Override links may be a fact field or a link table, as long as they're undoable like other edits.
- The exact rules in the create templates, guided by the probes. Start from the probe's "guided" rule when drafting a mix.
- How Referenced in queries the scenes that include members.
- The task order, as long as each probe comes before the feature it serves.
