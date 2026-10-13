#!/usr/bin/env python3
"""自動出題：「畫家 × 館藏」限制條件題，標準答案由 Cypher 從圖譜算出（不需人工標註）。

設計：docs/designs/2026-10-11-graph-retrieval-anchor.md（規劃書「評估設計／自動出題」）
- 畫家：別名表中在圖譜有節點的畫家；館藏：T2 支援的三館（大都會、哈佛、荷蘭國家博物館）
- 正例：該畫家在該館至少 1 件；應拒答題：0 件（約佔 10%）
- 畫家寫法輪替：台灣譯名、Wikidata 全名、姓氏、英文名；問句模板 4 種輪替
- 標準答案：該畫家所有節點（同一人多節點）在該館的 Artwork.id 集合

用法（Windows py311_venv，Neo4j 唯讀）：
    python scripts/gen_constraint_questions.py <artist_aliases.json> <輸出.json>
"""

import json
import random
import sys
from pathlib import Path

from neo4j import GraphDatabase

REPO = Path(__file__).resolve().parent.parent
MUSEUMS = {
    "Metropolitan Museum of Art": ["大都會藝術博物館", "大都會博物館"],
    "Harvard Art Museums": ["哈佛藝術博物館"],
    "Rijksmuseum": ["荷蘭國家博物館"],
}
TEMPLATES = [
    "{m}收藏了哪些{a}的作品？",
    "{a}有哪些作品收藏在{m}？",
    "請列出{m}館藏中{a}的作品。",
    "在{m}可以看到{a}的哪些作品？",
]
NEGATIVE_SHARE = 0.10


def env(key):
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"')
    return None


def writings(artist):
    """畫家寫法：(類型, 寫法)；中文只用台灣繁體（別名表 tw 標記），台灣譯名優先。"""
    by = {}
    for x in artist["aliases"]:
        if x["type"] == "en" or x.get("tw"):
            by.setdefault(x["type"], []).append(x["alias"])
    out = []
    if by.get("manual"):
        out.append(("台灣譯名", by["manual"][0]))
    full = [x for x in by.get("full", []) if "·" in x]
    if full:
        out.append(("全名", full[0]))
    if by.get("surname"):
        out.append(("姓氏", by["surname"][0]))
    out.append(("英文", artist["name_en"]))
    return out


def main():
    aliases, out_path = sys.argv[1], sys.argv[2]
    artists = [a for a in json.loads(Path(aliases).read_text(encoding="utf-8"))["artists"] if a["neo4j_names"]]
    drv = GraphDatabase.driver("bolt://127.0.0.1:7687", auth=(env("NEO4J_USER") or "neo4j", env("NEO4J_PASSWORD")))
    pos, neg = [], []
    with drv.session() as s:
        for a in artists:
            for museum in MUSEUMS:
                ids = sorted(
                    r["id"]
                    for r in s.run(
                        "MATCH (x:Artist)-[c:CREATED]->(w:Artwork)-[h:HELD_BY]->(i:Institution) "
                        "WHERE x.name IN $names AND i.name = $m AND c.valid_to IS NULL AND h.valid_to IS NULL "
                        "AND coalesce(w.is_deleted, false) = false RETURN DISTINCT w.id AS id",
                        names=a["neo4j_names"],
                        m=museum,
                    )
                )
                (pos if ids else neg).append((a, museum, ids))
    drv.close()
    rng = random.Random(20261011)
    n_neg = max(3, round(len(pos) * NEGATIVE_SHARE / (1 - NEGATIVE_SHARE)))
    chosen = pos + rng.sample(neg, min(n_neg, len(neg)))
    questions = []
    for i, (a, museum, ids) in enumerate(chosen, 1):
        kind, name = writings(a)[i % len(writings(a))]
        m_zh = MUSEUMS[museum][i % len(MUSEUMS[museum])]
        questions.append(
            {
                "key": f"C{i}",
                "question": TEMPLATES[i % len(TEMPLATES)].format(m=m_zh, a=name),
                "artist_qid": a["qid"],
                "artist_en": a["name_en"],
                "writing": kind,
                "museum": museum,
                "gold_ids": ids,
                "should_refuse": not ids,
            }
        )
    Path(out_path).write_text(json.dumps(questions, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"正例 {len(pos)}（共 {sum(len(x[2]) for x in pos)} 件）、應拒答 {len(chosen) - len(pos)}，合計 {len(questions)} 題")
    for q in questions:
        print(q["key"], q["writing"], len(q["gold_ids"]), q["question"])


if __name__ == "__main__":
    main()
