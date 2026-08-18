#!/usr/bin/env python3
"""
RAG 系統性能監控器
監控查詢性能、資源使用、準確性等關鍵指標
"""

import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import psutil

logger = logging.getLogger(__name__)


@dataclass
class QueryMetrics:
    """查詢指標"""

    query: str
    response_time: float
    num_results: int
    cache_hit: bool
    accuracy_score: float | None = None
    user_feedback: int | None = None  # 1-5 評分
    timestamp: float = field(default_factory=time.time)


@dataclass
class SystemMetrics:
    """系統指標"""

    cpu_percent: float
    memory_percent: float
    gpu_percent: float = 0.0
    disk_io: dict[str, float] = field(default_factory=dict)
    network_io: dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class PerformanceMonitor:
    """性能監控器"""

    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.query_history = deque(maxlen=max_history)
        self.system_history = deque(maxlen=max_history)
        self.error_history = deque(maxlen=1000)

        # 聚合統計
        self.daily_stats = defaultdict(
            lambda: {
                "query_count": 0,
                "avg_response_time": 0.0,
                "cache_hit_rate": 0.0,
                "error_rate": 0.0,
            }
        )

        # 即時監控
        self.current_qps = 0
        self.last_qps_update = time.time()
        self.recent_queries = deque(maxlen=100)  # 最近100個查詢

    def log_query(self, metrics: QueryMetrics):
        """記錄查詢指標"""
        self.query_history.append(metrics)
        self.recent_queries.append(metrics)

        # 更新每日統計
        date_key = datetime.fromtimestamp(metrics.timestamp).strftime("%Y-%m-%d")
        daily = self.daily_stats[date_key]
        daily["query_count"] += 1

        # 滑動平均更新響應時間
        total_time = daily["avg_response_time"] * (daily["query_count"] - 1)
        daily["avg_response_time"] = (total_time + metrics.response_time) / daily["query_count"]

        # 更新 QPS
        self._update_qps()

    def log_system_metrics(self):
        """記錄系統指標"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk_io = psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else {}
            network_io = psutil.net_io_counters()._asdict() if psutil.net_io_counters() else {}

            # GPU 使用率 (如果可用)
            gpu_percent = self._get_gpu_usage()

            metrics = SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                gpu_percent=gpu_percent,
                disk_io=disk_io,
                network_io=network_io,
            )

            self.system_history.append(metrics)

        except Exception as e:
            logger.warning(f"系統指標收集失敗: {e}")

    def log_error(self, error: str, query: str = "", context: dict = None):
        """記錄錯誤"""
        error_record = {
            "error": error,
            "query": query,
            "context": context or {},
            "timestamp": time.time(),
        }
        self.error_history.append(error_record)

        # 更新每日錯誤率
        date_key = datetime.now().strftime("%Y-%m-%d")
        daily = self.daily_stats[date_key]
        total_queries = daily["query_count"]
        if total_queries > 0:
            error_count = sum(
                1
                for err in self.error_history
                if datetime.fromtimestamp(err["timestamp"]).strftime("%Y-%m-%d") == date_key
            )
            daily["error_rate"] = error_count / total_queries

    def _update_qps(self):
        """更新每秒查詢數"""
        current_time = time.time()
        if current_time - self.last_qps_update >= 1.0:
            # 計算最近1分鐘的 QPS
            one_minute_ago = current_time - 60
            recent_count = sum(1 for q in self.recent_queries if q.timestamp >= one_minute_ago)
            self.current_qps = recent_count / 60.0
            self.last_qps_update = current_time

    def _get_gpu_usage(self) -> float:
        """獲取 GPU 使用率"""
        try:
            import pynvml

            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            return float(utilization.gpu)
        except:
            return 0.0

    def get_current_stats(self) -> dict[str, Any]:
        """獲取當前統計"""
        if not self.query_history:
            return {"message": "暫無查詢記錄"}

        recent_queries = list(self.query_history)[-100:]  # 最近100個查詢

        # 基本統計
        response_times = [q.response_time for q in recent_queries]
        cache_hits = [q.cache_hit for q in recent_queries]
        accuracy_scores = [q.accuracy_score for q in recent_queries if q.accuracy_score is not None]

        stats = {
            # 響應時間統計
            "response_time": {
                "avg": np.mean(response_times),
                "median": np.median(response_times),
                "p95": np.percentile(response_times, 95),
                "p99": np.percentile(response_times, 99),
                "min": np.min(response_times),
                "max": np.max(response_times),
            },
            # 快取統計
            "cache": {
                "hit_rate": np.mean(cache_hits) if cache_hits else 0,
                "total_hits": sum(cache_hits),
                "total_requests": len(cache_hits),
            },
            # 準確性統計
            "accuracy": {
                "avg_score": np.mean(accuracy_scores) if accuracy_scores else None,
                "scored_queries": len(accuracy_scores),
                "total_queries": len(recent_queries),
            },
            # 吞吐量統計
            "throughput": {
                "current_qps": self.current_qps,
                "total_queries": len(self.query_history),
                "recent_queries": len(recent_queries),
            },
            # 錯誤統計
            "errors": {
                "recent_errors": len(self.error_history),
                "error_rate": len(self.error_history) / len(self.query_history)
                if self.query_history
                else 0,
            },
        }

        # 系統資源統計
        if self.system_history:
            recent_system = list(self.system_history)[-10:]  # 最近10個系統指標

            stats["system"] = {
                "cpu_percent": np.mean([s.cpu_percent for s in recent_system]),
                "memory_percent": np.mean([s.memory_percent for s in recent_system]),
                "gpu_percent": np.mean([s.gpu_percent for s in recent_system]),
            }

        return stats

    def get_performance_trends(self, hours: int = 24) -> dict[str, Any]:
        """獲取性能趨勢 (最近N小時)"""
        cutoff_time = time.time() - (hours * 3600)
        recent_queries = [q for q in self.query_history if q.timestamp >= cutoff_time]

        if not recent_queries:
            return {"message": f"最近 {hours} 小時內無查詢記錄"}

        # 按小時分組
        hourly_stats = defaultdict(list)
        for query in recent_queries:
            hour_key = datetime.fromtimestamp(query.timestamp).strftime("%Y-%m-%d %H:00")
            hourly_stats[hour_key].append(query)

        trends = {}
        for hour, queries in hourly_stats.items():
            trends[hour] = {
                "query_count": len(queries),
                "avg_response_time": np.mean([q.response_time for q in queries]),
                "cache_hit_rate": np.mean([q.cache_hit for q in queries]),
                "accuracy_score": np.mean(
                    [q.accuracy_score for q in queries if q.accuracy_score is not None]
                ),
            }

        return {
            "time_range": f"最近 {hours} 小時",
            "total_queries": len(recent_queries),
            "hourly_trends": trends,
        }

    def get_slow_queries(self, limit: int = 10, min_response_time: float = 1.0) -> list[dict]:
        """獲取慢查詢"""
        slow_queries = [
            {
                "query": q.query[:100] + "..." if len(q.query) > 100 else q.query,
                "response_time": q.response_time,
                "num_results": q.num_results,
                "cache_hit": q.cache_hit,
                "timestamp": datetime.fromtimestamp(q.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
            }
            for q in self.query_history
            if q.response_time >= min_response_time
        ]

        # 按響應時間排序
        slow_queries.sort(key=lambda x: x["response_time"], reverse=True)
        return slow_queries[:limit]

    def get_popular_queries(self, limit: int = 10) -> list[dict]:
        """獲取熱門查詢"""
        query_counts = defaultdict(int)
        query_metrics = {}

        for q in self.query_history:
            query_key = q.query.lower().strip()
            query_counts[query_key] += 1

            # 保存查詢的平均指標
            if query_key not in query_metrics:
                query_metrics[query_key] = {
                    "original_query": q.query,
                    "total_response_time": 0,
                    "total_results": 0,
                    "cache_hits": 0,
                    "count": 0,
                }

            metrics = query_metrics[query_key]
            metrics["total_response_time"] += q.response_time
            metrics["total_results"] += q.num_results
            metrics["cache_hits"] += int(q.cache_hit)
            metrics["count"] += 1

        # 計算平均值並排序
        popular_queries = []
        for query, count in sorted(query_counts.items(), key=lambda x: x[1], reverse=True)[:limit]:
            metrics = query_metrics[query]
            popular_queries.append(
                {
                    "query": metrics["original_query"][:100] + "..."
                    if len(metrics["original_query"]) > 100
                    else metrics["original_query"],
                    "count": count,
                    "avg_response_time": metrics["total_response_time"] / metrics["count"],
                    "avg_results": metrics["total_results"] / metrics["count"],
                    "cache_hit_rate": metrics["cache_hits"] / metrics["count"],
                }
            )

        return popular_queries

    def get_alerts(self) -> list[dict]:
        """獲取性能告警"""
        alerts = []
        stats = self.get_current_stats()

        # 響應時間告警
        if stats["response_time"]["p95"] > 5.0:
            alerts.append(
                {
                    "type": "performance",
                    "severity": "warning",
                    "message": f"95% 響應時間過高: {stats['response_time']['p95']:.2f}s",
                    "threshold": 5.0,
                    "current_value": stats["response_time"]["p95"],
                }
            )

        # 快取命中率告警
        if stats["cache"]["hit_rate"] < 0.5:
            alerts.append(
                {
                    "type": "cache",
                    "severity": "info",
                    "message": f"快取命中率偏低: {stats['cache']['hit_rate']:.1%}",
                    "threshold": 0.5,
                    "current_value": stats["cache"]["hit_rate"],
                }
            )

        # 錯誤率告警
        if stats["errors"]["error_rate"] > 0.1:
            alerts.append(
                {
                    "type": "error",
                    "severity": "critical",
                    "message": f"錯誤率過高: {stats['errors']['error_rate']:.1%}",
                    "threshold": 0.1,
                    "current_value": stats["errors"]["error_rate"],
                }
            )

        # 系統資源告警
        if "system" in stats:
            if stats["system"]["memory_percent"] > 90:
                alerts.append(
                    {
                        "type": "resource",
                        "severity": "critical",
                        "message": f"記憶體使用率過高: {stats['system']['memory_percent']:.1f}%",
                        "threshold": 90,
                        "current_value": stats["system"]["memory_percent"],
                    }
                )

            if stats["system"]["cpu_percent"] > 80:
                alerts.append(
                    {
                        "type": "resource",
                        "severity": "warning",
                        "message": f"CPU 使用率過高: {stats['system']['cpu_percent']:.1f}%",
                        "threshold": 80,
                        "current_value": stats["system"]["cpu_percent"],
                    }
                )

        return alerts

    def export_metrics(self, format: str = "json") -> str:
        """匯出指標"""
        data = {
            "export_time": datetime.now().isoformat(),
            "query_count": len(self.query_history),
            "system_metrics_count": len(self.system_history),
            "error_count": len(self.error_history),
            "current_stats": self.get_current_stats(),
            "daily_stats": dict(self.daily_stats),
        }

        if format.lower() == "json":
            return json.dumps(data, ensure_ascii=False, indent=2)
        else:
            raise ValueError(f"不支持的格式: {format}")

    def reset_metrics(self):
        """重置所有指標"""
        self.query_history.clear()
        self.system_history.clear()
        self.error_history.clear()
        self.daily_stats.clear()
        self.recent_queries.clear()
        logger.info("✅ 性能指標已重置")


# 使用示例
if __name__ == "__main__":
    monitor = PerformanceMonitor()

    # 模擬一些查詢
    for i in range(10):
        metrics = QueryMetrics(
            query=f"測試查詢 {i}",
            response_time=np.random.normal(0.5, 0.2),
            num_results=np.random.randint(1, 10),
            cache_hit=np.random.random() > 0.3,
            accuracy_score=np.random.random(),
        )
        monitor.log_query(metrics)

    # 顯示統計
    print("📊 當前統計:")
    stats = monitor.get_current_stats()
    print(json.dumps(stats, ensure_ascii=False, indent=2))

    print("\n🐌 慢查詢:")
    slow_queries = monitor.get_slow_queries()
    for query in slow_queries:
        print(f"  {query['response_time']:.2f}s: {query['query']}")

    print("\n⚠️ 告警:")
    alerts = monitor.get_alerts()
    for alert in alerts:
        print(f"  [{alert['severity'].upper()}] {alert['message']}")
