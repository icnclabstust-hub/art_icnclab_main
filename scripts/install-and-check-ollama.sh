#!/bin/bash
# Ollama 安裝和整合檢查腳本

set -e

echo "🦙 開始 Ollama 安裝和整合檢查..."
echo "================================================"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 函數定義
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

# 1. 檢查系統資訊
echo ""
log_info "步驟 1: 檢查系統資訊"
echo "系統: $(uname -s)"
echo "架構: $(uname -m)"
echo "用戶: $(whoami)"
echo "Python: $(python3 --version 2>/dev/null || echo 'Not found')"
echo "Node.js: $(node --version 2>/dev/null || echo 'Not found')"
echo "記憶體: $(free -h 2>/dev/null | grep Mem || echo 'Memory info not available')"

# 2. 檢查是否已安裝 Ollama
echo ""
log_info "步驟 2: 檢查 Ollama 安裝狀態"
if command -v ollama &> /dev/null; then
    OLLAMA_VERSION=$(ollama --version 2>/dev/null || echo "unknown")
    log_success "Ollama 已安裝: $OLLAMA_VERSION"
    OLLAMA_INSTALLED=true
else
    log_warning "Ollama 尚未安裝"
    OLLAMA_INSTALLED=false
fi

# 3. 安裝 Ollama (如果未安裝)
if [ "$OLLAMA_INSTALLED" = false ]; then
    echo ""
    log_info "步驟 3: 安裝 Ollama"

    # 檢查是否在 WSL 環境
    if grep -qi microsoft /proc/version 2>/dev/null; then
        log_info "檢測到 WSL 環境"
        echo "請在 Windows 主機上執行以下命令安裝 Ollama:"
        echo "1. 訪問 https://ollama.com/download"
        echo "2. 下載 Windows 版本並安裝"
        echo "3. 或使用 PowerShell: winget install ollama"
        echo ""
        log_warning "WSL 環境下建議在 Windows 主機安裝 Ollama，然後通過網路存取"
        read -p "是否已在 Windows 主機安裝 Ollama? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "將測試通過 localhost:11434 連接 Ollama..."
        else
            log_error "請先安裝 Ollama 後再執行此腳本"
            exit 1
        fi
    else
        log_info "嘗試自動安裝 Ollama..."
        if curl -fsSL https://ollama.com/install.sh | sh; then
            log_success "Ollama 安裝成功"
            OLLAMA_INSTALLED=true
        else
            log_error "自動安裝失敗，請手動安裝:"
            echo "curl -fsSL https://ollama.com/install.sh | sh"
            exit 1
        fi
    fi
fi

# 4. 啟動 Ollama 服務
echo ""
log_info "步驟 4: 檢查和啟動 Ollama 服務"

# 檢查服務是否運行
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    log_success "Ollama 服務已運行"
else
    log_warning "Ollama 服務未運行，嘗試啟動..."

    # 嘗試在背景啟動
    if command -v ollama &> /dev/null; then
        log_info "在背景啟動 Ollama 服務..."
        nohup ollama serve > /tmp/ollama.log 2>&1 &
        OLLAMA_PID=$!
        log_info "Ollama 服務已在背景啟動 (PID: $OLLAMA_PID)"

        # 等待服務啟動
        log_info "等待服務啟動..."
        for i in {1..30}; do
            if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
                log_success "Ollama 服務啟動成功"
                break
            fi
            echo -n "."
            sleep 1
        done
        echo ""

        # 再次檢查
        if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            log_error "Ollama 服務啟動失敗"
            log_info "請手動執行: ollama serve"
            exit 1
        fi
    else
        log_error "找不到 ollama 命令，請確認安裝正確"
        exit 1
    fi
fi

# 5. 檢查可用模型
echo ""
log_info "步驟 5: 檢查已安裝的模型"
MODELS_RESPONSE=$(curl -s http://localhost:11434/api/tags 2>/dev/null || echo "")

if [ -n "$MODELS_RESPONSE" ]; then
    echo "Ollama 服務回應:"
    echo "$MODELS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$MODELS_RESPONSE"

    # 檢查是否有推薦模型
    echo ""
    log_info "檢查推薦模型..."

    RECOMMENDED_MODELS=("gemma4:12B" "qwen3:14b" "qwen3:8b" "qwen3-vl:8b" "mxbai-embed-large" "nomic-embed-text")
    MISSING_MODELS=()

    for model in "${RECOMMENDED_MODELS[@]}"; do
        if echo "$MODELS_RESPONSE" | grep -q "$model"; then
            log_success "模型已安裝: $model"
        else
            log_warning "模型未安裝: $model"
            MISSING_MODELS+=("$model")
        fi
    done

    # 提示下載缺失模型
    if [ ${#MISSING_MODELS[@]} -gt 0 ]; then
        echo ""
        log_info "建議安裝以下模型以獲得最佳體驗:"
        for model in "${MISSING_MODELS[@]}"; do
            echo "  ollama pull $model"
        done
        echo ""
        read -p "是否現在下載必要模型? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "開始下載模型..."

            # 下載基本 LLM 模型（使用推薦模型）
            if echo "${MISSING_MODELS[@]}" | grep -q "gemma4:12B"; then
                log_info "下載 gemma4:12B (這可能需要較長時間)..."
                ollama pull gemma4:12B
                log_success "gemma4:12B 下載完成"
            elif echo "${MISSING_MODELS[@]}" | grep -q "qwen3:14b"; then
                log_info "下載 qwen3:14b..."
                ollama pull qwen3:14b
                log_success "qwen3:14b 下載完成"
            elif echo "${MISSING_MODELS[@]}" | grep -q "qwen3:8b"; then
                log_info "下載 qwen3:8b..."
                ollama pull qwen3:8b
                log_success "qwen3:8b 下載完成"
            elif echo "${MISSING_MODELS[@]}" | grep -q "qwen3-vl:8b"; then
                log_info "下載 qwen3-vl:8b..."
                ollama pull qwen3-vl:8b
                log_success "qwen3-vl:8b 下載完成"
            fi

            # 下載 embedding 模型
            if echo "${MISSING_MODELS[@]}" | grep -q "mxbai-embed-large"; then
                log_info "下載 mxbai-embed-large..."
                ollama pull mxbai-embed-large
                log_success "mxbai-embed-large 下載完成"
            elif echo "${MISSING_MODELS[@]}" | grep -q "nomic-embed-text"; then
                log_info "下載 nomic-embed-text..."
                ollama pull nomic-embed-text
                log_success "nomic-embed-text 下載完成"
            fi
        fi
    fi

else
    log_error "無法連接到 Ollama 服務"
    exit 1
fi

# 6. 測試基本功能
echo ""
log_info "步驟 6: 測試 Ollama 基本功能"

# 測試文本生成
log_info "測試文本生成..."
TEST_RESPONSE=$(curl -s -X POST http://localhost:11434/api/generate -d '{
    "model": "gemma4:12B",
  "prompt": "請用中文簡短回答：什麼是藝術史？",
  "stream": false,
  "options": {"num_predict": 50}
}' 2>/dev/null || echo "")

if [ -n "$TEST_RESPONSE" ] && echo "$TEST_RESPONSE" | grep -q "response"; then
    log_success "文本生成測試通過"
    RESPONSE_TEXT=$(echo "$TEST_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('response', 'No response'))" 2>/dev/null || echo "解析失敗")
    echo "回應: $RESPONSE_TEXT"
else
    log_warning "文本生成測試失敗或模型未找到"
    echo "回應: $TEST_RESPONSE"
fi

# 7. 測試系統整合
echo ""
log_info "步驟 7: 測試與藝術史資料系統整合"

# 檢查整合測試腳本
if [ -f "test-ollama-integration.js" ]; then
    log_info "執行整合測試..."
    if node scripts/test-ollama-integration.js; then
        log_success "系統整合測試通過"
    else
        log_warning "系統整合測試部分失敗，請檢查詳細輸出"
    fi
else
    log_warning "整合測試腳本不存在，創建簡單測試..."

    # 創建簡單的 Node.js 測試
    cat > /tmp/simple_ollama_test.js << 'EOF'
const axios = require('axios');

async function testOllamaIntegration() {
    try {
        console.log('🧪 測試 Ollama 連接...');

        // 測試服務健康狀態
        const healthResponse = await axios.get('http://localhost:11434/api/tags', { timeout: 5000 });
        console.log('✅ Ollama 服務連接正常');
        console.log(`📋 可用模型數量: ${healthResponse.data.models ? healthResponse.data.models.length : 0}`);

        // 測試文本生成
        const generateResponse = await axios.post('http://localhost:11434/api/generate', {
            model: 'gemma4:12B',
            prompt: '藝術史',
            stream: false,
            options: { num_predict: 30 }
        }, { timeout: 30000 });

        if (generateResponse.data.response) {
            console.log('✅ 文本生成功能正常');
            console.log(`📝 生成內容: ${generateResponse.data.response.substring(0, 100)}...`);
        }

        console.log('🎉 Ollama 整合測試成功！');
        return true;

    } catch (error) {
        console.error('❌ 整合測試失敗:', error.message);
        return false;
    }
}

testOllamaIntegration().then(success => {
    process.exit(success ? 0 : 1);
});
EOF

    if node /tmp/simple_ollama_test.js; then
        log_success "簡單整合測試通過"
    else
        log_error "簡單整合測試失敗"
    fi
fi

# 8. 生成配置建議
echo ""
log_info "步驟 8: 生成配置建議"

echo ""
echo "🔧 建議的環境變數配置 (.env):"
echo "USE_OLLAMA=true"
echo "OLLAMA_BASE_URL=http://localhost:11434"

# 根據安裝的模型推薦配置
if echo "$MODELS_RESPONSE" | grep -q "llama3.1:8b"; then
    echo "OLLAMA_DEFAULT_MODEL=llama3.1:8b"
elif echo "$MODELS_RESPONSE" | grep -q "llama3:8b"; then
    echo "OLLAMA_DEFAULT_MODEL=llama3:8b"
elif echo "$MODELS_RESPONSE" | grep -q "mistral:7b"; then
    echo "OLLAMA_DEFAULT_MODEL=mistral:7b"
fi

if echo "$MODELS_RESPONSE" | grep -q "mxbai-embed-large"; then
    echo "OLLAMA_EMBEDDING_MODEL=mxbai-embed-large"
elif echo "$MODELS_RESPONSE" | grep -q "nomic-embed-text"; then
    echo "OLLAMA_EMBEDDING_MODEL=nomic-embed-text"
fi

echo "OLLAMA_TIMEOUT=120000"

# 9. 總結報告
echo ""
echo "================================================"
log_info "安裝和整合檢查完成！"
echo ""

echo "📊 檢查結果摘要:"
if [ "$OLLAMA_INSTALLED" = true ]; then
    echo "  ✅ Ollama 安裝狀態: 已安裝"
else
    echo "  ❌ Ollama 安裝狀態: 未安裝"
fi

if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "  ✅ 服務運行狀態: 正常"
else
    echo "  ❌ 服務運行狀態: 異常"
fi

MODEL_COUNT=$(echo "$MODELS_RESPONSE" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('models', [])))" 2>/dev/null || echo "0")
echo "  📋 已安裝模型: $MODEL_COUNT 個"

echo ""
echo "🚀 下一步建議:"
echo "1. 確保 .env 文件包含上述配置"
echo "2. 重新啟動藝術史資料系統"
echo "3. 執行完整整合測試: node scripts/test-ollama-integration.js"
echo "4. 開始使用本地 AI 功能！"

echo ""
log_success "🎉 Ollama 已準備就緒，可以與藝術史資料系統協同工作！"