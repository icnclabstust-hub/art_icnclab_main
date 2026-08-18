#!/usr/bin/env python3
"""
RAG 系統優化管理器
實現核心優化策略：混合檢索、智能快取、異步處理
"""

import asyncio
import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
import redis
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

# LangChain imports
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

logger = logging.getLogger(__name__)


@dataclass
class OptimizationConfig:
    """優化配置"""

    enable_hybrid_retrieval: bool = True
    enable_smart_cache: bool = True
    enable_async_processing: bool = True
    enable_query_expansion: bool = True

    # 混合檢索權重
    vector_weight: float = 0.7
    bm25_weight: float = 0.3

    # 快取配置
    cache_ttl: int = 3600  # 1小時
    max_cache_size: int = 10000

    # 異步處理配置
    max_workers: int = 4
    batch_size: int = 32
    batch_timeout: float = 0.1


class SmartCache:
    """智能快取系統"""

    def __init__(self, config: OptimizationConfig, redis_client=None):
        self.config = config
        self.redis_client = redis_client or redis.Redis(
            host="localhost", port=6379, db=0, decode_responses=True
        )
        self.local_cache = {}
        self.cache_stats = {"hits": 0, "misses": 0, "total_requests": 0}

    def _generate_cache_key(self, query: str, context: dict = None) -> str:
        """生成快取鍵"""
        key_data = f"rag_query:{query}"
        if context:
            key_data += f":{json.dumps(context, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def get(self, query: str, context: dict = None) -> dict[str, Any] | None:
        """獲取快取結果"""
        self.cache_stats["total_requests"] += 1
        cache_key = self._generate_cache_key(query, context)

        # 先檢查本地快取
        if cache_key in self.local_cache:
            cached_data = self.local_cache[cache_key]
            if time.time() - cached_data["timestamp"] < self.config.cache_ttl:
                self.cache_stats["hits"] += 1
                logger.debug(f"本地快取命中: {cache_key}")
                return cached_data["data"]
            else:
                # 過期，刪除
                del self.local_cache[cache_key]

        # 檢查 Redis 快取
        try:
            cached_result = self.redis_client.get(cache_key)
            if cached_result:
                data = json.loads(cached_result)
                self.cache_stats["hits"] += 1

                # 同時更新本地快取
                self.local_cache[cache_key] = {"data": data, "timestamp": time.time()}

                logger.debug(f"Redis 快取命中: {cache_key}")
                return data
        except Exception as e:
            logger.warning(f"Redis 快取讀取失敗: {e}")

        self.cache_stats["misses"] += 1
        return None

    async def set(self, query: str, result: dict[str, Any], context: dict = None):
        """設置快取"""
        cache_key = self._generate_cache_key(query, context)

        # 更新本地快取
        self.local_cache[cache_key] = {"data": result, "timestamp": time.time()}

        # 限制本地快取大小
        if len(self.local_cache) > self.config.max_cache_size:
            oldest_key = min(
                self.local_cache.keys(), key=lambda k: self.local_cache[k]["timestamp"]
            )
            del self.local_cache[oldest_key]

        # 更新 Redis 快取
        try:
            self.redis_client.setex(
                cache_key, self.config.cache_ttl, json.dumps(result, ensure_ascii=False)
            )
            logger.debug(f"結果已快取: {cache_key}")
        except Exception as e:
            logger.warning(f"Redis 快取寫入失敗: {e}")

    def get_hit_rate(self) -> float:
        """獲取快取命中率"""
        if self.cache_stats["total_requests"] == 0:
            return 0.0
        return self.cache_stats["hits"] / self.cache_stats["total_requests"]

    def get_stats(self) -> dict[str, Any]:
        """獲取快取統計"""
        return {
            **self.cache_stats,
            "hit_rate": self.get_hit_rate(),
            "local_cache_size": len(self.local_cache),
        }


class HybridRetriever(BaseRetriever):
    """混合檢索器：結合向量檢索和 BM25"""

    def __init__(
        self,
        vector_retriever: BaseRetriever,
        documents: list[Document],
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
    ):
        self.vector_retriever = vector_retriever
        self.bm25_retriever = BM25Retriever.from_documents(documents)
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight

        # 創建集成檢索器
        self.ensemble_retriever = EnsembleRetriever(
            retrievers=[self.vector_retriever, self.bm25_retriever],
            weights=[vector_weight, bm25_weight],
        )

    def _get_relevant_documents(self, query: str, **kwargs) -> list[Document]:
        """獲取相關文檔"""
        return self.ensemble_retriever.get_relevant_documents(query, **kwargs)


class QueryExpander:
    """查詢擴展器"""

    def __init__(self, art_terminology: dict[str, list[str]] = None):
        self.art_terminology = art_terminology or self._get_default_terminology()
        self.expansion_cache = {}

    def _get_default_terminology(self) -> dict[str, list[str]]:
        """獲取默認藝術術語字典"""
        return {
            "印象派": ["光線", "色彩", "戶外寫生", "筆觸", "瞬間印象"],
            "文藝復興": ["人文主義", "透視法", "古典", "比例", "和諧"],
            "巴洛克": ["戲劇性", "明暗對比", "動感", "豪華", "宗教"],
            "現代主義": ["抽象", "實驗", "創新", "打破傳統", "個性化"],
            "色彩": ["明度", "彩度", "色相", "對比", "調和"],
            "構圖": ["平衡", "對稱", "黃金比例", "視覺重心", "線條"],
            "技法": ["筆觸", "畫法", "材料", "工具", "表現手法"],
        }

    @lru_cache(maxsize=1000)
    def expand_query(self, query: str) -> str:
        """擴展查詢"""
        expanded_terms = set()
        query_words = query.split()

        # 添加術語同義詞
        for word in query_words:
            if word in self.art_terminology:
                expanded_terms.update(self.art_terminology[word][:3])  # 限制3個擴展詞

        # 基於語意的擴展（簡化版）
        semantic_expansions = self._get_semantic_expansions(query)
        expanded_terms.update(semantic_expansions)

        if expanded_terms:
            expansion = " ".join(expanded_terms)
            return f"{query} {expansion}"

        return query

    def _get_semantic_expansions(self, query: str) -> list[str]:
        """獲取語意擴展詞"""
        semantic_rules = {
            "畫家": ["藝術家", "創作者", "畫師"],
            "作品": ["畫作", "藝術品", "創作"],
            "風格": ["流派", "特色", "表現形式"],
            "歷史": ["發展", "演變", "背景"],
            "技法": ["手法", "方法", "表現技巧"],
        }

        expansions = []
        for key, values in semantic_rules.items():
            if key in query:
                expansions.extend(values[:2])  # 限制2個擴展詞

        return expansions


class AsyncProcessor:
    """異步處理器"""

    def __init__(self, config: OptimizationConfig):
        self.config = config
        self.executor = ThreadPoolExecutor(max_workers=config.max_workers)
        self.pending_queries = []
        self.processing_lock = asyncio.Lock()

    async def process_query(self, query_func, *args, **kwargs) -> Any:
        """異步處理查詢"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, query_func, *args, **kwargs)

    async def batch_process(self, queries: list[str], process_func) -> list[Any]:
        """批次處理查詢"""
        if len(queries) <= 1:
            # 單個查詢直接處理
            if queries:
                return [await self.process_query(process_func, queries[0])]
            return []

        # 並行處理多個查詢
        tasks = []
        for query in queries:
            task = asyncio.create_task(self.process_query(process_func, query))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 處理異常結果
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"批次處理錯誤: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)

        return processed_results

    async def add_to_batch(self, query: str) -> Any | None:
        """添加到批次處理隊列"""
        async with self.processing_lock:
            self.pending_queries.append(query)

            if len(self.pending_queries) >= self.config.batch_size:
                # 批次已滿，立即處理
                batch = self.pending_queries[: self.config.batch_size]
                self.pending_queries = self.pending_queries[self.config.batch_size :]
                return batch

        # 等待更多查詢或超時
        await asyncio.sleep(self.config.batch_timeout)

        async with self.processing_lock:
            if self.pending_queries:
                batch = self.pending_queries.copy()
                self.pending_queries.clear()
                return batch

        return None

    def shutdown(self):
        """關閉執行器"""
        self.executor.shutdown(wait=True)


class OptimizationManager:
    """優化管理器"""

    def __init__(self, config: OptimizationConfig):
        self.config = config
        self.smart_cache = SmartCache(config) if config.enable_smart_cache else None
        self.query_expander = QueryExpander() if config.enable_query_expansion else None
        self.async_processor = AsyncProcessor(config) if config.enable_async_processing else None
        self.performance_metrics = {
            "total_queries": 0,
            "cache_hits": 0,
            "avg_response_time": 0,
            "response_times": [],
        }

    async def optimize_retrieval(
        self, base_retriever: BaseRetriever, documents: list[Document] = None
    ) -> BaseRetriever:
        """優化檢索器"""
        if not self.config.enable_hybrid_retrieval or not documents:
            return base_retriever

        logger.info("🔧 啟用混合檢索優化...")

        hybrid_retriever = HybridRetriever(
            vector_retriever=base_retriever,
            documents=documents,
            vector_weight=self.config.vector_weight,
            bm25_weight=self.config.bm25_weight,
        )

        return hybrid_retriever

    async def optimized_query(
        self, retriever: BaseRetriever, query: str, context: dict = None
    ) -> dict[str, Any]:
        """執行優化的查詢"""
        start_time = time.time()

        try:
            # 1. 檢查快取
            if self.smart_cache:
                cached_result = await self.smart_cache.get(query, context)
                if cached_result:
                    logger.debug(f"快取命中: {query[:50]}...")
                    return cached_result

            # 2. 查詢擴展
            expanded_query = query
            if self.query_expander:
                expanded_query = self.query_expander.expand_query(query)
                if expanded_query != query:
                    logger.debug(f"查詢擴展: {query} -> {expanded_query}")

            # 3. 執行檢索
            if self.async_processor:
                # 異步檢索
                documents = await self.async_processor.process_query(
                    retriever.get_relevant_documents, expanded_query
                )
            else:
                # 同步檢索
                documents = retriever.get_relevant_documents(expanded_query)

            # 4. 組織結果
            result = {
                "query": query,
                "expanded_query": expanded_query if expanded_query != query else None,
                "documents": [
                    {
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "relevance_score": getattr(doc, "relevance_score", None),
                    }
                    for doc in documents
                ],
                "retrieval_time": time.time() - start_time,
                "num_results": len(documents),
            }

            # 5. 更新快取
            if self.smart_cache:
                await self.smart_cache.set(query, result, context)

            # 6. 更新性能指標
            self._update_metrics(time.time() - start_time)

            return result

        except Exception as e:
            logger.error(f"優化查詢失敗: {e}")
            error_result = {
                "query": query,
                "error": str(e),
                "retrieval_time": time.time() - start_time,
                "num_results": 0,
            }
            return error_result

    def _update_metrics(self, response_time: float):
        """更新性能指標"""
        self.performance_metrics["total_queries"] += 1
        self.performance_metrics["response_times"].append(response_time)

        # 保持最近1000次查詢的記錄
        if len(self.performance_metrics["response_times"]) > 1000:
            self.performance_metrics["response_times"] = self.performance_metrics["response_times"][
                -1000:
            ]

        # 計算平均響應時間
        self.performance_metrics["avg_response_time"] = np.mean(
            self.performance_metrics["response_times"]
        )

    def get_optimization_stats(self) -> dict[str, Any]:
        """獲取優化統計"""
        stats = {
            "optimization_config": {
                "hybrid_retrieval": self.config.enable_hybrid_retrieval,
                "smart_cache": self.config.enable_smart_cache,
                "async_processing": self.config.enable_async_processing,
                "query_expansion": self.config.enable_query_expansion,
            },
            "performance_metrics": self.performance_metrics.copy(),
        }

        if self.smart_cache:
            cache_stats = self.smart_cache.get_stats()
            stats["cache_stats"] = cache_stats
            self.performance_metrics["cache_hits"] = cache_stats["hits"]

        # 計算優化效果
        if self.performance_metrics["response_times"]:
            stats["performance_metrics"]["p95_response_time"] = np.percentile(
                self.performance_metrics["response_times"], 95
            )
            stats["performance_metrics"]["p99_response_time"] = np.percentile(
                self.performance_metrics["response_times"], 99
            )

        return stats

    async def cleanup(self):
        """清理資源"""
        if self.async_processor:
            self.async_processor.shutdown()

        logger.info("✅ 優化管理器清理完成")


# 使用示例
async def demo_optimization():
    """演示優化功能"""
    # 配置
    config = OptimizationConfig(
        enable_hybrid_retrieval=True,
        enable_smart_cache=True,
        enable_async_processing=True,
        enable_query_expansion=True,
    )

    # 創建優化管理器
    optimizer = OptimizationManager(config)

    # 模擬查詢
    test_queries = [
        "印象派繪畫的特色",
        "達文西的藝術技法",
        "巴洛克與古典主義的區別",
        "現代藝術的發展歷程",
    ]

    print("🚀 RAG 優化系統演示\n" + "=" * 50)

    # 注意：這裡需要實際的檢索器和文檔
    # mock_retriever = MockRetriever()  # 需要實際實現
    # mock_documents = []  # 需要實際文檔

    for i, query in enumerate(test_queries, 1):
        print(f"\n【查詢 {i}】{query}")
        print("-" * 30)

        # result = await optimizer.optimized_query(mock_retriever, query)
        # print(f"檢索時間: {result['retrieval_time']:.3f}秒")
        # print(f"結果數量: {result['num_results']}")

        # 模擬處理時間
        await asyncio.sleep(0.1)

    # 顯示優化統計
    stats = optimizer.get_optimization_stats()
    print("\n" + "=" * 50)
    print("📊 優化統計:")
    print(f"總查詢數: {stats['performance_metrics']['total_queries']}")
    print(f"平均響應時間: {stats['performance_metrics']['avg_response_time']:.3f}秒")

    if "cache_stats" in stats:
        cache_stats = stats["cache_stats"]
        print(f"快取命中率: {cache_stats['hit_rate']:.1%}")

    # 清理
    await optimizer.cleanup()


if __name__ == "__main__":
    asyncio.run(demo_optimization())
