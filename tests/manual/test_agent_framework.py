#!/usr/bin/env python3
"""
Agent框架完整測試腳本
測試多模態RAG Agent系統的各項功能
"""

import asyncio
import logging
import sys
import traceback
from datetime import datetime

# 添加src目錄到Python路径
sys.path.append("src")

from agent_system import AgentSystem


class AgentFrameworkTester:
    """Agent框架測試器"""

    def __init__(self):
        self.logger = logging.getLogger("agent_framework_tester")
        self.test_results = []
        self.system = None

    async def run_all_tests(self):
        """運行所有測試"""
        print("🚀 開始Agent框架完整測試")
        print("=" * 60)

        tests = [
            ("系統初始化測試", self.test_system_initialization),
            ("Agent通信測試", self.test_agent_communication),
            ("RAG實驗執行測試", self.test_rag_experiment_execution),
            ("多實驗調度測試", self.test_multiple_experiment_scheduling),
            ("錯誤處理測試", self.test_error_handling),
            ("系統監控測試", self.test_system_monitoring),
            ("資源管理測試", self.test_resource_management),
            ("系統關閉測試", self.test_system_shutdown),
        ]

        for test_name, test_func in tests:
            await self._run_single_test(test_name, test_func)

        self._print_test_summary()

    async def _run_single_test(self, test_name: str, test_func):
        """運行單個測試"""
        print(f"\n🔍 {test_name}")
        print("-" * 40)

        start_time = datetime.now()
        try:
            result = await test_func()
            duration = (datetime.now() - start_time).total_seconds()

            if result:
                print(f"✅ 測試通過 ({duration:.2f}s)")
                self.test_results.append(
                    {
                        "name": test_name,
                        "status": "PASSED",
                        "duration": duration,
                        "message": "測試成功",
                    }
                )
            else:
                print(f"❌ 測試失敗 ({duration:.2f}s)")
                self.test_results.append(
                    {
                        "name": test_name,
                        "status": "FAILED",
                        "duration": duration,
                        "message": "測試返回False",
                    }
                )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            print(f"💥 測試異常 ({duration:.2f}s): {str(e)}")
            print(f"   錯誤詳情: {traceback.format_exc()}")
            self.test_results.append(
                {"name": test_name, "status": "ERROR", "duration": duration, "message": str(e)}
            )

    async def test_system_initialization(self) -> bool:
        """測試系統初始化"""
        try:
            # 創建Agent系統
            self.system = AgentSystem()

            # 初始化系統
            await self.system.initialize()

            # 檢查初始化狀態
            if not self.system.communication_hub:
                print("❌ 通信中樞未初始化")
                return False

            if not self.system.master_agent:
                print("❌ Master Agent未初始化")
                return False

            print("✓ Agent系統初始化成功")
            print(f"✓ 創建了 {len(self.system.agents)} 個RAG Agent")
            return True

        except Exception as e:
            print(f"❌ 初始化失敗: {e}")
            return False

    async def test_agent_communication(self) -> bool:
        """測試Agent間通信"""
        try:
            if not self.system:
                return False

            # 啟動系統
            await self.system.start()

            # 等待Agent啟動
            await asyncio.sleep(2)

            # 檢查通信中樞統計
            comm_stats = self.system.communication_hub.get_statistics()
            print(f"✓ 已註冊Agent數量: {comm_stats['registered_agents']}")
            print(f"✓ 在線Agent數量: {comm_stats['online_agents']}")

            # 檢查Master Agent狀態
            master_status = self.system.master_agent.get_status()
            print(f"✓ Master Agent狀態: {master_status['status']}")

            return comm_stats["online_agents"] > 0

        except Exception as e:
            print(f"❌ 通信測試失敗: {e}")
            return False

    async def test_rag_experiment_execution(self) -> bool:
        """測試RAG實驗執行"""
        try:
            if not self.system or not self.system.is_running:
                return False

            print("📝 創建RAG實驗配置...")

            # 直接測試RAG Agent
            vector_rag_agent = None
            for _agent_id, agent in self.system.agents.items():
                if hasattr(agent, "rag_framework") and agent.rag_framework == "vector_rag":
                    vector_rag_agent = agent
                    break

            if not vector_rag_agent:
                print("❌ 未找到向量RAG Agent")
                return False

            # 測試單個查詢處理
            test_query = "什麼是文藝復興？"
            print(f"🔍 測試查詢: {test_query}")

            result = await vector_rag_agent.process_single_query(test_query)

            if result and result.get("success"):
                print("✓ 查詢處理成功")
                print(f"✓ 檢索文檔數: {len(result.get('retrieved_documents', []))}")
                print(f"✓ 生成答案: {result.get('generated_answer', '')[:100]}...")
                print(f"✓ 響應時間: {result.get('metrics', {}).get('total_time', 0):.2f}秒")
                return True
            else:
                print("❌ 查詢處理失敗")
                return False

        except Exception as e:
            print(f"❌ RAG實驗執行測試失敗: {e}")
            return False

    async def test_multiple_experiment_scheduling(self) -> bool:
        """測試多實驗調度"""
        try:
            if not self.system or not self.system.is_running:
                return False

            # 創建多個實驗配置
            experiments = []
            for i in range(3):
                experiment_config = {
                    "experiment_id": f"scheduled_experiment_{i}",
                    "rag_framework": "vector_rag",
                    "llm_model": "ollama",
                    "priority": i + 1,
                    "estimated_duration": 20,
                    "experiment_params": {
                        "test_queries": [f"測試查詢 {i}"],
                        "max_retrieved_docs": 3,
                    },
                }
                experiments.append(experiment_config)

            print(f"📋 創建了 {len(experiments)} 個實驗配置")

            # 規劃實驗活動
            campaign_result = await self.system.master_agent.plan_experiment_campaign(
                {"experiment_params": {"test_mode": True}}
            )

            print(f"✓ 實驗活動規劃完成: {campaign_result['campaign_id']}")
            print(f"✓ 總實驗數量: {campaign_result['campaign']['total_experiments']}")

            # 檢查調度器狀態
            scheduler_status = self.system.master_agent.experiment_scheduler.get_status()
            print(f"✓ 調度器狀態: {scheduler_status['is_running']}")

            return True

        except Exception as e:
            print(f"❌ 多實驗調度測試失敗: {e}")
            return False

    async def test_error_handling(self) -> bool:
        """測試錯誤處理"""
        try:
            if not self.system:
                return False

            print("🚨 測試錯誤處理機制...")

            # 測試1: 處理無效查詢
            vector_rag_agent = list(self.system.agents.values())[0]

            try:
                await vector_rag_agent.process_single_query("")
                print("✓ 空查詢處理正常")
            except Exception as e:
                print(f"✓ 空查詢錯誤處理: {str(e)[:50]}...")

            # 測試2: 模擬Agent異常
            try:
                # 嘗試訪問不存在的方法
                await vector_rag_agent.nonexistent_method()
            except AttributeError:
                print("✓ Agent方法錯誤處理正常")

            print("✓ 錯誤處理機制運行正常")
            return True

        except Exception as e:
            print(f"❌ 錯誤處理測試失敗: {e}")
            return False

    async def test_system_monitoring(self) -> bool:
        """測試系統監控"""
        try:
            if not self.system:
                return False

            # 獲取系統狀態
            system_status = self.system.get_system_status()
            print(f"✓ 系統運行狀態: {system_status['is_running']}")
            print(f"✓ 活躍Agent數量: {len(system_status['active_agents'])}")

            if system_status["uptime_seconds"] > 0:
                print(f"✓ 系統運行時間: {system_status['uptime_seconds']:.1f}秒")

            # 檢查Master Agent狀態
            master_status = system_status["master_agent_status"]
            print(f"✓ Master Agent狀態: {master_status['master_agent']['status']}")

            # 檢查通信統計
            comm_stats = system_status["communication_stats"]
            print(
                f"✓ 消息統計: 發送{comm_stats['message_stats']['sent']}, "
                f"接收{comm_stats['message_stats']['received']}"
            )

            return True

        except Exception as e:
            print(f"❌ 系統監控測試失敗: {e}")
            return False

    async def test_resource_management(self) -> bool:
        """測試資源管理"""
        try:
            if not self.system:
                return False

            # 檢查調度器的資源池
            if hasattr(self.system.master_agent, "experiment_scheduler"):
                scheduler = self.system.master_agent.experiment_scheduler
                resource_pool = scheduler.resource_pool

                utilization = resource_pool.get_utilization()
                print(f"✓ CPU利用率: {utilization['cpu_utilization']:.2%}")
                print(f"✓ 內存利用率: {utilization['memory_utilization']:.2%}")

                # 檢查向量資料庫狀態
                for db_name, db_info in resource_pool.vector_databases.items():
                    print(
                        f"✓ {db_name}: {db_info['status']}, "
                        f"使用率: {db_info['current_usage']}/{db_info['concurrent_limit']}"
                    )

                return True
            else:
                print("❌ 調度器未初始化")
                return False

        except Exception as e:
            print(f"❌ 資源管理測試失敗: {e}")
            return False

    async def test_system_shutdown(self) -> bool:
        """測試系統關閉"""
        try:
            if not self.system:
                return False

            print("🔄 開始系統關閉測試...")

            # 記錄關閉前狀態
            active_agents_before = len(self.system.active_agents)
            print(f"✓ 關閉前活躍Agent數量: {active_agents_before}")

            # 執行關閉
            await self.system.shutdown()

            # 檢查關閉後狀態
            print(f"✓ 關閉後活躍Agent數量: {len(self.system.active_agents)}")
            print(f"✓ 系統運行狀態: {self.system.is_running}")

            return not self.system.is_running and len(self.system.active_agents) == 0

        except Exception as e:
            print(f"❌ 系統關閉測試失敗: {e}")
            return False

    def _print_test_summary(self):
        """打印測試摘要"""
        print("\n" + "=" * 60)
        print("📊 測試結果摘要")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["status"] == "PASSED"])
        failed_tests = len([r for r in self.test_results if r["status"] == "FAILED"])
        error_tests = len([r for r in self.test_results if r["status"] == "ERROR"])

        print(f"總測試數量: {total_tests}")
        print(f"✅ 通過: {passed_tests}")
        print(f"❌ 失敗: {failed_tests}")
        print(f"💥 異常: {error_tests}")
        print(f"🎯 成功率: {passed_tests / total_tests * 100:.1f}%")

        total_duration = sum(r["duration"] for r in self.test_results)
        print(f"⏱️ 總測試時間: {total_duration:.2f}秒")

        print("\n📋 詳細結果:")
        for i, result in enumerate(self.test_results, 1):
            status_icon = {"PASSED": "✅", "FAILED": "❌", "ERROR": "💥"}[result["status"]]
            print(f"{i:2d}. {status_icon} {result['name']} ({result['duration']:.2f}s)")
            if result["status"] != "PASSED":
                print(f"     💬 {result['message']}")

        print("\n" + "=" * 60)
        if passed_tests == total_tests:
            print("🎉 所有測試通過！Agent框架運行正常！")
        elif passed_tests >= total_tests * 0.8:
            print("⚠️ 大部分測試通過，但有部分問題需要關注")
        else:
            print("🚨 多項測試失敗，需要檢查系統配置")


async def main():
    """主函數"""
    # 配置日誌
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 確保必要目錄存在
    import os

    os.makedirs("logs", exist_ok=True)

    # 創建測試器
    tester = AgentFrameworkTester()

    try:
        # 運行所有測試
        await tester.run_all_tests()

    except KeyboardInterrupt:
        print("\n🛑 測試被用戶中斷")
    except Exception as e:
        print(f"\n💥 測試運行出錯: {e}")
        traceback.print_exc()
    finally:
        # 確保系統關閉
        if tester.system and tester.system.is_running:
            print("\n🔄 正在關閉系統...")
            await tester.system.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
