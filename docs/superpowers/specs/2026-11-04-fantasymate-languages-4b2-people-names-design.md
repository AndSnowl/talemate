# Languages 4b-2: people's names

Date: 2026-11-04. Part 4 of the languages design (`2026-10-30-fantasymate-languages-4-design.md`, section "4b: fuller names") splits 4b in two. 4b-1, the grammar engine, is built and merged (5d9af7e6; design `2026-11-02-fantasymate-languages-4b1-grammar-engine-design.md`). This document is 4b-2, people's names on top of it.

Mockup (owner chose frame **B**, 2026-11-04): `docs/superpowers/mockups/2026-11-04-languages-4b2-person-name.html`.

## Why

The owner's picture: make a new character who is someone's daughter, say a daughter of Eilhaud of Drassone. With no other direction, "I would expect the name to partially match the mother depending on the language, like the family name, basically I expect it to pass down the name properly and make up the rest, and if something is meaning based, fittingly make up the rest" (owner).

Today a person gets a single rolled name, or a 4b-1 composed rule rolled part by part. Nothing comes from the person's family. A name has no parts the world knows about, and other names have no notion of who uses them.

## Goals

1. **A person's name is built from their language's rules, with parts from the world.** In order of priority:
   1. what the owner gives;
   2. the parts inherited from real connections (a parent's family name in its woman's form, a house, a name made from the parent's name);
   3. the rest made up: rolled parts are rolled, and meaning parts get a meaning that fits the person's facts.
2. **Forms by sex and by rank,** as each language defines them. Kesterovsk → Kesterovska; a noble's "di + house" against a commoner's "daughter of Eilhaud" (owner: "Rank can change forms too, depending on the language").
3. **A person's page shows the name in labelled parts, each editable** (owner). Inherited parts say where they came from.
4. **Titles, collected.** A person holds a list of titles, each with who uses it (owner's example: Rand in the Wheel of Time is the Dragon Reborn, Coramoor, Car'a'carn, He Who Comes With the Dawn, King of Illian, Lord of the Morning, "depending on who you ask, essentially what their culture/language calls him").
   - A title is in English by default.
   - A title in a language is built from its meaning by the 4b-1 engine, like owl-names, with new words saved to the dictionary. Typing one's own is always an option (owner).
5. **What others call them.** The language holds default forms of address by kind of relationship ("family use the given name", "strangers use title and house"). A person's page shows only the names that **differ from the default** (owner): pet names and per-person or per-group names, on the relationship they belong to (frame B).
6. **Pet names from the language's rules,** with invented ones as overrides (owner, part 4).

## Non-goals

- **Scenes.** Forms of address are "part of scenes in dialog and anything from the perspective of the acting character" (owner). 4b-2 stores and shows them; scenes use them after the scene rework.
- **Migration** (owner: "we can just start fresh, we are still very much in early, unreleased development"). Existing people with one name string are not split into parts. No migration code.
- **Names that change over a life** stay unmodelled (part 4). Changing a parent later doesn't rewrite the child's name.
- **Working out a parent from a child's name.** A father made later isn't derived from the daughter's name (part 4, owner).

## Anti-goals

- **Translating everything.** Titles and joining words are written in English unless the language keeps that word. "As arbitrary as the title" (owner): we say Tsar but not the French word for king; "Eleanor of Aquitaine" but "Leonardo da Vinci".
- **Clutter.** Default address isn't repeated on every relationship row. Only what differs shows, and it's folded.
- **The model doing grammar** (4b-1 anti-goal, still binding). The model picks meanings and reads facts. The engine builds the forms.
- **Overfitting** to son-of / daughter-of. The customs table in part 4 (from a parent, a child, a place, a group, a role or deed; order that changes; forms by sex, rank or marriage; no personal name) is the test.

## Writing in English or the language

Set up in the language, word by word (owner): each **fixed word** of a name rule, and each title the language keeps, has a switch "write it in English".
- Drassonais "di" is switched to English and shows as "of": "Maëlis of Drassone". The owner, about the mockup: "In this situation, of would probably be English too."
- Varovni "Ul" stays "Ul", since "Owl-of" is the point of that custom.
- A title the language keeps (a Tsar) is listed in the language with its own word; every other title is English.

The name is still built in the language (the engine knows "di"). The switch decides only how it's written in the world.

## A person's name

### The parts

A person's name is stored as **parts**, each labelled by the rule part it fills (given, family, house, owl-name, "of"…), with:
- its text;
- where it came from: rolled, typed, from a meaning, or **inherited** from a named connection;
- for a meaning part, its working (as 4b-1 keeps it).

The full name is put together from the parts. Editing a part rebuilds the full name, and renaming the entry the old way (✎ on the name) still works. *My call:* a hand rename that no longer matches the parts clears the parts, and the page says "not built from a rule". The text wins.

### Inherited parts

A rule part can be **from a connection** (part 4's block, "the name of something the person is connected to"). It names the connection by role words ("father", "mother", "parent", "house", "born in", "lord") and says what it takes from it:
- that entry's whole name, or one of its **parts** (the parent's family part, the parent's given part);
- in which form (woman's form, "son of" form, an ending such as -evra).

Since people now have parts, "take the mother's family name" reads her family part directly. *My call:* a parent with no parts (made before 4b-2, or renamed by hand) gives its whole name, or its last word for a family-name part.

Which parent is the language's choice. The rule says which role words it reads, in order: "mother, then father".

**Telling a mother from a father** (*my call*, no model call): by the role words first ("mother", "father", "son of" on the parent's side). Then by the parent's own stored "built as". Then the first parent found, with the page saying which parent it took so the owner can switch it.

**When the connection doesn't exist** (part 4, owner): a required inherited part is rolled. The person it implies is offered in the draft's New stubs, unticked, with the connection ready ("Borodey, father of Mileva"). Ticking it creates them already connected.

### Forms by sex and rank

- A rule part can have **forms by who the person is**: sex, rank, or other choices the language defines (married or not). The language names the choices; they aren't fixed to man and woman, or noble and common.
- A language can have **different rules by rank** (nobles: "given di house"; commoners: "given, daughter of [parent's given]"). A rule says who it's for. Picking a person's rule follows from sex and rank.
- **Where sex and rank come from** (part 4, *my call*, still standing): the model reads them from the person's facts when the name is made. There's no new field. *My call, new:* the Name section shows what was read ("built as: woman · noble"), and the owner can change it there. That choice is kept with the name parts, so a reroll uses it.

### On the draft

**Changed before merge (owner, 2026-11-06): drafts only mark.** The automatic build below was turned off. A person's draft keeps the model's name and marks it ("Name it can build it from ⟨Language⟩'s rules for people"). The draft also keeps who the person is built as, and the model's title. Name it opens with the rule for them and the inherited parts pinned. Building automatically waits for 4c, where the model picks the rule from descriptions Claude writes, and one shared draft pipeline does the same for "+ Add facts" and group adds. The rest of this section describes the build Name it now does.

Drafts only mark names (4a). *My call* (the owner agreed to the playback): **the draft shows the full name at once,** with the inherited parts filled from the parent and the rest made up, and the whole name still marked. **Name it…** opens with the inherited parts pinned, showing where they came from, so a reroll changes only the made-up parts. Whatever the owner typed in the prompt as the name wins over every rule.

*My calls* on how far that goes:
- **The built name replaces the model's name the way picking a name in Name it on a draft does in 4a**: the draft's own name, and its facts and text that use it, are renamed in the draft. Other entries' lines follow when the draft is accepted, as renames do now. This is the one place a draft's name is set by the app rather than marked, and the name stays marked so the owner sees it was made.
- **It applies to person drafts and to people ticked in New stubs.** A group's "+ Add" rows and untouched stubs keep 4a's behaviour.
- **No extra model call per draft.** The draft call already reads the person's facts; it also returns sex, rank and a meaning for each meaning part. The engine builds the rest. Name it's Suggest stays the way to ask again.

**A missing parent's stub** (*my call*) gets a full name, built from its language's rule for its sex (from the role words: "mother" is a woman), with the rolled inherited part pinned. That is ordinary rolling, with no model call, and the stub stays marked like any drafted name.

### Name it on a person

The 4b-1 builder, with:
- **a person's current parts pre-filled and pinned,** which is 4b-1's "names that adapt to the owner's input";
- **inherited parts** shown as their source ("from her father Eilhaud"), pinned. Unpinning one lets it roll like any part.
- **Suggest** reads the person's facts for the meaning parts, as in 4b-1.

## The page (mockup frame B)

**Name section,** in the left column near the top, above In and Languages:
- The language and rule, in one line: "Drassonais · Women's names (noble): given + of + house".
- A fixed grid of parts, each with its label, its text, and a ✎. Inherited parts are outlined and say "from her father Eilhaud", linked. A fixed word shows as written ("of"), with its language word available as a tooltip.
- "built as: woman · noble", changeable.
- **Titles,** listed under the parts (below).

**What others call them (frame B):** each relationship carries its own folded "calls her" line, only when that name differs from the default (see Stored names). A name says whether it comes from the language's rule ("-ette, small, dear") or is the owner's own, with ↻ to roll the rule again and ✎ to type one.

### Titles

A person's title list. Each title has:
- its words, in English or in a language;
- **who uses it:** an entry (a people, a group, a place, a person) or everyone;
- optionally its meaning, when it's in a language: Car'a'carn, "chief of chiefs";
- whether it's shown with the main name, and where: in front ("Lady Maëlis") or after ("Dorvak the Smith"). *My call:* at most one title is, chosen by the owner, and none by default unless the draft gave one ("Lady").

**A title is held, not a rule part** (*my call*, from the playback the owner agreed to: "a title is something a person holds, not a rolled part of their name"). Name rules don't have a title slot. The app puts the shown title in front of or after the name built from the parts.

**Kept titles** (*my call*) are a lookup in the language: each kept title has its English meaning ("emperor" → Tsar). When the owner adds an English title to a person whose language keeps a word for it, the app offers the kept word; it doesn't swap it in silently. A title built from a meaning stays on that person; its new words go to the dictionary, and it isn't added to the kept list unless the owner adds it there.

Adding a title: type it in English, type it in a language, or **give a meaning and a language**, which the 4b-1 engine builds, with rolls and pins as in Name it (new words saved when the title is kept).

A title used by a group or people shows on the person's relationship with that group, when there is one, as a "calls him" line. Otherwise it shows only in the title list.

## Forms of address, in the language

The language's Names chapter gains an **Address** card next to the Name rules and Grammar cards:
- rows by **kind of relationship**: family, close friends, equals, superiors, inferiors, strangers. The language can add its own, and maps role words onto them ("mother", "brother" → family).
- each row says which parts of the person's name are used ("given", "title + house", "pet name"), with an example built from a sample person.
- **pet-name rules** are ordinary 4b-1 rules (often the given name with an ending meaning "small, dear"). The Address card says which kinds of relationship use them.

The world stores and shows these. Nothing outside the page uses them until scenes do.

## Stored names (*my call*)

Other names gain who uses them and what kind they are, extending today's `AKA_KEYS` (`name, tag, everyday, language`):
- `kind`: pet name, title, own (a name someone uses that's neither);
- `by`: the entry that uses it, or none for everyone;
- `meaning` and the language working, for names built from a meaning;
- `rule`: set when it came from a rule (so "from the rule" can show, and ↻ can reroll).

A pet name from a rule is rolled once, when the person is made, and kept, so it's stable.

**What shows where** (*my call*, squaring "only what differs" with mockup B):
- **The person's own pet name** (from the rule, or typed) shows once, in the Name section: "pet name: Lisette · used by family". It is part of who they are, not an override.
- **A relationship row's "calls her" line** shows only what differs from the Address card's default for that kind of relationship: a per-person name (her brother calls her Maë), a group's title for them, or a relationship that doesn't use the default (a stranger who uses her pet name).
- `by` names an entry (a person, group, people or place), or nobody, meaning everyone. A pet name's users come from the Address card, so it stores no `by`.

## The language file and the skill

- **The language file gains:**
  - rule parts **from a connection**;
  - **forms by sex and rank** on parts, and **who a rule is for**;
  - the **write it in English** switch on fixed words;
  - **kept titles**;
  - the **address** rows.
- **Language files** without these still load. Their people get 4b-1 names, and their pages show no Address card.
- **The language-design skill, the briefs, Change it… and the import check** learn the new blocks, as 4b-1's did. **Fill them in** gains "how names pass down, by sex and rank, and how people are addressed", from the language's naming prose.

## Probe (before building the model-dependent parts; ask the owner first)

On the owner's languages in the test app, on the world model (Skyfall on koboldcpp), and on the agent route for Fill them in:

1. **Reading sex and rank from facts** for about 15 people, including ones whose facts hint rather than say ("the duke's heir").
2. **Fill them in** for inheritance, forms by rank and address, from each language's naming prose (Varovni's owl-names, Moscavian's patronymics, Drassonais' "di + place"). Score whether the built examples match the prose's.
3. **Suggest for titles and meaning parts** from facts: does "chief of chiefs"-style meaning come out fitting?

*My call:* the fallback is the same as 4b-1's: the language agent's client when Skyfall fails, and the owner filling rows by hand when Fill them in fails.

## Constraints

- **Stack and rules:** Python and Vue as the app is now; no new dependencies. 4b-1's "no model call" on Reroll, pin, pick and building from a known structure still holds.
- **Inherited parts are read from the world** at build time with no model call. Only sex and rank, and meanings, need the model.
- **AI runs** (koboldcpp, Claude Code) only with the owner's go-ahead.
- **The owner's test app:** never restart it with `talemate_app.py stop/start`. Back up `worlds/` and `config.yaml`, and ask first.
- **UI:** controls by content; same look means the same component (4a's pin chips, 4b-1's builder grid); a fixed grid that doesn't resize with its contents (owner, 4b-1); screenshots at 1920×1080.

## Left to the builder

- The JSON shape of name parts on a person, of rule parts from a connection, and of forms by sex and rank.
- How role words match connections. Today connections are filings with free-text roles (`src/talemate/world/filing.py`), and relationship facts are free text. Match on either; no fixed relationship kinds are added.
- The default list of address kinds and how role words map onto them, provided the language can change both.
- Where a title from "everyone" sits when the person has no relationship rows.
- Whether a person's Name section folds when it has only one part.
