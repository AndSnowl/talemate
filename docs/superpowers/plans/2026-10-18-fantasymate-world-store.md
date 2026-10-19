# World Store (Phases 0 and 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the fact round-trip probe against the owner's local model (phase 0). Then build the world store (phase 1): a per-world SQLite database of things that have stable ids, core-field timelines, dated facts, references by id, source stamps on both clocks, undo by source, and a derived search index.

**Architecture:**
- **Phase 0** is a throwaway script in `scripts/dev/`. It talks to koboldcpp over HTTP and writes a report. A pure metrics module beside it is unit-tested.
- **Phase 1** is a new, self-contained package, `src/talemate/world/`. It is not wired into scenes, agents or the UI yet; phase 2 does that.
- **Every write happens inside a revision.** A revision is one numbered, source-stamped batch.
- **Rows are never updated in place.** A row is added at a revision and retired at a later one. Reading the world "at story date D as of revision R" is therefore one filter on both clocks.

**Tech stack:** Python 3.11+, stdlib `sqlite3`, pydantic 2, `isodate` (already a dependency), chromadb (already a dependency), pytest with `asyncio_mode = "auto"`.

**Spec:** `docs/superpowers/specs/2026-10-18-fantasymate-world-data-model-design.md`

## Global Constraints

- **Running things on Guix.** Run everything through `guix shell -m manifest.scm -- …` from the repo root, and always use `uv run --no-sync` (plain `uv run` removes pytest). Ruff comes from the manifest. About 141 failures in the plain suite are environment-only (NLTK `punkt_tab`), and they are not regressions.
- **Live-model probes need the owner's go-ahead.** Phase 0 calls the owner's koboldcpp. Running it requires `TALEMATE_AI_TESTS=1` and the owner's explicit go-ahead. Its unit tests never touch the network.
- **Only `tests/ai` may call a real model.** Every new test in the plain suite stays network-free.
- **Hard fork.** Phase 1 doesn't touch existing scene, character, shared-context or culture code. The package stands alone.
- **One world is one folder:**
  - `worlds/<world-id>/world.sqlite` is the database;
  - `worlds/<world-id>/assets/` holds images and other files;
  - `worlds/<world-id>/index/` holds the derived search index.
  - `WORLDS_DIR = TALEMATE_ROOT / "worlds"`.
- **Ids are `uuid4().hex`** (32 characters), never reused.
- **The default calendar uses Earth lengths.**
  - Durations are added with `datetime + isodate.parse_duration(...)`, so P1M moves one calendar month. That's my call; Talemate's own helper approximates a month as 30 days.
  - Dates are proleptic Gregorian, so world years run 1–9999, and eras map them to displayed years.
- **References inside fact text** are written `[[thing:<32-hex-id>]]` and rendered with the referenced thing's name on the viewing date.
- **Conventions:** tests use the `tests/` layout and stdlib `tmp_path`, and code follows the repo's style of module docstrings and `structlog` loggers named `talemate.world.<module>`.

## Review Focus

These are the inputs most likely to bite a real user. Each one has a pinning test in the task that owns the code.

1. **A fact with an open start ("always") viewed at an early date** should be visible. Pinned in Task 6: `test_open_start_fact_visible_before_any_date`.
2. **Two field values on the same date** should not both exist: setting the second one is a correction that replaces the first. Pinned in Task 5: `test_set_field_same_date_replaces`.
3. **A reference to a thing that is later renamed** should show the name valid on the viewing date, and a reference to an unknown id should render as `⟨unknown⟩` rather than crash. Pinned in Task 6: `test_render_uses_name_at_date` and `test_render_unknown_reference`.
4. **Undoing a revision whose fact was edited again by a later revision** should leave that fact alone and list it as a conflict. Pinned in Task 8: `test_undo_lists_later_edited_rows`.
5. **A failed write mid-revision** (for example a validation error on the third change) should leave nothing behind: no revision row and no partial changes. Pinned in Task 5: `test_failed_revision_rolls_back`.

---

## Phase 0: the round-trip probe

### Task 1: Probe metrics

This module holds pure functions only, for summarising and rendering a probe run. It follows the pattern of `scripts/dev/cultures_eval_metrics.py`.

**Files:**
- Create: `scripts/dev/fact_probe_metrics.py`
- Test: `tests/dev/test_fact_probe_metrics.py` (load the module with `importlib.util.spec_from_file_location` the way `tests/dev/test_ai_helpers.py` does)

**Interfaces:**
- Produces:
  - **The raw results dict:**
    ```
    {"model": str, "started": str, "finished": str,
     "samples": [{"name": str,
                  "rounds": [{"facts": [{"category": str, "text": str}],
                              "prose": str,
                              "invented": [str],
                              "dropped": [str]}]}],
     "errors": [{"sample": str, "round": int, "step": str, "error": str}]}
    ```
    Round 0's `facts` come from the source description; round N's come from round N−1's prose. `invented` lists prose claims with no backing in that round's facts. `dropped` lists facts the prose left out.
  - **`summarise(results: dict) -> dict`** returns, per sample:
    - `facts_per_round: list[int]`;
    - `invented_per_round: list[int]`;
    - `dropped_per_round: list[int]`;
    - `drift: float`, the share of round-0 facts with no match in the last round, by case-insensitive exact text after whitespace normalisation.

    It also returns `totals` with the same counts summed over samples.
  - **`render_markdown(results: dict, summary: dict) -> str`** returns a plain-language report: a header naming the model, one table per sample (round, facts, invented, dropped), every invented claim listed verbatim, and an errors section only when there are errors.

- [ ] **Step 1: Write the failing tests**
  - `test_summarise_counts_per_round`: two samples with known round lists give the expected `facts_per_round`, `invented_per_round` and `dropped_per_round`, and `totals` adds them up.
  - `test_drift_ignores_case_and_whitespace`: round-0 fact `"Has a  heron tattoo"` against last-round fact `"has a heron tattoo"` gives `drift == 0.0`. Removing it gives `drift == 1.0` for a one-fact sample.
  - `test_render_lists_invented_claims_verbatim`: the rendered report contains each invented string, and contains `"Errors"` only when `results["errors"]` is non-empty.
- [ ] **Step 2: Run them to make sure they fail**
  Run: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/dev/test_fact_probe_metrics.py -v -n0`
  Expected: FAIL (module missing).
- [ ] **Step 3: Implement `summarise` and `render_markdown`** in `scripts/dev/fact_probe_metrics.py`.
- [ ] **Step 4: Run the tests to make sure they pass** with the same command. Expected: PASS.
- [ ] **Step 5: Commit** with the message `test(probe): fact round-trip metrics`.

### Task 2: Probe script

**Files:**
- Create: `scripts/dev/probe_fact_roundtrip.py`
- Create: `scripts/dev/probe_data/characters.json`. Four source descriptions, each `{"name", "text"}`:
  1. a short one-liner;
  2. a three-paragraph prose description;
  3. a pasted character-card-style block with `Personality:` and `Appearance:` headings;
  4. a character whose description contains exact wording to preserve ("a puckered scar").
- Test: `tests/dev/test_probe_fact_roundtrip.py`

**Interfaces:**
- Consumes:
  - `fact_probe_metrics.summarise` and `render_markdown` (Task 1);
  - `ai_helpers.koboldcpp_url()` and `koboldcpp_model(url)`.
- Produces: a CLI that writes `report.json` and `report.md` into `--out`, which defaults to `.test-artifacts/fact-probe-<stamp>/`. Both files are rewritten after every step.

These are the script's functions:
- **`chat(url: str, system: str, user: str, *, max_tokens: int = 1024, timeout: float = 600) -> str`**
  - Sends a POST to `<url>/v1/chat/completions`, koboldcpp's OpenAI-compatible endpoint, with `temperature` 0.7, using stdlib `urllib`.
  - Returns `choices[0].message.content` with any `<think>…</think>` block stripped.
- **`extract_facts(url, text: str) -> list[dict]`**
  - Prompts the model to return only a JSON list of `{"category", "text"}`, with category one of `appearance, personality, background, ability, relationship, speech`.
  - Parses the first JSON array in the reply.
  - Raises `ValueError` on unparsable output, and the caller records that as an error.
- **`write_prose(url, facts: list[dict]) -> str`**: one paragraph per category present, using only the given facts and keeping their exact wording where natural.
- **`check_prose(url, facts, prose) -> tuple[list[str], list[str]]`**
  - Asks the model to return JSON `{"invented": [...], "dropped": [...]}`.
  - `invented` lists claims in the prose that no fact supports; `dropped` lists facts the prose omits.
- **`run_sample(url, sample: dict, rounds: int) -> dict`**: extract, then (prose, check, re-extract) `rounds` times.
- **`main(argv=None) -> int`**
  - Arguments: `--rounds` (default 3), `--samples PATH`, `--out DIR`.
  - Exits with code 2 and a one-line message unless `TALEMATE_AI_TESTS=1`.
  - Exits with code 3 when `koboldcpp_model(url)` returns `None`.

- [ ] **Step 1: Write the failing tests.** Use a local stub HTTP server, as in `tests/dev/test_ai_helpers.py`. It answers `/api/v1/model`, and answers `/v1/chat/completions` with canned replies chosen by a keyword in the system prompt.
  - `test_main_refuses_without_opt_in`: with `TALEMATE_AI_TESTS` unset, the return code is 2 and nothing is written.
  - `test_run_sample_against_stub`: two rounds give `len(rounds) == 3`, round 0 has the stub's facts, and `invented` comes from the stub's check reply.
  - `test_unparsable_facts_recorded_as_error`: a stub reply of `"sorry"` to extraction puts one entry in `results["errors"]` with `step == "extract"`, and the run continues with the next sample.
  - `test_think_block_stripped`: a reply of `"<think>x</think>[...]"` parses.
- [ ] **Step 2: Run them to make sure they fail**
  Run: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/dev/test_probe_fact_roundtrip.py -v -n0`
  Expected: FAIL.
- [ ] **Step 3: Implement the script and write `characters.json`.**
- [ ] **Step 4: Run the tests to make sure they pass** with the same command. Expected: PASS.
- [ ] **Step 5: Commit** with the message `feat(probe): fact round-trip probe script`.

### Task 3: Run the probe (owner-gated)

- [ ] **Step 1: Ask the owner** for permission to run the probe against koboldcpp. Stop here until they say yes.
- [ ] **Step 2: Run it**
  ```
  TALEMATE_AI_TESTS=1 guix shell -m manifest.scm -- uv run --no-sync python scripts/dev/probe_fact_roundtrip.py --rounds 3
  ```
  Expected: exit code 0, with `report.md` written.
- [ ] **Step 3: Summarise for the owner.** Cover invented and dropped claims per round, drift, and which prompt changes look worth trying. Per the spec, a poor result changes phase 2's prompts, not this plan's schema, so Task 4 onward proceeds regardless.
- [ ] **Step 4: Commit the findings** to `docs/superpowers/probes/2026-10-18-fact-roundtrip.md`, with the message `docs(probe): fact round-trip findings`. This is a short write-up quoting the summary table. Don't commit the raw `.test-artifacts`.

---

## Phase 1: the world store

The package layout:

```
src/talemate/world/
  __init__.py      # re-exports the public names below
  dates.py         # WorldDate, Precision
  calendar.py      # Calendar, Era, Holiday
  kinds.py         # KindSpec, FieldSpec, KINDS, get_kind
  refs.py          # reference token parse/format
  schema.py        # DDL + migrations
  store.py         # World (open/create/list), Source, Revision (writes)
  view.py          # WorldView, ThingState, FactState (reads)
  timeline.py      # thing timelines
  undo.py          # undo by source
  index.py         # derived search index
```

Tests go in `tests/world/` (add an empty `__init__.py`). Shared fixtures go in `tests/world/conftest.py`: `world(tmp_path)` creates a fresh `World` under `tmp_path`, and `maren(world)` creates a character with known fields and facts.

### Task 4: Dates and calendar

**Files:**
- Create: `src/talemate/world/__init__.py`, `src/talemate/world/dates.py`, `src/talemate/world/calendar.py`
- Modify: `src/talemate/path.py` (add `WORLDS_DIR` and export it)
- Test: `tests/world/__init__.py`, `tests/world/test_dates.py`, `tests/world/test_calendar.py`

**Interfaces:**
- **`dates.py`**
  - `class Precision(str, Enum)`: `YEAR`, `MONTH`, `DAY`, `EXACT`.
  - `class WorldDate(BaseModel, frozen=True)`, with fields `instant: int` (seconds since 0001-01-01T00:00:00) and `precision: Precision`.
  - `WorldDate.of(year: int, month: int | None = None, day: int | None = None, hour: int = 0, minute: int = 0) -> WorldDate`. Precision follows the most specific part given: year only → YEAR, plus month → MONTH, plus day → DAY. EXACT is used only when `hour` or `minute` is non-zero.
  - `WorldDate.to_datetime() -> datetime.datetime`
  - `WorldDate.plus(duration: str) -> WorldDate` takes an ISO-8601 duration, keeps EXACT precision when the duration has a time part and otherwise keeps the original precision, and raises `ValueError` for a negative result or a year past 9999.
  - Ordering compares by `instant`.
- **`calendar.py`**
  - `class Era(BaseModel)`: `name: str`, `abbreviation: str = ""`, `start_year: int`. The displayed year is `year - start_year + 1`.
  - `class Holiday(BaseModel)`: `name: str`, `month: int`, `day: int`.
  - `class Calendar(BaseModel)`:
    - `month_names: list[str]`, exactly 12, defaulting to the English names;
    - `weekday_names: list[str]`, exactly 7, defaulting to the English names;
    - `eras: list[Era] = []`;
    - `holidays: list[Holiday] = []`.
  - `Calendar.format(date: WorldDate) -> str`. YEAR → `"312"`. MONTH → `"Thawmonth 312"`. DAY → `"3 Thawmonth 312"`. EXACT adds `" 14:05"`. When the date falls in an era (the latest era whose `start_year <= year`), the year is the era year plus `" " + abbreviation` if one is set.
  - `Calendar.holidays_on(date: WorldDate) -> list[Holiday]`

- [ ] **Step 1: Write the failing tests**
  - `test_of_sets_precision`: `of(304).precision is YEAR` and `of(304, 2, 3).precision is DAY`.
  - `test_plus_month_is_calendar_month`: `of(312, 1, 31).plus("P1M").to_datetime().month == 2`.
  - `test_plus_rejects_past_9999`
  - `test_dates_order_by_instant`
  - `test_format_each_precision`: a calendar with month 3 named `"Thawmonth"` gives `"312"`, `"Thawmonth 312"` and `"3 Thawmonth 312"`.
  - `test_format_uses_latest_era`: eras starting at 1 and at 300 (`"AR"`) render year 312 as `"13 AR"`.
  - `test_calendar_rejects_wrong_month_count`
  - `test_holidays_on`
- [ ] **Step 2: Run them to make sure they fail**
  Run: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/world -v -n0`
  Expected: FAIL.
- [ ] **Step 3: Implement `dates.py` and `calendar.py`, and add `WORLDS_DIR`.**
- [ ] **Step 4: Run the tests to make sure they pass** with the same command. Expected: PASS.
- [ ] **Step 5: Commit** with the message `feat(world): in-world dates and calendar`.

### Task 5: Kinds, schema, World and revisions (the write side)

**Files:**
- Create: `src/talemate/world/kinds.py`, `refs.py`, `schema.py`, `store.py`
- Test: `tests/world/conftest.py`, `tests/world/test_kinds.py`, `tests/world/test_store.py`

**Interfaces:**
- Consumes: `WorldDate`, `Calendar` (Task 4) and `WORLDS_DIR`.

**`kinds.py`**
- `class FieldSpec(BaseModel)`: `name: str` and `type: Literal["text", "date", "thing", "shares", "json"]`. A `thing` field holds a thing id; `shares` holds `[{"thing_id": str, "share": float}]`.
- `class KindSpec(BaseModel)`: `name: str`, `fields: list[FieldSpec]`, `categories: list[str]`.
- `KINDS: dict[str, KindSpec]` holds exactly these kinds:

| Kind | Fields | Categories |
|---|---|---|
| `character` | name:text, born:date, culture:thing, voice:json, color:text | appearance, personality, background, ability, relationship, speech |
| `place` | name:text, kind:text, parent:thing, cultures:shares | description, history, law, general |
| `culture` | name:text, language:json | customs, food, dress, belief, general |
| `item` | name:text, owner:thing | description, history, power, general |
| `event` | name:text, when:date, until:date, place:thing | summary, consequence, general |
| `lore` | name:text | general |

- `get_kind(name: str) -> KindSpec` raises `KeyError` for an unknown kind. Adding a kind later is one entry here; that's the spec's extensibility point.
- `validate_field(kind: KindSpec, field: str, value) -> None` raises `ValueError` for an unknown field or a wrong value type. A `date` field takes a `WorldDate` or its dict form. A `thing` field takes a 32-hex string.

**`refs.py`**
- `REF_PATTERN`, compiled from `r"\[\[thing:([0-9a-f]{32})\]\]"`.
- `ref(thing_id: str) -> str` returns the token.
- `parse_refs(text: str) -> list[str]` returns the referenced ids in order, de-duplicated.

**`schema.py`**
- `SCHEMA_VERSION = 1`.
- `MIGRATIONS: list[str]`: index i upgrades version i to i+1.
- `apply(conn) -> None` runs pending migrations inside a transaction and records `PRAGMA user_version`.
- Version 1 creates these tables:
  - **`meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)`**: world id, name, calendar JSON, created timestamp.
  - **`revisions(rev INTEGER PRIMARY KEY AUTOINCREMENT, source_kind TEXT NOT NULL CHECK (source_kind IN ('manual','scene','undo')), scene_id TEXT, branch_id TEXT, message_id TEXT, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)`**
  - **`things(id TEXT PRIMARY KEY, kind TEXT NOT NULL, rev_added INTEGER NOT NULL REFERENCES revisions, rev_removed INTEGER REFERENCES revisions)`**
  - **`field_values(row_id INTEGER PRIMARY KEY, thing_id TEXT NOT NULL REFERENCES things, field TEXT NOT NULL, value_json TEXT NOT NULL, valid_from INTEGER, from_precision TEXT, rev_added INTEGER NOT NULL, rev_removed INTEGER)`**. A NULL `valid_from` means "always".
  - **`facts(row_id INTEGER PRIMARY KEY, fact_id TEXT NOT NULL, thing_id TEXT NOT NULL REFERENCES things, category TEXT NOT NULL, text TEXT NOT NULL, valid_from INTEGER, from_precision TEXT, valid_until INTEGER, until_precision TEXT, origin_json TEXT, rev_added INTEGER NOT NULL, rev_removed INTEGER)`**
    - `fact_id` is the stable logical id; each row is one version of that fact.
    - `origin_json` is optional provenance. The spec's "adopted from prose" uses it in phase 2.
  - **`fact_refs(row_id INTEGER NOT NULL REFERENCES facts, thing_id TEXT NOT NULL)`**: the references found in that fact version's text.
  - Indexes on `(thing_id, field)`, `(thing_id)`, `(fact_id)`, `fact_refs(thing_id)`, and each table's `rev_added` and `rev_removed`.

**`store.py`**
- `class Source(BaseModel)`:
  - `kind: Literal["manual", "scene", "undo"]`;
  - `scene_id`, `branch_id` and `message_id`: each `str | None`;
  - `note: str = ""`.
  - Constructors: `Source.manual(note="")` and `Source.scene(scene_id, branch_id, message_id)`.
- `class World`:
  - `World.create(name: str, root: Path = WORLDS_DIR, calendar: Calendar | None = None) -> World` makes `<root>/<id>/world.sqlite`, plus `assets/` and `index/`.
  - `World.open(path: Path) -> World` takes the world folder. It raises `FileNotFoundError` when the database is missing, and `ValueError` when `user_version > SCHEMA_VERSION`.
  - `World.list(root: Path = WORLDS_DIR) -> list[WorldInfo]`, where `WorldInfo` has `id`, `name`, `path` and `head_rev`. Folders without a `world.sqlite` are skipped.
  - Properties and methods: `id`, `name`, `path`, `calendar`, `set_calendar(calendar: Calendar) -> None`, `head_rev() -> int` (0 when there are no revisions yet), `close()`.
  - `World.revision(source: Source) -> ContextManager[Revision]` gives one SQLite transaction per revision. Leaving the block normally commits; an exception rolls back everything, including the revision row.
  - Connection settings: `PRAGMA foreign_keys=ON`, `journal_mode=WAL`, and `sqlite3.connect(..., isolation_level=None)` with explicit `BEGIN IMMEDIATE`.
- `class Revision` has `rev: int`. Every method validates against the kind (`ValueError`) and checks that the thing exists and isn't removed (`KeyError`):
  - **`create_thing(kind: str, fields: dict[str, object] | None = None, *, valid_from: WorldDate | None = None) -> str`**: initial field values are added at `valid_from`.
  - **`set_field(thing_id, field, value, valid_from: WorldDate | None) -> None`**: adds a value. If a live value of that field already has the same `valid_from` (NULL counts as equal to NULL), that row is retired first. This is the correction case.
  - **`remove_field_value(thing_id, field, valid_from: WorldDate | None) -> None`**
  - **`add_fact(thing_id, category, text, valid_from: WorldDate | None = None, valid_until: WorldDate | None = None, origin: dict | None = None) -> str`**
    - Returns the new `fact_id`.
    - Raises `ValueError` when `valid_until <= valid_from`, and when a referenced id isn't an existing thing.
    - Writes `fact_refs`.
  - **`correct_fact(fact_id, *, text=None, category=None, valid_from=..., valid_until=...) -> None`**: retires the live version and adds a new version with the same `fact_id`, with unspecified parts copied. Use a sentinel so that `None` can mean "open".
  - **`end_fact(fact_id, until: WorldDate) -> None`**: shorthand for `correct_fact(fact_id, valid_until=until)`.
  - **`remove_fact(fact_id) -> None`** and **`remove_thing(thing_id) -> None`**. Removing a thing also retires its live field values and facts.

- [ ] **Step 1: Write the failing tests**
  - `test_kinds_table`: `get_kind("character")` fields and categories match the table above, and `get_kind("magic")` raises `KeyError`.
  - `test_parse_refs_dedupes_in_order`
  - `test_create_and_reopen`: create, close, `World.open(path)`; `name`, `id`, `calendar` and `head_rev()` survive.
  - `test_list_skips_non_worlds`
  - `test_open_rejects_newer_schema`: set `user_version = 99` by hand, then `open` raises `ValueError`.
  - `test_revision_numbers_increase_and_record_source`: two revisions get revs 1 and 2, and the second one's `source_kind`, `scene_id` and `message_id` rows read back.
  - `test_set_field_same_date_replaces` (Review Focus 2): after two `set_field` calls at the same date, exactly one live row remains, with the second value.
  - `test_failed_revision_rolls_back` (Review Focus 5): inside one revision, create a thing, add a fact, then `add_fact` with category `"nope"`. That raises `ValueError`, and afterwards `head_rev() == 0` and the `things` table is empty.
  - `test_add_fact_rejects_unknown_reference`
  - `test_add_fact_rejects_until_before_from`
  - `test_correct_fact_keeps_fact_id`: after a correction, two rows share the `fact_id`, and only the new one is live.
  - `test_remove_thing_retires_children`
- [ ] **Step 2: Run them to make sure they fail**
  Run: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/world -v -n0`
  Expected: the new tests FAIL.
- [ ] **Step 3: Implement `kinds.py`, `refs.py`, `schema.py` and `store.py`.**
- [ ] **Step 4: Run the tests to make sure they pass.** Expected: PASS.
- [ ] **Step 5: Commit** with the message `feat(world): world database, kinds and revisions`.

### Task 6: Reading the world on both clocks

**Files:**
- Create: `src/talemate/world/view.py`
- Modify: `src/talemate/world/store.py` (add `World.view`)
- Test: `tests/world/test_view.py`

**Interfaces:**
- Consumes: `World` and `Revision` (Task 5), and `parse_refs` and `REF_PATTERN`.
- **The filter.** A row is visible at `(at, rev)` when:
  - `rev_added <= rev AND (rev_removed IS NULL OR rev_removed > rev)`;
  - for facts, also `(valid_from IS NULL OR valid_from <= at) AND (valid_until IS NULL OR valid_until > at)`;
  - for a field, the visible value is the live row with the greatest `valid_from <= at`, where NULL sorts lowest.

  `at=None` means "latest", which is +∞: every live field takes its greatest `valid_from`, and only facts with a NULL `valid_until` are visible. `rev=None` means `head_rev()`.
- **`World.view(at: WorldDate | None = None, rev: int | None = None) -> WorldView`**
- **`class FactState(BaseModel)`**: `fact_id`, `category`, `text`, `valid_from: WorldDate | None`, `valid_until: WorldDate | None`, `source_rev: int`, `refs: list[str]`.
- **`class ThingState(BaseModel)`**: `id`, `kind`, `fields: dict[str, object]` (only the fields that have a visible value), `facts: list[FactState]` (ordered by `valid_from`, NULL first, then `fact_id`).
- **`class WorldView`**:
  - `at` and `rev`;
  - `thing(thing_id) -> ThingState | None`: None when the thing doesn't exist at `rev`;
  - `things(kind: str | None = None) -> list[ThingState]`;
  - `name_of(thing_id) -> str | None`: the `name` field at `at`;
  - `render(text: str) -> str`: replaces each reference with `name_of(id)`, falling back to the latest name at `rev` when the thing has no name on that date, and to `⟨unknown⟩` when the id isn't found;
  - `referencing(thing_id) -> list[tuple[str, FactState]]`: the `(owner thing id, fact)` pairs for visible facts that reference the thing.

- [ ] **Step 1: Write the failing tests.** Use the `maren` fixture.
  - Maren is born `of(290)` and her name is set at `of(290)`.
  - She has these facts:
    - "heron tattoo" from `of(304)`, open-ended;
    - "Warden" from `of(305)` until `of(316)`;
    - "lost her left eye" from `of(314)`;
    - "quick laugh" with an open start.
  - She is renamed "Maren the Grey" at `of(317)`.

  The tests:
  - `test_view_at_date_filters_facts`: at `of(312)` the visible facts are the tattoo, the Warden fact and the quick laugh, not the eye.
  - `test_open_start_fact_visible_before_any_date` (Review Focus 1): at `of(291)` the quick laugh is visible.
  - `test_latest_view_hides_ended_facts`: at `at=None` the Warden fact isn't visible, and the eye fact is.
  - `test_view_at_old_revision`: add the eye fact in its own revision; viewing at `rev` just before it omits it, even at `of(318)`.
  - `test_prequel_fact_shows_in_earlier_view`: after the other facts, a new revision adds a scar from `of(300)`, and `view(at=of(312))` includes it. This is the spec's "a prequel can add a scar to the past" case.
  - `test_render_uses_name_at_date` (Review Focus 3): Oskar's fact `"owes [[thing:<maren>]] a debt"` renders "Maren" at `of(312)` and "Maren the Grey" at `None`.
  - `test_render_unknown_reference` (Review Focus 3): the text contains a reference to a well-formed but missing id. Insert it with a raw SQL write, since `add_fact` rejects unknown ids. It renders `⟨unknown⟩`.
  - `test_referencing_finds_reverse_links`
  - `test_removed_thing_absent_from_view`
- [ ] **Step 2: Run them to make sure they fail**
  Run: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/world/test_view.py -v -n0`
  Expected: FAIL.
- [ ] **Step 3: Implement `view.py` and `World.view`.** Do the filtering in SQL, with one query per table per call.
- [ ] **Step 4: Run the tests to make sure they pass.** Expected: PASS.
- [ ] **Step 5: Commit** with the message `feat(world): two-clock world views`.

### Task 7: Thing timelines

This is the data behind the timeline strip in the spec's character mockup.

**Files:**
- Create: `src/talemate/world/timeline.py`
- Modify: `src/talemate/world/store.py` (add `World.timeline`)
- Test: `tests/world/test_timeline.py`

**Interfaces:**
- **`class TimelineEntry(BaseModel)`**:
  - `date: WorldDate | None`: None for "always";
  - `change: Literal["field", "fact_start", "fact_end"]`;
  - `field: str | None`;
  - `value: object | None`;
  - `fact_id: str | None`;
  - `text: str | None`;
  - `source_rev: int`;
  - `source: Source`.
- **`World.timeline(thing_id: str, rev: int | None = None) -> list[TimelineEntry]`**
  - Covers every field value and every fact start and end that is live at `rev`.
  - Sorted by date (None first). On the same date, field changes come before fact starts, which come before fact ends; ties then break by `source_rev`.

- [ ] **Step 1: Write the failing tests**
  - `test_timeline_order`: with the `maren` fixture, the entries come out in the expected order (always, 290, 304, 305, 314, 316, 317), with the 316 entry being a `fact_end`.
  - `test_timeline_carries_source`: a fact added from `Source.scene("s1", "b1", "m9")` has `source.message_id == "m9"`.
  - `test_timeline_excludes_retired_rows`
- [ ] **Step 2: Run them to make sure they fail.** Expected: FAIL.
- [ ] **Step 3: Implement `timeline.py`.**
- [ ] **Step 4: Run the tests to make sure they pass.** Expected: PASS.
- [ ] **Step 5: Commit** with the message `feat(world): thing timelines`.

### Task 8: Undo by source

**Files:**
- Create: `src/talemate/world/undo.py`
- Modify: `src/talemate/world/store.py` (add `World.revisions` and `World.undo`)
- Test: `tests/world/test_undo.py`

**Interfaces:**
- **`World.revisions(*, scene_id: str | None = None, branch_id: str | None = None, message_id: str | None = None) -> list[RevisionInfo]`**
  - `RevisionInfo` has `rev`, `source: Source` and `created_at: str`.
  - All filters combine with AND. This is how the inbox (phase 3) finds what a branch or message contributed.
- **`class UndoConflict(BaseModel)`**:
  - `table: Literal["things", "field_values", "facts"]`;
  - `row_id: str | int`;
  - `thing_id: str`;
  - `reason: str`, either "changed again in a later revision" or "removed in a later revision";
  - `later_rev: int`.
- **`class UndoReport(BaseModel)`**: `undo_rev: int | None` (None when nothing was reverted), `reverted: int`, `conflicts: list[UndoConflict]`.
- **`World.undo(revs: list[int], note: str = "") -> UndoReport`** writes one new revision with `source_kind='undo'`. The algorithm:
  1. **Rows the target revisions added.** For each row with `rev_added` in `revs`: if it is still live, retire it at the undo revision.
  2. **Rows that were changed later.** If a row from step 1 was already retired by a later revision not in `revs`, don't touch it or its successor; add an `UndoConflict`. For facts, a later version with the same `fact_id` counts as a change. For field values, a later live value of the same `(thing_id, field, valid_from)` counts.
  3. **Rows the target revisions retired.** For each row with `rev_removed` in `revs`, re-insert a copy with `rev_added` set to the undo revision. Skip it when a newer live version of the same fact or field slot exists, and add a conflict instead.
  4. **Things.** A thing created in `revs` is retired, along with its rows, unless a later revision outside `revs` added rows to it. In that case it's a conflict, and the thing stays.

- [ ] **Step 1: Write the failing tests**
  - `test_undo_reverts_added_fact`: revision 2 adds a fact; `undo([2])` gives `reverted == 1`, and the latest view no longer has it.
  - `test_undo_restores_corrected_fact`: revision 2 corrects a fact's text; after the undo, the old text is live again with the same `fact_id`.
  - `test_undo_lists_later_edited_rows` (Review Focus 4): revision 2 adds a fact and revision 3 corrects it by hand. `undo([2])` leaves the corrected fact live, gives `conflicts[0].later_rev == 3`, and `reverted == 0`.
  - `test_undo_branch_by_source`: revisions from branches E and F interleave. `undo([r.rev for r in world.revisions(branch_id="E")])` removes only E's facts.
  - `test_undo_nothing_writes_no_revision`: undoing an already-undone revision returns `undo_rev is None`, and `head_rev()` doesn't change.
  - `test_view_before_undo_still_available`: `view(rev=<before undo>)` still shows the reverted fact. The history is kept.
- [ ] **Step 2: Run them to make sure they fail.** Expected: FAIL.
- [ ] **Step 3: Implement `undo.py`, `World.revisions` and `World.undo`.**
- [ ] **Step 4: Run the tests to make sure they pass.** Expected: PASS.
- [ ] **Step 5: Commit** with the message `feat(world): undo by source`.

### Task 9: Derived search index

**Files:**
- Create: `src/talemate/world/index.py`
- Test: `tests/world/test_index.py`

**Interfaces:**
- Consumes: `WorldView` (Task 6).
- **`class IndexDoc(BaseModel)`**: `id: str`, `thing_id: str`, `kind: str`, `category: str | None`, `text: str`, `valid_from: int`, `valid_until: int`.
  - Open bounds are stored as `OPEN_START = -1` and `OPEN_END = 2**53 - 1`, because chromadb metadata must be numeric.
- **`index_documents(world: World, rev: int | None = None) -> list[IndexDoc]`**:
  - One header document per thing (`id = "<thing_id>"`, text `"<kind>: <latest name>"`).
  - One document per live fact *version* (`id = "fact:<row_id>"`). The text is the fact rendered with `world.view(at=None, rev=rev).render`, prefixed by the thing's name. The fact's own valid span goes in the bounds.
  - Facts are indexed across all dates, so the date filter happens at query time.
- **`class WorldIndex`**:
  - `__init__(world: World, *, client=None, embedding_function=None)`. The default client is `chromadb.PersistentClient(path=world.path / "index")`, with a collection named `"world-<world.id>"`.
  - `rebuild(rev: int | None = None) -> int` drops and refills the collection and returns the document count.
  - `query(text: str, *, at: WorldDate | None, n: int = 10, kind: str | None = None) -> list[IndexDoc]` filters on `valid_from <= at.instant < valid_until`; `at=None` means `valid_until == OPEN_END`.
  - Phase 2 decides which embedding function the app passes, reusing the memory agent's settings.

- [ ] **Step 1: Write the failing tests.** Use `chromadb.EphemeralClient()` and a deterministic fake embedding function, such as character-trigram hashing into 64 floats, so there are no downloads and no network.
  - `test_index_documents_one_per_fact_plus_header`
  - `test_index_documents_render_names`: a fact referencing Oskar contains "Oskar Dell", not the token.
  - `test_query_filters_by_date`: after `rebuild`, querying "eye" at `of(312)` returns no eye fact, and at `of(315)` returns it.
  - `test_rebuild_is_idempotent`: rebuilding twice gives the same count.
- [ ] **Step 2: Run them to make sure they fail.** Expected: FAIL.
- [ ] **Step 3: Implement `index.py`.**
- [ ] **Step 4: Run the tests to make sure they pass.** Expected: PASS.
- [ ] **Step 5: Run the whole plain suite** to check that nothing outside `world/` changed:
  Run: `guix shell -m manifest.scm -- uv run --no-sync pytest`
  Expected: only the known NLTK environment failures, and all `tests/world` tests pass.
- [ ] **Step 6: Run ruff:** `guix shell -m manifest.scm -- ruff check src/talemate/world tests/world scripts/dev && guix shell -m manifest.scm -- ruff format --check src/talemate/world tests/world scripts/dev`. Expected: clean.
- [ ] **Step 7: Commit** with the message `feat(world): derived search index`.

---

## Not in this plan (later phases)

- Scenes, the message tree, mention records and scene-local changes.
- Generated prose and its cache.
- Images.
- Agents and nodes.
- UI.
- The inbox and conflict detection.
- Cultures moving onto the new shape.

Phase 2's plan starts from this package's public interface: `World`, `Revision`, `WorldView`, `World.timeline`, `World.undo` and `WorldIndex`. Its own AI probes come first, as the spec's "probe the AI before building" principle requires.
