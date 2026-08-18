#!/usr/bin/env python3
"""
數據映射器 - 將現有爬蟲數據映射到增強的節點分類體系
將Europeana和其他數據源的數據轉換為新的增強節點類型
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from enhanced_art_history_schema import EnhancedArtHistorySchema, NodeType, RelationType
from enhanced_graph_builder import EnhancedArtEntity, EnhancedArtHistoryGraphBuilder

logger = logging.getLogger(__name__)


@dataclass
class MappingRule:
    """數據映射規則"""

    source_field: str
    target_node_type: NodeType
    target_property: str
    transformation: str | None = None
    condition: str | None = None


class ArtHistoryDataMapper:
    """藝術史數據映射器"""

    def __init__(self):
        self.schema = EnhancedArtHistorySchema()
        self.builder = EnhancedArtHistoryGraphBuilder()
        self.mapping_rules = self._define_mapping_rules()
        self.mapped_entities = []
        self.mapped_relationships = []

    def _define_mapping_rules(self) -> dict[str, list[MappingRule]]:
        """定義數據映射規則"""
        return {
            # Europeana數據映射
            "europeana": [
                # 藝術家映射
                MappingRule("dcCreator", NodeType.ARTIST, "name"),
                MappingRule("dcCreator", NodeType.ARTIST, "full_name"),
                MappingRule("edmTimeSpan", NodeType.ARTIST, "birth_year", "extract_birth_year"),
                MappingRule("edmTimeSpan", NodeType.ARTIST, "death_year", "extract_death_year"),
                # 作品映射
                MappingRule("dcTitle", NodeType.ARTWORK, "title"),
                MappingRule("dcDescription", NodeType.ARTWORK, "description"),
                MappingRule("dcDate", NodeType.ARTWORK, "creation_date"),
                MappingRule("dcFormat", NodeType.ARTWORK, "medium"),
                MappingRule("dcType", NodeType.ARTWORK, "genre"),
                MappingRule("dcSubject", NodeType.ARTWORK, "subject_matter", "list_conversion"),
                # 特定作品類型映射
                MappingRule("dcType", NodeType.PAINTING, "genre", condition="type_is_painting"),
                MappingRule("dcType", NodeType.SCULPTURE, "genre", condition="type_is_sculpture"),
                MappingRule("dcType", NodeType.PHOTOGRAPH, "genre", condition="type_is_photograph"),
                # 機構映射
                MappingRule("edmDataProvider", NodeType.MUSEUM, "name"),
                MappingRule("edmDataProvider", NodeType.GALLERY, "name", condition="is_gallery"),
                MappingRule("edmCountry", NodeType.MUSEUM, "country"),
                # 地理映射
                MappingRule("dctermsCreated", NodeType.LOCATION, "name", "extract_location"),
                MappingRule("edmCountry", NodeType.COUNTRY, "name"),
                # 時期映射
                MappingRule("edmTimeSpan", NodeType.PERIOD, "name", "extract_period"),
                MappingRule("edmTimeSpan", NodeType.CENTURY, "name", "extract_century"),
                # 主題映射
                MappingRule("dcSubject", NodeType.THEME, "name", "extract_themes"),
                MappingRule("dcSubject", NodeType.MOTIF, "name", "extract_motifs"),
            ],
            # 維基百科數據映射
            "wikipedia": [
                MappingRule("title", NodeType.ARTIST, "name"),
                MappingRule("summary", NodeType.ARTIST, "biography"),
                MappingRule("birth_year", NodeType.ARTIST, "birth_year"),
                MappingRule("death_year", NodeType.ARTIST, "death_year"),
                MappingRule("nationality", NodeType.ARTIST, "nationality"),
                MappingRule("movement", NodeType.MOVEMENT, "name"),
            ],
            # Getty數據映射
            "getty": [
                MappingRule("preferred_term", NodeType.ARTIST, "name"),
                MappingRule("scope_note", NodeType.ARTIST, "biography"),
                MappingRule("birth_date", NodeType.ARTIST, "birth_year"),
                MappingRule("death_date", NodeType.ARTIST, "death_year"),
                MappingRule("nationality", NodeType.ARTIST, "nationality"),
            ],
        }

    def map_europeana_data(
        self, europeana_data: list[dict]
    ) -> tuple[list[EnhancedArtEntity], list[dict]]:
        """映射Europeana數據到增強節點類型"""
        entities = []
        relationships = []

        for item in europeana_data:
            try:
                # 確定主要作品類型
                artwork_type = self._determine_artwork_type(item)

                # 創建作品實體
                artwork_entity = self._create_artwork_entity(item, artwork_type)
                if artwork_entity:
                    entities.append(artwork_entity)

                # 創建藝術家實體
                artist_entity = self._create_artist_entity(item)
                if artist_entity:
                    entities.append(artist_entity)

                # 創建機構實體
                institution_entity = self._create_institution_entity(item)
                if institution_entity:
                    entities.append(institution_entity)

                # 創建地理實體
                location_entities = self._create_location_entities(item)
                entities.extend(location_entities)

                # 創建時期實體
                period_entities = self._create_period_entities(item)
                entities.extend(period_entities)

                # 創建主題實體
                theme_entities = self._create_theme_entities(item)
                entities.extend(theme_entities)

                # 創建關係
                item_relationships = self._create_relationships(
                    item, artwork_entity, artist_entity, institution_entity
                )
                relationships.extend(item_relationships)

            except Exception as e:
                logger.warning(f"映射項目時出錯: {str(e)[:100]}")
                continue

        # 去重
        unique_entities = self._deduplicate_entities(entities)

        logger.info(f"✅ 映射完成: {len(unique_entities)} 個實體, {len(relationships)} 個關係")
        return unique_entities, relationships

    def _determine_artwork_type(self, item: dict) -> NodeType:
        """確定作品的具體類型"""
        dc_type = item.get("dcType", "").lower()
        dc_format = item.get("dcFormat", "").lower()
        # 原本另取 dcTitle 但從未參與判型——僅憑標題判斷媒材誤判率高（如
        # 「Painting the Modern Garden」書籍），維持只看 dcType/dcFormat。

        # 繪畫
        if any(
            keyword in dc_type or keyword in dc_format
            for keyword in ["painting", "oil", "canvas", "fresco", "watercolor", "gouache"]
        ):
            return NodeType.PAINTING

        # 雕塑
        elif any(
            keyword in dc_type or keyword in dc_format
            for keyword in ["sculpture", "statue", "bronze", "marble", "clay", "ceramic"]
        ):
            return NodeType.SCULPTURE

        # 素描
        elif any(
            keyword in dc_type or keyword in dc_format
            for keyword in ["drawing", "sketch", "charcoal", "pencil", "ink"]
        ):
            return NodeType.DRAWING

        # 版畫
        elif any(
            keyword in dc_type or keyword in dc_format
            for keyword in ["print", "etching", "engraving", "lithograph", "woodcut"]
        ):
            return NodeType.PRINT

        # 攝影
        elif any(
            keyword in dc_type or keyword in dc_format
            for keyword in ["photograph", "photo", "daguerreotype", "digital"]
        ):
            return NodeType.PHOTOGRAPH

        # 手稿
        elif any(
            keyword in dc_type or keyword in dc_format
            for keyword in ["manuscript", "illuminated", "codex", "scroll"]
        ):
            return NodeType.MANUSCRIPT

        # 工藝品
        elif any(
            keyword in dc_type or keyword in dc_format
            for keyword in ["craft", "decorative", "applied", "pottery", "textile"]
        ):
            return NodeType.CRAFT

        # 默認為藝術作品
        else:
            return NodeType.ARTWORK

    def _create_artwork_entity(
        self, item: dict, artwork_type: NodeType
    ) -> EnhancedArtEntity | None:
        """創建作品實體"""
        title = item.get("dcTitle")
        if not title:
            return None

        properties = {
            "title": title,
            "description": item.get("dcDescription", ""),
            "creation_date": self._extract_date(item.get("dcDate", "")),
            "medium": item.get("dcFormat", ""),
            "genre": item.get("dcType", ""),
            "subject_matter": self._extract_list(item.get("dcSubject", "")),
            "current_location": item.get("edmDataProvider", ""),
            "cultural_significance": item.get("dcDescription", ""),
            "provenance": [item.get("edmDataProvider", "")],
            "source_url": item.get("edmIsShownAt", ""),
            "external_id": item.get("id", ""),
            "language": item.get("dcLanguage", ""),
            "rights": item.get("dcRights", ""),
        }

        # 根據作品類型添加特定屬性
        if artwork_type == NodeType.PAINTING:
            properties.update(
                {
                    "technique": self._extract_techniques(item),
                    "style": self._extract_style(item),
                    "color_palette": self._extract_colors(item),
                }
            )
        elif artwork_type == NodeType.SCULPTURE:
            properties.update(
                {
                    "material": self._extract_materials(item),
                    "technique": self._extract_sculpture_techniques(item),
                }
            )

        return EnhancedArtEntity(artwork_type, title, properties)

    def _create_artist_entity(self, item: dict) -> EnhancedArtEntity | None:
        """創建藝術家實體"""
        creator = item.get("dcCreator")
        if not creator:
            return None

        properties = {
            "name": creator,
            "full_name": creator,
            "biography": f"Artist mentioned in {item.get('edmDataProvider', 'unknown source')}",
            "notable_works": [item.get("dcTitle", "")],
            "historical_significance": item.get("dcDescription", ""),
            "active_period": self._extract_date(item.get("dcDate", "")),
            "associated_locations": [self._extract_location(item)],
            "source_references": [item.get("edmIsShownAt", "")],
        }

        return EnhancedArtEntity(NodeType.ARTIST, creator, properties)

    def _create_institution_entity(self, item: dict) -> EnhancedArtEntity | None:
        """創建機構實體"""
        provider = item.get("edmDataProvider")
        if not provider:
            return None

        # 判斷機構類型
        institution_type = self._determine_institution_type(provider)

        properties = {
            "name": provider,
            "full_name": provider,
            "country": item.get("edmCountry", ""),
            "collection_focus": self._infer_collection_focus(item),
            "notable_collections": [item.get("dcTitle", "")],
            "website": item.get("edmIsShownAt", ""),
            "specialization": [item.get("dcType", "")],
            "source_data": "Europeana",
        }

        return EnhancedArtEntity(institution_type, provider, properties)

    def _determine_institution_type(self, provider_name: str) -> NodeType:
        """確定機構類型"""
        provider_lower = provider_name.lower()

        if any(keyword in provider_lower for keyword in ["museum", "museo", "musée", "muzeum"]):
            return NodeType.MUSEUM
        elif any(keyword in provider_lower for keyword in ["gallery", "galerie", "galleria"]):
            return NodeType.GALLERY
        elif any(
            keyword in provider_lower for keyword in ["library", "biblioteca", "bibliothèque"]
        ):
            return NodeType.LIBRARY
        elif any(keyword in provider_lower for keyword in ["archive", "archivo", "archivio"]):
            return NodeType.ARCHIVE
        elif any(
            keyword in provider_lower for keyword in ["university", "universidad", "université"]
        ):
            return NodeType.UNIVERSITY
        else:
            return NodeType.INSTITUTION

    def _create_location_entities(self, item: dict) -> list[EnhancedArtEntity]:
        """創建地理實體"""
        entities = []

        # 國家
        country = item.get("edmCountry")
        if country:
            country_entity = EnhancedArtEntity(
                NodeType.COUNTRY,
                country,
                {
                    "name": country,
                    "cultural_heritage": "Represented in Europeana",
                    "artistic_traditions": [item.get("dcType", "")],
                },
            )
            entities.append(country_entity)

        # 從創建地點提取城市
        location = self._extract_location(item)
        if location and location != country:
            location_entity = EnhancedArtEntity(
                NodeType.CITY,
                location,
                {
                    "name": location,
                    "country": country,
                    "cultural_significance": f"Associated with {item.get('dcTitle', '')}",
                    "artistic_heritage": [item.get("dcType", "")],
                },
            )
            entities.append(location_entity)

        return entities

    def _create_period_entities(self, item: dict) -> list[EnhancedArtEntity]:
        """創建時期實體"""
        entities = []

        date_str = item.get("dcDate", "")
        if not date_str:
            return entities

        # 提取世紀
        century = self._extract_century(date_str)
        if century:
            century_entity = EnhancedArtEntity(
                NodeType.CENTURY,
                century,
                {
                    "name": century,
                    "time_period": century,
                    "cultural_context": f"Period of {item.get('dcTitle', '')}",
                    "artistic_movements": [item.get("dcType", "")],
                },
            )
            entities.append(century_entity)

        # 提取具體年代
        decade = self._extract_decade(date_str)
        if decade:
            decade_entity = EnhancedArtEntity(
                NodeType.DECADE,
                decade,
                {
                    "name": decade,
                    "time_period": decade,
                    "historical_events": f"Period of {item.get('dcTitle', '')}",
                    "artistic_trends": [item.get("dcType", "")],
                },
            )
            entities.append(decade_entity)

        return entities

    def _create_theme_entities(self, item: dict) -> list[EnhancedArtEntity]:
        """創建主題實體"""
        entities = []

        subjects = self._extract_list(item.get("dcSubject", ""))
        for subject in subjects:
            if len(subject.strip()) > 2:  # 過濾太短的主題
                theme_entity = EnhancedArtEntity(
                    NodeType.THEME,
                    subject,
                    {
                        "name": subject,
                        "description": f"Theme found in {item.get('dcTitle', '')}",
                        "cultural_context": item.get("edmCountry", ""),
                        "associated_works": [item.get("dcTitle", "")],
                        "time_period": self._extract_date(item.get("dcDate", "")),
                    },
                )
                entities.append(theme_entity)

        return entities

    def _create_relationships(
        self,
        item: dict,
        artwork: EnhancedArtEntity,
        artist: EnhancedArtEntity,
        institution: EnhancedArtEntity,
    ) -> list[dict]:
        """創建實體間關係"""
        relationships = []

        if artwork and artist:
            relationships.append(
                {
                    "from": artwork.name,
                    "type": RelationType.CREATED_BY.value,
                    "to": artist.name,
                    "properties": {
                        "creation_date": self._extract_date(item.get("dcDate", "")),
                        "attribution_certainty": 0.8,
                        "source": "Europeana",
                    },
                }
            )

        if artwork and institution:
            relationships.append(
                {
                    "from": artwork.name,
                    "type": RelationType.HOUSED_IN.value,
                    "to": institution.name,
                    "properties": {
                        "collection_type": "Digital collection",
                        "access_type": "Online",
                        "source": "Europeana",
                    },
                }
            )

        # 地理關係
        country = item.get("edmCountry")
        if artist and country:
            relationships.append(
                {
                    "from": artist.name,
                    "type": RelationType.ASSOCIATED_WITH.value,
                    "to": country,
                    "properties": {"association_type": "Cultural heritage", "source": "Europeana"},
                }
            )

        return relationships

    # === 輔助方法 ===

    def _extract_date(self, date_str: str) -> str:
        """提取並標準化日期"""
        if not date_str:
            return ""

        # 查找四位數年份
        year_match = re.search(r"\b(1[0-9]{3}|20[0-2][0-9])\b", date_str)
        if year_match:
            return year_match.group(1)

        # 查找世紀表示
        century_match = re.search(r"(\d+)(?:st|nd|rd|th)?\s*century", date_str.lower())
        if century_match:
            return f"{century_match.group(1)}th century"

        return date_str

    def _extract_century(self, date_str: str) -> str | None:
        """從日期字符串提取世紀"""
        year_match = re.search(r"\b(1[0-9]{3}|20[0-2][0-9])\b", date_str)
        if year_match:
            year = int(year_match.group(1))
            century = (year - 1) // 100 + 1
            return f"{century}th century"

        century_match = re.search(r"(\d+)(?:st|nd|rd|th)?\s*century", date_str.lower())
        if century_match:
            return f"{century_match.group(1)}th century"

        return None

    def _extract_decade(self, date_str: str) -> str | None:
        """從日期字符串提取年代"""
        year_match = re.search(r"\b(1[0-9]{3}|20[0-2][0-9])\b", date_str)
        if year_match:
            year = int(year_match.group(1))
            decade = (year // 10) * 10
            return f"{decade}s"
        return None

    def _extract_location(self, item: dict) -> str:
        """提取地理位置"""
        # 嘗試從多個字段提取位置信息
        location_fields = ["dctermsCreated", "dctermsSpatial", "edmPlace"]
        for field in location_fields:
            if field in item and item[field]:
                return item[field]
        return ""

    def _extract_list(self, value: Any) -> list[str]:
        """將值轉換為列表"""
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            # 分割字符串
            return [item.strip() for item in re.split(r"[;,|]", value) if item.strip()]
        else:
            return [str(value)] if value else []

    def _extract_techniques(self, item: dict) -> list[str]:
        """提取繪畫技法"""
        techniques = []
        format_str = item.get("dcFormat", "").lower()

        if "oil" in format_str:
            techniques.append("Oil painting")
        if "watercolor" in format_str:
            techniques.append("Watercolor")
        if "fresco" in format_str:
            techniques.append("Fresco")
        if "tempera" in format_str:
            techniques.append("Tempera")

        return techniques

    def _extract_materials(self, item: dict) -> list[str]:
        """提取雕塑材料"""
        materials = []
        format_str = item.get("dcFormat", "").lower()

        if any(mat in format_str for mat in ["bronze", "brass"]):
            materials.append("Bronze")
        if any(mat in format_str for mat in ["marble", "stone"]):
            materials.append("Stone")
        if "wood" in format_str:
            materials.append("Wood")
        if any(mat in format_str for mat in ["clay", "ceramic"]):
            materials.append("Clay")

        return materials

    def _extract_style(self, item: dict) -> str:
        """提取藝術風格"""
        # 從描述或類型中推斷風格
        desc = item.get("dcDescription", "").lower()
        dc_type = item.get("dcType", "").lower()

        style_keywords = {
            "renaissance": "Renaissance",
            "baroque": "Baroque",
            "impressionist": "Impressionism",
            "romantic": "Romanticism",
            "classical": "Classicism",
            "modern": "Modernism",
        }

        for keyword, style in style_keywords.items():
            if keyword in desc or keyword in dc_type:
                return style

        return ""

    def _extract_colors(self, item: dict) -> list[str]:
        """提取色彩信息"""
        colors = []
        desc = item.get("dcDescription", "").lower()

        color_keywords = ["red", "blue", "green", "yellow", "black", "white", "gold", "silver"]
        for color in color_keywords:
            if color in desc:
                colors.append(color.capitalize())

        return colors

    def _infer_collection_focus(self, item: dict) -> list[str]:
        """推斷收藏重點"""
        dc_type = item.get("dcType", "")
        return [dc_type] if dc_type else ["General collection"]

    def _deduplicate_entities(self, entities: list[EnhancedArtEntity]) -> list[EnhancedArtEntity]:
        """去除重複實體"""
        seen = set()
        unique_entities = []

        for entity in entities:
            key = (entity.entity_type.value, entity.name)
            if key not in seen:
                seen.add(key)
                unique_entities.append(entity)

        return unique_entities

    def map_single_item(
        self, item: dict, source: str = "unknown"
    ) -> tuple[list[EnhancedArtEntity], list[dict]]:
        """映射單個數據項目"""
        entities = []
        relationships = []

        try:
            # 確定主要作品類型
            artwork_type = self._determine_artwork_type(item)

            # 創建作品實體
            artwork_entity = self._create_artwork_entity(item, artwork_type)
            if artwork_entity:
                entities.append(artwork_entity)

            # 創建藝術家實體
            artist_entity = self._create_artist_entity(item)
            if artist_entity:
                entities.append(artist_entity)

            # 創建機構實體
            institution_entity = self._create_institution_entity(item)
            if institution_entity:
                entities.append(institution_entity)

            # 創建關係
            item_relationships = self._create_relationships(
                item, artwork_entity, artist_entity, institution_entity
            )
            relationships.extend(item_relationships)

        except Exception as e:
            logger.warning(f"映射項目時出錯: {str(e)[:100]}")

        return entities, relationships

    def save_mapped_data(self, entities: list[EnhancedArtEntity], relationships: list[dict]):
        """保存映射後的數據"""
        # 保存實體
        entities_data = [
            {
                "type": entity.entity_type.value,
                "name": entity.name,
                "properties": entity.properties,
                "subcategory": entity.subcategory,
                "aliases": entity.aliases,
            }
            for entity in entities
        ]

        with open("mapped_entities.json", "w", encoding="utf-8") as f:
            json.dump(entities_data, f, ensure_ascii=False, indent=2)

        # 保存關係
        with open("mapped_relationships.json", "w", encoding="utf-8") as f:
            json.dump(relationships, f, ensure_ascii=False, indent=2)

        logger.info("✅ 映射數據已保存")


# 測試函數
def test_data_mapping():
    """測試數據映射功能"""
    # 模擬Europeana數據
    sample_data = [
        {
            "id": "test1",
            "dcTitle": "The Starry Night",
            "dcCreator": "Vincent van Gogh",
            "dcDate": "1889",
            "dcDescription": "Post-impressionist painting showing swirling night sky",
            "dcType": "Painting",
            "dcFormat": "Oil on canvas",
            "dcSubject": "Night; Village; Stars; Landscape",
            "edmDataProvider": "Museum of Modern Art",
            "edmCountry": "Netherlands",
            "edmIsShownAt": "https://example.com/starry-night",
        }
    ]

    mapper = ArtHistoryDataMapper()
    entities, relationships = mapper.map_europeana_data(sample_data)

    print("✅ 測試完成:")
    print(f"   實體數量: {len(entities)}")
    print(f"   關係數量: {len(relationships)}")

    print("\n實體類型分布:")
    entity_types = {}
    for entity in entities:
        entity_type = entity.entity_type.value
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

    for entity_type, count in sorted(entity_types.items()):
        print(f"   - {entity_type}: {count}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_data_mapping()
