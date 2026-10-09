#!/usr/bin/env python3
"""24 組合評估：6 個 LLM × 4 個系統路由，同模型 RAG＋LLM（翻譯與生成用同一模型）。

使用者 2026-10-09 決定（docs/decision-log.md 同日條目）：30 題（巴洛克黃金集 15＋「15題」理論題 15）
× 每組合 3 次；評估專用實例把翻譯逾時放寬到 60 秒（線上維持 3 秒），避開 03:00～03:40 夜間流程。

量測（每次 run 生成完畢後統一評分，評分模型只載入一次）：
- 事實題（巴洛克 1～6）：答案是否含館藏記錄的關鍵事實（年代、材質）
- 關係題（巴洛克 7～12）：引用文件中屬於該藝術家的比例（規則判定，artist 欄位，見限制）
- 理論題（15 題）：A／B 級參考主張的覆蓋與矛盾（裁判 gemma4:12b）
- 翻譯：檢索用查詢的術語正確率、方法（llm_hinted／fallback／dictionary）與耗時
- 每題總時間、生成失敗數

限制：關係題相關性為規則判定（artist 欄位含藝術家名），Europeana 中 artist 為攝影者的紀錄會被誤判；
理論題裁判未經人工驗證（NFR-13 要求 κ ≥ 0.7）。正式基準以人工黃金集為準。

用法（WSL 內，評估實例須已在 --api 運作）：
    python3 scripts/eval_24combo.py --api http://127.0.0.1:8011 --runs 3
    python3 scripts/eval_24combo.py --summary-only   # 只重算彙總
可中斷續跑：已完成的（run, 模型, 路由, 題號）會略過。
"""

import argparse
import datetime as dt
import json
import statistics
import subprocess
import time
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GOLDEN = REPO / "docs" / "golden-set"
MODELS = ["llama3.1:8b", "qwen3:8b", "deepseek-r1:8b", "gemma4:12b", "qwen3:14b", "gpt-oss:20b"]
ROUTES = ["vector", "fulltext", "graph", "hybrid"]
OLLAMA = "http://127.0.0.1:11434/api/generate"
JUDGE = "gemma4:12b"
NIGHT_START, NIGHT_END = dt.time(2, 55), dt.time(3, 40)

FACT_KEYS = {
    1: [["1642"], ["油", "oil"]],
    2: [["1665"]],
    3: [["1656"]],
    4: [["1599", "1600"]],
    5: [["1612", "1614"], ["木板", "板上", "panel"]],
    6: [["大理石", "marble"]],
}
# 檢索用查詢應出現的英文術語（任一變體即算）
EXPECT = {
    "B1": [["Rembrandt"], ["Night Watch"], ["medium", "material"]],
    "B2": [["Vermeer"], ["Girl with a Pearl Earring"]],
    "B3": [["Velázquez", "Velazquez"], ["Las Meninas"]],
    "B4": [["Caravaggio"], ["Calling of St", "Calling of Saint"]],
    "B5": [["Rubens"], ["Descent from the Cross", "Deposition"], ["medium", "material"]],
    "B6": [["Bernini"], ["Bacchanal"], ["faun"]],
    "B7": [["Metropolitan"], ["Vermeer"]],
    "B8": [["Rembrandt"], ["portrait"]],
    "B9": [["Velázquez", "Velazquez"], ["royal"], ["portrait"]],
    "B10": [["Poussin"], ["mytholog"]],
    "B11": [["Claude Lorrain"], ["landscape"]],
    "B12": [["Carracci"], ["religious"]],
    "B13": [["Gentileschi"], ["Judith"], ["Holofernes"]],
    "B14": [["Borromini"], ["Quattro Fontane"], ["plan", "floor"]],
    "B15": [["Bernini"], ["Ecstasy of Saint Teresa", "Ecstasy of St"], ["chapel"]],
    "T1": [
        ["cathedral works", "cathedral workshop", "fabbriceria", "works office", "opera del duomo"]
    ],
    "T2": [["figura"], ["Church Fathers", "patristic"], ["Early Renaissance"]],
    "T3": [["disegno"], ["drawing"]],
    "T4": [["Riegl"], ["Kunstwollen"], ["Panofsky"], ["Sedlmayr"], ["Pächt", "Pacht"]],
    "T5": [["Leonardo"], ["sfumato"], ["Botticelli"], ["Codex Atlanticus", "Atlantic Codex"]],
    "T6": [
        ["Medici Bank"],
        ["double-entry"],
        ["Poggio Bracciolini"],
        ["Brunelleschi"],
        ["San Lorenzo"],
    ],
    "T7": [
        ["alchem"],
        ["distill"],
        ["Netherlandish", "Flemish"],
        ["Van Eyck"],
        ["refractive index"],
    ],
    "T8": [["Michelangelo"], ["Sistine"], ["prophet"], ["sibyl"], ["Vasari"]],
    "T9": [["colorito"], ["Venetian"], ["Rubens"], ["altarpiece"]],
    "T10": [["Isabella d"], ["grotesque", "grottesche"], ["studiolo"], ["Vasari"]],
    "T11": [
        ["Wölfflin", "Wolfflin"],
        ["School of Athens"],
        ["Night Watch"],
        ["Counter-Reformation"],
    ],
    "T12": [
        ["School of Athens"],
        ["Plato"],
        ["Aristotle"],
        ["gesture"],
        ["rationalism"],
        ["empiricism"],
    ],
    "T13": [["fresco"], ["Raphael"], ["Titian"], ["oil"], ["scattering"]],
    "T14": [["Michelangelo"], ["Moses"], ["David"], ["terribilità", "terribilita"]],
    "T15": [
        ["Ilkhanid", "Ilkhanate", "Il-Khanid"],
        ["miniature"],
        ["Mediterranean"],
        ["Trecento"],
        ["altarpiece"],
    ],
}
COV_PROMPT = """判斷「回答」是否表達了「參考主張」的內容（換句話說也算）。
- covered：回答有表達此主張
- contradicted：回答說了與此主張矛盾的內容
- missing：回答沒有提到
參考主張：{c}
回答：{a}
只輸出 JSON：{{"verdict": "covered|contradicted|missing"}}"""


def post(url, body, timeout=1800):
    req = urllib.request.Request(  # noqa: S310 -- 固定本機位址
        url, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 -- 固定本機位址
        return json.load(r)


def fold(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def questions():
    baroque = json.load(open(GOLDEN / "2026-10-01-baroque-questions.json", encoding="utf-8"))[
        "questions"
    ]
    theory = json.load(open(GOLDEN / "2026-10-08-theory15-claims.json", encoding="utf-8"))
    qs = [(f"B{q['no']}", q["question"]) for q in baroque] + [
        (f"T{b['no']}", b["question"]) for b in theory
    ]
    claims = {f"T{b['no']}": [c["text"] for c in b["claims"] if c["grade"] in "AB"] for b in theory}
    return qs, claims


def wait_for_night_window():
    """夜間流程（03:00 起，備份會停 Neo4j）期間暫停。"""
    while NIGHT_START <= dt.datetime.now().time() < NIGHT_END:
        time.sleep(60)


def load_rows(path):
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def generate_run(api, run, qs, out):
    done = {(r["model"], r["route"], r["key"]) for r in load_rows(out)}
    with open(out, "a", encoding="utf-8") as f:
        for model in MODELS:  # 模型放最外層：同一模型的 4 路由×30 題連續跑，模型只載入一次
            for route in ROUTES:
                start = time.time()
                for key, q in qs:
                    if (model, route, key) in done:
                        continue
                    wait_for_night_window()
                    post(f"{api}/api/v1/cache/clear", {})
                    t = time.time()
                    try:
                        d = post(
                            f"{api}/api/v1/query",
                            {
                                "query": q,
                                "model_combination_id": f"{model}@{route}",
                                "max_results": 5,
                                "temperature": 0.1,
                                "max_tokens": 2048,
                            },
                        )
                        err = None
                    except Exception as e:  # 單題失敗記錄後繼續
                        d, err = {"answer": "", "citations": [], "metadata": {}}, repr(e)[:300]
                    tr = (d.get("metadata") or {}).get("translation") or {}
                    row = {
                        "run": run,
                        "model": model,
                        "route": route,
                        "key": key,
                        "sec": round(time.time() - t, 2),
                        "answer": d.get("answer", ""),
                        "cited": [c.get("external_id") for c in d.get("citations", [])],
                        "retrieval_query": tr.get("retrieval_query", q),
                        "tr_method": tr.get("method"),
                        "tr_ms": tr.get("ms"),
                        "error": err,
                        "at": dt.datetime.now().isoformat(timespec="seconds"),
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f.flush()
                elapsed = time.time() - start
                stamp = f"{dt.datetime.now():%m-%d %H:%M}"
                print(f"[{stamp}] 第{run}次 {model}@{route} 完成（{elapsed:.0f}s）", flush=True)


def judge_run(rows, claims, relevant, scored_path):
    scored = {(r["model"], r["route"], r["key"]): r for r in load_rows(scored_path)}
    with open(scored_path, "a", encoding="utf-8") as f:
        for r in rows:
            if (r["model"], r["route"], r["key"]) in scored:
                continue
            no, kind = int(r["key"][1:]), r["key"][0]
            if kind == "B" and no in FACT_KEYS:
                r["fact"] = sum(
                    any(k.lower() in r["answer"].lower() for k in g) for g in FACT_KEYS[no]
                ) / len(FACT_KEYS[no])
            if kind == "B" and str(no) in relevant:
                rel = set(relevant[str(no)])
                r["rel"] = sum(c in rel for c in r["cited"]) / max(len(r["cited"]), 1)
            if kind == "T":
                c = Counter()
                for claim in claims[r["key"]]:
                    if not r["answer"]:
                        c["missing"] += 1
                        continue
                    j = post(
                        OLLAMA,
                        {
                            "model": JUDGE,
                            "prompt": COV_PROMPT.format(c=claim, a=r["answer"][:4000]),
                            "stream": False,
                            "think": False,
                            "options": {"temperature": 0, "num_predict": 60},
                        },
                    )
                    try:
                        c[
                            json.loads(j["response"].strip().strip("`").removeprefix("json")).get(
                                "verdict", "?"
                            )
                        ] += 1
                    except Exception:
                        c["?"] += 1
                r["cov"] = dict(c)
            r["terms"] = sum(
                any(fold(v) in fold(r["retrieval_query"]) for v in g) for g in EXPECT[r["key"]]
            ) / len(EXPECT[r["key"]])
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()


def summarize(out_dir, runs, claims):
    total_claims = sum(len(v) for v in claims.values())
    rows = [r for k in range(1, runs + 1) for r in load_rows(out_dir / f"run{k}_scored.jsonl")]
    table = []
    for model in MODELS:
        for route in ROUTES:
            rs = [r for r in rows if r["model"] == model and r["route"] == route]
            if not rs:
                continue
            per_run = {}
            for k in sorted({r["run"] for r in rs}):
                x = [r for r in rs if r["run"] == k]
                per_run[k] = {
                    "fact": statistics.mean(r["fact"] for r in x if "fact" in r),
                    "rel": statistics.mean(r["rel"] for r in x if "rel" in r),
                    "cov": sum(r["cov"].get("covered", 0) for r in x if "cov" in r) / total_claims,
                    "contra": sum(r["cov"].get("contradicted", 0) for r in x if "cov" in r),
                }
            runs_done = list(per_run.values())

            def mean(metric, runs_done=runs_done):
                return statistics.mean(v[metric] for v in runs_done)

            table.append(
                {
                    "combo": f"{model}@{route}",
                    "runs": len(per_run),
                    "fact": mean("fact"),
                    "rel": mean("rel"),
                    "cov": mean("cov"),
                    "cov_runs": [round(v["cov"], 3) for v in per_run.values()],
                    "contra": mean("contra"),
                    "terms": statistics.mean(r["terms"] for r in rs),
                    "fallback": sum(1 for r in rs if r["tr_method"] == "fallback"),
                    "tr_ms_median": statistics.median(
                        [r["tr_ms"] for r in rs if r["tr_ms"]] or [0]
                    ),
                    "sec_median": statistics.median(r["sec"] for r in rs),
                    "errors": sum(1 for r in rs if r["error"]),
                }
            )
    (out_dir / "summary.json").write_text(
        json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"\n=== 24 組合彙總（{runs} 次平均；理論題覆蓋＝A／B 主張 {total_claims} 個中的比例）===")
    print(
        f"{'組合':26}{'事實':>6}{'關係':>6}{'理論覆蓋':>9}{'矛盾':>6}{'術語':>6}{'退回':>5}{'翻譯ms':>8}{'每題秒':>7}{'錯誤':>5}"
    )
    for t in sorted(table, key=lambda t: -t["cov"]):
        print(
            f"{t['combo']:26}{t['fact']:>6.0%}{t['rel']:>6.0%}{t['cov']:>9.1%}{t['contra']:>6.1f}{t['terms']:>6.0%}"
            f"{t['fallback']:>5}{t['tr_ms_median']:>8.0f}{t['sec_median']:>7.1f}{t['errors']:>5}"
        )


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default="http://127.0.0.1:8011")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", default=str(REPO / "logs" / "eval" / "24combo-2026-10-09"))
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    qs, claims = questions()
    relevant = json.load(open(GOLDEN / "2026-10-09-relation-rule-relevant.json", encoding="utf-8"))
    if not args.summary_only:
        meta = out_dir / "meta.json"
        if not meta.exists():
            git = ["git", "-C", str(REPO), "rev-parse", "HEAD"]
            sha = subprocess.run(git, capture_output=True, text=True).stdout.strip()  # noqa: S603, S607
            meta.write_text(
                json.dumps(
                    {
                        "started": dt.datetime.now().isoformat(),
                        "commit_sha": sha,
                        "api": args.api,
                        "models": MODELS,
                        "routes": ROUTES,
                        "runs": args.runs,
                        "judge": JUDGE,
                        "questions": len(qs),
                    },
                    ensure_ascii=False,
                    indent=1,
                ),
                encoding="utf-8",
            )
        for run in range(1, args.runs + 1):
            gen_path = out_dir / f"run{run}.jsonl"
            generate_run(args.api, run, qs, gen_path)
            print(f"[{dt.datetime.now():%m-%d %H:%M}] 第{run}次評分中…", flush=True)
            judge_run(load_rows(gen_path), claims, relevant, out_dir / f"run{run}_scored.jsonl")
            summarize(out_dir, run, claims)
    else:
        summarize(out_dir, args.runs, claims)


if __name__ == "__main__":
    main()
