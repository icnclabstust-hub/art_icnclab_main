#!/usr/bin/env bash
# verify-nightly.sh — 夜間流程實跑驗證 + 現況自檢
#
# 為什麼有這支：OPS-02 要確認「移除 Yale 後的第一次完整夜間實跑」是否真的成功。
# 「最終沒有錯誤訊息」不等於成功——爬蟲單一來源失敗不中止整體，outbox 積壓也不會報錯。
# 本腳本把 docs/2026-09-22-system-flow-steps.md 流程 A 的 A-1～A-14 逐步取證。
#
# 本檔於 2026-09-22 併入原 scripts/doctor.sh 仍有效的自檢能力（該腳本已停用刪除）：
#   副本身分判定、systemd NRestarts crash-loop 計數、PPID 檢查、OOM 跡象、
#   資源檢查、.env 白名單遮蔽。未移植 doctor.sh 中已被埠號整併推翻的判讀
#   （該檔第 108 行仍稱「7688 為專案正確值」，2026-09-20 起已非事實）。
#
# 全唯讀：只做 ss / ls / find / curl -s / psql SELECT / systemctl show /
# journalctl / dmesg / Get-ScheduledTaskInfo。不執行任何 start / stop / restart，
# 不做任何 INSERT / UPDATE / DELETE。可安全重複執行。
# 金鑰一律遮蔽（白名單放行），輸出可整份回貼。
#
# 用法（在 WSL Ubuntu-22.04 內）：
#   bash scripts/verify-nightly.sh | tee ~/verify-nightly-$(date +%F).txt
#   sudo bash scripts/verify-nightly.sh      # 第 12 節的 dmesg 需要權限
#
# 可用環境變數覆寫：
#   RUNTIME_DIR   執行期目錄（預設為桌面那份，見 problem-register A4）
#   SINCE_HOURS   視為「本次夜跑」的時間窗，預設 24
#
set -uo pipefail

RUNTIME_DIR="${RUNTIME_DIR:-/mnt/c/Users/user/Desktop/藝術史資料庫/art-history-database}"
SINCE_HOURS="${SINCE_HOURS:-24}"

h(){ printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }
kv(){ printf '    %-22s %s\n' "$1" "$2"; }
ind(){ sed 's/^/    /'; }
ok(){   printf '    ✅ %s\n' "$*"; }
bad(){  printf '    ❌ %s\n' "$*"; }
warn(){ printf '    ⚠  %s\n' "$*"; }
run(){ printf '    $ %s\n' "$*"; "$@" 2>&1 | sed 's/^/      /' || printf '      (指令失敗或不存在)\n'; }
win(){ powershell.exe -NoProfile -NonInteractive -Command "$1" 2>/dev/null | tr -d '\r' | ind; }
# URL 內嵌的 user:pass@ 一律遮蔽，否則位址類變數會把密碼原樣印出
maskurl(){ printf '%s' "$1" | sed -E 's#://[^:/@]+:[^@]*@#://<帳密已遮蔽>@#'; }

echo "verify-nightly.sh — $(date -Is)  host=$(hostname)  user=$(whoami)"
echo "執行期目錄 = $RUNTIME_DIR"
echo "時間窗 = 最近 ${SINCE_HOURS} 小時"
echo "對應文件：docs/2026-09-22-system-flow-steps.md 流程 A；驗收項 OPS-02"

# ------------------------------------------------------------------ 0
h "0. 設定載入（白名單放行，不在清單上的變數一律遮蔽）"
ENVF="$RUNTIME_DIR/.env"
getenv(){ [ -f "$ENVF" ] && grep -E "^\s*$1\s*=" "$ENVF" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'"'"'\r'; }
if [ -f "$ENVF" ]; then
  ok ".env 存在：$(readlink -f "$ENVF")"
  echo "  （安全設計：採白名單放行而非黑名單遮蔽。黑名單會漏掉沒有 PASSWORD 字樣的"
  echo "    金鑰變數，例如 NEO4J_AUTH=neo4j/密碼；白名單則是新增未知變數時預設安全。）"
  grep -E '^[A-Z][A-Z0-9_]*=' "$ENVF" | while IFS= read -r line; do
    name=${line%%=*}; val=${line#*=}
    case "$name" in
      *URI|*URL|*PORT|*HOST|*ENDPOINT|*_DB|*DATABASE|*DIR)
        printf '    %s=%s\n' "$name" "$(maskurl "$val")" ;;
      *) printf '    %s=<已遮蔽>\n' "$name" ;;
    esac
  done

  DATA_RAW_DIR=$(getenv DATA_RAW_DIR)
  NEO4J_URI=$(getenv NEO4J_URI)
  CHROMADB_PORT=$(getenv CHROMADB_PORT)

  echo
  echo "  關鍵檢定（對照 docs/ports.md）："
  case "$NEO4J_URI" in
    "")     warn "未設 NEO4J_URI —— 程式碼預設值為已廢除的 7688，會連到空埠（OPS-04）" ;;
    *7688*) bad  "NEO4J_URI 仍指向已廢除的 7688 —— 埠號整併機器端未套用（OPS-08）" ;;
    *7687*) ok   "NEO4J_URI 指向標準埠 7687" ;;
    *)      warn "NEO4J_URI = $(maskurl "$NEO4J_URI")（非 7687／7688，請確認）" ;;
  esac
  ML=$(getenv ML_SERVICE_URL)
  case "$ML" in
    "")     bad  "未設 ML_SERVICE_URL —— 程式碼將採預設 http://cuda-ml-service:8080，"
            echo "       該主機名是 docker-compose 服務名，Docker 已移除後無法解析（缺陷 C3）" ;;
    *8080*) warn "ML_SERVICE_URL 仍指 8080 —— 與 Open WebUI 衝突，應遷 8002（缺陷 C1）" ;;
    *8002*) ok   "ML_SERVICE_URL 已遷至 8002" ;;
  esac
  grep -qE '^RAG_API_PORT=' "$ENVF" && \
    warn "有 RAG_API_PORT，但程式碼讀的是 RAG_MANAGER_PORT —— 此為死變數（缺陷 C2）"
  case "$DATA_RAW_DIR" in
    /*|[A-Za-z]:*) ok "DATA_RAW_DIR 為絕對路徑" ;;
    "") warn "DATA_RAW_DIR 未設定，第 5 節會略過" ;;
    *)  warn "DATA_RAW_DIR 是相對路徑（OPS-04）—— 不同工作目錄會指到不同地方" ;;
  esac
else
  bad "找不到 $ENVF —— 第 0、5～9 節會略過。請用 RUNTIME_DIR= 指定正確路徑"
fi

# ------------------------------------------------------------------ 1
h "1. 副本身分（SYS-05：改了程式卻沒生效，先看這一節）"
kv "工作目錄" "$(pwd)"
if git rev-parse --git-dir >/dev/null 2>&1; then
  kv "有 .git" "是"
  kv "remote"  "$(git remote get-url origin 2>/dev/null || echo '(無 origin)')"
  kv "branch"  "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  kv "HEAD"    "$(git log -1 --format='%h %ad %s' --date=short 2>/dev/null)"
  kv "未提交變更" "$(git status --porcelain 2>/dev/null | wc -l) 筆"
else
  bad "無 .git —— 這是離線快照，與版控脫鉤，改動無法追溯"
fi
echo
echo "  -- 執行期目錄是否已是正本的 checkout（SYS-05-T 的判定）--"
if [ -d "$RUNTIME_DIR/.git" ]; then
  ok "執行期目錄有 .git：$(git -C "$RUNTIME_DIR" remote get-url origin 2>/dev/null)"
  kv "  其 HEAD" "$(git -C "$RUNTIME_DIR" log -1 --format='%h %s' 2>/dev/null)"
  kv "  未提交" "$(git -C "$RUNTIME_DIR" status --porcelain 2>/dev/null | wc -l) 筆"
elif [ -d "$RUNTIME_DIR" ]; then
  bad "執行期目錄存在但無 .git —— 與正本脫鉤（缺陷 A4）。"
  echo "       改正本的程式碼不會改變實際運行的系統；部署須走流程 F-5 手動同步。"
else
  warn "執行期目錄不存在，無法判定"
fi
echo
echo "  -- 機器上其他疑似副本 --"
for d in /mnt/*/ "$HOME"; do
  find "$d" -maxdepth 3 \
    \( -path '*/.cache/*' -o -path '*/.claude/*' -o -name node_modules -o -name '*venv*' \) -prune -o \
    -type d \( -iname '*art*icnclab*' -o -iname '*藝術史*' \) -print 2>/dev/null
done | sort -u | ind

# ------------------------------------------------------------------ 2
h "2. 排程器上次執行結果（A-1 的觸發端，Windows 側）"
if command -v powershell.exe >/dev/null 2>&1; then
  win 'Get-ScheduledTask | Where-Object {$_.TaskName -like "*ArtHistory*" -or $_.TaskName -like "*DailyCrawl*"} |
       ForEach-Object { $i = $_ | Get-ScheduledTaskInfo
         "{0,-34} State={1,-9} LastRun={2} Result=0x{3:X}" -f $_.TaskName,$_.State,$i.LastRunTime,$i.LastTaskResult }'
  echo "    判讀：Result=0x0 才是成功。0x41303 = 從未執行。其他非零值代表腳本非正常結束。"
else
  warn "叫不到 powershell.exe，略過（此節須在 WSL 內執行才查得到 Windows 排程器）"
fi

# ------------------------------------------------------------------ 3
h "3. 服務存活與埠號（A-1；對照 docs/ports.md）"
echo "  -- 監聽中的相關埠 --"
ss -tlnp 2>/dev/null | grep -E ':(5432|6379|7474|7687|7688|7475|8000|8002|8007|8010|8080|9200|11434)\b' | ind \
  || echo "    （無任何相關埠在監聽——服務可能全部沒在跑）"
echo
for spec in "5432:PostgreSQL" "6379:Redis" "7687:Neo4j-bolt" "8000:ChromaDB" \
            "8007:rag-manager-v2" "8080:OpenWebUI" "9200:Elasticsearch" "11434:Ollama"; do
  p=${spec%%:*}; n=${spec#*:}
  if ss -tln 2>/dev/null | grep -qE ":$p\b"; then ok "$p $n 在監聽"; else bad "$p $n 沒在監聽"; fi
done
for p in 7688 7475; do
  ss -tln 2>/dev/null | grep -qE ":$p\b" && bad "$p 仍有服務——舊 Neo4j 實例沒停乾淨（缺陷 B1）" || ok "$p 已淨空"
done
echo
echo "  -- 對外綁定檢查（NFR-08，應全部為 127.0.0.1）--"
ss -tln 2>/dev/null | grep -E '0\.0\.0\.0|\[::\]' | ind || ok "無 0.0.0.0 綁定"

echo
echo "  -- systemd 服務狀態與重啟次數（crash-loop 的關鍵指標，缺陷 B3）--"
for s in ollama neo4j elasticsearch postgresql redis-server; do
  st=$( { systemctl is-active  "$s" 2>/dev/null || echo n/a; } | head -1)
  en=$( { systemctl is-enabled "$s" 2>/dev/null || echo n/a; } | head -1)
  nr=$( { systemctl show "$s" -p NRestarts --value 2>/dev/null || echo '?'; } | head -1)
  kv "$s" "active=$st  enabled=$en  重啟次數=$nr"
done
echo "    判讀：重啟次數持續增長 = crash-loop。"
echo "          neo4j 與 ollama 的 systemd 實例應為 disabled（與本專案無關，見 OPS-08）。"
echo
echo "  -- 誰在 systemd 之外跑這些服務（PPID=1 才是 systemd 啟動）--"
ps -eo pid,ppid,user,etime,cmd --sort=start_time 2>/dev/null \
  | grep -iE 'neo4j|elastic|ollama|chroma|gunicorn|uvicorn|open.?webui|PPID' \
  | grep -v grep | ind || echo "    (未找到相關程序)"
echo "    判讀：專案服務由 Start-NativeServices.ps1 以 Start-Process wsl.exe 拉起，"
echo "          PPID 非 1 屬正常（SYS-03）；systemd 同時也在跑同一服務才是衝突。"

# ------------------------------------------------------------------ 4
h "4. Ollama 模型清單（A-2 — 這一步不能跳過）"
TAGS=$(curl -s --max-time 5 http://127.0.0.1:11434/api/tags 2>/dev/null)
if [ -z "$TAGS" ]; then
  bad "連不上 11434。佔埠者可能不是 Ollama——跑 scripts/collect.sh 查 PID 身分（缺陷 B2）"
elif echo "$TAGS" | grep -q '"models"[[:space:]]*:[[:space:]]*\[[[:space:]]*\]'; then
  bad "回傳空清單——佔埠的實例沒有任何模型，生成請求必然失敗（缺陷 B2）"
else
  ok "模型清單："
  echo "$TAGS" | grep -oE '"name"[[:space:]]*:[[:space:]]*"[^"]+"' | cut -d'"' -f4 | ind
  echo "    判讀：須確認本專案用的生成模型與嵌入模型都在清單內。"
fi

# ------------------------------------------------------------------ 5
h "5. 原始檔落地與 Yale 移除確認（A-3）"
if [ -n "${DATA_RAW_DIR:-}" ] && [ -d "$DATA_RAW_DIR" ]; then
  echo "  -- 最近 ${SINCE_HOURS}h 內新增/異動的檔案，依第一層子目錄（來源）計數 --"
  find "$DATA_RAW_DIR" -type f -mmin "-$((SINCE_HOURS*60))" -printf '%P\n' 2>/dev/null \
    | awk -F/ '{print ($2==""?"(根目錄)":$1)}' | sort | uniq -c | sort -rn | ind
  TOT=$(find "$DATA_RAW_DIR" -type f -mmin "-$((SINCE_HOURS*60))" 2>/dev/null | wc -l)
  echo "    本次總計 $TOT 檔"
  [ "$TOT" -eq 0 ] && bad "時間窗內沒有任何新檔——爬蟲很可能整批沒跑" || ok "有新檔落地"
  echo
  echo "  -- 來源數判定（規格 DAT-04 基準為 11 個來源）--"
  SRC=$(find "$DATA_RAW_DIR" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null | sort)
  echo "$SRC" | ind; echo "    目錄數 = $(echo "$SRC" | grep -c .)"
  echo
  echo "  -- Yale 移除確認（OPS-02 的重點）--"
  YN=$(find "$DATA_RAW_DIR" -iname '*yale*' -mmin "-$((SINCE_HOURS*60))" 2>/dev/null | wc -l)
  [ "$YN" -eq 0 ] && ok "時間窗內無 Yale 新檔，符合『已移除』" \
                  || bad "時間窗內仍有 $YN 個 Yale 檔——移除未生效"
  echo "  -- 設定檔與程式碼內是否仍殘留 Yale 來源 --"
  grep -rniE 'yale' "$RUNTIME_DIR" --include='*.py' --include='*.js' --include='*.json' \
      --include='*.yaml' --include='*.yml' --include='.env' -l 2>/dev/null | head -20 | ind \
      || ok "設定與程式碼中查無 Yale 殘留"
else
  warn "DATA_RAW_DIR 不存在或未設定，略過本節（不代表通過）"
fi

# ------------------------------------------------------------------ 6
h "6. PostgreSQL：catalog / outbox（A-7、A-8）"
PG_OK=0
if ! command -v psql >/dev/null 2>&1; then
  warn "本機無 psql，略過第 6～9 節的資料庫查證（不代表通過）"
else
  PGPASSWORD="$(getenv PGPASSWORD)"; [ -z "$PGPASSWORD" ] && PGPASSWORD="$(getenv DB_PASSWORD)"
  PGH="$(getenv PGHOST)";      [ -z "$PGH" ]  && PGH="$(getenv DB_HOST)";      PGH="${PGH:-127.0.0.1}"
  PGU="$(getenv PGUSER)";      [ -z "$PGU" ]  && PGU="$(getenv DB_USER)";      PGU="${PGU:-postgres}"
  PGDB="$(getenv PGDATABASE)"; [ -z "$PGDB" ] && PGDB="$(getenv DB_NAME)";     PGDB="${PGDB:-postgres}"
  export PGPASSWORD
  echo "  連線：host=$PGH user=$PGU db=$PGDB（密碼已遮蔽）"
  pgq(){ psql -h "$PGH" -U "$PGU" -d "$PGDB" -tA -c "$1" 2>&1; }

  if ! pgq 'SELECT 1' | grep -q '^1$'; then
    bad "連不上 PostgreSQL，第 6～9 節略過（不代表通過）"
  else
    PG_OK=1
    echo "  -- 實際存在的資料表（先確認表名，再查數）--"
    pgq "SELECT table_schema||'.'||table_name FROM information_schema.tables
         WHERE table_schema IN ('public','catalog','biz','eval')
         ORDER BY 1" | ind
    echo
    echo "  -- 各表估計筆數 --"
    pgq "SELECT schemaname||'.'||relname||'  '||n_live_tup
         FROM pg_stat_user_tables
         WHERE schemaname IN ('public','catalog','biz','eval')
         ORDER BY 1" | ind
    echo "    註：n_live_tup 為統計估計值；關鍵表的精確筆數見第 9 節。"
    echo
    echo "  -- outbox 積壓（關鍵：積壓不會報錯，但代表三庫已經開始不同步）--"
    OB=$(pgq "SELECT table_schema||'.'||table_name FROM information_schema.tables
              WHERE table_name ILIKE '%outbox%' LIMIT 1")
    if [ -n "$OB" ]; then
      echo "    outbox 表 = $OB"
      echo -n "    欄位："; pgq "SELECT column_name FROM information_schema.columns
           WHERE table_schema||'.'||table_name='$OB' ORDER BY ordinal_position" | tr '\n' ' '
      echo
      pgq "SELECT COUNT(*) FROM $OB" | sed 's/^/    總筆數: /'
      for col in processed_at consumed_at published_at delivered_at; do
        n=$(pgq "SELECT COUNT(*) FROM $OB WHERE $col IS NULL" 2>/dev/null)
        case "$n" in ''|*ERROR*|*error*|*exist*) ;; *)
          [ "$n" -eq 0 ] && ok "未消費事件 0 筆（依 $col 判定）——訂閱器已追平" \
                         || bad "未消費事件 $n 筆（依 $col 判定）——訂閱器落後（DAT-03）" ;;
        esac
      done
    else
      warn "查不到 outbox 表，略過積壓檢查"
    fi
  fi
fi

# ------------------------------------------------------------------ 7
h "7. 三庫一致性計數比對（A-11 / DAT-04）"
CHP="${CHROMADB_PORT:-8000}"
echo "  -- ChromaDB（:$CHP）--"
curl -s --max-time 5 "http://127.0.0.1:$CHP/api/v2/heartbeat" 2>/dev/null | ind \
  || curl -s --max-time 5 "http://127.0.0.1:$CHP/api/v1/heartbeat" 2>/dev/null | ind \
  || bad "ChromaDB 無回應"
echo "  -- Elasticsearch（:9200）--"
ESU="$(getenv ES_USER)"; ESU="${ESU:-elastic}"; ESP="$(getenv ES_PASSWORD)"
if [ -n "$ESP" ]; then
  curl -s --max-time 5 -u "$ESU:$ESP" 'http://127.0.0.1:9200/_cat/indices?v&h=index,docs.count,store.size' 2>/dev/null | ind \
    || bad "ES 查詢失敗（缺陷 B3：ES 可能正在 30 秒重啟迴圈中，見第 3 節重啟次數）"
else
  warn "取不到 ES_PASSWORD，略過。提醒：OPS-01 這組密碼已視為外洩，須更換"
fi
echo "  -- Neo4j --"
if command -v cypher-shell >/dev/null 2>&1; then
  N4P="$(getenv NEO4J_PASSWORD)"; N4U="$(getenv NEO4J_USER)"; N4U="${N4U:-neo4j}"
  cypher-shell -a "${NEO4J_URI:-bolt://127.0.0.1:7687}" -u "$N4U" -p "$N4P" --format plain \
    'MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC;' 2>&1 | ind
else
  warn "無 cypher-shell，略過"
fi
echo "    判讀：catalog 的 chunk 數應等於 Chroma 向量數、等於 ES doc 數。三者不等即 DAT-05 告警條件。"

# ------------------------------------------------------------------ 8
h "8. 軟到期與 30 天保留（A-9、A-10 / DAT-20～21）"
if [ "$PG_OK" = 1 ]; then
  T=$(pgq "SELECT table_schema||'.'||table_name FROM information_schema.columns
           WHERE column_name='valid_to' LIMIT 1")
  if [ -n "$T" ]; then
    echo "    含 valid_to 的表 = $T"
    pgq "SELECT COUNT(*) FILTER (WHERE valid_to IS NULL)                        AS 有效,
                COUNT(*) FILTER (WHERE valid_to IS NOT NULL)                    AS 已軟到期,
                COUNT(*) FILTER (WHERE valid_to > now()-interval '${SINCE_HOURS} hours') AS 本次新標記,
                COUNT(*) FILTER (WHERE valid_to < now()-interval '30 days')     AS 逾30天未清除
         FROM $T" | ind
    echo "    判讀：『逾30天未清除』必須為 0，否則 A-10 的硬刪除沒有執行（DAT-21）。"
  else
    warn "查不到含 valid_to 的表，略過"
  fi
else
  warn "PostgreSQL 不可用，略過本節（不代表通過）"
fi

# ------------------------------------------------------------------ 9
h "9. 嵌入模型版本標註與評測表現況（DAT-30、EVL-04）"
if [ "$PG_OK" = 1 ]; then
  n=$(pgq "SELECT COUNT(*) FROM information_schema.columns
           WHERE column_name IN ('embedding_model','embedding_version')")
  [ "${n:-0}" -gt 0 ] && ok "已有 embedding_model/version 欄位（DAT-30 已實作）" \
                      || warn "查無 embedding_model/version 欄位——DAT-30 尚未實作，符合規格書現況記載"
  for t in eval.golden_set eval.measurements eval.alerts eval.refusal_queue biz.messages; do
    c=$(pgq "SELECT COUNT(*) FROM $t" 2>/dev/null)
    case "$c" in ''|*ERROR*|*error*|*exist*) echo "    $t：表不存在" ;;
      *) echo "    $t：$c 筆" ;;
    esac
  done
  echo "    判讀：依規格書現況，eval 三表與 biz.messages 預期皆為 0 筆。"
  echo "          若 eval.alerts 已有筆數，代表 EVL-11 已實作，須逐筆看內容。"
else
  warn "PostgreSQL 不可用，略過本節（不代表通過）"
fi

# ------------------------------------------------------------------ 10
h "10. 備份產出（A-13 / NFR-11）"
FOUND_BK=0
for d in "$RUNTIME_DIR/db_backups" "$HOME/db_backups" "$RUNTIME_DIR/backups"; do
  [ -d "$d" ] || continue
  FOUND_BK=1
  echo "  -- $d --"
  find "$d" -type f -mtime -2 -printf '%TY-%Tm-%Td %TH:%TM  %10s  %P\n' 2>/dev/null | sort | ind \
    || echo "    （最近 2 天無備份檔）"
done
[ "$FOUND_BK" -eq 0 ] && bad "三個候選路徑都找不到備份目錄——A-13 可能沒執行，或備份寫到別處"
echo "    判讀：PostgreSQL 與 Neo4j 兩者都要有當日備份，且大小不可異常偏小。"

# ------------------------------------------------------------------ 11
h "11. 夜間 log 的錯誤掃描（涵蓋 A-3～A-13 的靜默失敗）"
echo "  -- 最近 ${SINCE_HOURS}h 內異動的 log 檔 --"
LOGS=$(find "$RUNTIME_DIR" -type f \( -name '*.log' -o -name '*.out' -o -name '*.txt' \) \
       -mmin "-$((SINCE_HOURS*60))" 2>/dev/null | head -40)
if [ -z "$LOGS" ]; then
  warn "時間窗內找不到任何 log 檔——夜間流程可能根本沒跑，或 log 寫到別處"
else
  echo "$LOGS" | ind
  echo
  echo "  -- 其中的錯誤行（各檔最多 5 行）--"
  echo "$LOGS" | while IFS= read -r f; do
    m=$(grep -inE 'traceback|error|exception|failed|refused|timeout|OOM' "$f" 2>/dev/null | head -5)
    [ -n "$m" ] && { echo "  【$f】"; echo "$m" | ind; }
  done
  echo "    判讀：爬蟲單一來源失敗不會中止整體流程，所以這一節是唯一能看出『部分失敗』的地方。"
fi

# ------------------------------------------------------------------ 12
h "12. OOM 跡象與資源（OPS-07：ES 重啟迴圈的指定檢定方式）"
for svc in elasticsearch neo4j; do
  echo "  -- $svc 近一小時的 OOM／逾時線索 --"
  journalctl -u "$svc" --since '1 hour ago' --no-pager 2>/dev/null \
    | grep -iE 'oom|killed|out of memory|timeout|failed to start' | tail -20 | ind \
    || echo "    (查無，或無權限讀 journal)"
done
echo "  -- 核心 OOM killer --"
dmesg -T 2>/dev/null | grep -iE 'out of memory|oom-kill' | tail -10 | ind \
  || echo "    (dmesg 無權限 —— 請改用 sudo 執行本腳本)"
echo
echo "  -- 資源（Neo4j／ES／Ollama 同時啟動的競爭條件）--"
run free -h
run nproc
run df -h /
echo "    判讀：確認為 OOM 則依 OPS-07 釘死 ES heap -Xms2g -Xmx2g。"

# ------------------------------------------------------------------ 13
h "13. OPS-02 驗收勾選表（請依上列輸出逐項判定）"
cat <<'CHECKEOF'
    [ ] 1. 排程器 LastTaskResult = 0x0                       ← 第 2 節
    [ ] 2. 八個服務埠全部在監聽，7688/7475 淨空              ← 第 3 節
    [ ] 3. systemd 重啟次數沒有持續增長                      ← 第 3 節
    [ ] 4. Ollama 模型清單非空且含專案模型                   ← 第 4 節
    [ ] 5. 時間窗內有新檔落地，且 Yale 新檔數 = 0            ← 第 5 節
    [ ] 6. outbox 未消費事件 = 0（訂閱器已追平）             ← 第 6 節
    [ ] 7. catalog chunk 數 = Chroma 向量數 = ES doc 數      ← 第 7 節
    [ ] 8. 逾 30 天未清除的軟到期資料 = 0                    ← 第 8 節
    [ ] 9. PostgreSQL 與 Neo4j 當日備份都存在且大小正常      ← 第 10 節
    [ ] 10. log 無 Traceback／Exception／OOM                 ← 第 11、12 節

    十項全中，OPS-02 才算通過。任一項未中，對照
    docs/2026-09-22-system-flow-steps.md §8.2 徵狀對照表處理。
    標「略過（不代表通過）」的區節等同未驗證，不可當作通過。
CHECKEOF

echo
echo "verify-nightly.sh 結束 — $(date -Is)"
echo "請將本輸出完整回貼，作為「現況」的憑據。"
