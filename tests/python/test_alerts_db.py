"""告警寫入 eval.alerts 的整合測試（拋棄式 PostgreSQL）。"""

import pytest
from guard_store import record_guard_shadow
from ingest.alerts import (
    DiskStatus,
    format_summary,
    mismatch_pct,
    open_alerts,
    record_consistency,
    record_disk,
    record_gate_errors,
)
from ingest.verify import compare_ids

GB = 1024**3


@pytest.fixture
def alerts_conn(conn):
    conn.execute("TRUNCATE eval.alerts, eval.guard_shadow")
    return conn


def consistency_rows(conn):
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
    assert consistency_rows(alerts_conn) == [
        ("consistency_chromadb", "harvard", pytest.approx(50), "warning", "1")
    ]


def test_repeated_mismatch_updates_instead_of_duplicating(alerts_conn):
    record_consistency(alerts_conn, "harvard", "chromadb", compare_ids({"a", "b"}, {"a"}))

    outcome = record_consistency(
        alerts_conn, "harvard", "chromadb", compare_ids({"a", "b"}, {"a", "y", "z"})
    )

    assert outcome == "updated"
    rows = consistency_rows(alerts_conn)
    assert len(rows) == 1
    assert rows[0][4] == "2"


def test_recovery_resolves_open_alert_and_next_drift_opens_new_one(alerts_conn):
    record_consistency(alerts_conn, "harvard", "chromadb", compare_ids({"a", "b"}, {"a"}))

    assert (
        record_consistency(alerts_conn, "harvard", "chromadb", compare_ids({"a"}, {"a"}))
        == "resolved"
    )
    assert consistency_rows(alerts_conn) == []

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
    assert [(r[0], r[1]) for r in consistency_rows(alerts_conn)] == [
        ("consistency_chromadb", "europeana"),
        ("consistency_elasticsearch", "harvard"),
    ]


def test_mismatch_pct_handles_empty_catalog():
    assert mismatch_pct(compare_ids(set(), {"x", "y"})) == 200.0


def disk(free_gb, total_gb=100):
    return DiskStatus(label="f", path="/mnt/f", total_bytes=total_gb * GB, free_bytes=free_gb * GB)


def test_disk_thresholds():
    assert (disk(30).severity, disk(15).severity, disk(5).severity) == (None, "warning", "critical")
    assert disk(15).free_pct == 15.0


def test_disk_alert_escalates_then_resolves(alerts_conn):
    assert record_disk(alerts_conn, disk(50)) == "ok"
    assert record_disk(alerts_conn, disk(15)) == "opened"
    assert record_disk(alerts_conn, disk(5)) == "updated"

    [alert] = open_alerts(alerts_conn)
    assert (alert["metric_name"], alert["route_id"], alert["severity"]) == (
        "disk_free",
        "f",
        "critical",
    )
    assert alert["detail"]["free_gb"] == 5.0

    assert record_disk(alerts_conn, disk(40)) == "resolved"
    assert open_alerts(alerts_conn) == []


def shadow(conn, status, n=1):
    for _ in range(n):
        record_guard_shadow(conn, {"route_id": "hybrid", "gate_status": status})


def test_gate_error_rate_above_one_percent_is_critical(alerts_conn):
    assert record_gate_errors(alerts_conn)[0] == "no_data"

    shadow(alerts_conn, "ok", 98)
    shadow(alerts_conn, "hang")
    shadow(alerts_conn, "crash")
    outcome, stats = record_gate_errors(alerts_conn)

    assert outcome == "opened"
    assert (stats["total"], stats["gate_hang"], stats["gate_crash"], stats["error_pct"]) == (
        100,
        1,
        1,
        2.0,
    )
    [alert] = open_alerts(alerts_conn)
    assert (alert["metric_name"], alert["severity"]) == ("gate_error_rate", "critical")


def test_gate_error_rate_at_or_below_one_percent_resolves(alerts_conn):
    shadow(alerts_conn, "ok", 99)
    shadow(alerts_conn, "crash")

    assert record_gate_errors(alerts_conn)[0] == "ok"


def test_embedding_label_alert_opens_on_mix_or_unlabeled_and_resolves(alerts_conn):
    from collections import Counter  # noqa: PLC0415

    from embedding_labels import UNLABELED  # noqa: PLC0415
    from ingest.alerts import record_embedding_labels  # noqa: PLC0415

    current = ("bge-m3:latest", "790764642607")
    assert record_embedding_labels(alerts_conn, "chromadb", Counter({current: 10})) == "ok"
    assert record_embedding_labels(alerts_conn, "chromadb", Counter({UNLABELED: 10})) == "opened"
    assert (
        record_embedding_labels(
            alerts_conn, "chromadb", Counter({current: 90, ("bge-m3:latest", "aaaa"): 10})
        )
        == "updated"
    )

    [alert] = open_alerts(alerts_conn)
    assert (alert["metric_name"], alert["route_id"], float(alert["delta_pct"])) == (
        "embedding_versions",
        "chromadb",
        10.0,
    )
    assert alert["detail"]["combinations"][0] == {
        "model": "bge-m3:latest",
        "version": "790764642607",
        "count": 90,
    }
    assert record_embedding_labels(alerts_conn, "chromadb", Counter({current: 100})) == "resolved"


def test_summary_lists_critical_first(alerts_conn):
    record_consistency(alerts_conn, "harvard", "chromadb", compare_ids({"a", "b"}, {"a"}))
    record_disk(alerts_conn, disk(5))

    alerts = open_alerts(alerts_conn)
    assert [a["severity"] for a in alerts] == ["critical", "warning"]
    text = format_summary(alerts)
    assert text.splitlines()[0] == "未處理告警：2 筆"
    assert "[critical] disk_free／f：5%" in text
    assert format_summary([]) == "未處理告警：0 筆"
