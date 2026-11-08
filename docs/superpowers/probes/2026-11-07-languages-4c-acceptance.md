# Languages 4c acceptance

Date: 2026-11-07. The owner said yes to the run.
- **Where:** a throwaway app holding a copy of the owner's test-app world; the owner's own app was not touched.
- **Models:** Skyfall-31B on koboldcpp; Claude Code (opus) for Fill them in.
- **Raw run:** `raw/2026-11-07-languages-4c-acceptance.json`.

## Before the runs

Preparing the script turned up a gap the final review hadn't caught. Name it opened from a flagged name in "+ Add facts" or a group's "+ Add" wasn't in person mode, so no rule was picked there. The spec says the pick happens in Name it, the same panel for every draft. Fixed: `openNameItForMark` opens a character's mark in person mode. A check failed first.

## The runs

1. **Fill them in on Zhelvan:** 123 s. The main rules came first, with their descriptions; the pieces were folded below.
2. **Name it on Gosmar Zochar Vekhal's page:** the model picked "the Gosmar (tsar) of Zhelvanya" in 1.9 s and built "Gosmar Nashen Zvoralesh of Zhelvanya".
3. **A new prince** ("the Gosmar's youngest son, a Zhelvan prince who keeps falcons"):
   - The draft took 47 s. The model named him "Aldric Gosmar", marked "Name it can build it from Zhelvan's rules for people".
   - Name it from the flag picked "noblemen of an estate" in 1.8 s and built "Tiker Kivtol Gudyelov of Keduvsk", which was used and accepted.
   - Reasonable: Zhelvan's sovereign rule is for the Gosmar himself, and there's no rule for his children.
   - The page's Name section shows the parts.
4. **"+ Add facts" on the Gosmar** ("his younger brother, a cavalry commander, and his sister, the abbess…"):
   - The draft took 28 s and named Vekhal Drossyn Zochar and Zochar Veyla Nyessa.
   - **Neither was flagged:** the name check judged both names fine. By the owner's decision (marks unchanged: only flagged names, plus a drafted person's own), no person mark was offered, so the "+ Add facts" pick wasn't exercised on a real run. The check above covers it.
   - **The flags** were "Northern Vanguard" (a regiment) and "Convent of Still Waters".
   - **For the owner:** Name it on the regiment defaulted to Zhelvan's men's rule and built a person's name. This is older behaviour that 4c made visible:
     - Zhelvan has no rule for groups by kind (its "groups" rule is filed under "people");
     - the default rule falls back to the first main rule, a people rule.

## Harness note

The first run read the "+ Add facts" placeholder ("Drafting…") as the finished draft. Step 4 was re-run, waiting for the fact rows.
