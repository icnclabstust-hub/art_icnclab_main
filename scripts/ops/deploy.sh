#!/bin/bash

# =============================================================================
# 藝術史資料庫系統部署腳本
# Docker Compose 優化版本部署
# =============================================================================

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 顯示橫幅
show_banner() {
    echo -e "${CYAN}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🎨 藝術史資料庫系統 - Docker Compose 部署腳本"
    echo "🚀 CUDA/GPU ML服務整合 | 多模態RAG | 監控完整"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${NC}"
}

# 日誌功能
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️  $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ❌ $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] ℹ️  $1${NC}"
}

# 檢查先決條件
check_prerequisites() {
    log "檢查系統先決條件..."

    # 檢查Docker
    if ! command -v docker >/dev/null 2>&1; then
        error "Docker未安裝，請先安裝Docker"
        exit 1
    fi

    # 檢查Docker Compose
    if ! docker compose version >/dev/null 2>&1; then
        error "Docker Compose未安裝或版本過舊"
        exit 1
    fi

    # 檢查NVIDIA Container Toolkit (用於GPU支援)
    if command -v nvidia-smi >/dev/null 2>&1; then
        if ! docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi >/dev/null 2>&1; then
            warn "NVIDIA Container Toolkit未正確安裝，GPU功能將不可用"
        else
            log "✅ NVIDIA GPU支援已就緒"
        fi
    else
        warn "未檢測到NVIDIA GPU"
    fi

    # 檢查必要檔案
    local required_files=(
        "docker-compose.optimized.yml"
        ".env"
        "ml-service/Dockerfile"
        "ml-service/requirements.txt"
        "../../ml-service/start.sh"
        "config/nginx/nginx.conf"
        "../../monitoring/prometheus.yml"
    )

    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            error "必要檔案不存在: $file"
            exit 1
        fi
    done

    log "✅ 先決條件檢查完成"
}

# 環境變數檢查
check_environment() {
    log "檢查環境變數配置..."

    if [[ ! -f ".env" ]]; then
        error ".env 檔案不存在"
        exit 1
    fi

    # 檢查關鍵環境變數
    source .env

    local required_vars=(
        "POSTGRES_PASSWORD"
        "DB_NAME"
        "DB_USER"
    )

    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            error "環境變數 $var 未設定"
            exit 1
        fi
    done

    log "✅ 環境變數檢查完成"
}

# 建立必要目錄
create_directories() {
    log "建立必要目錄結構..."

    local directories=(
        "data/raw"
        "data/processed"
        "data/output"
        "logs"
        "models"
        "cache"
        "ssl"
        "backups"
        "notebooks"
        "ml-data"
        "monitoring/grafana/dashboards"
        "monitoring/grafana/datasources"
        "monitoring/alerts"
        "database/init"
        "database/schema"
    )

    for dir in "${directories[@]}"; do
        mkdir -p "$dir"
        info "建立目錄: $dir"
    done

    # 設定權限
    chmod +x ml-service/start.sh
    chmod 755 data logs models cache

    log "✅ 目錄結構建立完成"
}

# 清理舊容器和網路
cleanup_old_deployment() {
    log "清理舊的部署..."

    # 停止並移除舊容器
    if docker compose -f docker-compose.optimized.yml ps -q >/dev/null 2>&1; then
        docker compose -f docker-compose.optimized.yml down --remove-orphans || true
    fi

    # 清理未使用的資源
    docker system prune -f --volumes || true

    log "✅ 舊部署清理完成"
}

# 建立Docker鏡像
build_images() {
    log "建立Docker鏡像..."

    # 建立ML服務鏡像
    info "建立CUDA ML服務鏡像..."
    docker compose -f docker-compose.optimized.yml build cuda-ml-service

    # 建立主API服務鏡像
    if [[ -f "Dockerfile" ]]; then
        info "建立主API服務鏡像..."
        docker compose -f docker-compose.optimized.yml build art-database-api
    else
        warn "主API服務Dockerfile不存在，跳過建立"
    fi

    log "✅ Docker鏡像建立完成"
}

# 部署服務
deploy_services() {
    log "部署服務..."

    # 分階段啟動服務以確保依賴關係正確
    info "啟動基礎設施服務 (資料庫、快取、搜索引擎)..."
    docker compose -f docker-compose.optimized.yml up -d \
        postgres redis elasticsearch neo4j chromadb

    # 等待資料庫啟動
    info "等待資料庫服務準備就緒..."
    sleep 30

    info "啟動監控服務..."
    docker compose -f docker-compose.optimized.yml up -d \
        prometheus grafana node-exporter

    info "啟動ML服務..."
    docker compose -f docker-compose.optimized.yml up -d \
        cuda-ml-service jupyter mlflow

    # 等待ML服務啟動
    info "等待ML服務準備就緒..."
    sleep 45

    info "啟動主API服務..."
    docker compose -f docker-compose.optimized.yml up -d \
        art-database-api

    info "啟動反向代理..."
    docker compose -f docker-compose.optimized.yml up -d \
        nginx

    log "✅ 服務部署完成"
}

# 健康檢查
health_check() {
    log "執行系統健康檢查..."

    local services=(
        "postgres:5432"
        "redis:6379"
        "elasticsearch:9200"
        "neo4j:7474"
        "chromadb:8000"
        "cuda-ml-service:8080"
        "prometheus:9090"
        "grafana:3000"
    )

    for service in "${services[@]}"; do
        local name="${service%:*}"
        local port="${service#*:}"

        info "檢查 $name 服務..."

        local retries=0
        local max_retries=30

        while [[ $retries -lt $max_retries ]]; do
            if docker compose -f docker-compose.optimized.yml exec -T "$name" \
                timeout 5 bash -c "echo >/dev/tcp/localhost/$port" 2>/dev/null; then
                log "✅ $name 服務健康"
                break
            fi

            retries=$((retries + 1))
            if [[ $retries -eq $max_retries ]]; then
                error "$name 服務健康檢查失敗"
                return 1
            fi

            sleep 2
        done
    done

    log "✅ 系統健康檢查完成"
}

# 顯示部署狀態
show_deployment_status() {
    log "部署狀態總覽:"
    echo ""

    # 顯示容器狀態
    info "容器狀態:"
    docker compose -f docker-compose.optimized.yml ps

    echo ""
    info "服務存取端點:"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}🌐 主要服務:${NC}"
    echo -e "   • 主API: http://localhost:3000/api"
    echo -e "   • ML服務: http://localhost:8080/health"
    echo -e "   • Swagger文檔: http://localhost:3000/api/docs"
    echo ""
    echo -e "${GREEN}📊 監控面板:${NC}"
    echo -e "   • Grafana: http://localhost:3001 (admin/\${GRAFANA_PASSWORD})"
    echo -e "   • Prometheus: http://localhost:9090"
    echo -e "   • Jupyter Lab: http://localhost:8888 (token: \${JUPYTER_TOKEN})"
    echo ""
    echo -e "${GREEN}💾 資料庫:${NC}"
    echo -e "   • PostgreSQL: localhost:5432"
    echo -e "   • Redis: localhost:6379"
    echo -e "   • Elasticsearch: http://localhost:9200"
    echo -e "   • Neo4j: http://localhost:7474"
    echo -e "   • ChromaDB: http://localhost:8000"
    echo ""
    echo -e "${GREEN}🔬 實驗管理:${NC}"
    echo -e "   • MLflow: http://localhost:5000"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# 主要部署流程
main() {
    show_banner

    # 解析命令行參數
    local action="${1:-deploy}"

    case "$action" in
        "deploy"|"up")
            check_prerequisites
            check_environment
            create_directories
            cleanup_old_deployment
            build_images
            deploy_services
            health_check
            show_deployment_status
            log "🎉 部署成功完成！"
            ;;
        "down"|"stop")
            log "停止所有服務..."
            docker compose -f docker-compose.optimized.yml down --remove-orphans
            log "✅ 服務已停止"
            ;;
        "restart")
            log "重啟服務..."
            docker compose -f docker-compose.optimized.yml restart
            health_check
            log "✅ 服務已重啟"
            ;;
        "logs")
            info "顯示服務日誌..."
            docker compose -f docker-compose.optimized.yml logs -f
            ;;
        "status")
            show_deployment_status
            ;;
        "clean")
            log "清理所有資源..."
            docker compose -f docker-compose.optimized.yml down -v --remove-orphans
            docker system prune -a -f --volumes
            log "✅ 清理完成"
            ;;
        *)
            echo "用法: $0 {deploy|up|down|stop|restart|logs|status|clean}"
            echo ""
            echo "指令說明:"
            echo "  deploy/up  - 完整部署系統"
            echo "  down/stop  - 停止所有服務"
            echo "  restart    - 重啟服務"
            echo "  logs       - 顯示服務日誌"
            echo "  status     - 顯示部署狀態"
            echo "  clean      - 清理所有資源"
            exit 1
            ;;
    esac
}

# 執行主流程
main "$@"