#!/usr/bin/env python3
"""
集成MCP工具的Agent系統主程序
擴展原有系統以支持MCP工具集成
"""

import asyncio
import signal
from datetime import datetime
from typing import Any

# 導入原有系統組件
from agent_system import AgentSystem

# 導入MCP集成組件
from mcp.mcp_agent_integration import (
    get_mcp_integration_manager,
)
from mcp.mcp_tool_proxy import get_proxy_manager
from mcp.mcp_tool_registry import get_mcp_registry


class MCPAgentSystem(AgentSystem):
    """
    集成MCP工具的Agent系統
    擴展原有AgentSystem以支持MCP工具集成
    """

    def __init__(self):
        # 先初始化父類
        super().__init__()

        # MCP集成組件
        self.mcp_integration_manager = get_mcp_integration_manager()
        self.mcp_registry = get_mcp_registry()
        self.mcp_proxy_manager = get_proxy_manager()

        # MCP Agent實例
        self.mcp_agents: dict[str, Any] = {}
        self.mcp_enabled = True

        self.logger.info("MCP Agent系統管理器初始化完成")

    async def initialize_mcp_system(self):
        """初始化MCP系統"""
        try:
            self.logger.info("開始初始化MCP系統...")

            # 初始化MCP核心系統
            await self.mcp_integration_manager.initialize_mcp_system()

            # 創建MCP支持的Agent
            self.mcp_agents = await self.mcp_integration_manager.create_and_register_agents()

            # 將MCP Agent添加到系統中
            self.agents.update(self.mcp_agents)

            self.logger.info(f"MCP系統初始化完成，創建了 {len(self.mcp_agents)} 個MCP Agent")

        except Exception as e:
            self.logger.error(f"MCP系統初始化失敗: {str(e)}")
            self.mcp_enabled = False

    async def start_system(self):
        """啟動完整系統（包含MCP支持）"""
        try:
            self.logger.info("🚀 啟動MCP增強型Agent系統...")

            # 初始化MCP系統
            if self.mcp_enabled:
                await self.initialize_mcp_system()

            # 啟動通信中樞
            await self.communication_hub.initialize()
            self.logger.info("✅ 通信中樞已啟動")

            # 啟動所有Agent（包括MCP Agent）
            startup_tasks = []
            for agent_id, agent in self.agents.items():
                if hasattr(agent, "initialize"):
                    task = agent.initialize()
                    startup_tasks.append((agent_id, task))
                elif hasattr(agent, "start"):
                    task = agent.start()
                    startup_tasks.append((agent_id, task))

            # 並行啟動所有Agent
            for agent_id, task in startup_tasks:
                try:
                    await task
                    self.active_agents.append(agent_id)
                    self.logger.info(f"✅ Agent {agent_id} 已啟動")
                except Exception as e:
                    self.logger.error(f"❌ Agent {agent_id} 啟動失敗: {str(e)}")

            self.is_running = True
            self.startup_time = datetime.now()

            # 系統健康檢查
            await self._system_health_check()

            self.logger.info(f"🎉 系統啟動完成！運行 {len(self.active_agents)} 個Agent")

        except Exception as e:
            self.logger.error(f"系統啟動失敗: {str(e)}")
            raise

    async def _system_health_check(self):
        """系統健康檢查"""
        try:
            # 檢查通信中樞
            comm_health = await self.communication_hub.get_health_status()
            self.logger.info(f"通信中樞健康狀況: {comm_health}")

            # 檢查MCP工具健康狀況
            if self.mcp_enabled and "mcp_master" in self.agents:
                mcp_master = self.agents["mcp_master"]
                mcp_health = await mcp_master.monitor_mcp_tools_health()
                self.logger.info(f"MCP工具健康狀況: {mcp_health['registry_stats']}")

            # 檢查Agent狀態
            agent_statuses = {}
            for agent_id, agent in self.agents.items():
                if hasattr(agent, "status"):
                    agent_statuses[agent_id] = agent.status.value
                else:
                    agent_statuses[agent_id] = "unknown"

            self.logger.info(f"Agent狀態: {agent_statuses}")

        except Exception as e:
            self.logger.error(f"系統健康檢查失敗: {str(e)}")

    async def run_mcp_rag_experiment(self, query: str, **kwargs) -> dict[str, Any]:
        """運行MCP增強的RAG實驗"""
        if not self.mcp_enabled or "mcp_vector_rag" not in self.agents:
            return {"success": False, "error": "MCP RAG Agent不可用"}

        try:
            rag_agent = self.agents["mcp_vector_rag"]
            result = await rag_agent.mcp_rag_pipeline(query, **kwargs)

            self.logger.info(f"MCP RAG實驗完成: {query[:50]}...")
            return result

        except Exception as e:
            self.logger.error(f"MCP RAG實驗失敗: {str(e)}")
            return {"success": False, "error": str(e)}

    async def process_multimodal_data(
        self, image_data: bytes = None, audio_data: bytes = None
    ) -> dict[str, Any]:
        """處理多模態數據"""
        if not self.mcp_enabled or "mcp_multimodal" not in self.agents:
            return {"success": False, "error": "MCP多模態Agent不可用"}

        try:
            multimodal_agent = self.agents["mcp_multimodal"]
            results = {}

            if image_data:
                image_result = await multimodal_agent.process_artwork_image(image_data)
                results["image_analysis"] = image_result

            if audio_data:
                audio_result = await multimodal_agent.transcribe_audio(audio_data)
                results["audio_transcription"] = audio_result

            return {"success": True, "results": results}

        except Exception as e:
            self.logger.error(f"多模態數據處理失敗: {str(e)}")
            return {"success": False, "error": str(e)}

    async def run_comparative_rag_experiment(
        self, queries: list[str], rag_frameworks: list[str] = None, llm_models: list[str] = None
    ) -> dict[str, Any]:
        """運行對比RAG實驗"""
        if not rag_frameworks:
            rag_frameworks = ["vector_rag", "advanced_rag", "graph_rag"]

        if not llm_models:
            llm_models = ["openai", "anthropic", "ollama"]

        results = {}

        try:
            for query in queries:
                query_results = {}

                for framework in rag_frameworks:
                    framework_results = {}

                    for model in llm_models:
                        try:
                            # 使用不同的RAG框架和模型組合
                            result = await self.run_mcp_rag_experiment(
                                query, framework=framework, llm_model=model
                            )
                            framework_results[model] = result

                        except Exception as e:
                            framework_results[model] = {"success": False, "error": str(e)}

                    query_results[framework] = framework_results

                results[query] = query_results

            self.logger.info(
                f"對比實驗完成：{len(queries)} 個查詢 × {len(rag_frameworks)} 個框架 × {len(llm_models)} 個模型"
            )
            return {"success": True, "experiment_results": results}

        except Exception as e:
            self.logger.error(f"對比實驗失敗: {str(e)}")
            return {"success": False, "error": str(e)}

    async def get_mcp_system_status(self) -> dict[str, Any]:
        """獲取MCP系統狀態"""
        try:
            status = {
                "mcp_enabled": self.mcp_enabled,
                "system_running": self.is_running,
                "startup_time": self.startup_time.isoformat() if self.startup_time else None,
                "active_agents": len(self.active_agents),
                "mcp_agents": list(self.mcp_agents.keys()) if self.mcp_enabled else [],
                "tool_registry": {},
                "proxy_stats": {},
            }

            if self.mcp_enabled:
                # MCP工具註冊表狀態
                status["tool_registry"] = self.mcp_registry.get_registry_stats()

                # MCP代理統計
                status["proxy_stats"] = self.mcp_proxy_manager.get_proxy_stats()

                # MCP工具健康狀況
                if "mcp_master" in self.agents:
                    mcp_master = self.agents["mcp_master"]
                    health_report = await mcp_master.monitor_mcp_tools_health()
                    status["tool_health"] = health_report["tool_health"]

            return status

        except Exception as e:
            self.logger.error(f"獲取MCP系統狀態失敗: {str(e)}")
            return {"error": str(e)}

    async def shutdown_system(self):
        """關閉系統"""
        self.logger.info("正在關閉MCP增強型Agent系統...")

        try:
            # 停止所有Agent
            for agent_id, agent in self.agents.items():
                try:
                    if hasattr(agent, "stop"):
                        await agent.stop()
                        self.logger.info(f"Agent {agent_id} 已停止")
                except Exception as e:
                    self.logger.error(f"停止Agent {agent_id} 時發生錯誤: {str(e)}")

            # 關閉通信中樞
            if hasattr(self.communication_hub, "shutdown"):
                await self.communication_hub.shutdown()

            # 關閉MCP系統
            if self.mcp_enabled:
                await self.mcp_integration_manager.shutdown()

            self.is_running = False
            self.logger.info("系統已關閉")

        except Exception as e:
            self.logger.error(f"關閉系統時發生錯誤: {str(e)}")


async def main():
    """主程序"""
    # 設置信號處理
    system = None

    def signal_handler(signum, frame):
        print(f"\n收到信號 {signum}，正在關閉系統...")
        if system and system.is_running:
            asyncio.create_task(system.shutdown_system())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # 創建並啟動系統
        system = MCPAgentSystem()
        await system.start_system()

        # 運行示例實驗
        await run_demo_experiments(system)

        # 保持系統運行
        print("系統運行中... 按 Ctrl+C 停止")
        while system.is_running:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n接收到中斷信號")
    except Exception as e:
        print(f"系統運行錯誤: {str(e)}")
    finally:
        if system:
            await system.shutdown_system()


async def run_demo_experiments(system: MCPAgentSystem):
    """運行示例實驗"""
    try:
        print("\n🧪 運行示例實驗...")

        # 1. 簡單RAG查詢測試
        print("\n1️⃣  測試MCP RAG查詢...")
        rag_result = await system.run_mcp_rag_experiment(
            "什麼是印象派畫風？", vector_db="chromadb", collection="art_history", top_k=5
        )
        print(f"RAG查詢結果: {rag_result.get('success', False)}")

        # 2. 系統狀態檢查
        print("\n2️⃣  檢查系統狀態...")
        status = await system.get_mcp_system_status()
        print(f"MCP工具狀態: {status.get('tool_registry', {}).get('active_tools', 0)} 個工具活躍")

        # 3. 對比實驗（簡化版）
        print("\n3️⃣  運行簡化對比實驗...")
        comparative_result = await system.run_comparative_rag_experiment(
            queries=["什麼是文藝復興？"], rag_frameworks=["vector_rag"], llm_models=["openai"]
        )
        print(f"對比實驗結果: {comparative_result.get('success', False)}")

        print("\n✅ 示例實驗完成！")

    except Exception as e:
        print(f"❌ 示例實驗失敗: {str(e)}")


if __name__ == "__main__":
    # 運行系統
    asyncio.run(main())
