# Probe: catching bad names in drafts (2026-10-28)

**Why.** This is probe 2 of the languages design (`docs/superpowers/specs/2026-10-28-fantasymate-languages-design.md`, part 2). Part 4 wants drafts to flag real-world names and stock titles, then regenerate them from the language in reach. The questions:
- how often do real names leak into drafts today?
- can the local model flag them?
- can it rewrite a stock title around a slot for the language's name?

**The setup.**
- **Model:** Skyfall-31B-v4.2-i1-Q4_K_M (koboldcpp), one call at a time. The owner approved this plan's probes in advance.
- **Harness:** `scripts/dev/probe_name_flags.py`.
- **Labels:** `raw/2026-10-28-name-flags-labels.json`, committed before any call (73900503). It has 60 names, each with a one-line context: 20 real, 15 stock titles and 25 ok. The ok names include the AI clichés Maren, Elara, Thornwood, Kael and Lyra, which are the cliché list's job, not this probe's.
- **Raw output:** `raw/2026-10-28-name-flags.json`, run `skyfall`.
- **Stages:**
  1. *Baseline:* 5 create prompts, twice each, through the app's own `create.preview_thing`. Every proposed name was checked against probe 1's list of 251 real Russian words and names.
  2. *Flag:* the 60 names, in 4 batches, through the chat endpoint.
  3. *Rewrite:* the 15 stock titles. The first pass used `REWRITE_SYSTEM`; the second used `REWRITE_SYSTEM_V2`, which is shorter, has examples and limits the length.

## Results

### Baseline: what a draft proposes today

The 10 drafts proposed 121 names, with no errors. 17 of them hit the real-word list:

| Prompt | Real-word hits |
|---|---|
| Tsardom of Moscavia | Dmitr the Ironwroth, Aleksandr III · Yelena Vostrik, Sokoly |
| its capital | Tsar Irina I · Tsar Oshen III, Tsar Aldric the Watcher |
| its neighbours | Yelena the Watchful · Voron I |
| a noble house | House of Voronov, Aldric Voronov · House of Voronov, Snegovaya Krepost, Tsar Dmitri II, Prince Aleksei Voronov, Yelena Voronova |
| its great river | — · Tsar Aldric Moonshadow |

Some hits come from a common word in an invented name ("Tsar" in "Tsar Aldric the Watcher"). The list missed more real Russian *vocabulary* than it caught:
- Kholodnaya and Kholodnoye ("cold");
- Snegovaya Krepost ("snowy fortress");
- Velikograd, Novgrad and Vostokgrad ("great/new/east city");
- Koldunya ("witch"), Strazh ("guard"), Zakonnik ("lawman"), Morozsk ("frost") and Snezhana (a real given name, "snowy");
- real rulers' names that the list didn't cover: Volodymyr II and Ihor I;
- real surnames: Solovyov and Chernyavsky.

The leak the owner sees is mostly **real Russian words used as names**, plus real given names and surnames (Aleksandr, Dmitri, Yelena, Voronov). Real places and rivers (Moscow, the Volga) didn't appear in these 10 drafts.

### Flagging

| Class | Precision | Recall |
|---|---|---|
| real | 0.95 | 1.00 |
| stock-title | 1.00 | 0.67 |

- **Real names:** all 20 were caught. The one false flag was **Moscavia**: "a real historical region (Muscovy/Moscow), thinly disguised". That's arguably right.
- **Missed stock titles:** the Shadowlands, the Iron Council, the Eastern Wastes, the Order of the Silver Flame (each judged "specific" because its context line gave it a role), and the Merchant Guild (left out of the reply).
- **The AI clichés passed as ok** (Maren: "works as an innkeeper name"). As expected, the model doesn't see them as a problem, so the cliché list is needed.

### Rewriting stock titles

**First prompt:** 1 of 15 kept the `{name}` slot. The rest were long, with subtitles, and invented their own name in braces, for example "The Peltspeaker Accords: Fur and Sovereignty Along the Sable Line", or "{Valdremor's} Icebound Throne -- The Spring Dispatches of the Northern Reach".

**Second prompt** (examples, at most six words, "write the literal placeholder"): 12 of 15 kept `{name}`, filled here from a small test language. The other 3 wrote `{Name}`, which the app can accept too.

| Original | Rewritten (filled) |
|---|---|
| Free Cities of the Southern Realms | {Name}'s Fur Market |
| the Shadowlands | {Name}'s Blackreach |
| Kingdom of the North | Spring Envoys of Vadiov |
| the Iron Council | the Iron Bench of Binsaa |
| the Eastern Wastes | Sokeka Dustfields |
| the Order of the Silver Flame | the Silver Flame of Lilneka |
| the Southern Kingdoms | {Name} Succession Feud |
| the Frozen North | Tedoin Fangs Descend |
| the Dark Forest | the Kobluka Pinewood |
| the Merchant Guild | the Salt Tax of Nivaka |
| the Old Kingdom | Tavkain's Ruined Throne |
| the Western Isles | Nesiov Shiver Peaks |
| the High Council | the Lantern Bench of Seso (copies the prompt's example) |
| the Borderlands | Dodsoin Borderlands |
| the Crimson Brotherhood | Kuso Swordmongers |

Some rewrites change what the thing is, which the prompt forbids. A kingdom became "Spring Envoys", a guild became "the Salt Tax", and a set of islands became "Shiver Peaks". The context line ("sends envoys each spring", "sets the price of salt") pulled them off course.

**The owner's verdict on the rewrites:** the owner saw the samples and agreed with the recommendations (2026-10-28), with no separate verdict.

## Findings

1. **Flagging famous real names works on the local model** (Skyfall: 20 of 20 caught, 1 debatable false flag). The labelled set was famous places and people only. Whether the model also flags vocabulary-built names like Kholodnaya or Snegovaya Krepost is untested; part 4's own probe should check it.
2. **The real leak is Russian vocabulary and given names, not famous places.** A real-place list alone would miss most of it. Two things may catch it: the flag call (untested on these), and a check of a name against the language's own fit check (`fits`), since a name the Moscavian language didn't make won't fit its rules.
3. **Stock titles need help.** The model misses a third of them when the context gives them a role. The app-wide cliché list should hold title *shapes* ("the X Council", "the Eastern Wastes"), and should be used alongside the model.
4. **The AI clichés are invisible to the model.** The cliché list is required, as the design says.
5. **Rewriting works with a tight prompt.** Part 4 should:
   - use the V2-style prompt (examples, a length cap, a literal slot);
   - accept `{Name}` as a slot;
   - leave out the context line, or tell the model plainly to keep the kind of thing.
6. **Candidate names in the create prompt:** this probe doesn't answer that directly. Finding 2 suggests fixing names afterwards is enough for most cases. Putting the language's rolled names in the create prompt is worth trying in part 4's own probe, since most leaks are invented-sounding names built from real words.
