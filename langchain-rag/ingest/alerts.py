"""一致性稽核結果寫入 ``eval.alerts``（規格 DAT-05、EVL-10／11）。

同一檢索庫、同一來源同時只保留一筆未處理告警：再次偵測到不一致時更新明細，
恢復一致時自動標記為已處理。需要 migration ``07-eval-alerts-severity-and-grants.sql``。
"""

import psycopg
from psycopg.types.json import Jsonb

from ingest.verify import Comparison

METRIC_PREFIX = "consistency_"
SEVERITY = "warning"


def metric_name(store: str) -> str:
    """一致性告警的指標名稱，例如 ``consistency_chromadb``。"""
    return f"{METRIC_PREFIX}{store}"


def mismatch_pct(comparison: Comparison) -> float:
    """不一致的 id 數佔 catalog 應有數的百分比（catalog 為空時以 1 為分母）。"""
    mismatched = comparison.only_in_catalog + comparison.only_in_store
    return round(mismatched * 100 / max(comparison.catalog_count, 1), 2)


def _detail(comparison: Comparison) -> dict:
    return {
        "catalog_count": comparison.catalog_count,
        "store_count": comparison.store_count,
        "only_in_catalog": comparison.only_in_catalog,
        "only_in_store": comparison.only_in_store,
        "catalog_samples": comparison.catalog_samples,
        "store_samples": comparison.store_samples,
    }


def record_consistency(
    conn: psycopg.Connection, source: str, store: str, comparison: Comparison
) -> str:
    """依比對結果開立、更新或結案一致性告警。

    Args:
        conn: PostgreSQL 連線。
        source: 來源名稱，存於 ``route_id``。
        store: 檢索庫名稱（``chromadb``／``elasticsearch``）。
        comparison: ``compare_ids`` 的結果。

    Returns:
        ``opened``（新開告警）、``updated``（既有未處理告警更新明細）、
        ``resolved``（恢復一致，結案 n 筆）或 ``ok``（一致且無未處理告警）。
    """
    name = metric_name(store)
    if comparison.consistent:
        resolved = conn.execute(
            "UPDATE eval.alerts SET resolved_at = CURRENT_TIMESTAMP"
            " WHERE metric_name = %s AND route_id = %s AND resolved_at IS NULL",
            (name, source),
        ).rowcount
        return "resolved" if resolved else "ok"

    inserted = conn.execute(
        "INSERT INTO eval.alerts (metric_name, route_id, delta_pct, severity, detail)"
        " VALUES (%s, %s, %s, %s, %s)"
        " ON CONFLICT (metric_name, (COALESCE(route_id, ''))) WHERE resolved_at IS NULL"
        " DO UPDATE SET delta_pct = EXCLUDED.delta_pct, detail = EXCLUDED.detail"
        " RETURNING (xmax = 0)",
        (name, source, mismatch_pct(comparison), SEVERITY, Jsonb(_detail(comparison))),
    ).fetchone()[0]
    return "opened" if inserted else "updated"
