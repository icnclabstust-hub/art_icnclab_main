#!/usr/bin/env python3
"""守門員 128 句分層盲標匯出（規格 #15 Q6）。

- 來源：8080 評估逐句忠實度（logs/eval/8080-2026-10-09/faith_run1.jsonl，裁判 gemma4:12b）
- 分層：裁判判「無依據」64 句＋「有依據」64 句（矛盾併入無依據層）；固定亂數種子，可重現
- 證據：以同題、同「模型@路由」向 8001 /api/v1/retrieve 重取 5 份來源全文（唯讀）
- 盲標：試算表不含裁判判斷、模型、路由；每列只有編號、問題、句子、證據、標註欄。
  對照答案另存 <輸出>_key.json（標完才開啟）
- 匯出後由學生標註：有依據／無依據／無法判斷；2 週後重標 20–30 句；兩位學生重疊約 30 句

用法（py311_venv）：python scripts/guard_blind_export.py <輸出.xlsx>
"""

import json
import random
import sys
import urllib.request
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "logs/eval/8080-2026-10-09/faith_run1.jsonl"
PER_STRATUM = 64
SEED = 20261014


def retrieve(model, route, q):
    body = json.dumps(
        {"query": q, "model_combination_id": f"{model}@{route}", "max_results": 5}
    ).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8001/api/v1/retrieve", body, {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=600) as r:  # noqa: S310 -- 固定本機位址
        d = json.load(r)
    return "\n\n".join(
        f"【來源 {i}】{(s.get('metadata') or {}).get('title') or ''}\n{(s.get('content') or '')[:1500]}"  # noqa: E501 -- 輸出訊息字串
        for i, s in enumerate(d["sources"], 1)
    )


def main():
    out = Path(sys.argv[1])
    sys.path.insert(0, str(REPO / "scripts"))
    from eval_24combo import questions  # noqa: PLC0415

    qtext = dict(questions()[0])
    pool = {"unsupported": [], "supported": []}
    for line in open(SRC, encoding="utf-8"):
        r = json.loads(line)
        for s, v in zip(r["sentences"], r["verdicts"], strict=True):
            layer = (
                "supported"
                if v == "supported"
                else "unsupported"
                if v in ("unsupported", "contradicted")
                else None
            )
            if layer and len(s) >= 10:
                pool[layer].append(
                    {
                        "model": r["model"],
                        "route": r["route"],
                        "key": r["key"],
                        "sentence": s,
                        "judge": v,
                    }
                )
    rng = random.Random(SEED)  # noqa: S311 -- 抽樣用固定種子，非安全用途
    sample = []
    for layer in ("unsupported", "supported"):
        sample += [dict(x, stratum=layer) for x in rng.sample(pool[layer], PER_STRATUM)]
    rng.shuffle(sample)
    evidence = {}
    for x in sample:
        k = (x["model"], x["route"], x["key"])
        if k not in evidence:
            evidence[k] = retrieve(x["model"], x["route"], qtext[x["key"]])
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "盲標"
    ws.append(
        [
            "編號",
            "問題",
            "待判句子",
            "檢索到的證據（只能依此判斷）",
            "標註（有依據／無依據／無法判斷）",
            "備註",
        ]
    )
    for c in ws[1]:
        c.font = Font(bold=True)
    key = {}
    for i, x in enumerate(sample, 1):
        sid = f"S{i:03d}"
        ws.append(
            [
                sid,
                qtext[x["key"]],
                x["sentence"],
                evidence[(x["model"], x["route"], x["key"])],
                "",
                "",
            ]
        )
        key[sid] = {k: x[k] for k in ("model", "route", "key", "judge", "stratum")}
    for col, w in zip("ABCDEF", (8, 40, 50, 90, 22, 20), strict=True):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    guide = wb.create_sheet("標註說明")
    for line in [
        "目的：檢查回答中的每一句，是否能由「檢索到的證據」支持。",
        "有依據：證據明確寫了這句的內容（換句話說、翻譯也算）。",
        "無依據：證據沒有寫，或只寫了一部分（例如年代對、作者錯）。即使你知道這句是對的，證據沒寫就是無依據。",
        "無法判斷：句子不是事實陳述（例如客套話、建議），或證據過長無法確認。",
        "只能依本列的證據判斷，不可查網路或用自己的知識。",
        "請勿查看其他工作表或對照答案檔；標完後交回。",
    ]:
        guide.append([line])
    guide.column_dimensions["A"].width = 110
    wb.save(out)
    out.with_name(out.stem + "_key.json").write_text(
        json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(
        f"匯出 {len(sample)} 句（無依據層 {PER_STRATUM}、有依據層 {PER_STRATUM}）→ {out}；對照答案 → {out.stem}_key.json"  # noqa: E501 -- 輸出訊息字串
    )


if __name__ == "__main__":
    main()
