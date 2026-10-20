"""`index_documents` runs without chromadb (R7: it can fail to import on
this machine). `WorldIndex` needs it, so its tests skip with a clear reason
when it isn't importable, and only run for real under
`guix shell -m manifest.scm zlib -- bash -c 'LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync pytest tests/world'`.
"""

from talemate.world.dates import WorldDate
from talemate.world.index import OPEN_END, OPEN_START, WorldIndex, index_documents
from talemate.world.refs import ref
from talemate.world.store import Source

from world.embedding import TrigramEmbeddingFunction, chromadb, requires_chromadb


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
        embedding_function=TrigramEmbeddingFunction(),
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
        embedding_function=TrigramEmbeddingFunction(),
    )

    first = index.rebuild()
    second = index.rebuild()

    assert first == second == len(index_documents(world))


def test_index_documents_carry_fact_ids(world, maren):
    docs = index_documents(world)

    header = next(doc for doc in docs if doc.id == maren.id)
    assert header.fact_id is None
    by_fact = {doc.fact_id: doc for doc in docs if doc.fact_id is not None}
    assert set(by_fact) == {maren.tattoo, maren.warden, maren.laugh, maren.eye}
    assert "eye" in by_fact[maren.eye].text


def _index(world):
    return WorldIndex(
        world,
        client=chromadb.EphemeralClient(),
        embedding_function=TrigramEmbeddingFunction(),
    )


@requires_chromadb
def test_query_returns_fact_ids(world, maren):
    index = _index(world)
    index.rebuild()

    hits = index.query("Lost her left eye", at=WorldDate.of(315), n=10)

    eye = next(doc for doc in hits if "eye" in doc.text.lower())
    assert eye.fact_id == maren.eye
    header = next(doc for doc in hits if doc.id == maren.id)
    assert header.fact_id is None


@requires_chromadb
def test_built_rev_records_rebuild_rev(world, maren):
    index = _index(world)
    assert index.built_rev() is None

    index.rebuild()
    assert index.built_rev() == world.head_rev()

    index.rebuild(rev=maren.rev_created)
    assert index.built_rev() == maren.rev_created
