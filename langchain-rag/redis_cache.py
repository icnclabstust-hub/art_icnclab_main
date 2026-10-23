"""查詢快取遷至 Redis（規格 RET-11～13，決策 B10：一般鍵值快取，非語意近似）。

設計：docs/designs/2026-10-13-redis-query-cache.md
- 鍵：``rag:q:`` ＋ SHA-256（正規化問題｜策略鍵｜max_results），值為 JSON，``SETEX`` 帶 TTL
- 來源變動失效（RET-12）：寫入時把用到的 doc_id 記入反向索引 ``rag:doc:<doc_id>``，
  由 ``subscribers/cache_sub.py`` 依 outbox 事件刪除受影響項目
- 拒答不快取（RET-13）：由呼叫端以 :func:`is_refusal` 判斷後略過寫入
- 介面與 ``QueryCache`` 相同（get／set／clear／get_stats），呼叫端不需改
- 讀寫失敗（Redis 中途斷線、密碼變更）視為未命中並記警告，不讓查詢失敗；
  只有 ``invalidate_docs`` 照常拋出，讓失效訂閱器的游標不前移、下次重試
"""

import hashlib
import json
import logging
import re
import unicodedata
from collections.abc import Iterable
from typing import Any

logger = logging.getLogger(__name__)

PREFIX = "rag:"
KEY_PREFIX = f"{PREFIX}q:"
DOC_PREFIX = f"{PREFIX}doc:"
STATS_KEY = f"{PREFIX}stats"

# 拒答句型（提示規則要求查無時說「檢索結果中沒有找到」；pipe 查無來源時加註「知識庫中尚無」）。
# 寧可多判：誤判正常回答只少一筆快取（變慢），漏判會把錯誤拒答快取一小時（答錯）。
# 2026-10-13 模擬 S6 漏判「並未提供…也無法在…中找到」，補上否定＋查找動詞的組合與英文句型。
_REFUSAL = re.compile(
    r"沒有找到|找不到|未能找到|無法(?:回答|提供|確認|找到|在)|不能確認"
    r"|並未(?:提供|提及|包含|找到|收錄)|沒有(?:相關的?)?(?:資訊|資料|信息|記錄)"
    r"|知識庫中尚無|資料庫中沒有"
    r"|(?i:no (?:relevant )?(?:information|records?|results?)|not (?:found|mentioned|provided)"
    r"|cannot (?:find|answer|confirm)|could not find|unable to (?:find|answer))"
)
_TRAILING_PUNCT = re.compile(r"[\s？?。.!！~～…]+$")


def normalize_query(query: str) -> str:
    """快取鍵用的問題正規化：NFKC、去頭尾空白、空白合一、英文小寫、去句末標點。"""
    text = unicodedata.normalize("NFKC", query).strip()
    text = re.sub(r"\s+", " ", text).lower()
    return _TRAILING_PUNCT.sub("", text)


REFUSAL_HEAD_CHARS = 150  # 拒答說法出現在開頭才算拒答
REFUSAL_SHORT_CHARS = 300  # 或整個回答很短


def is_refusal(answer: Any) -> bool:
    """答案是否為拒答（RET-13：拒答不進快取）。

    「查不到」說法出現在開頭 150 字內，或回答短於 300 字，才算拒答；長回答中段的
    「資料並未提及某細節」屬部分作答，照常快取。以 8080 評估 1,200 個回答校準（2026-10-13）：
    模擬中的拒答全數抓到，理論題被判拒答由 357／600 降為 213／600。
    """
    if not isinstance(answer, str):
        return False
    m = _REFUSAL.search(answer)
    return bool(m) and (m.start() < REFUSAL_HEAD_CHARS or len(answer) < REFUSAL_SHORT_CHARS)


class RedisQueryCache:
    """以 Redis 保存的查詢快取；介面同 ``QueryCache``。"""

    def __init__(self, client, ttl_seconds: int = 3600):
        self.client = client
        self.ttl = ttl_seconds

    def _make_key(self, query: str, strategy: str, max_results: int) -> str:
        content = f"{normalize_query(query)}|{strategy}|{max_results}"
        return KEY_PREFIX + hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get(self, query: str, strategy: str, max_results: int) -> Any | None:
        try:
            raw = self.client.get(self._make_key(query, strategy, max_results))
            self.client.hincrby(STATS_KEY, "hits" if raw is not None else "misses", 1)
        except Exception as e:  # 快取故障不影響查詢：當作未命中
            logger.warning(f"⚠️ Redis 快取讀取失敗，視為未命中: {e}")
            return None
        if raw is None:
            return None
        logger.info(f"💾 Redis 快取命中: {query[:30]}... | 策略: {strategy}")
        return json.loads(raw)

    def set(
        self,
        query: str,
        strategy: str,
        max_results: int,
        data: Any,
        doc_ids: Iterable[str] = (),
    ) -> None:
        key = self._make_key(query, strategy, max_results)
        try:
            pipe = self.client.pipeline()
            pipe.setex(key, self.ttl, json.dumps(data, ensure_ascii=False, default=str))
            for doc_id in {d for d in doc_ids if d}:
                index = DOC_PREFIX + str(doc_id)
                pipe.sadd(index, key)
                pipe.expire(index, self.ttl)
            pipe.execute()
        except Exception as e:  # 寫入失敗只少一筆快取
            logger.warning(f"⚠️ Redis 快取寫入失敗: {e}")

    def invalidate_docs(self, doc_ids: Iterable[str]) -> int:
        """刪除用到這些 doc_id 的快取項（RET-12）；回傳刪除的快取項數。"""
        removed = 0
        for doc_id in {str(d) for d in doc_ids if d}:
            index = DOC_PREFIX + doc_id
            keys = list(self.client.smembers(index))
            if keys:
                removed += self.client.delete(*keys)
            self.client.delete(index)
        if removed:
            logger.info(f"🗑️  來源變動，失效 {removed} 個快取項")
        return removed

    def clear(self) -> None:
        """只刪 ``rag:`` 前綴（Redis 可能與他人共用，不 FLUSHDB）。"""
        keys = list(self.client.scan_iter(match=f"{PREFIX}*", count=500))
        if keys:
            self.client.delete(*keys)
        logger.info(f"🗑️  清空 Redis 快取: {len(keys)} 個鍵")

    def get_stats(self) -> dict[str, Any]:
        stats = {k: int(v) for k, v in (self.client.hgetall(STATS_KEY) or {}).items()}
        hits, misses = stats.get("hits", 0), stats.get("misses", 0)
        total = hits + misses
        size = sum(1 for _ in self.client.scan_iter(match=f"{KEY_PREFIX}*", count=500))
        return {
            "backend": "redis",
            "size": size,
            "ttl_seconds": self.ttl,
            "hits": hits,
            "misses": misses,
            "total_requests": total,
            "hit_rate": f"{(hits / total * 100) if total else 0:.2f}%",
        }


def connect_redis(url: str, password: str | None = None):
    """建立 Redis 連線並 ping；失敗時拋出例外由呼叫端決定是否退回。

    Args:
        url: 例 ``redis://localhost:6379/0``（不含密碼）。
        password: Redis ``requirepass``；空字串或 None 表示不驗證。
    """
    import redis  # noqa: PLC0415 -- CACHE_BACKEND=memory 時不需要

    client = redis.Redis.from_url(
        url, password=password or None, decode_responses=True, socket_timeout=2
    )
    client.ping()
    return client
