#!/bin/bash
# RAG 系統效能測試工具

echo "========================================"
echo "🔍 RAG 系統效能測試"
echo "========================================"
echo ""

# 顏色定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 測試計數
PASS=0
FAIL=0

# 測試函數
test_performance() {
    local test_name=$1
    local command=$2
    local max_time=$3

    echo "測試: $test_name"
    echo "---"

    START=$(date +%s.%N)
    eval "$command" > /dev/null 2>&1
    EXIT_CODE=$?
    END=$(date +%s.%N)

    DURATION=$(echo "$END - $START" | bc)

    if [ $EXIT_CODE -eq 0 ]; then
        if (( $(echo "$DURATION < $max_time" | bc -l) )); then
            echo -e "${GREEN}✅ 通過${NC} - 執行時間: ${DURATION}秒 (目標: <${max_time}秒)"
            PASS=$((PASS + 1))
        else
            echo -e "${YELLOW}⚠️  緩慢${NC} - 執行時間: ${DURATION}秒 (目標: <${max_time}秒)"
            PASS=$((PASS + 1))
        fi
    else
        echo -e "${RED}❌ 失敗${NC} - 服務可能未運行"
        FAIL=$((FAIL + 1))
    fi
    echo ""
}

echo "開始效能測試..."
echo ""

# 測試 1: Neo4j 連接
test_performance "Neo4j 連接測試" \
    "docker exec art-history-neo4j cypher-shell -u neo4j -p CHANGE_ME_NEO4J_PASSWORD 'RETURN 1'" \
    0.5

# 測試 2: Neo4j 簡單查詢
test_performance "Neo4j 簡單計數查詢" \
    "docker exec art-history-neo4j cypher-shell -u neo4j -p CHANGE_ME_NEO4J_PASSWORD 'MATCH (a:Artwork) RETURN count(a)'" \
    0.3

# 測試 3: Neo4j 複雜查詢
test_performance "Neo4j 複雜關聯查詢" \
    "docker exec art-history-neo4j cypher-shell -u neo4j -p CHANGE_ME_NEO4J_PASSWORD 'MATCH (a:Artwork)-[:BELONGS_TO_PERIOD]->(:Period {name: \"Renaissance\"}) RETURN count(a)'" \
    1.0

# 測試 4: ChromaDB 健康檢查
test_performance "ChromaDB 健康檢查" \
    "curl -s http://localhost:8000/api/v1/heartbeat" \
    0.2

# 測試 5: ChromaDB 列出集合
test_performance "ChromaDB 列出集合" \
    "curl -s http://localhost:8000/api/v1/collections" \
    0.3

# 測試 6: RAG Manager 健康檢查
test_performance "RAG Manager 健康檢查" \
    "curl -s http://localhost:8007/health" \
    0.3

# 測試 7: Ollama 狀態
test_performance "Ollama 服務狀態" \
    "curl -s http://localhost:11434/api/tags" \
    0.5

echo "========================================"
echo "📊 測試結果統計"
echo "========================================"
echo ""
echo -e "${GREEN}通過: $PASS${NC}"
echo -e "${RED}失敗: $FAIL${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✅ 所有服務運行正常！${NC}"
else
    echo -e "${RED}⚠️  有 $FAIL 個服務需要檢查${NC}"
fi

echo ""
echo "========================================"
echo "📋 詳細服務狀態"
echo "========================================"
echo ""

# Neo4j 統計
echo "🗄️  Neo4j 資料庫："
docker exec art-history-neo4j cypher-shell -u neo4j -p CHANGE_ME_NEO4J_PASSWORD \
    "MATCH (n) RETURN 'Nodes' as Type, count(n) as Count UNION MATCH ()-[r]->() RETURN 'Relationships' as Type, count(r) as Count" 2>/dev/null | tail -n +2
echo ""

# ChromaDB 統計
echo "🔍 ChromaDB 向量庫："
CHROMA_COLLECTIONS=$(curl -s http://localhost:8000/api/v1/collections 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$CHROMA_COLLECTIONS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"Collections: {len(data) if isinstance(data, list) else 'N/A'}\")" 2>/dev/null || echo "Collections: 0"
else
    echo "無法連接到 ChromaDB"
fi
echo ""

# Ollama 模型
echo "🤖 Ollama 已加載模型："
docker exec art-history-ollama ollama ps 2>/dev/null | tail -n +2
echo ""

# RAG Manager 狀態
echo "🔗 RAG Manager 狀態："
RAG_STATUS=$(curl -s http://localhost:8007/health 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$RAG_STATUS" | python3 -m json.tool 2>/dev/null || echo "健康"
else
    echo "無法連接到 RAG Manager"
fi
echo ""

# 記憶體使用
echo "💾 容器資源使用："
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
    art-history-neo4j art-history-chromadb art-history-ollama art-history-rag-manager-v2 art-history-openwebui 2>/dev/null
echo ""

echo "========================================"
echo "🎯 效能建議"
echo "========================================"
echo ""

# 分析 Ollama 記憶體使用
OLLAMA_MEM=$(docker stats --no-stream --format "{{.MemPerc}}" art-history-ollama 2>/dev/null | sed 's/%//')
if (( $(echo "$OLLAMA_MEM > 40" | bc -l) )); then
    echo "⚠️  Ollama 記憶體使用較高 (${OLLAMA_MEM}%)"
    echo "   建議: 考慮使用更小的模型以提升速度"
    echo "   執行: ./switch_to_fast_model.sh"
    echo ""
fi

# 分析 Neo4j 記憶體
NEO4J_MEM=$(docker stats --no-stream --format "{{.MemPerc}}" art-history-neo4j 2>/dev/null | sed 's/%//')
if (( $(echo "$NEO4J_MEM > 10" | bc -l) )); then
    echo "ℹ️  Neo4j 記憶體使用: ${NEO4J_MEM}%"
    echo "   狀態: 正常範圍"
    echo ""
fi

echo "✅ 測試完成！"
echo ""
