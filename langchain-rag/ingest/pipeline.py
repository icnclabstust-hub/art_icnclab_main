"""攝取流程：雜湊比對 → 內容掃描 → 單一交易寫入 catalog 與 outbox（sync_events）。

每一份文件各自一個交易：documents／chunks 的異動與對應的 sync_events 要嘛一起成功、
要嘛一起失敗，訂閱器因此永遠不會看到「沒有事件的異動」或「沒有異動的事件」。
"""

import logging
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from ingest.ids import chunk_uuid, content_hash, doc_uuid
from ingest.records import ChunkRecord, build_chunks
from ingest.scanner import load_rules, scan_artwork

logger = logging.getLogger(__name__)

STATUS_CLEAN = "clean"
STATUS_QUARANTINED = "quarantined"
STATUS_REVIEWED = "reviewed"
PROGRESS_EVERY = 500


@dataclass
class IngestStats:
    """一次攝取的統計。

    Attributes:
        new: 首次出現的文件數。
        changed: 內容雜湊變更的文件數。
        unchanged: 內容未變而略過的文件數。
        quarantined: 本次被隔離的文件數。
        pruned: 因來源已消失而標記刪除的文件數。
        events: 寫入 sync_events 的事件數。
    """

    new: int = 0
    changed: int = 0
    unchanged: int = 0
    quarantined: int = 0
    pruned: int = 0
    events: int = 0


@dataclass(frozen=True)
class _ChunkRow:
    chunk_id: Any
    external_id: str
    content_hash: str
    is_deleted: bool


def _emit(
    conn: psycopg.Connection,
    stats: IngestStats,
    entity_type: str,
    entity_id: Any,
    op: str,
    payload: dict,
) -> None:
    conn.execute(
        "INSERT INTO catalog.sync_events (entity_type, entity_id, op, payload)"
        " VALUES (%s, %s, %s, %s)",
        (entity_type, entity_id, op, Jsonb(payload)),
    )
    stats.events += 1


def _existing_chunks(conn: psycopg.Connection, doc_id: Any) -> dict[str, _ChunkRow]:
    rows = conn.execute(
        "SELECT chunk_id, external_id, content_hash, is_deleted FROM catalog.chunks"
        " WHERE doc_id = %s",
        (doc_id,),
    ).fetchall()
    return {r[1]: _ChunkRow(*r) for r in rows}


def _retire_chunks(
    conn: psycopg.Connection,
    stats: IngestStats,
    doc_id: Any,
    source: str,
    rows: Iterable[_ChunkRow],
    *,
    delete_rows: bool,
) -> None:
    """對這些 chunk 寫 soft_delete 事件，並刪除列（chunk 被取代）或標記刪除（文件被移除）。"""
    chunk_ids = []
    for row in rows:
        _emit(
            conn,
            stats,
            "chunk",
            row.chunk_id,
            "soft_delete",
            {"external_id": row.external_id, "doc_id": str(doc_id), "source": source},
        )
        chunk_ids.append(row.chunk_id)
    if not chunk_ids:
        return
    if delete_rows:
        conn.execute("DELETE FROM catalog.chunks WHERE chunk_id = ANY(%s)", (chunk_ids,))
    else:
        conn.execute(
            "UPDATE catalog.chunks SET is_deleted = TRUE WHERE chunk_id = ANY(%s)", (chunk_ids,)
        )


def _upsert_document(
    conn: psycopg.Connection,
    doc_id: Any,
    external_id: str,
    source: str,
    digest: str,
    version: int,
    status: str,
    metadata: dict,
) -> None:
    conn.execute(
        "INSERT INTO catalog.documents"
        " (doc_id, external_id, source, content_hash, version, is_deleted,"
        "  quarantine_status, metadata)"
        " VALUES (%s, %s, %s, %s, %s, FALSE, %s, %s)"
        " ON CONFLICT (doc_id) DO UPDATE SET source = EXCLUDED.source,"
        "  content_hash = EXCLUDED.content_hash, version = EXCLUDED.version,"
        "  is_deleted = FALSE, quarantine_status = EXCLUDED.quarantine_status,"
        "  metadata = EXCLUDED.metadata",
        (doc_id, external_id, source, digest, version, status, Jsonb(metadata)),
    )


def _upsert_chunks(
    conn: psycopg.Connection,
    stats: IngestStats,
    doc_id: Any,
    source: str,
    records: list[ChunkRecord],
    existing: dict[str, _ChunkRow],
) -> None:
    for rec in records:
        digest = content_hash({"text": rec.text, "metadata": rec.metadata})
        current = existing.get(rec.external_id)
        if current and current.content_hash == digest and not current.is_deleted:
            continue
        chunk_id = chunk_uuid(rec.external_id)
        conn.execute(
            "INSERT INTO catalog.chunks"
            " (chunk_id, doc_id, external_id, content_hash, chunk_index, version, is_deleted)"
            " VALUES (%s, %s, %s, %s, %s, 1, FALSE)"
            " ON CONFLICT (chunk_id) DO UPDATE SET content_hash = EXCLUDED.content_hash,"
            "  chunk_index = EXCLUDED.chunk_index, version = catalog.chunks.version + 1,"
            "  is_deleted = FALSE",
            (chunk_id, doc_id, rec.external_id, digest, rec.index),
        )
        _emit(
            conn,
            stats,
            "chunk",
            chunk_id,
            "upsert",
            {
                "external_id": rec.external_id,
                "doc_id": str(doc_id),
                "source": source,
                "text": rec.text,
                "metadata": rec.metadata,
            },
        )


def _write_document(
    conn: psycopg.Connection,
    stats: IngestStats,
    source: str,
    artwork: dict,
    build_document_text: Callable[[dict], str],
    previous: tuple | None,
    hits: tuple[str, ...],
    digest: str,
) -> None:
    external_id = artwork["id"]
    doc_id = doc_uuid(external_id)
    version = 1 if previous is None else previous[3] + 1
    status = STATUS_CLEAN if not hits else STATUS_QUARANTINED
    metadata = {"artwork": artwork, "scan": {"rules": list(hits)}}
    existing = _existing_chunks(conn, doc_id)
    previously_active = (
        previous is not None and not previous[1] and previous[2] != STATUS_QUARANTINED
    )

    _upsert_document(conn, doc_id, external_id, source, digest, version, status, metadata)

    if status == STATUS_QUARANTINED:
        if previously_active:
            _retire_chunks(conn, stats, doc_id, source, existing.values(), delete_rows=True)
            _emit(
                conn,
                stats,
                "document",
                doc_id,
                "soft_delete",
                {"external_id": external_id, "source": source},
            )
        return

    records = build_chunks(source, artwork, build_document_text)
    keep = {r.external_id for r in records}
    obsolete = [row for ext, row in existing.items() if ext not in keep]
    _retire_chunks(conn, stats, doc_id, source, obsolete, delete_rows=True)
    _upsert_chunks(
        conn,
        stats,
        doc_id,
        source,
        records,
        {ext: row for ext, row in existing.items() if ext in keep},
    )
    _emit(
        conn,
        stats,
        "document",
        doc_id,
        "upsert",
        {"external_id": external_id, "source": source, "version": version, "artwork": artwork},
    )


def _prune_missing(
    conn: psycopg.Connection, stats: IngestStats, source: str, seen: set[str]
) -> None:
    rows = conn.execute(
        "SELECT doc_id, external_id, version, quarantine_status FROM catalog.documents"
        " WHERE source = %s AND NOT is_deleted",
        (source,),
    ).fetchall()
    for doc_id, external_id, version, status in rows:
        if external_id in seen:
            continue
        with conn.transaction():
            if status != STATUS_QUARANTINED:
                _retire_chunks(
                    conn,
                    stats,
                    doc_id,
                    source,
                    _existing_chunks(conn, doc_id).values(),
                    delete_rows=False,
                )
                _emit(
                    conn,
                    stats,
                    "document",
                    doc_id,
                    "soft_delete",
                    {"external_id": external_id, "source": source},
                )
            conn.execute(
                "UPDATE catalog.documents SET is_deleted = TRUE, version = %s WHERE doc_id = %s",
                (version + 1, doc_id),
            )
        stats.pruned += 1


def ingest_artworks(
    conn: psycopg.Connection,
    source: str,
    artworks: Iterable[dict],
    build_document_text: Callable[[dict], str],
    *,
    dry_run: bool = False,
    prune: bool = False,
    rules: list[tuple[str, re.Pattern[str]]] | None = None,
) -> IngestStats:
    """把一批正規化後的作品攝取進 catalog。

    Args:
        conn: autocommit 的 psycopg 連線。
        source: 來源名稱（例如 ``harvard``）。
        artworks: ``normalize_*`` 產出的 dict 序列，每筆需含 ``id``。
        build_document_text: 組合文件文字的函式（沿用既有實作）。
        dry_run: 只統計，不寫入任何資料。
        prune: 為真時，把 catalog 中該來源「本次未出現」的文件標記刪除。
            只有在 ``artworks`` 是該來源的完整快照時才可使用，否則會誤刪。
        rules: 已編譯的掃描規則；省略時載入預設規則檔。

    Returns:
        本次攝取的統計。
    """
    compiled = rules if rules is not None else load_rules()
    stats = IngestStats()
    seen: set[str] = set()

    for count, artwork in enumerate(artworks, start=1):
        external_id = artwork["id"]
        seen.add(external_id)
        digest = content_hash(artwork)
        previous = conn.execute(
            "SELECT content_hash, is_deleted, quarantine_status, version"
            " FROM catalog.documents WHERE doc_id = %s",
            (doc_uuid(external_id),),
        ).fetchone()

        if previous and previous[0] == digest and not previous[1]:
            stats.unchanged += 1
        else:
            hits = scan_artwork(artwork, compiled).rules
            if previous is None:
                stats.new += 1
            else:
                stats.changed += 1
            if hits:
                stats.quarantined += 1
                logger.warning("隔離 %s：命中規則 %s", external_id, ", ".join(hits))
            if not dry_run:
                with conn.transaction():
                    _write_document(
                        conn, stats, source, artwork, build_document_text, previous, hits, digest
                    )
        if count % PROGRESS_EVERY == 0:
            logger.info("[%s] 已處理 %d 筆", source, count)

    if prune and not dry_run:
        _prune_missing(conn, stats, source, seen)
    return stats
