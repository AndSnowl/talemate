# Fantasymate: Connections between entries

Date: 2026-10-21. Status: design, awaiting the owner's approval.

This is the slice after phase 2 plan B (species, races, mixes and inheritance, merged on 2026-10-21). The owner chose it ahead of cultures because every section relies on it. It builds on:
- the main spec, `2026-10-18-fantasymate-world-data-model-design.md`, especially "Connections between entries" and "Named things that don't exist yet", which this slice takes in;
- plan B's spec, `2026-10-20-fantasymate-phase-2b-heritage-design.md`.

The mockup the owner approved is `.superpowers/brainstorm/12463-1792596708/content/connections.html` (not committed). "The screens" below describes it.

## Intent

The owner fills in a world by following details from one entry to the next. The owl-folk's origin names the "Tsardom of Moscavia", so the next step is to make the Tsardom. The Tsardom's facts then name its capital, cities, rivers and mountains, and each of those is a next step in turn. Today every one of those names is plain text. The model doesn't know an existing entry is meant, so a place prompt that says "Moscavian Owls" invents a new species inside the place's facts. And nothing marks the names that still need making.

Connections makes the links between entries real and lets context flow along them, the way a character's species already shapes the character:
- important names are found, highlighted and linked;
- names that don't exist yet become stubs you can follow;
- generating something brings in what the rest of the world already says about it.

**The owner's measure** is that a place is written knowing who lives there: "now that it's fully aware of the inhabitants of that location, it will cater it more so to those inhabitants and their known history and qualities." It is "a generalized version of what I already saw with tying species to characters."

## How the owner will judge it

A session like plan B's, in a fresh world:
1. Make the owl species again, with its origin naming a country.
2. Make humans.
3. Make locations, by following the stubs: the country first, then the cities, rivers, lakes and mountains its facts name.

**Passing means:**
- The country, created from its stub, reflects the owl-folk's origin and nature.
- The names the generations invent show up as stubs, and following them is natural.
- Naming an existing entry in a prompt ("Moscavian Owls") links to it rather than inventing a duplicate.
- Plan A's and plan B's anti-goals still hold: no slower turns and no hidden context.

## Goals

### Shared name-finding, built once

A single part finds the important names in a piece of text and resolves each to an existing entry, a stub, or new. It lives in `worldplay`; the matching itself can sit in strict `world/` code wherever it doesn't need the model.

**This slice wires it to the world side:**
- create prompts;
- generated facts;
- generated prose.

**Later slices reuse it** (owner): scene messages, the inbox and mention records (plan D). The scene prompt's existing name matching (`setup.match_names`) moves onto it, so scene setup and the create box behave the same.

**What counts** (owner): proper names only. Places, characters, named events and other named things count: "Yelena" in "his mother Yelena" counts. Generic descriptions don't: "the postmaster", "a war", "his mother".

### Highlighting and links

**Two styles, everywhere names appear:** in fact text on a thing page, in generated prose, in a create preview, and as you type in a create prompt.
- **An existing entry:** a solid link to it.
- **A stub:** a different colour with a dashed underline.

**Hovering a stub** shows:
- its name and "not made yet";
- its kind, which is a guess;
- its mention count;
- Expand and Ignore.

Clicking a stub opens its create box (see "Expanding a stub").

**References are stored by id and keep the words written.** A name found in a fact is stored as a reference to the entry or stub, carrying the text actually written: `[[thing:<id>|Moscavia]]` for "Moscavia" meaning the Tsardom of Moscavia. *My call*, so linking never changes the wording, which is an anti-goal.
- A reference with no shown text (the existing `[[thing:<id>]]` form) renders the thing's name, as today.
- After a rename, a shown text equal to the old full name follows the rename. Any other shown text ("Moscavia", "Yelena's") stays as written.

### Other names ("also known as")

Every entry has a main name and a list of other names (owner, 2026-10-21).
- **The main name is always the most proper one:** "Tsardom of Moscavia".
- **Other names are tagged:**
  - **proper:** another formal name;
  - **common:** what people in the world actually call it, such as "Moscavia", "the Tsardom" or "Moscavian Owls".

  One common name can be marked as the everyday name.
- **Why the tags** (owner): so the AI doesn't fill stories with full proper names. When an entry has an everyday name, prompts give it alongside the main name, e.g. "Tsardom of Moscavia (usually called Moscavia)", and ask that it be used in narration and dialogue. *My call* on the wording; tune it in the probes.
- **Where other names come from:**
  - the AI suggests some, tagged, when it creates an entry or expands a stub (the owl-folk's origin can give "Moscavian Owls");
  - every time the owner re-picks a match by hand, the written name is added as a common name;
  - the owner can add, edit, tag and remove them on the entry's page.
- **Matching** (*my call*, agreed by the owner):
  - the main name and every other name link automatically, in code, as you type;
  - looser matches, such as one word of a longer name, are only offered as suggestions on hover;
  - no model call is made while typing.
- Other names have timelines like other fields, so a place can be renamed in 1020 and keep its old name for earlier scenes.

### Stubs

A stub is a real entry of its kind (character, place, event, lore, species and so on), marked as a stub. It holds:
- its name;
- a guessed kind, which the owner can change (owner: a decision-model job later; for now the AI's own reply or the code guesses);
- links to every fact that mentions it, and its mention count.

**Made automatically** (owner): accepting an entry turns every new proper name in its facts into a stub at once, with no confirmation step.

**Facts written or edited by hand** (*my call*):
- Names of existing entries and stubs are linked automatically, in code.
- An unknown capitalised phrase is highlighted as a suggestion, with "make a stub" on hover. It doesn't become a stub on its own, because without the model the app can't tell a name from a capitalised word.
- Existing worlds get no one-time pass: the owner starts a fresh world for each milestone.

**Generated prose** is highlighted only (*my call*). Its links come from the facts it was written from, and new names found only in prose don't become stubs. That follows the rule that prose is never fed back into the facts.

**Where stubs show:**
- in a dedicated **Stubs** tab: name, kind, where it was first mentioned, mention count, Expand, Ignore;
- dimmed, under a "Stubs" heading, in their kind's own list;
- in a small "stubs this entry named" section on the entry that named them. The owner was unsure about this one and approved it in the mockup.

**Ignoring a stub** (owner):
- it's hidden everywhere: no highlight, and off the lists;
- it isn't deleted;
- "show ignored" on the Stubs tab lists it.

**Revived on use** (owner): an ignored stub comes back if something needs it. Example: scene setup pulls Aldric in from Vasha's relationship facts and needs a character sheet. Aldric is un-ignored and filled out into a full entry. Expanding an ignored stub by hand revives it too.

**Made real:** once a stub is expanded into a full entry, every mention of it is a normal link.

**Two of the same name:** a second mention links to the existing stub or entry, and the owner can re-point it with the scene prompt's re-pick. *My call*, following plan A's "the owner's choice always wins".

### Expanding a stub

**What the create box is creating** (*my call*): names in a prompt are context, and a create box fills a stub only when it was opened from that stub, by clicking it or pressing Expand. One exception covers a typed name: if a new preview's name matches a stub of the same kind, the preview offers "fill the stub *X* instead of making a new one", and the owner chooses. This avoids both duplicates and stubs being overwritten by accident.

Opening a stub this way gives the create box for that stub, prefilled with a **suggested prompt** made from its mentions. Example: "The Tsardom of Moscavia: the country where, in 994, everyone turned into owl-folk overnight." The owner may edit it. *My call:* the suggestion is assembled in code from the mentioning facts; the owner said the bare name would also be fine.

**The context the AI gets** when creating from a stub, or when a prompt names something:
- **Mentioned in:** every fact, in any entry, that mentions the thing.
- **About those:** the key facts of each entry that mentions it. For example, the owl-folk's body, instincts and numbers when expanding the Tsardom. This is what lets a place reflect its inhabitants.
- **Named in this prompt:** the facts of each existing entry the prompt names, as scene setup does today.
- **Capped** so a much-mentioned capital doesn't flood the prompt. The cap and what counts as "key facts" are settled by a probe (see "Probes").

Accepting writes the entry in place of the stub, under the same id, so every existing reference simply becomes a real link.

### Create prompts reuse scene setup's matching

The create box gets the same behaviour as the new-scene prompt:
- names highlight as you type;
- hover to re-pick a match, e.g. "Moscavian Owls" → the Owl-folk species, or mark it "treat as new";
- the matched entries' facts go into the context.

The owner's choices always win, as in plan A.

### Add reference by hand

Right-clicking in any text box where the owner writes (a create prompt, a fact form) opens a menu with **Add reference…**. That opens a small search in place, over entries and stubs, and inserts a reference at the cursor. It works alongside the automatic matching. *My call:* the custom menu keeps the browser's cut, copy and paste items.

### Scenes and stubs

When a scene prompt names a stub, or scene setup pulls one in from a world thing's facts, setup fills the stub out into a full entry before the scene starts, ignored stubs included. *My calls:*
- **Planning writes nothing,** as in plan A. The filled-out entry is a preview, shown in the setup cards like other world things and editable there.
- **It's written to the world when the scene starts.** Cancelling setup leaves the stub as it was.
- **Names the new entry invents become stubs** when it's written. They aren't followed further during setup.
- It uses the same expansion and context as above. It's a one-off step, never an ordinary turn.

### Events, items, and kinds a stub can have

Named events count as names. *My calls:*
- **Events become creatable:** the existing `event` kind is creatable from a prompt and gets a page, so a "Night of Feathers" stub has somewhere to go. Its `when` and `until` fields use the world calendar.
- **Items become creatable** the same way (the `item` kind already exists), since generations name swords, crowns and relics.
- **A stub can be any kind.** A culture stub is allowed and listed, but its Expand stays disabled until the cultures slice, with a note saying so.
- **Groups and factions** ("the Owl Guard") have no kind yet, so they're lore stubs.

## Non-goals

- **Names that turn up during play,** such as a guard or tavern a scene invents: later, with the inbox (owner). This slice builds the shared part they'll reuse.
- **Mention records for scene messages:** plan D.
- **The decision model doing the kind guess:** later. The AI's reply or a code rule guesses until then.
- **Asking the AI about your world:** much later. It may need an instruct model.
- **Cultures:** the next slice after this one.
- **Changing how `@` actions are followed:** that's the runner work.

## Anti-goals

- **Noise.** Generic words highlighted, or stubs for things like "the postmaster", "a war" or "his mother". Proper names only.
- **Duplicates.** A prompt naming an existing entry, and the model inventing a second one anyway: that's the Moscavian Owls case.
- **Slower turns.** Name-finding and context assembly happen at create, edit and scene setup, never on an ordinary turn.
- **Losing the owner's text.** Linking a name must never change the wording the owner or the model wrote, beyond turning the name into a reference that renders the same.
- **Hidden context.** The create box shows what context the AI gets ("Mentioned in", "About those", "Named in this prompt").

## Constraints

- **Everything in the main spec and plans A and B holds:**
  - Guix and `uv run --no-sync`;
  - the fast testing loop, with browser tests at `-n 4` at most;
  - `src/talemate/world/` stays under strict mypy with no other talemate imports;
  - theme roles, the Pinia worlds store and world-store ids;
  - generated prose is never fed back into fact extraction;
  - every world AI call goes through `world_ai_call`;
  - replies are parsed with the shared non-strict parser.
- **The local model is the target** (koboldcpp, currently Skyfall-31B).
- **Probe the AI before building** (owner's principle). Probes need the owner's go-ahead.

## Probes (before the features they serve)

1. **Finding new proper names and their kinds in a generation.** Can the create reply list the proper names its facts invent, with a kind for each, accurately and without generic nouns? Compare that with a code rule (capitalised phrases checked against the reply), and with both together.
2. **Context from mentions.** Expand a country stub with and without the mentioning entries' key facts, and judge whether it reflects its inhabitants (the owner's measure). Settle the cap and what counts as key facts.
3. **Duplicates.** A place prompt naming an existing species (the "Moscavian Owls" case), with and without that species matched into the context: does the model stop inventing a new species?
4. **Everyday names.** Do the AI-suggested other names come out sensible and correctly tagged? Does giving an everyday name in the context make narration use "Moscavia" rather than the full "Tsardom of Moscavia"?

## Left to the builder

- How stubs are stored: a flag on the thing, a field, or a kind. They must be undoable and versioned like other edits, and visible to the reference check before deleting.
- How the shared name-finding splits between `world/` and `worldplay/`.
- The task order, as long as each probe comes before the feature it serves.
