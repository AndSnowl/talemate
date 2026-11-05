# Languages 4b-2 acceptance: people's names

Date: 2026-11-04. Real runs, with the owner's go-ahead for every AI run of 4b-2:
- Fill them in on Claude Code (opus);
- drafts and title meanings on Skyfall-31B (koboldcpp).

They ran in a fresh throwaway app holding copies of the owner's test-app worlds and config. The owner's own app was not touched.

- **Script:** `.superpowers/sdd/…/real_runs_4b2.py`.
- **Raw runs:** `raw/2026-11-04-languages-4b2-acceptance-run{1,2,3}.json`.

## The runs

1. **Fill them in from the grammar** on Drassonais (Test3) and Varovni (Test2), through the People's names card and the import review. It took 109–128 s for Drassonais and 189–254 s for Varovni.
   - **Drassonais** got:
     - choices sex and rank;
     - kept titles mesté "sir" and dauné "madam";
     - forms of address;
     - full-name rules: "from father, then mother · family", for: man / for: woman.
   - **Varovni** got:
     - the family name's woman's form ("forms by sex");
     - an owl-name rule;
     - in one run, kept titles Gosvarush "Your Majesty" and Slevarush "honoured priest".
2. **"a daughter of Eilhaud of Drassone, raised at court"** drafted in Test3, then accepted, then Name it on her, then a title from the meaning "keeper of the river".
3. **"an owl-folk hunter who watches the stars, a son of Zakan"** drafted in Test2.

## What each run found, and what was fixed

| run | found | fixed |
|---|---|---|
| 1 | The model's In rows said "daughter" or "son", not "daughter of", so neither child inherited. The owl son got no built name. | `PARENT_WORDS` gains "daughter", "son" and "child". |
| 1 | A filled-in pet rule gave "Dilhie" back unchanged. | A pet rule that changes nothing gives no pet name. |
| 2 | Both children inherited, but the daughter's source was the realm "Drassone" ("heir and daughter of the sovereign"), and the son's a court. | Only a person (character or being) is a parent. |
| 2 | Name it on the accepted daughter rolled her inherited part: her parent row was never ticked, so she isn't filed under him. | A stored inherited part keeps its source in Name it. |
| 3 | The model linked no parent; the son's only row is his place, unticked, so no language was in reach. | A person's language falls back to any of the model's rows. |
| 3 | The daughter's draft invented its own father ("Treindrac Di Terrou") rather than linking Eilhaud. | Not code: the model's reading. The app rolled her family part and offered him as an unticked stub, as designed. |

**Also seen, not code:**
- Fill them in gave Varovni's "Ul" an English writing ("Owl-of"). The owner wants it native, which is one row to change in the Names chapter.
- Drassonais rules write "Di" with a capital.
- Some pet rules are weak ("dear Divlol").

The title from a meaning built "Uldrie Di Rivache" ("keeper" + di + "river") in about 11 s, with the new word saved when picked.

## State at hand-off

All suites pass after the fixes: plain 7795, checks 243, full e2e (count in the final message). Owner's verdict and feedback rounds: pending.
