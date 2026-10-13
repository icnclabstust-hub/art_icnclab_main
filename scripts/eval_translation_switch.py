#!/usr/bin/env python3
"""F1 量測：換模型時查詢翻譯逾時（2026-10-13 模擬故障點 F1）。

設計：docs/designs/2026-10-13-sim10-fix-plan.md §四
每題輪換模型（llama → qwen3:8b → deepseek → gemma → qwen3:14b → …），使每次查詢都需換載模型，
模擬多人用不同模型；30 題（巴洛克 15＋理論 15）走 /api/v1/query（翻譯＋檢索＋生成）。
記錄：翻譯方式（llm_hinted／fallback／dictionary）、翻譯耗時、總耗時、
術語正確率（同 eval_24combo 的 EXPECT）。

用法（WSL，測試實例已以待測設定啟動在 --api）：
    python3 scripts/eval_translation_switch.py --api http://127.0.0.1:8011 --label t3 --out <目錄>
經 8080（Open WebUI → pipe → 8001）：8080 只回答案，翻譯方式與耗時改讀 8001 日誌的
「查詢翻譯（方式）完成，N ms」行；術語正確率無法量（無檢索句）：
    python3 scripts/eval_translation_switch.py --webui http://127.0.0.1:8080 \
        --key-file ~/.openwebui_key --api http://127.0.0.1:8001 \
        --log /tmp/rag_manager_v2.log --label prod8080 --out <目錄>
"""

import argparse
import json
import re
import statistics as st
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_24combo import EXPECT, PIPES, fold, post, query_webui, questions  # noqa: E402

MODELS = ["llama3.1:8b", "qwen3:8b", "deepseek-r1:8b", "gemma4:12b", "qwen3:14b"]
ROUTE = "hybrid"
MAX_TOKENS = 512  # 只比較翻譯與換載；生成長度固定以縮短量測時間


def term_score(key, retrieval_query):
    groups = EXPECT[key]
    return sum(any(fold(v) in fold(retrieval_query) for v in g) for g in groups) / len(groups)


def last_translation(log_path, start):
    """讀 8001 日誌自 start 起新增的最後一筆「查詢翻譯（方式）完成，N ms」。"""
    with open(log_path, encoding="utf-8", errors="replace") as f:
        f.seek(start)
        found = re.findall(r"查詢翻譯（(\w+)）完成，([\d.]+) ms", f.read())
    return {"method": found[-1][0], "ms": float(found[-1][1])} if found else {}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default="http://127.0.0.1:8011")
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--webui", help="經 Open WebUI 提問（例 http://127.0.0.1:8080）")
    ap.add_argument("--key-file", help="Open WebUI API 金鑰檔")
    ap.add_argument("--log", help="8001 日誌（--webui 時讀翻譯方式）")
    args = ap.parse_args()
    api_key = Path(args.key_file).expanduser().read_text().strip() if args.webui else None
    PIPES[ROUTE] = f"system_{ROUTE}_rag_multi"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    qs, _ = questions()
    rows = []
    for i, (key, q) in enumerate(qs):
        model = MODELS[i % len(MODELS)]
        post(f"{args.api}/api/v1/cache/clear", {})
        t = time.time()
        log_pos = Path(args.log).stat().st_size if args.log else 0
        try:
            if args.webui:
                d = query_webui(args.webui, api_key, model, ROUTE, q)
                d["metadata"] = {"translation": last_translation(args.log, log_pos)}
            else:
                d = post(
                    f"{args.api}/api/v1/query",
                    {
                        "query": q,
                        "model_combination_id": f"{model}@{ROUTE}",
                        "max_results": 5,
                        "temperature": 0.1,
                        "max_tokens": MAX_TOKENS,
                    },
                )
            err = d.pop("error", None)
        except Exception as e:  # noqa: BLE001 -- 記錄後繼續
            d, err = {}, repr(e)[:200]
        tr = (d.get("metadata") or {}).get("translation") or {}
        rq = tr.get("retrieval_query")
        rows.append(
            {
                "label": args.label,
                "key": key,
                "model": model,
                "sec": round(time.time() - t, 2),
                "tr_method": tr.get("method"),
                "tr_ms": tr.get("ms"),
                "tr_model": tr.get("model"),
                "retrieval_query": rq,
                "terms": term_score(key, rq) if rq else None,
                "error": err,
            }
        )
        r = rows[-1]
        print(
            f"[{args.label}] {key} {model:15} {r['tr_method']} {r['tr_ms']} ms "
            f"總 {r['sec']} 秒 術語 {r['terms']}",
            flush=True,
        )
    (out / f"{args.label}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    fb = sum(1 for r in rows if r["tr_method"] == "fallback")
    scored = [r["terms"] for r in rows if r["terms"] is not None]
    terms = st.mean(scored) if scored else float("nan")
    med, avg = st.median(r["sec"] for r in rows), st.mean(r["sec"] for r in rows)
    errors = sum(1 for r in rows if r["error"])
    print(
        f"\n[{args.label}] 退回詞典 {fb}/{len(rows)}；術語 {terms:.3f}；"
        f"總耗時中位數 {med:.1f} 秒、平均 {avg:.1f} 秒；錯誤 {errors}"
    )


if __name__ == "__main__":
    main()
