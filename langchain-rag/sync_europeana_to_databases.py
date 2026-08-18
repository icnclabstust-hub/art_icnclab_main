#!/usr/bin/env python3
"""
Europeana 專用同步腳本
自動抓 data/raw/europeana/ 下最新一份 europeana_crawled_*.json，累加寫入 Neo4j + ChromaDB
（不清除舊資料，依 europeanaId 用 MERGE/upsert，同一件作品重複爬到只會更新、
不會產生重複節點；不同天爬到的不同作品會持續累積）。
寫入 ChromaDB 前會先用 chunk_text() 切塊（512 字元一塊、重疊 64 字元），
文字未超過門檻的一般短文件會直接整段當一塊，不受影響。

用法:
    python3 sync_europeana_to_databases.py
"""

import json
import logging
import os
from pathlib import Path

import chromadb
from bge_m3_embedding import BGEM3EmbeddingFunction
from chunking import build_chunk_records
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 原生 Neo4j（WSL 直接執行，非 Docker）；7688 是因為 WSL 環境本身有另一個系統 Neo4j 服務佔用了 7687
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7688")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
if not NEO4J_PASSWORD:
    raise RuntimeError(
        "缺少 NEO4J_PASSWORD 環境變數。請在啟動前設定，例如："
        "NEO4J_PASSWORD=... python3 sync_europeana_to_databases.py"
        "（daily_crawl_and_sync.sh 已內建設定，不需手動處理）"
    )
CHROMADB_HOST = os.getenv("CHROMADB_HOST", "localhost")
CHROMADB_PORT = int(os.getenv("CHROMADB_PORT", "8000"))
DATA_DIR = Path(os.getenv("DATA_RAW_DIR", str(Path(__file__).parent.parent / "data" / "raw")))
MIN_FILE_SIZE_BYTES = 1024


def find_latest_europeana_file():
    candidates = [
        f
        for f in DATA_DIR.rglob("europeana_crawled_*.json")
        if f.stat().st_size >= MIN_FILE_SIZE_BYTES
    ]
    if not candidates:
        raise FileNotFoundError(f"找不到任何 europeana_crawled_*.json 檔案於 {DATA_DIR}")
    latest = max(candidates, key=lambda f: f.stat().st_mtime)
    return latest


def safe_date(value):
    """Europeana 部分項目 date 是 {'def': '1900/1907'} 這種語系物件，這裡轉成純字串"""
    if value is None:
        return ""
    if isinstance(value, dict):
        return value.get("def") or next(iter(value.values()), "") or ""
    return str(value)


def main():
    latest_file = find_latest_europeana_file()
    logger.info(f"🗂️  使用最新檔案: {latest_file.name}")

    with open(latest_file, encoding="utf-8") as f:
        payload = json.load(f)
    items = payload["data"] if isinstance(payload, dict) else payload
    logger.info(f"讀取到 {len(items)} 筆 Europeana 資料")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    logger.info("✅ Neo4j 連線成功")

    client = chromadb.HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)
    collection = client.get_or_create_collection(
        name="art_history_bgem3", embedding_function=BGEM3EmbeddingFunction()
    )

    ids, documents, metadatas = [], [], []
    neo4j_ok, neo4j_err = 0, 0

    with driver.session() as session:
        for item in items:
            europeana_id = item.get("europeanaId") or f"euro_unknown_{len(ids)}"
            title = item.get("title") or "Untitled"
            creators = item.get("creator") or []
            creator_str = ", ".join(creators) if creators else ""
            date = safe_date(item.get("date"))
            description = item.get("description") or ""
            provider = item.get("provider") or ""
            country = item.get("country") or ""
            url = item.get("europeanaUrl") or ""

            text_parts = [f"Title: {title}"]
            if creator_str:
                text_parts.append(f"Creator: {creator_str}")
            if date:
                text_parts.append(f"Date: {date}")
            if country:
                text_parts.append(f"Country: {country}")
            if provider:
                text_parts.append(f"Provider: {provider}")
            if description:
                text_parts.append(f"Description: {description}")
            document_text = "\n".join(text_parts)

            node_id = f"europeana_{europeana_id}".replace("/", "_")[:128]
            chunk_ids, chunk_docs, chunk_metas = build_chunk_records(
                node_id,
                document_text,
                {
                    "title": str(title)[:500],
                    "artist": str(creator_str)[:200],
                    "date": str(date)[:100],
                    "source": "europeana",
                },
            )
            ids.extend(chunk_ids)
            documents.extend(chunk_docs)
            metadatas.extend(chunk_metas)

            try:
                session.run(
                    """
                    MERGE (a:Artwork {id: $id})
                    SET a.title = $title,
                        a.date = $date,
                        a.source = 'europeana',
                        a.description = $description,
                        a.provider = $provider,
                        a.country = $country,
                        a.url = $url,
                        a.updated_at = datetime()
                    """,
                    id=node_id,
                    title=title,
                    date=date,
                    description=description[:1000],
                    provider=provider,
                    country=country,
                    url=url,
                )
                if creator_str:
                    for creator_name in creators:
                        if creator_name and creator_name.strip():
                            session.run(
                                """
                                MERGE (artist:Artist {name: $name})
                                WITH artist
                                MATCH (artwork:Artwork {id: $artwork_id})
                                MERGE (artist)-[:CREATED]->(artwork)
                                """,
                                name=creator_name.strip(),
                                artwork_id=node_id,
                            )
                neo4j_ok += 1
            except Exception as e:
                neo4j_err += 1
                logger.error(f"Neo4j 寫入失敗 ({europeana_id}): {e}")

    driver.close()
    logger.info(f"Neo4j: 成功 {neo4j_ok}, 失敗 {neo4j_err}")

    batch_size = 100
    added = 0
    for i in range(0, len(ids), batch_size):
        # upsert 而非 add：同一個 id 重複寫入會更新既有向量，不會報錯也不會產生重複
        collection.upsert(
            ids=ids[i : i + batch_size],
            documents=documents[i : i + batch_size],
            metadatas=metadatas[i : i + batch_size],
        )
        added += len(ids[i : i + batch_size])
        logger.info(f"ChromaDB 進度 {added}/{len(ids)}")

    logger.info(f"✅ ChromaDB 累加/更新 {added} 筆，collection 目前總數: {collection.count()}")


if __name__ == "__main__":
    main()
