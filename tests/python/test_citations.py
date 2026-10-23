"""回應引用 citations[] 的單元測試（不需任何服務）。"""

from citations import build_citations
from ingest.ids import chunk_uuid, doc_uuid


def test_chunk_hit_maps_to_catalog_uuids():
    [citation] = build_citations(
        [
            {
                "content": "text",
                "metadata": {
                    "parent_id": "harvard_1",
                    "chunk_id": "harvard_1_chunk2",
                    "source": "harvard",
                    "title": "Water Lilies",
                },
                "score": 0.8,
                "source": "harvard",
            }
        ]
    )

    assert citation == {
        "index": 1,
        "doc_id": str(doc_uuid("harvard_1")),
        "chunk_id": str(chunk_uuid("harvard_1_chunk2")),
        "external_id": "harvard_1",
        "chunk_external_id": "harvard_1_chunk2",
        "source": "harvard",
        "title": "Water Lilies",
        "score": 0.8,
    }


def test_graph_artwork_has_doc_id_but_no_chunk():
    [citation] = build_citations(
        [{"metadata": {"id": "met_9", "title": "Man in a Turban", "source": "met_museum"}}]
    )

    assert citation["doc_id"] == str(doc_uuid("met_9"))
    assert citation["chunk_id"] is None
    assert citation["score"] is None


def test_source_without_reliable_id_is_not_fabricated():
    [citation] = build_citations(
        [{"metadata": {"name": "Rembrandt"}, "score": 2.4, "source": "Neo4j Knowledge Graph"}]
    )

    assert (citation["doc_id"], citation["external_id"]) == (None, None)
    assert citation["title"] == "Rembrandt"
    assert citation["source"] == "Neo4j Knowledge Graph"


def test_index_follows_source_order_and_empty_input():
    sources = [{"metadata": {"parent_id": pid}} for pid in ("a", "b", "c")]

    assert [c["index"] for c in build_citations(sources)] == [1, 2, 3]
    assert build_citations([]) == []
