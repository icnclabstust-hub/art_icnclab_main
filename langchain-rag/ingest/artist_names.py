"""作者字串解析：把各來源的作者欄位拆成「一人一個名字」。

設計：docs/designs/2026-10-18-graph-data-quality.md D2。

各來源逗號意義不同，不能一律以逗號切開（E29：片段名字 1,618／3,261）：
- V&A「Feure, Georges de」＝姓, 名；
  芝加哥「Salvador Dalí⏎Spanish, 1904–1989」＝名字＋國籍、生卒年；
  大都會「Anonymous, British, 19th century」＝佚名；
  克里夫蘭「Sandro Botticelli, Workshop」＝名字＋角色；
  Europeana／specialized 夾雜 URI、「姓, 名 (年份)」、希臘文重複；只有 Google Books 是多位作者。

規則：
1. 有換行取第一行；去 URI、角色註記（「. Auteur du texte」）、年份；括號內是人名
   （「Perugino (Pietro di Cristoforo Vannucci)」）保留，其餘括號去掉
2. 「|」「;」一定分隔不同人；再以逗號分段，去掉國籍、世紀、角色詞（Workshop）、頭銜（MBE、Mrs）；
   已有拉丁字母寫法時去掉純希臘文等重複寫法
3. 「姓, 名」合併（含 & 的公司名、Google Books、兩段都像全名時不合併）；去重；
   Anonymous／Unknown／Unidentified／Unbekannt／onbekend 視為無作者
"""

import re

NATIONALITY = {
    "american", "british", "english", "french", "dutch", "flemish", "italian", "german",
    "spanish", "japanese", "chinese", "austrian", "belgian", "swiss", "russian", "czech",
    "danish", "swedish", "norwegian", "irish", "scottish", "greek", "hungarian", "polish",
    "portuguese", "mexican", "canadian", "netherlandish", "bohemian", "korean", "indian",
    "persian", "egyptian", "roman", "venetian", "florentine", "sienese", "european",
    "byzantine", "islamic",
}  # fmt: skip
ROLE = {
    "workshop", "studio", "school", "follower", "circle", "manner", "attributed", "after",
    "copy", "possibly", "probably", "designer", "maker", "manufacturer", "publisher",
    "printer", "engraver", "author", "artist", "photographer", "editor",
}  # fmt: skip
HONORIFIC = {
    "mbe",
    "obe",
    "cbe",
    "frss",
    "ra",
    "rws",
    "frs",
    "mrs",
    "mr",
    "miss",
    "sir",
    "dame",
    "dr",
}
PARTICLES = {
    "de",
    "da",
    "di",
    "del",
    "della",
    "van",
    "von",
    "der",
    "den",
    "le",
    "la",
    "du",
    "ter",
    "y",
}
FILLER = {"active", "and", "in", "of", "or"}
# 書籍作者以逗號分隔多人，不做「姓, 名」合併
MULTI_AUTHOR_SOURCES = {"google_books"}

NOBODY = re.compile(
    r"^(anonym\w*|unknown\w*( artist| maker| photographer)?|unidentified( artist)?|n/?a|various"
    r"|unbekannt\w*( fotograf)?|onbekend|inconnu|ignoto)$",
    re.IGNORECASE,
)
YEARS = re.compile(
    r"\b(born|died|d\.|b\.|ca?\.)?\s*(1[0-9]{3}|20[0-9]{2})\s*[-–]?\s*(1[0-9]{3}|20[0-9]{2})?\b-?"
)
URI = re.compile(r"https?://\S+")
PAREN = re.compile(r"\s*[(（]([^)）]*)[)）]")
ROLE_SUFFIX = re.compile(r"\.\s*(auteur|author|illustrat|éditeur|editor|photograph)[^,]*", re.I)
LATIN = re.compile(r"[A-Za-zÀ-ɏḀ-ỿ]")
NONLATIN = re.compile(r"[Ͱ-ϿЀ-ӿ֐-ۿ一-鿿]")
PERSON_SEP = re.compile(r"\s*[|;]\s*")


def _junk(seg: str) -> bool:
    """不是人名的分段：佚名、年份、世紀、國籍、角色詞、頭銜。"""
    low = seg.lower().strip(" .")
    if not low or NOBODY.match(low):
        return True
    if re.search(r"\d", low) or "century" in low or low.startswith("active"):
        return True
    words = set(re.findall(r"[a-z]+", low))
    return bool(words) and words <= NATIONALITY | ROLE | HONORIFIC | FILLER


def _paren(m: re.Match) -> str:
    """括號內是人名就保留（藝名 (本名)），年份、角色、國籍等括號去掉。"""
    inner = m.group(1).strip()
    caps = [w for w in re.findall(r"[A-Za-zÀ-ɏ]+", inner) if w[0].isupper()]
    if not re.search(r"\d", inner) and len(caps) >= 2 and not _junk(inner):
        return m.group(0)
    return ""


def _given_like(seg: str) -> bool:
    """「名」段：1～3 個字，首字大寫或為連接詞（de、van）。"""
    toks = seg.split()
    return 1 <= len(toks) <= 3 and all(t[0].isupper() or t.lower() in PARTICLES for t in toks)


def _segments(text: str, multi: bool) -> list[str]:
    # 句點保留（「& Co.」「Ltd.」是名字的一部分）；年份去掉後留下的連字號、空白去掉
    segs = [YEARS.sub("", x).strip(" ;-") for x in text.split(",")]
    segs = [" ".join(t for t in x.split() if t.lower().strip(".()") not in HONORIFIC) for x in segs]
    segs = [x for x in segs if x and not _junk(x)]
    # 同時有拉丁字母寫法時，去掉純希臘文等重複寫法；多作者來源的中文作者是不同人，不去掉
    if not multi and any(LATIN.search(x) for x in segs):
        segs = [x for x in segs if LATIN.search(x) or not NONLATIN.search(x)]
    return segs


def _merge_surname_first(segs: list[str], multi: bool) -> list[str]:
    names, i = [], 0
    while i < len(segs):
        a = segs[i]
        b = segs[i + 1] if i + 1 < len(segs) else None
        if (
            not multi
            and b is not None
            and "&" not in a
            and "&" not in b
            and len(a.split()) <= 2
            and _given_like(b)
            and not (len(a.split()) >= 2 and len(b.split()) >= 2)  # 兩段都像全名＝兩個人
        ):
            names.append(f"{b} {a}")
            i += 2
        else:
            names.append(a)
            i += 1
    return names


def parse_artists(source: str, raw: str | None) -> list[str]:
    """作者字串 → 人名清單（依出現順序、去重；佚名回傳空清單）。"""
    if not raw:
        return []
    text = raw.split("\n")[0]
    text = PAREN.sub(_paren, ROLE_SUFFIX.sub("", URI.sub("", text)))
    out: list[str] = []
    for part in PERSON_SEP.split(text):
        multi = source in MULTI_AUTHOR_SOURCES
        for name in _merge_surname_first(_segments(part, multi), multi):
            name = re.sub(r"\s+", " ", name).strip()
            if name and not NOBODY.match(name) and name not in out:
                out.append(name)
    return out
