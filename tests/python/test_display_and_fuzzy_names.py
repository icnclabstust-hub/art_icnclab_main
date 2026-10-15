"""台灣譯名顯示（display_names）與譯名模糊錨點（graph_anchor.fuzzy_anchor）。"""

import display_names
import graph_anchor
import pytest


def test_display_names_replace_variant_and_keep_full_name():
    out = display_names.normalize("李奧納多·達文西與倫勃朗都曾研究光影。")
    assert out == "李奧納多·達文西與林布蘭都曾研究光影。"  # 全名不被拆成「達文西·達文西」


def test_display_names_leaves_unrelated_text():
    assert display_names.normalize("文藝復興的透視法") == "文藝復興的透視法"


def test_fuzzy_anchor_off_by_default(monkeypatch):
    monkeypatch.delenv("GRAPH_FUZZY_NAMES", raising=False)
    assert not graph_anchor.AliasTable().anchor("凡艾克有哪些作品？", "").hit


def test_fuzzy_anchor_threshold_95(monkeypatch):
    pytest.importorskip("pypinyin")
    pytest.importorskip("rapidfuzz")
    monkeypatch.setenv("GRAPH_FUZZY_NAMES", "95")
    table = graph_anchor.AliasTable()
    # 凡艾克（Van Eyck，不在表）在門檻 90 會誤配凡·戴克（93.3 分），95 不錨定
    assert not table.anchor("凡艾克有哪些作品收藏在大都會？", "").hit
    # 同音異字的譯名變體可找回（林布蘭 → 林布籣 為模擬錯字）
    hit = table.anchor("林布籣有哪些作品收藏在大都會？", "")
    assert hit.hit and hit.matched[0]["type"] == "fuzzy"
