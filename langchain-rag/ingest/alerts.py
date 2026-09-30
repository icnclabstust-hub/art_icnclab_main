"""告警寫入 ``eval.alerts``（規格 EVL-10～12，eval.alerts 為唯一告警出口）。

同一指標、同一路由（來源、磁碟等）同時只保留一筆未處理告警：再次偵測到時更新數值、
等級與明細，恢復正常時自動標記為已處理。目前的告警來源：

- 一致性稽核（DAT-05）：``consistency_<檢索庫>``，route＝來源
- 備份磁碟剩餘空間（DAT-17）：``disk_free``，route＝磁碟標籤
- 防護元件出錯比例（GRD-10）：``gate_error_rate``，route＝``all``
- 嵌入模型混用或未標註（DAT-31）：``embedding_versions``，route＝檢索庫

需要 migration ``07-eval-alerts-severity-and-grants.sql``。
"""

import shutil
from collections import Counter
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from ingest.verify import Comparison

METRIC_PREFIX = "consistency_"
SEVERITY = "warning"

DISK_METRIC = "disk_free"
DISK_WARNING_PCT = 20.0  # DAT-17
DISK_CRITICAL_PCT = 10.0

GATE_METRIC = "gate_error_rate"
GATE_CRITICAL_PCT = 1.0  # GRD-10（日計）

EMBEDDING_METRIC = "embedding_versions"


def open_or_update(
    conn: psycopg.Connection,
    metric: str,
    route: str | None,
    delta_pct: float,
    severity: str,
    detail: dict[str, Any],
) -> str:
    """開立告警；同指標同路由已有未處理告警時改為更新數值、等級與明細。

    Returns:
        ``opened`` 或 ``updated``。
    """
    inserted = conn.execute(
        "INSERT INTO eval.alerts (metric_name, route_id, delta_pct, severity, detail)"
        " VALUES (%s, %s, %s, %s, %s)"
        " ON CONFLICT (metric_name, (COALESCE(route_id, ''))) WHERE resolved_at IS NULL"
        " DO UPDATE SET delta_pct = EXCLUDED.delta_pct, severity = EXCLUDED.severity,"
        " detail = EXCLUDED.detail"
        " RETURNING (xmax = 0)",
        (metric, route, delta_pct, severity, Jsonb(detail)),
    ).fetchone()[0]
    return "opened" if inserted else "updated"


def resolve(conn: psycopg.Connection, metric: str, route: str | None) -> str:
    """把同指標同路由的未處理告警標為已處理。

    Returns:
        ``resolved``（有結案）或 ``ok``（本來就沒有未處理告警）。
    """
    resolved = conn.execute(
        "UPDATE eval.alerts SET resolved_at = CURRENT_TIMESTAMP"
        " WHERE metric_name = %s AND COALESCE(route_id, '') = COALESCE(%s, '')"
        " AND resolved_at IS NULL",
        (metric, route),
    ).rowcount
    return "resolved" if resolved else "ok"


# ---------------------------------------------------------------- 一致性稽核（DAT-05）


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
        ``opened``、``updated``、``resolved`` 或 ``ok``。
    """
    name = metric_name(store)
    if comparison.consistent:
        return resolve(conn, name, source)
    return open_or_update(
        conn, name, source, mismatch_pct(comparison), SEVERITY, _detail(comparison)
    )


# ---------------------------------------------------------------- 備份磁碟空間（DAT-17）


@dataclass(frozen=True)
class DiskStatus:
    """一個路徑所在磁碟的空間狀況。"""

    label: str
    path: str
    total_bytes: int
    free_bytes: int

    @property
    def free_pct(self) -> float:
        return round(self.free_bytes * 100 / self.total_bytes, 2) if self.total_bytes else 0.0

    @property
    def severity(self) -> str | None:
        """低於 10% 為 critical、低於 20% 為 warning，否則 None（正常）。"""
        if self.free_pct < DISK_CRITICAL_PCT:
            return "critical"
        if self.free_pct < DISK_WARNING_PCT:
            return "warning"
        return None


def disk_status(label: str, path: str) -> DiskStatus:
    """讀取路徑所在磁碟的總量與剩餘空間。"""
    usage = shutil.disk_usage(path)
    return DiskStatus(label=label, path=path, total_bytes=usage.total, free_bytes=usage.free)


def record_disk(conn: psycopg.Connection, status: DiskStatus) -> str:
    """依剩餘空間開立、更新或結案 ``disk_free`` 告警。"""
    if status.severity is None:
        return resolve(conn, DISK_METRIC, status.label)
    detail = {
        "path": status.path,
        "free_gb": round(status.free_bytes / 1024**3, 1),
        "total_gb": round(status.total_bytes / 1024**3, 1),
    }
    return open_or_update(conn, DISK_METRIC, status.label, status.free_pct, status.severity, detail)


# ---------------------------------------------------------------- 防護出錯比例（GRD-10）


def record_gate_errors(conn: psycopg.Connection, hours: int = 24) -> tuple[str, dict[str, Any]]:
    """統計最近 ``hours`` 小時 ``eval.guard_shadow`` 的 hang／crash 比例，超過 1% 開 critical。

    沒有任何紀錄時不判斷（既有告警維持原狀）。

    Returns:
        (結果, 統計數字)；結果為 ``opened``／``updated``／``resolved``／``ok``／``no_data``。
    """
    total, hang, crash = conn.execute(
        "SELECT count(*), count(*) FILTER (WHERE gate_status = 'hang'),"
        " count(*) FILTER (WHERE gate_status = 'crash')"
        " FROM eval.guard_shadow WHERE created_at >= now() - make_interval(hours => %s)",
        (hours,),
    ).fetchone()
    stats = {"hours": hours, "total": total, "gate_hang": hang, "gate_crash": crash}
    if not total:
        return "no_data", stats
    rate = round((hang + crash) * 100 / total, 2)
    stats["error_pct"] = rate
    if rate <= GATE_CRITICAL_PCT:
        return resolve(conn, GATE_METRIC, "all"), stats
    return open_or_update(conn, GATE_METRIC, "all", rate, "critical", stats), stats


# ---------------------------------------------------------------- 嵌入模型混用（DAT-31）


def record_embedding_labels(conn: psycopg.Connection, store: str, counts: Counter) -> str:
    """同一檢索庫出現多個 (模型, 版本) 組合或有未標註向量時開 warning，否則結案。

    ``delta_pct`` 為「不屬於最多數組合」的向量比例。
    """
    from embedding_labels import UNLABELED  # noqa: PLC0415 -- 避免 ingest 載入時依賴此模組

    total = sum(counts.values())
    if total == 0 or (len(counts) == 1 and UNLABELED not in counts):
        return resolve(conn, EMBEDDING_METRIC, store)
    majority = max(counts.values())
    detail = {
        "total": total,
        "combinations": [
            {"model": m, "version": v, "count": n} for (m, v), n in counts.most_common()
        ],
    }
    delta = round((total - majority) * 100 / total, 2) if len(counts) > 1 else 100.0
    return open_or_update(conn, EMBEDDING_METRIC, store, delta, "warning", detail)


# ---------------------------------------------------------------- 每日彙總（EVL-12）


def open_alerts(conn: psycopg.Connection) -> list[dict[str, Any]]:
    """所有未處理告警，critical 在前、同等級依發生時間排序。"""
    rows = conn.execute(
        "SELECT metric_name, route_id, severity, delta_pct, triggered_at, detail"
        " FROM eval.alerts WHERE resolved_at IS NULL"
        " ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,"
        " triggered_at"
    ).fetchall()
    keys = ("metric_name", "route_id", "severity", "delta_pct", "triggered_at", "detail")
    return [dict(zip(keys, row, strict=True)) for row in rows]


def format_summary(alerts: list[dict[str, Any]]) -> str:
    """把未處理告警整理成給 Operator 看的純文字。"""
    if not alerts:
        return "未處理告警：0 筆"
    lines = [f"未處理告警：{len(alerts)} 筆"]
    for a in alerts:
        since = a["triggered_at"].strftime("%Y-%m-%d %H:%M") if a["triggered_at"] else "?"
        lines.append(
            f"  [{a['severity']}] {a['metric_name']}／{a['route_id'] or '-'}"
            f"：{float(a['delta_pct']):g}%（自 {since}）"
        )
    return "\n".join(lines)
