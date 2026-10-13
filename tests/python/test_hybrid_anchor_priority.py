"""三路融合的限制條件優先：graph 錨點 T2（畫家 × 館藏）命中時只採 graph 結果。

設計：docs/designs/2026-10-11-graph-retrieval-anchor.md §五觀察 1；2026-10-13 模擬 S4。
"""

import asyncio

import pytest


@pytest.fixture
def rag(monkeypatch):
    pytest.importorskip("chromadb")  # 主程式依賴
    monkeypatch.setenv("NEO4J_PASSWORD", "unused")
    import unified_rag_manager_v2  # noqa: PLC0415

    return unified_rag_manager_v2


class FakeRoute:
    def __init__(self, docs):
        self.docs = docs

    async def retrieve(self, query, max_results=5, fallback=True):
        return self.docs


def doc(i, match=None):
    md = {"id": i, "external_id": i}
    if match:
        md["graph_match"] = match
    return {"content": i, "metadata": md, "score": 1.0, "source": "x"}


def run(rag, graph_docs):
    routes = {
        "vector": FakeRoute([doc("v1"), doc("v2")]),
        "fulltext": FakeRoute([doc("f1"), doc("f2")]),
        "graph": FakeRoute(graph_docs),
    }
    hybrid = rag.SystemHybridRAG(routes)
    return [d["metadata"]["id"] for d in asyncio.run(hybrid.retrieve("q", 5))]


def test_constraint_template_returns_only_graph(rag):
    assert run(rag, [doc("g1", "anchor:T2"), doc("g2", "anchor:T2")]) == ["g1", "g2"]


def test_artist_only_template_is_still_fused(rag):
    ids = run(rag, [doc("g1", "anchor:T1"), doc("g2", "anchor:T1")])
    assert {"v1", "f1", "g1"} <= set(ids)


def test_no_graph_result_is_fused(rag):
    assert {"v1", "f1"} <= set(run(rag, []))
