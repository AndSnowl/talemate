# Fantasymate: the vision, and a fresh start

Date: 2026-11-07. Status: approved by the owner (2026-11-08).

This document does two things. It records the owner's vision for fantasymate as it stands after the
languages work, and it describes the first two projects that follow from it: consolidating the
plans into a docs repo of their own, and starting the program over in a fresh repo. A third
project, the first major goal, is only sketched here; it gets its own brainstorm.

Everything marked *(my call)* is a decision Claude made that the owner did not; check those first.

## Intent

Fantasymate is a narrative role-playing game (not a classic text adventure: prose, not strict
commands) played over a long campaign, many sessions across a long period, in a world that is
generated in the spirit of Dwarf Fortress and supercharged by AI.

Two motivations, from the owner:

1. **Fun to play**, for the same reasons Dwarf Fortress's adventure mode and history browsing are
   fun: a real world with real history that you can go out into and change.
2. **See how far the concept can go**, without regard to the cost or accessibility of the AI. The
   only concession is offering options for how a user spends their money: local or API for the
   creative (narrative) model; local, API, Claude Code or competitors for the frontier instruct
   model.

The ambition sits on a spectrum between Dwarf Fortress and worlds and stories as intricate as the
Trails series or One Piece. Neither end will be hit; the point is how far along it gets.

### Why the old plan isn't enough

- **Dwarf Fortress** makes history, separates important actors from common folk who become named
  people when you look closer, and produces an active, emergent world you can act in (read about a
  legendary sword, then go and take it). It is weak at interpreting and giving meaning: flat,
  mechanical accounts; the same races, languages and monsters in every world; few ways to earn
  the sword through deeds or learn of it naturally in play. Everything is hard-coded.
- **Fantasymate so far** is the opposite: it can describe and give meaning to anything, in any
  genre, but has no timeline that holds, no real history, no simulation, and falls into AI
  clichés.
- **The bridge is what the language work revealed.** A short, expensive instruct-model run designs
  a deterministic generator (a language: sounds, grammar, name rules), and the app then applies it
  cheaply and consistently forever, for both practical use and the creative model. In the owner's
  words, "generate the generators": step back one layer from Dwarf Fortress's hard-coded
  procedural systems and have the instruct model write them per world, per nation, per culture.

The core of the vision is a **synergy between a conventional simulation, an instruct model and a
creative model.** The creative model has an idea (a nation); the instruct model fleshes it out into
well-defined systems that fit the simulation; the simulation runs it, and asks the creative model
for decisions at the moments that need judgement; the creative model turns the numbers and
outcomes into history, explanation and character. Something like a 4X game or Crusader Kings,
directed by AI in a narratively satisfying way and interpreted by AI.

## The play experience

Over many sessions:

- **Making a character.** The player describes a character. The world places them with a history
  fitting the prompt, and builds what matters around them: other characters and places that either
  didn't exist or were only names or statistics.
- **Conflict at every scale, always.** The character starts with small conflicts; they build up
  into politics, wars, or fighting forces of evil.
- **Player parity.** Everything the AI can control, the player can too, and the player can prompt
  for change. For example, in a time skip between two adventures, start the conflict they want
  their character to walk into later.
- **Consequences cascade through the world**, as in Dwarf Fortress, but interpreted, with creative
  decisions, on systems tailored to that world. Finding a lost artifact of great power might let a
  losing nation win, or lose less badly, or make things worse by handing the other side a casus
  belli simply for owning it. This is the reality a hard simulation adds.
- **Time moves forward.** There is far less room to change the past, since that would break the
  simulation. Branching a world is fine.
- **Zooming in.** The world generates around the player in all directions as they go, now with the
  simulation as the backbone the prose drapes over.

## Architecture

The owner confirmed this picture (2026-11-07). The parts marked as Claude's guesses were accepted
as written.

- **One source of truth:** the world store plus the simulation's state (map, positions,
  populations, resources, polities, ongoing situations such as wars, plagues and research). Prose
  is derived from the truth and never read back into it. (The second half is already a probe
  finding: never re-extract facts from generated prose.)
- **One set of verbs.** The simulation, the creative model, the instruct model and the player all
  change the world through the same typed actions ("found settlement", "declare war", "transfer
  artifact", "discover tech node"), each checked before it applies. This is how player parity
  works and how prose can't contradict the simulation.
- **Generators are schema + engine + checker.** Languages, tech graphs, magic systems, government
  structures, species, biomes and ASCII palettes each get a fixed shape, a deterministic seeded
  engine and a checker. The instruct model writes **data** that the checker proves valid; the
  engine runs it cheaply forever. Generated *code* is the rare exception, for something that truly
  needs new behaviour, and is sandboxed. Owner: "we want something that can be checked
  perfectly."
- **The creative model works at decision points.** Propose, assess, roll, narrate
  (`docs/ideas/world-activation.org`). Against cliché: several deliberately different options,
  dice, and random "spice" (procedural constraints or directions added to a prompt that the model
  would not reach on its own).
- **Python runners orchestrate.** A world runner for genesis and progression; scene runners for
  adventures. The instruct model orchestrates mainly genesis and heavy steps ("this nation needs a
  government", "a breakthrough opens a new branch of the tech graph"). Routine progression is the
  conventional simulation calling the creative model at decision points, so a long time skip
  doesn't cost an instruct-model call per year.
- **Level of detail.** Far away the world is aggregates ("40,000 farmers"); close up it is named
  people and places. Stubs are promoted as the player approaches.

Systems the owner has named so far: languages (built), tech as a graph rather than a tree (multiple
routes, disconnected parts; research invested over time; things lost, rediscovered, rare
breakthroughs decided by a roll and then explained), magic, governments and orders and cults,
species, biomes and palettes, deities acting through small favours, resources and trade.

**Magic is whatever the world's prompt says it is** (owner, 2026-11-08). "One underlying system,
interpreted differently by each culture, combinable by the learned" was only one example prompt.
Others are just as valid:
- "The gods live on the sun and make it brilliant. All magic starts as sunlight, passed through
  lenses and baked into things, and a rare few can bend the light to their will."
- "A magic system that fits this world, mostly standard with some twists."
- "Only species X can wield magic, which comes from …"

So the magic generator's schema has to hold very different systems, not one fixed design. The
owner's leaning, not decided: magic is probably close to technology, perhaps sharing a general
**discovery graph**. A creative-model moment might have a character combine two things on that graph
and open something new from it.

## Goals, non-goals, anti-goals (the whole vision)

**Goals**
- A world generated from a guiding prompt, with real history, real geography and a running
  simulation under it.
- Per-world generators written by the instruct model as checked data.
- Prose, history and character that interpret the simulation and never contradict it.
- Long campaigns: adventures, time skips, consequences, and the player steering at every level.

**Non-goals**
- Rewriting the past in place. Branch instead.
- Cheapness or accessibility of AI as a design constraint. Options for spending, yes.

**Anti-goals** (failure even if it technically works). Carried over from world activation:
- characters acting out of character, or the obvious reactions missing;
- histories that look alike from two short prompts;
- the world revolving around the player's characters;
- bookkeeping instead of story (inbox fatigue);
- silent canon: something entering the world the player never saw;
- a hot character's feed repeating the same event.

New (owner, 2026-11-07):
- **Omniscient characters.** With a large history and strict canon, every character risks being a
  perfect historian. Scenes need something that decides what each character knows. That's not a
  blanket rule: an accountant asked about the accounts should know a near-exact number, but nobody
  knows every number everywhere. Knowledge can have a backbone in the simulation: news and rumour
  spread over time and distance and get warped along the way, possibly with creative-model passes.
  (The world data model's knowledge records and world activation's "news spreads" are the start.)
- **Apocalypses that can't happen.** The world must be able to end, up to the destruction of all
  life. There should be a way to "reboot" it (as Warhammer's Old World became the Age of Sigmar),
  done by the player, or by the world itself once deities exist.

## Constraints

- **Python backend, Vue frontend.** Python all the way down was considered and kept: wall-clock
  time is spent waiting on models, not on simulation ticks; the simulation is coarse (events and
  situations at levels of detail, not per-tile physics); hot spots (terrain, borders, pathfinding,
  trade flow) can use numpy, or a small Rust module later if profiling demands it. The carried-over
  code and tests are Python, and runners and generators are meant to be readable Python.
- Local models through koboldcpp for the creative model. Tests that call a real model stay separate
  and are run only after asking the owner. Probe the AI with a throwaway before building any
  LLM-dependent feature.
- Guix dev environment (`docs/dev/local-testing.md`): `guix shell`, `uv run --no-sync`.
- AGPL-3.0, as Talemate is, and as the owner would have chosen anyway.
- Unreleased: no migration code for old data. Start fresh.
- UI rules already learned: controls sit by the content they act on; same look means one
  component; screenshots at 1920×1080.

## The layout

```
~/Projects/fantasymate/
  docs/          plans, ideas, brainstorms, specs   (its own git repo)
  fantasymate/   the program                         (its own git repo)
  talemate/      this fork, moved here as a reference archive
```

Modelled on `~/Projects/Project Frontier` (owner). The point: brainstorming and plans don't live in
the shipped product, and the old fork stays close and always findable. *(My call: the folder is
lowercase `fantasymate`, matching the product name.)*

## The order

1. The vision and the plans repo (project 1, below).
2. The program repo (project 2, below).
3. The first major goal (project 3, sketched below; its own brainstorm).

## Project 1: the vision and the plans repo

Create `~/Projects/fantasymate/docs` as a git repo.

**What goes in**
- `vision.org`: this document's vision half (intent, play experience, architecture, goals and
  anti-goals, constraints), rewritten as the standing reference. *(My call: org, like Project
  Frontier's docs and the current `docs/ideas/`.)*
- `index.org`: the map of the docs: what each file is, its state, and the order of work. Replaces
  the current `docs/ideas/index.org`, which is written for patching Talemate (upstream merges,
  shared-context storage, GPU server deploys from the fork). Those parts are dropped.
- The idea docs, carried over and **reframed for the vision**, each stopping to consider what could
  be improved:
  - `world-activation.org`: becomes the heart of the simulation plans. Its non-goal "a full 4X
    simulation with economies and armies" flips: the simulation is the backbone. Its open questions
    (scale, the copy of the world, who acts next) stay open.
  - `generated-rules.org`: becomes the generators doc: schema + engine + checker as the pattern,
    with languages as the worked example and governments, tech graphs, magic, species, biomes as
    the next candidates. Keeps "the catch": a model's first idea can carry meaning a generator
    never would; a way for such names to survive, built from their meaning, must remain.
  - `world-map.org`: the non-goal "no generated world: placement is manual" flips: worldgen owns
    geometry; the player edits. The glyph look (mockup D) and nested maps stay.
  - `world-calendar.org`: the Talemate parts (static history as durations, shared-context copying)
    are gone; what's left is the calendar the world store already has, plus eras and coarse
    precision from world activation.
  - `languages.org`: rewritten as what languages *are* now (the built system), plus what's still
    open (the part 4 spec's filed-for-later items).
- New idea stubs for the systems named in the vision that have no doc yet: knowledge and rumour,
  tech graph, magic (with the owner's prompts and the discovery-graph leaning above), governance,
  apocalypse and reboot. Each records what the owner has said, no
  more. *(My call: stubs, not designs.)*
- A pointer file listing where the history lives: the archive's `docs/superpowers/` (specs, plans,
  probes, mockups), `feedback/`, `.superpowers/` ledgers, and `docs/ideas/upstream-pr-279-review.md`.
  These are **not** copied; they stay in the archive as history.
- From now on, new brainstorm specs, plans and probes for fantasymate are written here, not in the
  program repo. *(My call on the folder names: `specs/`, `plans/`, `probes/`.)*

**Done when** the owner has read `vision.org` and the reframed idea docs and approved them, and the
repo has its first commits.

## Project 2: the program repo

Create `~/Projects/fantasymate/fantasymate` as a **fresh** git repo. No git history is carried; the
first commit names the source commit in the archive (`b606dee7` or whatever main is then). *(My
call: a fresh history, since the owner asked for a fresh start; the archive keeps the full log.)*

**Fantasymate names throughout:** the Python package (`fantasymate`), the config, the websocket
types, the frontend package, the dev scripts. No "talemate" left, apart from the license credit.

**Carried over** (from the code sweep on 2026-11-07):
- `src/talemate/world/`: the revisioned SQLite store, undo and replay, filing, timelines,
  calendar and dates, heritage, kinds, nearness.
- `src/talemate/languages/`: the language file, generator, name grammar, people's names, checker,
  importer, brief, and the headless Claude Code runner. Plus the language-design skill
  (`.claude/skills/language-design/`).
- The `worldplay/` parts that don't depend on a Talemate scene: create, repoint, merge, groups,
  links, people, facts, cleaning, **prose generation** (`prose_gen.py`: entry pages keep their
  generated prose sections), and their prompt templates (`templates/world/` and what
  `talemate.prompts` they need).
- **Where the cut falls** *(my call)*: carry whatever the behaviour in "Done when" needs, and
  nothing that only serves scenes. That pulls in helpers on neither list above (for example
  `worldplay/ai.py`, `decide.py`, `held.py`, `mentions.py`, `references.py`, and `world/index.py`
  if recall still uses it). The few things carried code takes from left-behind files
  (`DEPARTS_FROM`, `age_in_years` in `worldplay/characters.py`) move into carried modules.
  `world/scenes.py` is left behind unless the world store's schema needs it.
- `src/talemate/client/`: the LLM client layer, with each role naming its own client.
- The server's worlds router (`server/worlds.py`, `world_drafts.py`), which should be split into
  smaller routers as it moves.
- Frontend: `components/worlds/`, `stores/worlds.js`, `theme/` and the appearance settings, the
  wordmark, the client and app settings pages.
- Their tests: `tests/world`, `tests/worldplay`, `tests/languages`, the worlds server tests, and the
  Playwright e2e harness with its worlds and theme tests. Plus `manifest.scm`, the dev docs that
  still apply (`local-testing.md`, `dev-loop-optimizations.md`), and the probe tools still useful.
- AGPL-3.0 `LICENSE`, crediting Talemate (vegu-ai/talemate) as the origin of the client layer and
  app shell.

**Left behind**: the node system (`game/`, node graphs, node editor); the Talemate agents
(conversation, narrator, director, editor, summarize, memory, world_state, creator, help); TTS;
image generation and scene assets; character card import; the installers and Docker files;
Talemate's own world-state manager UI; the scene and message UI; the empty `cultures/` leftovers.

**The spine that has to be rebuilt.** With Talemate's core gone, these need a thin replacement:
- app config and the client registry (which clients exist; which role uses which);
- a minimal "role" or agent config in place of Talemate's `Agent` (the language agent's route,
  client and model setting is the one in use today);
- the websocket server shell;
- a new frontend app shell in place of `TalemateApp.vue`.

**Scenes stop working** in the new repo until scene runners exist, because today a world scene plays
by converting into a Talemate `Scene`. The scene setup cards, Continue, New scene and in-scene
tools in the worlds UI are removed or hidden. The owner accepted this: worlds and languages first,
the first major goal next, adventures after. The `worldplay` bridge files (`characters.py`,
`context.py`, `setup.py`, `persistence.py`) are left behind, not ported half-working.

**The new app starts empty** (owner, 2026-11-07). The owner's existing worlds and language files are
test data and don't come over. On-disk formats (the world database schema, folder layout,
`.language.json`, config keys) are free to change during the rename and the split. This holds for a
long time: no keeping worlds working between features, no migrations.

**Done when**
- the plain suite and the e2e suite pass in the new repo;
- in the new app, the owner can make and edit worlds, all entry kinds, drafts, Name it, and make,
  change and import languages, as on the archive's main today. Making a language through Claude
  Code works;
- nothing named "talemate" is left outside the license credit;
- the owner has approved, then both repos are pushed to new GitHub repos (confirm names and
  visibility with the owner before pushing).

**The fork is frozen** once project 2 starts *(my call)*: no new work lands on its main, so the
first commit's source commit is fixed and nothing needs syncing later. Fixes go into the new repo.

**History left as files** *(my call)*: `docs/ideas/` is carried into the docs repo (project 1);
`feedback/`, `.superpowers/` and other untracked history stay as loose files in the archive and
move with the folder. They are not committed to the fork, whose GitHub remote may be public.

**Moving this fork** into `~/Projects/fantasymate/talemate` is the last step, after the owner says
go:
- Its worktrees under `.worktrees/` use absolute paths: run `git worktree repair` after the move.
  Ask the owner which of the four worktrees to keep; `languages-4b2` holds their running test app.
  Its worlds are disposable test data (owner), but stop it cleanly before the move.
- Claude Code's memory for this project is keyed on the folder path
  (`~/.claude/projects/-home-skeleton-Projects-Web-talemate/memory/`). Copy the memories that still
  apply to the new projects' memory folders and update their paths. Many of them (cultures, the fork
  plan's state log) are history and can stay with the archive.
- Do the move at the end of a session, since the running session's working folder moves with it.

## Project 3, sketched: the first major goal

The owner picked this (2026-11-07). From a prompt, genesis makes:
- a small map;
- two or three nations, each with languages and governments;
- a few named rulers.

The player runs a time skip and watches a simulated conflict play out, interpreted in a feed. It
puts the main ideas in play together: a simulation, characters steering it, and the result
interpreted as story. It needs its own brainstorm, starting from world activation's spike list (LLM
alone vs. propose-assess-roll; the feed's speed; who acts next; territory from claims; prose to map;
"stop when"), plus the first new generator (governance is the obvious candidate).

## Left to the builder

- How thin the rebuilt spine is (config, roles, websocket shell, app shell), as long as the client
  layer's per-role model choice survives.
- How the big worlds router is split.
- Which probe scripts are still worth carrying.
- Directory layout inside the program repo (`src/fantasymate/...` is expected).
