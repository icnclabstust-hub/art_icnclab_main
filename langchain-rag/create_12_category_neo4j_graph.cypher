// === 清理現有數據 ===
MATCH (n) DETACH DELETE n

// === People 節點 ===
CREATE (:Artist {name: "Leonardo da Vinci", full_name: "Leonardo di ser Piero da Vinci", birth_year: 1452, death_year: 1519, nationality: "Italian", birthplace: "Vinci, Republic of Florence", specialization: "Polymath", role: "畫家、發明家、科學家", biography: "文藝復興時期的博學者，在繪畫、雕塑、建築、科學等領域都有傑出貢獻", category: "People", subcategory: "Artist"})
CREATE (:Artist {name: "Michelangelo Buonarroti", birth_year: 1475, death_year: 1564, nationality: "Italian", birthplace: "Caprese, Republic of Florence", specialization: "Sculptor, Painter, Architect", role: "雕塑家、畫家、建築師", biography: "文藝復興盛期最偉大的藝術家之一", category: "People", subcategory: "Artist"})
CREATE (:Patron {name: "Lorenzo de Medici", title: "Lorenzo the Magnificent", birth_year: 1449, death_year: 1492, nationality: "Italian", role: "贊助人、統治者", family: "Medici", patronage_focus: "藝術、文學、哲學", category: "People", subcategory: "Patron"})
CREATE (:Theorist {name: "Giorgio Vasari", birth_year: 1511, death_year: 1574, nationality: "Italian", role: "藝術史家、畫家、建築師", major_work: "Lives of the Most Excellent Painters, Sculptors, and Architects", category: "People", subcategory: "Theorist"})
CREATE (:Collector {name: "Isabella d'Este", birth_year: 1474, death_year: 1539, title: "Marchesa of Mantua", role: "收藏家、贊助人", collection_focus: "文藝復興藝術、古典文物", category: "People", subcategory: "Collector"})

// === Artworks 節點 ===
CREATE (:Painting {title: "Mona Lisa", alternative_titles: "La Gioconda, Portrait of Lisa Gherardini", creation_date: "1503-1519", artist: "Leonardo da Vinci", dimensions: "77 cm × 53 cm", medium: "Oil on poplar panel", description: "神秘微笑的麗莎‧格拉迪尼肖像", significance: "世界最著名的畫作", current_location: "Louvre Museum, Paris", category: "Artworks", subcategory: "Painting"})
CREATE (:Painting {title: "The Last Supper", creation_date: "1495-1498", artist: "Leonardo da Vinci", dimensions: "460 cm × 880 cm", medium: "Tempera and oil on plaster", description: "耶穌與十二門徒的最後晚餐", location: "Santa Maria delle Grazie, Milan", technique_used: "Linear perspective, composition", category: "Artworks", subcategory: "Painting"})
CREATE (:Sculpture {title: "David", creation_date: "1501-1504", artist: "Michelangelo Buonarroti", dimensions: "517 cm height", material: "Carrara marble", description: "準備迎戰歌利亞的大衛", significance: "佛羅倫斯共和國的象徵", current_location: "Galleria dell'Accademia, Florence", category: "Artworks", subcategory: "Sculpture"})
CREATE (:Architecture {title: "Sistine Chapel", construction_date: "1473-1481", architect: "Giovanni dei Dolci", location: "Vatican City", description: "教皇私人小聖堂", famous_for: "米開朗基羅的天頂畫", category: "Artworks", subcategory: "Architecture"})

// === Movements 節點 ===
CREATE (:EarlyRenaissance {name: "Early Renaissance", chinese_name: "早期文藝復興", start_period: 1400, end_period: 1490, origin_location: "Florence, Italy", key_characteristics: "透視法復興、人文主義、古典元素", major_figures: ["Brunelleschi", "Donatello", "Masaccio"], category: "Movements", subcategory: "EarlyRenaissance"})
CREATE (:HighRenaissance {name: "High Renaissance", chinese_name: "盛期文藝復興", start_period: 1495, end_period: 1520, origin_location: "Rome, Florence", key_characteristics: "完美平衡、理想化美感、數學精確性", major_figures: ["Leonardo da Vinci", "Michelangelo", "Raphael"], category: "Movements", subcategory: "HighRenaissance"})
CREATE (:Mannerism {name: "Mannerism", chinese_name: "曼納主義", start_period: 1520, end_period: 1600, key_characteristics: "誇張比例、複雜姿態、人工色彩", reaction_to: "High Renaissance perfection", category: "Movements", subcategory: "Mannerism"})

// === Techniques 節點 ===
CREATE (:OilPainting {name: "Oil Painting", chinese_name: "油畫技法", description: "使用油性顏料的繪畫技法", materials: ["oil binder", "pigments", "canvas or wood panel"], advantages: "緩慢乾燥、易於混合、色彩豐富", notable_practitioners: ["Jan van Eyck", "Leonardo da Vinci"], category: "Techniques", subcategory: "OilPainting"})
CREATE (:Fresco {name: "Fresco", chinese_name: "濕壁畫", description: "在濕石灰牆面上繪製的技法", process: "在石灰砂漿未乾時作畫", advantages: "持久性、與牆面結合", notable_examples: ["Sistine Chapel Ceiling", "School of Athens"], category: "Techniques", subcategory: "Fresco"})
CREATE (:Sfumato {name: "Sfumato", chinese_name: "暈塗法", italian_term: "sfumato", literal_meaning: "smoky", description: "無線條邊界的微妙色彩過渡技法", inventor: "Leonardo da Vinci", visual_effect: "煙霧般的柔和過渡", category: "Techniques", subcategory: "Sfumato"})

// === Themes 節點 ===
CREATE (:ReligiousMotif {name: "Annunciation", chinese_name: "天使報喜", description: "天使加百列向聖母瑪利亞報告聖子降生", religious_tradition: "Christianity", symbolic_elements: ["lily (purity)", "dove (Holy Spirit)", "book (Word of God)"], common_compositions: "天使左側，聖母右側", category: "Themes", subcategory: "ReligiousMotif"})
CREATE (:Mythology {name: "Venus and Mars", chinese_name: "維納斯與馬爾斯", origin: "Roman mythology", symbolism: "愛情征服戰爭", famous_examples: ["Botticelli's Venus and Mars"], category: "Themes", subcategory: "Mythology"})
CREATE (:Portrait {name: "Portrait painting", chinese_name: "肖像畫", description: "個人形象的藝術表現", evolution: "從中世紀宗教背景到文藝復興個人主義", types: ["individual", "group", "self-portrait"], category: "Themes", subcategory: "Portrait"})

// === Chronology 節點 ===
CREATE (:MediciPeriod {name: "Medici Rule in Florence", chinese_name: "美第奇家族統治期", start_year: 1434, end_year: 1737, key_rulers: ["Cosimo the Elder", "Lorenzo the Magnificent", "Cosimo I"], cultural_impact: "文藝復興的重要贊助者", patronage_style: "人文主義、古典復興", category: "Chronology", subcategory: "MediciPeriod"})
CREATE (:Century {name: "15th Century", chinese_name: "15世紀", start_year: 1401, end_year: 1500, art_historical_period: "Early Renaissance", major_developments: ["透視法發明", "人文主義興起", "古典藝術復興"], category: "Chronology", subcategory: "Century"})
CREATE (:Century {name: "16th Century", chinese_name: "16世紀", start_year: 1501, end_year: 1600, art_historical_period: "High Renaissance to Mannerism", major_developments: ["藝術巔峰期", "曼納主義興起", "宗教改革影響"], category: "Chronology", subcategory: "Century"})

// === Places 節點 ===
CREATE (:City {name: "Florence", chinese_name: "佛羅倫斯", country: "Italy", region: "Tuscany", cultural_significance: "文藝復興發源地", artistic_importance: "早期文藝復興中心", notable_sites: ["Uffizi Gallery", "Palazzo Pitti", "Duomo"], ruling_family: "Medici", category: "Places", subcategory: "City"})
CREATE (:City {name: "Rome", chinese_name: "羅馬", country: "Italy", region: "Lazio", cultural_significance: "盛期文藝復興中心", artistic_importance: "教皇贊助的藝術中心", notable_sites: ["Vatican Museums", "Sistine Chapel", "St. Peter's Basilica"], category: "Places", subcategory: "City"})
CREATE (:Museum {name: "Louvre Museum", chinese_name: "羅浮宮", location: "Paris, France", founded_year: 1793, type: "Art museum", notable_collections: ["Mona Lisa", "Venus de Milo"], annual_visitors: 9600000, category: "Places", subcategory: "Museum"})

// === Institutions 節點 ===
CREATE (:PatronageFamily {name: "Medici Family", chinese_name: "美第奇家族", location: "Florence", active_period: "1434-1737", type: "Banking and ruling family", supported_artists: ["Michelangelo", "Botticelli", "Donatello"], cultural_contribution: "文藝復興主要推動者", category: "Institutions", subcategory: "PatronageFamily"})
CREATE (:Workshop {name: "Verrocchio's Workshop", chinese_name: "韋羅基奧工坊", master: "Andrea del Verrocchio", location: "Florence", active_period: "1460-1488", notable_apprentices: ["Leonardo da Vinci", "Lorenzo di Credi"], specialization: "繪畫、雕塑教學", category: "Institutions", subcategory: "Workshop"})

// === Events 節點 ===
CREATE (:Commission {name: "Sistine Chapel Ceiling Commission", chinese_name: "西斯廷禮拜堂天頂委託", commissioner: "Pope Julius II", artist: "Michelangelo", commission_date: 1508, completion_date: 1512, significance: "盛期文藝復興巔峰作品", payment: "3000 ducats", category: "Events", subcategory: "Commission"})
CREATE (:Publication {name: "Publication of Vasari's Lives", chinese_name: "瓦薩里《名人傳》出版", author: "Giorgio Vasari", first_edition: 1550, second_edition: 1568, significance: "第一部藝術史著作", category: "Events", subcategory: "Publication"})

// === Sources 節點 ===
CREATE (:PrimarySource {title: "Lives of the Most Excellent Painters, Sculptors, and Architects", chinese_title: "最傑出的畫家、雕塑家和建築師的生平", author: "Giorgio Vasari", publication_date: "1550, 1568", language: "Italian", significance: "第一部系統性藝術史著作", coverage: "13-16世紀義大利藝術家", category: "Sources", subcategory: "PrimarySource"})
CREATE (:Treatise {title: "De Pictura", chinese_title: "論繪畫", author: "Leon Battista Alberti", publication_date: 1435, significance: "第一部透視法理論著作", key_concepts: ["linear perspective", "mathematical principles"], category: "Sources", subcategory: "Treatise"})

// === Concepts 節點 ===
CREATE (:ArtisticTechnique {name: "Linear Perspective", chinese_name: "線性透視法", italian_term: "prospettiva", inventor: "Filippo Brunelleschi", description: "在二維平面上表現三維空間的數學方法", key_principles: ["vanishing point", "horizon line", "orthogonal lines"], category: "Concepts", subcategory: "ArtisticTechnique"})
CREATE (:ArtisticTechnique {name: "Contrapposto", chinese_name: "對位法", italian_term: "contrapposto", origin: "古希臘雕塑", description: "人體重心偏向一腿的自然姿態", renaissance_revival: "多納泰羅和米開朗基羅的運用", category: "Concepts", subcategory: "ArtisticTechnique"})

// === Translations 節點 ===
CREATE (:TermMapping {italian_term: "sfumato", english_term: "sfumato technique", chinese_term: "暈塗法", pronunciation: "sfu-MA-to", literal_meaning: "smoky", art_context: "無邊界色彩過渡技法", category: "Translations", subcategory: "TermMapping"})
CREATE (:TermMapping {italian_term: "contrapposto", english_term: "contrapposto", chinese_term: "對位法", pronunciation: "kon-tra-POS-to", literal_meaning: "counterpose", art_context: "雕塑人體姿態技法", category: "Translations", subcategory: "TermMapping"})
CREATE (:TermMapping {italian_term: "chiaroscuro", english_term: "chiaroscuro", chinese_term: "明暗法", pronunciation: "kee-are-uh-SKYOOR-oh", literal_meaning: "light-dark", art_context: "光影對比繪畫技法", category: "Translations", subcategory: "TermMapping"})

// === 建立關係 ===
MATCH (a), (b)
WHERE (a.name = "Leonardo da Vinci" OR a.title = "Leonardo da Vinci")
  AND (b.name = "Mona Lisa" OR b.title = "Mona Lisa")
CREATE (a)-[:CREATED_BY {creation_year: 1503}]->(b)

MATCH (a), (b)
WHERE (a.name = "Leonardo da Vinci" OR a.title = "Leonardo da Vinci")
  AND (b.name = "The Last Supper" OR b.title = "The Last Supper")
CREATE (a)-[:CREATED_BY {creation_year: 1495}]->(b)

MATCH (a), (b)
WHERE (a.name = "Michelangelo Buonarroti" OR a.title = "Michelangelo Buonarroti")
  AND (b.name = "David" OR b.title = "David")
CREATE (a)-[:CREATED_BY {creation_year: 1501}]->(b)

MATCH (a), (b)
WHERE (a.name = "Leonardo da Vinci" OR a.title = "Leonardo da Vinci")
  AND (b.name = "High Renaissance" OR b.title = "High Renaissance")
CREATE (a)-[:BELONGS_TO_MOVEMENT {role: "founding figure"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Michelangelo Buonarroti" OR a.title = "Michelangelo Buonarroti")
  AND (b.name = "High Renaissance" OR b.title = "High Renaissance")
CREATE (a)-[:BELONGS_TO_MOVEMENT {role: "master"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Leonardo da Vinci" OR a.title = "Leonardo da Vinci")
  AND (b.name = "Sfumato" OR b.title = "Sfumato")
CREATE (a)-[:DEVELOPED_TECHNIQUE {innovation_level: "inventor"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Leonardo da Vinci" OR a.title = "Leonardo da Vinci")
  AND (b.name = "Oil Painting" OR b.title = "Oil Painting")
CREATE (a)-[:MASTERED_TECHNIQUE {skill_level: "expert"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Mona Lisa" OR a.title = "Mona Lisa")
  AND (b.name = "Sfumato" OR b.title = "Sfumato")
CREATE (a)-[:DEMONSTRATES_TECHNIQUE {prominence: "primary"}]->(b)

MATCH (a), (b)
WHERE (a.name = "The Last Supper" OR a.title = "The Last Supper")
  AND (b.name = "Linear Perspective" OR b.title = "Linear Perspective")
CREATE (a)-[:DEMONSTRATES_TECHNIQUE {innovation: "compositional"}]->(b)

MATCH (a), (b)
WHERE (a.name = "The Last Supper" OR a.title = "The Last Supper")
  AND (b.name = "Religious Motif" OR b.title = "Religious Motif")
CREATE (a)-[:DEPICTS_THEME {theme_type: "Biblical"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Mona Lisa" OR a.title = "Mona Lisa")
  AND (b.name = "Portrait" OR b.title = "Portrait")
CREATE (a)-[:EXEMPLIFIES_GENRE {style: "Renaissance portraiture"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Mona Lisa" OR a.title = "Mona Lisa")
  AND (b.name = "Louvre Museum" OR b.title = "Louvre Museum")
CREATE (a)-[:HOUSED_IN {acquisition_date: "1797"}]->(b)

MATCH (a), (b)
WHERE (a.name = "David" OR a.title = "David")
  AND (b.name = "Florence" OR b.title = "Florence")
CREATE (a)-[:CREATED_IN {original_location: "Palazzo della Signoria"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Leonardo da Vinci" OR a.title = "Leonardo da Vinci")
  AND (b.name = "Verrocchio's Workshop" OR b.title = "Verrocchio's Workshop")
CREATE (a)-[:APPRENTICED_AT {period: "1466-1476"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Michelangelo Buonarroti" OR a.title = "Michelangelo Buonarroti")
  AND (b.name = "Medici Family" OR b.title = "Medici Family")
CREATE (a)-[:PATRONIZED_BY {patron: "Lorenzo de Medici"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Leonardo da Vinci" OR a.title = "Leonardo da Vinci")
  AND (b.name = "Florence" OR b.title = "Florence")
CREATE (a)-[:BORN_IN {birth_year: 1452}]->(b)

MATCH (a), (b)
WHERE (a.name = "Michelangelo Buonarroti" OR a.title = "Michelangelo Buonarroti")
  AND (b.name = "Rome" OR b.title = "Rome")
CREATE (a)-[:WORKED_IN {major_period: "1508-1512"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Leonardo da Vinci" OR a.title = "Leonardo da Vinci")
  AND (b.name = "15th Century" OR b.title = "15th Century")
CREATE (a)-[:ACTIVE_DURING {active_years: "1452-1519"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Lorenzo de Medici" OR a.title = "Lorenzo de Medici")
  AND (b.name = "Medici Rule in Florence" OR b.title = "Medici Rule in Florence")
CREATE (a)-[:REPRESENTS_PERIOD {significance: "patron ruler"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Sistine Chapel Ceiling Commission" OR a.title = "Sistine Chapel Ceiling Commission")
  AND (b.name = "Michelangelo Buonarroti" OR b.title = "Michelangelo Buonarroti")
CREATE (a)-[:COMMISSIONED_ARTIST {commissioner: "Pope Julius II"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Publication of Vasari's Lives" OR a.title = "Publication of Vasari's Lives")
  AND (b.name = "Giorgio Vasari" OR b.title = "Giorgio Vasari")
CREATE (a)-[:AUTHORED_BY {publication_year: 1550}]->(b)

MATCH (a), (b)
WHERE (a.name = "Lives of the Most Excellent Painters, Sculptors, and Architects" OR a.title = "Lives of the Most Excellent Painters, Sculptors, and Architects")
  AND (b.name = "Giorgio Vasari" OR b.title = "Giorgio Vasari")
CREATE (a)-[:WRITTEN_BY {genre: "art history"}]->(b)

MATCH (a), (b)
WHERE (a.name = "De Pictura" OR a.title = "De Pictura")
  AND (b.name = "Leon Battista Alberti" OR b.title = "Leon Battista Alberti")
CREATE (a)-[:AUTHORED_BY {subject: "perspective theory"}]->(b)

MATCH (a), (b)
WHERE (a.name = "sfumato" OR a.title = "sfumato")
  AND (b.name = "暈塗法" OR b.title = "暈塗法")
CREATE (a)-[:TRANSLATED_AS {language_pair: "Italian-Chinese"}]->(b)

MATCH (a), (b)
WHERE (a.name = "contrapposto" OR a.title = "contrapposto")
  AND (b.name = "對位法" OR b.title = "對位法")
CREATE (a)-[:TRANSLATED_AS {language_pair: "Italian-Chinese"}]->(b)

MATCH (a), (b)
WHERE (a.name = "chiaroscuro" OR a.title = "chiaroscuro")
  AND (b.name = "明暗法" OR b.title = "明暗法")
CREATE (a)-[:TRANSLATED_AS {language_pair: "Italian-Chinese"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Linear Perspective" OR a.title = "Linear Perspective")
  AND (b.name = "Oil Painting" OR b.title = "Oil Painting")
CREATE (a)-[:ENHANCED_BY {improvement: "spatial depth"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Contrapposto" OR a.title = "Contrapposto")
  AND (b.name = "Renaissance sculpture" OR b.title = "Renaissance sculpture")
CREATE (a)-[:REVIVED_IN {revival_period: "15th century"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Early Renaissance" OR a.title = "Early Renaissance")
  AND (b.name = "15th Century" OR b.title = "15th Century")
CREATE (a)-[:OCCURRED_DURING {overlap: "majority"}]->(b)

MATCH (a), (b)
WHERE (a.name = "High Renaissance" OR a.title = "High Renaissance")
  AND (b.name = "16th Century" OR b.title = "16th Century")
CREATE (a)-[:OCCURRED_DURING {peak_period: "1495-1520"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Early Renaissance" OR a.title = "Early Renaissance")
  AND (b.name = "Florence" OR b.title = "Florence")
CREATE (a)-[:ORIGINATED_IN {starting_point: "1400s"}]->(b)

MATCH (a), (b)
WHERE (a.name = "High Renaissance" OR a.title = "High Renaissance")
  AND (b.name = "Rome" OR b.title = "Rome")
CREATE (a)-[:CENTERED_IN {papal_patronage: "Julius II, Leo X"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Medici Family" OR a.title = "Medici Family")
  AND (b.name = "Florence" OR b.title = "Florence")
CREATE (a)-[:BASED_IN {dominance_period: "1434-1737"}]->(b)

MATCH (a), (b)
WHERE (a.name = "Verrocchio's Workshop" OR a.title = "Verrocchio's Workshop")
  AND (b.name = "Florence" OR b.title = "Florence")
CREATE (a)-[:LOCATED_IN {district: "Oltrarno"}]->(b)

