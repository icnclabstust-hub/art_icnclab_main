#!/usr/bin/env python3
"""
增強型自適應策略監控系統
提供實時性能監控、指標追蹤和自動優化功能
"""

import asyncio
import json
import logging
import os
import statistics
import sys
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from typing import Any

# 添加當前目錄到Python路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        Summary,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logging.warning("Prometheus client not available, metrics will be stored internally only")

from enhanced_adaptive_strategies import (
    ContextualRAGStrategy,
    EnhancedAdaptiveManager,
    QueryContext,
)


@dataclass
class PerformanceMetrics:
    """性能指標數據結構"""

    timestamp: float
    strategy_name: str
    query_intent: str
    response_time: float
    accuracy: float
    success: bool
    confidence: float
    user_satisfaction: float
    exploration_rate: float
    learning_rate: float
    total_queries: int


@dataclass
class SystemHealth:
    """系統健康狀態"""

    cpu_usage: float
    memory_usage: float
    active_strategies: int
    avg_response_time: float
    success_rate: float
    error_rate: float
    learning_velocity: float


class AdaptiveStrategyMonitor:
    """增強型自適應策略監控器"""

    def __init__(
        self,
        adaptive_manager: EnhancedAdaptiveManager,
        metrics_retention_hours: int = 24,
        alert_thresholds: dict | None = None,
    ):
        """
        初始化監控器

        Args:
            adaptive_manager: 自適應策略管理器
            metrics_retention_hours: 指標保留時間（小時）
            alert_thresholds: 告警閾值配置
        """
        self.adaptive_manager = adaptive_manager
        self.metrics_retention_hours = metrics_retention_hours
        self.alert_thresholds = alert_thresholds or self._default_alert_thresholds()

        # 內部指標存儲
        self.performance_history: deque = deque(maxlen=10000)  # 最近10000條記錄
        self.strategy_stats = defaultdict(list)
        self.system_alerts = []
        self.monitoring_active = True

        # 日誌配置
        self.logger = self._setup_logger()

        # Prometheus指標（如果可用）
        self.prometheus_registry = None
        self.prometheus_metrics = {}
        if PROMETHEUS_AVAILABLE:
            self._setup_prometheus_metrics()

        # 監控統計
        self.start_time = time.time()
        self.last_cleanup = time.time()

        self.logger.info("增強型自適應策略監控器已初始化")

    def _default_alert_thresholds(self) -> dict:
        """默認告警閾值"""
        return {
            "max_response_time": 5.0,  # 最大響應時間（秒）
            "min_success_rate": 0.8,  # 最小成功率
            "max_error_rate": 0.2,  # 最大錯誤率
            "min_accuracy": 0.7,  # 最小準確度
            "max_exploration_rate": 0.5,  # 最大探索率
            "min_learning_velocity": 0.01,  # 最小學習速度
            "max_memory_usage": 0.85,  # 最大內存使用率
            "max_cpu_usage": 0.80,  # 最大CPU使用率
        }

    def _setup_logger(self) -> logging.Logger:
        """設置日誌記錄"""
        logger = logging.getLogger("AdaptiveStrategyMonitor")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _setup_prometheus_metrics(self):
        """設置Prometheus指標"""
        self.prometheus_registry = CollectorRegistry()

        # 策略選擇計數器
        self.prometheus_metrics["strategy_selections"] = Counter(
            "adaptive_strategy_selections_total",
            "Total number of strategy selections by type",
            ["strategy_type", "query_intent"],
            registry=self.prometheus_registry,
        )

        # 響應時間直方圖
        self.prometheus_metrics["response_time"] = Histogram(
            "adaptive_strategy_response_time_seconds",
            "Strategy selection response time in seconds",
            ["strategy_type"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=self.prometheus_registry,
        )

        # 準確度統計
        self.prometheus_metrics["accuracy"] = Summary(
            "adaptive_strategy_accuracy",
            "Strategy accuracy scores",
            ["strategy_type"],
            registry=self.prometheus_registry,
        )

        # 成功率gauge
        self.prometheus_metrics["success_rate"] = Gauge(
            "adaptive_strategy_success_rate",
            "Current strategy success rate",
            ["strategy_type"],
            registry=self.prometheus_registry,
        )

        # 探索率gauge
        self.prometheus_metrics["exploration_rate"] = Gauge(
            "adaptive_strategy_exploration_rate",
            "Current exploration rate",
            registry=self.prometheus_registry,
        )

        # 學習率gauge
        self.prometheus_metrics["learning_rate"] = Gauge(
            "adaptive_strategy_learning_rate",
            "Current learning rate",
            registry=self.prometheus_registry,
        )

        # 系統健康指標
        self.prometheus_metrics["system_health"] = Gauge(
            "adaptive_strategy_system_health",
            "System health score (0-1)",
            registry=self.prometheus_registry,
        )

        self.logger.info("Prometheus指標已設置完成")

    async def record_strategy_performance(
        self,
        strategy: ContextualRAGStrategy,
        context: QueryContext,
        performance_data: dict[str, Any],
    ):
        """
        記錄策略性能數據

        Args:
            strategy: 選擇的策略
            context: 查詢上下文
            performance_data: 性能數據
        """
        # 獲取系統狀態
        system_status = self.adaptive_manager.get_system_status()

        # 分析查詢意圖
        recommendation = self.adaptive_manager.get_strategy_recommendation(context)
        intent_scores = recommendation["query_analysis"]["intent_scores"]
        top_intent = max(intent_scores.items(), key=lambda x: x[1])

        # 創建性能指標記錄
        metrics = PerformanceMetrics(
            timestamp=time.time(),
            strategy_name=strategy.value,
            query_intent=top_intent[0],
            response_time=performance_data.get("response_time", 0.0),
            accuracy=performance_data.get("confidence", 0.0),
            success=performance_data.get("success", True),
            confidence=performance_data.get("confidence", 0.0),
            user_satisfaction=performance_data.get("user_satisfaction", 3.0),
            exploration_rate=system_status.get("exploration_rate", 0.0),
            learning_rate=system_status.get("learning_rate", 0.0),
            total_queries=system_status.get("total_queries_processed", 0),
        )

        # 存儲到歷史記錄
        self.performance_history.append(metrics)
        self.strategy_stats[strategy.value].append(metrics)

        # 更新Prometheus指標
        if PROMETHEUS_AVAILABLE and self.prometheus_metrics:
            self._update_prometheus_metrics(metrics)

        # 檢查告警條件
        await self._check_alerts(metrics)

        # 定期清理舊數據
        if time.time() - self.last_cleanup > 3600:  # 每小時清理一次
            await self._cleanup_old_data()
            self.last_cleanup = time.time()

        self.logger.debug(
            f"已記錄策略性能: {strategy.value} - 響應時間: {metrics.response_time:.3f}s"
        )

    def _update_prometheus_metrics(self, metrics: PerformanceMetrics):
        """更新Prometheus指標"""
        try:
            # 增加策略選擇計數
            self.prometheus_metrics["strategy_selections"].labels(
                strategy_type=metrics.strategy_name, query_intent=metrics.query_intent
            ).inc()

            # 記錄響應時間
            self.prometheus_metrics["response_time"].labels(
                strategy_type=metrics.strategy_name
            ).observe(metrics.response_time)

            # 記錄準確度
            self.prometheus_metrics["accuracy"].labels(strategy_type=metrics.strategy_name).observe(
                metrics.accuracy
            )

            # 更新探索率和學習率
            self.prometheus_metrics["exploration_rate"].set(metrics.exploration_rate)
            self.prometheus_metrics["learning_rate"].set(metrics.learning_rate)

            # 計算並更新成功率
            recent_metrics = [
                m for m in self.performance_history if m.timestamp > time.time() - 3600
            ]  # 最近1小時
            if recent_metrics:
                success_rate = sum(1 for m in recent_metrics if m.success) / len(recent_metrics)
                self.prometheus_metrics["success_rate"].labels(
                    strategy_type=metrics.strategy_name
                ).set(success_rate)

            # 計算系統健康分數
            health_score = self._calculate_system_health_score()
            self.prometheus_metrics["system_health"].set(health_score)

        except Exception as e:
            self.logger.error(f"更新Prometheus指標時出錯: {e}")

    def _calculate_system_health_score(self) -> float:
        """計算系統健康分數 (0-1)"""
        if not self.performance_history:
            return 1.0

        # 最近1小時的數據
        recent_data = [m for m in self.performance_history if m.timestamp > time.time() - 3600]

        if not recent_data:
            return 1.0

        # 計算各項指標
        avg_response_time = statistics.mean([m.response_time for m in recent_data])
        success_rate = sum(1 for m in recent_data if m.success) / len(recent_data)
        avg_accuracy = statistics.mean([m.accuracy for m in recent_data])

        # 健康分數計算（可根據需要調整權重）
        response_score = max(
            0, 1 - (avg_response_time / self.alert_thresholds["max_response_time"])
        )
        success_score = success_rate
        accuracy_score = avg_accuracy

        health_score = response_score * 0.3 + success_score * 0.4 + accuracy_score * 0.3
        return max(0.0, min(1.0, health_score))

    async def _check_alerts(self, metrics: PerformanceMetrics):
        """檢查告警條件"""
        alerts = []

        # 響應時間告警
        if metrics.response_time > self.alert_thresholds["max_response_time"]:
            alerts.append(
                {
                    "type": "high_response_time",
                    "severity": "warning",
                    "message": f"響應時間過長: {metrics.response_time:.3f}s (閾值: {self.alert_thresholds['max_response_time']}s)",
                    "timestamp": metrics.timestamp,
                    "strategy": metrics.strategy_name,
                }
            )

        # 準確度告警
        if metrics.accuracy < self.alert_thresholds["min_accuracy"]:
            alerts.append(
                {
                    "type": "low_accuracy",
                    "severity": "warning",
                    "message": f"準確度過低: {metrics.accuracy:.3f} (閾值: {self.alert_thresholds['min_accuracy']})",
                    "timestamp": metrics.timestamp,
                    "strategy": metrics.strategy_name,
                }
            )

        # 探索率告警
        if metrics.exploration_rate > self.alert_thresholds["max_exploration_rate"]:
            alerts.append(
                {
                    "type": "high_exploration_rate",
                    "severity": "info",
                    "message": f"探索率較高: {metrics.exploration_rate:.3f} (閾值: {self.alert_thresholds['max_exploration_rate']})",
                    "timestamp": metrics.timestamp,
                    "strategy": metrics.strategy_name,
                }
            )

        # 存儲告警
        for alert in alerts:
            self.system_alerts.append(alert)
            self.logger.warning(f"系統告警: {alert['message']}")

        # 保持告警列表不超過1000條
        if len(self.system_alerts) > 1000:
            self.system_alerts = self.system_alerts[-500:]

    async def _cleanup_old_data(self):
        """清理過期數據"""
        cutoff_time = time.time() - (self.metrics_retention_hours * 3600)

        # 清理性能歷史
        original_count = len(self.performance_history)
        self.performance_history = deque(
            [m for m in self.performance_history if m.timestamp > cutoff_time],
            maxlen=self.performance_history.maxlen,
        )

        # 清理策略統計
        for strategy_name in list(self.strategy_stats.keys()):
            self.strategy_stats[strategy_name] = [
                m for m in self.strategy_stats[strategy_name] if m.timestamp > cutoff_time
            ]
            if not self.strategy_stats[strategy_name]:
                del self.strategy_stats[strategy_name]

        # 清理舊告警
        self.system_alerts = [
            alert for alert in self.system_alerts if alert["timestamp"] > cutoff_time
        ]

        cleaned_count = original_count - len(self.performance_history)
        if cleaned_count > 0:
            self.logger.info(f"已清理 {cleaned_count} 條過期數據")

    def get_strategy_statistics(
        self, strategy_name: str | None = None, hours: int = 1
    ) -> dict[str, Any]:
        """
        獲取策略統計信息

        Args:
            strategy_name: 策略名稱，None表示所有策略
            hours: 統計時間範圍（小時）

        Returns:
            策略統計信息
        """
        cutoff_time = time.time() - (hours * 3600)

        if strategy_name:
            # 特定策略統計
            strategy_data = [
                m for m in self.strategy_stats.get(strategy_name, []) if m.timestamp > cutoff_time
            ]
        else:
            # 全部策略統計
            strategy_data = [m for m in self.performance_history if m.timestamp > cutoff_time]

        if not strategy_data:
            return {"message": "無統計數據", "data_count": 0}

        # 計算統計指標
        response_times = [m.response_time for m in strategy_data]
        accuracies = [m.accuracy for m in strategy_data]
        success_count = sum(1 for m in strategy_data if m.success)

        return {
            "strategy": strategy_name or "all",
            "time_range_hours": hours,
            "data_count": len(strategy_data),
            "avg_response_time": statistics.mean(response_times),
            "median_response_time": statistics.median(response_times),
            "max_response_time": max(response_times),
            "min_response_time": min(response_times),
            "avg_accuracy": statistics.mean(accuracies),
            "success_rate": success_count / len(strategy_data),
            "total_queries": len(strategy_data),
            "query_rate_per_hour": len(strategy_data) / hours,
        }

    def get_system_health_report(self) -> dict[str, Any]:
        """獲取系統健康報告"""
        current_time = time.time()
        uptime_hours = (current_time - self.start_time) / 3600

        # 最近數據
        recent_data = [m for m in self.performance_history if m.timestamp > current_time - 3600]

        health_score = self._calculate_system_health_score()

        return {
            "timestamp": current_time,
            "uptime_hours": uptime_hours,
            "health_score": health_score,
            "total_queries_monitored": len(self.performance_history),
            "recent_queries_count": len(recent_data),
            "active_strategies": len(self.strategy_stats),
            "pending_alerts": len(
                [a for a in self.system_alerts if a["timestamp"] > current_time - 3600]
            ),
            "monitoring_status": "active" if self.monitoring_active else "inactive",
            "prometheus_enabled": PROMETHEUS_AVAILABLE and bool(self.prometheus_metrics),
        }

    def get_prometheus_metrics(self) -> str:
        """獲取Prometheus格式的指標數據"""
        if not PROMETHEUS_AVAILABLE or not self.prometheus_registry:
            return "# Prometheus metrics not available\n"

        return generate_latest(self.prometheus_registry).decode("utf-8")

    async def generate_optimization_recommendations(self) -> list[dict[str, Any]]:
        """生成優化建議"""
        recommendations = []

        # 分析最近的性能數據
        recent_data = [m for m in self.performance_history if m.timestamp > time.time() - 3600]

        if not recent_data:
            return [{"type": "info", "message": "數據不足，無法生成建議"}]

        # 響應時間分析
        avg_response_time = statistics.mean([m.response_time for m in recent_data])
        if avg_response_time > self.alert_thresholds["max_response_time"] * 0.7:
            recommendations.append(
                {
                    "type": "performance",
                    "priority": "medium",
                    "message": f"平均響應時間較高 ({avg_response_time:.3f}s)，建議檢查系統資源",
                    "suggestions": [
                        "檢查數據庫連接池配置",
                        "優化向量搜索索引",
                        "考慮增加緩存策略",
                        "檢查GPU記憶體使用情況",
                    ],
                }
            )

        # 策略多樣性分析
        strategy_usage = defaultdict(int)
        for m in recent_data:
            strategy_usage[m.strategy_name] += 1

        if len(strategy_usage) < 3:
            recommendations.append(
                {
                    "type": "strategy_diversity",
                    "priority": "low",
                    "message": "策略選擇多樣性較低，可能需要調整探索率",
                    "suggestions": [
                        "適當提高探索率以嘗試更多策略",
                        "檢查查詢意圖識別準確性",
                        "考慮添加更多策略類型",
                    ],
                }
            )

        # 學習效果分析
        if len(recent_data) > 10:
            early_accuracy = statistics.mean(
                [m.accuracy for m in recent_data[: len(recent_data) // 2]]
            )
            later_accuracy = statistics.mean(
                [m.accuracy for m in recent_data[len(recent_data) // 2 :]]
            )

            if later_accuracy <= early_accuracy:
                recommendations.append(
                    {
                        "type": "learning",
                        "priority": "medium",
                        "message": "學習效果不明顯，建議調整學習參數",
                        "suggestions": ["適當提高學習率", "檢查反饋質量", "考慮重置部分策略權重"],
                    }
                )

        return recommendations

    async def start_monitoring(self):
        """開始監控"""
        self.monitoring_active = True
        self.logger.info("增強型自適應策略監控已啟動")

    async def stop_monitoring(self):
        """停止監控"""
        self.monitoring_active = False
        self.logger.info("增強型自適應策略監控已停止")

    def export_metrics_to_json(self, filepath: str):
        """導出指標到JSON文件"""
        export_data = {
            "export_timestamp": time.time(),
            "system_health": self.get_system_health_report(),
            "performance_history": [asdict(m) for m in list(self.performance_history)],
            "recent_alerts": self.system_alerts[-100:],  # 最近100條告警
            "strategy_statistics": {
                name: self.get_strategy_statistics(name, hours=24)
                for name in self.strategy_stats.keys()
            },
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        self.logger.info(f"指標數據已導出到: {filepath}")


# FastAPI集成示例
async def create_monitoring_endpoints():
    """創建監控API端點的示例代碼"""
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import Response

        app = FastAPI(title="增強型自適應策略監控API")

        # 這裡需要實際的監控器實例
        # monitor = AdaptiveStrategyMonitor(adaptive_manager)

        @app.get("/metrics")
        async def get_prometheus_metrics():
            """Prometheus指標端點"""
            # return Response(content=monitor.get_prometheus_metrics(),
            #               media_type="text/plain")
            pass

        @app.get("/health")
        async def get_health():
            """系統健康檢查"""
            # return monitor.get_system_health_report()
            pass

        @app.get("/stats/{strategy_name}")
        async def get_strategy_stats(strategy_name: str, hours: int = 1):
            """獲取策略統計"""
            # return monitor.get_strategy_statistics(strategy_name, hours)
            pass

        @app.get("/recommendations")
        async def get_recommendations():
            """獲取優化建議"""
            # return await monitor.generate_optimization_recommendations()
            pass

        return app

    except ImportError:
        logging.warning("FastAPI not available for monitoring endpoints")
        return None


if __name__ == "__main__":
    # 測試監控系統
    async def test_monitor():
        from enhanced_adaptive_strategies import EnhancedAdaptiveManager

        # 創建測試用的自適應管理器
        adaptive_manager = EnhancedAdaptiveManager()

        # 創建監控器
        monitor = AdaptiveStrategyMonitor(adaptive_manager)

        # 啟動監控
        await monitor.start_monitoring()

        # 模擬一些性能數據記錄
        test_context = QueryContext(query_text="測試查詢")

        for i in range(10):
            strategy = await adaptive_manager.select_optimal_strategy(test_context)

            # 模擬性能數據
            performance_data = {
                "response_time": 0.1 + i * 0.01,
                "confidence": 0.8 + i * 0.02,
                "success": True,
                "user_satisfaction": 4.0,
            }

            await monitor.record_strategy_performance(strategy, test_context, performance_data)
            await asyncio.sleep(0.1)

        # 獲取統計信息
        health_report = monitor.get_system_health_report()
        print("系統健康報告:", json.dumps(health_report, ensure_ascii=False, indent=2))

        # 生成優化建議
        recommendations = await monitor.generate_optimization_recommendations()
        print("優化建議:", json.dumps(recommendations, ensure_ascii=False, indent=2))

        # 停止監控
        await monitor.stop_monitoring()

    asyncio.run(test_monitor())
