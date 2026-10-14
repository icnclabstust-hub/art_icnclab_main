#!/usr/bin/env python3
"""擴充查詢翻譯詞典（2026-10-13 故障點 F1：換載模型時使用者實際拿到的是詞典翻譯）。

設計：docs/designs/2026-10-13-sim10-fix-plan.md §四（量測結論：維持 3 秒逾時、改擴充詞典）
來源與過濾（系統性收錄，不依測試題的漏詞逐一補）：
1. 畫家：langchain-rag/artist_aliases.json（Wikidata，40 位）——只收台灣繁體（tw）全名／譯名／姓氏
2. 機構：圖譜中作品數最多的機構，以英文維基條目查 Wikidata 中文（台灣）標籤
3. Getty AAT（預設不收，見 AAT_FACETS 註解；BUILD_AAT=1 啟用）：五個 facet 的 zh-hant 首選標籤；
   **英文標籤須在本系統館藏文字出現 ≥ 3 次**（翻出來也查不到的詞不收）
4. 國教院樂詞網「視覺藝術名詞」（2026-10-14 A1；預設不收，BUILD_NAER=1 啟用評估）：
   同義詞以「；」拆開、去括號註記；英文須在館藏文字出現 ≥ 3 次。
   授權：政府網站資料開放宣告（應註明出處）
共同規則：中文至少 2 字；同一中文對應多個英文則捨棄；不覆寫原詞典（翻譯器載入時原詞典優先）。

用法（WSL）：
    python3 scripts/build_term_dictionary.py
輸出：langchain-rag/art_terms_extended.json（與 art_history_terms_dictionary.json 同格式）；
設 TERM_DICT_OUT 改寫到候選檔（評估用，不動線上詞典）
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "langchain-rag"))
from ingest.db import connect  # noqa: E402

OUT = Path(os.getenv("TERM_DICT_OUT", REPO / "langchain-rag" / "art_terms_extended.json"))
BUILD_NAER = os.getenv("BUILD_NAER", "0") == "1"  # 2026-10-14 A1：未達標，預設不收
ALIASES = REPO / "langchain-rag" / "artist_aliases.json"
BASE = REPO / "art_history_terms_dictionary.json"
UA = {"User-Agent": "ArtHistoryRAG-thesis/0.1 (academic; dictionary build)"}
# Getty AAT 暫不收錄（2026-10-14 驗證）：zh-hant 標籤缺西洋藝術史關鍵術語（altarpiece、fresco、
# chapel、Venetian、Trecento、miniature 皆無）、有語意錯配（medium→「中色」）、寫法與使用者不同
# （Netherlandish→「尼德蘭文化」），且「相關概念」多為泛用詞（雄性、數據、秋季），會切開複合詞
# （「禮拜堂」→ worship＋堂）。30 題術語正確率只 0.636→0.652。設 BUILD_AAT=1 可重新評估。
AAT_FACETS = (
    {
        "aat_styles_periods": "300264088",
        "aat_visual_works": "300191086",
        "aat_techniques": "300053001",
        "aat_materials": "300264091",
        "aat_concepts": "300264086",
    }
    if os.getenv("BUILD_AAT") == "1"
    else {}
)
MIN_CORPUS_HITS = 3
CJK = re.compile(r"[一-鿿]")
# 圖譜錨點的館名簡稱（graph_anchor.MUSEUMS）一併收錄
MUSEUM_SHORT = {
    "大都會": "Metropolitan Museum of Art",
    "大都會博物館": "Metropolitan Museum of Art",
}


def get_json(url, headers=None):
    for wait in (0, 5, 20, 60):
        time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})  # noqa: S310
            with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310 -- 固定 https 網址
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503):
                raise
    raise RuntimeError(f"重試用盡：{url[:80]}")


def corpus_text():
    """館藏文字（每個 chunk 最新一筆 upsert 事件的內文），轉小寫。"""
    with connect() as c:
        rows = c.execute(
            "SELECT DISTINCT ON (payload->>'external_id') op, payload->>'text'"
            " FROM catalog.sync_events WHERE entity_type = 'chunk'"
            " ORDER BY payload->>'external_id', event_id DESC"
        ).fetchall()
    return "\n".join(t for op, t in rows if op == "upsert" and t).lower()


def corpus_hits(text, term):
    return len(re.findall(rf"(?<![a-z]){re.escape(term.lower())}(?![a-z])", text))


def artists():
    data = json.loads(ALIASES.read_text(encoding="utf-8"))["artists"]
    out = {}
    for a in data:
        zh = [x["alias"] for x in a["aliases"] if x["type"] != "en" and x.get("tw")]
        if zh:
            out[a["name_en"]] = {"zh": sorted(set(zh))}
    return out


def institutions(top_n=30):
    from neo4j import GraphDatabase  # noqa: PLC0415

    drv = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    with drv.session() as s:
        names = [
            r["n"]
            for r in s.run(
                "MATCH (:Artwork)-[:HELD_BY]->(i:Institution) RETURN i.name AS n, count(*) AS c"
                " ORDER BY c DESC LIMIT $k",
                k=top_n,
            )
        ]
    drv.close()
    out = defaultdict(set)
    for name in names:
        q = urllib.parse.urlencode(
            {
                "action": "wbgetentities",
                "sites": "enwiki",
                "titles": name,
                "props": "labels|aliases",
                "languages": "zh-tw|zh-hant",
                "redirects": "yes",
                "format": "json",
            }
        )
        ent = next(iter(get_json(f"https://www.wikidata.org/w/api.php?{q}")["entities"].values()))
        time.sleep(0.5)
        if "missing" in ent:
            continue
        for lang in ("zh-tw", "zh-hant"):
            label = ent.get("labels", {}).get(lang, {}).get("value")
            if label:
                out[name].add(label)
            out[name] |= {a["value"] for a in ent.get("aliases", {}).get(lang, [])}
    for zh, en in MUSEUM_SHORT.items():
        out[en].add(zh)
    return {en: {"zh": sorted(v)} for en, v in out.items() if v}


def aat_facet(facet_id):
    """facet 下有 zh-hant 首選標籤的概念：{英文首選標籤: {中文標籤}}。

    不排序、不分頁、只取首選標籤：加上 ORDER BY／OFFSET／altLabel 時查詢超過 25 分鐘，
    單取首選標籤每個 facet 約 1～3 秒（2026-10-14 實測）。
    """
    sparql = f"""select ?en ?zh where {{
      ?c gvp:broaderExtended aat:{facet_id} ; xl:prefLabel ?zl .
      ?zl xl:literalForm ?zh . filter(lang(?zh) = "zh-hant")
      ?c gvp:prefLabelGVP/xl:literalForm ?en }}"""
    url = "https://vocab.getty.edu/sparql.json?" + urllib.parse.urlencode({"query": sparql})
    rows = get_json(url, {"Accept": "application/sparql-results+json"})["results"]["bindings"]
    concepts = defaultdict(set)
    for b in rows:
        concepts[b["en"]["value"]].add(b["zh"]["value"])
    return concepts


def naer_visual_arts(text):
    """國教院視覺藝術名詞：{英文: {"zh": [...]}}，英文須在館藏出現 ≥ MIN_CORPUS_HITS 次。

    兩條防誤譯規則（2026-10-14 A1 實測：「圖像」→ icon、「人文主義」被切成 人文 → humanities）：
    1. 歧義以 NAER 全表判定：同一中文對應多個英文（圖像＝graphics／icon）即不收，
       不因另一個英文在館藏出現次數不足被濾掉而漏判
    2. 收錄的中文若是 NAER 另一個較長中文的一部分（人文 ⊂ 人文主義），較長的詞也一併收錄
       （即使其英文館藏次數不足），讓翻譯器最長比對先命中完整複合詞
    """
    from build_display_names import naer_terms  # noqa: PLC0415

    _, raw = naer_terms(Path.home() / ".cache/arthistory/naer")

    def split_zh(zh_raw):
        zh = {
            re.sub(r"[（(【{][^）)】}]*[）)】}]", "", z).strip() for z in re.split(r"[；;]", zh_raw)
        }
        return {z for z in zh if len(CJK.findall(z)) >= 2 and len(z) == len(CJK.findall(z))}

    entries = {re.sub(r"\s*\(.*?\)", "", en).strip(): split_zh(z) for en, z in raw.items()}
    owners = defaultdict(set)
    for en, zhs in entries.items():
        for z in zhs:
            owners[z].add(en.lower())
    unique = {z for z, ens in owners.items() if len(ens) == 1}
    kept = {}
    for en, zhs in entries.items():
        if len(en) < 3 or corpus_hits(text, en) < MIN_CORPUS_HITS:
            continue
        zh = sorted(zhs & unique)
        if zh:
            kept[en] = {"zh": zh}
    kept_zh = {z for v in kept.values() for z in v["zh"]}
    for en, zhs in entries.items():  # 規則 2：補較長的複合詞
        longer = {z for z in zhs & unique if any(k in z and k != z for k in kept_zh)}
        if longer and en not in kept:
            kept[en] = {"zh": sorted(longer)}
    return kept


def main():
    text = corpus_text()
    print(f"館藏文字 {len(text):,} 字元")
    base = json.loads(BASE.read_text(encoding="utf-8"))
    base_terms = {
        t.lower()
        for cat in base.values()
        for k, v in cat.items()
        for t in [k, *[x for lst in v.values() for x in (lst if isinstance(lst, list) else [lst])]]
    }

    dictionary = {"artists_wikidata": artists(), "institutions_wikidata": institutions()}
    if BUILD_NAER:
        dictionary["naer_visual_arts"] = naer_visual_arts(text)
        print(f"naer_visual_arts: {len(dictionary['naer_visual_arts'])} 個詞條")
    for name, facet in AAT_FACETS.items():
        kept = {}
        for en, zhs in aat_facet(facet).items():
            # AAT 首選標籤常帶括號限定語（"altarpieces (religious visual works)"）；比對館藏用括號前
            core = re.sub(r"\s*\(.*\)$", "", en).strip()
            if corpus_hits(text, core) < MIN_CORPUS_HITS:
                continue
            zh = sorted(z for z in zhs if len(CJK.findall(z)) >= 2)
            if zh:
                kept[core] = {"zh": zh}
        dictionary[name] = kept
        print(f"{name}: {len(kept)} 個概念")
        time.sleep(1)

    # 同一中文對應多個英文 → 捨棄；原詞典已有的中文 → 不收（原詞典優先）
    owners = defaultdict(set)
    for cat in dictionary.values():
        for en, v in cat.items():
            for z in v["zh"]:
                owners[z].add(en.lower())  # 不分大小寫（NAER 英文為小寫）
    dropped = {z for z, ens in owners.items() if len(ens) > 1 or z.lower() in base_terms}
    for cat in dictionary.values():
        for en in list(cat):
            cat[en]["zh"] = [z for z in cat[en]["zh"] if z not in dropped]
            if not cat[en]["zh"]:
                del cat[en]
    dictionary["_meta"] = {
        "built": time.strftime("%Y-%m-%d"),
        "sources": "Wikidata (CC0)"
        + ("、國家教育研究院樂詞網視覺藝術名詞（政府網站資料開放宣告）" if BUILD_NAER else "")
        + ("、Getty AAT (ODC-By 1.0)" if AAT_FACETS else ""),
        "min_corpus_hits": MIN_CORPUS_HITS,
        "dropped_ambiguous_or_in_base": len(dropped),
    }
    OUT.write_text(json.dumps(dictionary, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(v) for k, v in dictionary.items() if k != "_meta")
    zh_total = sum(len(e["zh"]) for k, v in dictionary.items() if k != "_meta" for e in v.values())
    print(
        f"輸出 {OUT.name}：{total} 個英文詞條、{zh_total} 個中文詞；捨棄歧義／重複 {len(dropped)}"
    )


if __name__ == "__main__":
    main()
