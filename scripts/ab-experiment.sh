#!/usr/bin/env bash
# ab-experiment.sh — 兩項修正、各自兩法，用同一題做 A/B 對照
#
# 對照矩陣（實驗設計見 docs/2026-09-20-ab-experiment.md）：
#   自變項 1｜Neo4j 綁定    ：甲 0.0.0.0 ／ 乙 127.0.0.1 + preferIPv4Stack ／ 丙 0.0.0.0 無 preferIPv4Stack（機制對照）
#   自變項 2｜藝術家來源欄位：甲 Artist.source（單值）／ 乙 Artist.sources（推導清單）
#   固定項  ｜同一題、同一個圖快照、同一組檢索參數
#
# 設計原則（沿用 doctor.sh）：
#   1. 預設全唯讀。只有 `binding` 子命令會改動現場，且一定先備份、可一鍵還原。
#   2. 不設 -e。單項查不到本身就是要呈現的結果。
#   3. 每一步都印出「實際執行的 Cypher／HTTP 請求」，實驗要可重現才有意義。
#   4. 不猜 schema。屬性名一律先 discover 再用，對不上就明講，不默默給出錯的數字。
#
# 用法（在 WSL Ubuntu-22.04 內，專案執行期目錄下）：
#   bash scripts/ab-experiment.sh discover                 # 步驟 0：唯讀，確認 schema 與服務
#   bash scripts/ab-experiment.sh accuracy | tee ~/acc.txt # 步驟 1：唯讀，來源欄位準確率
#   bash scripts/ab-experiment.sh probe                    # 步驟 2：唯讀，目前綁定的連線可靠度
#   bash scripts/ab-experiment.sh binding --method B       # 步驟 3：改綁定（會動現場，需 sudo）
#   bash scripts/ab-experiment.sh restore                  # 還原最近一次備份
#
# 環境變數（有預設，但請先用 discover 確認）：
#   NEO4J_USER/NEO4J_PASSWORD  cypher-shell 認證（必填）
#   NEO4J_BOLT                 預設 bolt://127.0.0.1:7687
#   RAG_URL                    預設 http://127.0.0.1:8007
#   RAG_QUERY_PATH             不設則自動試探候選路徑
#   NEO4J_CONF                 預設 /etc/neo4j/neo4j.conf，原生安裝請指到安裝目錄的 conf
#   L_ARTIST/L_WORK/REL        標籤與關係名
#   P_REL_EXPIRE/P_WORK_DELETED/P_WORK_SOFT/P_WORK_SOURCE/P_ARTIST_NAME  屬性名

set -uo pipefail

# ---------------------------------------------------------------- 可調參數
NEO4J_BOLT="${NEO4J_BOLT:-bolt://127.0.0.1:7687}"
NEO4J_HTTP="${NEO4J_HTTP:-http://127.0.0.1:7474}"
NEO4J_CONF="${NEO4J_CONF:-/etc/neo4j/neo4j.conf}"
RAG_URL="${RAG_URL:-http://127.0.0.1:8007}"
RAG_QUERY_PATH="${RAG_QUERY_PATH:-}"

L_ARTIST="${L_ARTIST:-Artist}"
L_WORK="${L_WORK:-Artwork}"
REL="${REL:-CREATED}"
P_REL_EXPIRE="${P_REL_EXPIRE:-expired_at}"
P_WORK_DELETED="${P_WORK_DELETED:-deleted_at}"
P_WORK_SOFT="${P_WORK_SOFT:-is_deleted}"
P_WORK_SOURCE="${P_WORK_SOURCE:-source}"
P_ARTIST_NAME="${P_ARTIST_NAME:-name}"

# 同一題：選梵谷是因為他是唯一能同時打到兩個方法的案例——
# 橫跨 3 個來源（單值必失一部分），且舊值 met_museum 已無現存作品（單值不只是少，是錯）。
SUBJECT="${SUBJECT:-Vincent van Gogh}"
QUESTION="${QUESTION:-梵谷（Vincent van Gogh）現存作品分別來自哪些館藏來源？請完整列出全部來源。}"
STALE_TOKEN="${STALE_TOKEN:-met}"     # 預期不該出現的過時來源關鍵字
K_TRIALS="${K_TRIALS:-5}"             # 同一題重跑次數（測 LLM 穩定度）
N_CONN="${N_CONN:-20}"                # 連線可靠度試次

h()  { printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }
kv() { printf '  %-30s %s\n' "$1" "$2"; }
ind(){ sed 's/^/    /'; }
warn(){ printf '  \033[33m⚠ %s\033[0m\n' "$*"; }
bad(){ printf '  \033[31m✗ %s\033[0m\n' "$*"; }
ok(){ printf '  \033[32m✓ %s\033[0m\n' "$*"; }

# ---------------------------------------------------------------- Cypher 執行器
# 一律印出實際送出的 Cypher。實驗若不能重現，數字就不算數。
cy() {
  local q="$1" quiet="${2:-}"
  [ "$quiet" = quiet ] || { printf '  --- Cypher ---\n'; printf '%s\n' "$q" | ind; }
  if command -v cypher-shell >/dev/null 2>&1; then
    cypher-shell -a "$NEO4J_BOLT" -u "${NEO4J_USER:-neo4j}" -p "${NEO4J_PASSWORD:-}" \
      --format plain "$q" 2>&1
  elif python3 -c 'import neo4j' 2>/dev/null; then
    Q="$q" python3 - <<'PY' 2>&1
import os
from neo4j import GraphDatabase
d = GraphDatabase.driver(os.environ.get("NEO4J_BOLT","bolt://127.0.0.1:7687"),
                         auth=(os.environ.get("NEO4J_USER","neo4j"),
                               os.environ.get("NEO4J_PASSWORD","")))
with d.session() as s:
    for r in s.run(os.environ["Q"]):
        print(", ".join(f"{k}={v}" for k, v in r.items()))
d.close()
PY
  else
    echo "ERR: 找不到 cypher-shell，也沒有 python3 neo4j 套件"
    return 1
  fi
}
export NEO4J_BOLT

# 「現存」的定義：關係未到期 + 作品未軟刪除。三個條件用同一個片語，
# 保證 ground truth 與欄位重算用的是同一把尺。
LIVE_WHERE="r.$P_REL_EXPIRE IS NULL
      AND w.$P_WORK_DELETED IS NULL
      AND coalesce(w.$P_WORK_SOFT, false) = false"

# ---------------------------------------------------------------- 0. discover
cmd_discover() {
  echo "ab-experiment.sh discover — $(date -Is)  host=$(hostname)"
  h "0a. 服務是否在跑"
  kv "Neo4j bolt"  "$NEO4J_BOLT"
  kv "Neo4j HTTP"  "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$NEO4J_HTTP" || echo 連不上)"
  kv "RAG health"  "$(curl -s --max-time 5 "$RAG_URL/health" | head -c 200 || echo 連不上)"
  echo "  -- 目前監聽位址（0.0.0.0 / :: / 127.0.0.1 是本實驗的關鍵差異） --"
  ss -tlnp 2>/dev/null | awk 'NR==1 || /:(7474|7687)\>/' | ind || warn "無 ss 指令"

  h "0b. Neo4j 設定檔目前的三行"
  if [ -r "$NEO4J_CONF" ]; then
    kv "設定檔" "$NEO4J_CONF"
    grep -nE '^\s*(server\.default_listen_address|server\.bolt\.listen_address|server\.http\.listen_address|server\.jvm\.additional)' \
      "$NEO4J_CONF" | ind || echo "    (三項皆未設定 → 用 Neo4j 內建預設)"
    ls -1 "$(dirname "$NEO4J_CONF")"/neo4j.conf.bak-* 2>/dev/null | ind \
      || echo "    (無備份檔。binding 子命令會自動建立)"
  else
    bad "讀不到 $NEO4J_CONF —— 原生安裝的設定檔在安裝目錄下，請設 NEO4J_CONF=..."
  fi

  h "0c. schema 對不對（屬性名猜錯，後面的準確率就是假的）"
  echo "  -- 實際存在的標籤 / 關係 / 屬性 --"
  cy "CALL db.labels() YIELD label RETURN collect(label) AS labels" quiet | ind
  cy "CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) AS rels" quiet | ind
  cy "CALL db.propertyKeys() YIELD propertyKey RETURN collect(propertyKey) AS keys" quiet | ind
  echo "  -- 本腳本假設的名稱（請逐項對照上面三行） --"
  for p in "L_ARTIST=$L_ARTIST" "L_WORK=$L_WORK" "REL=$REL" \
           "P_REL_EXPIRE=$P_REL_EXPIRE" "P_WORK_DELETED=$P_WORK_DELETED" \
           "P_WORK_SOFT=$P_WORK_SOFT" "P_WORK_SOURCE=$P_WORK_SOURCE" "P_ARTIST_NAME=$P_ARTIST_NAME"; do
    kv "${p%%=*}" "${p#*=}"
  done
  warn "對不上就用環境變數覆寫再跑，例如 P_REL_EXPIRE=valid_to bash scripts/ab-experiment.sh accuracy"
  warn "特別注意：Cypher 對不存在的屬性回傳 null，不報錯。名字打錯時「未到期」條件會變成恆真，"
  warn "          數字照樣印出來，但軟刪除的作品會被算進去——這是本實驗最可能的無聲誤差來源。"

  h "0e. 誰在讀 Artist.source / Artist.sources（決定 E1 的收益是現在還是未來）"
  echo "  在執行期目錄下 grep。清單為空 = 目前沒有消費端 = 端到端測不出 E1 的差異。"
  grep -rn --include='*.py' --include='*.js' --include='*.ts' --include='*.cypher' \
    -E '\ba\.sources?\b|\bartist\.sources?\b|Artist\.sources?' . 2>/dev/null \
    | grep -vE 'node_modules|/\.git/|venv' | head -20 | ind \
    || echo "    (沒有任何程式碼讀這兩個欄位)"

  h "0d. 受測對象是否存在"
  cy "MATCH (a:$L_ARTIST) WHERE a.$P_ARTIST_NAME CONTAINS 'Gogh'
      RETURN a.$P_ARTIST_NAME AS name, a.source AS old_source, a.sources AS new_sources" | ind
}

# ---------------------------------------------------------------- 1. accuracy
cmd_accuracy() {
  echo "ab-experiment.sh accuracy — $(date -Is)"
  echo "自變項：Artist.source（甲，單值） vs Artist.sources（乙，推導清單）"
  echo "基準：由圖即時推導的來源集合（關係未到期 + 作品未軟刪除）"

  h "1a. 同一題的受測對象：$SUBJECT"
  cy "MATCH (a:$L_ARTIST {$P_ARTIST_NAME: '$SUBJECT'})-[r:$REL]->(w:$L_WORK)
      WHERE $LIVE_WHERE
      WITH a, collect(DISTINCT w.$P_WORK_SOURCE) AS truth
      RETURN a.source                       AS 甲_單值,
             coalesce(a.sources, [])        AS 乙_清單,
             apoc.coll.sort(truth)          AS 基準_即時推導" | ind
  echo "  （無 APOC 時改用下面這句）"
  cy "MATCH (a:$L_ARTIST {$P_ARTIST_NAME: '$SUBJECT'})-[r:$REL]->(w:$L_WORK)
      WHERE $LIVE_WHERE
      WITH a, collect(DISTINCT w.$P_WORK_SOURCE) AS truth
      RETURN a.source AS 甲_單值, coalesce(a.sources, []) AS 乙_清單,
             truth AS 基準_即時推導, size(truth) AS 基準來源數" | ind

  h "1b. 全體準確率（N=1 算不出準確率，所以母體一起算）"
  echo "  micro-P = 命中數/預測數，micro-R = 命中數/基準數，F1 = 2PR/(P+R)"
  local out
  out=$(cy "MATCH (a:$L_ARTIST)-[r:$REL]->(w:$L_WORK)
      WHERE $LIVE_WHERE AND w.$P_WORK_SOURCE IS NOT NULL
      WITH a, collect(DISTINCT w.$P_WORK_SOURCE) AS truth
      WITH truth,
           CASE WHEN a.source IS NULL THEN [] ELSE [a.source] END AS predA,
           coalesce(a.sources, []) AS predB
      RETURN count(*) AS artists,
             sum(size(truth))  AS truth_n,
             sum(size(predA))  AS predA_n,
             sum(size(predB))  AS predB_n,
             sum(size([s IN predA WHERE s IN truth])) AS tpA,
             sum(size([s IN predB WHERE s IN truth])) AS tpB,
             sum(CASE WHEN size(predA)=0 THEN 1 ELSE 0 END) AS emptyA,
             sum(CASE WHEN size(predB)=0 THEN 1 ELSE 0 END) AS emptyB,
             sum(CASE WHEN size(predA)>0 AND NOT predA[0] IN truth THEN 1 ELSE 0 END) AS staleA,
             sum(CASE WHEN size(truth)>1 THEN 1 ELSE 0 END) AS multi")
  printf '%s\n' "$out" | ind
  printf '%s\n' "$out" | python3 -c '
import sys, re
# cypher-shell --format plain 是「表頭列 + 數值列」，python driver 後援是「k=v」。兩種都吃。
txt = sys.stdin.read()
v = {}
for line in txt.splitlines():
    if "=" in line and not line.strip().startswith("+"):
        for m in re.finditer(r"([A-Za-z_]+)\s*=\s*([0-9]+)", line):
            v[m.group(1)] = int(m.group(2))
if not v:
    rows = [l for l in txt.splitlines() if l.strip()]
    for i in range(len(rows) - 1):
        keys = [k.strip().strip(chr(34)) for k in rows[i].split(",")]
        vals = [x.strip().strip(chr(34)) for x in rows[i+1].split(",")]
        if len(keys) == len(vals) and all(x.lstrip("-").isdigit() for x in vals) and "truth_n" in keys:
            v = dict(zip(keys, map(int, vals)))
            break
if "truth_n" not in v:
    print("    (解析不到欄位，請依上表自行計算 micro-P/R/F1)"); sys.exit()
def prf(tp, pn):
    p = tp / pn if pn else 0.0
    r = tp / v["truth_n"] if v["truth_n"] else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f
pa, ra, fa = prf(v["tpA"], v["predA_n"])
pb, rb, fb = prf(v["tpB"], v["predB_n"])
print()
print("    %-12s %-9s %-9s %-9s %-8s %s" % ("方法", "micro-P", "micro-R", "F1", "空值數", "首值已過時"))
print("    %-12s %-9.4f %-9.4f %-9.4f %-8d %d" % ("甲 source", pa, ra, fa, v["emptyA"], v["staleA"]))
print("    %-12s %-9.4f %-9.4f %-9.4f %-8d %s" % ("乙 sources", pb, rb, fb, v["emptyB"], "n/a（非單值）"))
print()
print("    母體 %d 位藝術家，基準來源總數 %d，其中 %d 位有多重來源。" % (v["artists"], v["truth_n"], v["multi"]))
print("    甲的召回上限 = 1/每人來源數，多重來源者必然漏。這是表示法的天花板，不是資料品質問題，")
print("    所以補跑一次舊資料也救不回來——這一格是「方法可行性」的結論，不是「準確率高低」而已。")
'

  h "1c. 乙的反向檢查：作品全被軟刪除的人，sources 應為空"
  cy "MATCH (a:$L_ARTIST) WHERE size(coalesce(a.sources, [])) > 0
      AND NOT EXISTS {
        MATCH (a)-[r:$REL]->(w:$L_WORK) WHERE $LIVE_WHERE
      }
      RETURN count(a) AS 應為空卻有值" | ind
  echo "    ↑ 非 0 表示重算沒有涵蓋「作品下架」這條路徑，乙的自我維護宣稱不成立。"

  h "1d. 打破循環論證：基準本身對不對"
  echo "  乙的定義就是「由作品層 source 推導」，拿同一條規則當基準，乙必然滿分。"
  echo "  所以這一格另外驗「作品層 source 有沒有寫對」——它由匯入路徑寫入，與藝術家層無關。"
  cy "MATCH (a:$L_ARTIST {$P_ARTIST_NAME: '$SUBJECT'})-[r:$REL]->(w:$L_WORK)
      WHERE $LIVE_WHERE
      RETURN w.$P_WORK_SOURCE AS source,
             coalesce(w.url, w.source_url, w.id, elementId(w)) AS 可查證欄位
      LIMIT 20" | ind
  echo "    請人工比對：source 欄位是否與 URL／識別碼的來源相符。"
  echo "    這 20 筆對得上，上面的準確率才有意義；對不上，先修匯入路徑再談比較。"

  h "1e. 端到端：同一題問 $K_TRIALS 次"
  local path; path=$(rag_path) || { bad "找不到可用的 RAG 查詢端點，端到端這段跳過"; return 1; }
  kv "端點" "$RAG_URL$path"
  kv "題目" "$QUESTION"
  local i ans
  for i in $(seq 1 "$K_TRIALS"); do
    ans=$(rag_ask "$path" "$QUESTION")
    printf '  [第 %d 次] %s\n' "$i" "$(printf '%s' "$ans" | tr '\n' ' ' | head -c 400)"
    score_answer "$ans"
  done
  warn "自動評分只做關鍵字命中，是粗評。判定「答案正確」以人工複核為準，"
  warn "但「出現過時來源」這一格是硬指標：命中即為錯答，不需人工判斷。"
}

# RAG 端點試探：不寫死路徑，逐個試，並印出試了什麼。
rag_path() {
  local p
  if [ -n "$RAG_QUERY_PATH" ]; then printf '%s' "$RAG_QUERY_PATH"; return 0; fi
  for p in /query /api/query /ask /api/ask /api/v1/query /chat; do
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -X POST \
      -H 'Content-Type: application/json' -d '{"question":"ping"}' "$RAG_URL$p")
    printf '  試 %-16s → HTTP %s\n' "$p" "$code" >&2
    case "$code" in 200|201) printf '%s' "$p"; return 0;; esac
  done
  return 1
}

rag_ask() {
  local path="$1" q="$2" body
  body=$(printf '{"question":%s}' "$(printf '%s' "$q" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))')")
  curl -s --max-time 120 -X POST -H 'Content-Type: application/json' -d "$body" "$RAG_URL$path" \
    | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin)
except Exception:
    sys.exit(0)
for k in ("answer","response","result","text","content","output"):
    if isinstance(d,dict) and k in d: print(d[k] if isinstance(d[k],str) else json.dumps(d[k],ensure_ascii=False)); break
else: print(json.dumps(d,ensure_ascii=False))'
}

# 評分：真實來源逐一比對 + 過時來源是否出現。
score_answer() {
  local ans="$1" truth hit=0 miss=0 s
  truth=$(cy "MATCH (a:$L_ARTIST {$P_ARTIST_NAME: '$SUBJECT'})-[r:$REL]->(w:$L_WORK)
              WHERE $LIVE_WHERE
              RETURN DISTINCT w.$P_WORK_SOURCE AS s" quiet \
          | sed 's/^s=//' | grep -v '^s$' | tr -d '"' | grep -v '^$')
  for s in $truth; do
    if printf '%s' "$ans" | grep -qi -- "${s%%_*}"; then hit=$((hit+1)); else miss=$((miss+1)); fi
  done
  if printf '%s' "$ans" | grep -qi -- "$STALE_TOKEN"; then
    bad "含過時來源關鍵字「$STALE_TOKEN」→ 本次判錯（命中 $hit／漏 $miss）"
  else
    ok "命中 $hit／漏 $miss，未出現過時來源"
  fi
}

# ---------------------------------------------------------------- 2. probe
cmd_probe() {
  echo "ab-experiment.sh probe — $(date -Is)"
  echo "測目前生效的綁定方式。切換綁定請用 binding 子命令，再回來跑這支。"

  h "2a. 實際監聽位址"
  ss -tlnp 2>/dev/null | awk 'NR==1 || /:(7474|7687)\>/' | ind
  echo "    判讀：出現 0.0.0.0 → 甲；127.0.0.1 → 乙；:::7474 或 [::] → Java 雙堆疊（WSL 轉發器不吃）"
  echo "  -- socket 家族（這是整個假說的關鍵證據） --"
  for port in 7474 7687; do
    pid=$(ss -tlnp 2>/dev/null | awk -v P=":$port\\>" '$4 ~ P {match($0,/pid=[0-9]+/); if(RSTART) print substr($0,RSTART+4,RLENGTH-4); exit}')
    if [ -n "${pid:-}" ]; then
      fam=$(ss -tlnpH "sport = :$port" 2>/dev/null | awk '{print $1, $4}')
      kv "$port" "${fam:-未知}  pid=$pid"
    else
      kv "$port" "(未被監聽)"
    fi
  done
  echo "    tcp + 0.0.0.0/127.0.0.1 = 純 IPv4 socket（WSL 轉發器認得）"
  echo "    tcp + [::]/[::ffff:127.0.0.1] = Java 雙堆疊 socket（轉發器不認得，就是原本連不上的成因）"

  h "2a-2. WSL 網路模式（共變項：mirrored 模式下 localhost 語意完全不同）"
  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -NonInteractive -Command \
      "if (Test-Path \"$env:USERPROFILE\\.wslconfig\") { Get-Content \"$env:USERPROFILE\\.wslconfig\" } else { '(無 .wslconfig → NAT 模式，預設值)' }" \
      2>/dev/null | tr -d '\r' | ind
    echo "    networkingMode=mirrored 時 localhost 直接共用，本實驗的兩法可能都會通，"
    echo "    結論就不能外推到 NAT 模式的機器。請把這格記進結果表。"
  fi

  h "2b. WSL 內部 $N_CONN 次"
  trials "WSL-HTTP"  "curl -s -o /dev/null --max-time 5 $NEO4J_HTTP"
  trials "WSL-Bolt"  "cy_ping"

  h "2c. Windows 側 $N_CONN 次（真正要驗的是這一段）"
  if command -v powershell.exe >/dev/null 2>&1; then
    local okc=0 i
    for i in $(seq 1 "$N_CONN"); do
      powershell.exe -NoProfile -NonInteractive -Command \
        "try{ (Invoke-WebRequest -Uri 'http://localhost:7474' -TimeoutSec 5 -UseBasicParsing).StatusCode }catch{ 0 }" \
        2>/dev/null | tr -d '\r' | grep -q '^200$' && okc=$((okc+1))
    done
    kv "Win localhost:7474 → 200" "$okc/$N_CONN"
    okc=0
    for i in $(seq 1 "$N_CONN"); do
      powershell.exe -NoProfile -NonInteractive -Command \
        "(Test-NetConnection -ComputerName localhost -Port 7687 -WarningAction SilentlyContinue).TcpTestSucceeded" \
        2>/dev/null | tr -d '\r' | grep -qi '^true$' && okc=$((okc+1))
    done
    kv "Win localhost:7687 TCP" "$okc/$N_CONN"
    warn "TCP 連得上 ≠ Bolt 可用。前次結論只測到這一格就停了，下面 2d 才是真的驗證。"
  else
    warn "找不到 powershell.exe，Windows 側跳過"
  fi

  h "2d. Windows 側真正的 Bolt 交握（補上前次沒做的那一步）"
  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -NonInteractive -Command \
      "try{ \$r = Invoke-WebRequest -Uri 'http://localhost:7474/db/neo4j/tx/commit' -Method POST -TimeoutSec 10 -UseBasicParsing \
         -Headers @{ 'Content-Type'='application/json'; 'Authorization'='Basic ' + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('${NEO4J_USER:-neo4j}:${NEO4J_PASSWORD:-}')) } \
         -Body '{\"statements\":[{\"statement\":\"RETURN 1 AS ok\"}]}'; \$r.Content }catch{ 'FAILED: ' + \$_.Exception.Message }" \
      2>/dev/null | tr -d '\r' | head -c 400 | ind
    echo
    echo "    ↑ 回 {\"results\":[...\"ok\"...]} 才算「Windows 端真的能用 Neo4j」。"
    echo "      這條走 HTTP API 而非 Bolt 協定，但同樣需要認證成功，足以取代人工開 Browser 登入。"
  fi

  h "2e. 暴露面（甲乙兩法的實質差別在這裡，不在能不能通）"
  local wslip; wslip=$(hostname -I 2>/dev/null | awk '{print $1}')
  kv "WSL IP" "${wslip:-未知}"
  if [ -n "$wslip" ]; then
    curl -s -o /dev/null -w '  非 loopback 介面 %{http_code}\n' --max-time 5 "http://$wslip:7474" \
      || echo "  非 loopback 介面：連不上"
    echo "    200 = 綁 0.0.0.0，同網段任何主機只要路由到得了就能連（Neo4j 預設只有密碼保護，無 TLS）"
    echo "    連不上 = 綁 127.0.0.1，攻擊面僅限本機"
  fi

  h "2f. RAG 後端是否受影響（同一題的前置條件）"
  kv "RAG health" "$(curl -s --max-time 5 "$RAG_URL/health" | head -c 200 || echo 連不上)"
}

cy_ping() { cy "RETURN 1 AS ok" quiet | grep -q 'ok' ; }

trials() {
  local name="$1" cmd="$2" okc=0 i t0 t1
  t0=$(date +%s%N)
  for i in $(seq 1 "$N_CONN"); do eval "$cmd" >/dev/null 2>&1 && okc=$((okc+1)); done
  t1=$(date +%s%N)
  kv "$name" "$okc/$N_CONN  平均 $(( (t1-t0)/1000000/N_CONN )) ms"
}

# ---------------------------------------------------------------- 3. binding（唯一會改現場的子命令）
cmd_binding() {
  local method="${1:-}"
  case "$method" in A|B|C) ;; *) bad "用法：binding --method A|B|C"; return 2;; esac
  [ -w "$NEO4J_CONF" ] || { bad "$NEO4J_CONF 不可寫，請用 sudo，或設 NEO4J_CONF 指到原生安裝的設定檔"; return 1; }

  local bak="$NEO4J_CONF.bak-ab-$(date +%F-%H%M%S)"
  cp -p "$NEO4J_CONF" "$bak" || { bad "備份失敗，中止"; return 1; }
  ok "已備份 → $bak"

  # 先清掉本腳本管轄的三行，再依方法寫回。不用 sed 就地改，避免多次執行疊加。
  grep -vE '^\s*(server\.default_listen_address|server\.bolt\.listen_address|server\.http\.listen_address)\s*=' "$bak" \
    | grep -vE '^\s*server\.jvm\.additional\s*=\s*-Djava\.net\.preferIPv4Stack=true\s*$' > "$NEO4J_CONF"

  {
    echo ""
    echo "# --- ab-experiment.sh 方法 $method（$(date -Is)）；還原：$bak ---"
    case "$method" in
      A) echo "server.default_listen_address=0.0.0.0"
         echo "server.jvm.additional=-Djava.net.preferIPv4Stack=true" ;;
      B) echo "server.default_listen_address=127.0.0.1"
         echo "server.bolt.listen_address=127.0.0.1:7687"
         echo "server.http.listen_address=127.0.0.1:7474"
         echo "server.jvm.additional=-Djava.net.preferIPv4Stack=true" ;;
      C) echo "server.default_listen_address=0.0.0.0" ;;   # 機制對照：不加 preferIPv4Stack
    esac
  } >> "$NEO4J_CONF"

  echo "  -- 寫入後的三行 --"
  grep -nE '^\s*server\.(default_listen_address|bolt\.listen_address|http\.listen_address|jvm\.additional)' "$NEO4J_CONF" | ind

  warn "Neo4j 需重啟才生效。本腳本不替你決定用哪種方式重啟——"
  warn "這台機器上系統實例走 systemd、專案實例走 Start-NativeServices.ps1 的 neo4j console，"
  warn "弄錯會再製造一次 B1 的雙實例互搶。請自行重啟正確的那一個，然後："
  echo "    bash scripts/ab-experiment.sh probe | tee ~/probe-$method.txt"
  echo "  還原：bash scripts/ab-experiment.sh restore"
}

cmd_restore() {
  local latest
  latest=$(ls -1t "$(dirname "$NEO4J_CONF")"/neo4j.conf.bak-* 2>/dev/null | head -1)
  [ -n "$latest" ] || { bad "找不到備份檔"; return 1; }
  kv "將還原自" "$latest"
  cp -p "$latest" "$NEO4J_CONF" && ok "已還原，記得重啟 Neo4j" || bad "還原失敗"
}

# ---------------------------------------------------------------- 分派
case "${1:-}" in
  discover) cmd_discover ;;
  accuracy) cmd_accuracy ;;
  probe)    cmd_probe ;;
  binding)  shift; [ "${1:-}" = --method ] && shift; cmd_binding "${1:-}" ;;
  restore)  cmd_restore ;;
  *) sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
