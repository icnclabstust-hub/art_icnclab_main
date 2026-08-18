#!/bin/bash
# 快速CUDA深度學習環境配置腳本

echo "🚀 快速配置CUDA深度學習環境"
echo "===================================="

# 檢查虛擬環境
if [ ! -d "cuda_art_env" ]; then
    echo "📦 創建CUDA虛擬環境..."
    python3 -m venv cuda_art_env
fi

# 激活環境
echo "🔄 激活虛擬環境..."
source cuda_art_env/bin/activate

# 檢查PyTorch是否已安裝
echo "🔍 檢查PyTorch安裝狀態..."
if python -c "import torch" 2>/dev/null; then
    echo "✅ PyTorch已安裝"
    python -c "
import torch
print(f'PyTorch版本: {torch.__version__}')
print(f'CUDA可用: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU設備: {torch.cuda.get_device_name()}')
"
else
    echo "⏳ PyTorch正在安裝中或未安裝..."
    echo "   請等待後台安裝完成，或手動運行:"
    echo "   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"
fi

# 安裝其他依賴
echo "📚 安裝深度學習依賴..."

# 檢查並安裝sentence-transformers
if ! python -c "import sentence_transformers" 2>/dev/null; then
    echo "   安裝sentence-transformers..."
    pip install sentence-transformers --quiet
else
    echo "   ✅ sentence-transformers已安裝"
fi

# 檢查並安裝faiss
if ! python -c "import faiss" 2>/dev/null; then
    echo "   安裝faiss-gpu..."
    pip install faiss-gpu --quiet || pip install faiss-cpu --quiet
else
    echo "   ✅ faiss已安裝"
fi

# 檢查並安裝transformers
if ! python -c "import transformers" 2>/dev/null; then
    echo "   安裝transformers..."
    pip install transformers --quiet
else
    echo "   ✅ transformers已安裝"
fi

# 運行環境測試
echo ""
echo "🧪 運行環境測試..."
python3 test_cuda_readiness.py

echo ""
echo "🎉 CUDA環境配置完成！"
echo "===================================="
echo "📋 下一步:"
echo "   1. source cuda_art_env/bin/activate"
echo "   2. python3 cuda_enhanced_rag.py"
echo "   3. python3 cuda_art_history_integration.py"
echo "===================================="