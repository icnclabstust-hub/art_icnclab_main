"""嵌入 Ollama 位址須在呼叫時讀環境變數（主程式於 import 後才載入 .env；2026-10-15 上線事故）。"""

import pytest

chromadb = pytest.importorskip("chromadb")
from bge_m3_embedding import embed_urls  # noqa: E402


def test_embed_urls_read_at_call_time(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://gpu:11434")
    monkeypatch.delenv("EMBED_OLLAMA_URL", raising=False)
    assert embed_urls() == ["http://gpu:11434"]
    # import 之後才設定（模擬 load_dotenv）
    monkeypatch.setenv("EMBED_OLLAMA_URL", "http://cpu:11435")
    assert embed_urls() == ["http://cpu:11435", "http://gpu:11434"]
