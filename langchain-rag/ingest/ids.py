"""確定性 id 與內容雜湊。

catalog 用 UUIDv5 由既有字串 id 推導：同一筆資料重跑永遠得到同一個 UUID，
所以不需要另外維護對照表，也不會因重跑產生重複列。
"""

import hashlib
import json
import uuid

CATALOG_NAMESPACE = uuid.UUID("b199485e-4ad6-5886-87ad-1bdd6a9fa302")


def doc_uuid(external_id: str) -> uuid.UUID:
    """由文件的既有字串 id 推導 catalog 的 doc_id。

    Args:
        external_id: 既有系統的作品 id（例如 ``harvard_123``）。

    Returns:
        確定性的 UUIDv5。
    """
    return uuid.uuid5(CATALOG_NAMESPACE, f"doc:{external_id}")


def chunk_uuid(external_id: str) -> uuid.UUID:
    """由 chunk 的既有字串 id（Chroma id）推導 catalog 的 chunk_id。

    Args:
        external_id: 既有系統的 chunk id（單塊為作品 id，多塊為 ``<id>_chunk<i>``）。

    Returns:
        確定性的 UUIDv5。
    """
    return uuid.uuid5(CATALOG_NAMESPACE, f"chunk:{external_id}")


def content_hash(value: object) -> str:
    """對可 JSON 序列化的物件取 SHA-256（鍵排序、保留非 ASCII），作為變更偵測依據。

    Args:
        value: dict／list／字串等可序列化物件。

    Returns:
        64 字元的十六進位雜湊字串。
    """
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
