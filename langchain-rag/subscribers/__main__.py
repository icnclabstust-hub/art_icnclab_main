"""命令列：``python -m subscribers run --target chromadb|elasticsearch|neo4j|cache [--once]``，
``python -m subscribers purge-neo4j [--days 30] [--apply]``（清除超過保留期的到期資料），
``python -m subscribers refresh-artist-sources``（重算全部藝術家的來源清單），
以及 ``python -m subscribers label-embeddings [--apply]``（既有向量補嵌入模型標註，DAT-30）。"""

import argparse
import logging
import os
import sys
import time

from ingest.db import connect

from subscribers.base import lag, run_once

DEFAULT_COLLECTION = "art_history_bgem3"
POLL_INTERVAL_SECONDS = 30


def _chroma_collection(with_embedding_function: bool):
    import chromadb  # noqa: PLC0415 -- 只有實際執行訂閱器才需要

    client = chromadb.HttpClient(
        host=os.getenv("CHROMADB_HOST", "localhost"), port=int(os.getenv("CHROMADB_PORT", "8000"))
    )
    name = os.getenv("CHROMADB_COLLECTION", DEFAULT_COLLECTION)
    if not with_embedding_function:
        return client.get_collection(name=name)
    from bge_m3_embedding import BGEM3EmbeddingFunction  # noqa: PLC0415

    return client.get_or_create_collection(name=name, embedding_function=BGEM3EmbeddingFunction())


def _neo4j_subscriber(allow_empty_graph: bool):
    from neo4j import GraphDatabase  # noqa: PLC0415

    from subscribers.neo4j_sub import Neo4jSubscriber, ensure_schema  # noqa: PLC0415

    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        raise SystemExit("缺少 NEO4J_PASSWORD 環境變數")
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), password),
    )
    driver.verify_connectivity()
    if not allow_empty_graph:
        # 防呆：整併前 7687 可能是 WSL 系統自帶的 Neo4j（無藝術史資料），寫錯實例會造成分歧
        with driver.session() as session:
            artworks = session.run("MATCH (a:Artwork) RETURN count(a) AS c").single()["c"]
        if artworks == 0:
            raise SystemExit(
                "目標 Neo4j 沒有任何 Artwork 節點，疑似連到錯的實例"
                "（例如 WSL 系統自帶的 neo4j.service）。確認無誤才加 --allow-empty-graph"
            )
    with driver.session() as session:
        ensure_schema(session)
    return Neo4jSubscriber(driver.session)


def _build_subscriber(target: str, allow_empty_graph: bool = False):
    if target == "cache":  # Redis 查詢快取失效（RET-12）
        from redis_cache import RedisQueryCache, connect_redis  # noqa: PLC0415

        from subscribers.cache_sub import CacheInvalidationSubscriber  # noqa: PLC0415

        url = os.getenv("RAG_CACHE_REDIS_URL", "redis://localhost:6379/0")
        client = connect_redis(url, os.getenv("REDIS_PASSWORD"))
        return CacheInvalidationSubscriber(RedisQueryCache(client))
    if target == "neo4j":
        return _neo4j_subscriber(allow_empty_graph)
    if target == "chromadb":
        from embedding_labels import current_embedding_labels  # noqa: PLC0415

        from subscribers.chroma_sub import ChromaSubscriber  # noqa: PLC0415

        return ChromaSubscriber(
            _chroma_collection(with_embedding_function=True),
            embedding_labels=current_embedding_labels(),
        )
    from elasticsearch.helpers import bulk  # noqa: PLC0415

    from subscribers.es_sub import ElasticsearchSubscriber  # noqa: PLC0415

    return ElasticsearchSubscriber(
        es_client(), _chroma_collection(with_embedding_function=False), bulk
    )


def es_client():
    """以環境變數建立 Elasticsearch 用戶端（本機自簽憑證）。"""
    from elasticsearch import Elasticsearch  # noqa: PLC0415

    password = os.getenv("ES_PASSWORD")
    if not password:
        raise SystemExit("缺少 ES_PASSWORD 環境變數")
    return Elasticsearch(
        os.getenv("ES_URL", "https://localhost:9200"),
        basic_auth=(os.getenv("ES_USERNAME", "elastic"), password),
        verify_certs=False,
    )


def chroma_collection():
    """不掛 embedding function 的 collection（只讀 metadata／向量時使用）。"""
    return _chroma_collection(with_embedding_function=False)


def _cmd_label_embeddings(args: argparse.Namespace) -> int:
    from bge_m3_embedding import BGEM3EmbeddingFunction  # noqa: PLC0415
    from embedding_labels import current_embedding_labels  # noqa: PLC0415

    from subscribers import labels as labels_module  # noqa: PLC0415
    from subscribers.es_sub import ES_INDEX  # noqa: PLC0415

    labels = current_embedding_labels()
    collection = chroma_collection()
    worst = labels_module.verify_sample(collection, BGEM3EmbeddingFunction(), args.sample)
    print(f"抽樣 {args.sample} 個 chunk 以目前模型重算：最小 cosine {worst:.6f}")
    if worst < labels_module.MIN_COSINE:
        print(
            f"❌ 低於 {labels_module.MIN_COSINE}：庫存向量與目前模型版本不同，"
            "不可只補標籤，應全量重建（DAT-32）"
        )
        return 1
    chroma_n = labels_module.label_chroma(collection, labels, apply=args.apply)
    es_n = labels_module.label_es(es_client(), ES_INDEX, labels, apply=args.apply)
    mode = "已補標" if args.apply else "預覽（未寫入，加 --apply 才會寫入）"
    print(f"[{mode}] 標註 {labels}：ChromaDB {chroma_n} 筆、Elasticsearch {es_n} 筆")
    return 0


def _cmd_purge_neo4j(args: argparse.Namespace) -> int:
    from neo4j import GraphDatabase  # noqa: PLC0415

    from subscribers.neo4j_sub import purge  # noqa: PLC0415

    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        raise SystemExit("缺少 NEO4J_PASSWORD 環境變數")
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), password),
    )
    with driver.session() as session:
        counts = purge(session, args.days, apply=args.apply)
    mode = "已刪除" if args.apply else "預覽（未刪除，加 --apply 才會刪除）"
    print(f"[{mode}] 保留 {args.days} 天：" + "／".join(f"{k} {v}" for k, v in counts.items()))
    return 0


def _cmd_refresh_artist_sources(_args: argparse.Namespace) -> int:
    from neo4j import GraphDatabase  # noqa: PLC0415

    from subscribers.neo4j_sub import refresh_artist_sources  # noqa: PLC0415

    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        raise SystemExit("缺少 NEO4J_PASSWORD 環境變數")
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), password),
    )
    with driver.session() as session:
        count = refresh_artist_sources(session)
    print(f"已重算 {count} 位藝術家的 sources")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 進入點。

    Args:
        argv: 參數清單；省略時用 ``sys.argv``。

    Returns:
        行程結束碼。
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(prog="subscribers")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="消費 catalog.sync_events")
    run.add_argument(
        "--target", required=True, choices=["chromadb", "elasticsearch", "neo4j", "cache"]
    )
    run.add_argument("--once", action="store_true", help="追上後即結束（預設持續輪詢）")
    run.add_argument(
        "--allow-empty-graph", action="store_true", help="允許寫入沒有 Artwork 節點的 Neo4j"
    )
    purge_cmd = sub.add_parser("purge-neo4j", help="清除 Neo4j 超過保留期的到期關係與軟刪除作品")
    purge_cmd.add_argument("--days", type=int, default=30, help="保留天數（預設 30）")
    purge_cmd.add_argument("--apply", action="store_true", help="實際刪除（預設只預覽）")
    purge_cmd.set_defaults(purge=True)
    sub.add_parser("refresh-artist-sources", help="重算全部藝術家的來源清單（可重複執行）")
    label_cmd = sub.add_parser(
        "label-embeddings", help="替既有向量補上嵌入模型標註（先抽樣重算確認同版本）"
    )
    label_cmd.add_argument("--sample", type=int, default=30, help="抽樣重算的 chunk 數")
    label_cmd.add_argument("--apply", action="store_true", help="實際寫入（預設只預覽）")

    args = parser.parse_args(argv)

    if args.command == "purge-neo4j":
        return _cmd_purge_neo4j(args)
    if args.command == "refresh-artist-sources":
        return _cmd_refresh_artist_sources(args)
    if args.command == "label-embeddings":
        return _cmd_label_embeddings(args)

    subscriber = _build_subscriber(args.target, args.allow_empty_graph)
    with connect() as conn:
        while True:
            handled = run_once(conn, subscriber)
            print(f"[{subscriber.name}] 處理 {handled} 筆，剩餘落後 {lag(conn, subscriber.name)}")
            if args.once:
                return 0
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
