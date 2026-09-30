#!/bin/bash
# 每日爬蟲 + 新架構同步（catalog 為單一真相來源）
# 流程：爬 9 個來源 -> 各來源攝取進 PostgreSQL catalog（雜湊比對＋內容掃描）
#       -> 訂閱器增量同步 ChromaDB、Elasticsearch、Neo4j -> Neo4j 分類關係 -> 一致性驗證 -> PostgreSQL 備份 -> Neo4j 備份 -> 清 RAG 快取
# 個別步驟失敗不會中斷整體（例如 Google Books 429 屬已知偶發狀況）。
# Yale 已於 2026-09-23 完全移除（爬蟲、攝取與既有資料皆已撤出），見 docs/decision-log.md。
#
# 與舊版 daily_crawl_and_sync.sh 並存，尚未取代排程；切換前請先依
# docs/designs/2026-09-20-phase1-catalog-ingestion.md 的驗收標準確認。
#
# 用法：bash scripts/daily_crawl_and_sync_catalog.sh            # 完整流程
#       SKIP_CRAWL=1 bash scripts/daily_crawl_and_sync_catalog.sh  # 只攝取＋同步（用現有資料檔）

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
LOG_DIR="$PROJECT_DIR/logs/daily_crawl"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/catalog_crawl_$(date +%Y-%m-%dT%H-%M-%S).log"

cd "$PROJECT_DIR" || exit 1

# 密碼與 API Key 只從 .env 讀取，不寫進腳本（S-01）
ENV_FILE="${ENV_FILE:-$PROJECT_DIR/.env}"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
else
    echo "❌ 找不到 $ENV_FILE，各項密碼與 API Key 將是空的" >&2
fi

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" && nvm use 24 >/dev/null 2>&1

# 爬蟲固定寫入 crawlers/data/raw；.env 的 DATA_RAW_DIR 是相對路徑（./data/raw），不可沿用
export DATA_RAW_DIR="$PROJECT_DIR/crawlers/data/raw"
# 一律用標準埠：舊版 .env 的 NEO4J_URI 仍可能是整併前的 7688（見 docs/reports/2026-09-20-phase0-status.md）
export NEO4J_URI="bolt://127.0.0.1:7687"
export CHROMADB_HOST="${CHROMADB_HOST:-localhost}"
export CHROMADB_PORT="${CHROMADB_PORT:-8000}"

CRAWL_TIMEOUT_SECONDS=1800
STEP_PAUSE_SECONDS=30

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

run_step() {
    local name="$1"; shift
    local start=$(date +%s)
    log "--- 開始: $name ---"
    if "$@" >> "$LOG_FILE" 2>&1; then
        log "✅ $name 完成（$(( $(date +%s) - start )) 秒）"
    else
        log "❌ $name 失敗（$(( $(date +%s) - start )) 秒，略過，繼續下一步）"
    fi
}

crawl() {
    local file="$1"
    (cd "$PROJECT_DIR/crawlers" && timeout "$CRAWL_TIMEOUT_SECONDS" node "$file")
}

log "=== 每日爬蟲＋新架構同步開始 ==="

if [ -z "${SKIP_CRAWL:-}" ]; then
    mkdir -p "$DATA_RAW_DIR"
    for entry in \
        "Europeana:europeana-crawler.js" \
        "Harvard:harvard-art-museums-crawler.js" \
        "MET:start-single-crawler.js" \
        "Renaissance/Baroque:renaissance-baroque-crawler.js" \
        "Specialized Art:specialized-art-crawler.js" \
        "Google Books:fetch_google_books.js" \
        "Art Institute of Chicago:art-institute-chicago-crawler.js" \
        "V&A:va-museum-crawler.js" \
        "Cleveland:cleveland-museum-crawler.js"; do
        run_step "爬蟲 ${entry%%:*}" crawl "${entry#*:}"
        sleep "$STEP_PAUSE_SECONDS"
    done
fi

cd "$PROJECT_DIR/langchain-rag" || exit 1

for source in europeana harvard met_museum specialized_art google_books \
    art_institute_chicago va_museum cleveland_museum; do
    run_step "攝取 $source" python3 -m ingest run --source "$source"
done

run_step "訂閱器 ChromaDB" python3 -m subscribers run --target chromadb --once
run_step "訂閱器 Elasticsearch" python3 -m subscribers run --target elasticsearch --once
if [ -n "${NEO4J_PASSWORD:-}" ]; then
    run_step "訂閱器 Neo4j" python3 -m subscribers run --target neo4j --once
    # 訂閱器只寫 Artwork／Artist／CREATED；風格、材質、地點、機構等分類關係由這支規則式腳本
    # （詞典與屬性比對，不呼叫 LLM）補上。--no-clean 只疊加、可重複執行；預設模式會先刪除分類節點，不可用於每日流程
    run_step "Neo4j 分類關係（疊加）" python3 classify_art_history_graph.py --no-clean
    # 保留期清理：只刪除「到期／軟刪除超過 30 天」的關係與作品（以及因此孤立的藝術家）；30 天內的仍可還原
    run_step "Neo4j 保留期清理（30 天）" python3 -m subscribers purge-neo4j --days 30 --apply
else
    log "⚠️ 未設定 NEO4J_PASSWORD，略過 Neo4j 訂閱器與分類"
fi

for source in europeana harvard met_museum specialized_art google_books \
    art_institute_chicago va_museum cleveland_museum \
    masterpieces_curated wikipedia_pilot; do
    # 舊資料補登（2026-09-21）後 catalog 與三庫已完全一致；此處回報「不一致」代表出現新的漂移，需要調查。
    # 不套用 run_step 的成敗判定；不一致寫入 eval.alerts、恢復一致自動結案（規格 DAT-05／EVL-11）
    log "--- 驗證 $source ---"
    python3 -m ingest verify --source "$source" --es --record-alerts 2>&1 | grep -vE "INFO|Warning|warn" >> "$LOG_FILE"
done

# 同步完成後備份 PostgreSQL（catalog 是單一真相來源，目前只存在這裡）；連線參數已由 .env 載入
run_step "PostgreSQL 備份" bash "$PROJECT_DIR/scripts/ops/backup_postgres.sh"

# Neo4j 社群版只能離線備份：會短暫停止 Neo4j（約 1 分鐘）再自動重新啟動，所以必須排在
# 所有寫入 Neo4j 的步驟（攝取、訂閱器、驗證）之後，且在清 RAG 快取之前
run_step "Neo4j 備份（短暫停機）" bash "$PROJECT_DIR/scripts/ops/backup_neo4j.sh"

# 告警檢查與彙總（規格 DAT-17、GRD-10、EVL-12）：結果寫入 eval.alerts，失敗不中斷流程
log "--- 備份磁碟剩餘空間 ---"
python3 -m ingest check-disk --path "wsl=$HOME/backups" --path "f=/mnt/f/art_backups" \
    2>&1 | grep -vE "INFO|Warning|warn" >> "$LOG_FILE"
log "--- 防護元件出錯比例（近 24 小時）---"
python3 -m ingest check-guard 2>&1 | grep -vE "INFO|Warning|warn" >> "$LOG_FILE"
log "--- 未處理告警彙總（另存 logs/alerts/open_alerts.txt）---"
python3 -m ingest alerts-summary --out "$PROJECT_DIR/logs/alerts/open_alerts.txt" \
    2>&1 | grep -vE "INFO|Warning|warn" >> "$LOG_FILE"

log "--- 清除 RAG 查詢快取 ---"
curl -s -X POST "http://localhost:${RAG_MANAGER_PORT:-8001}/api/v1/cache/clear" >> "$LOG_FILE" 2>&1

log "=== 每日爬蟲＋新架構同步結束 ==="
