"""一致性驗證：比對 catalog 與各檢索庫的 chunk id 集合。"""

from collections.abc import Iterable
from dataclasses import dataclass, field

import psycopg

PAGE_SIZE = 1000
SAMPLE_SIZE = 5


@dataclass
class Comparison:
    """兩個 id 集合的比對結果。

    Attributes:
        catalog_count: catalog 中有效 chunk 數。
        store_count: 檢索庫中的 chunk 數。
        only_in_catalog: 只在 catalog 的數量（尚未同步）。
        only_in_store: 只在檢索庫的數量（catalog 沒有：舊資料尚未認領，或該被刪除）。
        catalog_samples: 前幾個只在 catalog 的 id。
        store_samples: 前幾個只在檢索庫的 id。
    """

    catalog_count: int
    store_count: int
    only_in_catalog: int
    only_in_store: int
    catalog_samples: list[str] = field(default_factory=list)
    store_samples: list[str] = field(default_factory=list)

    @property
    def consistent(self) -> bool:
        """兩邊 id 集合完全相同。"""
        return self.only_in_catalog == 0 and self.only_in_store == 0


def catalog_chunk_ids(conn: psycopg.Connection, source: str) -> set[str]:
    """catalog 中某來源「應存在於檢索庫」的 chunk 字串 id（排除已刪除與隔離）。"""
    rows = conn.execute(
        "SELECT c.external_id FROM catalog.chunks c JOIN catalog.documents d USING (doc_id)"
        " WHERE d.source = %s AND NOT d.is_deleted AND NOT c.is_deleted"
        " AND d.quarantine_status <> 'quarantined'",
        (source,),
    ).fetchall()
    return {r[0] for r in rows}


def chroma_chunk_ids(collection, source: str) -> set[str]:
    """ChromaDB 中某來源的所有 chunk id。"""
    ids: set[str] = set()
    offset = 0
    while True:
        batch = collection.get(where={"source": source}, limit=PAGE_SIZE, offset=offset, include=[])
        if not batch["ids"]:
            return ids
        ids.update(batch["ids"])
        offset += PAGE_SIZE


def elasticsearch_chunk_ids(es, index: str, source: str) -> set[str]:
    """Elasticsearch 中某來源的所有文件 id。"""
    from elasticsearch.helpers import scan  # noqa: PLC0415 -- 只有 verify --es 才需要此依賴

    query = {"query": {"term": {"source": source}}, "_source": False}
    return {hit["_id"] for hit in scan(es, index=index, query=query)}


def compare_ids(catalog_ids: Iterable[str], store_ids: Iterable[str]) -> Comparison:
    """比對兩個 id 集合。

    Args:
        catalog_ids: catalog 端的 id。
        store_ids: 檢索庫端的 id。

    Returns:
        ``Comparison``。
    """
    catalog_set, store_set = set(catalog_ids), set(store_ids)
    only_catalog = sorted(catalog_set - store_set)
    only_store = sorted(store_set - catalog_set)
    return Comparison(
        catalog_count=len(catalog_set),
        store_count=len(store_set),
        only_in_catalog=len(only_catalog),
        only_in_store=len(only_store),
        catalog_samples=only_catalog[:SAMPLE_SIZE],
        store_samples=only_store[:SAMPLE_SIZE],
    )
