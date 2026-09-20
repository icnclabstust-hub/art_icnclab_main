"""命令列：``python -m subscribers run --target chromadb|elasticsearch|neo4j [--once]``，
以及 ``python -m subscribers purge-neo4j [--days 30] [--apply]``（清除超過保留期的到期資料）。"""

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
    if target == "neo4j":
        return _neo4j_subscriber(allow_empty_graph)
    if target == "chromadb":
        from subscribers.chroma_sub import ChromaSubscriber  # noqa: PLC0415

        return ChromaSubscriber(_chroma_collection(with_embedding_function=True))
    from elasticsearch import Elasticsearch  # noqa: PLC0415
    from elasticsearch.helpers import bulk  # noqa: PLC0415

    from subscribers.es_sub import ElasticsearchSubscriber  # noqa: PLC0415

    password = os.getenv("ES_PASSWORD")
    if not password:
        raise SystemExit("缺少 ES_PASSWORD 環境變數")
    es = Elasticsearch(
        os.getenv("ES_URL", "https://localhost:9200"),
        basic_auth=(os.getenv("ES_USERNAME", "elastic"), password),
        verify_certs=False,
    )
    return ElasticsearchSubscriber(es, _chroma_collection(with_embedding_function=False), bulk)


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
    run.add_argument("--target", required=True, choices=["chromadb", "elasticsearch", "neo4j"])
    run.add_argument("--once", action="store_true", help="追上後即結束（預設持續輪詢）")
    run.add_argument(
        "--allow-empty-graph", action="store_true", help="允許寫入沒有 Artwork 節點的 Neo4j"
    )
    purge_cmd = sub.add_parser("purge-neo4j", help="清除 Neo4j 超過保留期的到期關係與軟刪除作品")
    purge_cmd.add_argument("--days", type=int, default=30, help="保留天數（預設 30）")
    purge_cmd.add_argument("--apply", action="store_true", help="實際刪除（預設只預覽）")
    purge_cmd.set_defaults(purge=True)

    args = parser.parse_args(argv)

    if args.command == "purge-neo4j":
        return _cmd_purge_neo4j(args)

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
