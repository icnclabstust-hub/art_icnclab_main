"""惡意內容掃描器：僅用確定性規則偵測提示注入樣式、隱藏字元與異常文字。

命中即隔離（quarantined），由人工複審；不引入模型，避免掃描本身成為新的攻擊面。
規則清單放在 ``scan_rules.json``，新增規則不必改程式。
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

RULES_PATH = Path(__file__).with_name("scan_rules.json")

# 只標記「能藏指令或欺騙顯示」的不可見字元，不整類封鎖 Cf：軟連字號（U+00AD）、
# ZWNJ／ZWJ（U+200C／U+200D，波斯文與印度系文字必用）、LRM／RLM（U+200E／U+200F）都是正常文本，
# 曾在真實館藏資料（Yale）上因此誤判。
SUSPICIOUS_HIDDEN_CHARS = frozenset(
    [0x180E, 0x200B, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0xFEFF]  # 零寬／不可見運算符
    + list(range(0x202A, 0x202F))  # 雙向嵌入與覆寫
    + list(range(0x2066, 0x206A))  # 雙向隔離
    + list(range(0xE0000, 0xE0080))  # Unicode 標籤字元（可用來夾帶 ASCII 指令）
)
# 位元組順序記號 U+FEFF 偶爾殘留於字串開頭，僅在其他位置出現才算可疑。
ALLOWED_LEADING_CHARS = {"\ufeff"}

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
    return any(ord(ch) in SUSPICIOUS_HIDDEN_CHARS for ch in body)


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
