# Languages 3a: languages you can use — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a language can live in a world as its own entry: imported from a file or pasted text, checked, shown on its page, attached to places and people through Languages sections, and used to make names by right-click. The language-design skill can make one.

**Architecture:**
- **Backend.** A new `language` entry kind stores the language's technical part in its own fields, and a shared `languages` field records who speaks what. Pure logic lives in `src/talemate/languages/`:
  - `models` and `schema`: the file format;
  - `check`: the shared check;
  - `entry`: entry ↔ model conversion;
  - `lookup`: whose languages apply to an entry;
  - `importer`: import and diffs;
  - `naming`: rolling, defining and translating names.
- **Server and UI.** The worlds server plugin exposes it. The worlds UI adds the language page, the Languages section and right-click naming.
- **Model calls.** Only for definitions and picks, on the creator agent's client, as the probes showed works locally.

**Tech Stack:** Python 3.11, pydantic v2, SQLite world store; Vue 3 / Vuetify 3; pytest, node checks, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-10-28-fantasymate-languages-part-3-design.md` (3a). Also read part 3 of `docs/superpowers/specs/2026-10-28-fantasymate-languages-design.md` (the "main spec"), and `docs/superpowers/probes/2026-10-28-language-make.md`.

## Global Constraints

- **Environment.** Run everything through `guix shell -m manifest.scm -- …` from the repo root. Use `uv run --no-sync`, never plain `uv run`. Run e2e with `pytest tests/e2e -m e2e -n 4` (never more than 4 workers). Frontend: `npx --yes corepack@0.34.0 pnpm` from inside `talemate_frontend`. See `docs/dev/local-testing.md`.
- **The plain suite ends every task with 0 failures.** Run the area's e2e folder while iterating, and the full e2e suite once per UI task, at its end.
- **The owner's UI rules:**
  - controls sit right after what they act on;
  - right-align only in areas half the screen wide or less;
  - things that look the same are one component;
  - the approved screen is the model.
- **UI is built inline, with screenshots** (`scripts/dev/look.py`) after every visible change, shown to the owner for rounds of feedback (spec, Constraints).
  - Right-click naming and the Languages section follow `.superpowers/brainstorm/18627-1793167762/content/naming-flow.html`.
  - The language page and the import review are designed in the build.
- **No linguistics jargon** in any text the owner reads (spec, Anti-goals). The check's report, the page labels and the menus use plain words.
- **Every change to a language is an undoable world edit:** written through `Revision.set_field` / `add_fact` in one `world.revision(...)`.
- **koboldcpp:** this plan needs no probe runs. Tests use stub clients. Any manual run against the owner's koboldcpp needs "ready for AI testing?" first.
- **Commits** end with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **Where the work happens:** a worktree on `feature/languages-3a` (`.worktrees/languages-3a`), with its own venv (`uv sync --extra dev`) and `pnpm install`.
- **After changing a test id or selector** the AI tests drive, `grep -rn` it in `tests/ai`.

## Review Focus

1. **A cycle in filings** (A filed in B, B filed in A, which is possible after an undo) must not hang the languages lookup. Expect it to stop and return what it found. Test: Task 5, `test_lookup_survives_a_filing_cycle`.
2. **A deleted language that is still named in someone's `languages` rows.** Expect the rows to be skipped in lookups and shown as "(deleted language)" on the page, with no error. Test: Task 5, `test_lookup_skips_deleted_language`.
3. **Pasted text with prose or a code fence around the JSON** (what chat assistants return). Expect it to import as if it were the bare file. Test: Task 6, `test_parse_accepts_fenced_and_wrapped_text`.
4. **Re-importing a revised language that drops or changes a word already used as an entry's name.** Expect the used word to be kept, and the diff to report that it was kept. Test: Task 6, `test_revision_keeps_used_words`.
5. **Right-click naming for an entry kind the language has no generator for** (e.g. an item, when only people and places generators exist). Expect it to fall back to the closest generator rather than error. Test: Task 7, `test_generator_for_kind_falls_back`.

---

### Task 1: The language file format

**Files:**
- Modify: `src/talemate/languages/models.py`
- Create:
  - `src/talemate/languages/schema.py`
  - `src/talemate/languages/language.schema.json` (generated, committed)
- Test: `tests/languages/test_models.py`

**Interfaces:**
- Produces, used by every later task:
  - `Language`, gaining `flavour: str = ""` (lower-case: `"russian"`, `"english"`, `""`) and `similar: list[SimilarLink] = []`.
  - `GeneratorDef.use: str`, any of:
    - `people`, `places`, `things`, `words`;
    - an entry kind (`character`, `place`, `item`, `event`, `lore`, `being`, `species`, `race`);
    - a form: `adjective`, `demonym`.

    `level` keeps its values (`description` | `naming` | `full`).
  - `Phrase.category`: any non-blank string.
  - `SimilarLink(name: str, degree: Literal["close","distant","one-way"])`, referring to another language by name in a file.
  - `LanguageFile(format: Literal["fantasymate.language"] = …, version: Literal[1] = 1, language: Language, parent: str | None = None, description: str = "")`.
  - `schema.language_file_schema() -> dict`, which returns `LanguageFile.model_json_schema()`.
  - `schema.SCHEMA_PATH: Path`, pointing to `language.schema.json`.
  - `Language.word_generator() -> GeneratorDef | None`, the first generator with `use == "words"`.

- [ ] **Step 1: Write the failing tests**

```python
def test_language_file_round_trips():
    lang = Language(name="Moscavian", level="full", flavour="russian",
                    categories={"C": "k v r", "V": "a o"},
                    generators=[GeneratorDef(id="w", name="Words", use="words", patterns=["CVCV"]),
                                GeneratorDef(id="p", name="People", use="character", patterns=["CVC"])])
    f = LanguageFile(language=lang, parent="Old Moscavian")
    again = LanguageFile.model_validate_json(f.model_dump_json())
    assert again == f and again.language.word_generator().id == "w"

def test_generator_use_accepts_kinds_and_forms():
    for use in ("people", "words", "place", "adjective", "demonym"):
        GeneratorDef(id="g", name="g", use=use, patterns=["CV"])

def test_committed_schema_matches_the_model():
    assert json.loads(SCHEMA_PATH.read_text()) == language_file_schema()
```

- [ ] **Step 2: Run them and watch them fail.** Run `uv run --no-sync pytest tests/languages/test_models.py -q`. Expected: an ImportError (`LanguageFile`).
- [ ] **Step 3: Implement the model changes and `schema.py`.** `use` becomes `str` with a validator against the allowed set listed above. Generate `language.schema.json` with a one-off `python -c` that writes `language_file_schema()` with `indent=2`.
- [ ] **Step 4: Run the tests and `tests/languages`.** Expected: PASS, and the 18 generator tests still pass.
- [ ] **Step 5: Commit** with the message `feat(languages): the language file format and its schema`.

### Task 2: The shared check, its repair note and its command

**Files:**
- Create:
  - `src/talemate/languages/check.py`
  - `src/talemate/languages/__main__.py`
  - `src/talemate/languages/data/real_words/russian.txt`, the probe's 251 entries from `docs/superpowers/probes/raw/2026-10-28-language-make-labels.json` `real_words`, one per line
  - `src/talemate/languages/data/real_words/english.txt`, about 300 real English place names, one per line; it must include Thornfield, Ashford, Ravenford, Ashmere, Briarwick and Duskhollow-shaped real towns such as Ashby, Thornbury, Oakham and Blackpool
- Test: `tests/languages/test_check.py`

**Interfaces:**
- Consumes: Task 1's models; `generator.validate_language`, `fits`, `roll`.
- Produces:
  - `CheckReport(BaseModel)` with:
    - `blocking: list[str]`
    - `warnings: list[str]`
    - `fit_share: float | None`, None when skipped
    - `fit_skipped_reason: str | None`
    - `real_hits: list[str]`
    - `real_skipped_reason: str | None`
    - `unfit_words: list[str]`
    - `samples: dict[str, list[str]]`, by generator id
    - `ok -> bool` (no blocking)
  - `check_language(language: Language, *, samples: int = 20, seed: int = 0) -> CheckReport`
  - `repair_note(report: CheckReport) -> str`
  - `needs_repair(report) -> bool`: blocking, or `len(unfit_words) > len(dictionary) / 3`
  - `is_part_style(language) -> bool`: `flavour == "english"`
  - **CLI:** `python -m talemate.languages check FILE` reads the file with `LanguageFile.model_validate_json` (a validation error is reported as blocking), then prints the repair note (or "ok" and the samples). It exits 1 when there is something blocking, else 0. Task 6 switches the reading to `parse_language_text`.

  **The rules** (spec, *My calls*):
  - **Blocking:** an invalid file, or a generator that doesn't parse.
  - **Fit:**
    - checked against the word generator;
    - a word that doesn't fit counts as fitting if it splits into two or more of the language's own dictionary words that each fit;
    - skipped for part styles, and skipped when there's no word generator (with the reason "no word rules");
    - it only ever warns.
  - **Real words:**
    - `russian`: the dictionary and every sample, word by word, with the probe's stemming (`language_probe_metrics._stem`, moved here);
    - part styles: only whole sample names, matched exactly (case-insensitive) against `english.txt`;
    - any other flavour: skipped with the reason "no list for this flavour";
    - it only ever warns.

- [ ] **Step 1: Write the failing tests**

```python
def test_bad_pattern_blocks():
    r = check_language(_lang(reject=["("]))
    assert not r.ok and any("rule" in b for b in r.blocking)

def test_unfit_words_warn_but_do_not_block():
    r = check_language(_lang(words=[("kata","hill"), ("xyzzy","?")]))
    assert r.ok and r.unfit_words == ["xyzzy"] and r.fit_share == 0.5

def test_compound_of_fitting_words_counts_as_fitting():
    r = check_language(_lang(words=[("vel","great"), ("garo","walls"), ("velgaro","great fort")]))
    assert "velgaro" not in r.unfit_words

def test_russian_real_words_warn():
    r = check_language(_lang(flavour="russian", words=[("voda","water")]))
    assert r.ok and "voda" in r.real_hits

def test_part_style_flags_real_place_names_not_parts():
    style = _parts_style(["thorn"], ["field"])       # only ever rolls "Thornfield"
    r = check_language(style)
    assert r.fit_share is None and "Thornfield" in r.real_hits
    assert "thorn" not in r.real_hits

def test_unknown_flavour_skips_real_check():
    r = check_language(_lang(flavour="elvish"))
    assert r.real_skipped_reason and r.real_hits == []

def test_repair_note_lists_blocking_first_in_plain_words():
    note = repair_note(check_language(_lang(reject=["("], words=[("xyzzy","?")])))
    assert note.index("must be fixed") < note.index("xyzzy")
    for term in ("phoneme", "phonotactic", "morpheme"):
        assert term not in note.lower()

def test_cli_exit_codes(tmp_path, capsys):
    good = tmp_path / "g.json"; good.write_text(LanguageFile(language=_lang()).model_dump_json())
    assert main(["check", str(good)]) == 0
```

`_lang(...)` and `_parts_style(...)` are test helpers in the same file.

- [ ] **Step 2: Run them and watch them fail.** Run `uv run --no-sync pytest tests/languages/test_check.py -q`. Expected: an ImportError.
- [ ] **Step 3: Implement `check.py` and `__main__.py`.** Use argparse with one subcommand, `check`. The real-word lists are loaded once from `data/real_words/`. `scripts/dev/language_probe_metrics.py` imports `_stem` from `check.py`, so there's one copy.
- [ ] **Step 4: Run the tests and `tests/dev/test_language_probe_metrics.py`.** Expected: PASS.
- [ ] **Step 5: Commit** with the message `feat(languages): the shared check, repair note and check command`.

### Task 3: The `language` kind and the `languages` field

**Files:**
- Modify:
  - `src/talemate/world/kinds.py` (KINDS, `_SHARED_FIELDS`, `KIND_ORDER`, and the validators in `validate_field`)
  - `src/talemate/world/prose.py:60` (`UNRENDERED_FIELDS`)
  - `tests/world/test_kinds.py:270` (the comment on `test_the_old_structure_is_gone` now says the old `language` *field* is gone, and the `language` *kind* is new)
- Test: `tests/world/test_kinds.py`, `tests/world/test_store.py`

**Interfaces:**
- Produces:
  - **The `language` kind:**
    - fields: `name` (text), `depth` (text: `description`|`naming`|`full`), `flavour` (text), `sound` (text), `rules` (json: `{"categories": {...}, "generators": [...]}`), `words` (json: `[{"word","meaning"}]`), `phrases` (json: `[{"id","category","original","translation"}]`), `parent` (thing), `similar` (json: `[{"target": id, "degree"}]`), plus the shared fields;
    - categories: `["general", "history", "about", "statement", "timeline"]`;
    - placed after `lore` in `KIND_ORDER`.
  - **The shared `languages` field** (json), on every kind: `[{"language": <32-hex>, "role": "spoken"|"official"|"scholarly"|"ceremonial"|"trade"|"liturgical", "share": number 0-100 | null, "fluency": "native"|"fluent"|"broken"|null, "since": date|null, "until": date|null}]`.
    - The validator `_validate_languages` checks the shapes, `share` only on `spoken`, `until > since`, and no exact duplicate rows.
    - `fluency` is allowed on any kind, but only the character UI offers it.
  - **Validators** for `rules` (it must load as `Language(categories=..., generators=...)` and pass `validate_language`), `words`, `phrases` and `similar`.
  - All the new fields go into `UNRENDERED_FIELDS`.
  - `language` is **not** added to `CREATE_KINDS`, `NAME_KINDS` or `groups.ALLOWED_KINDS`. Languages are imported, never written from a prompt.

- [ ] **Step 1: Write the failing tests**

```python
def test_language_kind_fields():
    names = {f.name for f in get_kind("language").fields}
    assert {"depth","flavour","sound","rules","words","phrases","parent","similar","languages"} <= names

def test_languages_field_validates_rows():
    k = get_kind("place")
    validate_field(k, "languages", [{"language": "a"*32, "role": "spoken", "share": 70}])
    for bad in ([{"language": "x", "role": "spoken"}],
                [{"language": "a"*32, "role": "official", "share": 50}],
                [{"language": "a"*32, "role": "sung"}]):
        with pytest.raises(ValueError):
            validate_field(k, "languages", bad)

def test_rules_field_rejects_bad_pattern():
    with pytest.raises(ValueError):
        validate_field(get_kind("language"), "rules",
                       {"categories": {"C": "k"}, "generators": [{"id":"g","name":"g","use":"words","patterns":["CV"],"reject":["("]}]})

def test_language_field_write_is_undoable(world):          # tests/world/test_store.py
    with world.revision(Source.manual()) as rev:
        lid = rev.create_thing("language", {"name": "Moscavian", "words": [{"word":"vel","meaning":"great"}]})
    with world.revision(Source.manual()) as rev:
        rev.set_field(lid, "words", [], None)
    world.undo([world.latest_revision()])
    assert world.view().thing(lid).fields["words"] == [{"word":"vel","meaning":"great"}]
```

Use the store's actual way of naming the latest revision; check `test_undo.py` for the helper.

- [ ] **Step 2: Run them and watch them fail.** Run `uv run --no-sync pytest tests/world/test_kinds.py tests/world/test_store.py -q -k "language"`. Expected: a KeyError for `language`.
- [ ] **Step 3: Implement the kind, the field and the validators** in `kinds.py`.
- [ ] **Step 4: Run all of `tests/world` and `tests/worldplay`.** Expected: PASS. Any test that asserts exact kind lists is updated to include `language`.
- [ ] **Step 5: Commit** with the message `feat(world): the language kind and the languages field`.

### Task 4: An entry as a language, and which words are used

**Files:**
- Create: `src/talemate/languages/entry.py`
- Test: `tests/languages/test_entry.py`

**Interfaces:**
- Consumes: Tasks 1 and 3; `WorldView.thing`, `WorldView.things`.
- Produces:
  - `language_of(state: ThingState) -> Language`: builds a `Language` from a `language` entry's fields. `level` comes from `depth`, defaulting to `naming`. `similar` comes back as names.
  - `fields_of(language: Language) -> dict[str, object]`: the entry fields for a `Language`. `name` is kept out; the caller sets it.
  - `used_words(view: WorldView, language_id: str) -> set[str]`: the language's dictionary words (lower-case) that occur as a whole word in the name or any `aka` name of a live entry, stubs included.
  - `languages(view) -> list[ThingState]`: the live `language` entries.

- [ ] **Step 1: Write the failing tests**

```python
def test_entry_round_trip(world):
    lang = _moscavian()
    with world.revision(Source.manual()) as rev:
        lid = rev.create_thing("language", {"name": lang.name, **fields_of(lang)})
    assert language_of(world.view().thing(lid)).model_dump() == lang.model_dump()

def test_used_words_from_names_and_aka(world):
    lid = _store(world, _moscavian(words=[("velgarov","great fort"), ("sorau","free land"), ("kata","hill")]))
    with world.revision(Source.manual()) as rev:
        rev.create_thing("place", {"name": "Velgarov"})
        rev.create_thing("place", {"name": "Free Provinces of Sorau",
                                   "aka": [{"name": "Kata Sorau", "tag": "proper", "everyday": False}]})
    assert used_words(world.view(), lid) == {"velgarov", "sorau", "kata"}
```

- [ ] **Step 2: Run them and watch them fail.** Run `uv run --no-sync pytest tests/languages/test_entry.py -q`. Expected: an ImportError.
- [ ] **Step 3: Implement `entry.py`.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** with the message `feat(languages): language entries and used words`.

### Task 5: Which languages apply to an entry

**Files:**
- Create: `src/talemate/languages/lookup.py`
- Test: `tests/languages/test_lookup.py`

**Interfaces:**
- Consumes: `filing.filings_of(view, thing_id, live=True)`; Task 3's field.
- Produces:
  - `LanguageRow(BaseModel)`: `language_id: str, name: str, role: str, share: float | None, fluency: str | None, source_id: str` (the entry that states it), `inherited: bool`.
  - `languages_for(view: WorldView, thing_id: str) -> list[LanguageRow]`. The rules (main spec):
    - The entry's own live rows, if any. A row is live when its `since`/`until` cover `view.at`; at the latest telling, when `until` is None.
    - Otherwise, walk its live filings, each one separately and depth-first. Visit each entry once, and stop each branch at the first entry that states rows. Return the union, without duplicate `(language_id, role)`, marked `inherited=True`.
    - **Characters:** follow only filings whose target's kind is `place`, and keep only `spoken` and `official` rows.
    - Skip rows whose language entry is missing or removed.
  - `default_language(rows: list[LanguageRow]) -> str | None`: the official row first, else the `spoken` row with the largest share, else the first row.
  - `languages_for_scene(view, place_id: str | None, speaker_id: str | None) -> list[LanguageRow]`: the speaker's languages first, then the place's, without duplicates. Task 12 uses it.

- [ ] **Step 1: Write the failing tests**

```python
def test_own_rows_win(lang_world): ...                      # Sorau states Sorauan official, Moscavian 25%
def test_inherits_from_filed_place(lang_world):
    rows = languages_for(v, ids["Thornfield"])               # filed in Sorau, states none
    assert {r.name for r in rows} == {"Sorauan", "Moscavian"} and all(r.inherited for r in rows)
def test_character_takes_places_only_and_spoken_official(lang_world): ...  # filed in Sorau and the Owl Synod (liturgical Old Moscavian) -> no Old Moscavian
def test_dated_rows(lang_world): ...                         # official Moscavian until 1412, Sorauan since: view at 1400 vs 1500
def test_lookup_survives_a_filing_cycle(lang_world): ...     # Review Focus 1
def test_lookup_skips_deleted_language(lang_world): ...      # Review Focus 2
def test_default_language_order():
    assert default_language([_row("a","spoken",25), _row("b","official",None)]) == "b"
    assert default_language([_row("a","spoken",25), _row("c","spoken",70)]) == "c"
```

The fixture `lang_world` (in `tests/languages/conftest.py`) builds Moscavian, Sorauan, Old Moscavian, Sorau (place), Thornfield (place filed in Sorau), the Owl Synod (lore), and Mira (a character filed in Sorau and in the Owl Synod). The cycle test writes the filings through the store's undo of a removal, or directly through `field_values` if the store refuses; read `test_filing.py` for how cycles are made there.

- [ ] **Step 2: Run them and watch them fail.** Run `uv run --no-sync pytest tests/languages/test_lookup.py -q`. Expected: an ImportError.
- [ ] **Step 3: Implement `lookup.py`.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** with the message `feat(languages): which languages apply to an entry`.

### Task 6: Import, diff and the server handlers for languages

**Files:**
- Create: `src/talemate/languages/importer.py`
- Modify: `src/talemate/server/worlds.py` (new payloads and handlers next to `handle_set_field`, around L5366)
- Test: `tests/languages/test_importer.py`, `tests/server/test_worlds_languages.py`

**Interfaces:**
- Consumes: Tasks 1, 2 and 4; `probe_fact_roundtrip._extract_json`'s approach (reimplement it in `importer.py`; don't import from `scripts/`).
- Produces:
  - `parse_language_text(text: str) -> LanguageFile`. It takes:
    - a whole file;
    - a pasted reply with prose or a fenced block around it (the first balanced JSON object that validates as `LanguageFile`, else as a bare `Language`, which gets wrapped).

    It raises `LanguageParseError(str)` with a plain message.
  - `LanguageDiff(BaseModel)`:
    - `words_added`, `words_removed`, `words_changed: list[str]`
    - `phrases_added`, `phrases_removed`, `phrases_changed: list[str]`
    - `generators_changed: bool`
    - `kept_used: list[str]` (used words the new version dropped or changed, put back)
    - `samples_before`, `samples_after: dict[str, list[str]]`
  - `ImportPreview(BaseModel)`: `file: LanguageFile, report: CheckReport, diff: LanguageDiff | None`.
  - `preview_import(view, text: str, target_id: str | None = None) -> ImportPreview`
  - `apply_import(rev, view, preview: ImportPreview, target_id: str | None = None) -> str`:
    - refuses (ValueError) when `not preview.report.ok`;
    - creates a `language` entry or updates `target_id`;
    - resolves `parent` and `similar` names to existing language entries by name, and leaves out names that don't exist;
    - puts back the used words;
    - returns the id.
  - `export_language(view, language_id) -> LanguageFile`, for "export" and for 3b's briefs.
  - The CLI from Task 2 now reads its file with `parse_language_text`, so a reply saved with prose around it checks too. Test: `test_cli_reads_wrapped_text`.
  - **Server handlers** (each payload subclasses `_ThingEdit` where it acts on a thing):
    - `handle_language_preview(data)`: `{text, target_id?}` → reply `language_preview` with `ImportPreview.model_dump()` and `repair_note`.
    - `handle_language_import(data)`: `{text, target_id?}`, in one revision → `self._edited("language_import", id, at, prose=False)`.
    - `handle_language_export(data)`: `{thing_id}` → reply `language_export` with the file JSON.
    - `handle_language_samples(data)`: `{thing_id, seed}` → reply `language_samples` with `{generator_id: names}`.
    - Editing words, phrases, flavour and `languages` rows uses the existing `handle_set_field`. Check that none of these fields are in `GUARDED_FIELDS`.

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_accepts_fenced_and_wrapped_text():           # Review Focus 3
    body = LanguageFile(language=_moscavian()).model_dump_json()
    for text in (body, f"Here you go:\n```json\n{body}\n```\nEnjoy!", _moscavian().model_dump_json()):
        assert parse_language_text(text).language.name == "Moscavian"

def test_parse_error_is_plain():
    with pytest.raises(LanguageParseError, match="no language"):
        parse_language_text("sorry, I can't")

def test_import_creates_entry_and_links_parent(world): ...   # Old Moscavian exists; file says parent "Old Moscavian"
def test_import_refuses_blocking(world): ...
def test_revision_keeps_used_words(world):                   # Review Focus 4
    # Velgarov exists as a place; new version drops "velgarov" and changes "sorau"'s meaning
    p = preview_import(view, new_text, target_id=lid)
    assert set(p.diff.kept_used) == {"velgarov", "sorau"}
    # after apply, both words are back with their old meanings
def test_diff_lists_changes(world): ...

async def test_language_preview_and_import_handlers(worlds_plugin): ...  # tests/server: preview reply carries report + repair_note; import creates the thing
```

Model the server test on an existing one in `tests/server/` that drives `WorldsPlugin` handlers; find it with `grep -rln "WorldsPlugin" tests/server`.

- [ ] **Step 2: Run them and watch them fail.** Run `uv run --no-sync pytest tests/languages/test_importer.py tests/server/test_worlds_languages.py -q`. Expected: an ImportError.
- [ ] **Step 3: Implement `importer.py` and the handlers.**
- [ ] **Step 4: Run the tests and the server tests folder.** Expected: PASS.
- [ ] **Step 5: Commit** with the message `feat(languages): import, export and diffs, with worlds handlers`.

### Task 7: Naming: rolling, defining, adding words, names in other languages

**Files:**
- Create:
  - `src/talemate/languages/naming.py`
  - `src/talemate/prompts/templates/world/language-define.jinja2`
  - `src/talemate/prompts/templates/world/language-pick.jinja2`
- Modify:
  - `src/talemate/world/kinds.py` (`_validate_aka` accepts an optional `language: <32-hex>` key)
  - `talemate_frontend/src/components/worlds/draftPage.js` (`akaEntry` keeps `language` when present)
  - `src/talemate/worldplay/links.py:552-554` (keep `language` when rebuilding aka entries)
  - `src/talemate/server/worlds.py` (handlers)
- Test: `tests/languages/test_naming.py`, `tests/world/test_kinds.py`, `tests/server/test_worlds_languages.py`

**Interfaces:**
- Consumes: Tasks 1, 4, 5 and 6; `worldplay.ai.world_ai_call`; `Prompt.request(uid, client, kind, vars=...)`; `WorldsPlugin._client()`.
- Produces:
  - `generator_for(language: Language, kind: str) -> GeneratorDef`. Its order:
    1. a generator whose `use == kind`;
    2. the bucket (`character`/`being` → `people`; `place` → `places`; anything else → `things`);
    3. `places`;
    4. the first generator that isn't a `words` generator.

    It raises `ValueError("this language has no name rules")` only when there are none.
  - `roll_names(language, kind: str, count: int = 4, seed: int | None = None, exclude=frozenset()) -> list[str]`: excludes names already used in the world.
  - `async define(client, language: Language, names: list[str], context: str = "") -> dict[str, str]`: one call to `world.language-define`, giving one plain sentence per name. A name the reply misses gets `""`.
  - `async pick(client, language, candidates: list[str], what: str) -> tuple[str, str]`: `world.language-pick` returns the name and why. A pick that isn't among the candidates falls back to the first candidate.
  - `add_word(rev, view, language_id: str, word: str, meaning: str) -> None`: appends to `words`, replacing the same word's entry. A used word's meaning isn't changed (the existing meaning is kept).
  - `async name_in(view, client, thing_id: str, language_id: str) -> NameInResult(name: str, new_words: list[{"word","meaning"}])`:
    - each English word of the entry's name whose meaning is in the dictionary (a whole-word match on `meaning`, case-insensitive) is translated with it;
    - each word with no match gets 8 candidates rolled from the word generator; `pick` chooses one; `define` gives its meaning (the English word);
    - words that are already language words (a dictionary hit on `word`) stay as they are.
  - `apply_name_in(rev, view, thing_id, language_id, result) -> None`: adds the aka `{"name": result.name, "tag": "proper", "everyday": False, "language": language_id}` and the new words.
  - **Handlers:**
    - `handle_language_names(data)`: `{thing_id?, language_id, kind, count, seed}`; spawns roll + define; replies `language_names` with `[{"name","definition"}]`.
    - `handle_language_add_word(data)`: `{language_id, word, meaning}`; an edit; replies through `_edited`.
    - `handle_language_suggest_definition(data)`: `{language_id, word, context}`; replies `language_definition`.
    - `handle_language_name_in(data)`: `{thing_id, language_id}`; replies `language_name_in` with the result for review.
    - `handle_language_apply_name_in(data)`: `{thing_id, language_id, result}`; an edit.
    - `handle_language_menu(data)`: `{thing_id?}`; replies `language_menu` with `languages_for` rows plus `default_language` and all languages, so the menu can offer a picker.
  - **Phrases (*My call*, ruled here):** *Make a phrase…* offers the language's own phrases by category. New phrases come from the outside routes, in 3b's "more words/phrases" brief. The local model doesn't write phrases (probe 1: it can't write the language's words).

- [ ] **Step 1: Write the failing tests**

```python
def test_generator_for_kind_falls_back():                    # Review Focus 5
    lang = _lang(gens={"people": "people", "places": "places"})
    assert generator_for(lang, "item").id == "places"
    assert generator_for(lang, "character").id == "people"

def test_roll_names_excludes_used(world): ...
async def test_define_uses_one_call_and_fills_missing(stub_client): ...   # stub replies for 3 of 4 names
async def test_pick_falls_back_to_first_candidate(stub_client): ...
def test_add_word_keeps_used_meaning(world): ...
async def test_name_in_translates_known_and_rolls_missing(world, stub_client):
    # dictionary has ("svoven", "free"); name "Free Provinces of Sorau"; stub picks "karaj" for "provinces"
    r = await name_in(view, stub_client, sorau_id, mosc_id)
    assert r.name == "Svoven Karaj Sorau" and {"word": "karaj", "meaning": "provinces"} in r.new_words
def test_aka_accepts_language_key(): ...
```

`stub_client` follows how `tests/worldplay` stubs `Prompt.request` (find the existing fixture with `grep -rn "def .*client" tests/worldplay/conftest.py`).

- [ ] **Step 2: Run them and watch them fail.** Run `uv run --no-sync pytest tests/languages/test_naming.py -q`. Expected: an ImportError.
- [ ] **Step 3: Implement `naming.py`, the two templates (AsIsExtractor; plain-language task text; JSON replies) and the handlers.**
- [ ] **Step 4: Run the tests, `tests/world`, `tests/worldplay` and `tests/server`.** Expected: PASS.
- [ ] **Step 5: Commit** with the message `feat(languages): naming, definitions and names in other languages`.

### Task 8: The language-design skill

**Files:**
- Move: `.claude/skills/culture-design/` → `.claude/skills/language-design/` (with `git mv`), then rewrite `SKILL.md`
- Test: manual (Step 3)

**Interfaces:**
- Consumes: Task 1's schema (`src/talemate/languages/language.schema.json`) and Task 2's CLI.
- Produces: a skill whose `description` triggers on designing or revising a language or naming style for a fantasymate world. It covers the three jobs (a new language; a daughter, from a parent file plus drift; a revision, from the current file plus a request), and in each:
  - asks plain questions only when the request leaves them open;
  - never uses real words of the flavour's real language;
  - always includes a `words` generator for full languages;
  - writes `<name>.language.json` to the schema;
  - runs `guix shell -m manifest.scm -- uv run --no-sync python -m talemate.languages check <file>` (or `python -m talemate.languages check` where there's no guix) and fixes the file until it exits 0, with no more than a third of the words flagged as not fitting;
  - ends by telling the user to import it with **Import language** in the World tab.

- [ ] **Step 1: Rewrite `SKILL.md`.** Keep the old skill's plain-questions guidance and drop its culture parts.
- [ ] **Step 2: Remove the old skill's culture references.** Run `grep -rn -i "culture" .claude/skills/language-design`. Expected: no output.
- [ ] **Step 3: Check the skill by hand.** In a scratch folder, follow the skill to write a tiny naming style. Run the check command and confirm exit 0 and plain output. Save the file as `tests/languages/data/sample.language.json`, which Tasks 9–11 use as a fixture.
- [ ] **Step 4: Commit** with the message `feat(languages): the language-design skill`.

### Task 9: The language page and importing (UI)

**Files:**
- Create in `talemate_frontend/src/components/worlds/`:
  - `LanguageSections.vue` (the technical sections of a language page)
  - `LanguageImport.vue` (the file/paste box, preview and accept)
  - `LanguageCheckReport.vue` (the report, in plain words, with the repair note and a "Copy note" button)
- Modify:
  - `worldKinds.js` (a `language` entry in `WORLD_KINDS`, `icon: 'mdi-alphabetical-variant'`, `LISTED_KINDS`, `TOP_KINDS`; not in `STUB_KINDS`)
  - `worldTree.js` L9 (`KIND_ORDER`)
  - `ThingPage.vue` (`HIDDEN_FIELDS` gains the new fields and `languages`; `<LanguageSections v-if="thing.kind === 'language'">` under the facts)
  - `KindList.vue` / `WorldTab.vue` (the language kind's page shows `LanguageImport` where other kinds show their prompt box)
  - `stores/worlds.js` (`previewLanguage`, `importLanguage`, `exportLanguage`, `languageSamples`, and their `handleMessage` cases)
- Test:
  - `tests/e2e/worlds/test_languages_page.py`
  - `talemate_frontend/checks/worlds.check.mjs` (add `language` to the kind checks)

**Interfaces:**
- Consumes: Task 6's handlers and reply actions (`language_preview`, `language_export`, `language_samples`).
- Produces: the store actions named above, and a page layout that Tasks 10 and 11 add to.
  - **The page, in order** (spec, *My call*): how it sounds (editable text); about 20 sample names with ⟳ Reroll; the words (a searchable table, word and meaning, each row editable, with add and remove); the phrases (by category); the generators (read-only text, with an *Advanced edit* JSON box that runs the check before saving); flavour and depth (small selects in the section header); then *Export language*.
  - **The import:** paste or choose a file → preview: name, depth, flavour, word and phrase counts, samples, and the check report → *Import* (disabled when there's something blocking). On an existing language, *Import a new version* shows the diff (added, removed, changed, and "kept because it's used: …").

- [ ] **Step 1: Write the failing e2e tests**

```python
def test_import_pasted_language_and_see_its_page(app, page):
    # paste tests/languages/data/sample.language.json wrapped in prose -> preview shows samples -> Import -> page has Words table with its words
def test_blocking_problem_disables_import(app, page):
    # paste a file with reject ["("] -> report shows "must be fixed" -> Import disabled; Copy note copies text
def test_new_version_shows_kept_used_words(app, page):
    # seeded language + place named with one of its words; import a version without that word -> diff lists it as kept
```

Use `seed_fm_world` (with a `language` thing whose fields come from the sample file), `_open_world`, `_world_tab` and `_open_thing`.

- [ ] **Step 2: Run them and watch them fail.** Run `pytest tests/e2e/worlds/test_languages_page.py -m e2e -n 1`. Expected: FAIL, the elements are missing.
- [ ] **Step 3: Build the components,** taking a screenshot after each visible change and showing it to the owner. Rework them from the owner's feedback until approved.
- [ ] **Step 4: Run the tests, the node checks and the worlds e2e folder.** Expected: PASS.
- [ ] **Step 5: Commit** with the message `feat(worlds-ui): the language page and importing a language`.

### Task 10: Languages sections on entries (UI)

**Files:**
- Create in `talemate_frontend/src/components/worlds/`:
  - `EntryLanguages.vue` (the section: own rows, or the inherited line with *Set its own*)
  - `LanguageLinks.vue` (on a language page: parent and similar links)
- Modify:
  - `ThingPage.vue` (`<EntryLanguages>` after `<EntryIn>`, on every kind except `language`, which gets `<LanguageLinks>`)
  - `stores/worlds.js` (`languagesFor(thingId)` → `language_menu`; `setLanguages(rows)` → `setField('languages', rows)`)
  - `src/talemate/server/worlds.py`: `_thing_payload` gains `languages_view: list[LanguageRow]` from `languages_for`, so the page shows inherited rows without another request
- Test: `tests/e2e/worlds/test_languages_section.py`, `tests/server/test_worlds_languages.py`

**Interfaces:**
- Consumes: Task 5's `languages_for` and `LanguageRow`.
- Produces: `EntryLanguages`, following the approved mockup's right-hand panel:
  - rows of language / role chip / a share bar with % for spoken / fluency for characters;
  - *+ Add* sits right after the heading (owner's rule);
  - each row's dates are editable in the row's menu, as filings' dates are;
  - inherited rows show as one muted line, "From <source>: …", with *Set its own*, which copies them in as the entry's own rows;
  - a deleted language shows as "(deleted language)" (Review Focus 2).

- [ ] **Step 1: Write the failing tests**

```python
async def test_thing_payload_includes_languages_view(...): ...   # server: Thornfield payload carries inherited rows from Sorau
def test_add_language_row_and_share(app, page): ...              # Sorau: + Add -> Sorauan, official; + Add -> Moscavian, spoken 25
def test_inherited_line_and_set_its_own(app, page): ...          # Thornfield shows "From Free Provinces of Sorau: …"; Set its own -> own rows
def test_character_fluency(app, page): ...                       # Mira: Sorauan native
```

- [ ] **Step 2: Run them and watch them fail.**
- [ ] **Step 3: Build them,** with screenshots compared to `naming-flow.html` panel 2, and the owner's feedback.
- [ ] **Step 4: Run the tests, the node checks, `tests/server` and the worlds e2e folder.** Expected: PASS.
- [ ] **Step 5: Commit** with the message `feat(worlds-ui): Languages sections on entries`.

### Task 11: Right-click naming in the worlds screens (UI)

**Files:**
- Create in `talemate_frontend/src/components/worlds/`:
  - `LanguageNameMenu.vue` (the "Make a name ▸" candidates list, "Make a phrase…", "Add 'X' to …", "Reroll this part ▸", and the language picker)
  - `languageMenu.js` (pure helpers: the default language, building the menu state, replacing a selection; node-checked)
- Modify:
  - `ReferenceMenu.vue` (new items that hand off to `LanguageNameMenu`; the existing items are unchanged)
  - `NameHighlightInput.vue` (a new prop `contextThingId: String|null`; uses `insertAt` for picks)
  - every user of `NameHighlightInput` passes `contextThingId`: the page's thing in `EntryAddFacts`, `EntryIn`, `ThingFactForm` and `GroupAddForm`; `null` in `CreateBox` and `NewSceneDialog`; the suggested thing in `SuggestionBar`
  - `ThingAka.vue` (a "Name it in ▸" item per entry; language chips on aka entries that carry `language`)
  - `stores/worlds.js` (`languageMenu`, `languageNames`, `addLanguageWord`, `suggestDefinition`, `nameIn`, `applyNameIn`)
- Test:
  - `talemate_frontend/checks/languageMenu.check.mjs` (plus its wrapper in `tests/dev/test_frontend_checks.py`)
  - `tests/e2e/worlds/test_language_naming.py`

**Interfaces:**
- Consumes: Task 7's handlers (`language_menu`, `language_names`, `language_add_word`, `language_definition`, `language_name_in`, `language_apply_name_in`).
- Produces: the menu as in `naming-flow.html` panel 1.
  - With no selection: *Make a name ▸* shows 4 candidates, each with its definition, plus *⟳ Reroll* and *More like <name>*. Clicking one inserts it at the caret and saves it as a word with its definition.
  - With a selection: *Add "<sel>" to <language>…* (a definition field pre-filled by `suggestDefinition`, editable, then Save) and *Reroll this part ▸* (candidates replace only the selection).
  - The language picker defaults to `default_language`. With nothing in reach it asks for a language and offers "Save on this page", which adds a `spoken` row.
  - The kind used for rolling is the page's kind, or the `CreateBox`'s kind.

- [ ] **Step 1: Write the failing tests**

```js
// languageMenu.check.mjs
check('replace_selection_keeps_the_rest', () => {
    assert.equal(replaceSelection('Free Provinces of Sorau', [19, 24], 'Velka'), 'Free Provinces of Velka');
});
check('default_language_prefers_official', () => { /* mirrors Task 5 */ });
```

```python
def test_make_a_name_inserts_and_saves_word(app, page): ...       # fixed reply for definitions; Tsardom of | -> pick -> text and words table
def test_add_selected_word_with_definition(app, page): ...
def test_reroll_this_part(app, page): ...
def test_nothing_in_reach_offers_save_on_page(app, page): ...
def test_name_it_in_other_language(app, page): ...                # Sorau -> Name it in Moscavian -> aka chip with language
```

The definition and pick calls use the e2e fixed-reply mechanism (`set_fixed_reply`; follow how `test_drafts.py` fixes model replies).

- [ ] **Step 2: Run them and watch them fail.**
- [ ] **Step 3: Build it,** with screenshots against `naming-flow.html`, and the owner's feedback.
- [ ] **Step 4: Run the tests, the node checks, `grep -rn` of `tests/ai` for any changed selector, and the full e2e suite.** Expected: PASS.
- [ ] **Step 5: Commit** with the message `feat(worlds-ui): right-click naming from a language`.

### Task 12: Right-click naming in the scene's message box (UI)

**Files:**
- Modify:
  - `talemate_frontend/src/components/SceneMessageInput.vue` (`@contextmenu` on the `v-textarea`, opening `ReferenceMenu` with only the language items and the edit items, and no *Add reference*)
  - `src/talemate/server/worlds.py`: `handle_language_menu` accepts `{scene: true}` and resolves the place and the speaker from the active world scene (`scene.world_context`: read `worldplay/context.py` for the record's place and player character ids), using `languages_for_scene`
- Test: `tests/server/test_worlds_languages.py`, `tests/e2e/worlds/test_language_naming.py` (a scene case)

**Interfaces:**
- Consumes: Task 5's `languages_for_scene`; Task 11's `LanguageNameMenu`.
- Produces: in a world scene, right-click in the message box offers *Make a name* / *Make a phrase…* with the speaking character's languages first. In a scene with no world, the menu shows only the edit items.

- [ ] **Step 1: Write the failing tests:** `test_scene_menu_uses_speaker_then_place` (server) and `test_scene_box_make_a_phrase` (e2e; seed a world scene with `seed_fm_world(scenes=[...])`).
- [ ] **Step 2: Run them and watch them fail.**
- [ ] **Step 3: Build it,** with screenshots.
- [ ] **Step 4: Run the tests and the full e2e suite.** Expected: PASS.
- [ ] **Step 5: Commit** with the message `feat(scene-ui): right-click naming in the message box`.

### Task 13: Acceptance

**Files:**
- Create: `docs/superpowers/probes/<acceptance date>-languages-3a-acceptance.md`, dated the day the owner walks it

- [ ] **Step 1: Write the owner's acceptance checklist,** in the shape of `docs/superpowers/probes/2026-10-27-polish-4-acceptance.md`. One checkbox per picture and behaviour:
  - make Moscavian with the skill, and import it by pasting;
  - its page, samples and words;
  - Sorau's Languages section;
  - Thornfield inheriting;
  - "Tsardom of" → Make a name;
  - adding Moscavia as a word;
  - Reroll this part;
  - Free Provinces of Sorau named in Moscavian;
  - a new version keeping used words;
  - the scene box.
- [ ] **Step 2: Start the isolated app and walk the list with the owner.** Run `scripts/dev/talemate_app.py start`. The owner's AI client is only used after "ready for AI testing?". Record the owner's results and notes in the file.
- [ ] **Step 3: Commit** with the message `docs(languages): 3a acceptance`.
