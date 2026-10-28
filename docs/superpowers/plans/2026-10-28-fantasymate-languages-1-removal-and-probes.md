# Languages, plan 1: remove the old culture system, then probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the old culture system, keeping only its name generator and fit check in a new `talemate.languages` package. Then run the three probes whose results shape parts 3 and 4 of the languages design.

**Architecture:**
- **Removal.** Part 1 of the design is a removal in three steps:
  1. Move the generator and the four data classes it needs into `src/talemate/languages/`.
  2. Delete the backend culture code. The two signals the Culture agent listened to stay; part 4 hooks the same moments.
  3. Delete the frontend culture code.
- **Probes.** Part 2 is three throwaway probes in `scripts/dev/`, following the repo's probe convention: labels are committed before any model call, raw output goes in `docs/superpowers/probes/raw/`, and findings go in `docs/superpowers/probes/`. The scoring code that runs without a model is unit-tested.

**Tech Stack:** Python 3.11, pydantic, pytest; Vue 3 / Vuetify frontend; Playwright e2e; Talemate's KoboldCpp client against the owner's koboldcpp.

**Spec:** `docs/superpowers/specs/2026-10-28-fantasymate-languages-design.md` (parts 1 and 2). Parts 3 and 4 get their own plans once the probe reports are in, because the spec says their details wait on the probes.

## Global Constraints

- **Environment.** Run everything through `guix shell -m manifest.scm -- …` from the repo root. Use `uv run --no-sync`, never plain `uv run`. Run e2e with `pytest tests/e2e -m e2e -n 4`, never more than 4 workers. See `docs/dev/local-testing.md`.
- **The plain suite** (`uv run --no-sync pytest`) ends every task with 0 failures.
- **Browser tests.** While iterating, run only the area's folder. Run the full e2e suite once, at the end of tasks 2 and 3.
- **koboldcpp runs need the owner's go-ahead.** Before any run that calls koboldcpp (`http://192.168.0.5:5001`), ask "ready for AI testing?" and wait. This plan has no standing permission. Each probe-run task asks again.
- **Model swaps are the owner's.** Probe 1 needs Qwen loaded for one run and Skyfall for the other. Ask the owner to load each model; never assume which one is loaded. Each run records `client.model_name`.
- **Hard fork.** Delete outright. Don't leave a compatibility layer for old culture data: worlds made before this slice aren't upgraded (spec, Non-goals).
- **Keep:**
  - `roll`, `fits` and `name_fits`, together with the rest of `cultures/generator.py` and its tests;
  - the `foreign` theme role in `talemate_frontend/src/theme/roles.js`;
  - the signals `agent.creator.before_name_character` and `world_state.snapshot.after`.
- **Leave alone:** words that only classify free text, such as `_KIND_GUESSES["culture"] = "lore"` (the model may still reply "culture") and the "of this culture" filing-role word in `worldplay/context.py`. Remove only what makes culture a concept of the app (spec part 1).
- **UI-driven tests.** After changing anything the AI tests drive, grep `tests/ai` for the removed selectors and test ids.
- **Commits** end with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **Where the work happens.** Build in a worktree on the branch `feature/languages-1` (`.worktrees/languages-1`). The stale worktree `.worktrees/cultures-ai-check` (branch `fix/cultures-ai-check`) is the owner's; don't touch it.

## Review Focus

1. **A saved scene from before the removal still loads.** Its characters carry `"culture": null` or a full culture dict. Expect it to load, with the key ignored. Test: Task 2, `test_character_ignores_saved_culture_key`.
2. **A config saved with a `culture` agent entry still boots.** Expect the entry to be ignored, with no crash on start. Test: Task 2, `test_config_with_culture_agent_loads`.
3. **The pre-naming and post-snapshot signals keep working once nothing listens.** Expect the creator to name characters exactly as before. Test: Task 2, the moved `tests/test_naming_hooks.py`.
4. **The worlds and scene screens don't reference the deleted components.** Expect no missing-import error at build and no console error on load. Test: Task 3, the full e2e suite plus `test_browser_smoke.py`.
5. **The probe scoring treats inflected real words as real.** For example "Moskva" and "Volgi" against the list's "moskva" and "volga". Expect a hit. Test: Task 4, `test_real_word_hits_strips_endings`.

---

### Task 1: Move the generator into `talemate.languages`

**Files:**
- Create: `src/talemate/languages/__init__.py`, `src/talemate/languages/models.py`
- Move: `src/talemate/cultures/generator.py` → `src/talemate/languages/generator.py` (with `git mv`)
- Move: `tests/cultures/test_generator.py` → `tests/languages/test_generator.py` (and create `tests/languages/__init__.py` if `tests/cultures/` has one)
- Modify: `src/talemate/cultures/models.py`, and every `talemate.cultures.generator` import (`grep -rn "cultures.generator\|cultures import generator" src tests scripts`)

**Interfaces:**
- Produces:
  - `talemate.languages.models`: `GeneratorDef`, `Phrase`, `DictionaryEntry` and `Language`, moved unchanged from `cultures/models.py:48-94`, with `new_id` and `slugify` if they use them.
  - `talemate.languages.generator`: `GeneratorError`, `parse_categories`, `pattern_letters`, `roll`, `fits`, `name_fits` and `validate_language`, with the same signatures as today.
  - Tasks 4 and 6 import these.

- [ ] **Step 1: Move the tests first, and point them at the new path.** Change the test file's imports to `from talemate.languages.generator import …` and `from talemate.languages.models import …`.
- [ ] **Step 2: Run them and watch them fail.** Run `uv run --no-sync pytest tests/languages -q`. Expected: `ModuleNotFoundError: talemate.languages`.
- [ ] **Step 3: Move the code.**
  - `git mv` the generator.
  - Move the four classes into `languages/models.py`.
  - In `cultures/models.py`, replace them with `from talemate.languages.models import GeneratorDef, Phrase, DictionaryEntry, Language  # noqa: F401`, so the culture code keeps working until Task 2.
  - Update every other import.
  - Reword the generator's module docstring. It now describes the pattern syntax as "the language format" rather than "the culture import file format", and drops the reference to "Task 7's authoring skill".
- [ ] **Step 4: Run the moved tests and the plain suite.** Run `uv run --no-sync pytest tests/languages -q`, then `uv run --no-sync pytest -q`. Expected: all 18 generator tests pass, and the suite has 0 failures.
- [ ] **Step 5: Commit** with the message `refactor(languages): move the name generator out of cultures`.

### Task 2: Delete the backend culture system

**Files:**
- Delete:
  - `src/talemate/cultures/` (the whole package)
  - `src/talemate/agents/culture/`
  - `src/talemate/server/cultures.py`
  - `src/talemate/prompts/templates/culture/`
  - `scripts/dev/cultures_eval_metrics.py`, `scripts/dev/eval_cultures_ai.py`
  - `tests/cultures/` (whatever Task 1 left)
  - `tests/test_culture_agent.py`, `tests/test_culture_naming.py`, `tests/test_culture_snapshot.py`
  - `tests/server/test_cultures_plugin.py`, `tests/server/test_cultures_story_plugin.py`
  - `tests/ai/cultures/`
  - `tests/dev/test_cultures_eval_metrics.py`
- Move: `tests/test_culture_core_hooks.py` → `tests/test_naming_hooks.py`
- Modify:
  - `src/talemate/agents/__init__.py:4` (drop the import)
  - `src/talemate/server/websocket_server.py:27,94` (drop the plugin)
  - `src/talemate/character.py:15,55,361-362,689-690` (drop the `culture` field, its `update` branch and its copy)
  - `src/talemate/agents/creator/character.py:140-145,470-473,487-489,930,1060`: docstrings say "a listener" instead of "the Culture agent", and the parameter `culture_hook` is renamed `naming_hook`
  - `src/talemate/agents/world_state/snapshot.py:44` (docstring)
  - `src/talemate/world/kinds.py:85` (drop `"culture"` from `HINT_AGENT`) and `:183` (the comment)
  - `src/talemate/worldplay/create.py:1811` (`BELIEF_HINTS` becomes `("religion", "order")`), plus the comments and docstrings at lines 81, 727, 897, 2817, 2891 and 3691 that list culture as a hint
  - `src/talemate/world/entries.py:8`, `src/talemate/world/heritage.py:8`, `src/talemate/server/worlds.py:5237`, `src/talemate/worldplay/held.py:235` (wording)
  - `tests/world/test_entries.py:32-160`: the Riverfolk and Hill Clans fixtures use `hint: "culture"`; switch them to `"order"` and keep what each test checks
  - `tests/dev/test_frontend_checks.py:28-35,105-115`: delete the two `culturesStory` tests
  - `tests/e2e/seed.py`: delete `_PLACES_GLOSSARY_SCRIPT`, `_CULTURE_SCRIPT`, `place_culture` and their helpers; in `_SCENE_SCRIPT`, drop the `world_dir_for` import and the `result["world_dir"]` line (lines 53 and 132) and the `culture=` argument (line 112). First grep `tests/e2e` for `world_dir` to confirm only cultures tests read it.
  - `docs/dev/local-testing.md`, `docs/dev/dev-loop-optimizations.md`: drop the culture test paths
- Delete: `src/talemate/prompts/templates/world/hints/culture.txt`
- Regenerate: `tests/data/characterization/scene_golden.json`, which loses the two `"culture": null` lines
- Test: `tests/test_character.py` (add), `tests/test_config_state.py` (add)

**Interfaces:**
- Consumes: `talemate.languages` (Task 1).
- Produces:
  - `CreatorAgent.determine_character_name(..., naming_hook: bool = True)`;
  - the signals `agent.creator.before_name_character` (`CharacterNamingEmission`) and `world_state.snapshot.after` (`WorldStateSnapshotEmission`), unchanged.
  - The part-4 plan hooks naming into these.

- [ ] **Step 1: Write the load-safety tests** (Review Focus 1 and 2).

```python
def test_character_ignores_saved_culture_key():
    for saved in (None, {"culture_id": "x", "shares": []}):
        c = Character(name="Ivan", culture=saved)
        assert "culture" not in c.model_dump()
        c.update(culture=saved)
        assert "culture" not in c.model_dump()
```

`test_config_with_culture_agent_loads`: write a config YAML with an `agents: {culture: {enabled: true}}` entry, point `talemate.config.state.CONFIG_FILE` at it with monkeypatch (as the file's other tests do), and call `talemate.config.state._load_config()`. Assert that it returns a `Config` and that `"culture" not in instance.agent_types()`.

- [ ] **Step 2: Run them and watch them fail.** Run `uv run --no-sync pytest tests/test_character.py -k culture -q`. Expected: FAIL, because `culture` is still in `model_dump()`.
- [ ] **Step 3: Delete and modify as listed under Files.**
  - `Character.update` with `culture=` must not `setattr` an unknown attribute. Skip the key explicitly, as Review Focus 1 needs.
  - Rename the hooks test file. Reword its docstring to "a listener (part 4's language naming)", and rename the `culture_scene` fixture to `naming_scene`.
  - Before deleting `agents/culture/`, record the commit it was deleted in. The part-4 plan studies those hooks there (`git show <sha>^:src/talemate/agents/culture/naming.py`).
- [ ] **Step 4: Check that nothing is left.** Run `grep -rn -i "talemate.cultures\|CultureAgent\|culture_hook" src tests scripts`. Expected: no output. Then run `grep -rn -i "cultur" src` and check each hit is free-text wording from the "Leave alone" rule.
- [ ] **Step 5: Run the plain suite and update the golden recording.** Run `uv run --no-sync pytest tests/characterization --update-baselines -q`, check that the diff in `scene_golden.json` is only the two `culture` lines, then run `uv run --no-sync pytest -q`. Expected: 0 failures.
- [ ] **Step 6: Run the worlds e2e folder.** Run `pytest tests/e2e/worlds -m e2e -n 4`. Expected: all pass. The cultures e2e folder is deleted in Task 3, so skip it here.
- [ ] **Step 7: Commit** with the message `refactor(cultures): remove the backend culture system`, and note the deletion sha in the commit body.

### Task 3: Delete the frontend culture system

**Files:**
- Delete:
  - `talemate_frontend/src/components/cultures/` (all of it, including `story.css`)
  - `talemate_frontend/checks/culturesStory.check.mjs`
  - `tests/e2e/cultures/`
- Modify:
  - `talemate_frontend/src/components/WorldStateManagerMenu.vue:51-79`: drop the cultures tab tools
  - `talemate_frontend/src/components/WorldStateManager.vue`: drop the cultures tab and its 16 references
  - `talemate_frontend/src/components/WorldState.vue:41,240-247`: drop `CultureChip` and `WorldPanelPlaces`
  - `talemate_frontend/src/components/EntityTooltip.vue:14-16,95-106`: drop `ForeignWordCard` and `NameLanguageSection`
  - `talemate_frontend/src/components/EntityHighlightMixin.js`: drop `culturesStory`, the storyLexicon imports, `culturesForeignMentions`, `culturesNameIndex`, and the `.scene-foreign` handling; keep the name-mention highlighting intact
  - `talemate_frontend/src/components/TalemateApp.vue:512,612,1059-1062,1219`: drop the cultures store, the badge, `openCulturesReview` and `ingestCulturesMessage`
  - `talemate_frontend/src/utils/messageColors.js`: drop its culture reference
- Test: the e2e suite; `tests/e2e/test_browser_smoke.py`

**Interfaces:**
- Consumes: Task 2 (the backend router is gone, so nothing may still send `cultures` websocket messages).
- Produces: a frontend with no `cultures` references. The `foreign` role in `theme/roles.js` stays for part 4.

- [ ] **Step 1: Delete and modify as listed under Files.** In `TalemateApp.vue`, check whether the review badge sat in a list that other entries share, and keep that list's shape.
- [ ] **Step 2: Check that nothing is left.** Run `grep -rn -i "cultur" talemate_frontend/src talemate_frontend/checks tests/e2e tests/ai`. Expected: no output.
- [ ] **Step 3: Build and run the frontend checks.** From `talemate_frontend`, run `npx --yes corepack@0.34.0 pnpm build`, then from the repo root run `uv run --no-sync pytest tests/dev/test_frontend_checks.py -q`. Expected: the build succeeds with no unresolved import, and the checks pass.
- [ ] **Step 4: Run the full browser suite and the plain suite.** First check for leftover apps (`ps -eo pid,etime,cmd | grep "[p]ytest-of-$USER/pytest-.*/app"`). Then run `pytest tests/e2e -m e2e -n 4` and `uv run --no-sync pytest -q`. Expected: both pass with 0 failures.
- [ ] **Step 5: Take before-and-after screenshots** of the World State panel and the World State Manager with `scripts/dev/look.py`. Expected: the only change is that the cultures tab, the culture chips and the places panel are gone.
- [ ] **Step 6: Commit** with the message `refactor(cultures): remove the frontend culture system`.

### Task 4: Probe 1 harness: making a language

**Files:**
- Create:
  - `scripts/dev/language_probe_metrics.py` (the scoring; no model)
  - `scripts/dev/probe_language_make.py` (the harness)
  - `docs/superpowers/probes/raw/2026-10-28-language-make-labels.json`
- Test: `tests/dev/test_language_probe_metrics.py`

**Interfaces:**
- Consumes: `talemate.languages.models.Language`, `talemate.languages.generator.roll`, `fits` and `validate_language` (Task 1); `probe_heritage_play.RecordingClient` and `_quiet_loading` (as `probe_tags_kind_names.py:100-126` uses them).
- Produces, for Task 6 and its own run (Task 5):
  - `real_word_hits(names: list[str], real: list[str]) -> list[str]`
  - `jargon_hits(text: str, jargon: list[str]) -> list[str]`
  - `language_checks(data: dict, rolls: int = 50, seed: int = 0) -> dict`, returning the keys `valid: bool`, `error: str | None`, `samples: dict[str, list[str]]` (by generator id), `dictionary_fit: float` (the share of dictionary words that `fits`), and `real_hits: list[str]`.

**The labels file** (commit it before any call), with these keys:
- `real_words`: about 200 transliterated real Russian items, all lower case, covering:
  - common nouns (gorod, reka, zemlya, volya, krasny, …);
  - given names (ivan, dmitri, olga, …);
  - surnames and patronymic stems;
  - cities (moskva, novgorod, kiev, …);
  - rivers (volga, dnepr, neva, …);
  - tsars' names.
- `jargon`: phonology, phoneme, phonotactics, fricative, plosive, sibilant, affricate, consonant cluster, vowel harmony, morphology, morpheme, agglutinative, fusional, inflection, allophone, IPA, coda, onset, nucleus.
- `cases`, each with a `prompt` and a `mode` (`decide` or `ask`):
  - `russian`: "a unique but recognizably Russian language";
  - `compound-desc`: "fantasy-sounding English compound names" (a naming style);
  - `compound-examples`: a naming style from Duskhollow, Thornfield, Ashmere, Ravenford, Briarwick;
  - `daughter`: the `russian` output as parent, with the drift "isolated in the mountains for five hundred years";
  - `ask-russian`: the `russian` prompt in `ask` mode.
- `small_jobs`:
  - `definitions`: write one-sentence definitions for 10 names rolled from the `russian` result;
  - `pick`: pick a capital's name for a tsardom from 20 rolled candidates, and say why;
  - `coin`: give "Free Provinces" in the `russian` language, coining the missing words with definitions.

- [ ] **Step 1: Write the failing tests.**

```python
def test_real_word_hits_exact_and_case():
    assert real_word_hits(["Moskva", "Velgarov"], ["moskva"]) == ["Moskva"]

def test_real_word_hits_strips_endings():
    # a final a/o/y/i/e/u, or "ov"/"ev"/"in", is stripped on both sides before comparing
    assert real_word_hits(["Volgi", "Novgoroda"], ["volga", "novgorod"]) == ["Volgi", "Novgoroda"]
    assert real_word_hits(["Sorau"], ["volga"]) == []

def test_jargon_hits_whole_words_only():
    assert jargon_hits("Harsh or soft? Any phonemes you dislike?", ["phoneme"]) == ["phoneme"]
    assert jargon_hits("A codable onsetter", ["coda", "onset"]) == []

def test_language_checks_valid_language():
    data = {"name": "T", "level": "naming",
            "categories": {"C": "k t r", "V": "a o"},
            "generators": [{"id": "p", "name": "places", "use": "places", "patterns": ["CVCV"]}],
            "dictionary": [{"word": "kata", "meaning": "hill"}, {"word": "xyz", "meaning": "?"}]}
    out = language_checks(data, rolls=20, seed=1)
    assert out["valid"] and out["error"] is None
    assert len(out["samples"]["p"]) == 20
    assert out["dictionary_fit"] == 0.5

def test_language_checks_reports_invalid():
    out = language_checks({"name": "T", "level": "naming", "generators": [
        {"id": "p", "name": "x", "use": "places", "patterns": ["((((((C))))))"]}]})
    assert not out["valid"] and out["error"]
```

  `jargon_hits` matches whole words, allowing a plural `s`. `real_word_hits` with endings stripped is the Review Focus 5 test. If `roll` can return fewer than `rolls` unique names for a tiny alphabet, give the valid-language test a generator big enough for 20.
- [ ] **Step 2: Run them and watch them fail.** Run `uv run --no-sync pytest tests/dev/test_language_probe_metrics.py -q`. Expected: `ModuleNotFoundError`.
- [ ] **Step 3: Implement the three functions** in `scripts/dev/language_probe_metrics.py`. `language_checks` uses `Language.model_validate`, `validate_language` and `roll(..., count=rolls)` per generator with `rng=random.Random(seed)` (`roll(language, generator_id, count=20, rng=None, exclude=frozenset()) -> list[str]`). It runs `fits` over each dictionary word and `real_word_hits` over all samples and dictionary words, using the labels' `real_words`, which are passed in through a module-level loader. Any exception becomes `valid=False`, with `error` set.
- [ ] **Step 4: Run the tests until they pass.** Same command. Expected: PASS.
- [ ] **Step 5: Write the harness** (`probe_language_make.py OUT.json --label NAME [--versions 2]`).
  - The prompts are constants in the script. They tell the model to:
    - reply with JSON in the `Language` shape (`categories`, `generators` in the pattern syntax, `dictionary`, `phrases`), with the syntax summary copied from the generator's docstring;
    - speak plainly, never in linguistics terms;
    - in `ask` mode, reply first with at most four plain questions, then, after a fixed canned answer from the labels, with the language;
    - for the part-based style, put the word parts in categories (multi-letter options such as `"A": "dusk thorn ash"`) and give each part's meaning in `dictionary`.
  - Each case runs `--versions` times (default 2), one call after another.
  - Each run records `client.model_name`, every call, the parsed JSON (or the parse error), `language_checks(…)`, and `jargon_hits` over the `ask` questions.
  - It saves after each call, as `probe_tags_kind_names.py` does.
  - `daughter` and the small jobs use version 1 of `russian` from the same run.
  - The module docstring gives the run command in the form of `probe_tags_kind_names.py:14-18` and names the findings file.
- [ ] **Step 6: Dry-run the harness without a model.** Run it with the client stubbed to return a fixed reply: add a `--fake` flag that swaps `RecordingClient` for a stub returning the valid-language JSON from Step 1. Expected: the output JSON has every case, with `valid: true`.
- [ ] **Step 7: Commit** the labels, metrics, tests and harness, with the message `probe(languages): language-making harness and labels`. This commit must come before any model call.

### Task 5: Probe 1 run and report

**Files:**
- Create:
  - `docs/superpowers/probes/raw/2026-10-28-language-make.json`
  - `docs/superpowers/probes/2026-10-28-language-make.md`
- Possibly delete: `.claude/skills/culture-design/` (Step 5)

- [ ] **Step 1: Ask the owner** "ready for AI testing?", and ask them to load Qwen in koboldcpp. Wait for both answers.
- [ ] **Step 2: Run the Qwen pass.** Run `guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python scripts/dev/probe_language_make.py docs/superpowers/probes/raw/2026-10-28-language-make.json --label qwen'`. Expected: the output's `model` names a Qwen model, and every case has a result.
- [ ] **Step 3: Ask the owner to load Skyfall,** then run again with `--label skyfall`.
- [ ] **Step 4: Write the report and get the owner's grades.** The report follows the shape of `docs/superpowers/probes/2026-10-24-tags-kind-names.md`: Why, Setup, Results, Findings.
  - Results table, per model and case: valid, `dictionary_fit`, real-word hits, jargon hits.
  - For each language, 20 of its samples, plus the small jobs' outputs.
  - The owner's grades:
    - Does `russian` sound recognizably Russian without being Russian?
    - Does `daughter` sound related?
    - Do the compound styles read like Duskhollow?
    - Are the definitions usable?

  Show the owner the samples and record their words verbatim.
- [ ] **Step 5: Record the decision, and act on the skill.** The report ends with one of these:
  - **In the app:** name the model, and delete `.claude/skills/culture-design/`.
  - **Claude outside the app:** keep the skill. The part-3 plan reworks it into the language-design skill.

  Then record whether definitions, picking and coining work locally (spec part 2, probe 1).
- [ ] **Step 6: Commit** with the message `probe(languages): language-making results`.

### Task 6: Probe 2 harness: catching bad names in drafts

**Files:**
- Create:
  - `scripts/dev/probe_name_flags.py`
  - `docs/superpowers/probes/raw/2026-10-28-name-flags-labels.json`
- Modify: `scripts/dev/language_probe_metrics.py` (add `flag_scores`)
- Test: `tests/dev/test_language_probe_metrics.py` (add)

**Interfaces:**
- Consumes: `real_word_hits` (Task 4); `worldplay.create.preview_thing(world, kind, prompt, fields, client, …) -> CreatePreview` (`create.py:2868`), used as `probe_tags_kind_names.py` and `probe_world_create.py` use it.
- Produces: `flag_scores(labels: dict[str, str], flagged: dict[str, str]) -> dict`. Both arguments map a name to one of `real`, `stock-title` or `ok`. The result has `precision` and `recall` for each of `real` and `stock-title`, plus the lists `missed` and `false_flags`.

**The labels file** (commit it before any call):
- `names`: about 60 names, each with a one-line fact context and a label:
  - `real`, about 20: Moscow, the Volga, Novgorod, Ivan the Terrible, the Kremlin, the Dnieper, Kazan, Boyar Duma, Rurik, …;
  - `stock-title`, about 15: Free Cities of the Southern Realms, the Shadowlands, Kingdom of the North, the Iron Council, the Eastern Wastes, …;
  - `ok`, about 25: invented names that should pass (Velgarov, Free Provinces of Sorau, Kerevask, …), and AI clichés like Maren and Elara. Clichés are the cliché list's job, not this probe's, so they count as `ok` here.
- `baseline_prompts`: 5 create prompts that reproduce the owner's runs: a nation "Tsardom of Moscavia, a cold northern tsardom of owl-folk", its capital, its neighbours, a noble house, and a river.

- [ ] **Step 1: Write the failing test.**

```python
def test_flag_scores():
    labels = {"Moscow": "real", "Volga": "real", "Free Cities of the South": "stock-title", "Sorau": "ok"}
    flagged = {"Moscow": "real", "Sorau": "real", "Free Cities of the South": "stock-title"}
    s = flag_scores(labels, flagged)
    assert s["real"] == {"precision": 0.5, "recall": 0.5}
    assert s["stock-title"] == {"precision": 1.0, "recall": 1.0}
    assert s["missed"] == ["Volga"] and s["false_flags"] == ["Sorau"]
```

  A name missing from `flagged` counts as `ok`.
- [ ] **Step 2: Run it and watch it fail.** Run `uv run --no-sync pytest tests/dev/test_language_probe_metrics.py -k flag -q`. Expected: FAIL.
- [ ] **Step 3: Implement `flag_scores`,** then run the test until it passes. Expected: PASS.
- [ ] **Step 4: Write the harness** (`probe_name_flags.py OUT.json --label NAME`). It has three stages:
  1. *Baseline:* run each baseline prompt through `preview_thing` twice, in a scratch world built as `probe_tags_kind_names.build` builds one. Record every name the preview proposes (the new-name list on `CreatePreview`) and its `real_word_hits`. This is how often real names leak in today.
  2. *Flag:* one call per batch of 15 labelled names, each with its context line. The model labels each name `real`, `stock-title` or `ok`, and says why. Score the replies with `flag_scores`.
  3. *Rewrite:* for each `stock-title`, the model returns a fresher, more specific title with a `{name}` slot ("Free Provinces of {name}"). The harness fills the slot with a name rolled from a small fixed test language in the labels, and records the result for the owner to judge.
  - Add a `--fake` dry-run flag, as in Task 4.
- [ ] **Step 5: Dry-run the harness.** Run it with `--fake`. Expected: every stage produces output.
- [ ] **Step 6: Commit** with the message `probe(languages): name-flagging harness and labels`, before any model call.

### Task 7: Probe 2 run and report

**Files:**
- Create:
  - `docs/superpowers/probes/raw/2026-10-28-name-flags.json`
  - `docs/superpowers/probes/2026-10-28-name-flags.md`

- [ ] **Step 1: Ask the owner** "ready for AI testing?", and which model to use (Skyfall is the world-building model). Wait for the answer.
- [ ] **Step 2: Run it.** Same command form as Task 5, with `probe_name_flags.py` and `--label skyfall`. If the owner asks, run a second pass with Qwen.
- [ ] **Step 3: Write the report.** It covers:
  - the baseline (how many real-world names per draft, with examples);
  - precision and recall for each class, with the misses;
  - the rewritten titles, with the owner's verdict on each, quoted.

  End with what probe 2 settles for part 4:
  - whether flagging runs on the local model;
  - whether candidate names should also go into the create prompt.
- [ ] **Step 4: Commit** with the message `probe(languages): name-flagging results`.

### Task 8: Probe 3: language awareness in scenes

**Files:**
- Create:
  - `scripts/dev/probe_language_scene.py`
  - `docs/superpowers/probes/raw/2026-10-28-language-scene.json`
  - `docs/superpowers/probes/2026-10-28-language-scene.md`

**Interfaces:**
- Consumes: `probe_heritage_play`'s world-building and play loop (`build_world`, `_load`, `play` and `RecordingClient`, `probe_heritage_play.py:240-348`), and `worldplay.context.world_context_block`.

- [ ] **Step 1: Write the harness.**
  - Build a small world with two characters who meet in a scene: Ivan (speaks Moscavian) and Mira (speaks Sorauan).
  - Run three variants, each played for the same six turns as `probe_heritage_play.play`, with Mira's player lines inviting conversation:
    - `none`: no language note;
    - `barrier`: the note "Ivan and Mira share no language: they can't simply talk.";
    - `similar`: "Ivan's Moscavian is close to Mira's Sorauan: they understand each other with effort."
  - Add the note by wrapping `world_context_block` so it appends the line. That's the spot where part 4's note will go.
  - Keyword-scan each turn for cues of misunderstanding, using a list in the script (gesture, didn't understand, repeated, slowly, accent, foreign tongue, frown, …).
  - Commit the harness (`probe(languages): scene language harness`) before any call.
- [ ] **Step 2: Ask the owner** "ready for AI testing?", and wait.
- [ ] **Step 3: Run it** with the same command form as Task 5. Expected: three variants, each with six turns.
- [ ] **Step 4: Write the report.**
  - Put the variants' turns side by side, with the scan counts.
  - Get the owner's verdict, quoted: does `barrier` play out as a barrier, `similar` as effortful talk, and `none` as fluent talk?
  - End with what this settles for part 4's scene note.
- [ ] **Step 5: Commit** with the message `probe(languages): scene language results`.

### Task 9: Hand-off

- [ ] **Step 1: Run the plain suite** (`uv run --no-sync pytest -q`) and the full e2e suite once more on the branch. Expected: 0 failures.
- [ ] **Step 2: Summarise for the owner.** Collect the three reports' decisions into a short list for the part-3 brainstorm:
  - where language-making runs;
  - whether the culture-design skill was deleted or kept;
  - flagging quality;
  - scene-note behaviour.

  Then use superpowers:finishing-a-development-branch.
