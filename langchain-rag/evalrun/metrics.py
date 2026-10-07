"""文件層級檢索指標（規格 EVL-05：召回率以文件為單位，非 chunk）。"""

import math
from collections.abc import Iterable


def dedupe(ids: Iterable[str]) -> list[str]:
    """去除重複 id、保留第一次出現的名次（同一文件的多個 chunk 只算一次）。"""
    seen: set[str] = set()
    ordered = []
    for doc_id in ids:
        if doc_id and doc_id not in seen:
            seen.add(doc_id)
            ordered.append(doc_id)
    return ordered


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """前 k 名中命中的相關文件數 ÷ 相關文件總數。

    Raises:
        ValueError: 沒有相關文件（應拒答題不計召回率）。
    """
    if not relevant:
        raise ValueError("沒有相關文件，無法計算召回率")
    return len(set(ranked[:k]) & relevant) / len(relevant)


def ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """二元相關的 nDCG@k：命中名次越前面分數越高，理想排序為 1。

    Raises:
        ValueError: 沒有相關文件。
    """
    if not relevant:
        raise ValueError("沒有相關文件，無法計算 nDCG")
    dcg = sum(1 / math.log2(rank + 1) for rank, doc in enumerate(ranked[:k], 1) if doc in relevant)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(len(relevant), k) + 1))
    return dcg / ideal
