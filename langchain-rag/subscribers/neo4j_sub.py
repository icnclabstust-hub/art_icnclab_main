"""Neo4j 訂閱器：把 catalog 的 document 事件套用成既有的圖模型（Artwork／Artist／CREATED）。

Phase 1 只做 MERGE 更新與「軟標記」：來源移除的文件設 ``is_deleted``／``deleted_at``，
不物理刪除節點；五種原子操作與 30 天保留清理留待 Phase 2。
既有讀取端目前不會過濾 ``is_deleted``，因此預設的 ``--prune`` 關閉時不會發生軟刪除。
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
SET a.is_deleted = true, a.deleted_at = datetime()
"""

_REACTIVATE_QUERY = """
MATCH (a:Artwork)
WHERE a.id IN $ids AND a.is_deleted = true
SET a.is_deleted = false
REMOVE a.deleted_at
"""


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
