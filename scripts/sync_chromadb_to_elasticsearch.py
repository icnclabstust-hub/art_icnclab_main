"""把 ChromaDB「art_history_bgem3」collection 的資料（含已算好的 BGE-M3 embedding）
同步進 Elasticsearch，建立支援 BM25 全文檢索 + 向量 kNN 的 index，供 hybrid_es_rag 策略使用。

不重新計算 embedding：直接沿用 ChromaDB 裡已經存好的向量，避免浪費 Ollama 算力。
可重複執行：用 chunk id 當 ES document id，重跑只會覆蓋更新，不會產生重複。
"""

import os

import chromadb
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

ES_URL = os.getenv("ES_URL", "https://localhost:9200")
ES_USERNAME = os.getenv("ES_USERNAME", "elastic")
ES_PASSWORD = os.getenv("ES_PASSWORD")
if not ES_PASSWORD:
    raise RuntimeError(
        "缺少 ES_PASSWORD 環境變數。請在啟動前設定，例如："
        "ES_PASSWORD=... python3 sync_chromadb_to_elasticsearch.py"
    )

CHROMADB_HOST = os.getenv("CHROMADB_HOST", "localhost")
CHROMADB_PORT = int(os.getenv("CHROMADB_PORT", "8000"))
CHROMADB_COLLECTION = os.getenv("CHROMADB_COLLECTION", "art_history_bgem3")

ES_INDEX = "art_history_hybrid"
EMBED_DIMS = 1024
BATCH_SIZE = 500

INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "content": {"type": "text"},
            "embedding": {
                "type": "dense_vector",
                "dims": EMBED_DIMS,
                "index": True,
                "similarity": "cosine",
            },
            "source": {"type": "keyword"},
            "parent_id": {"type": "keyword"},
            "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "artist": {"type": "text"},
            "date": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
        }
    }
}


def main():
    es = Elasticsearch(ES_URL, basic_auth=(ES_USERNAME, ES_PASSWORD), verify_certs=False)
    if not es.indices.exists(index=ES_INDEX):
        es.indices.create(index=ES_INDEX, body=INDEX_MAPPING)
        print(f"✅ 建立 index「{ES_INDEX}」")
    else:
        print(f"📌 index「{ES_INDEX}」已存在，直接 upsert")

    chroma_client = chromadb.HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)
    collection = chroma_client.get_collection(name=CHROMADB_COLLECTION)
    total = collection.count()
    print(f"ChromaDB collection「{CHROMADB_COLLECTION}」共 {total} 筆")

    offset = 0
    synced = 0
    while offset < total:
        batch = collection.get(
            limit=BATCH_SIZE,
            offset=offset,
            include=["documents", "metadatas", "embeddings"],
        )
        ids = batch["ids"]
        if not ids:
            break

        actions = []
        for i, chunk_id in enumerate(ids):
            metadata = batch["metadatas"][i] or {}
            actions.append(
                {
                    "_index": ES_INDEX,
                    "_id": chunk_id,
                    "_source": {
                        "content": batch["documents"][i],
                        "embedding": batch["embeddings"][i],
                        "source": metadata.get("source", ""),
                        "parent_id": metadata.get("parent_id", ""),
                        "title": metadata.get("title", ""),
                        "artist": metadata.get("artist", ""),
                        "date": str(metadata.get("date", "")),
                        "chunk_index": metadata.get("chunk_index", 0),
                    },
                }
            )

        success, errors = bulk(es, actions, raise_on_error=False)
        synced += success
        if errors:
            print(f"  ⚠️ {len(errors)} 筆寫入失敗，範例: {errors[0]}")

        offset += BATCH_SIZE
        print(f"[{min(offset, total)}/{total}] 已同步", flush=True)

    es.indices.refresh(index=ES_INDEX)
    count = es.count(index=ES_INDEX)["count"]
    print(
        f"=== 完成，ES index「{ES_INDEX}」共 {count} 筆（來源 {total} 筆，成功寫入 {synced} 筆）==="
    )


if __name__ == "__main__":
    main()
