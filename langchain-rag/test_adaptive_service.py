#!/usr/bin/env python3
"""
增強型自適應策略測試服務
提供REST API用於測試和驗證自適應RAG策略
"""

import asyncio
import logging
import os
import time
from datetime import datetime

import uvicorn

# 導入我們的增強策略
from enhanced_adaptive_strategies import (
    ContextualRAGStrategy,
    EnhancedAdaptiveManager,
    QueryContext,
)
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 配置日誌
logging.basicConfig(
    level=logging.DEBUG if os.getenv("LOG_LEVEL") == "DEBUG" else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Pydantic 模型
class TestQueryRequest(BaseModel):
    query: str = Field(..., description="測試查詢文本")
    user_id: str | None = Field(None, description="用戶ID")
    session_id: str | None = Field(None, description="會話ID")
    expected_intent: str | None = Field(None, description="預期意圖")
    simulate_multimodal: bool = Field(False, description="模擬多模態查詢")


class PerformanceFeedback(BaseModel):
    strategy: str = Field(..., description="使用的策略")
    success: bool = Field(..., description="是否成功")
    response_time: float = Field(..., description="響應時間")
    confidence: float = Field(..., description="信心度")
    user_satisfaction: float = Field(5.0, description="用戶滿意度(1-5)")


class BatchTestRequest(BaseModel):
    queries: list[str] = Field(..., description="批次測試查詢")
    test_duration: int = Field(300, description="測試持續時間(秒)")
    concurrent_users: int = Field(5, description="並發用戶數")


# FastAPI 應用
app = FastAPI(
    title="Enhanced Adaptive RAG Test Service",
    description="增強型自適應RAG策略測試服務",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 添加CORS中間件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局變數
adaptive_manager: EnhancedAdaptiveManager | None = None
test_results = []
test_stats = {
    "total_queries": 0,
    "successful_queries": 0,
    "failed_queries": 0,
    "avg_response_time": 0.0,
    "strategy_distribution": {},
}


@app.on_event("startup")
async def startup_event():
    """啟動時初始化"""
    global adaptive_manager

    try:
        logger.info("🚀 初始化增強型自適應策略管理器...")

        # 從環境變數讀取配置
        learning_rate = float(os.getenv("LEARNING_RATE", "0.15"))
        exploration_rate = float(os.getenv("EXPLORATION_RATE", "0.3"))

        adaptive_manager = EnhancedAdaptiveManager(
            learning_rate=learning_rate, exploration_rate=exploration_rate
        )

        logger.info(
            f"✅ 自適應策略管理器初始化完成 (學習率: {learning_rate}, 探索率: {exploration_rate})"
        )

    except Exception as e:
        logger.error(f"❌ 初始化失敗: {e}")
        raise


@app.get("/")
async def root():
    """根端點"""
    return {
        "service": "Enhanced Adaptive RAG Test Service",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "endpoints": [
            "/health",
            "/test/strategy",
            "/test/batch",
            "/feedback",
            "/stats",
            "/system/status",
        ],
    }


@app.get("/health")
async def health_check():
    """健康檢查"""
    if not adaptive_manager:
        raise HTTPException(status_code=503, detail="服務未初始化")

    return {
        "status": "healthy",
        "service": "adaptive-strategy-test",
        "timestamp": datetime.now().isoformat(),
        "total_queries_processed": test_stats["total_queries"],
    }


@app.post("/test/strategy")
async def test_strategy_selection(request: TestQueryRequest):
    """測試策略選擇"""
    if not adaptive_manager:
        raise HTTPException(status_code=503, detail="服務未初始化")

    start_time = time.time()

    try:
        # 構建查詢情境
        context = QueryContext(
            query_text=request.query,
            user_id=request.user_id,
            session_id=request.session_id,
            multimodal_components=["image", "text"] if request.simulate_multimodal else ["text"],
        )

        # 選擇最優策略
        selected_strategy = await adaptive_manager.select_optimal_strategy(context)

        # 獲取策略推薦詳情
        recommendation = adaptive_manager.get_strategy_recommendation(context)

        # 模擬執行結果
        processing_time = time.time() - start_time
        simulated_confidence = 0.7 + (hash(request.query) % 30) / 100.0  # 0.7-1.0

        # 更新統計
        test_stats["total_queries"] += 1
        test_stats["strategy_distribution"][selected_strategy.value] = (
            test_stats["strategy_distribution"].get(selected_strategy.value, 0) + 1
        )

        result = {
            "query": request.query,
            "selected_strategy": selected_strategy.value,
            "processing_time": processing_time,
            "simulated_confidence": simulated_confidence,
            "recommendation_details": recommendation,
            "context": {
                "user_id": context.user_id,
                "session_id": context.session_id,
                "multimodal": request.simulate_multimodal,
            },
            "timestamp": datetime.now().isoformat(),
        }

        # 記錄測試結果
        test_results.append(result)

        logger.info(
            f"🎯 策略選擇測試完成: {selected_strategy.value} (處理時間: {processing_time:.3f}s)"
        )

        return result

    except Exception as e:
        test_stats["failed_queries"] += 1
        logger.error(f"❌ 策略選擇測試失敗: {e}")
        # S-14：原文已入 log，前端只回類別訊息；B904：from e 保留例外鏈
        raise HTTPException(status_code=500, detail="測試失敗") from e


@app.post("/feedback")
async def submit_performance_feedback(feedback: PerformanceFeedback):
    """提交性能反饋"""
    if not adaptive_manager:
        raise HTTPException(status_code=503, detail="服務未初始化")

    try:
        # 將字符串策略轉換為枚舉
        strategy = ContextualRAGStrategy(feedback.strategy)

        # 構建虛擬情境（在實際應用中應該從請求中獲取）
        context = QueryContext(query_text="test_query")

        # 構建性能指標
        performance_metrics = {
            "success": feedback.success,
            "response_time": feedback.response_time,
            "confidence": feedback.confidence,
            "user_satisfaction": feedback.user_satisfaction,
        }

        # 更新策略性能
        await adaptive_manager.update_strategy_performance(strategy, context, performance_metrics)

        # 更新統計
        if feedback.success:
            test_stats["successful_queries"] += 1
        else:
            test_stats["failed_queries"] += 1

        # 更新平均響應時間
        total_queries = test_stats["total_queries"]
        if total_queries > 0:
            test_stats["avg_response_time"] = (
                test_stats["avg_response_time"] * (total_queries - 1) + feedback.response_time
            ) / total_queries

        logger.info(f"📊 性能反饋已更新: {strategy.value}")

        return {
            "success": True,
            "message": "性能反饋已記錄",
            "strategy": feedback.strategy,
            "timestamp": datetime.now().isoformat(),
        }

    except ValueError as e:
        # 策略名稱來自請求欄位而非例外原文，可回給前端；from e 保留例外鏈
        raise HTTPException(status_code=400, detail=f"無效的策略名稱: {feedback.strategy}") from e
    except Exception as e:
        logger.error(f"❌ 提交反饋失敗: {e}")
        raise HTTPException(status_code=500, detail="提交反饋失敗") from e


@app.post("/test/batch")
async def batch_test(request: BatchTestRequest, background_tasks: BackgroundTasks):
    """批次測試"""
    if not adaptive_manager:
        raise HTTPException(status_code=503, detail="服務未初始化")

    def run_batch_test():
        """在背景執行批次測試"""
        logger.info(f"🔄 開始批次測試: {len(request.queries)} 個查詢, {request.test_duration}秒")

        start_time = time.time()
        test_count = 0

        while time.time() - start_time < request.test_duration:
            for query in request.queries:
                try:
                    # 模擬查詢處理
                    context = QueryContext(
                        query_text=query,
                        user_id=f"test_user_{test_count % request.concurrent_users}",
                        session_id=f"test_session_{test_count}",
                    )

                    # 選擇策略（同步調用，實際中需要使用 asyncio.run）
                    import asyncio

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    selected_strategy = loop.run_until_complete(
                        adaptive_manager.select_optimal_strategy(context)
                    )

                    # 模擬性能指標
                    simulated_metrics = {
                        "success": True,
                        "response_time": 0.1 + (hash(query) % 20) / 100.0,  # 0.1-0.3s
                        "confidence": 0.6 + (hash(query) % 40) / 100.0,  # 0.6-1.0
                        "user_satisfaction": 3.0 + (hash(query) % 20) / 10.0,  # 3.0-5.0
                    }

                    # 更新性能
                    loop.run_until_complete(
                        adaptive_manager.update_strategy_performance(
                            selected_strategy, context, simulated_metrics
                        )
                    )

                    test_count += 1
                    loop.close()

                    if time.time() - start_time >= request.test_duration:
                        break

                except Exception as e:
                    logger.error(f"批次測試錯誤: {e}")
                    continue

                # 模擬請求間隔
                time.sleep(0.1)

        logger.info(f"✅ 批次測試完成: 處理了 {test_count} 個查詢")

    background_tasks.add_task(run_batch_test)

    return {
        "success": True,
        "message": "批次測試已啟動",
        "test_config": {
            "queries_count": len(request.queries),
            "test_duration": request.test_duration,
            "concurrent_users": request.concurrent_users,
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/stats")
async def get_test_statistics():
    """獲取測試統計"""
    if not adaptive_manager:
        raise HTTPException(status_code=503, detail="服務未初始化")

    # 獲取系統狀態
    system_status = adaptive_manager.get_system_status()

    return {
        "test_statistics": test_stats,
        "system_status": system_status,
        "recent_results": test_results[-10:] if len(test_results) > 10 else test_results,
        "total_results_count": len(test_results),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/system/status")
async def get_system_status():
    """獲取詳細系統狀態"""
    if not adaptive_manager:
        raise HTTPException(status_code=503, detail="服務未初始化")

    return {
        "adaptive_manager_status": adaptive_manager.get_system_status(),
        "test_service_status": {
            "total_queries": test_stats["total_queries"],
            "success_rate": test_stats["successful_queries"] / max(test_stats["total_queries"], 1),
            "avg_response_time": test_stats["avg_response_time"],
            "strategy_distribution": test_stats["strategy_distribution"],
        },
        "environment": {
            "learning_rate": os.getenv("LEARNING_RATE", "0.15"),
            "exploration_rate": os.getenv("EXPLORATION_RATE", "0.3"),
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/system/optimize")
async def trigger_optimization(background_tasks: BackgroundTasks):
    """觸發系統優化"""
    if not adaptive_manager:
        raise HTTPException(status_code=503, detail="服務未初始化")

    def run_optimization():
        """在背景執行優化"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        optimization_result = loop.run_until_complete(
            adaptive_manager.optimize_system_performance()
        )

        logger.info(f"✅ 系統優化完成: {optimization_result}")
        loop.close()

    background_tasks.add_task(run_optimization)

    return {"success": True, "message": "系統優化已啟動", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    logger.info("🚀 啟動增強型自適應策略測試服務...")
    logger.info("📚 API文檔: http://localhost:8003/docs")
    logger.info("🔄 健康檢查: http://localhost:8003/health")

    uvicorn.run(
        "test_adaptive_service:app",
        host="127.0.0.1",
        port=8003,
        reload=os.getenv("FLASK_ENV") == "testing",
        log_level="debug" if os.getenv("LOG_LEVEL") == "DEBUG" else "info",
    )
