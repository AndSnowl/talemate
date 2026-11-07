# Languages 4c: streamlining people's names

Date: 2026-11-06. This follows 4b-2, people's names (merged to main, 65d54a6b; design `2026-11-04-fantasymate-languages-4b2-people-names-design.md`). It comes from the owner's first round of feedback on 4b-2 and the brainstorm after it. The owner: "I think we are getting close with convenience and consistency are the remaining issues." Fill-them-in languages now carry many rules, and the drafts, Name it and the Names chapter need to line up.

## Why

- **Too many rules, all equal.** Fill them in gave the owner's Zhelvan 21 rules. Many are only pieces (given names, family names, ordinary words) that the full rules are made of, but the Names chapter and Name it's rule list show them all in one flat list.
- **The engine guesses the rule.** Today the draft call reads sex and rank, and the engine matches them to each rule's "for: woman · noble". The owner wants the model to choose, from descriptions Claude writes ("we have this character in this language, what generator do you use, standard, a noble, an emperor?"), inferring it from the prompt.
- **Drafts aren't one system.** A new-entry draft and "+ Add facts" share the marking code, but 4b-2 added a person step to the new-entry path only. The owner: "My desire is parity between systems that should be the same, not just parity but for them to BE the same, DRY."
- **Whole names come out half-renamed.** On "Tsar Aleksi III", Name it offered only "Aleksi". Going through with it would give "Tsar Gosmar Zochar Vekhal III", where the language's own word for tsar is "Gosmar", so the right result is "Gosmar Zochar Vekhal". Regnal numbers have no place in the language at all. Seen from the narrator, they are Roman numerals whatever the language (owner).

## Goals

1. **Main rules first, pieces folded** (owner).
   - **Names chapter:** the full generators come first (people's composed rules, places, items…), then a section folded by default holding the pieces.
   - **Name it's rule dropdown:** the same order, with the main rules first, a divider, then the pieces "in case you need one".
2. **Each main rule has a description,** written by Claude when it makes or changes a language: "for an emperor or tsar", "ordinary townsfolk", "nobles of a house". A person's rule is **picked by the model** from those descriptions, inferred from the prompt and the draft, **when Name it opens** on them (owner, 2026-11-06).
3. **Name it opens on the model's pick** (owner). Opening Name it on a drafted person shows the rule the model chose, and the description that made it choose; the owner switches rules from the dropdown.
4. **One draft pipeline** (owner). New-entry drafts, "+ Add facts" and "+ Add event", and a group's "+ Add" all go through the same cleaning steps. A step either runs for all of them or for none. Drafts only **mark** names: nothing is renamed automatically (owner, 2026-11-06), and the built name waits in Name it.
5. **Whole names, with narrator words kept.**
   - Name it on a person's marked name replaces the whole proper part of the name.
   - Narrator words stay in place: titles ("Tsar"), kind words ("Lake", "Vamod Lake"), and regnal numbers ("III").
   - When the picked rule already says the title in the language ("Gosmar"), the English title isn't kept as well.

## Non-goals

- **Automatic renaming.** It waits until the model's rule picking has proved itself (owner).
- **Counting regnal numbers.** Which number a ruler gets is the future governance generator's job (owner: "I wouldn't want to design something that will just get overwritten later"). 4c keeps numbers as the narrator writes them and lets the owner type or change them.
- **The family system** is its own later project:
  - a relation picker on the character prompt ("son of X", which also sets the heritage);
  - a family tree screen that expands to relatives left unknown until generated;
  - a relationship web.
- **Replacing whole stubs automatically** with rule-made names belongs to the autonomy idea (`docs/ideas/generated-rules.org`).
- **Codifying narrator language** beyond the word lists the app already has.

## Anti-goals

- **The model loses its creativity.** Rule picking must not discourage the model from writing other names: epithets and bynames like "Zochar the White" should keep coming (owner).
- **Two pipelines that drift.** No new path that copies an existing one: 4c removes the one that exists.
- **Hidden pieces.** Pieces are folded, never removed from reach; Name it can still roll just a given name or a family name.

## Main rules and pieces

- **The default.** A rule is a piece when another rule uses it as a part. The engine already works this out (`person_names._building_blocks`).
- **Overrides.** Claude can mark a rule main or piece when it makes the language, and the owner can switch either from a rule's row in the Names chapter. That covers odd cases like an ordinary-words rule no other rule uses, or a pet-name rule.
- **Descriptions.** Each main rule carries a description of one short line. Pieces may have one but need none.
- **Where they come from.** The language-design skill, the briefs and **Fill them in** write `main` and the descriptions. A language without descriptions still works, and the model then picks from the rules' names.
- *My call:* a rule's row in the Names chapter shows its description under its name, editable in place like the other rows.

## Picking the rule

- **When it's picked** (owner, 2026-11-06): when Name it opens on a person, from any draft or page. This isn't done ahead of time. It's the same code everywhere, it costs a model call only when Name it is used, and it leaves the draft call that writes the person untouched, so the model's other names ("Zochar the White") keep coming. When automatic naming in "+ Add facts" comes later (a future goal), it runs the same pick ahead of time for each new person, so nothing in 4c is redone.
- **What the model gets.** It sees the person's text (the draft's facts and prompt, or the page's facts) and the main people rules of the person's language, each with its id, name and description. It answers with one rule id, and sex and rank. Name it opens on that rule, showing the description that made it choose. While the call runs, the panel shows the rule today's matching gives, then switches to the pick when it arrives.
- **The probe** compares picking inside the draft call with picking when Name it opens, on the same prompts:
  - how often the pick is right;
  - whether other names like "Zochar the White" still appear;
  - how long Name it waits for the pick.

  Picking when Name it opens wins on consistency unless it's too slow.
- **A bad answer.** An answer that isn't a known rule falls back to today's matching on sex and rank (`pick_rule`).
- **The pick sits beside "built as"** (*my call*). The call that picks also returns sex and rank, which gives a new person in "+ Add facts" (who has no person block) a "built as" too. "Built as" still drives forms (Kesterovsk → Kesterovska) and stays on the person page. When the pick and a rule's `for_person` disagree, the pick wins: the model read the prompt, and the owner can switch. `for_person` stays in the language file and the skill as the fallback, and as a hint beside each description.
- **The pick is stable** (*my call*). Once made, it's kept with the person (in the draft, or in the person's stored name details as `rule`): opening Name it again doesn't ask the model again. A rule the owner switches to in Name it, and then uses, becomes the person's rule.
- **If neither way picks well** (*my call*): the probe is a go/no-go gate. If the model picks about as badly as today's matching, model picking isn't built. Sex-and-rank matching stays the way, and I come back to the owner before going on.

## One draft pipeline

- **Every draft goes through one cleaning function:** new-entry, "+ Add facts" and "+ Add event", and a group's "+ Add". It finds the languages in reach and marks the names. Which names it marks is unchanged (owner, 2026-11-06): the names the name check flags, plus a drafted person's own name. For a drafted person, it also records what Name it needs: the language, and who they're built as when the draft says.
- **"All or none" covers the person steps** (*my call*): marking and recording what Name it needs. The pick happens in Name it, which is one panel for all drafts and pages. How a draft finds its languages stays different by nature: a new entry finds them from the prompt and where it's filed, while "+ Add facts" uses the languages of the entry it's on. So the fact and group drafts gain no Languages section.
- **The text is never changed.** The person's mark says "Name it can build it from ⟨Language⟩'s rules for people" (as merged in 4b-2). The model's title, if any, is kept as a title.
- **No duplicate functions.** The three current entry points (`clean_preview`, `clean_fact_draft`, `clean_group_draft`) become thin callers of the one function, or are replaced by it.

## Whole names and narrator words

- **The narrator words** are the lists the marking code already uses:
  - title words (`TITLE_WORDS`): "Tsar";
  - kind words: "Lake";
  - frame words: "Kingdom of";
  - Roman numerals.
- **A person's mark covers the whole proper part.** For a person in a language with people rules, the marked part is every word that isn't a narrator word ("Aleksi" alone today becomes the whole proper name). Name it renames that whole part, and the narrator words stay where they were: "Tsar ⟨new name⟩ III".
- **Epithets and places the rule doesn't build are kept** (*my call*). "Zochar the White" keeps "the White" (the anti-goal protects such names), and an "of ⟨place⟩" the picked rule doesn't build stays where it is. The whole proper part replaced is the person's name up to the first such epithet or "of"; when the rule itself builds "of ⟨house⟩", the "of ⟨place⟩" is replaced too.
- **A title the rule already says** (a rule with a title part, such as Zhelvan's sovereign rule, "Gosmar"): the English title word in front is dropped when the built name is used. *My call:* a rule part counts as a title when its label is "title" or it is a word the language keeps as a title (`kept_titles`). This doesn't reverse 4b-2's "a title is held". A language's own rule may still write a title word, as Zhelvan's sovereign rule does, but the skill doesn't push title parts. Only the English title that the rule's word stands for is dropped ("Tsar" for "Gosmar", found through `kept_titles` or the part's English writing). Other titles in front ("Lady", "Captain") stay. The held title remains in the person's titles list and simply isn't shown in front of the name.
- **Regnal numbers.** A number is kept through Name it, opened from a draft's mark or from an accepted person's page alike (*my call*). It is stored with the person's name details (beside the parts, so the Name section and later rebuilds show "III"). Name it shows it as a small narrator field after the name, where the owner can type, change or clear it. It's always written as a Roman numeral and never built in the language.
- **Places keep their kind words too:** "Lake Vamod" and "Vamod Lake" keep "Lake" where it was, as today's marking already does for places.

## Probe (before building the model-dependent part; ask the owner first)

On the owner's test-app world (Zhelvan, Drassonais) and the world model (Skyfall on koboldcpp):
- About 15 person prompts, among them "the tsar's youngest son", "a fisherman's daughter", "the duke's heir" and an owl-folk hunter.
- Each run with the pick inside the draft call, and with the pick when Name it opens.
- Score the pick against labels written before the run, count the other names written, and time both.

Fill them in (Claude Code) is run on one language to check it writes `main` and the descriptions.

## Constraints

- Python and Vue, as the app is now; no new dependencies.
- No model call on Reroll, pin, pick, or Name it's builder.
- The owner's test app is the fresh one in `.worktrees/languages-4b2/.superpowers/test-app`. Back up its `worlds/` and `config.yaml` and ask before restarting it; `talemate_app.py start` wipes it.
- No migration code (owner): languages without `main` or descriptions use the defaults above.
- UI rules: controls by content; the same look means the same component; screenshots at 1920×1080.

## Left to the builder

- The field names for `main` and the description, and where the pick is stored.
- How the folded pieces section and the dropdown's divider look, within the UI rules.
- Whether the three cleaning entry points stay as thin callers or are replaced.
- How Name it shows the regnal number field.
