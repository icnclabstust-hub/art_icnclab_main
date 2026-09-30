"""一致性告警寫入 eval.alerts 的整合測試（拋棄式 PostgreSQL）。"""

import pytest
from ingest.alerts import mismatch_pct, record_consistency
from ingest.verify import compare_ids


@pytest.fixture
def alerts_conn(conn):
    conn.execute("TRUNCATE eval.alerts")
    return conn


def open_alerts(conn):
    return conn.execute(
        "SELECT metric_name, route_id, delta_pct, severity, detail->>'only_in_store'"
        " FROM eval.alerts WHERE resolved_at IS NULL ORDER BY metric_name"
    ).fetchall()


def test_consistent_without_open_alert_writes_nothing(alerts_conn):
    outcome = record_consistency(alerts_conn, "harvard", "chromadb", compare_ids({"a"}, {"a"}))

    assert outcome == "ok"
    assert alerts_conn.execute("SELECT count(*) FROM eval.alerts").fetchone()[0] == 0


def test_mismatch_opens_one_warning_alert(alerts_conn):
    outcome = record_consistency(
        alerts_conn, "harvard", "chromadb", compare_ids({"a", "b", "c", "d"}, {"a", "b", "c", "x"})
    )

    assert outcome == "opened"
    assert open_alerts(alerts_conn) == [
        ("consistency_chromadb", "harvard", pytest.approx(50), "warning", "1")
    ]


def test_repeated_mismatch_updates_instead_of_duplicating(alerts_conn):
    record_consistency(alerts_conn, "harvard", "chromadb", compare_ids({"a", "b"}, {"a"}))

    outcome = record_consistency(
        alerts_conn, "harvard", "chromadb", compare_ids({"a", "b"}, {"a", "y", "z"})
    )

    assert outcome == "updated"
    rows = open_alerts(alerts_conn)
    assert len(rows) == 1
    assert rows[0][4] == "2"


def test_recovery_resolves_open_alert_and_next_drift_opens_new_one(alerts_conn):
    record_consistency(alerts_conn, "harvard", "chromadb", compare_ids({"a", "b"}, {"a"}))

    assert (
        record_consistency(alerts_conn, "harvard", "chromadb", compare_ids({"a"}, {"a"}))
        == "resolved"
    )
    assert open_alerts(alerts_conn) == []

    assert (
        record_consistency(alerts_conn, "harvard", "chromadb", compare_ids({"a", "b"}, {"a"}))
        == "opened"
    )
    assert alerts_conn.execute("SELECT count(*) FROM eval.alerts").fetchone()[0] == 2


def test_alerts_are_scoped_per_store_and_source(alerts_conn):
    drift = compare_ids({"a", "b"}, {"a"})
    record_consistency(alerts_conn, "harvard", "chromadb", drift)
    record_consistency(alerts_conn, "harvard", "elasticsearch", drift)
    record_consistency(alerts_conn, "europeana", "chromadb", drift)

    assert (
        record_consistency(alerts_conn, "harvard", "chromadb", compare_ids({"a"}, {"a"}))
        == "resolved"
    )
    assert [(r[0], r[1]) for r in open_alerts(alerts_conn)] == [
        ("consistency_chromadb", "europeana"),
        ("consistency_elasticsearch", "harvard"),
    ]


def test_mismatch_pct_handles_empty_catalog():
    assert mismatch_pct(compare_ids(set(), {"x", "y"})) == 200.0
