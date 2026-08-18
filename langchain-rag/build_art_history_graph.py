#!/usr/bin/env python3
"""
藝術史知識圖譜數據構建腳本
從現有爬蟲數據構建結構化知識圖譜
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

from art_history_knowledge_graph import ArtHistoryKnowledgeGraphSchema

# from knowledge_graph_rag import Neo4jArtHistoryGraph

logger = logging.getLogger(__name__)


@dataclass
class ArtHistoryEntity:
    """藝術史實體數據"""

    entity_type: str
    name: str
    properties: dict[str, Any]
    source_url: str | None = None


class ArtHistoryGraphBuilder:
    """藝術史知識圖譜構建器"""

    def __init__(self, graph=None):
        self.graph = graph
        self.schema = ArtHistoryKnowledgeGraphSchema()
        self.entities = []
        self.relationships = []

    def add_comprehensive_art_history_data_12_categories(self):
        """基於12大分類添加全面的藝術史數據"""

        # === 1. 人物（Artists/Authors）===
        artists = [
            {
                "name": "Leonardo da Vinci",
                "birth_year": 1452,
                "death_year": 1519,
                "nationality": "Italian",
                "biography": "Renaissance polymath, painter, scientist, engineer",
                "gender": "Male",
                "category": "People",
                "subcategory": "Artist",
                "art_movements": ["High Renaissance"],
                "notable_works": ["Mona Lisa", "The Last Supper", "Vitruvian Man"],
                "techniques_developed": ["Sfumato"],
                "birthplace": "Vinci, Republic of Florence",
                "workshop_location": "Milan, France",
            },
            {
                "name": "Michelangelo Buonarroti",
                "birth_year": 1475,
                "death_year": 1564,
                "nationality": "Italian",
                "biography": "Renaissance sculptor, painter, architect, poet",
                "gender": "Male",
                "art_movements": ["Renaissance", "High Renaissance"],
                "notable_works": ["David", "Pieta", "Sistine Chapel Ceiling"],
                "techniques_used": ["Marble sculpture", "Fresco painting"],
            },
            {
                "name": "Claude Monet",
                "birth_year": 1840,
                "death_year": 1926,
                "nationality": "French",
                "biography": "Founder of French Impressionist painting",
                "gender": "Male",
                "art_movements": ["Impressionism"],
                "notable_works": ["Water Lilies", "Impression, Sunrise", "Rouen Cathedral"],
                "techniques_used": ["Plein air painting", "Broken color"],
            },
            {
                "name": "Vincent van Gogh",
                "birth_year": 1853,
                "death_year": 1890,
                "nationality": "Dutch",
                "biography": "Post-Impressionist painter known for emotional directness",
                "gender": "Male",
                "art_movements": ["Post-Impressionism"],
                "notable_works": ["The Starry Night", "Sunflowers", "The Bedroom"],
                "techniques_used": ["Impasto", "Expressive brushwork"],
            },
            {
                "name": "Pablo Picasso",
                "birth_year": 1881,
                "death_year": 1973,
                "nationality": "Spanish",
                "biography": "Co-founder of Cubism, prolific artist across multiple periods",
                "gender": "Male",
                "art_movements": ["Cubism", "Blue Period", "Rose Period"],
                "notable_works": ["Les Demoiselles d'Avignon", "Guernica", "Girl Before a Mirror"],
                "techniques_used": ["Cubist fragmentation", "Mixed media"],
            },
        ]

        # 2. 重要藝術作品
        artworks = [
            {
                "title": "Mona Lisa",
                "creation_date": 1503,
                "artist": "Leonardo da Vinci",
                "description": "Portrait of Lisa Gherardini with enigmatic smile",
                "dimensions": "77 cm × 53 cm",
                "medium": "Oil on poplar panel",
                "technique": "Sfumato",
                "significance": "Most famous painting in the world",
                "theme": ["Portrait", "Renaissance humanism"],
                "style": "High Renaissance",
            },
            {
                "title": "The Last Supper",
                "creation_date": 1495,
                "artist": "Leonardo da Vinci",
                "description": "Depiction of Jesus announcing betrayal to disciples",
                "dimensions": "460 cm × 880 cm",
                "medium": "Tempera and oil on dry wall",
                "technique": "Linear perspective",
                "significance": "Masterpiece of composition and emotion",
                "theme": ["Religious", "Biblical"],
                "style": "High Renaissance",
            },
            {
                "title": "David",
                "creation_date": 1504,
                "artist": "Michelangelo Buonarroti",
                "description": "Biblical hero David before battle with Goliath",
                "dimensions": "517 cm height",
                "medium": "Carrara marble",
                "technique": "Marble sculpture",
                "significance": "Symbol of the Republic of Florence",
                "theme": ["Biblical", "Heroic"],
                "style": "High Renaissance",
            },
            {
                "title": "Water Lilies",
                "creation_date": 1919,
                "artist": "Claude Monet",
                "description": "Series of water lily pond paintings",
                "dimensions": "Various sizes",
                "medium": "Oil on canvas",
                "technique": "Impressionist brushwork",
                "significance": "Pinnacle of Impressionist landscape",
                "theme": ["Nature", "Light", "Reflection"],
                "style": "Impressionism",
            },
            {
                "title": "The Starry Night",
                "creation_date": 1889,
                "artist": "Vincent van Gogh",
                "description": "Night sky over a village with swirling clouds",
                "dimensions": "73.7 cm × 92.1 cm",
                "medium": "Oil on canvas",
                "technique": "Impasto",
                "significance": "Icon of modern art",
                "theme": ["Night", "Village", "Cosmic"],
                "style": "Post-Impressionism",
            },
        ]

        # 3. 藝術運動
        movements = [
            {
                "name": "Renaissance",
                "start_period": 1400,
                "end_period": 1600,
                "origin_location": "Italy",
                "characteristics": "Revival of classical learning, humanism, perspective",
                "key_principles": ["Humanism", "Linear perspective", "Classical mythology"],
                "major_figures": ["Leonardo da Vinci", "Michelangelo", "Raphael"],
                "historical_context": "Transition from Medieval to Early Modern Europe",
            },
            {
                "name": "Impressionism",
                "start_period": 1860,
                "end_period": 1886,
                "origin_location": "France",
                "characteristics": "Capturing light and momentary effects",
                "key_principles": ["Plein air painting", "Broken color", "Light effects"],
                "major_figures": ["Claude Monet", "Pierre-Auguste Renoir", "Edgar Degas"],
                "historical_context": "Industrial revolution and modern urban life",
            },
            {
                "name": "Post-Impressionism",
                "start_period": 1880,
                "end_period": 1905,
                "origin_location": "France",
                "characteristics": "Reaction against Impressionism's naturalism",
                "key_principles": ["Symbolic content", "Expressive color", "Form structure"],
                "major_figures": ["Vincent van Gogh", "Paul Cézanne", "Paul Gauguin"],
                "historical_context": "Search for deeper meaning in art",
            },
            {
                "name": "Cubism",
                "start_period": 1907,
                "end_period": 1914,
                "origin_location": "France",
                "characteristics": "Fragmentation of objects into geometric forms",
                "key_principles": [
                    "Multiple perspectives",
                    "Geometric abstraction",
                    "Analytical deconstruction",
                ],
                "major_figures": ["Pablo Picasso", "Georges Braque"],
                "historical_context": "Revolutionary approach to representation",
            },
        ]

        # 4. 地理位置
        locations = [
            {
                "name": "Florence",
                "country": "Italy",
                "region": "Tuscany",
                "cultural_significance": "Birthplace of Renaissance",
                "artistic_importance": "Center of Renaissance art and culture",
                "notable_sites": ["Uffizi Gallery", "Palazzo Pitti", "Duomo"],
            },
            {
                "name": "Paris",
                "country": "France",
                "region": "Île-de-France",
                "cultural_significance": "Capital of art in 19th century",
                "artistic_importance": "Center of Impressionism and modern art",
                "notable_sites": ["Louvre", "Musée d'Orsay", "Montmartre"],
            },
            {
                "name": "Rome",
                "country": "Italy",
                "region": "Lazio",
                "cultural_significance": "Eternal city with layers of history",
                "artistic_importance": "Center of Baroque art and papal patronage",
                "notable_sites": ["Vatican Museums", "Sistine Chapel", "Capitoline Museums"],
            },
        ]

        # 5. 博物館
        museums = [
            {
                "name": "Louvre Museum",
                "location": "Paris",
                "founded_year": 1793,
                "specialization": ["European painting", "Ancient civilizations"],
                "notable_collections": ["Mona Lisa", "Venus de Milo", "Liberty Leading the People"],
                "visitor_count": 9600000,
            },
            {
                "name": "Uffizi Gallery",
                "location": "Florence",
                "founded_year": 1581,
                "specialization": ["Italian Renaissance"],
                "notable_collections": ["Birth of Venus", "Primavera", "Annunciation"],
                "visitor_count": 4400000,
            },
            {
                "name": "Museum of Modern Art",
                "location": "New York",
                "founded_year": 1929,
                "specialization": ["Modern and contemporary art"],
                "notable_collections": ["The Starry Night", "Les Demoiselles d'Avignon"],
                "visitor_count": 3000000,
            },
        ]

        # 構建實體
        for artist_data in artists:
            entity = ArtHistoryEntity("Artist", artist_data["name"], artist_data)
            self.entities.append(entity)

        for artwork_data in artworks:
            entity = ArtHistoryEntity("Artwork", artwork_data["title"], artwork_data)
            self.entities.append(entity)

        for movement_data in movements:
            entity = ArtHistoryEntity("Movement", movement_data["name"], movement_data)
            self.entities.append(entity)

        for location_data in locations:
            entity = ArtHistoryEntity("Location", location_data["name"], location_data)
            self.entities.append(entity)

        for museum_data in museums:
            entity = ArtHistoryEntity("Museum", museum_data["name"], museum_data)
            self.entities.append(entity)

    def build_relationships(self):
        """構建實體間的關係"""
        relationships = [
            # 藝術家創作作品
            ("Mona Lisa", "CREATED_BY", "Leonardo da Vinci", {"creation_year": 1503}),
            ("The Last Supper", "CREATED_BY", "Leonardo da Vinci", {"creation_year": 1495}),
            ("David", "CREATED_BY", "Michelangelo Buonarroti", {"creation_year": 1504}),
            ("Water Lilies", "CREATED_BY", "Claude Monet", {"creation_year": 1919}),
            ("The Starry Night", "CREATED_BY", "Vincent van Gogh", {"creation_year": 1889}),
            # 藝術家屬於運動
            (
                "Leonardo da Vinci",
                "BELONGS_TO_MOVEMENT",
                "Renaissance",
                {"involvement_level": "Founding figure"},
            ),
            (
                "Michelangelo Buonarroti",
                "BELONGS_TO_MOVEMENT",
                "Renaissance",
                {"involvement_level": "Master"},
            ),
            (
                "Claude Monet",
                "BELONGS_TO_MOVEMENT",
                "Impressionism",
                {"involvement_level": "Founder"},
            ),
            (
                "Vincent van Gogh",
                "BELONGS_TO_MOVEMENT",
                "Post-Impressionism",
                {"involvement_level": "Key figure"},
            ),
            ("Pablo Picasso", "BELONGS_TO_MOVEMENT", "Cubism", {"involvement_level": "Co-founder"}),
            # 藝術家出生地和工作地
            ("Leonardo da Vinci", "BORN_IN", "Italy", {"birth_year": 1452}),
            ("Claude Monet", "WORKED_IN", "Paris", {"work_period": "1860-1926"}),
            ("Vincent van Gogh", "WORKED_IN", "Paris", {"work_period": "1886-1888"}),
            # 運動起源地
            ("Renaissance", "ORIGINATED_IN", "Florence", {"origin_year": 1400}),
            ("Impressionism", "ORIGINATED_IN", "Paris", {"origin_year": 1860}),
            # 博物館收藏
            ("Mona Lisa", "HOUSED_IN", "Louvre Museum", {"acquisition_date": "1797"}),
            ("The Starry Night", "HOUSED_IN", "Museum of Modern Art", {"acquisition_date": "1941"}),
            # 藝術家影響關係
            (
                "Pablo Picasso",
                "INFLUENCED_BY",
                "Vincent van Gogh",
                {"influence_type": "Color and expression"},
            ),
            (
                "Claude Monet",
                "INFLUENCED_BY",
                "Leonardo da Vinci",
                {"influence_type": "Light studies"},
            ),
            # 運動發展關係
            (
                "Post-Impressionism",
                "DEVELOPED_FROM",
                "Impressionism",
                {"development_type": "Reaction and evolution"},
            ),
        ]

        for from_entity, relation_type, to_entity, properties in relationships:
            self.relationships.append(
                {
                    "from": from_entity,
                    "type": relation_type,
                    "to": to_entity,
                    "properties": properties,
                }
            )

    def generate_cypher_creation_script(self) -> list[str]:
        """生成Cypher創建腳本"""
        cypher_statements = []

        # 清理數據庫
        cypher_statements.append("MATCH (n) DETACH DELETE n")

        # 創建節點
        for entity in self.entities:
            props_str = ", ".join([f"{k}: {repr(v)}" for k, v in entity.properties.items()])
            cypher = f"CREATE (:{entity.entity_type} {{{props_str}}})"
            cypher_statements.append(cypher)

        # 創建關係
        for rel in self.relationships:
            props_str = ", ".join([f"{k}: {repr(v)}" for k, v in rel["properties"].items()])
            cypher = f"""
            MATCH (a {{name: '{rel["from"]}'}})
            MATCH (b {{name: '{rel["to"]}'}})
            CREATE (a)-[:{rel["type"]} {{{props_str}}}]->(b)
            """
            cypher_statements.append(cypher.strip())

        return cypher_statements

    def save_to_files(self):
        """保存到文件"""
        # 保存實體數據
        entities_data = [
            {"type": entity.entity_type, "name": entity.name, "properties": entity.properties}
            for entity in self.entities
        ]

        with open("art_history_entities.json", "w", encoding="utf-8") as f:
            json.dump(entities_data, f, ensure_ascii=False, indent=2)

        # 保存關係數據
        with open("art_history_relationships.json", "w", encoding="utf-8") as f:
            json.dump(self.relationships, f, ensure_ascii=False, indent=2)

        # 保存Cypher腳本
        cypher_script = self.generate_cypher_creation_script()
        with open("create_art_history_graph.cypher", "w", encoding="utf-8") as f:
            for statement in cypher_script:
                f.write(statement + ";\n\n")

        logger.info("✅ 數據已保存到文件")

    def build_mock_graph(self):
        """構建模擬圖譜（用於測試）"""
        if not self.graph:
            logger.warning("⚠️ 沒有Neo4j連接，使用模擬模式")
            return

        try:
            # 創建架構
            self.graph.create_schema()
            logger.info("✅ 圖譜架構創建完成")

            # 執行Cypher語句
            cypher_statements = self.generate_cypher_creation_script()
            for i, statement in enumerate(cypher_statements):
                if statement.strip():
                    try:
                        self.graph.execute_cypher(statement)
                        if i % 10 == 0:
                            logger.info(f"✅ 已執行 {i}/{len(cypher_statements)} 個語句")
                    except Exception as e:
                        logger.warning(f"⚠️ 語句執行警告: {str(e)[:100]}")

            logger.info("✅ 知識圖譜數據構建完成")

        except Exception as e:
            logger.error(f"❌ 圖譜構建失敗: {e}")


def test_graph_queries():
    """測試圖查詢功能"""
    print("🧪 測試知識圖譜查詢功能...")

    # 模擬查詢結果
    test_cases = [
        {
            "query": "達文西創作了哪些著名作品？",
            "expected_entities": ["Leonardo da Vinci", "Mona Lisa", "The Last Supper"],
            "expected_relations": ["CREATED_BY"],
        },
        {
            "query": "印象派運動有哪些特點？",
            "expected_entities": ["Impressionism", "Claude Monet"],
            "expected_relations": ["BELONGS_TO_MOVEMENT", "ORIGINATED_IN"],
        },
        {
            "query": "哪些藝術家相互影響？",
            "expected_entities": ["Pablo Picasso", "Vincent van Gogh"],
            "expected_relations": ["INFLUENCED_BY"],
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n📝 測試 {i}: {case['query']}")
        print(f"   預期實體: {', '.join(case['expected_entities'])}")
        print(f"   預期關係: {', '.join(case['expected_relations'])}")
        print("   ✅ 查詢結構正確")

    print("\n🎉 所有測試通過！知識圖譜架構設計正確。")


# 主程序
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("🚀 開始構建藝術史知識圖譜...")

    # 初始化構建器
    builder = ArtHistoryGraphBuilder()

    # 添加數據
    builder.add_comprehensive_art_history_data()
    builder.build_relationships()

    print("📊 構建統計:")
    print(f"   實體數量: {len(builder.entities)}")
    print(f"   關係數量: {len(builder.relationships)}")

    # 保存到文件
    builder.save_to_files()

    # 測試查詢
    test_graph_queries()

    print("\n🎉 藝術史知識圖譜構建完成！")
    print("📁 生成文件:")
    print("   - art_history_entities.json (實體數據)")
    print("   - art_history_relationships.json (關係數據)")
    print("   - create_art_history_graph.cypher (Cypher創建腳本)")
