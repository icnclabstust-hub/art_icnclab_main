#!/usr/bin/env python3
"""
RAG Agent基礎類別
所有RAG實驗Agent的共同父類
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any

import numpy as np

from agents.core.base_agent import AgentCapability, AgentMessage, BaseAgent, MessageType


class RAGExperimentResult:
    """RAG實驗結果數據結構"""

    def __init__(self, experiment_id: str, rag_framework: str):
        self.experiment_id = experiment_id
        self.rag_framework = rag_framework
        self.start_time = datetime.now()
        self.end_time = None
        self.status = "running"

        # 性能指標
        self.retrieval_metrics = {}
        self.generation_metrics = {}
        self.latency_metrics = {}
        self.resource_metrics = {}

        # 實驗數據
        self.queries_processed = 0
        self.successful_retrievals = 0
        self.failed_retrievals = 0
        self.generated_answers = 0

        # 詳細結果
        self.query_results = []
        self.error_log = []

    def add_query_result(
        self,
        query: str,
        retrieved_docs: list[dict],
        generated_answer: str,
        metrics: dict[str, float],
    ):
        """添加查詢結果"""
        result = {
            "query": query,
            "retrieved_docs": len(retrieved_docs),
            "answer": generated_answer,
            "metrics": metrics,
            "timestamp": datetime.now(),
        }
        self.query_results.append(result)
        self.queries_processed += 1

        if retrieved_docs:
            self.successful_retrievals += 1
        else:
            self.failed_retrievals += 1

        if generated_answer:
            self.generated_answers += 1

    def add_error(self, error: str, context: dict[str, Any] = None):
        """添加錯誤記錄"""
        error_entry = {"error": error, "context": context or {}, "timestamp": datetime.now()}
        self.error_log.append(error_entry)

    def finalize(self):
        """完成實驗，計算最終指標"""
        self.end_time = datetime.now()
        self.status = "completed"

        # 計算平均指標
        if self.queries_processed > 0:
            self.retrieval_metrics["success_rate"] = (
                self.successful_retrievals / self.queries_processed
            )
            self.generation_metrics["success_rate"] = (
                self.generated_answers / self.queries_processed
            )

            if self.query_results:
                avg_retrieval_time = np.mean(
                    [r["metrics"].get("retrieval_time", 0) for r in self.query_results]
                )
                avg_generation_time = np.mean(
                    [r["metrics"].get("generation_time", 0) for r in self.query_results]
                )

                self.latency_metrics["avg_retrieval_time"] = avg_retrieval_time
                self.latency_metrics["avg_generation_time"] = avg_generation_time
                self.latency_metrics["avg_total_time"] = avg_retrieval_time + avg_generation_time

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式"""
        return {
            "experiment_id": self.experiment_id,
            "rag_framework": self.rag_framework,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "retrieval_metrics": self.retrieval_metrics,
            "generation_metrics": self.generation_metrics,
            "latency_metrics": self.latency_metrics,
            "resource_metrics": self.resource_metrics,
            "queries_processed": self.queries_processed,
            "successful_retrievals": self.successful_retrievals,
            "failed_retrievals": self.failed_retrievals,
            "generated_answers": self.generated_answers,
            "query_results_count": len(self.query_results),
            "errors_count": len(self.error_log),
        }


class BaseRAGAgent(BaseAgent):
    """
    RAG Agent基礎類別
    提供所有RAG實驗Agent的通用功能
    """

    def __init__(self, agent_id: str, name: str, rag_framework: str, description: str = ""):
        super().__init__(agent_id, name, description)

        self.rag_framework = rag_framework

        # RAG組件
        self.vector_stores = {}
        self.embedders = {}
        self.llm_clients = {}
        self.retrievers = {}
        self.generators = {}

        # 實驗管理
        self.active_experiments: dict[str, RAGExperimentResult] = {}
        self.experiment_configs: dict[str, dict[str, Any]] = {}

        # 性能監控
        self.performance_tracker = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "avg_response_time": 0.0,
            "last_update": datetime.now(),
        }

        # 配置參數
        self.default_config = {
            "max_retrieved_docs": 5,
            "max_tokens": 2048,
            "temperature": 0.1,
            "timeout": 30.0,
        }

    async def _initialize(self):
        """初始化RAG Agent"""
        # 註冊消息處理器
        self.register_message_handler(MessageType.TASK_REQUEST, self._handle_experiment_request)

        # 初始化RAG組件
        await self._initialize_rag_components()

        # 載入預設配置
        await self._load_default_configurations()

    async def _initialize_rag_components(self):
        """初始化RAG組件 - 子類實現"""
        pass

    async def _load_default_configurations(self):
        """載入默認配置"""
        # 可以從文件或環境變數載入
        pass

    async def _register_capabilities(self) -> list[AgentCapability]:
        """註冊RAG Agent基礎能力"""
        return [
            AgentCapability(
                name="document_retrieval",
                description="文檔檢索和相關性排序",
                input_types=["query", "context"],
                output_types=["retrieved_documents"],
                resource_requirements={"cpu": 1, "memory": "1GB"},
                estimated_time=5.0,
            ),
            AgentCapability(
                name="answer_generation",
                description="基於檢索文檔生成答案",
                input_types=["query", "retrieved_documents"],
                output_types=["generated_answer"],
                resource_requirements={"cpu": 2, "memory": "2GB"},
                estimated_time=10.0,
            ),
            AgentCapability(
                name="rag_experiment_execution",
                description="執行完整RAG實驗流程",
                input_types=["experiment_config"],
                output_types=["experiment_results"],
                resource_requirements={"cpu": 2, "memory": "4GB"},
                estimated_time=300.0,
            ),
        ]

    async def _start(self):
        """啟動RAG Agent"""
        # 啟動性能監控任務
        asyncio.create_task(self._performance_monitoring_loop())

        # 驗證組件連通性
        await self._verify_component_connectivity()

    async def _stop(self):
        """停止RAG Agent"""
        # 完成活躍實驗
        for experiment_id in list(self.active_experiments.keys()):
            await self.finalize_experiment(experiment_id)

    async def _execute_task(self, task_id: str, task_data: dict[str, Any]) -> dict[str, Any]:
        """執行RAG任務"""
        task_type = task_data.get("type", task_data.get("action"))

        if task_type == "execute_experiment":
            return await self.execute_rag_experiment(
                task_data["experiment_id"], task_data["experiment_config"]
            )
        elif task_type == "single_query":
            return await self.process_single_query(task_data["query"], task_data.get("config", {}))
        elif task_type == "batch_queries":
            return await self.process_batch_queries(
                task_data["queries"], task_data.get("config", {})
            )
        else:
            raise ValueError(f"未知任務類型: {task_type}")

    # 核心RAG方法
    async def process_single_query(
        self, query: str, config: dict[str, Any] = None
    ) -> dict[str, Any]:
        """處理單個查詢"""
        start_time = datetime.now()

        try:
            # 合併配置
            effective_config = {**self.default_config, **(config or {})}

            # 執行檢索
            retrieved_docs = await self.retrieve_documents(query, effective_config)
            retrieval_time = (datetime.now() - start_time).total_seconds()

            # 生成答案
            generation_start = datetime.now()
            generated_answer = await self.generate_answer(query, retrieved_docs, effective_config)
            generation_time = (datetime.now() - generation_start).total_seconds()

            # 計算總時間
            total_time = (datetime.now() - start_time).total_seconds()

            # 更新性能統計
            self.performance_tracker["total_queries"] += 1
            if generated_answer:
                self.performance_tracker["successful_queries"] += 1
            else:
                self.performance_tracker["failed_queries"] += 1

            # 更新平均響應時間
            total_queries = self.performance_tracker["total_queries"]
            current_avg = self.performance_tracker["avg_response_time"]
            self.performance_tracker["avg_response_time"] = (
                current_avg * (total_queries - 1) + total_time
            ) / total_queries

            return {
                "query": query,
                "retrieved_documents": retrieved_docs,
                "generated_answer": generated_answer,
                "metrics": {
                    "retrieval_time": retrieval_time,
                    "generation_time": generation_time,
                    "total_time": total_time,
                    "retrieved_count": len(retrieved_docs),
                },
                "success": bool(generated_answer),
            }

        except Exception as e:
            self.logger.error(f"查詢處理失敗: {e}")
            self.performance_tracker["failed_queries"] += 1
            raise

    async def retrieve_documents(self, query: str, config: dict[str, Any]) -> list[dict[str, Any]]:
        """檢索相關文檔 - 由子類實現"""
        raise NotImplementedError("子類必須實現retrieve_documents方法")

    async def generate_answer(
        self, query: str, retrieved_docs: list[dict[str, Any]], config: dict[str, Any]
    ) -> str:
        """生成答案 - 由子類實現"""
        raise NotImplementedError("子類必須實現generate_answer方法")

    # 實驗管理方法
    async def execute_rag_experiment(
        self, experiment_id: str, experiment_config: dict[str, Any]
    ) -> dict[str, Any]:
        """執行RAG實驗"""
        try:
            # 創建實驗結果對象
            experiment_result = RAGExperimentResult(experiment_id, self.rag_framework)
            self.active_experiments[experiment_id] = experiment_result
            self.experiment_configs[experiment_id] = experiment_config

            # 獲取測試查詢
            test_queries = experiment_config.get("test_queries", [])
            if not test_queries:
                # 從配置文件載入默認測試查詢
                test_queries = await self._load_test_queries(experiment_config)

            self.logger.info(f"開始執行實驗 {experiment_id}，包含 {len(test_queries)} 個查詢")

            # 逐個處理查詢
            for i, query in enumerate(test_queries):
                try:
                    # 處理查詢
                    result = await self.process_single_query(query, experiment_config)

                    # 記錄結果
                    experiment_result.add_query_result(
                        query,
                        result["retrieved_documents"],
                        result["generated_answer"],
                        result["metrics"],
                    )

                    # 進度更新
                    progress = ((i + 1) / len(test_queries)) * 100
                    await self._report_experiment_progress(experiment_id, progress)

                except Exception as e:
                    experiment_result.add_error(f"查詢處理失敗: {str(e)}", {"query": query})
                    self.logger.error(f"實驗 {experiment_id} 查詢失敗: {e}")

            # 完成實驗
            experiment_result.finalize()

            # 生成實驗報告
            report = await self._generate_experiment_report(experiment_result)

            self.logger.info(f"實驗 {experiment_id} 完成")

            return {
                "experiment_id": experiment_id,
                "status": "completed",
                "results": experiment_result.to_dict(),
                "report": report,
            }

        except Exception as e:
            self.logger.error(f"實驗執行失敗 {experiment_id}: {e}")
            if experiment_id in self.active_experiments:
                self.active_experiments[experiment_id].add_error(f"實驗執行失敗: {str(e)}")
            raise

    async def finalize_experiment(self, experiment_id: str):
        """完成實驗"""
        if experiment_id in self.active_experiments:
            experiment_result = self.active_experiments[experiment_id]
            experiment_result.finalize()

            # 清理資源
            del self.active_experiments[experiment_id]
            if experiment_id in self.experiment_configs:
                del self.experiment_configs[experiment_id]

    # 消息處理
    async def _handle_experiment_request(self, message: AgentMessage):
        """處理實驗請求"""
        try:
            payload = message.payload
            action = payload.get("action")

            if action == "execute_experiment":
                result = await self.execute_rag_experiment(
                    payload["experiment_id"], payload["experiment_config"]
                )

                # 發送結果給Master Agent
                response = AgentMessage(
                    message_id=str(uuid.uuid4()),
                    sender_id=self.agent_id,
                    receiver_id=message.sender_id,
                    message_type=MessageType.TASK_RESPONSE,
                    payload={"experiment_results": result},
                    timestamp=datetime.now(),
                    correlation_id=message.correlation_id,
                )
                await self.send_message(response)

            elif action == "stop_experiment_tasks":
                experiment_id = payload.get("experiment_id")
                if experiment_id and experiment_id in self.active_experiments:
                    await self.finalize_experiment(experiment_id)

        except Exception as e:
            self.logger.error(f"處理實驗請求失敗: {e}")

    # 輔助方法
    async def _load_test_queries(self, config: dict[str, Any]) -> list[str]:
        """載入測試查詢"""
        # 默認藝術史測試查詢
        default_queries = [
            "找出文藝復興時期的著名肖像畫",
            "有哪些表現情感的現代藝術作品",
            "羅浮宮收藏的經典畫作有哪些",
            "印象派的主要特徵是什麼",
            "達文西的藝術風格特點",
        ]

        # 從配置或文件載入更多查詢
        query_file = config.get("query_file")
        if query_file:
            try:
                with open(query_file, encoding="utf-8") as f:
                    file_queries = json.load(f)
                    return file_queries.get("queries", default_queries)
            except Exception as e:
                self.logger.warning(f"載入查詢文件失敗，使用默認查詢: {e}")

        return default_queries

    async def _report_experiment_progress(self, experiment_id: str, progress: float):
        """報告實驗進度"""
        # 可以發送進度更新給Master Agent
        self.logger.debug(f"實驗 {experiment_id} 進度: {progress:.1f}%")

    async def _generate_experiment_report(
        self, experiment_result: RAGExperimentResult
    ) -> dict[str, Any]:
        """生成實驗報告"""
        return {
            "experiment_summary": {
                "framework": experiment_result.rag_framework,
                "duration": (
                    experiment_result.end_time - experiment_result.start_time
                ).total_seconds(),
                "queries_processed": experiment_result.queries_processed,
                "success_rate": experiment_result.retrieval_metrics.get("success_rate", 0),
            },
            "performance_metrics": {
                "retrieval": experiment_result.retrieval_metrics,
                "generation": experiment_result.generation_metrics,
                "latency": experiment_result.latency_metrics,
            },
            "error_analysis": {
                "total_errors": len(experiment_result.error_log),
                "error_types": self._analyze_error_types(experiment_result.error_log),
            },
            "recommendations": await self._generate_recommendations(experiment_result),
        }

    def _analyze_error_types(self, error_log: list[dict[str, Any]]) -> dict[str, int]:
        """分析錯誤類型"""
        error_types = {}
        for error in error_log:
            error_type = "unknown"
            if "connection" in error["error"].lower():
                error_type = "connection_error"
            elif "timeout" in error["error"].lower():
                error_type = "timeout_error"
            elif "parsing" in error["error"].lower():
                error_type = "parsing_error"

            error_types[error_type] = error_types.get(error_type, 0) + 1

        return error_types

    async def _generate_recommendations(self, experiment_result: RAGExperimentResult) -> list[str]:
        """生成改進建議"""
        recommendations = []

        success_rate = experiment_result.retrieval_metrics.get("success_rate", 0)
        if success_rate < 0.8:
            recommendations.append("考慮調整檢索參數以提高成功率")

        avg_time = experiment_result.latency_metrics.get("avg_total_time", 0)
        if avg_time > 10:
            recommendations.append("優化檢索和生成速度")

        if len(experiment_result.error_log) > 0:
            recommendations.append("檢查並修復錯誤處理邏輯")

        return recommendations

    async def _verify_component_connectivity(self):
        """驗證組件連通性"""
        # 檢查各個組件是否正常工作
        pass

    async def _performance_monitoring_loop(self):
        """性能監控循環"""
        while self.status != "stopped":
            try:
                # 更新性能指標
                self.performance_tracker["last_update"] = datetime.now()

                # 記錄性能指標
                self.logger.debug(f"性能統計: {self.performance_tracker}")

                await asyncio.sleep(60)  # 每分鐘更新一次

            except Exception as e:
                self.logger.error(f"性能監控錯誤: {e}")

    def get_performance_metrics(self) -> dict[str, Any]:
        """獲取性能指標"""
        return {
            "agent_id": self.agent_id,
            "rag_framework": self.rag_framework,
            "performance": self.performance_tracker.copy(),
            "active_experiments": list(self.active_experiments.keys()),
            "components_status": self._check_components_status(),
        }

    def _check_components_status(self) -> dict[str, str]:
        """檢查組件狀態"""
        return {
            "vector_stores": "connected" if self.vector_stores else "not_configured",
            "llm_clients": "connected" if self.llm_clients else "not_configured",
            "embedders": "connected" if self.embedders else "not_configured",
        }
