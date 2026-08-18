#!/bin/bash

# Ollama RAG Proxy 一鍵設置腳本
# 自動檢查、啟動所有必要服務，並提供 OpenWebUI 配置指引

echo "🎨 Ollama RAG Proxy 一鍵設置工具"
echo "========================================"
echo ""

# 設置工作目錄
WORK_DIR="/mnt/c/Users/ssking1999/Desktop/藝術史資料庫/art-history-database"
cd "$WORK_DIR"

# 顏色定義
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 服務狀態檢查函數
check_service() {
    local name=$1
    local url=$2
    local port=$3

    echo -n "檢查 $name ($port)... "

    if curl -s "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 運行中${NC}"
        return 0
    else
        echo -e "${RED}❌ 未運行${NC}"
        return 1
    fi
}

# 啟動服務函數
start_service() {
    local name=$1
    local script=$2
    local log=$3
    local port=$4

    echo "啟動 $name..."

    # 檢查腳本是否存在
    if [ ! -f "$script" ]; then
        echo -e "${RED}❌ 錯誤: 找不到 $script${NC}"
        return 1
    fi

    # 啟動服務
    node "$script" > "$log" 2>&1 &
    local pid=$!

    echo "   進程 ID: $pid"
    echo "   日誌文件: $log"

    # 等待服務啟動
    sleep 2

    # 驗證服務
    if ps -p $pid > /dev/null; then
        echo -e "${GREEN}   ✅ 啟動成功${NC}"
        return 0
    else
        echo -e "${RED}   ❌ 啟動失敗，查看日誌: tail -f $log${NC}"
        return 1
    fi
}

echo "步驟 1: 檢查所有必要服務"
echo "----------------------------------------"

# 檢查各個服務
SERVICES_OK=true

if ! check_service "Neo4j" "http://localhost:7474" "7474"; then
    SERVICES_OK=false
    echo -e "${YELLOW}   請啟動 Neo4j: docker start art-history-neo4j${NC}"
fi

if ! check_service "ChromaDB" "http://localhost:8001/api/v1/heartbeat" "8001"; then
    SERVICES_OK=false
    echo -e "${YELLOW}   請啟動 ChromaDB: docker start art-history-chromadb${NC}"
fi

if ! check_service "Ollama" "http://localhost:11434/api/tags" "11434"; then
    SERVICES_OK=false
    echo -e "${YELLOW}   請啟動 Ollama: docker start art-history-ollama${NC}"
fi

if ! check_service "OpenWebUI" "http://localhost:8080" "8080"; then
    SERVICES_OK=false
    echo -e "${YELLOW}   請啟動 OpenWebUI: docker start art-history-openwebui${NC}"
fi

echo ""

# 檢查 Multi-DB RAG Server
echo "步驟 2: 檢查 Multi-DB RAG Server (8010)"
echo "----------------------------------------"

if ! check_service "Multi-DB RAG Server" "http://localhost:8010/health" "8010"; then
    echo -e "${YELLOW}   需要啟動 Multi-DB RAG Server${NC}"

    if start_service "Multi-DB RAG Server" \
                     "multi-database-rag-server.js" \
                     "multi-database-rag-server.log" \
                     "8010"; then
        echo -e "${GREEN}   ✅ Multi-DB RAG Server 已啟動${NC}"
    else
        echo -e "${RED}   ❌ Multi-DB RAG Server 啟動失敗${NC}"
        SERVICES_OK=false
    fi
else
    echo -e "${GREEN}   ✅ Multi-DB RAG Server 已在運行${NC}"
fi

echo ""

# 檢查 Ollama RAG Proxy
echo "步驟 3: 檢查 Ollama RAG Proxy (11435)"
echo "----------------------------------------"

if ! check_service "Ollama RAG Proxy" "http://localhost:11435/health" "11435"; then
    echo -e "${YELLOW}   需要啟動 Ollama RAG Proxy${NC}"

    if start_service "Ollama RAG Proxy" \
                     "ollama-rag-proxy.js" \
                     "ollama-rag-proxy.log" \
                     "11435"; then
        echo -e "${GREEN}   ✅ Ollama RAG Proxy 已啟動${NC}"
    else
        echo -e "${RED}   ❌ Ollama RAG Proxy 啟動失敗${NC}"
        SERVICES_OK=false
    fi
else
    echo -e "${GREEN}   ✅ Ollama RAG Proxy 已在運行${NC}"
fi

echo ""
echo "========================================"

# 最終狀態報告
if [ "$SERVICES_OK" = true ]; then
    echo -e "${GREEN}🎉 所有服務運行正常！${NC}"
    echo ""
    echo "步驟 4: 配置 OpenWebUI"
    echo "----------------------------------------"
    echo ""
    echo "現在請在 OpenWebUI 中添加 Ollama RAG Proxy 連接："
    echo ""
    echo "  方法 A: 重新啟動 OpenWebUI 容器並設置環境變量"
    echo "  =============================================="
    echo "  docker stop art-history-openwebui"
    echo "  docker run -d \\"
    echo "    --name art-history-openwebui \\"
    echo "    --restart always \\"
    echo "    -p 8080:8080 \\"
    echo "    -e OLLAMA_BASE_URL=http://host.docker.internal:11435 \\"
    echo "    -e WEBUI_AUTH=false \\"
    echo "    -v open-webui:/app/backend/data \\"
    echo "    --add-host=host.docker.internal:host-gateway \\"
    echo "    ghcr.io/open-webui/open-webui:main"
    echo ""
    echo "  方法 B: 在 OpenWebUI 界面中手動添加"
    echo "  ===================================="
    echo "  1. 訪問 http://localhost:8080"
    echo "  2. 進入 Settings → Connections"
    echo "  3. 添加 Ollama 連接:"
    echo "     URL: http://localhost:11435"
    echo ""
    echo "步驟 5: 開始使用"
    echo "----------------------------------------"
    echo ""
    echo "配置完成後，您可以在模型選擇中看到 24 個 RAG+LLM 組合模型："
    echo ""
    echo "  • llama3.1-vector_rag    (Llama 3.1 + ChromaDB向量檢索)"
    echo "  • llama3.1-graph_rag     (Llama 3.1 + Neo4j圖譜檢索)"
    echo "  • llama3.1-hybrid_rag    (Llama 3.1 + 混合檢索)"
    echo "  • qwen2.5-vector_rag     (Qwen 2.5 + ChromaDB向量檢索)"
    echo "  • qwen2.5-graph_rag      (Qwen 2.5 + Neo4j圖譜檢索)"
    echo "  • gemma2-advanced_rag    (Gemma2 + 高級檢索)"
    echo "  • ... 等共 24 個組合"
    echo ""
    echo "📚 詳細使用說明請查看: ollama-rag-proxy使用指南.md"
    echo ""

    # 顯示測試命令
    echo "快速測試："
    echo "----------------------------------------"
    echo ""
    echo "# 測試 Proxy 健康狀態"
    echo "curl http://localhost:11435/health"
    echo ""
    echo "# 查看可用模型"
    echo "curl http://localhost:11435/api/tags"
    echo ""
    echo "# 測試 RAG 查詢"
    echo 'curl -X POST http://localhost:11435/api/generate \'
    echo '  -H "Content-Type: application/json" \'
    echo '  -d '"'"'{'
    echo '    "model": "llama3.1-vector_rag",'
    echo '    "prompt": "莫內的代表作品有哪些？",'
    echo '    "stream": false'
    echo '  }'"'"
    echo ""

else
    echo -e "${RED}⚠️  部分服務未運行${NC}"
    echo ""
    echo "請先啟動所有必要的服務，然後重新運行此腳本。"
    echo ""
    echo "啟動命令："
    echo "  docker start art-history-neo4j"
    echo "  docker start art-history-chromadb"
    echo "  docker start art-history-ollama"
    echo "  docker start art-history-openwebui"
    echo ""
fi

echo "========================================"
echo ""

# 提供日誌查看提示
echo "📊 服務日誌位置："
echo "  • Multi-DB RAG Server: multi-database-rag-server.log"
echo "  • Ollama RAG Proxy: ollama-rag-proxy.log"
echo ""
echo "查看實時日誌："
echo "  tail -f ollama-rag-proxy.log"
echo "  tail -f multi-database-rag-server.log"
echo ""

# 返回狀態碼
if [ "$SERVICES_OK" = true ]; then
    exit 0
else
    exit 1
fi
