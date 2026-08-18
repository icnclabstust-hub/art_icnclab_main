#!/usr/bin/env python3
"""
增強型自適應RAG策略管理器
實現更智能的多模態檢索策略選擇和優化
"""

import logging
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class ContextualRAGStrategy(Enum):
    """情境化RAG策略"""

    TEXT_SEMANTIC = "text_semantic"  # 純文本語義搜索
    VISUAL_MULTIMODAL = "visual_multimodal"  # 視覺多模態融合
    KNOWLEDGE_GRAPH = "knowledge_graph"  # 知識圖譜推理
    TEMPORAL_AWARE = "temporal_aware"  # 時序感知檢索
    HYBRID_FUSION = "hybrid_fusion"  # 多策略融合
    CONTEXTUAL_ADAPTIVE = "contextual_adaptive"  # 情境自適應


class QueryIntent(Enum):
    """查詢意圖分析"""

    FACTUAL_LOOKUP = "factual_lookup"  # 事實查詢
    ANALYTICAL_REASONING = "analytical_reasoning"  # 分析推理
    COMPARATIVE_ANALYSIS = "comparative_analysis"  # 對比分析
    CREATIVE_INTERPRETATION = "creative_interpretation"  # 創意詮釋
    HISTORICAL_CONTEXT = "historical_context"  # 歷史脈絡
    VISUAL_DESCRIPTION = "visual_description"  # 視覺描述


@dataclass
class QueryContext:
    """查詢情境信息"""

    query_text: str
    user_id: str | None = None
    session_id: str | None = None
    query_intent: QueryIntent | None = None
    domain_category: str = "general"
    complexity_score: float = 0.0
    multimodal_components: list[str] = field(default_factory=list)
    temporal_references: list[str] = field(default_factory=list)
    entity_mentions: list[str] = field(default_factory=list)
    previous_queries: list[str] = field(default_factory=list)


@dataclass
class StrategyPerformance:
    """策略性能統計"""

    strategy: ContextualRAGStrategy
    total_queries: int = 0
    success_count: int = 0
    avg_response_time: float = 0.0
    avg_confidence: float = 0.0
    avg_user_satisfaction: float = 0.0
    recent_performances: deque = field(default_factory=lambda: deque(maxlen=100))
    last_updated: datetime = field(default_factory=datetime.now)


class EnhancedAdaptiveManager:
    """增強型自適應策略管理器"""

    def __init__(self, learning_rate: float = 0.1, exploration_rate: float = 0.2):
        self.learning_rate = learning_rate
        self.exploration_rate = exploration_rate

        # 性能追蹤
        self.strategy_performances = {
            strategy: StrategyPerformance(strategy) for strategy in ContextualRAGStrategy
        }

        # 情境模式學習
        self.context_patterns = defaultdict(list)
        self.query_embeddings = {}  # 查詢向量表示

        # 用戶偏好學習
        self.user_preferences = defaultdict(dict)

        # 實時優化
        self.optimization_history = []
        self.last_optimization = datetime.now()

        # 多臂老虎機（Multi-Armed Bandit）
        self.strategy_rewards = defaultdict(list)
        self.strategy_selections = defaultdict(int)

    async def select_optimal_strategy(self, context: QueryContext) -> ContextualRAGStrategy:
        """選擇最優檢索策略"""
        # 1.（原本此處預先計算 intent/complexity 分數，但 _get_candidate_strategies
        #    與 _calculate_base_score 各自重算 intent，複雜度則從未接進任何評分——
        #    屬設計缺口。移除死計算；若要讓複雜度影響策略選擇，應把
        #    _calculate_complexity(context) 納入下方 strategy_scores 的加權。

        # 2. 獲取候選策略
        candidate_strategies = self._get_candidate_strategies(context)

        # 3. 基於歷史性能評分
        strategy_scores = {}
        for strategy in candidate_strategies:
            base_score = self._calculate_base_score(strategy, context)
            historical_score = self._get_historical_performance_score(strategy, context)
            exploration_bonus = self._calculate_exploration_bonus(strategy)

            strategy_scores[strategy] = (
                base_score * 0.4 + historical_score * 0.5 + exploration_bonus * 0.1
            )

        # 4. 應用ε-greedy策略
        if np.random.random() < self.exploration_rate:
            # 探索：隨機選擇
            selected_strategy = np.random.choice(list(candidate_strategies))
            logger.info(f"🎲 探索模式選擇策略: {selected_strategy.value}")
        else:
            # 利用：選擇最佳策略
            selected_strategy = max(strategy_scores, key=strategy_scores.get)
            logger.info(
                f"🎯 最優策略選擇: {selected_strategy.value} "
                f"(分數: {strategy_scores[selected_strategy]:.3f})"
            )

        # 5. 記錄選擇
        self.strategy_selections[selected_strategy] += 1

        return selected_strategy

    def _analyze_query_intent(self, context: QueryContext) -> dict[QueryIntent, float]:
        """分析查詢意圖"""
        query_lower = context.query_text.lower()
        intent_scores = {}

        # 事實查詢模式
        factual_patterns = ["什麼", "誰", "何時", "在哪", "what", "who", "when", "where"]
        intent_scores[QueryIntent.FACTUAL_LOOKUP] = sum(
            1 for pattern in factual_patterns if pattern in query_lower
        ) / len(factual_patterns)

        # 分析推理模式
        analytical_patterns = ["為什麼", "如何", "原因", "影響", "why", "how", "analyze", "explain"]
        intent_scores[QueryIntent.ANALYTICAL_REASONING] = sum(
            1 for pattern in analytical_patterns if pattern in query_lower
        ) / len(analytical_patterns)

        # 對比分析模式
        comparative_patterns = [
            "比較",
            "對比",
            "差異",
            "相似",
            "compare",
            "contrast",
            "difference",
            "similar",
        ]
        intent_scores[QueryIntent.COMPARATIVE_ANALYSIS] = sum(
            1 for pattern in comparative_patterns if pattern in query_lower
        ) / len(comparative_patterns)

        # 視覺描述模式
        visual_patterns = ["顏色", "構圖", "風格", "外觀", "color", "style", "visual", "appearance"]
        intent_scores[QueryIntent.VISUAL_DESCRIPTION] = sum(
            1 for pattern in visual_patterns if pattern in query_lower
        ) / len(visual_patterns)

        # 歷史脈絡模式
        historical_patterns = [
            "歷史",
            "時期",
            "背景",
            "發展",
            "history",
            "period",
            "context",
            "development",
        ]
        intent_scores[QueryIntent.HISTORICAL_CONTEXT] = sum(
            1 for pattern in historical_patterns if pattern in query_lower
        ) / len(historical_patterns)

        return intent_scores

    def _calculate_complexity(self, context: QueryContext) -> float:
        """計算查詢複雜度"""
        complexity_factors = []

        # 文本長度複雜度
        text_complexity = len(context.query_text.split()) / 50.0  # 標準化到0-1
        complexity_factors.append(min(text_complexity, 1.0))

        # 實體提及複雜度
        entity_complexity = len(context.entity_mentions) / 10.0
        complexity_factors.append(min(entity_complexity, 1.0))

        # 多模態複雜度
        multimodal_complexity = len(context.multimodal_components) / 3.0
        complexity_factors.append(min(multimodal_complexity, 1.0))

        # 時間參考複雜度
        temporal_complexity = len(context.temporal_references) / 5.0
        complexity_factors.append(min(temporal_complexity, 1.0))

        return statistics.mean(complexity_factors) if complexity_factors else 0.0

    def _get_candidate_strategies(self, context: QueryContext) -> list[ContextualRAGStrategy]:
        """獲取候選策略"""
        candidates = []

        # 基於意圖分析選擇候選策略
        intent_scores = self._analyze_query_intent(context)

        if intent_scores.get(QueryIntent.VISUAL_DESCRIPTION, 0) > 0.3:
            candidates.append(ContextualRAGStrategy.VISUAL_MULTIMODAL)

        if intent_scores.get(QueryIntent.ANALYTICAL_REASONING, 0) > 0.3:
            candidates.append(ContextualRAGStrategy.KNOWLEDGE_GRAPH)

        if intent_scores.get(QueryIntent.HISTORICAL_CONTEXT, 0) > 0.3:
            candidates.append(ContextualRAGStrategy.TEMPORAL_AWARE)

        if intent_scores.get(QueryIntent.COMPARATIVE_ANALYSIS, 0) > 0.3:
            candidates.append(ContextualRAGStrategy.HYBRID_FUSION)

        # 總是包含基礎策略
        if ContextualRAGStrategy.TEXT_SEMANTIC not in candidates:
            candidates.append(ContextualRAGStrategy.TEXT_SEMANTIC)

        # 復雜查詢使用自適應策略
        if context.complexity_score > 0.7:
            candidates.append(ContextualRAGStrategy.CONTEXTUAL_ADAPTIVE)

        return candidates

    def _calculate_base_score(
        self, strategy: ContextualRAGStrategy, context: QueryContext
    ) -> float:
        """計算策略基礎分數"""
        intent_scores = self._analyze_query_intent(context)

        # 策略-意圖適配性矩陣
        strategy_intent_weights = {
            ContextualRAGStrategy.TEXT_SEMANTIC: {
                QueryIntent.FACTUAL_LOOKUP: 0.8,
                QueryIntent.ANALYTICAL_REASONING: 0.6,
                QueryIntent.COMPARATIVE_ANALYSIS: 0.5,
                QueryIntent.CREATIVE_INTERPRETATION: 0.4,
                QueryIntent.HISTORICAL_CONTEXT: 0.6,
                QueryIntent.VISUAL_DESCRIPTION: 0.3,
            },
            ContextualRAGStrategy.VISUAL_MULTIMODAL: {
                QueryIntent.FACTUAL_LOOKUP: 0.4,
                QueryIntent.ANALYTICAL_REASONING: 0.7,
                QueryIntent.COMPARATIVE_ANALYSIS: 0.8,
                QueryIntent.CREATIVE_INTERPRETATION: 0.9,
                QueryIntent.HISTORICAL_CONTEXT: 0.5,
                QueryIntent.VISUAL_DESCRIPTION: 0.95,
            },
            ContextualRAGStrategy.KNOWLEDGE_GRAPH: {
                QueryIntent.FACTUAL_LOOKUP: 0.9,
                QueryIntent.ANALYTICAL_REASONING: 0.95,
                QueryIntent.COMPARATIVE_ANALYSIS: 0.8,
                QueryIntent.CREATIVE_INTERPRETATION: 0.6,
                QueryIntent.HISTORICAL_CONTEXT: 0.9,
                QueryIntent.VISUAL_DESCRIPTION: 0.4,
            },
            ContextualRAGStrategy.TEMPORAL_AWARE: {
                QueryIntent.FACTUAL_LOOKUP: 0.7,
                QueryIntent.ANALYTICAL_REASONING: 0.8,
                QueryIntent.COMPARATIVE_ANALYSIS: 0.9,
                QueryIntent.CREATIVE_INTERPRETATION: 0.7,
                QueryIntent.HISTORICAL_CONTEXT: 0.95,
                QueryIntent.VISUAL_DESCRIPTION: 0.5,
            },
            ContextualRAGStrategy.HYBRID_FUSION: {
                QueryIntent.FACTUAL_LOOKUP: 0.8,
                QueryIntent.ANALYTICAL_REASONING: 0.9,
                QueryIntent.COMPARATIVE_ANALYSIS: 0.95,
                QueryIntent.CREATIVE_INTERPRETATION: 0.8,
                QueryIntent.HISTORICAL_CONTEXT: 0.8,
                QueryIntent.VISUAL_DESCRIPTION: 0.8,
            },
            ContextualRAGStrategy.CONTEXTUAL_ADAPTIVE: {
                QueryIntent.FACTUAL_LOOKUP: 0.85,
                QueryIntent.ANALYTICAL_REASONING: 0.9,
                QueryIntent.COMPARATIVE_ANALYSIS: 0.9,
                QueryIntent.CREATIVE_INTERPRETATION: 0.85,
                QueryIntent.HISTORICAL_CONTEXT: 0.85,
                QueryIntent.VISUAL_DESCRIPTION: 0.8,
            },
        }

        weights = strategy_intent_weights.get(strategy, {})
        score = sum(
            intent_scores.get(intent, 0) * weights.get(intent, 0.5) for intent in QueryIntent
        )

        return min(score / len(QueryIntent), 1.0)

    def _get_historical_performance_score(
        self, strategy: ContextualRAGStrategy, context: QueryContext
    ) -> float:
        """獲取歷史性能分數"""
        perf = self.strategy_performances[strategy]

        if perf.total_queries == 0:
            return 0.5  # 默認中等分數

        # 綜合性能指標
        success_rate = perf.success_count / perf.total_queries
        confidence_score = perf.avg_confidence / 1.0  # 假設信心度最大為1
        satisfaction_score = perf.avg_user_satisfaction / 5.0  # 假設滿意度最大為5

        # 時間衰減因子
        days_since_update = (datetime.now() - perf.last_updated).days
        time_decay = max(0.5, 1.0 - days_since_update * 0.01)

        historical_score = (
            success_rate * 0.4 + confidence_score * 0.3 + satisfaction_score * 0.3
        ) * time_decay

        return min(historical_score, 1.0)

    def _calculate_exploration_bonus(self, strategy: ContextualRAGStrategy) -> float:
        """計算探索獎勵"""
        total_selections = sum(self.strategy_selections.values())
        if total_selections == 0:
            return 1.0

        strategy_selections = self.strategy_selections[strategy]
        selection_ratio = strategy_selections / total_selections

        # 獎勵較少被選擇的策略
        exploration_bonus = max(0, 1.0 - selection_ratio * 2)
        return exploration_bonus

    async def update_strategy_performance(
        self,
        strategy: ContextualRAGStrategy,
        context: QueryContext,
        performance_metrics: dict[str, float],
    ):
        """更新策略性能"""
        perf = self.strategy_performances[strategy]

        # 更新統計
        perf.total_queries += 1
        if performance_metrics.get("success", False):
            perf.success_count += 1

        # 更新平均值（使用指數移動平均）
        alpha = self.learning_rate

        if "response_time" in performance_metrics:
            if perf.avg_response_time == 0:
                perf.avg_response_time = performance_metrics["response_time"]
            else:
                perf.avg_response_time = (
                    1 - alpha
                ) * perf.avg_response_time + alpha * performance_metrics["response_time"]

        if "confidence" in performance_metrics:
            if perf.avg_confidence == 0:
                perf.avg_confidence = performance_metrics["confidence"]
            else:
                perf.avg_confidence = (
                    1 - alpha
                ) * perf.avg_confidence + alpha * performance_metrics["confidence"]

        if "user_satisfaction" in performance_metrics:
            if perf.avg_user_satisfaction == 0:
                perf.avg_user_satisfaction = performance_metrics["user_satisfaction"]
            else:
                perf.avg_user_satisfaction = (
                    1 - alpha
                ) * perf.avg_user_satisfaction + alpha * performance_metrics["user_satisfaction"]

        # 記錄最近表現
        perf.recent_performances.append(
            {"timestamp": datetime.now(), "metrics": performance_metrics.copy()}
        )

        perf.last_updated = datetime.now()

        # 更新獎勵記錄
        reward = self._calculate_reward(performance_metrics)
        self.strategy_rewards[strategy].append(reward)

        logger.info(
            f"📊 策略 {strategy.value} 性能更新: "
            f"成功率={perf.success_count / perf.total_queries:.2f}, "
            f"平均響應時間={perf.avg_response_time:.2f}s, "
            f"平均信心度={perf.avg_confidence:.2f}"
        )

    def _calculate_reward(self, metrics: dict[str, float]) -> float:
        """計算獎勵值"""
        # 多目標獎勵函數
        success_reward = 1.0 if metrics.get("success", False) else -0.5

        # 響應時間獎勵（時間越短獎勵越高）
        response_time = metrics.get("response_time", 10.0)
        time_reward = max(0, 1.0 - response_time / 30.0)  # 30秒為基準

        # 信心度獎勵
        confidence_reward = metrics.get("confidence", 0.5)

        # 用戶滿意度獎勵
        satisfaction_reward = metrics.get("user_satisfaction", 2.5) / 5.0

        total_reward = (
            success_reward * 0.4
            + time_reward * 0.2
            + confidence_reward * 0.2
            + satisfaction_reward * 0.2
        )

        return total_reward

    def get_strategy_recommendation(self, context: QueryContext) -> dict[str, Any]:
        """獲取策略推薦和解釋"""
        intent_analysis = self._analyze_query_intent(context)
        complexity_score = self._calculate_complexity(context)

        # 獲取所有策略的分數
        strategy_scores = {}
        explanations = {}

        for strategy in ContextualRAGStrategy:
            base_score = self._calculate_base_score(strategy, context)
            historical_score = self._get_historical_performance_score(strategy, context)

            strategy_scores[strategy.value] = {
                "total_score": (base_score + historical_score) / 2,
                "base_score": base_score,
                "historical_score": historical_score,
            }

            explanations[strategy.value] = self._generate_strategy_explanation(
                strategy, intent_analysis, complexity_score
            )

        return {
            "query_analysis": {
                "intent_scores": {intent.value: score for intent, score in intent_analysis.items()},
                "complexity_score": complexity_score,
                "entity_count": len(context.entity_mentions),
                "multimodal_components": context.multimodal_components,
            },
            "strategy_scores": strategy_scores,
            "explanations": explanations,
            "recommended_strategy": max(
                strategy_scores, key=lambda x: strategy_scores[x]["total_score"]
            ),
            "timestamp": datetime.now().isoformat(),
        }

    def _generate_strategy_explanation(
        self,
        strategy: ContextualRAGStrategy,
        intent_analysis: dict[QueryIntent, float],
        complexity_score: float,
    ) -> str:
        """生成策略選擇解釋"""
        explanations = {
            ContextualRAGStrategy.TEXT_SEMANTIC: f"基於純文本語義搜索，適合事實查詢"
            f"(分數:{intent_analysis.get(QueryIntent.FACTUAL_LOOKUP, 0):.2f})",
            ContextualRAGStrategy.VISUAL_MULTIMODAL: f"結合視覺和文本信息，適合視覺描述查詢"
            f"(分數:{intent_analysis.get(QueryIntent.VISUAL_DESCRIPTION, 0):.2f})",
            ContextualRAGStrategy.KNOWLEDGE_GRAPH: f"利用知識圖譜推理，適合分析性查詢"
            f"(分數:{intent_analysis.get(QueryIntent.ANALYTICAL_REASONING, 0):.2f})",
            ContextualRAGStrategy.TEMPORAL_AWARE: f"時序感知檢索，適合歷史脈絡查詢"
            f"(分數:{intent_analysis.get(QueryIntent.HISTORICAL_CONTEXT, 0):.2f})",
            ContextualRAGStrategy.HYBRID_FUSION: f"多策略融合，適合對比分析"
            f"(分數:{intent_analysis.get(QueryIntent.COMPARATIVE_ANALYSIS, 0):.2f})",
            ContextualRAGStrategy.CONTEXTUAL_ADAPTIVE: f"情境自適應策略，適合復雜查詢"
            f"(複雜度:{complexity_score:.2f})",
        }

        return explanations.get(strategy, "未知策略")

    async def optimize_system_performance(self):
        """系統性能優化"""
        logger.info("🔧 開始系統性能優化...")

        # 分析策略性能趨勢
        performance_analysis = self._analyze_performance_trends()

        # 調整探索率
        self._adjust_exploration_rate(performance_analysis)

        # 更新用戶偏好模型
        await self._update_user_preference_models()

        # 清理過期數據
        self._cleanup_expired_data()

        # 記錄優化結果
        optimization_record = {
            "timestamp": datetime.now(),
            "performance_analysis": performance_analysis,
            "exploration_rate": self.exploration_rate,
            "total_queries": sum(
                perf.total_queries for perf in self.strategy_performances.values()
            ),
        }

        self.optimization_history.append(optimization_record)
        self.last_optimization = datetime.now()

        logger.info("✅ 系統性能優化完成")
        return optimization_record

    def _analyze_performance_trends(self) -> dict[str, Any]:
        """分析性能趨勢"""
        trends = {}

        for strategy, perf in self.strategy_performances.items():
            if len(perf.recent_performances) >= 5:
                recent_rewards = [
                    self._calculate_reward(p["metrics"])
                    for p in list(perf.recent_performances)[-10:]
                ]

                trends[strategy.value] = {
                    "reward_trend": "increasing"
                    if len(recent_rewards) > 1 and recent_rewards[-1] > recent_rewards[0]
                    else "decreasing",
                    "avg_recent_reward": statistics.mean(recent_rewards),
                    "stability": 1.0 - statistics.stdev(recent_rewards)
                    if len(recent_rewards) > 1
                    else 1.0,
                }

        return trends

    def _adjust_exploration_rate(self, performance_analysis: dict[str, Any]):
        """調整探索率"""
        # 如果所有策略表現都很穩定，降低探索率
        avg_stability = (
            statistics.mean(
                [trend.get("stability", 0.5) for trend in performance_analysis.values()]
            )
            if performance_analysis
            else 0.5
        )

        if avg_stability > 0.8:
            self.exploration_rate = max(0.05, self.exploration_rate * 0.9)
        elif avg_stability < 0.3:
            self.exploration_rate = min(0.5, self.exploration_rate * 1.1)

        logger.info(f"🎛️ 探索率調整為: {self.exploration_rate:.3f}")

    async def _update_user_preference_models(self):
        """更新用戶偏好模型"""
        # 這裡可以實現基於用戶歷史行為的偏好學習
        logger.info("👤 更新用戶偏好模型")
        pass

    def _cleanup_expired_data(self):
        """清理過期數據"""
        cutoff_date = datetime.now() - timedelta(days=30)

        for strategy in self.strategy_performances:
            perf = self.strategy_performances[strategy]
            # 清理30天前的性能記錄
            perf.recent_performances = deque(
                [p for p in perf.recent_performances if p["timestamp"] > cutoff_date], maxlen=100
            )

        # 限制策略獎勵記錄數量
        for strategy in self.strategy_rewards:
            if len(self.strategy_rewards[strategy]) > 1000:
                self.strategy_rewards[strategy] = self.strategy_rewards[strategy][-500:]

        logger.info("🧹 過期數據清理完成")

    def get_system_status(self) -> dict[str, Any]:
        """獲取系統狀態"""
        total_queries = sum(perf.total_queries for perf in self.strategy_performances.values())

        strategy_stats = {}
        for strategy, perf in self.strategy_performances.items():
            strategy_stats[strategy.value] = {
                "total_queries": perf.total_queries,
                "success_rate": perf.success_count / max(perf.total_queries, 1),
                "avg_response_time": perf.avg_response_time,
                "avg_confidence": perf.avg_confidence,
                "selection_frequency": self.strategy_selections.get(strategy, 0)
                / max(total_queries, 1),
            }

        return {
            "total_queries_processed": total_queries,
            "exploration_rate": self.exploration_rate,
            "learning_rate": self.learning_rate,
            "strategy_performances": strategy_stats,
            "last_optimization": self.last_optimization.isoformat(),
            "system_uptime": (datetime.now() - self.last_optimization).total_seconds()
            / 3600,  # 小時
            "optimization_count": len(self.optimization_history),
        }
