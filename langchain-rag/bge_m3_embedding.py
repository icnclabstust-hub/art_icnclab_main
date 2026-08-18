"""ChromaDB 共用的 BGE-M3 embedding function，供查詢與寫入時保持一致。"""

import os

import requests
from chromadb import Documents, EmbeddingFunction, Embeddings

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
BGE_M3_MODEL = "bge-m3:latest"


class BGEM3EmbeddingFunction(EmbeddingFunction):
    """呼叫 Ollama 的 bge-m3 模型產生 embedding，取代 ChromaDB 預設的
    all-MiniLM-L6-v2（英文為主，中文與長句查詢效果差）。"""

    def __call__(self, input: Documents) -> Embeddings:
        texts = [t[:4000] if t else " " for t in input]
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={"model": BGE_M3_MODEL, "input": texts},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]
