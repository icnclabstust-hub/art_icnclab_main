#!/usr/bin/env python3
"""
實驗調度器
負責RAG實驗的智能調度和資源分配
"""

import asyncio
import heapq
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class SchedulingStrategy(Enum):
    """調度策略"""

    PRIORITY_FIRST = "priority_first"
    ROUND_ROBIN = "round_robin"
    SHORTEST_JOB_FIRST = "shortest_job_first"
    FAIR_SHARE = "fair_share"
    RESOURCE_AWARE = "resource_aware"


class ExperimentStatus(Enum):
    """實驗狀態"""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ResourceRequirement:
    """資源需求定義"""

    cpu_cores: int = 1
    memory_gb: float = 1.0
    gpu_count: int = 0
    vector_db: str | None = None
    llm_provider: str | None = None
    max_duration: int = 3600  # 秒


@dataclass
class ScheduledExperiment:
    """調度的實驗"""

    experiment_id: str
    config: dict[str, Any]
    priority: int
    resource_requirements: ResourceRequirement
    estimated_duration: int
    dependencies: list[str]
    created_at: datetime
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: ExperimentStatus = ExperimentStatus.PENDING
    assigned_resources: dict[str, Any] = None
    retry_count: int = 0
    max_retries: int = 3

    def __lt__(self, other):
        """支持優先級隊列"""
        # 優先級越小越優先，時間早的越優先
        return (self.priority, self.created_at) < (other.priority, other.created_at)


class ResourcePool:
    """資源池管理"""

    def __init__(self):
        self.total_resources = {"cpu_cores": 8, "memory_gb": 32.0, "gpu_count": 1}

        self.available_resources = self.total_resources.copy()
        self.allocated_resources: dict[str, dict[str, Any]] = {}

        # 服務資源
        self.vector_databases = {
            "chromadb": {"status": "available", "concurrent_limit": 5, "current_usage": 0},
            "qdrant": {"status": "available", "concurrent_limit": 10, "current_usage": 0},
            "weaviate": {"status": "available", "concurrent_limit": 8, "current_usage": 0},
        }

        self.llm_providers = {
            "openai": {"status": "available", "rate_limit": 100, "current_usage": 0},
            "anthropic": {"status": "available", "rate_limit": 50, "current_usage": 0},
            "ollama": {"status": "available", "concurrent_limit": 3, "current_usage": 0},
            "huggingface": {"status": "available", "rate_limit": 200, "current_usage": 0},
        }

        self.logger = logging.getLogger("resource_pool")

    def can_allocate(self, experiment_id: str, requirements: ResourceRequirement) -> bool:
        """檢查是否可以分配資源"""
        # 檢查基礎資源
        if (
            self.available_resources["cpu_cores"] < requirements.cpu_cores
            or self.available_resources["memory_gb"] < requirements.memory_gb
            or self.available_resources["gpu_count"] < requirements.gpu_count
        ):
            return False

        # 檢查向量資料庫
        if requirements.vector_db:
            db_info = self.vector_databases.get(requirements.vector_db)
            if not db_info or db_info["status"] != "available":
                return False
            if db_info["current_usage"] >= db_info["concurrent_limit"]:
                return False

        # 檢查LLM提供商
        if requirements.llm_provider:
            llm_info = self.llm_providers.get(requirements.llm_provider)
            if not llm_info or llm_info["status"] != "available":
                return False
            if (
                "concurrent_limit" in llm_info
                and llm_info["current_usage"] >= llm_info["concurrent_limit"]
            ):
                return False
            if "rate_limit" in llm_info and llm_info["current_usage"] >= llm_info["rate_limit"]:
                return False

        return True

    def allocate_resources(
        self, experiment_id: str, requirements: ResourceRequirement
    ) -> dict[str, Any]:
        """分配資源"""
        if not self.can_allocate(experiment_id, requirements):
            raise RuntimeError(f"無法為實驗 {experiment_id} 分配資源")

        # 分配基礎資源
        self.available_resources["cpu_cores"] -= requirements.cpu_cores
        self.available_resources["memory_gb"] -= requirements.memory_gb
        self.available_resources["gpu_count"] -= requirements.gpu_count

        allocated = {
            "cpu_cores": requirements.cpu_cores,
            "memory_gb": requirements.memory_gb,
            "gpu_count": requirements.gpu_count,
        }

        # 分配向量資料庫
        if requirements.vector_db:
            self.vector_databases[requirements.vector_db]["current_usage"] += 1
            allocated["vector_db"] = requirements.vector_db

        # 分配LLM
        if requirements.llm_provider:
            self.llm_providers[requirements.llm_provider]["current_usage"] += 1
            allocated["llm_provider"] = requirements.llm_provider

        self.allocated_resources[experiment_id] = allocated

        self.logger.info(f"為實驗 {experiment_id} 分配資源: {allocated}")
        return allocated

    def release_resources(self, experiment_id: str):
        """釋放資源"""
        if experiment_id not in self.allocated_resources:
            self.logger.warning(f"實驗 {experiment_id} 沒有分配的資源")
            return

        allocated = self.allocated_resources[experiment_id]

        # 釋放基礎資源
        self.available_resources["cpu_cores"] += allocated.get("cpu_cores", 0)
        self.available_resources["memory_gb"] += allocated.get("memory_gb", 0)
        self.available_resources["gpu_count"] += allocated.get("gpu_count", 0)

        # 釋放向量資料庫
        if "vector_db" in allocated:
            db_name = allocated["vector_db"]
            if db_name in self.vector_databases:
                self.vector_databases[db_name]["current_usage"] -= 1

        # 釋放LLM
        if "llm_provider" in allocated:
            llm_name = allocated["llm_provider"]
            if llm_name in self.llm_providers:
                self.llm_providers[llm_name]["current_usage"] -= 1

        del self.allocated_resources[experiment_id]

        self.logger.info(f"釋放實驗 {experiment_id} 的資源")

    def get_utilization(self) -> dict[str, float]:
        """獲取資源利用率"""
        return {
            "cpu_utilization": 1.0
            - (self.available_resources["cpu_cores"] / self.total_resources["cpu_cores"]),
            "memory_utilization": 1.0
            - (self.available_resources["memory_gb"] / self.total_resources["memory_gb"]),
            "gpu_utilization": 1.0
            - (self.available_resources["gpu_count"] / self.total_resources["gpu_count"])
            if self.total_resources["gpu_count"] > 0
            else 0,
        }


class ExperimentScheduler:
    """實驗調度器"""

    def __init__(self, strategy: SchedulingStrategy = SchedulingStrategy.PRIORITY_FIRST):
        self.strategy = strategy
        self.resource_pool = ResourcePool()

        # 調度隊列
        self.pending_queue = []  # 優先級隊列
        self.running_experiments: dict[str, ScheduledExperiment] = {}
        self.completed_experiments: dict[str, ScheduledExperiment] = {}
        self.failed_experiments: dict[str, ScheduledExperiment] = {}

        # 調度器狀態
        self.is_running = False
        self.max_concurrent_experiments = 3

        # 統計信息
        self.stats = {
            "total_scheduled": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
            "avg_wait_time": 0.0,
            "avg_execution_time": 0.0,
        }

        self.logger = logging.getLogger("experiment_scheduler")

    async def initialize(self):
        """初始化調度器"""
        self.is_running = True
        asyncio.create_task(self._scheduling_loop())
        asyncio.create_task(self._monitoring_loop())
        self.logger.info("實驗調度器初始化完成")

    async def shutdown(self):
        """關閉調度器"""
        self.is_running = False

        # 取消所有待處理實驗
        for experiment in self.pending_queue:
            experiment.status = ExperimentStatus.CANCELLED

        # 等待運行中的實驗完成
        while self.running_experiments:
            await asyncio.sleep(1)

        self.logger.info("實驗調度器已關閉")

    async def schedule_experiments(
        self, experiments: list[dict[str, Any]]
    ) -> list[ScheduledExperiment]:
        """調度實驗列表"""
        scheduled_experiments = []

        for exp_config in experiments:
            scheduled_exp = await self.schedule_single_experiment(exp_config)
            scheduled_experiments.append(scheduled_exp)

        return scheduled_experiments

    async def schedule_single_experiment(
        self, experiment_config: dict[str, Any]
    ) -> ScheduledExperiment:
        """調度單個實驗"""
        # 創建調度實驗對象
        experiment = ScheduledExperiment(
            experiment_id=experiment_config["experiment_id"],
            config=experiment_config,
            priority=experiment_config.get("priority", 5),
            resource_requirements=self._parse_resource_requirements(experiment_config),
            estimated_duration=experiment_config.get("estimated_duration", 600),
            dependencies=experiment_config.get("dependencies", []),
            created_at=datetime.now(),
        )

        # 檢查依賴
        if await self._check_dependencies(experiment):
            # 添加到調度隊列
            heapq.heappush(self.pending_queue, experiment)
            experiment.status = ExperimentStatus.SCHEDULED
            self.stats["total_scheduled"] += 1

            self.logger.info(f"實驗 {experiment.experiment_id} 已加入調度隊列")
        else:
            experiment.status = ExperimentStatus.PENDING
            self.logger.warning(f"實驗 {experiment.experiment_id} 依賴未滿足，保持待定狀態")

        return experiment

    def _parse_resource_requirements(self, config: dict[str, Any]) -> ResourceRequirement:
        """解析資源需求"""
        resources = config.get("resource_requirements", {})

        return ResourceRequirement(
            cpu_cores=resources.get("cpu_cores", 1),
            memory_gb=resources.get("memory_gb", 2.0),
            gpu_count=resources.get("gpu_count", 0),
            vector_db=self._select_vector_db(config),
            llm_provider=self._select_llm_provider(config),
            max_duration=config.get("max_duration", 3600),
        )

    def _select_vector_db(self, config: dict[str, Any]) -> str:
        """選擇向量資料庫"""
        rag_framework = config.get("rag_framework", "")

        # 基於RAG框架選擇合適的向量資料庫
        if "graph" in rag_framework:
            return "weaviate"  # 圖RAG使用Weaviate
        elif "advanced" in rag_framework:
            return "chromadb"  # 高級RAG使用ChromaDB
        else:
            return "qdrant"  # 默認使用Qdrant

    def _select_llm_provider(self, config: dict[str, Any]) -> str:
        """選擇LLM提供商"""
        llm_model = config.get("llm_model", "")

        if "gpt" in llm_model:
            return "openai"
        elif "claude" in llm_model:
            return "anthropic"
        elif "llama" in llm_model or "gemma" in llm_model:
            return "ollama"
        else:
            return "huggingface"

    async def _check_dependencies(self, experiment: ScheduledExperiment) -> bool:
        """檢查實驗依賴"""
        if not experiment.dependencies:
            return True

        # 檢查所有依賴實驗是否已完成
        for dep_id in experiment.dependencies:
            if dep_id not in self.completed_experiments and dep_id not in self.failed_experiments:
                return False

        return True

    async def _scheduling_loop(self):
        """調度循環"""
        while self.is_running:
            try:
                await self._schedule_next_experiments()
                await asyncio.sleep(5)  # 每5秒檢查一次

            except Exception as e:
                self.logger.error(f"調度循環錯誤: {e}")
                await asyncio.sleep(10)

    async def _schedule_next_experiments(self):
        """調度下一批實驗"""
        # 檢查是否可以啟動新實驗
        available_slots = self.max_concurrent_experiments - len(self.running_experiments)
        if available_slots <= 0:
            return

        # 從隊列中獲取可以執行的實驗
        ready_experiments = []
        remaining_queue = []

        while self.pending_queue and len(ready_experiments) < available_slots:
            experiment = heapq.heappop(self.pending_queue)

            # 檢查資源是否可用
            if self.resource_pool.can_allocate(
                experiment.experiment_id, experiment.resource_requirements
            ):
                # 再次檢查依賴
                if await self._check_dependencies(experiment):
                    ready_experiments.append(experiment)
                else:
                    remaining_queue.append(experiment)
            else:
                remaining_queue.append(experiment)

        # 重新加入不能執行的實驗
        for exp in remaining_queue:
            heapq.heappush(self.pending_queue, exp)

        # 啟動準備好的實驗
        for experiment in ready_experiments:
            await self._start_experiment(experiment)

    async def _start_experiment(self, experiment: ScheduledExperiment):
        """啟動實驗"""
        try:
            # 分配資源
            allocated_resources = self.resource_pool.allocate_resources(
                experiment.experiment_id, experiment.resource_requirements
            )

            experiment.assigned_resources = allocated_resources
            experiment.status = ExperimentStatus.RUNNING
            experiment.started_at = datetime.now()

            # 添加到運行列表
            self.running_experiments[experiment.experiment_id] = experiment

            self.logger.info(f"啟動實驗 {experiment.experiment_id}")

            # 這裡會通知Master Agent啟動實驗
            # 實際實現中會發送消息給Master Agent

        except Exception as e:
            self.logger.error(f"啟動實驗 {experiment.experiment_id} 失敗: {e}")
            experiment.status = ExperimentStatus.FAILED
            self.failed_experiments[experiment.experiment_id] = experiment

    async def complete_experiment(
        self, experiment_id: str, success: bool = True, results: dict[str, Any] = None
    ):
        """完成實驗"""
        if experiment_id not in self.running_experiments:
            self.logger.warning(f"實驗 {experiment_id} 不在運行列表中")
            return

        experiment = self.running_experiments[experiment_id]
        experiment.completed_at = datetime.now()

        # 釋放資源
        self.resource_pool.release_resources(experiment_id)

        # 移動到相應的完成列表
        if success:
            experiment.status = ExperimentStatus.COMPLETED
            self.completed_experiments[experiment_id] = experiment
            self.stats["total_completed"] += 1
        else:
            experiment.status = ExperimentStatus.FAILED
            self.failed_experiments[experiment_id] = experiment
            self.stats["total_failed"] += 1

            # 檢查是否需要重試
            if experiment.retry_count < experiment.max_retries:
                experiment.retry_count += 1
                experiment.status = ExperimentStatus.PENDING
                heapq.heappush(self.pending_queue, experiment)
                self.logger.info(f"實驗 {experiment_id} 將進行第 {experiment.retry_count} 次重試")
                return

        # 從運行列表移除
        del self.running_experiments[experiment_id]

        # 更新統計信息
        self._update_statistics(experiment)

        # 檢查是否有依賴此實驗的其他實驗
        await self._check_dependent_experiments(experiment_id)

        self.logger.info(f"實驗 {experiment_id} 完成，狀態: {experiment.status.value}")

    async def cancel_experiment(self, experiment_id: str):
        """取消實驗"""
        # 檢查各個隊列
        experiment = None

        # 檢查運行中的實驗
        if experiment_id in self.running_experiments:
            experiment = self.running_experiments[experiment_id]
            self.resource_pool.release_resources(experiment_id)
            del self.running_experiments[experiment_id]

        # 檢查待調度隊列
        else:
            for i, exp in enumerate(self.pending_queue):
                if exp.experiment_id == experiment_id:
                    experiment = exp
                    self.pending_queue.pop(i)
                    heapq.heapify(self.pending_queue)
                    break

        if experiment:
            experiment.status = ExperimentStatus.CANCELLED
            experiment.completed_at = datetime.now()
            self.stats["total_cancelled"] += 1
            self.logger.info(f"實驗 {experiment_id} 已取消")
        else:
            self.logger.warning(f"未找到實驗 {experiment_id}")

    async def _check_dependent_experiments(self, completed_experiment_id: str):
        """檢查依賴已完成實驗的其他實驗"""
        # 重新檢查待定隊列中的實驗
        for experiment in self.pending_queue:
            if completed_experiment_id in experiment.dependencies:
                # 重新檢查依賴
                if await self._check_dependencies(experiment):
                    experiment.status = ExperimentStatus.SCHEDULED

        # 隊列會在下次調度循環中處理

    def _update_statistics(self, experiment: ScheduledExperiment):
        """更新統計信息"""
        if experiment.started_at and experiment.completed_at:
            execution_time = (experiment.completed_at - experiment.started_at).total_seconds()

            # 更新平均執行時間
            total_completed = self.stats["total_completed"] + self.stats["total_failed"]
            if total_completed > 0:
                current_avg = self.stats["avg_execution_time"]
                self.stats["avg_execution_time"] = (
                    current_avg * (total_completed - 1) + execution_time
                ) / total_completed

        if experiment.scheduled_at and experiment.started_at:
            wait_time = (experiment.started_at - experiment.scheduled_at).total_seconds()

            # 更新平均等待時間
            current_avg = self.stats["avg_wait_time"]
            total_started = (
                len(self.running_experiments)
                + self.stats["total_completed"]
                + self.stats["total_failed"]
            )
            if total_started > 0:
                self.stats["avg_wait_time"] = (
                    current_avg * (total_started - 1) + wait_time
                ) / total_started

    async def _monitoring_loop(self):
        """監控循環"""
        while self.is_running:
            try:
                # 檢查超時實驗
                await self._check_experiment_timeouts()

                # 記錄統計信息
                self._log_statistics()

                await asyncio.sleep(30)  # 每30秒檢查一次

            except Exception as e:
                self.logger.error(f"監控循環錯誤: {e}")

    async def _check_experiment_timeouts(self):
        """檢查超時實驗"""
        current_time = datetime.now()

        timeout_experiments = []
        for exp_id, experiment in self.running_experiments.items():
            if experiment.started_at:
                runtime = (current_time - experiment.started_at).total_seconds()
                if runtime > experiment.resource_requirements.max_duration:
                    timeout_experiments.append(exp_id)

        for exp_id in timeout_experiments:
            self.logger.warning(f"實驗 {exp_id} 超時，將被取消")
            await self.complete_experiment(exp_id, success=False)

    def _log_statistics(self):
        """記錄統計信息"""
        self.logger.info(
            f"調度器統計 - 待調度: {len(self.pending_queue)}, "
            f"運行中: {len(self.running_experiments)}, "
            f"已完成: {self.stats['total_completed']}, "
            f"失敗: {self.stats['total_failed']}"
        )

        # 記錄資源利用率
        utilization = self.resource_pool.get_utilization()
        self.logger.debug(f"資源利用率: {utilization}")

    def get_status(self) -> dict[str, Any]:
        """獲取調度器狀態"""
        return {
            "is_running": self.is_running,
            "strategy": self.strategy.value,
            "queue_status": {
                "pending": len(self.pending_queue),
                "running": len(self.running_experiments),
                "completed": len(self.completed_experiments),
                "failed": len(self.failed_experiments),
            },
            "resource_utilization": self.resource_pool.get_utilization(),
            "statistics": self.stats.copy(),
            "max_concurrent": self.max_concurrent_experiments,
        }

    def get_experiment_status(self, experiment_id: str) -> dict[str, Any] | None:
        """獲取實驗狀態"""
        # 搜索各個隊列
        experiment = None

        if experiment_id in self.running_experiments:
            experiment = self.running_experiments[experiment_id]
        elif experiment_id in self.completed_experiments:
            experiment = self.completed_experiments[experiment_id]
        elif experiment_id in self.failed_experiments:
            experiment = self.failed_experiments[experiment_id]
        else:
            for exp in self.pending_queue:
                if exp.experiment_id == experiment_id:
                    experiment = exp
                    break

        if experiment:
            return {
                "experiment_id": experiment.experiment_id,
                "status": experiment.status.value,
                "priority": experiment.priority,
                "created_at": experiment.created_at.isoformat(),
                "scheduled_at": experiment.scheduled_at.isoformat()
                if experiment.scheduled_at
                else None,
                "started_at": experiment.started_at.isoformat() if experiment.started_at else None,
                "completed_at": experiment.completed_at.isoformat()
                if experiment.completed_at
                else None,
                "assigned_resources": experiment.assigned_resources,
                "retry_count": experiment.retry_count,
            }

        return None
