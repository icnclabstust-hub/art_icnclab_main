"""Elasticsearch 訂閱器：沿用既有 index 結構，向量直接取自 ChromaDB，不重新計算 embedding。"""

from collections.abc import Sequence

from subscribers.base import Event
from subscribers.chroma_sub import _final_state

SUBSCRIBER_NAME = "elasticsearch"
ES_INDEX = "art_history_hybrid"


class EmbeddingNotReadyError(RuntimeError):
    """ChromaDB 尚未套用這些 chunk，向量取不到；需等 ChromaDB 訂閱器先追上再重試。"""


class ElasticsearchSubscriber:
    """把 catalog 的 chunk 事件寫進 Elasticsearch。

    Args:
        es: ``Elasticsearch`` 用戶端。
        chroma_collection: 用來取既有向量的 chromadb collection。
        bulk: ``elasticsearch.helpers.bulk`` 相容函式（測試可注入）。
        index: 目標 index 名稱。
    """

    name = SUBSCRIBER_NAME
    entity_types = ("chunk",)

    def __init__(self, es, chroma_collection, bulk, index: str = ES_INDEX) -> None:
        self.es = es
        self.chroma = chroma_collection
        self.bulk = bulk
        self.index = index

    def _embeddings(self, ids: list[str]) -> dict[str, list[float]]:
        got = self.chroma.get(ids=ids, include=["embeddings"])
        found = {i: list(v) for i, v in zip(got["ids"], got["embeddings"], strict=True)}
        missing = [i for i in ids if i not in found]
        if missing:
            raise EmbeddingNotReadyError(
                f"ChromaDB 尚無 {len(missing)} 個 chunk 的向量（例如 {missing[0]}），"
                "請先讓 chromadb 訂閱器追上"
            )
        return found

    def handle(self, events: Sequence[Event]) -> None:
        """套用一批事件；同一批內以最後一個事件為準。"""
        latest = _final_state(events)
        upserts = [e for e in latest.values() if e.op == "upsert"]
        vectors = self._embeddings([e.payload["external_id"] for e in upserts]) if upserts else {}

        actions = []
        for event in upserts:
            payload = event.payload
            meta = payload["metadata"]
            actions.append(
                {
                    "_index": self.index,
                    "_id": payload["external_id"],
                    "_source": {
                        "content": payload["text"],
                        "embedding": vectors[payload["external_id"]],
                        "source": meta.get("source", ""),
                        "parent_id": meta.get("parent_id", ""),
                        "title": meta.get("title", ""),
                        "artist": meta.get("artist", ""),
                        "date": str(meta.get("date", "")),
                        "chunk_index": meta.get("chunk_index", 0),
                    },
                }
            )
        for ext, event in latest.items():
            if event.op == "soft_delete":
                actions.append({"_op_type": "delete", "_index": self.index, "_id": ext})
        if not actions:
            return
        _, errors = self.bulk(self.es, actions, raise_on_error=False, stats_only=False)
        real_errors = [
            e
            for e in errors
            if not (isinstance(e, dict) and "delete" in e and e["delete"].get("status") == 404)
        ]
        if real_errors:
            raise RuntimeError(
                f"Elasticsearch 寫入失敗 {len(real_errors)} 筆，例如 {real_errors[0]}"
            )
