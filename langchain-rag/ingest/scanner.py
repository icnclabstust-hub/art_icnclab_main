"""惡意內容掃描器：僅用確定性規則偵測提示注入樣式、隱藏字元與異常文字。

命中即隔離（quarantined），由人工複審；不引入模型，避免掃描本身成為新的攻擊面。
規則清單放在 ``scan_rules.json``，新增規則不必改程式。
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

RULES_PATH = Path(__file__).with_name("scan_rules.json")

# Cf（格式控制字元）涵蓋零寬字元與雙向控制字元，藝術史文本正常內容不會用到。
HIDDEN_CHAR_CATEGORIES = {"Cf"}
# 位元組順序記號 U+FEFF 屬 Cf，但偶爾殘留於字串開頭，僅在其他位置出現才算可疑。
ALLOWED_LEADING_CHARS = {"﻿"}

SYMBOL_RATIO_MIN_LENGTH = 200
SYMBOL_RATIO_THRESHOLD = 0.6


@dataclass(frozen=True)
class ScanResult:
    """掃描結果。

    Attributes:
        rules: 命中的規則名稱（依出現順序、不重複）。
    """

    rules: tuple[str, ...]

    @property
    def clean(self) -> bool:
        """沒有命中任何規則。"""
        return not self.rules


def load_rules(path: Path = RULES_PATH) -> list[tuple[str, re.Pattern[str]]]:
    """載入並編譯規則檔。

    Args:
        path: 規則 JSON 檔路徑。

    Returns:
        ``(規則名稱, 編譯後 regex)`` 清單。
    """
    with open(path, encoding="utf-8") as f:
        raw_rules = json.load(f)
    return [(rule["name"], re.compile(rule["pattern"])) for rule in raw_rules]


def _has_hidden_chars(text: str) -> bool:
    body = text.lstrip("".join(ALLOWED_LEADING_CHARS))
    return any(unicodedata.category(ch) in HIDDEN_CHAR_CATEGORIES for ch in body)


def _mostly_symbols(text: str) -> bool:
    if len(text) < SYMBOL_RATIO_MIN_LENGTH:
        return False
    symbols = sum(1 for ch in text if not (ch.isalnum() or ch.isspace()))
    return symbols / len(text) > SYMBOL_RATIO_THRESHOLD


def scan_artwork(
    artwork: dict, rules: list[tuple[str, re.Pattern[str]]] | None = None
) -> ScanResult:
    """掃描一筆正規化後的作品資料的所有字串欄位。

    Args:
        artwork: ``normalize_*`` 產出的 dict。
        rules: 已編譯規則；省略時載入預設規則檔。

    Returns:
        命中規則的 ``ScanResult``（未命中則 ``clean`` 為 True）。
    """
    compiled = rules if rules is not None else load_rules()
    hits: list[str] = []

    def add(name: str) -> None:
        if name not in hits:
            hits.append(name)

    for value in artwork.values():
        if not isinstance(value, str) or not value:
            continue
        for name, pattern in compiled:
            if pattern.search(value):
                add(name)
        if _has_hidden_chars(value):
            add("hidden_characters")
        if _mostly_symbols(value):
            add("mostly_symbols")
    return ScanResult(rules=tuple(hits))
