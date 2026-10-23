"""嵌入模型標註（規格 DAT-30～32）：每個向量的 metadata 記錄產生它的模型名稱與版本。

版本取 Ollama 的模型 digest：同名 tag（例如 latest）被重新 pull 成不同權重時 digest 會變，
夜間稽核即可發現同一 collection 內新舊向量混用（DAT-31）。本模組不依賴 chromadb，
訂閱器與稽核都能直接使用。
"""

import os
from collections import Counter
from collections.abc import Iterable, Mapping

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = "bge-m3:latest"
EMBEDDING_LABEL_KEYS = ("embedding_model", "embedding_version")
DIGEST_CHARS = 12
UNLABELED = ("(未標註)", "(未標註)")


def current_embedding_labels(base_url: str = OLLAMA_BASE_URL) -> dict[str, str]:
    """目前 Ollama 上嵌入模型的名稱與版本（digest 前 12 碼）。

    Raises:
        RuntimeError: Ollama 上找不到該模型。
    """
    import requests  # noqa: PLC0415 -- 只有實際查詢 Ollama 時需要

    resp = requests.get(f"{base_url}/api/tags", timeout=10)
    resp.raise_for_status()
    for model in resp.json().get("models", []):
        if model.get("name") == EMBEDDING_MODEL:
            return {
                "embedding_model": EMBEDDING_MODEL,
                "embedding_version": model["digest"][:DIGEST_CHARS],
            }
    raise RuntimeError(f"Ollama 上找不到嵌入模型 {EMBEDDING_MODEL}")


def label_combinations(metadatas: Iterable[Mapping | None]) -> Counter:
    """統計各 (模型, 版本) 組合的向量數；缺標註的算成 ``UNLABELED``。"""
    counts: Counter = Counter()
    for meta in metadatas:
        meta = meta or {}
        model, version = meta.get("embedding_model"), meta.get("embedding_version")
        counts[(model, version) if model and version else UNLABELED] += 1
    return counts
