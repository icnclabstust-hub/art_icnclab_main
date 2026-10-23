#!/usr/bin/env python3
"""Q10 音譯模糊比對的門檻校準（規格：pypinyin 去聲調＋rapidfuzz，暫定門檻 85）。

設計：docs/designs/2026-10-14-layer2-completion-plan.md；規格書 #12/#13（Q10）
測試集（不用 LLM、可重現）：
- 正例（未見過的譯名變體）：artist_aliases.json 中每位畫家的台灣繁體別名，逐一「留一」——把該別名
  從比對表拿掉，看它能否以拼音模糊比對找回同一位畫家（模擬使用者寫了詞典沒收的譯名）
- 負例（詞典外的畫家）：OUT_OF_TABLE 中 20 位不在別名表的畫家常見台灣譯名，應「不命中」
指標：各門檻下正例找回率（且找回的是對的人）、錯配數、負例誤中率。

用法：python scripts/eval_fuzzy_names.py langchain-rag/artist_aliases.json
"""

import json
import re
import sys
from collections import defaultdict

from pypinyin import lazy_pinyin
from rapidfuzz import fuzz

# 不在別名表的畫家（常見台灣譯名），用來量誤中
OUT_OF_TABLE = [
    "哥雅",
    "杜勒",
    "馬奈",
    "塞尚",
    "高更",
    "克林姆",
    "席勒",
    "莫迪里亞尼",
    "達利",
    "馬諦斯",
    "康丁斯基",
    "蒙德里安",
    "波洛克",
    "安迪沃荷",
    "霍克尼",
    "秀拉",
    "雷諾瓦",
    "羅丹",
    "米勒",
    "夏卡爾",
]
CJK = re.compile(r"[一-鿿]")


def py(s):
    """去聲調拼音，去掉間隔號與空白。"""
    return "".join(lazy_pinyin(re.sub(r"[·・\s]", "", s)))


def best_match(name, table):
    """回傳 (分數, 畫家)。table：[(別名, 畫家)]。"""
    p = py(name)
    scored = [(fuzz.ratio(p, py(a)), who) for a, who in table]
    return max(scored) if scored else (0, None)


def main():
    artists = json.load(open(sys.argv[1], encoding="utf-8"))["artists"]
    table = [
        (a["alias"], x["name_en"])
        for x in artists
        for a in x["aliases"]
        if a["type"] != "en" and a.get("tw") and len(CJK.findall(a["alias"])) >= 2
    ]
    by_artist = defaultdict(list)
    for alias, who in table:
        by_artist[who].append(alias)
    pos = []
    for who, aliases in by_artist.items():
        if len(aliases) < 2:
            continue
        for a in aliases:
            rest = [(x, w) for x, w in table if x != a]
            score, got = best_match(a, rest)
            pos.append((a, who, score, got))
    neg = [(n, *best_match(n, table)) for n in OUT_OF_TABLE]
    print(
        f"正例（留一譯名變體）{len(pos)} 個、負例（詞典外畫家）{len(neg)} 個；比對表 {len(table)} 個別名"  # noqa: E501 -- 輸出訊息字串
    )
    print(f"{'門檻':>4} {'找回且正確':>10} {'錯配':>6} {'負例誤中':>8}")
    for th in (70, 75, 80, 85, 90, 95):
        ok = sum(1 for _, who, s, got in pos if s >= th and got == who)
        wrong = sum(1 for _, who, s, got in pos if s >= th and got != who)
        fp = sum(1 for _, s, _ in neg if s >= th)
        print(f"{th:>4} {ok:>5}/{len(pos)} ({ok / len(pos):5.1%}) {wrong:>6} {fp:>4}/{len(neg)}")
    print("\n負例最高分（越高越容易誤中）：")
    for n, s, got in sorted(neg, key=lambda x: -x[1])[:6]:
        print(f"  {n} → {got} {s:.0f}")
    print("錯配例（分數 ≥ 80）：")
    for a, who, s, got in sorted(pos, key=lambda x: -x[2]):
        if got != who and s >= 80:
            print(f"  {a}（{who}）→ {got} {s:.0f}")


if __name__ == "__main__":
    main()
