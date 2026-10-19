"""The derived search index: a chromadb collection rebuilt from the world
database so the AI can later recall individual facts filtered by in-world
date.

The index is never a source of truth -- `WorldIndex.rebuild` drops and
refills it from scratch, and nothing here is read anywhere else in this
package. `index_documents` computes what the collection should hold without
touching chromadb at all, which keeps it usable on a machine where
`import chromadb` fails (R7: on at least one dev box, numpy can't find
`libz.so.1` outside a shell that hands it zlib). `chromadb` itself is
imported lazily, inside `WorldIndex`, so importing this module never
requires it.

chromadb metadata can't hold `None` or an unbounded span, so an open start
or end is stored as the numeric sentinels `OPEN_START`/`OPEN_END` instead,
and a header's missing `fact_id`/`category` as an empty string.

Each fact document carries its stable `fact_id`, and the collection records
the revision it was built at (`WorldIndex.built_rev`), so a hit can be
re-rendered from the world itself, e.g. at a scene's date.
"""

import sqlite3

import structlog
from pydantic import BaseModel

from .dates import WorldDate
from .store import World

log = structlog.get_logger("talemate.world.index")

# chromadb metadata values must be numeric; an unbounded span is stored as
# these sentinels rather than None or an infinity.
OPEN_START = -1
OPEN_END = 2**53 - 1


class IndexDoc(BaseModel):
    id: str
    thing_id: str
    kind: str
    category: str | None
    # the fact's stable id for a fact document; None for a thing header
    fact_id: str | None
    text: str
    valid_from: int
    valid_until: int


def index_rows(conn: sqlite3.Connection, rev: int) -> list[sqlite3.Row]:
    """Every fact row live at `rev` on the source clock (`rev_added <=
    rev`, not yet retired), across every story date. Package code never
    touches a `World`'s connection directly, so this takes it explicitly,
    the same way `timeline.build_timeline` and `undo.undo_revisions` do;
    `World._live_fact_rows` is the method that supplies it."""

    return conn.execute(
        "SELECT row_id, fact_id, thing_id, category, text, valid_from, valid_until "
        "FROM facts WHERE rev_added <= ? AND (rev_removed IS NULL OR rev_removed > ?)",
        (rev, rev),
    ).fetchall()


def index_documents(world: World, rev: int | None = None) -> list[IndexDoc]:
    """Every document the index should hold at `rev` (`None` means
    `world.head_rev()`): one header per thing (`id = thing_id`, text
    `"<kind>: <latest name>"`) plus one per fact *version* that's live at
    `rev` on the source clock (`rev_added <= rev`, not yet retired), across
    every story date -- an ended fact still needs to be searchable by the
    date it was true. Each fact's text is rendered with
    `world.view(at=None, rev=rev).render`, prefixed with its thing's
    (latest-known) name, and its own story-time span becomes the
    document's bounds."""

    rev = rev if rev is not None else world.head_rev()
    view = world.view(at=None, rev=rev)

    names: dict[str, str] = {}
    kinds: dict[str, str] = {}
    docs: list[IndexDoc] = []

    for thing in view.things():
        name = view.name_of(thing.id) or thing.id
        names[thing.id] = name
        kinds[thing.id] = thing.kind
        docs.append(
            IndexDoc(
                id=thing.id,
                thing_id=thing.id,
                kind=thing.kind,
                category=None,
                fact_id=None,
                text=f"{thing.kind}: {name}",
                valid_from=OPEN_START,
                valid_until=OPEN_END,
            )
        )

    # `remove_thing` retires a thing's facts in the same revision it
    # retires the thing, so any fact row still live at `rev` belongs to a
    # thing that's also live at `rev` -- `names`/`kinds` always have an
    # entry for `row["thing_id"]` below.
    for row in world._live_fact_rows(rev):
        thing_id = row["thing_id"]
        docs.append(
            IndexDoc(
                id=f"fact:{row['row_id']}",
                thing_id=thing_id,
                kind=kinds[thing_id],
                category=row["category"],
                fact_id=row["fact_id"],
                text=f"{names[thing_id]}: {view.render(row['text'])}",
                valid_from=OPEN_START
                if row["valid_from"] is None
                else row["valid_from"],
                valid_until=OPEN_END
                if row["valid_until"] is None
                else row["valid_until"],
            )
        )

    return docs


def _metadata_for(doc: IndexDoc) -> dict[str, object]:
    return {
        "thing_id": doc.thing_id,
        "kind": doc.kind,
        "category": doc.category or "",
        "fact_id": doc.fact_id or "",
        "valid_from": doc.valid_from,
        "valid_until": doc.valid_until,
    }


def _doc_from_result(doc_id: str, text: str, metadata: dict[str, object]) -> IndexDoc:
    return IndexDoc(
        id=doc_id,
        thing_id=metadata["thing_id"],
        kind=metadata["kind"],
        category=metadata["category"] or None,
        fact_id=metadata["fact_id"] or None,
        text=text,
        valid_from=metadata["valid_from"],
        valid_until=metadata["valid_until"],
    )


class WorldIndex:
    """A chromadb collection derived from one world's facts, named
    `"world-<world.id>"` and stored under `world.path / "index"` by
    default. Built by `rebuild`, read by `query`; never written to
    directly."""

    def __init__(self, world: World, *, client=None, embedding_function=None):
        self._world = world
        self._embedding_function = embedding_function
        self._client = client if client is not None else self._default_client(world)
        self._collection_name = f"world-{world.id}"

    @staticmethod
    def _default_client(world: World):
        import chromadb

        return chromadb.PersistentClient(path=str(world.path / "index"))

    def _collection_kwargs(self) -> dict[str, object]:
        if self._embedding_function is None:
            return {}
        return {"embedding_function": self._embedding_function}

    def _collection(self):
        return self._client.get_collection(
            self._collection_name, **self._collection_kwargs()
        )

    def rebuild(self, rev: int | None = None) -> int:
        """Drop the collection if it exists, recreate it, and refill it
        from `index_documents(self._world, rev)` (`None` means head),
        recording `rev` in the collection's metadata. Returns the document
        count."""

        import chromadb

        rev = rev if rev is not None else self._world.head_rev()

        try:
            self._client.delete_collection(self._collection_name)
        except chromadb.errors.NotFoundError:
            pass

        collection = self._client.create_collection(
            self._collection_name, metadata={"rev": rev}, **self._collection_kwargs()
        )

        docs = index_documents(self._world, rev)
        if docs:
            collection.add(
                ids=[doc.id for doc in docs],
                documents=[doc.text for doc in docs],
                metadatas=[_metadata_for(doc) for doc in docs],
            )

        log.info(
            "world.index.rebuild", world_id=self._world.id, rev=rev, count=len(docs)
        )
        return len(docs)

    def built_rev(self) -> int | None:
        """The revision the collection was last rebuilt at, or `None` if
        it hasn't been built."""

        import chromadb

        try:
            collection = self._collection()
        except chromadb.errors.NotFoundError:
            return None
        return (collection.metadata or {}).get("rev")

    def query(
        self,
        text: str,
        *,
        at: WorldDate | None,
        n: int = 10,
        kind: str | None = None,
    ) -> list[IndexDoc]:
        """The `n` documents closest to `text`, restricted to those whose
        story-time span covers `at` (`at=None` means the open-ended ones:
        `valid_until == OPEN_END`), and to `kind` when given."""

        clauses: list[dict[str, object]] = []
        if at is not None:
            clauses.append({"valid_from": {"$lte": at.instant}})
            clauses.append({"valid_until": {"$gt": at.instant}})
        else:
            clauses.append({"valid_until": OPEN_END})
        if kind is not None:
            clauses.append({"kind": kind})
        where = clauses[0] if len(clauses) == 1 else {"$and": clauses}

        result = self._collection().query(query_texts=[text], n_results=n, where=where)

        ids = result["ids"][0]
        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        return [
            _doc_from_result(doc_id, doc_text, metadata)
            for doc_id, doc_text, metadata in zip(ids, documents, metadatas)
        ]
