#!/usr/bin/env python3
"""Q2／#9 自動選路的離線模擬（用既有逐題分數，不重新生成）。

依架構（Phase 5 設計 §4.2 更正、10-14 第 2 層計畫 #8／#9）：
RAG Router 決定「走哪一路檢索」，模型由使用者以「模型@策略」選定。
因此「自動」＝模型固定、依 #8 意圖辨識的題型選路由；
完成標準：各題型指標不低於該題型最佳單一路由。
（10-14 第一版把模型與路由混成 20 組比較，比錯對象，已以本版取代。）

- 意圖辨識（規則式四類，實驗用，未上線）：博物館＋「哪些／列出」＝限制條件；
  書名號《》＋年代／媒材等問法＝事實；「有哪些」「哪些…作品／畫作／肖像」＝關係；其餘＝理論。
  規則是看著這批題目寫的，正確率會高估，需另備新題驗證。
- 逐題分數（0～1）：
  事實 B1–B6、關係 B7–B12：規則指標，2 次平均（graph／hybrid 用錨點版 8011 API，
    vector／fulltext 用 8080 評估）
  理論 T1–T15：10-13 主張覆蓋比例（gemma4:12b 裁判，未經 κ 驗證）；
    graph 錨點對理論題退回 fulltext，以 fulltext 分數代表（近似）
  限制條件 C1–C37：檢索 F1（Cypher 標準答案；與生成模型無關，五個模型共用）
- 自動選路：題目依「預測題型」取路由；各題型的路由以留一法決定（不用到自己的分數），
  平手時偏好預設 hybrid，再依路由順序。
"""

import json
import re
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
E = REPO / "logs" / "eval"
MODELS = ["llama3.1:8b", "qwen3:8b", "deepseek-r1:8b", "gemma4:12b", "qwen3:14b"]
ROUTES = ["hybrid", "graph", "vector", "fulltext"]  # 順序即平手偏好（hybrid 為預設）
TYPES = ["事實", "關係", "限制條件", "理論"]
CONSTRAINT_ROUTE = {
    "graph_anchor": "graph",
    "hybrid_anchor": "hybrid",
    "vector": "vector",
    "fulltext": "fulltext",
}


def classify(q: str) -> str:
    if re.search(r"博物館|美術館|館藏", q) and re.search(r"哪些|列出", q):
        return "限制條件"
    if "《" in q and re.search(r"年|何時|時候|媒材|材質|版本|收藏|位於|哪座", q):
        return "事實"
    if re.search(r"有哪些|哪些.{0,6}(作品|畫作|肖像)", q):
        return "關係"
    return "理論"


def gold_type(key: str) -> str | None:
    if key[0] == "C":
        return "限制條件"
    if key[0] == "T":
        return "理論"
    no = int(key[1:])
    return "事實" if no <= 6 else ("關係" if no <= 12 else None)


def load(p):
    return [json.loads(line) for line in open(p, encoding="utf-8") if line.strip()]


def scores():
    raw = defaultdict(list)  # (model, route, key) -> [分數…]
    for run in (1, 2):
        for r in load(E / "8080-2026-10-09" / f"run{run}_scored.jsonl"):
            v = r.get("fact", r.get("rel"))
            if r["key"][0] == "B" and r["route"] in ("vector", "fulltext") and v is not None:
                raw[(r["model"], r["route"], r["key"])].append(v)
        for d, route in (
            ("graph-spike-2026-10-11", "graph"),
            ("graph-spike-hybrid-2026-10-11", "hybrid"),
        ):
            for r in load(E / d / f"run{run}_scored.jsonl"):
                v = r.get("fact", r.get("rel"))
                if v is not None:
                    raw[(r["model"], route, r["key"])].append(v)
    golden = json.load(
        open(REPO / "docs/golden-set/2026-10-13-theory15-claims.json", encoding="utf-8")
    )
    n_claims = {f"T{q['no']}": sum(c["grade"] in "AB" for c in q["claims"]) for q in golden}
    for run in (1, 2):
        for r in load(E / "8080-2026-10-09" / "rejudge-2026-10-13" / f"run{run}_theory.jsonl"):
            v = r["cov"].get("covered", 0) / n_claims[r["key"]]
            if r["route"] in ("vector", "fulltext", "hybrid"):
                raw[(r["model"], r["route"], r["key"])].append(v)
            if r["route"] == "fulltext":  # graph 錨點對理論題退回 fulltext（近似）
                raw[(r["model"], "graph", r["key"])].append(v)
    for row in json.load(
        open(E / "constraint-2026-10-11" / "constraint_rows.json", encoding="utf-8")
    ):
        route = CONSTRAINT_ROUTE.get(row["route"])
        if route and row["f1"] is not None:  # 應拒答題無 F1
            for m in MODELS:
                raw[(m, route, row["key"])].append(row["f1"])
    return {k: st.mean(v) for k, v in raw.items()}


def questions():
    qs = {
        f"B{q['no']}": q["question"]
        for q in json.load(
            open(REPO / "docs/golden-set/2026-10-01-baroque-questions.json", encoding="utf-8")
        )["questions"]
    }
    qs |= {
        f"T{q['no']}": q["question"]
        for q in json.load(
            open(REPO / "docs/golden-set/2026-10-13-theory15-claims.json", encoding="utf-8")
        )
    }
    qs |= {
        q["key"]: q["question"]
        for q in json.load(open(E / "constraint-2026-10-11" / "questions.json", encoding="utf-8"))
        if q["gold_ids"]  # 應拒答 4 題無 F1，不計
    }
    return {k: v for k, v in qs.items() if gold_type(k)}


def main():
    S = scores()
    qs = questions()
    pred = {k: classify(q) for k, q in qs.items()}
    conf = Counter((gold_type(k), pred[k]) for k in qs)
    acc = sum(gold_type(k) == pred[k] for k in qs) / len(qs)
    print(f"意圖辨識：{len(qs)} 題正確率 {acc:.1%}（規則依同批題目撰寫，偏高估）")
    for k in qs:
        if gold_type(k) != pred[k]:
            print(f"  誤判 {k}：{gold_type(k)} → {pred[k]}｜{qs[k]}")
    out = {"intent_accuracy": acc, "confusion": {f"{a}->{b}": n for (a, b), n in conf.items()}}
    for m in MODELS:
        keys = [k for k in qs if all((m, r, k) in S for r in ROUTES)]
        by_type = defaultdict(list)
        for k in keys:
            by_type[gold_type(k)].append(k)

        def mean(r, ks, m=m):
            return st.mean(S[(m, r, k)] for k in ks) if ks else float("nan")

        auto, chosen = {}, defaultdict(Counter)
        for k in keys:
            train = [x for x in by_type[pred[k]] if x != k]
            route = max(ROUTES, key=lambda r: (round(mean(r, train), 6), -ROUTES.index(r)))
            auto[k] = S[(m, route, k)]
            chosen[pred[k]][route] += 1
        print(
            f"\n[{m}] 題數 {len(keys)}（"
            + "、".join(f"{t} {len(by_type[t])}" for t in TYPES)
            + "）"
        )
        res = {}
        for t in TYPES:
            ks = by_type[t]
            single = {r: mean(r, ks) for r in ROUTES}
            best = max(ROUTES, key=lambda r: single[r])
            a = st.mean(auto[k] for k in ks)
            ok = a >= single[best] - 1e-9
            res[t] = {
                "auto": a,
                "best_route": best,
                "best": single[best],
                "single": single,
                "pass": ok,
            }
            print(
                f"  {t:4}：自動 {a:.3f}｜最佳單一 {best} {single[best]:.3f}｜"
                + " ".join(f"{r} {single[r]:.3f}" for r in ROUTES)
                + f"｜{'達標' if ok else '未達'}；選路 {dict(chosen[t])}"
            )
        overall = {r: mean(r, keys) for r in ROUTES}
        a_all = st.mean(auto.values())
        best_all = max(ROUTES, key=lambda r: overall[r])
        print(
            f"  全部：自動 {a_all:.3f}｜最佳單一 {best_all} {overall[best_all]:.3f}｜預設 hybrid {overall['hybrid']:.3f}"  # noqa: E501 -- 輸出訊息字串
        )
        res["全部"] = {"auto": a_all, "best_route": best_all, "single": overall}
        out[m] = res
    path = E / "layer2-2026-10-14" / "auto_router_v2.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
