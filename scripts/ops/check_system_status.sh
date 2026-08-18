#!/bin/bash
# 藝術史資料庫系統狀態檢查腳本

echo "🔍 藝術史資料庫系統狀態報告"
echo "================================"
echo "檢查時間: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# 1. Docker 容器狀態
echo "🐳 Docker 容器狀態"
echo "--------------------------------"
CONTAINERS=("art-history-neo4j" "art-history-chromadb" "art-history-ollama" "art-history-openwebui")

for container in "${CONTAINERS[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        STATUS=$(docker inspect --format='{{.State.Status}}' $container 2>/dev/null)
        UPTIME=$(docker inspect --format='{{.State.StartedAt}}' $container 2>/dev/null | cut -d'T' -f1)
        echo -e "${GREEN}✅ ${container}${NC}"
        echo "   狀態: ${STATUS} | 啟動於: ${UPTIME}"
    else
        echo -e "${RED}❌ ${container}${NC}"
        echo "   狀態: 未運行"
    fi
done

echo ""

# 2. Neo4j 資料庫
echo "📊 Neo4j 資料庫統計"
echo "--------------------------------"

if docker ps --format '{{.Names}}' | grep -q "^art-history-neo4j$"; then
    # 總節點數
    TOTAL_NODES=$(docker exec art-history-neo4j cypher-shell -u neo4j -p CHANGE_ME_NEO4J_PASSWORD \
        "MATCH (n) RETURN count(n)" --format plain 2>/dev/null | tail -n 1 | tr -d ' ')

    if [ ! -z "$TOTAL_NODES" ]; then
        echo -e "${BLUE}📈 總節點數: ${TOTAL_NODES}${NC}"

        # 節點類型分佈
        echo ""
        echo "節點類型分佈:"
        docker exec art-history-neo4j cypher-shell -u neo4j -p CHANGE_ME_NEO4J_PASSWORD \
            "MATCH (n) RETURN labels(n)[0] as 類型, count(n) as 數量 ORDER BY 數量 DESC" \
            --format plain 2>/dev/null | head -n 15

        # 關係數量
        echo ""
        TOTAL_RELS=$(docker exec art-history-neo4j cypher-shell -u neo4j -p CHANGE_ME_NEO4J_PASSWORD \
            "MATCH ()-[r]->() RETURN count(r)" --format plain 2>/dev/null | tail -n 1 | tr -d ' ')
        echo -e "${BLUE}🔗 總關係數: ${TOTAL_RELS}${NC}"

        # 索引狀態
        echo ""
        echo "向量索引狀態:"
        docker exec art-history-neo4j cypher-shell -u neo4j -p CHANGE_ME_NEO4J_PASSWORD \
            "SHOW INDEXES YIELD name, type, state WHERE type = 'VECTOR' RETURN name, state" \
            --format plain 2>/dev/null | head -n 10
    else
        echo -e "${RED}❌ 無法連接 Neo4j 或資料庫為空${NC}"
    fi
else
    echo -e "${RED}❌ Neo4j 容器未運行${NC}"
fi

echo ""

# 3. ChromaDB 資料庫
echo "📊 ChromaDB 資料庫統計"
echo "--------------------------------"

if docker ps --format '{{.Names}}' | grep -q "^art-history-chromadb$"; then
    # 需要 jq 工具
    if command -v jq &> /dev/null; then
        COLLECTION_INFO=$(curl -s http://localhost:8001/api/v2/tenants/default_tenant/databases/default_database/collections/aa7a55a2-924e-41b0-a0f7-9b5c031477a4 2>/dev/null)

        if [ ! -z "$COLLECTION_INFO" ]; then
            VECTOR_COUNT=$(echo $COLLECTION_INFO | jq -r '.count // "N/A"')
            COLLECTION_NAME=$(echo $COLLECTION_INFO | jq -r '.name // "N/A"')

            echo -e "${BLUE}📈 向量數量: ${VECTOR_COUNT}${NC}"
            echo -e "${BLUE}📂 Collection 名稱: ${COLLECTION_NAME}${NC}"
        else
            echo -e "${YELLOW}⚠️ 無法獲取 ChromaDB 資訊${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️ 需要安裝 jq 工具才能顯示詳細資訊${NC}"
        echo "   安裝方法: sudo apt-get install jq"
    fi
else
    echo -e "${RED}❌ ChromaDB 容器未運行${NC}"
fi

echo ""

# 4. RAG Server 狀態
echo "🔧 RAG Server 狀態"
echo "--------------------------------"

# 檢查 RAG Server 進程
RAG_SERVER_PID=$(pgrep -f "multi-database-rag-server.js" 2>/dev/null)

if [ ! -z "$RAG_SERVER_PID" ]; then
    echo -e "${GREEN}✅ RAG Server 運行中 (PID: ${RAG_SERVER_PID})${NC}"

    # 測試健康檢查端點
    HEALTH_CHECK=$(curl -s http://localhost:8010/health 2>/dev/null)
    if [ ! -z "$HEALTH_CHECK" ]; then
        if command -v jq &> /dev/null; then
            echo "$HEALTH_CHECK" | jq '.'
        else
            echo "$HEALTH_CHECK"
        fi
    fi
else
    echo -e "${RED}❌ RAG Server 未運行${NC}"
    echo "   啟動方法: node multi-database-rag-server.js &"
fi

echo ""

# 5. Ollama 模型統計
echo "🤖 Ollama 模型統計"
echo "--------------------------------"

if docker ps --format '{{.Names}}' | grep -q "^art-history-ollama$"; then
    # 基礎模型數量
    BASE_MODELS=$(docker exec art-history-ollama ollama list 2>/dev/null | grep -v "rag" | grep -c ":")
    echo -e "${BLUE}📦 基礎 LLM 模型: ${BASE_MODELS} 個${NC}"

    # RAG 組合模型數量
    RAG_MODELS=$(docker exec art-history-ollama ollama list 2>/dev/null | grep -c "rag")
    echo -e "${BLUE}🎯 LLM+RAG 組合模型: ${RAG_MODELS} 個${NC}"

    # 顯示部分模型列表
    echo ""
    echo "最近創建的 RAG 組合模型 (前 10 個):"
    docker exec art-history-ollama ollama list 2>/dev/null | grep "rag" | head -n 10
else
    echo -e "${RED}❌ Ollama 容器未運行${NC}"
fi

echo ""

# 6. OpenWebUI 狀態
echo "🌐 OpenWebUI 狀態"
echo "--------------------------------"

if docker ps --format '{{.Names}}' | grep -q "^art-history-openwebui$"; then
    OPENWEBUI_PORT=$(docker port art-history-openwebui 8080 2>/dev/null | cut -d':' -f2)
    echo -e "${GREEN}✅ OpenWebUI 運行中${NC}"
    echo "   訪問地址: http://localhost:${OPENWEBUI_PORT}"

    # 測試連接
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080 2>/dev/null)
    if [ "$HTTP_STATUS" == "200" ]; then
        echo -e "   ${GREEN}✅ HTTP 狀態: ${HTTP_STATUS} (正常)${NC}"
    else
        echo -e "   ${YELLOW}⚠️ HTTP 狀態: ${HTTP_STATUS}${NC}"
    fi
else
    echo -e "${RED}❌ OpenWebUI 容器未運行${NC}"
fi

echo ""

# 7. 系統資源使用
echo "💻 系統資源使用"
echo "--------------------------------"

# Docker 容器資源使用
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
    art-history-neo4j art-history-chromadb art-history-ollama art-history-openwebui 2>/dev/null

echo ""

# 8. 磁碟空間
echo "💾 Docker Volume 磁碟使用"
echo "--------------------------------"
docker system df -v 2>/dev/null | grep -E "VOLUME NAME|art-history"

echo ""

# 9. 網絡連接測試
echo "🔌 網絡連接測試"
echo "--------------------------------"

ENDPOINTS=(
    "http://localhost:7474|Neo4j"
    "http://localhost:8001|ChromaDB"
    "http://localhost:8010|RAG Server"
    "http://localhost:8080|OpenWebUI"
    "http://localhost:11434|Ollama"
)

for endpoint in "${ENDPOINTS[@]}"; do
    IFS='|' read -r url name <<< "$endpoint"
    if curl -s -o /dev/null -w "%{http_code}" --max-time 3 "$url" 2>/dev/null | grep -q "200\|302\|404"; then
        echo -e "${GREEN}✅ ${name} (${url})${NC}"
    else
        echo -e "${RED}❌ ${name} (${url})${NC}"
    fi
done

echo ""

# 10. 總結
echo "================================"
echo "📋 總結"
echo "================================"

# 檢查關鍵服務
CRITICAL_SERVICES=0
if docker ps --format '{{.Names}}' | grep -q "^art-history-neo4j$"; then ((CRITICAL_SERVICES++)); fi
if docker ps --format '{{.Names}}' | grep -q "^art-history-chromadb$"; then ((CRITICAL_SERVICES++)); fi
if docker ps --format '{{.Names}}' | grep -q "^art-history-ollama$"; then ((CRITICAL_SERVICES++)); fi
if docker ps --format '{{.Names}}' | grep -q "^art-history-openwebui$"; then ((CRITICAL_SERVICES++)); fi

echo "關鍵服務運行狀態: ${CRITICAL_SERVICES}/4"

if [ "$CRITICAL_SERVICES" -eq 4 ]; then
    echo -e "${GREEN}✅ 所有關鍵服務正常運行${NC}"
    echo ""
    echo "💡 系統就緒，可以使用 OpenWebUI:"
    echo "   🌐 http://localhost:8080"
elif [ "$CRITICAL_SERVICES" -ge 2 ]; then
    echo -e "${YELLOW}⚠️ 部分服務未運行，系統功能受限${NC}"
else
    echo -e "${RED}❌ 多數服務未運行，請檢查 Docker 容器${NC}"
fi

echo ""
echo "📅 檢查完成時間: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
