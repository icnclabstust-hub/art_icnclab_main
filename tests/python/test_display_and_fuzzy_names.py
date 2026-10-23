"""台灣譯名顯示（display_names）與譯名模糊錨點（graph_anchor.fuzzy_anchor）。"""

import display_names
import graph_anchor
import pytest


def test_display_names_replace_variant_and_keep_full_name():
    out = display_names.normalize("李奧納多·達文西與倫勃朗都曾研究光影。")
    assert out == "李奧納多·達文西與林布蘭都曾研究光影。"  # 全名不被拆成「達文西·達文西」


@pytest.mark.parametrize(
    ("text", "question", "want"),
    [
        ("拉斐爾·聖齊奧的作品", None, "拉斐爾·聖齊奧的作品"),  # 不變「拉斐爾·拉斐爾」
        ("聖齊奧的作品", None, "拉斐爾的作品"),
        ("巴勃羅·畢卡索的作品", None, "巴勃羅·畢卡索的作品"),  # 已含顯示名
        ("維米爾的作品", None, "維米爾的作品"),  # 可接受寫法
        ("約翰尼斯·維梅爾", None, "約翰尼斯·維梅爾"),
        ("維拉斯奎茲的作品", None, "維拉斯奎茲的作品"),  # 可接受寫法
        ("迪亞哥·維拉斯奎茲的作品", None, "迪亞哥·維拉斯奎茲的作品"),  # 已含可接受寫法
        ("委拉斯開茲的作品", None, "委拉斯奎茲的作品"),  # 國教院顯示名
        ("倫勃朗的《夜巡》", "倫勃朗的《夜巡》是哪一年？", "倫勃朗的《夜巡》"),  # 使用者用字不改
    ],
)
def test_display_names_rules_2026_10_16(text, question, want):
    assert display_names.normalize(text, question) == want


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


def test_display_names_handle_mixed_simplified_characters():
    """2026-10-18 8080 測試：模型寫「委拉斯開兹」（兹＝簡體）時也要換成台灣顯示名；其餘字元不動。"""
    text = "《宮娥》是西班牙畫家 **迭戈·委拉斯開兹**（Diego Velázquez）的作品，这幅画很有名。"
    out = display_names.normalize(text, "《宮娥》是哪位畫家的作品？")
    assert "委拉斯奎茲" in out and "委拉斯開兹" not in out
    assert "这幅画很有名" in out  # 不是人名的簡體字保留原樣（由介面層 OpenCC 處理）
    # 提問中用的寫法（簡體或繁體）都不替換
    q = "委拉斯开兹的《宮娥》描繪了什麼？"
    assert "委拉斯開兹" in display_names.normalize("委拉斯開兹畫了宮娥。", q)
