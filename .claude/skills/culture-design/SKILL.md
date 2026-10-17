---
name: culture-design
description: Use when designing or extending a culture or a culture's language for a Talemate world, to produce a `<id>.culture.json` file for import into World Editor → Cultures.
---

# Culture Design

Interview the owner to design a culture — its people, its place, its
feel, and its language — and write the result as a single
`<id>.culture.json` file they import into Talemate's World Editor →
Cultures tab.

## Non-goals

- Do not translate long passages. A few sayings, curses and greetings
  with word-by-word breakdowns are the ceiling — not paragraphs.
- Do not add law or governance fields. Talemate has none for cultures;
  countries show a "later" placeholder for that.

## The file format

One culture is one `CultureFile` JSON object:

```json
{
  "format_version": 1,
  "culture": { "id": "...", "name": "...", "language": { ... }, ... },
  "glossary": [ { "text": "...", "kind": "person|place|thing|word", "meaning": "...", "true_name": "", "renderings": {} } ],
  "places": [ { "name": "...", "kind": "country|region|city|town|village|building|poi|terrain", "parent": null, "share": 100 } ],
  "foreign_renderings": [ { "name": "...", "rendering": "..." } ]
}
```

`culture` is the full culture (see `reference/example.culture.json` for a
complete, valid example — read it before writing your first file).
Key points:

- `culture.language.level` is exactly one of `description`, `naming`,
  `full` — nothing else.
- `glossary` entries are names and words you're declaring as belonging
  to this culture. They become Talemate glossary entries on import.
  Leaving `language` off the entries here is correct — it's implied by
  the culture being imported.
- Unassigned names (names the owner has in play but hasn't assigned to
  any culture yet, shown in Talemate's "Unassigned names" list) are
  claimed by adding a glossary entry here with the exact same `text`
  (case-insensitive). The import then moves that entry onto this
  culture instead of creating a duplicate.
- `places` are matched to existing places by name (case-insensitively).
  An unmatched place is created new, under its `parent` (also matched
  by name) or as a root if `parent` is null or doesn't match anything
  yet. A child may be listed before its parent.
- `foreign_renderings` is how *this* culture's speakers render a name
  that belongs to *another* culture — e.g. how river-folk say a
  mountain-clan name. Each `name` must match an existing glossary entry
  (in any culture); it's reported as a warning otherwise.
- Re-importing an existing culture replaces its core fields but keeps
  play `additions`, never deletes a glossary entry or place, and keeps
  Talemate's own copy of any glossary entry marked `reviewed` or edited
  by the owner — write the file as the full, current design each time,
  don't try to diff it yourself.

The full schema is `src/talemate/cultures/culture.schema.json`, or get it
fresh with `cli schema` (see Validating below).

## The interview

Ask one question at a time. Don't front-load a questionnaire.

1. **People and place.** Who are these people — a nation, a guild, a
   scattered diaspora? Where do they live, and what's the feel (blunt
   river-ferrymen, secretive mountain miners, courtly merchants)? This
   drives `description`, `customs`, `food`, `holidays`.
2. **Language level.** Ask which of the three they want, explaining
   briefly:
   - `description` — prose about the language only (`sound`,
     `syllable_notes`); no categories, no generators, nothing to roll.
   - `naming` — enough to roll names: `categories`, and generators for
     whichever of people/places/things the owner needs.
   - `full` — `naming`, plus `grammar`, a small `dictionary`, and
     `phrases` (a handful of sayings, curses, greetings with
     word-by-word `breakdown`s).
3. **Existing world context.** Ask for the world folder path
   (`scenes/<project>/shared-context/<name>.world/`) or for exported
   `.culture.json` files of neighbouring cultures. Read them before
   designing the language — see below.
4. **Writable or not.** Ask whether this culture's own people can write
   it, or whether it's only ever heard and rendered by others.

## Reading existing context

If given a world folder, read `cultures/*.json` for neighbouring
cultures' sounds, categories and generators, `glossary.json` for
existing names (including unassigned ones), and `places.json` for the
place hierarchy. Use this to:

- keep the new language's `sound` and `categories` audibly distinct
  from its neighbours (don't reuse the same consonant/vowel inventory
  unless the owner wants close-cousin languages);
- write `foreign_renderings` for any neighbouring-culture name this
  culture's people would say differently;
- claim unassigned names the owner points out (see above).

**Unwritable language.** Set `culture.language.writable: false`. Each
glossary entry for this culture gets `true_name` — the name in the
culture's own (unwritten) tongue — while `text` is the name as it's
actually used in play (commonly a neighbour's rendering, or a simple
phonetic approximation). If you've read a neighbouring culture's file
and know how its speakers would render this name, set that directly in
the entry's own `renderings` map (keyed by that culture's id) rather
than waiting on that neighbour to add a `foreign_renderings` entry
later.

## Extending an exported culture

If the owner hands you an exported `.culture.json` to extend, keep its
`additions` and its existing `glossary` entries as given — add to them,
don't drop anything. Re-import never deletes anything already in
Talemate: play `additions` are merged, and a glossary entry you omit is
simply kept as Talemate has it (it just isn't updated from your file).
The culture's core sections (description, customs, food, holidays,
language, dictionary, phrases, generators, ...) are a different matter:
those are replaced wholesale by what you write, so leaving something out
of them removes it.

## Building the language

- `sound`: a paragraph on how it feels to hear — pace, texture, what
  gets spat vs. drawn out.
- `categories`: short consonant (`C`) and vowel (`V`) inventories (add
  more letters for other classes if useful). See
  `reference/rule-syntax.md` for the full syntax, including weights
  (`r*2`) and multi-letter options (`kh`).
- `generators`: one or more per `use` the owner needs (`people`,
  `places`, `things`). Write 2-3 `patterns` per generator for variety.
  `reference/rule-syntax.md` covers optional groups `(...)`, choices
  `[a|b]`, pattern weights (`"CVC*3"`), `reject` regexes, and
  `min_length`/`max_length`.
- For `full`: `grammar` as a short prose paragraph (word order, a
  notable mood or inflection), a `dictionary` of the words you actually
  used in phrases, and `phrases` grouped by `category` (`saying`,
  `curse`, `greeting`, ...) with a word-by-word `breakdown`.

## Validating and sampling

Before handing the file over, always run both commands from the repo
root:

```
uv run python -m talemate.cultures.cli validate <file>
uv run python -m talemate.cultures.cli sample <file>
```

`validate` exits 0 and prints `OK: <file>` for a well-formed file, or
prints the error and exits 1 — fix and re-run. `sample` rolls names
from every generator (10 by default; pass `--generator <id>` or
`--count <n>` to narrow it) and marks each with ✓/✗ for whether it
"fits" the language's own patterns (see `reference/rule-syntax.md`).

Show the owner the sample output. If names feel off, revise
`categories`/`patterns` and re-roll — don't just hand-pick good-looking
samples and move on, since the generator keeps producing names during
play.

On a Guix machine, wrap both commands:
`guix shell uv node python@3.11 -- uv run --no-sync python -m talemate.cultures.cli validate <file>`.

## Finishing up

Write the file as `<id>.culture.json` wherever the owner asks (their
world folder, a scratch location, wherever). Tell them to import it via
**World Editor → Cultures → Import culture**.
