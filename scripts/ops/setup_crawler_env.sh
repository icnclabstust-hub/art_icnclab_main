#!/bin/bash
# 自動化爬蟲環境設置腳本

set -e

echo "🔧 自動化爬蟲系統 - 環境設置"
echo "=================================="
echo ""

# 檢查 Python3
echo "📋 檢查 Python 環境..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 錯誤: 未找到 Python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "✅ 找到 $PYTHON_VERSION"
echo ""

# 檢查是否已有虛擬環境
if [ -d "crawler_venv" ]; then
    echo "⚠️  發現現有虛擬環境"
    read -p "是否刪除並重新建立? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  刪除舊環境..."
        rm -rf crawler_venv
    else
        echo "✅ 使用現有環境"
    fi
fi

# 創建虛擬環境
if [ ! -d "crawler_venv" ]; then
    echo "🔨 創建虛擬環境 (crawler_venv)..."
    python3 -m venv crawler_venv
    echo "✅ 虛擬環境創建成功"
fi

echo ""
echo "📦 安裝依賴套件..."
echo "--------------------------------"

# 啟用虛擬環境並安裝套件
source crawler_venv/bin/activate

# 升級 pip
echo "⬆️  升級 pip..."
pip install --upgrade pip -q

# 安裝依賴
echo "📥 安裝爬蟲系統依賴..."
pip install requests schedule pyyaml neo4j chromadb

echo ""
echo "=================================="
echo "✅ 環境設置完成！"
echo "=================================="
echo ""
echo "📝 使用說明："
echo ""
echo "1. 啟動虛擬環境："
echo "   source crawler_venv/bin/activate"
echo ""
echo "2. 運行爬蟲："
echo "   python3 src/crawler/AutomatedCrawlerSystem.py"
echo ""
echo "3. 退出虛擬環境："
echo "   deactivate"
echo ""
echo "💡 或使用快速啟動腳本："
echo ""
