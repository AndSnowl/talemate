# Languages 3a (languages you can use): the owner's acceptance checklist

Date: 2026-10-28. Branch: `feature/languages-3a`.

The tests passed on this branch:
- the plain suite: 7438 passed, 6 skipped;
- the full e2e suite: 143 passed, `-n 4`;
- the frontend checks and the build.

## What to try, and what should happen

- [ ] **Make a language with the skill.** In Claude Code, ask for "a unique but recognizably Russian language" (the `language-design` skill). It asks a few plain questions, or decides if you say so, then writes `<name>.language.json` and runs the check until it passes.
- [ ] **Import it by pasting.** In the World tab, open Languages and paste the file, or the assistant's whole reply with its chat text around it. Press Check: you see the name, depth, counts, how it sounds, sample names per rule set, and the check's report in plain words. Import opens its page.
- [ ] **A broken file.** Paste one with a broken rule: the report says what must be fixed, Import stays disabled, and "Copy note" copies the note to paste back to the assistant.
- [ ] **The language's page.** About (facts, connections, timeline) opens by default. The other tabs, each in two columns (mockups Language A and Lexicon A):
  - **Language:** how it sounds, depth and "Sounds like", the sound inventory, syllable notes, related languages and grammar notes; beside them, a card per name rule set with sample names and editable patterns;
  - **Lexicon:** the dictionary (words, meanings as chips you add, edit and remove, parts, and a "name" tag on words the world uses as names; search) beside the phrases by category, with word-by-word breakdowns.

  Check it at a full-size window as well as a small one: nothing should be stretched far apart.
- [ ] **Sorau's Languages section.** On a place, "+ Add" rows such as Sorauan *official* and Moscavian *spoken* 25%. They show with a role chip and a share bar.
- [ ] **Thornfield inheriting.** A place filed in Sorau, with no rows of its own, shows "From Free Provinces of Sorau: …" with **Set its own**, which copies them in as its own rows.
- [ ] **A character's languages.** On a character, add Sorauan *spoken*, *native*. A character with no rows takes the spoken and official languages of the places it's filed in, never an order's liturgical one.
- [ ] **"Tsardom of" → Make a name.** In a New place box, type "Tsardom of ", right-click, and pick **Make a name…**. Pick a language (the ones spoken on the page come first, with a pin). Four names come with one-line definitions; click one. It's inserted and saved to the language's Dictionary. **Reroll** gives four more.
- [ ] **Add Moscavia as a word.** Type "Tsardom of Moscavia", select "Moscavia", right-click, and pick **Add "Moscavia" to a language…**. A definition is suggested; edit it and Save. It's in the Dictionary.
- [ ] **Reroll this part.** Select "Moscavia" again, right-click, and pick **Reroll this part…**. A picked name replaces only the selection.
- [ ] **Name it in…** On Free Provinces of Sorau, Other names → **Name it in… → Moscavian**. Words the language knows are translated, the rest are rolled and picked, and "of" is left out. **Keep it** adds the name as an other name marked with its language, and its new words to the Dictionary.
- [ ] **A new version keeps used words.** On a language's Language tab, **Import a new version** with a file that drops or redefines a word some entry is named with. The before/after says it's "kept because the world uses it", and after importing the word is still there with its old meaning.
- [ ] **The scene's message box.** In a world scene, right-click in the message box: there's **Make a name…** and **Make a phrase…** (no Add reference). The player character's languages come first, then the scene place's.

## Results

The owner can't import a language of their own until languages can be made
(plan 3b), so the walk splits: **the owner** judges whether it looks and
feels right, and **Playwright** proves each step does what it should. Every
step below has an e2e test that drives the real app (no model; fixed
replies), and all pass.

| Step | Proven by (tests/e2e/worlds/) |
|---|---|
| Import by pasting, its page opens | `test_languages_page.py::test_import_pasted_language_and_see_its_page` |
| A broken file: report, Import disabled, Copy note | `test_languages_page.py::test_blocking_problem_disables_import` |
| The page's tabs; meanings, chips, "name" tag | `test_languages_page.py` (page, phrases, `test_a_word_shows_its_meanings_and_what_it_names`) |
| Sorau's rows, Thornfield inheriting, Set its own | `test_languages_section.py::test_add_rows_then_inherit_and_set_its_own` |
| A character's own rows (fluency) | `test_languages_section.py::test_character_fluency` |
| A character takes its place's spoken and official languages, never a liturgical one | `test_languages_section.py::test_a_character_takes_its_places_everyday_languages` |
| "Tsardom of" → Make a name, saved to the Lexicon | `test_language_naming.py::test_make_a_name_inserts_and_saves_word` |
| Add Moscavia as a word, with a suggested meaning or none | `test_language_naming.py::test_add_selected_word_with_definition`, `test_add_a_word_with_no_meaning` |
| Reroll this part | `test_language_naming.py::test_reroll_this_part` |
| Name it in…, or type it yourself | `test_language_naming.py::test_name_it_in_other_language`, `test_name_it_in_lets_the_owner_type_the_name` |
| A new version keeps used words, with their meaning | `test_languages_page.py::test_new_version_shows_kept_used_words` |
| The scene's message box: Make a name (speaker's languages first, then the place's), Make a phrase, no Add reference | `test_scene_languages.py` |

The owner's look-and-feel verdicts:
- The language page: rebuilt after a design phase; mockups Language A + Lexicon A approved.
- Make a name in free text: worked; led to short meanings, several per word, and the "name" tag (approved).
