#!/usr/bin/env python3
"""
MCP工具註冊和發現系統
負責管理所有MCP工具的註冊、發現和代理功能
"""

import asyncio
import logging
import socket
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import aiohttp
import psutil


class MCPToolType(Enum):
    """MCP工具類型"""

    AI_LLM = "ai_llm"
    MULTIMODAL = "multimodal"
    VECTOR_DB = "vector_db"
    GRAPH_DB = "graph_db"
    WEB_SCRAPING = "web_scraping"
    EXPERIMENT = "experiment"
    MONITORING = "monitoring"
    DOCUMENT = "document"


class MCPToolStatus(Enum):
    """MCP工具狀態"""

    DISCOVERED = "discovered"
    REGISTERED = "registered"
    CONNECTED = "connected"
    ACTIVE = "active"
    ERROR = "error"
    UNAVAILABLE = "unavailable"


@dataclass
class MCPToolSpec:
    """MCP工具規格"""

    name: str
    tool_type: MCPToolType
    description: str
    version: str
    endpoint: str | None = None
    port: int | None = None
    docker_image: str | None = None
    docker_compose_service: str | None = None
    capabilities: list[str] = None
    resource_requirements: dict[str, Any] = None
    dependencies: list[str] = None
    config: dict[str, Any] = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []
        if self.resource_requirements is None:
            self.resource_requirements = {"cpu": 1, "memory": "1GB"}
        if self.dependencies is None:
            self.dependencies = []
        if self.config is None:
            self.config = {}


@dataclass
class MCPToolInstance:
    """MCP工具實例"""

    spec: MCPToolSpec
    status: MCPToolStatus
    assigned_agent: str | None = None
    endpoint_url: str | None = None
    process_id: int | None = None
    docker_container_id: str | None = None
    health_check_url: str | None = None
    last_health_check: datetime | None = None
    metrics: dict[str, Any] = None

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {
                "requests_count": 0,
                "success_count": 0,
                "error_count": 0,
                "avg_response_time": 0.0,
                "last_request": None,
            }


class MCPToolRegistry:
    """
    MCP工具註冊表
    管理所有MCP工具的註冊、發現、健康檢查和代理功能
    """

    def __init__(self):
        self.logger = logging.getLogger("mcp_tool_registry")

        # 工具註冊表
        self.tool_specs: dict[str, MCPToolSpec] = {}
        self.tool_instances: dict[str, MCPToolInstance] = {}
        self.tool_categories: dict[MCPToolType, list[str]] = {}

        # 代理和路由
        self.tool_proxies: dict[str, Callable] = {}
        self.agent_tool_mapping: dict[str, list[str]] = {}

        # 健康檢查
        self.health_check_tasks: dict[str, asyncio.Task] = {}
        self.health_check_interval = 30  # 秒

        # 統計和監控
        self.registry_stats = {
            "total_tools": 0,
            "active_tools": 0,
            "error_tools": 0,
            "total_requests": 0,
            "last_updated": datetime.now(),
        }

        self.logger.info("MCP工具註冊表初始化完成")

    async def register_core_tools(self):
        """註冊核心MCP工具"""
        core_tools = self._get_core_tool_specs()

        for tool_spec in core_tools:
            await self.register_tool(tool_spec)

        self.logger.info(f"註冊了 {len(core_tools)} 個核心MCP工具")

    def _get_core_tool_specs(self) -> list[MCPToolSpec]:
        """獲取核心工具規格"""
        return [
            # AI/LLM工具
            MCPToolSpec(
                name="openai",
                tool_type=MCPToolType.AI_LLM,
                description="OpenAI GPT系列模型API",
                version="1.0.0",
                port=8001,
                capabilities=["text_generation", "embeddings", "vision"],
                config={
                    "api_key_required": True,
                    "models": ["gpt-4", "gpt-3.5-turbo", "text-embedding-ada-002"],
                },
            ),
            MCPToolSpec(
                name="anthropic",
                tool_type=MCPToolType.AI_LLM,
                description="Anthropic Claude系列模型",
                version="1.0.0",
                port=8002,
                capabilities=["text_generation", "document_analysis"],
                config={
                    "api_key_required": True,
                    "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
                },
            ),
            MCPToolSpec(
                name="ollama",
                tool_type=MCPToolType.AI_LLM,
                description="本地開源LLM部署",
                version="1.0.0",
                port=11434,
                capabilities=["text_generation", "local_inference"],
                config={"local_deployment": True, "models": ["llama2", "vicuna", "chatglm"]},
            ),
            # 多模態處理工具
            MCPToolSpec(
                name="clip",
                tool_type=MCPToolType.MULTIMODAL,
                description="CLIP視覺-語言模型",
                version="1.0.0",
                port=8010,
                capabilities=["image_understanding", "text_image_matching", "visual_search"],
                resource_requirements={"cpu": 2, "memory": "4GB", "gpu": "optional"},
            ),
            MCPToolSpec(
                name="whisper",
                tool_type=MCPToolType.MULTIMODAL,
                description="Whisper語音識別模型",
                version="1.0.0",
                port=8011,
                capabilities=["speech_recognition", "audio_transcription", "multilingual"],
                resource_requirements={"cpu": 2, "memory": "2GB"},
            ),
            MCPToolSpec(
                name="blip",
                tool_type=MCPToolType.MULTIMODAL,
                description="BLIP圖像標註與問答",
                version="1.0.0",
                port=8012,
                capabilities=["image_captioning", "visual_qa", "image_description"],
                resource_requirements={"cpu": 2, "memory": "4GB", "gpu": "recommended"},
            ),
            # 向量資料庫工具
            MCPToolSpec(
                name="chromadb",
                tool_type=MCPToolType.VECTOR_DB,
                description="ChromaDB向量資料庫",
                version="1.0.0",
                port=8020,
                capabilities=["vector_storage", "similarity_search", "collections"],
                config={"persistent": True, "collection_limit": 100},
            ),
            MCPToolSpec(
                name="qdrant",
                tool_type=MCPToolType.VECTOR_DB,
                description="Qdrant向量搜索引擎",
                version="1.0.0",
                port=6333,
                capabilities=["vector_storage", "similarity_search", "filtering", "clustering"],
                resource_requirements={"cpu": 2, "memory": "2GB"},
            ),
            MCPToolSpec(
                name="weaviate",
                tool_type=MCPToolType.VECTOR_DB,
                description="Weaviate多模態向量資料庫",
                version="1.0.0",
                port=8080,
                capabilities=["vector_storage", "graphql_api", "multimodal_search"],
                resource_requirements={"cpu": 2, "memory": "3GB"},
            ),
            # 網路爬取工具
            MCPToolSpec(
                name="playwright",
                tool_type=MCPToolType.WEB_SCRAPING,
                description="Playwright瀏覽器自動化",
                version="1.0.0",
                port=8030,
                capabilities=["web_scraping", "screenshot", "pdf_generation", "dynamic_content"],
                resource_requirements={"cpu": 2, "memory": "2GB"},
            ),
            MCPToolSpec(
                name="scrapy",
                tool_type=MCPToolType.WEB_SCRAPING,
                description="Scrapy專業網路爬蟲",
                version="1.0.0",
                port=8031,
                capabilities=["distributed_crawling", "middleware", "data_pipeline"],
                resource_requirements={"cpu": 1, "memory": "1GB"},
            ),
            # 實驗管理工具
            MCPToolSpec(
                name="mlflow",
                tool_type=MCPToolType.EXPERIMENT,
                description="MLflow實驗追蹤",
                version="1.0.0",
                port=5000,
                capabilities=["experiment_tracking", "model_versioning", "metrics_logging"],
                config={"storage_backend": "postgresql", "artifact_store": "s3"},
            ),
            MCPToolSpec(
                name="wandb",
                tool_type=MCPToolType.EXPERIMENT,
                description="Weights & Biases實驗監控",
                version="1.0.0",
                port=8040,
                capabilities=[
                    "real_time_monitoring",
                    "hyperparameter_optimization",
                    "collaboration",
                ],
                config={"api_key_required": True, "project_required": True},
            ),
            # 監控工具
            MCPToolSpec(
                name="prometheus",
                tool_type=MCPToolType.MONITORING,
                description="Prometheus監控系統",
                version="1.0.0",
                port=9090,
                capabilities=["metrics_collection", "alerting", "time_series_db"],
                resource_requirements={"cpu": 1, "memory": "2GB"},
            ),
            MCPToolSpec(
                name="grafana",
                tool_type=MCPToolType.MONITORING,
                description="Grafana可視化儀表板",
                version="1.0.0",
                port=3000,
                capabilities=["data_visualization", "dashboard", "alerting"],
                dependencies=["prometheus"],
            ),
        ]

    async def register_tool(self, tool_spec: MCPToolSpec) -> bool:
        """註冊單個工具"""
        try:
            # 檢查工具是否已註冊
            if tool_spec.name in self.tool_specs:
                self.logger.warning(f"工具 {tool_spec.name} 已經註冊")
                return False

            # 註冊工具規格
            self.tool_specs[tool_spec.name] = tool_spec

            # 創建工具實例
            instance = MCPToolInstance(spec=tool_spec, status=MCPToolStatus.REGISTERED)
            self.tool_instances[tool_spec.name] = instance

            # 分類管理
            if tool_spec.tool_type not in self.tool_categories:
                self.tool_categories[tool_spec.tool_type] = []
            self.tool_categories[tool_spec.tool_type].append(tool_spec.name)

            # 更新統計
            self.registry_stats["total_tools"] += 1
            self.registry_stats["last_updated"] = datetime.now()

            self.logger.info(f"成功註冊MCP工具: {tool_spec.name} ({tool_spec.tool_type.value})")
            return True

        except Exception as e:
            self.logger.error(f"註冊工具 {tool_spec.name} 時發生錯誤: {str(e)}")
            return False

    async def discover_tools(self) -> list[str]:
        """自動發現可用的MCP工具"""
        discovered_tools = []

        # 檢查Docker服務
        docker_services = await self._discover_docker_services()
        discovered_tools.extend(docker_services)

        # 檢查網絡端口
        network_services = await self._discover_network_services()
        discovered_tools.extend(network_services)

        # 檢查本地進程
        local_services = await self._discover_local_services()
        discovered_tools.extend(local_services)

        self.logger.info(f"發現 {len(discovered_tools)} 個MCP工具服務")
        return discovered_tools

    async def _discover_docker_services(self) -> list[str]:
        """發現Docker服務"""
        discovered = []
        try:
            result = await asyncio.create_subprocess_exec(
                "docker",
                "ps",
                "--format",
                "{{.Names}}:{{.Ports}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                lines = stdout.decode().strip().split("\n")
                for line in lines:
                    if ":" in line:
                        name, ports = line.split(":", 1)
                        discovered.append(f"docker:{name}:{ports}")

        except Exception as e:
            self.logger.warning(f"Docker服務發現失敗: {str(e)}")

        return discovered

    async def _discover_network_services(self) -> list[str]:
        """發現網絡服務"""
        discovered = []
        common_ports = [
            5000,
            6333,
            8080,
            8020,
            9090,
            11434,
        ]  # MLflow, Qdrant, Weaviate, ChromaDB, Prometheus, Ollama

        for port in common_ports:
            if await self._check_port_availability("localhost", port):
                discovered.append(f"network:localhost:{port}")

        return discovered

    async def _discover_local_services(self) -> list[str]:
        """發現本地進程服務"""
        discovered = []
        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                info = proc.info
                if info["cmdline"]:
                    cmdline = " ".join(info["cmdline"])
                    # 檢查是否是已知的MCP服務
                    for tool_name in ["ollama", "chromadb", "qdrant", "mlflow"]:
                        if tool_name in cmdline.lower():
                            discovered.append(f"process:{info['pid']}:{info['name']}")
                            break
        except Exception as e:
            self.logger.warning(f"本地服務發現失敗: {str(e)}")

        return discovered

    async def _check_port_availability(self, host: str, port: int) -> bool:
        """檢查端口是否可用"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False

    async def connect_tool(self, tool_name: str) -> bool:
        """連接到指定工具"""
        if tool_name not in self.tool_instances:
            self.logger.error(f"工具 {tool_name} 未註冊")
            return False

        instance = self.tool_instances[tool_name]
        spec = instance.spec

        try:
            # 構建端點URL
            if spec.endpoint:
                endpoint_url = spec.endpoint
            elif spec.port:
                endpoint_url = f"http://localhost:{spec.port}"
            else:
                self.logger.error(f"工具 {tool_name} 缺少端點配置")
                return False

            instance.endpoint_url = endpoint_url

            # 健康檢查
            if await self._health_check(instance):
                instance.status = MCPToolStatus.CONNECTED
                self.logger.info(f"成功連接到工具: {tool_name} ({endpoint_url})")

                # 啟動定期健康檢查
                await self._start_health_monitoring(tool_name)

                return True
            else:
                instance.status = MCPToolStatus.ERROR
                self.logger.error(f"連接工具 {tool_name} 健康檢查失敗")
                return False

        except Exception as e:
            instance.status = MCPToolStatus.ERROR
            self.logger.error(f"連接工具 {tool_name} 時發生錯誤: {str(e)}")
            return False

    async def _health_check(self, instance: MCPToolInstance) -> bool:
        """執行健康檢查"""
        try:
            if not instance.endpoint_url:
                return False

            # 嘗試連接健康檢查端點
            health_url = f"{instance.endpoint_url}/health"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    health_url, timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        instance.last_health_check = datetime.now()
                        return True
                    else:
                        return False

        except Exception as e:
            self.logger.debug(f"健康檢查失敗 {instance.spec.name}: {str(e)}")
            return False

    async def _start_health_monitoring(self, tool_name: str):
        """啟動健康監控任務"""
        if tool_name in self.health_check_tasks:
            # 取消舊的監控任務
            self.health_check_tasks[tool_name].cancel()

        # 創建新的監控任務
        task = asyncio.create_task(self._health_monitor_loop(tool_name))
        self.health_check_tasks[tool_name] = task

    async def _health_monitor_loop(self, tool_name: str):
        """健康監控循環"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)

                if tool_name in self.tool_instances:
                    instance = self.tool_instances[tool_name]
                    if await self._health_check(instance):
                        if instance.status != MCPToolStatus.ACTIVE:
                            instance.status = MCPToolStatus.ACTIVE
                            self.registry_stats["active_tools"] += 1
                    else:
                        if instance.status == MCPToolStatus.ACTIVE:
                            self.registry_stats["active_tools"] -= 1
                        instance.status = MCPToolStatus.ERROR
                        self.registry_stats["error_tools"] += 1

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"健康監控錯誤 {tool_name}: {str(e)}")

    async def assign_tool_to_agent(self, tool_name: str, agent_id: str) -> bool:
        """將工具分配給Agent"""
        if tool_name not in self.tool_instances:
            self.logger.error(f"工具 {tool_name} 未註冊")
            return False

        instance = self.tool_instances[tool_name]
        instance.assigned_agent = agent_id

        # 更新Agent-工具映射
        if agent_id not in self.agent_tool_mapping:
            self.agent_tool_mapping[agent_id] = []
        self.agent_tool_mapping[agent_id].append(tool_name)

        self.logger.info(f"工具 {tool_name} 已分配給Agent {agent_id}")
        return True

    def get_tools_by_type(self, tool_type: MCPToolType) -> list[str]:
        """根據類型獲取工具列表"""
        return self.tool_categories.get(tool_type, [])

    def get_tools_by_agent(self, agent_id: str) -> list[str]:
        """獲取分配給特定Agent的工具"""
        return self.agent_tool_mapping.get(agent_id, [])

    def get_tool_status(self, tool_name: str) -> MCPToolStatus | None:
        """獲取工具狀態"""
        if tool_name in self.tool_instances:
            return self.tool_instances[tool_name].status
        return None

    def get_registry_stats(self) -> dict[str, Any]:
        """獲取註冊表統計信息"""
        # 更新實時統計
        active_count = sum(
            1
            for instance in self.tool_instances.values()
            if instance.status == MCPToolStatus.ACTIVE
        )
        error_count = sum(
            1 for instance in self.tool_instances.values() if instance.status == MCPToolStatus.ERROR
        )

        self.registry_stats.update(
            {
                "active_tools": active_count,
                "error_tools": error_count,
                "last_updated": datetime.now(),
            }
        )

        return self.registry_stats.copy()

    async def shutdown(self):
        """關閉MCP工具註冊表"""
        self.logger.info("正在關閉MCP工具註冊表...")

        # 取消所有健康檢查任務
        for task in self.health_check_tasks.values():
            task.cancel()

        # 等待任務完成
        if self.health_check_tasks:
            await asyncio.gather(*self.health_check_tasks.values(), return_exceptions=True)

        self.logger.info("MCP工具註冊表已關閉")


# 全局單例實例
_registry_instance = None


def get_mcp_registry() -> MCPToolRegistry:
    """獲取MCP工具註冊表單例實例"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = MCPToolRegistry()
    return _registry_instance
