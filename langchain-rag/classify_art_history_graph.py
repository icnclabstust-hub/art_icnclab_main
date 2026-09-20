#!/usr/bin/env python3
"""
藝術史知識圖譜分類腳本
依照 12 類分類體系，從既有的 Artwork/Artist 資料（屬性字串）與
art_history_terms_dictionary.json 詞典，抽取/建立分類節點與關係：

  (1) 人物 Artist          - 沿用既有 Artist 節點
  (2) 作品 Artwork          - 沿用既有 Artwork 節點
  (3) 流派/運動 Style        - 從 Artwork.period 抽取風格/運動關鍵字 + 詞典 art_periods
  (4) 技法與材質 Technique/Material - 從 Artwork.medium 拆解 + 詞典 materials/art_types
  (5) 主題與圖像學 Theme      - 僅建 schema；詞典 art_types 裡的 portrait/landscape/still life 視為
                               有可靠來源的類型標記一併建立，不對描述文字做關鍵字猜測
  (6) 時間 Period           - 從 Artwork.period 抽取朝代/時代/世紀等紀年關鍵字
  (7) 地點 Place            - 從 Artwork.culture 抽取國家/地區/民族關鍵字
  (8) 機構 Institution       - 依 source 對應機構 + specialized_art/europeana 的機構欄位
  (9) 事件 Event            - 僅建 schema，不填資料（無來源資料可用）
  (10) 文獻 Source/Text      - google_books 來源的 Artwork 額外標記 :Source 標籤
  (11) 概念與術語 Concept     - 詞典 art_concepts，比對 Artwork 標題/描述
  (12) 版本/語言 Translation  - 詞典裡每個詞條的多語言翻譯，建 Translation 節點掛在對應分類節點下

用法:
    python3 classify_art_history_graph.py            # 清除舊示範節點後重新分類
    python3 classify_art_history_graph.py --no-clean # 不清除，只疊加
"""

import json
import logging
import os
import re
from pathlib import Path

from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")  # 原生 Neo4j（WSL 直接執行），標準埠
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
if not NEO4J_PASSWORD:
    raise RuntimeError(
        "缺少 NEO4J_PASSWORD 環境變數。請在啟動前設定，例如："
        "NEO4J_PASSWORD=... python3 classify_art_history_graph.py"
    )
TERMS_FILE = Path(__file__).parent.parent / "../art_history_terms_dictionary.json"

# 示範/測試節點的標籤（舊 enhanced_graph_builder.py 產生，內容跟真實爬蟲資料無關）
DEMO_LABELS = [
    "Style",
    "Movement",
    "Technique",
    "Material",
    "Theme",
    "Iconography",
    "Place",
    "Institution",
    "Event",
    "Source",
    "Text",
    "Concept",
    "Translation",
]

# === (3) 流派/運動：風格關鍵字（會出現在 Artwork.period 裡） ===
STYLE_KEYWORDS = [
    "Renaissance",
    "Baroque",
    "Rococo",
    "Gothic",
    "Romanesque",
    "Byzantine",
    "Neoclassical",
    "Neoclassicism",
    "Romanticism",
    "Impressionism",
    "Post-Impressionism",
    "Realism",
    "Modernism",
    "Cubism",
    "Surrealism",
    "Expressionism",
    "Art Nouveau",
    "Art Deco",
    "Mannerism",
    "Ukiyo-e",
    "Abstract",
    "Minimalism",
    "Pop Art",
]

# === (6) 時間：紀年/朝代關鍵字判斷（regex，抓 "XXX period/dynasty/era" 或西元年份區間） ===
PERIOD_PATTERNS = [
    r"[A-Z][a-zA-Z]+ dynasty",
    r"[A-Z][a-zA-Z]+ period",
    r"[A-Z][a-zA-Z]+ era",
    r"\d{3,4}\s*[-–—]\s*\d{3,4}",
    r"\(\d{3,4}[-–—]\d{3,4}\)",
]

# === (7) 地點：culture 欄位常見國家/地區/民族關鍵字 ===
PLACE_KEYWORDS = [
    "Italian",
    "Italy",
    "French",
    "France",
    "German",
    "Germany",
    "British",
    "England",
    "Spanish",
    "Spain",
    "Dutch",
    "Netherlandish",
    "Netherlands",
    "Flemish",
    "Flanders",
    "American",
    "United States",
    "Chinese",
    "China",
    "Japanese",
    "Japan",
    "Korean",
    "Korea",
    "Indian",
    "India",
    "Persian",
    "Iran",
    "Tibetan",
    "Tibet",
    "Thai",
    "Thailand",
    "Swedish",
    "Sweden",
    "Finnish",
    "Finland",
    "Slovak",
    "Slovakia",
    "Polish",
    "Poland",
    "Venetian",
    "Venice",
    "Roman",
    "Greek",
    "Greece",
    "Egyptian",
    "Egypt",
    "African",
    "Ottoman",
    "Turkish",
    "Turkey",
    "Russian",
    "Russia",
    "Austrian",
    "Swiss",
    "Belgian",
]

# === (4) 材質/技法：medium 欄位拆解後的分類關鍵字 ===
MATERIAL_KEYWORDS = [
    "bronze",
    "marble",
    "oil",
    "wood",
    "ivory",
    "gold",
    "silver",
    "ceramic",
    "porcelain",
    "textile",
    "paper",
    "canvas",
    "clay",
    "stone",
    "glass",
    "copper",
    "iron",
    "steel",
    "wool",
    "silk",
    "leather",
    "alabaster",
    "granite",
    "terracotta",
    "lacquer",
    "enamel",
    "ink",
    "watercolor",
    "gesso",
    "gemstone",
    "pearl",
    "diamond",
    "ruby",
]
TECHNIQUE_KEYWORDS = [
    "fresco",
    "engraving",
    "tempera",
    "sculpture",
    "casting",
    "gilding",
    "painting",
    "drawing",
    "printing",
    "weaving",
    "glazed",
    "glaze",
    "carving",
    "embroidery",
    "etching",
    "lithograph",
    "woodcut",
    "mosaic",
    "inlay",
    "enameling",
    "chiseled",
]

# === (10) 機構：依來源對應（specialized_art / europeana 有真實機構欄位，其餘用固定名稱） ===
FIXED_SOURCE_INSTITUTIONS = {
    "met_museum": "Metropolitan Museum of Art",
    "harvard": "Harvard Art Museums",
    "masterpieces_curated": "Curated Masterpieces Collection",
    "google_books": "Google Books",
}


def load_terms_dictionary():
    with open(TERMS_FILE, encoding="utf-8") as f:
        return json.load(f)


def clean_demo_nodes(session):
    # 重要：只刪除「純」示範標籤節點，絕對不能誤刪同時帶有 Artwork/Artist 標籤的真實資料節點
    # （例如 google_books 的 Artwork 節點在本腳本跑過一次後會被多掛上 :Source 標籤，
    #  如果這裡沒有排除 Artwork/Artist，重跑腳本就會把這些真實作品節點也刪掉）
    result = session.run(
        """
        MATCH (n) WHERE any(l IN labels(n) WHERE l IN $labels)
          AND NOT n:Artwork AND NOT n:Artist
        DETACH DELETE n RETURN count(n) as c
        """,
        labels=DEMO_LABELS,
    )
    result.consume()
    logger.info("已清除舊示範/測試分類節點（不影響真實 Artwork/Artist 資料）")


def ensure_constraints(session):
    for label in [
        "Style",
        "Technique",
        "Material",
        "Period",
        "Place",
        "Institution",
        "Theme",
        "Event",
        "Concept",
    ]:
        session.run(
            f"CREATE CONSTRAINT {label.lower()}_name_unique IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.name IS UNIQUE"
        ).consume()
    # 注意：複合唯一約束 (NODE KEY) 是 Neo4j Enterprise 限定功能，Community Edition 不支援
    # Translation 節點的去重靠 MERGE 時同時比對 text/language/term 三個屬性達成，不靠 DB 約束
    logger.info("✅ 12 類節點的唯一性約束已就緒（Translation 節點靠 MERGE 三屬性比對去重）")


def add_translations(session, node_label, node_name, translations: dict):
    """幫某個分類節點掛上多語言 Translation 節點 (12. 版本/語言)"""
    for lang, texts in translations.items():
        for text in texts:
            session.run(
                f"""
                MATCH (n:{node_label} {{name: $name}})
                MERGE (t:Translation {{text: $text, language: $lang, term: $name}})
                MERGE (n)-[:HAS_TRANSLATION]->(t)
                """,
                name=node_name,
                text=text,
                lang=lang,
            )


def classify_styles_and_periods(session):
    """(3) 流派/運動 + (6) 時間：從 Artwork.period 抽取"""
    style_count, period_count = 0, 0
    rows = session.run(
        "MATCH (a:Artwork) WHERE a.period IS NOT NULL AND a.period <> '' "
        "RETURN DISTINCT a.period as period"
    )
    for row in rows:
        period_val = row["period"]
        matched_style = next((s for s in STYLE_KEYWORDS if s.lower() in period_val.lower()), None)
        if matched_style:
            session.run(
                """
                MERGE (s:Style {name: $name})
                WITH s
                MATCH (a:Artwork {period: $period_val})
                MERGE (a)-[:BELONGS_TO_STYLE]->(s)
                """,
                name=matched_style,
                period_val=period_val,
            )
            style_count += 1
        elif any(re.search(p, period_val) for p in PERIOD_PATTERNS):
            session.run(
                """
                MERGE (p:Period {name: $name})
                WITH p
                MATCH (a:Artwork {period: $period_val})
                MERGE (a)-[:CREATED_IN_PERIOD]->(p)
                """,
                name=period_val,
                period_val=period_val,
            )
            period_count += 1
    logger.info(
        f"✅ (3)流派/運動: {style_count} 種 period 值歸類為風格 | "
        f"(6)時間: {period_count} 種歸類為紀年"
    )


def classify_materials_and_techniques(session):
    """(4) 技法與材質：拆解 Artwork.medium"""
    material_count, technique_count = 0, 0
    rows = session.run(
        "MATCH (a:Artwork) WHERE a.medium IS NOT NULL AND a.medium <> '' "
        "RETURN DISTINCT a.medium as medium"
    )
    for row in rows:
        medium_val = row["medium"]
        medium_lower = medium_val.lower()
        for kw in MATERIAL_KEYWORDS:
            if kw in medium_lower:
                session.run(
                    """
                    MERGE (m:Material {name: $name})
                    WITH m
                    MATCH (a:Artwork {medium: $medium_val})
                    MERGE (a)-[:USES_MATERIAL]->(m)
                    """,
                    name=kw,
                    medium_val=medium_val,
                )
                material_count += 1
        for kw in TECHNIQUE_KEYWORDS:
            if kw in medium_lower:
                session.run(
                    """
                    MERGE (t:Technique {name: $name})
                    WITH t
                    MATCH (a:Artwork {medium: $medium_val})
                    MERGE (a)-[:USES_TECHNIQUE]->(t)
                    """,
                    name=kw,
                    medium_val=medium_val,
                )
                technique_count += 1
    logger.info(f"✅ (4)材質標記: {material_count} 筆 | 技法標記: {technique_count} 筆")


def classify_places(session):
    """(7) 地點：從 Artwork.culture 抽取"""
    place_count = 0
    rows = session.run(
        "MATCH (a:Artwork) WHERE a.culture IS NOT NULL AND a.culture <> '' "
        "RETURN DISTINCT a.culture as culture"
    )
    for row in rows:
        culture_val = row["culture"]
        for kw in PLACE_KEYWORDS:
            if kw.lower() in culture_val.lower():
                session.run(
                    """
                    MERGE (p:Place {name: $name})
                    WITH p
                    MATCH (a:Artwork {culture: $culture_val})
                    MERGE (a)-[:FROM_PLACE]->(p)
                    """,
                    name=kw,
                    culture_val=culture_val,
                )
                place_count += 1
                break  # 一個 culture 值只取第一個命中的地點關鍵字，避免重複
    logger.info(f"✅ (7)地點: {place_count} 種 culture 值歸類完成")


def classify_institutions(session):
    """(8) 機構：依來源對應，specialized_art/europeana 用真實機構欄位"""
    count = 0
    for source, inst_name in FIXED_SOURCE_INSTITUTIONS.items():
        result = session.run(
            """
            MERGE (i:Institution {name: $inst_name})
            WITH i
            MATCH (a:Artwork {source: $source})
            MERGE (a)-[:HELD_BY]->(i)
            RETURN count(a) as c
            """,
            inst_name=inst_name,
            source=source,
        )
        count += result.single()["c"]

    # specialized_art 的 department 欄位本身就是資料提供機構
    rows = session.run(
        "MATCH (a:Artwork {source:'specialized_art'}) "
        "WHERE a.department IS NOT NULL AND a.department <> '' "
        "RETURN DISTINCT a.department as dept"
    )
    for row in rows:
        dept = row["dept"]
        session.run(
            """
            MERGE (i:Institution {name: $dept})
            WITH i
            MATCH (a:Artwork {source:'specialized_art', department: $dept})
            MERGE (a)-[:HELD_BY]->(i)
            """,
            dept=dept,
        )
        count += 1

    # europeana 的 provider 欄位是真實機構
    rows = session.run(
        "MATCH (a:Artwork {source:'europeana'}) WHERE a.provider IS NOT NULL AND a.provider <> '' "
        "RETURN DISTINCT a.provider as provider"
    )
    for row in rows:
        provider = row["provider"]
        session.run(
            """
            MERGE (i:Institution {name: $provider})
            WITH i
            MATCH (a:Artwork {source:'europeana', provider: $provider})
            MERGE (a)-[:HELD_BY]->(i)
            """,
            provider=provider,
        )
        count += 1
    logger.info(f"✅ (8)機構: 共處理 {count} 個機構對應")


def tag_text_sources(session):
    """(10) 文獻 Source/Text：google_books 來源額外標記 :Source"""
    result = session.run(
        "MATCH (a:Artwork {source:'google_books'}) SET a:Source RETURN count(a) as c"
    )
    logger.info(f"✅ (10)文獻: {result.single()['c']} 筆 google_books 資料標記為 :Source")


def classify_concepts_and_theme_genres(session, terms):
    """(11) 概念與術語：art_concepts 詞典比對作品標題/描述

    (5) 主題與圖像學：只用詞典裡可靠的 genre 詞（portrait/landscape/still life），
    不對描述文字自由猜測
    """
    concept_count = 0
    for term, translations in terms.get("art_concepts", {}).items():
        # 先無條件建立 Concept 節點（就算目前沒有作品命中，節點與翻譯也要存在）
        # 再另外找命中的作品建立關聯
        session.run("MERGE (c:Concept {name: $term})", term=term).consume()
        result = session.run(
            """
            MATCH (a:Artwork)
            WHERE toLower(a.title) CONTAINS toLower($term)
               OR toLower(a.description) CONTAINS toLower($term)
            MATCH (c:Concept {name: $term})
            MERGE (a)-[:MENTIONS_CONCEPT]->(c)
            RETURN count(a) as c
            """,
            term=term,
        )
        concept_count += result.single()["c"]
        add_translations(session, "Concept", term, translations)
    n_concepts = len(terms.get("art_concepts", {}))
    logger.info(f"✅ (11)概念與術語: {n_concepts} 個概念詞條，共 {concept_count} 筆作品關聯")

    theme_genre_terms = {"portrait", "landscape", "still life"}
    theme_count = 0
    for term in theme_genre_terms:
        translations = terms.get("art_types", {}).get(term)
        if not translations:
            continue
        session.run("MERGE (th:Theme {name: $term})", term=term).consume()
        result = session.run(
            """
            MATCH (a:Artwork)
            WHERE toLower(a.title) CONTAINS toLower($term)
               OR toLower(a.description) CONTAINS toLower($term)
            MATCH (th:Theme {name: $term})
            MERGE (a)-[:DEPICTS_THEME]->(th)
            RETURN count(a) as c
            """,
            term=term,
        )
        theme_count += result.single()["c"]
        add_translations(session, "Theme", term, translations)
    logger.info(
        f"✅ (5)主題與圖像學（僅詞典可靠 genre 詞，未對描述文字自由猜測）: {theme_count} 筆作品關聯"
    )


def seed_dictionary_styles_materials(session, terms):
    """把詞典裡的 art_periods / materials / art_types(fresco,drawing) 詞條也建成節點並掛翻譯，
    即使目前作品資料沒有命中，也讓 (3)(4)(12) 的節點/翻譯完整"""
    for term, translations in terms.get("art_periods", {}).items():
        session.run("MERGE (s:Style {name: $name})", name=term).consume()
        add_translations(session, "Style", term, translations)

    for term, translations in terms.get("materials", {}).items():
        session.run("MERGE (m:Material {name: $name})", name=term).consume()
        add_translations(session, "Material", term, translations)

    for term in ["fresco", "drawing"]:
        translations = terms.get("art_types", {}).get(term)
        if translations:
            session.run("MERGE (t:Technique {name: $name})", name=term).consume()
            add_translations(session, "Technique", term, translations)

    for term, translations in terms.get("famous_artists", {}).items():
        # 只對已存在的真實 Artist 節點掛翻譯，不新建不存在的藝術家節點
        session.run(
            "MATCH (a:Artist {name: $name}) SET a.has_translation_seed = true",
            name=term,
        ).consume()
        add_translations(session, "Artist", term, translations)

    logger.info("✅ 詞典裡的風格/材質/技法/藝術家詞條與翻譯已補齊 (12.版本/語言)")


def ensure_empty_schema_labels(session):
    """(9) 事件：僅建立標籤與唯一性約束，不填入任何資料（無來源資料可用，避免捏造）"""
    session.run(
        "CREATE CONSTRAINT event_name_unique IF NOT EXISTS FOR (n:Event) REQUIRE n.name IS UNIQUE"
    ).consume()
    logger.info("✅ (9)事件: schema 已建立，暫不填入資料（無來源資料）")


def print_summary(session):
    logger.info("=" * 60)
    logger.info("📊 12 類分類節點統計")
    for label in [
        "Artist",
        "Artwork",
        "Style",
        "Technique",
        "Material",
        "Theme",
        "Period",
        "Place",
        "Institution",
        "Event",
        "Source",
        "Concept",
        "Translation",
    ]:
        result = session.run(f"MATCH (n:{label}) RETURN count(n) as c")
        logger.info(f"  {label}: {result.single()['c']}")
    logger.info("=" * 60)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--no-clean", action="store_true", help="不清除舊示範節點，只疊加分類")
    args = parser.parse_args()

    terms = load_terms_dictionary()

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    logger.info("✅ Neo4j 連接成功")

    with driver.session() as session:
        if not args.no_clean:
            clean_demo_nodes(session)

        ensure_constraints(session)
        ensure_empty_schema_labels(session)

        classify_styles_and_periods(session)
        classify_materials_and_techniques(session)
        classify_places(session)
        classify_institutions(session)
        tag_text_sources(session)
        classify_concepts_and_theme_genres(session, terms)
        seed_dictionary_styles_materials(session, terms)

        print_summary(session)

    driver.close()


if __name__ == "__main__":
    main()
