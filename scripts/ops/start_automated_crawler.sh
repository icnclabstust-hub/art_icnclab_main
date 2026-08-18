#!/bin/bash
# 自動化爬蟲系統啟動腳本

set -e

echo "🤖 自動化藝術史資料爬蟲系統"
echo "=================================="
echo ""

# 檢查 Python 環境
echo "📋 檢查環境..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 錯誤: 未找到 Python3"
    exit 1
fi

# 檢查並安裝依賴
echo "📦 檢查依賴套件..."
pip3 install -q requests schedule pyyaml neo4j chromadb 2>/dev/null || {
    echo "⚠️ 正在安裝依賴套件..."
    pip3 install requests schedule pyyaml neo4j chromadb
}

# 檢查配置文件
if [ ! -f "../../crawlers/crawler_config.yaml" ]; then
    echo "⚠️ 警告: 未找到 crawler_config.yaml，將使用預設配置"
fi

# 創建必要目錄
echo "📁 創建輸出目錄..."
mkdir -p automated_crawler_data
mkdir -p logs
mkdir -p cache

# 顯示選單
echo ""
echo "請選擇運行模式:"
echo "  1) 立即執行一次 (手動模式)"
echo "  2) 啟動自動排程 (每24小時執行)"
echo "  3) 測試配置 (不執行爬取)"
echo "  4) 查看統計資料"
echo ""
read -p "請輸入選項 (1-4): " mode

case $mode in
    1)
        echo ""
        echo "🚀 啟動單次爬取..."
        echo "=================================="
        python3 src/crawler/AutomatedCrawlerSystem.py <<EOF
1
EOF
        ;;
    2)
        echo ""
        echo "⏰ 啟動自動排程爬蟲..."
        echo "=================================="
        echo "提示: 按 Ctrl+C 停止"
        echo ""
        python3 src/crawler/AutomatedCrawlerSystem.py <<EOF
2
EOF
        ;;
    3)
        echo ""
        echo "🧪 測試配置..."
        echo "=================================="
        python3 -c "
import yaml
try:
    with open('../../crawlers/crawler_config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    print('✅ 配置文件格式正確')
    print(f\"重點時期: {config['crawler']['focus_periods']}\")
    print(f\"排程間隔: {config['schedule']['interval_hours']} 小時\")
    print(f\"Neo4j: {'啟用' if config['rag_system']['neo4j']['enabled'] else '停用'}\")
    print(f\"ChromaDB: {'啟用' if config['rag_system']['chromadb']['enabled'] else '停用'}\")
except Exception as e:
    print(f'❌ 配置錯誤: {e}')
"
        ;;
    4)
        echo ""
        echo "📊 統計資料"
        echo "=================================="
        if [ -f "automated_crawler_data/crawler_stats.json" ]; then
            python3 -c "
import json
with open('automated_crawler_data/crawler_stats.json', 'r') as f:
    stats = json.load(f)
print(f\"總計爬取: {stats['total_crawled']} 件作品\")
print(f\"總計處理: {stats['total_processed']} 件\")
print(f\"傳送到RAG: {stats['total_sent_to_rag']} 件\")
print(f\"最後爬取: {stats['last_crawl_time']}\")
"
        else
            echo "⚠️ 尚無統計資料，請先執行爬取任務"
        fi
        ;;
    *)
        echo "❌ 無效選項"
        exit 1
        ;;
esac

echo ""
echo "✅ 完成"
