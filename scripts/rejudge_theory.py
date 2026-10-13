#!/usr/bin/env python3
"""以新版理論題黃金集（2026-10-13）重判既有評估的理論題回答（覆蓋／矛盾），不重新生成。

原因：10-08 版 claims 誤含 15 個假主張（見 docs/decision-log.md 2026-10-13），舊覆蓋率分母錯誤，
且假主張被判 covered 的部分無法事後分離。裁判與提示同 scripts/eval_24combo.py（gemma4:12b）。
注意：Q3、Q5、Q10 題目文字已改動，舊回答是針對舊題目寫的，解讀時須註明。

用法（WSL）：
    python3 scripts/rejudge_theory.py <評估目錄> [--runs 2]
輸出：<評估目錄>/rejudge-2026-10-13/run{k}_theory.jsonl、summary.json；可中斷續跑。
"""

import argparse
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_24combo import MODELS, ROUTES, judge_run, load_rows, questions  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("eval_dir")
    ap.add_argument("--runs", type=int, default=2)
    args = ap.parse_args()
    src = Path(args.eval_dir)
    out = src / "rejudge-2026-10-13"
    out.mkdir(exist_ok=True)
    _, claims = questions()
    total = sum(len(v) for v in claims.values())
    for k in range(1, args.runs + 1):
        rows = [r for r in load_rows(src / f"run{k}.jsonl") if r["key"].startswith("T")]
        judge_run(rows, claims, {}, out / f"run{k}_theory.jsonl")
        print(f"第{k}次重判完成：{len(rows)} 個回答", flush=True)

    scored = [r for k in range(1, args.runs + 1) for r in load_rows(out / f"run{k}_theory.jsonl")]
    table = []
    for m in MODELS:
        for rt in ROUTES:
            rs = [r for r in scored if r["model"] == m and r["route"] == rt]
            if not rs:
                continue
            per_run = {}
            for k in sorted({r["run"] for r in rs}):
                x = [r for r in rs if r["run"] == k]
                per_run[k] = (
                    sum(r["cov"].get("covered", 0) for r in x) / total,
                    sum(r["cov"].get("contradicted", 0) for r in x),
                )
            table.append(
                {
                    "combo": f"{m}@{rt}",
                    "cov": st.mean(v[0] for v in per_run.values()),
                    "cov_runs": [round(v[0], 3) for v in per_run.values()],
                    "contra": st.mean(v[1] for v in per_run.values()),
                }
            )
    summary = {"total_claims": total, "table": table}
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"\n理論覆蓋（新版 A／B 主張 {total} 個；{args.runs} 次平均）")
    for t in sorted(table, key=lambda t: -t["cov"]):
        print(f"{t['combo']:26}{t['cov']:>7.1%}  {t['cov_runs']}  矛盾 {t['contra']:.1f}")


if __name__ == "__main__":
    main()
