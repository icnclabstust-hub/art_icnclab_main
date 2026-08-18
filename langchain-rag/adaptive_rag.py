#!/usr/bin/env python3
"""
自適應多策略 RAG 系統
根據查詢類型自動選擇最佳檢索策略
"""

import asyncio
import logging
import re
from enum import Enum
from typing import Any

from multimodal_rag import ArtHistoryRAGSystem, RAGConfig

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """查詢類型枚舉"""

    TEXT_ONLY = "text_only"
    VISUAL_FOCUSED = "visual_focused"
    RELATIONAL = "relational"
    TEMPORAL = "temporal"
    COMPARATIVE = "comparative"


class QueryClassifier:
    """查詢分類器"""

    def __init__(self):
        # 查詢模式定義
        self.patterns = {
            QueryType.VISUAL_FOCUSED: [
                r"顏色|色彩|構圖|筆觸|線條|形狀",
                r"明暗|光影|透視|風格|畫面",
                r"color|composition|brush|line|visual",
                r"看起來|外觀|視覺|圖像",
            ],
            QueryType.RELATIONAL: [
                r"關係|影響|師承|學派",
                r"誰.*誰|與.*關係|受.*影響",
                r"relationship|influence|school|movement",
                r"比較.*與|對比.*和",
            ],
            QueryType.TEMPORAL: [
                r"\d+年|\d+世紀|時期|年代|歷史",
                r"之前|之後|同時期|當時",
                r"century|period|era|history|before|after",
                r"發展|演變|變遷|歷程",
            ],
            QueryType.COMPARATIVE: [
                r"比較|對比|差異|不同|相似",
                r"與.*比|和.*比|.*與.*區別",
                r"compare|contrast|difference|similar",
                r"優缺點|特色對比",
            ],
        }

        # 關鍵詞權重
        self.weights = {
            QueryType.VISUAL_FOCUSED: 1.2,
            QueryType.RELATIONAL: 1.1,
            QueryType.TEMPORAL: 1.0,
            QueryType.COMPARATIVE: 1.3,
            QueryType.TEXT_ONLY: 0.8,
        }

    def classify_query(self, query: str) -> QueryType:
        """分類查詢類型"""
        scores = {query_type: 0.0 for query_type in QueryType}
        query_lower = query.lower()

        # 計算各類型匹配分數
        for query_type, patterns in self.patterns.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, query_lower))
                scores[query_type] += matches * self.weights[query_type]

        # 特殊規則
        if any(word in query_lower for word in ["什麼", "如何", "為什麼", "是什麼"]):
            scores[QueryType.TEXT_ONLY] += 0.5

        # 返回得分最高的類型
        if max(scores.values()) == 0:
            return QueryType.TEXT_ONLY

        return max(scores.items(), key=lambda x: x[1])[0]

    def get_classification_confidence(self, query: str) -> dict[str, float]:
        """獲取分類信心度"""
        scores = {query_type.value: 0.0 for query_type in QueryType}
        query_lower = query.lower()

        for query_type, patterns in self.patterns.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, query_lower))
                scores[query_type.value] += matches * self.weights[query_type]

        # 正規化分數
        total_score = sum(scores.values()) or 1.0
        return {k: v / total_score for k, v in scores.items()}


class AdaptiveRAGSystem:
    """自適應 RAG 系統"""

    def __init__(self, config: RAGConfig):
        self.config = config
        self.classifier = QueryClassifier()
        self.base_rag = None
        self.strategies = {}
        self.query_history = []

    async def initialize(self):
        """初始化系統"""
        logger.info("🚀 初始化自適應多策略 RAG 系統...")

        # 初始化基礎 RAG 系統
        self.base_rag = ArtHistoryRAGSystem(self.config)
        await self.base_rag.initialize()

        # 初始化各種策略
        self.strategies = {
            QueryType.TEXT_ONLY: self._text_strategy,
            QueryType.VISUAL_FOCUSED: self._visual_strategy,
            QueryType.RELATIONAL: self._relational_strategy,
            QueryType.TEMPORAL: self._temporal_strategy,
            QueryType.COMPARATIVE: self._comparative_strategy,
        }

        logger.info("✅ 自適應 RAG 系統初始化完成")

    async def query(self, question: str) -> dict[str, Any]:
        """執行自適應查詢"""
        try:
            # 1. 分類查詢
            query_type = self.classifier.classify_query(question)
            confidence = self.classifier.get_classification_confidence(question)

            logger.info(f"🔍 查詢類型: {query_type.value}")
            logger.info(f"📊 信心度分佈: {confidence}")

            # 2. 選擇策略
            strategy_func = self.strategies.get(query_type, self._text_strategy)

            # 3. 執行查詢
            result = await strategy_func(question)

            # 4. 添加元數據
            result.update(
                {
                    "query_type": query_type.value,
                    "classification_confidence": confidence,
                    "strategy_used": strategy_func.__name__,
                }
            )

            # 5. 記錄查詢歷史
            self.query_history.append(
                {
                    "question": question,
                    "query_type": query_type.value,
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )

            return result

        except Exception as e:
            logger.error(f"❌ 自適應查詢失敗: {e}")
            return {
                "question": question,
                "answer": f"查詢處理失敗: {str(e)}",
                "query_type": "error",
                "classification_confidence": {},
                "strategy_used": "fallback",
            }

    async def _text_strategy(self, question: str) -> dict[str, Any]:
        """純文本策略"""
        logger.info("📝 使用純文本策略")
        return await self.base_rag.query(question)

    async def _visual_strategy(self, question: str) -> dict[str, Any]:
        """視覺重點策略"""
        logger.info("🎨 使用視覺重點策略")

        # 增強查詢以包含更多視覺關鍵詞
        enhanced_query = self._enhance_visual_query(question)

        # 使用多模態檢索
        result = await self.base_rag.query(enhanced_query)

        # 後處理：強調視覺描述
        result["answer"] = self._enhance_visual_response(result["answer"])

        return result

    async def _relational_strategy(self, question: str) -> dict[str, Any]:
        """關係重點策略"""
        logger.info("🔗 使用關係重點策略")

        # 擴展查詢以包含關係資訊
        expanded_query = self._expand_relational_query(question)

        result = await self.base_rag.query(expanded_query)

        # 後處理：結構化關係資訊
        result["answer"] = self._structure_relational_response(result["answer"])

        return result

    async def _temporal_strategy(self, question: str) -> dict[str, Any]:
        """時間重點策略"""
        logger.info("⏰ 使用時間重點策略")

        # 增加時間上下文
        temporal_query = self._add_temporal_context(question)

        result = await self.base_rag.query(temporal_query)

        # 後處理：添加時間軸資訊
        result["answer"] = self._add_timeline_info(result["answer"])

        return result

    async def _comparative_strategy(self, question: str) -> dict[str, Any]:
        """比較分析策略"""
        logger.info("⚖️ 使用比較分析策略")

        # 結構化比較查詢
        structured_query = self._structure_comparison_query(question)

        result = await self.base_rag.query(structured_query)

        # 後處理：格式化比較結果
        result["answer"] = self._format_comparison_response(result["answer"])

        return result

    def _enhance_visual_query(self, query: str) -> str:
        """增強視覺查詢"""
        visual_contexts = [
            "請詳細描述視覺特色",
            "包括色彩、構圖、筆觸等技法分析",
            "說明畫面的視覺效果",
        ]

        return f"{query} {' '.join(visual_contexts)}"

    def _enhance_visual_response(self, response: str) -> str:
        """增強視覺回應"""
        if "色彩" not in response and "構圖" not in response:
            response += "\n\n【視覺分析】需要結合具體作品進行更詳細的視覺技法分析。"

        return response

    def _expand_relational_query(self, query: str) -> str:
        """擴展關係查詢"""
        relation_contexts = [
            "請說明相關的藝術家關係",
            "包括師承、影響、派別歸屬",
            "分析藝術運動之間的聯繫",
        ]

        return f"{query} {' '.join(relation_contexts)}"

    def _structure_relational_response(self, response: str) -> str:
        """結構化關係回應"""
        # 簡化版本：添加關係標題
        if "影響" in response or "關係" in response:
            return f"【關係分析】\n{response}"
        return response

    def _add_temporal_context(self, query: str) -> str:
        """添加時間上下文"""
        temporal_contexts = [
            "請說明歷史背景和時代特色",
            "包括前後時期的發展脈絡",
            "分析時間演進關係",
        ]

        return f"{query} {' '.join(temporal_contexts)}"

    def _add_timeline_info(self, response: str) -> str:
        """添加時間軸資訊"""
        # 檢查是否包含年份資訊
        years = re.findall(r"\d{4}年?|\d+世紀", response)
        if years:
            return f"【時間軸】{', '.join(years)}\n\n{response}"
        return response

    def _structure_comparison_query(self, query: str) -> str:
        """結構化比較查詢"""
        comparison_contexts = ["請進行系統性比較分析", "包括相似點和差異點", "說明各自的特色和優勢"]

        return f"{query} {' '.join(comparison_contexts)}"

    def _format_comparison_response(self, response: str) -> str:
        """格式化比較回應"""
        # 簡化版本：添加比較結構
        if "比較" in response or "差異" in response:
            return f"【比較分析】\n{response}"
        return response

    def get_query_statistics(self) -> dict[str, Any]:
        """獲取查詢統計"""
        if not self.query_history:
            return {"message": "暫無查詢記錄"}

        # 統計查詢類型分佈
        type_counts = {}
        for record in self.query_history:
            query_type = record["query_type"]
            type_counts[query_type] = type_counts.get(query_type, 0) + 1

        # 計算各類型比例
        total_queries = len(self.query_history)
        type_ratios = {k: v / total_queries for k, v in type_counts.items()}

        return {
            "total_queries": total_queries,
            "query_type_distribution": type_counts,
            "query_type_ratios": type_ratios,
            "recent_queries": self.query_history[-5:]
            if len(self.query_history) > 5
            else self.query_history,
        }

    async def optimize_strategies(self):
        """優化策略（基於查詢歷史）"""
        logger.info("🔧 開始策略優化...")

        stats = self.get_query_statistics()

        # 根據查詢分佈調整權重
        if "query_type_ratios" in stats:
            ratios = stats["query_type_ratios"]

            # 最常用的查詢類型獲得更高優先級
            most_common_type = max(ratios.items(), key=lambda x: x[1])[0]
            logger.info(f"📊 最常用查詢類型: {most_common_type}")

            # 調整分類器權重（簡化實現）
            for query_type in QueryType:
                if query_type.value == most_common_type:
                    self.classifier.weights[query_type] *= 1.1

        logger.info("✅ 策略優化完成")


# 測試和示例用法
async def main():
    """主測試函數"""
    config = RAGConfig()
    adaptive_rag = AdaptiveRAGSystem(config)
    await adaptive_rag.initialize()

    # 測試不同類型的查詢
    test_queries = [
        "印象派繪畫有什麼特色？",  # TEXT_ONLY
        "莫內的畫作色彩有什麼特別的地方？",  # VISUAL_FOCUSED
        "畢卡索與布拉克的關係如何？",  # RELATIONAL
        "19世紀藝術發展歷程是什麼？",  # TEMPORAL
        "印象派與後印象派有什麼區別？",  # COMPARATIVE
    ]

    print("🤖 自適應多策略 RAG 系統測試\n" + "=" * 60)

    for i, query in enumerate(test_queries, 1):
        print(f"\n【測試 {i}】{query}")
        print("-" * 40)

        result = await adaptive_rag.query(query)

        print(f"查詢類型: {result['query_type']}")
        print(f"使用策略: {result['strategy_used']}")
        print(f"回答: {result['answer'][:200]}...")

        # 顯示分類信心度
        confidence = result.get("classification_confidence", {})
        if confidence:
            print("分類信心度:")
            for query_type, conf in confidence.items():
                if conf > 0:
                    print(f"  {query_type}: {conf:.2f}")

    # 顯示查詢統計
    print("\n" + "=" * 60)
    stats = adaptive_rag.get_query_statistics()
    print("📊 查詢統計:")
    print(f"  總查詢數: {stats.get('total_queries', 0)}")
    print("  查詢類型分佈:")
    for query_type, count in stats.get("query_type_distribution", {}).items():
        ratio = stats.get("query_type_ratios", {}).get(query_type, 0)
        print(f"    {query_type}: {count} ({ratio:.1%})")


if __name__ == "__main__":
    asyncio.run(main())
