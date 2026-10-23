#!/usr/bin/env python3
"""建立畫家別名表（圖譜檢索修復方案 A 的 M0／M1；第一版存本機 JSON，進版控，不寫資料庫）。

設計：docs/designs/2026-10-11-graph-retrieval-anchor.md
- canonical ID：Wikidata QID（以英文維基條目名查得）
- 別名：Wikidata en／zh-tw／zh-hant／zh-hk／zh／zh-hans／zh-cn 標籤與別名
  （中文以 OpenCC s2twp 轉台灣繁體）、
  「·」切出的姓氏、翻譯詞典的台灣譯名（manual）
- 唯一性檢查：一個別名指向多位畫家時捨棄，除非 FAMILIES 明定（卡拉契＝Annibale＋Ludovico）
- 節點：Neo4j 中名稱正規化後等於某個英文別名的 Artist 節點（唯讀；同一畫家可能有多個節點）

用法（WSL）：
    python3 scripts/build_artist_aliases.py            # 輸出 langchain-rag/artist_aliases.json
OpenCC 只在建置時需要（呼叫 Open WebUI venv 的 python）；執行期不需要。
"""

import json
import os
import re
import subprocess
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from neo4j import GraphDatabase

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "langchain-rag" / "artist_aliases.json"
DICT = REPO / "langchain-rag" / "art_history_terms_dictionary.json"
OPENCC_PY = "/home/user/openwebui-venv/bin/python"
UA = {"User-Agent": "ArtHistoryRAG-thesis/0.1 (academic; artist alias table)"}
ZH = ["zh-tw", "zh-hant", "zh-hk", "zh", "zh-hans", "zh-cn"]
TITLE_FIX = {
    "Monet": "Claude Monet",
    "Van Gogh": "Vincent van Gogh",
    "Picasso": "Pablo Picasso",
    "Carracci": "Annibale Carracci",
}
EXTRA = ["Ludovico Carracci"]  # 卡拉契家族
FAMILIES = {
    "卡拉契": ["Annibale Carracci", "Ludovico Carracci"],
    "卡拉奇": ["Annibale Carracci", "Ludovico Carracci"],
}
# Wikidata 英文別名缺的常用寫法（Neo4j 節點用這些名稱）
EN_EXTRA = {"Diego Velázquez": ["Velázquez", "Diego Rodríguez de Silva y Velázquez"]}
# 只有名字、無法唯一指向畫家的英文別名（例：Guido 可能是別人）
EN_BLOCK = {"guido"}
# 詞典把卡拉契家族放在 Carracci 一條；這些譯名只屬於 Ludovico
LUDOVICO_ONLY = {"盧多維科·卡拉契", "卢多维科·卡拉奇"}


def wikidata(title):
    q = urllib.parse.urlencode(
        {
            "action": "wbgetentities",
            "sites": "enwiki",
            "titles": title,
            "props": "labels|aliases|claims",
            "languages": "|".join(["en", *ZH]),
            "redirects": "yes",
            "format": "json",
        }
    )
    for wait in (0, 5, 20, 60):
        time.sleep(wait)
        try:
            req = urllib.request.Request(f"https://www.wikidata.org/w/api.php?{q}", headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 -- 固定 https 網址
                ent = next(iter(json.load(r)["entities"].values()))
                return None if "missing" in ent else ent
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
    raise RuntimeError("Wikidata 429")


def names(ent, lang):
    out = [ent.get("labels", {}).get(lang, {}).get("value")]
    out += [a["value"] for a in ent.get("aliases", {}).get(lang, [])]
    return [x for x in out if x]


def s2twp(texts):
    code = (
        "import json,sys,opencc;c=opencc.OpenCC('s2twp');"
        "print(json.dumps([c.convert(t) for t in json.load(sys.stdin)]))"
    )
    r = subprocess.run(  # noqa: S603 -- 固定直譯器與程式碼，輸入只經 stdin
        [OPENCC_PY, "-c", code], input=json.dumps(texts), capture_output=True, text=True, check=True
    )  # noqa: S603
    return json.loads(r.stdout)


def fold(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


def node_keys(name):
    """Neo4j 畫家名稱的比對鍵：去換行後綴、括號註記、called 前綴；括號內全名另列。"""
    base = name.split("\n")[0]
    inner = re.findall(r"\(([^()]*)\)?", base)
    base = re.sub(r"\s*\(.*$", "", base)
    base = re.sub(r"^(called|attributed to)\s+", "", base, flags=re.I)
    keys = {fold(base)}
    keys |= {
        fold(x)
        for x in inner
        if x and not re.search(r"künstler|artist|dutch|french|italian|spanish|flemish", x, re.I)
    }
    return {k for k in keys if k}


SKIP_NAME = re.compile(
    r"workshop|follower|style of|after |attributed|circle of|school|unknown|anonymous|"
    r"manufactory|factory|copy|imitator|possibly|probably|maker:|born ",
    re.I,
)
TOP_MUSEUMS = ["Metropolitan Museum of Art", "Harvard Art Museums", "Rijksmuseum"]


def top_museum_artists(n):
    """三館作品數最多的畫家（清理後名稱），供自動出題擴充別名表（唯讀）。"""
    drv = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    counts = {}
    with drv.session() as s:
        for r in s.run(
            "MATCH (a:Artist)-[:CREATED]->(:Artwork)-[:HELD_BY]->(i:Institution) "
            "WHERE i.name IN $m RETURN a.name AS name, count(*) AS c",
            m=TOP_MUSEUMS,
        ):
            if SKIP_NAME.search(r["name"]):
                continue
            base = re.sub(r"\s*\(.*$", "", r["name"].splitlines()[0]).strip()
            if len(base.split()) >= 2:  # 只取有名有姓的寫法，避免單名歧義
                counts[base] = counts.get(base, 0) + r["c"]
    drv.close()
    return [k for k, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:n]]


def main():
    artists = json.load(open(DICT, encoding="utf-8"))["famous_artists"]
    known = {fold(TITLE_FIX.get(k, k)) for k in artists} | {fold(x) for x in EXTRA}
    n_top = int(os.getenv("TOP_MUSEUM_ARTISTS", "60"))
    top = [t for t in top_museum_artists(n_top) if fold(t) not in known]
    entries = []
    seen_qids = set()
    for key in list(artists) + EXTRA + top:
        title = TITLE_FIX.get(key, key)
        ent = wikidata(title)
        time.sleep(0.5)
        if not ent:
            print("Wikidata 查無：", title)
            continue
        if ent["id"] in seen_qids:  # 圖中不同寫法對到同一位畫家
            continue
        p31 = {
            c["mainsnak"].get("datavalue", {}).get("value", {}).get("id")
            for c in ent.get("claims", {}).get("P31", [])
        }
        if "Q5" not in p31:  # 只收人物（圖中有名為「17th century」「New Jersey」的 Artist 節點）
            print("非人物，略過：", title)
            continue
        if key in top and not any(names(ent, lang) for lang in ZH):
            continue  # 沒有中文標籤，無法出中文題
        seen_qids.add(ent["id"])
        en = [
            a
            for a in dict.fromkeys([title, *names(ent, "en"), *EN_EXTRA.get(title, [])])
            if fold(a) not in EN_BLOCK
        ]
        zh_raw = list(dict.fromkeys(n for lang in ZH for n in names(ent, lang)))
        manual = (
            []
            if key in EXTRA or key in top
            else [v for v in artists[key].get("zh", []) if v not in LUDOVICO_ONLY]
        )
        if key == "Ludovico Carracci":
            manual = sorted(LUDOVICO_ONLY)
        entries.append(
            {"qid": ent["id"], "name_en": title, "en": en, "zh_raw": zh_raw, "manual": manual}
        )

    flat = sorted({z for e in entries for z in e["zh_raw"] + e["manual"]})
    conv = dict(zip(flat, s2twp(flat), strict=True))
    for e in entries:
        full = list(dict.fromkeys([*e["zh_raw"], *(conv[z] for z in e["zh_raw"])]))
        e["aliases"] = (
            [{"alias": a, "type": "full", "source": "wikidata"} for a in full]
            + [
                {"alias": a.split("·")[-1], "type": "surname", "source": "wikidata"}
                for a in full
                # 姓氏至少 3 字：2 字姓氏常是普通詞（大衛、德加）；常用 2 字譯名由詞典 manual 提供
                if "·" in a and len(a.split("·")[-1]) >= 3
            ]
            + [{"alias": a, "type": "en", "source": "wikidata"} for a in e["en"]]
            + [{"alias": a, "type": "manual", "source": "dictionary"} for a in e["manual"]]
        )

    # 標記台灣繁體寫法（s2twp 轉換後不變者），供自動出題只用台灣使用者會寫的名稱
    zh_all = sorted({a["alias"] for e in entries for a in e["aliases"] if a["type"] != "en"})
    conv_all = dict(zip(zh_all, s2twp(zh_all), strict=True))  # 含拆出的姓氏
    for e in entries:
        for a in e["aliases"]:
            if a["type"] != "en":
                a["tw"] = conv_all[a["alias"]] == a["alias"]

    # 唯一性檢查：一個別名對到多位畫家就捨棄（家族例外）；
    # 但若某位畫家以全名／手動譯名擁有它，其他人只是拆出的姓氏，則歸全名擁有者
    # （例：「卡拉瓦喬」屬 Caravaggio，不因 Polidoro da Caravaggio 的姓氏而捨棄）
    owners, strong = {}, {}
    for e in entries:
        for a in e["aliases"]:
            k = fold(a["alias"]) if a["type"] == "en" else a["alias"]
            owners.setdefault(k, set()).add(e["name_en"])
            if a["type"] != "surname":
                strong.setdefault(k, set()).add(e["name_en"])
    dropped = []
    for e in entries:
        kept = []
        for a in e["aliases"]:
            k = fold(a["alias"]) if a["type"] == "en" else a["alias"]
            fam = FAMILIES.get(a["alias"])
            mine = owners[k]
            if len(strong.get(k, set())) == 1 and len(mine) > 1:
                if e["name_en"] not in strong[k]:
                    dropped.append((a["alias"], sorted(mine)))
                    continue
                mine = strong[k]
            if len(mine) > 1 and not (fam and mine <= set(fam)):
                dropped.append((a["alias"], sorted(owners[k])))
                continue
            kept.append(a)
        uniq = {}
        for a in kept:
            uniq.setdefault((a["alias"], a["type"]), a)
        e["aliases"] = list(uniq.values())
    for fam_alias, members in FAMILIES.items():  # 家族別名掛到每位成員
        for e in entries:
            if e["name_en"] in members and not any(a["alias"] == fam_alias for a in e["aliases"]):
                e["aliases"].append({"alias": fam_alias, "type": "manual", "source": "family"})

    # 對應 Neo4j 節點（唯讀）
    drv = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    with drv.session() as s:
        nodes = [
            (r["name"], r["works"])
            for r in s.run(
                "MATCH (a:Artist) RETURN a.name AS name, size([(a)-[:CREATED]->() | 1]) AS works"
            )
        ]
    drv.close()
    for e in entries:
        en_keys = {fold(a["alias"]) for a in e["aliases"] if a["type"] == "en"}
        e["neo4j_names"] = sorted(n for n, _ in nodes if node_keys(n) & en_keys)
        e["neo4j_works"] = sum(w for n, w in nodes if n in e["neo4j_names"])
        del e["zh_raw"], e["manual"]

    meta = {
        "built": time.strftime("%Y-%m-%d"),
        "source": "Wikidata (CC0) + art_history_terms_dictionary.json",
        "dropped_ambiguous": sorted({a for a, _ in dropped}),
    }
    OUT.write_text(
        json.dumps({"meta": meta, "artists": entries}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    for e in entries:
        zh = [a["alias"] for a in e["aliases"] if a["type"] in ("full", "surname", "manual")][:6]
        print(
            f"{e['name_en']:24} {e['qid']:8} 節點 {len(e['neo4j_names'])} "
            f"作品 {e['neo4j_works']:3} | {e['neo4j_names'][:4]} | {zh}"
        )
    print("捨棄的歧義別名：", meta["dropped_ambiguous"])


if __name__ == "__main__":
    main()
