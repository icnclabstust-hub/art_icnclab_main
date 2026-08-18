#!/bin/bash

# GPU環境設置腳本
# 此腳本用於設置CUDA ML服務的Docker環境

set -e

echo "🚀 設置CUDA ML服務Docker環境..."

# 檢查Docker是否已安裝
if ! command -v docker &> /dev/null; then
    echo "❌ Docker未安裝，請先安裝Docker"
    exit 1
fi

# 檢查Docker Compose是否已安裝
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose未安裝，請先安裝Docker Compose"
    exit 1
fi

# 檢查NVIDIA Docker支援
echo "🔍 檢查NVIDIA Docker支援..."
if ! docker run --rm --gpus all nvidia/cuda:12.8-base-ubuntu22.04 nvidia-smi &> /dev/null; then
    echo "⚠️ NVIDIA Docker支援未正確配置"
    echo "請確認已安裝nvidia-container-toolkit:"
    echo "  Ubuntu/Debian: sudo apt install nvidia-container-toolkit"
    echo "  然後重新啟動Docker: sudo systemctl restart docker"

    # 嘗試配置NVIDIA Docker支援
    echo "🔧 嘗試配置NVIDIA Docker支援..."
    if command -v nvidia-ctk &> /dev/null; then
        sudo nvidia-ctk runtime configure --runtime=docker
        sudo systemctl restart docker
        echo "✅ NVIDIA Docker已配置，請重新運行此腳本"
        exit 0
    else
        echo "❌ 無法自動配置，請手動安裝nvidia-container-toolkit"
        exit 1
    fi
fi

echo "✅ NVIDIA Docker支援已配置"

# 檢查GPU狀態
echo "🎮 檢查GPU狀態..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
else
    echo "⚠️ nvidia-smi未找到，但Docker GPU支援已配置"
fi

# 創建必要目錄
echo "📁 創建必要目錄..."
mkdir -p ./ml-service/models
mkdir -p ./ml-service/data
mkdir -p ./ml-service/logs
mkdir -p ./ml-data/training
mkdir -p ./ml-data/inference
mkdir -p ./notebooks
mkdir -p ./monitoring/prometheus
mkdir -p ./monitoring/grafana/dashboards
mkdir -p ./monitoring/grafana/datasources

# 設置權限
chmod -R 755 ./ml-service/
chmod +x ./ml-service/start.sh

# 複製環境變數檔案
if [ ! -f .env ]; then
    echo "📝 複製GPU環境變數配置..."
    cp .env.gpu .env
    echo "✅ 環境變數配置已創建：.env"
    echo "📝 請根據需要修改.env中的配置"
fi

# 建構Docker鏡像
echo "🐳 建構CUDA ML服務Docker鏡像..."
docker-compose -f docker-compose.gpu.yml build cuda-ml-service

echo "🎯 建構完成！"

# 提供使用說明
echo ""
echo "📋 使用說明："
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. 🚀 啟動所有服務（包含GPU支援）："
echo "   docker-compose -f docker-compose.gpu.yml up -d"
echo ""
echo "2. 📊 查看服務狀態："
echo "   docker-compose -f docker-compose.gpu.yml ps"
echo ""
echo "3. 🔍 查看ML服務日誌："
echo "   docker-compose -f docker-compose.gpu.yml logs -f cuda-ml-service"
echo ""
echo "4. 🧪 測試ML API："
echo "   curl http://localhost:8080/health"
echo ""
echo "5. 🎮 檢查GPU使用情況："
echo "   docker-compose -f docker-compose.gpu.yml exec cuda-ml-service nvidia-smi"
echo ""
echo "6. 📚 使用Jupyter Notebook（ML實驗）："
echo "   http://localhost:8888 (token: art-history-ml-2024)"
echo ""
echo "7. 📈 監控儀表板："
echo "   Grafana: http://localhost:3001 (admin/admin123)"
echo "   Prometheus: http://localhost:9090"
echo ""
echo "8. 🔧 停止所有服務："
echo "   docker-compose -f docker-compose.gpu.yml down"
echo ""
echo "⚡ 主要API端點："
echo "   - 主應用: http://localhost:3000"
echo "   - ML服務: http://localhost:8080"
echo "   - ML健康檢查: http://localhost:8080/health"
echo "   - ML API測試: node tests/manual/test-ml-api.js"
echo ""
echo "🎯 環境已準備完成！"