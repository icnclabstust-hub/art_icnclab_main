#!/usr/bin/env python3
"""
Agent監控器
負責監控Agent健康狀況、性能指標和異常檢測
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import psutil


class HealthStatus(Enum):
    """健康狀態"""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AlertLevel(Enum):
    """告警級別"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthMetrics:
    """健康指標"""

    agent_id: str
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    response_time: float
    task_success_rate: float
    error_count: int
    last_heartbeat: datetime
    status: HealthStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "response_time": self.response_time,
            "task_success_rate": self.task_success_rate,
            "error_count": self.error_count,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "status": self.status.value,
        }


@dataclass
class Alert:
    """告警"""

    alert_id: str
    agent_id: str
    level: AlertLevel
    message: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "agent_id": self.agent_id,
            "level": self.level.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class HealthChecker:
    """健康檢查器"""

    def __init__(self):
        self.thresholds = {
            "cpu_warning": 70.0,
            "cpu_critical": 90.0,
            "memory_warning": 80.0,
            "memory_critical": 95.0,
            "response_time_warning": 10.0,
            "response_time_critical": 30.0,
            "success_rate_warning": 0.8,
            "success_rate_critical": 0.6,
            "heartbeat_timeout": 120,  # 秒
        }

    def check_health(self, agent_id: str, metrics: dict[str, Any]) -> HealthStatus:
        """檢查Agent健康狀況"""
        issues = []

        # CPU檢查
        cpu_usage = metrics.get("cpu_usage", 0)
        if cpu_usage > self.thresholds["cpu_critical"]:
            issues.append("critical_cpu")
        elif cpu_usage > self.thresholds["cpu_warning"]:
            issues.append("warning_cpu")

        # 內存檢查
        memory_usage = metrics.get("memory_usage", 0)
        if memory_usage > self.thresholds["memory_critical"]:
            issues.append("critical_memory")
        elif memory_usage > self.thresholds["memory_warning"]:
            issues.append("warning_memory")

        # 響應時間檢查
        response_time = metrics.get("response_time", 0)
        if response_time > self.thresholds["response_time_critical"]:
            issues.append("critical_response")
        elif response_time > self.thresholds["response_time_warning"]:
            issues.append("warning_response")

        # 成功率檢查
        success_rate = metrics.get("task_success_rate", 1.0)
        if success_rate < self.thresholds["success_rate_critical"]:
            issues.append("critical_success")
        elif success_rate < self.thresholds["success_rate_warning"]:
            issues.append("warning_success")

        # 心跳檢查
        last_heartbeat = metrics.get("last_heartbeat")
        if last_heartbeat:
            if isinstance(last_heartbeat, str):
                last_heartbeat = datetime.fromisoformat(last_heartbeat)
            time_since_heartbeat = (datetime.now() - last_heartbeat).total_seconds()
            if time_since_heartbeat > self.thresholds["heartbeat_timeout"]:
                issues.append("critical_heartbeat")

        # 確定整體健康狀況
        if any("critical" in issue for issue in issues):
            return HealthStatus.CRITICAL
        elif any("warning" in issue for issue in issues):
            return HealthStatus.WARNING
        elif issues:
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY


class AgentMonitor:
    """Agent監控器"""

    def __init__(self):
        self.logger = logging.getLogger("agent_monitor")

        # 監控數據
        self.agents: dict[str, dict[str, Any]] = {}
        self.health_history: dict[str, list[HealthMetrics]] = {}
        self.alerts: dict[str, Alert] = {}
        self.active_alerts: dict[str, list[str]] = {}  # agent_id -> alert_ids

        # 組件
        self.health_checker = HealthChecker()

        # 配置
        self.monitoring_interval = 30  # 秒
        self.history_retention = timedelta(hours=24)
        self.max_history_entries = 1000

        # 告警處理器
        self.alert_handlers: list[Callable] = []

        # 運行狀態
        self.is_running = False

    async def initialize(self):
        """初始化監控器"""
        self.is_running = True
        asyncio.create_task(self._monitoring_loop())
        asyncio.create_task(self._cleanup_loop())
        self.logger.info("Agent監控器初始化完成")

    async def shutdown(self):
        """關閉監控器"""
        self.is_running = False
        self.logger.info("Agent監控器已關閉")

    def register_agent(self, agent_id: str, agent_info: dict[str, Any]):
        """註冊Agent到監控"""
        self.agents[agent_id] = {
            **agent_info,
            "registered_at": datetime.now(),
            "last_seen": datetime.now(),
            "status": "registered",
        }

        # 初始化歷史記錄
        self.health_history[agent_id] = []
        self.active_alerts[agent_id] = []

        self.logger.info(f"Agent {agent_id} 已註冊到監控")

    def unregister_agent(self, agent_id: str):
        """從監控中註銷Agent"""
        if agent_id in self.agents:
            # 清理數據
            del self.agents[agent_id]
            if agent_id in self.health_history:
                del self.health_history[agent_id]
            if agent_id in self.active_alerts:
                # 解決所有活躍告警
                for alert_id in self.active_alerts[agent_id]:
                    if alert_id in self.alerts:
                        self.alerts[alert_id].resolved = True
                        self.alerts[alert_id].resolved_at = datetime.now()
                del self.active_alerts[agent_id]

            self.logger.info(f"Agent {agent_id} 已從監控中註銷")

    async def update_agent_metrics(self, agent_id: str, metrics: dict[str, Any]):
        """更新Agent指標"""
        if agent_id not in self.agents:
            self.logger.warning(f"未註冊的Agent {agent_id} 嘗試更新指標")
            return

        # 更新Agent信息
        self.agents[agent_id]["last_seen"] = datetime.now()
        self.agents[agent_id]["last_metrics"] = metrics

        # 檢查健康狀況
        health_status = self.health_checker.check_health(agent_id, metrics)

        # 創建健康指標記錄
        health_metrics = HealthMetrics(
            agent_id=agent_id,
            timestamp=datetime.now(),
            cpu_usage=metrics.get("cpu_usage", 0),
            memory_usage=metrics.get("memory_usage", 0),
            response_time=metrics.get("response_time", 0),
            task_success_rate=metrics.get("task_success_rate", 1.0),
            error_count=metrics.get("error_count", 0),
            last_heartbeat=datetime.now(),
            status=health_status,
        )

        # 添加到歷史記錄
        self.health_history[agent_id].append(health_metrics)

        # 限制歷史記錄數量
        if len(self.health_history[agent_id]) > self.max_history_entries:
            self.health_history[agent_id] = self.health_history[agent_id][
                -self.max_history_entries :
            ]

        # 檢查是否需要產生告警
        await self._check_alerts(agent_id, health_metrics)

    async def check_all_agents(self):
        """檢查所有Agent的健康狀況"""
        for agent_id in list(self.agents.keys()):
            await self._check_agent_status(agent_id)

    async def _check_agent_status(self, agent_id: str):
        """檢查單個Agent狀態"""
        if agent_id not in self.agents:
            return

        agent_info = self.agents[agent_id]
        last_seen = agent_info["last_seen"]

        # 檢查是否失聯
        time_since_seen = (datetime.now() - last_seen).total_seconds()
        if time_since_seen > 300:  # 5分鐘未見
            await self._create_alert(
                agent_id, AlertLevel.WARNING, f"Agent {agent_id} 失聯 {time_since_seen:.0f} 秒"
            )

        # 獲取系統指標
        try:
            system_metrics = await self._collect_system_metrics()
            await self.update_agent_metrics(agent_id, system_metrics)
        except Exception as e:
            self.logger.error(f"收集Agent {agent_id} 系統指標失敗: {e}")

    async def _collect_system_metrics(self) -> dict[str, Any]:
        """收集系統指標"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)

            # 內存使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # 進程信息
            process = psutil.Process()
            process_cpu = process.cpu_percent()
            process_memory = process.memory_info().rss / 1024 / 1024  # MB

            return {
                "cpu_usage": cpu_percent,
                "memory_usage": memory_percent,
                "process_cpu": process_cpu,
                "process_memory": process_memory,
                "response_time": 0.0,  # 需要從Agent獲取
                "task_success_rate": 1.0,  # 需要從Agent獲取
                "error_count": 0,  # 需要從Agent獲取
            }

        except Exception as e:
            self.logger.error(f"收集系統指標失敗: {e}")
            return {}

    async def _check_alerts(self, agent_id: str, health_metrics: HealthMetrics):
        """檢查是否需要產生告警"""
        current_status = health_metrics.status

        # 檢查狀態變化
        if len(self.health_history[agent_id]) > 1:
            previous_status = self.health_history[agent_id][-2].status

            # 狀態惡化
            if previous_status == HealthStatus.HEALTHY and current_status in [
                HealthStatus.WARNING,
                HealthStatus.CRITICAL,
            ]:
                level = (
                    AlertLevel.WARNING
                    if current_status == HealthStatus.WARNING
                    else AlertLevel.CRITICAL
                )
                await self._create_alert(
                    agent_id, level, f"Agent健康狀況變為{current_status.value}"
                )
            elif (
                previous_status == HealthStatus.WARNING and current_status == HealthStatus.CRITICAL
            ):
                await self._create_alert(
                    agent_id, AlertLevel.CRITICAL, f"Agent健康狀況惡化為{current_status.value}"
                )
            elif (
                previous_status in [HealthStatus.WARNING, HealthStatus.CRITICAL]
                and current_status == HealthStatus.HEALTHY
            ):
                # 恢復正常，解決相關告警
                await self._resolve_alerts(agent_id, "健康狀況恢復正常")

        # 特定指標檢查
        if health_metrics.cpu_usage > 90:
            await self._create_alert(
                agent_id, AlertLevel.CRITICAL, f"CPU使用率過高: {health_metrics.cpu_usage:.1f}%"
            )

        if health_metrics.memory_usage > 95:
            await self._create_alert(
                agent_id, AlertLevel.CRITICAL, f"內存使用率過高: {health_metrics.memory_usage:.1f}%"
            )

        if health_metrics.response_time > 30:
            await self._create_alert(
                agent_id, AlertLevel.WARNING, f"響應時間過長: {health_metrics.response_time:.2f}秒"
            )

    async def _create_alert(self, agent_id: str, level: AlertLevel, message: str):
        """創建告警"""
        import uuid

        alert_id = str(uuid.uuid4())
        alert = Alert(
            alert_id=alert_id,
            agent_id=agent_id,
            level=level,
            message=message,
            timestamp=datetime.now(),
        )

        self.alerts[alert_id] = alert
        self.active_alerts[agent_id].append(alert_id)

        # 觸發告警處理器
        for handler in self.alert_handlers:
            try:
                await handler(alert)
            except Exception as e:
                self.logger.error(f"告警處理器執行失敗: {e}")

        self.logger.warning(f"Agent {agent_id} 產生{level.value}告警: {message}")

    async def _resolve_alerts(self, agent_id: str, reason: str):
        """解決Agent的告警"""
        if agent_id not in self.active_alerts:
            return

        resolved_count = 0
        for alert_id in self.active_alerts[agent_id][:]:
            if alert_id in self.alerts and not self.alerts[alert_id].resolved:
                self.alerts[alert_id].resolved = True
                self.alerts[alert_id].resolved_at = datetime.now()
                self.active_alerts[agent_id].remove(alert_id)
                resolved_count += 1

        if resolved_count > 0:
            self.logger.info(f"Agent {agent_id} 解決了 {resolved_count} 個告警: {reason}")

    async def _monitoring_loop(self):
        """監控循環"""
        while self.is_running:
            try:
                await self.check_all_agents()
                await asyncio.sleep(self.monitoring_interval)
            except Exception as e:
                self.logger.error(f"監控循環錯誤: {e}")
                await asyncio.sleep(10)

    async def _cleanup_loop(self):
        """清理循環"""
        while self.is_running:
            try:
                await self._cleanup_old_data()
                await asyncio.sleep(3600)  # 每小時清理一次
            except Exception as e:
                self.logger.error(f"清理循環錯誤: {e}")

    async def _cleanup_old_data(self):
        """清理舊數據"""
        cutoff_time = datetime.now() - self.history_retention

        # 清理健康歷史
        for agent_id in self.health_history:
            self.health_history[agent_id] = [
                metrics
                for metrics in self.health_history[agent_id]
                if metrics.timestamp > cutoff_time
            ]

        # 清理已解決的舊告警
        old_alerts = [
            alert_id
            for alert_id, alert in self.alerts.items()
            if alert.resolved and alert.resolved_at and alert.resolved_at < cutoff_time
        ]

        for alert_id in old_alerts:
            del self.alerts[alert_id]

        self.logger.debug(f"清理了 {len(old_alerts)} 個舊告警")

    def add_alert_handler(self, handler: Callable):
        """添加告警處理器"""
        self.alert_handlers.append(handler)

    def get_agent_health(self, agent_id: str) -> dict[str, Any] | None:
        """獲取Agent健康狀況"""
        if agent_id not in self.agents:
            return None

        agent_info = self.agents[agent_id]
        recent_metrics = None

        if agent_id in self.health_history and self.health_history[agent_id]:
            recent_metrics = self.health_history[agent_id][-1]

        active_alert_count = len(self.active_alerts.get(agent_id, []))

        return {
            "agent_id": agent_id,
            "name": agent_info.get("name"),
            "status": recent_metrics.status.value if recent_metrics else "unknown",
            "last_seen": agent_info["last_seen"].isoformat(),
            "metrics": recent_metrics.to_dict() if recent_metrics else None,
            "active_alerts": active_alert_count,
            "uptime": (datetime.now() - agent_info["registered_at"]).total_seconds(),
        }

    def get_system_overview(self) -> dict[str, Any]:
        """獲取系統概覽"""
        total_agents = len(self.agents)
        healthy_agents = 0
        warning_agents = 0
        critical_agents = 0

        for agent_id in self.agents:
            if agent_id in self.health_history and self.health_history[agent_id]:
                status = self.health_history[agent_id][-1].status
                if status == HealthStatus.HEALTHY:
                    healthy_agents += 1
                elif status == HealthStatus.WARNING:
                    warning_agents += 1
                elif status == HealthStatus.CRITICAL:
                    critical_agents += 1

        total_alerts = len([alert for alert in self.alerts.values() if not alert.resolved])
        critical_alerts = len(
            [
                alert
                for alert in self.alerts.values()
                if not alert.resolved and alert.level == AlertLevel.CRITICAL
            ]
        )

        return {
            "total_agents": total_agents,
            "healthy_agents": healthy_agents,
            "warning_agents": warning_agents,
            "critical_agents": critical_agents,
            "total_alerts": total_alerts,
            "critical_alerts": critical_alerts,
            "monitoring_since": min(
                (agent["registered_at"] for agent in self.agents.values()), default=datetime.now()
            ).isoformat(),
        }

    def get_agent_history(self, agent_id: str, hours: int = 1) -> list[dict[str, Any]]:
        """獲取Agent歷史數據"""
        if agent_id not in self.health_history:
            return []

        cutoff_time = datetime.now() - timedelta(hours=hours)

        return [
            metrics.to_dict()
            for metrics in self.health_history[agent_id]
            if metrics.timestamp > cutoff_time
        ]

    def get_active_alerts(self, agent_id: str = None) -> list[dict[str, Any]]:
        """獲取活躍告警"""
        active_alerts = [alert for alert in self.alerts.values() if not alert.resolved]

        if agent_id:
            active_alerts = [alert for alert in active_alerts if alert.agent_id == agent_id]

        return [alert.to_dict() for alert in active_alerts]
