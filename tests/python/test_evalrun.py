"""Phase 3 召回率量測：指標計算、黃金集匯入、量測 run 與基準比較。"""

import pytest
from evalrun import golden, runner
from evalrun.golden import GoldenItem
from evalrun.metrics import dedupe, ndcg_at_k, recall_at_k
from ingest.alerts import open_alerts

# ---------------------------------------------------------------- 指標（純函式）


def test_dedupe_keeps_first_rank_and_drops_empty():
    assert dedupe(["a", "b", "a", None, "", "c"]) == ["a", "b", "c"]


def test_recall_counts_hits_within_k():
    assert recall_at_k(["a", "x", "b", "c"], {"a", "b", "z"}, k=2) == pytest.approx(1 / 3)
    assert recall_at_k(["a", "x", "b"], {"a", "b"}, k=10) == 1.0  # k 大於候選數


def test_ndcg_rewards_earlier_hits():
    assert ndcg_at_k(["a", "b"], {"a", "b"}, k=10) == pytest.approx(1.0)
    assert ndcg_at_k(["x", "a"], {"a"}, k=10) == pytest.approx(1 / 1.5849625)
    assert ndcg_at_k(["x", "y"], {"a"}, k=10) == 0.0


def test_metrics_reject_empty_relevant_set():
    with pytest.raises(ValueError):
        recall_at_k(["a"], set(), k=10)
    with pytest.raises(ValueError):
        ndcg_at_k(["a"], set(), k=10)


def test_problems_flag_unlabeled_invalid_and_answerable_without_relevant():
    items = [
        GoldenItem("g#1", "q1", "fact", unlabeled=2),
        GoldenItem("g#2", "q2", "relation", invalid=["第3列「x」"]),
        GoldenItem("g#3", "q3", "refuse"),  # 應拒答題沒有相關文件是正常的
    ]
    found = golden.problems(items)
    assert found == [
        "g#1：2 列未標註",
        "g#1（fact）：沒有任何相關文件",
        "g#2：相關欄不是 0/1：第3列「x」",
        "g#2（relation）：沒有任何相關文件",
    ]


def test_read_workbook_parses_labels_points_and_missed(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "2026-10-07-baroque-candidates.xlsx"
    wb = openpyxl.Workbook()
    q = wb.active
    q.title = "題目"
    q.append(
        ["題號", "題型", "題目", "候選數", "答案要點（請填）", "漏掉的相關文件（選填）", "備註"]
    )
    q.append([1, "事實查詢", "夜巡哪一年？", 2, "1642\n油畫", "met_1， met_2", None])
    q.append([2, "應拒答", "不存在的作品", 1, None, None, None])
    c = wb.create_sheet("候選")
    c.append(
        [
            "題號",
            "序",
            "相關（1/0）",
            "標題",
            "藝術家",
            "年代",
            "來源",
            "摘要",
            "策略",
            "external_id",
            "doc_id",
        ]
    )
    c.append([1, 1, 1, "", "", "", "", "", "", "e1", "d1"])
    c.append([1, 2, 0, "", "", "", "", "", "", "e2", "d2"])
    c.append([2, 1, None, "", "", "", "", "", "", "e3", "d3"])
    wb.save(path)

    first, second = golden.read_workbook(str(path))

    assert (first.key, first.query_type, first.relevant_doc_ids) == (
        "2026-10-07-baroque#1",
        "fact",
        {"d1"},
    )
    assert first.gold_answer_points == ["1642", "油畫"]
    assert first.missed_external_ids == ["met_1", "met_2"]
    assert (second.query_type, second.unlabeled) == ("refuse", 1)
    assert [i.key for i in golden.read_workbook(str(path), only={2})] == ["2026-10-07-baroque#2"]


# ---------------------------------------------------------------- 資料庫（拋棄式 PostgreSQL）


@pytest.fixture
def eval_conn(conn):
    conn.execute("TRUNCATE eval.alerts, eval.runs, eval.measurements, eval.golden_queries CASCADE")
    return conn


def add_doc(conn, external_id, **flags):
    return conn.execute(
        "INSERT INTO catalog.documents"
        " (source, content_hash, external_id, is_deleted, quarantine_status) VALUES"
        " ('met_museum', 'h', %s, %s, %s) RETURNING doc_id::text",
        (external_id, flags.get("is_deleted", False), flags.get("quarantine", "clean")),
    ).fetchone()[0]


def test_upsert_golden_resolves_missed_ids_and_updates_on_reimport(eval_conn):
    d1, d2 = add_doc(eval_conn, "met_1"), add_doc(eval_conn, "met_2")
    item = GoldenItem("g#1", "q", "relation", relevant_doc_ids={d1}, missed_external_ids=["met_2"])

    assert golden.upsert_golden(eval_conn, [item], "annotator") == {"inserted": 1, "updated": 0}
    stored = eval_conn.execute(
        "SELECT relevant_doc_ids::text[], annotator FROM eval.golden_queries"
    ).fetchone()
    assert (set(stored[0]), stored[1]) == ({d1, d2}, "annotator")

    item.missed_external_ids = []
    assert golden.upsert_golden(eval_conn, [item], "annotator") == {"inserted": 0, "updated": 1}

    with pytest.raises(ValueError, match="met_404"):
        golden.upsert_golden(
            eval_conn, [GoldenItem("g#2", "q", "fact", missed_external_ids=["met_404"])], "a"
        )


def seed(conn):
    """兩題：q1 相關 {a1, a2}、q2 相關 {b1}；外加一題應拒答（不計召回）。"""
    a1, a2, b1 = add_doc(conn, "a1"), add_doc(conn, "a2"), add_doc(conn, "b1")
    golden.upsert_golden(
        conn,
        [
            GoldenItem("g#1", "q1", "relation", relevant_doc_ids={a1, a2}),
            GoldenItem("g#2", "q2", "fact", relevant_doc_ids={b1}),
            GoldenItem("g#3", "q3", "refuse"),
        ],
        "annotator",
    )
    return a1, a2, b1


def fixed_retriever(results):
    calls = []

    def retrieve(query, route, n):
        calls.append((query, route, n))
        return results[query][:n]

    retrieve.calls = calls
    return retrieve


def test_run_writes_four_routes_two_ks_two_metrics_per_query(eval_conn):
    a1, a2, b1 = seed(eval_conn)
    retrieve = fixed_retriever({"q1": [a1, "x", a2], "q2": ["y", b1]})

    run_id = runner.run(eval_conn, retrieve, "manual", commit_sha="abc", set_baseline=True)

    assert {c[0] for c in retrieve.calls} == {"q1", "q2"}  # 應拒答題不量測
    assert eval_conn.execute(
        "SELECT count(*) FROM eval.measurements WHERE run_id = %s", (run_id,)
    ).fetchone()[0] == (2 * 4 * 2 * 2)
    status, baseline, sha, ks = eval_conn.execute(
        "SELECT status, is_baseline, commit_sha, config_snapshot->'ks' FROM eval.runs"
    ).fetchone()
    assert (status, baseline, sha, ks) == ("done", True, "abc", [10, 20])
    summary = runner.summarize(eval_conn, run_id)
    assert summary[("hybrid", "post_rrf", "recall", 10)] == pytest.approx(1.0)
    assert summary[("vector", "pre_fusion", "ndcg", 10)] == pytest.approx(
        (ndcg_at_k([a1, "x", a2], {a1, a2}, 10) + ndcg_at_k(["y", b1], {b1}, 10)) / 2
    )


def test_run_without_golden_queries_raises_and_writes_nothing(eval_conn):
    with pytest.raises(runner.NoGoldenQueries):
        runner.run(eval_conn, fixed_retriever({}), "nightly")
    assert eval_conn.execute("SELECT count(*) FROM eval.runs").fetchone()[0] == 0


def test_retrieval_failure_marks_run_failed_without_measurements(eval_conn):
    seed(eval_conn)

    def broken(query, route, n):
        raise ConnectionError("8001 down")

    with pytest.raises(ConnectionError):
        runner.run(eval_conn, broken, "nightly")
    assert eval_conn.execute("SELECT status FROM eval.runs").fetchone()[0] == "failed"
    assert eval_conn.execute("SELECT count(*) FROM eval.measurements").fetchone()[0] == 0


def test_deleted_relevant_doc_marks_query_stale_and_excludes_it(eval_conn):
    a1, a2, b1 = seed(eval_conn)
    eval_conn.execute("UPDATE catalog.documents SET is_deleted = TRUE WHERE doc_id = %s", (b1,))
    retrieve = fixed_retriever({"q1": [a1, a2], "q2": [b1]})

    runner.run(eval_conn, retrieve, "manual")

    assert {c[0] for c in retrieve.calls} == {"q1"}
    assert eval_conn.execute(
        "SELECT status FROM eval.golden_queries WHERE golden_key = 'g#2'"
    ).fetchone()[0] == ("stale")


def test_regression_over_five_points_opens_alert_then_resolves(eval_conn):
    a1, a2, b1 = seed(eval_conn)
    good = {"q1": [a1, a2], "q2": [b1]}
    base_id = runner.run(eval_conn, fixed_retriever(good), "manual", set_baseline=True)
    assert runner.record_regressions(eval_conn, base_id) == {}  # 本次即基準，不判斷

    worse = runner.run(eval_conn, fixed_retriever({"q1": [a1, "x"], "q2": [b1]}), "nightly")
    outcomes = runner.record_regressions(eval_conn, worse)

    assert set(outcomes.values()) == {"opened"}  # q1 召回 1.0→0.5，平均退步 25 個百分點
    alert = next(a for a in open_alerts(eval_conn) if a["route_id"] == "hybrid")
    assert (alert["metric_name"], alert["severity"]) == ("eval_regression", "warning")
    assert alert["detail"]["drop_pp"] == pytest.approx(25.0)

    recovered = runner.run(eval_conn, fixed_retriever(good), "nightly")
    assert set(runner.record_regressions(eval_conn, recovered).values()) == {"resolved"}
    assert open_alerts(eval_conn) == []


def test_corpus_fingerprint_reports_drift_against_frozen_snapshot(eval_conn):
    add_doc(eval_conn, "a1")
    frozen = runner.corpus_fingerprint(eval_conn)
    frozen["snapshot_at"] = "2000-01-01T00:00:00+00"

    same = runner.corpus_fingerprint(eval_conn, frozen)
    assert same["same_as_frozen"] is True
    add_doc(eval_conn, "a2")
    drifted = runner.corpus_fingerprint(eval_conn, frozen)
    assert (drifted["same_as_frozen"], drifted["documents"], drifted["frozen_documents"]) == (
        False,
        2,
        1,
    )
    assert drifted["changed_since_frozen"] == 2
