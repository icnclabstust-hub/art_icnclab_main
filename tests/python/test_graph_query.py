"""系統圖譜路查詢組裝與分數篩選的單元測試（不需任何服務）。"""

from graph_query import apply_relative_cutoff, build_lucene_query, escape_lucene


def test_phrases_are_quoted_and_single_words_kept_without_fuzzy():
    query = build_lucene_query(["The Night Watch", "Rembrandt", "Night", "Watch", "Baroque"])

    assert query == '"The Night Watch" Rembrandt Night Watch Baroque'
    assert "~" not in query


def test_duplicates_blank_terms_and_extra_spaces_are_dropped():
    assert build_lucene_query(["Monet", "monet", "  ", "Water   Lilies"]) == 'Monet "Water Lilies"'
    assert build_lucene_query([]) == ""


def test_lucene_special_characters_are_escaped():
    assert escape_lucene('Saint-Denis (Paris): "A"~') == r"Saint\-Denis \(Paris\)\: \"A\"\~"
    assert build_lucene_query(["A && B || C"]) == r'"A \&\& B \|\| C"'


def test_relative_cutoff_drops_weak_hits_and_sorts():
    rows = [{"id": "b", "score": 2.6}, {"id": "a", "score": 9.0}, {"id": "c", "score": 3.0}]

    assert [r["id"] for r in apply_relative_cutoff(rows, 0.3)] == ["a", "c"]


def test_relative_cutoff_zero_keeps_everything_and_handles_empty():
    rows = [{"score": 1.0}, {"score": 0.01}]

    assert len(apply_relative_cutoff(rows, 0)) == 2
    assert apply_relative_cutoff([], 0.3) == []
