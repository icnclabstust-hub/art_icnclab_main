#!/usr/bin/env python3
"""
Master Agent - 實驗協調者
負責整個多模態RAG實驗系統的協調和管理
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any

from monitoring.agent_monitor import AgentMonitor
from scheduling.experiment_scheduler import ExperimentScheduler

from .base_agent import AgentCapability, AgentMessage, BaseAgent, MessageType


class MasterAgent(BaseAgent):
    """
    Master Agent - 系統協調者
    負責實驗規劃、Agent管理、資源調度等核心功能
    """

    def __init__(self):
        super().__init__(
            agent_id="master_agent", name="實驗協調者", description="多模態RAG實驗系統的主控制器"
        )

        # 子系統組件
        self.experiment_scheduler = None
        self.agent_monitor = None

        # Agent管理
        self.managed_agents: dict[str, dict[str, Any]] = {}
        self.agent_assignments: dict[str, list[str]] = {}  # agent_id -> task_ids

        # 實驗管理
        self.active_experiments: dict[str, dict[str, Any]] = {}
        self.experiment_queue: list[dict[str, Any]] = []
        self.experiment_history: list[dict[str, Any]] = []

        # 資源管理
        self.resource_pool = {
            "vector_databases": ["chromadb", "qdrant", "weaviate"],
            "llm_providers": ["openai", "anthropic", "ollama", "huggingface"],
            "processing_units": {"cpu_cores": 8, "memory_gb": 32, "gpu_count": 1},
        }

        # 配置25組合實驗矩陣
        self.experiment_matrix = {
            "rag_frameworks": [
                "advanced_rag",
                "vector_rag",
                "multilingual_rag",
                "graph_rag",
                "self_reflection_rag",
            ],
            "llm_models": ["gpt4", "claude3", "gpt_oss", "gemma", "specialized"],
        }

        self.logger.info("Master Agent 初始化完成")

    async def _initialize(self):
        """初始化Master Agent"""
        # 初始化調度器
        self.experiment_scheduler = ExperimentScheduler()
        await self.experiment_scheduler.initialize()

        # 初始化監控器
        self.agent_monitor = AgentMonitor()
        await self.agent_monitor.initialize()

        # 註冊消息處理器
        self.register_message_handler(MessageType.TASK_REQUEST, self._handle_task_request)
        self.register_message_handler(MessageType.TASK_RESPONSE, self._handle_task_response)
        self.register_message_handler(
            MessageType.COORDINATION_REQUEST, self._handle_coordination_request
        )

    async def _register_capabilities(self) -> list[AgentCapability]:
        """註冊Master Agent的能力"""
        return [
            AgentCapability(
                name="experiment_planning",
                description="實驗計劃制定和調度",
                input_types=["experiment_config"],
                output_types=["execution_plan"],
                resource_requirements={"cpu": 1, "memory": "1GB"},
                estimated_time=30.0,
            ),
            AgentCapability(
                name="agent_coordination",
                description="Agent間協調和任務分發",
                input_types=["coordination_request"],
                output_types=["task_assignment"],
                resource_requirements={"cpu": 0.5, "memory": "512MB"},
                estimated_time=5.0,
            ),
            AgentCapability(
                name="resource_management",
                description="系統資源分配和監控",
                input_types=["resource_request"],
                output_types=["resource_allocation"],
                resource_requirements={"cpu": 0.5, "memory": "256MB"},
                estimated_time=2.0,
            ),
            AgentCapability(
                name="result_aggregation",
                description="實驗結果聚合和分析",
                input_types=["experiment_results"],
                output_types=["analysis_report"],
                resource_requirements={"cpu": 2, "memory": "2GB"},
                estimated_time=60.0,
            ),
        ]

    async def _start(self):
        """啟動Master Agent"""
        # 啟動監控任務
        asyncio.create_task(self._monitor_system_health())
        asyncio.create_task(self._process_experiment_queue())
        asyncio.create_task(self._cleanup_completed_experiments())

        self.logger.info("Master Agent 所有子系統已啟動")

    async def _stop(self):
        """停止Master Agent"""
        # 停止所有活躍實驗
        for exp_id in list(self.active_experiments.keys()):
            await self.stop_experiment(exp_id)

        # 停止所有子Agent
        for agent_id in list(self.managed_agents.keys()):
            await self.stop_agent(agent_id)

    async def _execute_task(self, task_id: str, task_data: dict[str, Any]) -> dict[str, Any]:
        """執行Master Agent任務"""
        task_type = task_data.get("type")

        if task_type == "plan_experiment_campaign":
            return await self.plan_experiment_campaign(task_data["config"])
        elif task_type == "start_experiment":
            return await self.start_experiment(task_data["experiment_config"])
        elif task_type == "coordinate_agents":
            return await self.coordinate_agents(task_data["coordination_request"])
        elif task_type == "aggregate_results":
            return await self.aggregate_results(task_data["results"])
        else:
            raise ValueError(f"未知任務類型: {task_type}")

    # 實驗管理方法
    async def plan_experiment_campaign(self, config: dict[str, Any]) -> dict[str, Any]:
        """規劃實驗活動"""
        try:
            campaign_id = str(uuid.uuid4())

            # 生成25組合實驗
            experiments = []
            for rag_framework in self.experiment_matrix["rag_frameworks"]:
                for llm_model in self.experiment_matrix["llm_models"]:
                    exp_config = {
                        "experiment_id": str(uuid.uuid4()),
                        "rag_framework": rag_framework,
                        "llm_model": llm_model,
                        "config": config.get("experiment_params", {}),
                        "priority": self._calculate_experiment_priority(rag_framework, llm_model),
                        "estimated_duration": self._estimate_experiment_duration(
                            rag_framework, llm_model
                        ),
                    }
                    experiments.append(exp_config)

            # 使用調度器優化執行順序
            execution_plan = await self.experiment_scheduler.schedule_experiments(experiments)

            # 保存活動計劃
            campaign = {
                "campaign_id": campaign_id,
                "total_experiments": len(experiments),
                "execution_plan": execution_plan,
                "created_at": datetime.now(),
                "status": "planned",
                "estimated_completion": datetime.now()
                + timedelta(seconds=sum(exp["estimated_duration"] for exp in experiments)),
            }

            self.logger.info(f"實驗活動 {campaign_id} 規劃完成，包含 {len(experiments)} 個實驗")

            return {"campaign_id": campaign_id, "campaign": campaign, "experiments": experiments}

        except Exception as e:
            self.logger.error(f"實驗活動規劃失敗: {e}")
            raise

    async def start_experiment(self, experiment_config: dict[str, Any]) -> dict[str, Any]:
        """啟動單個實驗"""
        experiment_id = experiment_config["experiment_id"]

        try:
            # 分配資源
            resources = await self._allocate_experiment_resources(experiment_config)

            # 選擇和分配Agent
            assigned_agents = await self._assign_experiment_agents(experiment_config)

            # 創建實驗記錄
            experiment = {
                "experiment_id": experiment_id,
                "config": experiment_config,
                "assigned_agents": assigned_agents,
                "allocated_resources": resources,
                "status": "running",
                "start_time": datetime.now(),
                "progress": 0,
                "results": {},
            }

            self.active_experiments[experiment_id] = experiment

            # 發送任務給相關Agent
            await self._dispatch_experiment_tasks(experiment)

            self.logger.info(f"實驗 {experiment_id} 已啟動")

            return {
                "experiment_id": experiment_id,
                "status": "started",
                "assigned_agents": assigned_agents,
            }

        except Exception as e:
            self.logger.error(f"啟動實驗 {experiment_id} 失敗: {e}")
            raise

    async def stop_experiment(self, experiment_id: str) -> dict[str, Any]:
        """停止實驗"""
        if experiment_id not in self.active_experiments:
            raise ValueError(f"實驗 {experiment_id} 不存在")

        experiment = self.active_experiments[experiment_id]

        # 通知所有相關Agent停止任務
        for agent_id in experiment["assigned_agents"]:
            stop_message = AgentMessage(
                message_id=str(uuid.uuid4()),
                sender_id=self.agent_id,
                receiver_id=agent_id,
                message_type=MessageType.TASK_REQUEST,
                payload={"action": "stop_experiment_tasks", "experiment_id": experiment_id},
                timestamp=datetime.now(),
            )
            await self.send_message(stop_message)

        # 更新實驗狀態
        experiment["status"] = "stopped"
        experiment["end_time"] = datetime.now()

        # 移到歷史記錄
        self.experiment_history.append(experiment)
        del self.active_experiments[experiment_id]

        self.logger.info(f"實驗 {experiment_id} 已停止")

        return {"experiment_id": experiment_id, "status": "stopped"}

    # Agent管理方法
    async def register_managed_agent(self, agent_id: str, agent_info: dict[str, Any]):
        """註冊受管理的Agent"""
        self.managed_agents[agent_id] = {
            **agent_info,
            "registered_at": datetime.now(),
            "status": "registered",
            "current_tasks": [],
            "performance_metrics": {},
        }

        # 初始化任務分配列表
        self.agent_assignments[agent_id] = []

        self.logger.info(f"註冊Agent {agent_id}: {agent_info.get('name')}")

    async def start_agent(self, agent_id: str) -> dict[str, Any]:
        """啟動Agent"""
        if agent_id not in self.managed_agents:
            raise ValueError(f"Agent {agent_id} 未註冊")

        # 發送啟動命令
        start_message = AgentMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.agent_id,
            receiver_id=agent_id,
            message_type=MessageType.TASK_REQUEST,
            payload={"action": "start"},
            timestamp=datetime.now(),
        )
        await self.send_message(start_message)

        self.managed_agents[agent_id]["status"] = "starting"

        return {"agent_id": agent_id, "status": "starting"}

    async def stop_agent(self, agent_id: str) -> dict[str, Any]:
        """停止Agent"""
        if agent_id not in self.managed_agents:
            raise ValueError(f"Agent {agent_id} 未註冊")

        # 發送停止命令
        stop_message = AgentMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.agent_id,
            receiver_id=agent_id,
            message_type=MessageType.TASK_REQUEST,
            payload={"action": "stop"},
            timestamp=datetime.now(),
        )
        await self.send_message(stop_message)

        self.managed_agents[agent_id]["status"] = "stopping"

        return {"agent_id": agent_id, "status": "stopping"}

    # 協調方法
    async def coordinate_agents(self, coordination_request: dict[str, Any]) -> dict[str, Any]:
        """協調多個Agent"""
        request_type = coordination_request.get("type")

        if request_type == "resource_allocation":
            return await self._coordinate_resource_allocation(coordination_request)
        elif request_type == "task_distribution":
            return await self._coordinate_task_distribution(coordination_request)
        elif request_type == "result_collection":
            return await self._coordinate_result_collection(coordination_request)
        else:
            raise ValueError(f"未知協調類型: {request_type}")

    async def aggregate_results(self, results: dict[str, Any]) -> dict[str, Any]:
        """聚合實驗結果"""
        try:
            experiment_id = results.get("experiment_id")
            if not experiment_id:
                raise ValueError("缺少實驗ID")

            if experiment_id not in self.active_experiments:
                raise ValueError(f"實驗 {experiment_id} 不存在")

            # 更新實驗結果
            experiment = self.active_experiments[experiment_id]
            experiment["results"].update(results.get("data", {}))
            experiment["progress"] = results.get("progress", experiment["progress"])

            # 檢查是否完成
            if experiment["progress"] >= 100:
                experiment["status"] = "completed"
                experiment["end_time"] = datetime.now()

                # 生成最終報告
                final_report = await self._generate_experiment_report(experiment)
                experiment["final_report"] = final_report

                # 移到歷史記錄
                self.experiment_history.append(experiment)
                del self.active_experiments[experiment_id]

                self.logger.info(f"實驗 {experiment_id} 完成")

            return {
                "experiment_id": experiment_id,
                "status": experiment["status"],
                "progress": experiment["progress"],
            }

        except Exception as e:
            self.logger.error(f"結果聚合失敗: {e}")
            raise

    # 消息處理方法
    async def _handle_task_request(self, message: AgentMessage):
        """處理任務請求"""
        try:
            task_data = message.payload
            result = await self.execute_task(message.message_id, task_data)

            response = AgentMessage(
                message_id=str(uuid.uuid4()),
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                message_type=MessageType.TASK_RESPONSE,
                payload=result,
                timestamp=datetime.now(),
                correlation_id=message.correlation_id,
            )
            await self.send_message(response)

        except Exception as e:
            self.logger.error(f"處理任務請求失敗: {e}")

    async def _handle_task_response(self, message: AgentMessage):
        """處理任務響應"""
        try:
            response_data = message.payload
            agent_id = message.sender_id

            # 更新Agent狀態
            if agent_id in self.managed_agents:
                self.managed_agents[agent_id]["last_response"] = datetime.now()

                # 處理實驗結果
                if "experiment_results" in response_data:
                    await self.aggregate_results(response_data["experiment_results"])

        except Exception as e:
            self.logger.error(f"處理任務響應失敗: {e}")

    async def _handle_coordination_request(self, message: AgentMessage):
        """處理協調請求"""
        try:
            coordination_data = message.payload
            result = await self.coordinate_agents(coordination_data)

            response = AgentMessage(
                message_id=str(uuid.uuid4()),
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                message_type=MessageType.TASK_RESPONSE,
                payload=result,
                timestamp=datetime.now(),
                correlation_id=message.correlation_id,
            )
            await self.send_message(response)

        except Exception as e:
            self.logger.error(f"處理協調請求失敗: {e}")

    # 輔助方法
    def _calculate_experiment_priority(self, rag_framework: str, llm_model: str) -> int:
        """計算實驗優先級"""
        # 基於重要性的簡單優先級計算
        priority_map = {
            "advanced_rag": 1,
            "graph_rag": 2,
            "self_reflection_rag": 3,
            "vector_rag": 4,
            "multilingual_rag": 5,
        }
        return priority_map.get(rag_framework, 5)

    def _estimate_experiment_duration(self, rag_framework: str, llm_model: str) -> float:
        """估算實驗持續時間（秒）"""
        # 基於復雜度的時間估算
        base_time = 600  # 10分鐘基礎時間
        framework_multiplier = {
            "advanced_rag": 2.0,
            "graph_rag": 1.8,
            "self_reflection_rag": 1.5,
            "vector_rag": 1.0,
            "multilingual_rag": 1.3,
        }
        return base_time * framework_multiplier.get(rag_framework, 1.0)

    async def _allocate_experiment_resources(
        self, experiment_config: dict[str, Any]
    ) -> dict[str, Any]:
        """分配實驗資源"""
        # 簡化的資源分配邏輯
        return {
            "vector_db": "qdrant",  # 基於實驗配置選擇
            "cpu_cores": 2,
            "memory_gb": 4,
            "gpu_allocated": False,
        }

    async def _assign_experiment_agents(self, experiment_config: dict[str, Any]) -> list[str]:
        """分配實驗Agent"""
        # 基於實驗類型選擇相應Agent
        rag_framework = experiment_config["rag_framework"]
        agent_mapping = {
            "advanced_rag": "advanced_rag_agent",
            "vector_rag": "vector_rag_agent",
            "graph_rag": "graph_rag_agent",
            "multilingual_rag": "multilingual_rag_agent",
            "self_reflection_rag": "self_reflection_rag_agent",
        }

        assigned_agents = [
            agent_mapping.get(rag_framework, "vector_rag_agent"),
            "data_processing_agent",
            "evaluation_agent",
        ]

        return assigned_agents

    async def _dispatch_experiment_tasks(self, experiment: dict[str, Any]):
        """分發實驗任務"""
        experiment_id = experiment["experiment_id"]

        for agent_id in experiment["assigned_agents"]:
            task_message = AgentMessage(
                message_id=str(uuid.uuid4()),
                sender_id=self.agent_id,
                receiver_id=agent_id,
                message_type=MessageType.TASK_REQUEST,
                payload={
                    "action": "execute_experiment",
                    "experiment_id": experiment_id,
                    "experiment_config": experiment["config"],
                },
                timestamp=datetime.now(),
            )
            await self.send_message(task_message)

    async def _generate_experiment_report(self, experiment: dict[str, Any]) -> dict[str, Any]:
        """生成實驗報告"""
        return {
            "experiment_id": experiment["experiment_id"],
            "summary": "實驗完成",
            "results": experiment["results"],
            "duration": (experiment["end_time"] - experiment["start_time"]).total_seconds(),
            "generated_at": datetime.now(),
        }

    # 監控任務
    async def _monitor_system_health(self):
        """監控系統健康狀況"""
        while self.status != "stopped":
            try:
                # 檢查Agent健康狀況
                await self.agent_monitor.check_all_agents()

                # 更新性能指標
                await self._update_performance_metrics()

                await asyncio.sleep(30)  # 30秒檢查一次

            except Exception as e:
                self.logger.error(f"系統健康監控錯誤: {e}")

    async def _process_experiment_queue(self):
        """處理實驗隊列"""
        while self.status != "stopped":
            try:
                if self.experiment_queue:
                    # 檢查資源是否可用
                    if len(self.active_experiments) < 3:  # 最多同時3個實驗
                        experiment_config = self.experiment_queue.pop(0)
                        await self.start_experiment(experiment_config)

                await asyncio.sleep(10)

            except Exception as e:
                self.logger.error(f"實驗隊列處理錯誤: {e}")

    async def _cleanup_completed_experiments(self):
        """清理已完成的實驗"""
        while self.status != "stopped":
            try:
                # 清理超過24小時的歷史記錄
                cutoff_time = datetime.now() - timedelta(hours=24)
                self.experiment_history = [
                    exp
                    for exp in self.experiment_history
                    if exp.get("end_time", datetime.now()) > cutoff_time
                ]

                await asyncio.sleep(3600)  # 1小時清理一次

            except Exception as e:
                self.logger.error(f"實驗清理錯誤: {e}")

    async def _update_performance_metrics(self):
        """更新性能指標"""
        # 實現性能指標更新邏輯
        pass

    def get_system_status(self) -> dict[str, Any]:
        """獲取系統狀態"""
        return {
            "master_agent": self.get_status(),
            "managed_agents": len(self.managed_agents),
            "active_experiments": len(self.active_experiments),
            "experiment_queue": len(self.experiment_queue),
            "completed_experiments": len(self.experiment_history),
            "resource_utilization": self._calculate_resource_utilization(),
        }

    def _calculate_resource_utilization(self) -> dict[str, float]:
        """計算資源利用率"""
        # 簡化的資源利用率計算
        return {"cpu": 0.0, "memory": 0.0, "gpu": 0.0}
