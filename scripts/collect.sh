#!/usr/bin/env bash
# collect.sh — 一次收集所有待確認的現況，輸出成單一檔案
#
# 為什麼有這支：剩餘的檢定橫跨 WSL 與 Windows 兩側，原本要貼好幾段、還要切換終端。
# WSL 內可直接呼叫 powershell.exe / wsl.exe，故全部併為一支。
#
# 全唯讀：只執行 find / grep / systemctl show / journalctl / Get-Process 等查詢指令，
# 不做任何 start / stop / restart / rm / mv。可安全重複執行。
#
# 用法（在 WSL Ubuntu-22.04 內）：
#   bash scripts/collect.sh | tee ~/collect.txt
#
set -uo pipefail

h(){ printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }
ind(){ sed 's/^/    /'; }
win(){ powershell.exe -NoProfile -NonInteractive -Command "$1" 2>/dev/null | tr -d '\r' | ind; }

echo "collect.sh — $(date -Is)  host=$(hostname)"
echo "此輸出可直接整份回貼。金鑰不會出現在其中（見第4節的遮蔽規則）。"

# ------------------------------------------------------------------ 1
h "1. 快照位置與層數判定"
SNAP=/mnt/f/art_icnclab-main
if [ -e "$SNAP/art_icnclab-main/package.json" ]; then
  SNAP="$SNAP/art_icnclab-main"; echo "  判定：雙層結構（ZIP 解壓典型）"
elif [ -e "$SNAP/package.json" ]; then
  echo "  判定：單層結構"
else
  echo "  ⚠ 在 $SNAP 找不到 package.json —— 路徑可能不對"
fi
echo "  SNAP = $SNAP"
if [ -d "$SNAP" ]; then
  ls "$SNAP" | head -12 | ind
  [ -d "$SNAP/docs/designs" ] \
    && { echo "  ✅ docs/designs 存在，設計文件確實在這份："; ls "$SNAP/docs/designs" | ind; } \
    || echo "  ❌ 找不到 docs/designs"
fi

h "1b. 所有磁碟上的副本"
ls -d /mnt/*/ 2>/dev/null | ind
for d in /mnt/*/; do
  find "$d" -maxdepth 3 -type d \
    \( -name node_modules -o -name '*venv*' -o -name site-packages -o -name .git \) -prune -o \
    -type d \( -iname '*art*icnclab*' -o -iname '*藝術史*' \) -print 2>/dev/null
done | ind

# ------------------------------------------------------------------ 2
h "2. 搬動造成的破口（可能是發現3 的成因）"
# 只看與本專案相關的連結：指向 /mnt 的、或名稱含 art/icnclab/藝術史 的、或已斷的。
# 不過濾的話會把整個 ~/.cargo、~/.local 倒出來，全是雜訊。
echo "  -- 相關的符號連結（指向 /mnt、名稱相關、或已斷） --"
found=0
while IFS= read -r l; do
  tgt=$(readlink "$l")
  broken=""; [ -e "$l" ] || broken="   ← 已斷"
  case "$tgt$l" in
    */mnt/*|*art*|*icnclab*|*藝術史*) ;;
    *) [ -n "$broken" ] || continue ;;
  esac
  printf '    %s -> %s%s\n' "$l" "$tgt" "$broken"; found=1
done < <(find "$HOME" /home -maxdepth 5 -type l 2>/dev/null)
[ "$found" -eq 1 ] || echo "    (無相關連結。注意：調查報告提到的 /home/user/icnclab/art_history_db 若不在此表，表示它已不存在)"

echo "  -- 明確檢查調查報告提到的那個連結 --"
for l in /home/user/icnclab/art_history_db "$HOME/icnclab/art_history_db"; do
  if [ -L "$l" ]; then
    printf '    %s -> %s%s\n' "$l" "$(readlink "$l")" "$([ -e "$l" ] || printf '   ← 已斷')"
  else
    echo "    $l 不存在"
  fi
done

echo "  -- systemd unit 內寫死的 /mnt 路徑 --"
grep -rnE '/mnt/[a-z]/' /etc/systemd/system/*.service 2>/dev/null | head -20 | ind \
  || echo "    (無)"
echo "  -- 服務的工作目錄與啟動指令 --"
for s in neo4j elasticsearch ollama; do
  printf '    %s: ' "$s"
  systemctl show "$s" -p WorkingDirectory -p ExecStart --value 2>/dev/null | tr '\n' ' '
  echo
done

# ------------------------------------------------------------------ 3
h "3. Ollama 埠 11434 佔用者（發現2 的最後一格）"
echo "  -- Windows 側：誰在聽 11434 --"
win 'Get-NetTCPConnection -LocalPort 11434 -State Listen -EA SilentlyContinue |
     ForEach-Object { $p = Get-Process -Id $_.OwningProcess -EA SilentlyContinue
       "{0,-6} {1,-20} {2}" -f $_.OwningProcess, $p.ProcessName, $p.Path }'
echo "  -- 備援：若上面沒輸出，用 netstat + tasklist --"
win 'netstat -ano | Select-String ":11434" | Select-Object -First 3'
echo "  -- 所有名稱含 ollama 的 Windows 程序 --"
win 'Get-Process | Where-Object ProcessName -match "ollama|wslrelay|wslhost" |
     Select-Object Id,ProcessName,Path | Format-Table -AutoSize | Out-String'
echo "  -- WSL 發行版清單（另一個 Ubuntu 是否仍在跑） --"
wsl.exe -l -v 2>/dev/null | tr -d '\0' | ind || echo "    (無法取得)"
echo "  -- 本發行版內的 ollama 服務 --"
printf '    is-active=%s is-enabled=%s NRestarts=%s\n' \
  "$( { systemctl is-active ollama  2>/dev/null || echo n/a; } | head -1)" \
  "$( { systemctl is-enabled ollama 2>/dev/null || echo n/a; } | head -1)" \
  "$( { systemctl show ollama -p NRestarts --value 2>/dev/null || echo '?'; } | head -1)"
journalctl -u ollama --since '30 min ago' --no-pager 2>/dev/null \
  | grep -i 'address already in use' | tail -3 | ind || echo "    (近 30 分無埠衝突紀錄)"
echo "  -- 11434 實際可用性 --"
curl -s --max-time 5 http://127.0.0.1:11434/api/tags | head -c 300 | ind \
  || echo "    (連不上)"

# ------------------------------------------------------------------ 4
h "4. Neo4j / Elasticsearch 重啟迴圈（發現3 的兩個假說）"
echo "  -- 假說A：有東西在 systemd 之外啟動它們 --"
ps -eo pid,ppid,user,etime,cmd --sort=start_time 2>/dev/null \
  | grep -iE 'neo4j|elastic|chroma|PPID' | grep -v grep | ind || echo "    (未找到)"
echo "    ↑ PPID=1 表示由 systemd 啟動；非 1 表示有腳本在搶著啟動它"
echo "  -- 假說B：OOM 或啟動逾時 --"
for s in elasticsearch neo4j; do
  echo "    [$s]"
  journalctl -u "$s" --since '2 hours ago' --no-pager 2>/dev/null \
    | grep -iE 'oom|killed|out of memory|timeout|already running|failed to start' \
    | tail -8 | sed 's/^/      /' || echo "      (查無)"
done
dmesg -T 2>/dev/null | grep -iE 'out of memory|oom-kill' | tail -5 | ind \
  || echo "    (dmesg 需 sudo，可改用 sudo bash scripts/collect.sh)"
echo "  -- ES heap 設定（預設會吃掉實體記憶體一半） --"
grep -rhE '^-Xm[sx]' /etc/elasticsearch/jvm.options /etc/elasticsearch/jvm.options.d/ 2>/dev/null \
  | ind || echo "    (未明確設定 → 使用預設值，在多服務並存時易 OOM)"
echo "  -- 重啟次數 --"
for s in neo4j elasticsearch; do
  printf '    %s: NRestarts=%s is-active=%s\n' "$s" \
    "$( { systemctl show "$s" -p NRestarts --value 2>/dev/null || echo '?'; } | head -1)" \
    "$( { systemctl is-active "$s" 2>/dev/null || echo n/a; } | head -1)"
done
echo "  -- 週期性觸發器 --"
{ crontab -l 2>/dev/null; sudo crontab -l 2>/dev/null; } | grep -vE '^#|^$' | ind \
  || echo "    (無 cron 項目)"
systemctl list-timers --all --no-pager 2>/dev/null | head -10 | ind
win 'Get-ScheduledTask | Where-Object { $_.TaskName -match "neo4j|elastic|ollama|art" } |
     Select-Object TaskName,State | Format-Table -AutoSize | Out-String'

# ------------------------------------------------------------------ 5
h "5. 設定實際生效值（金鑰一律遮蔽）"
for cand in "$SNAP/.env" /mnt/d/art_icnclab/.env /mnt/f/art_icnclab/.env; do
  [ -f "$cand" ] || continue
  echo "  [$cand]"
  # 白名單放行：只有連線位址類變數印值，其餘只印變數名
  grep -E '^[A-Z][A-Z0-9_]*=' "$cand" | while IFS= read -r line; do
    name=${line%%=*}; val=${line#*=}
    case "$name" in
      *URI|*URL|*PORT|*HOST|*ENDPOINT)
        printf '      %s=%s\n' "$name" \
          "$(printf '%s' "$val" | sed -E 's#://[^:/@]+:[^@]*@#://<帳密已遮蔽>@#')" ;;
      *) printf '      %s=<已遮蔽>\n' "$name" ;;
    esac
  done
  grep -qE '^NEO4J_URI=' "$cand" || echo "      註：未設 NEO4J_URI 時採預設 bolt://127.0.0.1:7687（標準埠，2026-09-20 起）"
  grep -qE '^ML_SERVICE_URL=' "$cand" || echo "      ⚠ 未設 ML_SERVICE_URL → 預設 http://127.0.0.1:8080"
done

h "6. 實際監聽埠"
if command -v ss >/dev/null 2>&1; then
  ss -tlnp 2>/dev/null | ind
else
  echo "    ⚠ 無 ss 指令（請 sudo apt install iproute2）"
fi

h "完成"
echo "請將本檔整份回貼：  bash scripts/collect.sh | tee ~/collect.txt"
