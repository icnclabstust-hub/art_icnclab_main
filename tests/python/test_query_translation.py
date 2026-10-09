"""查詢翻譯（詞典提示＋LLM）的單元測試；以假的 HTTP client 取代 Ollama，不需任何服務。

設計：docs/designs/2026-10-09-llm-query-translation.md
"""

import asyncio

import pytest
from multilingual_query_translator import MultilingualQueryTranslator


class FakeResponse:
    def __init__(self, text):
        self._text = text

    def raise_for_status(self):
        return None

    def json(self):
        return {"response": self._text}


class FakeClient:
    """記錄每次呼叫；``reply`` 為字串時回傳該譯文，為例外時拋出。"""

    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    async def post(self, url, json, timeout):  # noqa: A002 -- 與 httpx 介面同名
        self.calls.append(json)
        if isinstance(self.reply, Exception):
            raise self.reply
        return FakeResponse(self.reply)


@pytest.fixture
def rag(monkeypatch):
    """載入 RAG 主程式（同 test_sources_and_neo4j：匯入時檢查 NEO4J_PASSWORD，給假值）。"""
    pytest.importorskip("chromadb")  # 主程式依賴；DB 測試環境（postgres 使用者）沒有安裝時略過
    monkeypatch.setenv("NEO4J_PASSWORD", "unused")
    import unified_rag_manager_v2  # noqa: PLC0415

    return unified_rag_manager_v2


@pytest.fixture
def setup(monkeypatch, rag):
    """注入詞典翻譯器與假 client，清空翻譯快取，並停用背景預熱。"""

    def install(reply, mode="llm_hinted", model="same"):
        client = FakeClient(reply)
        monkeypatch.setattr(rag, "query_translator", MultilingualQueryTranslator())
        monkeypatch.setattr(rag.conn_manager, "http_client", client, raising=False)
        monkeypatch.setattr(rag, "QUERY_TRANSLATION", mode)
        monkeypatch.setattr(rag, "QUERY_TRANSLATION_MODEL", model)
        monkeypatch.setattr(rag, "_schedule_translation_warmup", lambda model=None: None)
        rag._translation_cache.clear()
        return client

    return install


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ('Here is the translation: "Which portraits?"', "Which portraits?"),
        ("Here is the translation of the problem into English:\nDid X happen?", "Did X happen?"),
        ("Translation: What is sfumato?", "What is sfumato?"),
        ("  What did Vermeer paint?\n", "What did Vermeer paint?"),
        ("Here are the works by Vermeer", "Here are the works by Vermeer"),  # 不是開場白，保留
    ],
)
def test_clean_translation_strips_preamble_quotes_and_newlines(rag, raw, clean):
    assert rag._clean_translation(raw) == clean


def test_translation_model_uses_generation_model_when_known(monkeypatch, rag):
    monkeypatch.setattr(rag, "QUERY_TRANSLATION_MODEL", "same")
    assert rag._translation_model("qwen3:8b") == "qwen3:8b"
    # /retrieve 帶的是假模型名，改用預設模型
    assert rag._translation_model("x") == rag.QUERY_TRANSLATION_DEFAULT_MODEL
    monkeypatch.setattr(rag, "QUERY_TRANSLATION_MODEL", "gemma4:12b")
    assert rag._translation_model("qwen3:8b") == "gemma4:12b"


def test_english_query_is_not_translated(setup, rag):
    client = setup("unused")

    query, info = run(rag.translate_for_retrieval("Who painted The Night Watch?", "llama3.1:8b"))

    assert (query, info) == ("Who painted The Night Watch?", None)
    assert client.calls == []


def test_llm_translation_uses_dictionary_hints_and_generation_model(setup, rag):
    client = setup('Here is the translation: "When was The Night Watch painted?"')

    query, info = run(rag.translate_for_retrieval("林布蘭的夜巡是何時完成的？", "llama3.1:8b"))

    assert query == "When was The Night Watch painted?"
    assert (info["method"], info["model"]) == ("llm_hinted", "llama3.1:8b")
    [call] = client.calls
    assert call["model"] == "llama3.1:8b"
    assert "夜巡 -> The Night Watch" in call["prompt"]  # 詞典找到的術語作為提示


def test_query_without_dictionary_terms_is_still_translated(setup, rag):
    client = setup("How did Riegl's Kunstwollen evolve?")

    query, info = run(rag.translate_for_retrieval("Riegl 的 Kunstwollen 如何演變？", "llama3.1:8b"))

    assert query == "How did Riegl's Kunstwollen evolve?"
    assert info["method"] == "llm_hinted"
    assert "已知術語對照" not in client.calls[0]["prompt"]


def test_llm_failure_falls_back_to_dictionary_and_is_not_cached(setup, rag):
    client = setup(TimeoutError("cold start"))

    query, info = run(rag.translate_for_retrieval("林布蘭的夜巡", "llama3.1:8b"))

    assert query == "Rembrandt的The Night Watch"
    assert info["method"] == "fallback"
    assert rag._translation_cache == {}
    client.reply = "Rembrandt's The Night Watch"
    query, info = run(rag.translate_for_retrieval("林布蘭的夜巡", "llama3.1:8b"))
    assert (query, info["method"]) == ("Rembrandt's The Night Watch", "llm_hinted")


def test_successful_translation_is_cached_per_model(setup, rag):
    client = setup("When was it painted?")

    run(rag.translate_for_retrieval("夜巡是何時畫的？", "llama3.1:8b"))
    run(rag.translate_for_retrieval("夜巡是何時畫的？", "llama3.1:8b"))
    run(rag.translate_for_retrieval("夜巡是何時畫的？", "qwen3:8b"))

    assert [c["model"] for c in client.calls] == ["llama3.1:8b", "qwen3:8b"]


def test_dictionary_mode_does_not_call_llm(setup, rag):
    client = setup("unused", mode="dictionary")

    query, info = run(rag.translate_for_retrieval("林布蘭的夜巡", "llama3.1:8b"))

    assert (query, info["method"]) == ("Rembrandt的The Night Watch", "dictionary")
    assert client.calls == []
