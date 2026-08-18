#!/usr/bin/env python3
"""
整合多模態RAG優化管理器
統一管理向量檢索、知識圖譜、性能優化等所有RAG組件
"""

import asyncio
import json
import logging
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from performance_monitor import PerformanceMonitor, QueryMetrics

logger = logging.getLogger(__name__)


class RAGStrategy(Enum):
    """RAG策略類型"""

    VECTOR_ONLY = "vector_only"
    GRAPH_ONLY = "graph_only"
    HYBRID_BALANCED = "hybrid_balanced"
    ADAPTIVE = "adaptive"
    SPECIALIZED = "specialized"
    ADVANCED_RAG = "advanced_rag"
    SELF_RAG = "self_rag"
    AGENTIC_RAG = "agentic_rag"
    NAIVE_RAG = "naive_rag"


class QueryComplexity(Enum):
    """查詢複雜度"""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    EXPERT = "expert"


@dataclass
class RAGConfiguration:
    """RAG系統配置"""

    # 檢索策略
    strategy: RAGStrategy = RAGStrategy.HYBRID_BALANCED
    vector_weight: float = 0.6
    graph_weight: float = 0.4

    # 檢索參數
    top_k_vector: int = 10
    top_k_graph: int = 5
    top_k_final: int = 5

    # 重排序
    enable_reranking: bool = True
    rerank_model: str = "bge-reranker-large"

    # 快取設置
    enable_cache: bool = True
    cache_ttl: int = 3600  # 1小時
    cache_max_size: int = 1000

    # 性能設置
    timeout_seconds: int = 30
    max_retries: int = 3
    batch_size: int = 5

    # 生成參數
    temperature: float = 0.7
    max_tokens: int = 1000
    enable_streaming: bool = False


@dataclass
class RAGQueryResult:
    """RAG查詢結果"""

    query: str
    answer: str
    sources: list[dict[str, Any]]
    strategy_used: RAGStrategy
    processing_time: float
    confidence_score: float
    cache_hit: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class IntegratedRAGOptimizer:
    """整合多模態RAG優化管理器"""

    def __init__(
        self,
        ml_service_url: str = "http://localhost:8080",
        neo4j_url: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "CHANGE_ME_NEO4J_PASSWORD",
    ):

        self.ml_service_url = ml_service_url
        self.neo4j_url = neo4j_url
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password

        # 組件初始化
        self.monitor = PerformanceMonitor()
        self.config = RAGConfiguration()

        # 快取系統
        self.query_cache = {}
        self.cache_stats = {"hits": 0, "misses": 0, "total": 0}

        # 性能統計
        self.strategy_stats = {
            strategy: {"count": 0, "avg_time": 0.0, "success_rate": 0.0} for strategy in RAGStrategy
        }

        # 自適應學習
        self.query_patterns = {}
        self.optimization_history = []

        # 線程池
        self.executor = ThreadPoolExecutor(max_workers=4)

        # 組件實例（延遲初始化）
        self._vector_retriever = None
        self._graph_retriever = None
        self._graph_instance = None

    def initialize_components(self):
        """初始化RAG組件"""
        try:
            # 初始化知識圖譜（模擬）
            logger.info("🔄 初始化知識圖譜組件...")
            self._initialize_graph_component()

            # 初始化向量檢索（模擬）
            logger.info("🔄 初始化向量檢索組件...")
            self._initialize_vector_component()

            logger.info("✅ 所有RAG組件初始化完成")
            return True

        except Exception as e:
            logger.error(f"❌ RAG組件初始化失敗: {e}")
            return False

    def _initialize_graph_component(self):
        """初始化知識圖譜組件"""
        # 模擬知識圖譜組件（實際使用時需要真實組件）
        self._graph_instance = {
            "status": "ready",
            "entities": 20,
            "relationships": 20,
            "last_update": datetime.now(),
        }

    def _initialize_vector_component(self):
        """初始化向量檢索組件"""
        # 模擬向量檢索組件（實際使用時需要真實組件）
        self._vector_retriever = {
            "status": "ready",
            "dimension": 1024,
            "index_size": 1000,
            "last_update": datetime.now(),
        }

    async def query(self, query_text: str, **kwargs) -> RAGQueryResult:
        """統一查詢接口"""
        start_time = time.time()

        # 檢查快取
        cache_key = self._generate_cache_key(query_text, kwargs)
        if self.config.enable_cache and cache_key in self.query_cache:
            cached_result = self.query_cache[cache_key]
            cached_result.cache_hit = True
            self.cache_stats["hits"] += 1
            self.cache_stats["total"] += 1

            # 記錄快取命中
            self._log_query_metrics(query_text, cached_result, cache_hit=True)
            return cached_result

        self.cache_stats["misses"] += 1
        self.cache_stats["total"] += 1

        try:
            # 分析查詢複雜度
            complexity = self._analyze_query_complexity(query_text)

            # 選擇最佳策略
            strategy = self._select_optimal_strategy(query_text, complexity, **kwargs)

            # 移除kwargs中的strategy避免參數衝突
            filtered_kwargs = {k: v for k, v in kwargs.items() if k != "strategy"}

            # 執行RAG查詢
            result = await self._execute_rag_query(query_text, strategy, **filtered_kwargs)

            # 快取結果
            if self.config.enable_cache:
                self._cache_result(cache_key, result)

            # 記錄指標
            self._log_query_metrics(query_text, result)

            # 更新自適應學習
            self._update_adaptive_learning(query_text, strategy, result)

            return result

        except Exception as e:
            logger.error(f"❌ 查詢執行失敗: {e}")

            # 創建錯誤結果
            error_result = RAGQueryResult(
                query=query_text,
                answer=f"查詢處理失敗: {str(e)}",
                sources=[],
                strategy_used=RAGStrategy.HYBRID_BALANCED,
                processing_time=time.time() - start_time,
                confidence_score=0.0,
                metadata={"error": str(e)},
            )

            self._log_query_metrics(query_text, error_result)
            return error_result

    def _analyze_query_complexity(self, query: str) -> QueryComplexity:
        """分析查詢複雜度"""
        query_lower = query.lower()

        # 專家級查詢關鍵詞
        expert_keywords = [
            "影響",
            "師承",
            "發展",
            "演變",
            "比較",
            "關係",
            "influence",
            "development",
            "comparison",
        ]

        # 複雜查詢關鍵詞
        complex_keywords = [
            "風格",
            "技法",
            "特色",
            "歷史",
            "時期",
            "style",
            "technique",
            "history",
            "period",
        ]

        # 中等查詢關鍵詞
        medium_keywords = [
            "作品",
            "藝術家",
            "繪畫",
            "雕塑",
            "artwork",
            "artist",
            "painting",
            "sculpture",
        ]

        word_count = len(query.split())

        if any(keyword in query_lower for keyword in expert_keywords) or word_count > 15:
            return QueryComplexity.EXPERT
        elif any(keyword in query_lower for keyword in complex_keywords) or word_count > 10:
            return QueryComplexity.COMPLEX
        elif any(keyword in query_lower for keyword in medium_keywords) or word_count > 5:
            return QueryComplexity.MEDIUM
        else:
            return QueryComplexity.SIMPLE

    def _select_optimal_strategy(
        self, query: str, complexity: QueryComplexity, **kwargs
    ) -> RAGStrategy:
        """選擇最佳RAG策略"""

        # 用戶指定策略
        if "strategy" in kwargs:
            return RAGStrategy(kwargs["strategy"])

        # 基於複雜度的策略選擇
        if complexity == QueryComplexity.EXPERT:
            return RAGStrategy.HYBRID_BALANCED  # 專家級查詢使用混合策略
        elif complexity == QueryComplexity.COMPLEX:
            return RAGStrategy.GRAPH_ONLY  # 複雜查詢偏向圖譜
        elif complexity == QueryComplexity.MEDIUM:
            return RAGStrategy.ADAPTIVE  # 中等查詢自適應
        else:
            return RAGStrategy.VECTOR_ONLY  # 簡單查詢使用向量

    async def _execute_rag_query(
        self, query: str, strategy: RAGStrategy, **kwargs
    ) -> RAGQueryResult:
        """執行RAG查詢"""
        start_time = time.time()

        if strategy == RAGStrategy.VECTOR_ONLY:
            result = await self._vector_only_query(query, **kwargs)
        elif strategy == RAGStrategy.GRAPH_ONLY:
            result = await self._graph_only_query(query, **kwargs)
        elif strategy == RAGStrategy.HYBRID_BALANCED:
            result = await self._hybrid_balanced_query(query, **kwargs)
        elif strategy == RAGStrategy.ADAPTIVE:
            result = await self._adaptive_query(query, **kwargs)
        elif strategy == RAGStrategy.ADVANCED_RAG:
            result = await self._advanced_rag_query(query, **kwargs)
        elif strategy == RAGStrategy.SELF_RAG:
            result = await self._self_rag_query(query, **kwargs)
        elif strategy == RAGStrategy.AGENTIC_RAG:
            result = await self._agentic_rag_query(query, **kwargs)
        elif strategy == RAGStrategy.NAIVE_RAG:
            result = await self._naive_rag_query(query, **kwargs)
        else:
            result = await self._specialized_query(query, **kwargs)

        processing_time = time.time() - start_time
        result.processing_time = processing_time
        result.strategy_used = strategy

        return result

    async def _vector_only_query(self, query: str, **kwargs) -> RAGQueryResult:
        """純向量檢索查詢"""
        # 模擬向量檢索
        await asyncio.sleep(0.1)  # 模擬檢索時間

        sources = [
            {
                "content": f"向量檢索結果：{query}的相關藝術史文獻內容",
                "source": "vector_database",
                "score": 0.85,
                "metadata": {"retrieval_method": "vector"},
            }
        ]

        answer = f"基於向量檢索的回答：{query}在藝術史中是一個重要概念..."

        return RAGQueryResult(
            query=query,
            answer=answer,
            sources=sources,
            strategy_used=RAGStrategy.VECTOR_ONLY,
            processing_time=0.0,
            confidence_score=0.8,
        )

    async def _graph_only_query(self, query: str, **kwargs) -> RAGQueryResult:
        """純知識圖譜查詢"""
        # 模擬知識圖譜檢索
        await asyncio.sleep(0.15)  # 模擬檢索時間

        sources = [
            {
                "content": f"知識圖譜檢索結果：{query}相關的實體和關係",
                "source": "knowledge_graph",
                "entities": ["Leonardo da Vinci", "Mona Lisa", "Renaissance"],
                "relationships": ["CREATED_BY", "BELONGS_TO_MOVEMENT"],
                "score": 0.9,
                "metadata": {"retrieval_method": "graph"},
            }
        ]

        answer = f"基於知識圖譜的結構化回答：{query}涉及以下藝術史實體和關係..."

        return RAGQueryResult(
            query=query,
            answer=answer,
            sources=sources,
            strategy_used=RAGStrategy.GRAPH_ONLY,
            processing_time=0.0,
            confidence_score=0.85,
        )

    async def _hybrid_balanced_query(self, query: str, **kwargs) -> RAGQueryResult:
        """平衡混合查詢"""
        # 並行執行向量和圖譜檢索
        vector_task = self._vector_only_query(query, **kwargs)
        graph_task = self._graph_only_query(query, **kwargs)

        vector_result, graph_result = await asyncio.gather(vector_task, graph_task)

        # 合併結果
        combined_sources = vector_result.sources + graph_result.sources
        combined_answer = f"綜合向量檢索和知識圖譜的全面回答：{query}..."

        # 計算加權置信度
        confidence = (
            vector_result.confidence_score * self.config.vector_weight
            + graph_result.confidence_score * self.config.graph_weight
        )

        return RAGQueryResult(
            query=query,
            answer=combined_answer,
            sources=combined_sources,
            strategy_used=RAGStrategy.HYBRID_BALANCED,
            processing_time=0.0,
            confidence_score=confidence,
            metadata={
                "vector_confidence": vector_result.confidence_score,
                "graph_confidence": graph_result.confidence_score,
                "combination_weights": {
                    "vector": self.config.vector_weight,
                    "graph": self.config.graph_weight,
                },
            },
        )

    async def _adaptive_query(self, query: str, **kwargs) -> RAGQueryResult:
        """自適應查詢"""
        # 基於歷史性能選擇最佳策略
        best_strategy = self._get_best_performing_strategy()

        if best_strategy == RAGStrategy.VECTOR_ONLY:
            return await self._vector_only_query(query, **kwargs)
        elif best_strategy == RAGStrategy.GRAPH_ONLY:
            return await self._graph_only_query(query, **kwargs)
        else:
            return await self._hybrid_balanced_query(query, **kwargs)

    async def _specialized_query(self, query: str, **kwargs) -> RAGQueryResult:
        """專門化查詢（基於查詢類型）"""
        query_lower = query.lower()

        # 關係查詢偏向圖譜
        if any(
            word in query_lower for word in ["影響", "師承", "關係", "influence", "relationship"]
        ):
            return await self._graph_only_query(query, **kwargs)

        # 內容查詢偏向向量
        elif any(word in query_lower for word in ["描述", "內容", "特色", "describe", "content"]):
            return await self._vector_only_query(query, **kwargs)

        # 其他使用混合
        else:
            return await self._hybrid_balanced_query(query, **kwargs)

    async def _advanced_rag_query(self, query: str, **kwargs) -> RAGQueryResult:
        """Advanced RAG策略 - 多級檢索與重排序"""
        await asyncio.sleep(0.2)  # 模擬較長處理時間

        # 第一階段：粗檢索
        initial_vector_task = self._vector_only_query(query, **kwargs)
        initial_graph_task = self._graph_only_query(query, **kwargs)

        vector_result, graph_result = await asyncio.gather(initial_vector_task, initial_graph_task)

        # 第二階段：擴展檢索（基於初始結果擴展查詢）
        expanded_query = f"{query} 相關概念 發展歷史 藝術影響"
        expanded_vector_task = self._vector_only_query(expanded_query, **kwargs)
        expanded_result = await expanded_vector_task

        # 第三階段：重排序和融合
        all_sources = vector_result.sources + graph_result.sources + expanded_result.sources

        # 模擬重排序算法（基於相關性和多樣性）
        reranked_sources = sorted(all_sources, key=lambda x: x.get("score", 0), reverse=True)[
            : kwargs.get("top_k", 8)
        ]

        # 添加高級特徵
        for source in reranked_sources:
            source["metadata"]["advanced_features"] = {
                "multi_stage_retrieval": True,
                "query_expansion": True,
                "reranked": True,
                "relevance_score": source.get("score", 0) * 1.1,  # 提升分數
            }

        advanced_answer = (
            f"Advanced RAG深度分析：{query}\n\n通過多級檢索，我們發現：\n"
            f"1. 直接相關內容：{vector_result.answer[:50]}...\n"
            f"2. 結構化關係：{graph_result.answer[:50]}...\n"
            f"3. 擴展概念：{expanded_result.answer[:50]}...\n\n"
            f"綜合分析顯示這個概念在藝術史中具有多重意義和深遠影響。"
        )

        # 計算增強的置信度
        base_confidence = (vector_result.confidence_score + graph_result.confidence_score) / 2
        advanced_confidence = min(base_confidence * 1.15, 0.95)  # 提升但有上限

        return RAGQueryResult(
            query=query,
            answer=advanced_answer,
            sources=reranked_sources,
            strategy_used=RAGStrategy.ADVANCED_RAG,
            processing_time=0.0,
            confidence_score=advanced_confidence,
            metadata={
                "retrieval_stages": 3,
                "query_expansion": True,
                "reranking_applied": True,
                "sources_count": len(reranked_sources),
            },
        )

    async def _self_rag_query(self, query: str, **kwargs) -> RAGQueryResult:
        """Self-RAG策略 - 自我反思和迭代改進"""
        await asyncio.sleep(0.25)  # 模擬更長處理時間

        # 第一次檢索
        initial_result = await self._hybrid_balanced_query(query, **kwargs)

        # 自我評估階段
        self_critique = {
            "completeness": 0.7 if len(initial_result.sources) >= 3 else 0.5,
            "relevance": initial_result.confidence_score,
            "coverage": 0.8
            if "graph" in str(initial_result.sources) and "vector" in str(initial_result.sources)
            else 0.6,
        }

        overall_quality = statistics.mean(self_critique.values())

        # 如果質量不夠，進行自我改進
        if overall_quality < 0.75:
            # 生成改進查詢
            refined_query = f"{query} 詳細解釋 歷史背景 藝術特徵"
            refined_result = await self._advanced_rag_query(refined_query, **kwargs)

            # 合併和改進結果
            combined_sources = initial_result.sources + refined_result.sources
            # 去重並重排序
            unique_sources = []
            seen_content = set()
            for source in combined_sources:
                content_hash = hash(source.get("content", "")[:100])
                if content_hash not in seen_content:
                    seen_content.add(content_hash)
                    unique_sources.append(source)

            # 限制最終結果數量
            final_sources = unique_sources[: kwargs.get("top_k", 6)]

            # 生成自我反思的回答
            self_rag_answer = (
                f"Self-RAG反思性分析：{query}\n\n"
                f"初始分析：{initial_result.answer[:80]}...\n\n"
                f"深度反思：經過自我評估，發現需要補充更多細節。\n"
                f"改進分析：{refined_result.answer[:80]}...\n\n"
                f"綜合結論：通過多輪自我反思和改進，提供更全面準確的回答。"
            )

            final_confidence = min(overall_quality * 1.2, 0.92)

        else:
            # 質量已經足夠，直接返回改進的結果
            final_sources = initial_result.sources
            self_rag_answer = (
                f"Self-RAG高質量分析：{query}\n\n"
                f"經過自我評估，初始結果已達到高質量標準：\n"
                f"{initial_result.answer}\n\n"
                f"置信度評估：該分析在完整性、相關性和覆蓋度方面都達到了優秀水準。"
            )

            final_confidence = min(initial_result.confidence_score * 1.1, 0.90)

        # 添加Self-RAG特有的元數據
        for source in final_sources:
            source["metadata"]["self_rag_features"] = {
                "self_evaluated": True,
                "quality_score": overall_quality,
                "refinement_applied": overall_quality < 0.75,
                "confidence_boost": True,
            }

        return RAGQueryResult(
            query=query,
            answer=self_rag_answer,
            sources=final_sources,
            strategy_used=RAGStrategy.SELF_RAG,
            processing_time=0.0,
            confidence_score=final_confidence,
            metadata={
                "self_critique": self_critique,
                "quality_threshold": 0.75,
                "quality_achieved": overall_quality,
                "refinement_iterations": 1 if overall_quality < 0.75 else 0,
                "final_confidence": final_confidence,
            },
        )

    async def _agentic_rag_query(self, query: str, **kwargs) -> RAGQueryResult:
        """Agentic RAG策略 - 智能代理式多步推理檢索"""
        await asyncio.sleep(0.3)  # 模擬智能代理處理時間

        # 第一階段：問題分解和策略規劃
        query_analysis = {
            "intent": "factual"
            if any(word in query.lower() for word in ["什麼", "誰", "何時", "what", "who", "when"])
            else "analytical",
            "complexity": len(query.split()),
            "domain_keywords": [
                word
                for word in query.lower().split()
                if word in ["藝術", "畫家", "雕塑", "風格", "時期", "art", "artist", "style"]
            ],
            "requires_reasoning": any(
                word in query.lower()
                for word in ["為什麼", "如何", "影響", "why", "how", "influence"]
            ),
        }

        # 第二階段：智能代理決策
        if query_analysis["intent"] == "factual" and not query_analysis["requires_reasoning"]:
            # 事實性查詢：使用向量檢索
            primary_result = await self._vector_only_query(query, **kwargs)
        elif query_analysis["requires_reasoning"]:
            # 推理性查詢：結合圖譜關係
            primary_result = await self._graph_only_query(query, **kwargs)
        else:
            # 複雜查詢：使用混合策略
            primary_result = await self._hybrid_balanced_query(query, **kwargs)

        # 第三階段：知識增強和驗證
        # 根據初始結果，智能代理決定是否需要額外檢索
        if primary_result.confidence_score < 0.7:
            # 信心不足，執行補充檢索
            supplementary_query = f"{query} 相關藝術運動 歷史脈絡 代表作品"
            supplementary_result = await self._advanced_rag_query(supplementary_query, **kwargs)

            # 融合結果
            enhanced_sources = primary_result.sources + supplementary_result.sources[:3]
        else:
            enhanced_sources = primary_result.sources

        # 第四階段：智能代理推理和答案生成
        reasoning_steps = [
            f"問題分析：{query_analysis['intent']}查詢，複雜度級別{query_analysis['complexity']}",
            f"檢索策略：基於問題特徵選擇{primary_result.strategy_used.value}策略",
            f"知識整合：從{len(enhanced_sources)}個可靠來源整合信息",
            "推理驗證：通過多重驗證確保答案準確性",
        ]

        agentic_answer = f"Agentic RAG智能代理分析：{query}\n\n"
        agentic_answer += "🤖 智能推理過程：\n"
        for i, step in enumerate(reasoning_steps, 1):
            agentic_answer += f"{i}. {step}\n"

        agentic_answer += f"\n📊 分析結果：\n{primary_result.answer}\n\n"

        if primary_result.confidence_score < 0.7:
            agentic_answer += (
                "🔍 補充分析：智能代理識別需要更多信息，執行了補充檢索以提高準確性。\n"
            )

        agentic_answer += "\n🎯 智能代理結論：基於多階段推理和驗證，提供高可信度的專業分析。"

        # 計算增強的置信度（智能代理的判斷加權）
        agent_confidence_boost = 0.15 if query_analysis["requires_reasoning"] else 0.1
        final_confidence = min(primary_result.confidence_score + agent_confidence_boost, 0.95)

        # 添加Agentic RAG特有的元數據
        for source in enhanced_sources:
            source["metadata"]["agentic_rag_features"] = {
                "agent_selected": True,
                "reasoning_chain": True,
                "multi_stage_validation": True,
                "adaptive_strategy": True,
                "confidence_enhanced": True,
            }

        return RAGQueryResult(
            query=query,
            answer=agentic_answer,
            sources=enhanced_sources[: kwargs.get("top_k", 6)],
            strategy_used=RAGStrategy.AGENTIC_RAG,
            processing_time=0.0,
            confidence_score=final_confidence,
            metadata={
                "query_analysis": query_analysis,
                "reasoning_steps": reasoning_steps,
                "primary_strategy": primary_result.strategy_used.value,
                "supplementary_search": primary_result.confidence_score < 0.7,
                "agent_confidence_boost": agent_confidence_boost,
                "intelligence_level": "advanced",
            },
        )

    async def _naive_rag_query(self, query: str, **kwargs) -> RAGQueryResult:
        """Naive RAG策略 - 最簡單的檢索增強生成"""
        await asyncio.sleep(0.05)  # 模擬最快的處理時間

        # 簡單的關鍵詞提取
        keywords = [word for word in query.lower().split() if len(word) > 2]

        # 模擬最基本的檢索
        sources = [
            {
                "content": f"基於關鍵詞 '{' '.join(keywords[:3])}' 的基礎檢索結果",
                "source": "naive_retrieval",
                "score": 0.6,
                "metadata": {"retrieval_method": "keyword_match", "keywords_used": keywords[:3]},
            },
            {
                "content": f"與 '{query[:30]}...' 相關的簡單匹配內容",
                "source": "simple_search",
                "score": 0.55,
                "metadata": {"retrieval_method": "text_match", "query_snippet": query[:30]},
            },
        ]

        # 生成簡單直接的回答
        naive_answer = f"Naive RAG簡單檢索：{query}\n\n"
        naive_answer += "基於關鍵詞匹配，找到以下相關信息：\n"
        naive_answer += f"• 檢索到 {len(sources)} 個基礎來源\n"
        naive_answer += f"• 使用關鍵詞：{', '.join(keywords[:3])}\n\n"
        naive_answer += (
            f"基礎回答：這是一個關於 {keywords[0] if keywords else '未知主題'} 的簡單查詢結果。"
        )

        # 較低的置信度，因為是最基礎的策略
        basic_confidence = 0.5

        # 添加Naive RAG特有的元數據
        for source in sources:
            source["metadata"]["naive_rag_features"] = {
                "simple_matching": True,
                "keyword_based": True,
                "fast_retrieval": True,
                "basic_strategy": True,
            }

        return RAGQueryResult(
            query=query,
            answer=naive_answer,
            sources=sources,
            strategy_used=RAGStrategy.NAIVE_RAG,
            processing_time=0.0,
            confidence_score=basic_confidence,
            metadata={
                "keywords_extracted": keywords,
                "retrieval_method": "simple_keyword_match",
                "strategy_level": "basic",
                "processing_complexity": "minimal",
                "suitable_for": ["simple_queries", "quick_answers", "basic_search"],
            },
        )

    def _generate_cache_key(self, query: str, kwargs: dict) -> str:
        """生成快取鍵"""
        # 簡化的快取鍵生成
        key_data = {
            "query": query.lower().strip(),
            "strategy": kwargs.get("strategy", "default"),
            "top_k": kwargs.get("top_k", self.config.top_k_final),
        }
        return str(hash(json.dumps(key_data, sort_keys=True)))

    def _cache_result(self, cache_key: str, result: RAGQueryResult):
        """快取結果"""
        if len(self.query_cache) >= self.config.cache_max_size:
            # 移除最舊的快取項目
            oldest_key = next(iter(self.query_cache))
            del self.query_cache[oldest_key]

        self.query_cache[cache_key] = result

    def _log_query_metrics(self, query: str, result: RAGQueryResult, cache_hit: bool = False):
        """記錄查詢指標"""
        metrics = QueryMetrics(
            query=query,
            response_time=result.processing_time,
            num_results=len(result.sources),
            cache_hit=cache_hit,
            accuracy_score=result.confidence_score,
        )

        self.monitor.log_query(metrics)

    def _update_adaptive_learning(self, query: str, strategy: RAGStrategy, result: RAGQueryResult):
        """更新自適應學習"""
        # 更新策略統計
        stats = self.strategy_stats[strategy]
        stats["count"] += 1

        # 更新平均時間
        old_avg = stats["avg_time"]
        stats["avg_time"] = (old_avg * (stats["count"] - 1) + result.processing_time) / stats[
            "count"
        ]

        # 更新成功率（基於置信度）
        success = 1.0 if result.confidence_score > 0.7 else 0.0
        old_success_rate = stats["success_rate"]
        stats["success_rate"] = (old_success_rate * (stats["count"] - 1) + success) / stats["count"]

    def _get_best_performing_strategy(self) -> RAGStrategy:
        """獲取最佳性能策略"""
        best_strategy = RAGStrategy.HYBRID_BALANCED
        best_score = 0.0

        for strategy, stats in self.strategy_stats.items():
            if stats["count"] > 0:
                # 綜合評分：成功率權重70%，速度權重30%
                speed_score = max(0, 1.0 - stats["avg_time"] / 5.0)  # 5秒作為基準
                composite_score = stats["success_rate"] * 0.7 + speed_score * 0.3

                if composite_score > best_score:
                    best_score = composite_score
                    best_strategy = strategy

        return best_strategy

    def optimize_configuration(self) -> dict[str, Any]:
        """優化配置參數"""
        current_stats = self.monitor.get_current_stats()

        optimizations = {
            "timestamp": datetime.now().isoformat(),
            "current_performance": current_stats,
            "optimizations_applied": [],
        }

        # 基於響應時間優化
        if current_stats.get("response_time", {}).get("avg", 0) > 2.0:
            # 響應時間過長，減少檢索數量
            if self.config.top_k_vector > 5:
                self.config.top_k_vector -= 2
                optimizations["optimizations_applied"].append("減少向量檢索數量")

            if self.config.top_k_graph > 3:
                self.config.top_k_graph -= 1
                optimizations["optimizations_applied"].append("減少圖譜檢索數量")

        # 基於快取命中率優化
        cache_hit_rate = self.cache_stats["hits"] / max(self.cache_stats["total"], 1)
        if cache_hit_rate < 0.3:
            # 快取命中率過低，增加快取大小
            self.config.cache_max_size = min(self.config.cache_max_size + 200, 2000)
            optimizations["optimizations_applied"].append("增加快取大小")

        # 基於策略性能優化權重
        best_strategy = self._get_best_performing_strategy()
        if best_strategy == RAGStrategy.GRAPH_ONLY:
            self.config.graph_weight = min(self.config.graph_weight + 0.1, 0.8)
            self.config.vector_weight = 1.0 - self.config.graph_weight
            optimizations["optimizations_applied"].append("增加圖譜權重")
        elif best_strategy == RAGStrategy.VECTOR_ONLY:
            self.config.vector_weight = min(self.config.vector_weight + 0.1, 0.8)
            self.config.graph_weight = 1.0 - self.config.vector_weight
            optimizations["optimizations_applied"].append("增加向量權重")

        self.optimization_history.append(optimizations)
        logger.info(f"✅ 配置優化完成: {len(optimizations['optimizations_applied'])} 項調整")

        return optimizations

    def get_system_status(self) -> dict[str, Any]:
        """獲取系統狀態"""
        current_stats = self.monitor.get_current_stats()

        status = {
            "timestamp": datetime.now().isoformat(),
            "components": {
                "vector_retriever": "ready" if self._vector_retriever else "not_initialized",
                "graph_retriever": "ready" if self._graph_instance else "not_initialized",
                "performance_monitor": "ready",
                "cache": "ready" if self.config.enable_cache else "disabled",
            },
            "configuration": {
                "strategy": self.config.strategy.value,
                "vector_weight": self.config.vector_weight,
                "graph_weight": self.config.graph_weight,
                "cache_enabled": self.config.enable_cache,
                "top_k_vector": self.config.top_k_vector,
                "top_k_graph": self.config.top_k_graph,
            },
            "performance": current_stats,
            "cache_stats": {
                **self.cache_stats,
                "hit_rate": self.cache_stats["hits"] / max(self.cache_stats["total"], 1),
            },
            "strategy_performance": self.strategy_stats,
            "optimization_count": len(self.optimization_history),
        }

        return status

    async def batch_query(self, queries: list[str], **kwargs) -> list[RAGQueryResult]:
        """批次查詢處理"""
        logger.info(f"🔄 開始批次處理 {len(queries)} 個查詢...")

        # 創建異步任務
        tasks = [self.query(query, **kwargs) for query in queries]

        # 並行執行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 處理異常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ 查詢 {i + 1} 失敗: {result}")
                error_result = RAGQueryResult(
                    query=queries[i],
                    answer=f"批次查詢失敗: {str(result)}",
                    sources=[],
                    strategy_used=RAGStrategy.HYBRID_BALANCED,
                    processing_time=0.0,
                    confidence_score=0.0,
                    metadata={"error": str(result)},
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)

        logger.info(
            f"✅ 批次查詢完成，成功: {len([r for r in processed_results if r.confidence_score > 0])}/{len(queries)}"
        )
        return processed_results

    def cleanup(self):
        """清理資源"""
        if self.executor:
            self.executor.shutdown(wait=True)
        logger.info("✅ RAG優化管理器資源清理完成")


# 使用示例
if __name__ == "__main__":

    async def main():
        # 初始化優化管理器
        optimizer = IntegratedRAGOptimizer()

        if not optimizer.initialize_components():
            print("❌ 組件初始化失敗")
            return

        print("🎉 整合多模態RAG優化管理器啟動成功！")

        # 測試查詢
        test_queries = [
            "達文西的藝術特色是什麼？",
            "印象派與後印象派的差異",
            "哪些藝術家影響了畢卡索？",
        ]

        for query in test_queries:
            print(f"\n🔍 測試查詢: {query}")
            result = await optimizer.query(query)
            print(f"📊 策略: {result.strategy_used.value}")
            print(f"⏱️ 時間: {result.processing_time:.2f}s")
            print(f"🎯 置信度: {result.confidence_score:.2f}")
            print(f"💡 回答: {result.answer[:100]}...")

        # 批次查詢測試
        print("\n🔄 批次查詢測試...")
        batch_results = await optimizer.batch_query(test_queries)
        print(f"✅ 批次完成: {len(batch_results)} 個結果")

        # 性能優化
        print("\n⚙️ 執行性能優化...")
        optimization_report = optimizer.optimize_configuration()
        print(f"🔧 優化項目: {len(optimization_report['optimizations_applied'])}")

        # 系統狀態
        print("\n📊 系統狀態報告:")
        status = optimizer.get_system_status()
        print(f"組件狀態: {status['components']}")
        print(f"快取命中率: {status['cache_stats']['hit_rate']:.1%}")

        # 清理
        optimizer.cleanup()

    # 運行測試
    asyncio.run(main())
