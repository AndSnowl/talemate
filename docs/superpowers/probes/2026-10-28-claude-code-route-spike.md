# Spike: running Claude Code headless to make a language (2026-10-28)

**Why.** The part 3 design (`docs/superpowers/specs/2026-10-28-fantasymate-languages-part-3-design.md`, Constraints) asks for a spike before plan 3b, to settle three things: how the app invokes Claude Code, how it captures the output, and how the language-design skill runs the check.

**Setup.**
- Claude Code 2.1.280, signed in with a subscription (OAuth).
- A fresh folder from `mktemp -d` (`/tmp/fm-language-XXXXXX`) containing:
  - the skill, copied to `.claude/skills/language-design/`;
  - an executable `check` wrapper that runs `python -m talemate.languages check "$@"` with the app's Python (no guix needed);
  - `brief.md`.
- The request: "a unique but recognizably Russian language for the Tsardom of Moscavia", with "decide for me", kept small (about 30 words, 4 phrases).

## The invocation that works

```
claude -p "<brief>" \
  --setting-sources project \
  --tools "Read,Write,Edit,Bash,Skill" \
  --allowedTools "Skill,Bash(./check:*)" \
  --disallowedTools "Bash(git:*)" \
  --permission-mode acceptEdits \
  --output-format stream-json --verbose \
  --no-session-persistence --strict-mcp-config \
  [--model <model>]
```

It runs with the folder as the working directory and stdin closed.

## What was allowed and refused

Each line was tested with Haiku, in a folder outside `~/.claude`:

| Attempt | Result |
|---|---|
| Write, Edit or Read inside the folder | allowed |
| Write to `../escape.txt` | refused |
| Read `/etc/hostname`, `cat /etc/hostname` | refused |
| `curl`, `python3 -c …` | refused |
| `./check FILE` | allowed |
| `rm` inside the folder, `ls .` | allowed (read-only or inside the folder) |
| `git status` | allowed when the folder is inside a repository, hence `--disallowedTools "Bash(git:*)"` and a temporary folder outside any repository |
| `./check FILE; echo $?` | refused: a compound command needs approval for the extra part |

That matches the spec: "only run the app's check command, and read and write inside that scratch folder". Nothing skips permissions.

## Pitfalls found

- **`dontAsk` mode, and `Read`/`Write` allow rules,** don't give the boundary:
  - a bare `Read` rule allowed reading anywhere;
  - `Write(./**)` is ignored (only `Edit(path)` rules match file writes);
  - `acceptEdits` does it with no file rules at all.
- **`~/.claude` is protected.** Writes there are refused in every mode, so the scratch folder must live elsewhere (the system temp folder).
- **`--bare` is unusable for subscription users,** since it reads only an API key.
- **Other installed skills still show up** with `--setting-sources project`. That's harmless with the tool limits above.
- **Without `stdin` closed,** Claude Code waits 3 s and warns.

## The run

- **Time and cost:** about 4.7 minutes, 13 turns, $0.49 (Sonnet).
- **Steps:** it loaded the skill, read the rule syntax, wrote `moscavian.language.json` and ran `./check`. Of the 35 words, 28 didn't fit the rules at first; it rewrote the file, ran the check again, and got 1 of 35. Then it replied `DONE moscavian.language.json`.
- **Three permission denials** were all `./check …; echo "EXIT:$?"`. They cost turns but didn't stop it. The brief should say: run `./check FILE` on its own.
- **The file** has 35 words with short meanings (for example `voskor`: fortress, stronghold), 4 phrases, and generators for words, characters and places. It has no blocking problems. A copy is in the main checkout at `.superpowers/spike-cc/moscavian.language.json` (untracked).

## Output capture

- **`stream-json`** gives one JSON object per line:
  - `type: "assistant"` events carry `tool_use` blocks (name and input). These are the progress the app shows, for example "Writing moscavian.language.json" and "Running the check".
  - `type: "user"` events carry `tool_result` blocks, with `is_error` set on denials.
  - The final `type: "result"` event has `subtype`, `is_error`, `result` (the last reply text), `total_cost_usd`, `duration_ms`, `num_turns` and `permission_denials`.
- **The file is read from the folder,** as the one `*.language.json` there. If there isn't one, the app falls back to the reply text, using `parse_language_text`, which already accepts a whole reply with chat around the JSON.

## Decisions for plan 3b

1. **Invocation:** as above.
   - The command is a setting, default `claude`.
   - The model is a setting; empty means Claude Code's own default.
2. **The scratch folder** comes from `tempfile.mkdtemp(prefix="fm-language-")`. It holds the skill copy, a `check` wrapper, `brief.md`, and the current language file for a revision. It's removed after the result is read.
3. **The wrapper:**
   - on POSIX, `check` is a shell script running `sys.executable -m talemate.languages check "$@"`;
   - on Windows, `check.cmd` with `Bash(./check.cmd:*)`.
   - *My call:* Windows is written but untested.
4. **The repair loop:**
   - The app runs the shared check on the file itself.
   - When the repair note warrants it (a blocking problem, or warnings on more than a third of the words, per the spec), the app runs Claude Code again in the same folder, with the note and "fix `<file>`".
   - At most twice.
5. **Cancel** kills the process tree (as `client/pi_bridge.py` does) and removes the folder.
