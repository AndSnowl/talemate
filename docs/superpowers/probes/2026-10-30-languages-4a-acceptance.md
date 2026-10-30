# Languages 4a (clean names in drafts): the owner's acceptance checklist

Date: 2026-10-30.
- **Branch:** `feature/languages-4a`.
- **Plan:** `docs/superpowers/plans/2026-10-30-fantasymate-languages-4a-clean-names.md`.
- **Spec:** `docs/superpowers/specs/2026-10-30-fantasymate-languages-4-design.md`, part 4a.
- **Probe:** `docs/superpowers/probes/2026-10-30-clean-names.md`.

As before, there are two checks. **The owner** judges whether each step looks and feels right. **The tests** prove it works: the browser tests drive the real app with fixed model replies (`TALEMATE_TEST_FIXED_PREVIEW`, `…_FACTS`, `…_CLEAN`).

| Step | What to look at | Proven by |
|---|---|---|
| **A draft arrives clean.** Where a language is in reach, real names, AI clichés and stock titles in the draft's name, facts, summary and "For other pages" facts are already replaced by names rolled from it. Each is marked with a dotted underline. | Do the swapped sentences read right? | `tests/worldplay/test_create_cleaning.py`; `tests/languages/test_clean_find.py`, `test_clean_replace.py`; e2e `test_clean_names.py::test_a_replaced_name_shows_its_card` |
| **The card.** It shows "<new> · was <old>", why, and the meaning, with **Reroll**, **Keep <old> here** and **Never replace <old> in this world**. Reroll and keep change every occurrence. | Is the card clear? | `test_reroll_changes_every_occurrence`, `test_keep_here_puts_the_old_name_back`, `test_never_replace_adds_to_the_keep_list` |
| **Suspect names** (new since the mockup) have a wavy underline. The card says why ("Doesn't sound like Moscavian"), with **Replace it**, **Keep it** and **Never flag it in this world**. | Does the second mark read as "check this", not as an error? | `test_a_suspect_name_can_be_replaced_or_kept`, `test_keeping_a_suspect_name_drops_its_mark` |
| **The draft's Languages**, found from your words ("Tsardom of Moscavia" → Moscavian, official, "from your words"). Changing them cleans the draft again. With none, **Pick a language for this draft**, and real names are only marked. | Right languages, right roles? | `test_clean_languages.py`; `test_the_draft_shows_its_language_from_your_words`, `test_no_language_offers_pick_a_language`; `tests/server/test_worlds_cleaning.py` |
| **New stubs** list each replacement with "replaced Novgorod". | — | `test_a_replaced_name_shows_its_card` |
| **Accept** forgets the old names, writes the Languages rows, and saves each new name to its language as a word (with its meaning). The description is written after accept, not in the draft. | Is the Lexicon growing the way you want? | `test_accept_keeps_only_the_new_names`; `test_create_cleaning.py` (accept tests) |
| **Add facts, Add event and group + Add** are cleaned the same way, with the same card. | — | `test_facts_cleaning.py`, `test_groups_cleaning.py`; `test_add_facts_shows_marks_and_the_card` |
| **The Names page** (Settings → Names, mockup 2A): what gets replaced (Real names, AI clichés, Stock titles) beside what's kept. All-worlds rows have **Turn off here** and **Remove everywhere** (behind a confirm); this world's rows have **Make it global** and **Remove**. | Is it the central place you wanted? | `tests/e2e/worlds/test_names_settings.py`; `tests/languages/test_name_lists.py` |

## Real runs, with the owner's go-ahead (koboldcpp)

In a fresh test app, with the saved Moscavian imported:
- [ ] make the Moscavia starter ("Tsardom of Moscavia, a cold northern tsardom of owl-folk");
- [ ] make a noble-house draft;
- [ ] run **Add facts** on the noble house.

For each, record:
- what was replaced;
- what was marked suspect;
- what slipped through;
- how much time cleaning added (probe 4: a draft takes about 36 s);
- whether the swapped sentences read right.

## Results

*(pending the real runs)*

**The owner's verdict:** *(pending)*
