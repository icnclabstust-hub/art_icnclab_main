"""作者字串解析的單元測試（範例取自 E29 實際資料）。

設計：docs/designs/2026-10-18-graph-data-quality.md D2
"""

import pytest
from ingest import legacy
from ingest.artist_names import parse_artists
from subscribers.neo4j_sub import _artist_names


@pytest.mark.parametrize(
    ("source", "raw", "expected"),
    [
        ("va_museum", "Feure, Georges de", ["Georges de Feure"]),
        ("va_museum", "Halima Cassell, MBE, FRSS", ["Halima Cassell"]),
        ("va_museum", "Morley, L. H (Mrs)", ["L. H Morley"]),
        ("va_museum", "Unknown Maker", []),
        ("art_institute_chicago", "Salvador Dalí\nSpanish, 1904–1989", ["Salvador Dalí"]),
        ("met_museum", "Anonymous, British, 19th century", []),
        ("met_museum", "Unknown Artist", []),
        ("met_museum", "Italian", []),
        (
            "met_museum",
            "Perugino (Pietro di Cristoforo Vannucci)",
            ["Perugino (Pietro di Cristoforo Vannucci)"],
        ),
        ("met_museum", "Rembrandt (Rembrandt van Rijn)", ["Rembrandt (Rembrandt van Rijn)"]),
        ("met_museum", "Firth, Hall & Pond", ["Firth", "Hall & Pond"]),
        ("cleveland_museum", "Sandro Botticelli, Workshop", ["Sandro Botticelli"]),
        ("specialized_art", "Gould, John 1804-1881", ["John Gould"]),
        ("specialized_art", "Salameh, Georges (1973), Σαλαμέ, Γιώργος (1973)", ["Georges Salameh"]),
        (
            "specialized_art",
            "http://semantics.gr/authorities/searchculture-persons/1265175713, Apostolou, "
            "Eugenia (1954), Αποστόλου, Ευγενία (1954)",
            ["Eugenia Apostolou"],
        ),
        ("europeana", "Castle, Tony, unknown, Castle, Tony, onbekend", ["Tony Castle"]),
        ("europeana", "Unbekannter Fotograf (Herstellung) (Fotograf)", []),
        (
            "europeana",
            "Pillement, Georges (1898-1984). Auteur du texte, Daniloff, Nadine. Auteur du texte",
            ["Georges Pillement", "Nadine Daniloff"],
        ),
        (
            "google_books",
            "Mark Crinson, Richard J. Williams",
            ["Mark Crinson", "Richard J. Williams"],
        ),
        ("google_books", "喬斯坦．賈德 Jostein Gaarder", ["喬斯坦．賈德 Jostein Gaarder"]),
        ("harvard", "Auguste Rodin | Camille Claudel", ["Auguste Rodin", "Camille Claudel"]),
        ("harvard", "Titian | Agostino Carracci", ["Titian", "Agostino Carracci"]),
        ("harvard", "", []),
        ("google_books", "Jason C. Kuo, 郭继生", ["Jason C. Kuo", "郭继生"]),
        ("met_museum", "Richardson Ellson & Co.", ["Richardson Ellson & Co."]),
    ],
)
def test_parse_artists(source, raw, expected):
    assert parse_artists(source, raw) == expected


def test_subscriber_parses_each_creator():
    artwork = {"creators": ["Doe, Jane", "Roe", "http://d-nb.info/x, Doe, Jane"], "artist": "x"}
    assert _artist_names(artwork, "europeana") == ["Jane Doe", "Roe"]
    assert _artist_names({"artist": "Feure, Georges de"}, "va_museum") == ["Georges de Feure"]


def test_harvard_reads_crawler_name_field(monkeypatch):
    """E29：JS 爬蟲存 people[].name，舊程式只讀 displayname，Harvard 作者全部空白。"""
    monkeypatch.setenv("NEO4J_PASSWORD", "unused")
    module = legacy.load_legacy_module()
    item = {
        "harvardId": 5494,
        "title": "Head of Balzac",
        "people": [{"name": "Auguste Rodin"}, {"displayname": "Camille Claudel"}, {"role": "x"}],
    }
    artwork = module.normalize_harvard(item)
    assert artwork["artist"] == "Auguste Rodin | Camille Claudel"
    assert parse_artists("harvard", artwork["artist"]) == ["Auguste Rodin", "Camille Claudel"]
