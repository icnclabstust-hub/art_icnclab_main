#!/bin/bash
# 使用虛擬環境啟動爬蟲

set -e

echo "🤖 自動化藝術史資料爬蟲系統"
echo "=================================="
echo ""

# 檢查虛擬環境
if [ ! -d "crawler_venv" ]; then
    echo "⚠️  未找到虛擬環境"
    echo "正在自動設置環境..."
    bash scripts/ops/setup_crawler_env.sh
fi

# 啟用虛擬環境
echo "🔌 啟用虛擬環境..."
source crawler_venv/bin/activate

# 檢查必要服務
echo ""
echo "📋 檢查必要服務..."
echo "--------------------------------"

# 檢查 Neo4j
if docker ps | grep -q neo4j; then
    echo "✅ Neo4j 運行中"
else
    echo "⚠️  Neo4j 未運行"
    read -p "是否啟動 Neo4j? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose -f docker-compose.crawler.yml up -d neo4j
        echo "⏳ 等待 Neo4j 啟動..."
        sleep 5
    fi
fi

# 檢查 ChromaDB
if docker ps | grep -q chromadb; then
    echo "✅ ChromaDB 運行中"
else
    echo "⚠️  ChromaDB 未運行"
    read -p "是否啟動 ChromaDB? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose -f docker-compose.crawler.yml up -d chromadb
        echo "⏳ 等待 ChromaDB 啟動..."
        sleep 3
    fi
fi

echo ""
echo "=================================="
echo "🚀 啟動爬蟲系統"
echo "=================================="
echo ""

# 運行爬蟲
python3 src/crawler/AutomatedCrawlerSystem.py

# 退出虛擬環境
deactivate

echo ""
echo "✅ 完成"
