import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "langchain-rag"))


@pytest.fixture
def mgr(monkeypatch):
    pytest.importorskip("fastapi")
    return importlib.import_module("unified_rag_manager_v2")


def test_orig_keeps_query(mgr, monkeypatch):
    monkeypatch.setattr(mgr, "K_SCORE_QUERY", "orig")
    assert mgr._k_query("林布蘭的作品", "Rembrandt works") == "林布蘭的作品"


def test_concat_appends_translation(mgr, monkeypatch):
    monkeypatch.setattr(mgr, "K_SCORE_QUERY", "concat")
    assert mgr._k_query("林布蘭的作品", "Rembrandt works") == "林布蘭的作品 Rembrandt works"


def test_concat_skips_identical(mgr, monkeypatch):
    monkeypatch.setattr(mgr, "K_SCORE_QUERY", "concat")
    assert mgr._k_query("Rembrandt works", "Rembrandt works") == "Rembrandt works"
