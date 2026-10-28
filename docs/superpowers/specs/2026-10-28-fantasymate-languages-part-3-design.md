# Fantasymate languages, part 3: languages in the world, and how they're made

Date: 2026-10-28. Status: design, awaiting the owner's approval (builder check done).

This narrows part 3 of `docs/superpowers/specs/2026-10-28-fantasymate-languages-design.md` (the "main spec"), now that the probes are in. Read the main spec first; this document only adds to it and changes it where it says so.

The evidence comes from:
- the main spec, part 3;
- the probe reports in `docs/superpowers/probes/`, mainly `2026-10-28-language-make.md` with its Decision section, plus `2026-10-28-name-flags.md`;
- this conversation (2026-10-28);
- the approved mockup `.superpowers/brainstorm/18627-1793167762/content/naming-flow.html`.

Marked *My call* means the owner didn't decide it; the builder may revisit it with a reason. Everything else is the owner's.

## Why

The probes showed that the local models can't make a full language. Skyfall writes real Russian words, and Qwen loses the flavour or runs out of tokens. They can make English-part naming styles, pick among rolled names, and write definitions. So full languages are made outside the app, by Claude or another strong model, and come back as a file.

The owner wants that to feel like part of the app, not a workaround, and wants it to work for other users with other set-ups: a strong local model, an API client, a Claude Code install, or just a chat subscription in a browser.

## The pictures that define it (owner)

1. **First language.** The owner types their prompt ("a unique but recognizably Russian language") and gets back a good basic dictionary, some phrases, and generators good enough to start naming entries with straight away.
2. **The feedback loop.** As the world fills in, the language follows it. The owner writes the religion, then has the phrases redone so the blessings and curses belong to that faith instead of being generic.
   - When choosing what a revision takes into account, the app suggests related entries and the owner can add more.
3. **Routes.** The owner's own route is Claude Code on this machine, run by the app directly, with the brief always available to copy so the owner can steer it in a Claude session instead.
4. **Other users** pick their own route and model once, globally: a strong model in the app, Claude Code, or any outside assistant fed the brief.

## Two builds, in this order (owner)

**3a, languages you can use:** everything needed to have a language in the world and name things with it, made by hand with the reworked skill and imported.

**3b, making and revising from inside the app:** the routes, the brief, the questions and the revision loop.

Part 4 (fixing names in drafts and during play, the scene note, hover phrases) comes after both, as in the main spec.

## 3a: languages you can use

Everything in the main spec's part 3 stays, except where this section changes it.

### The language entry

- **A new entry kind, `language`** (main spec, *My call*, kept). It has a page, facts, a tag and filings like any entry.
- **Three depths** (main spec): description only, naming style, full language. Naming styles can be sound-based or English-part-based (Duskhollow).
- **The technical part** lives in fields of its own:
  - how it sounds (plain text);
  - sound categories and generators in the kept pattern syntax (`talemate.languages.generator`);
  - words with definitions;
  - phrases (curse, saying, blessing, greeting, and so on) with translations;
  - name patterns per kind of thing (main spec part 4's "names have structure"; *My call:* a generator's `use` widens to the entry kinds, plus forms such as an adjective);
  - *My call:* a **word generator** (`use: "words"`) that makes ordinary words. Its rules are what dictionary words are checked against, and what "Name it in…" rolls missing words from. A full language must have one; a naming style doesn't need one;
  - the parent language and similar-language links (main spec).
- **The page shows:**
  - the plain description of how it sounds;
  - about twenty sample names, rerollable;
  - the words, as a searchable table with definitions;
  - the phrases;
  - the generators, read-only by default, with an advanced edit.
  - *My call:* in that order. The technical parts sit below the ordinary page sections (facts, connections).
- **Words used in the world are fixed.** A word that names an entry (Moscavia, Velgarov) is marked as used, and nothing replaces or reworks it. *My call:* the mark comes from the entries' names and other names, and isn't stored separately, so it can't drift.
- Every change to a language is a world edit, undoable like any other.

### The file format and import

- **The language file:** versioned JSON whose content is the language entry's technical part plus its name and description. *My call:* it's close to today's `Language` model in `talemate.languages.models`, extended as above. It gets a schema file, and the skill writes to that schema.
- **Import:** from a file, or by pasting the text, which is what chat users have. The result is a new language entry, or a revision of an existing one (see "What a revision does").
- **The shared check,** for every language whatever made it (import, the in-app model, a hand edit). It's the same code in 3a and 3b:
  - the file is valid against the schema, and the generators parse (`validate_language`);
  - the language's own words fit its word generator (`fits`), with the share reported.
    - *My call:* this never blocks.
    - Words made of other words (Velgarov = vel + garov) count as fitting when each part does.
    - English-part naming styles skip it: their parts are real English words on purpose;
  - no real words, for its flavour:
    - *My call:* **flavour is a field on the language** ("Russian", "English", or none), set from the request and editable on its page. It isn't a world setting;
    - *My call:* the app ships real-word lists per flavour, starting with the probe's Russian list (words and names) and an English list of real place names;
    - for a Russian-flavoured language, real words and names are flagged, in its dictionary and in rolled names;
    - for an English-part naming style, the parts themselves are never flagged (dusk and hollow are real English on purpose), but **whole names that match a real English place are flagged** (owner: Thornfield, Ashford and Ravenford get a flag);
    - a language with no matching list skips this check, and says so;
  - sample names are rolled and shown.
- **What blocks** (*My call*): only an invalid file or a generator that doesn't parse. Words that don't fit and real-word hits are warnings.
- **The repair note.** A check with problems produces a plain note listing exactly what's wrong. Blocking problems come first ("`*n` was written as text in pattern …"), then warnings ("3 words don't fit the rules: …"). It's written for pasting back to the assistant that made the file. The headless route sends it back automatically only for blocking problems, or when warnings cover more than a third of the words (*My call*).
- **Accepting an import:** the owner sees the result (samples, word count, phrases, and the check's report) before it lands. A file with a blocking problem can't be accepted until it's fixed.

### Languages sections, lookups and right-click

As in the main spec, with nothing changed:
- Languages sections on any entry and on characters: roles, shares, dates, and fluency for characters.
- The lookup through filings, and a character falling back to where they're from.
- Similar and parent languages.
- Right-click *Make a name* / *Make a phrase* / *Add word* in the worlds screens and the scene's message box.

Picks are saved as words with definitions. Definitions come from the in-app model. The probe found Skyfall's best, and the client is the language agent's (see 3b; in 3a it's the creator agent's client, *My call*).

The old field name `language` is asserted absent by `tests/world/test_kinds.py::test_the_old_structure_is_gone`. The new kind is `language`, and the new field is `languages`, so that test keeps its meaning. Update its comment.

### Names in other languages (changed from the main spec)

The main spec has the model coin missing words when a name is given in another language. The probe showed both models fail at that: they wrote real Russian, or nonsense. So instead:
- Each missing word is **rolled from the language's own rules**, and the model only **picks** among the candidates and writes the definition. Picking works on both local models.
- The owner can type the word instead, as with *Add word*.

### The language-design skill

- `.claude/skills/culture-design/` becomes `.claude/skills/language-design/`, rewritten for the new file format.
- It produces a full language, a daughter (from a parent file and a drift description), or a revision (from the current file and a request).
- It runs the shared check through a small command the app provides, and fixes its own output before handing it over. *My call:* a CLI entry point beside the app, so the skill and 3b's headless route use the same check.
- From the end of 3a the owner can make Moscavian with Claude Code by hand and import it.

## 3b: making and revising from inside the app

### The language agent (global)

- **A new agent,** set once in the app like the others, with its own client (owner: the route and model are global). Anything world-specific lives in the world, not here.
- **Its routes** (owner):
  - **in the app,** on the agent's client: a strong local model or an API;
  - **Claude Code on this machine:** the app runs Claude Code headless with the brief, and imports what comes back;
  - **copy the brief:** always available, whatever route is set, so the owner can take it into any assistant and steer.
- **Per job** (*My call*, from the probe):

  | Job | Default route |
  |---|---|
  | full language, daughter, revision, "more words for X" | outside |
  | naming styles, picking names, definitions | in the app |

  Each job's route can be changed.
- **"Test this model"** (*My call*, agreed in principle): next to the in-app route, a button runs a small make-and-check on the chosen client and shows the result, so a user knows in about a minute whether their model can do the job.
- **Guidance:** the settings say plainly which jobs need a strong model, from the probe's findings, without naming models that will go stale.

### Before the brief goes out: questions in the app

- The plain-language questions are asked in the app by the in-app model, which works locally per the probe. The owner can answer or say "decide for me".
- The answers go into the brief, so every route gets them, including headless Claude Code, which can't ask anything.

### The brief

The app writes it, and it's the same text for every outside route. It holds:
- the request (new language, daughter, revision, more words) in the owner's words, with their answers;
- the current language file, for a daughter, revision or more words;
- the world context: the selected entries' facts (see below);
- the file format: the schema, an example, and the "no real words" rule;
- the instruction to run the check if it can, and to return the file as an artifact or code block.

### The Claude Code route

- The app runs Claude Code headless with the brief and the language-design skill, in a scratch folder.
- **What it may do** (owner, as recommended): only run the app's check command, and read and write inside that scratch folder. Every other tool and command is refused. The route is meant for other users' machines too, so it never skips permissions.
- It takes the file back and runs the shared check. On a failure, it sends the repair note back, at most twice (*My call*).
- It shows progress while running, and can be cancelled.
- Copy-the-brief stays one click away throughout.

### The revision loop (owner)

- On a language's page there's *Revise…*: the owner says what they want ("redo the blessings and curses around the Owl Synod").
- **Related entries are suggested,** and the owner can add more (owner). *My call* on what's suggested:
  - entries whose Languages sections name the language;
  - entries filed in those;
  - entries whose facts use the language's words.

  The owner ticks which ones go in.
- The result comes back through the shared check. The owner sees what changed before accepting: new, changed and removed words and phrases, and changed generators, with sample names before and after.
- Used words never change (see 3a). A revision that tries to change one is corrected before it's shown, and the change is reported.

### Naming styles made in the app

- An English-part naming style is made from a description or from example names, on the in-app route (the probe: both local models do this well from examples).
- "More parts" grows it, also in the app.
- The result goes through the same shared check and acceptance as an import.

## Non-goals

- Translating whole sentences (main spec).
- Anything from part 4: fixing names in drafts and during play, the cliché lists, the scene note, hover phrases.
- Running Claude Code anywhere but this machine; there's no remote-agent support.
- Upgrading old worlds (main spec).

## Anti-goals

- **Linguistics jargon** in questions, guidance or the check's report (main spec).
- **Silent changes to a language.** Every import or revision shows its changes first and is undoable.
- **A used name changing under the owner** because a language was revised.
- **A route that only works for the owner.** The copy-the-brief route must work with any capable chat assistant.
- **The local model writing words it can't write.** Translations are rolled from the rules, not written by the model (probe).

## Constraints

- **The owner's standing UI rules:** controls sit right after what they act on; right-align only in areas half the screen wide or less; things that look the same are one component; the approved screen is the model.
- **UI work is built inline,** with screenshots after every visible change (the owner's standing preference). The new screens have no mockups, and get none first (owner): the language page, the import review, the revision dialog, the agent's settings and the Claude Code progress view are designed in the build, through rounds of screenshots and the owner's feedback. Right-click naming and the Languages section follow the approved mockup.
- **Probes before model-dependent parts,** asking the owner before koboldcpp runs (standing rule; the owner pre-approved plan 1's probes only).
  - 3a's model jobs (definitions, picks) were probed.
  - 3b's in-app questions and naming styles were probed.
  - The headless Claude Code route needs a spike before its plan, to settle invocation, output capture and the skill's check (dev-process lesson: spike risky integrations).
- **Tune the AI handoff layer, not the schema** (owner principle).
- **Dev environment:** see `docs/dev/local-testing.md`.

## Left to the builder

- How the language entry's technical fields are stored (json fields like `filings`, or tables of their own), as long as they're undoable world edits.
- The schema file's exact shape and version field.
- Where the real-word lists live, and their format.
- The CLI command's name and options.
- How headless Claude Code is invoked and its output captured, after the spike.
- The order of tasks inside 3a and 3b, and whether each splits into more than one plan.
