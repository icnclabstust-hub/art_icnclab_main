"""
共用文字切塊工具，供 import_all_museums_to_neo4j.py 與 sync_europeana_to_databases.py 使用。

以字元數切塊、保留重疊區間，避免語意剛好斷在切塊邊界上。多數博物館資料本身就短
（Title/Creator/Date/Description 組合起來通常在 chunk_size 以內），這種情況會直接
整段當一塊、不做切割；只有真的超長的文本（例如較長的描述、未來若匯入書籍/展覽全文）
才會被拆成多塊。
"""

DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64


def chunk_text(
    text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP
) -> list[str]:
    """把文字切成多塊，塊與塊之間保留 overlap 字元的重疊。

    :param text: 原始文字
    :param chunk_size: 每塊最大字元數
    :param overlap: 相鄰兩塊之間的重疊字元數
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def build_chunk_records(
    doc_id: str,
    text: str,
    metadata: dict,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
):
    """把一筆文件切塊後，組成可以直接送進 ChromaDB upsert 的 (ids, documents, metadatas) 三個 list。

    只有 1 塊時沿用原本的 doc_id（不加後綴），維持跟既有資料的 id 相容，重複匯入
    同一筆資料不會產生新的孤兒向量；超過 1 塊才用 f"{doc_id}_chunk{i}" 區分。
    """
    pieces = chunk_text(text, chunk_size, overlap)
    ids, documents, metadatas = [], [], []
    total = len(pieces)
    for i, piece in enumerate(pieces):
        chunk_id = doc_id if total == 1 else f"{doc_id}_chunk{i}"
        chunk_meta = dict(metadata)
        chunk_meta["parent_id"] = doc_id
        chunk_meta["chunk_index"] = i
        chunk_meta["total_chunks"] = total
        ids.append(chunk_id)
        documents.append(piece)
        metadatas.append(chunk_meta)
    return ids, documents, metadatas
