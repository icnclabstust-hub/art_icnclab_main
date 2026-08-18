#!/usr/bin/env python3
"""
增強的藝術史知識圖譜構建器
基於更細緻的節點分類體系構建數據
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

from enhanced_art_history_schema import EnhancedArtHistorySchema, NodeType, RelationType

logger = logging.getLogger(__name__)


@dataclass
class EnhancedArtEntity:
    """增強的藝術史實體"""

    entity_type: NodeType
    name: str
    properties: dict[str, Any]
    subcategory: str | None = None
    aliases: list[str] = None

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []


class EnhancedArtHistoryGraphBuilder:
    """增強的藝術史知識圖譜構建器"""

    def __init__(self, graph=None):
        self.graph = graph
        self.schema = EnhancedArtHistorySchema()
        self.entities = []
        self.relationships = []

    def add_comprehensive_enhanced_data(self):
        """添加全面的增強藝術史數據"""

        # === 1. 詳細藝術家數據 ===
        artists = [
            {
                "name": "Leonardo da Vinci",
                "full_name": "Leonardo di ser Piero da Vinci",
                "birth_year": 1452,
                "death_year": 1519,
                "birth_place": "Vinci, Republic of Florence",
                "death_place": "Amboise, Kingdom of France",
                "nationality": "Italian",
                "gender": "Male",
                "biography": "Renaissance polymath: painter, scientist, engineer, inventor, anatomist",
                "education": ["Andrea del Verrocchio's workshop"],
                "teachers": ["Andrea del Verrocchio"],
                "students": ["Francesco Melzi", "Gian Giacomo Caprotti"],
                "art_movements": ["High Renaissance", "Renaissance"],
                "periods": ["Early Renaissance", "High Renaissance"],
                "primary_medium": ["Oil painting", "Drawing", "Fresco"],
                "signature_techniques": ["Sfumato", "Chiaroscuro", "Anatomical accuracy"],
                "notable_works": [
                    "Mona Lisa",
                    "The Last Supper",
                    "Vitruvian Man",
                    "Lady with an Ermine",
                ],
                "awards_honors": ["Court artist to Francis I of France"],
                "exhibitions": ["Leonardo da Vinci: Painter at the Court of Milan"],
                "collections": ["Louvre", "National Gallery London", "Uffizi"],
                "artistic_evolution": "From traditional workshop training to revolutionary innovations",
                "historical_significance": "Epitome of Renaissance universal genius",
                "market_value_trend": "Priceless - most valuable artworks in history",
                "social_background": "Illegitimate son of notary, rose through talent",
                "family_connections": ["Ser Piero da Vinci (father)"],
                "workshop_location": "Milan, Florence, France",
                "patrons": ["Ludovico Sforza", "Francis I of France", "Cesare Borgia"],
                "influences": ["Classical antiquity", "Nature observation", "Verrocchio"],
                "legacy": "Scientific method in art, perfectionism, interdisciplinary approach",
            },
            {
                "name": "Claude Monet",
                "full_name": "Oscar-Claude Monet",
                "birth_year": 1840,
                "death_year": 1926,
                "birth_place": "Paris, France",
                "death_place": "Giverny, France",
                "nationality": "French",
                "gender": "Male",
                "biography": "Founder and leading figure of Impressionism",
                "education": ["École des Beaux-Arts (briefly)", "Self-taught"],
                "teachers": ["Eugène Boudin", "Johan Jongkind"],
                "students": ["Blanche Hoschedé-Monet"],
                "art_movements": ["Impressionism"],
                "periods": ["Late 19th century", "Early 20th century"],
                "primary_medium": ["Oil painting", "Pastels"],
                "signature_techniques": ["Plein air painting", "Broken color", "Light studies"],
                "notable_works": [
                    "Water Lilies",
                    "Impression, Sunrise",
                    "Rouen Cathedral",
                    "Haystacks",
                ],
                "exhibitions": ["First Impressionist Exhibition 1874", "Salon des Indépendants"],
                "collections": [
                    "Musée Marmottan",
                    "Metropolitan Museum",
                    "National Gallery London",
                ],
                "artistic_evolution": "From landscape realism to light abstraction",
                "historical_significance": "Revolutionized modern painting through light studies",
                "workshop_location": "Giverny gardens",
                "patrons": ["Paul Durand-Ruel", "Gustave Caillebotte"],
                "influences": ["Eugène Boudin", "Japanese prints", "Turner"],
                "legacy": "Foundation of modern art through Impressionism",
            },
            {
                "name": "Frida Kahlo",
                "full_name": "Magdalena Carmen Frida Kahlo y Calderón",
                "birth_year": 1907,
                "death_year": 1954,
                "birth_place": "Coyoacán, Mexico City",
                "death_place": "Coyoacán, Mexico City",
                "nationality": "Mexican",
                "gender": "Female",
                "biography": "Surrealist painter known for self-portraits and Mexican culture",
                "education": ["Self-taught"],
                "art_movements": ["Surrealism", "Mexican Muralism", "Mexicanidad"],
                "periods": ["20th century modernism"],
                "primary_medium": ["Oil painting", "Mixed media"],
                "signature_techniques": ["Symbolic self-portraiture", "Mexican folk art elements"],
                "notable_works": [
                    "The Two Fridas",
                    "Self-Portrait with Thorn Necklace",
                    "The Broken Column",
                ],
                "exhibitions": [
                    "First solo exhibition 1953",
                    "Posthumous international recognition",
                ],
                "historical_significance": "Icon of Mexican identity and feminist art",
                "social_background": "Middle-class Mexican family, political activism",
                "patrons": ["Diego Rivera", "André Breton"],
                "influences": ["Mexican folk art", "Pre-Columbian art", "European Surrealism"],
                "legacy": "Feminist icon, Mexican cultural ambassador through art",
            },
        ]

        # === 2. 細分的作品類型 ===
        paintings = [
            {
                "title": "Mona Lisa",
                "alternative_titles": ["La Gioconda", "La Joconde"],
                "creation_date": "1503-1519",
                "completion_date": "1519",
                "artist": "Leonardo da Vinci",
                "dimensions": "77 cm × 53 cm (30 in × 21 in)",
                "medium": "Oil",
                "support": "Poplar wood panel",
                "technique": ["Sfumato", "Chiaroscuro", "Oil glazing"],
                "style": "High Renaissance",
                "genre": "Portrait",
                "subject_matter": ["Portrait", "Landscape background"],
                "description": "Portrait of Lisa Gherardini with enigmatic smile and atmospheric landscape",
                "iconography": ["Enigmatic smile", "Hands placement", "Veil", "Landscape"],
                "composition": "Three-quarter view with pyramidal composition",
                "color_palette": ["Earth tones", "Subtle greens", "Warm flesh tones"],
                "condition": "Good with minor cracking",
                "provenance": [
                    "Francis I of France",
                    "French Royal Collection",
                    "Louvre acquisition 1797",
                ],
                "exhibitions": ["Permanent display Louvre", "Rare loans to other museums"],
                "publications": ["Countless scholarly articles", "Popular culture references"],
                "current_location": "Louvre Museum, Paris",
                "insurance_value": "Priceless",
                "market_value": "Estimated over $1 billion",
                "signature": False,
                "inscription": "None visible",
                "frame": "Modern protective case",
                "historical_context": "Renaissance humanism and portraiture innovation",
                "cultural_significance": "Global icon of art and culture",
                "technical_analysis": "X-ray reveals under-drawings and painting process",
                "conservation_history": [
                    "1911 theft recovery",
                    "Modern climate control",
                    "Protective glass",
                ],
                "related_works": ["Lady with an Ermine", "Portrait of Ginevra de' Benci"],
            },
            {
                "title": "Water Lilies (Nymphéas)",
                "alternative_titles": ["Les Nymphéas", "Water Lily Pond"],
                "creation_date": "1897-1926",
                "completion_date": "Various dates - series",
                "artist": "Claude Monet",
                "dimensions": "Various sizes - largest 2m x 6m",
                "medium": "Oil",
                "support": "Canvas",
                "technique": ["Plein air painting", "Broken brushwork", "Color layering"],
                "style": "Impressionism",
                "genre": "Landscape",
                "subject_matter": ["Water garden", "Light reflections", "Natural abstraction"],
                "description": "Series of paintings of Monet's water garden at Giverny",
                "iconography": ["Water lilies", "Bridge", "Weeping willows", "Light reflections"],
                "composition": "Horizontal panoramic views, some without horizon line",
                "color_palette": ["Blues", "Greens", "Purples", "Yellow highlights"],
                "condition": "Varies by individual painting",
                "provenance": ["Artist's estate", "Various museums and private collections"],
                "exhibitions": ["Orangerie installation", "Major Monet retrospectives"],
                "current_location": "Multiple museums worldwide",
                "historical_context": "Late Impressionism and abstraction development",
                "cultural_significance": "Bridge between Impressionism and abstract art",
                "related_works": ["Japanese Bridge series", "Rouen Cathedral series"],
            },
        ]

        # === 3. 詳細博物館數據 ===
        museums = [
            {
                "name": "Louvre Museum",
                "full_name": "Musée du Louvre",
                "location": "Rue de Rivoli, Paris",
                "city": "Paris",
                "country": "France",
                "founded_year": 1793,
                "founder": "French Republic",
                "museum_type": "National art museum",
                "specialization": ["European painting", "Ancient civilizations", "Decorative arts"],
                "collection_size": 380000,
                "permanent_collection": ["Mona Lisa", "Venus de Milo", "Winged Victory"],
                "notable_works": ["Mona Lisa", "Liberty Leading the People", "Wedding at Cana"],
                "annual_visitors": 9600000,
                "director": "Laurence des Cars",
                "curators": ["Department curators for each collection"],
                "building_architect": "Pierre Lescot, I.M. Pei (pyramid)",
                "building_style": "French Renaissance with modern additions",
                "website": "www.louvre.fr",
                "opening_hours": "9 AM - 6 PM (varies by day)",
                "admission_policy": "Paid admission with exceptions",
                "educational_programs": ["School programs", "Adult courses", "Audio guides"],
                "research_facilities": True,
                "conservation_lab": True,
                "library": True,
                "gift_shop": True,
                "restaurant": True,
                "accessibility": ["Wheelchair access", "Audio descriptions", "Touch tours"],
                "partnerships": ["International museum loans", "Academic collaborations"],
                "funding_sources": ["French government", "Admissions", "Donations", "Sponsorships"],
                "mission_statement": "Preserve and present art heritage for public education",
                "acquisition_policy": "Strategic acquisitions filling collection gaps",
                "deaccession_policy": "Rarely deaccessions due to national treasure status",
            },
            {
                "name": "Museum of Modern Art",
                "full_name": "The Museum of Modern Art",
                "location": "11 West 53rd Street, Manhattan",
                "city": "New York",
                "country": "United States",
                "founded_year": 1929,
                "founder": "Group of influential patrons led by Abby Aldrich Rockefeller",
                "museum_type": "Modern and contemporary art museum",
                "specialization": ["Modern art", "Contemporary art", "Design", "Film"],
                "collection_size": 200000,
                "permanent_collection": [
                    "The Starry Night",
                    "Les Demoiselles d'Avignon",
                    "Campbell's Soup Cans",
                ],
                "notable_works": [
                    "The Starry Night",
                    "The Persistence of Memory",
                    "Broadway Boogie-Woogie",
                ],
                "annual_visitors": 3000000,
                "director": "Glenn D. Lowry",
                "building_architect": "Yoshio Taniguchi (2004 renovation)",
                "building_style": "Modern architecture",
                "website": "www.moma.org",
                "educational_programs": ["MoMA Learning", "Teacher programs", "Family programs"],
                "research_facilities": True,
                "conservation_lab": True,
                "library": True,
                "mission_statement": "Help people understand and enjoy modern and contemporary art",
            },
        ]

        # === 4. 詳細展覽數據 ===
        exhibitions = [
            {
                "title": "Leonardo da Vinci: Painter at the Court of Milan",
                "subtitle": "Complete paintings and drawings",
                "venue": "National Gallery, London",
                "start_date": "2011-11-09",
                "end_date": "2012-02-05",
                "duration": 88,
                "exhibition_type": "Monographic retrospective",
                "curator": ["Luke Syson", "Larry Keith"],
                "organizer": "National Gallery London",
                "sponsor": ["Credit Suisse", "Ernst & Young"],
                "theme": "Leonardo's painting practice and technique",
                "concept": "First exhibition to unite Leonardo's surviving paintings",
                "featured_artists": ["Leonardo da Vinci"],
                "artworks": ["Lady with an Ermine", "Salvator Mundi", "The Virgin of the Rocks"],
                "number_of_works": 65,
                "catalog": "Comprehensive scholarly catalog",
                "catalog_authors": ["Luke Syson", "Larry Keith", "Ashok Roy"],
                "visitor_count": 324000,
                "reviews": ["Five stars Guardian", "Exceptional Times review"],
                "press_coverage": ["International media attention", "Documentary films"],
                "educational_programs": ["Lectures", "Drawing workshops", "School visits"],
                "lectures": ["Technical analysis talks", "Renaissance context lectures"],
                "guided_tours": True,
                "audio_guide": True,
                "multimedia": ["Interactive displays", "Digital reconstructions"],
                "significance": "Unprecedented gathering of Leonardo paintings",
                "innovations": [
                    "Advanced technical analysis display",
                    "Digital x-ray presentations",
                ],
            }
        ]

        # === 5. 詳細技法數據 ===
        techniques = [
            {
                "name": "Sfumato",
                "alternative_names": ["Sfumare", "Smoky technique"],
                "category": "Painting technique",
                "description": "Subtle gradations of tone without harsh outlines",
                "origin_period": "High Renaissance",
                "origin_location": "Italy",
                "inventor": "Leonardo da Vinci",
                "development_history": "Evolved from Leonardo's anatomical and optical studies",
                "materials_required": ["Oil paints", "Multiple glazes", "Fine brushes"],
                "tools_required": ["Soft brushes", "Palette knife", "Glazing medium"],
                "process_steps": ["Underpainting", "Multiple glaze layers", "Subtle blending"],
                "difficulty_level": "Expert",
                "time_required": "Months to years",
                "notable_practitioners": ["Leonardo da Vinci", "Correggio", "Later followers"],
                "masterpieces_using": [
                    "Mona Lisa",
                    "Lady with an Ermine",
                    "The Virgin of the Rocks",
                ],
                "variations": ["Venetian sfumato", "Northern European adaptations"],
                "related_techniques": ["Chiaroscuro", "Glazing", "Impasto"],
                "advantages": ["Atmospheric effects", "Psychological depth", "Luminous quality"],
                "limitations": ["Time-intensive", "Requires expert skill", "Fragile layers"],
                "preservation_concerns": ["Layer separation", "Darkening glazes"],
                "modern_adaptations": ["Digital sfumato effects", "Contemporary oil techniques"],
                "teaching_traditions": ["Academic art education", "Classical ateliers"],
                "cultural_significance": "Epitome of Renaissance painting sophistication",
            }
        ]

        # 構建實體
        for artist_data in artists:
            entity = EnhancedArtEntity(NodeType.ARTIST, artist_data["name"], artist_data)
            self.entities.append(entity)

        for painting_data in paintings:
            entity = EnhancedArtEntity(NodeType.PAINTING, painting_data["title"], painting_data)
            self.entities.append(entity)

        for museum_data in museums:
            entity = EnhancedArtEntity(NodeType.MUSEUM, museum_data["name"], museum_data)
            self.entities.append(entity)

        for exhibition_data in exhibitions:
            entity = EnhancedArtEntity(
                NodeType.EXHIBITION, exhibition_data["title"], exhibition_data
            )
            self.entities.append(entity)

        for technique_data in techniques:
            entity = EnhancedArtEntity(NodeType.TECHNIQUE, technique_data["name"], technique_data)
            self.entities.append(entity)

        # === 6. 新增的節點類型 ===

        # 藝術評論家
        critics = [
            {
                "name": "John Ruskin",
                "full_name": "John Ruskin",
                "birth_year": 1819,
                "death_year": 1900,
                "nationality": "British",
                "specialization": ["Art criticism", "Social criticism", "Architecture"],
                "major_works": ["Modern Painters", "The Stones of Venice"],
                "influence": "Champion of Turner and Pre-Raphaelites",
                "writing_style": "Detailed aesthetic analysis with moral philosophy",
            }
        ]

        for critic_data in critics:
            entity = EnhancedArtEntity(NodeType.CRITIC, critic_data["name"], critic_data)
            self.entities.append(entity)

        # 策展人
        curators = [
            {
                "name": "Harald Szeemann",
                "birth_year": 1933,
                "death_year": 2005,
                "nationality": "Swiss",
                "specialization": ["Contemporary art", "Avant-garde movements"],
                "major_exhibitions": ["When Attitudes Become Form", "Documenta 5"],
                "curatorial_philosophy": "Art as research and experimentation",
                "institutions": ["Kunsthalle Bern", "Independent curator"],
            }
        ]

        for curator_data in curators:
            entity = EnhancedArtEntity(NodeType.CURATOR, curator_data["name"], curator_data)
            self.entities.append(entity)

        logger.info(f"✅ 添加了 {len(self.entities)} 個增強實體")

    def build_enhanced_relationships(self):
        """構建增強的實體間關係"""
        relationships = [
            # === 創作關係 ===
            (
                "Mona Lisa",
                RelationType.CREATED_BY,
                "Leonardo da Vinci",
                {
                    "creation_year": 1503,
                    "creation_location": "Florence/France",
                    "commission_type": "Portrait commission",
                    "attribution_certainty": 1.0,
                },
            ),
            (
                "Water Lilies (Nymphéas)",
                RelationType.CREATED_BY,
                "Claude Monet",
                {
                    "creation_year": 1919,
                    "creation_location": "Giverny",
                    "commission_type": "Personal project",
                    "attribution_certainty": 1.0,
                },
            ),
            # === 技法使用 ===
            (
                "Mona Lisa",
                RelationType.USES_TECHNIQUE,
                "Sfumato",
                {"skill_level": "Master", "innovation": "Perfected the technique"},
            ),
            # === 收藏關係 ===
            (
                "Mona Lisa",
                RelationType.HOUSED_IN,
                "Louvre Museum",
                {"acquisition_date": "1797", "display_status": "Permanent display"},
            ),
            (
                "Water Lilies (Nymphéas)",
                RelationType.HOUSED_IN,
                "Museum of Modern Art",
                {"acquisition_date": "Various", "display_status": "Rotating display"},
            ),
            # === 展覽關係 ===
            (
                "Mona Lisa",
                RelationType.EXHIBITED_AT,
                "Leonardo da Vinci: Painter at the Court of Milan",
                {
                    "exhibition_title": "Leonardo da Vinci: Painter at the Court of Milan",
                    "date": "2011-2012",
                    "venue": "National Gallery London",
                    "role": "Featured work",
                    "significance": "Rare loan",
                },
            ),
            # === 影響關係 ===
            (
                "Claude Monet",
                RelationType.INFLUENCED_BY,
                "Leonardo da Vinci",
                {
                    "influence_type": "Light studies and atmospheric effects",
                    "evidence": "Documented in Monet's writings",
                    "period": "1860s onwards",
                    "degree": 0.7,
                    "specific_aspects": ["Light observation", "Atmospheric perspective"],
                },
            ),
            # === 地理關係 ===
            ("Leonardo da Vinci", RelationType.BORN_IN, "Italy", {"birth_year": 1452}),
            (
                "Leonardo da Vinci",
                RelationType.WORKED_IN,
                "France",
                {"work_period": "1516-1519", "major_works_created": ["Late period works"]},
            ),
            (
                "Claude Monet",
                RelationType.WORKED_IN,
                "France",
                {
                    "work_period": "1840-1926",
                    "major_works_created": ["Impression Sunrise", "Water Lilies"],
                },
            ),
            # === 機構關係 ===
            ("Louvre Museum", RelationType.CREATED_IN, "Paris", {}),
            ("Museum of Modern Art", RelationType.CREATED_IN, "New York", {}),
            # === 評論關係 ===
            (
                "Leonardo da Vinci",
                RelationType.CRITIQUED_BY,
                "John Ruskin",
                {
                    "criticism_type": "Historical analysis",
                    "publication": "Modern Painters",
                    "assessment": "Praise for naturalistic observation",
                },
            ),
            # === 策展關係 ===
            (
                "Leonardo da Vinci: Painter at the Court of Milan",
                RelationType.CREATED_BY,
                "Luke Syson",
                {
                    "curatorial_approach": "Technical and historical analysis",
                    "exhibition_concept": "Complete painting oeuvre",
                },
            ),
        ]

        for from_entity, relation_type, to_entity, properties in relationships:
            self.relationships.append(
                {
                    "from": from_entity,
                    "type": relation_type.value,
                    "to": to_entity,
                    "properties": properties,
                }
            )

        logger.info(f"✅ 添加了 {len(self.relationships)} 個增強關係")

    def generate_enhanced_cypher_script(self) -> list[str]:
        """生成增強的Cypher創建腳本"""
        cypher_statements = []

        # 清理數據庫
        cypher_statements.append("MATCH (n) DETACH DELETE n")

        # 創建架構約束和索引
        cypher_statements.extend(self.schema.generate_enhanced_cypher_schema())

        # 創建節點
        for entity in self.entities:
            # 清理屬性值，處理特殊字符
            clean_props = {}
            for k, v in entity.properties.items():
                if isinstance(v, str):
                    # 轉義單引號
                    clean_props[k] = v.replace("'", "\\'")
                else:
                    clean_props[k] = v

            props_str = ", ".join([f"{k}: {repr(v)}" for k, v in clean_props.items()])
            cypher = f"CREATE (:{entity.entity_type.value} {{{props_str}}})"
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

    def save_enhanced_data(self):
        """保存增強數據到文件"""
        # 保存實體數據
        entities_data = [
            {
                "type": entity.entity_type.value,
                "name": entity.name,
                "properties": entity.properties,
                "subcategory": entity.subcategory,
                "aliases": entity.aliases,
            }
            for entity in self.entities
        ]

        with open("enhanced_art_history_entities.json", "w", encoding="utf-8") as f:
            json.dump(entities_data, f, ensure_ascii=False, indent=2)

        # 保存關係數據
        with open("enhanced_art_history_relationships.json", "w", encoding="utf-8") as f:
            json.dump(self.relationships, f, ensure_ascii=False, indent=2)

        # 保存Cypher腳本
        cypher_script = self.generate_enhanced_cypher_script()
        with open("create_enhanced_art_history_graph.cypher", "w", encoding="utf-8") as f:
            for statement in cypher_script:
                f.write(statement + ";\n\n")

        # 保存架構定義（簡化版本）
        schema_summary = {
            "node_types": [node_type.value for node_type in self.schema.nodes.keys()],
            "relationship_types": [rel["type"].value for rel in self.schema.relationships],
            "total_entities": len(self.entities),
            "total_relationships": len(self.relationships),
        }
        with open("enhanced_schema.json", "w", encoding="utf-8") as f:
            json.dump(schema_summary, f, ensure_ascii=False, indent=2)

        logger.info("✅ 增強數據已保存到文件")

    def print_statistics(self):
        """打印數據統計"""
        entity_types = {}
        for entity in self.entities:
            entity_type = entity.entity_type.value
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

        print("📊 增強圖譜統計:")
        print(f"   總實體數量: {len(self.entities)}")
        print(f"   總關係數量: {len(self.relationships)}")
        print("   節點類型分布:")
        for entity_type, count in sorted(entity_types.items()):
            print(f"     - {entity_type}: {count}")


# 主程序
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("🚀 開始構建增強的藝術史知識圖譜...")

    # 初始化增強構建器
    builder = EnhancedArtHistoryGraphBuilder()

    # 添加增強數據
    builder.add_comprehensive_enhanced_data()
    builder.build_enhanced_relationships()

    # 打印統計信息
    builder.print_statistics()

    # 保存到文件
    builder.save_enhanced_data()

    print("\n🎉 增強的藝術史知識圖譜構建完成！")
    print("📁 生成文件:")
    print("   - enhanced_art_history_entities.json (增強實體數據)")
    print("   - enhanced_art_history_relationships.json (增強關係數據)")
    print("   - create_enhanced_art_history_graph.cypher (增強Cypher腳本)")
    print("   - enhanced_schema.json (增強架構定義)")
