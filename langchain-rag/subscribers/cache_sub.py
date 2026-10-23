"""快取失效訂閱器（規格 RET-12）：catalog 文件版本變動時，刪除用到該文件的 Redis 快取項。

設計：docs/designs/2026-10-13-redis-query-cache.md
document 事件的 entity_id 即 doc_id；chunk 事件以 payload 的 doc_id 對應。刪除本身冪等。
"""

from collections.abc import Sequence

from subscribers.base import Event


class CacheInvalidationSubscriber:
    """依 outbox 事件呼叫 ``RedisQueryCache.invalidate_docs``。"""

    name = "redis"  # catalog.sync_cursor 的 CHECK 已預留此名稱（04 schema）
    entity_types = ("document", "chunk")

    def __init__(self, cache):
        self.cache = cache
        self.removed = 0

    def handle(self, events: Sequence[Event]) -> None:
        doc_ids = set()
        for e in events:
            if e.entity_type == "document":
                doc_ids.add(str(e.entity_id))
            elif e.payload.get("doc_id"):
                doc_ids.add(str(e.payload["doc_id"]))
        self.removed += self.cache.invalidate_docs(doc_ids)
