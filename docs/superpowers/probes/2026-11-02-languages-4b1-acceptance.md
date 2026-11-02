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

In the owner's fresh test app (Test, Test2, Test3, Moscavia), after the update:
- [ ] **Fill them in** on Varovni (Test2) and Tsevrani (Test3), agent route. Check the built examples against their own tables.
- [ ] **Add an owl-name rule** to Varovni by hand: [People (male)] + Ul + [a meaning · plural].
- [ ] **Give a meaning** "of the Stars" on that rule, from a character's Name it….
- [ ] **Suggest from its facts** on a Test3 character.
- [ ] **Reroll** with a part pinned.

## Results

To be filled in after the runs.
