"""訂閱器共用的游標迴圈：至少一次（at-least-once）投遞，處理函式必須冪等。

游標只在整批處理成功後才前移；處理失敗就不前移並讓例外往上拋，下次從同一位置重試，
所以資料落後會被看見，而不是被靜默吞掉。
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import psycopg

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 200


@dataclass(frozen=True)
class Event:
    """一筆 outbox 事件。

    Attributes:
        event_id: 全域遞增的事件編號。
        entity_type: ``document`` 或 ``chunk``。
        entity_id: catalog 的 UUID。
        op: ``upsert`` 或 ``soft_delete``。
        payload: 事件內容。
    """

    event_id: int
    entity_type: str
    entity_id: Any
    op: str
    payload: dict


class Subscriber(Protocol):
    """訂閱器介面。"""

    name: str
    entity_types: tuple[str, ...]

    def handle(self, events: Sequence[Event]) -> None:
        """套用一批（已依 entity_types 過濾、依 event_id 排序）事件；必須冪等。"""


def _ensure_cursor(conn: psycopg.Connection, name: str) -> None:
    conn.execute(
        "INSERT INTO catalog.sync_cursor (subscriber, last_event_id) VALUES (%s, 0)"
        " ON CONFLICT (subscriber) DO NOTHING",
        (name,),
    )


def get_cursor(conn: psycopg.Connection, name: str) -> int:
    """讀取訂閱者目前的游標。"""
    _ensure_cursor(conn, name)
    row = conn.execute(
        "SELECT last_event_id FROM catalog.sync_cursor WHERE subscriber = %s", (name,)
    ).fetchone()
    return row[0]


def lag(conn: psycopg.Connection, name: str) -> int:
    """訂閱者落後的事件數（最新事件編號減游標）。"""
    latest = conn.execute("SELECT COALESCE(MAX(event_id), 0) FROM catalog.sync_events").fetchone()[
        0
    ]
    return latest - get_cursor(conn, name)


def run_once(
    conn: psycopg.Connection, subscriber: Subscriber, batch_size: int = DEFAULT_BATCH_SIZE
) -> int:
    """消費所有尚未處理的事件直到追上。

    Args:
        conn: autocommit 的 psycopg 連線。
        subscriber: 訂閱器。
        batch_size: 每批讀取的事件數。

    Returns:
        本次實際交給訂閱器處理的事件數（不含被過濾掉的類型）。

    Raises:
        Exception: 處理函式丟出的例外會原樣往上拋，且游標停在失敗那批之前。
    """
    handled = 0
    cursor = get_cursor(conn, subscriber.name)
    while True:
        rows = conn.execute(
            "SELECT event_id, entity_type, entity_id, op, payload FROM catalog.sync_events"
            " WHERE event_id > %s ORDER BY event_id LIMIT %s",
            (cursor, batch_size),
        ).fetchall()
        if not rows:
            return handled
        relevant = [Event(*r) for r in rows if r[1] in subscriber.entity_types]
        if relevant:
            subscriber.handle(relevant)
            handled += len(relevant)
        cursor = rows[-1][0]
        conn.execute(
            "UPDATE catalog.sync_cursor SET last_event_id = %s WHERE subscriber = %s",
            (cursor, subscriber.name),
        )
        logger.info("[%s] 游標前移至 %d", subscriber.name, cursor)
