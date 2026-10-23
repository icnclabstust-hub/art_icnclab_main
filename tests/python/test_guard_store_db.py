"""影子紀錄寫入 eval.guard_shadow 的整合測試（拋棄式 PostgreSQL）。"""

import uuid
from decimal import Decimal

import pytest
from guard_store import record_guard_shadow


@pytest.fixture
def shadow_conn(conn):
    conn.execute("TRUNCATE eval.guard_shadow")
    return conn


def test_full_row_is_stored(shadow_conn):
    doc = uuid.uuid4()
    record_guard_shadow(
        shadow_conn,
        {
            "route_id": "hybrid",
            "model": "qwen3:8b",
            "gate_status": "ok",
            "guard_ms": 1.25,
            "n_sentences": 6,
            "n_anchored": 4,
            "n_supported": 2,
            "n_partial": 1,
            "n_unsupported": 1,
            "anchor_hit_rate": 0.6,
            "cited_doc_ids": [str(doc)],
            "cache_hit": False,
        },
    )

    row = shadow_conn.execute(
        "SELECT route_id, gate_status, n_unsupported, anchor_hit_rate, cited_doc_ids"
        " FROM eval.guard_shadow"
    ).fetchone()
    assert row[:4] == ("hybrid", "ok", 1, Decimal("0.6"))
    assert row[4] == [doc]


def test_hang_row_without_scores(shadow_conn):
    record_guard_shadow(shadow_conn, {"route_id": "hybrid", "gate_status": "hang"})

    row = shadow_conn.execute(
        "SELECT gate_status, n_sentences, cited_doc_ids FROM eval.guard_shadow"
    ).fetchone()
    assert row == ("hang", None, [])


def test_missing_required_field_and_invalid_status(shadow_conn):
    with pytest.raises(KeyError):
        record_guard_shadow(shadow_conn, {"gate_status": "ok"})

    import psycopg  # noqa: PLC0415

    with pytest.raises(psycopg.errors.CheckViolation):
        record_guard_shadow(shadow_conn, {"route_id": "hybrid", "gate_status": "timeout"})
