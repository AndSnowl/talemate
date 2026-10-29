# Languages 3b-2a (fuller languages, the Grammar tab): the owner's acceptance checklist

Date: 2026-10-29. Branch: `feature/languages-3b2a`. Plan: `docs/superpowers/plans/2026-10-29-fantasymate-languages-3b2a-fuller.md`. Spec: `docs/superpowers/specs/2026-10-29-fantasymate-languages-3b2-design.md`.

As in 3b-1, there are two checks. **The owner** judges whether each step looks and feels right. **The tests** prove it works: they drive the real app with a fake Claude Code and fixed replies.

| Step | What to look at | Proven by |
|---|---|---|
| **The Grammar tab** (mockup A). A language page has About · Language · **Grammar** · Lexicon. Topics are listed on the left, with an "Unusual" group. Cards show text, real tables, and examples word over meaning. A card's text can be edited in place. | Is it readable? Do the tables and examples work as the "diagram-like" part? | `tests/e2e/worlds/test_language_grammar.py` |
| **Old languages.** A language made before this round shows its grammar paragraph as one "Grammar" card, still editable. | — | `test_an_old_text_grammar_shows_as_one_card_and_can_be_edited`; `tests/languages/test_grammar_sections.py` |
| **Make it with.** The dialog shows Claude Code (with a model box), the agent's model (marked API tokens) or Copy the brief, for that run only. The Language agent's setting is unchanged. | — | `test_the_dialog_offers_route_model_and_size`, `test_a_chosen_route_is_used_for_the_run`; `tests/server/test_worlds_language_make.py` |
| **How much.** Full: everything in one go, or Quick, then fill in. Full is the default on Claude Code; Quick on the agent's model. A note says what each means and costs. | Is the note clear? | `test_choosing_the_agents_model_switches_to_quick`, `test_the_copied_brief_follows_how_much` |
| **The brief asks for a full language:** every core meaning (the structural words and the everyday list), at least 3 phrases in each of nine categories, all eleven grammar topics with tables, and name rules for characters, places, items, groups and a demonym. A Quick brief keeps to a core. | — | `tests/languages/test_brief.py` |
| **Still to fill in** in the review: words missing out of 229, phrase categories missing, grammar topics not written. It's information, never a problem, and never sends the language back. | — | `test_the_review_shows_still_to_fill_in`; `tests/languages/test_completeness.py` |

## Real run, with the owner's go-ahead

- [x] **Full on Opus via Claude Code** (2026-10-29, owner's go-ahead; results below) (on the owner's subscription; probably 10–15 minutes). Make "a unique but recognizably Russian language for the Tsardom of Moscavia", taking the Tsardom into account. Record:
  - words, and Still to fill in;
  - grammar sections and tables;
  - phrases per category;
  - the time it took.

  Save the test app's `worlds/` and `config.yaml` before any restart.

## Results

**The real run: Full, Opus, Claude Code (2026-10-29).** It was driven through the dialog in a fresh test app. Request: "a unique but recognizably Russian language for the Tsardom of Moscavia", taking the Tsardom into account (two facts).
- **Time:** the review appeared after 440 s. Both scratch folders were removed afterwards, and no process was left running.
- **Moscavian** came back with 251 words and 27 phrases: 3 in each of the nine categories.
  - Rule sets: words, characters, places, items, groups, and people of a place.
  - Sound groups: five, including consonant clusters and endings.
- **Still to fill in:** nothing. 0 of 229 core meanings missing, no phrase categories, no grammar topics.
- **Grammar:** 13 sections, the 11 standard topics plus two unusual ones ("The joined 'the'", "Leaving out 'is'"), with 14 tables and 24 examples. It includes:
  - conjugation tables for to speak, to be and to have;
  - noun endings by gender;
  - a pronoun grid;
  - counting to 100;
  - word-building endings;
  - name structure (given, father's, family);
  - "ty" vs "vy".
- **The check:** 94% of words fit the rules (16 flagged, a warning); no real-word hits.
- **Sample names:**
  - characters: Zmesaslan Tvobin, Mogivik Chizhin, Zhetsyuyar Strachov;
  - places: Khvonograd, Tvyovigrad, Vunisov;
  - groups: Sobrav Bechyav, Pryusichi.
- **Found:**
  - **Real Russian roots slip through.** *glazov* (eye; Russian *glaz*), *bolsh*, *dolgav*, *muzhets*, *kholdov*, *znavati*, *stoyti*. The check's Russian list has only about 250 words and misses common roots. This matters given the owner's "no real words" rule.
  - A word-rule sample came out as "Glory", an English word, by chance.
  - Claude Code wrote a helper `build.py` along the way. It can't run it (the boundary held); harmless.
- Screenshots (in the plan workspace): `real-dialog.png`, `real-review.png`, `real-language.png`, `real-grammar.png`, `real-lexicon.png`.
- **The owner's verdict:** *(pending)*
