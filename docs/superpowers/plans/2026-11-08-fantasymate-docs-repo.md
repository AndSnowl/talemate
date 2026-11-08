# Fantasymate docs repo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `~/Projects/fantasymate/docs` as its own git repo. It holds the standing vision, an index, the idea docs reframed for the vision, and stubs for the new systems.

**Architecture:** Plain org files in the same style as `~/Projects/Project Frontier/docs` and the fork's `docs/ideas/`. There's no code. Each task writes or reframes one doc and commits it. The only test is the owner reading it.

**Tech Stack:** Emacs org-mode files, git.

**Spec:** `docs/superpowers/specs/2026-11-07-fantasymate-vision-and-fresh-start-design.md` (in the fork, `~/Projects/Web/talemate`), section "Project 1: the vision and the plans repo". Read the whole spec first: `vision.org` is drawn from its vision half.

## Global Constraints

- Location: `~/Projects/fantasymate/docs`, its own git repo. Do not create `~/Projects/fantasymate/fantasymate`; that is the next plan.
- Format: org (`#+TITLE:`, `#+DATE:`, `*` headings), like `docs/ideas/*.org` in the fork.
- New work folders: `specs/`, `plans/`, `probes/`.
- Write in the owner's voice where the current idea docs do ("I", "owner"). Mark Claude's own decisions "(my call)", the way the current idea docs do.
- Don't copy the archive's specs, plans, probes, mockups, `feedback/` or `.superpowers/` in. Point to them instead.
- Stubs record only what the owner has said. Don't add designs.
- Writing rules: plain language; no "load-bearing", no em-dash pileups; short paragraphs; lists for parallel items.
- Commit trailer lines as given in the session's attribution reminder.

## Review Focus

- A reader opening the docs repo cold should reach `vision.org` from `index.org` in one step, and know from it where the archive is.
- Every idea doc's old Talemate framing is gone. That covers shared context, upstream merges, GPU-server deploys from the fork, and "a scene must be loaded". Check by grepping each finished doc for `shared context`, `upstream`, `Talemate`. The only hits allowed are history pointers.
- The two flipped non-goals (no 4X simulation in world activation, manual-only placement in the map) are visibly flipped. A note says what they were, so the change can be traced.
- Magic is described as prompt-defined, with the owner's three example prompts. It is never written as one fixed system.
- None of the owner's open questions get silently answered while reframing. Open items stay under "Left open".

---

### Task 1: Repo, vision.org, and the spec and plans

**Files:**
- Create: `~/Projects/fantasymate/docs/vision.org`
- Create: `~/Projects/fantasymate/docs/specs/2026-11-07-fantasymate-vision-and-fresh-start-design.md` (copy from the fork)
- Create: `~/Projects/fantasymate/docs/plans/2026-11-08-fantasymate-docs-repo.md` and `plans/2026-11-08-fantasymate-program-repo.md` (copies of this plan and the next one from the fork)
- Create: `~/Projects/fantasymate/docs/probes/.gitkeep`

- [ ] **Step 1:** `mkdir -p ~/Projects/fantasymate/docs/{specs,plans,probes}`, then `git init` there.
- [ ] **Step 2:** Copy the spec and both plans in, unchanged.
- [ ] **Step 3:** Write `vision.org` from the spec's sections "Intent", "The play experience", "Architecture" (including the magic paragraph), "Goals, non-goals, anti-goals" and "Constraints". Restructure it as a standing reference, not a dated design, with these headings: What it is · Why · The play experience · How it works · Goals, non-goals, anti-goals · Constraints. Leave out the project sections; those belong to the specs. End with a short "Where the history is" pointer to `index.org`.
- [ ] **Step 4: Verify.** Each anti-goal in the spec appears in `vision.org`. Run `grep -c` on "omniscient" and "reboot" and expect ≥1 each.
- [ ] **Step 5:** Commit with "vision, design spec and plans".

### Task 2: index.org and the history pointer

**Files:**
- Create: `~/Projects/fantasymate/docs/index.org`
- Create: `~/Projects/fantasymate/docs/history.org`

- [ ] **Step 1:** Write `index.org`:
  - a table of every doc with its file link, what it is and its state (the same columns as the fork's `docs/ideas/index.org`);
  - the order of work from the spec ("The order");
  - the three-folder layout from the spec ("The layout").

  Drop the fork index's "How it gets built", "Deploying the fork", "Where shared data lives" and the Talemate-era "Later" list. The one "Later" idea still alive is "Archive of past stories"; move it to the knowledge stub in Task 6.
- [ ] **Step 2:** Write `history.org`. It lists where the past lives in the archive `~/Projects/fantasymate/talemate`, which is still `~/Projects/Web/talemate` until the move:
  - `docs/superpowers/specs/`, `plans/`, `probes/`, `mockups/`;
  - `feedback/` and `.superpowers/` (untracked);
  - `docs/ideas/upstream-pr-279-review.md`.

  Give one line per folder saying what it holds. Name the key specs by topic: world data model, phase 2 slice, heritage, connections, filing, polish 1–5, languages 1–4c.
- [ ] **Step 3: Verify.** Every `file:` link in `index.org` points to a file that exists, or one a later task creates. List those later files in the commit message.
- [ ] **Step 4:** Commit with "index and history pointer".

### Task 3: world-activation.org, reframed as the simulation doc

**Files:**
- Create: `~/Projects/fantasymate/docs/world-activation.org` (from the fork's `docs/ideas/world-activation.org`)

- [ ] **Step 1:** Copy it, then reframe:
  - The Status section: no longer "long after fantasymate is playable". It is the heart of the simulation plans, and the first major goal comes from it (spec, "Project 3, sketched").
  - Non-goals: replace "a full 4X simulation…" with the simulation as the backbone, plus a one-line note: "Until 2026-11-07 this was a non-goal."
  - "How it fits what's planned": rewrite against the architecture in `vision.org` (one set of verbs, generators as schema + engine + checker, the levels of detail). Drop references to the inbox and scenes that assumed the Talemate scene model. Keep the source/undo ideas.
  - Add the spec's first-major-goal sketch as a section, linked to the spike list, which stays as is.
  - Keep "Left open" whole.
- [ ] **Step 2: Verify.** Run the grep from Review Focus. "Left open" has the same items as before, or more.
- [ ] **Step 3:** Commit with "world activation reframed as the simulation doc".

### Task 4: generators.org (from generated-rules.org)

**Files:**
- Create: `~/Projects/fantasymate/docs/generators.org`

- [ ] **Step 1:** Write `generators.org` from the fork's `docs/ideas/generated-rules.org`:
  - The pattern: schema + deterministic seeded engine + checker. The instruct model writes data; code is the sandboxed exception. Quote the owner: "we want something that can be checked perfectly."
  - Languages as the worked example, in one paragraph: language file, generator, name grammar, checker, and the Claude Code route with its brief and check command.
  - Candidates, each with one line of what the owner has said: governance (the next one; offices, ranks, titles, succession; names the title-holders), tech graph, magic, species, biomes and palettes.
  - Keep "The catch", the Pont-Tsevran name, whole. Keep "Why it fits autonomy" (stubs plus generators).
- [ ] **Step 2:** Commit with "generators doc".

### Task 5: world-map.org, world-calendar.org, languages.org

**Files:**
- Create: `~/Projects/fantasymate/docs/world-map.org`, `world-calendar.org`, `languages.org`

- [ ] **Step 1: `world-map.org`.**
  - Flip the non-goal "no generated world: placement is manual". Worldgen owns geometry and the player edits; add a one-line note of the old non-goal.
  - Keep the glyph look (mockup D link), nested maps and travel times.
  - Merge in world activation's "map bridge" by link, not by copy.
  - Remove "Where shared data lives".
- [ ] **Step 2: `world-calendar.org`.**
  - Keep the Earth-length calendar, names per culture, holidays and eras.
  - Note that the world store already has calendars, eras, holidays and date precision (`world/calendar.py`, `world/dates.py` in the program).
  - Add world activation's coarse precision and the undated "a long time ago".
  - Drop the Talemate items under "Left for the design" (`ArchiveEntry.ts`, shared-context sync, time-passage messages).
- [ ] **Step 3: `languages.org`.** Rewrite it as what languages are now:
  - the range (description only, naming rules, full language);
  - making them outside the creative model, through the language agent's routes;
  - Name it and the narrator rule;
  - people's names and name grammar.

  End with "Still open", taken from the fork's `docs/superpowers/specs/2026-10-30-fantasymate-languages-4-design.md` "filed for later" items: word order from grammar; the language agent handing facts and phrases to the world's model; automatic naming in + Add facts. Drop the Talemate code pointers (`world_state/schema.py` and so on).
- [ ] **Step 4: Verify.** Run the grep from Review Focus on all three.
- [ ] **Step 5:** Commit with "map, calendar and languages reframed".

### Task 6: Stubs for the new systems

**Files:**
- Create: `~/Projects/fantasymate/docs/knowledge.org`, `tech-graph.org`, `magic.org`, `governance.org`, `apocalypse.org`

- [ ] **Step 1:** Write each with `* Status` ("A stub: what the owner has said, not a design"), `* What the owner has said`, and `* Left open`. Content comes from the spec and this conversation's record in it:
  - `knowledge.org`:
    - the omniscient-characters anti-goal;
    - an information agent that decides what a character knows, where the accountant knows near-exact numbers but nobody knows every number;
    - news and rumour spreading and warping over time and distance, possibly through creative passes;
    - world activation's "news spreads";
    - the world data model's knowledge records;
    - the "Archive of past stories" idea moved over from the old index.
  - `tech-graph.org`: a graph, not a tree; multiple routes; disconnected parts; research invested over time; things lost and rediscovered; rare breakthroughs decided by a roll and then explained as one person's work.
  - `magic.org`: prompt-defined, with the three example prompts plus the original one; the leaning toward a shared discovery graph with technology; a character combining two things on the graph to open something new. State that the owner is "not quite sure, we aren't there yet".
  - `governance.org`: from generated-rules: nations to tribes, cults, academies and companies; offices, ranks, titles and succession; made after the language exists and after some ordinary passes of facts; regnal numbers are narrator words, and counting them waits on governance (languages 4c).
  - `apocalypse.org`: the world must be able to end, up to all life; a reboot in the way the Old World became the Age of Sigmar, by the player or by the world itself once deities exist.
- [ ] **Step 2:** Add all five to `index.org`'s table, with the state "Stub".
- [ ] **Step 3:** Commit with "stubs for knowledge, tech, magic, governance, apocalypse".

### Task 7: The owner reads it

- [ ] **Step 1:** Hand the owner `index.org` and `vision.org` first, then the reframed docs. List anything marked "(my call)" that was added during this plan.
- [ ] **Step 2:** Apply their changes and commit each round.
- [ ] **Step 3:** Once they approve, ask before creating a GitHub repo or pushing (name and visibility are theirs).
