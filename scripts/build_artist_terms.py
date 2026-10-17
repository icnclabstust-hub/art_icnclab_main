#!/usr/bin/env python3
"""圖譜畫家中文名詞典（2026-10-17 E25 方針第 2 步：查詢翻譯漏人名、亂猜人名）。

E25 量測：詞典沒有的人名，翻譯模型會亂猜（克林姆→Clim、席勒→Schiller）或整個漏掉（米勒）；
現有擴充詞典只有 artist_aliases.json 的 37 位。本腳本系統性收錄圖譜中所有有作品的畫家。

來源與規則：
1. 圖譜 Artist 名字（至少 1 件作品、拉丁字母）→ 候選英文名：原字串、去括號、括號內、
   「姓, 名」對調
2. QLever（Wikidata）：英文標籤或別名完全相同（單一字的名字只認標籤）、P31=人、
   職業屬視覺藝術家、攝影師、雕塑家、版畫家、雕版師、平面藝術家、建築師或設計師（各取
   P279* 子類）；同一候選名對到多位人物則捨棄。
   不用「藝術家」Q483501：其下含歌手等表演者（Capper 曾對到同名的中國歌手）
3. 中文：zh-tw／zh-hant／zh-hk／zh／zh-hans／zh-cn 標籤與別名，經 OpenCC s2twp 轉台灣繁體；
   標籤至少 2 字、別名至少 3 字（短別名常是普通詞）
4. 台灣譯名（display_names.json）的顯示名與 display_overrides.json 的可接受寫法一併收錄
5. 同一中文對應多位畫家則捨棄；英文鍵用 Wikidata 英文標籤

--famous（2026-10-18，E27）：館藏以外的知名視覺藝術家（維基條目數 ≥ FAMOUS_MIN_SITELINKS，
且有 Getty ULAN 或 RKDartists 編號），
讓館藏沒有的畫家（克林姆、席勒、米勒）也能譯對、明確回答「館藏沒有」。另收「姓氏」
（中文名最後一段，如「古斯塔夫·克林姆」→「克林姆」）：條目數 ≥ SURNAME_MIN_SITELINKS、
至少 2 字，且在全部人名（含圖譜詞典）中只對到一人才收；姓氏與 2 字名再查 Wikidata 是否也是
其他知名項目的名稱（知名度達畫家一半以上即捨棄，見 drop_collisions）。另收樂詞網台灣譯名。

用法（WSL；OpenCC 用 Open WebUI venv 的 python）：
    python3 scripts/build_artist_terms.py            # 圖譜畫家
    python3 scripts/build_artist_terms.py --famous   # 館藏以外的知名畫家
輸出：langchain-rag/art_terms_artists_graph.json（分類 artists_graph）、
art_terms_artists_famous.json（分類 artists_famous）；與原詞典同格式。
翻譯器設 QUERY_TERMS_EXTRA 才會載入（預設不載入；逗號分隔，前面的優先）。授權：Wikidata CC0。
"""

import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

REPO = Path(__file__).resolve().parent.parent
FAMOUS = "--famous" in sys.argv
_DEFAULT_OUT = "art_terms_artists_famous.json" if FAMOUS else "art_terms_artists_graph.json"
OUT = Path(os.getenv("ARTIST_TERMS_OUT", REPO / "langchain-rag" / _DEFAULT_OUT))
GRAPH_TERMS = REPO / "langchain-rag" / "art_terms_artists_graph.json"
FAMOUS_TERMS = REPO / "langchain-rag" / "art_terms_artists_famous.json"
ALIASES = REPO / "langchain-rag" / "artist_aliases.json"
ALIAS_EXT_OUT = Path(os.getenv("ALIAS_EXT_OUT", REPO / "langchain-rag" / "artist_aliases_ext.json"))
GRAPH_NODES: dict = {}  # graph_info 填入：{qid: {names, works, en}}
FAMOUS_MIN_SITELINKS = 30
SURNAME_MIN_SITELINKS = 40
COLLISION_RATIO = 0.5
# 人工排除：一般詞且同名檢查擋不下者（「王子」→ 歌手 Prince；「王子」概念的中文標籤是「親王」）
STOP_ZH = {"王子"}
DISPLAY = REPO / "langchain-rag" / "display_names.json"
OVERRIDES = REPO / "langchain-rag" / "display_overrides.json"
OPENCC_PY = "/home/user/openwebui-venv/bin/python"
QLEVER = "https://qlever.dev/api/wikidata"
UA = {"User-Agent": "ArtHistoryRAG-thesis/0.1 (academic; artist dictionary build)"}
PFX = (
    "PREFIX wd: <http://www.wikidata.org/entity/> "
    "PREFIX wdt: <http://www.wikidata.org/prop/direct/> "
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
    "PREFIX skos: <http://www.w3.org/2004/02/skos/core#> "
    "PREFIX wikibase: <http://wikiba.se/ontology#> "
    "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#> "
)
# 單一字的英文名（Anthony→安東尼、Abbas→阿巴斯）容易撞普通詞：只收知名人物（Rembrandt、Titian）
MONONYM_MIN_SITELINKS = 20
ZH_LANGS = ("zh-tw", "zh-hant", "zh-hk", "zh", "zh-hans", "zh-cn")
BATCH = 200
# 視覺藝術家、攝影師、雕塑家、版畫家、雕版師、平面藝術家、建築師、設計師
OCCUPATIONS = (
    "wd:Q1028181 wd:Q33231 wd:Q1281618 wd:Q11569986 wd:Q329439 wd:Q1925963 wd:Q42973 wd:Q5322166"
)
CJK = re.compile(r"[一-鿿]")
LATIN = re.compile(r"^[A-Za-zÀ-ɏḀ-ỿ' .,\-()&]+$")
SKIP = re.compile(
    r"\b(unknown|anonymous|workshop|follower|circle|school|style|after|attributed)\b", re.I
)


def fetch(url, accept=None, data=None):
    """data 不為 None 時以 POST 表單送出（長查詢超過網址上限會 HTTP 414）。"""
    for wait in (0, 10, 30, 90):
        time.sleep(wait)
        headers = {**UA, **({"Accept": accept} if accept else {})}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)  # noqa: S310 -- 固定 https
        try:
            with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310 -- 固定 https 網址
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503):
                raise
    raise RuntimeError(f"重試用盡：{url[:80]}")


def sparql(q):
    data = json.loads(
        fetch(
            QLEVER,
            "application/sparql-results+json",
            urllib.parse.urlencode({"query": PFX + q}).encode(),
        )
    )
    return data["results"]["bindings"]


def candidates(name):
    """圖譜名字 → 可能的英文名（去括號、括號內、姓名對調）。"""
    out = {name.strip()}
    base = re.sub(r"\s*\(.*?\)\s*", " ", name).strip()
    out.add(base)
    out.update(m.strip() for m in re.findall(r"\((.*?)\)", name))
    if base.count(",") == 1:
        last, first = (p.strip() for p in base.split(","))
        out.add(f"{first} {last}")
    return {
        c for c in out if len(c) >= 4 and LATIN.match(c) and not SKIP.search(c) and "," not in c
    }


def graph_artists():
    load_dotenv(REPO / ".env")
    drv = GraphDatabase.driver(
        "bolt://127.0.0.1:7687",
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    with drv.session() as s:
        rows = s.run("MATCH (a:Artist)--(:Artwork) RETURN a.name AS name, count(*) AS n").data()
    drv.close()
    return {r["name"]: r["n"] for r in rows if r["name"]}


def resolve(names):
    """{候選英文名: 唯一 QID}；對到多位人物的候選名捨棄；單一字的名字只認英文標籤。"""
    hits = defaultdict(set)
    names = sorted(names)
    for i in range(0, len(names), BATCH):
        values = " ".join(json.dumps(n, ensure_ascii=False) + "@en" for n in names[i : i + BATCH])
        q = (
            f"SELECT ?name ?x ?kind WHERE {{ VALUES ?name {{ {values} }} "
            '{ ?x rdfs:label ?name BIND("label" AS ?kind) } UNION '
            '{ ?x skos:altLabel ?name BIND("alias" AS ?kind) } '
            "?x wdt:P31 wd:Q5 . ?x wdt:P106 ?o . "
            f"?o wdt:P279* ?occ . VALUES ?occ {{ {OCCUPATIONS} }} }}"
        )
        for b in sparql(q):
            name = b["name"]["value"]
            if " " not in name and b["kind"]["value"] == "alias":
                continue
            hits[name].add(b["x"]["value"].rsplit("/", 1)[-1])
        print(f"  比對 {min(i + BATCH, len(names))}/{len(names)}", flush=True)
    return {n: next(iter(q)) for n, q in hits.items() if len(q) == 1}


def zh_names(qids):
    """{qid: {"en": 英文標籤, "links": 維基條目數, "labels": [...], "aliases": [...]}}。"""
    out = defaultdict(lambda: {"en": None, "links": 0, "labels": set(), "aliases": set()})
    qids = sorted(qids)
    langs = ", ".join(f'"{lang}"' for lang in ZH_LANGS)
    for i in range(0, len(qids), BATCH):
        values = " ".join(f"wd:{q}" for q in qids[i : i + BATCH])
        q = (
            f"SELECT ?x ?kind ?v WHERE {{ VALUES ?x {{ {values} }} "
            '{ ?x wikibase:sitelinks ?v BIND("links" AS ?kind) } UNION '
            '{ ?x rdfs:label ?v . FILTER(LANG(?v) = "en") BIND("en" AS ?kind) } UNION '
            f'{{ ?x rdfs:label ?v . FILTER(LANG(?v) IN ({langs})) BIND("label" AS ?kind) }} UNION '
            f'{{ ?x skos:altLabel ?v . FILTER(LANG(?v) IN ({langs})) BIND("alias" AS ?kind) }} }}'
        )
        for b in sparql(q):
            row = out[b["x"]["value"].rsplit("/", 1)[-1]]
            kind, v = b["kind"]["value"], b["v"]["value"]
            if kind == "en":
                row["en"] = v
            elif kind == "links":
                row["links"] = int(v)
            else:
                row["labels" if kind == "label" else "aliases"].add(v)
    return out


def famous_names():
    """館藏以外也收：維基條目數 ≥ FAMOUS_MIN_SITELINKS 的視覺藝術家（格式同 zh_names）。"""
    out = defaultdict(lambda: {"en": None, "links": 0, "labels": set(), "aliases": set()})
    langs = ", ".join(f'"{lang}"' for lang in ZH_LANGS)
    people = (
        "?x wdt:P31 wd:Q5 . ?x wikibase:sitelinks ?n . "
        # QLever 的 sitelinks 直接比數字恆為假，須先轉 xsd:integer（2026-10-18 實測）
        f"FILTER(xsd:integer(?n) >= {FAMOUS_MIN_SITELINKS}) ?x wdt:P106 ?o . "
        f"?o wdt:P279* ?occ . VALUES ?occ {{ {OCCUPATIONS} }} "
        # 須有藝術家權威編號（Getty ULAN 或 RKDartists）：排除只掛次要藝術職業的名人
        # （成龍、科菲·安南的姓氏「安南」曾混入）
        "{ ?x wdt:P245 ?aid } UNION { ?x wdt:P650 ?aid }"
    )
    for kind, pattern in (
        ("en", '?x rdfs:label ?v . FILTER(LANG(?v) = "en")'),
        ("label", f"?x rdfs:label ?v . FILTER(LANG(?v) IN ({langs}))"),
        ("alias", f"?x skos:altLabel ?v . FILTER(LANG(?v) IN ({langs}))"),
    ):
        rows = sparql(f"SELECT DISTINCT ?x ?n ?v WHERE {{ {people} {pattern} }}")
        for b in rows:
            row = out[b["x"]["value"].rsplit("/", 1)[-1]]
            row["links"] = int(b["n"]["value"])
            v = b["v"]["value"]
            if kind == "en":
                row["en"] = v
            else:
                row["labels" if kind == "label" else "aliases"].add(v)
        print(f"  {kind}：{len(rows)} 筆", flush=True)
    return out


def s2twp(texts, config="s2twp"):
    code = (
        f"import json,sys,opencc;c=opencc.OpenCC('{config}');"
        "print(json.dumps([c.convert(t) for t in json.load(sys.stdin)]))"
    )
    r = subprocess.run(  # noqa: S603 -- 固定直譯器與程式碼，輸入只經 stdin
        [OPENCC_PY, "-c", code], input=json.dumps(texts), capture_output=True, text=True, check=True
    )
    return json.loads(r.stdout)


def graph_info():
    artists = graph_artists()
    cand_of = {n: candidates(n) for n in artists}
    allc = set().union(*cand_of.values())
    print(f"圖譜畫家（有作品）{len(artists)}，候選英文名 {len(allc)}")
    qid_of = resolve(allc)
    qids = {qid_of[c] for cs in cand_of.values() for c in cs if c in qid_of}
    print(f"唯一對到 Wikidata 人物：{len(qids)} 位")
    # 圖譜節點 → QID（候選名全部對到同一人才算），供擴充別名表使用
    for name, cs in cand_of.items():
        hit = {qid_of[c] for c in cs if c in qid_of}
        if len(hit) == 1:
            row = GRAPH_NODES.setdefault(next(iter(hit)), {"names": [], "works": 0, "en": set()})
            row["names"].append(name)
            row["works"] += artists[name]
            row["en"].update(c for c in cs if c in qid_of)
    return zh_names(qids)


def main():
    info = famous_names() if FAMOUS else graph_info()
    surnames = set()
    print(f"人物 {len(info)} 位")
    mono = [r["en"] for r in info.values() if r["en"] and " " not in r["en"].strip()]
    info = {
        q: r
        for q, r in info.items()
        if r["en"] and (" " in r["en"].strip() or r["links"] >= MONONYM_MIN_SITELINKS)
    }
    kept = sum(" " not in r["en"].strip() for r in info.values())
    print(f"單一字名 {len(mono)} 位，條目數不足捨棄 {len(mono) - kept}")

    raw = [(q, t, kind) for q, r in info.items() for kind in ("labels", "aliases") for t in r[kind]]
    conv = s2twp([t for _, t, _ in raw])
    zh_of = defaultdict(set)  # 中文 → {英文}
    for (q, _, kind), t in zip(raw, conv, strict=True):
        en = info[q]["en"]
        t = re.sub(r"(?<=[一-鿿])[.．・•‧･](?=[一-鿿])", "·", t.strip())
        if not en or not CJK.search(t) or "，" in t or len(t) < (2 if kind == "labels" else 3):
            continue
        zh_of[t].add(en)
    if FAMOUS:
        names = [
            (info[q]["en"], info[q]["links"], t) for (q, _, _), t in zip(raw, conv, strict=True)
        ]
        names += naer_names(info, zh_of)
        surnames = add_surnames(names, zh_of)  # 只有姓氏的詞條另外標記（zh_surname）
        owner_of = {r["en"]: (q, r["links"]) for q, r in info.items()}
        drop_collisions(zh_of, surnames | {z for z in zh_of if len(z) == 2}, owner_of)
        for zh in STOP_ZH & set(zh_of):
            del zh_of[zh]
    dn = json.loads(DISPLAY.read_text(encoding="utf-8"))["畫家"]
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {}
    for en, v in dn.items():
        for t in [v["display"], *((overrides.get(en) or {}).get("accepted") or [])]:
            zh_of[re.sub(r"[．・•‧･]", "·", t)].add(en)

    terms = defaultdict(set)
    dropped = 0
    # 館藏以外的名單：圖譜詞典已有的中文名不重複收（翻譯器載入時圖譜詞典優先）
    taken = graph_zh() if FAMOUS else {}
    for zh, ens in zh_of.items():
        if len(ens) == 1 and zh not in taken:
            terms[next(iter(ens))].add(zh)
        elif len(ens) > 1:
            dropped += 1
    out = {
        "_meta": {
            "built": time.strftime("%Y-%m-%d"),
            "sources": (
                f"Wikidata (CC0) via QLever, visual artists sitelinks >= {FAMOUS_MIN_SITELINKS}"
                " with ULAN/RKD id; 國家教育研究院樂詞網「視覺藝術名詞」（應註明出處）"
                if FAMOUS
                else "Neo4j Artist × Wikidata (CC0) via QLever; display_names.json"
            ),
            "artists": len(terms),
            "dropped_ambiguous_zh": dropped,
        },
        ("artists_famous" if FAMOUS else "artists_graph"): {
            en: {
                k: v
                for k, v in (
                    ("zh", sorted(zs - surnames)),
                    ("zh_surname", sorted(zs & surnames)),  # 翻譯器檢查名字邊界
                )
                if v
            }
            for en, zs in sorted(terms.items())
        },
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"輸出 {OUT}：{len(terms)} 位畫家、{sum(map(len, terms.values()))} 個中文名；"
        f"歧義捨棄 {dropped}"
    )
    if not FAMOUS:
        write_alias_ext(info, terms)


def write_alias_ext(info, terms):
    """擴充圖譜錨點別名表（E28，2026-10-18）：artist_aliases.json 只有 40 位，其他畫家的問題
    圖譜認不出、只能退回。原 40 位條目原樣保留；其餘圖譜畫家（對到唯一 QID）加入：
    英文名＝Wikidata 英文標籤＋對到的圖譜候選名；中文＝本詞典與館藏外詞典（含姓氏）的中文名。
    一個別名對到多位畫家則捨棄。圖譜錨點設 GRAPH_ALIAS_PATH 指向輸出檔才會使用。
    """
    base = json.loads(ALIASES.read_text(encoding="utf-8"))
    famous = (
        json.loads(FAMOUS_TERMS.read_text(encoding="utf-8"))["artists_famous"]
        if FAMOUS_TERMS.exists()
        else {}
    )
    owner = defaultdict(set)  # 別名（英文 fold／中文）→ {qid}
    for a in base["artists"]:
        for al in a["aliases"]:
            owner[fold(al["alias"]) if al["type"] == "en" else al["alias"]].add(a["qid"])
    known = {a["qid"] for a in base["artists"]}
    new = []
    for qid, node in GRAPH_NODES.items():
        r = info.get(qid)
        if qid in known or not r or not r["en"]:
            continue
        en = r["en"]
        aliases = [
            {"alias": e, "type": "en", "source": "wikidata"} for e in sorted({en, *node["en"]})
        ]
        aliases += [
            {"alias": z, "type": "full", "source": "wikidata", "tw": True}
            for z in sorted(terms.get(en, set()) | set(famous.get(en, {}).get("zh", [])))
        ]
        aliases += [
            {"alias": z, "type": "surname", "source": "wikidata", "tw": True}
            for z in famous.get(en, {}).get("zh_surname", [])
        ]
        for al in aliases:
            owner[fold(al["alias"]) if al["type"] == "en" else al["alias"]].add(qid)
        new.append(
            {
                "qid": qid,
                "name_en": en,
                "en": sorted({en, *node["en"]}),
                "aliases": aliases,
                "neo4j_names": sorted(node["names"]),
                "neo4j_works": node["works"],
            }
        )
    dropped = sorted(k for k, q in owner.items() if len(q) > 1)
    for a in new:
        a["aliases"] = [
            al
            for al in a["aliases"]
            if len(owner[fold(al["alias"]) if al["type"] == "en" else al["alias"]]) == 1
        ]
    new = [a for a in new if a["aliases"]]
    out = {
        "meta": {
            **base["meta"],
            "extended": time.strftime("%Y-%m-%d"),
            "extended_by": "scripts/build_artist_terms.py（E28）",
            "extended_dropped_ambiguous": dropped[:200],
        },
        "artists": base["artists"] + new,
    }
    ALIAS_EXT_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"輸出 {ALIAS_EXT_OUT}：原 {len(base['artists'])} 位＋新增 {len(new)} 位；"
        f"歧義別名 {len(dropped)}"
    )


def graph_zh():
    """圖譜詞典的 {中文: 英文}（--famous 時排除重複、檢查姓氏唯一性用）。"""
    if not GRAPH_TERMS.exists():
        return {}
    data = json.loads(GRAPH_TERMS.read_text(encoding="utf-8"))["artists_graph"]
    return {zh: en for en, v in data.items() for zh in v["zh"]}


def fold(text):
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    ).lower()


def naer_names(info, zh_of):
    """樂詞網「視覺藝術名詞」的台灣譯名（「古斯塔夫．克林姆（奧地利）」）：英文與畫家英文名相同才收。

    回傳 [(英文, 條目數, 中文全名)] 供姓氏使用；全名直接加入 zh_of。
    """
    from build_display_names import naer_terms  # noqa: PLC0415 -- 只有 --famous 需要

    _, raw = naer_terms(Path.home() / ".cache/arthistory/naer")
    by_en = {fold(r["en"]): (r["en"], r["links"]) for r in info.values() if r["en"]}
    by_en.update({fold(en): (en, 0) for en in set(graph_zh().values()) if fold(en) not in by_en})
    out = []
    for eng, zh_raw in raw.items():
        if fold(eng) not in by_en:
            continue
        en, links = by_en[fold(eng)]
        for alt in zh_raw.split("；"):
            alt = re.sub(r"[（({][^）)}]*[）)}]$", "", alt).strip()
            alt = re.sub(r"(?<=[一-鿿])[.．・•‧･](?=[一-鿿])", "·", alt)
            if CJK.search(alt) and len(alt) >= 2:
                zh_of[alt].add(en)
                out.append((en, links, alt))
    print(f"  樂詞網台灣譯名 {len(out)} 個", flush=True)
    return out


def colliding(names):
    """查這些中文名在 Wikidata 還指哪些項目（任何類型，條目數 ≥ 30）：{中文: [(QID, 條目數)]}。

    比對繁體與簡體（OpenCC t2s）；POST 送出，每批 50 個。
    """
    names = sorted(names)
    simp = dict(zip(names, s2twp(names, "t2s"), strict=True))
    langs = ("zh", "zh-hans", "zh-cn", "zh-hant", "zh-tw", "zh-hk")
    hits = defaultdict(set)
    for i in range(0, len(names), 50):
        forms = {f: name for name in names[i : i + 50] for f in (name, simp[name])}
        values = " ".join(
            f"{json.dumps(f, ensure_ascii=False)}@{lang}" for f in forms for lang in langs
        )
        q = (
            f"SELECT DISTINCT ?v ?x ?n WHERE {{ VALUES ?v {{ {values} }} "
            "{ ?x rdfs:label ?v } UNION { ?x skos:altLabel ?v } "
            "?x wikibase:sitelinks ?n . FILTER(xsd:integer(?n) >= 30) }"
        )
        for b in sparql(q):
            qid = b["x"]["value"].rsplit("/", 1)[-1]
            hits[forms[b["v"]["value"]]].add((qid, int(b["n"]["value"])))
    return hits


def add_surnames(names, zh_of):
    """中文名最後一段當姓氏（「古斯塔夫·克林姆」→「克林姆」）：在全部畫家（含圖譜詞典）中只對到
    一人、條目數 ≥ SURNAME_MIN_SITELINKS 才加入；回傳加入的姓氏（之後由 drop_collisions 再篩）。
    """
    owners = defaultdict(set)  # 姓氏 → {(英文, 條目數)}
    for en, links, t in names:
        parts = re.split(r"[·．・]", t.strip())
        if en and len(parts) >= 2 and CJK.search(parts[-1]):
            owners[parts[-1]].add((en, links))
    for zh, en in graph_zh().items():  # 圖譜畫家的姓氏也算進唯一性（條目數以 0 計）
        parts = zh.split("·")
        if len(parts) >= 2:
            owners[parts[-1]].add((en, 0))
    added = set()
    for sur, pairs in owners.items():
        ens = {en for en, _ in pairs}
        links = max(n for _, n in pairs)
        if len(ens) == 1 and len(sur) >= 2 and links >= SURNAME_MIN_SITELINKS and sur not in zh_of:
            zh_of[sur].add(next(iter(ens)))
            added.add(sur)
    print(f"  姓氏候選 {len(added)} 個")
    return added


def drop_collisions(zh_of, check, owner_of):
    """姓氏與 2 字名：若另一個項目（不同 QID）也叫這個名字、且知名度 ≥ 畫家的 COLLISION_RATIO
    （至少條目數 30）就捨棄。席勒（詩人席勒）、杜甫、王子、安妮捨棄；莫內（法國村鎮 Monay）保留。
    owner_of：{英文: (QID, 條目數)}。
    """
    check = sorted(z for z in check if len(zh_of.get(z, ())) == 1)
    hits = colliding(check)
    dropped = []
    for zh in check:
        en = next(iter(zh_of[zh]))
        qid, links = owner_of.get(en, (None, 0))
        rivals = [n for q, n in hits[zh] if q != qid and n >= max(30, links * COLLISION_RATIO)]
        if rivals:
            del zh_of[zh]
            dropped.append(zh)
    print(f"  同名檢查 {len(check)} 個，捨棄 {len(dropped)}：{dropped[:20]}")


if __name__ == "__main__":
    main()
