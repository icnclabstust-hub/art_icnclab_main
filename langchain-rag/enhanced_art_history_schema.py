#!/usr/bin/env python3
"""
增強的藝術史知識圖譜架構設計
更細緻的節點分類和關係定義
"""

import json
from dataclasses import dataclass, field
from enum import Enum


class NodeType(Enum):
    """增強的節點類型定義"""

    # === 人物相關 ===
    ARTIST = "Artist"  # 藝術家
    CRITIC = "Critic"  # 藝術評論家
    CURATOR = "Curator"  # 策展人
    DEALER = "Dealer"  # 藝術商人
    PATRON = "Patron"  # 贊助者
    COLLECTOR = "Collector"  # 收藏家
    HISTORIAN = "ArtHistorian"  # 藝術史學家
    APPRENTICE = "Apprentice"  # 學徒
    ASSISTANT = "Assistant"  # 助手
    MODEL = "Model"  # 模特兒

    # === 作品相關 ===
    ARTWORK = "Artwork"  # 藝術作品
    PAINTING = "Painting"  # 繪畫
    SCULPTURE = "Sculpture"  # 雕塑
    DRAWING = "Drawing"  # 素描
    PRINT = "Print"  # 版畫
    PHOTOGRAPH = "Photograph"  # 攝影
    INSTALLATION = "Installation"  # 裝置藝術
    VIDEO_ART = "VideoArt"  # 影像藝術
    PERFORMANCE = "Performance"  # 行為藝術
    DIGITAL_ART = "DigitalArt"  # 數位藝術
    CRAFT = "Craft"  # 工藝品
    MANUSCRIPT = "Manuscript"  # 手稿
    SKETCH = "Sketch"  # 草圖
    STUDY = "Study"  # 習作

    # === 風格和運動 ===
    MOVEMENT = "Movement"  # 藝術運動
    STYLE = "Style"  # 藝術風格
    SCHOOL = "School"  # 畫派
    TECHNIQUE = "Technique"  # 技法
    MEDIUM = "Medium"  # 媒材
    GENRE = "Genre"  # 類型

    # === 時間概念 ===
    PERIOD = "Period"  # 時期
    ERA = "Era"  # 時代
    CENTURY = "Century"  # 世紀
    DECADE = "Decade"  # 年代
    YEAR = "Year"  # 年份
    SEASON = "Season"  # 季節

    # === 地理空間 ===
    CONTINENT = "Continent"  # 大陸
    COUNTRY = "Country"  # 國家
    REGION = "Region"  # 地區
    CITY = "City"  # 城市
    DISTRICT = "District"  # 區域
    LOCATION = "Location"  # 一般地點
    STUDIO = "Studio"  # 工作室
    WORKSHOP = "Workshop"  # 工坊
    ATELIER = "Atelier"  # 畫室

    # === 機構組織 ===
    MUSEUM = "Museum"  # 博物館
    GALLERY = "Gallery"  # 畫廊
    ACADEMY = "Academy"  # 學院
    INSTITUTION = "Institution"  # 機構
    FOUNDATION = "Foundation"  # 基金會
    SOCIETY = "Society"  # 學會
    GUILD = "Guild"  # 行會
    UNIVERSITY = "University"  # 大學
    LIBRARY = "Library"  # 圖書館
    ARCHIVE = "Archive"  # 檔案館

    # === 展覽活動 ===
    EXHIBITION = "Exhibition"  # 展覽
    SOLO_SHOW = "SoloShow"  # 個展
    GROUP_SHOW = "GroupShow"  # 聯展
    BIENNIAL = "Biennial"  # 雙年展
    FAIR = "ArtFair"  # 藝術博覽會
    AUCTION = "Auction"  # 拍賣
    COMPETITION = "Competition"  # 競賽
    FESTIVAL = "Festival"  # 節慶
    SYMPOSIUM = "Symposium"  # 研討會

    # === 主題內容 ===
    THEME = "Theme"  # 主題
    SUBJECT = "Subject"  # 題材
    MOTIF = "Motif"  # 母題
    SYMBOL = "Symbol"  # 象徵
    MYTHOLOGY = "Mythology"  # 神話
    RELIGION = "Religion"  # 宗教
    PORTRAIT = "Portrait"  # 肖像
    LANDSCAPE = "Landscape"  # 風景
    STILL_LIFE = "StillLife"  # 靜物
    HISTORY_PAINTING = "HistoryPainting"  # 歷史畫

    # === 材料工具 ===
    PIGMENT = "Pigment"  # 顏料
    CANVAS = "Canvas"  # 畫布
    PAPER = "Paper"  # 紙張
    WOOD = "Wood"  # 木材
    STONE = "Stone"  # 石材
    METAL = "Metal"  # 金屬
    CLAY = "Clay"  # 黏土
    TOOL = "Tool"  # 工具
    BRUSH = "Brush"  # 畫筆

    # === 收藏保存 ===
    COLLECTION = "Collection"  # 收藏
    PRIVATE_COLLECTION = "PrivateCollection"  # 私人收藏
    PUBLIC_COLLECTION = "PublicCollection"  # 公共收藏
    PROVENANCE = "Provenance"  # 來源
    CONSERVATION = "Conservation"  # 保存
    RESTORATION = "Restoration"  # 修復

    # === 文獻資料 ===
    DOCUMENT = "Document"  # 文獻
    LETTER = "Letter"  # 信件
    DIARY = "Diary"  # 日記
    BIOGRAPHY = "Biography"  # 傳記
    CATALOG = "Catalog"  # 目錄
    ARTICLE = "Article"  # 文章
    BOOK = "Book"  # 書籍
    REVIEW = "Review"  # 評論
    INTERVIEW = "Interview"  # 訪談

    # === 市場經濟 ===
    PRICE = "Price"  # 價格
    VALUATION = "Valuation"  # 估價
    SALE = "Sale"  # 銷售
    COMMISSION = "Commission"  # 委託
    CONTRACT = "Contract"  # 合約
    INSURANCE = "Insurance"  # 保險

    # === 技術分析 ===
    ANALYSIS = "Analysis"  # 分析
    X_RAY = "XRay"  # X光
    INFRARED = "Infrared"  # 紅外線
    PIGMENT_ANALYSIS = "PigmentAnalysis"  # 顏料分析
    CARBON_DATING = "CarbonDating"  # 碳定年
    CONDITION_REPORT = "ConditionReport"  # 狀況報告


class RelationType(Enum):
    """增強的關係類型定義"""

    # === 創作關係 ===
    CREATED_BY = "CREATED_BY"
    DESIGNED_BY = "DESIGNED_BY"
    PAINTED_BY = "PAINTED_BY"
    SCULPTED_BY = "SCULPTED_BY"
    DRAWN_BY = "DRAWN_BY"
    PHOTOGRAPHED_BY = "PHOTOGRAPHED_BY"
    ILLUSTRATED_BY = "ILLUSTRATED_BY"
    ENGRAVED_BY = "ENGRAVED_BY"

    # === 學習傳承 ===
    TAUGHT_BY = "TAUGHT_BY"
    STUDENT_OF = "STUDENT_OF"
    INFLUENCED_BY = "INFLUENCED_BY"
    INSPIRED_BY = "INSPIRED_BY"
    COPIED_FROM = "COPIED_FROM"
    DERIVED_FROM = "DERIVED_FROM"
    BASED_ON = "BASED_ON"
    ATTRIBUTED_TO = "ATTRIBUTED_TO"

    # === 合作關係 ===
    COLLABORATED_WITH = "COLLABORATED_WITH"
    ASSISTED_BY = "ASSISTED_BY"
    WORKED_WITH = "WORKED_WITH"
    COMMISSIONED_BY = "COMMISSIONED_BY"
    PATRONIZED_BY = "PATRONIZED_BY"
    SPONSORED_BY = "SPONSORED_BY"

    # === 歸屬關係 ===
    BELONGS_TO = "BELONGS_TO"
    MEMBER_OF = "MEMBER_OF"
    PART_OF = "PART_OF"
    INCLUDED_IN = "INCLUDED_IN"
    REPRESENTS = "REPRESENTS"
    EXEMPLIFIES = "EXEMPLIFIES"

    # === 時空關係 ===
    CREATED_IN = "CREATED_IN"
    BORN_IN = "BORN_IN"
    DIED_IN = "DIED_IN"
    LIVED_IN = "LIVED_IN"
    WORKED_IN = "WORKED_IN"
    TRAVELED_TO = "TRAVELED_TO"
    ACTIVE_IN = "ACTIVE_IN"
    DATED_TO = "DATED_TO"

    # === 收藏展示 ===
    OWNED_BY = "OWNED_BY"
    COLLECTED_BY = "COLLECTED_BY"
    HOUSED_IN = "HOUSED_IN"
    DISPLAYED_IN = "DISPLAYED_IN"
    EXHIBITED_AT = "EXHIBITED_AT"
    SOLD_AT = "SOLD_AT"
    DONATED_TO = "DONATED_TO"
    BEQUEATHED_TO = "BEQUEATHED_TO"

    # === 技術材料 ===
    USES_TECHNIQUE = "USES_TECHNIQUE"
    USES_MEDIUM = "USES_MEDIUM"
    MADE_OF = "MADE_OF"
    PAINTED_ON = "PAINTED_ON"
    EXECUTED_IN = "EXECUTED_IN"

    # === 內容主題 ===
    DEPICTS = "DEPICTS"
    PORTRAYS = "PORTRAYS"
    ILLUSTRATES = "ILLUSTRATES"
    SYMBOLIZES = "SYMBOLIZES"
    REFERENCES = "REFERENCES"
    ALLUDES_TO = "ALLUDES_TO"

    # === 發展演變 ===
    PRECEDED_BY = "PRECEDED_BY"
    FOLLOWED_BY = "FOLLOWED_BY"
    DEVELOPED_FROM = "DEVELOPED_FROM"
    EVOLVED_INTO = "EVOLVED_INTO"
    CONTEMPORANEOUS_WITH = "CONTEMPORANEOUS_WITH"

    # === 評價分析 ===
    CRITIQUED_BY = "CRITIQUED_BY"
    REVIEWED_BY = "REVIEWED_BY"
    ANALYZED_BY = "ANALYZED_BY"
    AUTHENTICATED_BY = "AUTHENTICATED_BY"
    APPRAISED_BY = "APPRAISED_BY"

    # === 保存修復 ===
    CONSERVED_BY = "CONSERVED_BY"
    RESTORED_BY = "RESTORED_BY"
    DAMAGED_BY = "DAMAGED_BY"
    DESTROYED_BY = "DESTROYED_BY"

    # === 文獻記錄 ===
    DOCUMENTED_IN = "DOCUMENTED_IN"
    MENTIONED_IN = "MENTIONED_IN"
    DESCRIBED_IN = "DESCRIBED_IN"
    CATALOGUED_IN = "CATALOGUED_IN"
    PUBLISHED_IN = "PUBLISHED_IN"


@dataclass
class EnhancedNodeDefinition:
    """增強的節點定義"""

    type: NodeType
    properties: dict[str, type]
    required_properties: list[str]
    description: str
    subcategories: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


class EnhancedArtHistorySchema:
    """增強的藝術史知識圖譜架構"""

    def __init__(self):
        self.nodes = self._define_enhanced_nodes()
        self.relationships = self._define_enhanced_relationships()

    def _define_enhanced_nodes(self) -> dict[NodeType, EnhancedNodeDefinition]:
        """定義增強的節點類型"""
        return {
            # === 藝術家節點 ===
            NodeType.ARTIST: EnhancedNodeDefinition(
                type=NodeType.ARTIST,
                properties={
                    "name": str,
                    "full_name": str,
                    "birth_year": int,
                    "death_year": int,
                    "birth_place": str,
                    "death_place": str,
                    "nationality": str,
                    "gender": str,
                    "biography": str,
                    "education": list[str],
                    "teachers": list[str],
                    "students": list[str],
                    "art_movements": list[str],
                    "periods": list[str],
                    "primary_medium": list[str],
                    "signature_techniques": list[str],
                    "notable_works": list[str],
                    "awards_honors": list[str],
                    "exhibitions": list[str],
                    "collections": list[str],
                    "artistic_evolution": str,
                    "historical_significance": str,
                    "market_value_trend": str,
                    "social_background": str,
                    "family_connections": list[str],
                    "workshop_location": str,
                    "patrons": list[str],
                    "influences": list[str],
                    "legacy": str,
                },
                required_properties=["name"],
                description="藝術家實體，包含完整的個人和藝術信息",
                subcategories=[
                    "Painter",
                    "Sculptor",
                    "Printmaker",
                    "Photographer",
                    "Conceptual Artist",
                ],
                aliases=["Creator", "Painter", "Master"],
            ),
            # === 繪畫作品節點 ===
            NodeType.PAINTING: EnhancedNodeDefinition(
                type=NodeType.PAINTING,
                properties={
                    "title": str,
                    "alternative_titles": list[str],
                    "creation_date": str,
                    "completion_date": str,
                    "artist": str,
                    "dimensions": str,
                    "medium": str,
                    "support": str,  # 畫布、木板等
                    "technique": list[str],
                    "style": str,
                    "genre": str,
                    "subject_matter": list[str],
                    "description": str,
                    "iconography": list[str],
                    "composition": str,
                    "color_palette": list[str],
                    "condition": str,
                    "provenance": list[str],
                    "exhibitions": list[str],
                    "publications": list[str],
                    "current_location": str,
                    "insurance_value": float,
                    "market_value": float,
                    "signature": bool,
                    "inscription": str,
                    "frame": str,
                    "historical_context": str,
                    "cultural_significance": str,
                    "technical_analysis": str,
                    "conservation_history": list[str],
                    "related_works": list[str],
                },
                required_properties=["title", "artist"],
                description="繪畫作品的詳細信息",
                subcategories=["Oil Painting", "Watercolor", "Fresco", "Tempera", "Acrylic"],
                aliases=["Picture", "Canvas", "Work"],
            ),
            # === 博物館節點 ===
            NodeType.MUSEUM: EnhancedNodeDefinition(
                type=NodeType.MUSEUM,
                properties={
                    "name": str,
                    "full_name": str,
                    "location": str,
                    "city": str,
                    "country": str,
                    "founded_year": int,
                    "founder": str,
                    "museum_type": str,
                    "specialization": list[str],
                    "collection_size": int,
                    "permanent_collection": list[str],
                    "notable_works": list[str],
                    "temporary_exhibitions": list[str],
                    "annual_visitors": int,
                    "director": str,
                    "curators": list[str],
                    "building_architect": str,
                    "building_style": str,
                    "website": str,
                    "opening_hours": str,
                    "admission_policy": str,
                    "educational_programs": list[str],
                    "research_facilities": bool,
                    "conservation_lab": bool,
                    "library": bool,
                    "gift_shop": bool,
                    "restaurant": bool,
                    "accessibility": list[str],
                    "partnerships": list[str],
                    "funding_sources": list[str],
                    "mission_statement": str,
                    "acquisition_policy": str,
                    "deaccession_policy": str,
                },
                required_properties=["name", "location"],
                description="博物館機構的完整信息",
                subcategories=[
                    "Art Museum",
                    "History Museum",
                    "Contemporary Art Center",
                    "Private Museum",
                ],
                aliases=["Gallery", "Institution", "Collection"],
            ),
            # === 藝術運動節點 ===
            NodeType.MOVEMENT: EnhancedNodeDefinition(
                type=NodeType.MOVEMENT,
                properties={
                    "name": str,
                    "alternative_names": list[str],
                    "start_period": int,
                    "end_period": int,
                    "peak_period": str,
                    "origin_location": str,
                    "geographic_spread": list[str],
                    "founders": list[str],
                    "key_figures": list[str],
                    "manifesto": str,
                    "core_principles": list[str],
                    "aesthetic_characteristics": list[str],
                    "technical_innovations": list[str],
                    "philosophical_background": str,
                    "social_context": str,
                    "political_context": str,
                    "economic_context": str,
                    "predecessor_movements": list[str],
                    "successor_movements": list[str],
                    "contemporary_movements": list[str],
                    "reaction_against": list[str],
                    "influenced_by": list[str],
                    "major_works": list[str],
                    "exhibitions": list[str],
                    "critical_reception": str,
                    "legacy": str,
                    "scholarly_interpretation": str,
                    "regional_variations": list[str],
                },
                required_properties=["name"],
                description="藝術運動的詳細發展脈絡",
                subcategories=["Avant-garde", "Traditional", "Modern", "Contemporary"],
                aliases=["School", "Style", "Trend"],
            ),
            # === 展覽節點 ===
            NodeType.EXHIBITION: EnhancedNodeDefinition(
                type=NodeType.EXHIBITION,
                properties={
                    "title": str,
                    "subtitle": str,
                    "venue": str,
                    "start_date": str,
                    "end_date": str,
                    "duration": int,
                    "exhibition_type": str,
                    "curator": list[str],
                    "guest_curator": list[str],
                    "organizer": str,
                    "sponsor": list[str],
                    "theme": str,
                    "concept": str,
                    "featured_artists": list[str],
                    "artworks": list[str],
                    "number_of_works": int,
                    "catalog": str,
                    "catalog_authors": list[str],
                    "installation_views": list[str],
                    "visitor_count": int,
                    "reviews": list[str],
                    "press_coverage": list[str],
                    "educational_programs": list[str],
                    "lectures": list[str],
                    "guided_tours": bool,
                    "audio_guide": bool,
                    "multimedia": list[str],
                    "significance": str,
                    "innovations": list[str],
                    "traveling_venues": list[str],
                },
                required_properties=["title", "venue"],
                description="展覽活動的完整記錄",
                subcategories=["Retrospective", "Group Show", "Thematic", "Historical Survey"],
                aliases=["Show", "Display", "Presentation"],
            ),
            # === 技法節點 ===
            NodeType.TECHNIQUE: EnhancedNodeDefinition(
                type=NodeType.TECHNIQUE,
                properties={
                    "name": str,
                    "alternative_names": list[str],
                    "category": str,
                    "description": str,
                    "origin_period": str,
                    "origin_location": str,
                    "inventor": str,
                    "development_history": str,
                    "materials_required": list[str],
                    "tools_required": list[str],
                    "process_steps": list[str],
                    "difficulty_level": str,
                    "time_required": str,
                    "notable_practitioners": list[str],
                    "masterpieces_using": list[str],
                    "variations": list[str],
                    "related_techniques": list[str],
                    "advantages": list[str],
                    "limitations": list[str],
                    "preservation_concerns": list[str],
                    "modern_adaptations": list[str],
                    "teaching_traditions": list[str],
                    "cultural_significance": str,
                },
                required_properties=["name"],
                description="藝術技法的詳細信息",
                subcategories=[
                    "Painting Technique",
                    "Sculpture Technique",
                    "Printmaking",
                    "Drawing",
                ],
                aliases=["Method", "Process", "Approach"],
            ),
        }

    def _define_enhanced_relationships(self) -> list[dict]:
        """定義增強的關係類型"""
        return [
            {
                "type": RelationType.CREATED_BY,
                "description": "作品創作關係",
                "properties": {
                    "creation_year": int,
                    "creation_location": str,
                    "commission_type": str,
                    "collaboration": list[str],
                    "attribution_certainty": float,
                },
            },
            {
                "type": RelationType.INFLUENCED_BY,
                "description": "影響關係",
                "properties": {
                    "influence_type": str,
                    "evidence": str,
                    "period": str,
                    "degree": float,
                    "specific_aspects": list[str],
                },
            },
            {
                "type": RelationType.EXHIBITED_AT,
                "description": "展覽關係",
                "properties": {
                    "exhibition_title": str,
                    "date": str,
                    "venue": str,
                    "role": str,
                    "significance": str,
                },
            },
        ]

    def generate_enhanced_cypher_schema(self) -> list[str]:
        """生成增強的Cypher架構"""
        statements = []

        # 清理現有數據
        statements.append("MATCH (n) DETACH DELETE n")

        # 創建約束
        for node_type, node_def in self.nodes.items():
            statements.append(
                f"CREATE CONSTRAINT {node_type.value.lower()}_name_unique IF NOT EXISTS "
                f"FOR (n:{node_type.value}) REQUIRE n.name IS UNIQUE"
            )

        # 創建索引
        index_properties = [
            "name",
            "title",
            "creation_date",
            "birth_year",
            "death_year",
            "location",
        ]
        for node_type in self.nodes.keys():
            for prop in index_properties:
                statements.append(
                    f"CREATE INDEX {node_type.value.lower()}_{prop}_index IF NOT EXISTS "
                    f"FOR (n:{node_type.value}) ON (n.{prop})"
                )

        return statements

    def export_enhanced_schema(self) -> str:
        """匯出增強架構"""
        schema_data = {
            "metadata": {
                "version": "2.0",
                "description": "Enhanced Art History Knowledge Graph Schema",
                "node_types_count": len(self.nodes),
                "relationship_types_count": len(self.relationships),
            },
            "nodes": {
                node_type.value: {
                    "properties": {
                        prop: str(prop_type.__name__)
                        if hasattr(prop_type, "__name__")
                        else str(prop_type)
                        for prop, prop_type in node_def.properties.items()
                    },
                    "required_properties": node_def.required_properties,
                    "description": node_def.description,
                    "subcategories": node_def.subcategories,
                    "aliases": node_def.aliases,
                }
                for node_type, node_def in self.nodes.items()
            },
            "relationships": [
                {
                    "type": rel["type"].value,
                    "description": rel["description"],
                    "properties": rel.get("properties", {}),
                }
                for rel in self.relationships
            ],
        }

        return json.dumps(schema_data, ensure_ascii=False, indent=2)


# 使用示例
if __name__ == "__main__":
    schema = EnhancedArtHistorySchema()

    print("=== 增強的藝術史知識圖譜架構 ===")
    print(f"節點類型數量: {len(schema.nodes)}")
    print(f"關係類型數量: {len(schema.relationships)}")

    # 輸出主要節點類型
    print("\n=== 主要節點類型 ===")
    categories = {
        "人物相關": ["ARTIST", "CRITIC", "CURATOR", "PATRON", "COLLECTOR"],
        "作品相關": ["PAINTING", "SCULPTURE", "DRAWING", "PRINT", "PHOTOGRAPH"],
        "機構組織": ["MUSEUM", "GALLERY", "ACADEMY", "INSTITUTION"],
        "展覽活動": ["EXHIBITION", "SOLO_SHOW", "GROUP_SHOW", "BIENNIAL"],
        "技術材料": ["TECHNIQUE", "MEDIUM", "PIGMENT", "CANVAS"],
    }

    for category, node_types in categories.items():
        print(f"\n{category}:")
        for node_type in node_types:
            if hasattr(NodeType, node_type):
                node_enum = getattr(NodeType, node_type)
                if node_enum in schema.nodes:
                    print(f"  - {node_enum.value}: {schema.nodes[node_enum].description}")
