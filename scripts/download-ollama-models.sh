#!/bin/bash
# Ollama 模型下載腳本

set -e

# 顏色定義
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🦙 Ollama 模型下載腳本${NC}"
echo "======================================="

# 檢查 Ollama 服務
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️ Ollama 服務未運行，請先執行: ollama serve${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Ollama 服務正常運行${NC}"
echo ""

# 顯示可用空間
echo "💾 磁碟空間檢查:"
df -h . | tail -1
echo ""

echo "🎯 建議的模型配置:"
echo ""

# 配置選項
echo "請選擇您的配置方案:"
echo "1) 🚀 完整配置 (~6GB) - llama3.1:8b + mxbai-embed-large"
echo "2) ⚖️ 平衡配置 (~5GB) - llama3:8b + mxbai-embed-large"
echo "3) 💡 輕量配置 (~4.5GB) - mistral:7b + nomic-embed-text"
echo "4) 🇨🇳 中文優化 (~5GB) - qwen2:7b + mxbai-embed-large"
echo "5) 🔧 自訂配置 - 手動選擇模型"

read -p "請輸入選項 (1-5): " choice

case $choice in
    1)
        echo -e "${BLUE}📥 下載完整配置模型...${NC}"
        LLM_MODEL="llama3.1:8b"
        EMBED_MODEL="mxbai-embed-large"
        ;;
    2)
        echo -e "${BLUE}📥 下載平衡配置模型...${NC}"
        LLM_MODEL="llama3:8b"
        EMBED_MODEL="mxbai-embed-large"
        ;;
    3)
        echo -e "${BLUE}📥 下載輕量配置模型...${NC}"
        LLM_MODEL="mistral:7b"
        EMBED_MODEL="nomic-embed-text"
        ;;
    4)
        echo -e "${BLUE}📥 下載中文優化配置模型...${NC}"
        LLM_MODEL="qwen2:7b"
        EMBED_MODEL="mxbai-embed-large"
        ;;
    5)
        echo -e "${BLUE}🔧 自訂配置模式${NC}"
        echo "可用的 LLM 模型:"
        echo "  - llama3.1:8b (推薦，最新)"
        echo "  - llama3:8b (穩定)"
        echo "  - mistral:7b (輕量)"
        echo "  - qwen2:7b (中文優化)"

        read -p "請輸入 LLM 模型名稱: " LLM_MODEL

        echo "可用的 Embedding 模型:"
        echo "  - mxbai-embed-large (推薦，高品質)"
        echo "  - nomic-embed-text (輕量)"

        read -p "請輸入 Embedding 模型名稱: " EMBED_MODEL
        ;;
    *)
        echo -e "${YELLOW}⚠️ 無效選項，使用預設配置 (llama3.1:8b + mxbai-embed-large)${NC}"
        LLM_MODEL="llama3.1:8b"
        EMBED_MODEL="mxbai-embed-large"
        ;;
esac

echo ""
echo -e "${BLUE}開始下載模型:${NC}"
echo "📋 LLM 模型: $LLM_MODEL"
echo "📋 Embedding 模型: $EMBED_MODEL"
echo ""

# 下載 LLM 模型
echo -e "${BLUE}⬇️ 下載 LLM 模型: $LLM_MODEL${NC}"
if ollama pull "$LLM_MODEL"; then
    echo -e "${GREEN}✅ $LLM_MODEL 下載完成${NC}"
else
    echo -e "${YELLOW}❌ $LLM_MODEL 下載失敗${NC}"
fi

echo ""

# 下載 Embedding 模型
echo -e "${BLUE}⬇️ 下載 Embedding 模型: $EMBED_MODEL${NC}"
if ollama pull "$EMBED_MODEL"; then
    echo -e "${GREEN}✅ $EMBED_MODEL 下載完成${NC}"
else
    echo -e "${YELLOW}❌ $EMBED_MODEL 下載失敗${NC}"
fi

echo ""
echo -e "${GREEN}🎉 模型下載完成！${NC}"

# 檢查已安裝的模型
echo ""
echo -e "${BLUE}📋 已安裝的模型列表:${NC}"
ollama list

echo ""
echo -e "${BLUE}🧪 快速測試模型功能...${NC}"

# 測試 LLM 模型
echo "測試 $LLM_MODEL..."
RESPONSE=$(ollama run "$LLM_MODEL" "請用中文簡短介紹文藝復興藝術" --verbose=false 2>/dev/null | head -1 || echo "測試失敗")
echo "回應: $RESPONSE"

echo ""
echo -e "${BLUE}📝 建議的 .env 配置:${NC}"
echo "USE_OLLAMA=true"
echo "OLLAMA_BASE_URL=http://localhost:11434"
echo "OLLAMA_DEFAULT_MODEL=$LLM_MODEL"
echo "OLLAMA_EMBEDDING_MODEL=$EMBED_MODEL"
echo "OLLAMA_TIMEOUT=120000"

echo ""
echo -e "${GREEN}✅ 設定完成！現在可以執行整合測試:${NC}"
echo "node scripts/test-ollama-integration.js"