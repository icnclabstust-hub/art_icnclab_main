#!/usr/bin/env python3
"""限制條件題（畫家 × 館藏）檢索層評估：集合精確率／召回率／F1、各條件滿足率、配對統計檢定。

設計：docs/designs/2026-10-11-graph-retrieval-anchor.md（規劃書「評估設計」）
- 題目與標準答案：scripts/gen_constraint_questions.py（Cypher 算出）
- 路由：錨點版 graph／hybrid（8011，GRAPH_RETRIEVAL=anchor）vs 現況 graph／fulltext／vector／hybrid（8001）
- 只呼叫 /api/v1/retrieve（不生成）；翻譯模型 llama3.1:8b（3 秒內可完成 LLM 翻譯）
- 召回率以前 5 筆計：|R∩G| / min(|G|, 5)
- 統計：分析單位為題目；Wilcoxon 符號等級（F1，正例題），Holm 校正，事前指定 4 組比較

裁判：全部為規則比對（集合運算與 Neo4j 查作品的畫家、館藏），不使用 LLM。

用法（Windows py311_venv）：
    python scripts/eval_constraint_retrieval.py <questions.json> <artist_aliases.json> <輸出目錄>
"""

import json
import statistics as st
import sys
import urllib.request
from pathlib import Path

from neo4j import GraphDatabase
from scipy.stats import wilcoxon

REPO = Path(__file__).resolve().parent.parent
ROUTES = {
    "graph_anchor": ("http://127.0.0.1:8011", "graph"),
    "hybrid_anchor": ("http://127.0.0.1:8011", "hybrid"),
    "graph_legacy": ("http://127.0.0.1:8001", "graph"),
    "fulltext": ("http://127.0.0.1:8001", "fulltext"),
    "vector": ("http://127.0.0.1:8001", "vector"),
    "hybrid_legacy": ("http://127.0.0.1:8001", "hybrid"),
}
COMPARISONS = [
    ("graph_anchor", "graph_legacy"),
    ("graph_anchor", "fulltext"),
    ("graph_anchor", "hybrid_legacy"),
    ("hybrid_anchor", "hybrid_legacy"),
]
MODEL = "llama3.1:8b"
K = 5


def env(key):
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"')
    return None


def retrieve(api, route, query):
    body = json.dumps({"query": query, "model_combination_id": f"{MODEL}@{route}", "max_results": K}).encode()
    req = urllib.request.Request(f"{api}/api/v1/retrieve", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:  # noqa: S310 -- 固定本機位址
        d = json.load(r)
    ids = []
    for c in d.get("citations", []):
        cid = c.get("external_id")
        if cid and cid not in ids:
            ids.append(cid)
    return ids[:K]


def holm(pvals):
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj, running = [0.0] * len(pvals), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvals) - rank) * pvals[i]))
        adj[i] = running
    return adj


def main():
    questions = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    artists = {a["qid"]: a for a in json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))["artists"]}
    out = Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for q in questions:
        for name, (api, route) in ROUTES.items():
            rows.append({"key": q["key"], "route": name, "ids": retrieve(api, route, q["question"])})
        print(q["key"], {r["route"]: len(r["ids"]) for r in rows if r["key"] == q["key"]}, flush=True)

    # 取回作品的畫家與館藏（規則判定各條件）
    all_ids = sorted({i for r in rows for i in r["ids"]})
    drv = GraphDatabase.driver("bolt://127.0.0.1:7687", auth=(env("NEO4J_USER") or "neo4j", env("NEO4J_PASSWORD")))
    info = {}
    with drv.session() as s:
        for r in s.run(
            "MATCH (w:Artwork) WHERE w.id IN $ids "
            "OPTIONAL MATCH (a:Artist)-[:CREATED]->(w) OPTIONAL MATCH (w)-[:HELD_BY]->(i:Institution) "
            "RETURN w.id AS id, collect(DISTINCT a.name) AS artists, collect(DISTINCT i.name) AS insts",
            ids=all_ids,
        ):
            info[r["id"]] = (set(r["artists"]), set(r["insts"]))
    drv.close()

    qmap = {q["key"]: q for q in questions}
    for r in rows:
        q = qmap[r["key"]]
        gold, got = set(q["gold_ids"]), r["ids"]
        names = set(artists[q["artist_qid"]]["neo4j_names"])
        hit = len(gold & set(got))
        r["precision"] = hit / len(got) if got else 0.0
        r["recall"] = hit / min(len(gold), K) if gold else None
        p, rc = r["precision"], r["recall"]
        r["f1"] = (2 * p * rc / (p + rc) if p + rc else 0.0) if rc is not None else None
        r["artist_ok"] = sum(bool(info.get(i, (set(), set()))[0] & names) for i in got) / len(got) if got else None
        r["museum_ok"] = sum(q["museum"] in info.get(i, (set(), set()))[1] for i in got) / len(got) if got else None
        r["violations"] = sum(  # 應拒答題：取回「該畫家且在該館」之外的作品數（越少越好）
            1 for i in got if not (info.get(i, (set(), set()))[0] & names and q["museum"] in info.get(i, (set(), set()))[1])
        )
    (out / "constraint_rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    pos = [q["key"] for q in questions if q["gold_ids"]]
    neg = [q["key"] for q in questions if not q["gold_ids"]]
    summary = {}
    print(f"\n正例 {len(pos)} 題、應拒答 {len(neg)} 題（裁判：規則比對）")
    print(f"{'路由':16}{'精確率':>7}{'召回率':>7}{'F1':>7}{'畫家條件':>9}{'館藏條件':>9}{'空結果':>7}")
    for name in ROUTES:
        rs = [r for r in rows if r["route"] == name and r["key"] in pos]
        nonempty = [r for r in rs if r["ids"]]
        summary[name] = {
            "precision": st.mean(r["precision"] for r in rs),
            "recall": st.mean(r["recall"] for r in rs),
            "f1": st.mean(r["f1"] for r in rs),
            "artist_ok": st.mean(r["artist_ok"] for r in nonempty) if nonempty else None,
            "museum_ok": st.mean(r["museum_ok"] for r in nonempty) if nonempty else None,
            "empty": sum(1 for r in rs if not r["ids"]),
            "neg_returned": sum(len(r["ids"]) for r in rows if r["route"] == name and r["key"] in neg),
        }
        s = summary[name]
        print(f"{name:16}{s['precision']:>7.3f}{s['recall']:>7.3f}{s['f1']:>7.3f}{s['artist_ok'] or 0:>9.3f}{s['museum_ok'] or 0:>9.3f}{s['empty']:>7}")

    f1 = {name: [next(r["f1"] for r in rows if r["route"] == name and r["key"] == k) for k in pos] for name in ROUTES}
    tests = []
    for a, b in COMPARISONS:
        diff = [x - y for x, y in zip(f1[a], f1[b], strict=True)]
        nz = sum(1 for d in diff if d)
        p = wilcoxon(f1[a], f1[b]).pvalue if nz else 1.0
        tests.append({"a": a, "b": b, "mean_diff": st.mean(diff), "nonzero": nz, "p": p})
    for t, adj in zip(tests, holm([t["p"] for t in tests]), strict=True):
        t["p_holm"] = adj
    print("\nWilcoxon 符號等級（F1，正例題配對）＋Holm 校正")
    for t in tests:
        print(f"{t['a']} vs {t['b']}: 平均差 {t['mean_diff']:+.3f}，非零差 {t['nonzero']} 題，p={t['p']:.2e}，Holm p={t['p_holm']:.2e}")
    (out / "constraint_summary.json").write_text(
        json.dumps({"summary": summary, "tests": tests, "n_pos": len(pos), "n_neg": len(neg)}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
