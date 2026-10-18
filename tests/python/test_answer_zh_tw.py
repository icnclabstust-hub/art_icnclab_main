"""回答轉臺灣繁體（ANSWER_ZH_TW）的單元測試；不需任何服務。"""

import pytest


@pytest.fixture
def rag(monkeypatch):
    pytest.importorskip("chromadb")
    monkeypatch.setenv("NEO4J_PASSWORD", "unused")
    import unified_rag_manager_v2  # noqa: PLC0415

    return unified_rag_manager_v2


def test_off_by_default_keeps_text_and_prompt(rag, monkeypatch):
    monkeypatch.setattr(rag, "ANSWER_ZH_TW", False)
    assert rag.to_zh_tw("创作体") == "创作体"
    prompt = rag.RAGStrategy._build_prompt(None, "林布蘭？", "ctx")
    assert rag.ANSWER_ZH_TW_RULE.strip() not in prompt


def test_on_converts_to_taiwan_traditional_and_adds_rule(rag, monkeypatch):
    pytest.importorskip("opencc")
    monkeypatch.setattr(rag, "ANSWER_ZH_TW", True)
    monkeypatch.setattr(rag, "_zh_tw", None)
    # 2026-10-18 量測殘留的簡體字；群、秘是臺灣標準寫法不改；「升天」依臺灣詞庫為「昇天」
    assert rag.to_zh_tw("创作体卧恒，群像升天神秘") == "創作體臥恆，群像昇天神秘"
    assert rag.to_zh_tw("委拉斯开兹") == "委拉斯開茲"
    prompt = rag.RAGStrategy._build_prompt(None, "林布蘭？", "ctx")
    assert rag.ANSWER_ZH_TW_RULE.strip() in prompt
