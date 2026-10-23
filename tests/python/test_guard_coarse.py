"""同步粗篩的單元測試（不需任何服務）。"""

import pytest
from guard_coarse import check_answer, extract_anchors, split_sentences

SOURCE = (
    "Title: The Night Watch\nCreator: Rembrandt van Rijn\nDate: 1642\n"
    "Description: Militia Company of District II under the Command of Captain Frans Banninck Cocq."
)


def test_split_handles_chinese_english_and_markdown():
    text = "1. **巨幅尺寸**：這幅畫很大。It was painted in 1642. 真的嗎？\n# 標題\n- 短"

    assert split_sentences(text) == [
        "巨幅尺寸 ：這幅畫很大。",
        "It was painted in 1642.",
        "真的嗎？",
    ]


def test_anchors_are_numbers_and_latin_words_without_stopwords():
    assert extract_anchors("林布蘭（Rembrandt）於1642年完成 The Night Watch") == [
        "1642",
        "rembrandt",
        "night",
        "watch",
    ]
    assert extract_anchors("這幅畫非常有名") == []


def test_sentence_statuses():
    answer = (
        "《夜巡》由 Rembrandt 於 1642 年完成。"
        "畫中隊長是 Banninck Cocq 與 Kloveniers。"
        "此畫收藏於 Louvre，1503 年購入。"
        "這幅畫非常有名。"
    )
    result = check_answer(answer, [SOURCE])

    assert [s.status for s in result.sentences] == [
        "supported",
        "partial",
        "unsupported",
        "no_anchor",
    ]
    assert result.summary() == {
        "n_sentences": 4,
        "n_anchored": 3,
        "n_supported": 1,
        "n_partial": 1,
        "n_unsupported": 1,
        "anchor_hit_rate": pytest.approx(4 / 7, abs=1e-4),
    }


def test_matching_respects_word_boundaries_and_case():
    result = check_answer("Painted by REMBRANDT in 164.", ["rembrandtesque 1642"])

    assert result.sentences[0].found == []


def test_abbreviated_year_range_in_source_supports_full_year():
    # 實機發現：MET 寫 "c. 1915–26"，答案寫「1915–1926 年」原本被誤判為 1926 不在來源
    result = check_answer("Monet 約於 1915–1926 年創作。", ["Creator: Monet\nDate: c. 1915–26"])

    assert result.sentences[0].status == "supported"
    assert check_answer("完成於 1926 年。", ["Date: 1915-1920"]).sentences[0].status == (
        "unsupported"
    )


def test_no_anchors_gives_none_rate_and_empty_answer():
    assert check_answer("這幅畫非常有名。", [SOURCE]).anchor_hit_rate is None
    assert check_answer("", [SOURCE]).summary()["n_sentences"] == 0
