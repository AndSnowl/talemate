# Connections: owner acceptance run

Date: 2026-10-21. Branch `feature/connections`, first run at a74fee65. Model: koboldcpp, Skyfall-31B-v4.2-i1-Q4_K_M.

## Result

**Accepted, with no hiccups.** The owner ran the spec's session:
- the owl species, with its origin naming the Tsardom of Moscavia;
- humans;
- places made by following stubs;
- the Tsardom's religion explored in depth;
- a courier scene.

In the owner's words: "The connections are working phenomenally, the Tsardom generation included so many juicy details", including racism between the owl-folk races, and religious institutions with their explanation of the transformation. "This has essentially become wikipedia for a fantasy world that builds itself around you." Generation "stayed strong" through deep chains of lore: structure, practices and ceremonies.

## Requests during the run (done)

- **Right-click menu** (e636301f): browsers give pages no access to spell check, so the custom menu now has Undo, Redo, Select all and Delete, all on the field's own undo history. It also has a "Spell check: Shift+right-click" hint, and Shift+right-click opens the browser's own menu.
- **Home-network access** (81f1a280): `talemate_app.py start --lan` serves the app at the machine's LAN address. There's no login, so it's for the home network only.

## Recorded for later

- **Our own spell check** that knows every world word (main spec, a quality-of-life item).
- **Connections in scenes** (main spec, under Scene runners). In the courier scene, the model knew the postmaster's name from context but not her entry, and invented details. An entry that comes into play should bring its own facts in, and names first seen in play should become stubs (through the inbox).
- **Deferred minors** from the build are listed in the ledger. The final review triaged them as safe to leave. They include:
  - everyday names in the scene-setup prompt and character sheets;
  - re-picks in the new-scene dialog teaching other names;
  - the create-mix template lacking the bare-demonym rule.
