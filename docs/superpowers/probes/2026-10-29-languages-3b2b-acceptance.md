# Languages 3b-2b (changing a language): the owner's acceptance checklist

Date: 2026-10-29. Branch: `feature/languages-3b2b`. Plan: `docs/superpowers/plans/2026-10-29-fantasymate-languages-3b2b-changing.md`. Spec: `docs/superpowers/specs/2026-10-29-fantasymate-languages-3b2-design.md`, section 2.

As before, there are two checks. **The owner** judges whether each step looks and feels right. **The tests** prove it works: they drive the real app with a fake Claude Code, whose `change` mode edits the language file it's given.

| Step | What to look at | Proven by |
|---|---|---|
| **Change it…** in a language page's header opens a panel under it with:<br>• the request;<br>• **Fit it to**: suggested entries, ticked, each with why ("speaks it (official)", "filed in Sorau", 'its facts use "dov"');<br>• the route;<br>• Change it, Copy the brief and Discard. | Are the suggestions useful? | `tests/e2e/worlds/test_language_change.py`: `test_fit_it_to_suggests_speakers`; `tests/languages/test_related.py` |
| **The review:** what changed by part (words, phrases, grammar, name rules, how it sounds, before and after), then **Accept the change** or **Drop it**. Drop keeps the request. | Is it clear what changed? | `test_change_it_runs_and_the_review_shows_what_changed`, `test_drop_keeps_the_request`; `tests/languages/test_changes.py` |
| **Your edits are kept.** While a change runs, edit the same word: the review says "Kept your edit", and your version stays. | — | `test_the_owners_edit_during_a_change_is_kept`; `test_the_owners_edit_is_kept_where_both_changed` |
| **Used words are kept:** a word naming an entry keeps its meanings ("Kept as they are"). | — | `test_used_words_still_win_over_a_change` |
| **Still to fill in** with **Fill in next: words / phrases / grammar**. On the Copy the brief route it copies that step's brief. It isn't there when nothing is missing. | — | `test_fill_in_next_offers_the_first_gap`, `test_fill_in_next_copies_its_brief_on_the_brief_route`, `test_no_fill_button_when_nothing_is_missing` |
| **Change…** on a grammar chapter opens the panel with "Change the Verbs section: " ready to finish. | — | `test_a_grammar_chapters_change_opens_the_panel_aimed_at_it` |
| **From an entry:** **Change a language to fit this…** after Add fact, and in the right-click menu. The panel opens on the entry with the language spoken there picked and the entry ticked. The review comes back there. | Does it feel natural while writing an entry? | `test_from_an_entry_the_panel_opens_in_place`, `test_the_right_click_menu_offers_it`, `test_the_review_comes_back_on_the_entry` |
| **Safe edges:**<br>• a change for a deleted language is refused plainly;<br>• Accept twice writes once;<br>• one job at a time, with a note. | — | `tests/server/test_worlds_languages.py`, `tests/server/test_worlds_language_make.py` |

## Real runs, with the owner's go-ahead

Use the saved Moscavian (`.superpowers/saved/2026-10-29-moscavian/moscavian.language.json`), imported into a fresh test world with an Owl Synod religion entry.

- [x] From the Owl Synod entry: "redo the blessings and farewells around the Owl Synod".
- [x] From Moscavian's page: "they're traders: add words for trade and the river market".

Record what changed, what was kept, and how long each took.

## Results

**The real runs: Claude Code, Opus (2026-10-29).** They ran through the panel in a fresh test app. Moscavian came from the saved 3b-2a file, with the Tsardom of Moscavia speaking it (official) and an Owl Synod lore entry with three belief facts.

1. **From the Owl Synod entry.** Request: "Redo the blessings and the farewells around the Owl Synod and the owl's watchful eye; add words for the Synod's ranks and rites".
   - The language picked itself, and the review came back on the entry after **170 s**.
   - New words (17): *sovyar* (owl), *sovyarsobrav*, *sovyarsvyatar*, *krylar*, *operyenka*, …
   - Phrases: 6 new, 6 removed (the old blessings and farewells redone).
   - A new grammar section, "The Owl Synod's ranks and rites".
   - Accepted.
   - Blessings: *Glazov dye sovyar pon tyev.* "The owl's eye on you."; *Sovyarot glyedi tyev vu nochav.* "May the owl watch over you in the night."
   - Farewells: *Tishavi kryletsy!* "Silent wings!"; *Sovyarot bryemi tyev.* "May the owl carry you."
2. **From Moscavian's page.** Request: "They're traders as much as warriors: add words for trade, money, debt and the river market, and redo the curses and oaths around debts and broken bargains".
   - The review came after **225 s**.
   - New words (34): *zvyenta*, *kolyesh* (coin), *trezhar* (bargain-breaker), *ryechavslodar*, …
   - Phrases: 8 new, 6 removed.
   - A new grammar section, "Trade, debts and bargains".
   - Accepted.
   - Curses: *Kolyeshy dye tyev — pyeplov!* "Your coins are ash!"; *Rukva dye tyev gnilava, trezhar!* "Rot to your hand, bargain-breaker!"
   - Oaths: *Vyerzhav dye yaz — kruvya dye yaz.* "My debt is my blood."; *Pon rukva ye solyar.* "By hand and salt."

After both runs, Moscavian has 302 words and four unusual grammar sections. The real runs left no scratch folders behind.

**Found:**
- **The review shows changed phrases as counts** ("6 new, 6 removed") instead of before and after, side by side, as the approved mockup did.
- **My server tests left scratch folders** in the system temp folder. That's fixed (d0676d4e). About 67 old folders from earlier test runs remain in `/tmp` (`fm-check-*`, `fm-language-*`); removing them was refused as a shared `/tmp` sweep, so they're the owner's to remove.

**The owner's verdict:** *(pending: the owner will look in the test app, including where the entry panel sits)*
