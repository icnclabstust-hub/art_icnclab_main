"""回答中的畫家譯名統一為台灣顯示名（規格 Q1）。

- 顯示名：display_overrides.json（人工表，使用者 2026-10-16 決定，最優先）→ display_names.json
  （自建表 → 國教院視覺藝術名詞 → Wikidata zh-tw／zh-hant／zh＋s2twp）。
- 替換對象：artist_aliases.json 中 ≥ 3 個漢字、只屬於一位畫家的中文別名；最長優先、不重疊。
- 不替換（使用者 2026-10-16 規則）：
  1. 可接受寫法（人工表 accepted，例如「維拉斯奎茲」「維米爾」）
  2. 所在人名已包含顯示名或可接受寫法（「巴勃羅·畢卡索」「迪亞哥·維拉斯奎茲」；
     「拉斐爾·聖齊奧」不會變「拉斐爾·拉斐爾」）
  3. 使用者提問中用的寫法（回答跟提問用同一個字）
- 開關 DISPLAY_NAMES=1（呼叫時讀取）；串流逐句、/query 整段套用。
- 繁簡混用（2026-10-18）：模型常寫「委拉斯開兹」（兹＝簡體），比對前以 display_char_fold.json
  （scripts/build_display_char_fold.py）逐字轉繁、長度不變；替換寫回原文位置，其餘字元不動。
"""

import json
import os
import re
from pathlib import Path

_HERE = Path(__file__).parent
_CJK = re.compile(r"[一-鿿]")
_NAME_CHARS = re.compile(r"[一-鿿·・．.]")  # 人名範圍（含間隔號）
_table: tuple[re.Pattern, dict[str, str], dict[str, set[str]]] | None = None
_fold: dict[int, str] | None = None


def _fold_table() -> dict[int, str]:
    """簡體字 → 繁體字（str.translate 用）；檔案不存在時為空表（只比對原字）。"""
    global _fold
    if _fold is None:
        path = _HERE / "display_char_fold.json"
        try:
            pairs = json.loads(path.read_text(encoding="utf-8"))["fold"]
            _fold = str.maketrans({k: v for k, v in pairs.items() if len(k) == len(v) == 1})
        except (OSError, KeyError, ValueError):
            _fold = {}
    return _fold


def enabled() -> bool:
    return os.getenv("DISPLAY_NAMES", "0") == "1"


def _build() -> tuple[re.Pattern, dict[str, str], dict[str, set[str]]]:
    """回傳 (比對式, 別名 → 替換結果, 別名 → 該畫家顯示名＋可接受寫法)；替換結果等於自己＝保護。

    別名、顯示名、可接受寫法一律先逐字轉繁（_fold_table），與 normalize 轉繁後的文字比對。
    """
    fold = _fold_table()
    aliases = json.loads((_HERE / "artist_aliases.json").read_text(encoding="utf-8"))
    display = json.loads((_HERE / "display_names.json").read_text(encoding="utf-8"))["畫家"]
    over_path = _HERE / "display_overrides.json"
    overrides = json.loads(over_path.read_text(encoding="utf-8")) if over_path.exists() else {}
    owners: dict[str, set[str]] = {}
    for a in aliases["artists"]:
        for al in a["aliases"]:
            if al["type"] != "en":
                owners.setdefault(al["alias"].translate(fold), set()).add(a["qid"])
    mapping: dict[str, str] = {}
    shown_of: dict[str, set[str]] = {}
    for a in aliases["artists"]:
        over = overrides.get(a["name_en"]) or {}
        shown = over.get("display") or (display.get(a["name_en"]) or {}).get("display")
        if not shown:
            continue
        keeps = {k.translate(fold) for k in {shown, *(over.get("accepted") or [])}}
        for keep in keeps:  # 顯示名與可接受寫法：整段保護
            mapping[keep] = keep
            shown_of[keep] = keeps
        for al in a["aliases"]:
            alias = al["alias"].translate(fold)
            if (
                al["type"] == "en"
                or len(_CJK.findall(alias)) < 3
                or owners.get(alias) != {a["qid"]}
            ):
                continue
            if alias in mapping:
                continue
            # 已含顯示名或可接受寫法的全名（「迪亞哥·維拉斯奎茲」）整段保護、不改短
            protected = any(k in alias or alias in k for k in keeps)
            mapping[alias] = alias if protected else shown
            shown_of[alias] = keeps
    pattern = re.compile("|".join(re.escape(k) for k in sorted(mapping, key=len, reverse=True)))
    return pattern, mapping, shown_of


def _name_span(text: str, start: int, end: int) -> str:
    """比中位置所在的整個人名（向兩側延伸漢字與間隔號，最多各 12 字）。"""
    left = start
    while left > 0 and start - left < 12 and _NAME_CHARS.match(text[left - 1]):
        left -= 1
    right = end
    while right < len(text) and right - end < 12 and _NAME_CHARS.match(text[right]):
        right += 1
    return text[left:right]


def normalize(text: str, question: str | None = None) -> str:
    """把回答中的畫家別名換成台灣顯示名；question＝使用者原問題（其中用到的寫法不替換）。"""
    global _table
    if _table is None:
        try:
            _table = _build()
        except (OSError, KeyError, ValueError):
            _table = (re.compile(r"(?!x)x"), {}, {})
    pattern, mapping, shown_of = _table
    if not mapping:
        return text
    fold = _fold_table()
    folded = text.translate(fold)  # 逐字轉繁、長度不變：比對位置即原文位置
    used = {m.group(0) for m in pattern.finditer(question.translate(fold))} if question else set()

    out, last = [], 0
    for m in pattern.finditer(folded):
        alias = m.group(0)
        target = mapping[alias]
        span = _name_span(folded, m.start(), m.end())
        rest = span.replace(alias, "", 1)
        keep = (
            target == alias
            or alias in used
            or any(k in rest for k in shown_of[alias])  # 所在人名已含顯示名或可接受寫法
        )
        out.append(text[last : m.start()])
        out.append(text[m.start() : m.end()] if keep else target)
        last = m.end()
    out.append(text[last:])
    return "".join(out)
