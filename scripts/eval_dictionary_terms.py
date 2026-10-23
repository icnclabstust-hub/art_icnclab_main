#!/usr/bin/env python3
"""詞典翻譯的術語正確率（離線，不經 API、不生成）：第 2 層完成標準 #7（≥ 0.85、0 誤譯）。

30 題（巴洛克 15＋理論 15）逐題以 MultilingualQueryTranslator 做詞典翻譯（換載模型時
使用者實際拿到的翻譯），術語正確率＝eval_24combo.EXPECT 各組至少命中一個變體的比例。
同時列出每題的替換（原文 -> 英文），供人工檢查誤譯。

用法：
    python scripts/eval_dictionary_terms.py [擴充詞典.json] [輸出.json]
不給擴充詞典時用線上預設（langchain-rag/art_terms_extended.json）。
"""

import json
import os
import statistics as st
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "langchain-rag"))


def main():
    if len(sys.argv) > 1:
        os.environ["QUERY_TERMS_EXTENDED"] = str(Path(sys.argv[1]).resolve())
    from eval_24combo import EXPECT, fold, questions  # noqa: PLC0415
    from multilingual_query_translator import MultilingualQueryTranslator  # noqa: PLC0415

    tr = MultilingualQueryTranslator(str(REPO / "art_history_terms_dictionary.json"))
    rows = []
    for key, q in questions()[0]:
        out, found = tr.translate_terms(q)
        groups = EXPECT[key]
        hit = [any(fold(v) in fold(out) for v in g) for g in groups]
        rows.append(
            {
                "key": key,
                "score": sum(hit) / len(groups),
                "missed": [g for g, h in zip(groups, hit, strict=True) if not h],
                "replacements": found,
                "query": out,
            }
        )
    score = st.mean(r["score"] for r in rows)
    print(f"術語正確率 {score:.3f}（{len(rows)} 題；索引 {len(tr.term_index)} 詞條）")
    for r in rows:
        if r["missed"]:
            print(f"  {r['key']:4} {r['score']:.2f} 缺 {r['missed']}")
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(
            json.dumps({"score": score, "rows": rows}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
