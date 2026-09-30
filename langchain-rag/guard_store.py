"""影子模式紀錄寫入 ``eval.guard_shadow``（規格 GRD-06a／06d、GRD-08）。

只寫數值與文件 id，不寫提問、答案原文或使用者 id（BIZ-03、EVL-15a）。
需要 migration ``08-eval-guard-shadow.sql``。
"""

from collections.abc import Mapping
from typing import Any

import psycopg

COLUMNS = (
    "route_id",
    "model",
    "gate_status",
    "guard_ms",
    "n_sentences",
    "n_anchored",
    "n_supported",
    "n_partial",
    "n_unsupported",
    "anchor_hit_rate",
    "cited_doc_ids",
    "cache_hit",
)


def record_guard_shadow(conn: psycopg.Connection, row: Mapping[str, Any]) -> None:
    """寫入一筆影子紀錄；``row`` 缺少的欄位存 NULL（``cited_doc_ids`` 缺少時為空陣列）。

    Args:
        conn: PostgreSQL 連線。
        row: 欄位名稱見 ``COLUMNS``。

    Raises:
        KeyError: 缺少必填的 ``route_id`` 或 ``gate_status``。
    """
    values = {name: row.get(name) for name in COLUMNS}
    for required in ("route_id", "gate_status"):
        if not values[required]:
            raise KeyError(required)
    values["cited_doc_ids"] = list(values["cited_doc_ids"] or [])
    placeholders = ", ".join(["%s"] * len(COLUMNS))
    conn.execute(
        f"INSERT INTO eval.guard_shadow ({', '.join(COLUMNS)}) VALUES ({placeholders})",  # noqa: S608 -- 欄位名為常數
        [values[name] for name in COLUMNS],
    )
