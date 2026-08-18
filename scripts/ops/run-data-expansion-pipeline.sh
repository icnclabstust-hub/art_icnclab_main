#!/bin/bash
# 藝術史資料擴增完整流水線
# 整合爬蟲、向量化、RAG系統測試

set -e  # 遇到錯誤時停止

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日誌函數
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 檢查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 檢查服務是否運行
check_service() {
    local service_name=$1
    local service_url=$2

    log_info "檢查 $service_name..."

    if curl -s "$service_url" >/dev/null 2>&1; then
        log_success "$service_name 運行中"
        return 0
    else
        log_warning "$service_name 未運行"
        return 1
    fi
}

# 主程序
main() {
    log_info "🚀 啟動藝術史資料擴增流水線"
    echo "══════════════════════════════════════════════════════"

    # 1. 環境檢查
    log_info "步驟 1/4: 環境檢查"
    echo "──────────────────────────────────────────────────────"

    # 檢查必需的命令
    if ! command_exists node; then
        log_error "Node.js 未安裝"
        exit 1
    fi

    if ! command_exists python3; then
        log_error "Python 3 未安裝"
        exit 1
    fi

    log_success "命令檢查通過"

    # 檢查服務
    check_service "Neo4j" "http://localhost:7474" || true
    check_service "ChromaDB" "http://localhost:8001/api/v1/heartbeat" || true
    check_service "Ollama" "http://localhost:11434/api/tags" || true

    echo ""

    # 2. 執行爬蟲收集資料
    log_info "步驟 2/4: 執行爬蟲收集藝術史資料"
    echo "──────────────────────────────────────────────────────"

    if [ -f "expand-art-history-data.js" ]; then
        log_info "啟動資料收集爬蟲..."
        node expand-art-history-data.js

        if [ $? -eq 0 ]; then
            log_success "資料收集完成"
        else
            log_warning "資料收集部分失敗，繼續執行..."
        fi
    else
        log_error "找不到 expand-art-history-data.js"
        exit 1
    fi

    echo ""

    # 3. 向量化並整合到資料庫
    log_info "步驟 3/4: 向量化並整合到資料庫"
    echo "──────────────────────────────────────────────────────"

    if [ -f "integrate-to-vector-db.py" ]; then
        log_info "啟動向量化整合..."

        # 檢查是否需要安裝Python依賴
        if [ -f "langchain-rag/requirements.txt" ]; then
            log_info "檢查Python依賴..."
            pip3 install -q -r langchain-rag/requirements.txt 2>/dev/null || true
        fi

        python3 integrate-to-vector-db.py --hours 24

        if [ $? -eq 0 ]; then
            log_success "向量化整合完成"
        else
            log_warning "向量化整合部分失敗，繼續執行..."
        fi
    else
        log_error "找不到 integrate-to-vector-db.py"
        exit 1
    fi

    echo ""

    # 4. 測試RAG系統整合
    log_info "步驟 4/4: 測試RAG系統整合"
    echo "──────────────────────────────────────────────────────"

    if [ -f "../../tests/manual/test-rag-with-new-data.js" ]; then
        log_info "執行RAG整合測試..."
        node tests/manual/test-rag-with-new-data.js

        if [ $? -eq 0 ]; then
            log_success "RAG整合測試通過"
        else
            log_warning "RAG整合測試部分失敗"
        fi
    else
        log_warning "找不到 test-rag-with-new-data.js，跳過測試"
    fi

    echo ""

    # 完成摘要
    echo "══════════════════════════════════════════════════════"
    log_success "✨ 藝術史資料擴增流水線完成！"
    echo "══════════════════════════════════════════════════════"
    echo ""
    log_info "查看結果："
    echo "  1. 資料收集摘要: data-expansion-summary.json"
    echo "  2. ChromaDB 資料庫: http://localhost:8001"
    echo "  3. Neo4j 瀏覽器: http://localhost:7474"
    echo ""
    log_info "測試 RAG 系統："
    echo "  curl -X POST http://localhost:8007/api/v1/query \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    -d '{"
    echo "      \"query\": \"告訴我關於文藝復興時期的藝術\","
    echo "      \"model_combination_id\": \"llama3.1:8b@vector_only\","
    echo "      \"max_results\": 5"
    echo "    }'"
    echo ""
}

# 執行主程序
main "$@"
