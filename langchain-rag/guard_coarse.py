"""同步粗篩（規格 GRD-06、06b）：逐句檢查答案中的「錨點」是否出現在檢索來源。

只做本地字面比對、不呼叫任何模型（GRD-06b）。答案多為中文而來源多為英文，一般詞彙
重疊無法跨語言比對，所以只取與語言無關的錨點：

- 數字（兩位數以上，例如年代 1642、尺寸 363）
- 拉丁字母詞（例如 Rembrandt、Night、Kloveniers），排除英文虛詞

錨點全部出現在來源 → supported；全部不在 → unsupported；部分 → partial；沒有錨點的句子
→ no_anchor（粗篩無法判斷，留給非同步精篩 GRD-07）。粗篩抓得到「編造的名稱或年代」，
抓不到「名稱正確但描述錯誤」（例如把民兵連說成消防隊），後者屬精篩範圍。
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?；;])|\n+|(?<=[.])\s+")
MARKDOWN_NOISE = re.compile(r"[*#>`_|]+|^\s*(?:[-•]|\d+[.)、])\s*")
NUMBER = re.compile(r"\d{2,}")
# 館藏常把年代區間寫成縮寫（c. 1915–26），答案則寫完整年份 1926；比對前先補出完整年份
SHORT_YEAR_RANGE = re.compile(r"(?<!\d)(\d{2})(\d{2})\s*[–—-]\s*(\d{2})(?!\d)")
LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]{2,}")
MIN_SENTENCE_CHARS = 4

STOPWORDS = frozenset(
    """the and for are was were with from that this these those which who whom whose what
    when where how its his her their our your has have had not but all any can could would
    should may might will shall into onto over under than then there here also such very
    more most much many some one two out about after before between during through while
    being been does did done just only other same own too off per via""".split()
)


@dataclass
class SentenceCheck:
    """單句的粗篩結果。"""

    text: str
    anchors: list[str]
    found: list[str]

    @property
    def status(self) -> str:
        """``supported``／``partial``／``unsupported``／``no_anchor``。"""
        if not self.anchors:
            return "no_anchor"
        if len(self.found) == len(self.anchors):
            return "supported"
        return "partial" if self.found else "unsupported"


@dataclass
class CoarseResult:
    """整份答案的粗篩結果（只有彙總數值會被記錄，句子原文不落地）。"""

    sentences: list[SentenceCheck] = field(default_factory=list)

    def count(self, status: str) -> int:
        return sum(1 for s in self.sentences if s.status == status)

    @property
    def n_anchored(self) -> int:
        return sum(1 for s in self.sentences if s.anchors)

    @property
    def anchor_hit_rate(self) -> float | None:
        """所有錨點中出現在來源的比例；沒有任何錨點時為 None。"""
        total = sum(len(s.anchors) for s in self.sentences)
        if not total:
            return None
        return sum(len(s.found) for s in self.sentences) / total

    def summary(self) -> dict:
        """供回應 metadata 與影子紀錄使用的彙總數值。"""
        rate = self.anchor_hit_rate
        return {
            "n_sentences": len(self.sentences),
            "n_anchored": self.n_anchored,
            "n_supported": self.count("supported"),
            "n_partial": self.count("partial"),
            "n_unsupported": self.count("unsupported"),
            "anchor_hit_rate": round(rate, 4) if rate is not None else None,
        }


def split_sentences(text: str) -> list[str]:
    """依中英文句末標點與換行切句，去掉 markdown 標記與過短片段。"""
    sentences = []
    for piece in SENTENCE_SPLIT.split(text):
        cleaned = MARKDOWN_NOISE.sub(" ", piece or "").strip()
        if len(cleaned) >= MIN_SENTENCE_CHARS:
            sentences.append(cleaned)
    return sentences


def extract_anchors(sentence: str) -> list[str]:
    """取出句中的數字與拉丁字母詞（去重、保留出現順序，英文虛詞不算）。"""
    anchors: list[str] = []
    for token in NUMBER.findall(sentence) + LATIN_WORD.findall(sentence):
        normalized = token.strip("'’-").lower()
        if len(normalized) < 2 or normalized in STOPWORDS or normalized in anchors:
            continue
        anchors.append(normalized)
    return anchors


def check_answer(answer: str, source_texts: Iterable[str]) -> CoarseResult:
    """逐句比對答案錨點與來源文字（大小寫不敏感、以詞為界）。

    Args:
        answer: 模型產生的答案。
        source_texts: 送進生成的各來源內容。

    Returns:
        ``CoarseResult``。
    """
    corpus = "\n".join(source_texts).lower()
    expanded_years = [f"{m[1]}{m[3]}" for m in SHORT_YEAR_RANGE.finditer(corpus)]
    if expanded_years:
        corpus += "\n" + " ".join(expanded_years)
    result = CoarseResult()
    for sentence in split_sentences(answer):
        anchors = extract_anchors(sentence)
        found = [
            a for a in anchors if re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])", corpus)
        ]
        result.sentences.append(SentenceCheck(text=sentence, anchors=anchors, found=found))
    return result
