#!/usr/bin/env python3
"""
RL-Agentic RAG API Server
提供 HTTP API 接口用於查詢和監控
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 添加項目路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 導入 RL Agent（使用簡化版本，避免 PyTorch 依賴問題）
try:
    from rl_agentic_rag import RLAgenticRAG

    USE_FULL_VERSION = True
except ImportError:
    # 如果完整版本不可用，使用簡化版本
    from rl_simple_test import SimpleRLAgent as RLAgenticRAG

    USE_FULL_VERSION = False

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 初始化 FastAPI
app = FastAPI(
    title="RL-Agentic RAG API",
    description="強化學習驅動的 Agentic RAG 策略選擇服務",
    version="1.0.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局 Agent 實例
agent: RLAgenticRAG | None = None
agent_config = {
    "model_path": os.getenv("RL_MODEL_PATH", "models/rl/rl_agent_final.pt"),
    "config_path": os.getenv("RL_CONFIG_PATH", "agents/rl/rl_config.yaml"),
    "training_mode": os.getenv("RL_TRAINING_MODE", "false").lower() == "true",
}


# Pydantic 模型
class QueryRequest(BaseModel):
    query: str = Field(..., description="查詢文本")
    context: dict[str, Any] = Field(default_factory=dict, description="上下文信息")
    training: bool = Field(default=False, description="是否在訓練模式")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "介紹文藝復興時期的藝術特色",
                "context": {"user_expertise": 0.5, "time_of_day": 14, "device_type": 0},
                "training": False,
            }
        }


class QueryResponse(BaseModel):
    query: str
    strategy: str
    action: int
    confidence: float
    reward: float
    processing_time: float
    epsilon: float | None = None
    model_version: str


class StatsResponse(BaseModel):
    total_queries: int
    training_steps: int
    epsilon: float
    average_reward: float
    action_distribution: dict[str, int]
    model_version: str
    training_mode: bool


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: str
    training_mode: bool


class FeedbackRequest(BaseModel):
    query: str
    strategy: str
    user_satisfaction: float = Field(..., ge=0.0, le=1.0)
    actual_processing_time: float | None = None


# 初始化 Agent
@app.on_event("startup")
async def startup_event():
    """啟動時初始化 Agent"""
    global agent

    logger.info("=" * 70)
    logger.info("🚀 RL-Agentic RAG Server 啟動中...")
    logger.info(f"使用版本: {'完整版 (PyTorch)' if USE_FULL_VERSION else '簡化版 (NumPy)'}")
    logger.info("=" * 70)

    try:
        # 初始化 Agent
        if USE_FULL_VERSION:
            agent = RLAgenticRAG()

            # 嘗試載入模型
            model_path = agent_config["model_path"]
            if os.path.exists(model_path):
                agent.load(model_path)
                logger.info(f"✅ 成功載入模型: {model_path}")
            else:
                logger.warning(f"⚠️  模型文件不存在: {model_path}")
                logger.info("將使用未訓練的新模型")

            # 設置訓練模式
            agent.is_training = agent_config["training_mode"]
            if not agent.is_training:
                agent.epsilon = 0.0  # 推理模式不探索
        else:
            # 簡化版本
            agent = RLAgenticRAG()
            logger.info("✅ 使用簡化版本 (純 NumPy)")

        logger.info(f"訓練模式: {agent_config['training_mode']}")
        logger.info("✅ RL Agent 初始化完成")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"❌ Agent 初始化失敗: {e}")
        raise


# API 端點
@app.get("/", tags=["Root"])
async def root():
    """根端點"""
    return {
        "service": "RL-Agentic RAG API",
        "version": "1.0.0",
        "status": "running",
        "model_version": "simplified" if not USE_FULL_VERSION else "full",
        "endpoints": {
            "query": "/query",
            "stats": "/stats",
            "health": "/health",
            "feedback": "/feedback",
        },
    }


@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
async def health_check():
    """健康檢查"""
    return HealthResponse(
        status="healthy" if agent is not None else "unhealthy",
        model_loaded=agent is not None,
        model_version="simplified" if not USE_FULL_VERSION else "full",
        training_mode=agent_config["training_mode"],
    )


@app.post("/query", response_model=QueryResponse, tags=["Query"])
async def query_endpoint(request: QueryRequest):
    """
    執行查詢並獲取 RL Agent 推薦的策略

    - **query**: 查詢文本
    - **context**: 上下文信息（用戶專業度、時間等）
    - **training**: 是否在訓練模式下運行
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent 未初始化")

    try:
        # 執行查詢
        if USE_FULL_VERSION:
            result = await agent.query(request.query, request.context)
        else:
            # 簡化版本是同步的
            result = agent.query(request.query, request.context)

        # 構建響應
        response = QueryResponse(
            query=result["query"],
            strategy=result["strategy"],
            action=result["action"],
            confidence=result.get("confidence", 0.0),
            reward=result["reward"],
            processing_time=result["processing_time"],
            epsilon=result.get("epsilon"),
            model_version="simplified" if not USE_FULL_VERSION else "full",
        )

        logger.info(f"查詢: {request.query[:50]}... -> 策略: {result['strategy']}")

        return response

    except Exception as e:
        logger.error(f"查詢處理失敗: {e}")
        raise HTTPException(status_code=500, detail="查詢處理失敗") from e


@app.get("/stats", response_model=StatsResponse, tags=["Monitoring"])
async def get_stats():
    """獲取統計信息"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent 未初始化")

    try:
        stats = agent.get_stats()

        return StatsResponse(
            total_queries=stats["total_queries"],
            training_steps=stats.get("training_steps", 0),
            epsilon=stats["epsilon"],
            average_reward=stats["average_reward"],
            action_distribution=stats["action_distribution"],
            model_version="simplified" if not USE_FULL_VERSION else "full",
            training_mode=agent_config["training_mode"],
        )

    except Exception as e:
        logger.error(f"獲取統計信息失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取統計信息失敗") from e


@app.post("/feedback", tags=["Training"])
async def submit_feedback(request: FeedbackRequest, background_tasks: BackgroundTasks):
    """
    提交用戶反饋，用於在線學習

    - **query**: 原始查詢
    - **strategy**: 使用的策略
    - **user_satisfaction**: 用戶滿意度 (0-1)
    - **actual_processing_time**: 實際處理時間
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent 未初始化")

    if not agent_config["training_mode"]:
        return {"status": "ignored", "message": "訓練模式未啟用，反饋被忽略"}

    try:
        # TODO: 實現反饋處理邏輯
        # 這裡可以將反饋存儲到經驗回放緩衝池，用於後續訓練

        logger.info(f"收到反饋: {request.query[:50]}... 滿意度: {request.user_satisfaction}")

        return {"status": "accepted", "message": "反饋已接收，將用於模型優化"}

    except Exception as e:
        logger.error(f"處理反饋失敗: {e}")
        raise HTTPException(status_code=500, detail="處理反饋失敗") from e


@app.post("/save_model", tags=["Training"])
async def save_model():
    """保存當前模型"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent 未初始化")

    if not USE_FULL_VERSION:
        return {"status": "skipped", "message": "簡化版本不支持模型保存"}

    try:
        save_path = agent_config["model_path"]
        agent.save(save_path)

        logger.info(f"✅ 模型已保存: {save_path}")

        return {"status": "success", "path": save_path, "message": "模型保存成功"}

    except Exception as e:
        logger.error(f"保存模型失敗: {e}")
        raise HTTPException(status_code=500, detail="保存模型失敗") from e


if __name__ == "__main__":
    # 從環境變量獲取配置
    host = os.getenv("RL_SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("RL_SERVER_PORT", "8011"))
    workers = int(os.getenv("RL_SERVER_WORKERS", "1"))

    logger.info(f"啟動 RL-Agentic RAG Server on {host}:{port}")

    uvicorn.run(app, host=host, port=port, workers=workers, log_level="info")
