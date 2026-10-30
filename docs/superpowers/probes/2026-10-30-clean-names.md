# Probe 4: cleaning names in drafts (2026-10-30)

**Why.** Part 4 of the languages design (`docs/superpowers/specs/2026-10-30-fantasymate-languages-4-design.md`) cleans real names, AI stock names and stock titles out of drafts. Before planning 4a it needed four answers:
1. how many real names reach a draft's fact text today;
2. whether the model can flag names built from real words, and how the fit check compares;
3. whether a swapped sentence still reads right;
4. whether the draft's languages can be found from the owner's words.

**The setup.**
- **Model:** Skyfall-31B-v4.2-i1-Q4_K_M (koboldcpp), one call at a time. The owner said go (2026-10-30).
- **Harness:** `scripts/dev/probe_clean_names.py`.
- **Labels:** `raw/2026-10-30-clean-names-labels.json`, committed before any call (49b04f7c). It holds 41 names: 26 real (famous places, real words used as names, real given names and surnames) and 15 invented, 12 of them rolled from Moscavian. Plus 10 swap sentences and 10 language prompts.
- **Raw output:** `raw/2026-10-30-clean-names.json`, run `skyfall`.
- **Language:** the saved Moscavian (`.superpowers/saved/2026-10-29-moscavian/`, 251 words).
- Composed rules on Claude Code (probe 4's stage 5) wait for 4b.

## Results

### 1. Today's drafts (probe 2's five Moscavia prompts, three times each)

- All 15 drafts were made with no errors, at 36 s each on average (29–49 s). They proposed 10 to 17 names each.
- **Real names are everywhere.** Every draft but one had some:
  - **real places:** the Volga, the Don, the Moskva River, the Dnepr, the Kolyma, Kholmogory, Velikiy Ustyug, the White Sea, Volhynia, Sokolniki, "Solnaya Rus";
  - **thin disguises of Moscow:** Moskovgrad, the Tsardom of Moskov, Moskovia;
  - **real given names and surnames:** Dmitri (in 7 drafts), Yelena, Sofya, Oleg, Vladimir, Konstantin, Aleksei, Svyatoslav, Voronov (4 drafts), Solovyev, Khmelnytskyi;
  - **Russian words used as names:** Velikiy Solnechny ("great sunny"), the River Kholodnaya ("cold"), Snegovoy Sobor ("snow cathedral"), Zimnyaya Kniga ("winter book"), Ledyanaya Oprichnina ("ice guard"), Velikograd ("great city"), Novgrad.
  
  The noble-house drafts were the worst: up to seven real names in one draft (Grand Prince Vladimir III, the Volga, the Don, the Moskva River…).
- **AI stock names and titles recur:**
  - Frostfang or Frostspine Mountains (4 drafts);
  - "Free Cities of the … Coast/March" (4);
  - the Shivering Coast or Sea (3);
  - the Festival of the Longest Night (2);
  - the Court of Owls (2);
  - the Night Watch, the Council of Elders, Aldric.
- **Names in fact text that the draft's names list leaves out** were mostly sentence starts and months ("In", "The", "May"). A few were real:
  - Lunnaya Strela ("moon arrow");
  - Serebryanye ("silver");
  - Sokolniki (a Moscow district);
  - Velikiy Solovey ("great nightingale");
  - "Volga's".
  
  So scanning the text matters, and it has to handle possessives and ignore sentence starts.
- **The real-words list** (probe 1's 251 words) caught most people's names but missed most of the vocabulary names above.

### 2. Flagging (41 labelled names)

| | Real names caught | Real names missed | False flags |
|---|---|---|---|
| probe 2's prompt (V1) | 12 of 26 (46%) | all 14 real-word names and the surnames | Aldric Moonshadow |
| **V2** (names real words, real given names and surnames) | **25 of 26 (96%)** | Koldunya ("witch"; it said "invented, Slavic flavour") | Aldric Moonshadow, as a stock title |
| the fit check against Moscavian (no model) | 17 of 26 | Tver, Snegovaya Krepost, Velikograd, Strazh, Snezhana, Yelena, Irina, Voronov, Solovyov | Aldric Moonshadow (doesn't sound Moscavian) |

- **V2 gives a reason the owner can read:** "Russian 'great city'", "Russian surname meaning 'of the crow'".
- **The fit check misses names that share Moscavian's endings** (-grad, -ov, -a), which are exactly the leaky ones. As a trigger it would be weak, but it's fine for suspect marks. None of the 12 rolled Moscavian names was flagged by anything.
- **Aldric Moonshadow** isn't real, but V2 called it a stock title, which is arguably right: it's an AI cliché.

### 3. Swapping a name in a sentence (10 sentences)

- **The model's rewrite was identical to plain substitution in all 10.** "Fur caravans trade south with Lezhograd and the salt marshes beyond." "Barges carry grain down the Tikhyedov to the southern markets." The sentences read fine.
- **9 of 10 picks were among the candidates.** One (Troegegrad) was a variant the model made up.
- **One pick didn't suit the person:** "Prince Vshytsisha Shyasina" is a woman's name for a prince. Moscavian's people rule mixes men's and women's names, so a pick has to match the person. That's the forms question 4b answers.

### 4. Languages from the owner's words (10 prompts)

| | Right languages |
|---|---|
| the model | 7 of 10 |
| **name match, no model** (the language's name or its first five letters) | **10 of 10** |

- **The model invents languages** for prompts that name none: "a mountain village of herders" got Moscavian, Brelovan and Kostrevin. It also added Brelovan and Sorauan to "the Moscavian capital".
- **Where the languages were right, its roles were mostly sensible:** liturgical Brelovan, trade for the merchant guild, 65/35 for the border town. But it said "spoken" where "official" fits a country, and "ceremonial" where the prompt said "a mark of learning" (scholarly).

## Findings

1. **The leak is real and broad:** real places, thin disguises of Moscow, real given names and surnames, and Russian words used as names, plus a steady set of AI stock titles. Cleaning is worth building.
2. **The model's flag with the V2 prompt is the main detector** (96%, with readable reasons). Lists are still needed for the AI clichés and stock titles, which the model doesn't treat as problems. The fit check catches some leaky names but misses the ones sharing the language's endings. It fits the owner's "suspect" mark, not replacing.
3. **Swapping is plain substitution.** The model only needs to pick among candidates. The app should check the pick is a candidate (or take the first) and substitute itself. A rewrite call isn't needed.
4. **Finding the languages is a name match; the model only gives roles and shares** for the languages the match found. It must never add a language the words don't name.
5. **Text scanning** needs the flag call or a filter, because capitalised runs in facts are mostly sentence starts and months.
6. **A person's pick must suit the person** (man or woman). In 4a the model's pick should be told the person's sex from the facts; 4b's forms make this structural.
7. **One call per draft is enough for flagging:** a draft has 10–17 names plus a few from the text, within one V2 batch.

**The owner's verdict:** *(pending)*
