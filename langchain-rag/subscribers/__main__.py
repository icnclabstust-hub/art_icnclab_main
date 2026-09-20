"""命令列：``python -m subscribers run --target chromadb|elasticsearch [--once]``。

Neo4j 訂閱器待 Neo4j 埠號整併後另行加入（見設計文件 §11）。
"""

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


def _build_subscriber(target: str):
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
    run.add_argument("--target", required=True, choices=["chromadb", "elasticsearch"])
    run.add_argument("--once", action="store_true", help="追上後即結束（預設持續輪詢）")
    args = parser.parse_args(argv)

    subscriber = _build_subscriber(args.target)
    with connect() as conn:
        while True:
            handled = run_once(conn, subscriber)
            print(f"[{subscriber.name}] 處理 {handled} 筆，剩餘落後 {lag(conn, subscriber.name)}")
            if args.once:
                return 0
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
