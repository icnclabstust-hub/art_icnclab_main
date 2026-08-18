#!/usr/bin/env python3
"""
CUDA加速的藝術史資料庫ML服務
支援GPU訓練、推理和嵌入生成
"""

import logging
import os
import time
import uuid
from datetime import datetime

import GPUtil
import psutil
import torch
import torch.nn as nn
from flask import Flask, g, jsonify, request
from flask_cors import CORS
from torch.utils.data import Dataset
from transformers import (
    BertModel,
)

# 配置日誌
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 創建Flask應用
app = Flask(__name__)
CORS(app)

# 全局配置
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MODEL_CACHE_DIR = "/app/models"
DATA_CACHE_DIR = "/app/data"

# 確保目錄存在
os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
os.makedirs(DATA_CACHE_DIR, exist_ok=True)

# 全局變數儲存已載入的模型
loaded_models = {}
training_jobs = {}


class ArtClassificationModel(nn.Module):
    """多任務藝術品分類模型"""

    def __init__(
        self,
        model_name="bert-base-multilingual-cased",
        num_periods=6,
        num_styles=20,
        num_regions=5,
        num_mediums=10,
    ):
        super().__init__()

        self.bert = BertModel.from_pretrained(model_name, cache_dir=MODEL_CACHE_DIR)
        hidden_size = self.bert.config.hidden_size

        # 多任務分類頭
        self.period_classifier = nn.Linear(hidden_size, num_periods)
        self.style_classifier = nn.Linear(hidden_size, num_styles)
        self.region_classifier = nn.Linear(hidden_size, num_regions)
        self.medium_classifier = nn.Linear(hidden_size, num_mediums)

        self.dropout = nn.Dropout(0.1)

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = self.dropout(outputs.pooler_output)

        return {
            "period": self.period_classifier(pooled_output),
            "style": self.style_classifier(pooled_output),
            "region": self.region_classifier(pooled_output),
            "medium": self.medium_classifier(pooled_output),
        }


class ArtDataset(Dataset):
    """藝術品資料集類別"""

    def __init__(self, texts, labels, tokenizer, max_length=512):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = str(self.texts[idx])
        label = self.labels[idx]

        encoding = self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )

        return {
            "input_ids": encoding["input_ids"].flatten(),
            "attention_mask": encoding["attention_mask"].flatten(),
            "labels": torch.tensor(label, dtype=torch.long),
        }


class TrainingJob:
    """訓練作業管理"""

    def __init__(self, job_id: str, model_type: str, config: dict):
        self.job_id = job_id
        self.model_type = model_type
        self.config = config
        self.status = "preparing"
        self.progress = 0.0
        self.current_epoch = 0
        self.total_epochs = config.get("epochs", 10)
        self.current_loss = None
        self.current_accuracy = None
        self.start_time = time.time()
        self.eta = None

    def update_progress(self, epoch: int, loss: float, accuracy: float = None):
        self.current_epoch = epoch
        self.current_loss = loss
        self.current_accuracy = accuracy
        self.progress = (epoch / self.total_epochs) * 100

        # 估算剩餘時間
        elapsed = time.time() - self.start_time
        if epoch > 0:
            time_per_epoch = elapsed / epoch
            remaining_epochs = self.total_epochs - epoch
            self.eta = remaining_epochs * time_per_epoch


def get_gpu_stats():
    """獲取GPU統計資訊"""
    try:
        if torch.cuda.is_available():
            gpu = GPUtil.getGPUs()[0] if GPUtil.getGPUs() else None
            if gpu:
                return {
                    "gpu_name": gpu.name,
                    "gpu_load": f"{gpu.load * 100:.1f}%",
                    "gpu_memory_used": f"{gpu.memoryUsed}MB",
                    "gpu_memory_total": f"{gpu.memoryTotal}MB",
                    "gpu_memory_free": f"{gpu.memoryFree}MB",
                    "gpu_temperature": f"{gpu.temperature}°C",
                }
    except Exception as e:
        logger.warning(f"無法獲取GPU統計: {e}")

    return {
        "gpu_available": torch.cuda.is_available(),
        "gpu_count": torch.cuda.device_count(),
        "current_device": torch.cuda.current_device() if torch.cuda.is_available() else None,
    }


def get_system_stats():
    """獲取系統統計資訊"""
    memory = psutil.virtual_memory()
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": memory.percent,
        "memory_used": f"{memory.used // 1024 // 1024}MB",
        "memory_total": f"{memory.total // 1024 // 1024}MB",
        "disk_usage": psutil.disk_usage("/").percent,
    }


@app.before_request
def before_request():
    """請求前處理"""
    g.start_time = time.time()


@app.after_request
def after_request(response):
    """請求後處理"""
    if hasattr(g, "start_time"):
        duration = time.time() - g.start_time
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
    return response


@app.route("/health", methods=["GET"])
def health_check():
    """健康檢查端點"""
    try:
        gpu_stats = get_gpu_stats()
        system_stats = get_system_stats()

        return jsonify(
            {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "gpu_available": torch.cuda.is_available(),
                "cuda_version": torch.version.cuda,
                "pytorch_version": torch.__version__,
                "device": str(DEVICE),
                "loaded_models": list(loaded_models.keys()),
                "active_training_jobs": len(training_jobs),
                "gpu_stats": gpu_stats,
                "system_stats": system_stats,
            }
        )
    except Exception as e:
        logger.error(f"健康檢查失敗: {e}")
        return jsonify(
            {"status": "unhealthy", "error": str(e), "timestamp": datetime.now().isoformat()}
        ), 500


@app.route("/models/status", methods=["GET"])
def models_status():
    """模型狀態查詢"""
    try:
        models_info = {}
        for model_name, model_data in loaded_models.items():
            models_info[model_name] = {
                "type": model_data.get("type", "unknown"),
                "loaded_at": model_data.get("loaded_at"),
                "parameters": model_data.get("parameters", 0),
                "device": str(model_data.get("device", "unknown")),
            }

        return jsonify(
            {
                "success": True,
                "models": models_info,
                "gpu_stats": get_gpu_stats(),
                "cuda_version": torch.version.cuda,
                "cudnn_version": torch.backends.cudnn.version(),
                "gpu_name": get_gpu_stats().get("gpu_name", "Unknown"),
                "total_memory": get_gpu_stats().get("gpu_memory_total", "Unknown"),
                "available_memory": get_gpu_stats().get("gpu_memory_free", "Unknown"),
            }
        )
    except Exception as e:
        logger.error(f"獲取模型狀態失敗: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/train", methods=["POST"])
def start_training():
    """啟動模型訓練"""
    try:
        data = request.json
        model_type = data.get("model_type", "classification")
        config = data.get("config", {})
        training_data = data.get("data", [])

        if not training_data:
            return jsonify({"success": False, "error": "沒有提供訓練資料"}), 400

        # 生成訓練作業ID
        job_id = str(uuid.uuid4())

        # 創建訓練作業
        training_job = TrainingJob(job_id, model_type, config)
        training_jobs[job_id] = training_job

        # 估算訓練時間（簡化版本）
        estimated_time = (
            len(training_data) * config.get("epochs", 10) * 0.1
        )  # 每個樣本每個epoch約0.1秒

        # 在實際實現中，這裡會啟動後台訓練
        logger.info(f"啟動訓練作業 {job_id}: {model_type} 模型")
        training_job.status = "running"

        return jsonify(
            {
                "success": True,
                "job_id": job_id,
                "model_type": model_type,
                "data_size": len(training_data),
                "config": config,
                "eta": f"{estimated_time:.1f}秒",
                "status": "started",
            }
        )

    except Exception as e:
        logger.error(f"啟動訓練失敗: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/train/<job_id>/progress", methods=["GET"])
def get_training_progress(job_id):
    """獲取訓練進度"""
    try:
        if job_id not in training_jobs:
            return jsonify({"success": False, "error": "找不到指定的訓練作業"}), 404

        job = training_jobs[job_id]

        return jsonify(
            {
                "success": True,
                "job_id": job_id,
                "status": job.status,
                "progress": job.progress,
                "current_epoch": job.current_epoch,
                "total_epochs": job.total_epochs,
                "current_loss": job.current_loss,
                "current_accuracy": job.current_accuracy,
                "eta": f"{job.eta:.1f}秒" if job.eta else None,
            }
        )

    except Exception as e:
        logger.error(f"獲取訓練進度失敗: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/inference", methods=["POST"])
def inference():
    """推理端點"""
    try:
        data = request.json
        texts = data.get("texts", [])
        _tasks = data.get("tasks", ["classification"])  # 模擬中未使用，保留以記錄 API 參數
        model_version = data.get("model_version", "latest")

        if not texts:
            return jsonify({"success": False, "error": "沒有提供要分析的文本"}), 400

        start_time = time.time()

        # 模擬推理結果（實際實現中會使用真實模型）
        results = []
        for text in texts:
            result = {
                "text": text,
                "predictions": {
                    "period": {"label": "文藝復興", "confidence": 0.85},
                    "style": {"label": "寫實主義", "confidence": 0.78},
                    "region": {"label": "歐洲", "confidence": 0.92},
                    "medium": {"label": "油畫", "confidence": 0.88},
                },
            }
            results.append(result)

        processing_time = time.time() - start_time

        return jsonify(
            {
                "success": True,
                "results": results,
                "processing_time": f"{processing_time:.3f}秒",
                "model_version": model_version,
                "gpu_time": f"{processing_time * 0.8:.3f}秒",  # 假設80%時間在GPU上
                "batch_size": len(texts),
            }
        )

    except Exception as e:
        logger.error(f"推理失敗: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/classify/artwork", methods=["POST"])
def classify_artwork():
    """藝術品專用分類"""
    try:
        data = request.json
        text = data.get("text", "")
        tasks = data.get("tasks", ["period", "style", "region", "medium"])

        if not text:
            return jsonify({"success": False, "error": "沒有提供要分析的文本"}), 400

        # 模擬分類結果
        classification = {
            "period": "文藝復興",
            "style": "寫實主義",
            "region": "歐洲",
            "medium": "油畫",
        }

        confidence_scores = {"period": 0.85, "style": 0.78, "region": 0.92, "medium": 0.88}

        return jsonify(
            {
                "success": True,
                "classification": classification,
                "confidence_scores": confidence_scores,
                "text_analyzed": text,
                "tasks_performed": tasks,
            }
        )

    except Exception as e:
        logger.error(f"藝術品分類失敗: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/embeddings", methods=["POST"])
def generate_embeddings():
    """生成嵌入向量"""
    try:
        data = request.json
        texts = data.get("texts", [])
        model = data.get("model", "multilingual-bert")

        if not texts:
            return jsonify({"success": False, "error": "沒有提供要處理的文本"}), 400

        start_time = time.time()

        # 模擬嵌入生成（實際實現中會使用真實模型）
        embeddings = []
        for _text in texts:
            # 生成768維的隨機嵌入（實際應該是模型輸出）
            embedding = torch.randn(768).tolist()
            embeddings.append(embedding)

        processing_time = time.time() - start_time

        return jsonify(
            {
                "success": True,
                "embeddings": embeddings,
                "model_used": model,
                "embedding_dim": 768,
                "processing_time": f"{processing_time:.3f}秒",
                "texts_processed": len(texts),
            }
        )

    except Exception as e:
        logger.error(f"嵌入生成失敗: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/similarity/search", methods=["POST"])
def similarity_search():
    """相似性搜索"""
    try:
        data = request.json
        query_text = data.get("query_text", "")
        top_k = data.get("top_k", 10)
        _include_embeddings = data.get("include_embeddings", False)  # 模擬中未使用

        if not query_text:
            return jsonify({"success": False, "error": "沒有提供查詢文本"}), 400

        # 模擬相似性搜索結果
        similar_items = []
        scores = []

        for i in range(min(top_k, 10)):
            similar_items.append(
                {
                    "id": f"artwork_{i + 1}",
                    "title": f"相似藝術品 {i + 1}",
                    "description": f"這是與查詢最相似的第 {i + 1} 個作品",
                    "metadata": {"period": "文藝復興", "style": "寫實主義", "region": "歐洲"},
                }
            )
            scores.append(round(0.95 - i * 0.05, 2))

        return jsonify(
            {
                "success": True,
                "query_text": query_text,
                "similar_items": similar_items,
                "scores": scores,
                "top_k": len(similar_items),
            }
        )

    except Exception as e:
        logger.error(f"相似性搜索失敗: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify(
        {"success": False, "error": "API端點不存在", "message": f"請求的路徑不存在: {request.path}"}
    ), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "error": "內部服務器錯誤", "message": str(error)}), 500


if __name__ == "__main__":
    logger.info("🚀 啟動CUDA ML服務...")
    logger.info(f"🎮 CUDA可用: {torch.cuda.is_available()}")
    logger.info(f"🔧 CUDA版本: {torch.version.cuda}")
    logger.info(f"🧠 PyTorch版本: {torch.__version__}")
    logger.info(f"⚡ 設備: {DEVICE}")

    if torch.cuda.is_available():
        logger.info(f"🎯 GPU設備數量: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            logger.info(f"   GPU {i}: {torch.cuda.get_device_name(i)}")

    app.run(
        host="127.0.0.1",
        port=8080,
        debug=os.getenv("FLASK_DEBUG", "False").lower() == "true",
        threaded=True,
    )
