# Cultures and languages: design

Date: 2026-10-17
Status: draft for review
Background: `docs/ideas/index.org`, `docs/ideas/languages.org`
Look and feel: clickable mockup at https://claude.ai/artifact/8gNmqtRbpBdGHxswpf7iZD (version 4). The mockup is the reference for layout and interaction. Its sample world (Taelrik, Elsiri, Ghûn, Veldhaer…) is example content only.

Marking used below:

- **Decided** means the owner said so.
- **My call** means the designer chose and the owner hasn't confirmed it yet; it can be revisited.
- Anything not marked is left to the builder.

## 1. Intent

The owner plays one fantasy world that keeps growing across many stories. These are scenes in one Talemate project, linked to one Shared World context. Without a reference, the storyteller mixes French-ish, English-ish and generic fantasy names in one region, and no culture gets a voice of its own.

This feature gives every culture in the world a consistent source of names and words, and makes the story use them:

- New people and places are named in their culture's language.
- A character who "curses in Taelrik" uses real Taelrik curses.
- A toll-house inscription is a real Taelrik saying, and the reader can click it to see the translation.
- Once a name is used, it stays the same in every later story.

**Decided:** languages are built as the **first part of a culture system**. The culture system grows in later stages (customs used in play, holidays on the calendar, regions on the map). This first version builds:

- the culture record
- a place record that cultures attach to
- languages, filled in completely

**Decided:** this feature comes before the world map and calendar, because languages name the places the map will hold. The place record designed here is the one the map builds on.

## 2. Goals

1. Names for people, places and things fit their culture, every time.
2. Phrases, sayings, curses and short lines in a culture's language appear in the story when it calls for them, drawn from that language's stored dictionary and phrase list.
3. A name stays the same across scenes and stories once it has been used, because every coined name goes into a world-level glossary.
4. The AI works out which culture a new person or place belongs to. The owner can disagree and change it, which is how most things in Talemate work.
5. Foreign words in the story are highlighted the way names and objects are today. Clicking one shows its translation.
6. The owner reviews what the AI added (names, cultures, additions to a culture) whenever they like. Review never blocks play.
7. Fixing a name updates the places where it has already been used.

## 3. Non-goals

- **Decided:** the local storytelling model does not design languages or cultures. A Claude Code skill does that with the owner, outside Talemate (section 9).
- **Decided:** this is not a translation engine for long passages. Short phrases and lines are the scale.
- Customs, holidays, and food & dress are stored and given to the storyteller as text. They are **not** given dates, calendar logic or game mechanics in this version.
- Law and governance are not part of a culture (see 5.3). They are not built in this version at all.
- No map, coordinates or travel. The place record only holds what cultures need.

## 4. Anti-goals: failures even if it technically works

- **Play gets noticeably slower.** Extra model calls happen only when a new character is created or after a world state snapshot, never on every narrator turn.
- **Ordinary English words get highlighted** as foreign words.
- **Review becomes a chore that gets in the way.** Nothing waits on review: unreviewed items are used immediately and just carry a marker.
- **A rename silently damages saves.** For example, it replaces part of another word, or it can't be undone.
- **Context bloat.** The storyteller's prompt fills up with dictionaries. Only what the current scene needs goes in.
- **A culture that can't be written gets fake spelled-out speech** instead of described speech.

## 5. The world model

All of this is world-level data, shared by every scene linked to the same Shared World context.

### 5.1 Culture

A culture is a people with a way of life. Its fields:

- name
- display colour (used for chips and mix bars)
- description ("who they are")
- its language (one per culture in this version, **my call**)
- customs: a list of short statements
- food & dress: text
- holidays: a list of name, when (plain text, e.g. "first frost") and description

The record keeps room for later sections, shown as such in the UI. Real holiday dates arrive with the world calendar.

**Decided:** the Claude Code skill seeds a culture's core: description, language, customs, holidays, food. It can never write everything a story will need. The storyteller adds to the culture during play, and each addition is stored marked *unreviewed* (section 8).

### 5.2 Language

A language sits at one of three levels (**decided**):

1. **Description only.** How it sounds and how to describe it being spoken. Used for species whose speech can't be written in Latin letters (tones, clicks, hums).
2. **Naming rules.** Sounds and syllable rules, plus name generators.
3. **Full language.** All of the above, plus grammar notes, a dictionary and a phrase list, enough to work with short phrases.

Fields:

- name
- level
- writable yes/no
- description of how it sounds
- sounds (consonant and vowel inventory)
- syllable patterns and constraints
- name generators
- grammar notes (full only)
- dictionary entries: word, meaning, part of speech, notes (full only)
- phrases, grouped by category such as sayings & blessings, curses, greetings. Each phrase has the original, a translation, an optional word-by-word breakdown, and a usage note.

**Generators (decided: rule-based, not Markov chains).** A generator is named by what it makes ("Given names (male)", "Place names", "Inns & halls") and tagged with what it is for: people, places or things. It is built from the language's sound categories and syllable patterns, with optional parts, weights and reject rules, in the style of Lexifer or Vulgarlang. One run returns a batch of candidates (about 20). The same rules can also check whether an existing name "fits" the language, which is used for flagging in section 7.4. The builder defines the exact rule syntax as part of the import format (section 9).

**Unwritable languages.** A thing named in an unwritable language has its true name stored as a description ("three falling hums ending in a tongue-click"), plus one rendering per other culture: "Khaz-Rull" in Taelrik, "Kasrool" in Elsiri. **Decided:** renderings are worked out once (by the skill or by hand) and stored. Talemate does not convert them automatically.

### 5.3 Place

Talemate has no place record today, only world entries. This feature adds one. Its fields:

- name
- kind: country, region, city, town, village, building, point of interest, terrain feature (the map's list)
- parent place (places nest)
- cultures: an optional list of culture and share pairs
- link to a world entry, for its description (optional)
- who set the cultures: AI or owner
- an "AI unsure" flag

How a place's cultures work:

- **Decided:** cultures attach to places and regions as well as to people. In a scene, the **most local** place with cultures set decides who you meet.
- **Decided:** a place can hold several cultures, each with a share. A trade-hub city might be Taelrik 55 / Elsiri 30 / Vaskari 15. A mix like that means a blend of people, unlike a pocket.
- **Decided:** a pocket is a child place with its own cultures inside a parent with different ones. Example: the Elsiri Birch Coast inside the Taelrik Reach.
- **My call:** a place with no cultures of its own takes them from the nearest ancestor that has them.
- **My call:** people in a pocket usually also speak the surrounding country's language. The Birch Coast Elsiri also speak Taelrik. This is told to the storyteller; it isn't stored per person.
- **Decided:** law and governance belong to a place, usually a country, shared by all the cultures under it. This version only reserves room for that and shows it as "later".

The map will add coordinates, terrain and so on to this record later. Nothing in this version should make that hard, so place ids must be stable and places must not be keyed by name.

### 5.4 Culture of a person

A character carries one culture (**my call** for this version). It is stored with the character as world-level data, so it follows a shared character into every linked scene. The AI sets it, with a "set by AI / by owner" marker and an unsure flag. Once the owner changes it, the AI never changes it again. The same rule applies to place cultures.

### 5.5 Glossary

Every coined name or word goes into the glossary the moment it's used (**decided**). An entry holds:

- text
- language, or none for unassigned
- kind: person, place, thing, word
- meaning (optional)
- renderings in other languages
- where it came from:
  - by the AI from a generator, recording the generator and every candidate it was offered
  - by the AI freely, with no language
  - from an import
  - by the owner
- where it was first used: story, plus scene or message
- reviewed / unreviewed
- links to the character or place it names, if any

**Unassigned names.** **Decided:** the AI may invent a name with no language behind it. Such names go to an "Unassigned names" pile, so they stay stable in later stories. Later the owner may design a language and assign each one, either keeping the name as it is or replacing it with a proper one (which is a rename, section 8.2).

### 5.6 Where it's stored (my call)

Everything is stored in its own files next to the Shared World context file, not inside it:

```
scenes/<project>/shared-context/<context-name>.json      (existing, unchanged)
scenes/<project>/shared-context/<context-name>.world/
    cultures/<culture-id>.json   (culture + its language)
    places.json
    glossary.json
```

Why:

- The shared context file is diffed and rewritten on every save, and `SharedContext` has no extension point. See `src/talemate/shared_context.py`; adding fields needs edits throughout `init_from_file` / `update_*` / `clean_up`.
- Separate files keep the feature self-contained and easy to merge from upstream, and dictionaries would bloat that file.
- Tying the folder to the context file means a scene that isn't linked to a shared world has no cultures. A scene forked from the timeline is already cut off from its shared context, so it is cut off from cultures too. **Decided:** that's acceptable.
- The Cultures tab in a scene without a shared context shows a prompt to link or create one. It reuses the existing Shared World flow.

A character's culture is the one exception: it is stored as a character field and syncs through the existing shared-character mechanism.

Saves must be safe against crashes and simultaneous edits: write to a temporary file, then rename it into place. Edits from the open scene are written straight away; they don't wait for a scene save, because the data is shared.

## 6. The screens

The mockup is the reference.

### 6.1 World Editor → Cultures tab (decided: a new tab in the World Editor)

The tab is added to the World Editor's top tabs, after Suggestions. It shows a count badge of unreviewed items. The app-level World Editor tab shows the same count.

The left drawer has:

- **Create**: "Import culture" (section 9).
- **Cultures**: each culture with its colour, language and level, plus its unreviewed count.
- **Where they live**: "Places & regions".
- **Not yet in a language**: "Unassigned names".
- A short note saying this data belongs to the shared world.

The main area has the usual compact toolbar with save state and the file chip.

**A culture's page.** The header shows the culture's colour and name, a chip "Speaks <language> · <level>", the source file and import date, and a **Re-import** button. Sub-tabs:

- **Culture**:
  - who they are
  - where they live: places with this culture and their share, as mix bars
  - its language, with a link to the Language tab
  - customs, with play additions shown inline for Keep / Edit / Drop
  - food & dress
  - holidays (with a note that real dates come with the calendar)
- **Language**: how it sounds, counts, sounds and syllables, grammar notes.
- **Glossary**:
  - Filter chips: Not reviewed (default) / Reviewed / All, plus a text filter.
  - A table: name, kind, meaning, first used in, added by.
  - A detail panel for the selected entry:
    - where it came from, including for AI picks the generator and every candidate, with the chosen one marked
    - name, language and meaning fields
    - renderings in other languages
    - first use
    - actions: **Looks right** (marks it reviewed and saves any edits), **Pick another** (only for generator picks; offers the passed-over candidates or a fresh roll), **Remove**
- **Dictionary**: a searchable table (full languages only).
- **Phrases**: grouped cards (full languages only).
- **Generators**: each generator with its rule summary and a **Roll** button showing sample output.

Tabs a language can't fill are hidden. A description-only language shows its description and a table of how other cultures render its names.

**Places & regions.**

- A nested table of places: name, kind, its own cultures (or "from <parent>"), and a mix bar.
- A detail panel for the selected place:
  - per-culture share sliders that always add up to 100, and Add culture
  - "Set its own" for places that currently inherit
  - a plain-language reading of what the mix means in a scene, e.g. "about 9 in 10 Elsiri, 1 in 10 Taelrik… most also speak Taelrik, the language of The Taelrik Reach"
  - who set it
  - the AI-unsure note
  - for countries, a "Law & governance, later" placeholder
- Places the AI was unsure about carry the review dot.

Adding, renaming, re-parenting and deleting places all happen here. Deleting a place with children asks where the children go.

**Unassigned names.** The same table and detail panel as a glossary. Changing the Language field assigns a name to a language.

### 6.2 In the story

Highlights follow `talemate_frontend/src/utils/sceneMessageRenderer.js` and `components/EntityTooltip.vue`.

- **Names** (people, places, things) keep the existing amber dotted-underline highlight. Their bubble gains a language section:
  - the language chip and meaning
  - the culture, with "worked out by the AI from <place>" and a **Change** button
  - for an unwritable name, the true-name description plus each culture's rendering
  - if unreviewed, a small amber dot on the highlight and a note in the bubble ("added this session, not reviewed yet; picked from <generator>") with a **Review** button that opens that entry in the Cultures tab
- **Foreign words and phrases** (**decided:** highlighted like names, translation shown in the bubble; **my call:** blue dotted underline, in italics) get a bubble showing:
  - the text, a kind chip (word / saying / curse / inscription) and the language
  - the translation
  - the word-by-word breakdown when stored
  - the usage note
  - **Open in <culture>**
- What gets highlighted as a foreign word: stored phrases and glossary entries of kind word or thing from the cultures present in the scene. Single dictionary words are highlighted only when they can't be mistaken for English. The builder picks the rule, but anti-goal 2 must hold.
- The scene's World panel (left drawer) shows a culture chip next to each character and place, and a review dot for unreviewed ones.

## 7. How the AI uses it

**Decided:** the storyteller is a local model, so nothing depends on it calling tools reliably. Choices are made in separate, small steps around narration.

### 7.1 Which cultures are in the scene

The scene's current place is found as follows:

1. Match the world state's `location` (and the places in the snapshot) against place records.
2. If it's unknown, create the place, marked AI and unreviewed. Its parent and cultures are inferred from context, with the unsure flag set when the guess is weak.

The scene's cultures are then that place's effective mix plus the cultures of the characters present.

### 7.2 Getting it into context (my call)

A dedicated agent, the **Culture agent**, connects to the `agent.narrator.inject_instructions` and `agent.conversation.inject_instructions` signals. The working example is `agents/summarize/analyze_scene.py:163-181`. Through them it adds one compact `DynamicInstruction` section. The section contains:

- the current place, its mix in plain words, and the "also speak <outer language>" note
- for each culture present: a short description, the most relevant customs, and how its language sounds
- for unwritable languages: an explicit instruction to describe the speech, never spell it out, and to use the culture-appropriate rendering for names
- the names already in the glossary for the people and places present, so they stay consistent
- for a character whose sheet mentions using a language (e.g. "curses in Taelrik"): that language's matching phrase category, a few entries with translations, and an instruction to use those exact phrases
- **a few pre-rolled unused names** from the local culture's place and people generators: "if you need a new name, use one of these". This is how names the narrator coins on the fly come out in the right language without a tool call.

The section has a size budget, set in the agent's configuration, and is trimmed to fit. Customs, food and holidays go in only when relevant, e.g. a holiday is named when the scene is set at that time.

### 7.3 Naming a new character

**My call: the name is chosen *before* anything else about the character is written**, so the description, attributes and dialogue are written with the culture's name from the start. Swapping the name afterwards (e.g. at `before_persist_character`) is not used, because by then the fast one-shot prompt and split mode's `_determine_split_name` have already written the old name into the sheet.

This means a small new hook in core, on the list in section 10. Both places that settle a name call it before generating the rest of the character:

- split mode: `_determine_split_name` / `creator.determine_character_name`
- fast mode: the fast one-shot generation, `generate_character_unified` / `_fill_aspect_name` / `creator/generate-character.jinja2`

There are two acceptable ways to do it:

- **Pre-supply the name.** The hook returns a chosen name, which is passed in as already decided.
- **Constrain the choice.** The hook injects the candidate list into the name-determination prompt with "choose one of these".

The builder picks one per path. All creation entry points have to be covered: `agents/director/character_management.py:482-560`, `agents/creator/character.py:449,704,991`, the director websocket handler and the creator and director nodes.

**My call: names that already exist are never replaced.** The culture agent only names a character when the AI is naming freshly. It leaves the name alone when:

- the owner typed it, or
- it already appears in the scene's messages (the narrator wrote it first).

In those cases the existing name is kept and goes to the glossary as in 7.4, flagged if it doesn't fit.

The flow:

1. Decide the culture: the creator's own description if it names one; otherwise the scene's place mix, picking a culture by share; otherwise the cultures of related characters. Set the unsure flag when the guess is weak.
2. Pick the matching generator (e.g. given names, female; family names) and roll about 20 candidates.
3. A small model call picks the one that best fits the character and moment, and may say why.
4. Set the name, store the culture on the character, and add a glossary entry (unreviewed, with generator and candidates).

If the culture has no generators (description only, or no culture at all), the existing naming is kept and the name goes to the glossary as unassigned, or under the language with a rendering.

### 7.4 Spotting names during play

**Decided:** the hook is the World State snapshot (`agents/world_state/snapshot.py`). No async signal fires after a snapshot today. The builder adds one, e.g. `world_state.snapshot.after`, in core; this is one of the few core edits.

After each snapshot, character and place names are checked against the glossary. So are item names, but **only proper names** (**my call**): a named ship, sword or inn, not "lantern" or "rusty sword". The test is a cheap rule, not a model call: capitalised mid-sentence and not a common English word. The builder can refine the rule.

The check:

- **New name:** add it to the glossary, unreviewed, under the culture of the person or place, or unassigned if there is none.
- **Known name:** nothing to do.
- **New name that doesn't fit:** checked with the language's rules. The entry gets a "doesn't fit <language>" flag shown in review. It is still added.

New places found this way also get a place record (7.1).

### 7.5 Additions to a culture during play

When the storyteller states something new and lasting about a culture (a custom, a dish, a holiday), it is recorded as an unreviewed addition to that culture. In the mockup, "ferrymen spit over the rail before landing" is one such addition. The builder decides how these are detected. A post-snapshot check that runs only on scenes where a culture is present is the expected route. It must not run every turn (anti-goal 1).

## 8. Review and rename

### 8.1 Review

**Decided:** everything the AI adds is used immediately and marked unreviewed. The owner reviews later, and review never blocks play.

The unreviewed items are:

- glossary entries
- AI-set cultures on characters and places, when the AI flagged them as unsure
- culture additions from play

Counts show on:

- the World Editor app tab
- the Cultures tab
- each culture in the drawer
- the Glossary sub-tab
- the Unassigned pile
- Places & regions

From any review dot or **Review** button in the story you land on that item.

### 8.2 Rename everywhere

**Decided:** fixing a name updates where it's already used.

When a name changes (edited by hand, Pick another, or an unassigned name given a proper one):

1. A confirmation dialog lists every place the old name appears, all ticked by default. It offers **Rename everywhere**, **Glossary only** and **Cancel**. Grouped by:
   - each scene **linked to this shared world** (**my call**): story messages, history (archived and layered), character sheets, world entries, world state
   - the shared world: shared characters, shared world entries, static history
2. Matching is whole-word and handles possessives ("Tovrin's"). It never touches a name that is part of a longer word, and it is case-aware.
3. Scenes forked from the timeline are not touched (**decided**). Nor are scenes linked to a different shared world or to none (**my call**). The dialog says so. Linked scenes are found by reading each scene file's `shared_context` link in the project folder.
4. The open scene is changed through its normal edit paths, so its changelog and memory stay correct. Other scenes are changed and saved safely, and their memory is rebuilt the next time they load.
5. Before writing, each file that will change is backed up to `<project>/.rename-backups/<timestamp>/`, so a rename can be undone by hand. A built-in undo is not required.
6. Renaming a character's name also renames the character itself. This needs care, because Talemate keys characters by name in `character_data` and in the shared context.

## 9. The culture-design skill and import

### 9.1 The skill (part of this feature, decided)

A Claude Code skill, `culture-design`, designs a culture with the owner. **My call:** it ships in this repo at `.claude/skills/culture-design/` so it changes together with the import format. It:

- interviews the owner and produces the culture's core: description, customs, food & dress, holidays, and its language at the chosen level (sounds, syllable rules, generators, and for a full language grammar notes, dictionary and phrases)
- can read the world's other cultures, to make renderings of names into and out of an unwritable language, and to keep neighbouring languages distinct
- can read an exported culture, including play additions and unassigned names, and extend it. For example, it can claim unassigned names that suit the new language.
- tests its generators before writing, by producing sample names, and validates its output against the JSON schema

### 9.2 Import format (decided: ours to choose)

One JSON file per culture, `<culture-id>.culture.json`, with a `format_version`. It contains:

- the culture
- its language, including the generator rule syntax (section 5.2)
- optional glossary entries
- optional renderings of other cultures' names

A JSON Schema for it is kept in the repo, used by both the skill and Talemate's importer.

**Import:**

1. A preview shows what's in the file and how it relates to the world:
   - new or updating an existing culture
   - counts
   - unassigned names it claims
   - places it mentions that already exist
2. Confirming writes the file into the world folder.

**Re-import (my call):**

- Play additions are a separate, tagged list for good, including those the owner has kept. The culture page shows them merged into their section (customs, food, holidays). Re-import never removes them. The preview lists any that the file now contains too, so they can be merged, and doesn't duplicate them.
- Replaces the culture's and language's core sections with the file's.
- Never deletes glossary entries, places or play additions that exist only in Talemate.
- When both sides have the same glossary entry, Talemate's copy is kept if the owner has reviewed or edited it. The preview shows these conflicts.

**Export:** writes the culture back out in the same format, with play additions and new glossary entries, so the skill can extend it.

## 10. Where the code goes

**Decided:** the feature lives in the fork `AndSnowl/talemate` and keeps edits to existing files few, so upstream merges stay easy and the feature could later be offered upstream.

- **Backend.** A new package, e.g. `src/talemate/cultures/`, holds the models, storage, generator engine, place-mix resolution, import/export and rename. A `CultureAgent` provides:
  - signal hooks
  - its configuration (enable, context budget, candidate count)
  - a websocket handler, following the `websocket_handler` class-attribute pattern in `agents/world_state/websocket_handler.py`
- **Frontend.** New components, e.g. under `talemate_frontend/src/components/cultures/`, registered as a World Editor tab (`WorldStateManager.vue`).
- **Expected small core edits:**
  - the World Editor tab registration
  - the second highlight kind in `sceneMessageRenderer.js`
  - the bubble additions in `EntityTooltip.vue`
  - a post-snapshot signal
  - a culture field on `Character` and its shared-context sync
  - the pre-naming hook in character creation (7.3)

**Tests:** pytest under `tests/`, covering:

- the generator engine and "fits" check
- storage round-trip and safe writes
- import validation, re-import merge and export
- effective place mix (inheritance, pockets, shares)
- culture choice and name pick on character creation (with the model call stubbed)
- glossary update after a snapshot
- rename across scene files, including word-boundary cases and backups

The frontend has no test setup; check it by hand against the mockup.

## 11. Related things found while designing

These aren't part of this feature, but the builder should know about them.

- **Shared world entries get overwritten on load.** `load/__init__.py:348` applies shared world entries, then `:361` replaces `scene.world_state` from the scene file. Shared world-entry edits made in another scene are therefore lost on load.
- **Stale loop variable.** `shared_context.py:114` calls `set_shared(False)` on the stale loop variable `scene_character` instead of `character`.
- **Shared context only saves with a changelog.** Shared context is only committed on save when the scene has a changelog (`tale_mate.py:1932-1936`). This feature's own files don't depend on that.
- **Deployment.** Before any of this can be used on the GPU server, the server has to build from a branch of the fork (`docs/ideas/index.org`, "Deploying the fork"). That's a separate task.

## 12. Left to the builder

- The exact JSON schema and generator rule syntax.
- The rule for which single dictionary words get highlighted.
- How culture additions during play are detected (7.5).
- The model-call prompts for the culture guess, the name pick and the place inference.
- Whether places can link to more than one world entry.
- Exact wording and layout details beyond the mockup.
