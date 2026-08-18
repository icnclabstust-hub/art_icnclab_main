#!/usr/bin/env python3
"""
多模態RAG Agent系統主程序
負責啟動和管理整個Agent生態系統
"""

import asyncio
import json
import logging
import signal
import sys
from datetime import datetime
from typing import Any

from agents.core.master_agent import MasterAgent
from agents.rag.vector_rag_agent import VectorRAGAgent
from communication.communication_hub import CommunicationHub


class AgentSystem:
    """Agent系統管理器"""

    def __init__(self):
        # 配置日誌
        self._setup_logging()
        self.logger = logging.getLogger("agent_system")

        # 核心組件
        self.communication_hub = CommunicationHub()
        self.master_agent = MasterAgent()

        # Agent實例
        self.agents: dict[str, Any] = {}
        self.active_agents: list[str] = []

        # 系統狀態
        self.is_running = False
        self.startup_time = None

        self.logger.info("Agent系統管理器初始化完成")

    def _setup_logging(self):
        """設置日誌"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler("logs/agent_system.log", encoding="utf-8"),
            ],
        )

    async def initialize(self):
        """初始化系統"""
        try:
            self.logger.info("開始初始化Agent系統...")

            # 1. 初始化通信中樞
            await self.communication_hub.initialize()

            # 2. 初始化Master Agent
            self.master_agent.communication_hub = self.communication_hub
            await self.master_agent.initialize()

            # 3. 註冊Master Agent到通信中樞
            await self.communication_hub.register_agent(
                self.master_agent.agent_id,
                {
                    "name": self.master_agent.name,
                    "capabilities": [cap.name for cap in self.master_agent.capabilities],
                },
            )

            # 4. 創建RAG Agent實例
            await self._create_rag_agents()

            # 5. 設置信號處理
            self._setup_signal_handlers()

            self.logger.info("Agent系統初始化完成")

        except Exception as e:
            self.logger.error(f"Agent系統初始化失敗: {e}")
            raise

    async def _create_rag_agents(self):
        """創建RAG Agent實例"""
        # 創建向量RAG Agent
        vector_rag_agent = VectorRAGAgent()
        vector_rag_agent.communication_hub = self.communication_hub
        await vector_rag_agent.initialize()

        self.agents[vector_rag_agent.agent_id] = vector_rag_agent

        # 註冊到通信中樞
        await self.communication_hub.register_agent(
            vector_rag_agent.agent_id,
            {
                "name": vector_rag_agent.name,
                "capabilities": [cap.name for cap in vector_rag_agent.capabilities],
            },
        )

        # 註冊到Master Agent
        await self.master_agent.register_managed_agent(
            vector_rag_agent.agent_id,
            {
                "name": vector_rag_agent.name,
                "type": "rag_agent",
                "framework": vector_rag_agent.rag_framework,
                "capabilities": [cap.name for cap in vector_rag_agent.capabilities],
            },
        )

        self.logger.info(f"RAG Agent {vector_rag_agent.agent_id} 創建完成")

    def _setup_signal_handlers(self):
        """設置信號處理器"""

        def signal_handler(signum, frame):
            self.logger.info(f"接收到信號 {signum}，開始關閉系統...")
            asyncio.create_task(self.shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def start(self):
        """啟動系統"""
        try:
            self.startup_time = datetime.now()
            self.is_running = True

            # 啟動Master Agent
            await self.master_agent.start()
            self.active_agents.append(self.master_agent.agent_id)

            # 啟動所有RAG Agent
            for agent_id, agent in self.agents.items():
                await agent.start()
                self.active_agents.append(agent_id)

            self.logger.info(f"Agent系統啟動完成，活躍Agent數量: {len(self.active_agents)}")

            # 運行系統監控
            await self._run_system_monitoring()

        except Exception as e:
            self.logger.error(f"Agent系統啟動失敗: {e}")
            await self.shutdown()
            raise

    async def shutdown(self):
        """關閉系統"""
        if not self.is_running:
            return

        self.logger.info("開始關閉Agent系統...")
        self.is_running = False

        try:
            # 停止所有RAG Agent
            for agent_id in list(self.active_agents):
                if agent_id != self.master_agent.agent_id and agent_id in self.agents:
                    agent = self.agents[agent_id]
                    await agent.stop()
                    await self.communication_hub.unregister_agent(agent_id)
                    self.active_agents.remove(agent_id)
                    self.logger.info(f"Agent {agent_id} 已停止")

            # 停止Master Agent
            if self.master_agent.agent_id in self.active_agents:
                await self.master_agent.stop()
                await self.communication_hub.unregister_agent(self.master_agent.agent_id)
                self.active_agents.remove(self.master_agent.agent_id)

            # 關閉通信中樞
            # 注意：由於communication_hub.shutdown()方法不存在，我們跳過這步
            # await self.communication_hub.shutdown()

            self.logger.info("Agent系統已完全關閉")

        except Exception as e:
            self.logger.error(f"系統關閉時發生錯誤: {e}")

    async def _run_system_monitoring(self):
        """運行系統監控"""
        while self.is_running:
            try:
                # 定期記錄系統狀態
                await self._log_system_status()

                # 檢查Agent健康狀況
                await self._check_agents_health()

                await asyncio.sleep(60)  # 每分鐘檢查一次

            except Exception as e:
                self.logger.error(f"系統監控錯誤: {e}")
                await asyncio.sleep(10)

    async def _log_system_status(self):
        """記錄系統狀態"""
        if self.startup_time:
            uptime = (datetime.now() - self.startup_time).total_seconds()
        else:
            uptime = 0

        status = {
            "uptime_seconds": uptime,
            "active_agents": len(self.active_agents),
            "master_status": self.master_agent.get_status(),
            "communication_stats": self.communication_hub.get_statistics(),
        }

        self.logger.debug(
            f"系統狀態: {json.dumps(status, default=str, indent=2, ensure_ascii=False)}"
        )

    async def _check_agents_health(self):
        """檢查Agent健康狀況"""
        unhealthy_agents = []

        for agent_id in self.active_agents:
            try:
                if agent_id == self.master_agent.agent_id:
                    agent = self.master_agent
                else:
                    agent = self.agents.get(agent_id)

                if agent and hasattr(agent, "status"):
                    if agent.status.value not in ["ready", "busy"]:
                        unhealthy_agents.append(agent_id)

            except Exception as e:
                self.logger.error(f"檢查Agent {agent_id} 健康狀況時出錯: {e}")
                unhealthy_agents.append(agent_id)

        if unhealthy_agents:
            self.logger.warning(f"發現不健康的Agent: {unhealthy_agents}")

    async def run_demo_experiment(self):
        """運行演示實驗"""
        try:
            self.logger.info("開始運行演示實驗...")

            # 創建實驗配置
            experiment_config = {
                "experiment_id": "demo_experiment_001",
                "rag_framework": "vector_rag",
                "llm_model": "ollama",
                "priority": 1,
                "estimated_duration": 300,
                "experiment_params": {
                    "test_queries": [
                        "什麼是文藝復興時期的藝術特徵？",
                        "蒙娜麗莎這幅畫有什麼特別之處？",
                        "印象派和後印象派有什麼區別？",
                    ],
                    "max_retrieved_docs": 3,
                    "temperature": 0.1,
                },
            }

            # 規劃實驗活動
            campaign_result = await self.master_agent.plan_experiment_campaign(
                {"experiment_params": experiment_config["experiment_params"]}
            )

            self.logger.info(f"實驗活動規劃完成: {campaign_result['campaign_id']}")

            # 啟動單個演示實驗
            experiment_result = await self.master_agent.start_experiment(experiment_config)

            self.logger.info(f"演示實驗已啟動: {experiment_result}")

            # 等待實驗完成 (這裡簡化為等待一段時間)
            await asyncio.sleep(10)

            # 模擬實驗完成
            completion_result = await self.master_agent.aggregate_results(
                {
                    "experiment_id": experiment_config["experiment_id"],
                    "progress": 100,
                    "data": {"queries_processed": 3, "avg_response_time": 2.5, "success_rate": 1.0},
                }
            )

            self.logger.info(f"演示實驗完成: {completion_result}")

            return {
                "campaign": campaign_result,
                "experiment": experiment_result,
                "completion": completion_result,
            }

        except Exception as e:
            self.logger.error(f"演示實驗運行失敗: {e}")
            raise

    def get_system_status(self) -> dict[str, Any]:
        """獲取系統狀態"""
        return {
            "is_running": self.is_running,
            "startup_time": self.startup_time.isoformat() if self.startup_time else None,
            "uptime_seconds": (datetime.now() - self.startup_time).total_seconds()
            if self.startup_time
            else 0,
            "active_agents": self.active_agents,
            "total_agents": len(self.agents) + 1,  # +1 for master agent
            "master_agent_status": self.master_agent.get_system_status(),
            "communication_stats": self.communication_hub.get_statistics(),
        }


async def main():
    """主函數"""
    system = AgentSystem()

    try:
        # 初始化系統
        await system.initialize()

        # 啟動系統
        await system.start()

        # 運行演示實驗
        demo_result = await system.run_demo_experiment()
        print("\n" + "=" * 60)
        print("演示實驗完成！")
        print("=" * 60)
        print(json.dumps(demo_result, default=str, indent=2, ensure_ascii=False))

        # 保持系統運行
        print("\nAgent系統正在運行...按Ctrl+C停止")
        while system.is_running:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n接收到中斷信號...")
    except Exception as e:
        print(f"\n系統運行出錯: {e}")
    finally:
        await system.shutdown()


if __name__ == "__main__":
    # 確保日誌目錄存在
    import os

    os.makedirs("logs", exist_ok=True)

    # 運行系統
    asyncio.run(main())
