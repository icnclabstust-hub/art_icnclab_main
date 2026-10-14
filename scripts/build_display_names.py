#!/usr/bin/env python3
"""Q1 顯示名稱表：以國際名（Wikidata 英文標籤）為 key，依台灣用語優先順序決定中文顯示名。

設計：規格書 Q1；2026-10-14 使用者確認順序（避免 zh＋簡轉繁產生「倫勃朗」這類大陸譯名）：
  1. 自建台灣譯名表（art_history_terms_dictionary.json 人工整理的第一個中文詞）
  2. 國家教育研究院「視覺藝術名詞」（樂詞網審譯，以英文名稱比對，不分大小寫）
  3. Wikidata zh-tw  4. zh-hant  5. zh 經 OpenCC s2twp 轉台灣繁體
  6. 都沒有：只顯示原文（英文標籤）
類別：畫家（artist_aliases.json 的 40 位）、藝術運動（P31=Q968159）、藝術類型（P31=Q1792379）、
藝術史學者（P106=Q1792450）。
資料來源：Wikidata 以 QLever（以完整 Wikidata 傾印建置的 SPARQL 服務，無官方 WDQS 的
60 秒逾時與每分鐘 1 次限流）查詢；Wikidata 為 CC0。NAER 名詞由樂詞網下載專區取得。
國教院「外國學者人名譯名」只涵蓋音樂、物理、化學、生命科學、數學，不含藝術，故不收。
Getty ULAN（ODC-By 1.0）2026-10-14 查 39 位畫家：中文名只有 2 位且為簡體（梵高等），不收作顯示來源。
樂詞網授權：政府網站資料開放宣告（無償、非專屬、可再授權、不撤回；應註明出處、不得惡意變更）。

用法（WSL；OpenCC 只在建置時需要，呼叫 Open WebUI venv 的 python）：
    python3 scripts/build_display_names.py [NAER 快取資料夾]
輸出：langchain-rag/display_names.json；覆蓋率印在終端（尚未接入系統，只是資料）。
"""

import io
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET  # noqa: S405 -- 解析政府開放資料 ODS，非任意來源
import zipfile
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "langchain-rag" / "display_names.json"
ALIASES = REPO / "langchain-rag" / "artist_aliases.json"
BASE = REPO / "art_history_terms_dictionary.json"
OPENCC_PY = "/home/user/openwebui-venv/bin/python"
QLEVER = "https://qlever.dev/api/wikidata"
NAER_URL = "https://terms.naer.edu.tw/media/terms_data/1/" + urllib.parse.quote(
    "視覺藝術名詞壓縮檔.zip"
)
UA = {"User-Agent": "ArtHistoryRAG-thesis/0.1 (academic; display names)"}
CLASSES = {
    "藝術運動": "?x wdt:P31 wd:Q968159 .",
    "藝術類型": "?x wdt:P31 wd:Q1792379 .",
    "藝術史學者": "?x wdt:P106 wd:Q1792450 .",
}
PFX = (
    "PREFIX wd: <http://www.wikidata.org/entity/> "
    "PREFIX wdt: <http://www.wikidata.org/prop/direct/> "
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
)
LANGS = {"en": "en", "zh": "zh", "hant": "zh-hant", "tw": "zh-tw"}
ODS_NS = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}


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


def labels(pattern):
    """{qid: {"en": …, "zh": …, "hant": …, "tw": …}}（每語言取一個標籤）。"""
    opt = " ".join(
        f'OPTIONAL {{ ?x rdfs:label ?{v} . FILTER(LANG(?{v})="{lang}") }}'
        for v, lang in LANGS.items()
    )
    q = PFX + f"SELECT ?x ?{' ?'.join(LANGS)} WHERE {{ {pattern} {opt} }}"
    data = json.loads(
        fetch(
            QLEVER + "?" + urllib.parse.urlencode({"query": q}), "application/sparql-results+json"
        )
    )
    out = {}
    for b in data["results"]["bindings"]:
        qid = b["x"]["value"].rsplit("/", 1)[-1]
        row = out.setdefault(qid, {})
        for v in LANGS:
            if v in b and v not in row:
                row[v] = b[v]["value"]
    return out


def naer_terms(cache: Path):
    """NAER 視覺藝術名詞：{英文小寫: 中文}；同一英文多個中文時取第一筆。"""
    cache.mkdir(parents=True, exist_ok=True)
    z = cache / "naer_visual_arts.zip"
    if not z.exists():
        z.write_bytes(fetch(NAER_URL))
    with zipfile.ZipFile(z) as outer:
        ods = outer.read(outer.infolist()[0])
    with zipfile.ZipFile(io.BytesIO(ods)) as inner:
        root = ET.fromstring(inner.read("content.xml"))  # noqa: S314
    t, p = f"{{{ODS_NS['table']}}}", f"{{{ODS_NS['text']}}}p"
    terms, raw = {}, {}
    for tr in root.iter(t + "table-row"):
        cells = ["".join(x.itertext()) for tc in tr for x in [*tc.iter(p)][:1]]
        if len(cells) >= 3 and cells[0].isdigit():
            zh = re.sub(r"[（({][^）)}]*[）)}]$", "", cells[2].split("；")[0]).strip()
            terms.setdefault(cells[1].strip().lower(), zh)  # 去國籍尾綴「（義大利）」「{荷蘭}」
            raw.setdefault(cells[1].strip().lower(), cells[2].strip())
    return terms, raw


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
    cache = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".cache/arthistory/naer"
    naer, naer_raw = naer_terms(cache)
    manual = {
        en: v["zh"][0]
        for group in json.loads(BASE.read_text(encoding="utf-8")).values()
        for en, v in group.items()
        if isinstance(v, dict) and v.get("zh")
    }
    cats = {}
    artists = json.loads(ALIASES.read_text(encoding="utf-8"))["artists"]
    qids = " ".join(f"wd:{a['qid']}" for a in artists)
    cats["畫家"] = labels(f"VALUES ?x {{ {qids} }}")
    for a in artists:  # 畫家英文名以別名表為準（QLever 偶有缺英文標籤）
        cats["畫家"].setdefault(a["qid"], {})["en"] = a["name_en"]
    for name, pat in CLASSES.items():
        cats[name] = labels(pat)
    need = sorted({r["zh"] for c in cats.values() for r in c.values() if "zh" in r})
    conv = dict(zip(need, s2twp(need), strict=True))
    out = {
        "meta": {
            "order": ["manual", "naer", "zh-tw", "zh-hant", "zh+s2twp", "original"],
            "attribution": [
                "國家教育研究院樂詞網「視覺藝術名詞」（政府網站資料開放宣告，使用時應註明出處）",
                "Wikidata（CC0），經 QLever 查詢",
            ],
        }
    }
    for cat, rows in cats.items():
        entries, src = {}, Counter()
        for qid, r in rows.items():
            en = r.get("en") or qid
            for source, value in (  # noqa: B007 -- 迴圈結束後使用 source
                ("manual", manual.get(en)),
                ("naer", naer.get(en.lower())),
                ("zh-tw", r.get("tw")),
                ("zh-hant", r.get("hant")),
                ("zh+s2twp", conv.get(r.get("zh", ""))),
                ("original", en),
            ):
                if value:
                    break
            src[source] += 1
            entries[en] = {"qid": qid, "display": value, "source": source}
            if source == "naer":  # 開放宣告第四點：保留原文，顯示值只去國籍尾綴與同義詞
                entries[en]["naer_original"] = naer_raw[en.lower()]
        out[cat] = entries
        diff = [
            (en, manual[en], naer[en.lower()])
            for en in entries
            if en in manual and en.lower() in naer and manual[en] != naer[en.lower()]
        ]
        if diff:
            print(f"  {cat} 人工表與 NAER 不一致 {len(diff)} 筆：{diff}")
        n = len(rows)
        print(
            f"{cat}：{n} 筆｜"
            + "、".join(f"{s} {src[s]}（{src[s] / n:.1%}）" for s in out["meta"]["order"] if src[s])
        )
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"NAER 視覺藝術名詞 {len(naer)} 個英文詞；輸出 {OUT}")


if __name__ == "__main__":
    sys.exit(main())
