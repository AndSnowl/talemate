"""Tests for the small-draft store (`talemate.server.world_drafts`), the
versioned, LRU container every small ask-to-tick draft (facts, group-adds,
nested drafts) will share. Pure and generic over pydantic models; no world,
no websocket."""

from __future__ import annotations

import pydantic
import pytest

from talemate.server.world_drafts import (
    DRAFT_VERSIONS,
    SMALL_DRAFTS_KEPT,
    SmallDrafts,
    facts_key,
    group_key,
    nested_key,
    page_key,
)


class Stub(pydantic.BaseModel):
    name: str


def test_add_and_current():
    drafts = SmallDrafts()
    drafts.add("k", Stub(name="first"))
    index = drafts.add("k", Stub(name="second"))

    assert index == 1
    assert drafts.current("k") == Stub(name="second")
    assert drafts.versions("k") == [Stub(name="first"), Stub(name="second")]


def test_versions_capped():
    drafts = SmallDrafts(versions=5)
    for n in range(7):
        drafts.add("k", Stub(name=str(n)))

    kept = drafts.versions("k")
    assert [s.name for s in kept] == ["2", "3", "4", "5", "6"]


def test_use_restores_and_refuses_unknown():
    drafts = SmallDrafts()
    drafts.add("k", Stub(name="first"))
    drafts.add("k", Stub(name="second"))

    restored = drafts.use("k", 1)
    assert restored == Stub(name="first")
    assert drafts.current("k") == Stub(name="first")
    assert drafts.index("k") == 0

    with pytest.raises(ValueError):
        drafts.use("k", 9)

    with pytest.raises(KeyError):
        drafts.current("nope")


def test_lru_eviction():
    drafts = SmallDrafts(limit=2)
    drafts.add("a", Stub(name="a"))
    drafts.add("b", Stub(name="b"))
    drafts.add("c", Stub(name="c"))

    assert drafts.held("a") is False
    assert drafts.held("b") is True
    assert drafts.held("c") is True

    # touching a held key with add or use keeps it from eviction
    drafts2 = SmallDrafts(limit=2)
    drafts2.add("a", Stub(name="a"))
    drafts2.add("b", Stub(name="b"))
    drafts2.use("a", 1)
    drafts2.add("c", Stub(name="c"))

    assert drafts2.held("a") is True
    assert drafts2.held("b") is False
    assert drafts2.held("c") is True


def test_discard_and_clear():
    drafts = SmallDrafts()
    drafts.add("a", Stub(name="a"))
    drafts.add("b", Stub(name="b"))

    drafts.discard("a")
    assert drafts.held("a") is False
    assert drafts.held("b") is True
    # a missing key is a no-op
    drafts.discard("nope")

    drafts.clear()
    assert drafts.held("b") is False


def test_keys():
    assert facts_key("thing-1") == "facts:thing-1"
    assert group_key("x", "tag") == "group:x:tag"
    assert group_key("x", None) == "group:x:"
    assert group_key("x", "") == "group:x:"
    assert nested_key("stub:1") == "nested:stub:1"
    assert page_key(nested_key("new:lore:nested:x")) == "new:lore:nested:x"
    with pytest.raises(ValueError):
        page_key("facts:thing-1")


def test_ask_sequence():
    """The per-key ask sequence number (R2): a reply is dropped unless it
    answers the latest ask for its key.

    Eviction choice (documented here, since the brief leaves it open):
    once the LRU cap forgets a key, its outstanding ask is forgotten too,
    the same as a discard. A late reply for a forgotten key gets no
    special treatment -- it's simply no longer "latest", so the caller
    drops it, same as any other stale reply. (The alternative -- letting
    a forgotten key's ask stay valid -- would let a stale reply silently
    start a brand new draft under an old, already-forgotten key, which is
    more surprising than just dropping it.)
    """

    drafts = SmallDrafts()
    seq = drafts.ask("k")
    assert drafts.is_latest("k", seq) is True

    # a second ask for the same key makes the first stale
    seq2 = drafts.ask("k")
    assert seq2 != seq
    assert drafts.is_latest("k", seq) is False
    assert drafts.is_latest("k", seq2) is True

    # discard invalidates any outstanding ask for that key
    seq3 = drafts.ask("other")
    drafts.discard("other")
    assert drafts.is_latest("other", seq3) is False
    # ...and asking again after a discard never reissues its number, so
    # a reply still out from before the discard stays stale
    seq3b = drafts.ask("other")
    assert drafts.is_latest("other", seq3) is False
    assert drafts.is_latest("other", seq3b) is True

    # clear invalidates every outstanding ask
    seq4 = drafts.ask("k")
    drafts.clear()
    assert drafts.is_latest("k", seq4) is False

    # eviction: a key's outstanding ask is forgotten along with its slot
    evicting = SmallDrafts(limit=2)
    evicting.add("a", Stub(name="a"))
    ask_a = evicting.ask("a")
    assert evicting.is_latest("a", ask_a) is True

    evicting.add("b", Stub(name="b"))
    evicting.add("c", Stub(name="c"))  # evicts "a" (least recently used)

    assert evicting.held("a") is False
    assert evicting.is_latest("a", ask_a) is False

    # an unknown key was never asked
    assert drafts.is_latest("never-asked", 1) is False


def test_asking_until_answered():
    """`.asking(key)`: an ask is out for `key` until `.answered(key, seq)`
    names that ask, or a discard, clear or eviction forgets it. Answering
    an older ask leaves a newer one out."""

    drafts = SmallDrafts()
    assert drafts.asking("k") is False
    first = drafts.ask("k")
    assert drafts.asking("k") is True
    second = drafts.ask("k")
    drafts.answered("k", first)
    assert drafts.asking("k") is True
    drafts.answered("k", second)
    assert drafts.asking("k") is False
    # answered asks are still the latest: the reply that answered is taken
    assert drafts.is_latest("k", second) is True

    drafts.ask("k")
    drafts.discard("k")
    assert drafts.asking("k") is False
    drafts.ask("k")
    drafts.clear()
    assert drafts.asking("k") is False

    evicting = SmallDrafts(limit=1)
    evicting.add("a", Stub(name="a"))
    evicting.ask("a")
    evicting.add("b", Stub(name="b"))
    assert evicting.asking("a") is False


def test_module_constants():
    assert DRAFT_VERSIONS == 5
    assert SMALL_DRAFTS_KEPT == 20
