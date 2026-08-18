#!/bin/bash

# ============================================================
# 藝術史資料庫 - LLM 模型下載腳本
# ============================================================
# 功能：下載所有需要的 Ollama 模型
# ============================================================

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_model() {
    echo -e "${PURPLE}🤖 $1${NC}"
}

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║          🤖 LLM 模型下載工具                          ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# 檢查 Ollama 容器是否運行
log_info "檢查 Ollama 服務狀態..."
if ! docker ps | grep -q art-history-ollama; then
    log_error "Ollama 容器未運行，請先執行 ./start-openwebui.sh"
    exit 1
fi
log_success "Ollama 服務正在運行"

# 定義要下載的模型列表
declare -A MODELS=(
    ["llama3.1:8b"]="Llama 3.1 8B - 通用能力，指令遵循（8GB）"
    ["qwen2.5:7b"]="Qwen 2.5 7B - 中文優化，平衡性能（7GB）"
    ["gemma2:2b"]="Gemma 2 2B - 輕量級，快速響應（2GB）"
    ["deepseek-r1:8b"]="DeepSeek-R1 8B - 推理專家（8GB）"
    ["nomic-embed-text"]="Nomic Embed Text - 向量嵌入模型（274MB）"
)

# 可選的大模型
declare -A OPTIONAL_MODELS=(
    ["llama3.1:70b"]="Llama 3.1 70B - 最強性能（40GB，需大量記憶體）"
    ["qwen2.5:14b"]="Qwen 2.5 14B - 更強中文能力（14GB）"
    ["mixtral:8x7b"]="Mixtral 8x7B - MoE 架構，高效（26GB）"
)

# 顯示可用模型
echo ""
log_info "可下載的模型："
echo ""
echo "必要模型（推薦全部下載）："
for model in "${!MODELS[@]}"; do
    echo "  🔹 $model - ${MODELS[$model]}"
done

echo ""
echo "可選模型（需要更多資源）："
for model in "${!OPTIONAL_MODELS[@]}"; do
    echo "  🔸 $model - ${OPTIONAL_MODELS[$model]}"
done

echo ""
read -p "是否下載所有必要模型？(y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_warning "已取消下載"
    exit 0
fi

# 下載必要模型
log_info "開始下載必要模型..."
echo ""

for model in "${!MODELS[@]}"; do
    log_model "下載模型: $model"
    echo "   描述: ${MODELS[$model]}"

    if docker exec art-history-ollama ollama pull "$model"; then
        log_success "模型 $model 下載完成"
    else
        log_error "模型 $model 下載失敗"
    fi
    echo ""
done

# 詢問是否下載可選模型
echo ""
read -p "是否下載可選的大型模型？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "下載可選模型..."
    echo ""

    for model in "${!OPTIONAL_MODELS[@]}"; do
        log_model "下載模型: $model"
        echo "   描述: ${OPTIONAL_MODELS[$model]}"

        read -p "   確認下載此模型？(y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            if docker exec art-history-ollama ollama pull "$model"; then
                log_success "模型 $model 下載完成"
            else
                log_error "模型 $model 下載失敗"
            fi
        else
            log_warning "跳過模型 $model"
        fi
        echo ""
    done
fi

# 顯示已下載的模型
echo ""
log_info "顯示所有已下載的模型："
echo ""
docker exec art-history-ollama ollama list

# 測試模型
echo ""
read -p "是否測試已下載的模型？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "測試模型 llama3.1:8b..."
    echo ""

    docker exec art-history-ollama ollama run llama3.1:8b "請用中文簡短介紹達文西的蒙娜麗莎" --verbose

    echo ""
    log_success "模型測試完成"
fi

# 顯示磁碟使用情況
echo ""
log_info "模型佔用空間："
docker exec art-history-ollama du -sh /root/.ollama/models 2>/dev/null || echo "無法獲取大小信息"

# 完成提示
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║               🎉 模型下載完成！                        ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
log_success "所有模型已成功下載"
echo ""
echo "📚 下一步："
echo "   1. 執行 ./register-models.sh 註冊 RAG 模型組合"
echo "   2. 訪問 http://localhost:8080 使用 OpenWebUI"
echo ""
echo "💡 提示："
echo "   • 查看模型列表: docker exec art-history-ollama ollama list"
echo "   • 刪除模型: docker exec art-history-ollama ollama rm <model-name>"
echo "   • 測試模型: docker exec -it art-history-ollama ollama run <model-name>"
echo ""
