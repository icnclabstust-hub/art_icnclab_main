#!/usr/bin/env python3
"""8080 評估的忠實度（暫定）：回答中每一句是否有檢索來源支持。

8080 只回傳回答與來源標題，取不到來源內文；本腳本以同一問題、同一「模型@路由」向 8001
``/api/v1/retrieve`` 重新檢索（只檢索、不生成），取回 5 份來源內文，再由裁判逐句判斷：
- supported：來源支持此句
- unsupported：來源沒有提到（可能是模型自己的知識或編造）
- contradicted：來源內容與此句矛盾

忠實度＝supported 句數／判斷句數（NFR-13 只計有來源的層；分層回答尚未上線，整個回答都算）。
拒答句（「檢索結果中沒有找到…」之類）不是事實陳述，不列入判斷，另計拒答數。

限制（報告須註明）：
- 裁判 gemma4:12b 未經人工驗證（NFR-13 要求 κ ≥ 0.7，128 句盲標待完成），結果為「暫定」。
- 重新檢索不保證與當時完全相同（翻譯逾時 3 秒時改用詞典）；以「重取來源與當時引用標題的重疊率」
  檢查，重疊率低的組合解讀時要保留。

用法（WSL 內）：
    python3 scripts/eval_faithfulness_8080.py --run 1
可中斷續跑。
"""

import argparse
import json
import os
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_24combo import (  # noqa: E402
    MODELS,
    OLLAMA,
    ROUTES,
    load_rows,
    post,
    wait_for_night_window,
)

REPO = Path(__file__).resolve().parent.parent
JUDGE = "gemma4:12b"
DOC_CHARS = int(os.getenv("FAITH_DOC_CHARS", "900"))  # 每份來源截斷長度（預設 900，5 份約 4,500 字）
REFUSAL = re.compile(r"沒有找到|找不到|無法回答|無法提供|並未包含|沒有相關|未包含|未提及|沒有提到")
FAITH_PROMPT = """你是嚴格的審稿人。以下是檢索到的「來源」與一段「回答」的編號句子。
逐句判斷該句內容是否能由來源支持：
- supported：來源有寫（換句話說、翻譯成中文也算）
- unsupported：來源沒有提到
- contradicted：來源寫的與此句矛盾
只依來源判斷，不要用你自己的知識。

來源：
{sources}

句子：
{sentences}

只輸出 JSON 陣列，依句子編號順序，例如 ["supported","unsupported"]"""


def sentences(answer):
    """依句號、問號、驚嘆號與換行切句；去掉 markdown 符號與過短片段。"""
    parts = re.split(r"(?<=[。！？!?])|\n+", answer)
    out = []
    for p in parts:
        p = re.sub(r"^[\s#>*\-•\d.、]+", "", p or "").strip()
        if len(p) >= 6:
            out.append(p)
    return out


def retrieve(api, model, route, query):
    d = post(
        f"{api}/api/v1/retrieve",
        {"query": query, "model_combination_id": f"{model}@{route}", "max_results": 5},
    )
    docs = []
    for s in d.get("sources", []):
        md = s.get("metadata", {}) or {}
        docs.append(
            {
                "title": md.get("title") or md.get("name") or "",
                "content": str(s.get("content", ""))[:DOC_CHARS],
            }
        )
    return docs


def judge(docs, sents):
    src = "\n\n".join(f"[{i}] {d['title']}\n{d['content']}" for i, d in enumerate(docs, 1))
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(sents, 1))
    j = post(
        OLLAMA,
        {
            "model": JUDGE,
            "prompt": FAITH_PROMPT.format(sources=src or "（無）", sentences=numbered),
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_predict": 16 * len(sents) + 40},
        },
    )
    text = j["response"].strip().strip("`").removeprefix("json").strip()
    try:
        verdicts = json.loads(text[text.index("[") : text.rindex("]") + 1])
    except ValueError:
        return ["?"] * len(sents)
    verdicts = [v if v in ("supported", "unsupported", "contradicted") else "?" for v in verdicts]
    return (verdicts + ["?"] * len(sents))[: len(sents)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default="http://127.0.0.1:8001")
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--out", default=str(REPO / "logs" / "eval" / "8080-2026-10-09"))
    args = ap.parse_args()
    out_dir = Path(args.out)
    qs = dict(
        (f"B{q['no']}", q["question"])
        for q in json.load(
            open(REPO / "docs/golden-set/2026-10-01-baroque-questions.json", encoding="utf-8")
        )["questions"]
    )
    qs.update(
        (f"T{b['no']}", b["question"])
        for b in json.load(
            open(REPO / "docs/golden-set/2026-10-08-theory15-claims.json", encoding="utf-8")
        )
    )
    rows = load_rows(out_dir / f"run{args.run}.jsonl")
    scored_path = out_dir / f"faith_run{args.run}.jsonl"
    done = {(r["model"], r["route"], r["key"]) for r in load_rows(scored_path)}
    with open(scored_path, "a", encoding="utf-8") as f:
        for i, r in enumerate(rows, 1):
            k = (r["model"], r["route"], r["key"])
            if k in done or r.get("error"):
                continue
            wait_for_night_window()
            docs = retrieve(args.api, r["model"], r["route"], qs[r["key"]])
            sents = sentences(r["answer"])
            refusals = [s for s in sents if REFUSAL.search(s)]
            claims = [s for s in sents if not REFUSAL.search(s)]
            verdicts = judge(docs, claims) if claims else []
            cited = r.get("cited_titles") or []
            got = {d["title"] for d in docs}
            row = {
                "model": r["model"],
                "route": r["route"],
                "key": r["key"],
                "n_sent": len(claims),
                "n_refusal": len(refusals),
                "verdicts": verdicts,
                "sentences": claims,
                "overlap": sum(t in got for t in cited) / len(cited) if cited else None,
                "retrieved_titles": sorted(got),
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            if i % 30 == 0:
                print(f"{i}/{len(rows)} {r['model']}@{r['route']}", flush=True)
    summarize(load_rows(scored_path), out_dir / f"faith_summary_run{args.run}.json")


def summarize(rows, path):
    def stats(rs):
        v = [x for r in rs for x in r["verdicts"]]
        judged = [x for x in v if x != "?"]
        per_answer = [
            sum(x == "supported" for x in r["verdicts"]) / len(r["verdicts"])
            for r in rs
            if r["verdicts"]
        ]
        ov = [r["overlap"] for r in rs if r["overlap"] is not None]
        return {
            "faithfulness": sum(x == "supported" for x in judged) / max(len(judged), 1),
            "unsupported": sum(x == "unsupported" for x in judged) / max(len(judged), 1),
            "contradicted": sum(x == "contradicted" for x in judged) / max(len(judged), 1),
            "answers_ge80": sum(p >= 0.8 for p in per_answer) / max(len(per_answer), 1),
            "sentences": len(judged),
            "unparsed": len(v) - len(judged),
            "refusal_only": sum(1 for r in rs if not r["verdicts"] and r["n_refusal"]),
            "overlap": statistics.mean(ov) if ov else None,
        }

    by_combo, by_model = defaultdict(list), defaultdict(list)
    for r in rows:
        by_combo[f"{r['model']}@{r['route']}"].append(r)
        by_model[r["model"]].append(r)
    table = {
        "combos": {
            c: stats(by_combo[c])
            for c in (f"{m}@{rt}" for m in MODELS for rt in ROUTES)
            if c in by_combo
        },
        "models": {m: stats(by_model[m]) for m in MODELS if m in by_model},
    }
    path.write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"\n{'模型／組合':26}{'忠實度':>7}{'無依據':>7}{'矛盾':>6}{'≥80%回答':>9}{'句數':>6}{'重疊':>6}"
    )
    for name, t in list(table["models"].items()) + sorted(
        table["combos"].items(), key=lambda kv: -kv[1]["faithfulness"]
    ):
        ov = f"{t['overlap']:.0%}" if t["overlap"] is not None else "-"
        print(
            f"{name:26}{t['faithfulness']:>7.1%}{t['unsupported']:>7.1%}{t['contradicted']:>6.1%}"
            f"{t['answers_ge80']:>9.0%}{t['sentences']:>6}{ov:>6}"
        )


if __name__ == "__main__":
    main()
