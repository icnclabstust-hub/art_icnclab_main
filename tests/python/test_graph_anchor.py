"""圖譜錨點（方案 A）的單元測試；只用小型別名表，不需 Neo4j。

設計：docs/designs/2026-10-11-graph-retrieval-anchor.md
"""

import json

import graph_anchor as g
import pytest


@pytest.fixture
def table(tmp_path):
    data = {
        "meta": {},
        "artists": [
            {
                "qid": "Q5598",
                "name_en": "Rembrandt",
                "neo4j_names": ["Rembrandt", "Rembrandt van Rijn"],
                "aliases": [
                    {"alias": "林布蘭", "type": "full", "source": "wikidata"},
                    {"alias": "Rembrandt", "type": "en", "source": "wikidata"},
                ],
            },
            {
                "qid": "Q42207",
                "name_en": "Caravaggio",
                "neo4j_names": ["Caravaggio"],
                "aliases": [
                    {"alias": "卡拉瓦喬", "type": "full", "source": "wikidata"},
                    {"alias": "Caravaggio", "type": "en", "source": "wikidata"},
                ],
            },
            {
                "qid": "Q7824",
                "name_en": "Annibale Carracci",
                "neo4j_names": ["Annibale Carracci"],
                "aliases": [{"alias": "卡拉契", "type": "manual", "source": "family"}],
            },
            {
                "qid": "Q380553",
                "name_en": "Ludovico Carracci",
                "neo4j_names": ["Ludovico Carracci"],
                "aliases": [{"alias": "卡拉契", "type": "manual", "source": "family"}],
            },
            {
                "qid": "Q212657",
                "name_en": "Artemisia Gentileschi",
                "neo4j_names": [],
                "aliases": [{"alias": "真蒂萊斯基", "type": "manual", "source": "dictionary"}],
            },
        ],
    }
    path = tmp_path / "aliases.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return g.AliasTable(path)


def test_chinese_alias_anchors_all_nodes_of_artist(table):
    a = table.anchor("資料庫中有哪些林布蘭的肖像畫？", "Which portraits by Rembrandt?")
    assert a.qids == ["Q5598"]
    assert a.names == ["Rembrandt", "Rembrandt van Rijn"]


def test_english_alias_needs_word_boundary(table):
    # Rembrandt Peale 之類的另一位畫家不在別名表；但「Rembrandts」這種黏字不能誤中
    assert not table.anchor(None, "Rembrandtsplein in Amsterdam").hit
    assert table.anchor(None, "works of Rembrandt, Dutch").qids == ["Q5598"]


def test_family_alias_anchors_every_member(table):
    a = table.anchor("卡拉契家族有哪些宗教題材作品？", "")
    assert sorted(a.qids) == ["Q380553", "Q7824"]


def test_artist_without_graph_nodes_abstains(table):
    a = table.anchor("真蒂萊斯基的《朱蒂斯》有哪些版本？", "")
    assert a.qids == ["Q212657"] and not a.hit


def test_unknown_artist_abstains(table):
    assert not table.anchor("普桑有哪些神話題材作品？", "Poussin mythological works").hit


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        (
            "大都會藝術博物館收藏了哪些維梅爾的畫作？",
            ("T2", {"museum": "Metropolitan Museum of Art"}),
        ),
        ("林布蘭的肖像畫有哪些？", ("T1", {})),
    ],
)
def test_template_choice(question, expected):
    assert g.choose_template(question, "") == expected


def test_question_type_uses_title_brackets():
    assert g.question_type("林布蘭的《夜巡》是哪一年完成的？") == "fact"
    assert g.question_type("林布蘭有哪些肖像畫？") == "relation"
    assert g.question_type(None) == "relation"


class FakeArtwork(dict):
    pass


def test_rank_artworks_prefers_title_hits():
    recs = [
        {"artwork": FakeArtwork(id="a", title="Landscape with a Mill")},
        {"artwork": FakeArtwork(id="b", title="Portrait of a Man", medium="Oil on canvas")},
        {"artwork": FakeArtwork(id="c", title="Study", description="portrait sketch")},
    ]
    ranked = g.rank_artworks(recs, "Which portraits by Rembrandt?", 2)
    assert [r["artwork"]["id"] for _, r in ranked] == ["b", "c"]
