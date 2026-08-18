#!/usr/bin/env python3
"""
12大分類藝術史GraphRAG系統
基於用戶要求的分類方法重新設計知識圖譜架構
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ArtHistory12Categories(Enum):
    """12大藝術史分類"""

    # 1. 人物（Artists/Authors）
    PEOPLE = "People"

    # 2. 作品（Artworks/Objects）
    ARTWORKS = "Artworks"

    # 3. 流派/運動（Styles/Movements）
    MOVEMENTS = "Movements"

    # 4. 技法與材質（Techniques/Materials）
    TECHNIQUES = "Techniques"

    # 5. 主題與圖像學（Iconography/Themes）
    THEMES = "Themes"

    # 6. 時間（Periods/Chronology）
    CHRONOLOGY = "Chronology"

    # 7. 地點（Places）
    PLACES = "Places"

    # 8. 機構（Institutions）
    INSTITUTIONS = "Institutions"

    # 9. 事件（Events）
    EVENTS = "Events"

    # 10. 文獻（Sources/Texts）
    SOURCES = "Sources"

    # 11. 概念與術語（Concepts/Terms）
    CONCEPTS = "Concepts"

    # 12. 版本/語言（Translations & Terms Mapping）
    TRANSLATIONS = "Translations"


class DetailedNodeTypes(Enum):
    """詳細節點類型 - 基於12大分類"""

    # 1. 人物類別
    ARTIST = "Artist"  # 藝術家
    THEORIST = "Theorist"  # 理論家
    PATRON = "Patron"  # 贊助人
    COLLECTOR = "Collector"  # 收藏家
    WORKSHOP_MASTER = "WorkshopMaster"  # 工坊主持
    CRITIC = "Critic"  # 評論家
    CURATOR = "Curator"  # 策展人
    DEALER = "Dealer"  # 藝術商

    # 2. 作品類別
    PAINTING = "Painting"  # 繪畫
    SCULPTURE = "Sculpture"  # 雕塑
    ARCHITECTURE = "Architecture"  # 建築專案
    MANUSCRIPT = "Manuscript"  # 手稿
    PRINT = "Print"  # 版畫
    DRAWING = "Drawing"  # 素描
    DECORATIVE_ART = "DecorativeArt"  # 裝飾藝術

    # 3. 流派/運動類別
    EARLY_RENAISSANCE = "EarlyRenaissance"  # 早期文藝復興
    HIGH_RENAISSANCE = "HighRenaissance"  # 盛期文藝復興
    LATE_RENAISSANCE = "LateRenaissance"  # 晚期文藝復興
    MANNERISM = "Mannerism"  # 曼納主義
    BAROQUE = "Baroque"  # 巴洛克
    NEOCLASSICISM = "Neoclassicism"  # 新古典主義

    # 4. 技法與材質類別
    OIL_PAINTING = "OilPainting"  # 油彩
    TEMPERA = "Tempera"  # 蛋彩
    FRESCO = "Fresco"  # 壁畫
    WET_FRESCO = "WetFresco"  # 濕壁畫
    MARBLE_CARVING = "MarbleCarving"  # 大理石雕刻
    BRONZE_CASTING = "BronzeCasting"  # 青銅鑄造

    # 5. 主題與圖像學類別
    RELIGIOUS_MOTIF = "ReligiousMotif"  # 宗教母題
    MYTHOLOGY = "Mythology"  # 神話
    PORTRAIT = "Portrait"  # 肖像
    ALLEGORY = "Allegory"  # 寓意
    LANDSCAPE = "Landscape"  # 風景
    STILL_LIFE = "StillLife"  # 靜物

    # 6. 時間類別
    CENTURY = "Century"  # 世紀
    EPOCH = "Epoch"  # 紀元
    DYNASTY = "Dynasty"  # 朝代
    MEDICI_PERIOD = "MediciPeriod"  # 美第奇統治期
    PAPAL_PERIOD = "PapalPeriod"  # 教皇時期

    # 7. 地點類別
    CITY = "City"  # 城市
    REGION = "Region"  # 區域
    CHURCH = "Church"  # 教堂
    PALACE = "Palace"  # 宮殿
    MUSEUM = "Museum"  # 博物館（當代收藏地）
    ARCHAEOLOGICAL_SITE = "ArchaeologicalSite"  # 考古遺址

    # 8. 機構類別
    GUILD = "Guild"  # 行會
    PATRONAGE_FAMILY = "PatronageFamily"  # 贊助家族
    ACADEMY = "Academy"  # 學院
    COLLECTION_INSTITUTION = "CollectionInstitution"  # 收藏機構
    WORKSHOP = "Workshop"  # 工坊

    # 9. 事件類別
    COMMISSION = "Commission"  # 委託
    EXHIBITION = "Exhibition"  # 展覽
    RELOCATION = "Relocation"  # 遷藏
    RESTORATION = "Restoration"  # 修復
    PUBLICATION = "Publication"  # 出版
    CONTROVERSY = "Controversy"  # 爭議
    DISCOVERY = "Discovery"  # 發現

    # 10. 文獻類別
    VASARI_LIVES = "VasariLives"  # Vasari《藝苑名人傳》
    PRIMARY_SOURCE = "PrimarySource"  # 原典
    CATALOG_RAISONNE = "CatalogueRaisonne"  # 作品全集目錄
    RESEARCH_PAPER = "ResearchPaper"  # 研究論文
    EXHIBITION_CATALOG = "ExhibitionCatalog"  # 策展文

    # 11. 概念與術語類別
    PERSPECTIVE = "Perspective"  # 透視
    SFUMATO = "Sfumato"  # sfumato（暈塗法）
    CONTRAPPOSTO = "Contrapposto"  # contrapposto（對位法）
    CHIAROSCURO = "Chiaroscuro"  # chiaroscuro（明暗法）
    DISEGNO = "Disegno"  # disegno（素描/設計）
    COLORITO = "Colorito"  # colorito（色彩）

    # 12. 版本/語言類別
    ITALIAN_TERM = "ItalianTerm"  # 義大利語術語
    ENGLISH_TERM = "EnglishTerm"  # 英語術語
    CHINESE_TERM = "ChineseTerm"  # 中文術語
    ALTERNATIVE_NAME = "AlternativeName"  # 別名
    SYNONYM = "Synonym"  # 同義詞


class GraphRAGRelationTypes(Enum):
    """GraphRAG關係類型"""

    # 創作關係
    CREATED_BY = "CREATED_BY"
    DESIGNED_BY = "DESIGNED_BY"
    ATTRIBUTED_TO = "ATTRIBUTED_TO"

    # 影響關係
    INFLUENCED_BY = "INFLUENCED_BY"
    INSPIRED_BY = "INSPIRED_BY"
    TAUGHT_BY = "TAUGHT_BY"
    STUDIED_UNDER = "STUDIED_UNDER"

    # 歸屬關係
    BELONGS_TO_MOVEMENT = "BELONGS_TO_MOVEMENT"
    MEMBER_OF = "MEMBER_OF"
    PART_OF_COLLECTION = "PART_OF_COLLECTION"

    # 地理時間關係
    LOCATED_IN = "LOCATED_IN"
    BORN_IN = "BORN_IN"
    WORKED_IN = "WORKED_IN"
    ACTIVE_DURING = "ACTIVE_DURING"
    CREATED_DURING = "CREATED_DURING"

    # 技法材質關係
    USES_TECHNIQUE = "USES_TECHNIQUE"
    MADE_WITH = "MADE_WITH"
    EXECUTED_IN = "EXECUTED_IN"

    # 主題內容關係
    DEPICTS = "DEPICTS"
    REPRESENTS = "REPRESENTS"
    CONTAINS_MOTIF = "CONTAINS_MOTIF"
    SYMBOLIZES = "SYMBOLIZES"

    # 收藏展示關係
    HOUSED_IN = "HOUSED_IN"
    EXHIBITED_AT = "EXHIBITED_AT"
    COMMISSIONED_BY = "COMMISSIONED_BY"
    OWNED_BY = "OWNED_BY"

    # 文獻記錄關係
    DOCUMENTED_IN = "DOCUMENTED_IN"
    DESCRIBED_IN = "DESCRIBED_IN"
    MENTIONED_IN = "MENTIONED_IN"
    CATALOGUED_IN = "CATALOGUED_IN"

    # 語言對照關係
    TRANSLATED_AS = "TRANSLATED_AS"
    ALSO_KNOWN_AS = "ALSO_KNOWN_AS"
    EQUIVALENT_TO = "EQUIVALENT_TO"
    VARIANT_OF = "VARIANT_OF"


@dataclass
class GraphRAGNode:
    """GraphRAG節點定義"""

    node_id: str
    category: ArtHistory12Categories
    node_type: DetailedNodeTypes
    properties: dict[str, Any]
    metadata: dict[str, Any] = None


@dataclass
class GraphRAGRelation:
    """GraphRAG關係定義"""

    from_node: str
    to_node: str
    relation_type: GraphRAGRelationTypes
    properties: dict[str, Any] = None
    confidence: float = 1.0


class GraphRAGQueryRouter:
    """GraphRAG查詢路由器 - 實現12大分類查詢路由"""

    def __init__(self):
        self.category_mappings = self._build_category_mappings()
        self.query_patterns = self._define_query_patterns()

    def _build_category_mappings(self) -> dict[ArtHistory12Categories, list[DetailedNodeTypes]]:
        """構建分類到節點類型的映射"""
        return {
            ArtHistory12Categories.PEOPLE: [
                DetailedNodeTypes.ARTIST,
                DetailedNodeTypes.THEORIST,
                DetailedNodeTypes.PATRON,
                DetailedNodeTypes.COLLECTOR,
                DetailedNodeTypes.WORKSHOP_MASTER,
                DetailedNodeTypes.CRITIC,
            ],
            ArtHistory12Categories.ARTWORKS: [
                DetailedNodeTypes.PAINTING,
                DetailedNodeTypes.SCULPTURE,
                DetailedNodeTypes.ARCHITECTURE,
                DetailedNodeTypes.MANUSCRIPT,
                DetailedNodeTypes.PRINT,
                DetailedNodeTypes.DRAWING,
            ],
            ArtHistory12Categories.MOVEMENTS: [
                DetailedNodeTypes.EARLY_RENAISSANCE,
                DetailedNodeTypes.HIGH_RENAISSANCE,
                DetailedNodeTypes.LATE_RENAISSANCE,
                DetailedNodeTypes.MANNERISM,
                DetailedNodeTypes.BAROQUE,
                DetailedNodeTypes.NEOCLASSICISM,
            ],
            ArtHistory12Categories.TECHNIQUES: [
                DetailedNodeTypes.OIL_PAINTING,
                DetailedNodeTypes.TEMPERA,
                DetailedNodeTypes.FRESCO,
                DetailedNodeTypes.WET_FRESCO,
                DetailedNodeTypes.MARBLE_CARVING,
                DetailedNodeTypes.BRONZE_CASTING,
            ],
            ArtHistory12Categories.THEMES: [
                DetailedNodeTypes.RELIGIOUS_MOTIF,
                DetailedNodeTypes.MYTHOLOGY,
                DetailedNodeTypes.PORTRAIT,
                DetailedNodeTypes.ALLEGORY,
                DetailedNodeTypes.LANDSCAPE,
                DetailedNodeTypes.STILL_LIFE,
            ],
            ArtHistory12Categories.CHRONOLOGY: [
                DetailedNodeTypes.CENTURY,
                DetailedNodeTypes.EPOCH,
                DetailedNodeTypes.DYNASTY,
                DetailedNodeTypes.MEDICI_PERIOD,
                DetailedNodeTypes.PAPAL_PERIOD,
            ],
            ArtHistory12Categories.PLACES: [
                DetailedNodeTypes.CITY,
                DetailedNodeTypes.REGION,
                DetailedNodeTypes.CHURCH,
                DetailedNodeTypes.PALACE,
                DetailedNodeTypes.MUSEUM,
                DetailedNodeTypes.ARCHAEOLOGICAL_SITE,
            ],
            ArtHistory12Categories.INSTITUTIONS: [
                DetailedNodeTypes.GUILD,
                DetailedNodeTypes.PATRONAGE_FAMILY,
                DetailedNodeTypes.ACADEMY,
                DetailedNodeTypes.COLLECTION_INSTITUTION,
                DetailedNodeTypes.WORKSHOP,
            ],
            ArtHistory12Categories.EVENTS: [
                DetailedNodeTypes.COMMISSION,
                DetailedNodeTypes.EXHIBITION,
                DetailedNodeTypes.RELOCATION,
                DetailedNodeTypes.RESTORATION,
                DetailedNodeTypes.PUBLICATION,
                DetailedNodeTypes.CONTROVERSY,
            ],
            ArtHistory12Categories.SOURCES: [
                DetailedNodeTypes.VASARI_LIVES,
                DetailedNodeTypes.PRIMARY_SOURCE,
                DetailedNodeTypes.CATALOG_RAISONNE,
                DetailedNodeTypes.RESEARCH_PAPER,
                DetailedNodeTypes.EXHIBITION_CATALOG,
            ],
            ArtHistory12Categories.CONCEPTS: [
                DetailedNodeTypes.PERSPECTIVE,
                DetailedNodeTypes.SFUMATO,
                DetailedNodeTypes.CONTRAPPOSTO,
                DetailedNodeTypes.CHIAROSCURO,
                DetailedNodeTypes.DISEGNO,
                DetailedNodeTypes.COLORITO,
            ],
            ArtHistory12Categories.TRANSLATIONS: [
                DetailedNodeTypes.ITALIAN_TERM,
                DetailedNodeTypes.ENGLISH_TERM,
                DetailedNodeTypes.CHINESE_TERM,
                DetailedNodeTypes.ALTERNATIVE_NAME,
                DetailedNodeTypes.SYNONYM,
            ],
        }

    def _define_query_patterns(self) -> dict[str, dict]:
        """定義查詢模式"""
        return {
            # 人物查詢模式
            "artist_works": {
                "entry_categories": [ArtHistory12Categories.PEOPLE],
                "target_categories": [ArtHistory12Categories.ARTWORKS],
                "key_relations": [GraphRAGRelationTypes.CREATED_BY],
                "expansion_depth": 2,
                "priority_nodes": [DetailedNodeTypes.ARTIST, DetailedNodeTypes.PAINTING],
            },
            # 作品分析模式
            "artwork_analysis": {
                "entry_categories": [ArtHistory12Categories.ARTWORKS],
                "target_categories": [
                    ArtHistory12Categories.PEOPLE,
                    ArtHistory12Categories.TECHNIQUES,
                    ArtHistory12Categories.THEMES,
                    ArtHistory12Categories.PLACES,
                ],
                "key_relations": [
                    GraphRAGRelationTypes.CREATED_BY,
                    GraphRAGRelationTypes.USES_TECHNIQUE,
                    GraphRAGRelationTypes.DEPICTS,
                    GraphRAGRelationTypes.HOUSED_IN,
                ],
                "expansion_depth": 3,
                "priority_nodes": [DetailedNodeTypes.PAINTING, DetailedNodeTypes.ARTIST],
            },
            # 流派運動模式
            "movement_exploration": {
                "entry_categories": [ArtHistory12Categories.MOVEMENTS],
                "target_categories": [
                    ArtHistory12Categories.PEOPLE,
                    ArtHistory12Categories.ARTWORKS,
                    ArtHistory12Categories.CHRONOLOGY,
                    ArtHistory12Categories.PLACES,
                ],
                "key_relations": [
                    GraphRAGRelationTypes.BELONGS_TO_MOVEMENT,
                    GraphRAGRelationTypes.ACTIVE_DURING,
                    GraphRAGRelationTypes.LOCATED_IN,
                ],
                "expansion_depth": 3,
                "priority_nodes": [DetailedNodeTypes.HIGH_RENAISSANCE, DetailedNodeTypes.ARTIST],
            },
            # 技法研究模式
            "technique_study": {
                "entry_categories": [ArtHistory12Categories.TECHNIQUES],
                "target_categories": [
                    ArtHistory12Categories.PEOPLE,
                    ArtHistory12Categories.ARTWORKS,
                    ArtHistory12Categories.CONCEPTS,
                ],
                "key_relations": [
                    GraphRAGRelationTypes.USES_TECHNIQUE,
                    GraphRAGRelationTypes.CREATED_BY,
                ],
                "expansion_depth": 2,
                "priority_nodes": [DetailedNodeTypes.OIL_PAINTING, DetailedNodeTypes.SFUMATO],
            },
            # 地理文化模式
            "geographic_cultural": {
                "entry_categories": [ArtHistory12Categories.PLACES],
                "target_categories": [
                    ArtHistory12Categories.PEOPLE,
                    ArtHistory12Categories.ARTWORKS,
                    ArtHistory12Categories.INSTITUTIONS,
                    ArtHistory12Categories.MOVEMENTS,
                ],
                "key_relations": [
                    GraphRAGRelationTypes.LOCATED_IN,
                    GraphRAGRelationTypes.BORN_IN,
                    GraphRAGRelationTypes.WORKED_IN,
                    GraphRAGRelationTypes.HOUSED_IN,
                ],
                "expansion_depth": 3,
                "priority_nodes": [DetailedNodeTypes.CITY, DetailedNodeTypes.MUSEUM],
            },
            # 時間脈絡模式
            "temporal_context": {
                "entry_categories": [ArtHistory12Categories.CHRONOLOGY],
                "target_categories": [
                    ArtHistory12Categories.PEOPLE,
                    ArtHistory12Categories.ARTWORKS,
                    ArtHistory12Categories.MOVEMENTS,
                    ArtHistory12Categories.EVENTS,
                ],
                "key_relations": [
                    GraphRAGRelationTypes.ACTIVE_DURING,
                    GraphRAGRelationTypes.CREATED_DURING,
                ],
                "expansion_depth": 2,
                "priority_nodes": [DetailedNodeTypes.CENTURY, DetailedNodeTypes.MEDICI_PERIOD],
            },
            # 術語對照模式
            "terminology_mapping": {
                "entry_categories": [ArtHistory12Categories.TRANSLATIONS],
                "target_categories": [
                    ArtHistory12Categories.CONCEPTS,
                    ArtHistory12Categories.TECHNIQUES,
                ],
                "key_relations": [
                    GraphRAGRelationTypes.TRANSLATED_AS,
                    GraphRAGRelationTypes.EQUIVALENT_TO,
                    GraphRAGRelationTypes.ALSO_KNOWN_AS,
                ],
                "expansion_depth": 1,
                "priority_nodes": [DetailedNodeTypes.ITALIAN_TERM, DetailedNodeTypes.CHINESE_TERM],
            },
        }

    def analyze_query_intent(self, query: str) -> dict[str, Any]:
        """分析查詢意圖並確定路由策略"""
        query_lower = query.lower()

        # 關鍵詞檢測
        category_keywords = {
            ArtHistory12Categories.PEOPLE: [
                "藝術家",
                "達文西",
                "米開朗基羅",
                "拉斐爾",
                "artist",
                "leonardo",
                "michelangelo",
            ],
            ArtHistory12Categories.ARTWORKS: [
                "作品",
                "繪畫",
                "雕塑",
                "蒙娜麗莎",
                "painting",
                "sculpture",
                "mona lisa",
            ],
            ArtHistory12Categories.MOVEMENTS: [
                "文藝復興",
                "巴洛克",
                "renaissance",
                "baroque",
                "mannerism",
            ],
            ArtHistory12Categories.TECHNIQUES: [
                "油彩",
                "濕壁畫",
                "技法",
                "oil painting",
                "fresco",
                "technique",
            ],
            ArtHistory12Categories.THEMES: [
                "主題",
                "宗教",
                "神話",
                "肖像",
                "theme",
                "religious",
                "portrait",
            ],
            ArtHistory12Categories.CHRONOLOGY: [
                "時期",
                "世紀",
                "美第奇",
                "period",
                "century",
                "medici",
            ],
            ArtHistory12Categories.PLACES: [
                "佛羅倫斯",
                "羅馬",
                "博物館",
                "florence",
                "rome",
                "museum",
            ],
            ArtHistory12Categories.INSTITUTIONS: [
                "學院",
                "工坊",
                "行會",
                "academy",
                "workshop",
                "guild",
            ],
            ArtHistory12Categories.EVENTS: [
                "委託",
                "展覽",
                "修復",
                "commission",
                "exhibition",
                "restoration",
            ],
            ArtHistory12Categories.SOURCES: [
                "文獻",
                "瓦薩里",
                "研究",
                "vasari",
                "source",
                "research",
            ],
            ArtHistory12Categories.CONCEPTS: [
                "透視",
                "暈塗法",
                "perspective",
                "sfumato",
                "chiaroscuro",
            ],
            ArtHistory12Categories.TRANSLATIONS: [
                "義大利語",
                "英文",
                "中文",
                "翻譯",
                "italian",
                "translation",
            ],
        }

        detected_categories = []
        for category, keywords in category_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                detected_categories.append(category)

        # 查詢意圖分析
        intent_patterns = {
            "creation": ["創作", "製作", "設計", "created", "made", "designed"],
            "influence": ["影響", "啟發", "師從", "influenced", "inspired", "taught"],
            "collection": ["收藏", "展示", "博物館", "collection", "museum", "housed"],
            "technique": ["技法", "材質", "方法", "technique", "material", "method"],
            "comparison": ["比較", "對比", "差異", "compare", "versus", "difference"],
            "chronology": ["時間", "年代", "歷史", "time", "period", "history"],
            "location": ["地點", "位置", "城市", "location", "place", "city"],
            "relationship": ["關係", "連結", "相關", "relationship", "connection", "related"],
        }

        detected_intents = []
        for intent, patterns in intent_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                detected_intents.append(intent)

        # 選擇最適合的查詢模式
        if not detected_categories:
            query_pattern = "artwork_analysis"  # 默認模式
        elif ArtHistory12Categories.PEOPLE in detected_categories:
            if "creation" in detected_intents:
                query_pattern = "artist_works"
            else:
                query_pattern = "movement_exploration"
        elif ArtHistory12Categories.ARTWORKS in detected_categories:
            query_pattern = "artwork_analysis"
        elif ArtHistory12Categories.MOVEMENTS in detected_categories:
            query_pattern = "movement_exploration"
        elif ArtHistory12Categories.TECHNIQUES in detected_categories:
            query_pattern = "technique_study"
        elif ArtHistory12Categories.PLACES in detected_categories:
            query_pattern = "geographic_cultural"
        elif ArtHistory12Categories.CHRONOLOGY in detected_categories:
            query_pattern = "temporal_context"
        elif ArtHistory12Categories.TRANSLATIONS in detected_categories:
            query_pattern = "terminology_mapping"
        else:
            query_pattern = "artwork_analysis"  # 默認模式

        return {
            "detected_categories": detected_categories,
            "detected_intents": detected_intents,
            "selected_pattern": query_pattern,
            "query_config": self.query_patterns[query_pattern],
            "confidence": len(detected_categories) / len(category_keywords)
            if detected_categories
            else 0.1,
        }

    def generate_cypher_query(self, query_analysis: dict[str, Any], limit: int = 50) -> str:
        """基於查詢分析生成Cypher查詢"""
        pattern = query_analysis["selected_pattern"]

        # 注意：query_analysis["query_config"] 的 entry_categories / target_categories
        # 目前未被使用——
        # 下方各 pattern 的 Cypher 是硬編碼的節點標籤。若要讓查詢真正跟隨 12 分類
        # 設定，需以這兩個欄位動態組標籤（標籤值來自程式內固定分類表，非使用者輸入）。

        if pattern == "artist_works":
            cypher = f"""
            MATCH (artist:Artist)-[r:CREATED_BY]-(artwork:Painting|Sculpture|Drawing)
            OPTIONAL MATCH (artwork)-[:USES_TECHNIQUE]->(technique)
            OPTIONAL MATCH (artwork)-[:HOUSED_IN]->(museum:Museum)
            RETURN artist.name as artist_name,
                   artwork.title as artwork_title,
                   artwork.creation_date as date,
                   technique.name as technique_name,
                   museum.name as current_location
            LIMIT {limit}
            """

        elif pattern == "artwork_analysis":
            cypher = f"""
            MATCH (artwork:Painting|Sculpture)-[r1:CREATED_BY]->(artist:Artist)
            OPTIONAL MATCH (artwork)-[r2:USES_TECHNIQUE]->(technique)
            OPTIONAL MATCH (artwork)-[r3:DEPICTS]->(theme)
            OPTIONAL MATCH (artwork)-[r4:HOUSED_IN]->(location:Museum|Palace|Church)
            RETURN artwork.title as title,
                   artist.name as artist,
                   technique.name as technique,
                   theme.name as theme,
                   location.name as location,
                   artwork.creation_date as date
            LIMIT {limit}
            """

        elif pattern == "movement_exploration":
            cypher = f"""
            MATCH (movement:HighRenaissance|EarlyRenaissance|Baroque|Mannerism)
            OPTIONAL MATCH (artist:Artist)-[:BELONGS_TO_MOVEMENT]->(movement)
            OPTIONAL MATCH (artist)-[:CREATED_BY]-(artwork)
            OPTIONAL MATCH (movement)-[:ACTIVE_DURING]->(period)
            RETURN movement.name as movement_name,
                   artist.name as artist_name,
                   artwork.title as artwork_title,
                   period.name as time_period
            LIMIT {limit}
            """

        elif pattern == "technique_study":
            cypher = f"""
            MATCH (technique:OilPainting|Fresco|Tempera|MarbleCarving)
            OPTIONAL MATCH (artwork)-[:USES_TECHNIQUE]->(technique)
            OPTIONAL MATCH (artwork)-[:CREATED_BY]->(artist:Artist)
            OPTIONAL MATCH (technique)-[:RELATED_TO]->(concept)
            RETURN technique.name as technique_name,
                   technique.description as description,
                   artwork.title as example_work,
                   artist.name as practitioner,
                   concept.name as related_concept
            LIMIT {limit}
            """

        elif pattern == "geographic_cultural":
            cypher = f"""
            MATCH (place:City|Region|Museum|Palace|Church)
            OPTIONAL MATCH (artist:Artist)-[:BORN_IN|WORKED_IN]->(place)
            OPTIONAL MATCH (artwork)-[:HOUSED_IN|CREATED_IN]->(place)
            OPTIONAL MATCH (institution:Guild|Academy)-[:LOCATED_IN]->(place)
            RETURN place.name as location_name,
                   artist.name as artist_name,
                   artwork.title as artwork_title,
                   institution.name as institution_name
            LIMIT {limit}
            """

        elif pattern == "temporal_context":
            cypher = f"""
            MATCH (period:Century|MediciPeriod|PapalPeriod|Dynasty)
            OPTIONAL MATCH (artist:Artist)-[:ACTIVE_DURING]->(period)
            OPTIONAL MATCH (artwork)-[:CREATED_DURING]->(period)
            OPTIONAL MATCH (event:Commission|Exhibition)-[:OCCURRED_DURING]->(period)
            RETURN period.name as period_name,
                   period.start_year as start_year,
                   period.end_year as end_year,
                   artist.name as active_artist,
                   artwork.title as created_work,
                   event.description as historical_event
            LIMIT {limit}
            """

        elif pattern == "terminology_mapping":
            cypher = f"""
            MATCH (italian:ItalianTerm)-[:TRANSLATED_AS]->(chinese:ChineseTerm)
            OPTIONAL MATCH (italian)-[:EQUIVALENT_TO]->(english:EnglishTerm)
            OPTIONAL MATCH (italian)-[:REFERS_TO]->(concept)
            RETURN italian.term as italian_term,
                   chinese.term as chinese_term,
                   english.term as english_term,
                   concept.name as concept_name,
                   concept.description as explanation
            LIMIT {limit}
            """

        else:
            # 默認通用查詢
            cypher = f"""
            MATCH (n)-[r]->(m)
            WHERE n.name IS NOT NULL AND m.name IS NOT NULL
            RETURN labels(n)[0] as from_type, n.name as from_name,
                   type(r) as relationship,
                   labels(m)[0] as to_type, m.name as to_name
            LIMIT {limit}
            """

        return cypher.strip()


class ArtHistory12CategorySchema:
    """12大分類藝術史知識圖譜架構"""

    def __init__(self):
        self.categories = ArtHistory12Categories
        self.node_types = DetailedNodeTypes
        self.relation_types = GraphRAGRelationTypes
        self.query_router = GraphRAGQueryRouter()

    def get_category_description(self) -> dict[str, str]:
        """獲取12大分類的詳細描述"""
        return {
            "人物": "藝術家、理論家、贊助人、收藏家、工坊主持等藝術史重要人物",
            "作品": "繪畫、雕塑、建築專案、手稿、版畫等各類藝術創作",
            "流派運動": "早/盛/晚期文藝復興、曼納主義、巴洛克等藝術流派和運動",
            "技法材質": "油彩、蛋彩、壁畫、濕壁畫、大理石雕刻等技術與材料",
            "主題圖像": "宗教母題、神話、肖像、寓意等藝術主題和圖像學分類",
            "時間": "年代、紀元、朝代對照（如美第奇統治期）等時間脈絡",
            "地點": "城市、區域、教堂/宮殿/博物館（含當代收藏地）等空間概念",
            "機構": "行會、贊助家族、學院、收藏機構等組織實體",
            "事件": "委託、展覽、遷藏、修復、出版、爭議等歷史事件",
            "文獻": "原典（Vasari等）、目錄、研究論文、策展文等文獻資料",
            "概念術語": "透視、sfumato、contrapposto等藝術史專業概念",
            "語言對照": "義/英/中對譯、別名、同義詞等多語言對應關係",
        }

    def generate_schema_cypher(self) -> list[str]:
        """生成12大分類的Cypher架構腳本"""
        cypher_statements = []

        # 清理數據庫
        cypher_statements.append("MATCH (n) DETACH DELETE n")

        # 創建類別索引節點
        for category in ArtHistory12Categories:
            cypher_statements.append(f"""
            CREATE (:Category {{
                name: '{category.value}',
                description: '{self.get_category_description().get(category.value, "")}',
                is_entry_point: true
            }})
            """)

        # 創建約束和索引
        for node_type in DetailedNodeTypes:
            # 唯一約束
            cypher_statements.append(f"""
            CREATE CONSTRAINT {node_type.value.lower()}_name_unique IF NOT EXISTS
            FOR (n:{node_type.value}) REQUIRE n.name IS UNIQUE
            """)

            # 索引
            cypher_statements.append(f"""
            CREATE INDEX {node_type.value.lower()}_name_index IF NOT EXISTS
            FOR (n:{node_type.value}) ON (n.name)
            """)

        # 創建關係類型索引
        cypher_statements.append("""
        CREATE INDEX relationship_type_index IF NOT EXISTS
        FOR ()-[r]-() ON (type(r))
        """)

        return cypher_statements

    def create_sample_data(self) -> list[str]:
        """創建12大分類的示例數據"""
        sample_data = []

        # 1. 人物數據
        sample_data.extend(
            [
                """CREATE (:Artist {
                name: 'Leonardo da Vinci',
                full_name: 'Leonardo di ser Piero da Vinci',
                birth_year: 1452,
                death_year: 1519,
                nationality: 'Italian',
                birth_place: 'Vinci, Republic of Florence',
                periods: ['Early Renaissance', 'High Renaissance'],
                signature_techniques: ['sfumato', 'chiaroscuro'],
                category: 'People'
            })""",
                """CREATE (:Patron {
                name: 'Lorenzo de Medici',
                title: 'Lorenzo the Magnificent',
                family: 'Medici',
                period: 'Early Renaissance',
                patronage_focus: ['Arts', 'Literature', 'Philosophy'],
                category: 'People'
            })""",
                """CREATE (:Collector {
                name: 'Isabella d Este',
                title: 'Marchesa of Mantua',
                collection_focus: ['Renaissance art', 'Classical antiquities'],
                notable_acquisitions: ['Mantegna works', 'Leonardo drawings'],
                category: 'People'
            })""",
            ]
        )

        # 2. 作品數據
        sample_data.extend(
            [
                """CREATE (:Painting {
                title: 'Mona Lisa',
                alternative_titles: ['La Gioconda', 'Portrait of Lisa Gherardini'],
                creation_date: '1503-1519',
                dimensions: '77 cm × 53 cm',
                medium: 'Oil on poplar panel',
                technique: ['sfumato'],
                current_location: 'Louvre Museum',
                category: 'Artworks'
            })""",
                """CREATE (:Sculpture {
                title: 'David',
                creation_date: '1501-1504',
                dimensions: '517 cm height',
                material: 'Carrara marble',
                technique: ['contrapposto'],
                current_location: 'Galleria dell Accademia, Florence',
                category: 'Artworks'
            })""",
            ]
        )

        # 3. 流派/運動數據
        sample_data.extend(
            [
                """CREATE (:HighRenaissance {
                name: 'High Renaissance',
                start_period: 1495,
                end_period: 1520,
                origin_location: 'Rome, Florence',
                key_characteristics: ['perfect balance', 'idealized beauty',
                    'mathematical precision'],
                major_figures: ['Leonardo', 'Michelangelo', 'Raphael'],
                category: 'Movements'
            })""",
                """CREATE (:Mannerism {
                name: 'Mannerism',
                start_period: 1520,
                end_period: 1600,
                characteristics: ['elongated proportions', 'complex poses', 'artificial colors'],
                category: 'Movements'
            })""",
            ]
        )

        # 4. 技法與材質數據
        sample_data.extend(
            [
                """CREATE (:Sfumato {
                name: 'Sfumato',
                description: 'Subtle gradation of tones without lines or borders',
                inventor: 'Leonardo da Vinci',
                origin_period: 'High Renaissance',
                visual_characteristics: ['soft transitions', 'atmospheric effects'],
                category: 'Techniques'
            })""",
                """CREATE (:OilPainting {
                name: 'Oil Painting',
                description: 'Painting technique using pigments suspended in oil',
                materials_required: ['oil binder', 'pigments', 'canvas or panel'],
                advantages: ['slow drying', 'blendability', 'rich colors'],
                category: 'Techniques'
            })""",
            ]
        )

        # 5. 主題與圖像學數據
        sample_data.extend(
            [
                """CREATE (:ReligiousMotif {
                name: 'Annunciation',
                description: 'Angel Gabriel announcing to Mary',
                religious_tradition: 'Christianity',
                symbolic_elements: ['lily', 'dove', 'book'],
                category: 'Themes'
            })""",
                """CREATE (:Portrait {
                name: 'Portrait painting',
                description: 'Artistic representation of a person',
                subcategories: ['individual portrait', 'group portrait', 'self-portrait'],
                category: 'Themes'
            })""",
            ]
        )

        # 6. 時間數據
        sample_data.extend(
            [
                """CREATE (:MediciPeriod {
                name: 'Medici Rule in Florence',
                start_year: 1434,
                end_year: 1737,
                key_periods: ['Cosimo the Elder', 'Lorenzo the Magnificent', 'Grand Duchy'],
                cultural_impact: 'Renaissance patronage',
                category: 'Chronology'
            })""",
                """CREATE (:Century {
                name: '16th Century',
                start_year: 1501,
                end_year: 1600,
                major_events: ['High Renaissance', 'Mannerism', 'Counter-Reformation'],
                category: 'Chronology'
            })""",
            ]
        )

        # 7. 地點數據
        sample_data.extend(
            [
                """CREATE (:City {
                name: 'Florence',
                country: 'Italy',
                region: 'Tuscany',
                cultural_significance: 'Birthplace of Renaissance',
                notable_sites: ['Uffizi Gallery', 'Palazzo Pitti', 'Duomo'],
                category: 'Places'
            })""",
                """CREATE (:Museum {
                name: 'Louvre Museum',
                location: 'Paris, France',
                founded_year: 1793,
                specialization: ['European painting', 'Ancient civilizations'],
                notable_collections: ['Mona Lisa', 'Venus de Milo'],
                category: 'Places'
            })""",
            ]
        )

        # 8. 機構數據
        sample_data.extend(
            [
                """CREATE (:PatronageFamily {
                name: 'Medici Family',
                location: 'Florence',
                patronage_period: '1434-1737',
                supported_artists: ['Michelangelo', 'Botticelli', 'Donatello'],
                category: 'Institutions'
            })""",
                """CREATE (:Workshop {
                name: 'Verrocchio Workshop',
                master: 'Andrea del Verrocchio',
                location: 'Florence',
                notable_apprentices: ['Leonardo da Vinci', 'Lorenzo di Credi'],
                category: 'Institutions'
            })""",
            ]
        )

        # 9. 事件數據
        sample_data.extend(
            [
                """CREATE (:Commission {
                title: 'Sistine Chapel Ceiling Commission',
                commissioner: 'Pope Julius II',
                artist: 'Michelangelo',
                date: '1508-1512',
                significance: 'Masterpiece of High Renaissance',
                category: 'Events'
            })""",
                """CREATE (:Restoration {
                title: 'Sistine Chapel Restoration',
                period: '1980-1994',
                significance: 'Revealed original colors',
                controversy: 'Cleaning methods debate',
                category: 'Events'
            })""",
            ]
        )

        # 10. 文獻數據
        sample_data.extend(
            [
                """CREATE (:VasariLives {
                title: 'Lives of the Most Excellent Painters, Sculptors, and Architects',
                author: 'Giorgio Vasari',
                publication_date: '1550, 1568',
                significance: 'First art history book',
                language: 'Italian',
                category: 'Sources'
            })""",
                """CREATE (:ResearchPaper {
                title: 'Leonardo da Vinci Sfumato Technique Analysis',
                author: 'Modern Art Historian',
                publication_year: 2020,
                focus: 'Technical analysis of sfumato',
                category: 'Sources'
            })""",
            ]
        )

        # 11. 概念與術語數據
        sample_data.extend(
            [
                """CREATE (:Perspective {
                name: 'Linear Perspective',
                description: 'Mathematical system for representing 3D space on 2D surface',
                inventor: 'Filippo Brunelleschi',
                principles: ['vanishing point', 'horizon line', 'orthogonal lines'],
                category: 'Concepts'
            })""",
                """CREATE (:Contrapposto {
                name: 'Contrapposto',
                description: 'Sculptural pose with weight on one leg',
                origin: 'Classical antiquity',
                renaissance_revival: 'Rediscovered in Renaissance',
                category: 'Concepts'
            })""",
            ]
        )

        # 12. 版本/語言數據
        sample_data.extend(
            [
                """CREATE (:ItalianTerm {
                term: 'sfumato',
                pronunciation: 'sfu-MA-to',
                literal_meaning: 'smoky',
                art_context: 'painting technique',
                category: 'Translations'
            })""",
                """CREATE (:ChineseTerm {
                term: '暈塗法',
                romanization: 'yun tu fa',
                explanation: '煙霧般的色彩過渡技法',
                category: 'Translations'
            })""",
                """CREATE (:EnglishTerm {
                term: 'sfumato technique',
                definition: 'subtle gradation without lines',
                category: 'Translations'
            })""",
            ]
        )

        return sample_data

    def create_sample_relationships(self) -> list[str]:
        """創建示例關係"""
        relationships = []

        # 創作關係
        relationships.extend(
            [
                "MATCH (leo:Artist {name: 'Leonardo da Vinci'}), "
                "(mona:Painting {title: 'Mona Lisa'}) "
                "CREATE (mona)-[:CREATED_BY {year: 1503}]->(leo)",
                "CREATE (mona)-[:CREATED_BY {year: 1503}]->(leo)",
                "MATCH (leo:Artist {name: 'Leonardo da Vinci'}), (sfumato:Sfumato) "
                "CREATE (leo)-[:DEVELOPED_TECHNIQUE]->(sfumato)",
            ]
        )

        # 影響關係
        relationships.extend(
            [
                "MATCH (leo:Artist {name: 'Leonardo da Vinci'}), (hr:HighRenaissance) "
                "CREATE (leo)-[:BELONGS_TO_MOVEMENT]->(hr)",
                "MATCH (mona:Painting {title: 'Mona Lisa'}), (sfumato:Sfumato) "
                "CREATE (mona)-[:USES_TECHNIQUE]->(sfumato)",
            ]
        )

        # 收藏關係
        relationships.extend(
            [
                "MATCH (mona:Painting {title: 'Mona Lisa'}), "
                "(louvre:Museum {name: 'Louvre Museum'}) "
                "CREATE (mona)-[:HOUSED_IN]->(louvre)",
                "CREATE (mona)-[:HOUSED_IN]->(louvre)",
            ]
        )

        # 地理關係
        relationships.extend(
            [
                "MATCH (leo:Artist {name: 'Leonardo da Vinci'}), "
                "(florence:City {name: 'Florence'}) "
                "CREATE (leo)-[:WORKED_IN]->(florence)",
                "CREATE (leo)-[:WORKED_IN]->(florence)",
                "MATCH (louvre:Museum {name: 'Louvre Museum'}), (paris:City {name: 'Paris'}) "
                "CREATE (louvre)-[:LOCATED_IN]->(paris)",
            ]
        )

        # 語言對照關係
        relationships.extend(
            [
                "MATCH (it:ItalianTerm {term: 'sfumato'}), (cn:ChineseTerm {term: '暈塗法'}) "
                "CREATE (it)-[:TRANSLATED_AS]->(cn)",
                "MATCH (it:ItalianTerm {term: 'sfumato'}), "
                "(en:EnglishTerm {term: 'sfumato technique'}) "
                "CREATE (it)-[:EQUIVALENT_TO]->(en)",
                "CREATE (it)-[:EQUIVALENT_TO]->(en)",
            ]
        )

        return relationships


def test_12_category_system():
    """測試12大分類系統"""
    print("🎨 測試12大藝術史分類GraphRAG系統")
    print("=" * 60)

    schema = ArtHistory12CategorySchema()
    router = GraphRAGQueryRouter()

    # 測試查詢分析
    test_queries = [
        "達文西創作了哪些著名作品？",
        "什麼是sfumato技法？",
        "文藝復興時期佛羅倫斯有哪些重要藝術家？",
        "蒙娜麗莎現在收藏在哪裡？",
        "美第奇家族贊助了哪些藝術家？",
        "contrapposto的中文翻譯是什麼？",
    ]

    print("\n🔍 查詢分析測試:")
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. 查詢: {query}")
        analysis = router.analyze_query_intent(query)
        print(f"   檢測到的分類: {[cat.value for cat in analysis['detected_categories']]}")
        print(f"   查詢意圖: {analysis['detected_intents']}")
        print(f"   選擇的模式: {analysis['selected_pattern']}")
        print(f"   信心度: {analysis['confidence']:.2f}")

        # 生成Cypher查詢
        cypher = router.generate_cypher_query(analysis, limit=10)
        print(f"   生成的Cypher: {cypher[:100]}...")

    print("\n📊 12大分類統計:")
    categories = schema.get_category_description()
    for i, (category, description) in enumerate(categories.items(), 1):
        print(f"{i:2d}. {category}: {description}")

    print("\n✅ 測試完成！")
    print(f"   節點類型總數: {len(DetailedNodeTypes)}")
    print(f"   關係類型總數: {len(GraphRAGRelationTypes)}")
    print(f"   查詢模式總數: {len(router.query_patterns)}")


if __name__ == "__main__":
    test_12_category_system()
