#!/usr/bin/env python3
"""
知識圖譜增強RAG系統
整合Neo4j知識圖譜與向量檢索，提供結構化關係推理能力
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

from art_history_knowledge_graph import ArtHistoryKnowledgeGraphSchema
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from multimodal_rag import MultimodalRetriever
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


@dataclass
class GraphQueryResult:
    """圖查詢結果"""

    entities: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    paths: list[list[dict[str, Any]]]
    cypher_query: str
    execution_time: float


class Neo4jArtHistoryGraph:
    """藝術史Neo4j圖譜管理器"""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "CHANGE_ME_NEO4J_PASSWORD",  # noqa: S107 -- 佔位字串，非真實密碼
    ):
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None
        self.schema = ArtHistoryKnowledgeGraphSchema()

    def connect(self):
        """連接Neo4j數據庫"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            # 測試連接
            with self.driver.session() as session:
                session.run("RETURN 'connection successful' AS message")
                logger.info("✅ Neo4j連接成功")
                return True
        except Exception as e:
            logger.error(f"❌ Neo4j連接失敗: {e}")
            return False

    def close(self):
        """關閉數據庫連接"""
        if self.driver:
            self.driver.close()

    def create_schema(self):
        """創建圖譜架構"""
        if not self.driver:
            raise Exception("請先連接數據庫")

        with self.driver.session() as session:
            # 創建約束和索引
            schema_statements = self.schema.get_cypher_schema_creation()
            for statement in schema_statements:
                try:
                    session.run(statement)
                    logger.info(f"✅ 執行架構語句: {statement[:50]}...")
                except Exception as e:
                    logger.warning(f"⚠️ 架構語句執行警告: {e}")

    def populate_sample_data(self):
        """填充示例數據"""
        if not self.driver:
            raise Exception("請先連接數據庫")

        with self.driver.session() as session:
            sample_statements = self.schema.get_sample_data_cypher()
            for statement in sample_statements:
                try:
                    session.run(statement.strip())
                    logger.info("✅ 創建示例數據")
                except Exception as e:
                    logger.warning(f"⚠️ 示例數據創建警告: {e}")

    def execute_cypher(self, query: str, parameters: dict = None) -> GraphQueryResult:
        """執行Cypher查詢"""
        if not self.driver:
            raise Exception("請先連接數據庫")

        start_time = time.time()
        entities = []
        relationships = []
        paths = []

        with self.driver.session() as session:
            try:
                result = session.run(query, parameters or {})

                for record in result:
                    # 處理節點
                    for _key, value in record.items():
                        if hasattr(value, "labels"):  # 這是一個節點
                            entities.append(
                                {
                                    "id": value.id,
                                    "labels": list(value.labels),
                                    "properties": dict(value.items()),
                                }
                            )
                        elif hasattr(value, "type"):  # 這是一個關係
                            relationships.append(
                                {
                                    "id": value.id,
                                    "type": value.type,
                                    "start_node": value.start_node.id,
                                    "end_node": value.end_node.id,
                                    "properties": dict(value.items()),
                                }
                            )
                        elif isinstance(value, list):  # 可能是路徑
                            path_elements = []
                            for element in value:
                                if hasattr(element, "labels"):
                                    path_elements.append(
                                        {
                                            "type": "node",
                                            "labels": list(element.labels),
                                            "properties": dict(element.items()),
                                        }
                                    )
                                elif hasattr(element, "type"):
                                    path_elements.append(
                                        {
                                            "type": "relationship",
                                            "rel_type": element.type,
                                            "properties": dict(element.items()),
                                        }
                                    )
                            if path_elements:
                                paths.append(path_elements)

                execution_time = time.time() - start_time

                return GraphQueryResult(
                    entities=entities,
                    relationships=relationships,
                    paths=paths,
                    cypher_query=query,
                    execution_time=execution_time,
                )

            except Exception as e:
                logger.error(f"❌ Cypher查詢執行失敗: {e}")
                raise


class ArtHistoryGraphRetriever(BaseRetriever):
    """藝術史圖譜檢索器"""

    def __init__(self, graph: Neo4jArtHistoryGraph, **kwargs):
        super().__init__(**kwargs)
        self.graph = graph

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        """根據查詢獲取相關文檔"""
        # 解析查詢意圖
        query_intent = self._analyze_query_intent(query)

        # 生成Cypher查詢
        cypher_query = self._generate_cypher_query(query, query_intent)

        # 執行圖查詢
        graph_result = self.graph.execute_cypher(cypher_query)

        # 轉換為文檔
        documents = self._convert_graph_result_to_documents(graph_result, query)

        return documents

    def _analyze_query_intent(self, query: str) -> dict[str, Any]:
        """分析查詢意圖"""
        intent = {"query_type": "general", "entities": [], "relationships": [], "focus": None}

        query_lower = query.lower()

        # 藝術家相關查詢
        if any(word in query_lower for word in ["藝術家", "畫家", "雕塑家", "artist", "painter"]):
            intent["query_type"] = "artist_focused"
            intent["focus"] = "Artist"

        # 作品相關查詢
        elif any(word in query_lower for word in ["作品", "畫作", "雕塑", "artwork", "painting"]):
            intent["query_type"] = "artwork_focused"
            intent["focus"] = "Artwork"

        # 風格/運動相關查詢
        elif any(word in query_lower for word in ["風格", "運動", "流派", "style", "movement"]):
            intent["query_type"] = "movement_focused"
            intent["focus"] = "Movement"

        # 影響關係查詢
        elif any(word in query_lower for word in ["影響", "師承", "學習", "influence", "taught"]):
            intent["query_type"] = "relationship_focused"
            intent["relationships"] = ["INFLUENCED_BY", "TAUGHT_BY"]

        # 時期相關查詢
        elif any(word in query_lower for word in ["時期", "年代", "時代", "period", "era"]):
            intent["query_type"] = "period_focused"
            intent["focus"] = "Period"

        return intent

    def _generate_cypher_query(self, query: str, intent: dict[str, Any]) -> str:
        """生成Cypher查詢語句"""

        if intent["query_type"] == "artist_focused":
            return """
            MATCH (a:Artist)
            WHERE a.name CONTAINS $query OR a.biography CONTAINS $query
            OPTIONAL MATCH (a)-[r1:CREATED_BY]-(w:Artwork)
            OPTIONAL MATCH (a)-[r2:BELONGS_TO_MOVEMENT]-(m:Movement)
            RETURN a, collect(DISTINCT w) as artworks, collect(DISTINCT m) as movements
            LIMIT 10
            """.replace("$query", f"'{query}'")

        elif intent["query_type"] == "artwork_focused":
            return """
            MATCH (w:Artwork)
            WHERE w.title CONTAINS $query OR w.description CONTAINS $query
            OPTIONAL MATCH (w)-[r1:CREATED_BY]-(a:Artist)
            OPTIONAL MATCH (w)-[r2:USES_TECHNIQUE]-(t:Technique)
            RETURN w, a, collect(DISTINCT t) as techniques
            LIMIT 10
            """.replace("$query", f"'{query}'")

        elif intent["query_type"] == "movement_focused":
            return """
            MATCH (m:Movement)
            WHERE m.name CONTAINS $query OR m.characteristics CONTAINS $query
            OPTIONAL MATCH (m)-[r1:BELONGS_TO_MOVEMENT]-(a:Artist)
            OPTIONAL MATCH (m)-[r2:ORIGINATED_IN]-(l:Location)
            RETURN m, collect(DISTINCT a) as artists, l
            LIMIT 10
            """.replace("$query", f"'{query}'")

        elif intent["query_type"] == "relationship_focused":
            return """
            MATCH (a1:Artist)-[r:INFLUENCED_BY|TAUGHT_BY]-(a2:Artist)
            WHERE a1.name CONTAINS $query OR a2.name CONTAINS $query
            RETURN a1, r, a2
            LIMIT 10
            """.replace("$query", f"'{query}'")

        else:  # 一般查詢
            return """
            MATCH (n)
            WHERE any(prop in keys(n) WHERE toString(n[prop]) CONTAINS $query)
            OPTIONAL MATCH (n)-[r]-(related)
            RETURN n, collect(DISTINCT related)[..5] as related_entities
            LIMIT 10
            """.replace("$query", f"'{query}'")

    def _convert_graph_result_to_documents(
        self, result: GraphQueryResult, original_query: str
    ) -> list[Document]:
        """將圖查詢結果轉換為文檔"""
        documents = []

        # 處理實體
        for entity in result.entities:
            content = self._format_entity_content(entity)
            metadata = {
                "source": "knowledge_graph",
                "entity_type": entity.get("labels", ["Unknown"])[0],
                "entity_id": entity.get("id"),
                "query": original_query,
                "execution_time": result.execution_time,
            }

            doc = Document(page_content=content, metadata=metadata)
            documents.append(doc)

        # 處理關係
        for rel in result.relationships:
            content = self._format_relationship_content(rel)
            metadata = {
                "source": "knowledge_graph",
                "relationship_type": rel.get("type"),
                "relationship_id": rel.get("id"),
                "query": original_query,
            }

            doc = Document(page_content=content, metadata=metadata)
            documents.append(doc)

        return documents

    def _format_entity_content(self, entity: dict[str, Any]) -> str:
        """格式化實體內容"""
        labels = entity.get("labels", ["Unknown"])
        properties = entity.get("properties", {})

        content = f"實體類型: {', '.join(labels)}\n"

        for key, value in properties.items():
            if isinstance(value, list):
                content += f"{key}: {', '.join(map(str, value))}\n"
            else:
                content += f"{key}: {value}\n"

        return content

    def _format_relationship_content(self, relationship: dict[str, Any]) -> str:
        """格式化關係內容"""
        rel_type = relationship.get("type", "UNKNOWN")
        properties = relationship.get("properties", {})

        content = f"關係類型: {rel_type}\n"

        for key, value in properties.items():
            content += f"{key}: {value}\n"

        return content


class HybridKnowledgeGraphRAG:
    """混合知識圖譜RAG系統"""

    def __init__(
        self,
        graph: Neo4jArtHistoryGraph,
        vector_retriever: MultimodalRetriever,
        ml_service_url: str = "http://localhost:8080",
    ):
        self.graph = graph
        self.vector_retriever = vector_retriever
        self.graph_retriever = ArtHistoryGraphRetriever(graph=graph)
        self.ml_service_url = ml_service_url

    async def hybrid_retrieve(
        self, query: str, vector_weight: float = 0.6, graph_weight: float = 0.4, top_k: int = 5
    ) -> list[Document]:
        """混合檢索：結合向量檢索和圖檢索"""

        # 並行執行向量檢索和圖檢索
        vector_docs = await self._get_vector_documents(query)
        graph_docs = self.graph_retriever.get_relevant_documents(query)

        # 計算混合分數
        hybrid_docs = []

        # 向量文檔加權
        for i, doc in enumerate(vector_docs[:top_k]):
            score = vector_weight * (1.0 - i / max(len(vector_docs), 1))
            doc.metadata["hybrid_score"] = score
            doc.metadata["source_type"] = "vector"
            hybrid_docs.append(doc)

        # 圖文檔加權
        for i, doc in enumerate(graph_docs[:top_k]):
            score = graph_weight * (1.0 - i / max(len(graph_docs), 1))
            doc.metadata["hybrid_score"] = score
            doc.metadata["source_type"] = "graph"
            hybrid_docs.append(doc)

        # 按混合分數排序
        hybrid_docs.sort(key=lambda x: x.metadata.get("hybrid_score", 0), reverse=True)

        return hybrid_docs[:top_k]

    async def _get_vector_documents(self, query: str) -> list[Document]:
        """獲取向量檢索文檔"""
        try:
            # 這裡應該調用現有的向量檢索系統
            # 暫時返回空列表，實際使用時需要整合
            return []
        except Exception as e:
            logger.warning(f"向量檢索失敗: {e}")
            return []

    def enhanced_query(self, query: str) -> dict[str, Any]:
        """增強查詢處理"""
        start_time = time.time()

        # 1. 圖檢索
        graph_docs = self.graph_retriever.get_relevant_documents(query)

        # 2. 生成增強上下文
        context = self._build_enhanced_context(graph_docs)

        # 3. 調用ML服務生成回答
        response = self._generate_response(query, context)

        processing_time = time.time() - start_time

        return {
            "query": query,
            "response": response,
            "context_documents": len(graph_docs),
            "graph_entities": len([d for d in graph_docs if d.metadata.get("entity_type")]),
            "graph_relationships": len(
                [d for d in graph_docs if d.metadata.get("relationship_type")]
            ),
            "processing_time": f"{processing_time:.2f}秒",
            "context": context[:500] + "..." if len(context) > 500 else context,
        }

    def _build_enhanced_context(self, documents: list[Document]) -> str:
        """構建增強上下文"""
        context_parts = []

        # 分離實體和關係
        entities = [d for d in documents if d.metadata.get("entity_type")]
        relationships = [d for d in documents if d.metadata.get("relationship_type")]

        if entities:
            context_parts.append("=== 相關實體資訊 ===")
            for doc in entities[:3]:  # 限制數量
                context_parts.append(doc.page_content)

        if relationships:
            context_parts.append("\n=== 相關關係資訊 ===")
            for doc in relationships[:3]:  # 限制數量
                context_parts.append(doc.page_content)

        return "\n".join(context_parts)

    def _generate_response(self, query: str, context: str) -> str:
        """生成回答"""
        try:
            import requests

            response = requests.post(
                f"{self.ml_service_url}/rag/generate",
                json={"question": query, "context": context},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    return result.get("generated_text", "無法生成回答")

            return "回答生成服務暫時不可用"

        except Exception as e:
            logger.error(f"回答生成失敗: {e}")
            return f"基於知識圖譜的上下文，這是對「{query}」的結構化回答。{context[:200]}..."


# 使用示例
if __name__ == "__main__":
    # 初始化Neo4j圖譜
    graph = Neo4jArtHistoryGraph()

    if graph.connect():
        # 創建架構
        graph.create_schema()

        # 填充示例數據
        graph.populate_sample_data()

        # 初始化混合RAG系統
        # vector_retriever = MultimodalRetriever(...)  # 需要實際的向量檢索器
        rag_system = HybridKnowledgeGraphRAG(
            graph=graph,
            vector_retriever=None,  # 暫時為None
        )

        # 測試查詢
        test_queries = [
            "達文西的藝術作品有哪些？",
            "印象派運動的特點是什麼？",
            "哪些藝術家互相影響？",
        ]

        for query in test_queries:
            print(f"\n🔍 查詢: {query}")
            result = rag_system.enhanced_query(query)
            print(f"📊 處理時間: {result['processing_time']}")
            print(f"💡 回答: {result['response']}")
            print(f"📈 上下文實體: {result['graph_entities']}")
            print(f"🔗 上下文關係: {result['graph_relationships']}")

        graph.close()
    else:
        print("❌ 無法連接Neo4j數據庫")
