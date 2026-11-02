# Languages 4b-1: the grammar engine for names

Date: 2026-11-02. Part 4 of the languages design (`2026-10-30-fantasymate-languages-4-design.md`) splits 4b into two plans, in this order (owner):

- **4b-1, this document: the grammar engine.** Name rules can be made of parts. Names built from meanings follow the language's word order and word forms. Every kind of name uses it: people, places, groups, things.
- **4b-2, later: people's names on top.** Full names that adapt to what the owner gives; parts from connections; forms by sex or rank; forms of address by kind of relationship, with per-person overrides; pet names from rules, with invented ones as overrides. Its own brainstorm and design come after 4b-1 is built.

Builds on 4a (merged 2026-11-01): drafts only mark names, and the owner names things with the **Name it…** panel (rules, patterns, pins, Reroll, From a meaning with rolls per new word).

Mockups (approved 2026-11-02):
- `docs/superpowers/mockups/2026-11-02-languages-4b1-name-it-builder.html`, option **B**;
- `docs/superpowers/mockups/2026-11-02-languages-4b1-names-chapter.html`.

## Why

- **Meaning parts are made up today.** An earlier generated language had names ending "… of the Sun" ("Ul Sol-something"), but the generator only makes up sounds. A name part that means something must be real words of the language: translated, or coined with a meaning and saved to the dictionary (owner).
- **The grammar is ignored.** From a meaning builds words in the owner's English order, so "white lake" in a French-like language came out "Blanchic Aunfoimtte" (white lake). "Of the Sun" should come out as the language says it: "Ul" plus the right form of "sun", in the right place. The owner wants rules the generator applies, "so it always gives the words … the right conjugation".
- **One system everywhere.** People's other names are specific to 4b-2, but correct grammar matters everywhere, and everything should use the same system (owner).

The owner's own languages show the range the rules must cover. These are in the test app's worlds (`.worktrees/languages-4a/.superpowers/sdd/2026-11-01-…-revised-name-it/app/worlds`):

- **"The":** an ending (Tsevrani -ek / -k after a vowel; Varsenyk -ar / -r), a word in front (Drassonais lo, lou; l' before a vowel), or an ending that depends on the noun (Moscavian -ot on hard nouns, -ta on soft ones).
- **More than one:** an ending (Varovni -i / -ni), a vowel swap (Moscavian soft -a/-o → -i; Tsevrani -a/-o → -y), or doubling the first part of the word (Bumbagoo bumpa → bubumpa; Skrathik tok → totok).
- **Describing words:** before the noun (Varovni, Tsevrani, Moscavian, Varsenyk) or after it (Drassonais, Bumbagoo, Skrathik).
- **"Of":** a word after the owned thing (Varovni "zovna dez gosvar"; Tsevrani "korsha tre dervo"), or di plus a place (Drassonais "di Sauvaire").
- **Joined words:** the describing word first (Varovni ilvo + ulkhar → ilvulkhar) or the main word first (Drassonais auvrefougre).
- **Endings with meanings:** small or dear (-yk, -el, -enka), land of (-ya, -nya, -enya), person of (-ets, -ais, -yn), place of (-auve, -esh), one who does (-ov, -aud, -ar).
- **A composed custom already exists:** Varovni's "Since the Light, many Owl-folk add an owl-name after their old name, joined by the word ul (owl-of): Dorvak Ul Zvesk, 'Dorvak Owl-of-Stars'."

## Goals

1. The language file holds a small set of **grammar rules for names**, which the name engine applies directly:
   - word order: describing words, "of", joined words;
   - word forms: "the", more than one;
   - the meaningful endings.
2. **Name rules can be composed** of parts: another rule, a fixed word, or a meaning part.
3. **Names are built from meanings grammatically,** whatever the meaning comes from:
   - the owner gives it;
   - the model suggests it from the entry's facts;
   - it's rolled at random from the dictionary.
4. **The Name it panel becomes a builder** (mockup B). It shows the name in use part by part; each part has its own rolls and a pin, and Reroll rolls every unpinned part.
5. **The language page's Names chapter shows the rules** (mockup). Every row is in plain words with an example built from it, and can be edited directly.
6. **Rules get written.**
   - **New languages:** the language skill and the brief write them.
   - **Existing languages:** a Change it… run, **Fill them in from the grammar**, turns the prose and tables into rules for the owner to review.
   - **Imports:** the import check validates them.
   - **Old files:** they still load and work as in 4a.

## Non-goals

- **No sentences or verbs.** The engine builds words and short name phrases ("white lake", "of the Stars", "Owl-of-Stars"). It doesn't conjugate verbs or build clauses.
- **People's names** belong to 4b-2: full names that adapt to the owner's input, parts from connections, forms by sex or rank, forms of address, pet names.
- **Names that change over a life** are not modelled (part 4 design).
- **Scenes** wait for the scene rework, which is where forms of address get used.
- **Sound changes** (SCA-style rules that rewrite sounds over time) are out of scope. Endings may say what they follow ("after a vowel"); that's all.

## Anti-goals

- **The model never does the grammar.** It picks meanings, and the engine builds the forms and the order. A rule the engine can't apply is shown as missing; the model doesn't fall back to conjugating.
- **No rules the owner can't read.** Every rule shows in plain words with an example built from it, and a wrong rule shows a wrong example.
- **No model call on Reroll.** Rolling, pinning and picking stay instant, as in 4a.
- **The language's prose isn't replaced.** The rules sit beside it, and the prose stays what people read.
- **No overfitting to one custom** (owner's caution in part 4). The building blocks are general, and each language picks its own mix.

## The rules in the file

The language gains a `name_grammar` object. The exact field names are the builder's. These are the blocks, from what's mostly settled to what's most open:

**Order**
- `describing`: before or after the noun.
- `of`:
  - how "of X" is said: a word ("dez", "tre", "ul", "di") or an ending;
  - where it goes: before or after the owned thing;
  - whether X takes "the".
- `joining`: in a joined word, the describing word first or the main word first. Optionally, the first word is clipped to its first syllable (Tsevrani "bel-" from belesh).

**Forms.** Each form is a list of conditional changes, tried in order; the first that applies wins:
- `the`;
- `more_than_one`.

A change is one of:
- add an ending: "-ek", or "-k" after a vowel;
- swap an ending: final "-a" or "-o" becomes "-y";
- add a word before or after: "lo", with "l'" before a vowel;
- double the first part of the word: bumpa → bubumpa.

Conditions say what the word ends with, or begins with: a vowel, a consonant, or given letters. The language's own vowels come from its sound categories when it has them. A word with no matching change is left as it is.

**Endings.** A list of `{ending, meaning, example}`, each with the same conditional changes the forms use (Varsa + -enya → Varsenya drops a vowel; -ya / -nya after a consonant / vowel). It is the language's word-building table: -yk "small, dear", -nya "land of". A meaning part can ask for one by meaning ("land of" + Varsa → Varsenya). 4b-2's pet names use the same list ("small, dear").

**Unknown kinds of word.** A word with no `part` in the dictionary is taken as a noun when it fills a noun slot, and as describing when it fills a describing slot. Meaning parts know which they need.

## Composed name rules

A name rule (`GeneratorDef`) can have **parts** instead of patterns. Each part is one of:

- **another rule:** "[Men's names]", rolled from that rule;
- **a fixed word:** "Ul";
- **a meaning part:** a slot for words of the language, built from a meaning. It says:
  - what kind of words fill it: a noun, or describing words plus a noun;
  - which forms apply: more than one, "the";
  - optionally, how it joins: "of" this noun, or joined into one word;
  - optionally, a hint for the model: "something in the sky".

**Building happens inside a meaning part** (*my call*). A meaning part's "of" and joining apply to its own words: "of the Stars" or "white lake" inside the slot. The parts of a composed rule stay in the order the rule lists them; whoever writes the rule (the skill, Change it…, the owner) orders them for the language. The engine never reorders parts across the rule.

A composed rule can have several **shapes**, alternatives picked with weights, as patterns are. Parts can be **optional**, kept half the time when rolled, as `( … )` is in patterns. A plain pattern rule stays exactly as it is.

**How a meaning becomes words:**
1. Each meaning word is looked up in the dictionary (a word, or a meaning it has). If it's missing, it's coined from the word rules, with its meaning, and saved only if the owner picks the name (as in 4a).
2. The phrase is put together by the order rules: describing words before or after, "of" as its word or ending, in its place.
3. Forms are applied: more than one, "the".
4. The parts are capitalised as names are today, and the working is kept: each word, its meaning, which are new, and each form applied.

**From an English meaning to the slot** (*my call*). When the owner types a meaning ("of the Stars", "white lake", "lakeland"), the model splits it into a structure: the main noun, describing words, whether it's "of", more than one or "the". It runs in the same call that coins new words, so there's no extra round trip. A meaning that already matches the structure exactly (one dictionary noun) skips the model.

- **The owner's words win over the slot** (*my call*). A slot's settings ("a noun · plural") are defaults for Random and Suggest. A typed meaning keeps its own structure, so "white lake" in a noun slot gives the describing word and the noun, in the language's order.
- **Several meaning parts:** the one Give a meaning box fills them in order. The model shares the meaning out, one phrase per part ("Stars", "of the Frost"), and a part it leaves empty keeps its roll. With no composed rule picked, the box builds one name from the whole meaning.

## Three ways to a name

Most common first (owner):

1. **✨ Suggest from its facts.** The model reads the entry's facts and, for each meaning part, picks a meaning that fits: a star-watcher gets "Stars". The engine builds the words. For a rule with no meaning parts, Suggest has the model choose from a batch of rolls, as naming does today (*my call*).
2. **Give a meaning.** The owner types it and it fills the builder's meaning parts. Each new word gets rolls and pins, as From a meaning has now. "From a meaning" becomes this.
3. **Random, for brainstorming and completeness** (owner: "Not a use case that is super useful … but okay for completeness sake"). Reroll rolls every unpinned part. A meaning part picks a random dictionary word of the right kind, with no model call.

## The Name it panel: the builder (mockup B)

- **A part can be typed in** (*my call*). A rule part (such as "man's name") takes the owner's own word, which pins it: the mockup's pinned "Dorvak". Pre-filling parts from the entry's current name belongs with 4b-2's names that adapt to the owner's input. **Use this name** renames the words chosen in the header, as in 4a: an entry keeps its old name as another name, and a stub forgets it.

- **The name in use is laid out part by part.**
  - Each part shows what it is ("man's name", "fixed", "a meaning · plural") and its rolls.
  - The chosen roll is marked, and each part has a pin.
  - **Reroll unpinned** rolls every part that isn't pinned.
  - The built name shows below the parts, with **Use this name** and the working: "zvesk 'star' + -i".
- **A rule without parts** (a plain pattern rule) keeps 4a's batch of ten names, with pins.
- **The rest of 4a stays:**
  - the header's name chips choose which words of an entry's name are renamed;
  - picking renames everywhere;
  - coined words are saved on pick;
  - pins are dropped when the panel closes.
- **Give a meaning** sits under the builder and fills its meaning parts. With no composed rule picked, it builds a name from the meaning alone, as From a meaning does now, but grammatically.

## The Names chapter (mockup)

- **The language's names prose stays at the top.**
- **Name rules card:** each rule, with composed rules shown as their parts ("[Men's names] [Ul] [a meaning · plural]") and an example rolled from it. Rows can be added, edited and removed.
- **Grammar for names card:** each rule in plain words, with an example the engine builds from it ("skelt → skeltek, skelti"). Each row has a pencil for editing it directly; a whole-card Change it… link sits in the header.
  - Direct edits are row by row, with no free-form editing of the whole file (*my call*).
  - An edit is saved like any language edit, so the existing merge keeps it through later Change it… runs.
- **A language without these rules** shows "No grammar for names yet: names are built in your word order", with **Fill them in from the grammar**.

## Composed rules outside the panel

*My calls:*
- **Everywhere a rule rolls, a composed rule rolls too:** the right-click "Make a name" in the scene box, and `roll_names`. Its meaning parts pick random dictionary words, as Random does. When a language has both a plain and a composed rule for the same use, the default (`generator_for`) stays the plain rule. A composed rule is used when it's picked, or when it's the only one.
- **A built name fits its language** (`fits`), so the cleaning finder doesn't flag names the owner picked. Fixed words and dictionary words fit, and so do words with the language's forms and endings applied.
- **Name it in… (`name_in`) and From a meaning's translation (`translate_text`) build through the engine too,** so every route from a meaning is grammatical. "Names are built from meanings grammatically, whatever the meaning comes from."

## Getting the rules into languages

- **Fill them in from the grammar:** a Change it… run whose request is "write the grammar for names from this language's grammar sections and tables". It goes through the existing route, review and merge, and the review shows the new rules with their built examples.
- **The language-design skill and the Full and Quick briefs** describe `name_grammar` and composed rules, and ask for them. The skill's example gains a composed rule, and the brief's "Still to fill in" gains "grammar for names".
- **The import check** validates the rules: known blocks, conditions that parse, parts that name rules the language has. It warns, rather than refuses, on an example that doesn't build.
- **`language.schema.json`** gains `name_grammar` and composed rule parts. Old files without them load unchanged.

## Probe 4b-1 (before building; ask the owner before running)

Two model-dependent pieces, each probed on the owner's own languages:

1. **Fill them in from the grammar** on the agent route (Claude Code):
   - Run it on the six languages in the test app's worlds.
   - Score whether the rules it writes build the examples their own grammar tables give ("skelt → skeltek"), and record what it misses.
2. **Splitting an English meaning and Suggest from facts** on the world model (Skyfall on koboldcpp):
   - About 20 meanings: "of the Stars", "white lake", "the old grey stones", "lakeland".
   - About 10 entries' facts for Suggest.
   - Score the structure and how fitting the meanings are.

**Order of work and the fallback** (*my call*):
- The engine, the file, the Names chapter and the builder's Random and typed paths need no model, so they're built first.
- The probe runs before the model-dependent pieces are built: Fill them in, the meaning split, and Suggest.
- If Skyfall can't split meanings or suggest reliably, those two use the language agent's client (the global language route, `in_app` with its own model) instead of the world model.
- If Fill them in fails on a language, the owner fills the rules row by row in the Names chapter, which needs no model.

## Constraints

- Python and Vue as the app is now. The engine is plain Python next to `talemate.languages.generator`, with no new dependencies.
- **No model call** on Reroll, pin, pick, or building from a known structure.
- Old language files load and behave as in 4a. A language without `name_grammar` builds in the owner's word order, as now, and the Names chapter says so.
- Follow the repo's UI rules: controls by content; the same look means the same component (4a's pin chips are the same component here); screenshots at 1920×1080.

## Left to the builder

- The exact field names and JSON shape of `name_grammar` and composed parts.
- How conditions are written (a small set of named conditions, or short patterns), provided they're readable in the Names chapter.
- How examples are chosen for the cards (from the grammar tables when they have one, else a dictionary noun).
- Whether a composed rule's parts can nest (a part that is itself composed). They should at least be able to name another composed rule.
