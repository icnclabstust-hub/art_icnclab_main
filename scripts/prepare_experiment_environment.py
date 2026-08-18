#!/usr/bin/env python3
"""
實驗環境準備腳本
設置實驗所需的目錄結構、數據文件和配置
"""

import json
import logging
import os
from pathlib import Path


def setup_directories():
    """設置實驗目錄結構"""

    directories = [
        "data/experiments",
        "data/experiments/images",
        "data/experiments/audio",
        "logs",
        "results/experiments",
        "results/reports",
    ]

    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"✅ 創建目錄: {dir_path}")


def create_sample_art_images():
    """創建樣本藝術圖像的元數據（實際圖像需要單獨準備）"""

    sample_images = {
        "monet_impression_sunrise.jpg": {
            "title": "印象·日出",
            "artist": "克勞德·莫內",
            "year": 1872,
            "style": "印象派",
            "description": "印象派運動的標誌性作品，展現了莫內對光線和色彩的革命性處理",
            "analysis_points": [
                "筆觸自由奔放",
                "色彩鮮明對比",
                "捕捉瞬間光線效果",
                "簡化的形象處理",
            ],
        },
        "rodin_thinker.jpg": {
            "title": "思想者",
            "artist": "奧古斯特·羅丹",
            "year": 1904,
            "style": "現實主義雕塑",
            "description": "羅丹最著名的雕塑作品，象徵人類的理性思考",
            "analysis_points": [
                "深思的姿態",
                "肌肉線條的精細雕刻",
                "象徵主義表達",
                "情感的外化表現",
            ],
        },
        "van_gogh_starry_night.jpg": {
            "title": "星月夜",
            "artist": "文森特·梵高",
            "year": 1889,
            "style": "後印象派",
            "description": "梵高最具代表性的作品，展現了其獨特的藝術視角",
            "analysis_points": [
                "旋渦狀的筆觸",
                "濃烈的色彩對比",
                "情感化的表現手法",
                "夢幻般的景象描繪",
            ],
        },
    }

    images_dir = Path("data/experiments/images")

    # 保存圖像元數據
    with open(images_dir / "image_metadata.json", "w", encoding="utf-8") as f:
        json.dump(sample_images, f, ensure_ascii=False, indent=2)

    # 創建佔位符文件（提醒用戶需要添加實際圖像）
    for image_name in sample_images.keys():
        placeholder_path = images_dir / f"{image_name}.placeholder"
        with open(placeholder_path, "w") as f:
            f.write(f"請將真實的 {image_name} 圖像文件放置在此位置\n")
            f.write(
                f"圖像信息: {sample_images[image_name]['title']} - {sample_images[image_name]['artist']}\n"
            )

    print(f"✅ 創建圖像元數據: {len(sample_images)} 個樣本圖像")


def create_sample_audio_data():
    """創建樣本音頻數據的元數據"""

    sample_audio = {
        "art_lecture_01.mp3": {
            "title": "文藝復興雕塑藝術講座",
            "duration": "5:30",
            "speaker": "藝術史教授",
            "transcript": "今天我們來討論文藝復興時期的雕塑藝術。文藝復興時期的雕塑家們，特別是米開朗基羅，創造了許多不朽的傑作。他們不僅掌握了精湛的技藝，更重要的是表達了人文主義的理想...",
            "key_topics": ["文藝復興", "雕塑技法", "米開朗基羅", "人文主義"],
        },
        "museum_guide_impressionism.mp3": {
            "title": "印象派展覽導覽",
            "duration": "8:15",
            "speaker": "博物館導覽員",
            "transcript": "歡迎來到印象派展廳。印象派是19世紀後半期起源於法國的藝術運動。這個運動的藝術家們試圖準確地描繪光線隨時間推移的變化對景物外貌產生的效果...",
            "key_topics": ["印象派", "光線效果", "戶外寫生", "色彩理論"],
        },
    }

    audio_dir = Path("data/experiments/audio")

    # 保存音頻元數據
    with open(audio_dir / "audio_metadata.json", "w", encoding="utf-8") as f:
        json.dump(sample_audio, f, ensure_ascii=False, indent=2)

    # 創建佔位符文件
    for audio_name in sample_audio.keys():
        placeholder_path = audio_dir / f"{audio_name}.placeholder"
        with open(placeholder_path, "w") as f:
            f.write(f"請將真實的 {audio_name} 音頻文件放置在此位置\n")
            f.write(f"音頻信息: {sample_audio[audio_name]['title']}\n")
            f.write(f"時長: {sample_audio[audio_name]['duration']}\n")

    print(f"✅ 創建音頻元數據: {len(sample_audio)} 個樣本音頻")


def create_experiment_config():
    """創建實驗配置文件"""

    config = {
        "experiment_settings": {
            "default_timeout": 30,
            "retry_attempts": 3,
            "parallel_experiments": 2,
            "save_detailed_results": True,
            "log_level": "INFO",
        },
        "rag_frameworks": {
            "vector_rag": {
                "enabled": True,
                "description": "經典向量檢索RAG",
                "default_params": {"top_k": 5, "chunk_size": 512, "overlap": 0.1},
            },
            "advanced_rag": {
                "enabled": False,
                "description": "混合檢索RAG（需要實現）",
                "default_params": {"semantic_weight": 0.7, "keyword_weight": 0.3},
            },
            "graph_rag": {
                "enabled": False,
                "description": "知識圖譜增強RAG（需要Neo4j）",
                "default_params": {
                    "graph_depth": 2,
                    "relation_types": ["influences", "created_by", "belongs_to"],
                },
            },
        },
        "llm_models": {
            "openai": {
                "enabled": True,
                "model_name": "gpt-4",
                "api_endpoint": "http://localhost:8001",
                "default_params": {"temperature": 0.3, "max_tokens": 500},
            },
            "anthropic": {
                "enabled": True,
                "model_name": "claude-3-sonnet",
                "api_endpoint": "http://localhost:8002",
                "default_params": {"temperature": 0.3, "max_tokens": 500},
            },
            "ollama": {
                "enabled": False,
                "model_name": "llama2",
                "api_endpoint": "http://localhost:11434",
                "note": "需要本地部署Ollama服務",
            },
        },
        "vector_databases": {
            "chromadb": {
                "enabled": True,
                "endpoint": "http://localhost:8020",
                "collection_name": "art_history",
            },
            "qdrant": {
                "enabled": True,
                "endpoint": "http://localhost:6333",
                "collection_name": "art_history_qdrant",
            },
        },
    }

    config_path = Path("data/experiments/experiment_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"✅ 創建實驗配置: {config_path}")


def create_docker_compose_for_experiments():
    """創建實驗專用的Docker Compose文件"""

    docker_compose_content = """version: '3.8'

services:
  # ChromaDB向量資料庫
  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8020:8000"
    volumes:
      - chromadb_data:/chroma/chroma
    environment:
      - CHROMA_SERVER_HOST=0.0.0.0
      - CHROMA_SERVER_HTTP_PORT=8000
    networks:
      - mcp_experiment_network

  # Qdrant向量資料庫
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    networks:
      - mcp_experiment_network

  # MLflow實驗追蹤
  mlflow:
    image: python:3.9-slim
    ports:
      - "5000:5000"
    volumes:
      - mlflow_data:/mlflow
      - ./scripts:/scripts
    working_dir: /scripts
    command: >
      bash -c "pip install mlflow &&
               mlflow server --host 0.0.0.0 --port 5000 --default-artifact-root /mlflow"
    networks:
      - mcp_experiment_network

  # Grafana監控儀表板
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"  # 避免與主系統的3000端口衝突
    volumes:
      - grafana_data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
    networks:
      - mcp_experiment_network

  # Prometheus監控
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
    networks:
      - mcp_experiment_network

volumes:
  chromadb_data:
  qdrant_data:
  mlflow_data:
  grafana_data:
  prometheus_data:

networks:
  mcp_experiment_network:
    driver: bridge
"""

    with open("docker-compose.experiments.yml", "w") as f:
        f.write(docker_compose_content)

    print("✅ 創建實驗環境Docker Compose文件")


def create_prometheus_config():
    """創建Prometheus配置"""

    prometheus_config = """global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'mcp-system'
    static_configs:
      - targets: ['host.docker.internal:3000']

  - job_name: 'chromadb'
    static_configs:
      - targets: ['chromadb:8000']

  - job_name: 'qdrant'
    static_configs:
      - targets: ['qdrant:6333']
"""

    with open("../prometheus.yml", "w") as f:
        f.write(prometheus_config)

    print("✅ 創建Prometheus配置文件")


def create_startup_script():
    """創建實驗啟動腳本"""

    startup_script = """#!/bin/bash

echo "🚀 啟動藝術史RAG實驗環境..."

# 1. 啟動Docker服務
echo "📦 啟動Docker服務..."
docker-compose -f docker-compose.experiments.yml up -d

# 等待服務啟動
echo "⏳ 等待服務啟動..."
sleep 30

# 2. 檢查服務狀態
echo "🔍 檢查服務狀態..."
curl -s http://localhost:8020/api/v1/heartbeat && echo "✅ ChromaDB 運行正常"
curl -s http://localhost:6333/health && echo "✅ Qdrant 運行正常"
curl -s http://localhost:5000/health && echo "✅ MLflow 運行正常"
curl -s http://localhost:3001 && echo "✅ Grafana 運行正常"

# 3. 運行實驗
echo "🧪 開始運行實驗..."
cd src/experiments
python3 art_history_experiment_suite.py

echo "🎉 實驗環境啟動完成！"
echo "📊 Grafana 儀表板: http://localhost:3001 (admin/admin123)"
echo "📈 MLflow 實驗追蹤: http://localhost:5000"
echo "🔍 Prometheus 監控: http://localhost:9090"
"""

    with open("ops/start_experiments.sh", "w") as f:
        f.write(startup_script)

    # 使腳本可執行
    os.chmod("ops/start_experiments.sh", 0o755)

    print("✅ 創建實驗啟動腳本")


def create_readme():
    """創建實驗說明文檔"""

    readme_content = """# 藝術史多模態RAG實驗環境

## 📋 概述

這是一個完整的藝術史多模態RAG實驗環境，用於評估不同RAG架構和LLM模型在藝術史領域的性能。

## 🚀 快速開始

### 1. 環境準備

```bash
# 運行環境準備腳本
python3 scripts/prepare_experiment_environment.py

# 啟動實驗環境
./start_experiments.sh
```

### 2. 手動啟動服務

```bash
# 啟動Docker服務
docker-compose -f docker-compose.experiments.yml up -d

# 運行實驗
cd src/experiments
python3 art_history_experiment_suite.py
```

## 📊 服務訪問

- **Grafana 監控儀表板**: http://localhost:3001 (admin/admin123)
- **MLflow 實驗追蹤**: http://localhost:5000
- **Prometheus 監控**: http://localhost:9090
- **ChromaDB**: http://localhost:8020
- **Qdrant**: http://localhost:6333

## 🔬 實驗階段

### Phase 1: 基準性能測試
- 測試5種RAG框架 × 5種LLM模型 = 25種組合
- 評估指標：準確率、響應時間、成功率

### Phase 2: 多模態能力測試
- 測試文本、圖像、音頻等多模態數據處理能力
- 評估跨模態檢索和融合效果

### Phase 3: 領域專業化測試
- 測試在藝術史專業知識上的表現
- 評估複雜推理和文化語境理解能力

### Phase 4: 優化調參測試
- 基於前期結果優化最佳組合的參數
- 提供生產環境的配置建議

## 📁 目錄結構

```
art-history-database/
├── data/experiments/          # 實驗數據
│   ├── images/               # 圖像數據
│   ├── audio/                # 音頻數據
│   └── experiment_config.json # 實驗配置
├── src/experiments/          # 實驗代碼
│   └── art_history_experiment_suite.py
├── results/                  # 實驗結果
│   ├── experiments/          # 實驗數據
│   └── reports/              # 實驗報告
├── docker-compose.experiments.yml # Docker服務配置
└── start_experiments.sh      # 啟動腳本
```

## 🛠️ 故障排除

### 常見問題

1. **Docker服務啟動失敗**
   ```bash
   docker-compose -f docker-compose.experiments.yml logs
   ```

2. **端口衝突**
   - 修改 docker-compose.experiments.yml 中的端口映射
   - 或停止衝突的服務

3. **實驗失敗**
   - 檢查 logs/ 目錄下的日誌文件
   - 確認MCP工具服務運行正常

### 系統要求

- **內存**: 至少8GB RAM
- **磁盤**: 至少10GB可用空間
- **Docker**: 版本20.10+
- **Python**: 版本3.9+

## 📈 實驗結果解讀

實驗完成後將生成：
- 詳細的性能對比報告
- 最佳配置推薦
- 可視化儀表板
- 原始實驗數據

查看結果：
- 在 `results/reports/` 目錄找到生成的報告
- 通過 Grafana 查看實時監控數據
- 通過 MLflow 查看實驗追蹤記錄
"""

    with open("EXPERIMENT_README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)

    print("✅ 創建實驗說明文檔")


def main():
    """主程序"""
    print("🔧 開始準備藝術史RAG實驗環境...")

    # 設置日誌
    logging.basicConfig(level=logging.INFO)

    try:
        # 1. 創建目錄結構
        setup_directories()

        # 2. 創建樣本數據
        create_sample_art_images()
        create_sample_audio_data()

        # 3. 創建配置文件
        create_experiment_config()
        create_prometheus_config()

        # 4. 創建Docker環境
        create_docker_compose_for_experiments()

        # 5. 創建啟動腳本
        create_startup_script()

        # 6. 創建說明文檔
        create_readme()

        print("\n" + "=" * 60)
        print("🎉 實驗環境準備完成！")
        print("=" * 60)
        print("📂 實驗數據目錄: data/experiments/")
        print("🐳 Docker服務配置: docker-compose.experiments.yml")
        print("🚀 啟動腳本: ./start_experiments.sh")
        print("📖 詳細說明: EXPERIMENT_README.md")
        print("\n下一步:")
        print("1. 檢查並調整配置文件")
        print("2. 準備實際的圖像和音頻文件（可選）")
        print("3. 運行 ./start_experiments.sh 啟動實驗環境")
        print("=" * 60)

    except Exception as e:
        print(f"❌ 環境準備失敗: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
