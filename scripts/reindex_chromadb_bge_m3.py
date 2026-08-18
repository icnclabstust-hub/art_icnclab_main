"""把 ChromaDB「art_history」collection（原本用預設 all-MiniLM-L6-v2 英文 embedding）
重新用 BGE-M3（多語言）embedding，寫入新 collection「art_history_bgem3」。

安全考量：不刪除原本的 art_history collection，先建立新的，測試無誤後
再由 unified_rag_manager_v2.py 等程式切換過去讀取新 collection。
"""

import time

import chromadb
import requests
from chromadb import Documents, EmbeddingFunction, Embeddings

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "bge-m3:latest"
OLD_COLLECTION = "art_history"
NEW_COLLECTION = "art_history_bgem3"
BATCH_SIZE = 32


class BGEM3EmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:
        texts = [t[:4000] if t else " " for t in input]
        resp = requests.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": texts},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]


def main():
    client = chromadb.HttpClient(host="localhost", port=8000)
    old_collection = client.get_collection(name=OLD_COLLECTION)
    total = old_collection.count()
    print(f"來源 collection「{OLD_COLLECTION}」共 {total} 筆")

    embed_fn = BGEM3EmbeddingFunction()
    # 若中斷續跑，沿用已存在的新 collection
    new_collection = client.get_or_create_collection(
        name=NEW_COLLECTION, embedding_function=embed_fn
    )
    already_done = new_collection.count()
    print(f"目標 collection「{NEW_COLLECTION}」目前已有 {already_done} 筆")

    offset = 0
    processed = 0
    start_time = time.time()
    while offset < total:
        batch = old_collection.get(
            limit=BATCH_SIZE, offset=offset, include=["documents", "metadatas"]
        )
        ids = batch["ids"]
        docs = batch["documents"]
        metas = batch["metadatas"]

        if not ids:
            break

        # 跳過已經寫入新 collection 的（用 id 檢查，支援中斷續跑）
        existing = set()
        if already_done > 0:
            check = new_collection.get(ids=ids, include=[])
            existing = set(check["ids"])
        new_ids, new_docs, new_metas = [], [], []
        for i, doc, meta in zip(ids, docs, metas, strict=True):
            if i not in existing:
                new_ids.append(i)
                new_docs.append(doc)
                new_metas.append(meta)

        if new_ids:
            new_collection.add(ids=new_ids, documents=new_docs, metadatas=new_metas)

        offset += BATCH_SIZE
        processed += len(ids)
        elapsed = time.time() - start_time
        print(
            f"[{min(offset, total)}/{total}] 已處理，耗時 {elapsed:.0f}秒",
            flush=True,
        )

    final_count = new_collection.count()
    print(f"=== 完成，新 collection 共 {final_count} 筆（來源 {total} 筆）===")


if __name__ == "__main__":
    main()
