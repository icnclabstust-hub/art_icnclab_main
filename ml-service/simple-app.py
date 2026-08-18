#!/usr/bin/env python3
"""
簡化版CUDA ML服務（用於演示和測試）
不依賴PyTorch，模擬GPU加速功能
"""

import logging
import os
import time
import uuid
from datetime import datetime

from flask import Flask, g, jsonify, request
from flask_cors import CORS

# 配置日誌
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 創建Flask應用
app = Flask(__name__)
CORS(app)

# 模擬CUDA狀態
CUDA_AVAILABLE = os.path.exists("/usr/local/cuda/bin/nvcc")
DEVICE = "cuda:0" if CUDA_AVAILABLE else "cpu"

# 全局變數
loaded_models = {
    "art-classification": {
        "type": "classification",
        "loaded_at": datetime.now().isoformat(),
        "parameters": 110000000,  # BERT-base參數量
        "device": DEVICE,
    },
    "multilingual-bert": {
        "type": "embedding",
        "loaded_at": datetime.now().isoformat(),
        "parameters": 110000000,
        "device": DEVICE,
    },
}

training_jobs = {}


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

    def simulate_training(self):
        """模擬訓練過程"""
        import random
        import threading

        def train():
            self.status = "running"
            for epoch in range(1, self.total_epochs + 1):
                time.sleep(2)  # 模擬每個epoch的時間

                # 模擬訓練指標
                self.current_epoch = epoch
                self.current_loss = round(2.0 - epoch * 0.15 + random.uniform(-0.1, 0.1), 4)
                self.current_accuracy = round(0.5 + epoch * 0.04 + random.uniform(-0.02, 0.02), 4)
                self.progress = (epoch / self.total_epochs) * 100

                # 計算ETA
                elapsed = time.time() - self.start_time
                time_per_epoch = elapsed / epoch
                remaining_epochs = self.total_epochs - epoch
                self.eta = remaining_epochs * time_per_epoch

                logger.info(
                    f"訓練進度: Epoch {epoch}/{self.total_epochs}, "
                    f"Loss: {self.current_loss}, Accuracy: {self.current_accuracy}"
                )

            self.status = "completed"
            self.progress = 100.0
            logger.info(f"訓練完成: {self.job_id}")

        training_thread = threading.Thread(target=train)
        training_thread.daemon = True
        training_thread.start()


def get_gpu_stats():
    """獲取GPU統計資訊（模擬）"""
    if CUDA_AVAILABLE:
        return {
            "gpu_name": "NVIDIA RTX 4090",
            "gpu_load": "45.2%",
            "gpu_memory_used": "8192MB",
            "gpu_memory_total": "24576MB",
            "gpu_memory_free": "16384MB",
            "gpu_temperature": "65°C",
            "cuda_version": "12.8",
            "driver_version": "572.60",
        }
    else:
        return {
            "gpu_available": False,
            "cuda_available": CUDA_AVAILABLE,
            "message": "GPU not available, using CPU mode",
        }


def get_system_stats():
    """獲取系統統計資訊"""
    try:
        import psutil

        memory = psutil.virtual_memory()
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": memory.percent,
            "memory_used": f"{memory.used // 1024 // 1024}MB",
            "memory_total": f"{memory.total // 1024 // 1024}MB",
            "disk_usage": psutil.disk_usage("/").percent,
        }
    except ImportError:
        return {"cpu_percent": "N/A", "memory_percent": "N/A", "message": "psutil not available"}


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
    gpu_stats = get_gpu_stats()
    system_stats = get_system_stats()

    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "gpu_available": CUDA_AVAILABLE,
            "cuda_version": gpu_stats.get("cuda_version", "N/A"),
            "pytorch_version": "Simulated",
            "device": DEVICE,
            "loaded_models": list(loaded_models.keys()),
            "active_training_jobs": len(training_jobs),
            "gpu_stats": gpu_stats,
            "system_stats": system_stats,
            "service_mode": "simulation",
        }
    )


@app.route("/models/status", methods=["GET"])
def models_status():
    """模型狀態查詢"""
    return jsonify(
        {
            "success": True,
            "models": loaded_models,
            "gpu_stats": get_gpu_stats(),
            "cuda_version": "12.8",
            "cudnn_version": "8.9.0",
            "gpu_name": "NVIDIA RTX 4090" if CUDA_AVAILABLE else "CPU",
            "total_memory": "24576MB" if CUDA_AVAILABLE else "32GB",
            "available_memory": "16384MB" if CUDA_AVAILABLE else "16GB",
        }
    )


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

        # 啟動模擬訓練
        training_job.simulate_training()

        # 估算訓練時間
        estimated_time = len(training_data) * config.get("epochs", 10) * 0.1

        logger.info(f"啟動訓練作業 {job_id}: {model_type} 模型，資料量: {len(training_data)}")

        return jsonify(
            {
                "success": True,
                "job_id": job_id,
                "model_type": model_type,
                "data_size": len(training_data),
                "config": config,
                "eta": f"{estimated_time:.1f}秒",
                "status": "started",
                "device": DEVICE,
            }
        )

    except Exception as e:
        logger.error(f"啟動訓練失敗: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/train/<job_id>/progress", methods=["GET"])
def get_training_progress(job_id):
    """獲取訓練進度"""
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


@app.route("/inference", methods=["POST"])
def inference():
    """推理端點"""
    try:
        data = request.json
        texts = data.get("texts", [])
        _tasks = data.get("tasks", ["classification"])  # 模擬模式未使用，保留以記錄 API 參數
        model_version = data.get("model_version", "latest")

        if not texts:
            return jsonify({"success": False, "error": "沒有提供要分析的文本"}), 400

        start_time = time.time()

        # 模擬推理過程
        results = []
        for _i, text in enumerate(texts):
            # 模擬不同的分類結果
            periods = ["古代", "中世紀", "文藝復興", "巴洛克", "現代", "當代"]
            styles = ["寫實主義", "印象派", "表現主義", "立體派", "抽象主義"]
            regions = ["歐洲", "亞洲", "美洲", "非洲", "大洋洲"]
            mediums = ["油畫", "水彩", "雕塑", "版畫", "攝影"]

            import random

            result = {
                "text": text,
                "predictions": {
                    "period": {
                        "label": random.choice(periods),
                        "confidence": round(random.uniform(0.7, 0.95), 3),
                    },
                    "style": {
                        "label": random.choice(styles),
                        "confidence": round(random.uniform(0.6, 0.9), 3),
                    },
                    "region": {
                        "label": random.choice(regions),
                        "confidence": round(random.uniform(0.8, 0.95), 3),
                    },
                    "medium": {
                        "label": random.choice(mediums),
                        "confidence": round(random.uniform(0.7, 0.92), 3),
                    },
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
                "gpu_time": f"{processing_time * 0.8:.3f}秒",
                "batch_size": len(texts),
                "device": DEVICE,
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

        # 基於文本內容的智能分類模擬
        classification = {}
        confidence_scores = {}

        # 關鍵字匹配邏輯
        text_lower = text.lower()

        if any(word in text_lower for word in ["文藝復興", "renaissance", "達文西", "leonardo"]):
            classification["period"] = "文藝復興"
            confidence_scores["period"] = 0.92
        elif any(word in text_lower for word in ["巴洛克", "baroque"]):
            classification["period"] = "巴洛克"
            confidence_scores["period"] = 0.88
        else:
            classification["period"] = "現代"
            confidence_scores["period"] = 0.75

        if any(word in text_lower for word in ["寫實", "肖像", "realistic", "portrait"]):
            classification["style"] = "寫實主義"
            confidence_scores["style"] = 0.85
        elif any(word in text_lower for word in ["印象", "impressionist"]):
            classification["style"] = "印象派"
            confidence_scores["style"] = 0.89
        else:
            classification["style"] = "古典主義"
            confidence_scores["style"] = 0.72

        if any(word in text_lower for word in ["歐洲", "europe", "義大利", "italy"]):
            classification["region"] = "歐洲"
            confidence_scores["region"] = 0.94
        else:
            classification["region"] = "其他"
            confidence_scores["region"] = 0.65

        if any(word in text_lower for word in ["油畫", "oil", "painting"]):
            classification["medium"] = "油畫"
            confidence_scores["medium"] = 0.91
        elif any(word in text_lower for word in ["雕塑", "sculpture"]):
            classification["medium"] = "雕塑"
            confidence_scores["medium"] = 0.87
        else:
            classification["medium"] = "混合媒材"
            confidence_scores["medium"] = 0.68

        return jsonify(
            {
                "success": True,
                "classification": classification,
                "confidence_scores": confidence_scores,
                "text_analyzed": text,
                "tasks_performed": tasks,
                "processing_device": DEVICE,
            }
        )

    except Exception as e:
        logger.error(f"藝術品分類失敗: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# 藝術史專業術語語意辭典
ART_HISTORY_SEMANTIC_DICTIONARY = {
    # 藝術風格與流派
    "印象派": ["光線", "色彩", "戶外", "瞬間", "筆觸", "自然主義", "莫內", "雷諾瓦"],
    "巴洛克": ["戲劇性", "動感", "明暗對比", "宗教", "裝飾", "卡拉瓦喬", "貝尼尼"],
    "文藝復興": ["人文主義", "透視法", "解剖學", "古典", "達文西", "米開朗基羅", "拉斐爾"],
    "抽象表現主義": ["情感", "非具象", "色彩情感", "自動技法", "波洛克", "羅斯科"],
    "立體主義": ["幾何", "多視角", "分析", "重構", "畢卡索", "布拉克"],
    # 藝術技法
    "明暗對比": ["光影", "戲劇性", "立體感", "chiaroscuro", "卡拉瓦喬"],
    "透視法": ["空間", "深度", "線性透視", "空氣透視", "布魯內萊斯基"],
    "點彩技法": ["色彩分割", "光學混合", "新印象派", "秀拉", "西涅克"],
    "濕畫法": ["油畫", "色彩融合", "柔和過渡", "alla prima", "直接畫法"],
    # 藝術主題
    "宗教題材": ["聖經", "神話", "聖母", "耶穌", "聖徒", "宗教改革"],
    "肖像畫": ["個性", "心理", "社會地位", "身份", "表情", "姿態"],
    "風景畫": ["自然", "季節", "光線", "大氣", "透視", "構圖"],
    "靜物畫": ["日常物品", "象徵", "vanitas", "質感", "光影"],
    # 時代與文化
    "古典時期": ["希臘", "羅馬", "理想美", "比例", "和諧", "柱式"],
    "中世紀": ["拜占庭", "哥德式", "羅馬式", "宗教藝術", "手抄本"],
    "現代主義": ["創新", "實驗", "打破傳統", "都市化", "工業化"],
    "後現代": ["多元", "解構", "挪用", "概念藝術", "裝置藝術"],
}


def enhance_text_with_semantic_context(text):
    """使用藝術史語意辭典增強文本理解"""
    enhanced_terms = []
    text_lower = text.lower()

    for term, related_terms in ART_HISTORY_SEMANTIC_DICTIONARY.items():
        if term in text or any(related in text_lower for related in related_terms):
            enhanced_terms.extend(related_terms)

    # 去重並返回語意增強的詞彙
    return list(set(enhanced_terms))


@app.route("/embeddings", methods=["POST"])
def generate_embeddings():
    """生成嵌入向量（語意增強版）"""
    try:
        data = request.json
        texts = data.get("texts", [])
        model = data.get("model", "multilingual-bert")

        if not texts:
            return jsonify({"success": False, "error": "沒有提供要處理的文本"}), 400

        start_time = time.time()

        # 語意增強的嵌入生成
        import hashlib
        import random

        embeddings = []
        semantic_enhancements = []

        for text in texts:
            # 獲取語意增強詞彙
            enhanced_terms = enhance_text_with_semantic_context(text)
            semantic_enhancements.append(enhanced_terms)

            # 結合原文本和語意增強詞彙生成hash
            combined_text = text + " ".join(enhanced_terms)
            text_hash = hashlib.md5(combined_text.encode(), usedforsecurity=False).hexdigest()

            # 使用增強hash作為隨機種子
            random.seed(text_hash)

            # 生成基礎嵌入
            embedding = [random.gauss(0, 1) for _ in range(768)]

            # 如果有語意增強，調整嵌入向量
            if enhanced_terms:
                # 為每個增強詞彙添加語意權重
                for _i, term in enumerate(enhanced_terms[:10]):  # 限制前10個詞彙
                    term_hash = hashlib.md5(term.encode(), usedforsecurity=False).hexdigest()
                    random.seed(term_hash)
                    weight = 0.1 + random.random() * 0.2  # 0.1-0.3的權重

                    # 在特定維度增加語意信號
                    for j in range(min(50, len(embedding))):  # 在前50維加入語意信號
                        embedding[j] += weight * random.gauss(0, 0.5)

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
                "semantic_enhancements": semantic_enhancements,
                "device": DEVICE,
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
        _include_embeddings = data.get("include_embeddings", False)  # 模擬模式未使用

        if not query_text:
            return jsonify({"success": False, "error": "沒有提供查詢文本"}), 400

        # 模擬相似性搜索結果
        similar_items = []
        scores = []

        # 基於查詢內容生成相關結果
        art_examples = [
            {
                "title": "蒙娜麗莎",
                "description": "達文西的經典肖像畫作品",
                "period": "文藝復興",
                "style": "寫實主義",
            },
            {
                "title": "星空",
                "description": "梵谷的印象派代表作",
                "period": "後印象派",
                "style": "表現主義",
            },
            {
                "title": "思想者",
                "description": "羅丹的著名雕塑作品",
                "period": "現代",
                "style": "寫實主義",
            },
            {
                "title": "大衛像",
                "description": "米開朗基羅的雕塑傑作",
                "period": "文藝復興",
                "style": "古典主義",
            },
            {
                "title": "睡蓮",
                "description": "莫奈的印象派風景畫",
                "period": "印象派",
                "style": "印象主義",
            },
            {
                "title": "格爾尼卡",
                "description": "畢卡索的立體派代表作",
                "period": "現代",
                "style": "立體派",
            },
            {
                "title": "吶喊",
                "description": "蒙克的表現主義名作",
                "period": "現代",
                "style": "表現主義",
            },
            {
                "title": "維納斯的誕生",
                "description": "波提切利的文藝復興作品",
                "period": "文藝復興",
                "style": "古典主義",
            },
        ]

        for i, item in enumerate(art_examples[:top_k]):
            similar_items.append(
                {
                    "id": f"artwork_{i + 1}",
                    "title": item["title"],
                    "description": item["description"],
                    "metadata": {
                        "period": item["period"],
                        "style": item["style"],
                        "region": "歐洲",
                    },
                }
            )
            # 根據相關性計算分數（簡化版本）
            base_score = 0.95 - i * 0.08
            if any(word in query_text.lower() for word in item["title"].lower().split()):
                base_score += 0.1
            scores.append(round(max(0.1, base_score), 2))

        return jsonify(
            {
                "success": True,
                "query_text": query_text,
                "similar_items": similar_items,
                "scores": scores,
                "top_k": len(similar_items),
                "search_time": "0.045秒",
            }
        )

    except Exception as e:
        logger.error(f"相似性搜索失敗: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify(
        {
            "success": False,
            "error": "API端點不存在",
            "message": f"請求的路徑不存在: {request.path}",
            "available_endpoints": [
                "/health",
                "/models/status",
                "/train",
                "/inference",
                "/classify/artwork",
                "/embeddings",
                "/similarity/search",
            ],
        }
    ), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "error": "內部服務器錯誤", "message": str(error)}), 500


# 多模態RAG端點
@app.route("/image/features", methods=["POST"])
def extract_image_features():
    """圖像特徵提取"""
    try:
        data = request.json
        _image_path = data.get("image_path", "")  # 模擬模式未使用

        # 模擬圖像特徵提取
        import random

        features = [random.uniform(-1, 1) for _ in range(2048)]

        return jsonify(
            {
                "success": True,
                "features": features,
                "feature_dim": len(features),
                "model": "resnet50",
                "processing_time": 0.05,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/classify/artwork-style", methods=["POST"])
def classify_artwork_style():
    """藝術風格分類"""
    try:
        data = request.json
        image_path = data.get("image_path", "")

        # 模擬風格分類
        styles = ["印象派", "現代", "古典", "抽象", "寫實"]
        predicted_style = styles[hash(image_path) % len(styles)]
        confidence = 0.6 + (hash(image_path) % 40) / 100.0

        return jsonify(
            {
                "success": True,
                "style_prediction": predicted_style,
                "confidence_score": confidence,
                "all_scores": {style: 0.1 + (hash(style) % 80) / 100.0 for style in styles},
                "processing_time": 0.1,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def generate_detailed_art_response(question, enhanced_terms):
    """基於語意增強生成詳細的藝術史回應"""

    # 專業藝術史知識庫
    knowledge_base = {
        "印象派": {
            "definition": "印象派是19世紀下半葉興起於法國的藝術運動，"
            "以捕捉光線和色彩的瞬間變化為特色。",
            "characteristics": [
                "強調光線和色彩的變化效果，特別是自然光線下的色彩表現",
                "採用快速、可見的筆觸技法，不追求過度的細節描繪",
                "偏好戶外寫生（plein air），直接面對自然創作",
                "描繪日常生活場景，如咖啡館、街道、花園等現代都市生活",
                "色彩明亮純淨，避免使用黑色和棕色等暗色調",
                "注重視覺印象勝過精確的形體描繪",
            ],
            "key_artists": [
                "莫內 (Claude Monet)",
                "雷諾瓦 (Pierre-Auguste Renoir)",
                "德加 (Edgar Degas)",
                "畢沙羅 (Camille Pissarro)",
            ],
            "representative_works": [
                "《日出印象》",
                "《睡蓮》系列",
                "《煎餅磨坊的舞會》",
                "《芭蕾舞排練》",
            ],
            "historical_context": "印象派的出現與19世紀工業革命、都市化進程"
            "以及攝影技術的發明密切相關，藝術家們開始探索新的視覺表達方式。",
        },
        "文藝復興": {
            "definition": "文藝復興是14-16世紀歐洲的文化運動，以復興古典文化和人文主義精神為核心。",
            "characteristics": [
                "重視人文主義思想，強調人的價值和理性",
                "發展線性透視法，創造三維空間的錯覺",
                "深入研究人體解剖學，追求準確的人體比例",
                "復興古典希臘羅馬的美學理念",
                "宗教題材與世俗題材並重",
                "追求理想化的美和和諧的構圖",
            ],
            "key_artists": [
                "達文西 (Leonardo da Vinci)",
                "米開朗基羅 (Michelangelo)",
                "拉斐爾 (Raphael)",
                "多納泰羅 (Donatello)",
            ],
            "representative_works": [
                "《蒙娜麗莎》",
                "《大衛像》",
                "《雅典學院》",
                "《維納斯的誕生》",
            ],
            "historical_context": "文藝復興始於義大利，受到拜占庭學者西遷、"
            "古典文獻重新發現以及商業繁榮的推動。",
        },
        "巴洛克": {
            "definition": "巴洛克藝術興起於17世紀，以戲劇性、動感和豐富裝飾為特色的藝術風格。",
            "characteristics": [
                "強烈的明暗對比（chiaroscuro），創造戲劇性效果",
                "充滿動感和張力的構圖",
                "豐富的裝飾性元素",
                "情感表達強烈而直接",
                "空間感強烈，常用對角線構圖",
                "宗教題材與權力展示並重",
            ],
            "key_artists": [
                "卡拉瓦喬 (Caravaggio)",
                "貝尼尼 (Bernini)",
                "魯本斯 (Rubens)",
                "委拉斯奎茲 (Velázquez)",
            ],
            "representative_works": [
                "《聖馬太蒙召》",
                "《大衛像》(貝尼尼版)",
                "《瑪麗·德·美第奇組畫》",
                "《宮娥》",
            ],
            "historical_context": "巴洛克藝術是天主教反宗教改革的產物，"
            "同時也反映了絕對君主制的權力美學。",
        },
    }

    # 根據問題和語意增強詞彙生成回應
    response_parts = []

    # 識別主要藝術概念
    main_concepts = []
    for concept in knowledge_base.keys():
        if concept in question or any(
            term in enhanced_terms for term in knowledge_base[concept]["key_artists"]
        ):
            main_concepts.append(concept)

    # 如果沒有直接匹配，基於語意增強詞彙推斷
    if not main_concepts:
        for concept, info in knowledge_base.items():
            concept_terms = info["key_artists"] + [concept]
            if any(term in enhanced_terms for term in concept_terms):
                main_concepts.append(concept)

    # 生成詳細回應
    if main_concepts:
        for concept in main_concepts[:2]:  # 限制最多兩個主要概念
            info = knowledge_base[concept]

            response_parts.append(f"**{concept}**")
            response_parts.append(info["definition"])

            response_parts.append("\n**主要特色：**")
            for char in info["characteristics"][:4]:  # 限制特色數量
                response_parts.append(f"• {char}")

            response_parts.append(f"\n**代表藝術家：** {', '.join(info['key_artists'][:3])}")

            if info["representative_works"]:
                response_parts.append(
                    f"**代表作品：** {', '.join(info['representative_works'][:3])}"
                )

            response_parts.append(f"\n**歷史背景：** {info['historical_context']}")

            if len(main_concepts) > 1:
                response_parts.append("\n" + "-" * 40 + "\n")

    # 如果有語意增強但沒有匹配主要概念，生成基於語意的回應
    elif enhanced_terms:
        response_parts.append(f"根據您的問題「{question}」，這涉及以下藝術史概念：")

        # 分析語意增強詞彙
        style_terms = [
            term
            for term in enhanced_terms
            if term in ["光線", "色彩", "筆觸", "明暗對比", "透視法"]
        ]
        artist_terms = [
            term for term in enhanced_terms if term in ["莫內", "達文西", "米開朗基羅", "卡拉瓦喬"]
        ]
        period_terms = [term for term in enhanced_terms if term in ["古典", "現代主義", "宗教"]]

        if style_terms:
            response_parts.append(f"\n**技法特色：** {', '.join(style_terms)}")
            response_parts.append("這些技法代表了不同藝術時期的創新和發展。")

        if artist_terms:
            response_parts.append(f"\n**相關藝術家：** {', '.join(artist_terms)}")

        if period_terms:
            response_parts.append(f"\n**時代背景：** {', '.join(period_terms)}")

    # 兜底回應
    if not response_parts:
        response_parts = [
            f"關於「{question}」的藝術史問題，這是一個複雜的主題，涉及多個層面的理解：",
            "\n**藝術史研究通常包含：**",
            "• 風格分析：了解不同時期的視覺特色和技法發展",
            "• 歷史背景：探討社會、文化、宗教對藝術的影響",
            "• 藝術家研究：分析個別創作者的風格演變和貢獻",
            "• 主題研究：理解不同題材在藝術史中的意義和演變",
            "\n建議參考專業藝術史資料，結合具體作品分析以獲得更深入的理解。",
        ]

    return "\n".join(response_parts)


@app.route("/rag/generate", methods=["POST"])
def rag_generate():
    """RAG智能生成（語意增強版）"""
    try:
        data = request.json
        question = data.get("question", "")

        # 使用語意增強分析問題
        enhanced_terms = enhance_text_with_semantic_context(question)

        # 生成詳細回應
        response_text = generate_detailed_art_response(question, enhanced_terms)

        # 計算回應品質指標
        word_count = len(response_text.split())
        has_structure = "**" in response_text or "•" in response_text
        has_examples = any(
            artist in response_text for artist in ["莫內", "達文西", "米開朗基羅", "卡拉瓦喬"]
        )

        confidence = 0.7
        if word_count > 50:
            confidence += 0.1
        if has_structure:
            confidence += 0.1
        if has_examples:
            confidence += 0.1
        if enhanced_terms:
            confidence += 0.05

        return jsonify(
            {
                "success": True,
                "generated_text": response_text,
                "word_count": word_count,
                "confidence": round(confidence, 2),
                "semantic_enhancements": enhanced_terms,
                "retrieval_results": len(enhanced_terms),
                "generation_time": 0.3,
                "quality_indicators": {
                    "has_structure": has_structure,
                    "has_examples": has_examples,
                    "semantic_depth": len(enhanced_terms),
                },
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/rag/multimodal-generate", methods=["POST"])
def multimodal_generate():
    """多模態描述生成"""
    try:
        data = request.json
        text_input = data.get("text_input", "")
        _image_features = data.get("image_features", [])  # 模擬模式未使用

        # 模擬多模態描述生成
        descriptions = [
            "這幅作品展現了精湛的色彩運用技法，構圖均衡，筆觸細膩。畫家運用明暗對比營造出強烈的視覺效果，體現了該時期的藝術風格特色。",
            "作品中的光影處理極為出色，色彩層次豐富，展現了藝術家對於自然光線的深刻理解。整體構圖穩重而富有動感。",
            "這是一件具有濃郁時代特色的藝術品，技法純熟，風格鮮明。藝術家巧妙地運用色彩和線條，創造出獨特的美感體驗。",
        ]

        selected_description = descriptions[hash(text_input) % len(descriptions)]

        return jsonify(
            {
                "success": True,
                "description": selected_description,
                "confidence": 0.78,
                "modality_weights": {"text": 0.6, "image": 0.4},
                "processing_time": 0.15,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/rag/recommend", methods=["POST"])
def rag_recommend():
    """個性化推薦"""
    try:
        data = request.json
        user_profile = data.get("user_profile", {})
        count = data.get("count", 5)

        # 模擬個性化推薦
        artworks = [
            {"title": "睡蓮", "artist": "莫內", "period": "印象派", "confidence_score": 0.92},
            {"title": "星夜", "artist": "梵高", "period": "後印象派", "confidence_score": 0.88},
            {"title": "日出印象", "artist": "莫內", "period": "印象派", "confidence_score": 0.85},
            {"title": "向日葵", "artist": "梵高", "period": "後印象派", "confidence_score": 0.82},
            {
                "title": "草地上的午餐",
                "artist": "馬內",
                "period": "印象派",
                "confidence_score": 0.79,
            },
        ]

        recommendations = artworks[:count]

        return jsonify(
            {
                "success": True,
                "recommendations": recommendations,
                "recommendation_strategy": "interest_based",
                "user_interests": user_profile.get("interests", []),
                "processing_time": 0.08,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    logger.info("🚀 啟動CUDA ML服務 (簡化版)...")
    logger.info(f"🎮 CUDA可用: {CUDA_AVAILABLE}")
    logger.info(f"⚡ 設備: {DEVICE}")
    logger.info("🧠 服務模式: 模擬模式 (Simulation)")

    if CUDA_AVAILABLE:
        logger.info("✅ 檢測到CUDA環境")
    else:
        logger.info("ℹ️ 未檢測到CUDA環境，使用CPU模擬")

    logger.info("🔗 服務將在 http://127.0.0.1:8080 啟動")

    # F-01 [MUST]：生產啟動不得開 debug。debug=True 會啟用 Werkzeug 除錯器，
    # 任何能連到本服務的人都可在例外頁面上執行任意 Python。
    # 與 app.py 的啟動方式對齊：預設關閉，需要時才用環境變數開啟。
    app.run(
        host="127.0.0.1",
        port=8080,
        debug=os.getenv("FLASK_DEBUG", "False").lower() == "true",
        threaded=True,
    )
