#!/usr/bin/env python3
"""
統一博物館資料匯入腳本
將各博物館 API 爬蟲產出的資料（data/raw/ 下的 JSON 檔）同時寫入 Neo4j 知識圖譜
（供 GraphRAG 使用）與 ChromaDB 向量資料庫（供 VectorOnlyRAG/Advanced RAG 使用）。

每個來源自動挑選 data/raw/ 下「最新一份」符合的快照檔案匯入（見 SOURCE_PATTERNS）。

預設為「累加模式」：不清除舊資料，只用 MERGE（依各來源的穩定 id，如 met_{id}、
harvard_{harvardId}）寫入。同一件作品重複爬到只會更新屬性、不會產生重複節點；
不同天爬到的不同作品會持續累積，圖譜只會越來越完整，不會因為某次爬蟲抓到的
子集合較小而遺失先前已收集的資料。

用法:
    python import_all_museums_to_neo4j.py          # 累加模式（預設）：只 MERGE，不清除舊資料
    python import_all_museums_to_neo4j.py --clean  # 清除模式：先清空非 Europeana 資料再重建
                                                     # （僅在需要修正資料品質問題時使用）
"""

import json
import logging
import os
import re
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
        "NEO4J_PASSWORD=... python3 import_all_museums_to_neo4j.py"
        "（daily_crawl_and_sync.sh 已內建設定，不需手動處理）"
    )
DATA_DIR = Path(os.getenv("DATA_RAW_DIR", str(Path(__file__).parent.parent / "data" / "raw")))
CHROMADB_HOST = os.getenv("CHROMADB_HOST", "localhost")
CHROMADB_PORT = int(os.getenv("CHROMADB_PORT", "8000"))
CHROMA_BATCH_SIZE = 100

# 忽略明顯是失敗/空跑產生的極小檔案
MIN_FILE_SIZE_BYTES = 1024

# 每個博物館來源要匹配的檔名正規表示式列表；每個 pattern 只取「最新一份」符合的檔案
SOURCE_PATTERNS = {
    "google_books": [r"^google_books_art_.*\.json$"],
    # 兩種命名法是同一資料的不同世代快照，用 alternation 合成一個 pattern 只取整體最新一份
    "harvard": [r"^(harvard_art_museums_.*|harvard_objects)\.json$"],
    "masterpieces_curated": [r"^masterpieces_curated\.json$"],
    "met_museum": [
        r"^met_museum_crawled_.*\.json$",
        r"^renaissance_baroque_\d.*\.json$",
        r"^renaissance_baroque_quick_.*\.json$",
    ],
    "specialized_art": [r"^specialized_art_.*\.json$"],
    "art_institute_chicago": [r"^art_institute_chicago_crawled_.*\.json$"],
    "va_museum": [r"^va_museum_crawled_.*\.json$"],
    "cleveland_museum": [r"^cleveland_museum_crawled_.*\.json$"],
    "yale_university_art_gallery": [r"^yale_university_art_gallery_crawled_.*\.json$"],
}


def resolve_sources() -> dict[str, list[str]]:
    """對每個 pattern 找出 data/raw/<來源子資料夾>/ 下最新且非空跑的檔案（遞迴搜尋所有子資料夾）"""
    all_files = [f for f in DATA_DIR.rglob("*.json") if f.stat().st_size >= MIN_FILE_SIZE_BYTES]
    resolved = {}
    for source, patterns in SOURCE_PATTERNS.items():
        picked = []
        for pattern in patterns:
            regex = re.compile(pattern)
            matches = [f for f in all_files if regex.match(f.name)]
            if matches:
                latest = max(matches, key=lambda f: f.stat().st_mtime)
                picked.append(str(latest.relative_to(DATA_DIR)))
                logger.info(f"🗂️  {source} <- 自動選用最新檔案: {latest.relative_to(DATA_DIR)}")
            else:
                logger.warning(f"⚠️ {source}: 找不到符合 pattern 的檔案: {pattern}")
        resolved[source] = picked
    return resolved


# 保留不動的來源（已由專用腳本乾淨匯入，不在這裡重複處理）
PRESERVE_SOURCES = ["europeana"]


def safe_str(value, max_len: int | None = None) -> str:
    """安全轉字串：None -> ''，list -> 逗號合併，其餘 str()"""
    if value is None:
        return ""
    if isinstance(value, list):
        text = ", ".join(safe_str(v) for v in value if v)
    elif isinstance(value, dict):
        text = value.get("def") or json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    return text[:max_len] if max_len else text


def load_items(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "items", "records", "artworks"):
            if key in data and isinstance(data[key], list):
                return data[key]
    return []


def normalize_google_books(item: dict) -> dict:
    return {
        "id": f"googlebooks_{item.get('id')}",
        "title": safe_str(item.get("title"), 500) or "Untitled",
        "artist": safe_str(item.get("authors"), 200),
        "date": safe_str(item.get("publishedDate"), 100),
        "medium": "",
        "culture": "",
        "period": "",
        "department": safe_str(item.get("categories"), 200),
        "description": safe_str(item.get("publisher"), 1000),
        "url": safe_str(item.get("infoLink")),
    }


def normalize_harvard(item: dict) -> dict:
    people = item.get("people") or []
    artist = ", ".join(
        p.get("displayname", "") for p in people if isinstance(p, dict) and p.get("displayname")
    )
    return {
        "id": f"harvard_{item.get('harvardId') or item.get('id')}",
        "title": safe_str(item.get("title"), 500) or "Untitled",
        "artist": artist,
        "date": safe_str(item.get("dated"), 100),
        "medium": safe_str(item.get("medium"), 300),
        "culture": safe_str(item.get("culture"), 200),
        "period": safe_str(item.get("period"), 200),
        "department": safe_str(item.get("department"), 200),
        "description": safe_str(item.get("description"), 1000),
        "url": safe_str(item.get("url")),
    }


def normalize_masterpiece(item: dict) -> dict:
    return {
        "id": safe_str(item.get("id")) or f"masterpiece_{item.get('title')}",
        "title": safe_str(item.get("title"), 500) or "Untitled",
        "artist": safe_str(item.get("artist"), 200),
        "date": safe_str(item.get("date"), 100),
        "medium": safe_str(item.get("medium"), 300),
        "culture": safe_str(item.get("culture"), 200),
        "period": safe_str(item.get("period"), 200),
        "department": safe_str(item.get("department"), 200),
        "description": safe_str(item.get("description"), 1000),
        "url": safe_str(item.get("primaryImage")),
    }


def normalize_met_like(item: dict) -> dict:
    """met_museum_crawled 與 renaissance_baroque 都來自 Met API，共用同一 id 空間以自然去重"""
    return {
        "id": f"met_{item.get('id')}",
        "title": safe_str(item.get("title"), 500) or "Untitled",
        "artist": safe_str(item.get("artist"), 200),
        "date": safe_str(item.get("date"), 100),
        "medium": safe_str(item.get("medium"), 300),
        "culture": safe_str(item.get("culture"), 200),
        "period": safe_str(item.get("period"), 200),
        "department": safe_str(item.get("department"), 200),
        "description": safe_str(item.get("creditLine") or item.get("classification"), 1000),
        "url": safe_str(item.get("objectURL")),
    }


def normalize_specialized_art(item: dict) -> dict:
    raw_id = safe_str(item.get("id")) or item.get("sourceUrl", "")
    clean_id = re.sub(r"[^A-Za-z0-9_\-]", "_", raw_id)[:150]
    creator = safe_str(item.get("creator"))
    if creator in ("未知創作者", "Unknown", ""):
        creator = ""
    return {
        "id": f"specialized_{clean_id}",
        "title": safe_str(item.get("title"), 500) or "Untitled",
        "artist": creator,
        "date": safe_str(item.get("date"), 100),
        "medium": safe_str(item.get("type"), 200),
        "culture": safe_str(item.get("country"), 200),
        "period": "",
        "department": safe_str(item.get("provider") or item.get("dataProvider"), 300),
        "description": safe_str(item.get("description"), 1000),
        "url": safe_str(item.get("sourceUrl")),
    }


def normalize_art_institute_chicago(item: dict) -> dict:
    return {
        "id": f"aic_{item.get('id')}",
        "title": safe_str(item.get("title"), 500) or "Untitled",
        "artist": safe_str(item.get("artist"), 200),
        "date": safe_str(item.get("date"), 100),
        "medium": safe_str(item.get("medium"), 300),
        "culture": safe_str(item.get("culture"), 200),
        "period": "",
        "department": safe_str(item.get("department"), 200),
        "description": safe_str(item.get("description"), 1000),
        "url": safe_str(item.get("objectURL")),
    }


def normalize_va_museum(item: dict) -> dict:
    return {
        "id": f"va_{item.get('id')}",
        "title": safe_str(item.get("title"), 500) or "Untitled",
        "artist": safe_str(item.get("artist"), 200),
        "date": safe_str(item.get("date"), 100),
        "medium": safe_str(item.get("medium"), 300),
        "culture": safe_str(item.get("culture"), 200),
        "period": "",
        "department": safe_str(item.get("department"), 200),
        "description": safe_str(item.get("description"), 1000),
        "url": safe_str(item.get("objectURL")),
    }


def normalize_cleveland_museum(item: dict) -> dict:
    return {
        "id": f"cma_{item.get('id')}",
        "title": safe_str(item.get("title"), 500) or "Untitled",
        "artist": safe_str(item.get("artist"), 200),
        "date": safe_str(item.get("date"), 100),
        "medium": safe_str(item.get("medium"), 300),
        "culture": safe_str(item.get("culture"), 200),
        "period": "",
        "department": safe_str(item.get("department"), 200),
        "description": safe_str(item.get("description"), 1000),
        "url": safe_str(item.get("objectURL")),
    }


def normalize_yale_university_art_gallery(item: dict) -> dict:
    return {
        "id": f"yale_{item.get('id')}",
        "title": safe_str(item.get("title"), 500) or "Untitled",
        "artist": safe_str(item.get("artist"), 200),
        "date": safe_str(item.get("date"), 100),
        "medium": safe_str(item.get("medium"), 300),
        "culture": safe_str(item.get("culture"), 200),
        "period": "",
        "department": safe_str(item.get("department"), 200),
        "description": safe_str(item.get("description"), 1000),
        "url": safe_str(item.get("objectURL")),
    }


NORMALIZERS = {
    "google_books": normalize_google_books,
    "harvard": normalize_harvard,
    "masterpieces_curated": normalize_masterpiece,
    "met_museum": normalize_met_like,
    "specialized_art": normalize_specialized_art,
    "art_institute_chicago": normalize_art_institute_chicago,
    "va_museum": normalize_va_museum,
    "cleveland_museum": normalize_cleveland_museum,
    "yale_university_art_gallery": normalize_yale_university_art_gallery,
}


NEO4J_BATCH_SIZE = 500

_ARTWORK_UNWIND_QUERY = """
UNWIND $rows AS row
MERGE (a:Artwork {id: row.id})
SET a.title = row.title,
    a.date = row.date,
    a.medium = row.medium,
    a.culture = row.culture,
    a.period = row.period,
    a.department = row.department,
    a.description = row.description,
    a.url = row.url,
    a.source = row.source,
    a.updated_at = datetime()
"""

_ARTIST_UNWIND_QUERY = """
UNWIND $rows AS row
MERGE (artist:Artist {name: row.artist_name})
SET artist.source = coalesce(artist.source, row.source)
WITH artist, row
MATCH (artwork:Artwork {id: row.artwork_id})
MERGE (artist)-[:CREATED]->(artwork)
"""


class Neo4jBatchWriter:
    """累積 Artwork 節點與 Artist 關係資料，滿一批（或手動 flush）才用 UNWIND 一次送出，
    大幅減少跟 Neo4j 的網路往返次數（原本是每筆資料各自呼叫一次 session.run()）。"""

    def __init__(self, session, batch_size: int = NEO4J_BATCH_SIZE):
        self.session = session
        self.batch_size = batch_size
        self.artwork_rows: list[dict] = []
        self.artist_rows: list[dict] = []
        self.total_artworks = 0
        self.total_artist_links = 0
        self.total_errors = 0

    def add(self, source: str, artwork: dict):
        row = dict(artwork)
        row["source"] = source
        self.artwork_rows.append(row)
        if artwork.get("artist"):
            for artist_name in [n.strip() for n in artwork["artist"].split(",") if n.strip()]:
                self.artist_rows.append(
                    {
                        "artist_name": artist_name,
                        "artwork_id": artwork["id"],
                        "source": source,
                    }
                )
        if len(self.artwork_rows) >= self.batch_size:
            self.flush()

    def flush(self):
        if self.artwork_rows:
            try:
                self.session.run(_ARTWORK_UNWIND_QUERY, rows=self.artwork_rows).consume()
                self.total_artworks += len(self.artwork_rows)
            except Exception as e:
                self.total_errors += len(self.artwork_rows)
                logger.error(f"❌ Neo4j Artwork 批次寫入失敗（{len(self.artwork_rows)} 筆）: {e}")
            self.artwork_rows = []
        if self.artist_rows:
            try:
                self.session.run(_ARTIST_UNWIND_QUERY, rows=self.artist_rows).consume()
                self.total_artist_links += len(self.artist_rows)
            except Exception as e:
                logger.error(f"❌ Neo4j Artist 關係批次寫入失敗（{len(self.artist_rows)} 筆）: {e}")
            self.artist_rows = []


def build_document_text(artwork: dict) -> str:
    """組成給 ChromaDB 的文件文字，欄位組合方式與 Europeana 同步腳本一致；
    文字若超過切塊門檻，會在寫入 ChromaDB 時由 chunk_text() 進一步切塊"""
    parts = [f"Title: {artwork['title']}"]
    if artwork.get("artist"):
        parts.append(f"Creator: {artwork['artist']}")
    if artwork.get("date"):
        parts.append(f"Date: {artwork['date']}")
    if artwork.get("medium"):
        parts.append(f"Medium: {artwork['medium']}")
    if artwork.get("culture"):
        parts.append(f"Culture: {artwork['culture']}")
    if artwork.get("period"):
        parts.append(f"Period: {artwork['period']}")
    if artwork.get("department"):
        parts.append(f"Department: {artwork['department']}")
    if artwork.get("description"):
        parts.append(f"Description: {artwork['description']}")
    return "\n".join(parts)


class ChromaBatchWriter:
    """累積 upsert 資料，滿一批（或手動 flush）才送出去，減少 HTTP 往返次數。

    來源原始資料本身可能含有重複 id（見 check_duplicates.py 的報告），而 ChromaDB
    的 upsert() 只要同一批次內出現重複 id 就會整批報錯，所以這裡在加入前先檢查
    目前這批有沒有撞到，撞到就先把現有的這批送出去，確保永遠不會有重複 id 同批送出。
    """

    def __init__(self, collection, batch_size: int = CHROMA_BATCH_SIZE):
        self.collection = collection
        self.batch_size = batch_size
        self.ids: list[str] = []
        self.documents: list[str] = []
        self.metadatas: list[dict] = []
        self._pending_ids: set = set()
        self.total_written = 0
        self.total_errors = 0

    def add(self, source: str, artwork: dict):
        metadata = {
            "title": artwork["title"][:500],
            "artist": artwork["artist"][:200],
            "date": artwork["date"][:100],
            "source": source,
        }
        chunk_ids, chunk_docs, chunk_metas = build_chunk_records(
            artwork["id"], build_document_text(artwork), metadata
        )
        chunk_rows = zip(chunk_ids, chunk_docs, chunk_metas, strict=True)
        for chunk_id, chunk_doc, chunk_meta in chunk_rows:
            if chunk_id in self._pending_ids:
                self.flush()
            self.ids.append(chunk_id)
            self._pending_ids.add(chunk_id)
            self.documents.append(chunk_doc)
            self.metadatas.append(chunk_meta)
            if len(self.ids) >= self.batch_size:
                self.flush()

    def flush(self):
        if not self.ids:
            return
        try:
            self.collection.upsert(ids=self.ids, documents=self.documents, metadatas=self.metadatas)
            self.total_written += len(self.ids)
        except Exception as e:
            self.total_errors += len(self.ids)
            logger.error(f"❌ ChromaDB 批次寫入失敗（{len(self.ids)} 筆）: {e}")
        finally:
            self.ids, self.documents, self.metadatas = [], [], []
            self._pending_ids = set()


def clean_previous_import(session):
    result = session.run(
        "MATCH (a:Artwork) WHERE NOT a.source IN $preserve DETACH DELETE a RETURN count(a) as c",
        preserve=PRESERVE_SOURCES,
    )
    result.consume()
    orphans = session.run("MATCH (a:Artist) WHERE NOT (a)--() DETACH DELETE a RETURN count(a) as c")
    orphans.consume()
    logger.info("已清除先前非 Europeana 的 Artwork 節點與孤立 Artist 節點")


def ensure_fulltext_indexes(session):
    indexes = [
        (
            "artist_name_fulltext",
            "CREATE FULLTEXT INDEX artist_name_fulltext "
            "IF NOT EXISTS FOR (n:Artist) ON EACH [n.name]",
        ),
        (
            "artwork_title_fulltext",
            "CREATE FULLTEXT INDEX artwork_title_fulltext "
            "IF NOT EXISTS FOR (n:Artwork) ON EACH [n.title]",
        ),
        (
            "artwork_description_fulltext",
            "CREATE FULLTEXT INDEX artwork_description_fulltext "
            "IF NOT EXISTS FOR (n:Artwork) ON EACH [n.description]",
        ),
    ]
    for name, query in indexes:
        session.run(query).consume()
        logger.info(f"✅ 索引就緒: {name}")


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clean",
        action="store_true",
        help="清除模式：先清空非 Europeana 的舊資料再重建（預設為累加模式，不清除）",
    )
    args = parser.parse_args()

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    logger.info("✅ Neo4j 連接成功")

    chroma_client = chromadb.HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)
    chroma_collection = chroma_client.get_or_create_collection(
        name="art_history_bgem3", embedding_function=BGEM3EmbeddingFunction()
    )
    chroma_writer = ChromaBatchWriter(chroma_collection)
    logger.info(f"✅ ChromaDB 連接成功 (collection 目前總數: {chroma_collection.count()})")

    with driver.session() as session:
        if args.clean:
            clean_previous_import(session)
        else:
            logger.info(
                "📌 累加模式：不清除舊資料，只用 MERGE 更新/新增"
                "（同一作品重複爬到不會產生重複節點）"
            )

        neo4j_writer = Neo4jBatchWriter(session)
        sources = resolve_sources()

        stats = {}
        for source, filenames in sources.items():
            normalizer = NORMALIZERS[source]
            ok, err = 0, 0
            for filename in filenames:
                if not (DATA_DIR / filename).exists():
                    logger.warning(f"⚠️ 找不到檔案，略過: {filename}")
                    continue
                items = load_items(filename)
                logger.info(f"📂 {source} <- {filename}: {len(items)} 筆")
                for item in items:
                    try:
                        artwork = normalizer(item)
                        neo4j_writer.add(source, artwork)
                        chroma_writer.add(source, artwork)
                        ok += 1
                    except Exception as e:
                        err += 1
                        logger.error(f"❌ {source} 寫入失敗: {e}")
            stats[source] = {"ok": ok, "err": err}
            logger.info(f"✅ {source}: 成功 {ok}, 失敗 {err}")

        neo4j_writer.flush()
        logger.info(
            f"✅ Neo4j 批次寫入完成，Artwork {neo4j_writer.total_artworks} 筆、"
            f"Artist 關係 {neo4j_writer.total_artist_links} 筆"
            f"（失敗批次筆數 {neo4j_writer.total_errors}）"
        )

        ensure_fulltext_indexes(session)

    driver.close()

    chroma_writer.flush()
    logger.info(
        f"✅ ChromaDB 累加/更新完成，本次寫入 {chroma_writer.total_written} 筆"
        f"（失敗 {chroma_writer.total_errors} 筆），"
        f"collection 目前總數: {chroma_collection.count()}"
    )

    logger.info("=" * 60)
    logger.info("📊 匯入摘要")
    for source, s in stats.items():
        logger.info(f"  {source}: {s['ok']} 成功 / {s['err']} 失敗")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
