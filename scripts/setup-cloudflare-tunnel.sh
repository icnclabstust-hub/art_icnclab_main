#!/bin/bash

# Cloudflare Tunnel 自動設置腳本
# 用途: 將 Open WebUI 暴露到公網

set -e  # 遇到錯誤立即退出

echo "======================================"
echo "  Cloudflare Tunnel 設置腳本"
echo "  Open WebUI 公網訪問配置"
echo "======================================"
echo ""

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 檢查是否為 root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}請不要使用 root 用戶運行此腳本${NC}"
   exit 1
fi

# 步驟 1: 檢查並安裝 cloudflared
echo -e "${YELLOW}[1/7] 檢查 cloudflared 安裝狀態...${NC}"
if ! command -v cloudflared &> /dev/null; then
    echo "cloudflared 未安裝，開始安裝..."

    # 檢測系統架構
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
        DOWNLOAD_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
    elif [ "$ARCH" = "aarch64" ]; then
        DOWNLOAD_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64"
    else
        echo -e "${RED}不支援的系統架構: $ARCH${NC}"
        exit 1
    fi

    wget -O cloudflared $DOWNLOAD_URL
    chmod +x cloudflared
    sudo mv cloudflared /usr/local/bin/
    echo -e "${GREEN}✓ cloudflared 安裝完成${NC}"
else
    echo -e "${GREEN}✓ cloudflared 已安裝${NC}"
    cloudflared version
fi

echo ""

# 步驟 2: 登入 Cloudflare
echo -e "${YELLOW}[2/7] 登入 Cloudflare 帳號...${NC}"
echo "即將打開瀏覽器，請選擇要使用的域名並授權"
read -p "按 Enter 繼續..."

cloudflared tunnel login

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ 登入失敗，請檢查網路連接${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 登入成功${NC}"
echo ""

# 步驟 3: 輸入配置資訊
echo -e "${YELLOW}[3/7] 輸入配置資訊...${NC}"

# Tunnel 名稱
read -p "輸入 Tunnel 名稱 (預設: art-history): " TUNNEL_NAME
TUNNEL_NAME=${TUNNEL_NAME:-art-history}

# 域名
read -p "輸入您的域名 (例如: example.com): " DOMAIN
if [ -z "$DOMAIN" ]; then
    echo -e "${RED}✗ 域名不能為空${NC}"
    exit 1
fi

# 子域名（可選）
read -p "輸入聊天服務的子域名 (預設: chat): " SUBDOMAIN
SUBDOMAIN=${SUBDOMAIN:-chat}

CHAT_DOMAIN="${SUBDOMAIN}.${DOMAIN}"

echo ""
echo "配置摘要:"
echo "  Tunnel 名稱: $TUNNEL_NAME"
echo "  主域名: $DOMAIN"
echo "  聊天地址: https://$CHAT_DOMAIN/chat/"
echo ""
read -p "確認以上資訊正確? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "已取消"
    exit 0
fi

echo ""

# 步驟 4: 創建 Tunnel
echo -e "${YELLOW}[4/7] 創建 Cloudflare Tunnel...${NC}"

# 檢查 tunnel 是否已存在
if cloudflared tunnel list | grep -q "$TUNNEL_NAME"; then
    echo "Tunnel '$TUNNEL_NAME' 已存在"
    read -p "是否刪除並重新創建? (y/n): " RECREATE
    if [ "$RECREATE" = "y" ] || [ "$RECREATE" = "Y" ]; then
        cloudflared tunnel delete -f "$TUNNEL_NAME"
        cloudflared tunnel create "$TUNNEL_NAME"
    fi
else
    cloudflared tunnel create "$TUNNEL_NAME"
fi

# 獲取 Tunnel ID
TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')

if [ -z "$TUNNEL_ID" ]; then
    echo -e "${RED}✗ 無法獲取 Tunnel ID${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Tunnel 創建成功${NC}"
echo "  Tunnel ID: $TUNNEL_ID"
echo ""

# 步驟 5: 創建配置文件
echo -e "${YELLOW}[5/7] 創建配置文件...${NC}"

mkdir -p ~/.cloudflared

# 查找 credentials 文件
CREDENTIALS_FILE="$HOME/.cloudflared/$TUNNEL_ID.json"

if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo -e "${RED}✗ 找不到 credentials 文件: $CREDENTIALS_FILE${NC}"
    exit 1
fi

# 創建 config.yml
cat > ~/.cloudflared/config.yml <<EOF
# Cloudflare Tunnel Configuration
# Tunnel Name: $TUNNEL_NAME
# Tunnel ID: $TUNNEL_ID

tunnel: $TUNNEL_ID
credentials-file: $CREDENTIALS_FILE

ingress:
  # Open WebUI - AI 聊天服務
  - hostname: $CHAT_DOMAIN
    service: http://localhost:80
    originRequest:
      noTLSVerify: true
      connectTimeout: 30s
      httpHostHeader: $CHAT_DOMAIN

  # 主網站
  - hostname: $DOMAIN
    service: http://localhost:80
    originRequest:
      noTLSVerify: true
      httpHostHeader: $DOMAIN

  # 捕獲所有其他請求（返回 404）
  - service: http_status:404
EOF

echo -e "${GREEN}✓ 配置文件創建完成${NC}"
echo "  位置: ~/.cloudflared/config.yml"
echo ""

# 步驟 6: 設置 DNS 記錄
echo -e "${YELLOW}[6/7] 設置 DNS 記錄...${NC}"

echo "為 $CHAT_DOMAIN 創建 DNS 記錄..."
if cloudflared tunnel route dns "$TUNNEL_NAME" "$CHAT_DOMAIN"; then
    echo -e "${GREEN}✓ $CHAT_DOMAIN DNS 記錄創建成功${NC}"
else
    echo -e "${YELLOW}! DNS 記錄可能已存在或創建失敗，請手動檢查${NC}"
fi

echo "為 $DOMAIN 創建 DNS 記錄..."
if cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN"; then
    echo -e "${GREEN}✓ $DOMAIN DNS 記錄創建成功${NC}"
else
    echo -e "${YELLOW}! DNS 記錄可能已存在或創建失敗，請手動檢查${NC}"
fi

echo ""

# 步驟 7: 測試配置
echo -e "${YELLOW}[7/7] 測試配置...${NC}"
if cloudflared tunnel ingress validate; then
    echo -e "${GREEN}✓ 配置驗證成功${NC}"
else
    echo -e "${RED}✗ 配置驗證失敗${NC}"
    exit 1
fi

echo ""
echo "======================================"
echo -e "${GREEN}  設置完成！${NC}"
echo "======================================"
echo ""
echo "下一步操作:"
echo ""
echo "1. 啟動 Tunnel (測試模式):"
echo "   cloudflared tunnel run $TUNNEL_NAME"
echo ""
echo "2. 訪問測試:"
echo "   主頁: https://$DOMAIN/"
echo "   AI 聊天: https://$CHAT_DOMAIN/chat/"
echo ""
echo "3. 如果測試成功，安裝為系統服務:"
echo "   sudo cloudflared service install"
echo "   sudo systemctl start cloudflared"
echo "   sudo systemctl enable cloudflared"
echo ""
echo "4. 檢查服務狀態:"
echo "   sudo systemctl status cloudflared"
echo ""
echo "5. 查看日誌:"
echo "   sudo journalctl -u cloudflared -f"
echo ""
echo -e "${YELLOW}注意: DNS 記錄可能需要幾分鐘才能生效${NC}"
echo ""

# 詢問是否立即啟動
read -p "是否現在啟動 Tunnel 進行測試? (y/n): " START_NOW
if [ "$START_NOW" = "y" ] || [ "$START_NOW" = "Y" ]; then
    echo ""
    echo "啟動 Tunnel... (按 Ctrl+C 停止)"
    echo ""
    cloudflared tunnel run "$TUNNEL_NAME"
else
    echo ""
    echo "稍後運行以下命令啟動 Tunnel:"
    echo "  cloudflared tunnel run $TUNNEL_NAME"
fi
