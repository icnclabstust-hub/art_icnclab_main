#!/usr/bin/env python3
"""作者連結遷移：以新的作者解析規則（ingest.artist_names）重建 Neo4j 的 CREATED 關係。

設計：docs/designs/2026-10-18-graph-data-quality.md D2
- 讀 catalog.documents（未刪除）的作品內容，組成 upsert 事件交給 Neo4jSubscriber（與每晚訂閱器
  同一條寫入路徑）：新作者補上 CREATED、不再列出的舊 CREATED 設 valid_to（軟到期，30 天後由
  purge-neo4j 刪除，期間可還原）
- 訂閱器在新名單為空時刻意不到期舊關係（避免來源暫缺欄位）；本腳本另外把「名字本身解析為無作者」
  的舊關係（Unknown Artist、Italian、1904–1989 這類片段）設 valid_to
- 預設 --dry-run：只比較並輸出各來源差異統計與抽樣，不寫入

用法（WSL）：
    python3 scripts/migrate_artist_links.py              # 預演
    python3 scripts/migrate_artist_links.py --apply      # 實際寫入（先確認 Neo4j 每晚備份已完成）
"""

import argparse
import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "langchain-rag"))

from dotenv import load_dotenv  # noqa: E402
from ingest.artist_names import parse_artists  # noqa: E402
from ingest.db import connect  # noqa: E402
from neo4j import GraphDatabase  # noqa: E402
from subscribers.base import Event  # noqa: E402
from subscribers.neo4j_sub import Neo4jSubscriber, _artist_names  # noqa: E402

BATCH = 200
_CURRENT_QUERY = """
MATCH (x:Artist)-[r:CREATED]->(a:Artwork) WHERE a.id IN $ids AND r.valid_to IS NULL
RETURN a.id AS id, collect(x.name) AS names
"""
_EXPIRE_JUNK_QUERY = """
UNWIND $rows AS row
MATCH (x:Artist {name: row.name})-[r:CREATED]->(a:Artwork {id: row.artwork_id})
WHERE r.valid_to IS NULL
SET r.valid_to = datetime()
"""


def load_documents(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT doc_id, external_id, source, version, metadata->'artwork'"
        " FROM catalog.documents WHERE NOT is_deleted AND quarantine_status = 'clean'"
        " ORDER BY external_id"
    ).fetchall()
    return [
        {"doc_id": d, "external_id": e, "source": s, "version": v, "artwork": a}
        for d, e, s, v, a in rows
        if a
    ]


def plan(docs: list[dict], current: dict[str, list[str]]) -> list[dict]:
    """每件作品：新作者清單、要補的、要到期的（含解析為無作者的舊名字）。"""
    out = []
    for doc in docs:
        new = _artist_names(doc["artwork"], doc["source"])
        old = current.get(doc["external_id"], [])
        junk = [n for n in old if not parse_artists(doc["source"], n)]
        # 新名單非空時訂閱器會到期所有不在新名單的舊名字；為空時只到期無作者的舊名字
        expire = [n for n in old if n not in new] if new else junk
        out.append(
            {
                **doc,
                "new": new,
                "old": old,
                "add": [n for n in new if n not in old],
                "expire": expire,
                "junk": junk,
            }
        )
    return out


def report(items: list[dict]) -> None:
    by = defaultdict(Counter)
    for it in items:
        c = by[it["source"]]
        c["作品"] += 1
        c["不變"] += not it["add"] and not it["expire"]
        c["補關係"] += len(it["add"])
        c["到期關係"] += len(it["expire"])
        c["改後無作者"] += not it["new"]
    total = Counter()
    for src, c in sorted(by.items()):
        total.update(c)
        print(f"{src:28} " + "｜".join(f"{k} {v}" for k, v in c.items()))
    print(f"{'合計':28} " + "｜".join(f"{k} {v}" for k, v in total.items()))
    old_names = {n for it in items for n in it["old"]}
    new_names = {n for it in items for n in it["new"]}
    added = len(new_names - old_names)
    print(f"作者名字：目前有效 {len(old_names)} → 遷移後 {len(new_names)}（新增 {added}）")
    random.seed(7)
    changed = [it for it in items if it["add"] or it["expire"]]
    for src in sorted(by):
        sample = [it for it in changed if it["source"] == src]
        for it in random.sample(sample, min(3, len(sample))):
            raw = (it["artwork"].get("artist") or "")[:60]
            print(f"  [{src}] {raw!r}\n      舊 {it['old'][:4]}\n      新 {it['new']}")


def apply(driver, items: list[dict]) -> None:
    subscriber = Neo4jSubscriber(driver.session)
    for i in range(0, len(items), BATCH):
        batch = items[i : i + BATCH]
        events = [
            Event(
                event_id=0,
                entity_type="document",
                entity_id=it["doc_id"],
                op="upsert",
                payload={
                    "external_id": it["external_id"],
                    "source": it["source"],
                    "version": it["version"],
                    "artwork": it["artwork"],
                },
            )
            for it in batch
        ]
        subscriber.handle(events)
        junk = [
            {"name": n, "artwork_id": it["external_id"]}
            for it in batch
            if not it["new"]
            for n in it["junk"]
        ]
        if junk:
            with driver.session() as session:
                session.run(_EXPIRE_JUNK_QUERY, rows=junk).consume()
        print(f"  已寫入 {min(i + BATCH, len(items))}/{len(items)}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="實際寫入（預設只預演）")
    ap.add_argument("--source", help="只處理指定來源")
    ap.add_argument("--out", help="預演明細輸出 JSON 路徑")
    args = ap.parse_args()
    load_dotenv(REPO / ".env")
    with connect() as conn:
        docs = load_documents(conn)
    if args.source:
        docs = [d for d in docs if d["source"] == args.source]
    driver = GraphDatabase.driver(
        "bolt://127.0.0.1:7687",
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    current: dict[str, list[str]] = {}
    with driver.session() as session:
        ids = [d["external_id"] for d in docs]
        for i in range(0, len(ids), 1000):
            for r in session.run(_CURRENT_QUERY, ids=ids[i : i + 1000]):
                current[r["id"]] = r["names"]
    items = plan(docs, current)
    report(items)
    if args.out:
        Path(args.out).write_text(
            json.dumps(
                [
                    {k: it[k] for k in ("external_id", "source", "old", "new", "expire")}
                    for it in items
                ],
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
    if args.apply:
        apply(driver, [it for it in items if it["add"] or it["expire"]])
        print("完成；之後請執行 python3 -m subscribers refresh-artist-sources")
    driver.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
