"""Held by, in words: a fact a sphere, a character or a being holds as a
belief reaches a scene or a prose prompt as "<Holder> holds that <text>",
or "<Holder> holds: <Text>" when the text has no subject of its own
(`held_text`, ruling C6), unless its text already says who holds it
(`attributes_itself`).

Low-level on purpose: it imports only `talemate.world`, so `prose_gen`
and `characters` (which imports `prose_gen`) can both use it. The
mid-sentence rule (`_mid_sentence`) is also the tie lines' ("..., but:
<text>"), re-exported by `characters`.
"""

from __future__ import annotations

import re

from talemate.world import spheres
from talemate.world.names import find_names
from talemate.world.view import FactState, ThingState, WorldView


def _opens_with_a_name(view: WorldView, raw: str, text: str) -> bool:
    """Whether `text` (rendered from `raw`) opens with a name: a
    reference, "I" ("I'll"), a word in capitals, or (checked last, the
    costly one) a world name `find_names` matches at its very start,
    linked or not, other than a mere suggestion."""

    if raw.lstrip().startswith("[["):
        return True
    word = text.split(" ", 1)[0].split("'", 1)[0].strip(",;:")
    if word == "I" or (len(word) > 1 and word.isupper()):
        return True
    return any(
        match.start == 0 and not match.suggested for match in find_names(view, text)
    )


def _mid_sentence(view: WorldView, raw: str, text: str) -> str:
    """`text` (rendered from `raw`) to follow "but: ": its closing period
    dropped and its first letter lowercased, unless it opens with a name
    (`_opens_with_a_name`)."""

    text = text.strip().rstrip(".").rstrip()
    if not text or _opens_with_a_name(view, raw, text):
        return text
    return text[0].lower() + text[1:]


# the verbs a text that says who holds it uses after the holder's name
# ("the Church teaches that ..."): it's then left as it is
_ATTRIBUTING_VERBS = (
    "teach",
    "teaches",
    "taught",
    "hold",
    "holds",
    "held",
    "believe",
    "believes",
    "believed",
)
_ARTICLES = ("the", "a", "an")


def _bare_name(name: str) -> str:
    """`name` casefolded, its spaces collapsed, less a leading article."""

    words = name.casefold().split()
    if len(words) > 1 and words[0] in _ARTICLES:
        words = words[1:]
    return " ".join(words)


def attributes_itself(text: str, names: list[str]) -> bool:
    """Whether `text` already says who holds it: one of `names` (the
    holder's, with or without a leading article, ignoring case) followed by
    "teaches", "holds", "believes" or another form of them, as a whole
    word, anywhere in it."""

    folded = " ".join(text.casefold().split())
    verbs = "|".join(_ATTRIBUTING_VERBS)
    for name in names:
        bare = _bare_name(name)
        if not bare:
            continue
        pattern = r"(?<![\w'-])%s\s+(?:%s)(?![\w'-])" % (re.escape(bare), verbs)
        if re.search(pattern, folded):
            return True
    return False


# the first words that give a held text a subject of its own (ruling C6):
# pronouns, then determiners and articles
_SUBJECT_WORDS = frozenset(
    "i he she it they we you his her its their one".split()
    + "the a an this that these those every each all some no any many most".split()
)


def has_subject(view: WorldView, raw: str, text: str) -> bool:
    """Whether `text` (rendered from `raw`) opens with a subject of its
    own: a name (`_opens_with_a_name`), a pronoun or a determiner. One
    that doesn't ("Healed a blind child") opens with a verb or something
    else, and can't follow "holds that"."""

    word = text.strip().split(" ", 1)[0].split("'", 1)[0].strip(',;:"(').casefold()
    return word in _SUBJECT_WORDS or _opens_with_a_name(view, raw, text.strip())


def held_text(
    view: WorldView, fact: FactState, owner: ThingState, text: str | None = None
) -> str:
    """`fact` (of `owner`) as a scene is told it, `text` its rendering
    (`view.render(fact.text)` when not given). Held by someone
    (`spheres.held_by`), it's "<Holder> holds that <text>", the text
    lowered as `_mid_sentence` lowers it (not when it opens with a name,
    but a name's leading "The" is), when it has a subject of its own (`has_subject`); otherwise
    "<Holder> holds: <Text>", its first letter capitalised (ruling C6).
    It's as it is when it isn't held, its holder has no name, or it
    already says who holds it (`attributes_itself`)."""

    rendered = view.render(fact.text) if text is None else text
    holder_id = spheres.held_by(view, fact, owner)
    holder = view.thing(holder_id) if holder_id is not None else None
    name = view.name_of(holder_id) if holder_id is not None else None
    if holder is None or not name:
        return rendered
    names = [name] + [
        entry["name"]
        for entry in holder.fields.get("aka") or []
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    ]
    if attributes_itself(rendered, names):
        return rendered
    holder_name = f"{name[0].upper()}{name[1:]}"
    if has_subject(view, fact.text, rendered):
        body = _mid_sentence(view, fact.text, rendered)
        # a name's leading article reads mid-sentence too: "holds that the
        # Light chose ..."
        if body.startswith("The "):
            body = "the " + body[4:]
        lead = f"{holder_name} holds that "
    else:
        body = rendered.strip().rstrip(".").rstrip()
        body = body[:1].upper() + body[1:]
        lead = f"{holder_name} holds: "
    if not body:
        return rendered
    end = "" if body[-1] in "?!" else "."
    return f"{lead}{body}{end}"
