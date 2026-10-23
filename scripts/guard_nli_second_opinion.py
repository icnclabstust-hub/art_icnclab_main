#!/usr/bin/env python3
"""守門員第二意見：mDeBERTa NLI（ONNX int8，CPU）判定 128 句盲標樣本，與 gemma 裁判比對。

依據：規格書 #15（Q6）。
- 模型：MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7（MIT）；id2label 0=entailment
- 證據切窗：每窗約 350 token（tokenizer 以前提＋假設截斷到 512），每句取各窗 entailment 機率最大值
- 比對：以 gemma 裁判（supported vs 非 supported）為參照，報 entailment 分數 AUROC、
  門檻 0.5 時一致率與 Cohen's κ、每句 CPU 延遲。
  人工盲標完成前，這只是「兩個自動裁判彼此一致的程度」，不代表誰對。

證據模式（第 4 個參數，2026-10-14 使用者要求「館藏條列改寫成自然文句」）：
- raw：原樣，約 350 token 切窗（第一版）
- natural：每個來源以固定模板改寫成英文自然句、一個來源一窗；去掉 id／source／url、
  捐贈說明（Purchase…／Gift of…／Bequest…）與「相關關係」清單中的重複資訊
- natural_clean：natural＋假設句去掉引用標記（[文件 1]、根據參考資料…）
- natural_zh：natural_clean，模板改為中文（英文欄位值不翻譯）
改寫用固定模板、不用 LLM，避免改寫時捏造證據。

用法（py311_venv）：
    python scripts/guard_nli_second_opinion.py <盲標.xlsx> <模型資料夾> <輸出.json> [模式]
"""

import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import openpyxl
from tokenizers import Tokenizer

WINDOW_TOKENS = 350
CREDIT = re.compile(
    r"^(Purchase|Gift|Bequest|Rogers Fund|.*Fund.*\d{4}$|.*Collection, Bequest)", re.I
)
FIELDS = {
    "title": "title",
    "實體": "title",
    "creator": "creator",
    "date": "date",
    "medium": "medium",
    "culture": "culture",
    "period": "period",
    "description": "description",
}


def parse_sources(evidence):
    """把「【來源 n】…」區塊拆成欄位 dict；HELD_BY／CREATED 關係補作館藏與作者。"""
    out = []
    for block in re.split(r"【來源 \d+】", evidence or "")[1:]:
        f = {}
        for line in block.splitlines():
            m = re.match(r"\s*-\s*(HELD_BY|CREATED)\s*->\s*(.+)", line)
            if m:
                f.setdefault(
                    "held_by" if m.group(1) == "HELD_BY" else "creator", m.group(2).strip()
                )
                continue
            k, sep, v = line.partition(":")
            k = FIELDS.get(k.strip().lower()) or FIELDS.get(k.strip())
            if sep and k and v.strip():
                f.setdefault(k, v.strip())
        if f.get("description") and CREDIT.match(f["description"]):
            del f["description"]  # 捐贈說明不是作品內容
        out.append(f)
    return out


def sentence_en(f):
    t = f.get("title", "This work")
    parts = [f"'{t}' is a work" + (f" by {f['creator']}" if f.get("creator") else "")]
    if f.get("date"):
        parts.append(f"created in {f['date']}")
    if f.get("medium"):
        parts.append(f"made with {f['medium'].rstrip('.')}")
    s = ", ".join(parts) + "."
    if f.get("period") or f.get("culture"):
        s += (
            " It belongs to "
            + " ".join(x for x in (f.get("culture"), f.get("period")) if x)
            + " art."
        )
    if f.get("held_by"):
        s += f" It is held by {f['held_by']}."
    return s + (f" {f['description']}" if f.get("description") else "")


def sentence_zh(f):
    t = f.get("title", "此作品")
    s = f"《{t}》是" + (f"{f['creator']}的" if f.get("creator") else "") + "作品"
    if f.get("date"):
        s += f"，創作於 {f['date']}"
    if f.get("medium"):
        s += f"，媒材為 {f['medium'].rstrip('.')}"
    s += "。"
    if f.get("period") or f.get("culture"):
        s += "屬於 " + " ".join(x for x in (f.get("culture"), f.get("period")) if x) + " 藝術。"
    if f.get("held_by"):
        s += f"收藏於 {f['held_by']}。"
    return s + (f"說明：{f['description']}" if f.get("description") else "")


def clean_hypothesis(h):
    h = re.sub(
        r"[\[［【(（]\s*(文件|來源|文檔|資料|Document|Source)\s*\d+[^\]］】)）]*[\]］】)）]", "", h
    )
    h = re.sub(
        r"^(根據|依據|依照)(參考|所提供的|提供的|檢索到的)?(資料|文件|文檔|來源)[^，,]*[，,]\s*",
        "",
        h,
    )
    return h.strip() or h


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def auroc(pos, neg):
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def main():
    sheet, model_dir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    mode = sys.argv[4] if len(sys.argv) > 4 else "raw"
    key = json.loads(sheet.with_name(sheet.stem + "_key.json").read_text(encoding="utf-8"))
    sess = ort.InferenceSession(
        str(model_dir / "onnx" / "model_quantized.onnx"), providers=["CPUExecutionProvider"]
    )
    names = {i.name for i in sess.get_inputs()}
    tok = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
    win_tok = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
    tok.enable_truncation(max_length=512)
    rows = []
    for sid, _q, sentence, evidence, *_ in openpyxl.load_workbook(sheet, read_only=True)[
        "盲標"
    ].iter_rows(min_row=2, values_only=True):
        if mode == "raw":
            ids = win_tok.encode(evidence or "").ids
            windows = [
                win_tok.decode(ids[i : i + WINDOW_TOKENS])
                for i in range(0, max(len(ids), 1), WINDOW_TOKENS)
            ] or [""]
        else:
            render = sentence_zh if mode == "natural_zh" else sentence_en
            windows = [render(f) for f in parse_sources(evidence)] or [evidence or ""]
            if mode != "natural":
                sentence = clean_hypothesis(sentence)
        t = time.perf_counter()
        enc = tok.encode_batch([(w, sentence) for w in windows])
        width = max(len(e.ids) for e in enc)
        feed = {
            "input_ids": np.array(
                [e.ids + [0] * (width - len(e.ids)) for e in enc], dtype=np.int64
            ),
            "attention_mask": np.array(
                [e.attention_mask + [0] * (width - len(e.ids)) for e in enc], dtype=np.int64
            ),
        }
        if "token_type_ids" in names:
            feed["token_type_ids"] = np.zeros_like(feed["input_ids"])
        logits = sess.run(None, feed)[0]
        prob = np.exp(logits - logits.max(axis=1, keepdims=True))
        prob /= prob.sum(axis=1, keepdims=True)
        ent = float(prob[:, 0].max())
        rows.append(
            {
                "sid": sid,
                "entail": ent,
                "contra": float(prob[:, 2].max()),
                "windows": len(windows),
                "ms": (time.perf_counter() - t) * 1000,
                "judge": key[sid]["judge"],
            }
        )
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    judge = [int(r["judge"] == "supported") for r in rows]
    nli = [int(r["entail"] >= 0.5) for r in rows]
    pos = [r["entail"] for r, j in zip(rows, judge, strict=True) if j]
    neg = [r["entail"] for r, j in zip(rows, judge, strict=True) if not j]
    agree = sum(a == b for a, b in zip(judge, nli, strict=True)) / len(rows)
    ms = np.array([r["ms"] for r in rows])
    print(
        f"[{mode}] 128 句：NLI entailment 分數對 gemma 裁判的 AUROC {auroc(pos, neg):.3f}；門檻 0.5 一致率 {agree:.1%}、"  # noqa: E501 -- 輸出訊息字串
        f"Cohen's κ {kappa(judge, nli):.3f}"
    )
    print(
        f"NLI 判有依據 {sum(nli)}／128；裁判判有依據 {sum(judge)}／128；平均每句 {np.mean([r['windows'] for r in rows]):.1f} 窗、"  # noqa: E501 -- 輸出訊息字串
        f"延遲 p50 {np.percentile(ms, 50):.0f} ms／p95 {np.percentile(ms, 95):.0f} ms"
    )
    both_no = sum(1 for a, b in zip(judge, nli, strict=True) if a == 0 and b == 0)
    print(f"兩者都判無依據（規格第 3 階段『重新生成』的觸發條件）：{both_no} 句")


if __name__ == "__main__":
    main()
