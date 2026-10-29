# Languages 3b-1 (making a language): the owner's acceptance checklist

Date: 2026-10-28. Branch: `feature/languages-3b1`. Plan: `docs/superpowers/plans/2026-10-28-fantasymate-languages-3b1-making.md`.

As in 3a, there are two checks. **The owner** judges whether each step looks and feels right. **The tests** prove it works. They drive the real app with a fake Claude Code (`tests/languages/data/fake-claude`) and fixed model replies, so no real model or Claude Code runs in them.

| Step | What to look at | Proven by |
|---|---|---|
| **The Language agent's settings.** The agent list has Language; its **Making languages** tab shows the guidance (which jobs need a strong model), the route, and the Claude Code command and model. | Is the guidance clear, with no jargon? | `tests/e2e/agents/test_language_agent_settings.py`; `tests/agents/test_language_agent.py` |
| **Make it with Claude Code.** In the World tab, open Languages. Type "a unique but recognizably Russian language", optionally take Tsardom of Moscavia into account, and press **Make it**. Progress lines show ("Reading the language guide", "Writing …", "Running the check"). The result lands in the import review below, with the file folded away; **Import** opens its page. | Does the progress feel alive? Is the review clear? | `test_language_make.py::test_make_a_language_with_claude_code_lands_in_the_review`, `test_progress_shows_while_it_runs`; `tests/server/test_worlds_language_make.py`; `tests/languages/test_claude_code.py` |
| **Questions.** **Ask me questions** shows up to four plain questions, each with an answer box. **Make it** sends the answers; **Decide for me** lets it choose. | Are the questions plain? | `test_questions_then_decide_for_me`; `tests/languages/test_making_questions.py` |
| **Copy the brief.** Always there. It copies a brief to paste into any assistant (Claude.ai, ChatGPT, …); paste the reply into Import a language. | Does a chat assistant make a good file from it? | `test_copy_the_brief_copies_text`; `tests/languages/test_brief.py` |
| **Cancel.** While it's being made, **Cancel** stops it and the page is idle again. | — | `test_cancel_returns_to_idle`; `test_cancelling_kills_the_process`; `test_cancel_stops_the_job_without_a_done` |
| **When it fails.** The reason shows in plain words, for example "Claude Code stopped: You've hit your usage limit.", or "Claude Code isn't installed here: …", and Copy the brief stays. | Is it clear what to do next? | `test_a_failed_run_shows_why`; `test_a_missing_command_says_claude_code_isnt_installed` |
| **The in-app route** (Language agent → This agent's model), if a strong model is set up: the same flow, with "Asking the model" and up to two repairs. | — | `tests/languages/test_making.py` |
| **The check is sent back.** A file with something to fix (a broken rule, or most words not following the rules) is sent back at most twice before the owner sees it. | — | `test_a_blocking_problem_is_sent_back_once_then_fixed`, `test_repairs_stop_after_two` |

## Real runs, with the owner's go-ahead

- [ ] **Claude Code, for real.** On the owner's machine, with their subscription, it costs about $0.50 and 5 minutes (the spike). Run "a unique but recognizably Russian language for the Tsardom of Moscavia", taking the Tsardom into account. Import the result, then name something with it.
- [ ] **Copy the brief into a chat assistant,** and import its reply.

## Results

*(filled in during the walk)*
