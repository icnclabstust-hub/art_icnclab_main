"""補登（backfill）：把「已在檢索庫、但 catalog 不認得」的舊資料反向登記進 catalog。

這些資料來自更早的爬取或一次性匯入，原始檔已不在。補登只寫 catalog，**不寫 outbox 事件**
（各檢索庫本來就有這些資料，重送只會浪費運算），也不改動任何既有 catalog 列；
之後同一筆資料被新流程重新爬到時，雜湊規則與正式攝取相同，內容一致就會判定「未變」。

例外：掃描器命中的文件依政策必須撤出檢索庫，因此補登為隔離狀態並寫入 soft_delete 事件。
"""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import psycopg
from psycopg.types.json import Jsonb

from ingest.ids import chunk_uuid, content_hash, doc_uuid
from ingest.scanner import load_rules, scan_artwork

logger = logging.getLogger(__name__)

PAGE_SIZE = 1000
STANDARD_FIELDS = (
    "title",
    "artist",
    "date",
    "medium",
    "culture",
    "period",
    "department",
    "description",
    "url",
)
EUROPEANA_EXTRA_FIELDS = ("provider", "country")
EUROPEANA = "europeana"
ORIGIN_CHROMA = "chromadb"
ORIGIN_NEO4J = "neo4j"
ORIGIN_BOTH = "chromadb+neo4j"

_ORPHAN_ARTWORKS_QUERY = """
MATCH (a:Artwork)
WHERE NOT a.id IN $managed
RETURN properties(a) AS props, [(x:Artist)-[:CREATED]->(a) | x.name] AS artists
"""


@dataclass(frozen=True)
class LegacyChunk:
    """檢索庫中現存的一個 chunk。"""

    external_id: str
    text: str
    metadata: dict


@dataclass
class LegacyDocument:
    """待補登的舊文件。

    Attributes:
        external_id: 文件 id（Chroma 的 ``parent_id`` 或 Neo4j 的 Artwork id）。
        source: 來源名稱。
        artwork: 重建出的正規化 dict（欄位與 ``normalize_*`` 輸出相同）。
        chunks: 該文件現存的 chunk（可能為空，例如只存在於 Neo4j 的節點）。
        origin: 資料重建自哪裡。
    """

    external_id: str
    source: str
    artwork: dict
    chunks: list[LegacyChunk] = field(default_factory=list)
    origin: str = ORIGIN_CHROMA


@dataclass
class BackfillStats:
    """補登統計。"""

    documents: int = 0
    chunks: int = 0
    skipped_existing: int = 0
    quarantined: int = 0
    events: int = 0
    quarantined_ids: list[str] = field(default_factory=list)


def _rebuild_artwork(
    external_id: str, source: str, node: dict | None, artists: list[str], fallback_meta: dict
) -> dict:
    """由 Neo4j 節點（優先）或 chunk metadata 重建正規化 dict。"""
    node = node or {}
    names = [a for a in artists if a]
    artist = ", ".join(names) if names else str(fallback_meta.get("artist", ""))
    artwork = {"id": external_id}
    for key in STANDARD_FIELDS:
        artwork[key] = str(node.get(key) or "")
    artwork["title"] = artwork["title"] or str(fallback_meta.get("title") or "Untitled")
    artwork["artist"] = artist
    artwork["date"] = artwork["date"] or str(fallback_meta.get("date", ""))
    if source == EUROPEANA:
        for key in EUROPEANA_EXTRA_FIELDS:
            artwork[key] = str(node.get(key) or "")
        artwork["creators"] = names
    return artwork


def _iter_chroma_chunks(collection) -> Iterable[tuple[str, str, dict]]:
    offset = 0
    while True:
        batch = collection.get(limit=PAGE_SIZE, offset=offset, include=["documents", "metadatas"])
        if not batch["ids"]:
            return
        for chunk_id, text, meta in zip(
            batch["ids"], batch["documents"], batch["metadatas"], strict=True
        ):
            yield chunk_id, text or "", meta or {}
        offset += PAGE_SIZE


def read_legacy_documents(
    collection, neo4j_session, managed_doc_ids: set[str]
) -> tuple[list[LegacyDocument], dict[str, int]]:
    """讀出 catalog 不認得的舊文件。

    Args:
        collection: chromadb collection。
        neo4j_session: 可 ``run(query, managed=...)`` 並回傳 ``.data()`` 的 Neo4j session。
        managed_doc_ids: catalog 已有的文件 external_id（這些一律不碰）。

    Returns:
        ``(待補登文件清單, 無法補登的原因統計)``；後者例如缺 ``source`` 的 Neo4j 節點數。
    """
    chunks_by_parent: dict[str, list[LegacyChunk]] = {}
    meta_by_parent: dict[str, dict] = {}
    for chunk_id, text, meta in _iter_chroma_chunks(collection):
        parent = meta.get("parent_id") or chunk_id
        if parent in managed_doc_ids:
            continue
        chunks_by_parent.setdefault(parent, []).append(LegacyChunk(chunk_id, text, meta))
        meta_by_parent.setdefault(parent, meta)

    rows = neo4j_session.run(_ORPHAN_ARTWORKS_QUERY, managed=sorted(managed_doc_ids)).data()
    nodes = {r["props"]["id"]: (r["props"], r["artists"]) for r in rows}

    unreadable = {"neo4j_node_without_source": 0}
    documents: list[LegacyDocument] = []
    for parent in sorted(set(chunks_by_parent) | set(nodes)):
        chunks = sorted(
            chunks_by_parent.get(parent, []), key=lambda c: c.metadata.get("chunk_index", 0)
        )
        node, artists = nodes.get(parent, (None, []))
        fallback = meta_by_parent.get(parent, {})
        source = fallback.get("source") or (node or {}).get("source")
        if not source:
            unreadable["neo4j_node_without_source"] += 1
            continue
        origin = ORIGIN_BOTH if node and chunks else ORIGIN_NEO4J if node else ORIGIN_CHROMA
        documents.append(
            LegacyDocument(
                external_id=parent,
                source=source,
                artwork=_rebuild_artwork(parent, source, node, artists, fallback),
                chunks=chunks,
                origin=origin,
            )
        )
    return documents, unreadable


def _emit(conn: psycopg.Connection, stats: BackfillStats, entity_type, entity_id, payload) -> None:
    conn.execute(
        "INSERT INTO catalog.sync_events (entity_type, entity_id, op, payload)"
        " VALUES (%s, %s, 'soft_delete', %s)",
        (entity_type, entity_id, Jsonb(payload)),
    )
    stats.events += 1


def _insert_document(conn: psycopg.Connection, doc: LegacyDocument, status: str, hits) -> None:
    conn.execute(
        "INSERT INTO catalog.documents"
        " (doc_id, external_id, source, content_hash, version, is_deleted,"
        "  quarantine_status, metadata)"
        " VALUES (%s, %s, %s, %s, 1, FALSE, %s, %s) ON CONFLICT (doc_id) DO NOTHING",
        (
            doc_uuid(doc.external_id),
            doc.external_id,
            doc.source,
            content_hash(doc.artwork),
            status,
            Jsonb(
                {
                    "artwork": doc.artwork,
                    "scan": {"rules": list(hits)},
                    "backfill": {"origin": doc.origin},
                }
            ),
        ),
    )


def backfill_documents(
    conn: psycopg.Connection,
    documents: Iterable[LegacyDocument],
    *,
    apply: bool = False,
    rules: list | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> BackfillStats:
    """把舊文件登記進 catalog。

    Args:
        conn: autocommit 的 psycopg 連線。
        documents: ``read_legacy_documents`` 的結果。
        apply: 為假時只統計（預覽）；為真才寫入。
        rules: 已編譯的掃描規則；省略時載入預設規則檔。
        on_progress: 每處理一份文件呼叫一次（可用於進度顯示）。

    Returns:
        補登統計。
    """
    compiled = rules if rules is not None else load_rules()
    stats = BackfillStats()
    for count, doc in enumerate(documents, start=1):
        doc_id = doc_uuid(doc.external_id)
        exists = conn.execute(
            "SELECT 1 FROM catalog.documents WHERE doc_id = %s", (doc_id,)
        ).fetchone()
        if exists:
            stats.skipped_existing += 1
            continue

        scan_input = {**doc.artwork, **{f"chunk_{i}": c.text for i, c in enumerate(doc.chunks)}}
        hits = scan_artwork(scan_input, compiled).rules
        stats.documents += 1
        if hits:
            stats.quarantined += 1
            stats.quarantined_ids.append(doc.external_id)
        else:
            stats.chunks += len(doc.chunks)
        if apply:
            with conn.transaction():
                _insert_document(conn, doc, "quarantined" if hits else "clean", hits)
                if hits:
                    for chunk in doc.chunks:
                        _emit(
                            conn,
                            stats,
                            "chunk",
                            chunk_uuid(chunk.external_id),
                            {
                                "external_id": chunk.external_id,
                                "doc_id": str(doc_id),
                                "source": doc.source,
                            },
                        )
                    _emit(
                        conn,
                        stats,
                        "document",
                        doc_id,
                        {"external_id": doc.external_id, "source": doc.source},
                    )
                else:
                    for index, chunk in enumerate(doc.chunks):
                        conn.execute(
                            "INSERT INTO catalog.chunks"
                            " (chunk_id, doc_id, external_id, content_hash, chunk_index,"
                            "  version, is_deleted)"
                            " VALUES (%s, %s, %s, %s, %s, 1, FALSE)"
                            " ON CONFLICT (chunk_id) DO NOTHING",
                            (
                                chunk_uuid(chunk.external_id),
                                doc_id,
                                chunk.external_id,
                                content_hash({"text": chunk.text, "metadata": chunk.metadata}),
                                int(chunk.metadata.get("chunk_index", index)),
                            ),
                        )
        if on_progress:
            on_progress(count)
    return stats
