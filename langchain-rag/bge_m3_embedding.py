"""ChromaDB 共用的 BGE-M3 embedding function，供查詢與寫入時保持一致。"""

import os

import requests
from chromadb import Documents, EmbeddingFunction, Embeddings
from embedding_labels import EMBEDDING_MODEL

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# 嵌入可改由另一個 Ollama（例如只用 CPU 的 11435）提供，避免與生成模型搶顯存而被卸載
# （2026-10-14 E13：GPU Ollama 換載生成模型時會連帶卸載 bge-m3，每次檢索重新載入 2～5 秒）
EMBED_OLLAMA_URL = os.getenv("EMBED_OLLAMA_URL", OLLAMA_BASE_URL)
BGE_M3_MODEL = EMBEDDING_MODEL  # 模型名稱與版本標註集中在 embedding_labels.py（DAT-30）


class BGEM3EmbeddingFunction(EmbeddingFunction):
    """呼叫 Ollama 的 bge-m3 模型產生 embedding，取代 ChromaDB 預設的
    all-MiniLM-L6-v2（英文為主，中文與長句查詢效果差）。"""

    def __call__(self, input: Documents) -> Embeddings:
        texts = [t[:4000] if t else " " for t in input]
        resp = requests.post(
            f"{EMBED_OLLAMA_URL}/api/embed",
            json={"model": BGE_M3_MODEL, "input": texts},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]
