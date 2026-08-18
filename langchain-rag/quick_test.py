#!/usr/bin/env python3
"""
快速測試增強型自適應策略
驗證核心功能正常運作
"""

import asyncio
import os
import sys
import time

# 添加當前目錄到Python路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from enhanced_adaptive_strategies import EnhancedAdaptiveManager, QueryContext


async def quick_test():
    """執行快速測試"""
    print("🚀 開始增強型自適應策略快速測試")
    print("=" * 50)

    # 初始化管理器
    print("初始化自適應策略管理器...")
    adaptive_manager = EnhancedAdaptiveManager(learning_rate=0.15, exploration_rate=0.3)
    print("✅ 初始化完成")

    # 測試查詢列表
    test_queries = [
        ("莫內的印象派作品有什麼特色？", "事實查詢"),
        ("比較印象派和古典主義的差異", "對比分析"),
        ("這幅畫使用了什麼顏色？", "視覺描述"),
        ("文藝復興的歷史背景", "歷史脈絡"),
        ("為什麼達芬奇很重要？", "分析推理"),
    ]

    print(f"\n📋 測試 {len(test_queries)} 個查詢的策略選擇...")

    strategy_counts = {}
    total_time = 0

    for i, (query, category) in enumerate(test_queries, 1):
        print(f"\n查詢 {i}: {category}")
        print(f"文本: {query}")

        # 創建查詢情境
        context = QueryContext(
            query_text=query, user_id=f"test_user_{i}", session_id=f"test_session_{i}"
        )

        # 測試策略選擇
        start_time = time.time()
        selected_strategy = await adaptive_manager.select_optimal_strategy(context)
        processing_time = time.time() - start_time
        total_time += processing_time

        print(f"選擇策略: {selected_strategy.value}")
        print(f"處理時間: {processing_time:.3f}s")

        # 統計策略選擇
        strategy_counts[selected_strategy.value] = (
            strategy_counts.get(selected_strategy.value, 0) + 1
        )

        # 模擬性能反饋
        simulated_metrics = {
            "success": True,
            "response_time": processing_time,
            "confidence": 0.8,
            "user_satisfaction": 4.2,
        }

        await adaptive_manager.update_strategy_performance(
            selected_strategy, context, simulated_metrics
        )
        print("📊 性能反饋已記錄")

    # 輸出統計結果
    print("\n📈 測試結果統計:")
    print(f"總處理時間: {total_time:.3f}s")
    print(f"平均處理時間: {total_time / len(test_queries):.3f}s")

    print("\n🎯 策略選擇分布:")
    for strategy, count in strategy_counts.items():
        percentage = (count / len(test_queries)) * 100
        print(f"  {strategy}: {count} 次 ({percentage:.1f}%)")

    # 測試系統狀態
    print("\n🔍 系統狀態檢查:")
    system_status = adaptive_manager.get_system_status()
    print(f"總處理查詢數: {system_status['total_queries_processed']}")
    print(f"探索率: {system_status['exploration_rate']:.3f}")
    print(f"學習率: {system_status['learning_rate']:.3f}")

    # 測試批次優化
    print("\n⚡ 執行系統優化...")
    optimization_start = time.time()
    await adaptive_manager.optimize_system_performance()
    optimization_time = time.time() - optimization_start
    print(f"優化執行時間: {optimization_time:.3f}s")

    # 測試策略推薦
    print("\n🤖 測試策略推薦功能...")
    test_context = QueryContext(query_text="測試查詢推薦功能")
    recommendation = adaptive_manager.get_strategy_recommendation(test_context)
    recommended_strategy = recommendation["recommended_strategy"]
    print(f"推薦策略: {recommended_strategy}")

    print("\n✅ 所有測試完成！增強型自適應策略運行正常")
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(quick_test())
        if result:
            print("\n🎉 測試結果: 成功")
            exit(0)
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        exit(1)
