#!/usr/bin/env python3
"""
增強型 Neo4j 檢索器
實現多種 LangChain 高級檢索策略，優化 Neo4j 查詢精確度
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.language_models import BaseLanguageModel
from langchain_core.retrievers import BaseRetriever
from neo4j import GraphDatabase
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

# ==================== 配置 ====================


@dataclass
class RetrieverConfig:
    """檢索器配置"""

    # Neo4j 連接
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "CHANGE_ME_NEO4J_PASSWORD"

    # 檢索參數
    top_k_initial: int = 20  # 初始檢索數量
    top_k_final: int = 5  # 最終返回數量

    # 向量搜索
    vector_index_name: str = "artist_name_embeddings"
    vector_dimensions: int = 1536

    # 全文搜索
    fulltext_index_name: str = "artist_fulltext"
    min_fulltext_score: float = 0.3

    # 重排序
    reranker_model: str = "BAAI/bge-reranker-base"
    enable_reranking: bool = True

    # 權重配置
    vector_weight: float = 0.4
    fulltext_weight: float = 0.3
    graph_weight: float = 0.3


# ==================== 增強型 Neo4j 檢索器 ====================


class EnhancedNeo4jRetriever(BaseRetriever):
    """增強型 Neo4j 檢索器 - 實現多種優化策略"""

    def __init__(
        self,
        config: RetrieverConfig,
        embedding_model: Any = None,
        llm: BaseLanguageModel | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.config = config
        self.embedding_model = embedding_model
        self.llm = llm

        # 初始化 Neo4j 驅動
        self.driver = GraphDatabase.driver(
            config.neo4j_uri, auth=(config.neo4j_user, config.neo4j_password)
        )

        # 初始化 Re-ranker（如果啟用）
        self.reranker = None
        if config.enable_reranking:
            try:
                self.reranker = CrossEncoder(config.reranker_model)
                logger.info(f"✅ 載入 Re-ranker: {config.reranker_model}")
            except Exception as e:
                logger.warning(f"⚠️ Re-ranker 載入失敗: {e}")

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        """獲取相關文檔 - 主要檢索邏輯"""

        # 1. 查詢擴展
        expanded_queries = self._expand_query(query)
        logger.info(f"🔍 查詢擴展: {len(expanded_queries)} 個查詢變體")

        # 2. 多策略檢索
        all_results = []

        for exp_query in expanded_queries:
            # 向量檢索
            if self.embedding_model:
                vector_results = self._vector_search(exp_query)
                all_results.extend(self._add_source_tag(vector_results, "vector"))

            # 全文檢索
            fulltext_results = self._fulltext_search(exp_query)
            all_results.extend(self._add_source_tag(fulltext_results, "fulltext"))

            # 圖關係檢索
            graph_results = self._graph_search(exp_query)
            all_results.extend(self._add_source_tag(graph_results, "graph"))

        # 3. 去重和合併
        unique_results = self._deduplicate_results(all_results)
        logger.info(f"📊 去重後: {len(unique_results)} 個結果")

        # 4. 圖關係擴展
        expanded_results = self._graph_expansion(unique_results)
        logger.info(f"🕸️ 關係擴展後: {len(expanded_results)} 個結果")

        # 5. 重排序
        if self.reranker and len(expanded_results) > 0:
            final_results = self._rerank(query, expanded_results)
            logger.info(f"🎯 重排序後: {len(final_results)} 個結果")
        else:
            final_results = expanded_results[: self.config.top_k_final]

        # 6. 轉換為 Document
        documents = self._convert_to_documents(final_results, query)

        return documents

    def _expand_query(self, query: str) -> list[str]:
        """查詢擴展 - 生成多個查詢變體"""
        queries = [query]  # 總是包含原始查詢

        # 如果有 LLM，使用 LLM 生成查詢變體
        if self.llm:
            try:
                prompt = f"""作為藝術史專家，請將以下查詢改寫成2個不同的表述：

原始查詢: {query}

要求:
1. 保持原意
2. 使用不同的詞彙
3. 一個更學術，一個更通俗

請直接返回2個查詢，每行一個，不要編號。"""

                response = self.llm.invoke(prompt)
                expanded = [line.strip() for line in response.content.split("\n") if line.strip()]
                queries.extend(expanded[:2])

            except Exception as e:
                logger.warning(f"⚠️ LLM 查詢擴展失敗: {e}")

        # 簡單的關鍵詞擴展（備用方案）
        else:
            # 中英文常見擴展
            expansions = {
                "達文西": ["Leonardo da Vinci", "列奧納多·達·芬奇"],
                "印象派": ["Impressionism", "印象主義"],
                "文藝復興": ["Renaissance"],
                "巴洛克": ["Baroque"],
            }

            for cn, variants in expansions.items():
                if cn in query:
                    for variant in variants:
                        queries.append(query.replace(cn, variant))

        return list(set(queries))  # 去重

    def _vector_search(self, query: str, top_k: int = None) -> list[dict]:
        """向量相似度搜索"""
        if not self.embedding_model:
            return []

        k = top_k or self.config.top_k_initial

        try:
            # 生成查詢向量
            query_embedding = self.embedding_model.embed_query(query)

            # Cypher 查詢
            cypher = """
            CALL db.index.vector.queryNodes($index_name, $top_k, $embedding)
            YIELD node, score
            RETURN
                id(node) as node_id,
                labels(node) as labels,
                properties(node) as properties,
                score as similarity_score
            ORDER BY score DESC
            """

            with self.driver.session() as session:
                result = session.run(
                    cypher,
                    {
                        "index_name": self.config.vector_index_name,
                        "top_k": k,
                        "embedding": query_embedding,
                    },
                )

                results = []
                for record in result:
                    results.append(
                        {
                            "node_id": record["node_id"],
                            "labels": record["labels"],
                            "properties": dict(record["properties"]),
                            "score": float(record["similarity_score"]),
                            "retrieval_method": "vector",
                        }
                    )

                return results

        except Exception as e:
            logger.error(f"❌ 向量搜索失敗: {e}")
            return []

    def _fulltext_search(self, query: str, top_k: int = None) -> list[dict]:
        """全文搜索"""
        k = top_k or self.config.top_k_initial

        try:
            cypher = """
            CALL db.index.fulltext.queryNodes($index_name, $query)
            YIELD node, score
            WHERE score > $min_score
            RETURN
                id(node) as node_id,
                labels(node) as labels,
                properties(node) as properties,
                score as relevance_score
            ORDER BY score DESC
            LIMIT $top_k
            """

            with self.driver.session() as session:
                result = session.run(
                    cypher,
                    {
                        "index_name": self.config.fulltext_index_name,
                        "query": query,
                        "min_score": self.config.min_fulltext_score,
                        "top_k": k,
                    },
                )

                results = []
                for record in result:
                    results.append(
                        {
                            "node_id": record["node_id"],
                            "labels": record["labels"],
                            "properties": dict(record["properties"]),
                            "score": float(record["relevance_score"]),
                            "retrieval_method": "fulltext",
                        }
                    )

                return results

        except Exception as e:
            logger.error(f"❌ 全文搜索失敗: {e}")
            return []

    def _graph_search(self, query: str, top_k: int = None) -> list[dict]:
        """圖結構搜索"""
        k = top_k or self.config.top_k_initial

        try:
            # 分析查詢意圖
            intent = self._analyze_query_intent(query)

            # 根據意圖選擇 Cypher 查詢
            if intent["type"] == "artist":
                cypher = """
                MATCH (a:Artist)
                WHERE toLower(a.name) CONTAINS toLower($query)
                   OR toLower(a.biography) CONTAINS toLower($query)
                   OR toLower(a.nationality) CONTAINS toLower($query)
                OPTIONAL MATCH (a)-[:CREATED]-(w:Artwork)
                OPTIONAL MATCH (a)-[:BELONGS_TO_MOVEMENT]-(m:Movement)
                WITH a, count(DISTINCT w) as artwork_count, collect(DISTINCT m.name)[..3] as movements
                RETURN
                    id(a) as node_id,
                    labels(a) as labels,
                    properties(a) as properties,
                    artwork_count,
                    movements,
                    1.0 as score
                LIMIT $top_k
                """

            elif intent["type"] == "artwork":
                cypher = """
                MATCH (w:Artwork)
                WHERE toLower(w.title) CONTAINS toLower($query)
                   OR toLower(w.description) CONTAINS toLower($query)
                OPTIONAL MATCH (w)-[:CREATED_BY]-(a:Artist)
                RETURN
                    id(w) as node_id,
                    labels(w) as labels,
                    properties(w) as properties,
                    a.name as artist_name,
                    1.0 as score
                LIMIT $top_k
                """

            else:  # 通用搜索
                cypher = """
                MATCH (n)
                WHERE any(prop in keys(n)
                    WHERE toString(n[prop]) CONTAINS $query)
                RETURN
                    id(n) as node_id,
                    labels(n) as labels,
                    properties(n) as properties,
                    1.0 as score
                LIMIT $top_k
                """

            with self.driver.session() as session:
                result = session.run(cypher, {"query": query, "top_k": k})

                results = []
                for record in result:
                    results.append(
                        {
                            "node_id": record["node_id"],
                            "labels": record["labels"],
                            "properties": dict(record["properties"]),
                            "score": float(record["score"]),
                            "retrieval_method": "graph",
                            "extra": {
                                k: record[k]
                                for k in record.keys()
                                if k not in ["node_id", "labels", "properties", "score"]
                            },
                        }
                    )

                return results

        except Exception as e:
            logger.error(f"❌ 圖搜索失敗: {e}")
            return []

    def _analyze_query_intent(self, query: str) -> dict:
        """分析查詢意圖"""
        query_lower = query.lower()

        artist_keywords = ["藝術家", "畫家", "雕塑家", "artist", "painter", "sculptor"]
        artwork_keywords = ["作品", "畫作", "雕塑", "artwork", "painting", "sculpture"]
        movement_keywords = ["運動", "流派", "風格", "movement", "style"]

        if any(kw in query_lower for kw in artist_keywords):
            return {"type": "artist"}
        elif any(kw in query_lower for kw in artwork_keywords):
            return {"type": "artwork"}
        elif any(kw in query_lower for kw in movement_keywords):
            return {"type": "movement"}
        else:
            return {"type": "general"}

    def _add_source_tag(self, results: list[dict], source: str) -> list[dict]:
        """為結果添加來源標記"""
        for result in results:
            result["source"] = source
        return results

    def _deduplicate_results(self, results: list[dict]) -> list[dict]:
        """去重 - 基於 node_id"""
        seen = {}
        unique_results = []

        for result in results:
            node_id = result["node_id"]

            if node_id not in seen:
                seen[node_id] = result
                unique_results.append(result)
            else:
                # 合併分數（多來源的結果取平均）
                existing = seen[node_id]
                existing["score"] = (existing["score"] + result["score"]) / 2
                existing["sources"] = existing.get("sources", [existing.get("source", "unknown")])
                existing["sources"].append(result.get("source", "unknown"))

        # 按分數排序
        unique_results.sort(key=lambda x: x["score"], reverse=True)

        return unique_results

    def _graph_expansion(self, results: list[dict]) -> list[dict]:
        """圖關係擴展 - 獲取相關節點"""
        if not results:
            return results

        try:
            node_ids = [r["node_id"] for r in results[:10]]  # 限制擴展數量

            cypher = """
            MATCH (n)
            WHERE id(n) IN $node_ids
            OPTIONAL MATCH (n)-[r]-(related)
            RETURN
                id(n) as source_node_id,
                id(related) as related_node_id,
                type(r) as relationship_type,
                labels(related) as related_labels,
                properties(related) as related_properties
            LIMIT 50
            """

            with self.driver.session() as session:
                expansion_result = session.run(cypher, {"node_ids": node_ids})

                # 將擴展結果添加到原始結果
                for record in expansion_result:
                    if record["related_node_id"]:
                        # 檢查是否已存在
                        if not any(r["node_id"] == record["related_node_id"] for r in results):
                            results.append(
                                {
                                    "node_id": record["related_node_id"],
                                    "labels": record["related_labels"],
                                    "properties": dict(record["related_properties"]),
                                    "score": 0.5,  # 擴展結果給較低分數
                                    "retrieval_method": "graph_expansion",
                                    "relationship": record["relationship_type"],
                                }
                            )

            return results

        except Exception as e:
            logger.error(f"❌ 圖擴展失敗: {e}")
            return results

    def _rerank(self, query: str, results: list[dict]) -> list[dict]:
        """使用 Cross-Encoder 重排序"""
        if not self.reranker or not results:
            return results[: self.config.top_k_final]

        try:
            # 準備文本對
            pairs = []
            for result in results:
                doc_text = self._format_for_reranking(result)
                pairs.append([query, doc_text])

            # 計算相關性分數
            scores = self.reranker.predict(pairs)

            # 合併原始分數和重排序分數
            for result, rerank_score in zip(results, scores):
                result["rerank_score"] = float(rerank_score)
                # 組合分數：原始分數 40% + 重排序分數 60%
                result["final_score"] = result["score"] * 0.4 + rerank_score * 0.6

            # 按最終分數排序
            results.sort(key=lambda x: x["final_score"], reverse=True)

            return results[: self.config.top_k_final]

        except Exception as e:
            logger.error(f"❌ 重排序失敗: {e}")
            return results[: self.config.top_k_final]

    def _format_for_reranking(self, result: dict) -> str:
        """格式化結果用於重排序"""
        props = result["properties"]
        labels = result["labels"]

        # 構建文本表示
        text_parts = [f"類型: {', '.join(labels)}"]

        # 添加關鍵屬性
        key_fields = ["name", "title", "biography", "description", "characteristics"]
        for field in key_fields:
            if field in props and props[field]:
                text_parts.append(f"{field}: {props[field]}")

        return " | ".join(text_parts)

    def _convert_to_documents(self, results: list[dict], query: str) -> list[Document]:
        """轉換為 LangChain Document 格式"""
        documents = []

        for i, result in enumerate(results):
            # 構建文檔內容
            content = self._format_result_content(result)

            # 構建元數據
            metadata = {
                "source": "neo4j",
                "node_id": result["node_id"],
                "labels": result["labels"],
                "retrieval_method": result.get("retrieval_method", "unknown"),
                "score": result.get("final_score", result.get("score", 0)),
                "rank": i + 1,
                "query": query,
            }

            # 添加額外元數據
            if "sources" in result:
                metadata["retrieval_sources"] = result["sources"]
            if "rerank_score" in result:
                metadata["rerank_score"] = result["rerank_score"]

            doc = Document(page_content=content, metadata=metadata)
            documents.append(doc)

        return documents

    def _format_result_content(self, result: dict) -> str:
        """格式化結果內容"""
        props = result["properties"]
        labels = result["labels"]

        content_parts = []

        # 標題
        content_parts.append(f"=== {', '.join(labels)} ===\n")

        # 屬性
        for key, value in props.items():
            if value and key not in ["embedding", "name_embedding"]:
                content_parts.append(f"{key}: {value}")

        # 關係信息（如果有）
        if "relationship" in result:
            content_parts.append(f"\n關係: {result['relationship']}")

        return "\n".join(content_parts)

    def close(self):
        """關閉連接"""
        if self.driver:
            self.driver.close()


# ==================== 便捷函數 ====================


def create_enhanced_retriever(
    embedding_model: Any = None,
    llm: BaseLanguageModel | None = None,
    config: RetrieverConfig | None = None,
) -> EnhancedNeo4jRetriever:
    """創建增強型檢索器的便捷函數"""

    if config is None:
        config = RetrieverConfig()

    retriever = EnhancedNeo4jRetriever(config=config, embedding_model=embedding_model, llm=llm)

    logger.info("✅ 增強型 Neo4j 檢索器創建成功")
    return retriever


# ==================== 測試 ====================


async def test_retriever():
    """測試檢索器"""
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    # 初始化組件
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

    # 創建檢索器
    config = RetrieverConfig(top_k_initial=15, top_k_final=5, enable_reranking=True)

    retriever = create_enhanced_retriever(embedding_model=embeddings, llm=llm, config=config)

    # 測試查詢
    test_queries = ["達文西的主要作品", "印象派的藝術特色", "文藝復興時期的繪畫風格"]

    for query in test_queries:
        print(f"\n{'=' * 60}")
        print(f"🔍 查詢: {query}")
        print(f"{'=' * 60}")

        start_time = time.time()
        docs = retriever.get_relevant_documents(query)
        elapsed = time.time() - start_time

        print(f"⏱️  檢索時間: {elapsed:.2f}秒")
        print(f"📚 結果數量: {len(docs)}")

        for i, doc in enumerate(docs, 1):
            print(f"\n[{i}] 分數: {doc.metadata.get('score', 0):.3f}")
            print(f"    標籤: {', '.join(doc.metadata.get('labels', []))}")
            print(f"    方法: {doc.metadata.get('retrieval_method', 'unknown')}")
            print(f"    內容: {doc.page_content[:200]}...")

    # 清理
    retriever.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_retriever())
