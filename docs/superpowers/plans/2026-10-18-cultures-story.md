# Cultures in the Story Implementation Plan (plan 3 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the cultures in the story. Foreign words and phrases get blue italic highlights whose bubble shows the translation. Name bubbles gain a language section. Unreviewed names carry an amber dot. The scene's World panel shows culture chips. The app-level World Editor tab shows the unreviewed count from the moment a scene loads. Every Review button and review dot lands on its item in the Cultures tab.

**Architecture:**
- **Backend (pure).** Two new modules under `src/talemate/cultures/`:
  - `lexicon.py` decides which phrases and words may be highlighted. It holds the English-safety rule.
  - `story.py` builds what the bubbles and chips need: name info, character cultures and place mixes.
- **Backend (plugin).** The existing `cultures` websocket plugin gains a `get_story` action and two pushes, `counts` and `story`. Both are sent with every `world` reply and after the Culture agent's `name_chosen` and `snapshot_processed` events. The frontend asks for them when a scene finishes loading. The scene's cultures come from the Culture agent (`scene_cultures`).
- **Frontend (pure).** `components/cultures/storyLexicon.js` holds every decision as plain functions: match variants, mention lists, name lookups, bubble and chip view-models, review-target resolution and message ingestion. A node script checks it, together with the renderer.
- **Frontend (wiring).** A tiny reactive store, `culturesStory.js`, is fed by TalemateApp, which always runs, so the badge works before the Cultures tab has ever been opened. The renderer gains a second highlight kind, `foreign`. The highlight mixin passes foreign mentions for every message. New components hold the bubble sections, the chips and the World panel's places list. Review jumps go through `requestReview` and a pending target that the Cultures tab consumes.
- **Testing:**
  - pytest for the backend
  - a node check script for the pure JS (no JS test framework), wrapped in a pytest test
  - Playwright browser tests in `tests/e2e/cultures/test_story.py`
  - one opt-in AI test that the controller runs

**Tech Stack:** Python 3.11, pydantic 2, pytest (pytest-asyncio, `asyncio_mode=auto`), Vue 3 + Vuetify 3, `marked` (already used by the renderer), Node (from `manifest.scm`), Playwright.

**Spec:** `docs/superpowers/specs/2026-10-17-cultures-and-languages-design.md`. Read:
- §6.2 "In the story"
- §8.1 "Review"
- §4, anti-goals 2 and 3
- §10, the core-edit rule

This plan builds on:
- plan 1, `docs/superpowers/plans/2026-10-17-cultures-foundation.md`: the models, `WorldStore`, the plugin and the Cultures tab
- plan 2, `docs/superpowers/plans/2026-10-18-cultures-ai.md`: `words.py`, `scene_context.py`, the Culture agent, `cultures.event`, `seed.py` and the AI driver

Its Interfaces blocks describe the existing API. The visual reference is the approved mockup: the `hl`, `renderScene` and `bubbleHTML` functions in `/tmp/claude-1000/-home-skeleton-Projects-Web-talemate/0ddab8b2-7e3a-438e-af8b-816df8d51f0a/scratchpad/talemate-languages.html`. If `/tmp` has been cleared, use the spec header's link (version 4).

**The four plans:**
1. *Foundation* (done)
2. *AI use* (done)
3. *In the story* (this plan)
4. *Rename everywhere*

Nothing in this plan renames anything (that is spec §8.2).

**Branch.** Work on a new branch stacked on `feature/cultures-ai`, e.g. `feature/cultures-story`.

**Environment.** This is a Guix machine. Every command runs from the repo root through `guix shell -m manifest.scm -- …`. Always use `uv run --no-sync`; a plain `uv run` drops the dev extra.
- Plain suite: `guix shell -m manifest.scm -- uv run --no-sync pytest`. Add `-n0 -v` and a path to run one file. There are 141 known failures from missing NLTK `punkt_tab` data, so judge a run by "no new failures".
- JS checks: `guix shell -m manifest.scm -- sh -c 'cd talemate_frontend && node checks/culturesStory.check.mjs'`
- Browser group: `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e -m e2e -n0 -v`. Pass a file path instead of `tests/e2e` to run one file.
- AI group (**controller only**): `TALEMATE_AI_TESTS=1 guix shell -m manifest.scm -- uv run --no-sync pytest tests/ai -m ai -n0 -v`
- Frontend build: `guix shell -m manifest.scm -- sh -c 'cd talemate_frontend && npx --yes corepack@0.34.0 pnpm run build'`
- Lint: `guix shell -m manifest.scm -- uv run --no-sync ruff check <paths>` and `… ruff format --check <paths>`

## Global Constraints

- **Core edits: exactly these six files, and nothing else outside the cultures feature files.** No backend core file changes.
  1. `talemate_frontend/src/utils/sceneMessageRenderer.js`:
     - the `foreign` highlight kind
     - the `data-entity-unreviewed` attribute
     - the `foreign` style default
     - a WeakMap cache in `compileEntityMentions`, which is now exported
  2. `talemate_frontend/src/components/EntityHighlightMixin.js`:
     - foreign mentions on every message
     - unreviewed flags on name mentions
     - clicks on `.scene-foreign`
     - one CSS import
  3. `talemate_frontend/src/components/EntityTooltip.vue`:
     - the `ForeignWordCard` branch
     - the `NameLanguageSection` slot under the snapshot text
  4. `talemate_frontend/src/components/TalemateApp.vue`:
     - one `ingestCulturesMessage` call at the top of `handleMessage`
     - a `badge` on the World Editor tab, with its `<v-badge>` in the tab template
     - `openCulturesReview` in `provide()`
  5. `talemate_frontend/src/components/WorldStateManager.vue`: the Cultures tab badge reads `culturesStory.counts` (closes plan 1's "badge shows 0 until the tab is opened" gap).
  6. `talemate_frontend/src/components/WorldState.vue`:
     - a `CultureChip` in each character title
     - a `places` data field, filled from the `world_state` message
     - a `<WorldPanelPlaces>` between the characters and the items
- **Feature files this plan may change:**
  - backend: `src/talemate/cultures/store.py`, `src/talemate/server/cultures.py`, `src/talemate/agents/culture/__init__.py`
  - frontend: everything under `talemate_frontend/src/components/cultures/`
  - tests: `tests/e2e/seed.py`, `tests/server/test_cultures_plugin.py` (order expectations only), `docs/dev/local-testing.md`, and the plan-1 follow-ups note
- **Ordinary English is never highlighted** (anti-goal 2). Only stored phrases, and glossary entries of kind `word` or `thing`, from the cultures present in the scene are highlighted, and only when `can_highlight` (Task 1) allows it. The rule:
  - A **single word** needs at least 4 letters and must not be common. "Common" means `talemate.cultures.words._is_common_word`: `COMMON_WORDS` after the possessive and plural are normalised.
  - A **multi-word glossary text** needs no common word at all, plus one qualifying word.
  - A **phrase** needs one qualifying word.
  - Glossary `thing` entries whose origin is `ai_free` and that have no meaning are left out. These are names the narrator wrote and the snapshot caught, not language words.
- **Matching happens in the frontend**, whole-word and case-insensitive. Apostrophes `'` and `’` are interchangeable, and leading or trailing punctuation is ignored. When a name and a foreign entry have the same text, the name wins. Otherwise the longest match wins. Each entry is highlighted only on its first occurrence per message, like names.
- **Where highlights show:** foreign words on every story message, and names only on the snapshot's anchor messages, as today. The Appearance toggle that hides entity highlights (`entities.show === false`) hides foreign highlights too.
- **Colours and styles:**
  - Names keep the existing amber dotted underline.
  - Foreign words: colour `rgb(var(--v-theme-highlight7))`, italic, dotted underline, and a hover background of `rgba(var(--v-theme-highlight7), 0.15)`.
  - The unreviewed dot: a 5px circle in `rgb(var(--v-theme-unsaved))`, superscript, after the name.
- **Copy, exactly:**
  - Foreign card:
    - the button "Open in {culture name}"
    - the existing "Configure highlights" button
  - Name section:
    - row labels "Language", "Culture", "True name"
    - the chip "none yet"
    - the notes "invented freely by the AI" / "no language yet" / "no meaning recorded"
    - the culture notes "Worked out by the AI · {reason}" (with no reason, just "Worked out by the AI"), "Set by you", "From {place}", plus " · not sure" when unsure
    - the button "Change"
  - Review note:
    - "Added by the AI, not reviewed yet." for `ai` / `ai_free` origins, otherwise "Not reviewed yet."
    - then " Picked from {generator name}." when the generator is known
    - the button "Review"
  - Chips: "No culture", "No language". A multi-culture place reads "{top culture} +{n}".
- **Nothing blocks or breaks play.**
  - Building the story payload never raises. Errors are logged and sent as `{"available": true, "error": …}` with empty lists.
  - A scene with no shared world gets `{"available": false}` and `counts == {}`: no highlights, no chips, no badge.
  - No model calls anywhere in this plan.
- **When `story` and `counts` are sent:**
  - with every `world` reply, in the order `counts`, `story`, `world`, so `world` stays last
  - on `get_story`
  - after the agent events `name_chosen` and `snapshot_processed`, whether or not they changed anything
  - never after `context_injected`, which happens every turn
- **Data shapes.** The JSON key names in Tasks 1–3 are a contract with the frontend. Keep them exactly.

## Review Focus

These are the inputs most likely to bite the owner, though no spec line names them. Each has a test in the task that owns the code.

1. **The narrator spells a stored phrase slightly differently:**
   - a curly apostrophe (`Rhok tal’dun`)
   - different case (`rhok TAL'DUN`)
   - the phrase's own `!` or `.` left off, or a comma added
   - the phrase inside quotation marks

   It must still highlight, and it must never match inside a longer word (`Rhokbert`, `saerviking`). (Task 4: checks `variants`, `case_and_quotes`, `word_boundary`)
2. **A name and a foreign entry overlap:**
   - the same text (a place "Veldhaer" and a glossary thing "Veldhaer")
   - a name inside a phrase ("Dhun" inside "Dhun sa'ver, kaeth sa'ver.")

   The result is exactly one span per occurrence, never nested spans. The name wins on equal text, and the longer phrase wins otherwise. (Task 4: check `overlap`)
3. **Switching scenes, or a scene with no shared world.** A stale lexicon or badge from the previous scene must clear on `scene.loading`. A world-less scene shows no highlights, no badge and no console errors. (Task 4: check `ingest_resets_on_scene_loading`; Task 5: `test_no_world_no_highlights_or_badge`)
4. **A big world**, with 1,500 lexicon entries and 200 messages. The match regex is built once per mention list, not once per message, so rendering stays fast. (Task 4: checks `compile_cache` and `perf`)
5. **A review target that is gone by the time it's clicked**, because the entry was deleted or reviewed elsewhere, or the phrase was removed. The Cultures tab opens on its normal page, with no error and no stuck pending jump. (Task 7: check `resolve_missing_target`; `test_review_jump_to_missing_entry_is_harmless`)

---

### Task 1: The lexicon builder (backend, pure)

**Files:**
- Create: `src/talemate/cultures/lexicon.py`
- Test: `tests/cultures/test_lexicon.py`

**Interfaces:**
- Consumes: `Culture`, `Phrase`, `GlossaryEntry` (plan 1), `_is_common_word` (plan 2, `words.py`).
- Produces:
  - `MIN_WORD_LETTERS = 4`; `MAX_LEXICON_ENTRIES = 1500`
  - `word_tokens(text: str) -> list[str]`: runs of letters, which may contain an inner `'`, `’` or `-` (regex `[^\W\d_]+(?:['’-][^\W\d_]+)*`).
  - `can_highlight(text: str, *, phrase: bool = False) -> bool`. A token *qualifies* when its letters (ignoring `'’-`) number at least `MIN_WORD_LETTERS` and `not _is_common_word(token)`. The rules:
    - no tokens → False
    - one token → whether it qualifies
    - several tokens, `phrase=True` → any token qualifies
    - several tokens, `phrase=False` → no token is common, and any token qualifies
  - `phrase_kind(category: str) -> str`: the first letter-run of the category, lowercased, with a trailing `s` dropped when it is longer than 3 letters; `"phrase"` when empty.
  - `class LexiconEntry(BaseModel)`, with fields:
    - `id: str`: `"phrase:{culture_id}:{phrase_id}"` or `"glossary:{entry_id}"`
    - `text: str`: the phrase's `original` or the entry's `text`, exactly as stored
    - `kind: str`: `phrase_kind(category)` for phrases, `"word"` for glossary `word` and `thing` entries
    - `culture_id: str`, `culture_name: str`, `language_name: str`, `color: str`
    - `translation: str`, `breakdown: list[list[str]] = []`, `usage: str = ""`
    - `target: dict`: `{"type":"phrase","culture_id","phrase_id"}` or `{"type":"glossary","entry_id"}`
  - `normalize_key(text: str) -> str`: lowercase, `’` becomes `'`, inner whitespace collapsed, leading and trailing `.,;:!?…"“”‘'()` and spaces stripped.
  - `build_scene_lexicon(present: list[Culture], glossary: list[GlossaryEntry]) -> list[LexiconEntry]`:
    - For each present culture in order:
      - **Phrases.** Every phrase with a non-empty `original` that passes `can_highlight(original, phrase=True)`. `translation`, `breakdown` and `usage` come from the phrase.
      - **Glossary entries** with `language == culture.id`, `kind in {"word","thing"}`, and `can_highlight(text)`. Skip `origin.by == "ai_free"` with an empty `meaning`.
        - `translation` is the entry's `meaning`. When that is empty, use the meaning of the dictionary entry whose `word` equals the text, case-insensitively. Otherwise use `""`.
        - `usage` is that dictionary entry's `notes`, otherwise `""`.
    - Deduplicate on `normalize_key(text)`; the first one wins, so phrases beat glossary words.
    - Cut to `MAX_LEXICON_ENTRIES`, keeping list order.

- [ ] **Step 1: Write the failing tests.**
  - **Fixtures.** Load Taelrik with `CultureFile.model_validate_json(Path("tests/cultures/data/taelrik.culture.json").read_text()).culture`. Build glossary entries in-test with `GlossaryEntry(..., origin=GlossaryOrigin(by=…))`.
  - `test_can_highlight_single_words`:
    - True: `"saervik"`, `"Rhok"`, `"dhaer"`
    - False: `"tal"`, `"the"`, `"lantern"`, `"Lanterns"`, `"lantern's"`, `"river"`, `""`, `"1234"`
  - `test_can_highlight_phrases_and_multiword_names`:
    - With `phrase=True`: `"Rhok tal'dun!"` and `"Vel'dhaer ossa tae."` are True; `"Go home"` is False.
    - With `phrase=False`: `"Grey Gull"` is False; `"Saervik Dhun"` is True.
  - `test_phrase_kind`:
    - `"curse"` gives `"curse"`; so does `"Curses"`
    - `"Sayings & blessings"` gives `"saying"`
    - `"Greetings"` gives `"greeting"`
    - `"inscription"` gives `"inscription"`
    - `""` gives `"phrase"`
  - `test_lexicon_phrases_and_words`: with present `[taelrik]` and a `saervik` thing (meaning "river-runner; a flat ferry boat", origin import):
    - all four phrase originals and `"saervik"` are present
    - the entry with id `"phrase:taelrik:curse-rot"` has:
      - `kind == "curse"`
      - `translation == "Rot your roots!"`
      - `breakdown == [["rhok","rot"],["tal","your (scornful)"],["dun","roots"]]`
      - `usage == "Common, coarse. Spat, not said."`
      - `culture_name == "Taelrik"`, `color == "#FF8A65"`
      - `target == {"type":"phrase","culture_id":"taelrik","phrase_id":"curse-rot"}`
    - saervik has `kind == "word"` and `target == {"type":"glossary","entry_id": <its id>}`
  - `test_lexicon_excludes_names_english_and_absent_cultures`. None of these are present:
    - the person `Kethrun` and the place `Veldhaer` (taelrik)
    - a word `"Lantern"` and a word `"tal"`
    - an `ai_free` thing `"Seawolf"` with no meaning
    - an Elsiri word `"saelin"` when Elsiri isn't present
  - `test_lexicon_dictionary_meaning_and_dedupe`:
    - a glossary word `"dhaer"` with an empty meaning gets `translation == "ford, river crossing"`
    - a glossary word `"rhok tal’dun"` gives no second entry beside the phrase
  - `test_lexicon_cap`: 2,000 generated qualifying words give `len == 1500`, and the 4 phrases come first.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/cultures/test_lexicon.py -n0 -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** `lexicon.py` and export `LexiconEntry` and `build_scene_lexicon` in its `__all__`.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit**: `git add src/talemate/cultures/lexicon.py tests/cultures/test_lexicon.py && git commit -m "feat(cultures): scene lexicon for foreign-word highlights"`

---

### Task 2: Story data and counts (backend, pure)

**Files:**
- Create: `src/talemate/cultures/story.py`
- Modify: `src/talemate/cultures/store.py`. Extract the counts computation from `snapshot()` into `WorldStore.counts() -> dict`; `snapshot()` uses it, and its output is unchanged.
- Test: `tests/cultures/test_story.py`, `tests/cultures/test_store.py` (extend)

**Interfaces:**
- Consumes: `effective_mix` (plan 1), `clean_name` (plan 2), the models.
- Produces, in `story.py` (all `BaseModel`):
  - `NameInfo`, with fields:
    - `id`, `text`, `kind`, `status`
    - `culture_id: str | None`, `culture_name: str | None`, `language_name: str | None`, `color: str | None`
    - `writable: bool = True`, `meaning: str = ""`, `true_name: str = ""`
    - `renderings: list[dict]`, each `{"culture_id","culture_name","text"}`; `culture_name` falls back to the id when the culture is unknown
    - `origin_by: str`, `generator_name: str | None`: the name of the generator `origin.generator_id` in that culture's language
    - `doesnt_fit: bool = False`, `character_name: str | None`, `place_id: str | None`
  - `CharacterInfo`, with fields:
    - `name`
    - `culture_id: str | None`, `culture_name: str | None`, `color: str | None`
    - `set_by: Literal["ai","owner"] | None`, `unsure: bool = False`, `reason: str = ""`
  - `PlaceInfo`, with fields:
    - `id`, `name`, `kind`
    - `own: bool`: true when the place's own cultures are the effective mix
    - `source_name: str | None`: the source place's name when it's inherited
    - `mix: list[dict]`, each `{"culture_id","culture_name","color","share"}`, share descending
    - `set_by`, `unsure`
  - `scene_name_keys(names: Iterable[str]) -> set[str]`: `clean_name(n).lower()` for each non-empty name.
  - `build_story(*, cultures: dict[str, Culture], places: list[Place], glossary: list[GlossaryEntry], characters: list[Character], scene_names: set[str]) -> dict`. It returns `{"names": [...], "characters": [...], "places": [...]}`, every item `model_dump(mode="json")`:
    - **names:** glossary entries of kind `person`, `place` or `thing` whose `text`, any rendering value, or `character_name`, put through `clean_name(…).lower()`, is in `scene_names`. At most 500, in glossary order.
    - **characters:** one `CharacterInfo` per character, sorted by name.
    - **places:** one `PlaceInfo` per place, in file order.
- Produces, in `store.py`: `WorldStore.counts() -> dict`, with the same keys as `snapshot()["counts"]`.

- [ ] **Step 1: Write the failing tests.**
  - **Fixtures.**
    - `build_places()` and `build_cultures()` from `tests/cultures/_fixtures.py`.
    - Replace the Taelrik culture with the real fixture culture, so it has generators and colour `#FF8A65`.
    - A `ghun` culture whose language has `writable=False`, with the name "Ghûn".
  - `test_names_scoped_to_scene`: the glossary holds Kethrun, Veldhaer, Brannoch, saervik (thing) and Tovrin. With `scene_names = scene_name_keys(["Kethrun","Veldhaer","Tovrin's"])`, the name texts are exactly `{"Kethrun","Veldhaer","Tovrin"}`.
  - `test_name_info_fields`: Kethrun (person, taelrik, meaning "ford-born", unreviewed, origin `ai` with `generator_id="given_male"`) gives:
    - `generator_name == "Given names (male)"`
    - `culture_name == "Taelrik"` and `language_name == "Taelrik"`
    - `color == "#FF8A65"` and `writable is True`
  - `test_unwritable_name_info_matched_by_rendering`: the entry has text `"the north mountain"`, language `ghun`, `true_name="three falling hums"` and `renderings={"taelrik":"Khaz-Rull","nowhere":"X"}`. With `scene_names={"khaz-rull"}`:
    - it is included, with `writable is False`
    - `renderings == [{"culture_id":"taelrik","culture_name":"Taelrik","text":"Khaz-Rull"},{"culture_id":"nowhere","culture_name":"nowhere","text":"X"}]`
  - `test_character_infos`: three characters give these results, sorted by name:
    - an AI culture of taelrik, unsure, with a reason → `culture_name == "Taelrik"`
    - an owner culture with `culture_id=None` → `set_by == "owner"`, `culture_id is None`
    - no culture → `set_by is None`
  - `test_place_infos_inherit_and_mix`:
    - veldhaer: `own is False`, `source_name == "The Taelrik Reach"`, `mix == [{"culture_id":"taelrik","culture_name":"Taelrik","color":"#FF8A65","share":100}]`
    - dhunmouth: `own is True`, and its mix ids are `["taelrik","elsiri","vaskari"]`
  - In `test_store.py`, `test_counts_matches_snapshot`: on a store with unreviewed entries, an unsure place and an unreviewed addition, `store.counts() == store.snapshot()["counts"]`.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/cultures/test_story.py tests/cultures/test_store.py -n0 -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** `story.py` and `WorldStore.counts()`.
- [ ] **Step 4: Run** the same command, then `guix shell -m manifest.scm -- uv run --no-sync pytest tests/cultures tests/server/test_cultures_plugin.py -n0`. Expected: all pass.
- [ ] **Step 5: Commit**: `git commit -m "feat(cultures): story data for bubbles and chips"` (add the files first).

---

### Task 3: Plugin pushes `counts` and `story`

**Files:**
- Modify: `src/talemate/server/cultures.py`, `src/talemate/agents/culture/__init__.py`
- Modify: `tests/server/test_cultures_plugin.py`. Only update `test_event_for_this_world_pushes_world_and_forwards`, whose action list becomes `["counts","story","world","snapshot_processed"]`, and fix any other test that asserts an exact message list.
- Test: `tests/server/test_cultures_story_plugin.py` (new)

**Interfaces:**
- Consumes: `build_scene_lexicon` (Task 1), `build_story`, `scene_name_keys`, `WorldStore.counts()` (Task 2), and `CultureAgent.load_world()` / `scene_cultures()` (plan 2).
- Produces, in the agent: `CultureAgent.scene_cultures(world, remember: bool = True)`. When `remember` is False, it does not call `set_scene_states`.
- Produces, in `CulturesPlugin`:
  - `_with_character_counts(counts: dict) -> dict`: adds `unsure_characters` and folds it into `unreviewed_total`, as `_send_world` already does. `_send_world` now uses it.
  - `_present_cultures() -> list[Culture]`:
    1. `agent = instance.get_agent("culture")`.
    2. Return `[]` unless the agent exists, `agent.scene is self.scene`, and `agent.load_world()` is not None.
    3. Otherwise return `agent.scene_cultures(world, remember=False).cultures`.
  - `_scene_names() -> set[str]`: `scene_name_keys` of the keys of `scene.world_state.characters`, `.items` and `.places`, plus `scene.character_data`.
  - `_send_counts(store)`: queues `{"type":"cultures","action":"counts","data": counts}`. `counts` is `{}` when `store is None` or on any error, which is logged.
  - `_send_story(store)`: queues `{"type":"cultures","action":"story","data": …}`:
    - with no world: `{"available": False}`
    - normally: `{"available": True, "world_name", "lexicon": [LexiconEntry dumps], **build_story(...)}`
    - on any exception: logged, and `{"available": True, "world_name", "error": str, "lexicon": [], "names": [], "characters": [], "places": []}`
  - `_send_world(store)` first calls `_send_counts(store)` and `_send_story(store)`, then queues `world` as before.
  - `handle_get_story(data)`: `_send_counts` then `_send_story`.
  - `on_cultures_event`:
    - when `changed`: unchanged, because `_send_world` now includes both pushes
    - else, when `event.kind in ("name_chosen", "snapshot_processed")`: `_send_story`
    - then it forwards the event as before

- [ ] **Step 1: Write the failing tests** in `tests/server/test_cultures_story_plugin.py`.
  - **Setup.** Copy the setup of `tests/test_culture_agent.py`: `MockScene`, `bootstrap_scene`, `_link_world` and `apply_import` of the Taelrik fixture, plus `build_places` saved with `save_places`. Use the `_MockWebsocketHandler` from `server.test_cultures_plugin`.
    - `scene.world_state.location = "The Quillister inn in Veldhaer"`.
    - Kethrun is in `scene.character_data` with `CharacterCulture(culture_id="taelrik")`.
    - `scene.world_state.characters = {"Kethrun": CharacterState(snapshot="x")}`; use the right state class from `talemate.world_state`.
  - `test_get_story_without_world`: a scene with no shared context gives the actions `["counts","story"]`, with `counts.data == {}` and `story.data == {"available": False}`.
  - `test_get_story_has_lexicon_names_and_counts`:
    - `counts.data["unreviewed_total"] == store.counts()["unreviewed_total"]`
    - story `lexicon` texts include `"Rhok tal'dun!"` and `"saervik"`
    - `names` texts include `"Kethrun"`
    - `characters[0]["culture_name"] == "Taelrik"`
  - `test_lexicon_empty_when_agent_disabled_or_other_scene`:
    - `agent.is_enabled = False` → `lexicon == []`, `names` non-empty, `available is True`
    - re-enabled, but with `agent.scene` set to another `MockScene()` → `lexicon == []`
  - `test_scene_cultures_remember_false`: `agent.scene_cultures(world, remember=False)` leaves `agent.get_scene_state("current_place_id")` unset.
  - `test_world_reply_sends_counts_story_then_world`: after `handle_review_glossary_entry(...)`, the last three actions are `["counts","story","world"]`.
  - `test_agent_events_push_story`:
    - `CulturesEvent(kind="snapshot_processed", changed=False, …)` for this world gives `["story","snapshot_processed"]`
    - a `context_injected` event gives only `["context_injected"]`
  - `test_story_errors_reported_not_raised`: write `"{"` into `glossary.json`. `handle_get_story({})` raises nothing; `counts.data == {}`, `story.data["error"]` is non-empty, and `story.data["lexicon"] == []`.
- [ ] **Step 2: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/server/test_cultures_story_plugin.py -n0 -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the plugin and agent changes.
- [ ] **Step 4: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/server/test_cultures_story_plugin.py tests/server/test_cultures_plugin.py tests/test_culture_agent.py tests/test_culture_snapshot.py -n0 -v`. Expected: all pass.
- [ ] **Step 5: Commit**: `git commit -m "feat(cultures): push story data and counts from the cultures plugin"`

---

### Task 4: Pure story logic in JS, and the renderer's `foreign` kind

**Files:**
- Create:
  - `talemate_frontend/src/components/cultures/storyLexicon.js`. Relative imports only; no Vue or `@/` imports, so node can load it.
  - `talemate_frontend/checks/culturesStory.check.mjs`
  - `tests/dev/test_frontend_checks.py`
- Modify (core edit 1): `talemate_frontend/src/utils/sceneMessageRenderer.js`
- Modify: `docs/dev/local-testing.md`. Under "The three test groups", add a short "Frontend logic checks" paragraph with the JS-check command, noting that the plain suite runs it through `tests/dev/test_frontend_checks.py`.

**Interfaces:**
- Consumes: the `story` payload (Task 3).
- **`storyLexicon.js` (this task's part).** Later tasks add `nameSection`, `resolveReviewTarget`, `characterChip` and `placeChip`, with their own checks.
  - `FOREIGN_KIND = 'foreign'`
  - `emptyStoryState() -> {counts: {}, story: {available: false, lexicon: [], names: [], characters: [], places: []}, pendingReview: null, reviewSeq: 0}`
  - `matchVariants(text: string) -> string[]`: normalise `’`/`‘` to `'`, collapse whitespace, and strip leading and trailing `.,;:!?…"“”‘'()` and spaces. It returns `[]` when nothing is left. Otherwise it returns `[straight]`, plus a version with `’` in place of every `'` when the text has one.
  - `foreignMentions(lexicon: LexiconEntry[]) -> Mention[]`: `{name: entry.id, kind: FOREIGN_KIND, subkind: entry.kind, phrases: matchVariants(entry.text)}`. Entries with no variants are dropped.
  - `nameKey(text: string) -> string`: lowercase, trim, `’` becomes `'`, strip trailing `.,;:!?` and a trailing `'s`.
  - `buildNameIndex(names: NameInfo[]) -> Map<string, NameInfo>`: keys are `nameKey` of `text`, of each rendering's `text`, and of `character_name`. The first entry wins.
  - `markUnreviewed(entityMentions: Mention[], index) -> Mention[]`: a new array. A mention whose `nameKey(name)` maps to a `status === 'unreviewed'` info gets `unreviewed: true`.
  - `combineMentions(entityMentions, foreign) -> Mention[]`: `[...entityMentions, ...foreign]`.
  - `findLexiconEntry(story, id) -> LexiconEntry | null`
  - `applyCulturesMessage(state, data) -> object | null`. It mutates `state` in place:
    - `{type:'system', id:'scene.loading'}` resets `counts`, `story` and `pendingReview` to empty (it keeps `reviewSeq`) → `null`
    - `{type:'system', id:'scene.loaded'}` → returns `{type:'cultures', action:'get_story'}`
    - `{type:'cultures', action:'counts'}` → `state.counts = data.data || {}`
    - `{type:'cultures', action:'world'}` → `state.counts = data.data?.counts || {}`
    - `{type:'cultures', action:'story'}` → `state.story = {...emptyStoryState().story, ...data.data}`
    - anything else → `null`
- **The renderer (core edit 1):**
  - `export function compileEntityMentions(mentions)`: memoised in a module-level `WeakMap` keyed by the array, so the same array gives the same object. `phraseToEntity[key]` becomes `{name, kind, subkind: entity.subkind || null, unreviewed: !!entity.unreviewed}`.
  - `DEFAULTS.foreign = {color: 'rgb(var(--v-theme-highlight7))', italic: true, bold: false}`. Add `this.config.foreign = merge('foreign', {className: 'scene-foreign'}, {color: DEFAULTS.foreign.color, bold: false, italic: true})`.
  - The `sceneEntity` token carries `entitySubkind` and `entityUnreviewed`. The renderer:
    - when `this.config.entities.show === false`: plain text, as today, for both kinds
    - the first-occurrence dedupe as today (`kind:name`)
    - kind `foreign`: `<span class="scene-foreign" data-foreign-id="{id}" data-foreign-kind="{subkind}" style="{foreign style}">{text}</span>`
    - other kinds: the existing span, plus ` data-entity-unreviewed="true"` when the mention was unreviewed
    - every attribute value goes through `escapeHtmlAttr`

- [ ] **Step 1: Write the failing check script** `checks/culturesStory.check.mjs`.
  - **Its runner.** A tiny `check(name, fn)` that records failures, then prints `ok <n> checks` and exits 0, or prints each failure and exits 1. It uses `node:assert/strict` and imports `../src/components/cultures/storyLexicon.js` and `../src/utils/sceneMessageRenderer.js`.
  - **Fixture.** A curse entry `{id:'phrase:taelrik:curse-rot', text:"Rhok tal'dun!", kind:'curse', …}`.
  - **The checks:**
    - `variants`:
      - `matchVariants("Rhok tal'dun!")` deep-equals `["Rhok tal'dun","Rhok tal’dun"]`
      - `matchVariants("Rhok tal’dun")` gives the same
      - `matchVariants("  saervik ")` gives `["saervik"]`
      - `matchVariants("Dhun sa'ver, kaeth sa'ver.")[0] === "Dhun sa'ver, kaeth sa'ver"`
      - `matchVariants("!!")` gives `[]`
    - `case_and_quotes`: `new SceneTextParser().parse('"rhok TAL’DUN," he said.', {mentions: foreignMentions([curse])})` contains `class="scene-foreign"`, `data-foreign-id="phrase:taelrik:curse-rot"`, `data-foreign-kind="curse"` and `font-style: italic`. The span's inner text is `rhok TAL’DUN`.
    - `word_boundary`: a mention for `saervik` leaves `saerviking` unwrapped; the curse leaves `Rhokbert tal'dunny` unwrapped.
    - `overlap`:
      - Entity `{name:'Dhun',kind:'place',phrases:['Dhun']}` combined with the foreign phrase `"Dhun sa'ver, kaeth sa'ver."`, on `"Dhun sa'ver, kaeth sa'ver. Later, Dhun again."`: exactly one `scene-foreign` span; one `scene-entity` span, after it; and no `scene-entity` inside the foreign span.
      - Entity "Veldhaer" combined with a foreign glossary word "Veldhaer": one `scene-entity` span and no `scene-foreign`.
    - `first_occurrence_only`: the curse twice in one text gives one span.
    - `unreviewed`: `markUnreviewed` with an index holding Kethrun `status:'unreviewed'` gives `data-entity-unreviewed="true"`. With `'reviewed'` the attribute is absent.
    - `show_false`: `new SceneTextParser({entities: {show: false}})` gives no `scene-foreign` and keeps the text.
    - `name_key_and_index`:
      - `nameKey("Tovrin’s") === "tovrin"`; `nameKey(" Kethrun. ") === "kethrun"`
      - `buildNameIndex` finds an unwritable entry by its rendering "Khaz-Rull"
    - `compile_cache`: `compileEntityMentions(arr) === compileEntityMentions(arr)`.
    - `perf`: 1,500 generated foreign mentions (`"zq" + i + "vek"`) and 200 parses of a 400-character text finish in under 5,000 ms.
    - `ingest_resets_on_scene_loading`:
      - On `s = emptyStoryState()`, a `counts` message sets `s.counts.unreviewed_total`, and a `story` message sets the lexicon.
      - `scene.loading` empties both and keeps `reviewSeq`.
      - `scene.loaded` returns `{type:'cultures',action:'get_story'}`.
      - A `world` message sets the counts.
    - `find_lexicon_entry`
- [ ] **Step 2: Write the pytest wrapper** `tests/dev/test_frontend_checks.py::test_cultures_story_checks`:
  - It skips unless `shutil.which("node")` is set and `talemate_frontend/node_modules/marked` exists.
  - It runs `node checks/culturesStory.check.mjs` with `cwd=talemate_frontend` and a 120 s timeout.
  - It asserts `returncode == 0` and `"ok " in stdout`, and shows stdout and stderr on failure.
- [ ] **Step 3: Run** the JS-check command. Expected: FAIL (missing exports).
- [ ] **Step 4: Implement** `storyLexicon.js` (this task's part) and the renderer edit.
- [ ] **Step 5: Run** the JS-check command, then `guix shell -m manifest.scm -- uv run --no-sync pytest tests/dev/test_frontend_checks.py -n0 -v`, then the frontend build. Expected: `ok …`, PASS, and a successful build.
- [ ] **Step 6: Commit**: `git commit -m "feat(cultures): foreign-word highlight kind and pure story logic"`

---

### Task 5: Shared state, highlights in the story, and the app badge

**Files:**
- Create:
  - `talemate_frontend/src/components/cultures/culturesStory.js`
  - `talemate_frontend/src/components/cultures/story.css`
  - `tests/e2e/cultures/data/ghun.culture.json`
  - `tests/e2e/cultures/test_story.py`
- Modify (core edits 2, 4, 5): `EntityHighlightMixin.js`, `TalemateApp.vue`, `WorldStateManager.vue`
- Modify: `tests/e2e/seed.py`, `tests/e2e/test_fixtures.py` (extend)

**Interfaces:**
- Consumes: Task 4's functions, and `tests/e2e/seed.py` (plan 2).
- **`culturesStory.js`:**
  - `culturesStory = reactive(emptyStoryState())`
  - `ingestCulturesMessage(data, send: (payload) => void)`: calls `applyCulturesMessage(culturesStory, data)`, and `send`s the payload it returns, if any.
  - `requestReview(target)`: sets `pendingReview = target`, `reviewSeq += 1`.
  - `takePendingReview() -> target | null`: returns the pending target and clears it.
- **`story.css`** (global, imported by the mixin):
  - `.scene-foreign`: cursor pointer, `text-decoration: underline dotted currentColor`, `text-underline-offset: 3px`, `border-radius: 2px`
  - `.scene-foreign:hover`: the highlight7 background
  - `.scene-entity[data-entity-unreviewed]::after`: the 5px dot from Global Constraints
- **Mixin (core edit 2):**
  - `import '@/components/cultures/story.css'`
  - computed `culturesForeignMentions`: `foreignMentions(culturesStory.story.lexicon || [])`
  - computed `culturesNameIndex`: `buildNameIndex(culturesStory.story.names || [])`
  - computed `culturesAnchorMentions`: `combineMentions(markUnreviewed(this.worldStateMentions, this.culturesNameIndex), this.culturesForeignMentions)`
  - `getEntityMentionsForMessage(id)`:
    - an anchor message gets `culturesAnchorMentions`, or `NO_ENTITY_MENTIONS` when it's empty
    - any other message gets `culturesForeignMentions` when non-empty, otherwise `NO_ENTITY_MENTIONS`
  - `onMessageContainerClick`: a click on `.scene-foreign` (checked first) looks up `findLexiconEntry(culturesStory.story, span.dataset.foreignId)`. When found, it calls `event.stopPropagation()` and `openEntityTooltip(span, {kind: 'foreign', name: entry.text, foreign: entry})`.
  - `onDocumentClickForTooltip` also ignores clicks inside `.scene-foreign`.
- **TalemateApp (core edit 4):**
  - In `handleMessage`, after `JSON.parse`: `ingestCulturesMessage(data, (p) => this.websocket?.send(JSON.stringify(p)))`.
  - The World Editor tab object gains `badge: () => culturesStory.counts.unreviewed_total || 0`. The tab template renders `<v-badge v-if="tab.badge && tab.badge() > 0" inline color="unsaved" :content="String(tab.badge())" :data-testid="'app-tab-badge-' + tab.value" />` after the title.
  - `provide()` gains `openCulturesReview: (target) => { requestReview(target); this.$refs.sceneMessages?.closeEntityTooltip?.(); this.onOpenWorldStateManager('cultures'); }`. Task 7 makes the tab act on the pending target.
- **WorldStateManager (core edit 5):**
  - `culturesUnreviewed` becomes a computed: `culturesStory.counts.unreviewed_total || 0`
  - remove the `data` field and the `@cultures-counts` handler
- **Seed** (`tests/e2e/seed.py`):
  - `seed_world(..., world_state: dict | None = None)`. Inside the script, after the messages are added:
    - `ws = dict(world_state)`
    - `ws.setdefault("anchor_message_ids", [m.id for m in scene.history])`
    - `scene.world_state = WorldState(**ws)`
  - `seed_scene_without_world(root, project="e2e-plain", *, messages=(), world_state=None) -> Path` takes the same two arguments.
- **`ghun.culture.json`:**
  - `format_version` 1
  - culture `ghun`, named "Ghûn", colour `#B0BEC5`, a one-line description
  - language "Ghûn", `level: "description"`, `writable: false`, sound "Hums and tongue-clicks, no letters."
  - no glossary
- **`test_story.py`'s seed helper**, `_seed_story(app, project, **overrides) -> SeededWorld`. It calls `seed_world`, then `place_culture` for Taelrik and Ghûn, then `place_places`, then `place_glossary`, in that order:
  - `location="Veldhaer"`
  - **Messages:**
    - M1: `"The saervik ground against the shingle at Veldhaer, and Kethrun spat over the rail. Above the toll-house door someone had carved the old words: Dhun sa'ver, kaeth sa'ver. Far to the north, Khaz-Rull wore its collar of cloud."`
    - M2: `"“Rhok tal’dun!” Kethrun muttered at the knot. A lantern swung from the tal post near Quillister House."`
  - **World state:**
    - character Kethrun (snapshot "The ferryman.", emotion "irritable", mentions `["Kethrun"]`)
    - places Veldhaer, Khaz-Rull and Quillister House, each with a snapshot and its own name as the mention
  - **Character:** Kethrun, with `{"culture_id":"taelrik","set_by":"ai","unsure":false,"reason":"picked from the Veldhaer mix"}`
  - **Places:**
    - reach: "The Taelrik Reach", country, taelrik 100
    - veldhaer: town, under reach
    - quillister: building, under veldhaer
    - khaz: "Khaz-Rull", terrain, ghun 100
  - **Glossary**, with fixed ids:
    - `g-kethrun`: person, taelrik, "ford-born", unreviewed, origin `ai` with `given_male` and candidates `["Kethrun","Tovrin"]`, `character_name` "Kethrun"
    - `g-veldhaer`: place, taelrik, "grey ford", reviewed, import, `place_id` veldhaer
    - `g-saervik`: thing, taelrik, "river-runner; a flat ferry boat", reviewed, import
    - `g-lantern`: word "Lantern", taelrik, "a lamp", reviewed, owner
    - `g-tal`: word "tal", taelrik, "your (scornful)", reviewed, owner
    - `g-quillister`: "Quillister House", place, language `null`, unreviewed, `ai_free`
    - `g-khaz`: "Khaz-Rull", place, ghun, `true_name` "three falling hums ending in a tongue-click", `renderings` `{"taelrik":"Khaz-Rull"}`, reviewed, import, `place_id` khaz

  Expected `unreviewed_total`: 2.

- [ ] **Step 1: Write the failing seed test** in `tests/e2e/test_fixtures.py`: `test_seed_world_state_with_anchor_ids`. The saved scene JSON's `world_state.anchor_message_ids` equals the ids of its history messages, and `world_state.characters` has Kethrun's `mentions`.
- [ ] **Step 2: Write the failing browser tests** in `test_story.py`:
  - `test_foreign_words_highlighted_never_english`:
    - The set of `.scene-foreign` inner texts is exactly `{"saervik", "Dhun sa'ver, kaeth sa'ver", "Rhok tal’dun"}`.
    - The computed `font-style` of each is `italic`.
    - No `.scene-foreign` reads `lantern`, `Lantern` or `tal`.
  - `test_unreviewed_name_dot`: `.scene-entity[data-entity-name="Kethrun"][data-entity-unreviewed]` exists; the Veldhaer entity span has no `data-entity-unreviewed`.
  - `test_app_badge_before_cultures_tab_opened`:
    - Without opening the World Editor, `get_by_test_id("app-tab-badge-world")` reads `2`.
    - Then `send_backend(page, {"type":"cultures","action":"review_glossary_entry","entry_id":"g-kethrun","status":"reviewed"})`, and the badge reads `1`.
    - Opening the World Editor shows the Cultures tab badge `1`.
  - `test_no_world_no_highlights_or_badge`: `seed_scene_without_world` with M1 and the same world state.
    - M1's text is visible.
    - `.scene-foreign` count is 0, and there is no `app-tab-badge-world`.
    - No `page.console_errors` entry contains `TypeError` or `cultures`.
- [ ] **Step 3: Run** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e/test_fixtures.py tests/e2e/cultures/test_story.py -m e2e -n0 -v`. Expected: FAIL.
- [ ] **Step 4: Implement** the store, the CSS, the three core edits, the seed changes and the Ghûn fixture.
- [ ] **Step 5: Run** the frontend build, the JS-check command, then the Step 3 command, then `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e -m e2e -n0 -v`. Expected: the build succeeds, `ok`, PASS, and the existing e2e tests stay green.
- [ ] **Step 6: Commit**: `git commit -m "feat(cultures): foreign-word highlights in the story and the app-level badge"`

---

### Task 6: Bubbles: foreign-word card and name language section

**Files:**
- Create: `talemate_frontend/src/components/cultures/ForeignWordCard.vue`, `talemate_frontend/src/components/cultures/NameLanguageSection.vue`
- Modify (core edit 3): `talemate_frontend/src/components/EntityTooltip.vue`
- Modify: `storyLexicon.js` (add `nameSection`), `checks/culturesStory.check.mjs`, `tests/e2e/cultures/test_story.py`

**Interfaces:**
- Consumes: `culturesStory`, `nameKey`, `buildNameIndex` (Tasks 4–5), and the injected `openCulturesReview`.
- Produces, in `storyLexicon.js`: `nameSection(story, entity: {name, kind}) -> NameSectionModel | null`, where `kind` is `character`, `item` or `place`. The model:
  ```js
  {
    info,                 // NameInfo | null, looked up with nameKey(entity.name)
    language,             // {name: info.language_name, color} | null
    languageNote,         // shown when language is null: 'invented freely by the AI' (origin ai_free) or 'no language yet'
    meaning,              // info.meaning; the template shows 'no meaning recorded' when empty and a language is set
    trueName,             // {language_name, text: info.true_name, renderings} when info.writable === false and true_name is set, else null
    culture,              // {chips: [{name, color, share|null}], note, changeTarget} | null
    review,               // {note, target: {type:'glossary', entry_id: info.id}} when info.status === 'unreviewed', else null
  }
  ```
  - **`culture` for a character:** the `CharacterInfo` with that `nameKey` and a non-null `culture_id`.
    - chips: `[{name: culture_name, color, share: null}]`
    - note: `Worked out by the AI · {reason}` (or `Worked out by the AI` with no reason) for `set_by:'ai'`, `Set by you` for `owner`, plus ` · not sure` when `unsure`
    - `changeTarget`: `{type:'people', character_name}`
  - **`culture` for a place:** the `PlaceInfo` whose name matches by `nameKey`, also tried without a leading "the ", and that has a non-empty `mix`.
    - one chip per mix entry, with its share
    - note: `From {source_name}` when it's not `own`, otherwise the AI/owner note as for characters
    - `changeTarget`: `{type:'place', place_id}`
  - Items get no culture.
  - It returns `null` when both `info` and `culture` are null.
  - Review note text: `Added by the AI, not reviewed yet.` for origin `ai`/`ai_free`, otherwise `Not reviewed yet.`, followed by ` Picked from {generator_name}.` when that is set.
- **`ForeignWordCard`** (prop `entry: LexiconEntry`; emits `configure-highlights`), with `data-testid="foreign-word-card"`. Its layout follows the mockup's word bubble:
  - **Header:** the text in italic highlight7; a tonal highlight7 chip with `mdi-translate` and `entry.kind`; an outlined chip with `language_name`.
  - **Body:**
    - `entry.translation` (`data-testid="foreign-translation"`)
    - a breakdown grid when `breakdown.length` (`data-testid="foreign-breakdown"`, each cell the word in italic over its gloss)
    - `usage` as a caption
  - **Actions:**
    - a tonal button `Open in {culture_name}` (`mdi-book-open-variant`) that calls `openCulturesReview(entry.target)`
    - a spacer
    - the existing "Configure highlights" text button, which emits
- **`NameLanguageSection`** (prop `entity`). It renders nothing when `nameSection(...)` is null. Otherwise it renders a top-bordered block, `data-testid="name-language-section"`, with label rows in the mockup's `.langline` style:
  - **Language**, or **True name** for unwritable names:
    - Language: a chip with the language name, then `“{meaning}”` or the note
    - True name: a chip with `mdi-waveform` and the language name, then the description; then one row per rendering, labelled with the culture name and showing the text (`data-testid="name-true-name"`)
  - **Culture** (`data-testid="name-culture-row"`): the chips, the note, and a small text button `Change` that calls `openCulturesReview(changeTarget)`.
  - **The review block**, when `review` is set (`data-testid="name-unreviewed-note"`): a tonal amber box with `mdi-new-box` and the note, plus a warning-tonal button `Review` (`data-testid="name-review-button"`) that calls `openCulturesReview(review.target)`.
  - Both components inject `openCulturesReview` with a no-op default.
- **EntityTooltip (core edit 3):**
  - inside the `v-card`, `<ForeignWordCard v-if="entity?.kind === 'foreign'" :entry="entity.foreign" @configure-highlights="onConfigureHighlights" />`
  - the existing content goes in `<template v-else>`
  - `<NameLanguageSection :entity="entity" />` sits right after the snapshot / "No description" text

- [ ] **Step 1: Add the failing checks** to `culturesStory.check.mjs`:
  - `name_section_character`: Kethrun has an unreviewed `NameInfo` with generator "Given names (male)", and an AI `CharacterInfo` with reason "picked from the Veldhaer mix".
    - `culture.note === "Worked out by the AI · picked from the Veldhaer mix"`
    - `review.note === "Added by the AI, not reviewed yet. Picked from Given names (male)."`
    - `review.target` deep-equals `{type:'glossary', entry_id:'g-kethrun'}`
  - `name_section_place_inherited`: Veldhaer, inherited from "The Taelrik Reach", gives `culture.note === "From The Taelrik Reach"`, the chip `{name:'Taelrik', share:100}`, and `review === null` (reviewed).
  - `name_section_unwritable`: Khaz-Rull gives `trueName.text === "three falling hums ending in a tongue-click"` and `trueName.renderings[0].text === "Khaz-Rull"`.
  - `name_section_unassigned`: Quillister House (`ai_free`, no language) gives `language === null`, `languageNote === "invented freely by the AI"`, and the review note `"Added by the AI, not reviewed yet."`.
  - `name_section_none`: an unknown item name gives `null`.
- [ ] **Step 2: Add the failing browser tests** to `test_story.py`:
  - `test_foreign_bubble_curse`: clicking the `Rhok tal’dun` span shows `foreign-word-card` with:
    - a `curse` chip and a `Taelrik` chip
    - `foreign-translation` reading `Rot your roots!`
    - a breakdown containing `rhok` / `rot` and `dun` / `roots`
    - the usage text `Common, coarse. Spat, not said.`
    - the button `Open in Taelrik`
  - `test_foreign_bubble_word_has_no_breakdown`: saervik's card has the translation `river-runner; a flat ferry boat`, a `word` chip, and no `foreign-breakdown`.
  - `test_name_bubble_language_section`: the Kethrun bubble shows the existing snapshot "The ferryman." and a `name-language-section` with:
    - `Taelrik` and `“ford-born”`
    - a `name-culture-row` containing `Worked out by the AI · picked from the Veldhaer mix`
    - a `name-unreviewed-note` containing `Picked from Given names (male).`
    - the `Review` button
  - `test_unwritable_name_bubble`: Khaz-Rull's bubble shows `name-true-name` with `three falling hums ending in a tongue-click` and a `Taelrik` row reading `Khaz-Rull`.
  - `test_place_bubble_inherited_culture`: Veldhaer's bubble culture row contains `From The Taelrik Reach`, and there's no unreviewed note.
- [ ] **Step 3: Run** the JS-check command and `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e/cultures/test_story.py -m e2e -n0 -v`. Expected: the new checks and tests FAIL.
- [ ] **Step 4: Implement** `nameSection`, the two components and the tooltip edit.
- [ ] **Step 5: Run** the frontend build, the JS-check command and the Step 3 browser command. Expected: success, `ok`, PASS.
- [ ] **Step 6: Commit**: `git commit -m "feat(cultures): translation and language sections in story bubbles"`

---

### Task 7: Review jumps land on the item

**Files:**
- Modify, under `talemate_frontend/src/components/cultures/`: `WorldStateManagerCultures.vue`, `CulturePage.vue`, `GlossaryView.vue`, `PhraseList.vue`, `PeopleView.vue`, `storyLexicon.js` (add `resolveReviewTarget`)
- Modify: `checks/culturesStory.check.mjs`, `tests/e2e/cultures/test_story.py`

**Interfaces:**
- Consumes: `requestReview`, `takePendingReview`, `culturesStory.reviewSeq` (Task 5), and the targets produced in Tasks 1 and 6.
- Produces, in `storyLexicon.js`: `resolveReviewTarget(world, target) -> {type, id?, focus} | null`, where `world` is the `world` payload:
  - **`glossary`:** the entry is found by id.
    - `language === null` → `{type:'unassigned', focus:{glossaryId}}`
    - its culture exists → `{type:'culture', id: language, focus:{subTab:'glossary', glossaryId}}`
    - otherwise `null`
  - **`phrase`:** the culture and the phrase exist → `{type:'culture', id: culture_id, focus:{subTab:'phrases', phraseId}}`
  - **`place`:** the place exists → `{type:'places', focus:{placeId}}`
  - **`people`:** a character with that name is in `world.characters` → `{type:'people', focus:{characterName}}`
  - anything else, or not found → `null`
- **`WorldStateManagerCultures`:**
  - It gets data `cultureFocus: null` and `peopleFocusName: null`.
  - It watches `culturesStory.reviewSeq` and calls `send('get_world')`.
  - On every `world` message, after `ensureSelection()`, it calls `applyPendingReview()`:
    1. `const t = takePendingReview(); if (!t) return; const r = resolveReviewTarget(this.world, t); if (!r) return;`
    2. `select(r.type, r.id)`, then set the state for that type:
       - **unassigned:** `unassignedSelectedId = focus.glossaryId`
       - **places:** `placesSelectedId = focus.placeId`
       - **people:** `peopleFocusName = focus.characterName`
       - **culture:** `cultureFocus = {...focus, seq: Date.now()}`, passed to `CulturePage` as `:focus`
- **`CulturePage`:** prop `focus: Object | null`. A watcher (`immediate`) sets `subTab = focus.subTab` when `hasTab` allows it, `glossarySelectedId = focus.glossaryId`, and passes `focus.phraseId` to `PhraseList` as `:focus-id`.
- **`GlossaryView`:** watch the `selectedId` prop. When it differs from `localSelectedId`, and the entry isn't in `visibleEntries`, set `activeFilter = 'all'` and `search = ''` first, then `localSelectedId = id`.
- **`PhraseList`:** prop `focusId`. The matching `.phrase-row` gets the class `phrase-focus` (a highlight7 left border) and `scrollIntoView({block:'center'})` on `nextTick`.
- **`PeopleView`:** prop `focusName`. The matching `.people-row` gets the class `people-row-focus` and scrolls into view.

- [ ] **Step 1: Add the failing checks:**
  - `resolve_targets`: each of the four types resolves as above, against a small world.
  - `resolve_missing_target`:
    - a deleted entry id, a missing phrase, an unknown place, an unknown character and `{type:'bogus'}` all give `null`
    - a glossary entry whose culture is gone gives `null`
- [ ] **Step 2: Add the failing browser tests:**
  - `test_review_button_opens_glossary_entry`: Kethrun's bubble → **Review**. The World Editor is visible, the Cultures tab and the Glossary sub-tab are selected, and `.glossary-row-selected` has the text `Kethrun`.
  - `test_review_unassigned_name`: Quillister House's bubble → **Review**. The "Unassigned names" card is visible, and the selected row is Quillister House.
  - `test_open_in_culture_phrase_and_word`:
    - The curse's **Open in Taelrik** selects the Phrases sub-tab, and `.phrase-focus` contains `Rhok tal'dun!`.
    - Back on the scene tab, saervik's **Open in Taelrik** selects the Glossary sub-tab with saervik selected, even though it's reviewed (the filter shows All).
  - `test_change_culture_opens_people`: Kethrun's **Change** opens the People view, and `.people-row-focus` contains `Kethrun`.
  - `test_review_jump_to_missing_entry_is_harmless`:
    - Open Kethrun's bubble.
    - Remove `g-kethrun` on disk only, with `place_glossary(world, <the seed list without g-kethrun>)`. This sends no push, so the bubble and its button stay. Then click **Review**.
    - The Cultures tab shows a culture page, and no console error is logged.
    - Then open the scene tab again and use saervik's **Open in Taelrik**. It still navigates, so no stale pending target is left.
- [ ] **Step 3: Run** the JS-check command and the `test_story.py` browser command. Expected: the new checks and tests FAIL.
- [ ] **Step 4: Implement.**
- [ ] **Step 5: Run** the frontend build, the JS-check command, then `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e -m e2e -n0 -v`. Expected: all pass. This includes plan 1–2's glossary, places and people tests.
- [ ] **Step 6: Commit**: `git commit -m "feat(cultures): review buttons in the story land on the item"`

---

### Task 8: Culture chips in the World panel

**Files:**
- Create: `talemate_frontend/src/components/cultures/CultureChip.vue`, `talemate_frontend/src/components/cultures/WorldPanelPlaces.vue`
- Modify (core edit 6): `talemate_frontend/src/components/WorldState.vue`
- Modify: `storyLexicon.js` (add `characterChip`, `placeChip`), `checks/culturesStory.check.mjs`, `tests/e2e/cultures/test_story.py`

**Interfaces:**
- Consumes: `culturesStory`, `nameKey`, `buildNameIndex`, and the injected `openCulturesReview`.
- Produces, in `storyLexicon.js`. `Chip` is `{label, color, unreviewed: boolean, target: object|null}`.
  - **`characterChip(story, name) -> Chip | null`.** Let `info` be the name's `NameInfo` and `ch` its `CharacterInfo`.
    - The label comes from the first of these that applies:
      1. `ch.culture_id` → `ch.culture_name`, in its colour
      2. `ch.set_by === 'owner'` with no culture → `No culture`, `grey`
      3. `info.culture_name` → that, in its colour
      4. `info` with no language → `No language`, `grey`
      5. otherwise `null`
    - `unreviewed` is `info?.status === 'unreviewed'` or (`ch.set_by === 'ai' && ch.unsure`).
    - `target`: `{type:'glossary', entry_id}` when the glossary entry is unreviewed, otherwise `{type:'people', character_name}` when unsure, otherwise `null`.
  - **`placeChip(story, name) -> Chip | null`.** It matches `PlaceInfo` as `nameSection` does.
    - With a mix: one culture gives its name; several give `{top} +{n-1}`, in the top culture's colour.
    - With no place, or an empty mix: the same fallbacks as rules 3–5 of `characterChip`.
    - `unreviewed` is `place.unsure` or the glossary entry being unreviewed.
    - `target`: the glossary entry first, otherwise `{type:'place', place_id}`.
- **`CultureChip`** (props `kind: 'character'|'place'`, `name`). It renders nothing for `null`. Otherwise:
  - an outlined `x-small` label chip, `class="culture-chip"`, `:data-chip-for="kind + ':' + name"`, in the chip colour
  - when `unreviewed`: a 7px `rgb(var(--v-theme-unsaved))` dot, `class="culture-review-dot"`, `role="button"`, `title="Not reviewed yet"`, with `@click.stop="openCulturesReview(target)"`
- **`WorldPanelPlaces`** (prop `places`: the `world_state.places` dict). It renders one `v-expansion-panels` per place in the items' markup. Each has:
  - the title `{{ name }}` with `<CultureChip kind="place" :name="name" />`
  - an `mdi-map-marker` action icon
  - the snapshot as the panel text
- **WorldState (core edit 6):**
  - `<CultureChip kind="character" :name="name" class="ml-1" />` after the emotion span in each character title
  - `places: {}` in `data()`, with `this.places = data.data.places || {}` in the `world_state` branch
  - `<WorldPanelPlaces :places="places" />` between the characters' and the objects' containers

- [ ] **Step 1: Add the failing checks:**
  - `character_chip`:
    - Kethrun → `{label:'Taelrik', unreviewed:true, target:{type:'glossary', entry_id:'g-kethrun'}}`
    - an owner with no culture → `No culture`, not unreviewed
    - an unsure AI culture with a reviewed name → target `{type:'people', …}`
    - an unknown name → `null`
  - `place_chip`:
    - Veldhaer → `Taelrik`, not unreviewed
    - Dhunmouth (3 cultures) → `Taelrik +2`
    - Quillister House, with a place record but no mix of its own and an inherited mix from Veldhaer → `Taelrik`
    - an unknown world-state place backed only by an unassigned unreviewed glossary entry → `No language`, unreviewed, target glossary
- [ ] **Step 2: Add the failing browser tests:**
  - `test_world_panel_character_chip_and_dot`:
    - The left drawer's `[data-chip-for="character:Kethrun"]` reads `Taelrik`, with a `.culture-review-dot` next to it.
    - Clicking the dot opens Cultures → Glossary with Kethrun selected.
    - The character's expansion panel did not toggle.
  - `test_world_panel_place_chips`:
    - The drawer lists Veldhaer, Khaz-Rull and Quillister House.
    - `place:Veldhaer` reads `Taelrik` and `place:Khaz-Rull` reads `Ghûn`.
    - `place:Quillister House` reads `Taelrik`: its record inherits Veldhaer's mix, and the chip carries the dot for its unreviewed glossary entry.
    - Clicking that dot lands on Unassigned names with Quillister House selected.
- [ ] **Step 3: Run** the JS-check command and the `test_story.py` browser command. Expected: FAIL.
- [ ] **Step 4: Implement.**
- [ ] **Step 5: Run** the frontend build, the JS-check command and the whole browser group. Expected: all pass.
- [ ] **Step 6: Commit**: `git commit -m "feat(cultures): culture chips and review dots in the World panel"`

---

### Task 9: AI test: a narrated curse is highlighted (opt-in; the controller runs it)

**Files:**
- Create: `tests/ai/cultures/test_story_ai.py`

**Interfaces:**
- Consumes:
  - `ai_app` and `browser_page` (`tests/ai/conftest.py`)
  - `seed_scenario`, `SCENARIOS` (`tests/ai/cultures/scenarios.py`)
  - `dismiss_onboarding`, `open_scene`, `send_backend` (`tests/e2e/seed.py`)
  - `CONNECTED_DOT` (`tests/ai/test_koboldcpp_smoke.py`)
  - the AI fixture `tests/ai/data/taelrik.culture.json`

- [ ] **Step 1: Write** `test_narrated_curse_is_highlighted_with_translation(ai_app, browser_page)`:
  1. **Seed and open.** `seed_scenario(ai_app.root, "ai-story-curse", SCENARIOS["taelrik_town"], with_trait_character=True)`. Then `goto(ai_app.frontend_url)`, `dismiss_onboarding` and `open_scene`, and wait for `get_by_test_id("ai-client").locator(CONNECTED_DOT)`, with a 60 s timeout.
  2. **Curses by id.** Load the fixture's phrases into `curses = {f"phrase:taelrik:{p['id']}": p["translation"] for p in phrases if p["category"] == "curse"}`.
  3. **Narrate.** Make up to 3 attempts. Each one:
     - records the count of `.message-container .scene-foreign[data-foreign-kind="curse"]`
     - sends `send_backend(page, {"type":"narrator","action":"progress","narrative_direction":"Hadrik drops a heavy crate on his foot and curses loudly in Taelrik."})`
     - waits up to 600 s until a new, non-empty story message has rendered. The narrator's is `.narrator-text`; take the character-message selector from `CharacterMessage.vue`, and count both.
     - stops at the first attempt where the curse-span count grew
     - records each attempt's newest message text
  4. **Assert.**
     - A new curse span exists. The failure message includes the recorded narrations; it's a model finding if the model never used a curse.
     - Clicking it shows `foreign-word-card`, and its `foreign-translation` equals `curses[span.get_attribute("data-foreign-id")]`.
- [ ] **Step 2: Verify it skips without opt-in.** Run `guix shell -m manifest.scm -- uv run --no-sync pytest tests/ai -m ai -n0 -v`. Expected: every test is SKIPPED with "AI tests need TALEMATE_AI_TESTS=1". Also `guix shell -m manifest.scm -- uv run --no-sync pytest --collect-only -q tests/ai` must collect without errors. Don't set `TALEMATE_AI_TESTS`.
- [ ] **Step 3: Commit**: `git commit -m "test(cultures): opt-in AI test for highlighted curses"`
- [ ] **Step 4: (Controller only. koboldcpp is pre-approved for tonight.)**
  1. Fetch the model name with `guix shell -m manifest.scm -- uv run --no-sync python -c "import sys; sys.path.insert(0,'scripts/dev'); import ai_helpers; print(ai_helpers.koboldcpp_model(ai_helpers.koboldcpp_url()))"`.
  2. Run `TALEMATE_AI_TESTS=1 guix shell -m manifest.scm -- uv run --no-sync pytest tests/ai/cultures/test_story_ai.py -m ai -n0 -v`.
  3. Expected: PASS. If it fails only because the model never used a stored curse, record the narrations and the model name from `.test-artifacts/<stamp>/model.txt` as an evaluation finding. A curse that appears in the text but isn't highlighted is a bug: fix it and re-run.

---

### Task 10: Whole-branch check

- [ ] **Step 1:** Run `guix shell -m manifest.scm -- uv run --no-sync pytest`. Expected: no new failures beyond the 141 known `punkt_tab` ones. `tests/dev/test_frontend_checks.py` passes.
- [ ] **Step 2:** Run `guix shell -m manifest.scm -- uv run --no-sync ruff check` and `… ruff format --check`, both on `src/talemate/cultures src/talemate/agents/culture src/talemate/server/cultures.py tests/cultures tests/server tests/dev tests/e2e tests/ai`. Expected: clean.
- [ ] **Step 3:** Run the frontend build, the JS-check command and the browser group. Expected: all succeed.
- [ ] **Step 4: Check the core-edit list.**
  - `git diff feature/cultures-ai --stat -- src/talemate ':!src/talemate/cultures' ':!src/talemate/agents/culture' ':!src/talemate/server/cultures.py'` must print nothing.
  - `git diff feature/cultures-ai --stat -- talemate_frontend ':!talemate_frontend/src/components/cultures' ':!talemate_frontend/checks'` must list exactly the six files in Global Constraints.
- [ ] **Step 5: Update** `docs/superpowers/plans/2026-10-17-cultures-foundation-followups.md`:
  - mark "The Cultures badge shows 0 until the tab has been opened once" as fixed (Task 5)
  - add any gap found while building this plan
- [ ] **Step 6: Commit**: `git commit -m "chore(cultures): plan 3 branch check"`
