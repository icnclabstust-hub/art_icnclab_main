#!/bin/bash

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
