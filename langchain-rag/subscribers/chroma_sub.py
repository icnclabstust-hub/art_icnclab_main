"""ChromaDB 訂閱器：把 chunk 事件套用到 collection，id 與 metadata 沿用既有規則。"""

from collections.abc import Sequence

from subscribers.base import Event

SUBSCRIBER_NAME = "chromadb"


def _final_state(events: Sequence[Event]) -> dict[str, Event]:
    """同一 chunk 在同一批出現多次時，只保留最後一個事件（後者覆蓋前者）。"""
    latest: dict[str, Event] = {}
    for event in events:
        latest[event.payload["external_id"]] = event
    return latest


class ChromaSubscriber:
    """把 catalog 的 chunk 事件寫進 ChromaDB。

    Args:
        collection: 已取得的 chromadb collection（需已掛上 embedding function）。
    """

    name = SUBSCRIBER_NAME
    entity_types = ("chunk",)

    def __init__(self, collection) -> None:
        self.collection = collection

    def handle(self, events: Sequence[Event]) -> None:
        """套用一批事件：upsert 一次送出，刪除一次送出。"""
        latest = _final_state(events)
        upserts = [e for e in latest.values() if e.op == "upsert"]
        deletes = [ext for ext, e in latest.items() if e.op == "soft_delete"]
        if upserts:
            self.collection.upsert(
                ids=[e.payload["external_id"] for e in upserts],
                documents=[e.payload["text"] for e in upserts],
                metadatas=[e.payload["metadata"] for e in upserts],
            )
        if deletes:
            self.collection.delete(ids=deletes)
