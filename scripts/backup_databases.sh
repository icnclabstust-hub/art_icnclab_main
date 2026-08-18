#!/bin/bash
# 備份 Neo4j + ChromaDB 實際資料庫內容（不是原始碼，是圖資料庫跟向量資料庫本身）
# 用於系統搬遷或定期備份：把兩個資料庫的資料目錄暫停服務後完整封存
# 還原方式見腳本最後的說明

set -e

BACKUP_ROOT="/home/user/backups/db_backup_$(date +%Y%m%d_%H%M%S)"
NEO4J_DATA_DIR="/home/user/native-neo4j/data"
CHROMADB_DATA_DIR="/home/user/native-chromadb/data"
OPENWEBUI_DATA_DIR="/home/user/openwebui-data"

mkdir -p "$BACKUP_ROOT"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 備份目錄: $BACKUP_ROOT"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 停止 Neo4j / ChromaDB / Open WebUI（暫停服務以確保資料一致性）..."
pkill -f "neo4j-community-2026.06.0" 2>/dev/null || true
pkill -f "chroma run --path /home/user/native-chromadb" 2>/dev/null || true
pkill -f "open-webui serve" 2>/dev/null || true
sleep 5

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 封存 Neo4j 資料..."
tar -czf "$BACKUP_ROOT/neo4j_data.tar.gz" -C "$(dirname "$NEO4J_DATA_DIR")" "$(basename "$NEO4J_DATA_DIR")"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 封存 ChromaDB 資料..."
tar -czf "$BACKUP_ROOT/chromadb_data.tar.gz" -C "$(dirname "$CHROMADB_DATA_DIR")" "$(basename "$CHROMADB_DATA_DIR")"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 封存 Open WebUI 資料（帳號、對話紀錄、pipe/tool 設定、custom.css）..."
tar -czf "$BACKUP_ROOT/openwebui_data.tar.gz" -C "$(dirname "$OPENWEBUI_DATA_DIR")" "$(basename "$OPENWEBUI_DATA_DIR")"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 備份完成："
ls -lh "$BACKUP_ROOT"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 完成，服務需要重新啟動（執行 Start-NativeServices.ps1）"

# --- 還原方式（在新機器上）---
# 1. 把 neo4j_data.tar.gz / chromadb_data.tar.gz / openwebui_data.tar.gz 複製到新機器的 WSL 裡
# 2. tar -xzf neo4j_data.tar.gz -C /home/user/native-neo4j/
# 3. tar -xzf chromadb_data.tar.gz -C /home/user/native-chromadb/
# 4. tar -xzf openwebui_data.tar.gz -C /home/user/
# 5. 執行 Start-NativeServices.ps1 啟動服務
