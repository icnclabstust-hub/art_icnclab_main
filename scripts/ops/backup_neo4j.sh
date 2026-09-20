#!/usr/bin/env bash
# Neo4j（社群版）離線備份：停止 → neo4j-admin database dump → 無論成敗都重新啟動 → 輪替 → 可選鏡像。
#
# 社群版沒有線上備份，也不能 dump 正在運作中的資料庫，所以會短暫停止 Neo4j（約 1～2 分鐘）。
# 請排在深夜、且所有寫入 Neo4j 的步驟之後（例如每日流程的最後）。
#
# 用法：bash scripts/ops/backup_neo4j.sh
# 環境變數：
#   NEO4J_HOME         Neo4j 安裝目錄（預設 ~/neo4j-community-2026.06.0）
#   BACKUP_DIR         主要備份目錄（預設 ~/backups/neo4j）
#   MIRROR_DIR         鏡像目錄（預設 /mnt/f/art_backups/neo4j；磁碟未掛載時略過並警告）
#   BACKUP_KEEP_COUNT  每個目錄保留幾個備份批次（預設 7）
#   NEO4J_RESTART      設為 0 則備份後不重新啟動（預設 1）
# 結束碼：0 成功；1 備份失敗；2 備份成功但鏡像失敗；3 備份後重新啟動失敗（最嚴重，需人工處理）。

set -u

NEO4J_HOME="${NEO4J_HOME:-$HOME/neo4j-community-2026.06.0}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/neo4j}"
MIRROR_DIR="${MIRROR_DIR:-/mnt/f/art_backups/neo4j}"
KEEP="${BACKUP_KEEP_COUNT:-7}"
RESTART="${NEO4J_RESTART:-1}"
DATABASES=(neo4j system)
STOP_WAIT_SECONDS=90
START_WAIT_SECONDS=180
STAMP="$(date +%Y%m%d_%H%M%S)"
BATCH_DIR="$BACKUP_DIR/neo4j_$STAMP"
START_LOG="${NEO4J_START_LOG:-/tmp/neo4j-native.log}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }

neo4j_running() { pgrep -f "$NEO4J_HOME/" > /dev/null 2>&1 && ss -tln 2> /dev/null | grep -qE ':(7687)\b'; }

start_neo4j() {
    [ "$RESTART" = "1" ] || { log "NEO4J_RESTART=0，不重新啟動"; return 0; }
    nohup setsid "$NEO4J_HOME/bin/neo4j" console > "$START_LOG" 2>&1 &
    local waited=0
    while [ "$waited" -lt "$START_WAIT_SECONDS" ]; do
        if ss -tln 2> /dev/null | grep -qE ':(7687)\b'; then
            sleep 5
            log "✅ Neo4j 已重新啟動"
            return 0
        fi
        sleep 3
        waited=$((waited + 3))
    done
    log "❌ Neo4j 在 ${START_WAIT_SECONDS} 秒內沒有重新啟動，請檢查 $START_LOG"
    return 1
}

prune() {
    local dir="$1"
    ls -1dt "$dir"/neo4j_* 2> /dev/null | tail -n +"$((KEEP + 1))" | while read -r old; do
        rm -rf -- "$old" && log "已刪除過舊備份：$old"
    done
}

mkdir -p "$BATCH_DIR" || { log "❌ 無法建立 $BATCH_DIR"; exit 1; }

was_running=false
if neo4j_running; then
    was_running=true
    log "停止 Neo4j..."
    "$NEO4J_HOME/bin/neo4j" stop > /dev/null 2>&1
    waited=0
    while neo4j_running && [ "$waited" -lt "$STOP_WAIT_SECONDS" ]; do
        sleep 2
        waited=$((waited + 2))
    done
    if neo4j_running; then
        log "❌ Neo4j 沒有在 ${STOP_WAIT_SECONDS} 秒內停止，放棄備份"
        rm -rf "$BATCH_DIR"
        exit 1
    fi
fi

dump_failed=false
for db in "${DATABASES[@]}"; do
    if "$NEO4J_HOME/bin/neo4j-admin" database dump "$db" --to-path="$BATCH_DIR" > "$BATCH_DIR/$db.log" 2>&1 \
        && [ -s "$BATCH_DIR/$db.dump" ]; then
        log "✅ 已 dump $db（$(du -h "$BATCH_DIR/$db.dump" | cut -f1)）"
    else
        log "❌ dump $db 失敗，見 $BATCH_DIR/$db.log"
        dump_failed=true
    fi
done

restart_failed=false
if [ "$was_running" = true ]; then
    start_neo4j || restart_failed=true
fi

if [ "$dump_failed" = true ]; then
    rm -rf "$BATCH_DIR"
    [ "$restart_failed" = true ] && exit 3
    exit 1
fi
rm -f "$BATCH_DIR"/*.log
log "✅ 備份完成：$BATCH_DIR"
prune "$BACKUP_DIR"
[ "$restart_failed" = true ] && exit 3

mirror_ok=false
if [[ "$MIRROR_DIR" == /mnt/* ]]; then
    # Windows 磁碟未掛載時 mkdir 會悄悄建在 WSL 自己的磁碟上，等於沒有鏡像，所以先確認真的是掛載點
    mountpoint -q "/mnt/$(echo "$MIRROR_DIR" | cut -d/ -f3)" && mirror_ok=true
else
    mirror_ok=true
fi
if [ "$mirror_ok" = true ] && mkdir -p "$MIRROR_DIR" && cp -r -- "$BATCH_DIR" "$MIRROR_DIR/"; then
    log "✅ 已鏡像：$MIRROR_DIR/$(basename "$BATCH_DIR")"
    prune "$MIRROR_DIR"
    exit 0
fi
log "⚠️ 鏡像失敗或目標磁碟未掛載：$MIRROR_DIR（主要備份仍已完成）"
exit 2
