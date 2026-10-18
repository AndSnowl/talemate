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
complete, valid example — read it before writing your first file; its
`Kethrun` glossary entry is a deliberately irregular legacy name that
predates Taelrik's current patterns and doesn't fit its generators —
that's intentional, not a bug to copy. A new native name you add should
fit).
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
- Places aren't glossary entries — a `places` entry only sets the
  place's name/kind/parent/share. It has no `renderings` map and can't
  be a `foreign_renderings` target. If a neighbouring culture should be
  able to render this place's name (e.g. how river-folk say a
  mountain-clan city), add a separate `glossary` entry for it too, with
  `kind: "place"`.
- `share` math on import: if, after this import, this culture is the
  only one with a share at a place (new or existing), it's set to 100%
  regardless of what `share` says in the file — don't be surprised when
  a lone culture's share isn't what you wrote. If this culture already
  has a share at a place from an earlier import, re-importing never
  moves it, even if the file's `share` differs; the owner adjusts mixed
  places afterwards in World Editor → Places & regions. Only a place
  where another culture already has a share and this culture doesn't
  yet gets the file's `share` applied as given.
- `foreign_renderings` is how *this* culture's speakers render a name
  that belongs to *another* culture — e.g. how river-folk say a
  mountain-clan name. Each `name` must match an existing glossary entry
  (in any culture) *at import time*; if the target culture hasn't been
  imported yet, the entry is silently dropped rather than held for
  later — when designing several cultures together, import the one a
  name belongs to before the culture that renders it.
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
2. **Where it lives, and shares.** Where does this culture sit in the
   place hierarchy (country/region/city/town/.../`parent`)? If it
   shares a place with a culture already in Talemate, ask roughly what
   share of that place is theirs — it's only a starting point, since
   shares behave specially on import (see `share` math below) and the
   owner can fine-tune them afterwards in Places & regions.
3. **Generators and seed names.** Which generators does the owner
   actually need — given names, family names, place names, whatever
   `people`/`places`/`things` the story calls for? Ask whether any
   names are already in play (an "Unassigned names" list entry, a name
   already used in a scene) that should be claimed as this culture's
   rather than invented fresh. Ask for a `color` (a hex value) for the
   World Editor's culture swatch.
4. **Language level.** Ask which of the three they want, explaining
   briefly:
   - `description` — prose about the language only (`sound`,
     `syllable_notes`); no categories, no generators, nothing to roll.
   - `naming` — enough to roll names: `categories`, and generators for
     whichever of people/places/things the owner needs.
   - `full` — `naming`, plus `grammar`, a small `dictionary`, and
     `phrases` (a handful of sayings, curses, greetings with
     word-by-word `breakdown`s).
5. **Existing world context.** Ask for the world folder path
   (`scenes/<project>/shared-context/<name>.world/`) or for exported
   `.culture.json` files of neighbouring cultures. Read them before
   designing the language — see below.
6. **Writable or not.** Ask whether this culture's own people can write
   it, or whether it's only ever heard and rendered by others.

If the owner wants several cultures for the same world, design and
import them one at a time, in dependency order: import a culture before
any other culture's `foreign_renderings` targets one of its names (see
above), and before you need to read its glossary for seed names or
existing renderings.

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
culture's own (unwritten) tongue, written as a bracketed description of
the sound, since there's no script for it, e.g.
`⟨two low hums, one click⟩` — while `text` is the name as it's actually
used in play (commonly a neighbour's rendering, or a simple phonetic
approximation). If a neighbour already has a rendering for this name —
in play already, or in that neighbour's own glossary/`renderings` —
reuse that rendering's text exactly as this entry's `text` rather than
inventing a second phonetic approximation for the same name. If you've
read a neighbouring culture's file and know how its speakers *would*
render this name but haven't seen that rendering fixed yet, set it
directly in the entry's own `renderings` map (keyed by that culture's
id) rather than waiting on that neighbour to add a `foreign_renderings`
entry later.

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
root, through the manifest:

```
guix shell -m manifest.scm -- uv run --no-sync python -m talemate.cultures.cli validate <file>
guix shell -m manifest.scm -- uv run --no-sync python -m talemate.cultures.cli sample <file>
```

`validate` exits 0 and prints `OK: <file>` for a well-formed file, or
prints the error and exits 1 — fix and re-run. It also prints a
`WARNING:` line for every likely mistake it finds (an unknown field, a
description-only language with unused generators, a glossary entry
that doesn't fit its own generators, an undefined category letter —
see below). None of these block the import, but read them.

`sample` rolls names from every generator (10 by default; pass
`--generator <id>` or `--count <n>` to narrow it) and marks each with
✓/✗ for whether it "fits" the language's own patterns (see
`reference/rule-syntax.md`). That mark is almost always ✓ — a
generator's own output fits its own patterns by construction — so it
says nothing about quality. Read the names themselves: do they sound
distinct from their neighbours, pronounceable, not accidentally funny?

Watch for an uppercase letter sitting in the middle of a rolled name
(e.g. `ZaXa`): any letter in a pattern that isn't one of the language's
own `categories` keys is written through literally, so a typo'd
category reads as a stray capital in every name it touches. `validate`
now warns about every such letter. If you meant a category, fix the
pattern or add the category. If you meant the capital literally — a
literal word fragment such as `"The CVC"` in an inn-name generator, or
a capital inside a choice literal like `[a|B]` — the warning is
expected and fine; it can't tell intent apart from a typo, so it flags
every capital outside `categories` either way. Leave it.

Also check the rolled names against every neighbouring culture's
language, not just this one's own — a name that also "fits" a
neighbour's patterns will read as native to both. Aim for about 0%
overlap. There's no CLI command for this; a one-liner is enough:

```python
from talemate.cultures.generator import roll, fits
names = roll(my_language, "given_male", count=50)
print(sum(fits(neighbour_language, n) for n in names), "/", len(names))
```

Show the owner the sample output. If names feel off, revise
`categories`/`patterns` and re-roll — don't just hand-pick good-looking
samples and move on, since the generator keeps producing names during
play.

## Finishing up

Write the file as `<id>.culture.json` wherever the owner asks (their
world folder, a scratch location, wherever). Tell them to import it via
**World Editor → Cultures → Import culture**.
