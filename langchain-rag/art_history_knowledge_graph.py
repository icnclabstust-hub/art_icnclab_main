#!/usr/bin/env python3
"""
藝術史知識圖譜架構設計
定義實體類型、屬性和關係
"""

import json
from dataclasses import dataclass, field
from enum import Enum


class NodeType(Enum):
    """節點類型定義"""

    ARTIST = "Artist"
    ARTWORK = "Artwork"
    MOVEMENT = "Movement"
    PERIOD = "Period"
    LOCATION = "Location"
    MUSEUM = "Museum"
    TECHNIQUE = "Technique"
    MEDIUM = "Medium"
    THEME = "Theme"
    STYLE = "Style"
    PATRON = "Patron"
    COLLECTION = "Collection"


class RelationType(Enum):
    """關係類型定義"""

    # 藝術家關係
    CREATED_BY = "CREATED_BY"
    INFLUENCED_BY = "INFLUENCED_BY"
    TAUGHT_BY = "TAUGHT_BY"
    COLLABORATED_WITH = "COLLABORATED_WITH"

    # 作品關係
    DEPICTS = "DEPICTS"
    USES_TECHNIQUE = "USES_TECHNIQUE"
    USES_MEDIUM = "USES_MEDIUM"
    PART_OF_COLLECTION = "PART_OF_COLLECTION"
    EXHIBITED_AT = "EXHIBITED_AT"

    # 時期和風格關係
    BELONGS_TO_MOVEMENT = "BELONGS_TO_MOVEMENT"
    ACTIVE_IN_PERIOD = "ACTIVE_IN_PERIOD"
    ORIGINATED_IN = "ORIGINATED_IN"
    DEVELOPED_FROM = "DEVELOPED_FROM"

    # 地理關係
    BORN_IN = "BORN_IN"
    WORKED_IN = "WORKED_IN"
    LOCATED_IN = "LOCATED_IN"

    # 收藏關係
    OWNED_BY = "OWNED_BY"
    PATRONIZED_BY = "PATRONIZED_BY"
    HOUSED_IN = "HOUSED_IN"


@dataclass
class NodeDefinition:
    """節點定義"""

    type: NodeType
    properties: dict[str, type]
    required_properties: list[str]
    description: str


@dataclass
class RelationshipDefinition:
    """關係定義"""

    type: RelationType
    from_node: NodeType
    to_node: NodeType
    properties: dict[str, type] = field(default_factory=dict)
    description: str = ""


class ArtHistoryKnowledgeGraphSchema:
    """藝術史知識圖譜架構"""

    def __init__(self):
        self.nodes = self._define_nodes()
        self.relationships = self._define_relationships()

    def _define_nodes(self) -> dict[NodeType, NodeDefinition]:
        """定義所有節點類型"""
        return {
            NodeType.ARTIST: NodeDefinition(
                type=NodeType.ARTIST,
                properties={
                    "name": str,
                    "birth_year": int,
                    "death_year": int,
                    "nationality": str,
                    "biography": str,
                    "gender": str,
                    "art_movements": list[str],
                    "notable_works": list[str],
                    "techniques_used": list[str],
                },
                required_properties=["name"],
                description="藝術家實體，包含個人信息和藝術背景",
            ),
            NodeType.ARTWORK: NodeDefinition(
                type=NodeType.ARTWORK,
                properties={
                    "title": str,
                    "creation_date": int,
                    "description": str,
                    "dimensions": str,
                    "medium": str,
                    "technique": str,
                    "provenance": str,
                    "significance": str,
                    "theme": list[str],
                    "style": str,
                    "condition": str,
                    "estimated_value": float,
                },
                required_properties=["title"],
                description="藝術作品實體，包含作品詳細信息",
            ),
            NodeType.MOVEMENT: NodeDefinition(
                type=NodeType.MOVEMENT,
                properties={
                    "name": str,
                    "start_period": int,
                    "end_period": int,
                    "origin_location": str,
                    "characteristics": str,
                    "key_principles": list[str],
                    "major_figures": list[str],
                    "historical_context": str,
                },
                required_properties=["name"],
                description="藝術運動實體，如印象派、巴洛克等",
            ),
            NodeType.PERIOD: NodeDefinition(
                type=NodeType.PERIOD,
                properties={
                    "name": str,
                    "start_year": int,
                    "end_year": int,
                    "region": str,
                    "cultural_context": str,
                    "major_events": list[str],
                    "artistic_trends": list[str],
                },
                required_properties=["name", "start_year", "end_year"],
                description="歷史時期實體，如文藝復興、中世紀等",
            ),
            NodeType.LOCATION: NodeDefinition(
                type=NodeType.LOCATION,
                properties={
                    "name": str,
                    "country": str,
                    "region": str,
                    "coordinates": str,
                    "cultural_significance": str,
                    "artistic_importance": str,
                    "notable_sites": list[str],
                },
                required_properties=["name", "country"],
                description="地理位置實體",
            ),
            NodeType.MUSEUM: NodeDefinition(
                type=NodeType.MUSEUM,
                properties={
                    "name": str,
                    "location": str,
                    "founded_year": int,
                    "specialization": list[str],
                    "notable_collections": list[str],
                    "visitor_count": int,
                    "website": str,
                },
                required_properties=["name", "location"],
                description="博物館實體",
            ),
            NodeType.TECHNIQUE: NodeDefinition(
                type=NodeType.TECHNIQUE,
                properties={
                    "name": str,
                    "description": str,
                    "origin_period": str,
                    "materials_required": list[str],
                    "difficulty_level": str,
                    "famous_practitioners": list[str],
                },
                required_properties=["name"],
                description="藝術技法實體",
            ),
            NodeType.MEDIUM: NodeDefinition(
                type=NodeType.MEDIUM,
                properties={
                    "name": str,
                    "type": str,  # 繪畫、雕塑、版畫等
                    "characteristics": str,
                    "historical_usage": str,
                    "preservation_concerns": str,
                },
                required_properties=["name"],
                description="藝術媒材實體",
            ),
            NodeType.THEME: NodeDefinition(
                type=NodeType.THEME,
                properties={
                    "name": str,
                    "description": str,
                    "cultural_context": str,
                    "symbolic_meaning": str,
                    "common_elements": list[str],
                    "historical_prevalence": str,
                },
                required_properties=["name"],
                description="藝術主題實體",
            ),
            NodeType.STYLE: NodeDefinition(
                type=NodeType.STYLE,
                properties={
                    "name": str,
                    "characteristics": str,
                    "time_period": str,
                    "regional_variations": list[str],
                    "visual_elements": list[str],
                    "representative_works": list[str],
                },
                required_properties=["name"],
                description="藝術風格實體",
            ),
            NodeType.PATRON: NodeDefinition(
                type=NodeType.PATRON,
                properties={
                    "name": str,
                    "type": str,  # 個人、教會、政府等
                    "time_period": str,
                    "patronage_style": str,
                    "commissioned_works": list[str],
                    "influence": str,
                },
                required_properties=["name"],
                description="藝術贊助者實體",
            ),
            NodeType.COLLECTION: NodeDefinition(
                type=NodeType.COLLECTION,
                properties={
                    "name": str,
                    "collector": str,
                    "period_collected": str,
                    "focus_area": list[str],
                    "notable_pieces": list[str],
                    "current_status": str,
                },
                required_properties=["name"],
                description="藝術收藏實體",
            ),
        }

    def _define_relationships(self) -> list[RelationshipDefinition]:
        """定義所有關係類型"""
        return [
            # 藝術家創作作品
            RelationshipDefinition(
                type=RelationType.CREATED_BY,
                from_node=NodeType.ARTWORK,
                to_node=NodeType.ARTIST,
                properties={"creation_year": int, "commission_type": str},
                description="作品由藝術家創作",
            ),
            # 藝術家影響關係
            RelationshipDefinition(
                type=RelationType.INFLUENCED_BY,
                from_node=NodeType.ARTIST,
                to_node=NodeType.ARTIST,
                properties={"influence_type": str, "evidence": str},
                description="藝術家受其他藝術家影響",
            ),
            # 師承關係
            RelationshipDefinition(
                type=RelationType.TAUGHT_BY,
                from_node=NodeType.ARTIST,
                to_node=NodeType.ARTIST,
                properties={"teaching_period": str, "teaching_location": str},
                description="藝術家師承關係",
            ),
            # 合作關係
            RelationshipDefinition(
                type=RelationType.COLLABORATED_WITH,
                from_node=NodeType.ARTIST,
                to_node=NodeType.ARTIST,
                properties={"collaboration_type": str, "project": str, "period": str},
                description="藝術家合作關係",
            ),
            # 作品描繪主題
            RelationshipDefinition(
                type=RelationType.DEPICTS,
                from_node=NodeType.ARTWORK,
                to_node=NodeType.THEME,
                properties={"prominence": float, "interpretation": str},
                description="作品描繪特定主題",
            ),
            # 使用技法
            RelationshipDefinition(
                type=RelationType.USES_TECHNIQUE,
                from_node=NodeType.ARTWORK,
                to_node=NodeType.TECHNIQUE,
                properties={"skill_level": str, "innovation": str},
                description="作品使用特定技法",
            ),
            # 使用媒材
            RelationshipDefinition(
                type=RelationType.USES_MEDIUM,
                from_node=NodeType.ARTWORK,
                to_node=NodeType.MEDIUM,
                properties={"primary": bool, "quality": str},
                description="作品使用特定媒材",
            ),
            # 屬於藝術運動
            RelationshipDefinition(
                type=RelationType.BELONGS_TO_MOVEMENT,
                from_node=NodeType.ARTIST,
                to_node=NodeType.MOVEMENT,
                properties={"involvement_level": str, "period": str},
                description="藝術家屬於特定藝術運動",
            ),
            # 活躍於歷史時期
            RelationshipDefinition(
                type=RelationType.ACTIVE_IN_PERIOD,
                from_node=NodeType.ARTIST,
                to_node=NodeType.PERIOD,
                properties={"activity_type": list[str], "productivity": str},
                description="藝術家活躍於特定歷史時期",
            ),
            # 出生地
            RelationshipDefinition(
                type=RelationType.BORN_IN,
                from_node=NodeType.ARTIST,
                to_node=NodeType.LOCATION,
                properties={"birth_year": int},
                description="藝術家出生地",
            ),
            # 工作地點
            RelationshipDefinition(
                type=RelationType.WORKED_IN,
                from_node=NodeType.ARTIST,
                to_node=NodeType.LOCATION,
                properties={"work_period": str, "major_works_created": list[str]},
                description="藝術家工作地點",
            ),
            # 博物館位置
            RelationshipDefinition(
                type=RelationType.LOCATED_IN,
                from_node=NodeType.MUSEUM,
                to_node=NodeType.LOCATION,
                description="博物館位置",
            ),
            # 作品收藏於博物館
            RelationshipDefinition(
                type=RelationType.HOUSED_IN,
                from_node=NodeType.ARTWORK,
                to_node=NodeType.MUSEUM,
                properties={"acquisition_date": str, "display_status": str},
                description="作品收藏於博物館",
            ),
            # 贊助關係
            RelationshipDefinition(
                type=RelationType.PATRONIZED_BY,
                from_node=NodeType.ARTIST,
                to_node=NodeType.PATRON,
                properties={"patronage_period": str, "support_type": str},
                description="藝術家受贊助者支持",
            ),
            # 運動起源地
            RelationshipDefinition(
                type=RelationType.ORIGINATED_IN,
                from_node=NodeType.MOVEMENT,
                to_node=NodeType.LOCATION,
                properties={"origin_year": int, "founding_context": str},
                description="藝術運動起源地",
            ),
            # 運動發展關係
            RelationshipDefinition(
                type=RelationType.DEVELOPED_FROM,
                from_node=NodeType.MOVEMENT,
                to_node=NodeType.MOVEMENT,
                properties={"development_type": str, "key_changes": list[str]},
                description="藝術運動發展關係",
            ),
            # 收藏關係
            RelationshipDefinition(
                type=RelationType.PART_OF_COLLECTION,
                from_node=NodeType.ARTWORK,
                to_node=NodeType.COLLECTION,
                properties={"acquisition_method": str, "acquisition_date": str},
                description="作品為收藏的一部分",
            ),
        ]

    def get_cypher_schema_creation(self) -> list[str]:
        """生成創建圖譜架構的Cypher語句"""
        cypher_statements = []

        # 創建約束
        for node_type, node_def in self.nodes.items():
            if "name" in node_def.required_properties:
                cypher_statements.append(
                    f"CREATE CONSTRAINT {node_type.value.lower()}_name_unique IF NOT EXISTS "
                    f"FOR (n:{node_type.value}) REQUIRE n.name IS UNIQUE"
                )

        # 創建索引
        for node_type, node_def in self.nodes.items():
            for prop in node_def.required_properties:
                cypher_statements.append(
                    f"CREATE INDEX {node_type.value.lower()}_{prop}_index IF NOT EXISTS "
                    f"FOR (n:{node_type.value}) ON (n.{prop})"
                )

        return cypher_statements

    def get_sample_data_cypher(self) -> list[str]:
        """生成示例數據的Cypher語句"""
        return [
            # 創建藝術家節點
            """
            CREATE (leonardo:Artist {
                name: "Leonardo da Vinci",
                birth_year: 1452,
                death_year: 1519,
                nationality: "Italian",
                biography: "Renaissance polymath, artist, scientist, engineer, inventor",
                gender: "Male",
                art_movements: ["Renaissance", "High Renaissance"],
                notable_works: ["Mona Lisa", "The Last Supper", "Vitruvian Man"],
                techniques_used: ["Sfumato", "Chiaroscuro", "Oil painting"]
            })
            """,
            # 創建作品節點
            """
            CREATE (monalisa:Artwork {
                title: "Mona Lisa",
                creation_date: 1503,
                description: "Portrait of Lisa Gherardini, famous for her enigmatic smile",
                dimensions: "77 cm × 53 cm",
                medium: "Oil",
                technique: "Sfumato",
                significance: "Most famous painting in the world",
                theme: ["Portrait", "Renaissance humanism"],
                style: "High Renaissance"
            })
            """,
            # 創建藝術運動節點
            """
            CREATE (renaissance:Movement {
                name: "Renaissance",
                start_period: 1400,
                end_period: 1600,
                origin_location: "Italy",
                characteristics: "Revival of classical learning and humanism",
                key_principles: ["Humanism", "Perspective", "Naturalism"],
                major_figures: ["Leonardo da Vinci", "Michelangelo", "Raphael"],
                historical_context: "Transition from Medieval to Early Modern Europe"
            })
            """,
            # 創建關係
            "MATCH (m:Artwork {title: 'Mona Lisa'}), (a:Artist {name: 'Leonardo da Vinci'}) CREATE (m)-[:CREATED_BY {creation_year: 1503}]->(a)",
            "MATCH (a:Artist {name: 'Leonardo da Vinci'}), (mov:Movement {name: 'Renaissance'}) CREATE (a)-[:BELONGS_TO_MOVEMENT {involvement_level: 'Leading figure'}]->(mov)",
        ]

    def export_schema(self, format: str = "json") -> str:
        """匯出架構定義"""
        schema_data = {
            "nodes": {
                node_type.value: {
                    "properties": {
                        prop: str(prop_type.__name__)
                        for prop, prop_type in node_def.properties.items()
                    },
                    "required_properties": node_def.required_properties,
                    "description": node_def.description,
                }
                for node_type, node_def in self.nodes.items()
            },
            "relationships": [
                {
                    "type": rel_def.type.value,
                    "from_node": rel_def.from_node.value,
                    "to_node": rel_def.to_node.value,
                    "properties": {
                        prop: str(prop_type.__name__)
                        for prop, prop_type in rel_def.properties.items()
                    },
                    "description": rel_def.description,
                }
                for rel_def in self.relationships
            ],
        }

        if format.lower() == "json":
            return json.dumps(schema_data, ensure_ascii=False, indent=2)
        else:
            raise ValueError(f"不支持的格式: {format}")


# 使用示例
if __name__ == "__main__":
    schema = ArtHistoryKnowledgeGraphSchema()

    # 輸出架構
    print("=== 藝術史知識圖譜架構 ===")
    print(f"節點類型數量: {len(schema.nodes)}")
    print(f"關係類型數量: {len(schema.relationships)}")

    # 輸出Cypher創建語句
    print("\n=== Cypher架構創建語句 ===")
    for stmt in schema.get_cypher_schema_creation():
        print(stmt)

    # 輸出示例數據
    print("\n=== 示例數據創建語句 ===")
    for stmt in schema.get_sample_data_cypher():
        print(stmt.strip())

    # 匯出完整架構
    print("\n=== 完整架構JSON ===")
    print(schema.export_schema())
