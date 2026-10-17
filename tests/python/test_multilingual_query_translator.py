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


@pytest.mark.parametrize(
    ("query", "must_not_contain"),
    [
        ("是否存在可證的影響關係？", "shadow"),  # 日文專用「影」不得套在中文的「影響」
        ("樹木的描繪", "wood"),  # 日文專用「木」不得套在中文查詢
        ("從光學散射看濕壁畫", "light"),  # 單一漢字「光」不得切開「光學」
        ("林布蘭的銅版畫", "bronze"),  # 「銅版畫」是版畫，不是青銅
        ("威尼斯 colorito 的色彩邏輯", "color ito"),  # 拉丁字母詞不得切開更長的字
    ],
)
def test_partial_matches_inside_longer_words_are_rejected(translator, query, must_not_contain):
    translated, _ = translator.translate_terms(query)

    assert must_not_contain not in translated


def test_standalone_terms_still_translate(translator):
    assert "color" in translator.translate_terms("這幅畫的 color 很特別")[0]
    assert "Peter Paul Rubens" in translator.translate_terms("魯本斯的祭壇畫")[0]
    # 日文查詢仍用日文詞條
    assert "ルネサンス" not in translator.translate_terms("ルネサンスの絵画")[0]


def test_japanese_with_kanji_is_detected_as_japanese(translator):
    assert translator.detect_language("ルネサンスの絵画") == "ja"
    assert translator.detect_language("文藝復興的繪畫") == "zh"


def test_name_dots_are_normalized_with_extra_dictionary(tmp_path, monkeypatch, translator):
    """E25：「喬凡尼．貝里尼」（全形點）原本對不上詞典的「喬凡尼·貝里尼」；設額外詞典時才統一。"""
    from multilingual_query_translator import normalize_name_dots  # noqa: PLC0415

    assert normalize_name_dots("喬凡尼．貝里尼的作品") == "喬凡尼·貝里尼的作品"
    assert normalize_name_dots("1.5 公尺．") == "1.5 公尺．"  # 不在兩個漢字之間不換
    _, terms = translator.translate_terms("拉斐爾．聖齊奧的作品")
    assert "拉斐爾．聖齊奧 -> Raphael" not in terms  # 預設不統一：只對到「聖齊奧」（現行行為）

    extra = tmp_path / "extra.json"
    extra.write_text('{"artists_graph": {}}', encoding="utf-8")
    monkeypatch.setenv("QUERY_TERMS_EXTRA", str(extra))
    _, terms = MultilingualQueryTranslator().translate_terms("拉斐爾．聖齊奧的作品")
    assert "拉斐爾．聖齊奧 -> Raphael" in terms


def test_extra_dictionary_is_loaded_with_lowest_priority(tmp_path, monkeypatch):
    extra = tmp_path / "extra.json"
    extra.write_text(
        '{"_meta": {}, "artists_graph": {"Gustav Klimt": {"zh": ["克林姆"]},'
        ' "Wrong Rembrandt": {"zh": ["林布蘭"]}}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("QUERY_TERMS_EXTRA", str(extra))
    t = MultilingualQueryTranslator()

    _, terms = t.translate_terms("克林姆和林布蘭")
    assert "克林姆 -> Gustav Klimt" in terms
    assert "林布蘭 -> Rembrandt" in terms  # 原詞典優先，不被額外詞典覆寫
    assert "Gustav Klimt" in t.person_terms


def test_extra_dictionary_not_loaded_by_default(translator):
    _, terms = translator.translate_terms("克林姆的作品")
    assert not any("Klimt" in x for x in terms)


def test_surname_terms_respect_name_boundary(tmp_path, monkeypatch):
    """E27：只有姓氏的詞條不可切開較長的名字（「聖羅倫」切開「聖羅倫佐」），正常用法照常對中。"""
    extra = tmp_path / "extra.json"
    extra.write_text(
        '{"artists_famous": {'
        '"Yves Saint Laurent": {"zh": ["伊夫·聖羅倫"], "zh_surname": ["聖羅倫"]},'
        '"Gustav Klimt": {"zh": ["古斯塔夫·克林姆"], "zh_surname": ["克林姆"]},'
        '"Lorenzo Lotto": {"zh": ["洛倫佐·洛托"]}, "Lorenzo Monaco": {"zh": ["洛倫佐·摩納哥"]},'
        '"Lorenzo Costa": {"zh": ["洛倫佐·科斯塔"]}}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("QUERY_TERMS_EXTRA", str(extra))
    t = MultilingualQueryTranslator()

    assert "佐" in t.name_chars  # 「洛倫佐」出現 3 次
    assert not any("Laurent" in x for x in t.translate_terms("聖羅倫佐大教堂")[1])
    assert "克林姆 -> Gustav Klimt" in t.translate_terms("克林姆的代表作")[1]
    assert "聖羅倫 -> Yves Saint Laurent" in t.translate_terms("聖羅倫的設計")[1]
