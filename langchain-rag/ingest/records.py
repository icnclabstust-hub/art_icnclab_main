"""把正規化後的作品轉成 ChromaDB 使用的 chunk 紀錄，規則與 ChromaBatchWriter.add 完全一致。"""

from collections.abc import Callable
from dataclasses import dataclass

from chunking import build_chunk_records

TITLE_MAX = 500
ARTIST_MAX = 200
DATE_MAX = 100


@dataclass(frozen=True)
class ChunkRecord:
    """一個要寫入檢索庫的文字塊。

    Attributes:
        external_id: 既有系統的 chunk id（Chroma id）。
        index: 在該文件內的序號。
        text: 文字內容。
        metadata: Chroma／ES 的 metadata。
    """

    external_id: str
    index: int
    text: str
    metadata: dict


def build_chunks(
    source: str, artwork: dict, build_document_text: Callable[[dict], str]
) -> list[ChunkRecord]:
    """切出某筆作品的所有 chunk。

    Args:
        source: 來源名稱（例如 ``harvard``）。
        artwork: 正規化後的作品 dict。
        build_document_text: 組合文件文字的函式（沿用既有實作）。

    Returns:
        依序號排列的 ``ChunkRecord`` 清單。
    """
    metadata = {
        "title": artwork["title"][:TITLE_MAX],
        "artist": artwork["artist"][:ARTIST_MAX],
        "date": artwork["date"][:DATE_MAX],
        "source": source,
    }
    ids, documents, metadatas = build_chunk_records(
        artwork["id"], build_document_text(artwork), metadata
    )
    return [
        ChunkRecord(external_id=cid, index=i, text=doc, metadata=meta)
        for i, (cid, doc, meta) in enumerate(zip(ids, documents, metadatas, strict=True))
    ]
