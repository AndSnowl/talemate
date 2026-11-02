# Fantasymate languages 4: clean names in drafts, and fuller names

Date: 2026-10-30. Status: approved 2026-10-30; 4a revised by the owner on 2026-11-01 after using it ("4a revised" section). Mockup approved: `docs/superpowers/mockups/2026-10-30-languages-4-clean-names.html` (frame 1, and layout 2A for the Names page).

This is part 4 of `docs/superpowers/specs/2026-10-28-fantasymate-languages-design.md` ("Part 4: the AI side"). It replaces that section's "Drafts: flag and regenerate" and its name-structure bullets. Parts 3a to 3b-2b are merged (0b91e3ce).
- **The owner's own words and decisions** carry no mark.
- ***My call*** marks a decision the owner didn't make. The builder may revisit it with a reason.
- **Scenes are out of this round** (owner, 2026-10-30): naming during play, who understands whom and foreign phrases wait for a scene rework. That rework will also need the scene to take in the world and write to it through the inbox. The part 4 "Scenes" section of the languages design stays as written, for that round.

## Why

The owner has made many drafts from one starter, "the Tsardom of Moscavia". Its fact text keeps bringing in real places, such as Novgorod and sometimes Moscow. The effect varies from draft to draft:
- sometimes the world stays fantasy;
- sometimes it turns alt-history;
- sometimes it becomes strict history.

The owner wants fantasy. Real names do more than sound wrong: they tell the model what kind of story this is. A world mostly full of its own names should keep the model in fantasy.

People who want alt-history or real history just won't make a language (owner). So **where no language is in reach, nothing is replaced**. That needs no setting.

Probe 2 (`docs/superpowers/probes/2026-10-28-name-flags.md`) found four kinds of bad name:
1. **Famous real names** (Moscow, the Volga). The local model (Skyfall) caught 20 of 20.
2. **The AI's stock names** (Maren, Elara, Kael). They're invisible to the model, so they need a list.
3. **Stock titles** ("the Iron Council"). The model missed a third of them, so title shapes go on a list too.
4. **Real words used as names**, which is the biggest leak: Kholodnaya ("cold"), Velikograd ("great city"), and real given names and surnames (Dmitri, Yelena, Voronov). A list of real places misses most of these, and the model was never tested on them. A name the language didn't make also fails the language's own fit check.

The owner also wants **fuller names for people**:
- names built from other name rules (a full-name rule made of single-part rules);
- the several names one person has: full, familiar, formal, nickname.

## The two parts

| Part | What it builds | Why this order |
|---|---|---|
| **4a: clean names in drafts** | replacing bad names before the owner sees a draft; the hover card; the Names page; the draft's language found from the prompt | the problem the owner actually hit |
| **4b: fuller names** | name rules made of other rules; parts taken from connections; kinds of other names | builds on 4a's replacing; 4a uses single rolled names until then |

Each part gets its own plan. Both need **probe 4** first (below), on the local model, with the owner's go-ahead before it runs.

## Goals

1. **Text the AI writes for review** arrives with real names, AI stock names and stock titles **marked**, never replaced (revised 2026-11-01). Names the model or the fit check doubts are marked too. This covers a draft's own name, its facts' text and its new stubs, on every review screen.
2. **The owner names things deliberately** with **Name it…**, on any selected words: random names from a rule they can see and narrow, with fast rerolls, or a name made from a meaning.
3. **One Names page** in the world's Settings shows every list that affects this world, the world's own and the app-wide ones together.
4. **The draft knows its language from the owner's words**, including more than one language, before anything is generated.
5. **A person's name has the structure its language gives it** (4b), with parts from the world where the world knows them.
6. **A person can carry several kinds of name** (4b): full, familiar, formal, nickname.

## Non-goals

- Scenes (see above).
- Replacing names in text already saved. Only AI text under review is cleaned; what's saved is the owner's.
- Tracking a person's life stages (a child-name becoming an adult name). The owner adds the new name as another name when it happens (*my call*, agreed in conversation).
- Working backwards from a name to its source. A father made after his daughter doesn't get his name from her "daughter of" name automatically: that's the owner's job (owner).
- Upgrading old worlds.

## Anti-goals

- **Overfitting to Moscavian** (owner). The name building blocks must cover naming customs well beyond "son of / daughter of" (see 4b).
- **A draft that reads worse after cleaning.** A replaced name sits in the same sentence and the sentence must still read naturally; stock titles keep their frame and only the name slot is filled (from the languages design).
- **Remembering old names.** Once a draft is accepted, only the new names exist (below).
- **Linguistics jargon** in front of the owner (standing).

## 4a revised (owner, 2026-11-01): mark, don't replace; Name it…

The owner used the built 4a in the test app (worlds Test and Test2). Their verdict:
- the automatic replacing isn't accurate enough;
- it loses meaning ("Court of Lakes" became "Court of Kinchvovy Brezhi": what does that mean?);
- it gets in the way of naming things deliberately.

Approved mockup: `docs/superpowers/mockups/2026-11-01-languages-4a-name-it.html` (owner, 2026-11-01):
- frame 1: a draft marked, not changed;
- frame 2: Name it… on part of a name;
- frame 3: Name it… on a saved entry.

**This section supersedes "How it's replaced" and the replace half of "What the owner sees" below.** Where the two disagree, this one wins. Finding names (the lists, the flag call, the fit check, the languages found from the owner's words), the Names page and the hover card stay as built.

### The narrator rule (owner)

The world is written in the narrator's language: English, as a story would tell it.
- **A language supplies:** names of people, places and things; flavour such as sayings, oaths and inscriptions; and ancient or magical words.
- **Everything descriptive stays English:** "the Tsardom of Otsyenya", "the Court of Lakes", "the Duchies of the Greywash Coast". The Otsyenyans surely have their own words for these, but the narrator's are the useful ones, for the model and for the owner.
- **A foreign word always shows its meaning where it has one.** Vryushovsk is "the lake". A name can also have no meaning today, like "Australia": a history, not a translation. Both kinds are wanted.
- **What gets built now (owner, 2026-11-01):** the draft prompts tell the model to keep descriptive words in English and to use the language only for names. The Name it… panel shows meanings. **Later, with the scene rework:** every foreign word anywhere in the text shows its meaning on hover.
- **A stock English title is never turned into a foreign phrase.** It's marked. The owner may give it fresher English, or name its name slot ("the Court of Vryushovsk", after the lake).

### Drafts mark, never replace (owner)

- **Every review screen marks flagged names and changes nothing.** That's a new entry's draft, Add facts, Add event and a group's + Add. The flagged names are: on a list, flagged by the model, or not fitting the language (unchanged from the built 4a).
- **The text arrives exactly as the model wrote it.** A list hit (Novgorod) is marked too, not swapped.
- **The card says why** ("a real city", "an AI cliché", "doesn't sound like Otsyenyan"), and offers **Name it…**, **Keep it** and **Never flag it in this world**.
- **What goes:** the pick call, the title rewrite, the spare names and **Reroll** on a mark. Their work moves into Name it…, where the owner chooses.
- ***My call:* a flagged name that's also a new stub keeps the stub's look.** The flag adds a thin wavy underline in the warning role, and one card holds both: the stub's own (kind, Expand) and the flag's ("flagged: a real city", Name it…). The owner found the replaced mark hid the stub.

### Name it… (owner)

- **Where:** on any selected words, the whole name or part of it. For example, select "Greywash" in "Duchies of the Greywash Coast". It works in a draft, on a stub, on an entry's name and in a fact's text, from the flag card or from the selection's right-click menu.
- **The panel stays open while the owner picks:**
  - **The rule in use is shown and can be switched** (country names, place names, men's names, women's names, words…). It can also be narrowed to **one pattern of a rule** (owner: "roll for one specific pattern only").
  - **A batch of names, about ten.** **Reroll** gives a fresh batch on each click: fast, no hovering, never cycling a short list. Speed matters most: the owner picks most names and many rolls aren't good.
  - **From a meaning:** the owner types what it should mean ("lakeland"). They get the language's word or words for it, each with what it's built from.
    - ***My call:*** this reuses the existing Name it in… translation: look up each English word, coin any the language lacks, with a meaning.
    - Picked words are saved to the language with their meaning.
- **Picking a name** puts it where the selection was.
  - **On an entry's or stub's name, it renames the entry,** and every link to it follows. No stub of the old name is left (the owner's Tsargrad → Khyagovsk left a Tsargrad stub).
  - **The picked word goes into the language's dictionary**, with its meaning or none.
- ***My calls* (from the builder check):**
  - **In a draft, a pick changes every place the draft writes those words:** name, facts, facts for other pages. A flagged name that wasn't a stub becomes a ticked new stub, as other new names do.
  - **Renaming a draft or a stub forgets the old name.** Renaming a saved entry keeps the old name as a common other name, as renaming does today (`repoint.retitle`), since its history and scenes may still use it.
  - **Rolled names don't ask the model for meanings,** so a reroll is instant. A rolled name made of dictionary words shows that meaning. Otherwise it's saved with none. **From a meaning** is the way to get one.
  - **On words that link to an entry, Name it… renames that entry everywhere,** and the panel says so.
  - **Name it… replaces the right-click "Make a name / Reroll this part" items** (one look, one component). "Name it in…" (translation) stays.
  - **One mark for every flagged name.** The card says why. A stub keeps its stub look, plus the thin wavy underline.
- **With no language behind the selection,** Name it… asks which of the world's languages to use. A built-in default language for worlds without one comes later (owner: maybe one they make with the language system).
- **"Named after someone"** (the lake named for a person, as in Lake Borodey or Borodevsk) is 4b: building blocks with forms.

### Languages as entries the model knows (owner)

- **A language entry has facts like any other entry,** and its page shows them, with Add fact and Add facts.
  - A draft's "facts for other pages" can target a language.
  - ***My call:*** making a language writes one fact about it ("Otsyenyan is the tongue of the Tsardom of Otsyenya"). The model then knows "Varonvi" is a language, not a codex, as one draft assumed.
- **The language-design skill makes separate men's and women's name rules by default** (the owner always asks for it).

### Bugs from the owner's run, to fix

1. **Names in a draft not stubbed:** country names in "Eared Owl-folk" (world Test) were made but not stubbed. Find whether cleaning broke new-name detection.
2. **Picking a language for a stub:** the row appears late, so the owner added it twice. It should show at once, with a busy indicator while anything is generated.
3. **A draft from a stub ignores the language it inherits:** "Pick a language" shows although its filing gives one.
4. **"Duchies of the Greywash" was judged as one name** after "Coast" was dropped. A name's parts should be found more carefully.
5. **A rename left the old stub behind** (Tsargrad), covered by Name it… above.

### Later

- a built-in default language for worlds with none;
- "named after someone" place forms (4b);
- scenes: language as flavour and as gameplay (who understands whom, translators, private talk), in the scene rework.

## 4a: clean names in drafts (as first built; partly superseded above)

### Which AI text is cleaned

**Most of what the AI writes for review** (owner), so the app is consistent and the same UI isn't remade several times:
- a new entry's draft;
- a stub made from a new connection;
- **Add facts…** on an existing entry;
- adding to a timeline;
- the facts a draft writes onto other existing entries ("elsewhere");
- any other screen where AI text waits for the owner's accept.

That means **one cleaning step and one marked-text component**, used by every one of these screens. The builder lists the screens from the code; the plan says which come in 4a.

**Descriptions are no longer generated in the draft** (owner). The owner always edits a draft, which makes its description out of date, and replaced names make that obvious. **The description is generated when the draft is accepted**, from the accepted facts and names. ***My call:*** the description is told to use only the names in the facts, and isn't cleaned this round.

### When names are cleaned

- **Only where a language is in reach of the draft.** That's the language found from the prompt (below), or the lookup an entry already uses (`languages_for`, `src/talemate/languages/lookup.py:116`) when the draft is filed somewhere.
- **No language in reach:** names that would be replaced are left as they are and marked, and the draft offers "Pick a language for this draft" (the right-click's picker). Cleaning runs once one is picked (from the languages design).
- **What gets checked:**
  - the draft's own name;
  - every name in its facts' text;
  - every new stub.
  
  Today a draft's new names come from the model's reply (`parse_names`, `src/talemate/worldplay/create.py:871`), not from the text, and capitalised phrases the reply didn't list stay suggestions (`unknown_proper_phrases`, `src/talemate/world/names.py:513`). Cleaning must cover the names in the text, whether or not the reply listed them. ***My call:*** a real name found in the text that the reply didn't list is treated like a listed new name: it is replaced, and its replacement becomes a new stub.

### What is never replaced

***My call*** (from the builder check):
- **words the owner typed in the prompt.** The owner meant them: "Tsardom of Moscavia" stays, and so does a deliberately written "Novgorod";
- **names of entries that already exist**;
- **words already in the language's dictionary**;
- **title words inside a name** ("Tsar", "Prince", "House of"), which stay as written. Only the bad part of a name is replaced: in "Tsar Dmitri II", only "Dmitri" is, and a real given name with an invented surname keeps the surname;
- **names on a keep list.**

### How a bad name is found

A name is replaced when any of these says so:
1. **The lists** (below): real names, AI stock names and stock-title shapes, from the app and from this world. A name on a "keep" list is never replaced.
2. **The model's flag** (probe 2's flag call): real or stock title. It's needed because no list holds every real place.
3. **The real-words list for the language's flavour** (`src/talemate/languages/data/real_words/`, used by the import check today).
4. **The fit check** (`name_fits`, `src/talemate/languages/generator.py:554`) **marks a name as suspect; it doesn't replace it** (owner). A name built from real words won't fit, but neither will many good names the model invents. Probe 4 measures how often each happens, and may move a clear class of misfits (say, a name made entirely of real words) to replacing.

### Suspect names (owner)

- A suspect name stays as written, with a **second kind of mark**, distinct from a replaced name's.
- **Its hover card** says why ("doesn't sound like Moscavian", or "close to the real word *kholodnaya*, 'cold'") and offers:
  - **Replace it:** rolls a name from the language, which then shows as a replaced name;
  - **Keep it:** the mark goes, and the name is accepted with the draft;
  - **Never flag it in this world:** adds it to the world's keep list.
- **On accept,** a suspect name still marked is kept as written. A suspect mark never blocks accepting.
- This adds one mark and one card state to the approved frame 1; the plan's first UI task shows it to the owner.

### How it's replaced

- **People, places and things:** a name is rolled from the language's rule for that kind (`generator_for`, `naming.py:55`). The model picks among candidates, as right-click naming does.
- **In 4a, each bad part of a person's name gets one rolled word** (*my call*). Frame 1's "Dorovan Kolvesky" and its unticked "father of" stub show where 4b takes this; full names with structure come in 4b.
- **Stock titles:** the model rewrites the frame and fills the slot from the language. Use probe 2's tight prompt (examples, at most six words, a literal `{name}` slot; accept `{Name}` too), and tell it plainly to keep the kind of thing. Probe 2 found the context line pulled rewrites off course: a kingdom became "Spring Envoys".
- **More than one language:** names are rolled from the draft's languages by their share. When the sentence clearly ties a name to one group ("the Sorauan town of…"), that group's language is used.
- **Names in a sentence** are swapped in place. The sentence must still read correctly: the owner's example is "trades furs with Novgorod" becoming "trades furs with Sovyetsk".
- **Every replacement becomes a new stub** in the draft, saying what it replaced ("replaced Novgorod"). This happens whether or not the original was a stub. Stubs start ticked, as other new names do.
- **Each new name is saved to the language as a word** when the draft is accepted, with a meaning when it has one (owner), as right-click picks are now.

### What the owner sees (mockup frame 1, approved)

- The draft arrives already cleaned. Each replaced name is marked (a dotted underline in the mockup).
- **Hovering shows a card:** the new name, "was" the old one, why ("a real city, on Real places, all worlds"), and how it was made when it has a meaning ("*sovy* 'owl' + -etsk").
  - **Reroll:** another name from the language.
  - **Keep Novgorod here:** this draft only.
  - **Never replace Novgorod in this world:** adds it to the world's keep list.
- **A Languages section on the draft.** It's hidden on drafts today (`ThingPage.vue:294`), and this round shows it: the language found from the owner's words, its role, and "from your words". The owner can change it before accepting, and changing it re-rolls the replacements (*my call*, agreed in conversation).
  - **On accept, the rows are saved as the entry's own Languages,** so what's filed under it inherits them (owner: "the draft fills in the new entry's Languages section").
  - **When the draft is also filed under an entry with languages,** the draft's own rows win, as an entry's own rows already win in the lookup (`languages_for`). With no rows found from the words, the inherited languages are used for cleaning and nothing is saved.
- **New stubs** list each replacement with what it replaced.
- **Accepting forgets the old names** (owner). The text says Sovyetsk and only Sovyetsk exists. Nothing records Novgorod → Sovyetsk. If the model writes Novgorod again later, it's a new place that needs a new replacement: the model already has Sovyetsk in its context, so a new Novgorod is a different place to it.

### The language from the owner's words

- **Before the draft runs,** the app looks for the world's languages in the prompt:
  - the language's name ("Moscavian");
  - ***my call*** close forms of it, mainly the country form that shares its stem ("Tsardom of Moscavia");
  - the language's other names.
- **Several languages:** the draft fills its Languages section from the owner's wording, using the existing roles and shares. "Mostly Moscavian, with a Sorauan minority in the south" gives Moscavian (official) and Sorauan with a smaller share.
- How the wording becomes roles and shares (the model, or rules) is for probe 4 and the builder.

### The lists, and the Names page (mockup 2A, approved)

- **Three lists of names to replace:** real names, AI clichés, stock titles. Plus **one list of names to keep**.
- **Two levels** (owner): this world's own, and the app's, which every world uses. "Per world, with an option to make it global."
- **One Names page,** in the world's Settings. Both levels show together:
  - each row is marked "all worlds" or "this world";
  - a world row has **Make it global** and **Remove**;
  - an app row has **Turn off here**, which keeps it for other worlds, and ***my call*** **Remove everywhere**, behind a confirm, so the app's lists can be edited without opening the config file.
- **The world's Settings gains tabs:** General (today's curation settings, `CurationSettings.vue`) and Names.
- **Adding to the lists from anywhere** (owner): the hover card's "Never replace…", and a name's menu (from the languages design: mark it "AI cliché", for the app or the world).
- ***My call:*** the app suggests a cliché when the same name keeps turning up across the world. That's from the languages design; how "keeps turning up" is measured is left to the builder.
- **Starting contents:**
  - real names: probe 2's labelled set, plus famous places for the flavours the app ships real-word lists for;
  - AI clichés: probe 2's (Maren, Elara, Thornwood, Kael, Lyra) and the usual ones;
  - stock titles: probe 2's fifteen shapes.
- **Where they live** (from the code): the world's lists in the world's meta, beside the curation settings (`src/talemate/world/store.py:882`). The app's lists in the app config (`src/talemate/config/schema.py`, as a new section or within `CreatorConfig`), seeded from a file that ships with the app.

## 4b: fuller names

**Split (owner, 2026-11-02):** 4b-1, the grammar engine, is designed in `2026-11-02-fantasymate-languages-4b1-grammar-engine-design.md`. 4b-2, people's names on top of it (full names that adapt to what the owner gives, parts from connections, forms by sex or rank, forms of address by kind of relationship with per-person overrides, pet names from rules with invented ones as overrides), comes after. The sections below are its starting point.

### Name rules made of other rules

The owner's idea: a full-name rule is a composition of single-part rules, and the AI (the language-design skill, a change) can write one out of rules the language already has.

**The building blocks** (*my call*, agreed in conversation). They're general, so each language uses its own mix:
- **A name is a list of parts, in order.** A part is one of:
  - **another name rule,** rolled;
  - **the name of something the person is connected to.** The part says which connection by its role words ("father", "mother", "clan", "born in", "lord"). Today a connection is a filing with a free-text role (`src/talemate/world/filing.py:83`); there are no fixed relationship kinds, and this round doesn't add them;
  - **a fixed word** ("of", a title).
- **A part can take a form,** chosen by something about the person: man or woman, rank, married or not. The language defines the choices; they aren't fixed to man and woman. Moscavian's family name has a woman's form: Strazhin → Strazhina.
- **A form can add an ending to a name**: Borodey + -evra = Borodevra.
- **What a form is chosen by** (man or woman, rank, married) ***my call***: the model reads it from the person's facts when the name is made. No new field is added (tune the handoff, not the schema). A rolled parent's form follows the connection's role words: "father" is a man.
- **A part can be optional.** An optional part with nothing to fill it is dropped; a required one is rolled (below).

**The customs these must express,** which test against overfitting (owner's caution):

| Custom | Example |
|---|---|
| from a parent | Mileva Borodevra (daughter of Borodey) |
| from a child | "father of Arin" |
| from a place | "of Kolvagorsk" |
| from a group | "of the Owl Synod", a clan or house name |
| from a role or a deed | "the Smith", "Ironhand" |
| order that changes | family name first; a title in front |
| forms by sex, rank or marriage | Strazhin / Strazhina |
| no personal name | a role or a description stands in (an unwritable language) |

Names that change over a life are not modelled (Non-goals).

### Parts from the world

- **If the connection exists,** the part uses that entry's name (owner): Mileva's daughter-of name comes from her actual father, Borodey.
- **If it doesn't exist and the part is required,** the part is rolled. The person the rolled name implies is offered in the draft's New stubs, **unticked**, with the connection ready: "Borodey, father of Mileva" (owner). Ticking it creates him already connected.
- **A father made later** isn't worked out from the daughter's name: that's the owner's responsibility (owner). The daughter's page says "daughter of Borodey" in words, which the model often picks up from context.
- The draft finds connections first, as it does now. A prompt that says "Borodey's daughter", with Borodey in the world, proposes that filing, and the name is built from it.

### Kinds of other names

- **Other names gain a kind** (owner): full, familiar (friends and family), formal (strangers and work), nickname. Today an other name has a name, tag, everyday flag and language (`AKA_KEYS`, `src/talemate/world/kinds.py:420`), and no kind.
- **The language can have a rule for each kind**, built from the same blocks. For example, a Moscavian pet-name rule gives Mileva → Milya.
- **A drafted person gets the kinds their language has rules for,** filled in, each saved with its language.
- How kind relates to today's "everyday" flag is left to the builder. ***My call:*** "everyday" stays as it is, for places and things that have a common name.

### The language file

- The language file (`language.schema.json`) gains composed rules and per-kind name rules. The language-design skill and **Change it…** learn to write them, and the import check validates them.
- **Old files without them still load.** People then get single rolled names, as in 4a.
- A language whose grammar has a "How names are built" section (the test world's Moscavian has one) is the model for what a change should turn into rules.

### Word order from the language's grammar (owner, 2026-11-01)

From a meaning builds a name in the owner's English word order, word by word. "white lake" in a French-like language comes out "Blanchic Aunfoimtte" (white lake), where the language would likely say "lake white". Names built from meanings should follow the language's own order: an adjective before or after its noun, possessives, "X of Y". That order is in the grammar's `word_order` and `adjectives` sections. The model could read them, or the language file could carry a small machine-readable order rule.

### The language agent on the world's model (owner, 2026-11-01)

A language made through the agent route (Claude) writes facts that repeat the brief: "French-like" and "Russian-sounding" end up in the world's context. Its phrases, especially curses, come out tamer than the world's own model (Skyfall) writes. To try: let the language agent hand the creative parts to the world's main model (facts, phrases, maybe the dictionary's flavour), keeping the structure, rules and checks with the agent. Probe it first: the same language brief, with phrases and facts from each model.

## Probe 4 (before building; ask the owner before running)

On Skyfall, through the app's own calls where they exist:
1. **Real names in fact text.** Run the Moscavia starter and its follow-ups (capital, neighbours, a noble house, the great river), several times each, and count the real names in facts, not only in the names list. Probe 2's ten drafts found no Moscow or Novgorod; the owner's runs did.
2. **Flagging names built from real words:** Kholodnaya, Snegovaya Krepost, Velikograd, Strazh, Snezhana, Solovyov. Does the model flag them? Does the fit check catch them, and how often does it catch good invented names by mistake?
3. **Rewriting a sentence around a swapped name:** does the sentence still read right, and does the model keep the kind of thing?
4. **Languages from the prompt:** for ten prompts naming zero, one or two languages in different wordings, compare the roles and shares the model proposes with the owner's reading.
5. **Composed names (4b only, can come later):** given Moscavian's "How names are built" section, can Claude Code (the language-design skill) write the composed rules? This runs through Claude Code, so ask first; it spends the owner's subscription.

## Constraints

- **Standing UI rules:**
  - controls sit right after what they act on;
  - right-align only in areas half the screen wide or less;
  - things that look the same are one component;
  - the approved mockup is the model;
  - screenshots at 1920×1080 and a small window.
- **Execution for UI:** inline, with screenshots after every visible change.
- **Local model in the app.** Cleaning runs as its own step after the draft's reply, not as tool calls by the storyteller.
- **Probes before building** anything that depends on the model; ask before running koboldcpp or Claude Code.
- **Tune the AI handoff layer, not the schema** (owner principle), except where this document adds fields: the lists, a draft's Languages, the other-name kind, and composed rules.

## Left to the builder

- How names in a fact's text are found (the reply's list, capitalised phrases, the model), as long as goal 1 holds.
- The exact syntax for composed rules and forms in the language file.
- How a connection's role words are matched (case, plurals, "daughter of" against "father").
- Whether cleaning runs in the same model call as the draft or as a second call (probe 4 informs this).
- How the hover card is shared with other hover cards (one component for one look).
- The order of tasks inside each part.
