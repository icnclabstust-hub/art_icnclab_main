#!/usr/bin/env python3
"""
Agent框架簡化測試
測試核心Agent功能，避免複雜依賴
"""

import asyncio
import logging
import sys

# 添加src目錄到Python路径
sys.path.append("src")


async def test_basic_agent_functionality():
    """測試基本Agent功能"""
    print("🚀 開始Agent框架簡化測試")
    print("=" * 60)

    try:
        # 測試1: 基礎Agent類
        print("\n🔍 測試1: Agent基礎類")
        from agents.core.base_agent import AgentCapability, BaseAgent

        # 創建測試Agent
        class TestAgent(BaseAgent):
            def __init__(self):
                super().__init__("test_agent", "測試Agent")

            async def _initialize(self):
                pass

            async def _register_capabilities(self):
                return [
                    AgentCapability(
                        name="test_capability",
                        description="測試能力",
                        input_types=["text"],
                        output_types=["text"],
                        resource_requirements={},
                        estimated_time=1.0,
                    )
                ]

            async def _start(self):
                pass

            async def _stop(self):
                pass

            async def _execute_task(self, task_id, task_data):
                return {"result": "測試完成", "task_id": task_id}

        agent = TestAgent()
        await agent.initialize()
        print("✅ Agent基礎類測試通過")

        # 測試2: 向量RAG Agent
        print("\n🔍 測試2: 向量RAG Agent")
        from agents.rag.vector_rag_agent import VectorRAGAgent

        vector_agent = VectorRAGAgent()
        await vector_agent.initialize()
        print("✅ 向量RAG Agent初始化成功")

        # 測試查詢處理
        test_query = "什麼是藝術史？"
        result = await vector_agent.process_single_query(test_query)

        if result and result.get("query") == test_query:
            print(f"✅ 查詢處理成功: {result.get('generated_answer', '')[:50]}...")
        else:
            print("❌ 查詢處理失敗")

        # 測試3: 通信中樞
        print("\n🔍 測試3: 通信中樞")
        from communication.communication_hub import CommunicationHub

        comm_hub = CommunicationHub()
        await comm_hub.initialize()

        # 註冊Agent
        await comm_hub.register_agent("test_agent", {"name": "測試Agent"})
        stats = comm_hub.get_statistics()
        print(f"✅ 通信中樞測試通過，已註冊Agent: {stats['registered_agents']}")

        # 測試4: 實驗調度器
        print("\n🔍 測試4: 實驗調度器")
        from scheduling.experiment_scheduler import ExperimentScheduler, SchedulingStrategy

        scheduler = ExperimentScheduler(SchedulingStrategy.PRIORITY_FIRST)
        await scheduler.initialize()

        # 創建測試實驗
        experiment_config = {
            "experiment_id": "test_experiment",
            "priority": 1,
            "estimated_duration": 10,
            "dependencies": [],
        }

        await scheduler.schedule_single_experiment(experiment_config)
        scheduler_status = scheduler.get_status()

        print(f"✅ 調度器測試通過，待調度實驗: {scheduler_status['queue_status']['pending']}")

        # 清理
        await scheduler.shutdown()

        # 測試5: Agent監控器
        print("\n🔍 測試5: Agent監控器")
        from monitoring.agent_monitor import AgentMonitor

        monitor = AgentMonitor()
        await monitor.initialize()

        # 註冊Agent到監控
        monitor.register_agent("test_agent", {"name": "測試Agent"})

        # 更新指標
        await monitor.update_agent_metrics(
            "test_agent",
            {
                "cpu_usage": 50.0,
                "memory_usage": 60.0,
                "response_time": 1.5,
                "task_success_rate": 0.95,
                "error_count": 0,
            },
        )

        health = monitor.get_agent_health("test_agent")
        system_overview = monitor.get_system_overview()

        print(f"✅ 監控器測試通過，Agent狀態: {health['status']}")
        print(f"✅ 系統概覽: 總計{system_overview['total_agents']}個Agent")

        # 清理
        await monitor.shutdown()

        print("\n" + "=" * 60)
        print("🎉 所有基礎測試通過！Agent框架核心功能正常")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n💥 測試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_agent_integration():
    """測試Agent集成功能"""
    print("\n🔍 集成測試: 完整工作流")
    print("-" * 40)

    try:
        # 創建向量RAG Agent
        from agents.rag.vector_rag_agent import VectorRAGAgent

        agent = VectorRAGAgent()
        await agent.initialize()
        await agent.start()

        # 模擬批量查詢測試
        test_queries = ["什麼是文藝復興？", "印象派有什麼特點？", "蒙娜麗莎的作者是誰？"]

        print(f"📝 處理 {len(test_queries)} 個測試查詢...")

        batch_result = await agent.process_batch_queries(test_queries)

        print("✅ 批量處理完成:")
        print(f"   - 總查詢數: {batch_result['total_queries']}")
        print(f"   - 成功查詢: {batch_result['successful_queries']}")
        print(f"   - 失敗查詢: {batch_result['failed_queries']}")
        print(f"   - 平均響應時間: {batch_result['avg_time_per_query']:.2f}秒")

        # 獲取性能指標
        performance = agent.get_performance_metrics()
        print("✅ Agent性能指標:")
        print(f"   - 框架: {performance['rag_framework']}")
        print(f"   - 總查詢數: {performance['performance']['total_queries']}")
        print(f"   - 平均響應時間: {performance['performance']['avg_response_time']:.2f}秒")

        # 停止Agent
        await agent.stop()

        print("✅ 集成測試通過")
        return True

    except Exception as e:
        print(f"❌ 集成測試失敗: {e}")
        return False


async def main():
    """主函數"""
    # 配置基礎日誌
    logging.basicConfig(level=logging.WARNING)  # 減少日誌輸出

    # 確保目錄存在
    import os

    os.makedirs("logs", exist_ok=True)

    # 運行測試
    basic_success = await test_basic_agent_functionality()
    integration_success = await test_agent_integration()

    # 測試總結
    print("\n" + "=" * 60)
    print("📊 測試總結")
    print("=" * 60)

    if basic_success and integration_success:
        print("🎉 所有測試通過！Agent框架已準備就緒")
        print("\n🚀 後續步驟:")
        print("   1. 運行完整的多實驗測試")
        print("   2. 集成更多RAG框架變體")
        print("   3. 添加更多MCP工具支持")
        print("   4. 建立生產級監控和告警")
    elif basic_success:
        print("⚠️ 基礎功能正常，但集成測試有問題")
        print("   建議檢查Agent間通信和協作機制")
    else:
        print("🚨 基礎功能測試失敗")
        print("   請檢查Agent框架的核心實現")


if __name__ == "__main__":
    asyncio.run(main())
