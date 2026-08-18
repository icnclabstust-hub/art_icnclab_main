#!/bin/bash

# =============================================================================
# CUDA ML Service 啟動腳本
# =============================================================================

set -e

echo "🚀 啟動 CUDA ML Service..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 檢查CUDA環境
echo "🔍 檢查CUDA環境..."
if command -v nvidia-smi >/dev/null 2>&1; then
    echo "✅ NVIDIA GPU檢測:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader,nounits
else
    echo "⚠️  未檢測到NVIDIA GPU，將使用CPU模式"
fi

# 檢查CUDA版本
if command -v nvcc >/dev/null 2>&1; then
    echo "✅ CUDA版本: $(nvcc --version | grep release | awk '{print $6}')"
else
    echo "⚠️  未檢測到CUDA toolkit"
fi

# 設定環境變數
export PYTHONPATH=/app:$PYTHONPATH
export TORCH_HOME=/app/cache/torch
export HF_HOME=/app/cache/huggingface
export TRANSFORMERS_CACHE=/app/cache/transformers

# 創建必要目錄
mkdir -p /app/logs
mkdir -p /app/models
mkdir -p /app/data
mkdir -p /app/cache/torch
mkdir -p /app/cache/huggingface
mkdir -p /app/cache/transformers

# 設定日誌
LOG_FILE="/app/logs/ml-service-$(date +%Y%m%d-%H%M%S).log"
touch "$LOG_FILE"

# 健康檢查等待時間
HEALTH_CHECK_RETRIES=30
HEALTH_CHECK_INTERVAL=2

echo "📝 日誌檔案: $LOG_FILE"
echo "🔧 環境變數已設定"
echo "📁 目錄結構已創建"

# 檢查Python環境
echo "🐍 Python版本: $(python --version)"
echo "🔧 pip版本: $(pip --version)"

# 檢查關鍵依賴
echo "📦 檢查關鍵依賴..."
python -c "
import sys
import importlib

# 必需依賴
required_packages = [
    ('flask', 'Flask'),
    ('numpy', 'NumPy'),
    ('sklearn', 'Scikit-learn')
]

# 可選依賴
optional_packages = [
    ('torch', 'PyTorch'),
    ('transformers', 'Transformers'),
    ('pandas', 'Pandas')
]

missing_required = False

for package, name in required_packages:
    try:
        module = importlib.import_module(package)
        version = getattr(module, '__version__', 'Unknown')
        print(f'✅ {name}: {version}')
    except ImportError:
        print(f'❌ {name}: 未安裝')
        missing_required = True

for package, name in optional_packages:
    try:
        module = importlib.import_module(package)
        version = getattr(module, '__version__', 'Unknown')
        print(f'✅ {name}: {version}')
    except ImportError:
        print(f'❌ {name}: 未安裝')

if missing_required:
    print('❌ 缺少必需依賴')
    sys.exit(1)
else:
    print('✅ 基本依賴檢查通過')
"

if [ $? -ne 0 ]; then
    echo "❌ 依賴檢查失敗，正在安裝..."
    pip install --no-cache-dir --upgrade -r requirements.txt
fi

# 檢查GPU可用性
echo "🎮 檢查GPU可用性..."
python -c "
try:
    import torch
    print(f'PyTorch版本: {torch.__version__}')
    print(f'CUDA可用: {torch.cuda.is_available()}')
    if torch.cuda.is_available():
        print(f'CUDA版本: {torch.version.cuda}')
        print(f'GPU數量: {torch.cuda.device_count()}')
        for i in range(torch.cuda.device_count()):
            print(f'GPU {i}: {torch.cuda.get_device_name(i)}')
            print(f'記憶體: {torch.cuda.get_device_properties(i).total_memory / 1e9:.1f} GB')
except ImportError:
    print('⚠️ PyTorch未安裝，將使用CPU模擬模式')
    print('✅ 服務將以簡化模式啟動')
"

# 啟動服務
echo "🚀 啟動ML服務..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 選擇啟動模式
if [ "${FLASK_ENV:-production}" = "development" ]; then
    echo "🔧 開發模式啟動"
    exec python simple-app.py 2>&1 | tee -a "$LOG_FILE"
else
    echo "🏭 生產模式啟動"
    exec gunicorn \
        --bind 127.0.0.1:8080 \
        --workers ${GUNICORN_WORKERS:-4} \
        --worker-class gevent \
        --worker-connections ${GUNICORN_WORKER_CONNECTIONS:-1000} \
        --timeout ${GUNICORN_TIMEOUT:-300} \
        --keepalive ${GUNICORN_KEEPALIVE:-5} \
        --max-requests ${GUNICORN_MAX_REQUESTS:-1000} \
        --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER:-100} \
        --log-level info \
        --log-file "$LOG_FILE" \
        --access-logfile "$LOG_FILE" \
        --error-logfile "$LOG_FILE" \
        --capture-output \
        simple-app:app
fi