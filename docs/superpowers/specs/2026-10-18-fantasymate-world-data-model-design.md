# Fantasymate project 3: the world-first data model

Date: 2026-10-18. Status: design, awaiting the owner's approval.

This is project 3 of the fantasymate fork (projects 1 and 2, rebrand and appearance, are in
`2026-10-18-fantasymate-rebrand-and-appearance-design.md`). That document's "Later: project 3"
section recorded earlier agreements; the ones that still hold are restated here so this document
stands on its own. Where this document and that section disagree, this one wins.

## Intent

The owner plays roleplay adventures inside one persistent fantasy world that keeps growing. Each
adventure should change the world, and the world should carry those changes into the next one.

Talemate was built scene first. A "world" is a shared-context file inside one project folder, and
sharing works by copying characters and entries into every scene and back on save, with the last
save winning. Nothing has a stable id (characters are keyed by name, message ids are renumbered on
every load, history ranges are list positions), time is a duration counted from each scene's start
with no dates, and forks drop the world entirely. Yet Talemate's mechanics (precise time skips,
character cards, layered history, a shared world) almost beg for a deep, consistent world.

Project 3 turns that around. The **world is the single source of truth and contains everything**.
Scenes are children of a world: they build their own context, refer to world things by true
reference instead of copies, and promote what matters back to the world through an inbox. Every
world thing has a stable id and a **timeline**, so it can be seen as it was at any in-world date.

**Hard fork.** From project 3 on, fantasymate no longer tracks upstream Talemate. Core code (the
scene model, save model, shared context, history, agents' data access) is reworked freely. This is
a different app now.

## Goals

- A world is the top-level thing. It holds scenes, characters, places, cultures, items, events,
  lore entries and the calendar.
- Everything has a stable id. References are by id, so a rename changes one record and is seen
  everywhere.
- Every world thing can be viewed **as it stood at any in-world date**. Following a link from an
  old story shows the thing as it was at that story's date.
- A scene refers to world things without copying them, adds its own scene-local things and
  changes, and proposes promotions to the world through the inbox.
- Approved changes can be undone by where they came from, so the owner can swap one fork's changes
  for another's.
- The existing Talemate systems the owner uses keep working on the new data (see "Existing
  features").

## Non-goals

- **No import of old Talemate saves.** The owner starts fresh worlds. (This drops the earlier
  "unsorted scenes" and shared-context migration ideas.)
- No magic systems, factions, gods or plugin-defined kinds yet. The storage must make adding kinds
  later cheap, but none are built now. Until then, lore entries hold that material.
- No keeping the app playable between phases. It may be broken until phase 2 is done. (Owner.)
- No hand-editable world files. The world lives in a database the app manages. (Owner.)

## Watchlist (failure modes to keep an eye on, not hard rules)

The owner's view: much of this depends on how the local AI behaves in the new setup, which is
trial and error. Watch for these and fix or pivot as they appear:

- **Inbox fatigue**: so many approvals that the owner stops reading them.
- **Slower play**: extraction, prose regeneration and promotion checks add waiting between turns.
- **Bookkeeping instead of story**: world screens feel like a spreadsheet to maintain.
- **Silent canon**: something enters the world (an AI-invented detail, say) that the owner never saw.
- **Worse AI context**: the storyteller knows less or contradicts itself more than stock Talemate.

**Baseline for comparison.** Keep a stock upstream Talemate install
(https://github.com/vegu-ai/talemate) to play comparable plots side by side and judge whether
prose, creativity and ambition get better or worse.

**Guiding principle (owner).** Catering to the AI should, wherever possible, be done in the layer
that hands data to and from the AI (context assembly, extraction and generation prompts), not by
reshaping the data model. Keep that layer separate from storage so it can be tuned without schema
changes.

**Probe the AI before building (owner).** Before fully implementing any feature that leans on the
model, first run a throwaway probe against the owner's local model to get a feel for how it
performs. Phase 0's round trip is the first; others include importance judgement, prequel
contradiction checks, the invented-fact check, and extracting promotion candidates from a scene.
Probes are cheap harnesses with no storage, they are AI tests (ask the owner before running), and
their results shape the prompts and the plan for that feature.

## Constraints

- Python backend in `src/talemate`, Vue frontend in `talemate_frontend`. Keep using them.
- Local models (the owner runs koboldcpp). Tests that call a real model stay separate from the
  plain suite, and the owner is asked before they run.
- The dev machine runs Guix; see `docs/dev/local-testing.md`.
- New screens use the theme tokens from project 2.
- The culture work (`src/talemate/cultures/`) is merged on `main` and is the closest thing to a
  world-level store today: ids on cultures, places and glossary entries, atomic writes, data never
  copied into scenes.

## Storage

- **One SQLite database per world** (owner: SQLite, managed by the app), with images and other
  files in a folder beside it. Scenes live inside their world's database, not in files of their
  own. (My call: one file per world, rather than one database for everything.)
- The search index the AI recalls from (chromadb today) stays a **derived index**, rebuilt from the
  database. It is never a source of truth.

## The shape of a world thing

Every world thing, of every kind, has the same general shape. A kind only names its core fields
and fact categories. This is what keeps future kinds (magic, factions, plugins) cheap. (My call on
the mechanism; the owner asked that the list be extensible later.)

A world thing has:

1. **An id** (stable, never reused) and a **kind**.
2. **Core fields**: a small set of hard data points. Each core field has its own timeline: a list
   of values, each true from an in-world date onward until the next value.
3. **Facts**: an open-ended list. This is where most of what a thing *is* lives. (Owner: "a
   character is an open-ended collection of facts", with solid data points beside it.) Each fact
   has:
   - text, which may contain **references** to other world things by id;
   - a **category** (for characters: appearance, personality, background, ability, relationship,
     and so on; my call, needed so prose can be organised);
   - a **from** date and an optional **until** date; either end may be open ("always", "still
     true");
   - a **source** (see "Two clocks").
4. **Generated prose**: readable text (a character's description and personality) written by the
   AI from the facts true at a given date, cached (see "Generated prose").
5. **Images**, each dated (see "Images").

References are stored as ids and shown with the name the referenced thing had **on the date being
viewed**. Renames never touch text.

**References can point at a fact as well as a thing** (owner, 2026-10-19). A fact has a stable
`fact_id`, which is kept across corrections, so other records can point at one specific fact:
"Oskar knows ⟨that Maren lost her eye⟩", an event that cites the facts it changed, a pin on one
fact.
- In text the token is `[[fact:<fact_id>]]`, alongside today's `[[thing:<id>]]`.
- The reference index records which kind of target it points at.
- A fact reference renders as the fact's text on the viewing date, or as a short label when it
  is used inline.
- A reference to a fact that has ended or been removed renders as it stood at the viewing date,
  and as "⟨unknown⟩" if it never existed then.

### Knowledge: who knows a fact

Owner, 2026-10-19, following the upstream review in `docs/ideas/upstream-pr-279-review.md`.

A fact is world truth. Who knows it is a separate, dated record, so a secret can exist in the
world without every character knowing it.

- **Common knowledge:** a fact can be marked common knowledge, meaning everyone in the world
  knows it (the default for most lore and public events). An optional scope narrows it to
  members of a culture or another group thing, for example "every Lowmarsh child knows the flood
  song".
- **Knowledge records:** otherwise a fact is known only by the characters with a *knowledge
  record* for it. A record has:
  - the knower (a thing id);
  - the fact (a fact id);
  - a from date, and an optional until date for forgetting or being deceived;
  - a source, as on every change.

  Knowledge records are world changes like any other. They are dated on story time, stamped with
  their source, go through the inbox, and can be undone by source. In undo terms each one is its
  own slot.
- **Facts about a character are known by that character,** unless the fact is marked as hidden
  from them (an unknown parent, a curse they don't know about). (My call.)
- **How the AI uses it:**
  - When context is built for one character (their dialogue, their decisions), only facts that
    character knows on the scene's date are given as their knowledge.
  - The narrator and the director see world truth, labelled with who knows what, so they can
    write dramatic irony without leaking it into a character's mouth.
  - Exactly how this is phrased in prompts is the AI-handoff layer's job; see the guiding
    principle.
- **Learning in play:** a character learning something in a scene is a scene-local knowledge
  record anchored to the message, promoted through the inbox like any other change. That is how
  knowledge carries across scenes.

### Kinds for now

The owner confirmed this list as complete for now:

| Kind | Core fields | Notes |
|---|---|---|
| Character | name, born, culture, voice | Age is computed from born and the viewing date, never stored. Name has a timeline (new names, titles). Description and personality are generated prose, not fields. |
| Place | name, kind, parent place, cultures (with shares) | One place kind replaces the three today (world-state places, the cultures' `places.json`, manual entries). A tavern sits inside a town inside a region. Map position comes later with the map feature. |
| Culture | name, language | Customs, holidays and the rest move onto this shape. The glossary keeps only language material (words, phrases, true names, renderings, the pool of unused names); people and places are things linked by id. |
| Item | name, owner | Things that matter, such as a sword handed down. |
| Event | name, date or span, place | Dated things that happened. A scene's history summary becomes an event when promoted. The "remember the ferryman?" recall reads from events. |
| Lore entry | name | Free-form world facts; replaces today's world entries. |
| Species | name | Added 2026-10-19 (owner). Intelligent species, such as humans; most settings have two or more. |
| Race | name, species | Added 2026-10-19 (owner). A variant of a species. In the UI it lives inside its species' page. |

**Characters gain the core fields species and race** (added 2026-10-19).

**Inheritance** (owner, 2026-10-19). A character takes on the general facts of their species,
race and culture, so a creation prompt only needs what makes this character unique. The
character's own facts come first, the species, race and culture facts fill in what the character
doesn't say, and the character's own fact wins on conflict. My guess, recorded as a direction: the
same layering generalises to the things a thing points at in core fields (a tavern takes on its
town, the town its region).

**Create from a prompt** (owner, 2026-10-19). Every kind except cultures, which are made through
the culture skill, can be created from a short prompt:
- The AI treats the prompt as intent, the way the `@` action treats scene input.
- It invents plausible detail generously within the chosen background things.
- The owner accepts, regenerates, edits or retries.
- The pipeline is prompt → facts → prose. Invention happens once, at creation.

**Later, with the map** (owner, 2026-10-19): two places can be in the same world before their
layout relative to each other is known. The map must allow places that aren't placed yet, or that
have unknown distances between them.

The **calendar** is world-level configuration rather than a thing: month and weekday names, eras,
holidays. It follows `docs/ideas/world-calendar.org`: Earth lengths for days, weeks, months and
years, so Talemate's time arithmetic keeps working, with names and eras per world (and later per
culture).

**Relationships** are relationship-category facts on a character that reference another character
("Maren → ⟨Oskar Dell⟩: owes him a life-debt"). They are always between named characters, never
"you"; the player can play anyone. X → Y and Y → X are separate facts.

## Two clocks

Every change carries two stamps:

- **Story time**: when it is true in the world (the fact's from/until, the core-field value's
  date).
- **Source**: where it came from (manual edit, or scene + branch + message) and the order in which
  it was approved into the world (a world revision number).

The two answer different questions:

- "Show me Maren as she was in my first story" reads along **story time** at that scene's date,
  using everything the world now knows. A prequel played a year later can add a scar to Maren's
  past, and the first story's link then shows it. (Owner: "as they stood at that place in time".)
- "Undo fork E's changes, I want F's" reads along **source**: remove everything E contributed,
  wherever on the calendar it landed.

A scene in play reads the world at its own date **and** at the world revision it has accepted (see
"World changes while a scene is away"). So queries are by both clocks.

**Dates** are absolute in-world instants on the world's calendar (my call: stored as a count from
a world epoch, rendered with the calendar's names). Facts often have imprecise starts ("since she
was a teenager"), so a date carries a precision (year, month, day, exact). An open start means
"always".

## Scenes

- A scene belongs to one world and has an **in-world start date**. (My call: it defaults to the
  latest date any scene in the world has reached, and the owner can change it. A scene may start
  before older scenes: prequels are expected.)
- A scene is a **tree of messages**. A fork is a new branch from any message, not a copied save.
  Each branch knows its parent and the message it split at.
- **Every message has a stable id and an in-world date**: the scene's start date plus the time
  that has passed by that message (Talemate's time-passage messages provide this). Messages with no
  time passage between them share a date.
- **Mention records.** When a message is created, record which thing ids it mentions and where.
  Highlights, the inbox's importance signals and recall read these records instead of matching
  name strings. Past message text is left exactly as written; a rename doesn't rewrite story text.
  (My call: this settles the earlier open question about rename policy for old story text.)
- **Scene-local things and changes** use the same shapes as world ones (a new thing, a new fact, an
  ended fact, a new core-field value), scoped to the scene and **anchored to the message** where
  they arose. A branch sees only the local changes on its own path.
- **Scene state as of a message** (2026-10-19, from the upstream review). Every per-scene state
  is anchored to messages, so branching at message 40 restores it as it was there. That covers:
  - game state;
  - agent state;
  - the world-state snapshot and tracked-state answers;
  - pins;
  - layered history summaries;
  - which character the player is playing.

  Storing it as changes anchored to messages (my call) makes it work like scene-local changes:
  a branch sees the state on its own path, up to its fork point.
- **Presence and absence** (2026-10-19, from upstream's "character knowledge, standard mode").
  Each message records which characters are present. When a character comes back after missing
  part of the story, two things are given to them automatically:
  - a short "away for 2 days" bridge, exact because messages carry dates;
  - what happened while they were gone, drawn from history.

  This costs no extra LLM calls. Presence also feeds knowledge: a character present for a
  message can learn what was said in it.
- Inside a scene, a world thing is seen as: the world's version at the scene's current date and
  accepted revision, **plus** any world changes sourced from this scene's current path (approved
  after that revision), **plus** the scene-local changes on the current path layered on top. (My
  call: approving a scene's own request never pulls unrelated world changes into it.)
- **Editing, regenerating, deleting and rewinding messages** (my call):
  - Edit and regenerate change a message **in place**; earlier versions are kept as versions of
    that message, not as branches. Only an explicit fork makes a branch, so the tree and the
    path-following inbox don't fill with throwaway branches.
  - When a message's text changes, the scene-local changes, mention records and **pending**
    requests anchored to it are re-derived from the new text (the old ones are dropped).
  - Deleting a message drops what was anchored to it. Rewinding is a fork from the earlier
    message.
  - **If world changes were already approved from that message** (owner): before the edit,
    regenerate or delete happens, the app asks whether the owner is sure, and offers to revert the
    world changes that came from it (using undo by source). The owner's reasoning: this is
    usually unintentional because the two actions contradict each other, and when it is
    intentional the world changes probably should go too.

### The character kind in full

Today's `Character` fields map like this (my call):

| Today | In the rewrite |
|---|---|
| description, base attributes, details | facts (description becomes generated prose) |
| example dialogue, dialogue instructions | facts in a *speech* category; the conversation prompts read them from there |
| color | core field (display only) |
| avatar, cover image | dated images |
| visual rules, visual finalizers | per-thing visual settings, alongside its images |
| greeting text | the scene's introduction, not the character |
| is_player | per scene branch: which character the player is playing there |
| culture | core field (already listed) |

## Promotion and the inbox

This carries forward the earlier agreements, adapted to the timeline model:

- The scene's AI decides what scene-local material deserves to join the world and files it in the
  inbox. Scenes never write the world on their own.
- **An inbox request is a bundle of changes** (the shapes above), anchored to a message, with the
  AI's short reason.
- **On approval** the changes go onto the world things' timelines, stamped with story time and
  source. The scene's local layer for them dissolves, because the world now says the same thing. A
  scene-local thing that's promoted keeps its id and becomes a world thing.
- Each request can be approved, edited then approved, rejected, or **kept in the scene only**. A
  rejected or scene-only change stays local to that scene and path permanently.
- **The inbox follows the fork path.** On F in A→B→D→F it shows requests from A, B, D and F, never
  sibling branches. A combined inbox lists all scenes' requests, each marked with its scene; each
  scene contributes the path it was last left on.
- **Requests are ordered changes.** A later request about the same thing is just a second change.
  If the first was rejected, the later one becomes the first sighting.
- **The AI judges importance** to keep inbox fatigue low: a major character goes to the inbox, a
  throwaway one stays in the scene. Signals: how often the thing is named, whether it speaks, ties
  to named characters, recurrence across scenes, how much the player engages with it. The AI
  re-checks at milestones so an unimportant character who becomes important is proposed later.
  Low-importance finds sit in a collapsed "minor" section so a wrong call can be recovered.
- **Prequel conflicts.** A change whose story time falls before things already established later
  on the calendar, and that contradicts them (killing Maren in 300 when later scenes have her
  alive), is **flagged in the inbox as a conflict and the owner decides**. (Owner.)
- **Branch conflicts.** Approving from branch E after approving from F warns of possible conflict.
  The changes at risk are those approved from nodes that are not ancestors of both. The owner can
  undo those or keep both.
- **Undo by source** reverts only what it needs to. A fact or field changed again afterwards, by a
  later approval or a hand edit, is listed for the owner instead of being reverted silently.
- The existing culture review and the "suggestions" view are absorbed into the inbox. The cultures
  AI's findings (names from snapshots, culture guesses) become scene requests instead of being
  written straight into the world glossary.
- Names of throwaway characters and names in pending requests still count as "in use" across the
  whole world, so two scenes don't get the same generated name.
- A scene-only place still needs a parent world place or its own culture mix, so naming and the
  culture context keep working there.

## World changes while a scene is away

A scene stays pinned to the world revision it last accepted. When the owner reopens a scene and the
world has changed since, the app **asks whether to bring the changes in**. (Owner.)

- On yes, the scene's accepted revision moves forward. Only what's affected changes: a world change
  that has nothing to do with the things this scene uses goes in quietly. (Owner.)
- (My call) If an incoming world change collides with this scene's own local changes, the collision
  is listed so the owner can choose. Past messages are never rewritten.

## Editing in the world screens

- Editing while viewing the **latest** date changes the latest state: a new fact or core-field value
  from that date, or ending a fact. (Owner.)
- Editing while viewing a **past** date edits that point in time. (Owner.) Because the facts hold
  spans, the two natural edits are: correct a fact's text or span (true for its whole span), or end
  a fact and start a new one (a change from that date). The screen offers both.
- Something true for a long time ("has had a heron tattoo since she was a teenager") is one fact
  with an early or open start. (Owner's example; it's what drove the facts design.)
- Manual edits have source "manual" and appear on timelines like any other change.

## Generated prose

- Prose (a character's description, personality and so on, assembled by fact category) is
  **generated per stretch of time** and cached. It only needs regenerating when a relevant fact or
  core field starts or ends, not for every date viewed.
- The owner **can hand-edit cached prose** to fix wording; this is expected to be rare. The usual
  fix is to put the exact wording into a fact and regenerate. (Owner.)
- (My call) Hand-edited prose is marked as edited. If the facts under it change later, regenerating
  warns first and gives the edited text to the AI as a reference, so the wording survives where it
  still fits.
- **Invented facts.** After generating prose, a second AI pass lists claims in it that no fact
  backs. Each can be **cut** from the prose or **adopted** as a new fact. An adopted fact records
  that it came from that prose, so it doesn't mark the prose outdated. Support both; which is the
  default gets settled by testing.
- **Creating a thing** accepts a sentence, freeform prose, or a pasted character card. The pipeline
  always ends with facts as the truth: input → facts → prose → the owner checks the prose. The round
  trip doubles as a check that extraction missed nothing.

## AI context

- This is where facts pay off on context budget. The scene's AI pulls only the facts true at the
  scene's date that are relevant to what's happening, not whole cards. Each fact is indexed on its
  own for recall. Cached prose is the cheap fallback when a broad sketch is enough.
- One prompt budget is shared across features rather than each feature capping its own (world-first
  steering competes with the ~350-token culture section).
- During play, the storyteller can follow links from the current place to its owner, that
  character's facts and their shared history.
- Per the guiding principle, this context-assembly layer sits apart from storage.

## Images

- Any thing that can be pictured (characters, places, items, cultures for dress or heraldry, and so
  on) can have images, generated through Talemate's existing visuals.
- **Images are dated.** Viewing a thing at a date shows the latest image on or before it, so Maren's
  portrait viewed from 312 still shows both eyes. (Owner.)
- When a new fact changes how something looks, the app **offers a new image** from that date.
  (Owner.)

## Existing features

The owner wants a more focused, improved Talemate, keeping the systems that don't clash. All of the
following were agreed:

| Feature | In the rewrite |
|---|---|
| World state snapshot and highlights | Same job; every highlight links to a world or scene thing by id, shown at the scene's date. New things it spots become scene-local things, making it the main source of inbox candidates. |
| Tracked states | Answers become short-lived scene facts anchored to messages, marked *state* so they're never offered for promotion. |
| Pins | Pin a thing or a single fact in a scene. |
| Suggestions | Absorbed by the inbox. |
| Layered history | Stays inside the scene, pointing at message ids instead of list positions. A summary becomes a world event when promoted. |
| Game state | Per scene and per branch, so a fork sees its own path's values. |
| Node editor | Kept. Nodes that read or write characters, entries or history are rewritten for the new data (the largest part of phase 2). |
| Director | Kept, reading the new context. |
| Voices | A core field on characters. |
| Agent settings and state | Settings per world with per-scene overrides; agent state per scene branch. |
| Search index | Rebuilt from the world database, facts filtered by the scene's date. |
| Visuals | Kept and extended (see "Images"). |

## Navigation (earlier agreement, unchanged)

The home screen lists worlds first, each card showing its recent scenes. A World tab works with no
scene loaded. Top navigation becomes **Worlds · World · Story · Scene · Inbox**, with Templates,
Prompts and Mods moved to a **Tools** menu.

"Story" was named in the earlier brainstorm but never defined. For now there is no story
container, only scenes (owner), and the builder may leave the Story tab out until the feature
below exists. (My call: if a tab is needed in the meantime, it shows the current scene's branch
tree.)

**Later, at the end of the work list (owner): stories as reading order.** A story groups scenes in
an order the owner chooses, which can differ from calendar order, such as a flashback story that
would spoil later ones if read first (the way *New Spring* sits in *The Wheel of Time*). Nothing in
this design should block it. Scenes already carry dates; a story would add a container and an
ordering.

## Decision model

Upstream 0.40 adds a decision model: a small classifier that answers yes/no, choice and score
questions with a confidence, and falls back to the LLM when it is off or unsure. That suits our
many judgement calls:
- importance for the inbox;
- the invented-fact check, which the phase-0 probe showed the LLM can't do reliably;
- prequel conflict checks;
- "bring in world changes?";
- whether a tracked state needs re-asking;
- the editor's repetition and verbal-tic checks.

- **It stays local (my call).** Story text is never sent to a hosted provider by default, which
  matches the owner's local-model setup. The candidate provider is Laya, a local non-generative
  decision model. Whether its API fits upstream's decision-model interface is the first probe.
- **Every judgement goes through it,** with the LLM as fallback. So each "AI judges X" feature
  in this spec is built against one decision interface, not ad hoc prompts.
- Per the "probe the AI before building" principle, each judgement gets a probe against the
  decision model first, and then against the LLM fallback.

## Upstream features to port

Reviewed 2026-10-19 against upstream PR #279 (Talemate 0.40). The full notes are in
`docs/ideas/upstream-pr-279-review.md`. Upstream code is keyed by names and message positions, so
these are **reimplemented on our data model**; copying is reserved for self-contained parts (the
decision model's core, the koboldcpp client changes, the memory reranker). The phase for each is
listed under "Phases".

| Feature | What it gives us | Phase |
|---|---|---|
| Decision model | one local interface for every judgement call | 2 (probe first) |
| Scene state as of a message | branches restore game/agent/world state at the fork point | 2 |
| Presence and away bridges | re-entry context with exact durations, no LLM calls | 2 |
| Prompt-override compatibility checker | flags user prompt overrides that break after template changes | 2 |
| koboldcpp client improvements, local memory reranker | better local-model behaviour and recall | 2 |
| Editor decision checks (repetition, tics) | quality guard without long LLM calls | 2–3 |
| Help chat permission gating | the help agent asks before changing things | any time |
| Learned knowledge, "Known by" view | knowledge carried across scenes through the inbox | 3 |
| "Add to world" from selected text, "make real" | owner-picked inbox candidates | 3 |
| Scene background | rebuilt on dated place images, not a per-scene setting | 5 |
| Replay | re-reading a branch, which later becomes the reader for stories | 5–6 |
| Character perspectives | per-character inner views of a passage | later, after a probe |

**Not ported:** upstream's scene revisions. They take one deduplicated snapshot per save and fork
by copying the save file, and they can't undo a specific change. Our message-level branches and
undo by source cover them. The one useful idea, scene state as of a point, is above.

**Watch:** upstream now targets strong reasoning models (its smallest "known good" local models
are 26–31B with reasoning on). Features that need one long structured call per passage
(perspectives) go against our watchlist ("slower play") and only come after a probe on the
owner's model.

## Scene runners (owner, 2026-10-19; a later phase)

The node-graph runtime that Talemate uses for the game loop, the `@` action and much agent
behaviour is replaced, in a later phase, by **scene runners** written in Python. The owner prefers
code to nodes here: the graphs are large (96 and 100 nodes in places), layered and hard to read,
and the owner's experience is that nodes suit visual event flows (inputs, variables, random
choices, branching), not this.

- **A runner is a scene type, separate from any scene.** Starting a scene in a world means:
  - pick a runner;
  - fill in the settings menu that runner defines;
  - play.
- **A runner is plain Python, editable inside the app.** Its main file is a few clearly named
  functions:
  - the initial input it asks for, such as the storyline prompt or a random-story topic;
  - the functions or commands available in the scene, like the Suite's "computer, …";
  - the gameplay loop, which names the agents it runs, in order and on conditions.

  It should be readable by someone who doesn't code much.
- **The machinery is readable defaults** (owner). The built-in agents and context builders are
  exposed in the app to read, not to edit. To change one, copy it, change the copy, and hook it
  into a new runner. Runners call into the library: agents, the world, context building.
- **Who it's for:** mostly people comfortable with Python or with prompting for Python, including
  the owner when an output irritates them. A good early candidate is a world-aware version of
  dynamic story v2's random-story mode.
- **Python, not Lisp/Scheme** (owner): the app is Python, and it will be shared.
- **Until then, the node runtime stays.** Phase 2's slice reuses the existing loop (see the slice
  design). New world features are built in Python, not as nodes. Plan E rewrites only the data
  nodes that touch characters and world entries. Once the default runner covers today's loop and
  the `@` action, the node editor becomes an optional extra or goes away.

## Phases

One design (this one), built in phases, each with its own plan. My recommendation, close to the
owner's suggested order (world, scenes, characters, cultures):

0. **Round-trip test first** (my call, moved ahead of phase 1 so phase 1 is planned on firm
   ground). A throwaway harness, no storage: description → facts → prose, repeated a few times
   against the owner's local model, measuring invented and dropped claims. Ask the owner before it
   runs (it calls a real model). Per the guiding principle, a poor result is answered in the
   AI-handoff layer (prompts, smaller extraction steps, a stricter check pass), not by giving up
   facts as the truth; it informs phase 2's prompt work, not phase 1's schema.
1. **World store.** SQLite per world, ids, the general thing shape (core-field timelines, facts,
   references, sources, both clocks), the calendar basics needed for dates, and the derived search
   index. Fully tested before any screen uses it. The app may be broken from here. (Done
   2026-10-19. Undo now follows explicit reversal links; see
   `docs/superpowers/plans/2026-10-19-world-undo-provenance.md`.)
1b. **Hardening before phase 2** (owner, 2026-10-19). This is the "Before phase 2" list under
   "Code health" below. Plan: `docs/superpowers/plans/2026-10-19-fantasymate-pre-phase-2.md`.
2. **Scenes and characters together** (a scene can't be played without characters). Message tree
   with stable ids and dates, mention records, scene-local changes, characters as facts with
   generated prose, the existing features moved over, the node editor's data nodes rewritten, the
   Worlds home and World tab basics. The app is playable again when this phase ends.
   **"Playable" means** (my call): a scene can be created in a world and played with characters,
   time passage, history, world state, tracked states, pins and the director. Because every kind
   shares one shape, phase 2 also brings in **basic places, lore entries and events** (enough for
   the AI's context and history); no adapters to the old stores are written. The cultures features
   (naming, culture context, highlights, culture review) are switched off until phase 4.
   **Order (owner, 2026-10-19):** phase 2 starts with a thin **playable slice**, so the local
   model's performance can be gauged early. It then widens in plans B–F; see
   `2026-10-19-fantasymate-phase-2-slice-design.md`. The additions below land in those later
   plans.
   **Additions from 2026-10-19:**
   - **Schema.** Fact references and knowledge records are added to the world store (plan C).
     Replay and undo learn the new slot kind (a knowledge record).
   - **Species, races and inheritance** (plan B).
   - **Scene state as of a message,** and presence with away bridges.
   - **Knowledge-aware context:** a character's own context gets only what they know;
     narrator and director context is labelled with who knows what.
   - **Decision model:** first a probe of Laya as the local provider against upstream's
     interface, then one decision interface with LLM fallback. Phase 2's own judgement calls
     (tracked-state skip, invented-fact check) use it.
   - **Opportunistic upstream ports:** the koboldcpp client improvements, the local memory
     reranker, the prompt-override compatibility checker, and editor decision checks.
3. **Promotion and the inbox**, including importance judgement (through the decision model),
   path-following, prequel and branch conflicts, undo by source, and the "bring in world
   changes?" prompt on reopening a scene. It also adds learned knowledge as inbox requests, a
   "Known by" view on facts, and "add to world" from selected text or "make real" as
   owner-picked candidates. The undo notes left for this phase:
   - a redo cancelled by another undo is silent, so the inbox should say why;
   - undo planning reads the whole link graph;
   - the timeline shows restored copies as coming from "undo".
4. **Cultures and places** onto the new shape: cultures and the glossary move over and are switched
   back on, the three kinds of place merge, and the culture review joins the inbox. Common
   knowledge can be scoped to a culture.
5. **The rest**: items, dated images with new-portrait offers, the view-as-of-a-date screen for
   any thing, and scene backgrounds drawn from the current place's dated images.
6. **Later**:
   - scene runners in Python, replacing the node runtime (see "Scene runners");
   - stories as a reading order (see "Navigation");
   - replay as a reader for branches and stories;
   - character perspectives, only after a probe shows the owner's model can do it without
     blocking play.

Help chat permission gating can land in any phase.

## Code health

This is a survey of the inherited code, measured on 2026-10-19 (sizes and counts, not a
line-by-line audit). The code works and has a real test suite: 251 test files and cached prompt
baselines. Its maintainability problems are concentrated in a few places:

- **God classes.**
  - `Scene` (`tale_mate.py`) has 126 methods and about 2,050 lines. It holds history, characters,
    time, saving, memory, assets and state.
  - `ClientBase` has 112 methods, and `Agent` has 69.
  - Agents reach straight into the scene, with about 440 `scene.` references under `agents/`.
- **Large files.**
  - About 20 Python files are over 1,100 lines, led by node core (2,559), `tale_mate.py` (2,168)
    and `client/base.py` (2,100).
  - On the frontend, the largest are `SceneMessages.vue` (2,394), `litegraphUtils.js` (2,305)
    and `TalemateApp.vue` (2,102).
- **Long functions.** 92 functions are over 100 lines, and 9 are over 200. The engine API
  `create()` factories are mostly nested class definitions. The real ones are
  `websocket_endpoint` (283), `_send_prompt` (229) and `persist_character` (217).
- **Import tangles.** There are 188 imports inside functions, most of them working around
  circular imports.
- **Implicit frontend state.**
  - There is no store.
  - 98 components each register their own websocket handlers.
  - Data passes through 140 provide/inject links.
- **Duplication and drift.**
  - There are two `slugify` functions.
  - Ad hoc ids are 6, 8, 10 or 12 hex characters long.
  - Atomic writes exist only in the cultures code.
  - There are 96 lookups of characters by name.
  - The shared-world sync copies data and overwrites it.
- **Silent errors.** 12 places catch an exception and do nothing.

### Before phase 2

Each of these is small and protective:

1. **A green test suite.** The 141 "environment" failures (NLTK's `punkt_tab` data is missing in
   tests) make every run red and hide real regressions. The tests must pass with no network
   access.
2. **chromadb usable outside pytest on Guix.** Add zlib to the dev shell and to the dev app's
   library path (ruling R7 of the world-store build).
3. **Pin today's behaviour where phase 2 will cut.** Add a golden test that plays a short scene
   with the mock client and records both the prompts the AI receives and the saved scene. The
   rewrite will change these recordings, and every change is then reviewed on purpose rather than
   happening by accident.
4. **Strict type checking (mypy) on `src/talemate/world/`**, enforced by the test suite, so the
   new package stays clean.
5. **World view hardening** that phase 2 builds on. The deferred review items:
   - tests for field values, date decoding and fact order;
   - tests that `referencing()` drops ended and removed facts;
   - replacing the `IN (…)` id lists, which fail past about 32,000 things, with a join on the
     same live filter.

Don't clean up code that phase 2 deletes: `shared_context.py`, the name-keyed character maps,
history ranges stored as list positions, and the per-file changelog.

### During the rework: each phase cleans what it touches

- **Strangle `Scene`.** Each phase-2 task that rewrites part of the scene moves that part into
  its own module: the message tree, the character registry by id, time and dates, and
  persistence, which moves into the world database. `Scene` shrinks to a coordinator. No
  big-bang restructuring.
- **Ids everywhere.**
  - Replace the name lookups with the id-based registry as characters move over.
  - Use the world store's 32-hex ids.
  - Delete the duplicate `slugify` and the ad hoc id helpers when their callers move.
- **A narrow interface for agents.** An agent moved onto the new data gets a small scene-context
  object with only what it needs, instead of the whole `Scene`. This is how the 440 references
  shrink.
- **New packages stay import-clean.** New code has no imports inside functions apart from
  deliberate lazy ones, and strict typing extends to each new package.
- **Frontend.**
  - The new Worlds, World and Inbox screens use a small Pinia store with one websocket handler
    per area.
  - An old component moves over only when it's being edited anyway.
- **Silent errors** get logged or re-raised whenever the code around them is touched.
- **Leave alone what the rework doesn't touch:** `ClientBase`, TTS, the large node files other
  than the data nodes, and `litegraphUtils.js`. They are large but self-contained, and splitting
  them now buys nothing.

## Left to the builder

- The SQLite schema, how the thing shape maps to tables, and how two-clock queries are done.
- How references are encoded in fact text.
- How prequel contradictions are detected (structural checks, AI judgement, or both).
- Prompt design for extraction, prose, invented-fact checks and importance.
- Which node-editor nodes need rewriting, and in what order.
- Screen details within the agreed navigation and theme tokens.
- What to delete from the old storage code and when, given the app may stay broken until phase 2
  ends.
