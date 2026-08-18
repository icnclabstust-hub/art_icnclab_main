#!/usr/bin/env python3
"""
GraphRAG模型創建器
創建完整的GraphRAG整合，結合Neo4j知識圖譜和OpenWebUI
"""

import logging
import sys
import time
from typing import Any

try:
    import uvicorn
    from fastapi import FastAPI, HTTPException
    from neo4j import GraphDatabase
    from pydantic import BaseModel
except ImportError as e:
    print(f"❌ 缺少依賴: {e}")
    print("請運行: pip install neo4j fastapi uvicorn")
    sys.exit(1)


class GraphRAGQuery(BaseModel):
    """GraphRAG查詢請求模型"""

    question: str
    max_nodes: int = 50
    max_relationships: int = 100
    query_type: str = "hybrid"  # vector, graph, hybrid


class GraphRAGResponse(BaseModel):
    """GraphRAG響應模型"""

    answer: str
    graph_results: list[dict]
    vector_results: list[dict]
    cypher_query: str
    processing_time: float
    query_type: str


class Neo4jGraphRAG:
    """Neo4j GraphRAG系統"""

    def __init__(
        self,
        uri="bolt://localhost:7687",
        username="neo4j",
        password="CHANGE_ME_NEO4J_PASSWORD",  # noqa: S107 -- 佔位字串，非真實密碼
    ):
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None
        self.connect()

    def connect(self):
        """連接到Neo4j"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            logging.info("✅ GraphRAG已連接到Neo4j")
        except Exception as e:
            logging.error(f"❌ GraphRAG連接Neo4j失敗: {e}")

    def close(self):
        """關閉連接"""
        if self.driver:
            self.driver.close()

    def analyze_question(self, question: str) -> dict[str, Any]:
        """分析問題類型和關鍵實體 - 基於12大分類"""
        question_lower = question.lower()

        analysis = {
            "entities": [],
            "relationships": [],
            "query_intent": "general",
            "categories": [],
        }

        # 12大分類關鍵詞檢測
        category_keywords = {
            "People": [
                "藝術家",
                "達文西",
                "米開朗基羅",
                "拉斐爾",
                "leonardo",
                "michelangelo",
                "raphael",
                "artist",
                "painter",
                "sculptor",
            ],
            "Artworks": [
                "作品",
                "繪畫",
                "雕塑",
                "蒙娜麗莎",
                "painting",
                "sculpture",
                "artwork",
                "mona lisa",
                "david",
            ],
            "Movements": [
                "文藝復興",
                "巴洛克",
                "曼納主義",
                "renaissance",
                "baroque",
                "mannerism",
                "movement",
                "style",
            ],
            "Techniques": [
                "技法",
                "油彩",
                "濕壁畫",
                "暈塗法",
                "technique",
                "oil painting",
                "fresco",
                "sfumato",
            ],
            "Themes": [
                "主題",
                "宗教",
                "神話",
                "肖像",
                "theme",
                "religious",
                "mythology",
                "portrait",
            ],
            "Chronology": [
                "時期",
                "世紀",
                "美第奇",
                "period",
                "century",
                "medici",
                "renaissance period",
            ],
            "Places": [
                "佛羅倫斯",
                "羅馬",
                "巴黎",
                "博物館",
                "florence",
                "rome",
                "paris",
                "museum",
                "gallery",
            ],
            "Institutions": ["學院", "工坊", "家族", "academy", "workshop", "family", "guild"],
            "Events": ["委託", "展覽", "修復", "commission", "exhibition", "restoration"],
            "Sources": ["文獻", "瓦薩里", "研究", "vasari", "source", "document", "research"],
            "Concepts": ["透視", "對位法", "明暗法", "perspective", "contrapposto", "chiaroscuro"],
            "Translations": [
                "義大利語",
                "英文",
                "中文",
                "italian",
                "english",
                "chinese",
                "translation",
            ],
        }

        # 檢測分類
        for category, keywords in category_keywords.items():
            if any(keyword in question_lower for keyword in keywords):
                analysis["categories"].append(category)

        # 檢測藝術家名稱（擴展）
        famous_artists = [
            "leonardo",
            "da vinci",
            "michelangelo",
            "raphael",
            "donatello",
            "botticelli",
            "brunelleschi",
            "ghiberti",
            "masaccio",
            "piero della francesca",
            "mantegna",
            "bellini",
            "giorgione",
            "titian",
            "tintoretto",
            "veronese",
            "caravaggio",
        ]
        for artist in famous_artists:
            if artist in question_lower:
                analysis["entities"].append({"type": "Artist", "name": artist.title()})

        # 檢測作品名稱
        famous_works = {
            "mona lisa": "Mona Lisa",
            "last supper": "The Last Supper",
            "david": "David",
            "sistine chapel": "Sistine Chapel Ceiling",
            "creation of adam": "Creation of Adam",
            "school of athens": "School of Athens",
            "primavera": "Primavera",
            "birth of venus": "Birth of Venus",
        }
        for work_key, work_name in famous_works.items():
            if work_key in question_lower:
                analysis["entities"].append({"type": "Artwork", "name": work_name})

        # 檢測技法概念
        techniques = {
            "sfumato": "Sfumato",
            "chiaroscuro": "Chiaroscuro",
            "contrapposto": "Contrapposto",
            "perspective": "Linear Perspective",
            "oil painting": "Oil Painting",
            "fresco": "Fresco",
            "tempera": "Tempera",
        }
        for tech_key, tech_name in techniques.items():
            if tech_key in question_lower:
                analysis["entities"].append({"type": "Technique", "name": tech_name})

        # 檢測地點
        places = {
            "florence": "Florence",
            "rome": "Rome",
            "venice": "Venice",
            "milan": "Milan",
            "vatican": "Vatican",
            "louvre": "Louvre Museum",
            "uffizi": "Uffizi Gallery",
        }
        for place_key, place_name in places.items():
            if place_key in question_lower:
                analysis["entities"].append({"type": "Place", "name": place_name})

        # 確定查詢意圖（12大分類導向）
        if any(
            word in question_lower
            for word in ["創作", "製作", "誰畫", "created", "painted", "made"]
        ):
            analysis["query_intent"] = "creation"
        elif any(
            word in question_lower for word in ["影響", "師從", "influenced", "taught", "inspired"]
        ):
            analysis["query_intent"] = "influence"
        elif any(
            word in question_lower
            for word in ["收藏", "博物館", "在哪", "housed", "museum", "where"]
        ):
            analysis["query_intent"] = "collection"
        elif any(
            word in question_lower
            for word in ["技法", "方法", "如何", "technique", "method", "how"]
        ):
            analysis["query_intent"] = "technique"
        elif any(
            word in question_lower
            for word in ["時期", "年代", "什麼時候", "period", "when", "date"]
        ):
            analysis["query_intent"] = "temporal"
        elif any(
            word in question_lower for word in ["地點", "位置", "城市", "location", "place", "city"]
        ):
            analysis["query_intent"] = "geographic"
        elif any(
            word in question_lower
            for word in ["主題", "描繪", "象徵", "theme", "depicts", "symbolizes"]
        ):
            analysis["query_intent"] = "thematic"
        elif any(
            word in question_lower
            for word in ["翻譯", "中文", "英文", "意思", "translation", "meaning"]
        ):
            analysis["query_intent"] = "terminology"
        elif any(
            word in question_lower
            for word in ["關係", "連結", "相關", "relationship", "connection", "related"]
        ):
            analysis["query_intent"] = "relationship"
        else:
            analysis["query_intent"] = "general"

        return analysis

    def generate_cypher_query(self, analysis: dict[str, Any], max_nodes: int = 50) -> str:
        """根據分析生成Cypher查詢"""
        intent = analysis["query_intent"]
        entities = analysis["entities"]

        if intent == "relationship" and entities:
            # 查詢實體之間的關係
            entity_patterns = []
            for entity in entities:
                entity_patterns.append(
                    f"(n:{entity['type']} {{name: CONTAINS '{entity['name']}'}}))"
                )

            if len(entity_patterns) >= 2:
                return f"""
                MATCH {entity_patterns[0]}-[r]-{entity_patterns[1]}
                RETURN n1.name as entity1, type(r) as relationship, n2.name as entity2
                LIMIT {max_nodes}
                """

        elif intent == "creation":
            # 查詢創作關係
            if entities and entities[0]["type"] == "Artist":
                artist_name = entities[0]["name"]
                return f"""
                MATCH (a:Artist)-[:CREATED]->(w:Artwork)
                WHERE a.name CONTAINS '{artist_name}'
                RETURN a.name as artist, w.title as artwork, w.date as date, w.medium as medium
                LIMIT {max_nodes}
                """

        elif intent == "collection":
            # 查詢博物館收藏
            if entities and entities[0]["type"] == "Museum":
                museum_name = entities[0]["name"]
                return f"""
                MATCH (m:Museum)-[:HOUSES]->(w:Artwork)<-[:CREATED]-(a:Artist)
                WHERE m.name CONTAINS '{museum_name}'
                RETURN m.name as museum, w.title as artwork, a.name as artist
                LIMIT {max_nodes}
                """

        elif intent == "classification":
            # 查詢風格分類
            return f"""
            MATCH (w:Artwork)
            WHERE w.classification IS NOT NULL OR w.culture IS NOT NULL
            RETURN w.title as artwork, w.classification as style,
                   w.culture as culture, w.date as period
            LIMIT {max_nodes}
            """

        # 默認查詢
        return f"""
        MATCH (n)-[r]->(m)
        RETURN labels(n)[0] as from_type, n.name as from_name, type(r) as relationship,
               labels(m)[0] as to_type, m.name as to_name
        LIMIT {max_nodes}
        """

    def execute_graph_query(self, cypher_query: str) -> list[dict]:
        """執行圖譜查詢"""
        if not self.driver:
            return []

        try:
            with self.driver.session() as session:
                result = session.run(cypher_query)
                return [record.data() for record in result]
        except Exception as e:
            logging.error(f"❌ 執行Cypher查詢失敗: {e}")
            return []

    def format_graph_results(self, results: list[dict], analysis: dict[str, Any]) -> str:
        """格式化圖譜查詢結果"""
        if not results:
            return "沒有找到相關的圖譜數據。"

        intent = analysis["query_intent"]

        if intent == "creation":
            formatted = "🎨 **藝術家創作關係:**\n\n"
            for result in results[:10]:
                artist = result.get("artist", "Unknown")
                artwork = result.get("artwork", "Unknown")
                date = result.get("date", "")
                medium = result.get("medium", "")
                formatted += f"- **{artist}** 創作了 **{artwork}**"
                if date:
                    formatted += f" ({date})"
                if medium:
                    formatted += f" - {medium}"
                formatted += "\n"

        elif intent == "collection":
            formatted = "🏛️ **博物館收藏:**\n\n"
            for result in results[:10]:
                museum = result.get("museum", "Unknown")
                artwork = result.get("artwork", "Unknown")
                artist = result.get("artist", "Unknown")
                formatted += f"- **{museum}** 收藏 **{artwork}** (by {artist})\n"

        elif intent == "relationship":
            formatted = "🔗 **關係網絡:**\n\n"
            for result in results[:10]:
                entity1 = result.get("entity1", result.get("from_name", "Unknown"))
                relationship = result.get("relationship", "RELATED")
                entity2 = result.get("entity2", result.get("to_name", "Unknown"))
                formatted += f"- **{entity1}** → {relationship} → **{entity2}**\n"

        else:
            formatted = "📊 **圖譜數據:**\n\n"
            for result in results[:10]:
                formatted += f"- {result}\n"

        return formatted

    def query(self, question: str, max_nodes: int = 50) -> GraphRAGResponse:
        """執行GraphRAG查詢"""
        start_time = time.time()

        # 分析問題
        analysis = self.analyze_question(question)

        # 生成並執行Cypher查詢
        cypher_query = self.generate_cypher_query(analysis, max_nodes)
        graph_results = self.execute_graph_query(cypher_query)

        # 格式化結果
        graph_answer = self.format_graph_results(graph_results, analysis)

        processing_time = time.time() - start_time

        return GraphRAGResponse(
            answer=graph_answer,
            graph_results=graph_results,
            vector_results=[],  # 可以後續整合向量搜索
            cypher_query=cypher_query,
            processing_time=processing_time,
            query_type="graph",
        )


# 創建FastAPI應用
app = FastAPI(title="GraphRAG API", description="Neo4j藝術史知識圖譜API")

# 初始化GraphRAG系統
graph_rag = Neo4jGraphRAG()


@app.post("/graphrag/query", response_model=GraphRAGResponse)
async def query_graphrag(query: GraphRAGQuery):
    """GraphRAG查詢端點"""
    try:
        result = graph_rag.query(query.question, query.max_nodes)
        return result
    except Exception as e:
        # S-14：例外原文只進 log，不回前端；B904：from e 保留例外鏈
        logging.error(f"GraphRAG查詢失敗: {e}")
        raise HTTPException(status_code=500, detail="GraphRAG查詢失敗") from e


@app.get("/graphrag/health")
async def health_check():
    """健康檢查"""
    return {"status": "healthy", "service": "GraphRAG API"}


@app.get("/graphrag/stats")
async def get_graph_stats():
    """獲取圖譜統計信息"""
    try:
        stats_query = """
        MATCH (n)
        RETURN labels(n)[0] as node_type, count(n) as count
        ORDER BY count DESC
        """
        stats = graph_rag.execute_graph_query(stats_query)

        relationships_query = """
        MATCH ()-[r]->()
        RETURN type(r) as relationship_type, count(r) as count
        ORDER BY count DESC
        """
        relationships = graph_rag.execute_graph_query(relationships_query)

        return {"nodes": stats, "relationships": relationships}
    except Exception as e:
        logging.error(f"獲取統計信息失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取統計信息失敗") from e


def main():
    """主函數"""
    logging.basicConfig(level=logging.INFO)

    print("🚀 啟動GraphRAG API服務...")
    print("📊 Neo4j知識圖譜API")
    print("🔗 API文檔: http://localhost:8010/docs")
    print("=" * 60)

    # 測試GraphRAG功能
    print("🧪 測試GraphRAG功能...")

    test_queries = [
        "Leonardo da Vinci創作了哪些著名作品？",
        "Harvard Art Museums有哪些收藏？",
        "文藝復興時期有哪些藝術家？",
    ]

    for query in test_queries:
        print(f"\n🔍 測試查詢: {query}")
        result = graph_rag.query(query)
        print(f"📝 生成的Cypher: {result.cypher_query.strip()}")
        print(f"📊 結果數量: {len(result.graph_results)}")
        print(f"⏱️ 處理時間: {result.processing_time:.3f}s")
        if result.graph_results:
            print(f"📋 示例結果: {result.graph_results[0]}")

    print("\n✅ GraphRAG測試完成！")
    print("🚀 啟動API服務在端口8010...")

    # 啟動API服務
    uvicorn.run(app, host="127.0.0.1", port=8010, log_level="info")


if __name__ == "__main__":
    main()
