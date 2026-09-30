"""系統圖譜路（``graph``）的查詢組裝與分數篩選：純函式，不連資料庫。

與舊策略 ``graph_only`` 的差異（2026-10-01 decision-log）：不做模糊比對（``~``）、
多字詞以片語查詢、同一查詢一次比對所有關鍵詞，並以相對分數門檻濾掉弱命中。
"""

import re
from collections.abc import Iterable, Sequence
from typing import Any

DEFAULT_MIN_RELATIVE_SCORE = 0.3
LUCENE_SPECIAL = re.compile(r'([+\-!(){}\[\]^"~*?:\\/&|])')


def escape_lucene(term: str) -> str:
    """跳脫 Lucene 查詢語法的特殊字元。"""
    return LUCENE_SPECIAL.sub(r"\\\1", term)


def build_lucene_query(terms: Iterable[str]) -> str:
    """把關鍵詞組成一個 Lucene 查詢（預設 OR）：多字詞加引號成片語，單字原樣。

    Args:
        terms: 關鍵詞，例如 ``["The Night Watch", "Rembrandt"]``。

    Returns:
        例如 ``'"The Night Watch" Rembrandt'``；沒有有效關鍵詞時回傳空字串。
    """
    parts: list[str] = []
    seen: set[str] = set()
    for term in terms:
        cleaned = " ".join(term.split())
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        escaped = escape_lucene(cleaned)
        parts.append(f'"{escaped}"' if " " in cleaned else escaped)
    return " ".join(parts)


def apply_relative_cutoff(
    rows: Sequence[dict[str, Any]], min_relative: float = DEFAULT_MIN_RELATIVE_SCORE
) -> list[dict[str, Any]]:
    """只保留分數不低於最高分 ``min_relative`` 倍的命中（依分數由高到低）。

    全文索引的分數沒有絕對尺度，所以用相對門檻：第一名很強時，遠落後的弱命中
    （例如只碰到一個常見字）會被濾掉。

    Args:
        rows: 帶 ``score`` 鍵的命中。
        min_relative: 相對門檻，0 表示不過濾。

    Returns:
        篩選並排序後的命中。
    """
    ordered = sorted(rows, key=lambda row: row["score"], reverse=True)
    if not ordered or ordered[0]["score"] <= 0:
        return ordered
    floor = ordered[0]["score"] * min_relative
    return [row for row in ordered if row["score"] >= floor]
