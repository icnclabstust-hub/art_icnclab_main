"""既有向量補上嵌入模型標註（規格 DAT-30），並統計各庫的標註組合（DAT-31）。

補標前以抽樣重算確認：隨機抽 N 個 chunk 用目前模型重新計算向量，與庫存向量的 cosine
皆 ≥ 0.9999 才視為同一模型版本而補標；否則中止（代表庫存向量來自別的版本，應全量重建，
DAT-32），不能只改標籤。
"""

import math
import random
from collections import Counter
from collections.abc import Callable, Mapping, Sequence

from embedding_labels import EMBEDDING_LABEL_KEYS, UNLABELED, label_combinations

PAGE_SIZE = 500
MIN_COSINE = 0.9999
MISSING_LABEL_QUERY = {"bool": {"must_not": {"exists": {"field": "embedding_version"}}}}
LABEL_MAPPING = {key: {"type": "keyword"} for key in EMBEDDING_LABEL_KEYS}
UPDATE_TIMEOUT_SECONDS = 900


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def verify_sample(
    collection, embed: Callable[[list[str]], list[list[float]]], n: int, seed: int = 0
) -> float:
    """抽樣重算並回傳最小 cosine；庫是空的時回傳 1.0。"""
    total = collection.count()
    if not total:
        return 1.0
    offsets = random.Random(seed).sample(range(total), min(n, total))  # noqa: S311 -- 抽樣非加密用途
    docs, stored = [], []
    for offset in offsets:
        got = collection.get(limit=1, offset=offset, include=["documents", "embeddings"])
        docs.append(got["documents"][0])
        stored.append(list(got["embeddings"][0]))
    fresh = embed(docs)
    return min(cosine(a, b) for a, b in zip(stored, fresh, strict=True))


def chroma_label_counts(collection) -> Counter:
    """ChromaDB collection 內各 (模型, 版本) 組合的向量數。"""
    counts: Counter = Counter()
    offset = 0
    while True:
        got = collection.get(limit=PAGE_SIZE, offset=offset, include=["metadatas"])
        if not got["ids"]:
            return counts
        counts += label_combinations(got["metadatas"])
        offset += PAGE_SIZE


def label_chroma(collection, labels: Mapping[str, str], apply: bool) -> int:
    """替缺標註的向量補上 ``labels``（只改 metadata，不動向量）；回傳需補／已補的數量。"""
    pending_ids, pending_metas = [], []
    offset = 0
    while True:
        got = collection.get(limit=PAGE_SIZE, offset=offset, include=["metadatas"])
        if not got["ids"]:
            break
        for chunk_id, meta in zip(got["ids"], got["metadatas"], strict=True):
            meta = meta or {}
            if not all(meta.get(k) for k in EMBEDDING_LABEL_KEYS):
                pending_ids.append(chunk_id)
                pending_metas.append({**meta, **labels})
        offset += PAGE_SIZE
    if apply:
        for start in range(0, len(pending_ids), PAGE_SIZE):
            collection.update(
                ids=pending_ids[start : start + PAGE_SIZE],
                metadatas=pending_metas[start : start + PAGE_SIZE],
            )
    return len(pending_ids)


def es_label_counts(es, index: str) -> Counter:
    """Elasticsearch index 內各 (模型, 版本) 組合的文件數（缺標註另計）。"""
    counts: Counter = Counter()
    if all(
        key in es.indices.get_mapping(index=index)[index]["mappings"].get("properties", {})
        for key in EMBEDDING_LABEL_KEYS
    ):
        result = es.search(
            index=index,
            size=0,
            aggs={
                "combo": {
                    "multi_terms": {
                        "terms": [{"field": k} for k in EMBEDDING_LABEL_KEYS],
                        "size": 50,
                    }
                }
            },
        )
        for bucket in result["aggregations"]["combo"]["buckets"]:
            counts[tuple(bucket["key"])] += bucket["doc_count"]
    missing = es.count(index=index, query=MISSING_LABEL_QUERY)["count"]
    if missing:
        counts[UNLABELED] += missing
    return counts


def label_es(es, index: str, labels: Mapping[str, str], apply: bool) -> int:
    """替缺標註的文件補上 ``labels``；回傳需補／已補的數量。"""
    missing = es.count(index=index, query=MISSING_LABEL_QUERY)["count"]
    if apply and missing:
        es.indices.put_mapping(index=index, properties=LABEL_MAPPING)
        # 每筆都要連同向量重寫，數千筆需數十秒；預設 10 秒逾時會讓用戶端先放棄（伺服器仍會做完）
        es.options(request_timeout=UPDATE_TIMEOUT_SECONDS).update_by_query(
            index=index,
            query=MISSING_LABEL_QUERY,
            script={
                "source": "ctx._source.embedding_model = params.m;"
                " ctx._source.embedding_version = params.v",
                "params": {"m": labels["embedding_model"], "v": labels["embedding_version"]},
            },
            conflicts="proceed",
            refresh=True,
        )
    return missing
