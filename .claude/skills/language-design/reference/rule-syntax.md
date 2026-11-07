# Generator rule syntax

This is the pattern language used by `Language.categories` and a
generator's `patterns`/`reject`. It is faithfully copied from the
module docstring of `src/talemate/languages/generator.py` — the importer
parses exactly this syntax, so do not invent variations on it.

## Categories

`Language.categories` maps a single uppercase letter to a space-separated
list of options, e.g.:

```json
{"C": "k kh t th dh r*2", "V": "a ae e o u i"}
```

- Options may be more than one letter long (`kh`, `th`).
- An option may carry a trailing weight suffix `*n` (an integer); options
  without a suffix have weight 1. In the example, `r` is twice as likely
  to be picked as any other consonant.

## Pattern tokens

A generator's `patterns` are read left to right. Each token is one of:

- an uppercase letter that names a defined category: "one weighted pick
  from that category's options";
- `(...)`: optional, included with 50% probability; may nest, e.g.
  `C(V(C))`;
- `[a|b|c]`: picks between the alternatives with equal probability; each
  alternative is itself a sub-pattern and may contain categories,
  optional groups and nested choices;
- anything else (lowercase letters, spaces, `'`, `-`, digits, and
  uppercase letters that are *not* defined categories): literal text,
  copied through as-is.

Example: `"CVC[rin|rek|mar|l]"` renders a consonant, a vowel, a
consonant, then one of `rin`/`rek`/`mar`/`l`.

**Careful with capitals.** Any uppercase letter that isn't one of
`categories`' keys is still legal — it's copied through as literal text
— but it's the most common typo in a hand-written pattern: a category
meant to be `C` but typed `X` silently renders as a stray capital `X`
in every name that pattern produces. `cli validate` warns about every
such letter (`Generator '<name>': '<X>' in pattern '<p>' is not a
category, so it is written literally`). The warning fires the same way
for a capital you meant literally — a literal word fragment such as
`"The CVC"` in an inn-name generator, or the `B` in a choice literal
like `[a|B]` — it can't tell a typo from an intentional literal, so
expect and ignore the warning whenever the capital is there on
purpose.

## Pattern weight

A whole pattern string may end in `*n` to weight it among a generator's
other patterns when one pattern is picked to render, e.g.
`["CVC*3", "CV"]` favours the first pattern 3:1. The `*n` suffix is
stripped before the pattern body is parsed.

## Output rules

Applied to each candidate produced from a pattern:

- `reject` is a list of regexes, matched case-insensitively against the
  full rendered name; any match drops the candidate.
- `min_length` / `max_length` count *letters only* (spaces, apostrophes
  and hyphens are free).
- when `capitalize` is true, the first letter of each space-separated
  word is uppercased (the rest of the word is left as rendered).
- results are de-duplicated case-insensitively.

## Checking whether a name "fits" (`cli sample`'s ✓/✗ marks)

Every pattern of every generator is compiled into an anchored,
case-insensitive regex. A name fits the language when, with its
whitespace collapsed to single spaces, the *whole* name matches a
pattern of some generator and none of that same generator's `reject`
regexes match it (a multi-word pattern such as `"CV CVC"` matches a
two-word name; another generator's reject rules don't count). A
language with no generators always "fits" — nothing to check against.

Use this when hand-writing a name (a protagonist, a landmark) that
should read as native to the language: if it doesn't fit, adjust the
name, or add it to the dictionary as a word with its meaning (a word made
of two or more of the language's own fitting words counts as fitting).

`python -m talemate.languages check FILE` reports the share of the
dictionary that fits the `words` generator. To see whether two languages
read as distinct, roll names from one and check them against the other's
rules: aim for close to none fitting the neighbour.

## Grammar for names and composed rules

`name_grammar` and a rule's `shapes` are described in `SKILL.md`. The app's
engine applies them: the model only ever chooses meanings. A language
without them still works; names are then built in the owner's English
word order.

## People's names

A people rule is a composed rule whose parts may also be `connection`
(taken from a parent: `roles`, `take`, and `rule` to roll from without
one) or `own` (the person's own part, for pet names), with `person_forms`
by sex or rank and `for_person` saying who it's for. A Drassonais noble
woman's rule:

```json
{"id": "noble-women", "name": "Noble women", "use": "character",
 "for_person": {"sex": "woman", "rank": "noble"},
 "shapes": [{"parts": [
   {"kind": "rule", "rule": "women-given", "label": "given"},
   {"kind": "word", "word": "di", "english": "of", "label": "of"},
   {"kind": "connection", "roles": ["father", "mother"], "take": "house",
    "rule": "houses", "label": "house"}]}]}
```

A Varovni family name in the woman's form:

```json
{"kind": "connection", "roles": ["father", "mother"], "take": "family",
 "rule": "family", "label": "family",
 "person_forms": [{"when": {"sex": "woman"},
                   "changes": [{"kind": "ending", "text": "a"}]}]}
```

`people_names` (choices, kept titles, address) is described in
`SKILL.md`. The app reads sex and rank from a person's facts, takes the
inherited parts from the world, and builds the rest; a language without
people rules gives people plain rolled names.
