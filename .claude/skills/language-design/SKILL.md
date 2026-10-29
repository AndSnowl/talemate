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
      {"id": "people", "name": "People", "use": "character", "patterns": ["CVCVC"]},
      {"id": "places", "name": "Places", "use": "place", "patterns": ["CVCVC(ov)"]}
    ],
    "grammar": "A short plain paragraph, for a full language.",
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
- **A full language must have a `words` generator** (`"use": "words"`):
  the rules ordinary words follow. Every dictionary word should fit it
  (or be made of two or more words that do); the app rolls new words for
  translations from it.
- Generators make names for `people`, `places`, `things`, or one entry
  kind (`character`, `place`, `item`, `event`, `lore`, `being`,
  `species`, `race`), or a form (`adjective`, `demonym`). Write 2-3
  patterns each.
- A naming style made of English parts: put whole-word parts in
  categories (`"A": "dusk thorn ash raven"`, `"B": "hollow field mere
  ford"`), use a pattern like `"AB"`, and give every part's meaning in
  the dictionary.
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
