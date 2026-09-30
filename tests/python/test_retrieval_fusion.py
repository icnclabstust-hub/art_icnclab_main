"""系統級 RRF 融合的單元測試（不需任何服務）。"""

import pytest
from retrieval_fusion import document_key, rrf_fuse


def hit(parent_id=None, content="text", source="harvard", **meta):
    metadata = dict(meta)
    if parent_id:
        metadata["parent_id"] = parent_id
    return {"content": content, "metadata": metadata, "score": 0.9, "source": source}


def keys(fused):
    return [d["metadata"]["fusion"]["doc_key"] for d in fused]


def test_document_key_prefers_parent_id_then_chunk_id_then_graph_ids():
    assert document_key(hit("harvard_1")) == "harvard_1"
    assert document_key(hit(chunk_id="met_9_chunk3")) == "met_9"
    assert document_key(hit(chunk_id="met_9")) == "met_9"
    assert document_key({"metadata": {"id": "va_5", "title": "Vase"}}) == "va_5"
    assert document_key({"metadata": {"name": "Rembrandt"}}) == "artist:Rembrandt"


def test_score_is_sum_of_reciprocal_ranks():
    fused = rrf_fuse(
        {"vector": [hit("a"), hit("b")], "fulltext": [hit("b"), hit("c")]}, k=60, top_n=3
    )

    assert keys(fused) == ["b", "a", "c"]
    assert fused[0]["score"] == pytest.approx(1 / 62 + 1 / 61)
    assert fused[0]["metadata"]["fusion"]["ranks"] == {"vector": 2, "fulltext": 1}
    assert fused[1]["score"] == pytest.approx(1 / 61)


def test_graph_artwork_aligns_with_chunk_parent_id():
    graph_node = {"metadata": {"id": "harvard_7", "title": "Night Watch"}, "content": "graph"}
    fused = rrf_fuse({"vector": [hit("harvard_7")], "graph": [graph_node]}, top_n=5)

    assert keys(fused) == ["harvard_7"]
    assert fused[0]["metadata"]["fusion"]["ranks"] == {"vector": 1, "graph": 1}


def test_multiple_chunks_of_one_document_count_once_per_route():
    fused = rrf_fuse(
        {"vector": [hit("a", content="c0"), hit("a", content="c1"), hit("b")]}, k=60, top_n=5
    )

    assert keys(fused) == ["a", "b"]
    assert fused[0]["content"] == "c0"
    assert fused[1]["score"] == pytest.approx(1 / 62)


def test_representative_comes_from_best_ranked_route():
    fused = rrf_fuse(
        {"vector": [hit("x"), hit("a", content="from vector")], "graph": [hit("a", content="g")]},
        top_n=5,
    )

    assert next(d for d in fused if d["metadata"]["fusion"]["doc_key"] == "a")["content"] == "g"


def test_top_n_and_empty_routes():
    fused = rrf_fuse({"vector": [hit(str(i)) for i in range(10)], "graph": []}, top_n=3)

    assert keys(fused) == ["0", "1", "2"]
    assert rrf_fuse({}, top_n=5) == []


def test_ties_are_broken_deterministically():
    fused = rrf_fuse({"vector": [hit("b")], "fulltext": [hit("a")]}, top_n=2)

    assert keys(fused) == ["a", "b"]


def test_input_documents_are_not_mutated():
    original = hit("a")
    rrf_fuse({"vector": [original]}, top_n=1)

    assert "fusion" not in original["metadata"]
    assert original["score"] == 0.9
