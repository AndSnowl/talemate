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
- [x] make the Moscavia starter ("Tsardom of Moscavia, a cold northern tsardom of owl-folk");
- [x] make a noble-house draft;
- [x] run **Add facts** on the noble house.

For each, record:
- what was replaced;
- what was marked suspect;
- what slipped through;
- how much time cleaning added (probe 4: a draft takes about 36 s);
- whether the swapped sentences read right.

## Results

The runs used Skyfall-31B on koboldcpp, in an isolated test app with the saved Moscavian (251 words). The owner said go (2026-10-30). Raw records: `real-runs-1.json` and `real-runs.json` in the plan's workspace.

### Round 1: five problems found

- **The starter (52 s, 12 marks).**
  - The flag call failed: it had about 40 names, and `analyze`'s 500-token reply was cut short.
  - So only the lists, real words and fit worked. The Baltic, the Swedish Varangians, the Khazar Khanate and the Volkhova were only marked or missed.
  - "White Sea" was found as "White", and "the Church of the White Light" was swapped too.
- **The noble house (60 s).** "Tsar" was replaced everywhere as a real word, which made a junk "Tsemasha" stub. "Grand Palace of Velikigrad" lost its frame.
- **Add facts (42 s).** The epithet "The Watchful" was rewritten as a stock title into "The Tsozyegorsk Watch", which also made a place stub.

**Fixed (31661968), each with a test:**
- names are flagged 14 at a time, with a longer reply;
- title words and numerals are never judged;
- buildings and institutions frame a name;
- a name found without its kind word is swapped in its whole written form;
- a stock-title label on an epithet, or on a name the reply didn't list, only marks it.

### Round 2, on the fixed code

| Draft | Time | Replaced | Suspect |
|---|---|---|---|
| The starter | 50 s | 8: Retka River, Sokolnaya Duma ("Duma" kept), Solnitsa ("little sun"), Rus, White Sea → Vlamograd Sea (whole form), Ural, Volga, and the stock title "Night Watch" | 4: Velikoretsk, Code of the Snow Owl, Chronicle of Feathers and Frost, Great Owl |
| The noble house | 74 s | 4: Moroz → Spirya, Kasyan → Zhymovik ("Lord" kept), House of Kolyada → House of Lyepiinsk (frame kept), Iron | 4: Vostrikgrad, Wardens of the Northern Reaches, Vostriks, Festival of the Frosting Light |
| Add facts | 72 s | 2: Morozhiy Kamin, and Aldric (an AI cliché) → Yekavik ("Grand Dirin" kept) | 6, partly fragments: "Vostrik Accord of", "Battle of the Sledden", "Ashen Guards" |

- **No flag call failed.** The Languages section was found from the owner's words each time (Moscavian, official).
- **Cleaning adds about 15–35 s to a draft.** A draft alone took about 36 s in probe 4.
- **The swapped sentences read naturally:** "trade with … the Blikhograd trade route", "the human kingdom of Moshizov".

**Still weak, for the owner's judgement:**
1. **A common English word in an epithet can be flagged as real and replaced.** "Iron" became "Zdakayov", which also made a place stub. The model's V2 prompt treats "English word" as real.
2. **A stock title is rewritten without its sentence,** so its meaning can drift. The "Night Watch" curfew became the "Ashen Guard of Piboinsk".
3. **Some suspect marks are fragments of longer names** ("Vostrik Accord of", from "Vostrik Accord of 971"). They're harmless but noisy.
4. **Names the model judged fine still get through:** Olekh (Oleg), Velikoretsk (marked suspect), and Velva.

**The owner's verdict:** *(pending)*

## Revised (2026-11-01): mark, then Name it…

The owner's verdict on the first build: the checking wasn't accurate enough, and swapping lost meaning ("Court of Lakes" → "Court of Kinchvovy Brezhi"). So drafts now only mark, and naming is the owner's, with **Name it…**.
- **Spec:** part 4, section "4a revised".
- **Plan:** `docs/superpowers/plans/2026-11-01-fantasymate-languages-4a-revised-name-it.md`.
- **Mockup:** `docs/superpowers/mockups/2026-11-01-languages-4a-name-it.html`.

| Step | What to look at | Proven by |
|---|---|---|
| **A draft arrives unchanged, with marks.** Real names, clichés, stock titles and names that don't fit the language get a wavy underline. A new stub keeps its stub look, under the mark. Names on the lists are only marked, never replaced. | Are the right names marked, and nothing rewritten? | `tests/languages/test_clean_mark.py`; `tests/worldplay/test_create_cleaning.py`; e2e `test_clean_names.py::test_a_draft_arrives_unchanged_with_flags`, `test_a_flagged_new_stub_keeps_its_stub_look_and_one_card` |
| **The card:** "Flagged: why", with **Name it…**, **Keep it** and **Never flag it in this world**. | Is it clear what each does? | `test_keeping_a_flagged_stub_keeps_the_stub`, `test_never_flag_adds_to_the_keep_list`, `test_new_stubs_say_why_a_name_is_flagged` |
| **Name it…** (mockup frames 2 and 3): the language, its rule and one pattern; ten names with a fast **Reroll**; **From a meaning** shows what each candidate is built from. Picking puts the name everywhere the draft writes it, and saves new words to the language. | Are the rolls quick, and is it clear which generator you're using? | `tests/languages/test_naming_panel.py`, `tests/server/test_worlds_name_it.py`; e2e `test_name_it.py` (8 tests) |
| **Name it… on any words:** part of a name ("Greywash" in "Duchies of the Greywash Coast"), a stub's page (the old name is forgotten), or an entry's page (the old name stays as another name). Right-click's Make a name and Reroll this part are replaced by it; the scene box keeps Make a name. | Does renaming land everywhere? | `test_name_it_on_part_of_a_name`, `test_name_it_on_an_entry_renames_it_and_keeps_the_old_name`, `test_name_it_on_a_stub_forgets_the_old_name`, `test_the_reference_menu_offers_name_it_not_make_a_name`; `tests/worldplay/test_repoint*.py` (rename_everywhere) |
| **The narrator rule:** with a language in the world, the create and Add facts prompts say titles and descriptions stay English and only proper names may sound foreign. | Do you still get "Court of Lakes", not a foreign title? | `test_the_create_prompt_carries_the_narrator_rule_with_a_language`, `test_add_facts_prompt_carries_it_too` |
| **Language entries get facts:** importing a language writes "X is a language of this world…", so other entries' "For other pages" can target it. The language skill makes men's and women's name rules by default. | — | `tests/languages/test_importer.py::test_importing_a_language_writes_a_fact_about_it` |
| **Your bugs.** A race draft whose reply lists no names offers its facts' unknown names as unticked New stubs rows ("the AI didn't list it: tick to make a stub"), and the race prompt asks for the places its facts name. A picked language shows at once, with a spinner, and Add waits. A stub's draft shows the language it inherits ("From Tsarvenya: …"), so you aren't asked to pick one. "Duchies of the Greywash Coast" judges only "Greywash". | Does the Eared Owl-folk draft offer Velmora and the rest now? | `test_create.py::test_names_the_reply_left_out_come_as_unticked_rows`, `test_accept_makes_stubs_only_for_ticked_rows`; e2e `test_names_the_ai_did_not_list_come_unticked`, `test_a_picked_language_shows_at_once`, `test_adding_twice_is_not_possible_while_saving`, `test_a_stub_draft_shows_the_language_it_inherits`; `test_clean_find.py::test_a_plural_frame_name_judges_only_its_name` |

### Real runs on the revised build (2026-11-01)

These ran on Skyfall-31B on koboldcpp, with the owner's go-ahead, in a fresh test app holding a copy of the owner's Test world (language Varsenyk, Tsarvenyan Owl-folk). The owner's own app was left alone. Raw records are `real-runs.json`, `real-runs.log` and the screenshots in the plan's workspace.

| Run | Time | What happened |
|---|---|---|
| **Race draft** ("Horned owl-folk … trading with the countries there") | 22 s | 6 facts, all body and instinct. The model named no places, so there was nothing to stub or offer, and the unlisted-names fix wasn't exercised. No marks. |
| **Lake draft** ("a great lake in Otsyenya, with fishing villages on its shores") | 36 s | "Lake Otsyeno", 12 facts, 3 new stubs listed and ticked: Vashkovo, Grethik Range, Frostspine Peaks. No language was in reach: the prompt names none, and a new place isn't filed yet. So nothing was marked. "Moskovian frontier" went unmarked. |
| **Name it on the lake** | — | Rule "Places", ten names (Zhyadyensk, Milyensk, Tremrenya…). **Reroll took 0.11 s.** One pattern (`CVCV[rsk|nsk]`) gave ten -rsk/-nsk names at once. |
| **From a meaning** ("lakeland") | 13 s | One candidate: **Khvodakhan**, "khvodakhan “lakeland” (new word, saved if you pick it)". Picking it renamed the lake, and "Lake Otsyeno" stayed as another name. |
| **Name it on a stub** (The Hooting Bazaar) | — | The panel said "“The Hooting Bazaar” is forgotten". Picking renamed it with no other name kept. |

What the runs show:
- Name it is fast and clear about which rule it's using.
- From a meaning gave one candidate this time; the plan asks for up to two.
- A draft with no language in reach marks only list hits. Pick a language, or file the draft somewhere that has one.
