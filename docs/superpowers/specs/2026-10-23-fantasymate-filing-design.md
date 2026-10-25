# Fantasymate: Filing, tags and draft pages

Date: 2026-10-23. Status: design, awaiting the owner's approval.

This redesign continues on `feature/spheres`, before that branch merges and before languages. The owner put it this way: "continue on this branch until we have a feature that feels right and complete."

It replaces most of the Spheres structure (`2026-10-22-fantasymate-spheres-design.md`). It keeps nearly all of Curation's machinery (`2026-10-22-fantasymate-curation-design.md`), but changes where things are filed and how they are shown.

The evidence for it:
- the owner's Curation acceptance run (2026-10-23), recorded in `.superpowers/sdd/2026-10-22-fantasymate-curation/progress.md`;
- the owner's acceptance world, copied to `/tmp/fantasymate-acceptance-curation`;
- the Curation probes in `docs/superpowers/probes/`.

The owner approved the mockups `redesign-v1.html`, `-v2.html` and `-v3.html`. They are saved under `.superpowers/sdd/mockups/` (not committed). v3 shows the current model, v2 the draft page and menus. Where v1 differs from v2 or v3, v1 is out of date.

## Intent

Curation made facts land in the right places. The structure around them stayed clunky, though. The owner's own words: "the real challenge now is the UI/UX. Spheres might be overfitting a bit."

What the acceptance world showed:
- **Drawers made thin entries.** The Night Court got 12 one-fact stubs filed in it, such as "Military Deployment", "Twilight Hours" and "Senior Advisor". These are roles and topics, not things anyone would follow.
- **One home per entry.** The Academy of the Chiseled Moon could be filed in Runic Magic or in Velikoye, but never both. The owner's question is "What's in Velikoye? Oh look, the Academy… who runs it? The Order of the Talon-Scribe." That question needs many-to-many links.
- **Templates forced a shape.** Nations worked. Culture didn't: "Velikoye Culture" held the Tsar's Palace.
- **Preview and page were two screens,** so every action had to be built twice, and each screen had gaps the other didn't.

The owner wants something leaner and emergent: "the leaner more emergent rule sets work better than trying to come up with every rule you'll ever need strictly on the spot." Entries are linked to other entries, each one is tagged with what it is, and a page groups what is filed in it by those tags.

## How the owner will judge it

The test is a fresh world and a session like the last ones: owl-folk; the Tsardom with its capital, river and church; a council; a field like runic magic and its parts; a few customs; characters with ties; and a scene.

**Passing means** that following links answers questions the way a reference does. In the owner's words: "What's in Velikoye? … what do they do there? … who runs it?" Lists stay readable as they grow. And anything the owner reads can be acted on right there ("seamlessness, able to act on things right when you read them"), in a draft or on an accepted page alike.

## The model

### Entries
- **Kinds** stay as they are: character, place, lore, item, species, race, mix, being, and event if it exists.
- **The `sphere` kind goes away** (*my call*, following from "spheres survive as prompts"). An entry written with a sphere template keeps its kind: a nation is a place, a faith or order is lore.
- **Tags.** Each entry has exactly one **tag** saying what it is, such as river, ruler, custom, institution, regiment, capital or schism.
  - The tag is a field on the entry, not on a link.
  - The AI picks it when writing the entry, reusing a tag already in use or coining a new one.
  - The owner can change it at any time.
  - Tags apply to every kind, places and characters included. Owner: "rivers and rulers group better."
  - Two tags are never needed, because the kind is the second axis. The Academy is a place by kind and an institution by tag.

### Filing: the one connection
- **An entry can be filed in any number of entries.** A filing has:
  - a **target** entry;
  - optional **dates** (since and until);
  - an optional **role** ("runs it", "presides", "practitioner", "branch of", "flows into");
  - for a person, an optional **within** (a part of the target) and "but…" **exceptions**. These are the fields ties have today.
- **Filing replaces:**
  - `part_of`, and drawers with their filing;
  - **ties**, which become filings with a role (owner: "make ties filings");
  - **the place parent**, so a place can be in several places, like a river (owner: "fold it into filing");
  - **branches** and their inheritance. A branch is an ordinary entry filed in its parent with the role "branch of". Its facts say what it does differently, and the parent's doctrine is one link away. Drops and overrides go.
- **Kept separate:** heritage (species, race, mix and members). It passes traits down, which is a different thing.
- **Mentions** (fact references) stay as they are. They are not filings.
- **Groups come from tags.** A page's Connected section groups what is filed in it by each entry's tag: Velikoye shows Rulers, Institutions, Rivers, Districts, Customs, Palaces. A custom filed in Velikoye and in Vosgrad shows under Customs on both pages, with nothing set up twice. Changing an entry's tag moves it to the matching group on every page it's filed in.
- **Culture** becomes custom-tagged entries filed in places, each over its own dates. The Feather Dance is in Velikoye from 900 to 1015 and in Kerensky from 1012.

### What stays as built

Most of Curation stays as it is, re-pointed where needed from `part_of` and drawers to filing:
- nearness and its knobs;
- repeats, same-thing, held-by and beings;
- merge and Re-point;
- move-in;
- timelines and disagreeing dates;
- the elsewhere list.

In particular:
- **Nearness:** a filing is a link for nearness, replacing the `part_of`, parent and tie weights with one filing weight.
- **Timelines** gather from what is filed in an entry, recursively up to the timeline reach. Timeline entries remain dated facts.
- **Held-by:** the implicit rule that a religion or culture's beliefs drawer counts as held goes, because drawers go. *My call:* an entry written with the religion prompt hint marks its belief facts as held by itself at write time. The owner can set or clear held-by on any fact.
- **The agent flag** carries over as a plain field any entry can have. The prompt hint sets its default.

### Prompt hints (formerly templates)
- The sphere templates (religion, nation, order, culture, field, other) become **prompt hints**. Each is a short text telling the AI what to consider, for example "for a nation: rulers, laws, military, regions, history".
- The owner picks a hint when writing an entry, or none. The AI may suggest one.
- They are stored as plain text files under `src/talemate/prompts/templates/world/hints/`, so the later scene-runner feature can read them and let the owner write custom ones.
- **The core prompt says only named things become entries.** Roles, topics and practices without a proper name stay as facts. This prevents the Night Court's twelve thin stubs.

## The AI files things itself

When writing any entry (create, expand, Fill, or "+ Add" in a group), the reply carries:
- **the tag:** it reuses one from the list of tags in use, which is given to it, or coins a new one;
- **where it is filed ("In"):** existing entries it belongs in, each with an optional role. The candidates are every nearby entry, whether or not anything is filed in it yet. Owner: "it should consider entries that don't have anything filed in them yet in addition to ones that do."
- **what belongs in it ("File into this"):** existing entries that look like they belong in the new one. When the military is made after the White Talon, this offers the White Talon. These arrive **unticked**, like move-ins.
- **It never invents a container entry.** It doesn't make the army just to hold the White Talon. The probe showed it never did. The owner adds containers through "+ in…", which can make a stub on the spot.

All of it shows in the draft as ticks the owner can change. Suggested "In" filings arrive **ticked**: the owner wants the AI "trying to file things".

## The pages

The World tab has **two panes**, the list and the page. There is no Tray.

The list has a search box at the top. Entries are grouped by kind, and a place is shown indented under the first place it's filed in. "Stubs" and "Tags" sit at the bottom.

### An entry page (accepted or draft)

**The header**
- the name;
- a kind chip, which can be changed on a draft or a stub;
- a tag chip, which can be changed and opens the tag picker;
- the other names;
- the prompt hint it was written with, if any.

**In.** One row per filing: the target, the role, the dates, and for a person, "within" and the "but…" exceptions under it. "+ in… 🔎" opens the entry search. Typing a new name there makes a stub.

**Summary,** then **Facts**:
- each row has a "⋯" menu;
- "+ Add facts…" takes a prompt and returns a small draft of facts for the owner to tick.

**Connected.** What's filed in this entry, grouped by tag:
- one line per entry, showing that entry's own summary, plus the role and dates;
- each group can be folded;
- a long group shows a filter box, then its synopsis if one exists, then the first few rows and "show all";
- each group has "✎ Synopsis", "+ Add", and the ability to drag rows to another group, which changes their tag.

**Mentioned in.** Entries that name this one without being filed in it. Folded by default.

**Timeline**
- it gathers what is filed in the entry, as in Curation, with ended facts shown as spans and disagreements offering pick-one;
- "+ Add event…" takes a prompt with a year;
- *my call:* an "Events ▾" filter offers "events only" or "all dated facts", and defaults to all.

### The draft page

A new or expanded entry opens as its real page, marked as a draft. Nothing is written until the owner accepts.

**The bar**
- Version N of M ▾: earlier generations are kept for the session, and any one can be restored;
- ↻ Regenerate;
- Edit prompt;
- **Discard;**
- **Accept.**

**The sections, in order**
1. **In:** the suggested filings, ticked.
2. **"Same thing?":** shown only when there are candidates. It has a search box, and leaving it empty means the entry is new.
3. **Facts.** A fact that repeats one already in the world shows its match, with four choices, each named by the fact it keeps (hubs round 1, P8): "Keep new" (the existing fact is removed), "Keep existing", "Keep both" or "Move existing here".
4. **For other pages:** each row shows a target that can be changed, plus "+ also here".
5. **Could move here:** facts on *any nearby page* that name this entry, unticked, with the name highlighted. This replaces "every fact of the container".
6. **New names:** each with a kind picker, a "same as…" search, an "in…" picker and rename. Rename re-roll is for later, with languages.
7. **File into this:** unticked.

**Prompt additions.** "+ Add facts…", "+ Add event…" and a group's "+ Add" all work on a draft too.

### Menus that work everywhere

These are the same on draft and accepted pages.

**On a fact (⋯ or right-click):**
- Move to… 🔎, using the entry search;
- Copy to… 🔎;
- Held by… 🔎;
- Edit, change dates, end this;
- Remove;
- and the existing cut, copy, paste, select all, undo, redo and spell check.

**On selected words:**
- Make a stub, with a kind;
- Make a stub and expand it now;
- Link to an entry… 🔎;
- Ask about this (shown greyed out; it belongs to the later "dynamic questions" feature).

### Tags

- **The tag picker:** search the tags in use, see how many entries each has, or make a new one.
- **World tab → Tags:** rename a tag or merge it into another, for example "school" into "institution". This updates every entry that carries it.

## Fixed along the way

These acceptance bugs fall out of the redesign or are fixed in it:
- **Changing a stub's kind to sphere fails.** This goes away with the sphere kind. Changing a stub's kind to any kind must work from the hover card, the Stubs page and the expand page.
- **Re-point doesn't add other names.** Fix it. Also add a "hard re-point", where the owner picks which of the target's names replaces the stub's words.
- **No way to cancel a preview.** Discard fixes this.
- **The "No, it's new" toggle and "Make it a sphere" are confusing.** The search-based "Same thing?" replaces them.
- **"Part of a body not yet made…"** is replaced by "+ in…", which can make a stub.

## Scene context, stubs and other fields (*my calls*, from the builder check)

**Scene context.** It is built from filings and replaces the sphere rules.
- **What counts as touched:**
  - the entries the scene's place is filed in, followed upward to the timeline reach;
  - the entries each present character is filed in;
  - entries named in the prompt or the setup.
- **What a touched entry shows:** its summary, then up to 5 of its own facts (the most-linked first), then its latest 3 timeline lines, at most 8 lines in all. Held facts are worded as held.
- **The agent flag** no longer changes context. It stays as a field the prompt hints set.
- **The wording of the scene's world block changes,** so a probe runs first (probe 5 below).
- **The scene's place** is still one entry. A place filed in several places brings each of those in as touched.

**One writer.** Every write uses `create-thing`, given a hint. The sphere core, Fill and branch prompts go, because without a drawer outline there's nothing for a two-step core to protect.
- **"+ Add" in a group** writes 1 to 3 new entries from the owner's prompt, tagged with the group's tag and filed in the page's entry. They come back as **draft rows inside the group**, where each row has a tick, a name the owner can edit, a kind, and its one line. Accept makes them stubs with that line as their first fact. Each can be expanded later into its own draft page.
- **The top-level "+ Add"** works the same way with no tag preset.

**Stubs.**
- **Tag and filing:** every name in a reply's `names` list carries a tag and, optionally, the AI's suggested filing, which arrives ticked as with any "In". The New names rows gain a tag picker.
- **Hand-made stubs:** a stub made from selected words or from "+ in…" asks for a kind and a tag, offering a default.
- **Unfiled stubs** show under the naming entry's "Mentioned in", not under Connected.
- **Untagged entries** sit in an "Other" group.

**Belief facts.** An entry written with the religion hint (and with culture or order, where it applies) gets a `belief` fact category. Facts written in that category are marked as held by the entry. This rests on the model choosing a category, which has been reliable, rather than on its held-by tagging, which scored 20%. Probe 4 tests it, and the fallback is tagging by hand.

**Within** must be an entry filed in the target, directly or further down. The person shows on both pages: the target's, with "within X", and the within entry's. Real beings count as persons.

**Heritage** is not shown in Connected. Species and race pages keep their heritage sections, which list races, mixes and members.

**"Could move here"** is found by code alone: facts that name the entry, on nearby pages. The model's `move_in` reply field is dropped, since it scored 0 of 18. Probe 1 covers the changed create reply.

**Other fields:**
- `event.place` and `item.owner` become filings, with the roles "took place in" and "owned by".
- The place `kind` text field is replaced by the tag.
- The legacy `culture` kind is removed; this is a fresh world.
- The character `culture` field, the place `cultures` shares and the culture `language` field are removed and become ordinary filings. A character is filed in whatever holds its culture, with the role "of this culture". A place's share of a culture becomes the role on its filing, for example "60% of the people".

## Cultures and languages (owner)

There is no special culture structure. The owner put it like this: "we are building the same system regardless of the pick, and that system functions with both picks."
- **Organised in one entry:** a culture can be an ordinary entry, for example "Moscavian culture" tagged "culture". Customs, places and characters are then filed in it.
- **Spread across places and peoples:** customs can instead sit directly on places, or on peoples (species and races).
- **Languages, next slice:** a language attaches by the same tools. It is an entry filed in a culture, a place or a people. Nothing in this design fixes which.

## Non-goals

These are for later and are recorded for their slices:
- **With languages:** rename and re-roll a name using the AI, getting a list of choices; re-roll in a language, where one is suggested but the owner can pick.
- **After languages:** "dynamic questions" ("How was this enchanted?"), which expand an existing field or entry with facts that answer the question.
- **Custom prompt hints:** writing your own, through the scene-runner feature.
- **No migration of old worlds.** The owner starts fresh.
- **No graph view.**

## Anti-goals

- **Thin entries for roles and topics.**
- **A second UI for drafts** that drifts from the page.
- **Anything moved, filed or written without the owner's tick.** Suggested "In" filings arrive ticked, but they are still shown before Accept.
- **Groups the owner has to maintain by hand.** Tags do the grouping.

## Constraints

- **The world store stays pure.** `world/` is strict-mypy and imports nothing from the rest of talemate.
- **Every multi-write action is one revision,** undone exactly.
- **Fact moves copy with a new id** (R1), and the client's rows are recomputed on the server.
- **The store changes:**
  - a `tag` field on every kind;
  - a `filings` field: a JSON list of {target, role, since, until, within, exceptions}, or an equivalent table. This is left to the builder, but it must be versioned and dated like other fields;
  - remove `part_of`, `ties`, the place `parent`, the sphere fields (`template`, `drawers`), branch `parent`, drops and overrides.
- **Probe-mandated prompt wording** changes only with new probe evidence. This redesign changes the create, core and Fill replies, so probes come first (below).
- **Browser tests** use at most 4 workers. The owner is asked before any AI tests; probes need approval.

## Probes (before the features they serve)

The owner approves each probe. The labels are set before the run, on a copy of an acceptance world.

1. **Tag and filing in the create reply:**
   - Does Skyfall pick sensible tags, reusing the existing list most of the time?
   - Does it suggest the right "In" filings, with roles? Cases: the river in the Tsardom and Velikoye; the Academy in Velikoye and Runic Magic; Plumage Signaling in the Owl-folk and the Night Court.
   - Does it stop minting thin stubs under "only named things become entries"?
2. **File into this:** when the military is made after the White Talon and the Frosted Wing, does it offer them? It must offer nothing false.
3. **A group synopsis:** a nation's rulers and officials, a city's institutions. Check that it is accurate to the entries and that nothing is invented.
4. **Prompt hints:** does a nation or religion hint still draw out the important facts drawers used to force (rulers, doctrine, rites), without the drawer structure?
5. **The scene's world block:** filing-based touched entries, with the wording above. Does the narrator use what it's given without the context flooding?

The pass bars and fallbacks are as in Curation: at least 80% right and at most 5% false. A failed suggestion falls back to "shown, unticked". A failed synopsis falls back to off.

## Left to the builder

- The storage shape of filings, field or table, under the versioning rule.
- The nearness weight for a filing.
- How Connected sorts within a group: by role, by date, then by name.
- How long a group gets before it folds, and the "show all" behaviour.
- When synopses are cached and refreshed (on a change to the group's members).
- How the list pane indents places that have several filings.
- The exact wording of the prompt hints, from the probes.
