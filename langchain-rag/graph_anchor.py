"""圖譜檢索修復方案 A：畫家錨點＋固定 Cypher 模板＋依題型退回。

設計：docs/designs/2026-10-11-graph-retrieval-anchor.md
（M2 錨點器、M3 模板 T1／T2、M4 退回、M5 日誌）
- 錨點只在畫家別名上做完整字串比對，不碰主題、分類等節點；歧義別名在建表時已捨棄
- 模板只用規則選擇，不呼叫 LLM
- 別名表由 scripts/build_artist_aliases.py 離線建置（artist_aliases.json）
"""

import contextvars
import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ALIAS_PATH = Path(os.getenv("GRAPH_ALIAS_PATH", Path(__file__).with_name("artist_aliases.json")))
LOG_DIR = Path(
    os.getenv(
        "GRAPH_ANCHOR_LOG_DIR", Path(__file__).resolve().parent.parent / "logs" / "graph_anchor"
    )
)

# /query、/retrieve 設定的原始問題（檢索拿到的是翻譯後的英文，中文別名要比對原文）
ORIGINAL_QUERY: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "original_query", default=None
)

# T2：館名關鍵詞 → Institution.name（圖中作品數最多的三館）
MUSEUMS = {
    "大都會藝術博物館": "Metropolitan Museum of Art",
    "大都會博物館": "Metropolitan Museum of Art",
    "大都會": "Metropolitan Museum of Art",
    "metropolitan museum": "Metropolitan Museum of Art",
    "the met": "Metropolitan Museum of Art",
    "哈佛藝術博物館": "Harvard Art Museums",
    "哈佛": "Harvard Art Museums",
    "harvard": "Harvard Art Museums",
    "荷蘭國家博物館": "Rijksmuseum",
    "國家博物館（阿姆斯特丹）": "Rijksmuseum",
    "rijksmuseum": "Rijksmuseum",
}
# 作品排序時忽略的英文詞
STOP = {
    "what",
    "which",
    "when",
    "where",
    "does",
    "were",
    "with",
    "from",
    "that",
    "this",
    "work",
    "works",
    "painting",
    "paintings",
    "painted",
    "artist",
    "artwork",
    "artworks",
    "about",
    "have",
    "made",
    "collection",
    "museum",
    "held",
    "their",
    "there",
    "into",
    "material",
    "medium",
    "used",
}

_T1 = """
MATCH (a:Artist)-[c:CREATED]->(w:Artwork)
WHERE a.name IN $names AND c.valid_to IS NULL AND coalesce(w.is_deleted, false) = false
RETURN DISTINCT w AS artwork
"""
_T2 = """
MATCH (a:Artist)-[c:CREATED]->(w:Artwork)-[h:HELD_BY]->(i:Institution)
WHERE a.name IN $names AND i.name = $museum AND c.valid_to IS NULL AND h.valid_to IS NULL
  AND coalesce(w.is_deleted, false) = false
RETURN DISTINCT w AS artwork
"""


def _fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


_CJK = re.compile(r"[一-鿿]")
_CJK_RUN = re.compile(r"[一-鿿·・]{3,}")
_CJK_SEP = re.compile(r"[·・\s]")


def fuzzy_threshold() -> float | None:
    """GRAPH_FUZZY_NAMES＝模糊比對門檻（0～100）；未設定或 0＝不啟用。呼叫時讀取。"""
    value = os.getenv("GRAPH_FUZZY_NAMES", "").strip()
    return float(value) if value and float(value) > 0 else None


def fuzzy_margin() -> float:
    """GRAPH_FUZZY_MARGIN＝第一名與（不同畫家）第二名的最小分差，預設 5。呼叫時讀取。"""
    return float(os.getenv("GRAPH_FUZZY_MARGIN", "5") or 5)


@dataclass
class Anchor:
    qids: list[str] = field(default_factory=list)
    matched: list[dict[str, str]] = field(default_factory=list)  # [{qid, alias, type}]
    names: list[str] = field(default_factory=list)  # Neo4j Artist.name 集合

    @property
    def hit(self) -> bool:
        return bool(self.names)


class AliasTable:
    def __init__(self, path: Path = ALIAS_PATH):
        data = json.loads(path.read_text(encoding="utf-8"))
        self.artists = {a["qid"]: a for a in data["artists"]}
        self.zh: dict[str, set[str]] = {}
        self.en: dict[str, set[str]] = {}
        for qid, a in self.artists.items():
            for al in a["aliases"]:
                if al["type"] == "en":
                    self.en.setdefault(_fold(al["alias"]), set()).add(qid)
                else:
                    self.zh.setdefault(al["alias"], set()).add(qid)
        self.types = {
            (qid, al["alias"]): al["type"] for qid, a in self.artists.items() for al in a["aliases"]
        }
        self._fuzzy_index: list[tuple[str, set[str], str]] | None = None

    def anchor(self, original: str | None, retrieval_query: str) -> Anchor:
        """完整字串命中；較長的別名優先，被長別名覆蓋的短別名不計（避免『卡拉瓦喬』內的子字串誤中）。"""
        hits: list[tuple[int, int, str, set[str]]] = []
        if original:
            for alias, qids in self.zh.items():
                for m in re.finditer(re.escape(alias), original):
                    hits.append((m.start(), m.end(), alias, qids))
        folded = _fold(retrieval_query)
        offset = 10**6  # 英文命中與中文命中分開計位置，不互相覆蓋
        for alias, qids in self.en.items():
            for m in re.finditer(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", folded):
                hits.append((offset + m.start(), offset + m.end(), alias, qids))
        hits.sort(key=lambda h: (-(h[1] - h[0]), h[0]))
        taken: list[tuple[int, int]] = []
        result = Anchor()
        for start, end, alias, qids in hits:
            if any(start < e and s < end for s, e in taken):
                continue
            taken.append((start, end))
            for qid in sorted(qids):
                result.matched.append(
                    {"qid": qid, "alias": alias, "type": self.types.get((qid, alias), "en")}
                )
                if qid not in result.qids:
                    result.qids.append(qid)
        if not result.qids and original:
            threshold = fuzzy_threshold()
            if threshold:
                fuzzy = self.fuzzy_anchor(original, threshold)
                if fuzzy:
                    qid, alias, window, score = fuzzy
                    result.matched.append(
                        {
                            "qid": qid,
                            "alias": alias,
                            "type": "fuzzy",
                            "text": window,
                            "score": str(round(score, 1)),
                        }
                    )
                    result.qids.append(qid)
        for qid in result.qids:
            result.names += [n for n in self.artists[qid]["neo4j_names"] if n not in result.names]
        return result

    def fuzzy_anchor(self, original: str, threshold: float):
        """完整比對無命中時，以去聲調拼音模糊比對中文別名（規格 Q10，門檻由 GRAPH_FUZZY_NAMES）。

        只比對 ≥ 3 個漢字的別名（2 字名易與一般詞同音誤中），候選為原文中長度相近的連續漢字片段；
        最高分 ≥ 門檻、只屬於一位畫家，且比不同畫家的次高分多 GRAPH_FUZZY_MARGIN 分才採用。
        回傳 (qid, 別名, 原文片段, 分數) 或 None。依據：10-14 E2（門檻 90：0 錯配、找回 55.3%）。
        """
        from pypinyin import lazy_pinyin  # noqa: PLC0415 -- 只在啟用模糊比對時需要
        from rapidfuzz import fuzz  # noqa: PLC0415

        if self._fuzzy_index is None:
            self._fuzzy_index = [
                (alias, qids, "".join(lazy_pinyin(_CJK_SEP.sub("", alias))))
                for alias, qids in self.zh.items()
                if len(_CJK.findall(alias)) >= 3
            ]
        # 每位畫家（以別名的擁有者集合為單位）各自的最高分
        per_owner: dict[frozenset[str], tuple[float, str, str]] = {}
        for run in _CJK_RUN.findall(original):
            run = _CJK_SEP.sub("", run)
            char_py = lazy_pinyin(run)  # 一字一拼音；片段拼音以切片串接，不逐片段重算
            for alias, qids, alias_py in self._fuzzy_index:
                n = len(_CJK_SEP.sub("", alias))
                key = frozenset(qids)
                for size in (n - 1, n, n + 1):
                    for i in range(0, max(len(run) - size, -1) + 1):
                        window = run[i : i + size]
                        if len(window) < 3:
                            continue
                        score = fuzz.ratio("".join(char_py[i : i + size]), alias_py)
                        if key not in per_owner or score > per_owner[key][0]:
                            per_owner[key] = (score, alias, window)
        if not per_owner:
            return None
        ranked = sorted(per_owner.items(), key=lambda kv: -kv[1][0])
        (owners, (score, alias, window)) = ranked[0]
        second = ranked[1][1][0] if len(ranked) > 1 else 0.0
        # 差距規則（使用者 2026-10-16）：第一名須比不同畫家的第二名高出 GRAPH_FUZZY_MARGIN 分
        if score < threshold or len(owners) != 1 or score - second < fuzzy_margin():
            return None
        return next(iter(owners)), alias, window, score


def choose_template(original: str | None, retrieval_query: str) -> tuple[str, dict[str, Any]]:
    text = f"{original or ''} {retrieval_query}".lower()
    for key in sorted(MUSEUMS, key=len, reverse=True):
        if key in text:
            return "T2", {"museum": MUSEUMS[key]}
    return "T1", {}


def question_type(original: str | None) -> str:
    """退回路由依題型：問特定作品（有書名號）＝事實題，其餘＝關係題。"""
    return "fact" if original and "《" in original else "relation"


def rank_artworks(records: list, retrieval_query: str, limit: int) -> list:
    """同一畫家的作品依英文檢索句命中排序：標題命中權重 3，描述／媒材 1；同分依 id 穩定排序。"""
    words = {
        w[:-1] if w.endswith("s") and len(w) > 4 else w  # 複數去 s：portraits 對上 Portrait
        for w in re.findall(r"[a-z]{4,}", _fold(retrieval_query))
        if w not in STOP
    }

    def score(rec):
        w = rec["artwork"]
        title = _fold(str(w.get("title") or ""))
        rest = _fold(" ".join(str(w.get(k) or "") for k in ("description", "medium", "department")))
        return 3 * sum(x in title for x in words) + sum(x in rest for x in words)

    scored = [(score(r), str(r["artwork"].get("id") or ""), r) for r in records]
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [(s, r) for s, _, r in scored[:limit]]


def write_log(entry: dict[str, Any]) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / f"{time.strftime('%Y-%m-%d')}.jsonl", "a", encoding="utf-8") as f:
            f.write(
                json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **entry}, ensure_ascii=False)
                + "\n"
            )
    except OSError:
        pass  # 日誌失敗不影響檢索
