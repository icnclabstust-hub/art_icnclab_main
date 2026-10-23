"""把檢索結果轉成回應的 ``citations[]``（規格 GEN-02）。

``doc_id``／``chunk_id`` 用攝取層同一套 UUIDv5 推導（``ingest.ids``），可直接對應
catalog 與黃金集的 ``relevant_doc_ids``；找不到可靠 id 的來源（例如舊策略回傳的
Artist 節點）兩者為 None，不自行捏造。``index`` 對應生成提示詞中的「[文檔 N]」。
"""

from collections.abc import Mapping, Sequence
from typing import Any

from ingest.ids import chunk_uuid, doc_uuid
from retrieval_fusion import document_external_id


def build_citations(sources: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """依檢索結果順序產生引用清單。

    Args:
        sources: 送進生成的檢索結果（``content``／``metadata``／``score``／``source``）。

    Returns:
        每筆含 ``index``、``doc_id``、``chunk_id``、``external_id``、``chunk_external_id``、
        ``source``、``title``、``score``。
    """
    citations = []
    for index, doc in enumerate(sources, 1):
        meta = doc.get("metadata") or {}
        external_id = document_external_id(doc)
        chunk_external_id = meta.get("chunk_id")
        score = doc.get("score")
        citations.append(
            {
                "index": index,
                "doc_id": str(doc_uuid(external_id)) if external_id else None,
                "chunk_id": str(chunk_uuid(str(chunk_external_id))) if chunk_external_id else None,
                "external_id": external_id,
                "chunk_external_id": chunk_external_id,
                "source": meta.get("source") or doc.get("source"),
                "title": meta.get("title") or meta.get("name"),
                "score": float(score) if isinstance(score, (int, float)) else None,
            }
        )
    return citations
