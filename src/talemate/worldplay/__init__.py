"""Worldplay: bringing a `talemate.world` world into play.

A world's things (`talemate.world`) are plain data -- fields, facts, a
calendar. This package turns them into what Talemate's existing agents
already understand:

- `characters.py` builds an ordinary `Character` from a world thing as of a
  given in-world date, with no model call;
- `prose_gen.py` calls the model to generate and cache the prose
  `characters.py` reads;
- `create.py` creates a thing from the owner's prompt (a preview that
  writes nothing, then accept), also calling the model;
- `context.py` is the scene-level "World" context block (goal, place,
  lore) injected into narrator and actor prompts, and keeps a scene's
  active characters fresh across time passage.

Nothing here is wired into normal scene play yet -- that's a later task.
"""
