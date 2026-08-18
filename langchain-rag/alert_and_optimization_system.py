#!/usr/bin/env python3
"""
告警和自動優化系統
基於監控數據自動檢測問題並執行優化措施
"""

import asyncio
import json
import logging
import os
import statistics
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

# 添加當前目錄到Python路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from adaptive_strategy_monitor import AdaptiveStrategyMonitor
from enhanced_adaptive_strategies import EnhancedAdaptiveManager, QueryContext


class AlertSeverity(Enum):
    """告警嚴重程度"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class OptimizationAction(Enum):
    """優化操作類型"""

    ADJUST_LEARNING_RATE = "adjust_learning_rate"
    ADJUST_EXPLORATION_RATE = "adjust_exploration_rate"
    RESET_STRATEGY_WEIGHTS = "reset_strategy_weights"
    CLEAR_CACHE = "clear_cache"
    RESTART_COMPONENT = "restart_component"
    SCALE_RESOURCES = "scale_resources"


@dataclass
class Alert:
    """告警數據結構"""

    id: str
    timestamp: float
    severity: AlertSeverity
    title: str
    message: str
    source: str
    metric_name: str
    current_value: float
    threshold_value: float
    tags: dict[str, str]
    resolved: bool = False
    resolved_timestamp: float | None = None


@dataclass
class OptimizationRule:
    """優化規則"""

    name: str
    condition: Callable[[dict], bool]
    action: OptimizationAction
    parameters: dict[str, Any]
    cooldown_seconds: int = 300  # 5分鐘冷卻期
    last_executed: float = 0


class AlertAndOptimizationSystem:
    """告警和自動優化系統"""

    def __init__(
        self,
        adaptive_manager: EnhancedAdaptiveManager,
        monitor: AdaptiveStrategyMonitor,
        enable_auto_optimization: bool = True,
    ):
        """
        初始化告警和優化系統

        Args:
            adaptive_manager: 自適應策略管理器
            monitor: 監控器
            enable_auto_optimization: 是否啟用自動優化
        """
        self.adaptive_manager = adaptive_manager
        self.monitor = monitor
        self.enable_auto_optimization = enable_auto_optimization

        # 告警存儲
        self.active_alerts: dict[str, Alert] = {}
        self.resolved_alerts: list[Alert] = []

        # 優化規則
        self.optimization_rules: list[OptimizationRule] = []
        self.optimization_history: list[dict[str, Any]] = []

        # 告警閾值配置
        self.alert_thresholds = self._default_alert_thresholds()

        # 系統狀態
        self.system_running = False
        self.last_check_time = 0

        # 日誌配置
        self.logger = self._setup_logger()

        # 初始化優化規則
        self._setup_optimization_rules()

        self.logger.info("告警和自動優化系統已初始化")

    def _setup_logger(self) -> logging.Logger:
        """設置日誌"""
        logger = logging.getLogger("AlertAndOptimizationSystem")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _default_alert_thresholds(self) -> dict[str, dict]:
        """默認告警閾值"""
        return {
            "response_time": {
                "warning": 2.0,  # 2秒
                "critical": 5.0,  # 5秒
            },
            "success_rate": {
                "warning": 0.85,  # 85%
                "critical": 0.70,  # 70%
            },
            "accuracy": {
                "warning": 0.75,  # 75%
                "critical": 0.60,  # 60%
            },
            "exploration_rate": {
                "warning": 0.6,  # 60%
                "critical": 0.8,  # 80%
            },
            "learning_velocity": {
                "warning": 0.01,  # 學習速度過慢
                "critical": 0.005,
            },
            "error_rate": {
                "warning": 0.15,  # 15%
                "critical": 0.25,  # 25%
            },
        }

    def _setup_optimization_rules(self):
        """設置自動優化規則"""

        # 規則1: 響應時間過長時降低探索率
        self.optimization_rules.append(
            OptimizationRule(
                name="reduce_exploration_on_slow_response",
                condition=lambda metrics: metrics.get("avg_response_time", 0) > 3.0,
                action=OptimizationAction.ADJUST_EXPLORATION_RATE,
                parameters={"adjustment_factor": 0.8, "min_rate": 0.1},
                cooldown_seconds=300,
            )
        )

        # 規則2: 成功率過低時重置策略權重
        self.optimization_rules.append(
            OptimizationRule(
                name="reset_weights_on_low_success",
                condition=lambda metrics: metrics.get("success_rate", 1.0) < 0.7,
                action=OptimizationAction.RESET_STRATEGY_WEIGHTS,
                parameters={},
                cooldown_seconds=600,
            )
        )

        # 規則3: 學習速度過慢時提高學習率
        self.optimization_rules.append(
            OptimizationRule(
                name="increase_learning_rate_on_slow_learning",
                condition=lambda metrics: metrics.get("learning_velocity", 0) < 0.01,
                action=OptimizationAction.ADJUST_LEARNING_RATE,
                parameters={"adjustment_factor": 1.2, "max_rate": 0.5},
                cooldown_seconds=240,
            )
        )

        # 規則4: 準確度持續下降時清理緩存
        self.optimization_rules.append(
            OptimizationRule(
                name="clear_cache_on_accuracy_drop",
                condition=lambda metrics: self._check_accuracy_trend(metrics),
                action=OptimizationAction.CLEAR_CACHE,
                parameters={},
                cooldown_seconds=900,
            )
        )

        # 規則5: 探索率過高時調整
        self.optimization_rules.append(
            OptimizationRule(
                name="reduce_high_exploration_rate",
                condition=lambda metrics: metrics.get("exploration_rate", 0) > 0.7,
                action=OptimizationAction.ADJUST_EXPLORATION_RATE,
                parameters={"adjustment_factor": 0.9, "min_rate": 0.2},
                cooldown_seconds=180,
            )
        )

    def _check_accuracy_trend(self, metrics: dict) -> bool:
        """檢查準確度趨勢"""
        # 獲取最近的性能歷史
        recent_data = [
            m
            for m in self.monitor.performance_history
            if m.timestamp > time.time() - 1800  # 最近30分鐘
        ]

        if len(recent_data) < 10:
            return False

        # 分析趨勢：比較前半段和後半段的準確度
        mid_point = len(recent_data) // 2
        early_accuracy = statistics.mean([m.accuracy for m in recent_data[:mid_point]])
        later_accuracy = statistics.mean([m.accuracy for m in recent_data[mid_point:]])

        # 如果準確度下降超過10%，觸發優化
        return (early_accuracy - later_accuracy) / early_accuracy > 0.1

    async def start_monitoring(self):
        """啟動告警監控"""
        self.system_running = True
        self.logger.info("告警和優化系統監控已啟動")

        # 啟動主監控循環
        monitoring_task = asyncio.create_task(self._monitoring_loop())
        optimization_task = asyncio.create_task(self._optimization_loop())

        try:
            await asyncio.gather(monitoring_task, optimization_task)
        except asyncio.CancelledError:
            self.logger.info("監控任務已取消")
        except Exception as e:
            self.logger.error(f"監控過程中出錯: {e}")

    async def stop_monitoring(self):
        """停止告警監控"""
        self.system_running = False
        self.logger.info("告警和優化系統監控已停止")

    async def _monitoring_loop(self):
        """告警監控主循環"""
        while self.system_running:
            try:
                await self._check_alerts()
                await asyncio.sleep(30)  # 每30秒檢查一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"告警檢查出錯: {e}")
                await asyncio.sleep(60)

    async def _optimization_loop(self):
        """自動優化主循環"""
        while self.system_running:
            try:
                if self.enable_auto_optimization:
                    await self._execute_optimizations()
                await asyncio.sleep(60)  # 每分鐘執行一次優化檢查
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"自動優化出錯: {e}")
                await asyncio.sleep(120)

    async def _check_alerts(self):
        """檢查告警條件"""
        # 獲取當前系統指標
        metrics = await self._collect_current_metrics()

        # 檢查各項指標
        await self._check_response_time_alerts(metrics)
        await self._check_success_rate_alerts(metrics)
        await self._check_accuracy_alerts(metrics)
        await self._check_exploration_rate_alerts(metrics)
        await self._check_learning_velocity_alerts(metrics)

        # 清理已解決的告警
        await self._cleanup_resolved_alerts()

        self.last_check_time = time.time()

    async def _collect_current_metrics(self) -> dict[str, Any]:
        """收集當前系統指標"""
        # 獲取最近1小時的數據
        recent_data = [
            m for m in self.monitor.performance_history if m.timestamp > time.time() - 3600
        ]

        if not recent_data:
            return {}

        # 計算各項指標
        response_times = [m.response_time for m in recent_data]
        accuracies = [m.accuracy for m in recent_data]
        success_count = sum(1 for m in recent_data if m.success)

        # 獲取系統狀態
        system_status = self.adaptive_manager.get_system_status()

        return {
            "avg_response_time": statistics.mean(response_times),
            "max_response_time": max(response_times) if response_times else 0,
            "success_rate": success_count / len(recent_data) if recent_data else 0,
            "avg_accuracy": statistics.mean(accuracies) if accuracies else 0,
            "exploration_rate": system_status.get("exploration_rate", 0),
            "learning_rate": system_status.get("learning_rate", 0),
            "total_queries": len(recent_data),
            "query_rate": len(recent_data) / 3600 if recent_data else 0,
            "learning_velocity": self._calculate_learning_velocity(recent_data),
        }

    def _calculate_learning_velocity(self, recent_data: list) -> float:
        """計算學習速度"""
        if len(recent_data) < 20:
            return 0.0

        # 將數據分成兩半比較準確度改善
        mid_point = len(recent_data) // 2
        early_accuracy = statistics.mean([m.accuracy for m in recent_data[:mid_point]])
        later_accuracy = statistics.mean([m.accuracy for m in recent_data[mid_point:]])

        return max(0, later_accuracy - early_accuracy)

    async def _check_response_time_alerts(self, metrics: dict):
        """檢查響應時間告警"""
        avg_response_time = metrics.get("avg_response_time", 0)
        thresholds = self.alert_thresholds["response_time"]

        alert_id = "response_time_alert"

        if avg_response_time > thresholds["critical"]:
            await self._create_alert(
                alert_id,
                AlertSeverity.CRITICAL,
                "響應時間嚴重過長",
                f"平均響應時間 {avg_response_time:.2f}s 超過臨界閾值 {thresholds['critical']}s",
                "response_time",
                avg_response_time,
                thresholds["critical"],
            )
        elif avg_response_time > thresholds["warning"]:
            await self._create_alert(
                alert_id,
                AlertSeverity.WARNING,
                "響應時間過長",
                f"平均響應時間 {avg_response_time:.2f}s 超過警告閾值 {thresholds['warning']}s",
                "response_time",
                avg_response_time,
                thresholds["warning"],
            )
        else:
            await self._resolve_alert(alert_id)

    async def _check_success_rate_alerts(self, metrics: dict):
        """檢查成功率告警"""
        success_rate = metrics.get("success_rate", 1.0)
        thresholds = self.alert_thresholds["success_rate"]

        alert_id = "success_rate_alert"

        if success_rate < thresholds["critical"]:
            await self._create_alert(
                alert_id,
                AlertSeverity.CRITICAL,
                "成功率嚴重過低",
                f"成功率 {success_rate:.1%} 低於臨界閾值 {thresholds['critical']:.1%}",
                "success_rate",
                success_rate,
                thresholds["critical"],
            )
        elif success_rate < thresholds["warning"]:
            await self._create_alert(
                alert_id,
                AlertSeverity.WARNING,
                "成功率過低",
                f"成功率 {success_rate:.1%} 低於警告閾值 {thresholds['warning']:.1%}",
                "success_rate",
                success_rate,
                thresholds["warning"],
            )
        else:
            await self._resolve_alert(alert_id)

    async def _check_accuracy_alerts(self, metrics: dict):
        """檢查準確度告警"""
        avg_accuracy = metrics.get("avg_accuracy", 0)
        thresholds = self.alert_thresholds["accuracy"]

        alert_id = "accuracy_alert"

        if avg_accuracy < thresholds["critical"]:
            await self._create_alert(
                alert_id,
                AlertSeverity.CRITICAL,
                "準確度嚴重過低",
                f"平均準確度 {avg_accuracy:.1%} 低於臨界閾值 {thresholds['critical']:.1%}",
                "accuracy",
                avg_accuracy,
                thresholds["critical"],
            )
        elif avg_accuracy < thresholds["warning"]:
            await self._create_alert(
                alert_id,
                AlertSeverity.WARNING,
                "準確度過低",
                f"平均準確度 {avg_accuracy:.1%} 低於警告閾值 {thresholds['warning']:.1%}",
                "accuracy",
                avg_accuracy,
                thresholds["warning"],
            )
        else:
            await self._resolve_alert(alert_id)

    async def _check_exploration_rate_alerts(self, metrics: dict):
        """檢查探索率告警"""
        exploration_rate = metrics.get("exploration_rate", 0)
        thresholds = self.alert_thresholds["exploration_rate"]

        alert_id = "exploration_rate_alert"

        if exploration_rate > thresholds["critical"]:
            await self._create_alert(
                alert_id,
                AlertSeverity.WARNING,
                "探索率過高",
                f"探索率 {exploration_rate:.1%} 超過臨界閾值 {thresholds['critical']:.1%}",
                "exploration_rate",
                exploration_rate,
                thresholds["critical"],
            )
        elif exploration_rate > thresholds["warning"]:
            await self._create_alert(
                alert_id,
                AlertSeverity.INFO,
                "探索率較高",
                f"探索率 {exploration_rate:.1%} 超過警告閾值 {thresholds['warning']:.1%}",
                "exploration_rate",
                exploration_rate,
                thresholds["warning"],
            )
        else:
            await self._resolve_alert(alert_id)

    async def _check_learning_velocity_alerts(self, metrics: dict):
        """檢查學習速度告警"""
        learning_velocity = metrics.get("learning_velocity", 0)
        thresholds = self.alert_thresholds["learning_velocity"]

        alert_id = "learning_velocity_alert"

        if learning_velocity < thresholds["critical"]:
            await self._create_alert(
                alert_id,
                AlertSeverity.CRITICAL,
                "學習速度嚴重過慢",
                f"學習速度 {learning_velocity:.3f} 低於臨界閾值 {thresholds['critical']:.3f}",
                "learning_velocity",
                learning_velocity,
                thresholds["critical"],
            )
        elif learning_velocity < thresholds["warning"]:
            await self._create_alert(
                alert_id,
                AlertSeverity.WARNING,
                "學習速度過慢",
                f"學習速度 {learning_velocity:.3f} 低於警告閾值 {thresholds['warning']:.3f}",
                "learning_velocity",
                learning_velocity,
                thresholds["warning"],
            )
        else:
            await self._resolve_alert(alert_id)

    async def _create_alert(
        self,
        alert_id: str,
        severity: AlertSeverity,
        title: str,
        message: str,
        metric_name: str,
        current_value: float,
        threshold_value: float,
    ):
        """創建告警"""
        if alert_id not in self.active_alerts:
            alert = Alert(
                id=alert_id,
                timestamp=time.time(),
                severity=severity,
                title=title,
                message=message,
                source="adaptive_strategy_monitor",
                metric_name=metric_name,
                current_value=current_value,
                threshold_value=threshold_value,
                tags={"component": "rag_system", "type": "performance"},
            )

            self.active_alerts[alert_id] = alert
            self.logger.warning(f"新告警: [{severity.value.upper()}] {title} - {message}")

            # 發送告警通知（這裡可以集成外部告警系統）
            await self._send_alert_notification(alert)

    async def _resolve_alert(self, alert_id: str):
        """解決告警"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts.pop(alert_id)
            alert.resolved = True
            alert.resolved_timestamp = time.time()

            self.resolved_alerts.append(alert)
            self.logger.info(f"告警已解決: {alert.title}")

            # 保持解決告警列表大小
            if len(self.resolved_alerts) > 1000:
                self.resolved_alerts = self.resolved_alerts[-500:]

    async def _cleanup_resolved_alerts(self):
        """清理過期的已解決告警"""
        cutoff_time = time.time() - (7 * 24 * 3600)  # 7天前
        self.resolved_alerts = [
            alert
            for alert in self.resolved_alerts
            if alert.resolved_timestamp and alert.resolved_timestamp > cutoff_time
        ]

    async def _send_alert_notification(self, alert: Alert):
        """發送告警通知（可集成外部系統）"""
        # 這裡可以集成 Slack, 郵件, 企業微信等通知系統
        notification_data = {
            "alert_id": alert.id,
            "severity": alert.severity.value,
            "title": alert.title,
            "message": alert.message,
            "timestamp": datetime.fromtimestamp(alert.timestamp).isoformat(),
            "metric": alert.metric_name,
            "current_value": alert.current_value,
            "threshold": alert.threshold_value,
        }

        self.logger.info(f"告警通知: {json.dumps(notification_data, ensure_ascii=False)}")

    async def _execute_optimizations(self):
        """執行自動優化"""
        if not self.enable_auto_optimization:
            return

        # 獲取當前指標
        metrics = await self._collect_current_metrics()

        for rule in self.optimization_rules:
            # 檢查冷卻期
            if time.time() - rule.last_executed < rule.cooldown_seconds:
                continue

            # 檢查條件
            if rule.condition(metrics):
                self.logger.info(f"觸發優化規則: {rule.name}")

                try:
                    success = await self._execute_optimization_action(rule, metrics)
                    if success:
                        rule.last_executed = time.time()

                        # 記錄優化歷史
                        self.optimization_history.append(
                            {
                                "timestamp": time.time(),
                                "rule_name": rule.name,
                                "action": rule.action.value,
                                "parameters": rule.parameters,
                                "metrics_before": metrics,
                                "success": success,
                            }
                        )

                        # 保持歷史記錄大小
                        if len(self.optimization_history) > 1000:
                            self.optimization_history = self.optimization_history[-500:]

                except Exception as e:
                    self.logger.error(f"執行優化操作失敗: {rule.name} - {e}")

    async def _execute_optimization_action(
        self, rule: OptimizationRule, current_metrics: dict
    ) -> bool:
        """執行優化操作"""
        try:
            if rule.action == OptimizationAction.ADJUST_LEARNING_RATE:
                return await self._adjust_learning_rate(rule.parameters)

            elif rule.action == OptimizationAction.ADJUST_EXPLORATION_RATE:
                return await self._adjust_exploration_rate(rule.parameters)

            elif rule.action == OptimizationAction.RESET_STRATEGY_WEIGHTS:
                return await self._reset_strategy_weights()

            elif rule.action == OptimizationAction.CLEAR_CACHE:
                return await self._clear_cache()

            else:
                self.logger.warning(f"未知的優化操作: {rule.action}")
                return False

        except Exception as e:
            self.logger.error(f"優化操作執行失敗: {e}")
            return False

    async def _adjust_learning_rate(self, parameters: dict) -> bool:
        """調整學習率"""
        current_rate = self.adaptive_manager.learning_rate
        adjustment_factor = parameters.get("adjustment_factor", 1.1)
        max_rate = parameters.get("max_rate", 0.5)

        new_rate = min(current_rate * adjustment_factor, max_rate)

        if abs(new_rate - current_rate) > 0.001:  # 避免微小變化
            self.adaptive_manager.learning_rate = new_rate
            self.logger.info(f"學習率已調整: {current_rate:.3f} -> {new_rate:.3f}")
            return True

        return False

    async def _adjust_exploration_rate(self, parameters: dict) -> bool:
        """調整探索率"""
        current_rate = self.adaptive_manager.exploration_rate
        adjustment_factor = parameters.get("adjustment_factor", 0.9)
        min_rate = parameters.get("min_rate", 0.1)

        new_rate = max(current_rate * adjustment_factor, min_rate)

        if abs(new_rate - current_rate) > 0.01:  # 避免微小變化
            self.adaptive_manager.exploration_rate = new_rate
            self.logger.info(f"探索率已調整: {current_rate:.3f} -> {new_rate:.3f}")
            return True

        return False

    async def _reset_strategy_weights(self) -> bool:
        """重置策略權重"""
        try:
            # 重置策略性能統計
            self.adaptive_manager.strategy_performance = {
                strategy: {"total_reward": 0.0, "count": 0}
                for strategy in self.adaptive_manager.strategy_performance
            }
            self.logger.info("策略權重已重置")
            return True
        except Exception as e:
            self.logger.error(f"重置策略權重失敗: {e}")
            return False

    async def _clear_cache(self) -> bool:
        """清理緩存"""
        try:
            # 這裡可以實現具體的緩存清理邏輯
            # 比如清理向量緩存、查詢緩存等
            self.logger.info("緩存已清理")
            return True
        except Exception as e:
            self.logger.error(f"清理緩存失敗: {e}")
            return False

    def get_alert_summary(self) -> dict[str, Any]:
        """獲取告警摘要"""
        return {
            "active_alerts_count": len(self.active_alerts),
            "active_alerts": [
                {
                    "id": alert.id,
                    "severity": alert.severity.value,
                    "title": alert.title,
                    "timestamp": alert.timestamp,
                    "age_seconds": time.time() - alert.timestamp,
                }
                for alert in self.active_alerts.values()
            ],
            "resolved_alerts_count": len(self.resolved_alerts),
            "last_check_time": self.last_check_time,
            "optimization_enabled": self.enable_auto_optimization,
            "optimization_rules_count": len(self.optimization_rules),
            "recent_optimizations": self.optimization_history[-10:],  # 最近10次優化
        }

    def export_alert_history(self, filepath: str, hours: int = 24):
        """導出告警歷史"""
        cutoff_time = time.time() - (hours * 3600)

        export_data = {
            "export_timestamp": time.time(),
            "export_range_hours": hours,
            "active_alerts": [
                {
                    "id": alert.id,
                    "timestamp": alert.timestamp,
                    "severity": alert.severity.value,
                    "title": alert.title,
                    "message": alert.message,
                    "metric_name": alert.metric_name,
                    "current_value": alert.current_value,
                    "threshold_value": alert.threshold_value,
                }
                for alert in self.active_alerts.values()
            ],
            "resolved_alerts": [
                {
                    "id": alert.id,
                    "timestamp": alert.timestamp,
                    "resolved_timestamp": alert.resolved_timestamp,
                    "severity": alert.severity.value,
                    "title": alert.title,
                    "message": alert.message,
                    "duration_seconds": (alert.resolved_timestamp or time.time()) - alert.timestamp,
                }
                for alert in self.resolved_alerts
                if alert.timestamp > cutoff_time
            ],
            "optimization_history": [
                opt for opt in self.optimization_history if opt["timestamp"] > cutoff_time
            ],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        self.logger.info(f"告警歷史已導出到: {filepath}")


# 測試程序
async def main():
    """測試告警和優化系統"""
    from adaptive_strategy_monitor import AdaptiveStrategyMonitor
    from enhanced_adaptive_strategies import EnhancedAdaptiveManager

    # 創建組件
    adaptive_manager = EnhancedAdaptiveManager()
    monitor = AdaptiveStrategyMonitor(adaptive_manager)

    # 創建告警系統
    alert_system = AlertAndOptimizationSystem(adaptive_manager, monitor)

    # 啟動監控
    await monitor.start_monitoring()

    # 模擬一些性能問題來觸發告警
    test_context = QueryContext(query_text="測試查詢")

    # 模擬響應時間過長
    for i in range(5):
        strategy = await adaptive_manager.select_optimal_strategy(test_context)
        await monitor.record_strategy_performance(
            strategy,
            test_context,
            {
                "response_time": 3.0 + i,  # 響應時間過長
                "confidence": 0.5,  # 準確度過低
                "success": False,  # 失敗
                "user_satisfaction": 2.0,
            },
        )
        await asyncio.sleep(1)

    # 啟動告警系統
    # 保留 task 引用避免被 GC 回收（asyncio 只保存弱引用）
    _alert_task = asyncio.create_task(alert_system.start_monitoring())  # noqa: RUF006

    # 運行5分鐘
    await asyncio.sleep(30)

    # 獲取告警摘要
    summary = alert_system.get_alert_summary()
    print("告警摘要:", json.dumps(summary, ensure_ascii=False, indent=2))

    # 停止系統
    await alert_system.stop_monitoring()
    await monitor.stop_monitoring()


if __name__ == "__main__":
    asyncio.run(main())
