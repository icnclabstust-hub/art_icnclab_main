#!/bin/bash
# 每日自動爬蟲 + 資料庫同步
# 依序爬 10 個博物館來源 -> 匯入 Neo4j+ChromaDB (非 Europeana 9 個來源) -> 同步 Europeana (Neo4j+ChromaDB) -> 清快取
# 個別爬蟲失敗不會中斷整個流程（例如 Google Books 429、MET 403 屬已知偶發狀況）
# 每個步驟、整體執行都有時間紀錄；歷史記錄另外累積在 logs/crawl_history.csv

PROJECT_DIR="/mnt/c/Users/user/Desktop/藝術史資料庫/art-history-database"
LOG_DIR="$PROJECT_DIR/logs/daily_crawl"
HISTORY_FILE="$PROJECT_DIR/logs/crawl_history.csv"
mkdir -p "$LOG_DIR"

TS=$(date +%Y-%m-%dT%H-%M-%S)
LOG_FILE="$LOG_DIR/crawl_$TS.log"

cd "$PROJECT_DIR" || exit 1

# 從 .env 讀取密碼/API Key（NEO4J_PASSWORD、ES_PASSWORD 等），不寫死在腳本裡避免密碼進 git
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$PROJECT_DIR/.env"
    set +a
else
    echo "❌ 找不到 $PROJECT_DIR/.env，NEO4J_PASSWORD/ES_PASSWORD 等密碼將是空的" >&2
fi

# 用 nvm 切換到 Node 24 LTS（系統內建 apt 版 Node 18 已 EOL）
# 這個腳本是被 bash script.sh 非互動式呼叫，不會自動讀 ~/.bashrc，所以要在這裡手動載入 nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" && nvm use 24 >/dev/null 2>&1

# 原生 Neo4j（WSL 直接執行，非 Docker），標準埠 bolt:7687（系統 neo4j.service 已於 2026-09-20 停用）
export NEO4J_URI="bolt://127.0.0.1:7687"
export CHROMADB_HOST="localhost"
export CHROMADB_PORT="8000"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

RUN_START_EPOCH=$(date +%s)
RUN_START_HUMAN=$(date '+%Y-%m-%d %H:%M:%S')

run_step() {
    local name="$1"; shift
    local step_start=$(date +%s)
    log "--- 開始: $name ---"
    if "$@" >> "$LOG_FILE" 2>&1; then
        local step_end=$(date +%s)
        local step_duration=$(( (step_end - step_start) / 60 ))
        local step_duration_sec=$(( (step_end - step_start) % 60 ))
        log "✅ $name 完成（耗時 ${step_duration}分${step_duration_sec}秒）"
    else
        local step_end=$(date +%s)
        local step_duration=$(( (step_end - step_start) / 60 ))
        local step_duration_sec=$(( (step_end - step_start) % 60 ))
        log "❌ $name 失敗（耗時 ${step_duration}分${step_duration_sec}秒，略過，繼續下一步）"
    fi
    sleep 30
}

log "=== 每日爬蟲開始 (開始時間: $RUN_START_HUMAN) ==="

run_step "Europeana"          node crawlers/europeana-crawler.js
run_step "Harvard"            node crawlers/harvard-art-museums-crawler.js
run_step "MET Museum"         node crawlers/start-single-crawler.js
run_step "Renaissance/Baroque" node crawlers/renaissance-baroque-crawler.js
run_step "Specialized Art"    node crawlers/specialized-art-crawler.js
run_step "Google Books"       node crawlers/fetch_google_books.js
run_step "Art Institute of Chicago" node crawlers/art-institute-chicago-crawler.js
run_step "V&A Museum"         node crawlers/va-museum-crawler.js
run_step "Cleveland Museum"   node crawlers/cleveland-museum-crawler.js
run_step "Yale University Art Gallery" node crawlers/yale-university-art-gallery-crawler.js

log "--- 開始: 檢查重複資料 ---"
python3 scripts/check_duplicates.py >> "$LOG_FILE" 2>&1
log "✅ 重複資料檢查完成（結果見 log）"

log "--- 開始: 匯入 Neo4j + ChromaDB (Harvard/MET/文藝復興巴洛克/專門藝術/Google Books/AIC/V&A/Cleveland/Yale) ---"
IMPORT_STATUS="成功"
if python3 langchain-rag/import_all_museums_to_neo4j.py >> "$LOG_FILE" 2>&1; then
    log "✅ Neo4j 匯入完成"
else
    log "❌ Neo4j 匯入失敗"
    IMPORT_STATUS="失敗"
fi

log "--- 開始: 同步 Europeana (Neo4j + ChromaDB) ---"
SYNC_STATUS="成功"
if python3 langchain-rag/sync_europeana_to_databases.py >> "$LOG_FILE" 2>&1; then
    log "✅ Europeana 同步完成"
else
    log "❌ Europeana 同步失敗"
    SYNC_STATUS="失敗"
fi

run_step "同步 Elasticsearch (hybrid_es_rag 用)" python3 scripts/sync_chromadb_to_elasticsearch.py

log "--- 開始: 回報品質分數 ---"
python3 scripts/report_quality_score.py >> "$LOG_FILE" 2>&1

log "--- 清除 RAG 查詢快取 ---"
curl -s -X POST http://localhost:8007/api/v1/cache/clear >> "$LOG_FILE" 2>&1

RUN_END_EPOCH=$(date +%s)
RUN_END_HUMAN=$(date '+%Y-%m-%d %H:%M:%S')
TOTAL_SECONDS=$(( RUN_END_EPOCH - RUN_START_EPOCH ))
TOTAL_MINUTES=$(( TOTAL_SECONDS / 60 ))
TOTAL_SECONDS_REMAIN=$(( TOTAL_SECONDS % 60 ))

log "=== 每日爬蟲結束 (結束時間: $RUN_END_HUMAN，總耗時: ${TOTAL_MINUTES}分${TOTAL_SECONDS_REMAIN}秒) ==="

# 目前 Artwork 總筆數（供歷史記錄用）
TOTAL_ARTWORKS=$(python3 -c "
from neo4j import GraphDatabase
try:
    driver = GraphDatabase.driver('$NEO4J_URI', auth=('neo4j', '$NEO4J_PASSWORD'))
    with driver.session() as s:
        print(s.run('MATCH (a:Artwork) RETURN count(a) as c').single()['c'])
    driver.close()
except Exception:
    print('N/A')
" 2>/dev/null)

# 累積歷史記錄（CSV，方便日後拉出來看每次執行的時間趨勢）
if [ ! -f "$HISTORY_FILE" ]; then
    echo "開始時間,結束時間,總耗時(分鐘),Neo4j匯入,Europeana同步,Artwork總筆數,log檔案" > "$HISTORY_FILE"
fi
echo "$RUN_START_HUMAN,$RUN_END_HUMAN,$TOTAL_MINUTES,$IMPORT_STATUS,$SYNC_STATUS,$TOTAL_ARTWORKS,crawl_$TS.log" >> "$HISTORY_FILE"

# 只保留最近 30 天的 log，避免無限累積
find "$LOG_DIR" -name "crawl_*.log" -mtime +30 -delete
