#!/usr/bin/env python3
"""
MCP Agent集成系統
將MCP工具無縫集成到現有的Agent框架中
"""

import logging
from typing import Any

# 導入現有Agent框架
from agents.core.base_agent import AgentCapability, BaseAgent
from agents.core.master_agent import MasterAgent
from agents.rag.vector_rag_agent import VectorRAGAgent
from mcp.mcp_tool_proxy import ProxyResponse, get_proxy_manager

# 導入MCP組件
from mcp.mcp_tool_registry import MCPToolType, get_mcp_registry


class MCPCapableAgent(BaseAgent):
    """
    支持MCP工具的Agent基類
    擴展BaseAgent以支持MCP工具調用
    """

    def __init__(self, agent_id: str, name: str, description: str):
        super().__init__(agent_id, name, description)

        # MCP相關組件
        self.mcp_registry = get_mcp_registry()
        self.mcp_proxy_manager = get_proxy_manager()

        # 分配的MCP工具
        self.assigned_tools: list[str] = []
        self.tool_capabilities: dict[str, list[str]] = {}

        self.logger.info(f"MCP支持Agent {self.agent_id} 初始化完成")

    async def initialize_mcp_tools(self):
        """初始化MCP工具"""
        try:
            # 根據Agent類型自動分配工具
            await self._auto_assign_tools()

            # 初始化分配的工具
            for tool_name in self.assigned_tools:
                proxy = await self.mcp_proxy_manager.get_proxy(tool_name)
                if proxy:
                    tool_spec = self.mcp_registry.tool_specs[tool_name]
                    self.tool_capabilities[tool_name] = tool_spec.capabilities
                    self.logger.info(f"成功初始化MCP工具: {tool_name}")
                else:
                    self.logger.warning(f"無法初始化MCP工具: {tool_name}")

        except Exception as e:
            self.logger.error(f"初始化MCP工具時發生錯誤: {str(e)}")

    async def _auto_assign_tools(self):
        """根據Agent類型自動分配MCP工具"""
        # 默認實現，子類可以重寫
        pass

    async def call_mcp_tool(
        self, tool_name: str, method: str, params: dict[str, Any] = None, **kwargs
    ) -> ProxyResponse:
        """調用MCP工具"""
        if tool_name not in self.assigned_tools:
            return ProxyResponse(success=False, error=f"工具 {tool_name} 未分配給當前Agent")

        try:
            response = await self.mcp_proxy_manager.execute_tool_request(
                tool_name, method, params, **kwargs
            )

            # 更新性能指標
            self.performance_metrics["tool_calls"] += 1
            if response.success:
                self.performance_metrics["successful_tool_calls"] += 1
            else:
                self.performance_metrics["failed_tool_calls"] += 1

            return response

        except Exception as e:
            self.logger.error(f"調用MCP工具 {tool_name} 時發生錯誤: {str(e)}")
            return ProxyResponse(success=False, error=str(e))

    async def call_multiple_tools(self, requests: list[dict[str, Any]]) -> dict[str, ProxyResponse]:
        """並行調用多個MCP工具"""
        tasks = []
        for req in requests:
            task = self.call_mcp_tool(
                req["tool_name"], req["method"], req.get("params"), **req.get("kwargs", {})
            )
            tasks.append((req["tool_name"], task))

        results = {}
        for tool_name, task in tasks:
            try:
                result = await task
                results[tool_name] = result
            except Exception as e:
                results[tool_name] = ProxyResponse(success=False, error=f"並行調用失敗: {str(e)}")

        return results

    def get_tool_capabilities(self, tool_name: str = None) -> dict[str, list[str]]:
        """獲取工具能力"""
        if tool_name:
            return {tool_name: self.tool_capabilities.get(tool_name, [])}
        return self.tool_capabilities.copy()


class MCPMasterAgent(MasterAgent, MCPCapableAgent):
    """
    支持MCP的Master Agent
    協調MCP工具在整個系統中的使用
    """

    def __init__(self):
        # 先初始化MasterAgent
        MasterAgent.__init__(self)
        # 然後手動添加MCP功能屬性
        self.mcp_registry = get_mcp_registry()
        self.mcp_proxy_manager = get_proxy_manager()
        self.assigned_tools: list[str] = []
        self.tool_capabilities: dict[str, list[str]] = {}

        # 更新agent_id以區分MCP版本
        self.agent_id = "mcp_master_agent"
        self.name = "MCP Master Agent"
        self.description = "支持MCP工具的主協調Agent"

    async def initialize(self):
        """重寫初始化方法"""
        await super().initialize()
        await self.initialize_mcp_tools()

    async def _auto_assign_tools(self):
        """Master Agent自動分配管理和監控工具"""
        management_tools = self.mcp_registry.get_tools_by_type(MCPToolType.MONITORING)
        experiment_tools = self.mcp_registry.get_tools_by_type(MCPToolType.EXPERIMENT)

        self.assigned_tools.extend(management_tools)
        self.assigned_tools.extend(experiment_tools)

        # 將工具分配給自己
        for tool_name in self.assigned_tools:
            await self.mcp_registry.assign_tool_to_agent(tool_name, self.agent_id)

    async def distribute_tools_to_agents(self, agent_tool_mapping: dict[str, list[str]]):
        """將MCP工具分發給子Agent"""
        for agent_id, tool_names in agent_tool_mapping.items():
            for tool_name in tool_names:
                success = await self.mcp_registry.assign_tool_to_agent(tool_name, agent_id)
                if success:
                    self.logger.info(f"工具 {tool_name} 已分配給Agent {agent_id}")

    async def monitor_mcp_tools_health(self) -> dict[str, Any]:
        """監控MCP工具健康狀況"""
        registry_stats = self.mcp_registry.get_registry_stats()
        proxy_stats = self.mcp_proxy_manager.get_proxy_stats()

        health_report = {
            "registry_stats": registry_stats,
            "proxy_stats": proxy_stats,
            "tool_health": {},
        }

        # 檢查每個工具的健康狀況
        for tool_name in self.mcp_registry.tool_instances.keys():
            status = self.mcp_registry.get_tool_status(tool_name)
            health_report["tool_health"][tool_name] = status.value if status else "unknown"

        return health_report


class MCPVectorRAGAgent(VectorRAGAgent, MCPCapableAgent):
    """
    支持MCP的向量RAG Agent
    整合向量資料庫和LLM工具
    """

    def __init__(self):
        # 先初始化VectorRAGAgent
        VectorRAGAgent.__init__(self)
        # 然後手動添加MCP功能屬性
        self.mcp_registry = get_mcp_registry()
        self.mcp_proxy_manager = get_proxy_manager()
        self.assigned_tools: list[str] = []
        self.tool_capabilities: dict[str, list[str]] = {}

        # 更新agent_id以區分MCP版本
        self.agent_id = "mcp_vector_rag_agent"
        self.name = "MCP Vector RAG Agent"
        self.description = "支持MCP工具的向量RAG Agent"

    async def initialize(self):
        """重寫初始化方法"""
        await super().initialize()
        await self.initialize_mcp_tools()

    async def _auto_assign_tools(self):
        """自動分配向量資料庫和LLM工具"""
        vector_db_tools = self.mcp_registry.get_tools_by_type(MCPToolType.VECTOR_DB)
        llm_tools = self.mcp_registry.get_tools_by_type(MCPToolType.AI_LLM)

        self.assigned_tools.extend(vector_db_tools)
        self.assigned_tools.extend(llm_tools)

        # 將工具分配給自己
        for tool_name in self.assigned_tools:
            await self.mcp_registry.assign_tool_to_agent(tool_name, self.agent_id)

    async def mcp_semantic_search(
        self, query: str, vector_db: str = "chromadb", collection: str = "default", top_k: int = 5
    ) -> ProxyResponse:
        """使用MCP工具執行語義搜索"""
        # 首先將查詢轉換為嵌入向量
        embedding_response = await self.call_mcp_tool(
            "openai",  # 使用OpenAI生成嵌入
            "embeddings",
            {"input": query, "model": "text-embedding-ada-002"},
        )

        if not embedding_response.success:
            return embedding_response

        query_vector = embedding_response.data["data"][0]["embedding"]

        # 在向量資料庫中搜索
        search_response = await self.call_mcp_tool(
            vector_db,
            "vectors/search",
            {"collection_name": collection, "query_vector": query_vector, "top_k": top_k},
        )

        return search_response

    async def mcp_generate_answer(
        self, query: str, context_docs: list[str], llm_model: str = "openai"
    ) -> ProxyResponse:
        """使用MCP LLM工具生成答案"""
        # 構建提示詞
        context = "\n".join([f"文檔{i + 1}: {doc}" for i, doc in enumerate(context_docs)])
        messages = [
            {"role": "system", "content": "你是一個專業的藝術史助理，基於提供的文檔回答問題。"},
            {"role": "user", "content": f"基於以下文檔回答問題:\n\n{context}\n\n問題: {query}"},
        ]

        response = await self.call_mcp_tool(
            llm_model, "chat/completions", {"messages": messages, "model": "gpt-4"}
        )

        return response

    async def mcp_rag_pipeline(self, query: str, **kwargs) -> dict[str, Any]:
        """完整的MCP RAG管道"""
        try:
            # 1. 語義搜索
            search_result = await self.mcp_semantic_search(query, **kwargs)
            if not search_result.success:
                return {"success": False, "error": f"搜索失敗: {search_result.error}"}

            # 2. 提取相關文檔
            documents = [match["metadata"]["text"] for match in search_result.data["matches"]]

            # 3. 生成答案
            answer_result = await self.mcp_generate_answer(query, documents)
            if not answer_result.success:
                return {"success": False, "error": f"答案生成失敗: {answer_result.error}"}

            return {
                "success": True,
                "answer": answer_result.data["choices"][0]["message"]["content"],
                "source_documents": documents,
                "search_results": search_result.data,
                "metadata": {
                    "search_time": search_result.execution_time,
                    "generation_time": answer_result.execution_time,
                    "total_time": search_result.execution_time + answer_result.execution_time,
                },
            }

        except Exception as e:
            self.logger.error(f"MCP RAG管道執行失敗: {str(e)}")
            return {"success": False, "error": str(e)}


class MCPMultimodalAgent(BaseAgent):
    """
    多模態處理Agent
    專門處理圖像、音頻等多模態數據
    """

    def __init__(self):
        super().__init__(
            agent_id="mcp_multimodal_agent",
            name="MCP Multimodal Agent",
            description="多模態處理專用Agent",
        )

        # 添加MCP功能屬性
        self.mcp_registry = get_mcp_registry()
        self.mcp_proxy_manager = get_proxy_manager()
        self.assigned_tools: list[str] = []
        self.tool_capabilities: dict[str, list[str]] = {}

    async def _initialize(self):
        """初始化Agent"""
        await self.initialize_mcp_tools()

    async def _start(self):
        """啟動Agent"""
        self.logger.info(f"多模態Agent {self.agent_id} 已啟動")

    async def _stop(self):
        """停止Agent"""
        self.logger.info(f"多模態Agent {self.agent_id} 已停止")

    def _register_capabilities(self):
        """註冊Agent能力"""
        capabilities = [
            AgentCapability(
                name="image_processing",
                description="圖像處理和分析",
                parameters={"supported_formats": ["jpeg", "png", "webp"]},
                output_type="dict",
            ),
            AgentCapability(
                name="audio_processing",
                description="音頻處理和轉錄",
                parameters={"supported_formats": ["wav", "mp3", "flac"]},
                output_type="dict",
            ),
        ]
        return capabilities

    async def _execute_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """執行任務"""
        task_type = task.get("type")

        if task_type == "process_image":
            return await self.process_artwork_image(task.get("image_data"))
        elif task_type == "transcribe_audio":
            return await self.transcribe_audio(task.get("audio_data"))
        else:
            return {"success": False, "error": f"不支持的任務類型: {task_type}"}

    async def _auto_assign_tools(self):
        """自動分配多模態處理工具"""
        multimodal_tools = self.mcp_registry.get_tools_by_type(MCPToolType.MULTIMODAL)
        self.assigned_tools.extend(multimodal_tools)

        # 將工具分配給自己
        for tool_name in self.assigned_tools:
            await self.mcp_registry.assign_tool_to_agent(tool_name, self.agent_id)

    async def initialize_mcp_tools(self):
        """初始化MCP工具"""
        await self._auto_assign_tools()
        for tool_name in self.assigned_tools:
            proxy = await self.mcp_proxy_manager.get_proxy(tool_name)
            if proxy:
                tool_spec = self.mcp_registry.tool_specs[tool_name]
                self.tool_capabilities[tool_name] = tool_spec.capabilities

    async def call_mcp_tool(
        self, tool_name: str, method: str, params: dict[str, Any] = None, **kwargs
    ) -> ProxyResponse:
        """調用MCP工具"""
        if tool_name not in self.assigned_tools:
            return ProxyResponse(success=False, error=f"工具 {tool_name} 未分配給當前Agent")

        return await self.mcp_proxy_manager.execute_tool_request(
            tool_name, method, params, **kwargs
        )

    async def process_artwork_image(self, image_data: bytes) -> dict[str, Any]:
        """處理藝術品圖像"""
        results = {}

        # 使用CLIP進行圖像理解
        clip_response = await self.call_mcp_tool(
            "clip", "image/process", {"image": image_data, "task": "understand"}
        )
        if clip_response.success:
            results["clip_analysis"] = clip_response.data

        # 使用BLIP生成圖像描述
        blip_response = await self.call_mcp_tool(
            "blip", "image/process", {"image": image_data, "task": "caption"}
        )
        if blip_response.success:
            results["image_caption"] = blip_response.data

        return results

    async def transcribe_audio(self, audio_data: bytes) -> ProxyResponse:
        """轉錄音頻內容"""
        return await self.call_mcp_tool(
            "whisper", "audio/process", {"audio": audio_data, "task": "transcribe"}
        )


class MCPAgentFactory:
    """MCP Agent工廠"""

    @staticmethod
    def create_mcp_agent(agent_type: str, **kwargs) -> BaseAgent:
        """創建MCP支持的Agent"""
        agent_classes = {
            "master": MCPMasterAgent,
            "vector_rag": MCPVectorRAGAgent,
            "multimodal": MCPMultimodalAgent,
        }

        if agent_type not in agent_classes:
            raise ValueError(f"不支持的Agent類型: {agent_type}")

        # 所有Agent都不接受額外參數
        return agent_classes[agent_type]()


class MCPIntegrationManager:
    """MCP集成管理器"""

    def __init__(self):
        self.logger = logging.getLogger("mcp_integration_manager")
        self.registry = get_mcp_registry()
        self.proxy_manager = get_proxy_manager()
        self.agents: dict[str, MCPCapableAgent] = {}

    async def initialize_mcp_system(self):
        """初始化整個MCP系統"""
        try:
            # 1. 註冊核心工具
            await self.registry.register_core_tools()

            # 2. 發現可用工具
            discovered_tools = await self.registry.discover_tools()
            self.logger.info(f"發現 {len(discovered_tools)} 個MCP工具服務")

            # 3. 連接到可用工具
            connected_count = 0
            for tool_name in self.registry.tool_specs.keys():
                if await self.registry.connect_tool(tool_name):
                    connected_count += 1

            self.logger.info(f"成功連接 {connected_count} 個MCP工具")

            # 4. 創建代理管理器
            self.logger.info("MCP系統初始化完成")

        except Exception as e:
            self.logger.error(f"MCP系統初始化失敗: {str(e)}")
            raise

    async def create_and_register_agents(self) -> dict[str, BaseAgent]:
        """創建和註冊MCP支持的Agent"""
        agent_configs = [{"type": "master"}, {"type": "vector_rag"}, {"type": "multimodal"}]

        for config in agent_configs:
            try:
                agent = MCPAgentFactory.create_mcp_agent(config["type"])
                await agent.initialize()
                self.agents[agent.agent_id] = agent
                self.logger.info(f"成功創建Agent: {agent.agent_id}")

            except Exception as e:
                self.logger.error(f"創建Agent {config['type']} 失敗: {str(e)}")

        return self.agents

    async def shutdown(self):
        """關閉MCP集成系統"""
        self.logger.info("正在關閉MCP集成系統...")

        # 停止所有Agent
        for agent in self.agents.values():
            try:
                await agent.stop()
            except Exception as e:
                self.logger.error(f"停止Agent時發生錯誤: {str(e)}")

        # 清理代理管理器
        await self.proxy_manager.cleanup_proxies()

        # 關閉註冊表
        await self.registry.shutdown()

        self.logger.info("MCP集成系統已關閉")


# 全局集成管理器實例
_integration_manager = None


def get_mcp_integration_manager() -> MCPIntegrationManager:
    """獲取MCP集成管理器單例實例"""
    global _integration_manager
    if _integration_manager is None:
        _integration_manager = MCPIntegrationManager()
    return _integration_manager
