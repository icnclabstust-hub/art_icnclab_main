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

    def single(self):
        return {"c": 3}


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
        self.calls.append((query.strip().split("\n")[0][:40], params, query))
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
    # 「姓, 名」合併為一人（E29：舊規則以逗號切成兩位畫家）
    assert [r["artist_name"] for r in artist_call[1]["rows"]] == ["Claude Oscar Monet"]


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
    assert [r["artist_name"] for r in artist_rows] == ["Jane Doe"]  # 與其他來源一致的名在前寫法


def test_neo4j_soft_delete_marks_instead_of_deleting():
    subscriber, calls = make_subscriber()

    subscriber.handle([document_event("harvard_2", op="soft_delete")])

    assert calls[0][1]["ids"] == ["harvard_2"]
    assert "DELETE" not in calls[0][2].replace("is_deleted", "")


def test_neo4j_reactivates_returning_documents():
    subscriber, calls = make_subscriber()

    subscriber.handle([document_event("harvard_3")])

    reactivate = next(c for c in calls if "is_deleted = false" in c[2])
    assert reactivate[1]["ids"] == ["harvard_3"]
    assert "REMOVE a.deleted_at, a.valid_to" in reactivate[2]


def test_neo4j_upsert_stamps_entity_and_relationship_lifecycle_fields():
    subscriber, calls = make_subscriber()

    subscriber.handle([document_event("harvard_4", artist="Monet, Claude")])

    entity = next(c for c in calls if "a.valid_from" in c[2])
    assert entity[1]["ids"] == ["harvard_4"]
    assert "REMOVE a.valid_to" in entity[2]
    add_rel = next(c for c in calls if "SET r.valid_from" in c[2])
    assert add_rel[1]["rows"] == [{"artwork_id": "harvard_4", "names": ["Claude Monet"]}]
    assert "REMOVE r.valid_to" in add_rel[2]


def test_neo4j_expires_created_relationships_of_artists_no_longer_listed():
    subscriber, calls = make_subscriber()

    subscriber.handle([document_event("harvard_5", artist="Renoir")])

    expire = next(c for c in calls if "SET r.valid_to = datetime()" in c[2])
    assert expire[1]["rows"] == [{"artwork_id": "harvard_5", "names": ["Renoir"]}]
    assert "NOT x.name IN row.names" in expire[2]
    assert "r.valid_to IS NULL" in expire[2]
    assert "DELETE" not in expire[2]


def test_neo4j_expiry_is_skipped_by_the_query_when_the_new_artist_list_is_empty():
    subscriber, calls = make_subscriber()

    subscriber.handle([document_event("harvard_6", artist="")])

    expire = next(c for c in calls if "SET r.valid_to = datetime()" in c[2])
    assert expire[1]["rows"][0]["names"] == []
    assert "size(row.names) > 0" in expire[2]


def test_neo4j_soft_delete_also_stamps_valid_to():
    subscriber, calls = make_subscriber()

    subscriber.handle([document_event("harvard_2", op="soft_delete")])

    assert "a.valid_to = datetime()" in calls[0][2]
    assert "a.is_deleted = true" in calls[0][2]


def test_artist_sources_are_refreshed_last_for_every_touched_artwork():
    subscriber, calls = make_subscriber()

    subscriber.handle([document_event("harvard_1"), document_event("harvard_2", op="soft_delete")])

    refresh = calls[-1]
    assert sorted(refresh[1]["ids"]) == ["harvard_1", "harvard_2"]
    assert "x.sources = sources" in refresh[2]
    # 只算現存作品：未到期的關係、未軟刪除的作品
    assert "r.valid_to IS NULL" in refresh[2]
    assert "is_deleted" in refresh[2]


def test_artist_source_is_only_a_fallback_never_overwritten():
    from subscribers.neo4j_sub import _REFRESH_ARTIST_SOURCES_QUERY  # noqa: PLC0415

    assert "x.source = coalesce(x.source, head(sources))" in _REFRESH_ARTIST_SOURCES_QUERY


def test_refresh_all_artist_sources_returns_the_processed_count():
    from subscribers.neo4j_sub import refresh_artist_sources  # noqa: PLC0415

    assert refresh_artist_sources(FakeSession([])) == 3


def test_purge_previews_without_deleting_and_applies_with_the_retention_window():
    from subscribers.neo4j_sub import purge  # noqa: PLC0415

    preview_calls, apply_calls = [], []

    preview = purge(FakeSession(preview_calls), days=30, apply=False)
    applied = purge(FakeSession(apply_calls), days=30, apply=True)

    assert (
        preview
        == applied
        == {
            "expired_relationships": 3,
            "deleted_artworks": 3,
            "orphan_artists": 3,
        }
    )
    assert not any("DELETE" in c[2] for c in preview_calls)
    assert all("DELETE" in c[2] for c in apply_calls)
    assert all(c[1]["days"] == 30 for c in apply_calls)
    assert any("DETACH DELETE a" in c[2] for c in apply_calls)
    assert all("duration({days: $days})" in c[2] for c in apply_calls[:2])


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


def test_duplicate_ids_keep_the_last_occurrence_across_files(tmp_path):
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    first.write_text(json.dumps([{"id": "x", "v": 1}, {"id": "y", "v": 1}]), encoding="utf-8")
    second.write_text(json.dumps([{"id": "x", "v": 2}]), encoding="utf-8")
    adapter = sources.SourceAdapter(
        name="demo",
        normalize=lambda item, _position: {"id": item["id"], "v": item["v"]},
        document_text=lambda artwork: artwork["id"],
        resolve_files=list,
        load_items=lambda filename: json.loads(open(filename, encoding="utf-8").read()),
    )

    artworks = sources.load_artworks(adapter, [str(first), str(second)])

    assert artworks == [{"id": "y", "v": 1}, {"id": "x", "v": 2}]


def test_ensure_schema_creates_both_uniqueness_constraints_idempotently():
    from subscribers.neo4j_sub import ensure_schema  # noqa: PLC0415

    calls = []
    ensure_schema(FakeSession(calls))
    ensure_schema(FakeSession(calls))

    statements = [c[0] for c in calls]
    assert len(statements) == 4
    assert all(st.startswith("CREATE CONSTRAINT") for st in statements)


def test_schema_statements_are_safe_to_rerun_and_cover_the_merge_keys():
    from subscribers.neo4j_sub import SCHEMA_STATEMENTS  # noqa: PLC0415

    joined = " ".join(SCHEMA_STATEMENTS)
    assert joined.count("IF NOT EXISTS") == len(SCHEMA_STATEMENTS)
    assert "(a:Artwork) REQUIRE a.id IS UNIQUE" in joined
    assert "(a:Artist) REQUIRE a.name IS UNIQUE" in joined


def test_graph_context_hides_lifecycle_fields_and_the_stale_single_source(monkeypatch):
    pytest.importorskip("chromadb")
    # 該模組載入時要求密碼環境變數；這裡只測純格式化函式，不會連線
    monkeypatch.setenv("NEO4J_PASSWORD", "unused")
    monkeypatch.setenv("ES_PASSWORD", "unused")
    from unified_rag_manager_v2 import GraphOnlyRAG  # noqa: PLC0415

    artist = {
        "name": "Vincent van Gogh",
        "source": "met_museum",
        "sources": ["cleveland_museum", "europeana"],
        "valid_from": "2026-09-21T00:00:00Z",
        "updated_at": "2026-09-21T00:00:00Z",
    }
    artwork = {"title": "Vase", "source": "harvard", "date": "1900", "valid_from": "x"}

    artist_text = GraphOnlyRAG._format_graph_node(None, artist, [])  # noqa: SLF001
    artwork_text = GraphOnlyRAG._format_graph_node(None, artwork, [])  # noqa: SLF001

    assert "sources: ['cleveland_museum', 'europeana']" in artist_text
    assert "met_museum" not in artist_text
    assert "valid_from" not in artist_text and "updated_at" not in artist_text
    assert "source: harvard" in artwork_text and "date: 1900" in artwork_text
    assert "valid_from" not in artwork_text
