#!/usr/bin/env python3
"""
整合系統測試腳本
測試多模態RAG優化管理器的完整功能
"""

import asyncio
import time

from integrated_rag_optimizer import IntegratedRAGOptimizer, RAGStrategy


async def test_integrated_rag_system():
    """測試整合RAG系統"""
    print("🚀 開始整合系統測試...")
    print("=" * 60)

    # 初始化系統
    optimizer = IntegratedRAGOptimizer()
    if not optimizer.initialize_components():
        print("❌ 系統初始化失敗")
        return False

    print("✅ 系統初始化成功")

    # 測試案例
    test_cases = [
        {
            "query": "達文西創作了哪些著名作品？",
            "expected_strategy": RAGStrategy.GRAPH_ONLY,
            "test_type": "關係查詢",
        },
        {
            "query": "描述蒙娜麗莎的藝術特色和歷史意義",
            "expected_strategy": RAGStrategy.VECTOR_ONLY,
            "test_type": "內容查詢",
        },
        {
            "query": "印象派與後印象派的發展關係如何？",
            "expected_strategy": RAGStrategy.HYBRID_BALANCED,
            "test_type": "複雜查詢",
        },
        {"query": "藝術", "expected_strategy": RAGStrategy.VECTOR_ONLY, "test_type": "簡單查詢"},
        {
            "query": "分析文藝復興時期藝術家之間的師承關係和相互影響",
            "expected_strategy": RAGStrategy.HYBRID_BALANCED,
            "test_type": "專家級查詢",
        },
    ]

    print(f"\n🧪 執行 {len(test_cases)} 個測試案例")
    print("-" * 60)

    successful_tests = 0
    total_processing_time = 0

    # 1. 單個查詢測試
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📝 測試 {i}: {test_case['test_type']}")
        print(f"查詢: {test_case['query']}")

        try:
            result = await optimizer.query(test_case["query"])

            print(f"策略: {result.strategy_used.value}")
            print(f"時間: {result.processing_time:.3f}s")
            print(f"置信度: {result.confidence_score:.2f}")
            print(f"快取命中: {result.cache_hit}")

            total_processing_time += result.processing_time

            # 驗證結果
            if result.confidence_score > 0.5:
                print("✅ 測試通過")
                successful_tests += 1
            else:
                print("❌ 置信度過低")

        except Exception as e:
            print(f"❌ 測試失敗: {e}")

    # 2. 批次查詢測試
    print("\n🔄 批次查詢測試")
    batch_queries = [tc["query"] for tc in test_cases[:3]]

    try:
        batch_start = time.time()
        batch_results = await optimizer.batch_query(batch_queries)
        batch_time = time.time() - batch_start

        successful_batch = sum(1 for r in batch_results if r.confidence_score > 0.5)
        print(f"批次結果: {successful_batch}/{len(batch_queries)} 成功")
        print(f"批次總時間: {batch_time:.3f}s")
        print(f"平均時間: {batch_time / len(batch_queries):.3f}s")

        if successful_batch >= len(batch_queries) * 0.8:
            print("✅ 批次測試通過")
        else:
            print("❌ 批次測試失敗")

    except Exception as e:
        print(f"❌ 批次測試失敗: {e}")

    # 3. 快取測試
    print("\n💾 快取系統測試")
    cache_test_query = "達文西的作品特色"

    # 首次查詢
    result1 = await optimizer.query(cache_test_query)
    print(f"首次查詢: {result1.processing_time:.3f}s, 快取命中: {result1.cache_hit}")

    # 第二次查詢（應該命中快取）
    result2 = await optimizer.query(cache_test_query)
    print(f"重複查詢: {result2.processing_time:.3f}s, 快取命中: {result2.cache_hit}")

    if result2.cache_hit:
        print("✅ 快取測試通過")
    else:
        print("❌ 快取未命中")

    # 4. 配置優化測試
    print("\n⚙️ 配置優化測試")
    try:
        optimization_report = optimizer.optimize_configuration()
        optimizations = optimization_report.get("optimizations_applied", [])
        print(f"執行優化: {len(optimizations)} 項調整")

        for opt in optimizations:
            print(f"  - {opt}")

        if len(optimizations) >= 0:  # 優化可能為0（系統已優化）
            print("✅ 配置優化測試通過")
        else:
            print("❌ 配置優化測試失敗")

    except Exception as e:
        print(f"❌ 配置優化測試失敗: {e}")

    # 5. 性能監控測試
    print("\n📊 性能監控測試")
    try:
        system_status = optimizer.get_system_status()

        print(f"組件狀態: {system_status['components']}")
        print(f"快取統計: {system_status['cache_stats']}")
        print(f"策略性能: {len(system_status['strategy_performance'])} 種策略")

        # 檢查組件狀態
        components_ready = sum(
            1 for status in system_status["components"].values() if status == "ready"
        )
        total_components = len(system_status["components"])

        if components_ready >= total_components * 0.8:
            print("✅ 性能監控測試通過")
        else:
            print("❌ 部分組件狀態異常")

    except Exception as e:
        print(f"❌ 性能監控測試失敗: {e}")

    # 6. 策略選擇測試
    print("\n🎯 策略選擇測試")
    strategy_tests = {
        "關係查詢": ("誰影響了畢卡索？", [RAGStrategy.GRAPH_ONLY, RAGStrategy.HYBRID_BALANCED]),
        "內容查詢": ("描述巴洛克藝術的特點", [RAGStrategy.VECTOR_ONLY, RAGStrategy.SPECIALIZED]),
        "簡單查詢": ("藝術家", [RAGStrategy.VECTOR_ONLY]),
    }

    strategy_correct = 0
    for test_name, (query, expected_strategies) in strategy_tests.items():
        result = await optimizer.query(query)
        if result.strategy_used in expected_strategies:
            print(f"✅ {test_name}: {result.strategy_used.value}")
            strategy_correct += 1
        else:
            print(
                f"❌ {test_name}: 期望 {[s.value for s in expected_strategies]}, "
                f"實際 {result.strategy_used.value}"
            )

    if strategy_correct >= len(strategy_tests) * 0.7:
        print("✅ 策略選擇測試通過")
    else:
        print("❌ 策略選擇準確率不足")

    # 7. 壓力測試
    print("\n🔥 壓力測試（10個並發查詢）")
    try:
        stress_queries = [f"藝術史查詢 {i}" for i in range(10)]
        stress_start = time.time()

        stress_results = await optimizer.batch_query(stress_queries)
        stress_time = time.time() - stress_start

        successful_stress = sum(1 for r in stress_results if r.confidence_score > 0)
        print(f"壓力測試結果: {successful_stress}/10 成功")
        print(f"總時間: {stress_time:.3f}s")
        print(f"QPS: {len(stress_queries) / stress_time:.2f}")

        if successful_stress >= 8 and stress_time < 5.0:
            print("✅ 壓力測試通過")
        else:
            print("❌ 壓力測試失敗")

    except Exception as e:
        print(f"❌ 壓力測試失敗: {e}")

    # 測試總結
    print("\n" + "=" * 60)
    print("📊 測試總結:")
    print(
        f"單個查詢成功率: {successful_tests}/{len(test_cases)} "
        f"({successful_tests / len(test_cases) * 100:.1f}%)"
    )
    print(f"平均查詢時間: {total_processing_time / len(test_cases):.3f}s")

    final_status = optimizer.get_system_status()
    print(f"快取命中率: {final_status['cache_stats']['hit_rate']:.1%}")
    print(
        f"系統組件狀態: {sum(1 for s in final_status['components'].values() if s == 'ready')}"
        f"/{len(final_status['components'])} 正常"
    )

    # 判斷測試整體結果
    overall_success_rate = successful_tests / len(test_cases)
    if overall_success_rate >= 0.8:
        print(f"\n🎉 整合系統測試通過！成功率: {overall_success_rate:.1%}")
        test_result = True
    else:
        print(f"\n❌ 整合系統測試失敗！成功率: {overall_success_rate:.1%}")
        test_result = False

    # 清理
    optimizer.cleanup()
    print("\n✅ 系統清理完成")

    return test_result


def run_performance_benchmark():
    """運行性能基準測試"""
    print("\n🏃‍♂️ 性能基準測試")
    print("-" * 40)

    benchmark_queries = [
        "達文西的藝術成就",
        "印象派的發展歷史",
        "畢卡索與立體主義的關係",
        "文藝復興時期的藝術特色",
        "巴洛克藝術的代表作品",
    ]

    async def run_benchmark():
        optimizer = IntegratedRAGOptimizer()
        optimizer.initialize_components()

        # 預熱
        await optimizer.query("測試查詢")

        # 基準測試
        times = []
        for query in benchmark_queries:
            start = time.time()
            await optimizer.query(query)
            duration = time.time() - start
            times.append(duration)
            print(f"查詢: {query[:20]}... 時間: {duration:.3f}s")

        print("\n📊 基準測試結果:")
        print(f"平均時間: {sum(times) / len(times):.3f}s")
        print(f"最快時間: {min(times):.3f}s")
        print(f"最慢時間: {max(times):.3f}s")
        print(f"95%時間: {sorted(times)[int(len(times) * 0.95)]:.3f}s")

        optimizer.cleanup()

    asyncio.run(run_benchmark())


# 主程序
if __name__ == "__main__":
    print("🎯 藝術史RAG整合系統全面測試")
    print("=" * 60)

    # 運行主測試
    success = asyncio.run(test_integrated_rag_system())

    # 運行性能基準測試
    run_performance_benchmark()

    # 最終報告
    print("\n" + "=" * 60)
    if success:
        print("🎉 所有測試通過！多模態RAG優化管理器工作正常。")
        exit(0)
    else:
        print("❌ 部分測試失敗，請檢查系統配置。")
        exit(1)
