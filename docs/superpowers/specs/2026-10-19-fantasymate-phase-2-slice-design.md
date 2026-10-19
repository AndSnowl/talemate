# Fantasymate phase 2, plan A: the playable slice

Date: 2026-10-19. Status: design, awaiting the owner's approval.

This is the first plan of phase 2 in `2026-10-18-fantasymate-world-data-model-design.md` (the
"main spec"). The main spec stays the authority for the data model. This document decides **what
the first phase-2 plan builds, in what order, and how we know it worked**, and it records the
product picture the owner gave on 2026-10-19.

## Intent

**The owner's rule:** "at the end of the day we need to cater to the local LLM; if it doesn't
work for that then it simply doesn't work."

So phase 2 doesn't build every layer before anything can be played. It starts with a **thin
playable slice**, so the owner can gauge, as early as possible, how their local model does with
world-backed context. The rest of phase 2 widens the slice in later plans. The cost, accepted by
the owner: some pieces are built simply first, then properly later.

## The product picture (owner, 2026-10-19)

**The first evening after this plan:** a tryout, not a full story.
- Make a world.
- Generate a few characters, and some places and lore, in the World tab, then look at how they
  came out.
- Create a scene that brings in a pre-generated character.
- Play a few turns from a simple premise; the story probably isn't finished.

**The finished product (later phases):**
- Start a world. Create cultures, two intelligent species (humans being one), and races or
  variants of each.
- Generate characters with a culture, a species and a race, then places.
- Play a first scene that adds to the world.
- Add magic, gods and a major world event or two early on, and expect scenes to draw on them.
- Start the map during or after the first scene.
- Mostly play in order through time, but sometimes jump to a distant place before knowing where
  it sits relative to the others.

## How the owner will judge the slice

These are the slice's acceptance tests. They are the owner's own, and they need the owner's local
model, so they are run by the owner, not in CI.

1. **Parity, bare.** Play a prompt the owner has played before in Talemate's Simulation v2: a
   bare setup describing the characters present and the place. It should feel about the same as
   stock Talemate. The baseline is the owner's stock upstream install.
2. **Parity, with world characters.** The same prompt, this time with pre-generated world
   characters. It should feel about the same, since the AI gets about the same amount of
   information.
3. **The world's clock works.** Add a dated fact to a character that the prose would mention,
   such as an irritating scar or a lost limb.
   - A new scene set **after** that date should pick it up at some point.
   - A scene set **before** that date should not.

Test 3 is what makes the slice more than a reskin. It needs dated facts you can edit, a start
date chosen for the scene, and context built from the world as of the scene's date.

## Goals (what the slice includes)

1. **Worlds home, minimal.** List worlds, create one, and open it.
2. **World tab, for characters, places and lore entries.**
   - **Create from a prompt** (owner). Each kind has a "describe it, then create" box, with
     optional pickers for core fields already known.
     - The AI treats the prompt as intent, the way Talemate's `@` action treats scene input:
       better wording and plausible invented detail (what's in the town, why it's half-flooded,
       a hint it's shady). It rarely drops what the owner wrote.
     - Under the hood (my call): prompt → a full fact list → prose from those facts. Invention
       happens once, at creation, and the owner sees the prose. Generated prose is never fed
       back into extraction; that was the probe's warning.
     - The owner can accept, regenerate, edit, or retry with a new prompt. No per-fact review is
       forced.
   - **A thing page:** core fields; dated facts that can be added, edited and ended, each with a
     category; generated prose with a regenerate button; and a date picker for "viewing as of".
     The mockup is the character page from the 2026-10-19 brainstorm (gruvbox dark).
   - Cultures stay out of the World tab's create box; they're made through the culture skill.
     The cultures features stay switched off, as the main spec says for phase 2.
3. **Scenes stored in the world database.**
   - Messages have stable ids and in-world dates (start date plus time passed). Time passage
     works.
   - The slice keeps **one linear path per scene** (my call). The tables are shaped for branches,
     but the fork UI and branch logic belong to a later plan.
   - Saving and loading go through the world database. No scene JSON files, no shared context.
4. **Creating a scene from one prompt** (owner).
   - The prompt is a rough storyline: who you are, where, doing what. It can be vague or
     specific.
   - **Names are highlighted as you type** (owner). A name that matches a world thing is
     highlighted and picks the first match. Hovering shows the pick, with options to choose a
     different thing or treat the name as new. Plain string matching is fine here, because the
     owner sees the result straight away.
   - Pickers for who the player plays and when the scene starts. The start defaults to after the
     latest scene in the world.
   - **A setup step before play:** who, where, when, and what was pulled in from the world or
     invented, with Start, Regenerate and Edit.
   - Whatever the prompt leaves open is first sourced from the world (search over the world
     index at the scene's date), and otherwise invented as a **scene-local thing**. Promotion of
     those comes with the inbox in phase 3; in the slice they just stay in the scene.
5. **Playing.** The narrator, the conversation agent and the `@` action work on the new data. The
   `@` action is a must-keep (owner): it is how the owner writes. The context the AI receives is
   built from the world **as of the scene's current date**, plus the scene's own things and
   history.
6. **"Continue in a new scene"** (owner agreed). It starts the next scene where this one ended:
   same date, place and people present, plus a summary of what happened. The owner types only the
   next goal. The recommended way to play is one goal or arc per scene, because the world carries
   the continuity.
7. **The golden scene recording gets richer first.**
   - Today's recording has no premise, location, world state or pins.
   - Before the slice changes scene or context code, the recording covers a scene with a premise,
     a place, and two characters with facts.
   - The slice's changes then show up as reviewed diffs of exactly what the AI receives.

## Non-goals for this plan (they come in later phase-2 plans)

- Species and races, and inheritance of facts from species, race and culture. These are the
  **next plan**, because the owner's finished-product picture leans on them.
- Fact references and knowledge records, and knowledge-aware context.
- Forking, branches, and scene state as of a message.
- Presence and away bridges.
- The director, tracked states, pins, layered history, and the world-state snapshot and its
  highlights.
- The node editor's data nodes.
- The decision model and the Laya probe.
- Events as their own kind with dates (lore entries cover them in the slice), items, and images.
- The upstream ports listed in the main spec.

The app may be broken outside the slice's path. Anything not on the path above may be left
switched off.

## Anti-goals

- **Worse than stock.** Acceptance tests 1 and 2 feel noticeably worse than Simulation v2 on the
  same model. If they do, the first fix is in the AI-handoff layer (prompt assembly), not the
  schema, as the main spec says.
- **Slower turns.** Turns take noticeably longer than in stock Talemate. The slice must not add
  LLM calls to an ordinary turn. Creation and scene setup may take longer, because they are
  one-off steps.
- **Silent invention entering the world.** Invented things stay scene-local in the slice, and
  nothing is promoted automatically.

## Constraints

- **Everything in the main spec holds,** including its "Code health → During the rework" rules:
  - move each piece of `Scene` you rewrite into its own module;
  - give agents a narrow scene context rather than the whole `Scene` where they're touched;
  - use world-store ids;
  - put a small Pinia store behind new screens;
  - use theme tokens.
- **The owner's testing rule:** fast loop, focused tests while iterating, and the full suite once
  per task. The browser suite runs at `-n 4`, once at the end of each task that changes UI. AI
  tests and probes need the owner's go-ahead.
- **Local models only** (koboldcpp, currently Skyfall-31B).
- **Probe the AI before building** (owner's principle). Two probes come before their features:
  1. **Create from a prompt:** short prompts for a character, a place and a lore entry → facts →
     prose, judged for plausible invention, keeping the owner's intent, and prose quality.
  2. **Scene setup:** a storyline prompt plus a small world → who, where and when, and what was
     sourced versus invented.

## The how that's decided

- **Reuse Talemate's play engine; swap what's underneath** (my call). The slice keeps the
  existing game loop, agents and prompt templates. What changes is underneath:
  - where scenes and characters come from and where they're saved (the world database);
  - how the AI's context is put together (from world views as of the scene's date).

  This is the smallest change that lets acceptance tests 1 and 2 compare like with like. The
  existing `Scene` object is the coordinator in the slice; each part the slice rewrites
  (persistence, the message list, the character source) moves into its own module, per the
  code-health rules.
- **Characters in play are built from the world thing** at the scene's date (fields plus facts
  plus cached prose), into whatever object the existing agents read. My call: an adapter at that
  one boundary. This is not an adapter to the old stores, which the main spec rules out.
- **What the AI sees for a character's dated facts** (my call). This keeps acceptance test 3
  honest without adding LLM calls to turns:
  - Adding, ending or editing a fact regenerates the prose for the affected stretch of time in
    the background, outside play.
  - Scene setup makes sure prose exists for the scene's start date.
  - If a scene's date crosses into a stretch that has no fresh prose, the AI gets the cached
    prose plus short lines for the facts that started or ended since that prose, such as "since
    314: lost her left eye". No LLM call is made mid-turn.
- **History in the slice** (my call): plain history summarisation (the archive) stays on, so
  longer runs keep working. "Continue in a new scene" reuses that summariser for its summary of
  what happened. The director, tracked states, the world-state snapshot and pins stay off.
- **Cultures in the slice** (my call): the culture picker is hidden, and characters have no
  culture yet. Culture things come into the world database in plan B, alongside species and race,
  as a minimal import of the culture skill's `culture.json`. Inheritance needs them there.
- **Parity against Simulation v2** (my call). In Simulation v2 the owner's first message is
  sent to a function-calling "computer" step. That step sets the environment, the player's
  persona, the AI-played characters and a **goal**, and then play is close to stock. The slice
  plays the owner's premise in Talemate's default scene loop, with the new scene setup doing the
  computer's job. The setup **keeps a goal**, generated from the prompt and editable, stored with
  the scene and given to the AI as the Suite did, because the owner found it useful. Mid-play
  "computer, …" commands are not in the slice; they suit a later Suite-style runner.
- **Name matching in the scene prompt** is plain string matching against world thing names, as
  the owner chose. Mention records for messages come with the later branch and knowledge work.

## Order of work (the builder may refine it)

1. Enrich the golden recording.
2. The two probes, run with the owner's go-ahead.
3. Scene and message tables in the world database, with saving and loading through it.
4. The character adapter, and context assembly as of the scene's date.
5. The World tab and thing pages for characters, places and lore, with create from a prompt.
6. Scene creation (prompt, name highlighting, setup step) and the Worlds home.
7. Play: the narrator, conversation and `@` on the new data; "continue in a new scene".
8. The owner runs acceptance tests 1–3.

## Later phase-2 plans, in order

- **B:** species and races (in the UI, races sit inside their species' page), and inheritance:
  a character's species, race and culture facts fill in what the character doesn't say, and the
  character's own fact wins on conflict. It also brings create-from-prompt with that background.
- **C:** fact references and knowledge records, with knowledge-aware context.
- **D:** branches and forking, scene state as of a message, presence and away bridges, and
  mention records.
- **E:** the remaining existing features (director, tracked states, pins, layered history, world
  state and highlights) and the node editor's data nodes.
- **F:** the decision model (first a Laya probe) and the phase-2 upstream ports.

## Left to the builder

- Table shapes for scenes and messages.
- How the adapter fits the existing agents.
- The Pinia store's shape.
- The prompt wording for creation and scene setup. Those prompts are shaped by the probe results.
