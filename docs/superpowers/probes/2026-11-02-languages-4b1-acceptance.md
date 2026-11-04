# Languages 4b-1 (the grammar engine for names): the owner's acceptance checklist

Date: 2026-11-02.
- **Branch:** `feature/languages-4b1`.
- **Plan:** `docs/superpowers/plans/2026-11-02-fantasymate-languages-4b1-grammar-engine.md`.
- **Spec:** `docs/superpowers/specs/2026-11-02-fantasymate-languages-4b1-grammar-engine-design.md`.
- **Probe:** `docs/superpowers/probes/2026-11-02-languages-4b1.md`.
- **Mockups:** `docs/superpowers/mockups/2026-11-02-languages-4b1-name-it-builder.html` (B) and `…-names-chapter.html`.

There are two checks, as before. **The owner** judges whether each step looks and feels right. **The tests** prove it works: the browser tests drive the real app with fixed model replies and a fake Claude Code.

| Step | What to look at | Proven by |
|---|---|---|
| **The grammar for names in the file.** A language can say where describing words go, how "of" is said, how joined words go, how "the" and "more than one" are made (changes tried in order, each with a condition: always, after a vowel or consonant, before a vowel, more than one, ends with…), and its meaningful endings. Old files load as before. | — | `tests/languages/test_name_grammar_model.py` |
| **The engine** builds words and short name phrases by those rules: Varovni skelt → skeltek, skelti; Tsevrani zhelva → zhelvy; Bumbagoo bumpa → bubumpa; Drassonais "L'Auvre", "Lo Chinou", "Lou Chinous"; "of the Stars" → "Ul Zveski"; "white lake" → "Aunfoimtte Blanchic" in Drassonais. | Are the forms your languages' own? | `tests/languages/test_name_grammar.py` |
| **Composed rules** roll part by part (another rule, a fixed word, a meaning part). A missing or looping rule shows "(missing rule)" and never hangs. Built names count as fitting the language, so they aren't flagged. A plain rule stays the default for its kind. | — | `tests/languages/test_composed.py` |
| **The Names chapter** shows *Grammar for names* under "How names are built". Each rule is in plain words with an example built from it, and a pencil edits that row. A row that can't build says so. A composed rule shows its parts as chips ("Men's names", "Ul", "a meaning · plural"), with a small parts editor. Without grammar: "No grammar for names yet: names are built in your word order", with **Fill them in from the grammar** and **Write them myself**. | Can you read and fix the rules? | `tests/server/test_worlds_name_grammar.py`; e2e `test_names_chapter.py` (4 tests) |
| **Fill them in from the grammar** opens Change it… with "Fill in: the grammar for names". The run writes `name_grammar` from the language's grammar sections and tables, and the review lists the new rules with their examples. The language skill and the briefs describe `name_grammar` and composed rules. | Do the rules match your languages' tables? | `tests/languages/test_brief.py`; e2e `test_language_change.py::test_fill_them_in_starts_a_names_change` |
| **Give a meaning** reads the English in code: "of", "the", plural, the last word as the noun. The model is asked only to split a one-word compound ("Blackwater") or pick a coined word. With a composed rule picked, it fills the meaning parts. "Name it in…" builds through the engine too. | Do names from meanings read right? | `tests/languages/test_naming_meaning.py`; `tests/server/test_worlds_name_it.py` |
| **The builder** (mockup B): a composed rule's name, part by part. Each part has its rolls (the same pinnable chips as the batch), a pin, and a box for your own word, which pins it. **Reroll unpinned**, **Suggest from its facts** (on an entry), **Use this name**, with how it's built shown below. A plain rule keeps the ten-name batch. | Is the builder quick and clear? | checks (builder joins, typing pins, reroll sends pins); e2e `test_name_it.py` (6 builder tests) |

## Real runs, with the owner's go-ahead

In the owner's fresh test app, world Test3, after the update (worlds backed up first, backend restarted alone). These ran in Test3 instead of Test2: Test2 has no character with facts, and Drassonais tests the plural "the" gap the probe found.
- [x] **Fill them in** on Tsevrani and Drassonais, on the agent route (Claude Code).
- [x] **A home-name rule built by hand** on Drassonais, from its own custom ("Families are named for their home: di plus a place"): [Men's names] + [a meaning · of].
- [x] **Give a meaning** "of the Forest" on that rule, from Eilhaud of Drassone's Name it…. "Use this name" was never pressed.
- [x] **Suggest from its facts** on Eilhaud (12 facts).
- [x] **Reroll** with a part pinned.

## Results (2026-11-02)

Screenshots and raw records are in the plan's workspace: `real-runs.json` and `real-*.png`.

**Fill them in.**
- **Tsevrani (72 s):**
  - describing words before the noun;
  - "of" is the word tre;
  - "the" is -k after a vowel, else -ek (dyesh → dyeshek), and -k on a plural;
  - more than one: -a/-o become -y, else -y (dyesh → dyeshy);
  - five endings: -ov one who does, -yk small, -ya land of, -de place, -yn one who is.
  - Its noun table matches.
- **Drassonais (43 s):**
  - describing words after the noun;
  - "of" is the word di;
  - main word first when joining;
  - "the" is **lou for more than one**, l' before a vowel, else lo, which is the probe's plural gap, now expressed;
  - more than one: -s;
  - four endings (-el, -aud, -auve, -ais).
  - Its table matches.

**The home-name rule** showed its parts as "Men's names" and "a meaning · of".

**The builder on Eilhaud:**
- **Give a meaning "of the Forest" → "… Di Sauvaire",** at once (sauvaire is in the dictionary). That is the very example Drassonais's own prose gives: "di Sauvaire, 'of the Forest'".
- **Suggest (6 s, Skyfall)** chose "owl" and coined *osre*: "Nesnhaud Di Osre", with "osre (new word, saved if you pick it)".
- **Reroll with the given name pinned** kept "Nesnhaud" in all three rolls: Di Drassone, Di Nazic, Di Brumic.

**Found and fixed during the runs:**
- "Fill in: the grammar for names" was hidden on a language with nothing else missing (Tsevrani). It now always shows under Still to fill in.
- The rows read "--ov", "“l'” before before a vowel" and "(plural)". They now read "-ov", "“l'” in front before a vowel" and "for more than one".
- The plain batch's meaning line stayed under the builder.

**Noted:** a composed rule's sample names show "Roll to see names." after its parts are edited, until Roll is pressed.

## The owner's rounds and verdict (2026-11-02 to 2026-11-04)

After the real runs, the owner tried 4b-1 in the test app, and each note was fixed in this branch:
- **Fill them in starts at once** from the card's button, and it also turns naming customs into rules made of parts (Varovni's owl-name, with the faked "Ul Kerd" patterns taken out).
- **A dictionary word that means several words stands for them:** ul, "owl-of", so "owl of the sun" gives Ul Svelm.
- **The builder was redesigned** (mockups `2026-11-03-languages-4b1-builder-meaning-per-part.html` and `…-builder-stable-grid.html`):
  - a meaning box in each meaning part, whose Find fills that part only;
  - Suggest fills only the meaning parts;
  - a Form select;
  - the panel-wide box only for plain rules;
  - a fixed grid that doesn't change size between rolls.
- **The name chips change only the word clicked.** Kept words (a title like King or Commander) stay where they are, with a result line ("King + new name + III").

**Verdict:** "alright I think this is all good now".

**Left for 4b-2:** titles the language makes by rank or sex, and relatives' stubs from a son-of or daughter-of name.
