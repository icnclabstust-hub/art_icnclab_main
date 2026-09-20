#!/usr/bin/env bash
# doctor.sh — 現況自檢：一道指令印出「我是誰、誰在跑、誰佔埠、設定實際值為何」
#
# 設計原則：
#   1. 全唯讀。不執行任何 start/stop/restart/rm/install。可安全重複執行。
#   2. 不因單一項目失敗而中止（不設 -e），因為「某項查不到」本身就是要呈現的結果。
#   3. 輸出可直接貼進 issue 或對話，作為「現況」的憑據。
#
# 用法： bash scripts/doctor.sh            # 於 WSL Ubuntu-22.04 內執行
#        bash scripts/doctor.sh > doctor-$(date +%F-%H%M).txt

set -uo pipefail

h()  { printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }
kv() { printf '  %-24s %s\n' "$1" "$2"; }
run(){ printf '  $ %s\n' "$*"; "$@" 2>&1 | sed 's/^/    /' || printf '    (指令失敗或不存在)\n'; }

echo "doctor.sh — $(date -Is)  host=$(hostname)  user=$(whoami)"

# ---------------------------------------------------------------- 1. 我是哪一份副本
h "1. 副本身分（對應發現1）"
kv "工作目錄" "$(pwd)"
if git rev-parse --git-dir >/dev/null 2>&1; then
  kv "有 .git"      "是"
  kv "remote"       "$(git remote get-url origin 2>/dev/null || echo '(無 origin)')"
  kv "branch"       "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  kv "HEAD"         "$(git log -1 --format='%h %ad %s' --date=short 2>/dev/null)"
  kv "未提交變更數" "$(git status --porcelain 2>/dev/null | wc -l)"
else
  kv "有 .git"      "否 ← 這是離線快照，與版控脫鉤，改動無法追溯"
fi

h "1b. 機器上其他疑似副本"
run find /mnt/c /mnt/d "$HOME" -maxdepth 3 -type d \
  \( -path '*/.cache/*' -o -path '*/.claude/*' -o -path '*/node_modules/*' \) -prune -o \
  -type d \( -iname '*art*icnclab*' -o -iname '*藝術史*' \) -print

# ---------------------------------------------------------------- 2. 服務狀態
h "2. 服務狀態（對應發現2/3/4）"
for s in ollama neo4j elasticsearch postgresql redis-server docker; do
  st=$( { systemctl is-active  "$s" 2>/dev/null || echo n/a; } | head -1)
  en=$( { systemctl is-enabled "$s" 2>/dev/null || echo n/a; } | head -1)
  nr=$( { systemctl show "$s" -p NRestarts --value 2>/dev/null || echo '?'; } | head -1)
  kv "$s" "active=$st  enabled=$en  重啟次數=$nr"
done
echo "  (重啟次數持續增長 = crash-loop；這是發現2/3 的關鍵指標)"

h "2b. 誰在 systemd 之外跑 Neo4j / ES（檢定假說A）"
echo "  PPID=1 表示由 systemd 啟動；PPID 非 1 表示有腳本在搶著啟動它"
ps -eo pid,ppid,user,etime,cmd --sort=start_time 2>/dev/null \
  | grep -iE 'neo4j|elastic|ollama|chroma|gunicorn|uvicorn|open.?webui|PPID' \
  | grep -v grep | sed 's/^/    /' || echo "    (未找到相關程序)"

h "2c. OOM 跡象（檢定假說B）"
for svc in elasticsearch neo4j; do
  echo "  -- $svc 近一小時的 OOM/逾時線索 --"
  journalctl -u "$svc" --since '1 hour ago' --no-pager 2>/dev/null \
    | grep -iE 'oom|killed|out of memory|timeout|failed to start' \
    | tail -20 | sed 's/^/    /' || echo "    (查無或無權限)"
done
echo "  -- 核心 OOM killer --"
dmesg -T 2>/dev/null | grep -iE 'out of memory|oom-kill' | tail -10 | sed 's/^/    /' \
  || echo "    (dmesg 無權限，請改用 sudo 執行本腳本)"

h "2d. 定期觸發器（誰在週期性重啟服務）"
run crontab -l
run systemctl list-timers --all

# ---------------------------------------------------------------- 3. 埠號
h "3. 實際監聽埠（對應發現5）"
run ss -tlnp
echo
if ! command -v ss >/dev/null 2>&1; then
  echo "  ⚠ 找不到 ss 指令，以下埠號對照表不可信，請先安裝 iproute2"
else
echo "  本專案關切的埠對照："
for p in 11434 7687 7688 8001 8002 8007 8008 8010 8080 3000 5432 6379 9200; do
  own=$(ss -tlnp 2>/dev/null | awk -v P=":$p\$" '$4 ~ P {print $6; exit}')
  kv "$p" "${own:-(未被佔用)}"
done
fi

h "3b. Ollama 實際可用性"
run curl -s --max-time 5 http://127.0.0.1:11434/api/tags

# ---------------------------------------------------------------- 4. 設定實際生效值
h "4. .env 實際生效值 vs 程式碼預設值（對應發現5 / Phase 2）"
ENVF="${ENVF:-.env}"
if [ -f "$ENVF" ]; then
  kv ".env 路徑" "$(readlink -f "$ENVF")"
  echo "  (預設遮蔽：只有連線位址類變數會印出值，其餘一律只印變數名)"
  # 安全設計：採「白名單放行」而非「黑名單遮蔽」。
  # 黑名單會漏掉沒有 PASSWORD 字樣的金鑰變數（例如 NEO4J_AUTH=neo4j/密碼）；
  # 白名單則是「不在清單上的一律遮蔽」，新增未知變數時預設安全。
  grep -E '^[A-Z][A-Z0-9_]*=' "$ENVF" | while IFS= read -r line; do
    name=${line%%=*}; val=${line#*=}
    case "$name" in
      *URI|*URL|*PORT|*HOST|*ENDPOINT|*_DB|*DATABASE)
        # URL 內嵌的 user:pass@ 仍須遮蔽
        printf '    %s=%s\n' "$name" \
          "$(printf '%s' "$val" | sed -E 's#://[^:/@]+:[^@]*@#://<帳密已遮蔽>@#')" ;;
      *) printf '    %s=<已遮蔽>\n' "$name" ;;
    esac
  done
  echo
  echo "  關鍵檢定："
  nu=$(grep -E '^NEO4J_URI=' "$ENVF" | head -1)
  if [ -z "$nu" ]; then
    echo "    ⚠ .env 未設 NEO4J_URI → 程式碼將採預設 bolt://127.0.0.1:7688"
    echo "      若 Neo4j 實際聽 7687（見 §3），則 RAG 後端連不上任何 Neo4j。"
  else
    # 與上方同樣遮蔽 URL 內嵌帳密，否則此處會把密碼原樣印出
    echo "    NEO4J_URI = $(printf '%s' "${nu#NEO4J_URI=}" \
      | sed -E 's#://[^:/@]+:[^@]*@#://<帳密已遮蔽>@#')"
  fi
  ml=$(grep -E '^ML_SERVICE_URL=' "$ENVF" | head -1)
  if [ -z "$ml" ]; then
    echo "    ⚠ .env 未設 ML_SERVICE_URL → 程式碼將採預設 http://cuda-ml-service:8080"
    echo "      cuda-ml-service 是 docker-compose 服務名，Docker 已移除後無法解析，"
    echo "      Node 後端將連不到 ml-service。"
  else
    echo "    ML_SERVICE_URL = $(printf '%s' "${ml#ML_SERVICE_URL=}" \
      | sed -E 's#://[^:/@]+:[^@]*@#://<帳密已遮蔽>@#')"
  fi
  grep -qE '^RAG_API_PORT=' "$ENVF" && \
    echo "    ⚠ .env 有 RAG_API_PORT，但程式碼讀的是 RAG_MANAGER_PORT → 此變數無效"

  echo
  echo "  ml-service / OpenWebUI 8080 歸屬檢定（決定：8080 歸 OpenWebUI）："
  grep -nE 'bind.*:8080' ml-service/start.sh 2>/dev/null | sed 's/^/    ⚠ ml-service 仍綁 8080: /' \
    || echo "    (ml-service/start.sh 不在此目錄，或已遷出 8080)"
else
  kv ".env" "找不到（在 $(pwd) 下）"
fi

# ---------------------------------------------------------------- 5. 資源
h "5. 資源（Neo4j/ES/Ollama 同時啟動的競爭條件）"
run free -h
run nproc
run df -h /

h "完成"
echo "請將本輸出完整回貼，作為「現況」的憑據。"
