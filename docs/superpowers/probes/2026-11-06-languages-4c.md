# Probe: languages 4c, picking a person's rule

Date: 2026-11-06. The owner said yes to the run.
- **Harness:** `scripts/dev/probe_4c.py`.
- **Labels:** `raw/2026-11-06-languages-4c-labels.json`, committed before any call.
- **Raw run:** `raw/2026-11-06-languages-4c-run.json`.
- **World:** a read-only copy of the owner's test-app world (Zhelvan).

## Fill them in (Claude Code, opus, the app's own route)

184 s. Every main people rule got a one-line description:
- "ordinary Zhelvan men";
- "noblemen named for their estate";
- "Snowy Owl-folk women, with a feather-name";
- "the Gosmar (tsar) of Zhelvanya".

Main and pieces came out right by default; no `main` overrides were needed.

**Harness failures, not findings.** The first three attempts failed in the probe script, before any result:
- the brief was too long to pass as an argument;
- the reply had text after its JSON;
- with tools turned off, Claude described a file it couldn't write.

The probe now calls the app's own `make_language`.

## Picking (Skyfall-31B on koboldcpp)

15 person prompts, each drafted twice:
- **A:** the draft call itself asked for the rule, with the `create-thing` template patched for the run;
- **B:** the plain draft, then a separate pick call with the rules' descriptions (Task 4's prompt).

| | right picks |
|---|---|
| today's matching on sex and rank (`pick_rule`) | 9 / 15 |
| A, in the draft call | 10 / 15 |
| **B, when Name it opens** | **13 / 15** |

- **Time:** the drafts took about 40 s either way. B's pick call averaged 1.5 s, at most 2.0 s.
- **Other names:** A's drafts wrote 29, B's 28. Asking for the pick in the draft didn't make the model timid, nor did leaving it out make it bolder.
- **B's misses:**
  - "the heir to the throne, eldest daughter of the Gosmar" got the Snowy Owl-folk women's rule. Zhelvan has no women's sovereign rule, and the closest fit was the noblewomen's.
  - "the Gosmar's nephew, a cavalry commander" got the Eared Owl-folk men's rule.
- **Today's matching** misses every owl-folk and sovereign person: it only sees sex and rank.
- **Scoring note:** the harness's first scoring matched "heir" inside "their" and miscounted the noble rules. It was re-scored by rule id, counting the noblewomen's rule right for a sovereign woman (no women's sovereign rule exists). A pick named by its rule's name rather than its id counts too, and Task 4 accepts both.

**Ruling: go.** Picking when Name it opens (B) passes the gate: 12 or more right, and better than today's matching. It's also the consistent way, the same for every draft and page. Task 4 is built as written.
