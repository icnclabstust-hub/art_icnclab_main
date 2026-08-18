#!/bin/bash
# CUDA深度學習環境配置腳本
# 為藝術史資料庫設置GPU加速環境

echo "🚀 配置CUDA深度學習環境"
echo "================================================"

# 檢查NVIDIA GPU
echo "🔍 檢查GPU硬件..."
nvidia-smi || echo "⚠️ NVIDIA GPU未檢測到"

# 檢查CUDA版本
echo "🔍 檢查CUDA版本..."
nvcc --version || echo "⚠️ CUDA編譯器未找到"

# 創建虛擬環境
echo "📦 創建Python虛擬環境..."
python3 -m venv cuda_art_env
source cuda_art_env/bin/activate

# 升級pip
echo "⬆️ 升級pip..."
pip install --upgrade pip

# 安裝PyTorch (CUDA 12.1)
echo "🔥 安裝PyTorch with CUDA 12.1..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 安裝深度學習依賴
echo "📚 安裝深度學習依賴..."
pip install sentence-transformers
pip install transformers
pip install datasets
pip install accelerate

# 安裝向量數據庫
echo "🗄️ 安裝向量數據庫..."
pip install faiss-gpu
pip install chromadb

# 安裝科學計算包
echo "🔬 安裝科學計算包..."
pip install numpy
pip install scipy
pip install scikit-learn
pip install pandas

# 安裝其他依賴
echo "🛠️ 安裝其他依賴..."
pip install tqdm
pip install matplotlib
pip install seaborn

# 測試CUDA環境
echo "🧪 測試CUDA環境..."
python3 -c "
import torch
print(f'PyTorch版本: {torch.__version__}')
print(f'CUDA可用: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU數量: {torch.cuda.device_count()}')
    print(f'當前GPU: {torch.cuda.get_device_name()}')
    print(f'GPU內存: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB')
"

echo "✅ CUDA環境配置完成！"
echo "================================================"
echo "💡 使用方法:"
echo "   source cuda_art_env/bin/activate"
echo "   python3 cuda_enhanced_rag.py"
echo "================================================"