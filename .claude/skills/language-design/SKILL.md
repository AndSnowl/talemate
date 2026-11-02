---
name: language-design
description: Use when designing, extending or revising a language or naming style for a fantasymate world (a new language from a plain request, a daughter language from a parent and how it drifted, a revision of an existing language, or an English-word naming style like Duskhollow), to produce a `<name>.language.json` file the owner imports in the World tab.
---

# Language design

Make a language or naming style for a fantasymate world, and write it as
one `<name>.language.json` file the owner imports with **Import
language** in the World tab (or pastes there). The app checks every
language the same way this skill does, so a file that passes here
imports cleanly.

## The three jobs

1. **A new language** from a plain request ("a unique but recognizably
   Russian language", "fantasy-sounding English compound names").
2. **A daughter language** from a parent's file plus how it drifted
   ("isolated in the mountains for five hundred years"): start from the
   parent's roots and sounds, and change them the way the drift
   suggests, so the two still sound related.
3. **A revision** of an existing language from its exported file plus a
   request ("redo the blessings and curses around the Owl Synod"). Keep
   every word the request doesn't touch. **Never change or drop a word
   the world already uses as a name** — when the owner gives you the
   world's context, those words are listed; leave them exactly as they
   are.

## Talking with the owner

The owner isn't a linguist. Ask only what the request leaves open, at
most four short questions, in everyday words ("harsh or soft?", "long
words or short?", "should place names feel old and formal?"). Never use
linguistics terms (phonology, phoneme, fricative, morpheme, ...) in
questions or in anything the owner reads. If the owner says "decide for
me", decide.

## Never use real words

A language can *sound like* a real one, but its words are invented:
"recognizably Russian" never means Russian words (no voda, zemlya,
gorod, real given names or surnames). Set `flavour` to the real language
it sounds like (`"russian"`, `"english"`, or `""`); the check then flags
real words of that language.

An English-word naming style (`flavour: "english"`) is made of real
English parts on purpose (dusk, thorn, hollow, ford). Its parts are fine;
whole names that are real English places (Ashford, Oakham) get flagged.

## The file

The schema is `src/talemate/languages/language.schema.json` (generated
from `talemate.languages.models.LanguageFile`). The shape:

```json
{
  "format": "fantasymate.language",
  "version": 1,
  "parent": "Old Moscavian",
  "description": "",
  "language": {
    "name": "Moscavian",
    "level": "full",
    "flavour": "russian",
    "sound": "Two or three plain sentences on how it sounds.",
    "categories": {"C": "k v r s z t n l", "V": "a o e u i"},
    "generators": [
      {"id": "words", "name": "Words", "use": "words", "patterns": ["CVC", "CVCVC"]},
      {"id": "men", "name": "Men's names", "use": "character", "patterns": ["CVCVC"]},
      {"id": "women", "name": "Women's names", "use": "character", "patterns": ["CVCVCa"]},
      {"id": "places", "name": "Places", "use": "place", "patterns": ["CVCVC(ov)"]},
      {"id": "from-a-place", "name": "Names from a place", "use": "character",
       "shapes": [{"parts": [{"kind": "rule", "rule": "men"},
                             {"kind": "meaning", "of": true, "hint": "the place they come from"}]}]}
    ],
    "name_grammar": {
      "describing": "before",
      "of": {"how": "word", "text": "da", "word_side": "before"},
      "the": [{"when": "after_vowel", "kind": "ending", "text": "t"},
              {"kind": "ending", "text": "ot"}],
      "more_than_one": [{"when": "ends:a|o", "kind": "swap", "drop": "a|o", "text": "i"},
                        {"kind": "ending", "text": "y"}],
      "endings": [{"ending": "enka", "meaning": "small, dear"},
                  {"ending": "stvo", "meaning": "land of"}]
    },
    "grammar": [
      {"title": "Nouns", "topic": "nouns",
       "text": "Plain words on how nouns work: gender, plurals, how 'the' is shown.",
       "tables": [{"caption": "dov (shrine)", "columns": ["", "one", "more than one"],
                   "rows": [["a", "dov", "dovy"], ["the", "doven", "dovyen"]]}],
       "examples": [{"original": "Zorin doven stoi", "translation": "The bright shrine stands.",
                     "breakdown": [["zorin", "bright"], ["doven", "shrine-the"], ["stoi", "stands"]]}]}
    ],
    "dictionary": [{"word": "vel", "meanings": ["great"]}, {"word": "soru", "meanings": ["wind", "breath"]}],
    "phrases": [{"id": "curse-rot", "category": "curse", "original": "Vel kar!", "translation": "Great rot!"}],
    "similar": [{"name": "Sorauan", "degree": "close"}]
  }
}
```

- `level`: `description` (only how it sounds, for speech that can't be
  written), `naming` (enough to make names), or `full` (names, words,
  phrases).
- **Meanings are short**, as a dictionary gives them: one to three words ("wind", "great fort"), never a sentence. A word can have several meanings; a word made only to be a name can have none. Never write "used as a name" as a meaning: the app shows which words name something.
- **Grammar is a list of sections**, each with a `title`, a `topic`, plain
  `text`, `tables` (caption, columns, rows) and `examples` (original,
  word-by-word breakdown, translation). The topics: `sounds`,
  `word_order`, `nouns`, `pronouns`, `verbs`, `adjectives`, `questions`,
  `numbers`, `word_building`, `names`, `politeness`; anything unusual the
  language does gets sections of topic `other`. Explain plainly: follow
  any grammar term with what it means.
- **How much to make:** the brief says. A full language has a word for
  every core meaning the brief lists (the structural words such as the,
  a, be, have, with, and the everyday list), at least 3 phrases in each
  category (greeting, farewell, blessing, curse, oath, saying, toast,
  insult, endearment), every grammar topic with tables where it has
  forms, and name rules for characters, places, items, groups and a
  demonym. A quick core keeps to what the brief lists. The app's check
  says what's "still to fill in".
- **A change** (the brief starts "# Change a language"): the language's
  file is already in your folder; edit it in place and keep the whole
  file. Change only what the request asks, keep the language's name, and
  keep every word the brief says names something in the world exactly as
  it is. The app merges your change with any edits the owner made
  meanwhile and shows them what changed.
- **Every word has a `part`:** `noun`, `verb`, `adjective`, `adverb`,
  `pronoun`, `article`, `preposition`, `conjunction`, `number`,
  `question`, `particle`, `exclamation` or `ending`. Small words have
  parts too ("in" is a preposition, "and" a conjunction).
- **A full language must have a `words` generator** (`"use": "words"`):
  the rules ordinary words follow. Every dictionary word should fit it
  (or be made of two or more words that do); the app rolls new words for
  translations from it.
- Generators make names for `people`, `places`, `things`, or one entry
  kind (`character`, `place`, `item`, `event`, `lore`, `being`,
  `species`, `race`), or a form (`adjective`, `demonym`). Write 2-3
  patterns each.
- **Character names come as two rules by default:** "Men's names" and
  "Women's names" (both `"use": "character"`, ids `men` and `women`),
  with the endings or sounds that tell them apart. Make one shared rule
  only when the brief says the language doesn't mark it.
- A naming style made of English parts: put whole-word parts in
  categories (`"A": "dusk thorn ash raven"`, `"B": "hollow field mere
  ford"`), use a pattern like `"AB"`, and give every part's meaning in
  the dictionary.
- **The grammar for names** (`name_grammar`) is what the app builds names
  with: where describing words go (`describing`), how "of" is said (`of`: a
  word or an ending), how "the" and "more than one" are made, and the endings
  with a meaning from the word-building table. Each form is a list of
  changes tried in order; the first whose `when` holds is used: `ending`
  (adds `text`), `swap` (drops one of the `|`-listed endings in `drop`, adds
  `text`), `word_before`, `word_after`, `double` (the first syllable
  doubled); `when` is `""`, `after_vowel`, `after_consonant`, `before_vowel`,
  `plural` or `ends:a|o`. Every rule must rebuild the examples your own
  tables give ("kor → koren, kori").
- **Composed name rules** (`shapes` instead of `patterns`) write naming
  customs as parts: another rule (`rule`), a fixed word (`word`), or a
  meaning (`meaning`, with `forms`, `of` and a `hint` for what it takes).
  Use them for customs the grammar describes, like an owl-name after the
  given name ("[Men's names] Ul [a meaning · plural]").
- `reference/rule-syntax.md` has the full pattern syntax. The weight
  marker is a number (`r*2`), never a literal `*n`; `|` only appears
  inside `[...]`.
- `parent` and `similar` name other languages in the world; the import
  links them when they exist.

## Check before handing it over

Run the app's check on the file, and fix it until it passes.

If your brief names a check command (the app gives one when it runs
you), run exactly that, on its own line with no other commands:

```bash
/the/path/from/the/brief/check NAME.language.json
```

Otherwise, from the app's folder:

```bash
guix shell -m manifest.scm -- uv run --no-sync python -m talemate.languages check NAME.language.json
```

(Without guix: `uv run --no-sync python -m talemate.languages check
NAME.language.json`.)

- Exit code 1 means something must be fixed: the note says what. Fix it
  and run again.
- Exit code 0 can still list things worth fixing: real words, or words
  that don't follow the language's own rules. Fix real words always, and
  fix unfitting words until no more than a third of the dictionary is
  flagged.
- Look at the sample names it prints: do they sound like what the owner
  asked for? If not, adjust the categories and patterns.

## Finishing up

Tell the owner the file's path, and that they import it with **Import
language** in the World tab (choose the file, or paste its text). For a
revision, they open the language's page and choose **Import a new
version**, which shows what changes before anything is saved.
