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

用法（WSL；OpenCC 用 Open WebUI venv 的 python）：
    python3 scripts/build_artist_terms.py
輸出：langchain-rag/art_terms_artists_graph.json（與原詞典同格式，分類 artists_graph）；
翻譯器設 QUERY_TERMS_EXTRA 才會載入（預設不載入）。授權：Wikidata CC0。
"""

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

REPO = Path(__file__).resolve().parent.parent
OUT = Path(os.getenv("ARTIST_TERMS_OUT", REPO / "langchain-rag" / "art_terms_artists_graph.json"))
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


def fetch(url, accept=None):
    for wait in (0, 10, 30, 90):
        time.sleep(wait)
        req = urllib.request.Request(  # noqa: S310 -- 固定 https 網址
            url, headers={**UA, **({"Accept": accept} if accept else {})}
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310 -- 固定 https 網址
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503):
                raise
    raise RuntimeError(f"重試用盡：{url[:80]}")


def sparql(q):
    data = json.loads(
        fetch(
            QLEVER + "?" + urllib.parse.urlencode({"query": PFX + q}),
            "application/sparql-results+json",
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


def s2twp(texts):
    code = (
        "import json,sys,opencc;c=opencc.OpenCC('s2twp');"
        "print(json.dumps([c.convert(t) for t in json.load(sys.stdin)]))"
    )
    r = subprocess.run(  # noqa: S603 -- 固定直譯器與程式碼，輸入只經 stdin
        [OPENCC_PY, "-c", code], input=json.dumps(texts), capture_output=True, text=True, check=True
    )
    return json.loads(r.stdout)


def main():
    artists = graph_artists()
    cand_of = {n: candidates(n) for n in artists}
    allc = set().union(*cand_of.values())
    print(f"圖譜畫家（有作品）{len(artists)}，候選英文名 {len(allc)}")
    qid_of = resolve(allc)
    qids = {qid_of[c] for cs in cand_of.values() for c in cs if c in qid_of}
    print(f"唯一對到 Wikidata 人物：{len(qids)} 位")
    info = zh_names(qids)
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
    dn = json.loads(DISPLAY.read_text(encoding="utf-8"))["畫家"]
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {}
    for en, v in dn.items():
        for t in [v["display"], *((overrides.get(en) or {}).get("accepted") or [])]:
            zh_of[re.sub(r"[．・•‧･]", "·", t)].add(en)

    terms = defaultdict(set)
    dropped = 0
    for zh, ens in zh_of.items():
        if len(ens) == 1:
            terms[next(iter(ens))].add(zh)
        else:
            dropped += 1
    out = {
        "_meta": {
            "built": time.strftime("%Y-%m-%d"),
            "sources": "Neo4j Artist × Wikidata (CC0) via QLever; display_names.json",
            "artists": len(terms),
            "dropped_ambiguous_zh": dropped,
        },
        "artists_graph": {en: {"zh": sorted(zs)} for en, zs in sorted(terms.items())},
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"輸出 {OUT}：{len(terms)} 位畫家、{sum(map(len, terms.values()))} 個中文名；"
        f"歧義捨棄 {dropped}"
    )


if __name__ == "__main__":
    main()
