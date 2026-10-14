#!/usr/bin/env python3
"""Q9 K（檢索信心）的暫定校準：哪個分數訊號能分辨「最高分候選確實含有證據」。

設計：規格書 #12/#13（Q9）：K＝最佳候選含有證據的機率；
無 reranker 時用 dense／hybrid 最高分與 score gap。
（10-14 Reranker A/B 無組別達採用條件，故用檢索分數。）
- 正樣本來源：限制條件 33 題（Cypher 標準答案），標籤＝最高分候選是否在標準答案中
- canary：資料庫確實沒有作品的 6 位畫家出 8 題（佔 19.5%），標籤恆為 0
- 訊號：最高分（top1）、與第 2 名差（gap12）、與第 5 名差（gap15）；
  路由 hybrid 與 vector（8001，唯讀）
- 輸出：各訊號 AUROC；precision ≥ 0.7 時的門檻與覆蓋率（規格 0.7 的新意義）
限制：替代量尺（非人工 golden set）、41 題，門檻視為暫定，不得在同一批題上反覆調整。

用法（py311_venv）：python scripts/eval_k_signal.py
"""

import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "logs/eval/layer2-2026-10-14"
CANARY_TPL = [
    ("{a}有哪些作品收藏在大都會藝術博物館？", None),
    ("{a}的代表作是什麼？", ("克林姆", "草間彌生")),
]


def retrieve(route, q):
    body = json.dumps(
        {"query": q, "model_combination_id": f"llama3.1:8b@{route}", "max_results": 10}
    ).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8001/api/v1/retrieve", body, {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=600) as r:  # noqa: S310 -- 固定本機位址
        d = json.load(r)
    return [
        (c.get("external_id") or "", float(s.get("score") or 0))
        for c, s in zip(d["citations"], d["sources"], strict=True)
    ]


def auroc(pos, neg):
    if not pos or not neg:
        return float("nan")
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def main():
    cons = [
        c
        for c in json.load(
            open(REPO / "logs/eval/constraint-2026-10-11/questions.json", encoding="utf-8")
        )
        if c["gold_ids"]
    ]
    canary_artists = [
        x["zh"] for x in json.load(open(OUT / "canary_artists.json", encoding="utf-8"))
    ]
    items = [(c["question"], set(c["gold_ids"]), "answerable") for c in cons]
    for tpl, only in CANARY_TPL:
        items += [
            (tpl.format(a=a), set(), "canary") for a in canary_artists if only is None or a in only
        ]
    rows = []
    for route in ("hybrid", "vector"):
        for q, gold, kind in items:
            got = retrieve(route, q)
            sc = [s for _, s in got]
            label = int(bool(got) and got[0][0] in gold)
            rows.append(
                {
                    "route": route,
                    "kind": kind,
                    "q": q,
                    "label": label,
                    "top1": sc[0] if sc else 0.0,
                    "gap12": sc[0] - sc[1] if len(sc) > 1 else 0.0,
                    "gap15": sc[0] - sc[4] if len(sc) > 4 else 0.0,
                }
            )
    (OUT / "k_signal.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    n_can = sum(1 for _, _, k in items if k == "canary")
    print(f"題目 {len(items)}（可答 {len(items) - n_can}、canary {n_can}）")
    for route in ("hybrid", "vector"):
        rs = [r for r in rows if r["route"] == route]
        pos_rate = sum(r["label"] for r in rs) / len(rs)
        print(f"\n[{route}] 最高分候選含證據比例（基準精確率）{pos_rate:.1%}")
        for sig in ("top1", "gap12", "gap15"):
            pos = [r[sig] for r in rs if r["label"]]
            neg = [r[sig] for r in rs if not r["label"]]
            ranked = sorted(rs, key=lambda r: -r[sig])
            best = None
            for i in range(1, len(ranked) + 1):
                prec = sum(r["label"] for r in ranked[:i]) / i
                if prec >= 0.7:
                    best = (ranked[i - 1][sig], i / len(ranked), prec)
            can_scores = [r[sig] for r in rs if r["kind"] == "canary"]
            ans_scores = [r[sig] for r in rs if r["kind"] == "answerable"]
            thr = (
                f"門檻 {best[0]:.4f}（覆蓋 {best[1]:.0%}、精確率 {best[2]:.0%}）"
                if best
                else "無法達到 0.7"
            )
            print(
                f"  {sig:6} AUROC {auroc(pos, neg):.3f}｜canary 最高 {max(can_scores):.4f}、可答中位 "  # noqa: E501 -- 輸出訊息字串
                f"{sorted(ans_scores)[len(ans_scores) // 2]:.4f}｜precision≥0.7 {thr}"
            )


if __name__ == "__main__":
    sys.exit(main())
