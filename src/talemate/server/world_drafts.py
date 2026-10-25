"""The small-draft store: one versioned slot per key, shared by every
small "ask to tick" draft a world-UI session can hold -- a fact or event
draft (`facts_key`), a group-add draft (`group_key`) and the nested draft
a page draft can hold open (`nested_key`). Pure and generic over pydantic
models: it knows nothing of a world, a session or the websocket protocol,
so `worlds.py` wires it in and owns the keys' meaning.

Mirrors the page-draft store in `worlds.py` (`_new_version`, `_touch`,
`_draft_out`): an `OrderedDict` of versions per key, an LRU cap, and a
separate dict of each key's current version. `DRAFT_VERSIONS` lives here
(R1) so `worlds.py` can import it without this module importing anything
back from `worlds.py`.
"""

from __future__ import annotations

from collections import OrderedDict

import pydantic

# the versions a draft keeps (Version n of m), the oldest dropped first --
# shared with the page-draft store in worlds.py, which imports it from here
DRAFT_VERSIONS = 5

# the small drafts a session keeps, the least recently used forgotten
# first -- separate from worlds.py's DRAFTS_KEPT, which caps page drafts
SMALL_DRAFTS_KEPT = 20


def facts_key(thing_id: str) -> str:
    """One fact-or-event draft per page."""

    return f"facts:{thing_id}"


def group_key(thing_id: str, tag: str | None) -> str:
    """One group-add draft per page and group (`tag` is `""` for the
    page's own, untagged group)."""

    return f"group:{thing_id}:{tag or ''}"


def nested_key(page_key: str) -> str:
    """One nested draft per page draft, keyed off that page draft's own
    key."""

    return f"nested:{page_key}"


class SmallDrafts:
    """A versioned, least-recently-used store of small drafts, keyed by
    `facts_key`/`group_key`/`nested_key` (or any string a caller picks).

    `.add` appends a version and makes it current; `.use` restores a kept
    version by its 1-based number; `.current`, `.versions`, `.index` and
    `.held` read a key's state; `.discard` drops one key and `.clear`
    drops every key.

    Each key also carries an "ask" sequence number (R2), separate from
    whether the key holds a draft: `.ask(key)` bumps and returns it when
    a caller starts an asynchronous reply (a model call) for that key,
    before any version exists; `.is_latest(key, seq)` tells the caller,
    once the reply comes back, whether it is still the one that matters.
    A reply isn't latest once a later ask for the same key replaced it,
    once `.discard` or `.clear` ran, or once the LRU cap forgot the key
    entirely (eviction forgets a key's ask along with its slot, the same
    as a discard -- see the asking methods below)."""

    def __init__(self, limit: int = SMALL_DRAFTS_KEPT, versions: int = DRAFT_VERSIONS):
        self._limit = limit
        self._versions = versions
        self._drafts: OrderedDict[str, list[pydantic.BaseModel]] = OrderedDict()
        self._current: dict[str, int] = {}
        # the latest ask sequence number issued per key; a key can be
        # asked before it ever holds a draft, so this is independent of
        # `_drafts`
        self._asks: dict[str, int] = {}
        # the last number issued, store-wide and never reused: a key
        # discarded and asked again must not hand out a number an older
        # reply still out already holds
        self._seq = 0

    def add(self, key: str, value: pydantic.BaseModel) -> int:
        """Append `value` as the newest version of `key`'s draft (at most
        `versions`, the oldest dropped first), make it current, and move
        `key` to most recently used, evicting the least recently used
        past `limit`. Returns the new current version's 0-based index."""

        versions = self._drafts.setdefault(key, [])
        versions.append(value)
        del versions[: -self._versions]
        index = len(versions) - 1
        self._touch(key, index)
        return index

    def current(self, key: str) -> pydantic.BaseModel:
        """The draft's current version."""

        versions = self._require(key)
        return versions[self._current[key]]

    def use(self, key: str, version: int) -> pydantic.BaseModel:
        """Make `version` (1-based) `key`'s current version and return
        it."""

        versions = self._require(key)
        if not 1 <= version <= len(versions):
            raise ValueError(f"the draft has no version {version}")
        index = version - 1
        self._touch(key, index)
        return versions[index]

    def versions(self, key: str) -> list[pydantic.BaseModel]:
        """Every version kept, oldest first."""

        return list(self._require(key))

    def index(self, key: str) -> int:
        """The draft's current version, 0-based."""

        self._require(key)
        return self._current[key]

    def held(self, key: str) -> bool:
        return key in self._drafts

    def discard(self, key: str) -> None:
        """Drop every version of `key`'s draft, if any, and invalidate
        any outstanding ask for it, so a reply already in flight is
        dropped rather than reviving what was just thrown away. A
        missing key is a no-op."""

        self._drafts.pop(key, None)
        self._current.pop(key, None)
        self._asks.pop(key, None)

    def clear(self) -> None:
        """Drop every draft and invalidate every outstanding ask (a
        world switch)."""

        self._drafts.clear()
        self._current.clear()
        self._asks.clear()

    def ask(self, key: str) -> int:
        """Bump and return `key`'s ask sequence number, for a reply that
        will come back later (a model call). Does not create a slot: a
        key with no draft yet can still be asked. Asking again for the
        same key (a regeneration, or a second request sent before the
        first answers) makes the earlier ask no longer latest, and so
        does asking again after a `.discard` (the numbers are never
        reused)."""

        self._seq += 1
        self._asks[key] = self._seq
        return self._seq

    def is_latest(self, key: str, seq: int) -> bool:
        """Whether `seq` (from an earlier `.ask(key)`) is still the
        latest one asked for `key`. False once a later ask replaced it,
        once `.discard` or `.clear` ran, once the LRU cap forgot `key`,
        or if `key` was never asked."""

        return self._asks.get(key) == seq

    def _require(self, key: str) -> list[pydantic.BaseModel]:
        versions = self._drafts.get(key)
        if not versions:
            raise KeyError(f"no such draft: {key}")
        return versions

    def _touch(self, key: str, index: int) -> None:
        """Make `index` current and `key` most recently used, forgetting
        the least recently used past `limit` -- and with it, that key's
        outstanding ask, the same as `discard` would."""

        self._current[key] = index
        self._drafts.move_to_end(key)
        while len(self._drafts) > self._limit:
            gone, _versions = self._drafts.popitem(last=False)
            self._current.pop(gone, None)
            self._asks.pop(gone, None)
