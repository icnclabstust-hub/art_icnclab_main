#!/bin/bash

# ============================================================================
# MCP工具部署腳本
# 多模態RAG系統核心工具自動化部署
# ============================================================================

set -e

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

# 檢查必要條件
check_prerequisites() {
    log_info "檢查部署前置條件..."

    # 檢查Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker未安裝，請先安裝Docker"
        exit 1
    fi

    # 檢查docker-compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "docker-compose未安裝"
        exit 1
    fi

    # 檢查.env文件
    if [ ! -f ".env" ]; then
        log_error ".env文件不存在，請先配置環境變數"
        exit 1
    fi

    log_success "前置條件檢查通過"
}

# 建立必要的網路
create_networks() {
    log_info "建立Docker網路..."

    # 建立MCP工具專用網路
    docker network create mcp-network 2>/dev/null || log_warning "網路mcp-network已存在"

    # 確保主網路存在
    docker network create art-network 2>/dev/null || log_warning "網路art-network已存在"

    log_success "Docker網路建立完成"
}

# 建立必要的目錄
create_directories() {
    log_info "建立必要的目錄結構..."

    # 確保所有資料目錄存在
    mkdir -p {data/raw/{images,audio,video,documents},data/processed/embeddings/{text-vectors,image-vectors,audio-vectors}}
    mkdir -p {models/{language-models,embedding-models,vision},logs/experiments}
    mkdir -p context/monitoring

    # 設置適當的權限
    chmod -R 755 data/ models/ logs/

    log_success "目錄結構建立完成"
}

# 檢查API Keys
check_api_keys() {
    log_info "檢查API Keys配置..."

    source .env

    local missing_keys=()

    # 檢查必須的API keys
    if [[ "$OPENAI_API_KEY" == *"placeholder"* ]] || [ -z "$OPENAI_API_KEY" ]; then
        missing_keys+=("OPENAI_API_KEY")
    fi

    if [[ "$HUGGINGFACE_TOKEN" == *"placeholder"* ]] || [ -z "$HUGGINGFACE_TOKEN" ]; then
        missing_keys+=("HUGGINGFACE_TOKEN")
    fi

    if [[ "$DEEPL_API_KEY" == *"placeholder"* ]] || [ -z "$DEEPL_API_KEY" ]; then
        missing_keys+=("DEEPL_API_KEY")
    fi

    if [ ${#missing_keys[@]} -gt 0 ]; then
        log_warning "以下API Keys尚未配置: ${missing_keys[*]}"
        log_warning "將使用模擬模式部署，功能會受限"
        return 1
    else
        log_success "API Keys配置檢查通過"
        return 0
    fi
}

# 部署核心AI工具
deploy_ai_tools() {
    log_info "部署AI工具..."

    docker-compose -f docker-compose.mcp-core.yml --profile ai pull
    docker-compose -f docker-compose.mcp-core.yml --profile ai up -d

    log_success "AI工具部署完成"
}

# 部署多模態工具
deploy_multimodal_tools() {
    log_info "部署多模態處理工具..."

    docker-compose -f docker-compose.mcp-core.yml --profile multimodal --profile nlp --profile embeddings --profile translation --profile vision pull
    docker-compose -f docker-compose.mcp-core.yml --profile multimodal --profile nlp --profile embeddings --profile translation --profile vision up -d

    log_success "多模態工具部署完成"
}

# 部署向量資料庫工具
deploy_vector_tools() {
    log_info "部署向量資料庫工具..."

    docker-compose -f docker-compose.mcp-core.yml --profile vector-db pull
    docker-compose -f docker-compose.mcp-core.yml --profile vector-db up -d

    log_success "向量資料庫工具部署完成"
}

# 部署實驗管理工具
deploy_experiment_tools() {
    log_info "部署實驗管理工具..."

    docker-compose -f docker-compose.mcp-core.yml --profile experiment --profile optimization pull
    docker-compose -f docker-compose.mcp-core.yml --profile experiment --profile optimization up -d

    log_success "實驗管理工具部署完成"
}

# 部署爬取和監控工具
deploy_utility_tools() {
    log_info "部署工具類服務..."

    docker-compose -f docker-compose.mcp-core.yml --profile scraping --profile monitoring pull
    docker-compose -f docker-compose.mcp-core.yml --profile scraping --profile monitoring up -d

    log_success "工具類服務部署完成"
}

# 健康檢查
health_check() {
    log_info "執行服務健康檢查..."

    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        log_info "健康檢查第 $attempt/$max_attempts 次..."

        # 檢查主要服務端點
        local healthy_services=0
        local total_services=5

        # 檢查ChromaDB (已存在)
        if curl -s http://localhost:8000/api/v1/heartbeat > /dev/null 2>&1; then
            ((healthy_services++))
        fi

        # 檢查Neo4j (已存在)
        if curl -s http://localhost:7474 > /dev/null 2>&1; then
            ((healthy_services++))
        fi

        # 檢查OpenWebUI (已存在)
        if curl -s http://localhost:8080 > /dev/null 2>&1; then
            ((healthy_services++))
        fi

        # 檢查MLflow
        if curl -s http://localhost:5000 > /dev/null 2>&1; then
            ((healthy_services++))
        fi

        # 檢查主應用API
        if curl -s http://localhost:3000/health > /dev/null 2>&1; then
            ((healthy_services++))
        fi

        if [ $healthy_services -ge 4 ]; then
            log_success "健康檢查通過 ($healthy_services/$total_services 服務正常)"
            return 0
        fi

        sleep 10
        ((attempt++))
    done

    log_warning "部分服務可能未完全啟動，請檢查服務狀態"
    return 1
}

# 顯示服務狀態
show_services_status() {
    log_info "當前服務狀態:"
    echo
    docker-compose -f docker-compose.mcp-core.yml ps
    echo

    log_info "服務端點摘要:"
    echo "🌐 主應用API:          http://localhost:3000"
    echo "🤖 OpenWebUI:          http://localhost:8080"
    echo "📊 Neo4j Browser:      http://localhost:7474"
    echo "🗂️ ChromaDB:           http://localhost:8000"
    echo "📈 MLflow:             http://localhost:5000"
    echo "🔧 Grafana:            http://localhost:3001"
    echo "⚡ Prometheus:         http://localhost:9090"
    echo
}

# 主要部署函數
main_deploy() {
    local mode=${1:-"full"}

    log_info "開始部署多模態RAG系統MCP工具 (模式: $mode)"

    check_prerequisites
    create_networks
    create_directories

    # 檢查API keys，但不阻止部署
    check_api_keys || log_warning "將在模擬模式下繼續部署"

    case $mode in
        "ai")
            deploy_ai_tools
            ;;
        "multimodal")
            deploy_multimodal_tools
            ;;
        "vector")
            deploy_vector_tools
            ;;
        "experiment")
            deploy_experiment_tools
            ;;
        "utilities")
            deploy_utility_tools
            ;;
        "essential")
            # 部署最基本的工具
            deploy_multimodal_tools
            deploy_experiment_tools
            ;;
        "full")
            # 部署所有工具（如果API keys可用）
            if check_api_keys; then
                deploy_ai_tools
                deploy_multimodal_tools
                deploy_vector_tools
                deploy_experiment_tools
                deploy_utility_tools
            else
                log_info "API Keys未完全配置，部署基礎工具"
                deploy_multimodal_tools
                deploy_experiment_tools
                deploy_utility_tools
            fi
            ;;
        *)
            log_error "未知的部署模式: $mode"
            log_info "可用模式: ai, multimodal, vector, experiment, utilities, essential, full"
            exit 1
            ;;
    esac

    log_info "等待服務啟動..."
    sleep 30

    health_check
    show_services_status

    log_success "MCP工具部署完成！"
}

# 清理函數
cleanup() {
    log_info "清理MCP工具..."
    docker-compose -f docker-compose.mcp-core.yml down --remove-orphans
    log_success "清理完成"
}

# 腳本入口
case "${1:-deploy}" in
    "deploy")
        main_deploy "${2:-full}"
        ;;
    "cleanup")
        cleanup
        ;;
    "status")
        show_services_status
        ;;
    "health")
        health_check
        ;;
    *)
        echo "使用方式: $0 {deploy|cleanup|status|health} [mode]"
        echo "  deploy modes: ai, multimodal, vector, experiment, utilities, essential, full"
        exit 1
        ;;
esac