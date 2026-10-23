#!/usr/bin/env bash
# PostgreSQL 例行備份：pg_dump（custom format）→ 驗證可讀 → 輪替 → 可選鏡像到另一顆磁碟。
#
# 用法：bash scripts/ops/backup_postgres.sh
# 連線：只讀環境變數 DB_HOST／DB_PORT／DB_NAME／DB_USER／DB_PASSWORD（由呼叫端從 .env 載入），
#       角色需具備唯讀權限（context/database/06-backup-read-grants.sql）。
# 可調整的環境變數：
#   BACKUP_DIR         主要備份目錄（預設 ~/backups/postgres）
#   MIRROR_DIR         鏡像目錄（預設 /mnt/f/art_backups/postgres；該磁碟未掛載時略過並警告）
#   BACKUP_KEEP_COUNT  每個目錄保留份數（預設 14）
# 結束碼：0 成功；1 備份失敗；2 備份成功但鏡像失敗。

set -u

BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/postgres}"
MIRROR_DIR="${MIRROR_DIR:-/mnt/f/art_backups/postgres}"
KEEP="${BACKUP_KEEP_COUNT:-14}"
DB_NAME_EFFECTIVE="${DB_NAME:-art_history_db}"
STAMP="$(date +%Y%m%d_%H%M%S)"
FILE_NAME="${DB_NAME_EFFECTIVE}_${STAMP}.dump"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }

prune() {
    local dir="$1"
    ls -1t "$dir"/"${DB_NAME_EFFECTIVE}"_*.dump 2>/dev/null | tail -n +"$((KEEP + 1))" | while read -r old; do
        rm -f -- "$old" && log "已刪除過舊備份：$old"
    done
}

mkdir -p "$BACKUP_DIR" || { log "❌ 無法建立 $BACKUP_DIR"; exit 1; }
TARGET="$BACKUP_DIR/$FILE_NAME"

export PGHOST="${DB_HOST:-localhost}" PGPORT="${DB_PORT:-5432}" PGDATABASE="$DB_NAME_EFFECTIVE"
export PGUSER="${DB_USER:-}" PGPASSWORD="${DB_PASSWORD:-}"

if ! pg_dump -Fc -f "$TARGET.partial"; then
    rm -f "$TARGET.partial"
    log "❌ pg_dump 失敗（權限或連線問題）"
    exit 1
fi
if ! pg_restore -l "$TARGET.partial" > /dev/null 2>&1; then
    rm -f "$TARGET.partial"
    log "❌ 備份檔無法讀取（pg_restore -l 失敗），已捨棄"
    exit 1
fi
mv "$TARGET.partial" "$TARGET"
log "✅ 備份完成：$TARGET（$(du -h "$TARGET" | cut -f1)，$(pg_restore -l "$TARGET" | grep -c 'TABLE DATA') 張表）"
prune "$BACKUP_DIR"

mirror_ok=false
if [[ "$MIRROR_DIR" == /mnt/* ]]; then
    # Windows 磁碟未掛載時 mkdir 會悄悄建在 WSL 自己的磁碟上，等於沒有鏡像，所以先確認真的是掛載點
    mount_root="/mnt/$(echo "$MIRROR_DIR" | cut -d/ -f3)"
    mountpoint -q "$mount_root" && mirror_ok=true
else
    mirror_ok=true
fi
if [ "$mirror_ok" = true ] && mkdir -p "$MIRROR_DIR" && cp -- "$TARGET" "$MIRROR_DIR/$FILE_NAME"; then
    log "✅ 已鏡像：$MIRROR_DIR/$FILE_NAME"
    prune "$MIRROR_DIR"
    exit 0
fi
log "⚠️ 鏡像失敗或目標磁碟未掛載：$MIRROR_DIR（主要備份仍已完成）"
exit 2
