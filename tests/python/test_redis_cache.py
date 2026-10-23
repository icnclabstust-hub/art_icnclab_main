"""Redis 查詢快取（RET-11～13）的單元測試；以記憶體假 Redis 取代，不需要 Redis 服務。

設計：docs/designs/2026-10-13-redis-query-cache.md
"""

import fnmatch

import pytest
from redis_cache import RedisQueryCache, is_refusal, normalize_query
from subscribers.base import Event
from subscribers.cache_sub import CacheInvalidationSubscriber


class FakeRedis:
    """只實作快取用到的指令；TTL 只記錄不倒數。"""

    def __init__(self):
        self.kv, self.sets, self.hashes, self.ttl = {}, {}, {}, {}

    def get(self, key):
        return self.kv.get(key)

    def setex(self, key, ttl, value):
        self.kv[key], self.ttl[key] = value, ttl

    def sadd(self, key, member):
        self.sets.setdefault(key, set()).add(member)

    def smembers(self, key):
        return set(self.sets.get(key, set()))

    def expire(self, key, ttl):
        self.ttl[key] = ttl

    def delete(self, *keys):
        n = 0
        for k in keys:
            n += int(self.kv.pop(k, None) is not None) + int(self.sets.pop(k, None) is not None)
            self.hashes.pop(k, None)
        return n

    def hincrby(self, key, field, amount):
        h = self.hashes.setdefault(key, {})
        h[field] = int(h.get(field, 0)) + amount

    def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    def scan_iter(self, match="*", count=None):
        keys = list(self.kv) + list(self.sets) + list(self.hashes)
        return iter([k for k in keys if fnmatch.fnmatch(k, match)])

    def pipeline(self):
        return FakePipeline(self)


class FakePipeline:
    def __init__(self, r):
        self.r, self.ops = r, []

    def __getattr__(self, name):
        return lambda *a: self.ops.append((name, a))

    def execute(self):
        for name, a in self.ops:
            getattr(self.r, name)(*a)


@pytest.fixture
def cache():
    return RedisQueryCache(FakeRedis(), ttl_seconds=60)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("林布蘭的夜巡是哪一年完成的？", "林布蘭的夜巡是哪一年完成的"),
        ("  Who painted  The Night Watch? ", "who painted the night watch"),
        ("維梅爾的作品。", "維梅爾的作品"),
        ("ＡＢＣ　作品", "abc 作品"),  # 全形英數與全形空白（NFKC）
    ],
)
def test_normalize_query(a, b):
    assert normalize_query(a) == normalize_query(b)


def test_normalization_does_not_merge_different_questions():
    assert normalize_query("林布蘭的夜巡哪年畫的") != normalize_query("林布蘭的夜巡用什麼媒材")


def test_hit_after_set_with_normalized_variant(cache):
    cache.set("林布蘭的夜巡是哪一年完成的？", "ans:x", 5, "1642 年", doc_ids=["d1"])
    assert cache.get("林布蘭的夜巡是哪一年完成的", "ans:x", 5) == "1642 年"
    assert cache.get("林布蘭的夜巡是哪一年完成的", "ans:y", 5) is None  # 參數不同不共用
    stats = cache.get_stats()
    assert (stats["hits"], stats["misses"], stats["size"]) == (1, 1, 1)


def test_sources_roundtrip_as_json(cache):
    sources = [{"content": "x", "metadata": {"title": "夜巡", "id": "met_1"}, "score": 0.9}]
    cache.set("q", "hybrid", 5, sources, doc_ids=["d1"])
    assert cache.get("q", "hybrid", 5) == sources


def test_invalidate_docs_removes_only_dependent_entries(cache):
    cache.set("q1", "s", 5, "a1", doc_ids=["d1", "d2"])
    cache.set("q2", "s", 5, "a2", doc_ids=["d3"])
    assert cache.invalidate_docs(["d2"]) == 1
    assert cache.get("q1", "s", 5) is None
    assert cache.get("q2", "s", 5) == "a2"
    assert cache.invalidate_docs(["d2"]) == 0  # 冪等


def test_clear_only_touches_rag_prefix(cache):
    cache.client.setex("other:key", 60, "keep")
    cache.set("q", "s", 5, "a", doc_ids=["d1"])
    cache.clear()
    assert cache.client.get("other:key") == "keep"
    assert cache.get("q", "s", 5) is None


@pytest.mark.parametrize(
    ("answer", "refusal"),
    [
        ("檢索結果中沒有找到委拉斯奎茲在哈佛的作品。", True),
        ("⚠️ 知識庫中尚無相關資料，回答僅來自模型本身知識。", True),
        ("《夜巡》完成於 1642 年，油彩畫布。", False),
        # 2026-10-13 模擬 S6 漏判的實際回答（被快取一小時）
        ("對不起，我們的檢索結果中並未提供關於博羅米尼的相關信息，也無法在 Metropolitan Museum "
         "of Art 中找到他的油畫作品。", True),
        ("根據參考資料，我們不能確認博羅米尼在大都會藝術博物館有哪些油畫作品。", True),
        ("The retrieved documents do not contain this; I could not find any record.", True),
        ("Claude Lorrain's Pastoral Landscape (1638) is held by the Met.", False),
        # 長回答中段的「並未提及某細節」是部分作答，照常快取
        ("disegno 在 16 世紀指構思與素描的統一。" * 12 + "其中原文頁碼資料並未提及。", False),
        (["not", "a", "string"], False),
    ],
)
def test_is_refusal(answer, refusal):
    assert is_refusal(answer) is refusal


def test_invalidation_subscriber_maps_document_and_chunk_events(cache):
    cache.set("q1", "s", 5, "a1", doc_ids=["doc-a"])
    cache.set("q2", "s", 5, "a2", doc_ids=["doc-b"])
    cache.set("q3", "s", 5, "a3", doc_ids=["doc-c"])
    sub = CacheInvalidationSubscriber(cache)
    sub.handle(
        [
            Event(1, "document", "doc-a", "upsert", {}),
            Event(2, "chunk", "chunk-1", "upsert", {"doc_id": "doc-b"}),
        ]
    )
    assert sub.removed == 2
    assert cache.get("q3", "s", 5) == "a3"


class BrokenRedis(FakeRedis):
    """模擬 Redis 中途斷線或密碼錯誤：所有指令都失敗。"""

    def _fail(self, *a, **k):
        raise ConnectionError("redis down")

    get = setex = sadd = expire = hincrby = smembers = delete = _fail

    def pipeline(self):
        return FakePipeline(self)


def test_redis_failure_is_a_miss_not_an_error():
    cache = RedisQueryCache(BrokenRedis(), ttl_seconds=60)
    assert cache.get("q", "s", 5) is None  # 不拋出
    cache.set("q", "s", 5, "a", doc_ids=["d1"])  # 不拋出


def test_invalidation_failure_propagates_so_cursor_does_not_advance():
    cache = RedisQueryCache(BrokenRedis(), ttl_seconds=60)
    with pytest.raises(ConnectionError):
        cache.invalidate_docs(["d1"])
