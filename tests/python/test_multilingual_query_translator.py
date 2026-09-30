"""查詢翻譯器的單元測試（使用 repo 內的術語詞典，不需任何服務）。"""

import pytest
from multilingual_query_translator import MultilingualQueryTranslator


@pytest.fixture(scope="module")
def translator():
    return MultilingualQueryTranslator()


def test_adjacent_replacements_are_separated_by_spaces(translator):
    translated, _ = translator.translate_terms("克勞德·洛蘭有哪些風景畫作品？")

    assert "landscape artwork" in translated
    assert "landscapeartwork" not in translated


def test_replacement_next_to_chinese_is_not_padded(translator):
    translated, _ = translator.translate_terms("林布蘭的夜巡")

    assert translated == "Rembrandt的The Night Watch"


@pytest.mark.parametrize(
    ("chinese", "english"),
    [
        ("維梅爾", "Johannes Vermeer"),
        ("委拉斯奎茲", "Diego Velázquez"),
        ("貝尼尼", "Gian Lorenzo Bernini"),
        ("戴珍珠耳環的少女", "Girl with a Pearl Earring"),
        ("宮娥", "Las Meninas"),
    ],
)
def test_baroque_names_added_2026_10_01(translator, chinese, english):
    translated, found = translator.translate_terms(f"{chinese}的作品")

    assert english in translated
    assert any(f"{chinese} -> {english}" == term for term in found)


def test_everyday_words_are_not_mapped_to_artworks(translator):
    translated, found = translator.translate_terms("我想找侍女的畫像")

    assert "Las Meninas" not in translated
    assert not any("Las Meninas" in term for term in found)
