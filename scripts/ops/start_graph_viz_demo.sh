#!/bin/bash

# OpenWebUI Neo4j 圖譜視覺化功能 - 快速啟動腳本
# 版本: v6.0.0

echo "======================================================================"
echo "🎨 OpenWebUI Neo4j 圖譜視覺化功能 - 快速啟動"
echo "======================================================================"
echo ""

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 檢查 Neo4j 是否運行
echo -e "${BLUE}🔍 檢查 Neo4j 服務...${NC}"
if curl -s http://localhost:7474 > /dev/null; then
    echo -e "${GREEN}✅ Neo4j 正在運行${NC}"
else
    echo -e "${RED}❌ Neo4j 未運行${NC}"
    echo -e "${YELLOW}正在啟動 Neo4j...${NC}"
    docker-compose up -d neo4j
    echo "等待 Neo4j 啟動..."
    sleep 10
fi

echo ""

# 檢查數據庫內容
echo -e "${BLUE}🔍 檢查數據庫內容...${NC}"
NODE_COUNT=$(docker exec art-database-neo4j cypher-shell -u neo4j -p CHANGE_ME_NEO4J_PASSWORD "MATCH (n) RETURN count(n);" 2>/dev/null | grep -o '[0-9]*' | head -1)

if [ -z "$NODE_COUNT" ]; then
    echo -e "${YELLOW}⚠️ 無法連接到 Neo4j 或數據庫為空${NC}"
    echo -e "${YELLOW}請確保數據已導入${NC}"
else
    echo -e "${GREEN}✅ 數據庫包含 $NODE_COUNT 個節點${NC}"
fi

echo ""

# 運行測試腳本
echo -e "${BLUE}🧪 運行測試腳本...${NC}"
if [ -f "../../tests/manual/test_graph_visualization.py" ]; then
    python3 tests/manual/test_graph_visualization.py
else
    echo -e "${RED}❌ 找不到測試腳本 test_graph_visualization.py${NC}"
fi

echo ""
echo "======================================================================"
echo "📊 演示與文檔"
echo "======================================================================"
echo ""
echo -e "${GREEN}✓${NC} 互動演示頁面: ${BLUE}graph_visualization_demo.html${NC}"
echo -e "${GREEN}✓${NC} 配置指南: ${BLUE}OpenWebUI_圖譜視覺化配置指南.md${NC}"
echo -e "${GREEN}✓${NC} 快速開始: ${BLUE}啟動圖譜視覺化功能.md${NC}"
echo -e "${GREEN}✓${NC} 完成報告: ${BLUE}OpenWebUI_Neo4j_圖譜視覺化_完成報告.md${NC}"

echo ""
echo "======================================================================"
echo "🚀 下一步操作"
echo "======================================================================"
echo ""
echo "1. 在瀏覽器中打開演示頁面:"
echo -e "   ${BLUE}open graph_visualization_demo.html${NC}"
echo ""
echo "2. 上傳函數到 OpenWebUI:"
echo "   - 登入 OpenWebUI (http://localhost:3000)"
echo "   - Admin Panel → Functions → Create New Function"
echo -e "   - 上傳: ${BLUE}enhanced_openwebui_rag_function_v6_with_graph_viz.py${NC}"
echo ""
echo "3. 測試問答:"
echo "   - 選擇模型: 🚀 Llama 3.1 70B + Enhanced RAG"
echo "   - 提問: '達文西創作了哪些作品?'"
echo ""
echo "======================================================================"
echo -e "${GREEN}✨ 設置完成! 祝使用愉快!${NC}"
echo "======================================================================"
