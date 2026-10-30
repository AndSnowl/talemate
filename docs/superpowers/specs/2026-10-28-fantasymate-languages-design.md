# Fantasymate: languages and naming

Date: 2026-10-28. Status: design, awaiting the owner's approval.

The evidence comes from:
- this conversation (2026-10-28);
- `docs/ideas/languages.org`, the owner's settled ideas from 2026-10-17, which this design narrows;
- `docs/superpowers/specs/2026-10-20-fantasymate-phase-2b-heritage-design.md`, "Cultures: moved to the next slice";
- the owner's experience across the acceptance runs so far, mostly in the Tsardom of Moscavia test world;
- the mockup the owner approved: `.superpowers/brainstorm/18627-1793167762/content/naming-flow.html` (right-click naming, and a page's Languages section).

Marked *My call* means the owner didn't decide it; the builder may revisit it with a reason. Everything else is the owner's.

## Why

The world-building model writes good facts and prose, but its names don't belong to the world:
- **It pulls in real history and geography.** A Russian-flavoured tsardom gets Moscow, the Volga and real tsars.
- **It reuses its favourites.** "Maren" turns up as a character name in almost every run, and "Free Cities of the Southern Realms" as the neighbouring country.
- **Names within a region don't sound related.** One person gets a French-sounding name, the next an English one.

The owner wants a language system that fixes these problems at the source, and that the owner can also use by hand anywhere they type.

This slice was overdue: cultures and languages were "next" after plan B, then after Connections, and Filing and the polish pass took the slot both times.

## The pictures that define it (owner)

1. **Making a language.** In the World tab, the owner types "a unique but recognizably Russian language". The model either asks a few plain-language questions or, if told to, makes its own choices. Out comes Moscavian.
2. **Naming by hand.** In a new entry's prompt the owner types "Tsardom of", right-clicks, and picks *Make a name*. Candidates appear, each with a one-sentence definition. The owner picks one, rerolls, or types "Moscavia" themselves, selects it, and adds it to the language as a word.
3. **Names with English around them.** "Free Provinces of Sorau": only "Sorau" is a language word; the rest stays English. Sorau's page also lists its full name in Sorau's own language, and in the other languages that matter to it, as other names.
4. **Light naming styles.** Duskhollow and Thornfield are made from English word parts. Some places need a consistent style like this without a whole language, because their people speak English in the lore or because the owner doesn't want to go that deep.
5. **The AI's drafts get fixed.** After a prompt, the generator makes many new stubs. Real-world names, the AI's stock names and stock titles are flagged and regenerated from the right language.
6. **In a scene,** a character who curses in Moscavian says the actual Moscavian phrase, with the translation on hover. Two characters with no shared language can't simply talk; two with similar languages manage with difficulty.

## Goals

The work comes in four parts, built in this order (owner).

### Part 1: remove the old culture system

- **Delete** the old culture system: `src/talemate/cultures/` (about 4,900 lines), the Culture agent (`src/talemate/agents/culture/`), the `culture` field on `Character` (`character.py`), `src/talemate/server/cultures.py` and its websocket wiring, the frontend's `components/cultures/` (about 25 components) and their references (`WorldStateManager*`, `WorldState.vue`, `EntityTooltip.vue`, `EntityHighlightMixin.js`, `TalemateApp.vue`, `utils/messageColors.js`), `tests/cultures/`, the cultures e2e tests, and `.claude/skills/culture-design/`.
  - *My call:* the skill is deleted only once probe 1 has run. If the probe sends language-making outside the app, the skill becomes the new language-design skill instead (see part 2).
- **Keep two pieces, moved into the new languages code:** the rule-based generator (`roll`, with its pattern syntax: weighted categories, optional groups, choices) and the "does this name fit the language" check (`fits`), both from `cultures/generator.py`, with their tests.
- **"Culture" goes away as a concept.** Connections (facts, filings, tags) are enough to give places and people their customs, beliefs and dress (owner). Remove the `culture` prompt hint (`kinds.py`, `HINT_AGENT`), its wording in `entries.py`, the culture remarks in `heritage.py` and `worlds.py`, and anything else a grep for "culture" finds in the world store and the worlds UI.
- **Keep** the theme's `foreign` colour role (`theme/roles.js`); part 4 uses it.

### Part 2: probes

Run these before any part-3 or part-4 design detail settles. Ask the owner before each run (standing rule: koboldcpp tests are run only with permission). Results go to `docs/superpowers/probes/`.

1. **Making a language.** Can a local instruct model (Qwen first, Skyfall for comparison) turn a plain prompt into a working language: sounds and syllable rules in the generator's pattern syntax, a starter word list with definitions, and phrases? Test:
   - "unique but recognizably Russian", judged on whether it sounds Russian without producing real Russian words;
   - a naming style from a short description ("fantasy-sounding English compound names") and from example names;
   - a daughter language from a parent plus a description of its drift ("isolated in the mountains for five hundred years").

   If no local model does well enough, the fallback is that Claude makes the language outside the app (the owner has made conlangs with shared roots and drift with Claude before), and the app imports the file. The owner accepted the friction of switching models for this step (plan B spec, "Cultures: moved to the next slice").
   - *My call:* with the fallback, everything that builds a language's rules moves outside too: making a language, making a daughter, and growing a naming style with more parts. The skill (reworked from `culture-design`) produces an import file in the new format, and the app imports it into a language entry.
   - The probe also tests the small model jobs that stay in the app either way: writing a one-sentence definition, picking among rolled candidates, and coining a word for a name's translation from the language's rules. If definitions fail locally, they're written by hand or left blank, and the probe report says which.
   - The right-click menu, Languages sections, lookups and the draft fixes don't change either way.
2. **Catching bad names in drafts.** Can a local model reliably flag (a) real-world names and (b) stock title shapes like "Free Cities of the Southern Realms", and rewrite a stock title into a fresher one with a slot for the language's name? This is the "real-world names bleeding in" probe on the later list.
3. **Language awareness in scenes.** Given a one-line context note ("Ivan and Mira share no language; Ivan's Moscavian is close to Mira's Sorauan"), does the scene model play out the barrier or the difficult-but-successful talk?

### Part 3: languages and naming

#### Languages are world entries

- *My call:* a new entry kind, **language**, so a language has a page, facts, history, a tag and connections like everything else ("Wikipedia for a fantasy world"). Its technical part (sounds and rules, words, phrases) lives on the language's page in sections of its own.
- **Three depths** (from `languages.org`); one kind covers all three, and a language can be deepened later:
  1. *Description only:* how it sounds and how to describe it being spoken. For speech that can't be written.
  2. *Naming style:* enough to make names. Either sound-based (syllable rules), or part-based like Duskhollow: lists of word parts with meanings (*dusk*, *thorn*, *ash* / *hollow*, *field*, *mere*), combined by rules.
  3. *Full language:* sounds, rules, word list, phrases.
- **Words have definitions.** Every word gets one sentence: just the name of a nation, named after someone, or built from other words ("Velgarov, 'great fort', from *vel* great + *garov* walls"). Phrases (curses, sayings, blessings, greetings) have definitions too.
- **Names are made by rules, not by the model** (`languages.org`, decided), so rolling and rerolling is instant. The model picks among candidates and writes the definitions.
- **Making a language** (picture 1):
  - From a plain prompt, in the World tab, the way other kinds are made from a prompt.
  - The model may ask questions, always in everyday words, never in linguistics terms ("harsh or soft?", "long words or short?"). The owner can tell it to decide by itself.
  - *My call:* the result shows a plain description of how it sounds and about twenty sample names with definitions. The owner keeps going in the same conversation until it's right.
- **Growing a naming style:** the owner can ask for more word parts at any time. Names the owner picks or types feed their parts back in.
- **Related languages:**
  - A language can name its **parent**. A daughter is made from the parent's roots, changed by the drift the owner describes, so related languages sound related.
  - A language can be marked **similar** to another. *My call:* with a degree: close (talk with effort), distant (a few shared words), or one-way (speakers of A follow B but not the reverse).

#### Pages and characters have a Languages section

- **A Languages section on any entry** (approved mockup): rows of a language and its role:
  - roles: *spoken*, *official*, *scholarly*, *ceremonial* (owner); *My call:* also *trade* and *liturgical*;
  - spoken rows can carry a **share in percent** (owner; it probed well in the old culture system);
  - *My call:* rows are dated, like facts, so a country can change its official language and scenes set before the change see the old one.
- **Nesting comes from filing:** an entry with no Languages rows of its own takes them from what it's filed in, walking up until an entry states some. A narrow place can state one language inside a wide multilingual one (owner). The mockup shows inherited languages as a muted line ("From Free Provinces of Sorau: …") with **Set its own**.
  - *My call:* if an entry is filed in several places, it takes the languages of all of them (each filing walked separately), without duplicates.
  - The walk must be cycle-safe, as every filing reader is (`filing.py`).
- **Characters:** a character's own Languages section, with any number of languages (owner). *My call:* each row also has a fluency: native, fluent or broken. With no section of their own, a character falls back to where they're from (owner). This replaces the culture layer heritage once planned.
  - *My call:* "where they're from" is the character's filings into **places** (not orders, faiths or families), current at the scene's date, walked up as for any place.
  - *My call:* only *spoken* and *official* rows reached that way give a character a language. A monk speaks his order's liturgical language only if his own section says so.

#### Right-click naming in any free-text box

- **Every free-text box** in the worlds UI (prompts, fact text, titles, names) and the scene's message box (`SceneMessageInput.vue`; owner) gets naming items in its right-click menu, alongside the existing "Add reference" (`ReferenceMenu.vue`, `NameHighlightInput.vue`). The approved mockup:
  - **Make a name ▸:** about four candidates, each with its definition, plus *Reroll* and *More like this one*. Clicking one inserts it at the cursor.
  - **Make a phrase…:** the same for phrases.
  - **With a word selected:** *Add "Moscavia" to Moscavian…* (a suggested definition the owner can edit), and *Reroll this part ▸*, which replaces only the selected part. In "Free Provinces of Sorau", rerolling "Sorau" leaves the rest.
  - **In the scene's message box,** the language in reach comes from the scene rather than a page: *My call:* the speaking character's languages first, then the scene's place's. *Make a phrase…* there is how the owner gives their own character a line in Moscavian.
  - **Which language:** the menu shows the language in reach, with a picker. *My call:* the default is the official language of the page's nearest Languages section, else the largest spoken share. A page with nothing in reach asks for a language and offers to save it on the page.
- *My call:* picking a generated name saves it to the language as a word, with its definition, so it isn't generated again for something else.

#### Names in each language (small-scale translation)

- A name can be given in each relevant language as one of its other names (owner, picture 3): "Free Provinces of Sorau" in Sorauan and in Moscavian.
  - *My call:* the owner starts it from the name's menu (*Name it in… ▸*), which lists the languages in reach first and all languages after. Nothing is translated automatically.
  - Other names carry which language they're in.
- *My call:* this is the only translation in this slice. Look up each English word; coin any word the language lacks, with a definition, and save it. Translating whole sentences comes later.

### Part 4: the AI side

#### Drafts: flag and regenerate

Three degrees of bad name (owner), handled differently:
1. **Real-world names** (Moscow, Volga): the model flags them; the name is regenerated from the language in reach.
2. **The AI's stock names** (Maren): caught by a **cliché list**: one list for the whole app that ships with the known ones, and each world can add its own (owner). *My call:* the owner can mark any name "AI cliché" from its menu, choosing the app list or the world's; and the app suggests one when the same name keeps turning up in the world. Flagged names are regenerated from the language.
3. **Stock titles** ("Free Cities of the Southern Realms"): the model rewrites the frame into something fresher and more specific, and the language fills the name slot, giving something like "Free Provinces of Sorau" (owner's example). Stock title shapes go on the cliché lists too.

- **How it shows:** the owner wants these flagged and regenerated. *My call:* the draft arrives with replacements already made; each is marked in the draft's New stubs with the original beside it ("was: Volga, a real-world river"), with *Keep the original*, *Take it* and *Reroll*. It uses the existing draft review.
- **No language in reach** (common early in a fresh world): *My call:* flagged names are still flagged, the draft offers "Pick a language for this draft" (the same picker as the right-click, with the offer to save it on the entry), and regeneration runs once one is picked. Until then, the originals stay.
- **Names in reach for the generator:** *My call:* new names in a draft come from the language of the place the draft is about (the same lookup as the right-click), and the language's share weights which language names a new thing. Whether to also put candidate names into the model's context, or only fix them afterwards, is for probe 2 to inform.
- **People's names have structure.** *My call:* a language can carry name patterns per kind of thing (for a Russian-like language: given name, patronymic, family name, with gendered endings; for places, an adjective form like "Moscavian"). Whatever the probe shows a language can hold, the generator uses.
  - **Patterns made of other patterns** (owner idea, 2026-10-29; its scope is for part 4's brainstorm). A name rule's pattern can refer to other name rules, so a full-name generator is the composition of a few single ones. For example, "Full name" = given name + patronymic + family name, each its own rule. The AI (the language-design skill, a change) can then write a rule out of rules it already made, instead of copying their syllables into one long pattern.

#### Scenes

- **Naming during play** (owner: yes). New people and places that appear in a scene get names from the language in reach, as the old Culture agent did for cultures:
  - *Before the writing:* when the story is about to invent a new character or place, a name is rolled from the language of the scene's place (or the character's own, when known), the model picks among candidates, and the pick is supplied to the writer. Existing names are never replaced.
  - *After the writing:* the world-state snapshot is the moment the app notices a new name (`languages.org`, "Spotting new names during play"). A new name is checked against the cliché lists, real-world names and the language's fit check; a bad one is flagged with a replacement offered, the same way drafts show it.
  - Study the old Culture agent's hooks (`agents/culture/naming.py`, `snapshot.py`: `agent.creator.before_name_character`, `after_persist_character`) before part 1 deletes them; the new code should hook the same moments.
  - *My call:* names taken during play are saved to the language as words, with definitions, like right-click picks.

- **Who understands whom.** The scene's context gets a short note derived from the characters' languages and the similar-language links (owner): no shared language means they can't simply talk; similar languages mean hard but successful talk. Probe 3 checks whether the model acts on it.
- **Foreign phrases.** A character's phrase in another language shows in that language, with its translation on hover (owner), coloured with the `foreign` theme role.
  - *My call:* the narrator gets fitting phrases from the language's list (a character who "curses in Moscavian" gets Moscavian curses). A foreign-looking word the narrator invents anyway is marked unknown, with an offer to add it to the language with a definition.

## Non-goals

- Translating whole sentences or passages (later; the owner called it a nice-to-have).
- Places on a map, travel distances, the calendar (`docs/ideas/world-map.org`, `world-calendar.org`).
- Upgrading worlds made before this slice; the owner starts fresh worlds.
- Carrying anything over from the old culture system except the generator and the fit check.

## Anti-goals

- **Linguistics jargon in front of the owner.** Questions and pages speak plainly ("harsh or soft?"), never "phonotactics" or "fricatives".
- **Languages that use real words.** "Recognizably Russian" must not mean Russian words; the probe judges this.
- **A fix that kills the model's creativity.** Stock titles get rewritten, not swapped for bare generated words; the frame stays the model's.
- **Culture coming back under another name.** Customs and beliefs stay facts and connections.
- **A second look for the same thing.** One naming menu everywhere; one hover card for foreign words (standing UI rule: things that look the same are one component).

## Constraints

- **The owner's standing UI rules** (`feedback/2026-10-25-polish1/triage.md` and the polish specs): controls sit right after what they act on; right-align only in areas half the screen wide or less; same look = one component; the approved screen is the model.
- **Execution for UI parts:** inline, with screenshots after every visible change, the owner's standing preference for UI work.
- **Local models only in the app.** The storyteller model can't be trusted to call tools mid-writing (`languages.org`): naming happens in steps of its own, before or after the writing.
- **Probes before building** anything that depends on a model, and ask before running koboldcpp.
- **Tune the AI handoff layer, not the schema** (owner principle).
- **Dev environment:** see `docs/dev/local-testing.md` (guix shell, `uv run --no-sync`, e2e with `-n 4`). After removing the cultures e2e folder, also grep `tests/ai` for culture selectors.

## Left to the builder

- Where the cliché list that ships with the app lives, and how a world's additions are stored.
- How language data (rules, words, parts, phrases) is stored in the world database, as long as it is undoable like other world data.
- The exact pattern syntax for name structures, building on the kept generator.
- How "the same name keeps turning up" is measured.
- How the right-click menu is shared across every free-text box.
- The order of tasks inside each part.
