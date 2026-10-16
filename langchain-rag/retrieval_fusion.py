"""系統級 RRF 融合：把向量／全文／圖三路的排名結果合成一份（規格 RET-04～07）。

融合以「文件」為單位（與召回率量測粒度 EVL-05 一致）：同一份文件在同一路出現多個 chunk
時只算最前面的名次；跨路以文件 external id 對齊（Chroma／ES 的 ``parent_id``、Neo4j
Artwork 的 ``id`` 為同一套 id）。只做 RRF，不做重排（RET-05／06：先取得量測基準）。
"""

import re
from collections.abc import Mapping, Sequence
from typing import Any

DEFAULT_RRF_K = 60
CHUNK_SUFFIX = re.compile(r"_chunk\d+$")


def document_external_id(doc: Mapping[str, Any]) -> str | None:
    """檢索結果所屬文件的既有字串 id（catalog ``external_id``）；沒有可靠 id 時回傳 None。

    依序採用：``metadata.parent_id``、``metadata.chunk_id`` 去掉 ``_chunkN`` 後綴、
    圖譜 Artwork 的 ``metadata.id``。
    """
    meta = doc.get("metadata") or {}
    if meta.get("parent_id"):
        return str(meta["parent_id"])
    if meta.get("chunk_id"):
        return CHUNK_SUFFIX.sub("", str(meta["chunk_id"]))
    if meta.get("id"):
        return str(meta["id"])
    return None


def document_key(doc: Mapping[str, Any]) -> str:
    """回傳檢索結果所屬文件的 id，供跨路對齊。

    優先用 ``document_external_id``；圖譜 Artist 節點用 ``artist:<name>``；都沒有時以
    來源＋標題＋內容開頭組合（只為了不同文件不被誤併）。

    Args:
        doc: 單筆檢索結果（``content``／``metadata``／``score``／``source``）。

    Returns:
        文件 id 字串。
    """
    external_id = document_external_id(doc)
    if external_id:
        return external_id
    meta = doc.get("metadata") or {}
    if meta.get("name") and not meta.get("title"):
        return f"artist:{meta['name']}"
    content = str(doc.get("content", ""))[:80]
    return f"{meta.get('source', doc.get('source', ''))}|{meta.get('title', '')}|{content}"


def rrf_fuse(
    ranked_lists: Mapping[str, Sequence[Mapping[str, Any]]],
    k: int = DEFAULT_RRF_K,
    top_n: int = 5,
    chunks_per_doc: int = 1,
) -> list[dict[str, Any]]:
    """以 Reciprocal Rank Fusion 合併多路排名：``score(d) = Σ 1/(k + rank_i(d))``。

    Args:
        ranked_lists: 路由名稱 → 該路依相關度排序的結果。
        k: RRF 常數（RET-04 預設 60）。
        top_n: 融合後保留的文件數（RET-07 預設 5）。
        chunks_per_doc: 每份入選文件最多附幾個段落（預設 1＝舊行為）。長條目（如 Wikipedia
            39 段）只取 1 段時理論題證據不足（10-08 根因 #3）；其餘段落取自各路候選，依名次排序。

    Returns:
        依 RRF 分數由高到低的文件；每筆為該文件名次最好那一路的結果副本，``score`` 改為
        RRF 分數，``metadata.fusion`` 記錄 ``rrf_score`` 與各路名次（1 起算）。
    """
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    best: dict[str, tuple[int, Mapping[str, Any]]] = {}
    extra: dict[str, list[tuple[int, Mapping[str, Any]]]] = {}  # 文件的其他段落（名次, 段落）
    for route, docs in ranked_lists.items():
        seen: set[str] = set()
        for pos, doc in enumerate(docs, 1):
            key = document_key(doc)
            if chunks_per_doc > 1:  # 各路出現過的所有段落都是候選（不只同一路的重複）
                extra.setdefault(key, []).append((pos, doc))
            if key in seen:
                continue
            seen.add(key)
            rank = len(seen)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            ranks.setdefault(key, {})[route] = rank
            if key not in best or rank < best[key][0]:
                best[key] = (rank, doc)

    ordered = sorted(scores, key=lambda key: (-scores[key], best[key][0], key))[:top_n]
    fused = []
    for key in ordered:
        doc = dict(best[key][1])
        metadata = dict(doc.get("metadata") or {})
        metadata["fusion"] = {"rrf_score": scores[key], "ranks": ranks[key], "doc_key": key}
        doc["metadata"] = metadata
        doc["score"] = scores[key]
        fused.append(doc)
        if chunks_per_doc > 1:
            taken = {_chunk_identity(doc)}
            for _, other in sorted(extra.get(key, []), key=lambda t: t[0]):
                if len(taken) >= chunks_per_doc:
                    break
                ident = _chunk_identity(other)
                if ident in taken:
                    continue
                taken.add(ident)
                more = dict(other)
                more["metadata"] = {
                    **dict(other.get("metadata") or {}),
                    "fusion": metadata["fusion"],
                }
                more["score"] = scores[key]
                fused.append(more)
    return fused


def _chunk_identity(doc: Mapping[str, Any]) -> str:
    """同一段落在不同路出現時視為相同（chunk_id 或內容開頭）。"""
    meta = doc.get("metadata") or {}
    return str(meta.get("chunk_id") or str(doc.get("content", ""))[:200])
