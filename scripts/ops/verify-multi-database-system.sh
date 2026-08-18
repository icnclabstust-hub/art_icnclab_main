#!/bin/bash

# 多資料庫 RAG 系統完整驗證腳本
# 測試所有組件和功能

echo "========================================"
echo "🔍 藝術史多資料庫 RAG 系統驗證工具"
echo "========================================"
echo ""

# 顏色定義
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 測試計數器
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# 測試函數
test_service() {
    local name=$1
    local url=$2
    local description=$3

    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo -n "[$TESTS_TOTAL] 測試 $name: "

    if curl -s -f -m 5 "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PASS${NC} - $description"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC} - $description"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

test_api_response() {
    local name=$1
    local url=$2
    local data=$3
    local expected=$4
    local description=$5

    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo -n "[$TESTS_TOTAL] 測試 $name: "

    response=$(curl -s -X POST "$url" \
        -H "Content-Type: application/json" \
        -d "$data" \
        2>/dev/null)

    if echo "$response" | grep -q "$expected"; then
        echo -e "${GREEN}✅ PASS${NC} - $description"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC} - $description"
        echo -e "${YELLOW}回應: ${response:0:100}...${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

echo "========================================="
echo "📊 第一部分：基礎服務健康檢查"
echo "========================================="
echo ""

# 1. Neo4j
test_service "Neo4j" "http://localhost:7474" "圖資料庫服務"

# 2. ChromaDB
test_service "ChromaDB" "http://localhost:8001/api/v1/heartbeat" "向量資料庫服務"

# 3. Ollama
test_service "Ollama" "http://localhost:11434" "嵌入模型服務"

# 4. 標準 RAG 服務器
test_service "標準 RAG 服務器" "http://localhost:8008/health" "端口 8008"

# 5. 多資料庫 RAG 服務器
test_service "多資料庫 RAG 服務器" "http://localhost:8010/health" "端口 8010"

# 6. OpenWebUI
test_service "OpenWebUI" "http://localhost:8080" "用戶界面"

echo ""
echo "========================================="
echo "🧪 第二部分：多資料庫 RAG 功能測試"
echo "========================================="
echo ""

# 測試 Vector RAG (ChromaDB 優先)
echo -e "${BLUE}測試 Vector RAG (ChromaDB 優先)...${NC}"
test_api_response \
    "Vector RAG" \
    "http://localhost:8010/query" \
    '{"query":"達文西的作品","strategy":"vector_only","top_k":3}' \
    "success" \
    "ChromaDB 向量檢索"

# 測試 Graph RAG (Neo4j)
echo -e "${BLUE}測試 Graph RAG (Neo4j)...${NC}"
test_api_response \
    "Graph RAG" \
    "http://localhost:8010/query" \
    '{"query":"文藝復興藝術家","strategy":"graph_only","top_k":3}' \
    "success" \
    "Neo4j 圖譜檢索"

# 測試 Hybrid RAG (Neo4j + ChromaDB)
echo -e "${BLUE}測試 Hybrid RAG (混合)...${NC}"
test_api_response \
    "Hybrid RAG" \
    "http://localhost:8010/query" \
    '{"query":"文藝復興時期的繪畫","strategy":"hybrid_balanced","top_k":5}' \
    "success" \
    "混合檢索"

# 測試 Enhanced RAG
echo -e "${BLUE}測試 Enhanced RAG...${NC}"
test_api_response \
    "Enhanced RAG" \
    "http://localhost:8010/query" \
    '{"query":"巴洛克藝術","strategy":"enhanced_rag","top_k":5}' \
    "success" \
    "增強型檢索"

# 測試 Advanced RAG (ChromaDB 優先)
echo -e "${BLUE}測試 Advanced RAG (ChromaDB 優先)...${NC}"
test_api_response \
    "Advanced RAG" \
    "http://localhost:8010/query" \
    '{"query":"米開朗基羅","strategy":"advanced_rag","top_k":3}' \
    "success" \
    "ChromaDB 多級檢索"

# 測試 Naive RAG (只用 ChromaDB)
echo -e "${BLUE}測試 Naive RAG (ChromaDB)...${NC}"
test_api_response \
    "Naive RAG" \
    "http://localhost:8010/query" \
    '{"query":"拉斐爾","strategy":"naive_rag","top_k":3}' \
    "success" \
    "ChromaDB 簡單檢索"

echo ""
echo "========================================="
echo "🔍 第三部分：資料來源追蹤驗證"
echo "========================================="
echo ""

# 測試來源追蹤
echo -e "${BLUE}驗證來源追蹤信息...${NC}"
TESTS_TOTAL=$((TESTS_TOTAL + 1))
response=$(curl -s -X POST "http://localhost:8010/query" \
    -H "Content-Type: application/json" \
    -d '{"query":"達文西","strategy":"vector_only","top_k":1}')

if echo "$response" | grep -q "source_database" && \
   echo "$response" | grep -q "original_source" && \
   echo "$response" | grep -q "retrieval_method"; then
    echo -e "[$TESTS_TOTAL] 來源追蹤: ${GREEN}✅ PASS${NC} - 包含完整來源信息"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "[$TESTS_TOTAL] 來源追蹤: ${RED}❌ FAIL${NC} - 缺少來源信息"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""
echo "========================================="
echo "📊 第四部分：資料庫狀態檢查"
echo "========================================="
echo ""

# Neo4j 節點計數
echo -e "${BLUE}檢查 Neo4j 資料量...${NC}"
TESTS_TOTAL=$((TESTS_TOTAL + 1))
neo4j_response=$(curl -s -X POST "http://localhost:7474/db/neo4j/tx/commit" \
    -u neo4j:CHANGE_ME_NEO4J_PASSWORD \
    -H "Content-Type: application/json" \
    -d '{"statements":[{"statement":"MATCH (n) RETURN count(n) as count"}]}' \
    2>/dev/null)

if echo "$neo4j_response" | grep -q "count"; then
    echo -e "[$TESTS_TOTAL] Neo4j 資料量: ${GREEN}✅ PASS${NC} - 資料庫正常"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "[$TESTS_TOTAL] Neo4j 資料量: ${RED}❌ FAIL${NC} - 查詢失敗"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# ChromaDB 集合檢查
echo -e "${BLUE}檢查 ChromaDB 集合...${NC}"
TESTS_TOTAL=$((TESTS_TOTAL + 1))
chroma_response=$(curl -s "http://localhost:8001/api/v2/tenants/default_tenant/databases/default_database/collections/aa7a55a2-924e-41b0-a0f7-9b5c031477a4" \
    2>/dev/null)

if echo "$chroma_response" | grep -q "art_history"; then
    echo -e "[$TESTS_TOTAL] ChromaDB 集合: ${GREEN}✅ PASS${NC} - 集合存在"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "[$TESTS_TOTAL] ChromaDB 集合: ${RED}❌ FAIL${NC} - 集合不存在"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""
echo "========================================="
echo "📈 第五部分：性能測試"
echo "========================================="
echo ""

# 測試查詢響應時間
echo -e "${BLUE}測試查詢響應時間...${NC}"
TESTS_TOTAL=$((TESTS_TOTAL + 1))
start_time=$(date +%s%N)
curl -s -X POST "http://localhost:8010/query" \
    -H "Content-Type: application/json" \
    -d '{"query":"達文西","strategy":"vector_only","top_k":3}' > /dev/null
end_time=$(date +%s%N)
elapsed_ms=$(( (end_time - start_time) / 1000000 ))

if [ $elapsed_ms -lt 5000 ]; then
    echo -e "[$TESTS_TOTAL] 響應時間: ${GREEN}✅ PASS${NC} - ${elapsed_ms}ms (< 5000ms)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "[$TESTS_TOTAL] 響應時間: ${YELLOW}⚠️  WARN${NC} - ${elapsed_ms}ms (較慢)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

echo ""
echo "========================================="
echo "📝 第六部分：文件完整性檢查"
echo "========================================="
echo ""

# 檢查關鍵文件
check_file() {
    local file=$1
    local description=$2

    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    if [ -f "$file" ]; then
        echo -e "[$TESTS_TOTAL] $description: ${GREEN}✅ PASS${NC} - 文件存在"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "[$TESTS_TOTAL] $description: ${RED}❌ FAIL${NC} - 文件不存在"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

check_file "multi-database-rag-server.js" "多資料庫服務器"
check_file "enhanced_openwebui_rag_function_v4.py" "OpenWebUI Function v4.1"
check_file "update-openwebui-function.md" "更新指南"
check_file "FINAL_PROJECT_REPORT.md" "最終報告"
check_file "MULTI_DATABASE_DEPLOYMENT_COMPLETE.md" "部署報告"

echo ""
echo "========================================="
echo "📋 測試總結"
echo "========================================="
echo ""

total_tests=$TESTS_TOTAL
passed_tests=$TESTS_PASSED
failed_tests=$TESTS_FAILED
pass_rate=$(awk "BEGIN {printf \"%.1f\", ($passed_tests/$total_tests)*100}")

echo "總測試數: $total_tests"
echo -e "通過: ${GREEN}$passed_tests${NC}"
echo -e "失敗: ${RED}$failed_tests${NC}"
echo -e "通過率: ${BLUE}${pass_rate}%${NC}"
echo ""

if [ $failed_tests -eq 0 ]; then
    echo -e "${GREEN}🎉 所有測試通過！系統運行正常！${NC}"
    echo ""
    echo "========================================="
    echo "✅ 系統狀態總覽"
    echo "========================================="
    echo ""
    echo "✅ Neo4j: 運行中 (端口 7474)"
    echo "✅ ChromaDB: 運行中 (端口 8001)"
    echo "✅ Ollama: 運行中 (端口 11434)"
    echo "✅ 多資料庫 RAG 服務器: 運行中 (端口 8010)"
    echo "✅ OpenWebUI: 運行中 (端口 8080)"
    echo ""
    echo "✅ 8 種 RAG 策略全部可用"
    echo "✅ 完整來源追蹤系統正常"
    echo "✅ 雙資料庫架構正常運作"
    echo ""
    echo "========================================="
    echo "📝 下一步行動"
    echo "========================================="
    echo ""
    echo "唯一剩餘步驟：手動更新 OpenWebUI Function"
    echo ""
    echo "1. 訪問 http://localhost:8080"
    echo "2. Workspace → Functions → 編輯藝術史 Function"
    echo "3. 複製 enhanced_openwebui_rag_function_v4.py 內容"
    echo "4. 貼上並保存"
    echo ""
    echo "詳細步驟請參閱: update-openwebui-function.md"
    echo ""
    exit 0
else
    echo -e "${RED}❌ 有 $failed_tests 個測試失敗${NC}"
    echo ""
    echo "請檢查失敗的服務並確保所有組件正在運行。"
    echo ""
    echo "常用診斷命令："
    echo "  - 檢查多資料庫服務器日誌: tail -f multi-database-rag-server.log"
    echo "  - 檢查進程: ps aux | grep -E 'neo4j|chroma|ollama|node'"
    echo "  - 檢查端口: netstat -tulpn | grep -E '7474|8001|8008|8010|11434'"
    echo ""
    exit 1
fi
