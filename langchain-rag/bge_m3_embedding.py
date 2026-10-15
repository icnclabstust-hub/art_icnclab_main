"""ChromaDB 共用的 BGE-M3 embedding function，供查詢與寫入時保持一致。"""

import logging
import os

import requests
from chromadb import Documents, EmbeddingFunction, Embeddings
from embedding_labels import EMBEDDING_MODEL


def embed_urls() -> list[str]:
    """嵌入用 Ollama 位址（依序嘗試）：EMBED_OLLAMA_URL（例如 CPU 的 11435），失敗退回主 Ollama。

    呼叫時才讀環境變數：主程式在 import 本模組之後才載入 .env（ENV_FILE），模組層級讀取會拿到
    預設值、讓嵌入仍走 GPU Ollama（2026-10-15 上線後 8080 驗證發現，每題重新載入 bge-m3 約 12 秒）。
    """
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    embed = os.getenv("EMBED_OLLAMA_URL") or base
    return [embed] + ([base] if embed != base else [])


logger = logging.getLogger(__name__)
BGE_M3_MODEL = EMBEDDING_MODEL  # 模型名稱與版本標註集中在 embedding_labels.py（DAT-30）


class BGEM3EmbeddingFunction(EmbeddingFunction):
    """呼叫 Ollama 的 bge-m3 模型產生 embedding，取代 ChromaDB 預設的
    all-MiniLM-L6-v2（英文為主，中文與長句查詢效果差）。"""

    def __call__(self, input: Documents) -> Embeddings:
        texts = [t[:4000] if t else " " for t in input]
        # 獨立的嵌入 Ollama 沒啟動時退回主 Ollama（同一模型，E14 實測向量餘弦 ≥ 0.99999）
        urls = embed_urls()
        for i, url in enumerate(urls):
            try:
                resp = requests.post(
                    f"{url}/api/embed",
                    json={"model": BGE_M3_MODEL, "input": texts},
                    timeout=120,
                )
                resp.raise_for_status()
                return resp.json()["embeddings"]
            except requests.RequestException as e:
                if i == len(urls) - 1:
                    raise
                logger.warning(f"⚠️ 嵌入 Ollama {url} 無法使用（{e!r}），退回 {urls[i + 1]}")
        raise RuntimeError("unreachable")
