# Fantasymate: Spheres

Date: 2026-10-22. Status: design, awaiting the owner's approval.

This is the slice after Connections (merged on 2026-10-21). It replaces the planned cultures slice. While thinking cultures through, the owner found a wider shape: cultures, religions, nations, academies, councils and fields of knowledge are all one kind of thing, a **sphere**. Languages come out as a separate slice, after this one (owner: "Spheres first, languages after").

It builds on:
- the main spec, `2026-10-18-fantasymate-world-data-model-design.md`;
- plan B's heritage and inheritance (`2026-10-20-fantasymate-phase-2b-heritage-design.md`);
- Connections (`2026-10-21-fantasymate-connections-design.md`).

Evidence: a Skyfall test of sphere structure, with raw output in `docs/superpowers/probes/raw/2026-10-22-sphere-structure.json` (see "What the test showed"). The owner approved the mockup at `.superpowers/brainstorm/26097-1792645894/content/spheres.html` (not committed); "The pages" below describes it.

## Intent

In the owner's Connections run, the Tsardom's religion, its rites, its council of elders and its stance on the transformation all came out as plain lore entries. They were rich, but flat. The owner wants these to be structured things the world is built from:
- a religion with doctrines, a hierarchy, ceremonies, holy sites, a timeline of what it has declared, and room for schisms;
- an academy with fields of study, a knowledge frontier and researchers;
- a culture whose practices can begin, change or be banned;
- a field like runic magic, whose theories can be disproven.

**What the owner sees in common:** "a capital T Thing which itself contains like positions, concepts, knowledge, practices, potentially the capacity to hold territory, probably more."

There are two flavours, and both change over time:
- **Agents** act in the world: churches, nations, academies, councils. Their timeline is what they say and do.
- **Beds of knowledge** are acted on: cultures, magical concepts, scientific concepts. Their timeline is how the knowledge changes: a practice begins or ends, a theory is disproven, something new is learned.

The direction is deeper characters. A character's ties to spheres ("a practitioner of the White Dawn, but…") say who they are without copying the sphere onto them.

## How the owner will judge it

A session like the last two, in a fresh world:
1. Make the owl species and the Tsardom.
2. Follow the Tsardom's first mention of its religion, which offers to make a sphere.
3. Expand the council of elders before the religion, then the religion, and see it written around the council.
4. Fill a drawer or two.
5. Give a character ties with "but…" exceptions.
6. Play a scene where the religion matters.

**Passing means:**
- spheres come out with sensible, specific drawers;
- following links grows them naturally;
- "part of" works in either order;
- character ties read well;
- the scene uses the sphere without flooding the context.

## Goals

### The sphere kind

A new kind, `sphere`, with:
- **a template** (a core field), one of `religion`, `nation`, `order` (academies, guilds, orders, councils, militaries, tribes), `culture`, `field` (fields of knowledge and magic) or `other`. The template sets the agent flag and the default drawers;
- **the agent flag,** set by the template (owner-changeable) and never by the model. The test showed the model calls a culture an agent about half the time;
- **a summary and facts,** as any entry has. A sphere's facts are its timeline (see Timeline);
- **its drawers** (below);
- **promotion:** a lore entry can be turned into a sphere by picking a template. It keeps its id and every link to it.

*My call:* one `sphere` kind with a template field, not one kind per template. The drawers, ties and "part of" links work the same for all of them, and the templates differ only in their defaults.

**The old `culture` kind is retired** (*my call*; the owner starts a fresh world each milestone, so there's no migration):
- a culture is a sphere with the `culture` template;
- the name-kind guess "culture" maps to a culture sphere;
- a place's `cultures` shares point at culture spheres;
- a character's `culture` field becomes a tie;
- the `language` field rides on culture spheres untouched until the languages slice moves it out;
- the culture-design skill's import isn't wired to spheres in this slice.

**What can be promoted** (*my call*): a lore entry, or a stub of any kind.
- Its facts are kept as they are: dated ones join the timeline, and undated ones show under the summary as "about".
- Its drawer outline is generated like a core step, with those facts as context.

**A place can be a sphere too** (owner, 2026-10-22: "one entry that's both"). A nation like the Tsardom is both a territory and an agent, so a place can take on a sphere template and its drawers while staying a place:
- it keeps its place fields: parent place, kind, and what's inside it;
- it gains drawers: the Tsar and officials under people, laws under beliefs, government and military under structure, and a timeline;
- its places drawer is the places inside it, so territory comes from the place tree, with no second list to maintain;
- links to it work either way, as a scene location and as a sphere.

"Promoting" a place adds the template and drawers; it keeps its id and kind. *My call:* places get this, since the owner asked about nations. Other kinds (events, characters) don't.

Promoting other non-stub kinds, such as events, isn't offered.

### Typed drawers

A sphere's content lives in **drawers**. Each drawer has a **type** the app understands and a **title** that fits the sphere: the church's practices drawer is "Rites and Ceremonies", the academy's knowledge drawer is "Fields of Study and Research Frontier".

**Drawer types:**
- **people:** characters tied to the sphere, each with a role (see Ties). This is one list (owner): roles such as "elder", "practitioner" or "researcher" replace separate lists.
- **places:** territory and sites: "holds sway in", "seated at", "holy site". These are links to places.
- **practices:** rites, ceremonies, customs, holidays, techniques.
- **beliefs:** doctrines, values, attitudes, myths and legends (national and local).
- **knowledge:** what is known or studied, and the frontier. Each institution has its own frontier, so one academy can be ahead of another (owner).
- **structure:** ranks, offices, councils, divisions.
- **branches:** schisms, denominations, schools, sub-orders (see Branches).
- **events:** the timeline (see Timeline).

**Items in drawers:**
- Items in the practices, beliefs, knowledge and structure drawers are **entries**, each with a "part of" link to the sphere and its drawer. Most are lore. The council of elders could itself be a sphere, nested inside the church.
- An item can also be a plain statement with no entry of its own.
- Named items are stubs until expanded, exactly as Connections stubs work.

**The owner shapes the drawers:**
- **templates give the starting drawers**, for example a religion's Doctrines, Hierarchy, Rites and Ceremonies, People, Holy Sites and Timeline;
- **the AI may propose and title drawers** within the types;
- **the owner can add, rename, retitle, reorder or drop** any drawer, and add a custom-titled one of any type.

### "Part of" links

Every entry can be **part of** a sphere, in a named drawer. Example: the Council of Elders is part of the White Dawn, under Hierarchy. This is how drawers are filled, and it works in either order (owner):

- **Expanding the child first.** Say the council is expanded while the White Dawn is still a stub. The council's mentions show it belongs to the White Dawn, so it's made with "part of: The White Dawn (stub)", and that stub's guessed kind becomes a religion sphere.
- **Expanding the sphere later.** The White Dawn's generation gets everything already part of it as context, so it's written around the existing council, not a rival one. Its drawers adopt those entries.
- **The sphere first.** If the White Dawn exists first, expanding the council puts it straight into the church's drawer, and its generation sees the whole church.
- **Nothing is generated behind the owner's back.** Expanding the council never creates the church.

Stubs can be guessed as spheres, with a template guess. The Tsardom's first mention of its religion becomes a stub guessed as a religion sphere, so Expand offers the sphere template, not lore. The decision model takes over this guess later.

### Ties: characters and spheres

A character's tie to a sphere has:
- **the sphere;**
- **a role:** practitioner, elder, courier, researcher, founder;
- **dates;**
- **exceptions,** described below.

A sphere's people drawer is just the list of ties pointing at it.

**Exceptions** (owner): a tie shows only where the character departs from the sphere: "Practitioner of the White Dawn, but doesn't believe snowy owl-folk are superior". Each exception is a fact on the character. It may link to the sphere item it rejects, reusing plan B's override link but shown as "but…" rather than as a struck-through inherited fact.

**How exceptions are stored** (*my call*): an exception is an ordinary fact on the character in a `ties` category. The item it rejects is a reference in its text (`[[thing:<item id>|…]]`), so no new override table is needed.

**Proposed at creation** (*my call*): character creation may propose ties to spheres that already exist, and exceptions linked to their items, all shown in the preview for the owner to accept, edit or drop. A sphere the facts name that doesn't exist yet becomes an ordinary stub through Connections, never an automatic tie.

**Nothing is copied.** The sphere's beliefs and practices are not copied onto the character. The tie's title links to them.

**Species inheritance is unchanged.** Species, race and mix stay as plan B built them, because they shape the character's body and opening description.

**The existing `culture` field** on characters (plan B's last lineage layer) becomes a tie to a culture sphere. *My call:* the culture layer leaves the lineage, so cultures no longer pass facts down the way species do. That follows the owner's "show only conflicts" model. Plan B's culture category mapping in prose then goes unused.

### Timeline

A sphere's timeline is its events drawer, made of dated facts on the sphere, in date order:
- **an agent's timeline** is what it says and does: "Declared the transformation a purification (994)", "Issued the Doctrine of Separation (1019)";
- **a bed of knowledge's timeline** is how it changes: "The Feather Dance banned (1015)", "Rune-resonance theory disproven (1018)".

**Effects across spheres are links.** When the church bans a folk practice:
- the church gets a dated fact, "Banned the Feather Dance (1015)";
- the practice's entry gets an ended-by fact dated 1015 that links to the ban;
- its "part of" link to the culture ends at that date.

The ban shows on both timelines.

**Who makes these effects in this slice** (*my call*):
- **The owner,** with an "End this…" action on a drawer item. It records the date and, optionally, the sphere or event that ended it, and writes the facts above on both sides.
- **Generation:** the core and Fill steps may produce dated timeline facts, but they don't make cross-sphere endings. Scenes doing so come later, through the inbox.

**Knowledge spreading** works the same way. A character's discovery is a dated fact on the academy's timeline, and the discovery is an item in its knowledge drawer. If another academy learns it, that academy gets its own dated fact and item.

### Branches

A branch (a schism, denomination, school or sub-order) is a sphere whose parent is another sphere. It **inherits the parent's drawers and items and overrides what it rejects**, reusing plan B's inheritance rules: the more specific layer wins, overrides apply only where every path passes through the overrider, and a deleted parent is skipped.

**What a branch overrides** (*my call*):
- **The parent's facts:** plan B's fact override links.
- **The parent's drawer items:** a branch can drop or replace an inherited item. That needs an item-level override (a branch-scoped exclusion, or a replacing entry linked to the item), which the builder chooses.

**What a branch shares:**
- **Timeline:** a branch shows the parent's timeline up to the date it split, then its own.
- **Members:** members of a branch aren't counted as members of the parent. In context, a branch brings its parent's summary along.

A branch is made from the parent's Branches drawer ("+ New branch"), from a prompt ("the Reformed Dawn, who reject the doctrine of snowy superiority"). The test showed the model never invents branches unprompted.

### Generation in two steps

The test showed that writing a whole sphere at once runs long: 6 of 16 replies were cut off. So:

1. **The core.** Creating or expanding a sphere writes its name, summary, other names, a few dated facts for the timeline, and a **drawer outline**. The outline is the drawers it should have, typed and titled, with a few named items each that become stubs.
2. **Filling a drawer.** "Fill" on a drawer asks Skyfall for that drawer's items. It uses the sphere's page so far, everything already part of it, and the Connections context: mentions, named entries and everyday names.

Following a stub inside a drawer expands that one item, as Connections does today.

### Context in play

Starting rules, which the owner expects to need tuning:
- **The character sheet** always carries each tie line and its exceptions. They're short and make the character.
- **A sphere's own key facts** enter a scene's context only when the scene touches the sphere:
  - the scene's place is in its territory: under the sphere's place tree when the sphere is a place, or under any place in its places drawer;
  - the prompt or setup names it;
  - one of its members is present.

  They're capped the way mention context is capped.
- **"Key facts"** (*my call*): the summary, then the top items of the beliefs and practices drawers (structure for agents), then the latest few timeline entries. Touching a nested sphere, such as a council member being present, brings along its parent's summary only.
- **No extra model calls on an ordinary turn.**

Deciding exactly what reaches the model when is part of the scene-runner work. This slice puts in the simple, capped rule above.

### The pages

These follow the approved mockup.
- **A sphere page:**
  - the template chip and the agent chip;
  - the summary;
  - typed, titled drawers, each with its items, Fill when empty, and "+ Add";
  - People with roles and dates;
  - Places with how the sphere relates to each;
  - the Timeline;
  - Branches with "+ New branch";
  - "+ Add a drawer";
  - promotion from a lore entry, via its page.
- **A character page's Ties section:** each tie with its role and dates, and only its "but…" exceptions. Adding a tie means picking a sphere and a role, with "+ Add exception".
- **Any entry's page:** a "Part of" line with the sphere and drawer, editable.
- **The World tab:** a Spheres list, grouped by template, with stubs dimmed as today.

## What the test showed

Skyfall was given four spheres (the White Dawn, an academy of runecraft, runic magic and Moscavian culture), two runs each in two prompt styles:
- **Free drawers** came out sensible and specific: Core Doctrines, Hierarchy, Sacred Practices, Key Texts, Key Sites, "Relationship with Humans". But the titles changed from run to run, so the app couldn't know what a drawer means.
- **A menu of drawer types** was chosen well and still titled to fit ("Fields of Study and Research Frontier"). This is why drawers are typed.
- **A people list with roles** worked naturally.
- **Timelines held together:** a 1019 synod issued a doctrine.
- **Branches were never chosen.**
- **Agent or bed of knowledge was misjudged** for cultures, so the template decides.
- **Each sphere invented its own Tsar,** because none existed in the context. Connections context fixes this.
- **Long replies were cut off.** Hence two-step generation.

## Non-goals

- **Languages:** phonemes, grammar, dictionary, phrases, name generators, translations, and which characters speak them. This is the next slice (owner). Until then, the existing `src/talemate/cultures/` language code is left as it is.
- **Borders and the map:** territory is links to places only.
- **The decision model** for kind and template guesses: the AI's reply or code guesses until it arrives.
- **Scenes adding to spheres during play:** a scene revealing a new rite, for instance, goes through the inbox later.
- **Deciding exactly what context each scene gets:** that's the runner work. This slice only adds the simple rule above.

## Anti-goals

- **Flat lore by another name:** spheres whose drawers are just untyped text the app can't use.
- **Copying the sphere onto every member:** characters stuffed with their church's whole creed.
- **Generation behind the owner's back:** expanding a child creating its parent.
- **Context floods:** every sphere a character is tied to dumped into every turn.
- **Slower turns.**

## Constraints

- **Everything in the main spec, plans A and B, and Connections holds:**
  - Guix, `uv run --no-sync` and the testing loop;
  - browser tests at `-n 4` at most;
  - strict mypy for `src/talemate/world/` with no other talemate imports;
  - theme roles and the Pinia store;
  - world-store ids;
  - prose is never fed back into facts;
  - every world AI call goes through `world_ai_call`;
  - replies are parsed by the shared non-strict parser.
- **The local model is the target** (koboldcpp, Skyfall-31B).
- **Probe the AI before building.** Probes need the owner's go-ahead.

## Probes (before the features they serve)

1. **The core and its drawer outline:** for each template, does it give sensible typed and titled drawers and item stubs, with no truncation?
2. **Filling a drawer:** given the sphere and what's already part of it, do the items fit and avoid duplicates? Is a sphere expanded after its child written around that child?
3. **Ties and exceptions at character creation:** does the AI propose ties and "but…" exceptions that read well and link to the right items?
4. **Context in play:** does a scene touching the White Dawn use its key facts, and stay on topic, within the cap?

## Left to the builder

- How drawers are stored: a field on the sphere, or a list of drawer records. They must be undoable and versioned like other edits.
- How "part of" and ties are stored: fields, or link records with roles and dates. They must be dated and undoable.
- The exact template defaults. Start from the test's menu results.
- The task order, as long as each probe comes before its feature.
