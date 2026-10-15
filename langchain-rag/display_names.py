"""回答中的畫家譯名統一為台灣顯示名（規格 Q1；顯示表 display_names.json，2026-10-14 建置）。

- 對照：artist_aliases.json 中同一位畫家的中文別名 → display_names.json「畫家」的 display
  （順序：自建台灣譯名表 → 國教院視覺藝術名詞 → Wikidata zh-tw → zh-hant → zh＋s2twp）。
- 只替換 ≥ 3 個漢字、只屬於一位畫家、且不是顯示名一部分的別名（避免「拉斐爾」這類短名誤換）；
  最長優先、不重疊。
- 開關 DISPLAY_NAMES=1（呼叫時讀取）；串流於 sentence_hook 逐句套用，/query 套用整段回答。
"""

import json
import os
import re
from pathlib import Path

_HERE = Path(__file__).parent
_CJK = re.compile(r"[一-鿿]")
_table: tuple[re.Pattern, dict[str, str]] | None = None


def enabled() -> bool:
    return os.getenv("DISPLAY_NAMES", "0") == "1"


def _build() -> tuple[re.Pattern, dict[str, str]]:
    aliases = json.loads((_HERE / "artist_aliases.json").read_text(encoding="utf-8"))
    display = json.loads((_HERE / "display_names.json").read_text(encoding="utf-8"))["畫家"]
    owners: dict[str, set[str]] = {}
    for a in aliases["artists"]:
        for al in a["aliases"]:
            if al["type"] != "en":
                owners.setdefault(al["alias"], set()).add(a["qid"])
    mapping: dict[str, str] = {}  # 別名 → 替換結果；值等於自己＝保護（整段比中但不改）
    for a in aliases["artists"]:
        shown = (display.get(a["name_en"]) or {}).get("display")
        if not shown:
            continue
        mapping[shown] = shown  # 顯示名本身受保護，避免其中片段被當成別名
        for al in a["aliases"]:
            alias = al["alias"]
            if (
                al["type"] == "en"
                or len(_CJK.findall(alias)) < 3
                or owners.get(alias) != {a["qid"]}
            ):
                continue
            # 含顯示名的全名（「李奧納多·達文西」含「達文西」）不改短，但要整段保護，
            # 否則其中的別名片段（「李奧納多」）會被單獨替換成「達文西·達文西」
            mapping[alias] = alias if (shown in alias or alias in shown) else shown
    pattern = re.compile("|".join(re.escape(k) for k in sorted(mapping, key=len, reverse=True)))
    return pattern, mapping


def normalize(text: str) -> str:
    """把回答中的畫家別名換成台灣顯示名；表不存在或為空時原樣回傳。"""
    global _table
    if _table is None:
        try:
            _table = _build()
        except (OSError, KeyError, ValueError):
            _table = (re.compile(r"(?!x)x"), {})
    pattern, mapping = _table
    if not mapping:
        return text
    return pattern.sub(lambda m: mapping[m.group(0)], text)
