# 埠號整併：Neo4j 改用標準埠、Ollama 歸現行實例（2026-09-20）

> 決定者：使用者（2026-09-20）
> 範圍：Neo4j `7688/7475` → `7687/7474`；Ollama `11434` 歸目前已在監聽的實例
> 程式碼修改**已完成並推入 `main`**；機器端操作**須由使用者執行**（見 §3）

---

## 1. 決定內容與理由

| 項目 | 變更前 | 變更後 | 理由 |
|---|---|---|---|
| Neo4j（bolt） | 7688 | **7687** | 消滅雙實例。原本用替代埠，是為了閃避 WSL 系統自帶的 `neo4j.service`；改為停用該系統服務，標準埠歸本專案 |
| Neo4j（HTTP） | 7475 | **7474** | 同上 |
| Ollama | 11434（三方互搶，crash-loop） | **11434，單一實例** | 停用 `Ubuntu-22.04` 的 `ollama.service`，由目前已在監聽 11434 的實例提供服務 |

### 關於「Neo4j 改為 7474」的釐清

7474 是 Neo4j 的 **HTTP** 埠，bolt 是 **7687**，兩者是一組而非二選一。
本次照「改用標準埠」執行：**bolt 7687 + HTTP 7474**，把 `7688/7475` 這組替代埠整個廢除。
若原意不同請提出，程式碼可回退（見 §5）。

### 為什麼停用系統的 `neo4j.service` 是對的

這是調查報告「發現3」的成因。機器上有兩個 Neo4j：

| 實例 | 埠 | 誰啟動 | 用途 |
|---|---|---|---|
| WSL 系統的 `neo4j.service` | 7687 / 7474 | systemd | **與本專案無關** |
| 專案原生實例 | 7688 / 7475 | `Start-NativeServices.ps1` 的 `neo4j console` | 本專案使用 |

系統那個持續啟動失敗、產生 crash-loop（報告中的 `Neo4j is already running (pid:492)`）。
既然專案不用它，停用它即可一併解決埠衝突與重啟迴圈。

---

## 2. 已完成的程式碼修改（10 個檔案）

| 檔案 | 修改內容 |
|---|---|
| `langchain-rag/unified_rag_manager_v2.py` | `NEO4J_URI` 預設值 7688 → 7687；註解重寫 |
| `langchain-rag/sync_europeana_to_databases.py` | 同上 |
| `langchain-rag/import_all_museums_to_neo4j.py` | 同上 |
| `langchain-rag/classify_art_history_graph.py` | 同上 |
| `scripts/Start-NativeServices.ps1` | `Test-Port 7475` → `7474`（3 處）；啟動 rag-manager 傳入的 `NEO4J_URI` → 7687；檔頭註解重寫 |
| `scripts/daily_crawl_and_sync.sh` | `export NEO4J_URI` → 7687 |
| `scripts/diagnose.py` | 健康檢查目標 `("Neo4j (7688)", …, 7688)` → 7687 |
| `scripts/error_knowledge_base.json` | 診斷說明與建議連線字串更新；錯誤比對樣式改為 `768[78]` 以同時匹配新舊 |
| `scripts/doctor.sh`（**已於 2026-09-22 停用刪除**，能力併入 `scripts/verify-nightly.sh`）/ `scripts/collect.sh` | `NEO4J_URI` 提示文字更新；埠號表保留 7688/7475 以**偵測舊實例是否沒停乾淨** |

### 順帶修掉的兩個同類 bug

查 11434 時發現兩處仍在用 **Docker 的 DNS 名稱**。Docker 已於 2026-07-28 移除，原生環境解析不到：

| 檔案 | 變更前 | 變更後 |
|---|---|---|
| `.env.example:25` | `OLLAMA_BASE_URL=http://host.docker.internal:11434` | `http://127.0.0.1:11434` |
| `openwebui-config/functions.py:12` | `self.ollama_api_url = "http://host.docker.internal:11434"` | `http://127.0.0.1:11434` |

這與 `cuda-ml-service:8080`（`docs/ports.md` §4）是同一類：**Docker 遺留的主機名**。

### 驗證

- 全部 10 個檔案通過語法檢查（`python3 -m py_compile` / `bash -n` / `json.load`）
- 除刻意保留的歷史註解外，程式碼中已無 `7688` / `7475` 的**作用中引用**

---

## 3. 機器端操作（須由使用者執行）

> 順序不可顛倒。先釋放埠，再改設定，最後啟動。

### 3.1 Neo4j

**步驟一：停用前先確認系統實例沒有要保留的資料**

```bash
# 若這個指令能連上且有資料，先想清楚要不要保留再往下
cypher-shell -a bolt://127.0.0.1:7687 -u neo4j \
  "MATCH (n) RETURN count(n) AS 節點數;"
```

**步驟二：停用系統的 neo4j.service，釋放 7687/7474**

```bash
sudo systemctl disable --now neo4j
ss -tlnp | grep -E '7687|7474' || echo "✅ 7687/7474 已釋放"
```

**步驟三：若仍被佔用，刪除佔位程序**

```bash
sudo fuser -k 7687/tcp 7474/tcp        # 砍掉佔用者
pkill -f neo4j-community               # 專案的原生實例也一併停掉（等下會重啟）
sleep 3
ss -tlnp | grep -E '7687|7474' || echo "✅ 已釋放"
```

**步驟四：把專案 Neo4j 的設定改回標準埠**

```bash
CONF=/home/user/neo4j-community-2026.06.0/conf/neo4j.conf
grep -nE 'listen_address|advertised_address' "$CONF"     # 先看目前設定
cp "$CONF" "$CONF.bak-2026-09-20"                        # 備份，供回退
```

把其中的 7688 / 7475 改回標準值（Neo4j 5.x／2026.x 的設定名）：

```
server.bolt.listen_address=:7687
server.http.listen_address=:7474
```

若檔案裡是舊版設定名（`dbms.connector.bolt.listen_address`），比照修改。

**步驟五：更新 `.env`**

```bash
# .env 在 C:\Users\user\Desktop\藝術史資料庫\art-history-database\.env
grep -n 'NEO4J_URI' "/mnt/c/Users/user/Desktop/藝術史資料庫/art-history-database/.env"
# 若有 NEO4J_URI 且值為 7688，改成：
# NEO4J_URI=bolt://127.0.0.1:7687
```

### 3.2 Ollama

```bash
# 停用 Ubuntu-22.04 自己的 ollama.service，不再參與搶埠
sudo systemctl disable --now ollama
systemctl is-active ollama       # 應為 inactive
```

**驗證目前那個實例是否堪用——這一步不能跳過：**

```bash
curl -s http://127.0.0.1:11434/api/tags | head -c 500
```

| 結果 | 意義 | 動作 |
|---|---|---|
| 回傳模型清單，且含本專案用的模型 | 完成 | 無 |
| 回傳空清單 `{"models":[]}` | 佔埠的那個實例**沒有模型** | 要在那個實例上 `ollama pull`。先跑 `collect.sh` 查出它是誰 |
| 連不上 | 佔埠的不是 Ollama，或已死 | 跑 `collect.sh` 查 PID 47888 的身分 |

> **這是本次唯一還可能出岔的地方。** 「把 11434 給現行實例」在網路層一定成立，
> 但若那個實例裡沒有專案需要的模型，生成請求仍會失敗。務必驗證模型清單。

### 3.3 重新啟動並驗收

```powershell
# Windows PowerShell
& "C:\Users\user\Desktop\藝術史資料庫\art-history-database\scripts\Start-NativeServices.ps1"
```

```bash
# WSL 驗收
ss -tlnp | grep -E '7687|7474|8000|8007|8080|11434'
python3 scripts/diagnose.py
bash scripts/verify-nightly.sh   # 原為 doctor.sh，2026-09-22 起改用此支
```

**驗收條件（五項全中才算完成）：**

| # | 條件 | 檢查方式 |
|---|---|---|
| 1 | 7687／7474 上是**專案的** Neo4j | `cypher-shell -a bolt://127.0.0.1:7687` 能連上且資料正確 |
| 2 | **7688／7475 沒有任何服務** | `ss -tlnp \| grep -E '7688\|7475'` 無輸出 |
| 3 | `neo4j.service` 已停用且不再 crash-loop | `systemctl is-enabled neo4j` 為 `disabled` |
| 4 | `ollama.service` 已停用 | `systemctl is-active ollama` 為 `inactive` |
| 5 | 11434 回傳含專案模型的清單 | `curl -s http://127.0.0.1:11434/api/tags` |

---

## 4. 本次未處理（仍列在問題登錄表）

| # | 項目 | 原因 |
|---|---|---|
| B3 | Elasticsearch 每 30 秒重啟 | 與本次埠號整併無關，ES 不在 `Start-NativeServices.ps1` 管理範圍內 |
| C1 | ml-service 與 OpenWebUI 搶 8080 | 獨立變更，8 處引用點，見 `ports.md` §3 |
| A4 | 執行期目錄與正本脫鉤 | **本次程式碼修改推入 `main`，但實際執行的是桌面那份目錄。<br>A4 未解決前，本次修改不會自動生效於實際系統** |

> ⚠ **A4 直接影響本次變更能否生效。**
> 機器端操作（§3）的步驟四、五改的是執行期目錄裡的設定檔，會立即生效；
> 但 §2 那 10 個檔案的程式碼修改在 `main` 上，**執行期目錄不會自動拿到**。
> 在 A4 解決前，需要手動把這 10 個檔案複製到
> `C:\Users\user\Desktop\藝術史資料庫\art-history-database\` 對應位置，
> 或等 A4 完成（執行期目錄改為正本的 git checkout）後一次生效。

---

## 5. 回退方式

```bash
# 程式碼：本次修改是單一 commit，revert 即可
git revert <本次 commit>

# Neo4j 設定：步驟四已備份
cp /home/user/neo4j-community-2026.06.0/conf/neo4j.conf.bak-2026-09-20 \
   /home/user/neo4j-community-2026.06.0/conf/neo4j.conf

# 服務：重新啟用
sudo systemctl enable --now neo4j
sudo systemctl enable --now ollama
```
