# Fantasymate languages 3b-2: fuller languages, and changing them as the world grows

Date: 2026-10-29. Status: approved by the owner, with mockups approved (below).

This follows 3b-1, which is merged (66af7745): making a language from inside the app, by three routes.
- Background reading:
  - `docs/superpowers/specs/2026-10-28-fantasymate-languages-part-3-design.md` (part 3, section 3b);
  - `docs/superpowers/plans/2026-10-28-fantasymate-languages-3b1-making.md` (what 3b-1 built);
  - the 3b-1 acceptance notes (`docs/superpowers/probes/2026-10-28-languages-3b1-acceptance.md`).
- This document changes part 3's 3b where it says so.
- **The owner's own words and decisions** carry no mark.
- ***My call*** marks a decision the owner didn't make. The builder may revisit it with a reason.

## Why

The owner has made real languages through 3b-1 with Claude Code: *Kostrevin* on Sonnet and *Brelovan* on Opus. Both work, but they are thin:
- 25 and 35 words, and 4 and 6 phrases;
- grammar as one short paragraph.

Opus did "significantly better" than Sonnet: more name rules, a larger dictionary and a richer set of sounds. Sonnet was "simplistic, kind of garbled". The brief never asked for size or coverage, so even Opus stopped small.

**How the owner will use a language** (owner):
- **Most days they generate:** naming entries, and adding a word or a phrase along the way.
- **Changes come mostly early,** while the culture takes shape and entries are being written. For example, "writing the religion entry, I'd want to redo the blessings from there". The phrases the AI writes say what a culture values. When that disagrees with the world, or the owner simply has a better idea (even before anything else is made), they want to ask for the change.
- **They want to read up on the language:** its sounds and its grammar, in detail, not a paragraph.

So this round is about two things:
1. **Fuller languages:** a much more complete language from the start, with real grammar.
2. **Changing them:** asking for a change in plain words, from the language's page or from the entry that prompted it.

## Goals

1. A newly made language is **complete enough to use and to read**:
   - a full vocabulary, including structural words;
   - grammar in sections with tables and worked examples;
   - phrases across the usual categories.
2. **The owner can choose how much work the first run does**: one thorough job, or a quick core filled in afterwards in stages.
3. **The owner can ask for a change to a language in plain words**, from its page or from any entry, and review the result before it lands.
4. **The route is chosen in the dialog** for each run.

## Non-goals (this round; the owner: "they can wait")

- Daughter languages.
- English-part naming styles made in the app (Duskhollow).
- A "Test this model" button.
- Hearing the sounds (pronunciation recordings): an idea the owner liked as a nice-to-have.
- Everything in part 4: fixing names in drafts and during play, the scene note, and hover phrases.

## Anti-goals

- **Linguistics jargon facing the owner** without a plain word beside it (part 3).
  - The owner is "rusty on conlangs".
  - Grammar sections may use a term like "noun cases" in a heading, but the text explains it plainly.
- **A change landing silently.** Every change goes through the review and is undoable.
- **A word the world already uses changing under the owner** (part 3).
- **A route that only works for the owner.** Copy the brief must stay a complete path.
- **A fixed grammar schema that can't hold an unusual language.** For example, the owner's idea of conjugating articles onto nouns needs a home.

## 1. Fuller languages

### Grammar as sections with tables (owner: "yes, sections with tables sounds right")

- **The language's grammar becomes a list of sections,** replacing the single text. Each section has:
  - a **title**, and a **topic** (from the standard list below, or `other`);
  - **plain text** explaining it;
  - **tables**, any number: a caption, column headings and rows of cells. They hold conjugations, noun endings by number or case, and the pronoun grid;
  - **examples**, any number, in the same shape as a phrase's breakdown: the original, a word-by-word breakdown and a translation. On the page these show word over meaning, which is the "diagram-like" part.
- *My call:* this generic shape (text, tables, examples) is the schema change. The app never needs to know what "gender agreement" is, only how to show a section. That keeps close to the owner's principle "tune the AI handoff layer, not the schema", while giving the page real tables. An unusual language simply has more sections.
- **The standard topics the brief asks for** (*my call*, from common conlang practice; the owner asked for "word order, conjugation, plurals, agreements, gender"):
  - sounds and stress;
  - word order;
  - nouns: gender or noun classes, plurals, cases or possession, articles and definiteness;
  - pronouns;
  - verbs: person, tense and aspect, mood, and "to be" and "to have";
  - adjectives and agreement;
  - questions and negation;
  - numbers and counting;
  - how words are built (endings for a doer, a place or something small; compounding);
  - how names are built (given and family names, patronymics);
  - politeness and registers.

  The brief also asks for **"anything unusual this language does"** as sections of their own.
- **Old languages:** a language whose grammar is plain text keeps it as one section titled "Grammar", read, not rewritten.
- **The check:** a grammar section's example words are checked like phrase words. They're counted against the language's own rules and flagged when they're real words. Neither blocks.

### A fuller vocabulary

- The brief asks for, by default (*my call* on the sizes; the owner asked for "a fuller lexicon of structural words, english examples being: the, a, be, are, am, was, have, with"):
  - **structural words:**
    - articles, if the language has them;
    - "to be" and "to have" in their forms;
    - pronouns;
    - common prepositions and conjunctions;
    - question words and "not";
    - numbers 1–10, then the tens and a hundred;
  - **about 200 everyday meanings,** based on the standard list linguists use for this (the Swadesh list): body, nature, family, colours, common verbs and adjectives;
  - **words that fit the chosen world entries;**
  - **phrases in every usual category** (greetings, farewells, blessings, curses, oaths, sayings, toasts, insults, endearments), several each;
  - **name rules** for the kinds the world uses (characters, places, items, groups), plus demonyms and the forms of a name.
- The check reports **what's missing against that list** (for example "no word for 'water'"). It's a warning, never a block. *My call:* the app ships the core list of meanings as data, as it ships the real-word lists.

### How much the first run does (owner: "the option for both, thinking of other users")

- **Full:** one long job that makes all of the above. It's the default for Claude Code, since that route uses the owner's subscription (owner: "a more thorough and longer job up front is preferable").
- **Quick, then fill in:**
  - a core language first: sounds, name rules, structural words, the grammar topics in short form, and a few phrases;
  - then background steps, each one a change through section 2: the everyday words, more phrases, fuller grammar tables.
  - It's the default for the agent's model, since that route spends API tokens (owner: "API tokens I might reconsider").
- The choice sits in the Make a language dialog. The dialog says plainly which route spends API tokens.
- **How filling in moves along** (*my call*, the owner drives it; no job queue):
  - The core is reviewed and imported like any made language. Filling in needs the entry to exist.
  - The language's page shows **Still to fill in**, worked out live from the check's completeness report: what's missing against the vocabulary list, phrase categories and grammar topics. It isn't a stored list, so it survives restarts and can't drift.
  - **Fill in next** runs one step as a change: a background job, then its own review.
  - Nothing runs on its own. Dropping a step's review leaves that gap on the list, to run again or ignore.
  - This works the same on every route, Full languages included: anything a Full run left thin shows on the list.
- **Copy the brief offers both sizes too** (*my call*): Full is one brief. Quick is the core brief now, and each Fill in next on the page has its own Copy the brief, to paste back by hand.
- **Full on the agent's model** (*my call*): it's offered as one call, with a plain note that it needs a model that can write a long reply. If the reply is cut short, the failure message suggests Quick, then fill in.
- **The completeness warnings aren't sent back automatically** (*my call*): the repair loop stays for must-fix problems and rule-fit, at most twice, as in 3b-1. A thin result shows in Still to fill in instead, one click away. That keeps the cost of a run predictable.

### The route in the dialog (owner: "show the route choice in the dialog")

- **Make a language** (and **Change it…**, below) shows the route choice: Claude Code on this computer, the agent's model, or Copy the brief. A model field sits next to Claude Code.
- *My call:* the choice is for that run only. It starts on the Language agent's default and doesn't change the setting.

## 2. Changing a language (owner: "that looks right")

- **Where to ask** (owner):
  - **On the language's page,** a **Change it…** box takes any plain request at any time, even before anything else exists ("they're traders, not warriors: redo the curses").
  - **From any entry:**
    - **Change a language to fit this…**, on the entry page and in its right-click menu, with that entry as context ("redo the blessings around the Owl Synod");
    - it offers the languages in reach of the entry first (its Languages section, then where it's filed), then the rest.
- **What a change can touch:** phrases, name rules, grammar sections, the description of how it sounds, and words in bulk ("add 30 words for the sea").
  - Single words don't need an agent (owner): rolling a word and giving it a meaning, as today, stays the way.
- **How it runs** (owner: "a few minutes in the background is fine"):
  - in the background, on the chosen route, with progress, Cancel and Copy the brief, as in 3b-1;
  - the brief carries the current language file, the request, the entries to fit, and the parts of the file format the change needs.
- **Related entries** (part 3, kept):
  - when asking from the language page, the app suggests entries that speak the language, entries filed in those, and entries whose facts use its words;
  - the owner ticks which go in, and can add others.
- **The review:** the existing "new version" review grows to cover everything a change can touch:
  - words: new, changed meaning, removed;
  - phrases: new, changed, removed;
  - grammar sections: new, changed, removed, each section viewable before and after;
  - name rules: what changed, with sample names before and after (as today);
  - the description of how it sounds, before and after, if it changed.

  The owner accepts or drops the whole change.
- **What never changes:**
  - a word the world uses as a name keeps its meanings (3a);
  - the review says when the request asked to change one.
- **One job at a time** (3b-1). While a Make or a change runs, the other buttons are disabled with a note saying why (*my call*: no queue).
- **The owner's own edits during a change are kept** (*my call*): a change takes minutes, and the owner may roll a word or edit a phrase meanwhile.
  - The app remembers the version the change was briefed on.
  - On accepting, it applies only what the change altered (compared with that version) onto the language as it is now.
  - Where the owner edited the same word, phrase, rule or grammar section in the meantime, the owner's edit stays, and the review lists it under "kept your edit".
  - Nothing the owner did is lost silently.
- **Where the review opens** (*my call*): where the change was asked. That's the language's page, or in place on the entry when asked from an entry, so the owner keeps their place while writing it. It's one review component used in both places.

## 3. Reading up on a language

- **The Language tab shows the grammar sections as cards:**
  - each card has its text, then its tables (real tables), then its examples word by word;
  - the topic list works as a table of contents.
- **How it sounds:** the existing sound groups stay, and each sound gets a plain description where one helps (*my call*; for example "zh: like the s in measure"). This is part of the brief's sounds-and-stress section; no audio this round.
- **Approved mockups (owner, 2026-10-29)**, the model for the build:
  - `docs/superpowers/mockups/2026-10-29-languages-3b2-grammar-layout.html`, option **A**: Grammar gets **its own tab** (About · Language · Grammar · Lexicon), with a topic list beside the cards; each card has a Change… link for that section;
  - `…-change-it.html`: **Change it…** in the language page's header opens a panel under it (request, suggested "Fit it to" entries with why, route, Change it / Copy the brief / Discard, and Still to fill in with Fill in next); the review shows what changed by part, before/after, and a "kept" note;
  - `…-make-and-entry.html`: Make a language gains **Make it with** and **How much** rows; on an entry, **Change a language to fit this…** sits beside "+ Add fact" and in the right-click menu, and opens the same panel in place.
- **The new screens got mockups before any code,** following the owner's design-phase preference from 3a:
  - the Language tab's grammar cards;
  - the Change it… box and the entry's "Change a language to fit this…";
  - the bigger review;
  - the route and size choices in the dialog.

## Constraints

- **The owner's UI rules:**
  - controls sit right after what they act on;
  - right-align only in half-width areas;
  - the same look is one component;
  - screenshots at 1920×1080 as well as a small window.
- **The 3b-1 Claude Code boundary stays exactly as it is.** The check runs only by its full path, from outside the work folder, and Claude Code reads and writes only in that folder (`docs/superpowers/probes/2026-10-28-claude-code-route-spike.md`, and the 3b-1 fix).
- **No real model in automated tests,** using the fake Claude Code and fixed replies. Real runs happen only with the owner's go-ahead.
- **Dev environment:** `docs/dev/local-testing.md`.
- **Never restart an isolated app the owner has used** without first saving its `worlds/` and `config.yaml`, because `talemate_app.py start` wipes the root (lesson from 2026-10-29).

## Left to the builder

- **The grammar section's exact field names,** and how a section's tables and examples are stored, as long as old text-only grammar still loads.
- **How the change brief describes the change** (a whole new file, or only the changed parts), as long as the review shows it as a before and after and used words are kept.
- **The order of the "quick, then fill in" steps,** and what each one asks for.
- **How the core list of meanings is stored,** and its exact contents.
- **Whether 3b-2 is one plan or two.** If two, my suggestion is fuller languages and the grammar page first, then changing a language.
