#!/usr/bin/env python3
"""
快速演示實驗
展示MCP集成的RAG系統功能
"""

import asyncio
import logging
import os
import sys

# 添加src目錄到路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from experiments.art_history_experiment_suite import ArtHistoryExperimentSuite


async def run_demo():
    """運行演示實驗"""

    print("🎨 藝術史多模態RAG實驗演示")
    print("=" * 50)

    # 設置日誌
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    try:
        # 創建實驗套件
        experiment_suite = ArtHistoryExperimentSuite()

        print("🔧 正在初始化實驗環境...")

        # 運行演示實驗
        results = await experiment_suite.run_quick_demo_experiment()

        print("\n📊 實驗結果:")
        print("-" * 30)

        if "error" in results:
            print(f"❌ 實驗失敗: {results['error']}")
            return

        # 顯示結果摘要
        summary = results.get("experiment_summary", {})
        print(f"📝 總實驗數: {summary.get('total_experiments', 0)}")
        print(f"✅ 成功實驗: {summary.get('successful_experiments', 0)}")

        if summary.get("total_experiments", 0) > 0:
            success_rate = (
                summary.get("successful_experiments", 0) / summary.get("total_experiments", 1) * 100
            )
            print(f"📈 成功率: {success_rate:.1f}%")

        # 顯示推薦配置
        recommendations = results.get("recommendations", [])
        if recommendations:
            print("\n🎯 推薦配置:")
            for rec in recommendations:
                print(f"   • {rec}")

        # 顯示階段結果
        phase_results = results.get("phase_results", [])
        if phase_results:
            print("\n📈 各階段結果:")
            for phase in phase_results:
                print(
                    f"   {phase['phase']}: {phase['successful_experiments']}/{phase['total_experiments']} 成功"
                )
                if phase.get("average_accuracy"):
                    print(f"      平均準確率: {phase['average_accuracy']:.2%}")

        print("\n🎉 演示實驗完成！")
        print("=" * 50)
        print("💡 提示:")
        print("   • 如需運行完整實驗，請先啟動MCP工具服務")
        print("   • 使用 ./start_experiments.sh 啟動完整環境")
        print("   • 查看 EXPERIMENT_README.md 了解詳細信息")

    except Exception as e:
        print(f"❌ 演示實驗異常: {str(e)}")
        logging.error(f"演示實驗異常: {str(e)}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(run_demo())
