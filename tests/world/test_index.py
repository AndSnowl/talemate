"""`index_documents` runs without chromadb (R7: it can fail to import on
this machine). `WorldIndex` needs it, so its tests skip with a clear reason
when it isn't importable, and only run for real under
`guix shell -m manifest.scm zlib -- bash -c 'LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync pytest tests/world'`.
"""

import hashlib

import pytest

from talemate.world.dates import WorldDate
from talemate.world.index import OPEN_END, OPEN_START, WorldIndex, index_documents
from talemate.world.refs import ref
from talemate.world.store import Source

try:
    import chromadb

    _CHROMADB_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - import failure path
    chromadb = None
    _CHROMADB_IMPORT_ERROR = exc

requires_chromadb = pytest.mark.skipif(
    chromadb is None,
    reason=f"chromadb is not importable in this environment: {_CHROMADB_IMPORT_ERROR}",
)


class _TrigramEmbeddingFunction:
    """A deterministic, offline stand-in for a real embedding function:
    hashes each character trigram of the input into one of 64 dimensions.
    Implements the parts of chromadb 1.5.9's `EmbeddingFunction` protocol it
    checks, so no deprecation warnings show."""

    DIMS = 64

    def __call__(self, input: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.DIMS
        padded = f"  {text.lower()}  "
        for i in range(len(padded) - 2):
            digest = hashlib.sha256(padded[i : i + 3].encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.DIMS
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = sum(v * v for v in vector) ** 0.5
        if norm == 0:
            return vector
        return [v / norm for v in vector]

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self(input)

    @staticmethod
    def name() -> str:
        return "test-trigram"

    def get_config(self) -> dict:
        return {}

    @staticmethod
    def build_from_config(config: dict) -> "_TrigramEmbeddingFunction":
        return _TrigramEmbeddingFunction()

    def is_legacy(self) -> bool:
        return False

    def default_space(self) -> str:
        return "cosine"

    def supported_spaces(self) -> list[str]:
        return ["cosine", "l2", "ip"]


def test_index_documents_one_per_fact_plus_header(world, maren):
    docs = index_documents(world)

    headers = [doc for doc in docs if doc.id == maren.id]
    assert len(headers) == 1
    header = headers[0]
    assert header.thing_id == maren.id
    assert header.kind == "character"
    assert header.category is None
    assert header.text == "character: Maren the Grey"
    assert header.valid_from == OPEN_START
    assert header.valid_until == OPEN_END

    fact_docs = [doc for doc in docs if doc.id != maren.id]
    assert len(fact_docs) == 4
    assert all(doc.id.startswith("fact:") for doc in fact_docs)
    assert all(doc.thing_id == maren.id for doc in fact_docs)
    assert all(doc.kind == "character" for doc in fact_docs)

    eye_doc = next(doc for doc in fact_docs if "eye" in doc.text.lower())
    assert eye_doc.text == "Maren the Grey: Lost her left eye."
    assert eye_doc.category == "appearance"
    assert eye_doc.valid_from == WorldDate.of(314).instant
    assert eye_doc.valid_until == OPEN_END

    warden_doc = next(doc for doc in fact_docs if "warden" in doc.text.lower())
    assert warden_doc.valid_from == WorldDate.of(305).instant
    assert warden_doc.valid_until == WorldDate.of(316).instant

    laugh_doc = next(doc for doc in fact_docs if "laugh" in doc.text.lower())
    assert laugh_doc.valid_from == OPEN_START
    assert laugh_doc.valid_until == OPEN_END


def test_index_documents_render_names(world):
    with world.revision(Source.manual(note="create Oskar and a friend")) as rev:
        oskar_id = rev.create_thing("character", fields={"name": "Oskar Dell"})
        friend_id = rev.create_thing("character", fields={"name": "A friend"})
        rev.add_fact(friend_id, "relationship", f"Owes {ref(oskar_id)} a debt.")

    docs = index_documents(world)
    fact_doc = next(doc for doc in docs if doc.thing_id == friend_id and doc.category)

    assert "Oskar Dell" in fact_doc.text
    assert "thing:" not in fact_doc.text


@requires_chromadb
def test_query_filters_by_date(world, maren):
    index = WorldIndex(
        world,
        client=chromadb.EphemeralClient(),
        embedding_function=_TrigramEmbeddingFunction(),
    )
    index.rebuild()

    before = index.query("eye", at=WorldDate.of(312), n=5)
    assert not any("eye" in doc.text.lower() for doc in before)

    after = index.query("eye", at=WorldDate.of(315), n=5)
    assert any("eye" in doc.text.lower() for doc in after)


@requires_chromadb
def test_rebuild_is_idempotent(world, maren):
    index = WorldIndex(
        world,
        client=chromadb.EphemeralClient(),
        embedding_function=_TrigramEmbeddingFunction(),
    )

    first = index.rebuild()
    second = index.rebuild()

    assert first == second == len(index_documents(world))
