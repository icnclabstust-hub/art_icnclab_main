"""量測 run：對黃金集重放檢索，寫入 ``eval.measurements``，並與基準比較（規格 EVL-05～08）。

量測位置（EVL-06 的四段，本階段只有前兩段存在）：
- ``pre_fusion``：各路檢索後（``vector``／``fulltext``／``graph``）
- ``post_rrf``：系統級 RRF 融合後（``hybrid``）
- 防護後、生成後屬 Phase 4；重排尚未實作（RET-05／06）

檢索一律走既有的 ``/api/v1/retrieve``（不生成、不寫任何紀錄）。``hybrid`` 內部各路取 20 筆候選，
與分別呼叫各路取 20 筆相同，因此不另開設計文件 §5.3 的 trace 入口。
"""

import json
import urllib.request
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import psycopg
from ingest import alerts
from psycopg.types.json import Jsonb

from evalrun.metrics import dedupe, ndcg_at_k, recall_at_k

ROUTES = {
    "vector": "pre_fusion",
    "fulltext": "pre_fusion",
    "graph": "pre_fusion",
    "hybrid": "post_rrf",
}
KS = (10, 20)
METRICS = {"recall": recall_at_k, "ndcg": ndcg_at_k}
REGRESSION_PP = 5.0  # EVL-08：任一指標相對基準退步超過 5 個百分點即告警
REGRESSION_METRIC = "eval_regression"

Retriever = Callable[[str, str, int], list[str]]  # (問題, 路由, 筆數) → 依名次排列的 doc_id


class NoGoldenQueries(RuntimeError):
    """黃金集沒有可量測的題目（尚未標註或全部 stale）。"""


def http_retriever(api_url: str = "http://127.0.0.1:8001") -> Retriever:
    """以 ``/api/v1/retrieve`` 取得某路由前 n 名的文件 id（無文件 id 的圖節點略過）。"""

    def retrieve(query: str, route: str, n: int) -> list[str]:
        body = json.dumps(
            {"query": query, "model_combination_id": f"eval@{route}", "max_results": n}
        )
        request = urllib.request.Request(  # noqa: S310 -- 固定本機位址
            f"{api_url}/api/v1/retrieve",
            data=body.encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310 -- 固定本機位址
            citations = json.load(response)["citations"]
        return dedupe(c.get("doc_id") for c in citations)

    return retrieve


def corpus_fingerprint(conn: psycopg.Connection, frozen: dict | None = None) -> dict[str, Any]:
    """量測當下的語料指紋；給定凍結快照時另算其後變動的文件數（路線圖 R2：記錄漂移）。"""
    count, fingerprint = conn.execute(
        "SELECT count(*),"
        " md5(string_agg(external_id || ':' || content_hash, ',' ORDER BY external_id))"
        " FROM catalog.documents WHERE NOT is_deleted AND quarantine_status <> 'quarantined'"
    ).fetchone()
    snapshot: dict[str, Any] = {"documents": count, "fingerprint_md5": fingerprint}
    if frozen:
        snapshot["frozen_at"] = frozen["snapshot_at"]
        snapshot["frozen_documents"] = frozen["documents"]
        snapshot["same_as_frozen"] = fingerprint == frozen["fingerprint_md5"]
        snapshot["changed_since_frozen"] = conn.execute(
            "SELECT count(*) FROM catalog.documents WHERE updated_at > %s::timestamptz",
            (frozen["snapshot_at"],),
        ).fetchone()[0]
    return snapshot


@dataclass(frozen=True)
class GoldenQuery:
    query_id: str
    key: str
    text: str
    relevant: frozenset[str]


def mark_stale(conn: psycopg.Connection) -> int:
    """標註的文件被刪除或隔離時，該題標 stale、排除於指標之外（設計 §5.5）。"""
    return conn.execute(
        "UPDATE eval.golden_queries g SET status = 'stale'"
        " WHERE status = 'active' AND EXISTS ("
        "   SELECT 1 FROM unnest(g.relevant_doc_ids) AS r(doc_id)"
        "   LEFT JOIN catalog.documents d USING (doc_id)"
        "   WHERE d.doc_id IS NULL OR d.is_deleted OR d.quarantine_status = 'quarantined')"
    ).rowcount


def active_queries(conn: psycopg.Connection) -> list[GoldenQuery]:
    """可量測的題目：active 且有相關文件（應拒答題不計召回率）。"""
    rows = conn.execute(
        "SELECT query_id::text, golden_key, query_text, relevant_doc_ids::text[]"
        " FROM eval.golden_queries WHERE status = 'active' AND cardinality(relevant_doc_ids) > 0"
        " ORDER BY golden_key"
    ).fetchall()
    return [GoldenQuery(r[0], r[1], r[2], frozenset(r[3])) for r in rows]


def run(
    conn: psycopg.Connection,
    retrieve: Retriever,
    trigger: str,
    *,
    commit_sha: str | None = None,
    config: dict | None = None,
    corpus: dict | None = None,
    set_baseline: bool = False,
) -> str:
    """執行一次量測並回傳 run_id。檢索失敗時 run 標為 failed 並拋出例外（不產生告警）。

    Raises:
        NoGoldenQueries: 沒有可量測的題目。
    """
    mark_stale(conn)
    queries = active_queries(conn)
    if not queries:
        raise NoGoldenQueries("eval.golden_queries 沒有可量測的題目（尚未標註或全部 stale）")
    run_id = conn.execute(
        "INSERT INTO eval.runs (trigger, commit_sha, config_snapshot, corpus_snapshot)"
        " VALUES (%s, %s, %s, %s) RETURNING run_id::text",
        (
            trigger,
            commit_sha,
            Jsonb({"routes": ROUTES, "ks": KS, **(config or {})}),
            Jsonb(corpus or {}),
        ),
    ).fetchone()[0]
    try:
        rows = []
        for query in queries:
            for route, stage in ROUTES.items():
                ranked = retrieve(query.text, route, max(KS))
                for k in KS:
                    for metric, fn in METRICS.items():
                        rows.append(
                            (
                                query.query_id,
                                route,
                                stage,
                                metric,
                                fn(ranked, query.relevant, k),
                                run_id,
                                k,
                            )
                        )
        with conn.transaction():
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO eval.measurements"
                    " (query_id, route_id, stage, metric_name, metric_value, run_id, k) VALUES"
                    " (%s, %s, %s, %s, %s, %s, %s)",
                    rows,
                )
            if set_baseline:
                conn.execute("UPDATE eval.runs SET is_baseline = FALSE WHERE is_baseline")
            conn.execute(
                "UPDATE eval.runs SET status = 'done', finished_at = now(), is_baseline = %s"
                " WHERE run_id = %s",
                (set_baseline, run_id),
            )
    except Exception:
        conn.execute(
            "UPDATE eval.runs SET status = 'failed', finished_at = now() WHERE run_id = %s",
            (run_id,),
        )
        raise
    return run_id


def summarize(conn: psycopg.Connection, run_id: str) -> dict[tuple[str, str, str, int], float]:
    """某次 run 各 (路由, 階段, 指標, k) 的題目平均值。"""
    rows = conn.execute(
        "SELECT route_id, stage, metric_name, k, avg(metric_value)::float FROM eval.measurements"
        " WHERE run_id = %s GROUP BY 1, 2, 3, 4",
        (run_id,),
    ).fetchall()
    return {(r[0], r[1], r[2], r[3]): r[4] for r in rows}


def baseline_run(conn: psycopg.Connection) -> str | None:
    row = conn.execute(
        "SELECT run_id::text FROM eval.runs WHERE is_baseline AND status = 'done'"
    ).fetchone()
    return row[0] if row else None


def record_regressions(conn: psycopg.Connection, run_id: str) -> dict[str, str]:
    """與基準比較，各路由取退步最多的指標：超過 5 個百分點開 warning，否則結案。

    沒有基準、或本次就是基準時不判斷。

    Returns:
        路由 → ``opened``／``updated``／``resolved``／``ok``；不判斷時為空 dict。
    """
    base_id = baseline_run(conn)
    if base_id is None or base_id == run_id:
        return {}
    base, current = summarize(conn, base_id), summarize(conn, run_id)
    worst: dict[str, tuple[float, str]] = defaultdict(lambda: (0.0, ""))
    for key, base_value in base.items():
        if key not in current:
            continue
        drop_pp = round((base_value - current[key]) * 100, 2)
        route, _stage, metric, k = key
        if drop_pp > worst[key[0]][0]:
            worst[route] = (drop_pp, f"{metric}@{k}")
    outcomes = {}
    for route in ROUTES:
        drop_pp, metric = worst[route]
        if drop_pp > REGRESSION_PP:
            detail = {"metric": metric, "drop_pp": drop_pp, "baseline_run": base_id, "run": run_id}
            outcomes[route] = alerts.open_or_update(
                conn, REGRESSION_METRIC, route, drop_pp, "warning", detail
            )
        else:
            outcomes[route] = alerts.resolve(conn, REGRESSION_METRIC, route)
    return outcomes
