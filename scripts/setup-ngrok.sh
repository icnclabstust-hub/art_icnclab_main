#!/bin/bash

# ngrok 快速設置腳本
# 用途: 快速將 Open WebUI 暴露到公網（適合測試）

set -e

echo "======================================"
echo "  ngrok 快速設置腳本"
echo "  5分鐘內完成公網訪問配置"
echo "======================================"
echo ""

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 步驟 1: 檢查並安裝 ngrok
echo -e "${YELLOW}[1/4] 檢查 ngrok 安裝狀態...${NC}"

if ! command -v ngrok &> /dev/null; then
    echo "ngrok 未安裝，開始安裝..."

    # 檢測系統
    if [ -f /etc/debian_version ]; then
        # Debian/Ubuntu
        curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
        echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
        sudo apt update
        sudo apt install ngrok -y
    else
        # 其他系統 - 手動下載
        echo "正在下載 ngrok..."
        wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
        tar xvzf ngrok-v3-stable-linux-amd64.tgz
        sudo mv ngrok /usr/local/bin/
        rm ngrok-v3-stable-linux-amd64.tgz
    fi

    echo -e "${GREEN}✓ ngrok 安裝完成${NC}"
else
    echo -e "${GREEN}✓ ngrok 已安裝${NC}"
    ngrok version
fi

echo ""

# 步驟 2: 配置 authtoken
echo -e "${YELLOW}[2/4] 配置 ngrok authtoken...${NC}"
echo ""
echo -e "${BLUE}請按照以下步驟獲取 authtoken:${NC}"
echo "1. 訪問 https://dashboard.ngrok.com/signup"
echo "2. 註冊或登入 ngrok 帳號（支援 Google/GitHub 登入）"
echo "3. 訪問 https://dashboard.ngrok.com/get-started/your-authtoken"
echo "4. 複製您的 authtoken"
echo ""

read -p "請輸入您的 ngrok authtoken: " AUTHTOKEN

if [ -z "$AUTHTOKEN" ]; then
    echo -e "${RED}✗ authtoken 不能為空${NC}"
    exit 1
fi

ngrok config add-authtoken "$AUTHTOKEN"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ authtoken 配置成功${NC}"
else
    echo -e "${RED}✗ authtoken 配置失敗${NC}"
    exit 1
fi

echo ""

# 步驟 3: 創建配置文件
echo -e "${YELLOW}[3/4] 創建 ngrok 配置...${NC}"

cat > ~/.ngrok.yml <<EOF
version: "2"
authtoken: $AUTHTOKEN

tunnels:
  art-history-web:
    proto: http
    addr: 80
    bind_tls: true
    inspect: true

region: ap  # 亞太地區（較快）

EOF

echo -e "${GREEN}✓ 配置文件創建完成${NC}"
echo ""

# 步驟 4: 啟動 tunnel
echo -e "${YELLOW}[4/4] 啟動 ngrok tunnel...${NC}"
echo ""

# 提供選項
echo "請選擇啟動模式:"
echo "1. 前台運行（按 Ctrl+C 停止）"
echo "2. 背景運行"
echo "3. 僅顯示啟動命令，稍後手動運行"
echo ""
read -p "請選擇 (1-3): " MODE

case $MODE in
    1)
        echo ""
        echo "啟動 ngrok... (按 Ctrl+C 停止)"
        echo ""
        ngrok http 80
        ;;
    2)
        echo ""
        echo "啟動背景服務..."
        nohup ngrok http 80 > ~/ngrok.log 2>&1 &
        NGROK_PID=$!
        echo -e "${GREEN}✓ ngrok 已在背景運行 (PID: $NGROK_PID)${NC}"
        echo ""

        # 等待 ngrok 啟動
        sleep 3

        # 嘗試獲取公網 URL
        echo "正在獲取公網地址..."
        sleep 2

        if command -v jq &> /dev/null; then
            PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url')
        else
            echo ""
            echo "請訪問 http://localhost:4040 查看 ngrok 控制台"
        fi

        if [ ! -z "$PUBLIC_URL" ]; then
            echo ""
            echo "======================================"
            echo -e "${GREEN}  公網地址已就緒！${NC}"
            echo "======================================"
            echo ""
            echo "  主頁: $PUBLIC_URL/"
            echo "  AI 聊天: $PUBLIC_URL/chat/"
            echo ""
            echo "  ngrok 控制台: http://localhost:4040"
            echo ""
        fi

        echo "查看日誌: tail -f ~/ngrok.log"
        echo "停止服務: kill $NGROK_PID"
        echo ""

        # 創建停止腳本
        cat > ~/stop-ngrok.sh <<'STOP'
#!/bin/bash
pkill ngrok
echo "ngrok 已停止"
STOP
        chmod +x ~/stop-ngrok.sh
        echo "快速停止: ~/stop-ngrok.sh"
        ;;
    3)
        echo ""
        echo "======================================"
        echo "  手動啟動命令"
        echo "======================================"
        echo ""
        echo "前台運行:"
        echo "  ngrok http 80"
        echo ""
        echo "背景運行:"
        echo "  nohup ngrok http 80 > ~/ngrok.log 2>&1 &"
        echo ""
        echo "查看公網地址:"
        echo "  curl http://localhost:4040/api/tunnels | jq"
        echo "  或訪問: http://localhost:4040"
        echo ""
        ;;
    *)
        echo -e "${RED}無效選擇${NC}"
        exit 1
        ;;
esac

echo ""
echo "======================================"
echo -e "${GREEN}  設置完成！${NC}"
echo "======================================"
echo ""
echo -e "${YELLOW}注意事項:${NC}"
echo "• 免費版 URL 會在每次重啟後變更"
echo "• 免費版有連線數限制"
echo "• 適合測試和臨時分享，不建議長期使用"
echo ""
echo -e "${BLUE}升級到付費版可獲得:${NC}"
echo "• 固定的自定義域名"
echo "• 更高的連線數限制"
echo "• 更多進階功能"
echo "• 訪問 https://ngrok.com/pricing"
echo ""
