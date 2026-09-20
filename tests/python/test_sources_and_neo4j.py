"""Europeana 來源介面卡與 Neo4j 訂閱器的測試。"""

import json
import os
import time

import pytest
from conftest import make_artwork
from ingest import sources
from ingest.pipeline import ingest_artworks
from subscribers.base import Event, get_cursor, lag, run_once
from subscribers.neo4j_sub import Neo4jSubscriber, Queries

FAKE_QUERIES = Queries(artwork="ARTWORK_Q", artist="ARTIST_Q")


class FakeResult:
    def consume(self):
        return None


class FakeSession:
    def __init__(self, calls, fail=False):
        self.calls = calls
        self.fail = fail

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, query, **params):
        if self.fail:
            raise ConnectionError("neo4j down")
        self.calls.append((query.strip().split("\n")[0][:40], params))
        return FakeResult()


def make_subscriber(fail=False):
    calls = []
    return Neo4jSubscriber(lambda: FakeSession(calls, fail), FAKE_QUERIES), calls


def document_event(external_id, op="upsert", source="harvard", **artwork_overrides):
    artwork = make_artwork(external_id, **artwork_overrides)
    payload = {"external_id": external_id, "source": source, "artwork": artwork}
    return Event(1, "document", "uuid", op, payload)


def test_europeana_normalization_matches_the_legacy_sync_rules():
    item = {
        "europeanaId": "/123/abc",
        "title": "Vase",
        "creator": ["Doe, Jane", " Roe "],
        "date": {"def": "1900/1907"},
        "description": "d" * 1500,
        "provider": "Museum X",
        "country": "France",
        "europeanaUrl": "https://europeana.eu/x",
    }

    artwork = sources.normalize_europeana(item)

    assert artwork["id"] == "europeana__123_abc"
    assert artwork["artist"] == "Doe, Jane,  Roe "
    assert artwork["creators"] == ["Doe, Jane", "Roe"]
    assert artwork["date"] == "1900/1907"
    assert len(artwork["description"]) == 1000


def test_europeana_missing_fields_fall_back_like_the_legacy_script():
    artwork = sources.normalize_europeana({}, position=7)

    assert artwork["id"] == "europeana_euro_unknown_7"
    assert artwork["title"] == "Untitled"
    assert artwork["artist"] == ""
    assert artwork["creators"] == []


def test_europeana_document_text_layout():
    artwork = sources.normalize_europeana(
        {
            "europeanaId": "1",
            "title": "Vase",
            "creator": ["Jane"],
            "date": "1900",
            "country": "France",
            "provider": "Museum X",
            "description": "Blue.",
        }
    )

    assert sources.europeana_document_text(artwork).split("\n") == [
        "Title: Vase",
        "Creator: Jane",
        "Date: 1900",
        "Country: France",
        "Provider: Museum X",
        "Description: Blue.",
    ]


def test_europeana_adapter_reads_the_wrapped_payload_and_picks_the_latest_file(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DATA_RAW_DIR", str(tmp_path))
    folder = tmp_path / "europeana"
    folder.mkdir()
    padding = "x" * 1200
    (folder / "europeana_crawled_old.json").write_text(
        json.dumps({"data": [{"europeanaId": "old", "title": padding}]}), encoding="utf-8"
    )
    newer = folder / "europeana_crawled_new.json"
    newer.write_text(
        json.dumps({"data": [{"europeanaId": "new", "title": padding}]}), encoding="utf-8"
    )
    os.utime(newer, (time.time() + 60, time.time() + 60))

    adapter = sources.get_adapter("europeana")
    artworks = sources.load_artworks(adapter, [])

    assert [a["id"] for a in artworks] == ["europeana_new"]


def test_missing_source_files_raise_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_RAW_DIR", str(tmp_path))

    with pytest.raises(FileNotFoundError):
        sources.load_artworks(sources.get_adapter("europeana"), [])


def test_neo4j_upsert_writes_artworks_and_split_artists():
    subscriber, calls = make_subscriber()

    subscriber.handle([document_event("harvard_1", artist="Monet, Claude Oscar")])

    artwork_call = next(c for c in calls if c[0].startswith("ARTWORK_Q"))
    assert artwork_call[1]["rows"][0]["id"] == "harvard_1"
    assert artwork_call[1]["rows"][0]["source"] == "harvard"
    artist_call = next(c for c in calls if c[0].startswith("ARTIST_Q"))
    assert [r["artist_name"] for r in artist_call[1]["rows"]] == ["Monet", "Claude Oscar"]


def test_neo4j_europeana_uses_the_creators_list_and_its_own_queries():
    subscriber, calls = make_subscriber()
    artwork = sources.normalize_europeana(
        {"europeanaId": "1", "title": "Vase", "creator": ["Doe, Jane"], "provider": "X"}
    )
    event = Event(
        1,
        "document",
        "u",
        "upsert",
        {"external_id": artwork["id"], "source": "europeana", "artwork": artwork},
    )

    subscriber.handle([event])

    queries = [c[0] for c in calls]
    assert not any(q.startswith(("ARTWORK_Q", "ARTIST_Q")) for q in queries)
    artist_rows = [r for c in calls for r in c[1].get("rows", []) if "artist_name" in r]
    assert [r["artist_name"] for r in artist_rows] == ["Doe, Jane"]


def test_neo4j_soft_delete_marks_instead_of_deleting():
    subscriber, calls = make_subscriber()

    subscriber.handle([document_event("harvard_2", op="soft_delete")])

    assert len(calls) == 1
    assert calls[0][1]["ids"] == ["harvard_2"]


def test_neo4j_reactivates_returning_documents():
    subscriber, calls = make_subscriber()

    subscriber.handle([document_event("harvard_3")])

    reactivate = calls[-1]
    assert reactivate[1]["ids"] == ["harvard_3"]


def test_neo4j_failure_propagates():
    subscriber, _ = make_subscriber(fail=True)

    with pytest.raises(ConnectionError):
        subscriber.handle([document_event("harvard_1")])


def test_neo4j_subscriber_end_to_end_with_the_cursor_loop(conn):
    ingest_artworks(
        conn,
        "harvard",
        [make_artwork("harvard_1"), make_artwork("harvard_2")],
        lambda a: a["title"],
    )
    subscriber, calls = make_subscriber()

    handled = run_once(conn, subscriber)

    assert handled == 2
    rows = [r["id"] for c in calls if c[0].startswith("ARTWORK_Q") for r in c[1]["rows"]]
    assert sorted(rows) == ["harvard_1", "harvard_2"]
    assert lag(conn, "neo4j") == 0
    assert get_cursor(conn, "neo4j") > 0


def test_neo4j_queries_come_from_the_legacy_import_script():
    pytest.importorskip("chromadb")
    from ingest import legacy  # noqa: PLC0415

    module = legacy.load_legacy_module()
    queries = Queries.from_legacy()

    assert queries.artwork == module._ARTWORK_UNWIND_QUERY  # noqa: SLF001
    assert queries.artist == module._ARTIST_UNWIND_QUERY  # noqa: SLF001
