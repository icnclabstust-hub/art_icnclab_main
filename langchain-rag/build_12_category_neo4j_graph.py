#!/usr/bin/env python3
"""
基於12大分類重建Neo4j藝術史知識圖譜
按照用戶指定的分類方法創建節點和關係
"""

import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ArtHistory12CategoryBuilder:
    """12大分類藝術史知識圖譜構建器"""

    def __init__(self):
        self.nodes = []
        self.relationships = []

    def add_12_category_data(self):
        """添加基於12大分類的數據"""

        # === 1. 人物（Artists/Authors）===
        people_data = [
            {
                "category": "People",
                "subcategory": "Artist",
                "name": "Leonardo da Vinci",
                "full_name": "Leonardo di ser Piero da Vinci",
                "birth_year": 1452,
                "death_year": 1519,
                "nationality": "Italian",
                "birthplace": "Vinci, Republic of Florence",
                "specialization": "Polymath",
                "role": "畫家、發明家、科學家",
                "biography": "文藝復興時期的博學者，在繪畫、雕塑、建築、科學等領域都有傑出貢獻",
            },
            {
                "category": "People",
                "subcategory": "Artist",
                "name": "Michelangelo Buonarroti",
                "birth_year": 1475,
                "death_year": 1564,
                "nationality": "Italian",
                "birthplace": "Caprese, Republic of Florence",
                "specialization": "Sculptor, Painter, Architect",
                "role": "雕塑家、畫家、建築師",
                "biography": "文藝復興盛期最偉大的藝術家之一",
            },
            {
                "category": "People",
                "subcategory": "Patron",
                "name": "Lorenzo de Medici",
                "title": "Lorenzo the Magnificent",
                "birth_year": 1449,
                "death_year": 1492,
                "nationality": "Italian",
                "role": "贊助人、統治者",
                "family": "Medici",
                "patronage_focus": "藝術、文學、哲學",
            },
            {
                "category": "People",
                "subcategory": "Theorist",
                "name": "Giorgio Vasari",
                "birth_year": 1511,
                "death_year": 1574,
                "nationality": "Italian",
                "role": "藝術史家、畫家、建築師",
                "major_work": "Lives of the Most Excellent Painters, Sculptors, and Architects",
            },
            {
                "category": "People",
                "subcategory": "Collector",
                "name": "Isabella d'Este",
                "birth_year": 1474,
                "death_year": 1539,
                "title": "Marchesa of Mantua",
                "role": "收藏家、贊助人",
                "collection_focus": "文藝復興藝術、古典文物",
            },
        ]

        # === 2. 作品（Artworks/Objects）===
        artworks_data = [
            {
                "category": "Artworks",
                "subcategory": "Painting",
                "title": "Mona Lisa",
                "alternative_titles": "La Gioconda, Portrait of Lisa Gherardini",
                "creation_date": "1503-1519",
                "artist": "Leonardo da Vinci",
                "dimensions": "77 cm × 53 cm",
                "medium": "Oil on poplar panel",
                "description": "神秘微笑的麗莎‧格拉迪尼肖像",
                "significance": "世界最著名的畫作",
                "current_location": "Louvre Museum, Paris",
            },
            {
                "category": "Artworks",
                "subcategory": "Painting",
                "title": "The Last Supper",
                "creation_date": "1495-1498",
                "artist": "Leonardo da Vinci",
                "dimensions": "460 cm × 880 cm",
                "medium": "Tempera and oil on plaster",
                "description": "耶穌與十二門徒的最後晚餐",
                "location": "Santa Maria delle Grazie, Milan",
                "technique_used": "Linear perspective, composition",
            },
            {
                "category": "Artworks",
                "subcategory": "Sculpture",
                "title": "David",
                "creation_date": "1501-1504",
                "artist": "Michelangelo Buonarroti",
                "dimensions": "517 cm height",
                "material": "Carrara marble",
                "description": "準備迎戰歌利亞的大衛",
                "significance": "佛羅倫斯共和國的象徵",
                "current_location": "Galleria dell'Accademia, Florence",
            },
            {
                "category": "Artworks",
                "subcategory": "Architecture",
                "title": "Sistine Chapel",
                "construction_date": "1473-1481",
                "architect": "Giovanni dei Dolci",
                "location": "Vatican City",
                "description": "教皇私人小聖堂",
                "famous_for": "米開朗基羅的天頂畫",
            },
        ]

        # === 3. 流派/運動（Styles/Movements）===
        movements_data = [
            {
                "category": "Movements",
                "subcategory": "EarlyRenaissance",
                "name": "Early Renaissance",
                "chinese_name": "早期文藝復興",
                "start_period": 1400,
                "end_period": 1490,
                "origin_location": "Florence, Italy",
                "key_characteristics": "透視法復興、人文主義、古典元素",
                "major_figures": ["Brunelleschi", "Donatello", "Masaccio"],
            },
            {
                "category": "Movements",
                "subcategory": "HighRenaissance",
                "name": "High Renaissance",
                "chinese_name": "盛期文藝復興",
                "start_period": 1495,
                "end_period": 1520,
                "origin_location": "Rome, Florence",
                "key_characteristics": "完美平衡、理想化美感、數學精確性",
                "major_figures": ["Leonardo da Vinci", "Michelangelo", "Raphael"],
            },
            {
                "category": "Movements",
                "subcategory": "Mannerism",
                "name": "Mannerism",
                "chinese_name": "曼納主義",
                "start_period": 1520,
                "end_period": 1600,
                "key_characteristics": "誇張比例、複雜姿態、人工色彩",
                "reaction_to": "High Renaissance perfection",
            },
        ]

        # === 4. 技法與材質（Techniques/Materials）===
        techniques_data = [
            {
                "category": "Techniques",
                "subcategory": "OilPainting",
                "name": "Oil Painting",
                "chinese_name": "油畫技法",
                "description": "使用油性顏料的繪畫技法",
                "materials": ["oil binder", "pigments", "canvas or wood panel"],
                "advantages": "緩慢乾燥、易於混合、色彩豐富",
                "notable_practitioners": ["Jan van Eyck", "Leonardo da Vinci"],
            },
            {
                "category": "Techniques",
                "subcategory": "Fresco",
                "name": "Fresco",
                "chinese_name": "濕壁畫",
                "description": "在濕石灰牆面上繪製的技法",
                "process": "在石灰砂漿未乾時作畫",
                "advantages": "持久性、與牆面結合",
                "notable_examples": ["Sistine Chapel Ceiling", "School of Athens"],
            },
            {
                "category": "Techniques",
                "subcategory": "Sfumato",
                "name": "Sfumato",
                "chinese_name": "暈塗法",
                "italian_term": "sfumato",
                "literal_meaning": "smoky",
                "description": "無線條邊界的微妙色彩過渡技法",
                "inventor": "Leonardo da Vinci",
                "visual_effect": "煙霧般的柔和過渡",
            },
        ]

        # === 5. 主題與圖像學（Iconography/Themes）===
        themes_data = [
            {
                "category": "Themes",
                "subcategory": "ReligiousMotif",
                "name": "Annunciation",
                "chinese_name": "天使報喜",
                "description": "天使加百列向聖母瑪利亞報告聖子降生",
                "religious_tradition": "Christianity",
                "symbolic_elements": ["lily (purity)", "dove (Holy Spirit)", "book (Word of God)"],
                "common_compositions": "天使左側，聖母右側",
            },
            {
                "category": "Themes",
                "subcategory": "Mythology",
                "name": "Venus and Mars",
                "chinese_name": "維納斯與馬爾斯",
                "origin": "Roman mythology",
                "symbolism": "愛情征服戰爭",
                "famous_examples": ["Botticelli's Venus and Mars"],
            },
            {
                "category": "Themes",
                "subcategory": "Portrait",
                "name": "Portrait painting",
                "chinese_name": "肖像畫",
                "description": "個人形象的藝術表現",
                "evolution": "從中世紀宗教背景到文藝復興個人主義",
                "types": ["individual", "group", "self-portrait"],
            },
        ]

        # === 6. 時間（Periods/Chronology）===
        chronology_data = [
            {
                "category": "Chronology",
                "subcategory": "MediciPeriod",
                "name": "Medici Rule in Florence",
                "chinese_name": "美第奇家族統治期",
                "start_year": 1434,
                "end_year": 1737,
                "key_rulers": ["Cosimo the Elder", "Lorenzo the Magnificent", "Cosimo I"],
                "cultural_impact": "文藝復興的重要贊助者",
                "patronage_style": "人文主義、古典復興",
            },
            {
                "category": "Chronology",
                "subcategory": "Century",
                "name": "15th Century",
                "chinese_name": "15世紀",
                "start_year": 1401,
                "end_year": 1500,
                "art_historical_period": "Early Renaissance",
                "major_developments": ["透視法發明", "人文主義興起", "古典藝術復興"],
            },
            {
                "category": "Chronology",
                "subcategory": "Century",
                "name": "16th Century",
                "chinese_name": "16世紀",
                "start_year": 1501,
                "end_year": 1600,
                "art_historical_period": "High Renaissance to Mannerism",
                "major_developments": ["藝術巔峰期", "曼納主義興起", "宗教改革影響"],
            },
        ]

        # === 7. 地點（Places）===
        places_data = [
            {
                "category": "Places",
                "subcategory": "City",
                "name": "Florence",
                "chinese_name": "佛羅倫斯",
                "country": "Italy",
                "region": "Tuscany",
                "cultural_significance": "文藝復興發源地",
                "artistic_importance": "早期文藝復興中心",
                "notable_sites": ["Uffizi Gallery", "Palazzo Pitti", "Duomo"],
                "ruling_family": "Medici",
            },
            {
                "category": "Places",
                "subcategory": "City",
                "name": "Rome",
                "chinese_name": "羅馬",
                "country": "Italy",
                "region": "Lazio",
                "cultural_significance": "盛期文藝復興中心",
                "artistic_importance": "教皇贊助的藝術中心",
                "notable_sites": ["Vatican Museums", "Sistine Chapel", "St. Peter's Basilica"],
            },
            {
                "category": "Places",
                "subcategory": "Museum",
                "name": "Louvre Museum",
                "chinese_name": "羅浮宮",
                "location": "Paris, France",
                "founded_year": 1793,
                "type": "Art museum",
                "notable_collections": ["Mona Lisa", "Venus de Milo"],
                "annual_visitors": 9600000,
            },
        ]

        # === 8. 機構（Institutions）===
        institutions_data = [
            {
                "category": "Institutions",
                "subcategory": "PatronageFamily",
                "name": "Medici Family",
                "chinese_name": "美第奇家族",
                "location": "Florence",
                "active_period": "1434-1737",
                "type": "Banking and ruling family",
                "supported_artists": ["Michelangelo", "Botticelli", "Donatello"],
                "cultural_contribution": "文藝復興主要推動者",
            },
            {
                "category": "Institutions",
                "subcategory": "Workshop",
                "name": "Verrocchio's Workshop",
                "chinese_name": "韋羅基奧工坊",
                "master": "Andrea del Verrocchio",
                "location": "Florence",
                "active_period": "1460-1488",
                "notable_apprentices": ["Leonardo da Vinci", "Lorenzo di Credi"],
                "specialization": "繪畫、雕塑教學",
            },
        ]

        # === 9. 事件（Events）===
        events_data = [
            {
                "category": "Events",
                "subcategory": "Commission",
                "name": "Sistine Chapel Ceiling Commission",
                "chinese_name": "西斯廷禮拜堂天頂委託",
                "commissioner": "Pope Julius II",
                "artist": "Michelangelo",
                "commission_date": 1508,
                "completion_date": 1512,
                "significance": "盛期文藝復興巔峰作品",
                "payment": "3000 ducats",
            },
            {
                "category": "Events",
                "subcategory": "Publication",
                "name": "Publication of Vasari's Lives",
                "chinese_name": "瓦薩里《名人傳》出版",
                "author": "Giorgio Vasari",
                "first_edition": 1550,
                "second_edition": 1568,
                "significance": "第一部藝術史著作",
            },
        ]

        # === 10. 文獻（Sources/Texts）===
        sources_data = [
            {
                "category": "Sources",
                "subcategory": "PrimarySource",
                "title": "Lives of the Most Excellent Painters, Sculptors, and Architects",
                "chinese_title": "最傑出的畫家、雕塑家和建築師的生平",
                "author": "Giorgio Vasari",
                "publication_date": "1550, 1568",
                "language": "Italian",
                "significance": "第一部系統性藝術史著作",
                "coverage": "13-16世紀義大利藝術家",
            },
            {
                "category": "Sources",
                "subcategory": "Treatise",
                "title": "De Pictura",
                "chinese_title": "論繪畫",
                "author": "Leon Battista Alberti",
                "publication_date": 1435,
                "significance": "第一部透視法理論著作",
                "key_concepts": ["linear perspective", "mathematical principles"],
            },
        ]

        # === 11. 概念與術語（Concepts/Terms）===
        concepts_data = [
            {
                "category": "Concepts",
                "subcategory": "ArtisticTechnique",
                "name": "Linear Perspective",
                "chinese_name": "線性透視法",
                "italian_term": "prospettiva",
                "inventor": "Filippo Brunelleschi",
                "description": "在二維平面上表現三維空間的數學方法",
                "key_principles": ["vanishing point", "horizon line", "orthogonal lines"],
            },
            {
                "category": "Concepts",
                "subcategory": "ArtisticTechnique",
                "name": "Contrapposto",
                "chinese_name": "對位法",
                "italian_term": "contrapposto",
                "origin": "古希臘雕塑",
                "description": "人體重心偏向一腿的自然姿態",
                "renaissance_revival": "多納泰羅和米開朗基羅的運用",
            },
        ]

        # === 12. 版本/語言（Translations & Terms Mapping）===
        translations_data = [
            {
                "category": "Translations",
                "subcategory": "TermMapping",
                "italian_term": "sfumato",
                "english_term": "sfumato technique",
                "chinese_term": "暈塗法",
                "pronunciation": "sfu-MA-to",
                "literal_meaning": "smoky",
                "art_context": "無邊界色彩過渡技法",
            },
            {
                "category": "Translations",
                "subcategory": "TermMapping",
                "italian_term": "contrapposto",
                "english_term": "contrapposto",
                "chinese_term": "對位法",
                "pronunciation": "kon-tra-POS-to",
                "literal_meaning": "counterpose",
                "art_context": "雕塑人體姿態技法",
            },
            {
                "category": "Translations",
                "subcategory": "TermMapping",
                "italian_term": "chiaroscuro",
                "english_term": "chiaroscuro",
                "chinese_term": "明暗法",
                "pronunciation": "kee-are-uh-SKYOOR-oh",
                "literal_meaning": "light-dark",
                "art_context": "光影對比繪畫技法",
            },
        ]

        # 將所有數據添加到節點列表
        all_data = [
            people_data,
            artworks_data,
            movements_data,
            techniques_data,
            themes_data,
            chronology_data,
            places_data,
            institutions_data,
            events_data,
            sources_data,
            concepts_data,
            translations_data,
        ]

        for data_group in all_data:
            self.nodes.extend(data_group)

    def build_12_category_relationships(self):
        """構建12大分類間的關係"""
        relationships = [
            # 人物 -> 作品關係
            {
                "from": "Leonardo da Vinci",
                "to": "Mona Lisa",
                "type": "CREATED_BY",
                "properties": {"creation_year": 1503},
            },
            {
                "from": "Leonardo da Vinci",
                "to": "The Last Supper",
                "type": "CREATED_BY",
                "properties": {"creation_year": 1495},
            },
            {
                "from": "Michelangelo Buonarroti",
                "to": "David",
                "type": "CREATED_BY",
                "properties": {"creation_year": 1501},
            },
            # 人物 -> 流派關係
            {
                "from": "Leonardo da Vinci",
                "to": "High Renaissance",
                "type": "BELONGS_TO_MOVEMENT",
                "properties": {"role": "founding figure"},
            },
            {
                "from": "Michelangelo Buonarroti",
                "to": "High Renaissance",
                "type": "BELONGS_TO_MOVEMENT",
                "properties": {"role": "master"},
            },
            # 人物 -> 技法關係
            {
                "from": "Leonardo da Vinci",
                "to": "Sfumato",
                "type": "DEVELOPED_TECHNIQUE",
                "properties": {"innovation_level": "inventor"},
            },
            {
                "from": "Leonardo da Vinci",
                "to": "Oil Painting",
                "type": "MASTERED_TECHNIQUE",
                "properties": {"skill_level": "expert"},
            },
            # 作品 -> 技法關係
            {
                "from": "Mona Lisa",
                "to": "Sfumato",
                "type": "DEMONSTRATES_TECHNIQUE",
                "properties": {"prominence": "primary"},
            },
            {
                "from": "The Last Supper",
                "to": "Linear Perspective",
                "type": "DEMONSTRATES_TECHNIQUE",
                "properties": {"innovation": "compositional"},
            },
            # 作品 -> 主題關係
            {
                "from": "The Last Supper",
                "to": "Religious Motif",
                "type": "DEPICTS_THEME",
                "properties": {"theme_type": "Biblical"},
            },
            {
                "from": "Mona Lisa",
                "to": "Portrait",
                "type": "EXEMPLIFIES_GENRE",
                "properties": {"style": "Renaissance portraiture"},
            },
            # 作品 -> 地點關係
            {
                "from": "Mona Lisa",
                "to": "Louvre Museum",
                "type": "HOUSED_IN",
                "properties": {"acquisition_date": "1797"},
            },
            {
                "from": "David",
                "to": "Florence",
                "type": "CREATED_IN",
                "properties": {"original_location": "Palazzo della Signoria"},
            },
            # 人物 -> 機構關係
            {
                "from": "Leonardo da Vinci",
                "to": "Verrocchio's Workshop",
                "type": "APPRENTICED_AT",
                "properties": {"period": "1466-1476"},
            },
            {
                "from": "Michelangelo Buonarroti",
                "to": "Medici Family",
                "type": "PATRONIZED_BY",
                "properties": {"patron": "Lorenzo de Medici"},
            },
            # 人物 -> 地點關係
            {
                "from": "Leonardo da Vinci",
                "to": "Florence",
                "type": "BORN_IN",
                "properties": {"birth_year": 1452},
            },
            {
                "from": "Michelangelo Buonarroti",
                "to": "Rome",
                "type": "WORKED_IN",
                "properties": {"major_period": "1508-1512"},
            },
            # 人物 -> 時間關係
            {
                "from": "Leonardo da Vinci",
                "to": "15th Century",
                "type": "ACTIVE_DURING",
                "properties": {"active_years": "1452-1519"},
            },
            {
                "from": "Lorenzo de Medici",
                "to": "Medici Rule in Florence",
                "type": "REPRESENTS_PERIOD",
                "properties": {"significance": "patron ruler"},
            },
            # 事件 -> 人物關係
            {
                "from": "Sistine Chapel Ceiling Commission",
                "to": "Michelangelo Buonarroti",
                "type": "COMMISSIONED_ARTIST",
                "properties": {"commissioner": "Pope Julius II"},
            },
            {
                "from": "Publication of Vasari's Lives",
                "to": "Giorgio Vasari",
                "type": "AUTHORED_BY",
                "properties": {"publication_year": 1550},
            },
            # 文獻 -> 人物關係
            {
                "from": "Lives of the Most Excellent Painters, Sculptors, and Architects",
                "to": "Giorgio Vasari",
                "type": "WRITTEN_BY",
                "properties": {"genre": "art history"},
            },
            {
                "from": "De Pictura",
                "to": "Leon Battista Alberti",
                "type": "AUTHORED_BY",
                "properties": {"subject": "perspective theory"},
            },
            # 術語翻譯關係
            {
                "from": "sfumato",
                "to": "暈塗法",
                "type": "TRANSLATED_AS",
                "properties": {"language_pair": "Italian-Chinese"},
            },
            {
                "from": "contrapposto",
                "to": "對位法",
                "type": "TRANSLATED_AS",
                "properties": {"language_pair": "Italian-Chinese"},
            },
            {
                "from": "chiaroscuro",
                "to": "明暗法",
                "type": "TRANSLATED_AS",
                "properties": {"language_pair": "Italian-Chinese"},
            },
            # 概念 -> 技法關係
            {
                "from": "Linear Perspective",
                "to": "Oil Painting",
                "type": "ENHANCED_BY",
                "properties": {"improvement": "spatial depth"},
            },
            {
                "from": "Contrapposto",
                "to": "Renaissance sculpture",
                "type": "REVIVED_IN",
                "properties": {"revival_period": "15th century"},
            },
            # 流派 -> 時間關係
            {
                "from": "Early Renaissance",
                "to": "15th Century",
                "type": "OCCURRED_DURING",
                "properties": {"overlap": "majority"},
            },
            {
                "from": "High Renaissance",
                "to": "16th Century",
                "type": "OCCURRED_DURING",
                "properties": {"peak_period": "1495-1520"},
            },
            # 流派 -> 地點關係
            {
                "from": "Early Renaissance",
                "to": "Florence",
                "type": "ORIGINATED_IN",
                "properties": {"starting_point": "1400s"},
            },
            {
                "from": "High Renaissance",
                "to": "Rome",
                "type": "CENTERED_IN",
                "properties": {"papal_patronage": "Julius II, Leo X"},
            },
            # 機構 -> 地點關係
            {
                "from": "Medici Family",
                "to": "Florence",
                "type": "BASED_IN",
                "properties": {"dominance_period": "1434-1737"},
            },
            {
                "from": "Verrocchio's Workshop",
                "to": "Florence",
                "type": "LOCATED_IN",
                "properties": {"district": "Oltrarno"},
            },
        ]

        self.relationships.extend(relationships)

    def generate_12_category_cypher(self) -> list[str]:
        """生成12大分類的Cypher創建語句"""
        cypher_statements = []

        # 清理現有數據
        cypher_statements.append("// === 清理現有數據 ===")
        cypher_statements.append("MATCH (n) DETACH DELETE n")
        cypher_statements.append("")

        # 按分類創建節點
        categories = {}
        for node in self.nodes:
            category = node["category"]
            if category not in categories:
                categories[category] = []
            categories[category].append(node)

        for category, nodes in categories.items():
            cypher_statements.append(f"// === {category} 節點 ===")
            for node in nodes:
                # 構建屬性字符串
                properties = []
                for key, value in node.items():
                    if key not in ["category", "subcategory"]:
                        if isinstance(value, str):
                            properties.append(f'{key}: "{value}"')
                        elif isinstance(value, list):
                            # 將列表轉換為字符串數組
                            list_str = "[" + ", ".join([f'"{item}"' for item in value]) + "]"
                            properties.append(f"{key}: {list_str}")
                        else:
                            properties.append(f"{key}: {value}")

                # 添加分類標籤
                properties.append(f'category: "{node["category"]}"')
                if "subcategory" in node:
                    properties.append(f'subcategory: "{node["subcategory"]}"')

                prop_str = ", ".join(properties)

                # 使用subcategory作為節點標籤，如果沒有則使用category
                label = node.get("subcategory", node["category"])
                cypher_statements.append(f"CREATE (:{label} {{{prop_str}}})")

            cypher_statements.append("")

        # 創建關係
        cypher_statements.append("// === 建立關係 ===")
        for rel in self.relationships:
            # 構建關係屬性
            prop_items = []
            for key, value in rel.get("properties", {}).items():
                if isinstance(value, str):
                    prop_items.append(f'{key}: "{value}"')
                else:
                    prop_items.append(f"{key}: {value}")

            prop_str = "{" + ", ".join(prop_items) + "}" if prop_items else ""

            cypher = f"""MATCH (a), (b)
WHERE (a.name = "{rel["from"]}" OR a.title = "{rel["from"]}")
  AND (b.name = "{rel["to"]}" OR b.title = "{rel["to"]}")
CREATE (a)-[:{rel["type"]} {prop_str}]->(b)"""

            cypher_statements.append(cypher)
            cypher_statements.append("")

        return cypher_statements

    def save_12_category_files(self):
        """保存12大分類文件"""
        # 保存節點數據
        with open("art_history_12_categories_nodes.json", "w", encoding="utf-8") as f:
            json.dump(self.nodes, f, ensure_ascii=False, indent=2)

        # 保存關係數據
        with open("art_history_12_categories_relationships.json", "w", encoding="utf-8") as f:
            json.dump(self.relationships, f, ensure_ascii=False, indent=2)

        # 保存Cypher腳本
        cypher_script = self.generate_12_category_cypher()
        with open("create_12_category_neo4j_graph.cypher", "w", encoding="utf-8") as f:
            for statement in cypher_script:
                f.write(statement + "\n")

        logger.info("✅ 12大分類數據文件已保存")

    def get_category_statistics(self) -> dict[str, int]:
        """獲取分類統計"""
        stats = {}
        for node in self.nodes:
            category = node["category"]
            stats[category] = stats.get(category, 0) + 1
        return stats


def main():
    """主函數"""
    print("🎨 構建12大分類藝術史Neo4j知識圖譜")
    print("=" * 60)

    builder = ArtHistory12CategoryBuilder()

    # 添加數據
    print("📊 添加12大分類數據...")
    builder.add_12_category_data()
    builder.build_12_category_relationships()

    # 統計信息
    stats = builder.get_category_statistics()
    print("\n📈 數據統計:")
    print(f"   總節點數: {len(builder.nodes)}")
    print(f"   總關係數: {len(builder.relationships)}")
    print("\n📋 分類分佈:")
    for category, count in stats.items():
        print(f"   {category}: {count} 個節點")

    # 保存文件
    print("\n💾 保存數據文件...")
    builder.save_12_category_files()

    print("\n✅ 12大分類Neo4j圖譜構建完成！")
    print("📁 生成文件:")
    print("   - art_history_12_categories_nodes.json (節點數據)")
    print("   - art_history_12_categories_relationships.json (關係數據)")
    print("   - create_12_category_neo4j_graph.cypher (Neo4j執行腳本)")
    print("\n🔧 使用方法:")
    print("   在Neo4j Browser中執行: create_12_category_neo4j_graph.cypher")


if __name__ == "__main__":
    main()
