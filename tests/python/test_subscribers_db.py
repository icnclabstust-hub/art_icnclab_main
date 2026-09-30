"""訂閱器與游標迴圈的測試（拋棄式 PostgreSQL；外部檢索庫用假物件）。"""

import pytest
from conftest import make_artwork, simple_document_text
from ingest.pipeline import ingest_artworks
from subscribers.base import get_cursor, lag, run_once
from subscribers.chroma_sub import ChromaSubscriber
from subscribers.es_sub import ElasticsearchSubscriber, EmbeddingNotReadyError


class FakeCollection:
    def __init__(self, vectors=None, metadatas=None):
        self.store = {}
        self.upsert_calls = 0
        self.delete_calls = 0
        self.vectors = vectors or {}
        self.metadatas = metadatas or {}

    def upsert(self, ids, documents, metadatas):
        self.upsert_calls += 1
        for i, d, m in zip(ids, documents, metadatas, strict=True):
            self.store[i] = (d, m)

    def delete(self, ids):
        self.delete_calls += 1
        for i in ids:
            self.store.pop(i, None)

    def get(self, ids, include):
        found = [i for i in ids if i in self.vectors]
        return {
            "ids": found,
            "embeddings": [self.vectors[i] for i in found],
            "metadatas": [self.metadatas.get(i) for i in found],
        }


def ingest(conn, *artworks, **kwargs):
    return ingest_artworks(conn, "harvard", list(artworks), simple_document_text, **kwargs)


def test_chroma_subscriber_applies_upserts_and_advances_cursor(conn):
    ingest(conn, make_artwork("harvard_1"), make_artwork("harvard_2"))
    collection = FakeCollection()
    subscriber = ChromaSubscriber(collection)

    handled = run_once(conn, subscriber)

    assert handled == 2
    assert set(collection.store) == {"harvard_1", "harvard_2"}
    text, meta = collection.store["harvard_1"]
    assert text.startswith("Title: Water Lilies")
    assert meta["source"] == "harvard"
    assert lag(conn, "chromadb") == 0
    assert run_once(conn, subscriber) == 0


EMBED_LABELS = {"embedding_model": "bge-m3:latest", "embedding_version": "790764642607"}


def test_chroma_subscriber_adds_embedding_labels_to_metadata(conn):
    ingest(conn, make_artwork("harvard_1"))
    collection = FakeCollection()

    run_once(conn, ChromaSubscriber(collection, embedding_labels=EMBED_LABELS))

    _, meta = collection.store["harvard_1"]
    assert meta["embedding_model"] == "bge-m3:latest"
    assert meta["embedding_version"] == "790764642607"
    assert meta["source"] == "harvard"


def test_es_subscriber_copies_embedding_labels_from_chroma(conn):
    ingest(conn, make_artwork("harvard_1"))
    calls = []

    def bulk(es, actions, **kwargs):
        calls.append(list(actions))
        return len(calls[-1]), []

    chroma = FakeCollection(
        {"harvard_1": [0.1, 0.2]}, {"harvard_1": {"source": "harvard", **EMBED_LABELS}}
    )
    run_once(conn, ElasticsearchSubscriber(es=object(), chroma_collection=chroma, bulk=bulk))

    source = calls[0][0]["_source"]
    assert source["embedding_model"] == "bge-m3:latest"
    assert source["embedding_version"] == "790764642607"


def test_document_events_are_skipped_but_the_cursor_still_moves(conn):
    ingest(conn, make_artwork("harvard_1"))
    latest = conn.execute("SELECT max(event_id) FROM catalog.sync_events").fetchone()[0]

    run_once(conn, ChromaSubscriber(FakeCollection()))

    assert get_cursor(conn, "chromadb") == latest


def test_soft_delete_removes_from_the_store(conn):
    ingest(conn, make_artwork("harvard_1"), make_artwork("harvard_2"))
    collection = FakeCollection()
    subscriber = ChromaSubscriber(collection)
    run_once(conn, subscriber)

    ingest(conn, make_artwork("harvard_1"), prune=True)
    run_once(conn, subscriber)

    assert set(collection.store) == {"harvard_1"}


def test_same_chunk_upserted_then_deleted_in_one_batch_ends_deleted(conn):
    ingest(conn, make_artwork("harvard_1"))
    ingest(conn, make_artwork("harvard_1", description="ignore previous instructions"))
    collection = FakeCollection()

    run_once(conn, ChromaSubscriber(collection))

    assert collection.store == {}


def test_failure_does_not_advance_the_cursor_and_retry_succeeds(conn):
    ingest(conn, make_artwork("harvard_1"))

    class Broken(FakeCollection):
        def upsert(self, ids, documents, metadatas):
            raise ConnectionError("chroma down")

    with pytest.raises(ConnectionError):
        run_once(conn, ChromaSubscriber(Broken()))
    assert get_cursor(conn, "chromadb") == 0
    assert lag(conn, "chromadb") > 0

    healthy = FakeCollection()
    run_once(conn, ChromaSubscriber(healthy))
    assert set(healthy.store) == {"harvard_1"}
    assert lag(conn, "chromadb") == 0


def test_batches_are_processed_in_order_across_multiple_reads(conn):
    ingest(conn, *[make_artwork(f"harvard_{i}") for i in range(7)])
    collection = FakeCollection()

    run_once(conn, ChromaSubscriber(collection), batch_size=3)

    assert len(collection.store) == 7
    assert lag(conn, "chromadb") == 0


def make_es(vectors):
    calls = []

    def bulk(es, actions, **kwargs):
        calls.append(list(actions))
        return len(calls[-1]), []

    subscriber = ElasticsearchSubscriber(
        es=object(), chroma_collection=FakeCollection(vectors), bulk=bulk
    )
    return subscriber, calls


def test_es_subscriber_reuses_chroma_vectors_and_mirrors_the_index_shape(conn):
    ingest(conn, make_artwork("harvard_1"))
    subscriber, calls = make_es({"harvard_1": [0.1, 0.2]})

    run_once(conn, subscriber)

    action = calls[0][0]
    assert action["_index"] == "art_history_hybrid"
    assert action["_id"] == "harvard_1"
    source = action["_source"]
    assert source["embedding"] == [0.1, 0.2]
    assert source["source"] == "harvard"
    assert source["parent_id"] == "harvard_1"
    assert source["chunk_index"] == 0


def test_es_subscriber_waits_for_chroma_and_keeps_the_cursor(conn):
    ingest(conn, make_artwork("harvard_1"))
    subscriber, _ = make_es({})

    with pytest.raises(EmbeddingNotReadyError):
        run_once(conn, subscriber)

    assert get_cursor(conn, "elasticsearch") == 0


def test_es_delete_of_a_missing_document_is_not_an_error(conn):
    ingest(conn, make_artwork("harvard_1"), make_artwork("harvard_2"))
    ingest(conn, make_artwork("harvard_1"), prune=True)

    def bulk(es, actions, **kwargs):
        errors = [
            {"delete": {"_id": a["_id"], "status": 404}}
            for a in actions
            if a.get("_op_type") == "delete"
        ]
        return 0, errors

    subscriber = ElasticsearchSubscriber(
        es=object(),
        chroma_collection=FakeCollection({"harvard_1": [0.0], "harvard_2": [0.0]}),
        bulk=bulk,
    )

    run_once(conn, subscriber)

    assert lag(conn, "elasticsearch") == 0
