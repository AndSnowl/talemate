# Languages 3b-1: making a language from inside the app — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The owner types "a unique but recognizably Russian language", answers a few plain questions (or says "decide for me"), and gets a checked language back in the import review. It's made by Claude Code on this machine, by a strong model in the app, or by any assistant given the copied brief.

**Architecture:**
- A new global `language` agent holds the client and the route settings.
- `talemate.languages` gains:
  - `brief` (the one text every outside route gets);
  - `making` (questions, the in-app route, and the job that runs a route plus the repair loop);
  - `claude_code` (the headless runner, from the spike).
- The worlds router runs a make job in the background, streams progress lines, and hands the finished file text to the existing `LanguageImport` review. Importing stays the only way a language lands.

**Tech Stack:** Python 3.11, pydantic, asyncio subprocesses, Jinja prompt templates (`Prompt.request`), Vue 3 + Vuetify, pytest, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-10-28-fantasymate-languages-part-3-design.md`, section "3b". Spike: `docs/superpowers/probes/2026-10-28-claude-code-route-spike.md`, which has the invocation, the pitfalls and the decisions this plan takes. Plan 3a is merged (0b96e4a7).

**Scope ruling (builder's call, spec "Left to the builder"):**
- 3b splits in two. This plan, **3b-1**, makes a *new* language (spec pictures 1, 3 and 4).
- **3b-2** comes later and covers the rest of the spec's 3b:
  - *Revise…* with suggested related entries (picture 2);
  - daughters and "more words";
  - naming styles made in the app, with "More parts";
  - *Test this model*.
- Every piece below is written so 3b-2 extends it: `MakeRequest.kind`, the brief's `current` file, the route per job.

## Global Constraints

- **No linguistics jargon** in questions, guidance, progress lines or errors (spec, Anti-goals).
- **Nothing lands silently.** Every route ends in the existing import review (`LanguageImport.vue` → `language_preview` → `language_import`), where the owner sees the samples and the check before accepting (spec, Anti-goals).
- **The route and model are global**, on the `language` agent. Nothing world-specific is stored there (spec, 3b).
- **Default route per job** (spec, table): a full language is made **outside**. The default is `claude_code`; `brief` is "copy the brief" only; `in_app` uses the agent's client.
- **Copy the brief** is always one click away, whatever the route (spec).
- **The Claude Code invocation** is exactly the spike's:
  - `-p <prompt> --setting-sources project --tools "Read,Write,Edit,Bash,Skill" --allowedTools "Skill,Bash(./check:*)" --disallowedTools "Bash(git:*)" --permission-mode acceptEdits --output-format stream-json --verbose --no-session-persistence --strict-mcp-config`, plus `--model M` when set;
  - the working directory is the scratch folder, and stdin is `DEVNULL`;
  - never `bypassPermissions`, never `--bare`.
- **The scratch folder** comes from `tempfile.mkdtemp(prefix="fm-language-")`, never under `~/.claude` or inside a repository. It's removed when the job ends, whether it succeeded, failed or was cancelled.
- **The repair loop runs at most twice.** It runs only when `needs_repair(report)` from `talemate.languages.check` says so: a blocking problem, or warnings on more than a third of the words (spec).
- **Owner's UI rules:**
  - controls sit right after what they act on;
  - right-align only in half-width areas;
  - the same look is one component;
  - UI is built inline, with screenshots after every visible change, including at 1920×1080.
- **The model is never asked to coin words** outside a whole-language job (spec, Anti-goals; probe).
- **Dev environment:** `docs/dev/local-testing.md`.
  - Tests: `guix shell -m manifest.scm -- uv run --no-sync pytest …`.
  - e2e: `-m e2e -n 4`.
  - Frontend build: `npx --yes corepack@0.34.0 pnpm build` in `talemate_frontend`.
- **No koboldcpp, and no real Claude Code, in automated tests.** Both are replaced by fixed replies and a fake `claude` script. The final acceptance runs real Claude Code only with the owner's go-ahead.

## Review Focus

1. **Claude Code isn't installed, or isn't signed in.** The dialog shows one plain sentence ("Claude Code isn't installed here: copy the brief instead, or pick another route in the language agent's settings") and Copy the brief still works. Task 4 tests a missing command and a non-zero exit with an error result.
2. **Cancel mid-run.** The process tree is killed, the folder is removed, no `language_make_done` arrives afterwards, and the dialog is idle again. Tasks 4 and 6 test this.
3. **The run ends without the expected file:** no `*.language.json`, a different name, or two files. The runner falls back to the reply text through `parse_language_text`. With neither, it fails with "Claude Code finished without a language file". Task 4 tests this.
4. **A second Make while one is running.** It's refused with "A language is already being made", and the first job carries on. Task 6 tests this.
5. **The world is closed, or another one opened, mid-run.** The finished text is still delivered, and the review checks it against whatever world is open then, as the import does today. With no world open, the dialog says so. Task 6 tests this.

---

### Task 1: The language agent

**Files:**
- Create: `src/talemate/agents/language/__init__.py`
- Modify: `src/talemate/agents/__init__.py` (import it so `@register()` runs)
- Modify: `src/talemate/server/worlds.py`. Add `_language_client()` beside `_client()` (line ~2185), and use it in every `handle_language_*` handler that asks a model (`language_names`, `language_suggest_definition`, `language_name_in`, and their helpers).
- Test: `tests/agents/test_language_agent.py`, `tests/server/test_worlds_languages.py`

**Interfaces:**
- Produces:
  - `LanguageAgent(Agent)`: `agent_type = "language"`, `verbose_name = "Language"`, `essential = False`, `requires_llm_client = True`, with a no-argument `__init__(client=None, **kwargs)`, as `bootstrap_engine` needs.
  - `LanguageAgent.make_settings() -> MakeSettings`.
  - `MakeSettings(BaseModel)`, in `talemate.languages.making`, created in this task (Task 5 adds the rest of the module). The agent imports it:
    - `route: Literal["claude_code", "in_app", "brief"] = "claude_code"`;
    - `claude_command: str = "claude"`;
    - `claude_model: str = ""`.
  - `WorldsPlugin._language_client() -> Any`: the language agent's client, else the creator's.
- Actions (`init_actions`), one action `"making"` with `label="Making languages"`. Its `description` is the guidance, in plain words:

  > "A whole language (its dictionary, phrases and naming rules) needs a strong model: Claude Code, or a large model on an API. Small local models do well at picking names and writing short meanings, which always run here."

  Its config:
  - `route`: type `text`, with choices:
    - `{"label": "Claude Code on this computer", "value": "claude_code"}`;
    - `{"label": "This agent's model", "value": "in_app"}`;
    - `{"label": "Copy the brief (I'll use my own assistant)", "value": "brief"}`;
    - default `"claude_code"`.
  - `claude_command`: type `text`, default `"claude"`, label "Claude Code command".
  - `claude_model`: type `text`, default `""`, label "Claude Code model (empty: its default)".

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/test_language_agent.py
from talemate.agents.registry import AGENT_CLASSES
from talemate.languages.making import MakeSettings

def test_the_language_agent_is_registered():
    assert "language" in AGENT_CLASSES

def test_its_making_settings_default_to_claude_code():
    agent = AGENT_CLASSES["language"]()
    assert agent.make_settings() == MakeSettings(route="claude_code", claude_command="claude", claude_model="")

def test_changed_settings_come_back():
    agent = AGENT_CLASSES["language"]()
    agent.actions["making"].config["route"].value = "in_app"
    agent.actions["making"].config["claude_model"].value = "sonnet"
    s = agent.make_settings()
    assert (s.route, s.claude_model) == ("in_app", "sonnet")
```

In `tests/server/test_worlds_languages.py`, add `test_definitions_ask_the_language_agents_client`. Set the language agent's client to a `MockClient("lang")` and the creator's to a different `MockClient("creator")`. Queue one definitions reply, call `handle_language_suggest_definition`, and assert the `lang` client's queue was consumed.

`MakeSettings` doesn't exist yet. For this task, create `src/talemate/languages/making.py` holding only `MakeSettings`; Task 5 adds the rest.

- [ ] **Step 2: Run them.** `guix shell -m manifest.scm -- uv run --no-sync pytest tests/agents/test_language_agent.py tests/server/test_worlds_languages.py -q -p no:cacheprovider`. Expected: FAIL (no `"language"` in `AGENT_CLASSES`).
- [ ] **Step 3: Implement.** Copy the shape of `src/talemate/agents/help/__init__.py`: `enabled`/`has_toggle`, actions from `init_actions()`. `_language_client` catches `KeyError` and a `None` client, and falls back to `instance.get_agent("creator").client`.
- [ ] **Step 4: Run them.** Expected: PASS. Then run the whole plain suite (`--ignore=tests/e2e --ignore=tests/ai`). Expected: 0 failures, since `bootstrap_engine` now builds the new agent too.
- [ ] **Step 5: Screenshot.**
  - Open the agent list in the app (isolated app, as in 3a) and open Language.
  - The route select, the two Claude Code fields and the guidance text should show without frontend code (`AgentModal.vue` is generic).
  - Shoot at 1920×1080. If something renders badly, fix it in `AgentModal`/`UxField` only if the fix is generic. Otherwise rule and ledger it.
- [ ] **Step 6: Commit.** `feat(languages): a global language agent with its own client and route`

### Task 2: The brief

**Files:**
- Create: `src/talemate/languages/brief.py`, `src/talemate/languages/data/example.language.json` (a copy of `tests/languages/data/sample.language.json`)
- Modify: `src/talemate/languages/making.py` (add `MakeRequest`), `.claude/skills/language-design/SKILL.md` (the check section)
- Test: `tests/languages/test_brief.py`

**Interfaces:**
- Produces:
  - `MakeRequest(BaseModel)`:
    - `kind: Literal["new"] = "new"` (3b-2 widens this);
    - `text: str` (the owner's words);
    - `answers: list[QuestionAnswer] = []`;
    - `decide_for_me: bool = False`;
    - `context_ids: list[str] = []`.
  - `QuestionAnswer(BaseModel)`: `question: str`, `answer: str`.
  - `write_brief(view: WorldView | None, request: MakeRequest, *, check_command: str | None = None) -> str`.
  - `BRIEF_FILE_NAME = "brief.md"`.
- The brief is Markdown, with these sections in order. The headings are exact, and tests look for them:
  1. `# Make a language for a fantasy world` and one plain line on what the file is for.
  2. `## What the owner asked for`: the request text, quoted. Then each answered question as `- Q: … / A: …`. If `decide_for_me`, the line "The owner said: decide for me."
  3. `## The world`, only when `context_ids` resolve to live entries. One `### <name> (<kind>)` per entry, then its facts as `- <category>: <rendered text>` (`view.render`).
  4. `## The file`:
     - "Write one JSON file named `<slug>.language.json`, valid against this schema", then the schema from `language.schema.json` in a ```json block;
     - "An example", then the example file in a ```json block;
     - the rules, as bullets: meanings are 1–3 words and never a sentence; a word made only to be a name may have no meaning; no real words from the language it sounds like (`flavour`); a full language needs a `words` generator.
  5. `## Check it`:
     - with `check_command`: "Run `<check_command> <file>` on its own line (no other commands with it), and fix the file until it reports no problems that must be fixed";
     - without: "If you can run code, check that the JSON parses. Return the whole file in one ```json code block, or as a file the owner can download."

- [ ] **Step 1: Write the failing tests.** In `tests/languages/test_brief.py`:
  - `test_a_brief_carries_the_request_and_answers`: the text appears; `"Q: How Russian should it sound?"` and its answer appear.
  - `test_decide_for_me_is_said_plainly`.
  - `test_the_world_section_lists_chosen_entries_facts`: use the `world` fixture to create a place "Tsardom of Moscavia" with a fact "description: Cold northern realm." Assert `"### Tsardom of Moscavia (place)"` and `"- description: Cold northern realm."`. Assert no `## The world` when `context_ids` is empty, or names only a deleted id.
  - `test_the_file_section_has_the_schema_and_example`: `json.loads` of the first ```json block equals the schema file's content.
  - `test_the_check_section_follows_the_route`: with `check_command="./check"`, the brief contains "`./check moscavian.language.json`"-style wording and "on its own line"; without it, "one ```json code block".
  - `test_the_brief_has_no_jargon`: none of the probe's jargon labels (`docs/superpowers/probes/raw/2026-10-28-language-make-labels.json`, key `jargon`) appear in a brief made from a plain request.
- [ ] **Step 2: Run.** `… pytest tests/languages/test_brief.py -q`. Expected: FAIL (`talemate.languages.brief` doesn't exist).
- [ ] **Step 3: Implement** `write_brief`. Build plain string sections; there's no Jinja here, since the brief isn't a model prompt for the app's client. The slug is the lower-cased first word of the request's quoted name, if one is quoted, else `language`. Package data goes in `pyproject.toml` if that's needed for `data/*.json`; check how `data/real_words/*.txt` is shipped and match it.
- [ ] **Step 4: Update the skill.** In `.claude/skills/language-design/SKILL.md`, the check section becomes: "If the folder has a `check` command (the app's), run `./check FILE` on its own line. Otherwise use the guix/uv command below." Keep the existing commands as the fallback.
- [ ] **Step 5: Run.** Expected: PASS.
- [ ] **Step 6: Commit.** `feat(languages): the brief every outside route gets` (`git add -f` for the skill, since `.claude` is ignored).

### Task 3: Questions in the app

**Files:**
- Create: `src/talemate/prompts/templates/world/language-questions.jinja2`
- Modify: `src/talemate/languages/making.py`, `src/talemate/server/worlds.py`
- Test: `tests/languages/test_making_questions.py`, `tests/server/test_worlds_languages.py`

**Interfaces:**
- Produces:
  - `async ask_questions(client, request_text: str, *, reply: str | None = None) -> list[str]`: at most 4 questions, blank lines and numbering stripped; an empty list when the client is `None` and there's no `reply`.
  - Handler `handle_language_questions(data: {"text": str})`, which replies `language_questions {"questions": [str]}`. The fixed reply comes from `FIXED_LANGUAGE_ENV`'s file, key `"questions"` (a string), when the e2e file has it.
- The template's system text is the probe's `ASK_SYSTEM` (`scripts/dev/probe_language_make.py:91`), unchanged in meaning: "…at most four short questions about what they want it to sound and feel like, in plain everyday words (never linguistics terms). Reply with the numbered questions only." The user turn is the request text. The template follows `world/language-define.jinja2`'s structure.

- [ ] **Step 1: Write the failing tests.**
  - `test_questions_are_parsed_from_a_numbered_reply`: the reply `"1. How Russian should it sound?\n2. Grand or earthy?\n\n3) Old or modern?"` gives the three questions without numbers.
  - `test_at_most_four_questions`: a 6-item reply gives 4.
  - `test_no_client_means_no_questions`: `ask_questions(None, "x") == []`.
  - Server: `test_language_questions_replies_with_questions` (fixed reply through a `MockClient` and `client_responses`).
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement**, using `_language_client()` and the `world_ai_call()` and `Prompt.request` pattern from `naming._define_reply`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit.** `feat(languages): plain questions before a language is made`

### Task 4: The Claude Code runner

**Files:**
- Create: `src/talemate/languages/claude_code.py`, `tests/languages/data/fake-claude` (executable Python script, `#!/usr/bin/env python3`)
- Test: `tests/languages/test_claude_code.py`

**Interfaces:**
- Consumes: `MakeSettings`, `BRIEF_FILE_NAME`, `parse_language_text` (from `talemate.languages.importer`).
- Produces:
  - `prepare_folder(brief: str) -> Path`: makes the `mkdtemp` folder and copies the skill to `.claude/skills/language-design/`. The skill's source is `<repo root>/.claude/skills/language-design`, found from `talemate.path.TALEMATE_ROOT`. It writes the check wrapper (`check`, chmod 755, `exec "<sys.executable>" -m talemate.languages check "$@"`; on Windows `check.cmd`) and `brief.md`.
  - `claude_args(settings: MakeSettings, prompt: str) -> list[str]`: exactly the Global Constraints invocation. `--model` goes in only when `settings.claude_model` is set.
  - `progress_line(event: dict) -> str | None`: plain lines from stream-json events:
    - `Skill` → "Reading the language guide";
    - `Write`/`Edit` → "Writing <file name>";
    - `Read` → "Reading <file name>";
    - `Bash` whose command starts with `./check` → "Running the check";
    - a `tool_result` with `is_error` → None;
    - everything else → None.
  - `ClaudeCodeResult(BaseModel)`: `text: str` (the language file's text), `reply: str`, `cost_usd: float | None`.
  - `class ClaudeCodeError(Exception)`: its message is shown to the owner as is.
  - `async run_claude_code(folder: Path, settings: MakeSettings, prompt: str, on_progress: Callable[[str], None]) -> ClaudeCodeResult`:
    - runs `asyncio.create_subprocess_exec(settings.claude_command, *claude_args(...), cwd=folder, stdin=DEVNULL, stdout=PIPE, stderr=PIPE)`;
    - reads stdout line by line, parsing JSON and calling `on_progress(line)` for each non-None `progress_line`;
    - drains stderr concurrently (the deadlock note in `client/pi_bridge.py:~596`);
    - on `CancelledError`, kills the process tree (reuse or mirror `pi_bridge.kill_pi_process_tree`) and re-raises.
  - `find_language_text(folder: Path, reply: str) -> str`:
    - the one `*.language.json` in the folder;
    - with several, the newest by mtime;
    - with none, the reply text if `parse_language_text(reply)` succeeds;
    - else raises `ClaudeCodeError("Claude Code finished without a language file")`.
  - Errors, in exact words:
    - the command isn't found (`FileNotFoundError`) → `ClaudeCodeError("Claude Code isn't installed here: copy the brief instead, or pick another route in the language agent's settings")`;
    - a `result` event with `is_error`, or a non-zero exit with no result → `ClaudeCodeError("Claude Code stopped: <result text or the last stderr line>")`.
- The fake script `tests/languages/data/fake-claude`:
  - reads `FAKE_CLAUDE_MODE` from its environment (`ok`, `reply-only`, `error`, `slow`);
  - prints stream-json lines matching the spike's shapes: `system/init`, an assistant `tool_use` Skill, a `Write` of `moscavian.language.json`, a `Bash` `./check moscavian.language.json`, and a `result`;
  - in `ok` it writes the sample language into its cwd;
  - in `reply-only` it puts the file in the `result` text, in a ```json block;
  - `slow` sleeps 30 s between lines (for the cancel test);
  - `error` prints a `result` with `is_error: true` and exits 1;
  - it ignores its arguments, but writes them to `args.json` in its cwd, so a test can check the flags.

- [ ] **Step 1: Write the failing tests.**
  - `test_claude_args_are_the_spikes`: assert the list equals the exact flags. `--model sonnet` is present only when set. `bypassPermissions` and `--bare` never appear.
  - `test_the_folder_holds_skill_check_and_brief`: `(folder/".claude/skills/language-design/SKILL.md").exists()`; `check` is executable; `brief.md` holds the brief; the folder isn't under `Path.home()/".claude"`.
  - `test_the_check_wrapper_runs_the_check`: run `./check <sample>` with `subprocess.run` in the folder; exit 0 and "Sample names" in the output.
  - `test_progress_lines_are_plain`: the events above map to "Reading the language guide", "Writing moscavian.language.json", "Running the check".
  - `test_a_run_returns_the_file` (`FAKE_CLAUDE_MODE=ok`, `claude_command` = the fake's path): the `ClaudeCodeResult.text` parses with `parse_language_text`; the progress list holds the three lines; `args.json` has `--permission-mode acceptEdits`.
  - `test_a_reply_only_run_falls_back_to_the_reply`.
  - `test_no_file_and_no_language_in_the_reply_fails_plainly`.
  - `test_a_missing_command_says_claude_code_isnt_installed`.
  - `test_an_error_result_is_reported`.
  - `test_cancelling_kills_the_process`: `slow`; start the run as a task; wait for the first progress line; cancel; assert `CancelledError`, and that the fake's PID (it writes `pid` to its cwd) no longer runs (`os.kill(pid, 0)` raises).
- [ ] **Step 2: Run.** `… pytest tests/languages/test_claude_code.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement.** Write the fake first, then the module.
- [ ] **Step 4: Run.** Expected: PASS. Then run the plain suite.
- [ ] **Step 5: Commit.** `feat(languages): run Claude Code headless to make a language`

### Task 5: The in-app route and the make job

**Files:**
- Create: `src/talemate/prompts/templates/world/language-make.jinja2`
- Modify: `src/talemate/languages/making.py`
- Test: `tests/languages/test_making.py`

**Interfaces:**
- Consumes: `write_brief`, `prepare_folder`, `run_claude_code`, `find_language_text`, `ClaudeCodeError`, `check_language`, `needs_repair`, `repair_note`, `parse_language_text`.
- Produces:
  - `async make_in_app(client, brief: str, *, repair: str | None = None, previous: str | None = None, reply: str | None = None) -> str`: the model's reply text. The template sends the brief (written with `check_command=None`). On repair, it adds the previous file and the repair note, with "Fix these problems and return the whole file again".
  - `MakeError(Exception)`: its message is shown as is.
  - `async make_language(view, request: MakeRequest, settings: MakeSettings, client, on_progress: Callable[[str], None], *, fixed: dict | None = None) -> str`:
    - returns the finished language file text;
    - raises `MakeError` for `route == "brief"` ("This route only copies the brief"), and wraps `ClaudeCodeError` as `MakeError` with the same message.
  - The repair loop, the same for both routes:
    1. run once;
    2. parse and `check_language`;
    3. while `needs_repair(report)` and repairs < 2, run again with `repair_note(report)`;
    4. return the last text, even if it still has warnings. The owner sees them in the review.
  - On a repair, the Claude Code route reuses the same folder, with the prompt "The app's check found these problems in `<file>`. Fix them, run the check again, and reply DONE.\n\n<note>".
  - The first Claude Code prompt is "Read brief.md and do what it says. Use the language-design skill. When the check passes, reply DONE <file name>.", with the brief written with `check_command="./check"`.
  - The folder is removed in a `finally`.
  - Progress lines: "Asking the model" / "Checking the result" / "Fixing what the check found (1 of 2)".
  - `fixed`: the e2e stand-in. `fixed["language_file"]` (str) is used as the in-app reply.

- [ ] **Step 1: Write the failing tests** (`MockClient` with `client_responses`, as in `tests/languages/test_meanings.py`):
  - `test_in_app_returns_a_checked_file`: one reply holding the sample file in chat text; the result parses.
  - `test_a_blocking_problem_is_sent_back_once_then_fixed`: the first reply has a broken pattern (`reject: ["("]`), the second is good. Two calls are consumed, and the second prompt contains the repair note's first line. Assert the prompt by capturing it the way the existing MockClient tests do; if MockClient can't capture prompts, assert the call count and the result.
  - `test_repairs_stop_after_two`: three broken replies, so three calls; the last text comes back and the report still has its problem.
  - `test_the_claude_code_route_runs_the_fake` (the fake's `ok` mode, through `make_language`): the text parses, and the folder no longer exists afterwards (capture it from `prepare_folder` with a monkeypatched wrapper).
  - `test_the_brief_route_is_not_runnable`: `MakeError("This route only copies the brief")`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit.** `feat(languages): make a language on a route, with the repair loop`

### Task 6: The make job in the worlds router

**Files:**
- Modify: `src/talemate/server/worlds.py`
- Test: `tests/server/test_worlds_language_make.py`

**Interfaces:**
- Consumes: `make_language`, `MakeRequest`, `MakeError`, `write_brief`, `LanguageAgent.make_settings`.
- Produces these handlers and replies:
  - `handle_language_brief(data: MakeRequest fields)` → `language_brief {"text": str}`. The brief for copying is written with `check_command=None`.
  - `handle_language_make_start(data: MakeRequest fields)`:
    - spawns the job (`self._spawn`) and keeps it as `self._make_task`;
    - replies `language_make_started {"route": str}`, then `language_make_progress {"line": str}` per line;
    - ends with `language_make_done {"text": str}` or `language_make_failed {"error": str}`;
    - while a job runs, it replies `language_make_failed {"error": "A language is already being made"}` and leaves the job alone.
  - `handle_language_make_cancel()`: cancels `_make_task` and replies `language_make_cancelled {}`. A cancelled job sends nothing else.
- Test hooks: the route can be overridden for e2e by the env var `TALEMATE_TEST_CLAUDE_COMMAND`, which sets `claude_command` (next to `FIXED_LANGUAGE_ENV`). The fixed language file's `"language_file"` key feeds `fixed`.
- No world open at start → `language_make_failed {"error": "Open a world first"}`. The world closed mid-run → the text is still sent (`language_make_done`), and the review handles it.

- [ ] **Step 1: Write the failing tests.** Use the plugin harness used by `tests/server/test_worlds_languages.py`, and await the spawned task.
  - `test_brief_reply_carries_the_request`.
  - `test_make_in_app_sends_progress_then_done`.
  - `test_make_with_claude_code_runs_the_fake` (`TALEMATE_TEST_CLAUDE_COMMAND` = the fake, `ok`): progress includes "Running the check"; done text parses.
  - `test_a_second_make_is_refused_while_one_runs` (the fake in `slow` mode).
  - `test_cancel_stops_the_job_without_a_done` (`slow`): after cancel, the replies hold `language_make_cancelled` and no `language_make_done`.
  - `test_a_failed_route_reports_its_message` (the fake in `error` mode).
  - `test_make_needs_an_open_world`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** `_make_task` is cleared in its done callback, and the callback sends the result. Read the settings from `instance.get_agent("language").make_settings()`, falling back to `MakeSettings()` on `KeyError`.
- [ ] **Step 4: Run.** Expected: PASS. Then run the plain suite.
- [ ] **Step 5: Commit.** `feat(languages): make a language from the worlds screen, with progress and cancel`

### Task 7: The make dialog

**Files:**
- Create: `talemate_frontend/src/components/worlds/LanguageMake.vue`
- Modify:
  - `talemate_frontend/src/components/worlds/WorldTab.vue`: on the Languages kind page, "Make a language" sits above "Import a language".
  - `talemate_frontend/src/components/worlds/LanguageImport.vue`: new prop `initialText: String`. When set, it fills the paste box and runs Check once.
  - `talemate_frontend/src/stores/worlds.js`: `languageQuestions`, `languageBrief`, `startLanguageMake`, `cancelLanguageMake`, and state `languageMake: {running, route, lines: [], text, error}`, fed by the replies from Tasks 3 and 6.
- Test: `tests/e2e/worlds/test_language_make.py`

**Interfaces:**
- Consumes: the Task 3 and Task 6 messages.
- The dialog, inline on the page (no modal), in this order:
  1. A text box, "What should it be like?" (`data-testid="make-request"`).
  2. "Take into account" (`data-testid="make-context"`): a chip list of entries with an autocomplete over the open world's entries. Reuse the worlds store's entry index, as `KindList` does. If none fits, rule and ledger it.
  3. Buttons right after the box: **Ask me questions** (`make-ask`) and **Make it** (`make-start`). **Copy the brief** (`make-copy-brief`) sits beside them at all times, and puts `language_brief`'s text on the clipboard.
  4. The questions, when asked: one text field each (`make-answer`). **Decide for me** (`make-decide`) sets `decide_for_me` and starts.
  5. While running: the progress lines as a short list (`make-progress`), a spinner, and **Cancel** (`make-cancel`).
  6. On failure: the error in plain words (`make-error`), with Copy the brief still there.
  7. On done: the dialog collapses to one line, "Made with <route label>: review it below", and `LanguageImport` opens with `initialText`.
- With route `brief`, **Make it** is replaced by **Copy the brief** as the main button, plus a line: "Paste what your assistant returns into Import a language below."

- [ ] **Step 1: Write the failing e2e tests.**
  - `test_make_a_language_with_claude_code_lands_in_the_review`: the app's env sets `TALEMATE_TEST_CLAUDE_COMMAND` to the fake, mode `ok`. Extend the `app` fixture's env the way `TALEMATE_TEST_FIXED_LANGUAGE` is set.
    1. Fill the request; click Make it.
    2. Expect `make-progress` to contain "Running the check".
    3. Expect `language-preview` to be visible with the sample's name; click Import.
    4. The language's page opens.
  - `test_questions_then_decide_for_me` (the fixed language file has `"questions": "1. Grand or earthy?\n2. Old or modern?"`): Ask me questions shows two `make-answer` fields; Decide for me starts the job.
  - `test_copy_the_brief_copies_text`: grant clipboard permissions on the page context, click Copy the brief, read `navigator.clipboard.readText()`, and expect "# Make a language for a fantasy world".
  - `test_cancel_returns_to_idle` (fake `slow`): Cancel; the progress disappears; Make it is enabled again.
  - `test_a_failed_run_shows_why` (fake `error`): `make-error` contains "Claude Code stopped".
  - The fake's mode per test: through a file the fake reads (`<app root>/e2e-fake-claude-mode`), written by a fixture, because the app's env is fixed at start. Add that file lookup to the fake. Its default is `ok`.
- [ ] **Step 2: Run.** `… pytest tests/e2e/worlds/test_language_make.py -m e2e -n 4 -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Build the frontend after every change; the isolated app copies the source at start, so restart it.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Screenshots.** At a small window and at 1920×1080, capture:
  - idle;
  - with questions;
  - running;
  - failed;
  - done, with the review below.

  Show the owner. Iterate on their feedback; it's a new screen with no mockup, which the spec allows ("designed in the build").
- [ ] **Step 6: Run the full plain and e2e suites.** Expected: 0 failures.
- [ ] **Step 7: Commit.** `feat(worlds-ui): make a language: questions, routes, progress and the brief`

### Task 8: Acceptance

**Files:**
- Create: `docs/superpowers/probes/2026-10-28-languages-3b1-acceptance.md`

- [ ] **Step 1: Write the checklist.** For each step, write the owner's look-and-feel check beside the e2e test that proves it, as in 3a's checklist. Steps:
  - the agent settings and guidance;
  - Make with Claude Code;
  - questions and decide-for-me;
  - Copy the brief, pasted into a chat assistant, and its reply imported;
  - the in-app route on a strong model, if the owner has one;
  - cancel;
  - the Claude Code missing message.
- [ ] **Step 2: Ask the owner before any real Claude Code or koboldcpp run** (standing rule; it spends their subscription). Then walk the checklist with them, and record the results and their verdicts.
- [ ] **Step 3: Commit.** `docs(languages): 3b-1 acceptance`
