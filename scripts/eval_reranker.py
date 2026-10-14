#!/usr/bin/env python3
"""Q5 Reranker A/B（規格 #10）：ONNX int8 交叉編碼器在 CPU 上重排，對照不重排。

設計：規格書 #10（Q5）；不需 torch，只用 onnxruntime＋tokenizers
（int8 ONNX 由 HF 下載到專案外 model_cache）。
- 組別：(d) 不重排；(a) bge-reranker-base（MIT）；(c) bge-reranker-v2-m3（Apache-2.0）。
  (b) GPU fp16 因尖峰 VRAM 7.2／8.15 GB（2026-10-14 實測）餘裕不足 1.5 GB，不測。
- 參數：候選數 10／20／30；max_length 256／512。
- 題目（替代量尺，規則型標準答案，非人工 golden set）：
  限制條件 33 題（Cypher）＋關係題 B7–B12（畫家規則）。
- 候選：8001 /api/v1/retrieve（唯讀），路由 hybrid 與 vector，取前 30 筆一次，10／20 取前綴。
- 指標：F1@5、nDCG@5（二元相關）、逐題勝負（相對 (d)）、每題重排延遲 p50／p95（CPU）。

用法（py311_venv）：python scripts/eval_reranker.py <model_cache 目錄> <輸出目錄>
"""

import json
import math
import statistics as st
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

REPO = Path(__file__).resolve().parent.parent
MODELS = {"a_base": "base", "c_v2m3": "v2m3"}
ROUTES = sys.argv[3].split(",") if len(sys.argv) > 3 else ["hybrid", "vector"]
NS, LENS = (10, 20, 30), (256, 512)


def retrieve(route, q, n=30):
    body = json.dumps(
        {"query": q, "model_combination_id": f"llama3.1:8b@{route}", "max_results": n}
    ).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8001/api/v1/retrieve", body, {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=600) as r:  # noqa: S310 -- 固定本機位址
        d = json.load(r)
    return [
        (c.get("external_id") or "", s.get("content") or "")
        for c, s in zip(d["citations"], d["sources"], strict=True)
    ]


class Reranker:
    def __init__(self, folder, max_len):
        self.sess = ort.InferenceSession(
            str(Path(folder) / "onnx" / "model_int8.onnx"), providers=["CPUExecutionProvider"]
        )
        self.tok = Tokenizer.from_file(str(Path(folder) / "tokenizer.json"))
        self.tok.enable_truncation(max_length=max_len)
        self.tok.enable_padding()
        self.inputs = {i.name for i in self.sess.get_inputs()}

    def scores(self, query, docs):
        enc = self.tok.encode_batch([(query, d) for d in docs])
        feed = {
            "input_ids": np.array([e.ids for e in enc], dtype=np.int64),
            "attention_mask": np.array([e.attention_mask for e in enc], dtype=np.int64),
        }
        if "token_type_ids" in self.inputs:
            feed["token_type_ids"] = np.array([e.type_ids for e in enc], dtype=np.int64)
        return self.sess.run(None, feed)[0].reshape(-1).tolist()


def metrics(ranked_ids, gold, k=5):
    top = ranked_ids[:k]
    hit = sum(i in gold for i in top)
    p, r = hit / len(top) if top else 0, hit / min(len(gold), k)
    f1 = 2 * p * r / (p + r) if p + r else 0
    dcg = sum(1 / math.log2(i + 2) for i, x in enumerate(top) if x in gold)
    idcg = sum(1 / math.log2(i + 2) for i in range(min(len(gold), k)))
    return f1, dcg / idcg if idcg else 0


def main():
    cache, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    cons = json.load(
        open(REPO / "logs/eval/constraint-2026-10-11/questions.json", encoding="utf-8")
    )
    rel = json.load(
        open(REPO / "docs/golden-set/2026-10-09-relation-rule-relevant.json", encoding="utf-8")
    )
    base_q = {
        f"B{q['no']}": q["question"]
        for q in json.load(
            open(REPO / "docs/golden-set/2026-10-01-baroque-questions.json", encoding="utf-8")
        )["questions"]
    }
    items = [(c["key"], c["question"], set(c["gold_ids"])) for c in cons if c["gold_ids"]]
    items += [(f"B{n}", base_q[f"B{n}"], set(rel[str(n)])) for n in range(7, 13)]
    cands = {(route, k): retrieve(route, q) for route in ROUTES for k, q, _ in items}
    print(f"題目 {len(items)}（限制條件 33＋關係 6）；候選已取得", flush=True)
    results = []
    for route in ROUTES:
        base_rows = {k: metrics([i for i, _ in cands[(route, k)]], g) for k, _, g in items}
        print(
            f"\n[{route}] (d) 不重排：F1@5 {st.mean(v[0] for v in base_rows.values()):.3f}  nDCG@5 {st.mean(v[1] for v in base_rows.values()):.3f}"  # noqa: E501 -- 輸出訊息字串
        )
        for label, folder in MODELS.items():
            for max_len in LENS:
                rr = Reranker(cache / folder, max_len)
                for n in NS:
                    f1s, nds, lat, win, lose = [], [], [], 0, 0
                    for k, q, g in items:
                        docs = cands[(route, k)][:n]
                        t = time.perf_counter()
                        sc = rr.scores(q, [c for _, c in docs]) if docs else []  # 無候選時不重排
                        lat.append((time.perf_counter() - t) * 1000)
                        order = [docs[i][0] for i in sorted(range(len(docs)), key=lambda i: -sc[i])]
                        f1, nd = metrics(order, g)
                        f1s.append(f1)
                        nds.append(nd)
                        win += nd > base_rows[k][1] + 1e-9
                        lose += nd < base_rows[k][1] - 1e-9
                    p50, p95 = np.percentile(lat, 50), np.percentile(lat, 95)
                    row = {
                        "route": route,
                        "model": label,
                        "max_len": max_len,
                        "n": n,
                        "f1": st.mean(f1s),
                        "ndcg": st.mean(nds),
                        "delta_ndcg": st.mean(nds) - st.mean(v[1] for v in base_rows.values()),
                        "win": win,
                        "lose": lose,
                        "p50_ms": p50,
                        "p95_ms": p95,
                    }
                    results.append(row)
                    print(
                        f"  {label:7} len{max_len} N{n:2}：F1@5 {row['f1']:.3f}  nDCG@5 {row['ndcg']:.3f}（{row['delta_ndcg']:+.3f}）"  # noqa: E501 -- 輸出訊息字串
                        f" 勝{win} 負{lose}  延遲 p50 {p50:.0f} ms／p95 {p95:.0f} ms",
                        flush=True,
                    )
    (out / f"reranker_ab_{'_'.join(ROUTES)}.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
