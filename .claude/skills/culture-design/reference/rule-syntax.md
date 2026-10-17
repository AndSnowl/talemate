# Generator rule syntax

This is the pattern language used by `Language.categories` and a
generator's `patterns`/`reject`. It is faithfully copied from the
module docstring of `src/talemate/cultures/generator.py` — the importer
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
case-insensitive regex. A name fits the language when, after
lowercasing, every space-separated word of the name fully matches at
least one compiled pattern, and no generator's `reject` regex matches
it. A language with no generators always "fits" — nothing to check
against.

Use this when hand-writing a name (a protagonist, a landmark) that
should read as native to the culture: if it doesn't fit, either adjust
the name or treat it as a foreign name and add a `foreign_renderings`
entry instead.
