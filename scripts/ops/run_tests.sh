#!/bin/bash

# 藝術史資料庫自動化測試腳本

set -e  # 遇到錯誤立即退出

echo "🧪 藝術史資料庫自動化測試"
echo "======================================"
echo ""

# 顏色定義
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 檢查Python環境
echo "🔍 檢查Python環境..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 未安裝${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}✅ Python版本: ${PYTHON_VERSION}${NC}"
echo ""

# 檢查必要的依賴
echo "🔍 檢查依賴套件..."
cd art-history-database/langchain-rag

REQUIRED_PACKAGES=("requests" "neo4j" "pytest")
MISSING_PACKAGES=()

for package in "${REQUIRED_PACKAGES[@]}"; do
    if ! python3 -c "import $package" 2>/dev/null; then
        MISSING_PACKAGES+=("$package")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo -e "${YELLOW}⚠️  缺少以下套件: ${MISSING_PACKAGES[*]}${NC}"
    echo "正在安裝..."
    pip3 install "${MISSING_PACKAGES[@]}"
fi

echo -e "${GREEN}✅ 所有依賴已就緒${NC}"
echo ""

# 檢查服務狀態
echo "🔍 檢查服務狀態..."

# 檢查Neo4j
if curl -s http://localhost:7474 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Neo4j 服務運行中${NC}"
else
    echo -e "${YELLOW}⚠️  Neo4j 服務未運行 (部分測試將被跳過)${NC}"
fi

# 檢查API服務
if curl -s http://localhost:8008/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API 服務運行中${NC}"
else
    echo -e "${YELLOW}⚠️  API 服務未運行 (部分測試將被跳過)${NC}"
fi

echo ""

# 運行測試
echo "🚀 開始運行測試..."
echo "======================================"
echo ""

# 使用pytest如果可用，否則使用unittest
if command -v pytest &> /dev/null; then
    echo "使用pytest運行測試..."
    pytest test_suite.py -v --tb=short --color=yes
    TEST_EXIT_CODE=$?
else
    echo "使用unittest運行測試..."
    python3 test_suite.py
    TEST_EXIT_CODE=$?
fi

echo ""
echo "======================================"

# 檢查測試結果
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ 所有測試通過！${NC}"

    # 生成測試覆蓋率報告（如果有coverage工具）
    if command -v coverage &> /dev/null; then
        echo ""
        echo "📊 生成測試覆蓋率報告..."
        coverage run -m pytest test_suite.py
        coverage report
        coverage html
        echo -e "${GREEN}✅ 覆蓋率報告已生成到 htmlcov/index.html${NC}"
    fi
else
    echo -e "${RED}❌ 測試失敗！${NC}"
    echo "請檢查 test_report.json 查看詳細信息"
fi

echo ""
echo "📁 測試報告已保存到:"
echo "  - test_report.json (JSON格式)"
if [ -f "htmlcov/index.html" ]; then
    echo "  - htmlcov/index.html (覆蓋率報告)"
fi

echo ""
echo "🎉 測試完成！"

exit $TEST_EXIT_CODE
