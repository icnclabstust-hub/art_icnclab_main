"""Neo4j 訂閱器：把 catalog 的 document 事件套用成既有的圖模型（Artwork／Artist／CREATED）。

生命週期採「軟到期」而非刪除，對應架構圖的五種原子操作：

1. ADD_ENTITY／2. UPDATE_ENTITY：MERGE 並補上 ``valid_from``、清除 ``valid_to``。
3. ADD_RELATIONSHIP：``CREATED`` 關係補上 ``valid_from``、清除 ``valid_to``。
4. EXPIRE_RELATIONSHIP：作品的藝術家名單改變時，不再列出的舊 ``CREATED`` 關係設 ``valid_to``
   （新名單為空時不動，避免來源暫時缺欄位就把作者資訊全數到期）。
5. SOFT_DELETE：作品設 ``is_deleted``／``deleted_at``／``valid_to``。

到期或軟刪除的資料保留 30 天供還原，之後由 ``purge`` 真正刪除；檢索端的圖查詢一律排除它們。
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from subscribers.base import Event
from subscribers.chroma_sub import _final_state

SUBSCRIBER_NAME = "neo4j"
EUROPEANA = "europeana"

_EUROPEANA_ARTWORK_QUERY = """
UNWIND $rows AS row
MERGE (a:Artwork {id: row.id})
SET a.title = row.title,
    a.date = row.date,
    a.source = 'europeana',
    a.description = row.description,
    a.provider = row.provider,
    a.country = row.country,
    a.url = row.url,
    a.updated_at = datetime()
"""

_EUROPEANA_ARTIST_QUERY = """
UNWIND $rows AS row
MERGE (artist:Artist {name: row.artist_name})
WITH artist, row
MATCH (artwork:Artwork {id: row.artwork_id})
MERGE (artist)-[:CREATED]->(artwork)
"""

_SOFT_DELETE_QUERY = """
UNWIND $ids AS id
MATCH (a:Artwork {id: id})
SET a.is_deleted = true, a.deleted_at = datetime(), a.valid_to = datetime()
"""

# 唯一性約束同時提供索引：沒有它 MERGE 每次都要掃過全部節點，也擋不住並行寫入造成的重複節點。
# IF NOT EXISTS 使其可重複執行；線上資料已確認無重複的 Artwork.id 與 Artist.name。
SCHEMA_STATEMENTS = (
    "CREATE CONSTRAINT artwork_id_unique IF NOT EXISTS FOR (a:Artwork) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT artist_name_unique IF NOT EXISTS FOR (a:Artist) REQUIRE a.name IS UNIQUE",
)


def ensure_schema(session) -> None:
    """建立訂閱器依賴的唯一性約束（已存在則略過）。

    Args:
        session: Neo4j session。

    Raises:
        Exception: 現有資料違反約束（例如已有重複 id）時由 Neo4j 拋出，不會靜默略過。
    """
    for statement in SCHEMA_STATEMENTS:
        session.run(statement).consume()


_REACTIVATE_QUERY = """
MATCH (a:Artwork)
WHERE a.id IN $ids AND a.is_deleted = true
SET a.is_deleted = false
REMOVE a.deleted_at, a.valid_to
"""


_LIFECYCLE_QUERY = """
UNWIND $ids AS id
MATCH (a:Artwork {id: id})
SET a.valid_from = coalesce(a.valid_from, datetime())
REMOVE a.valid_to
"""

_ADD_RELATIONSHIP_QUERY = """
UNWIND $rows AS row
MATCH (x:Artist)-[r:CREATED]->(a:Artwork {id: row.artwork_id})
WHERE x.name IN row.names
SET r.valid_from = coalesce(r.valid_from, datetime())
REMOVE r.valid_to
"""

_EXPIRE_RELATIONSHIP_QUERY = """
UNWIND $rows AS row
MATCH (x:Artist)-[r:CREATED]->(a:Artwork {id: row.artwork_id})
WHERE r.valid_to IS NULL AND size(row.names) > 0 AND NOT x.name IN row.names
SET r.valid_to = datetime()
"""

RETENTION_DAYS = 30
_PURGE_RULES = (
    (
        "expired_relationships",
        "MATCH ()-[r]->() WHERE r.valid_to IS NOT NULL"
        " AND r.valid_to < datetime() - duration({days: $days})",
        "r",
        "DELETE r",
    ),
    (
        "deleted_artworks",
        "MATCH (a:Artwork) WHERE a.is_deleted = true AND a.deleted_at IS NOT NULL"
        " AND a.deleted_at < datetime() - duration({days: $days})",
        "a",
        "DETACH DELETE a",
    ),
    (
        "orphan_artists",
        "MATCH (x:Artist) WHERE NOT (x)--()",
        "x",
        "DELETE x",
    ),
)


def purge(session, days: int = RETENTION_DAYS, *, apply: bool = False) -> dict[str, int]:
    """清除超過保留期的到期關係與已軟刪除作品，以及因此變成孤立的藝術家。

    Args:
        session: Neo4j session。
        days: 保留天數；到期或軟刪除超過此天數才會被刪除。
        apply: 為假時只計數（預覽）；為真才刪除。

    Returns:
        各類別的數量（預覽為預計刪除數，套用為實際刪除數）。
    """
    counts: dict[str, int] = {}
    for name, match, var, delete in _PURGE_RULES:
        statement = f"{match} {delete if apply else ''} RETURN count({var}) AS c"
        counts[name] = session.run(statement, days=days).single()["c"]
    return counts


@dataclass(frozen=True)
class Queries:
    """博物館來源（非 Europeana）使用的 Cypher，與既有匯入腳本共用同一份。"""

    artwork: str
    artist: str

    @classmethod
    def from_legacy(cls) -> "Queries":
        """取自既有匯入腳本，確保寫出的圖結構與舊流程完全相同。"""
        from ingest import legacy  # noqa: PLC0415 -- 只有實際執行訂閱器才需要

        module = legacy.load_legacy_module()
        return cls(artwork=module._ARTWORK_UNWIND_QUERY, artist=module._ARTIST_UNWIND_QUERY)  # noqa: SLF001


def _artist_names(artwork: dict) -> list[str]:
    creators = artwork.get("creators")
    if creators is not None:
        return [c for c in creators if c]
    return [n.strip() for n in (artwork.get("artist") or "").split(",") if n.strip()]


class Neo4jSubscriber:
    """把 catalog 的 document 事件寫進 Neo4j。

    Args:
        session_factory: 回傳 context manager 的函式（例如 ``driver.session``）。
        queries: 博物館來源用的 Cypher；省略時取自既有匯入腳本。
    """

    name = SUBSCRIBER_NAME
    entity_types = ("document",)

    def __init__(self, session_factory: Callable, queries: Queries | None = None) -> None:
        self.session_factory = session_factory
        self.queries = queries or Queries.from_legacy()

    def handle(self, events: Sequence[Event]) -> None:
        """套用一批事件；同一批內以最後一個事件為準。任何寫入失敗都會拋出例外。"""
        latest = _final_state(events)
        upserts = [e for e in latest.values() if e.op == "upsert"]
        deletes = [ext for ext, e in latest.items() if e.op == "soft_delete"]

        standard = [e for e in upserts if e.payload["source"] != EUROPEANA]
        europeana = [e for e in upserts if e.payload["source"] == EUROPEANA]
        with self.session_factory() as session:
            if standard:
                self._write(session, standard, self.queries.artwork, self.queries.artist)
            if europeana:
                self._write(session, europeana, _EUROPEANA_ARTWORK_QUERY, _EUROPEANA_ARTIST_QUERY)
            if upserts:
                ids = [e.payload["external_id"] for e in upserts]
                session.run(_REACTIVATE_QUERY, ids=ids).consume()
                session.run(_LIFECYCLE_QUERY, ids=ids).consume()
                rows = [
                    {
                        "artwork_id": e.payload["external_id"],
                        "names": _artist_names(e.payload["artwork"]),
                    }
                    for e in upserts
                ]
                session.run(_ADD_RELATIONSHIP_QUERY, rows=rows).consume()
                session.run(_EXPIRE_RELATIONSHIP_QUERY, rows=rows).consume()
            if deletes:
                session.run(_SOFT_DELETE_QUERY, ids=deletes).consume()

    @staticmethod
    def _write(session, events: Sequence[Event], artwork_query: str, artist_query: str) -> None:
        artwork_rows, artist_rows = [], []
        for event in events:
            artwork = event.payload["artwork"]
            source = event.payload["source"]
            artwork_rows.append({**artwork, "source": source})
            artist_rows.extend(
                {"artist_name": name, "artwork_id": artwork["id"], "source": source}
                for name in _artist_names(artwork)
            )
        session.run(artwork_query, rows=artwork_rows).consume()
        if artist_rows:
            session.run(artist_query, rows=artist_rows).consume()
