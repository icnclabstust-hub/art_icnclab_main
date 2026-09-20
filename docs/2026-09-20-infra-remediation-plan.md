# 現況問題解決計畫（對應 2026-09-20 調查報告）

> 性質：行動計畫。對應輸入文件 `71c939ad-2026-09-20-infra-findings-report.md`（調查報告）。
> 本文件只規劃與提供指令，**不代替執行任何會改動現場的動作**——現場在 WSL 機器上，本 session 無法觸及。

## 0. 先修正調查報告的一個關鍵錯誤

報告發現1研判「`D:\art_icnclab` 高度疑似真正的開發用 git repo」。**此研判已被證偽。**

證據（本次於 `icnclabstust-hub/art_icnclab` 實際 clone 查證）：

```
HEAD = 9c4aebd  2026-08-18  docs: 轉為歷史存檔，開發移至 metaversestust-pms/art_icnclab
README.md 首行：📦 本 repo 已轉為歷史存檔（2026-08-18）
                後續開發一律在 metaversestust-pms/art_icnclab（全新歷史的精整版）
```

報告記錄 `D:\art_icnclab` 的 HEAD 是 `979745c` (2026-08-17)，**比上述搬家公告早一個 commit**。
結論：`D:\art_icnclab` 是「存檔 repo 的過期 clone」，它停在公告之前，所以本機看不到自己已被封存。

因此副本數量應由「3 份」修正為「至少 6 處」：

| # | 位置 | 真實身分 | 處置方向 |
|---|---|---|---|
| 1 | `D:\art_icnclab-main\art_icnclab-main` | ZIP 快照，無 `.git`，今天所有產出在此 | 萃取獨有變更後封存 |
| 2 | `D:\art_icnclab` | `icnclabstust-hub/art_icnclab` 的過期 clone | 萃取獨有變更後封存 |
| 3 | `C:\Users\user\Desktop\藝術史資料庫`、`D:\藝術史資料庫` | 疑為執行期工作目錄 | 待確認；資料目錄須另行保全 |
| 4 | `icnclabstust-hub/art_icnclab`（GitHub，公開） | **2026-08-18 已自行宣告封存**；`db_backups/`（Git LFS）還原資料仍須由此取得 | 保留為唯讀存檔 |
| 5 | `metaversestust-pms/art_icnclab`（GitHub） | 公告指定之現行開發 repo | **種子候選**，見 `2026-09-20-phase1-seed-canon.md` STEP 0 |
| 6 | `icnclabstust-hub/art_icnclab_main`（GitHub，私有） | 2026-09-20 建立 | **✅ 已確定為正本**（使用者決定，2026-09-20）。但目前為空，須先種 |

補充（安全面，報告未涵蓋）：第 4 項是**公開 repo**。已驗證其 HEAD 檔案樹未追蹤任何 `.env`
（`.gitignore` 第 7–14、114 行已排除 `.env*` 與 `.webui_secret_key`，僅追蹤 `.env.example`）。
但**歷史提交未查**，不能據此宣稱從未外洩。見 §1.4。

## 1. 解題邏輯

報告列了 5 項發現，但它們不是 5 個獨立問題。拆解後只有 **一個根因** 與 **兩個病灶類別**：

- **根因**：整個專案沒有任何一處是「唯一真相源」。程式碼沒有（發現1）、執行期設定沒有（發現2、5）、服務歸屬也沒有（發現3、4）。
- **病灶A｜身分不明**：不知道哪份檔案／哪個服務實例才算數 → 發現1、2、5。
- **病灶B｜歸屬不明**：不知道某個程序是誰啟動的、由誰負責 → 發現3、4。

解題原則（這是整份計畫的可行性關鍵）：

> **不要去「合併」或「比對」所有副本。**
> n 份副本兩兩比對是 O(n²)、耗時且極易誤判。
> 改成：**指定一份正本，其餘每一份只需機械化證明「可被正本涵蓋」或「有獨有內容」**，
> 是 O(n)，而且每一步都是可重現的指令輸出，不需要人為判斷。

### 1.1 Phase 0：止血（約 10 分鐘，零風險）

在正本確立之前，**停止對任何一份副本做新的修改**。每多編輯一小時，合併債就多一小時。
特別是 `D:\art_icnclab-main\art_icnclab-main`——它沒有 `.git`，改動無法追溯。

### 1.2 Phase 1：種正本並機械化處置副本（約 40 分鐘）

> **完整指令見 `docs/2026-09-20-phase1-seed-canon.md`。** 此處只說明邏輯。

正本已確定為 `icnclabstust-hub/art_icnclab_main`（使用者決定，2026-09-20）。
但**該 repo 目前是空的**，所以 Phase 1 的問題形狀改變了：不是「比對既有正本」，
而是「先選一份種子把正本種起來，再把其餘副本的獨有內容撈回來」。

**最大風險在種子選擇，不在後續比對。** 存檔 repo 的 README（2026-08-18）指明開發已移至
`metaversestust-pms/art_icnclab`，距今整整一個月。若該處有人開發過，而我們誤用
`D:\art_icnclab`（停在 2026-08-17）當種子，那一個月的工作會被**靜默丟掉**。
所以手冊的 STEP 0（清點所有候選種子的新舊）不可跳過。

種好之後，處置其餘副本的手法如下。此法的價值在於**不需要任何人為判斷**：

```bash
cd ~/canon
git checkout -b rescue/zip-snapshot          # 每份副本開一個 rescue 分支
rsync -a --delete \
  --exclude='.git/' --exclude='node_modules/' --exclude='data/' \
  --exclude='db_backups/' --exclude='*venv*/' --exclude='.env' \
  /mnt/d/art_icnclab-main/art_icnclab-main/ ./
git status --porcelain                        # ← 這就是該副本的獨有內容，逐字為憑
```

判讀規則，只有三種結果：

| `git status --porcelain` 輸出 | 意義 | 處置 |
|---|---|---|
| 空 | 該副本內容完全被正本涵蓋 | 直接封存，零風險 |
| 只有 `D `（刪除） | 該副本是正本的子集 | 直接封存，零風險 |
| 有 `M `／`?? ` | 有獨有變更 | commit 成 rescue 分支，之後再 cherry-pick |

因為全程在分支上操作，**隨時可回退，不可能覆蓋掉別人的工作**——這正是報告
「貿然搬動有覆蓋他人工作的風險」那個顧慮的解法。

### 1.3 Phase 1 附帶產出：今天的工作何去何從

報告發現1提到的設計文件、SQL migration、`unified_rag_manager_v2.py` 稽核 log middleware 修改，
全都在 ZIP 快照裡。跑完 `rescue/zip-snapshot` 之後，它們會以 commit 的形式存在，
屆時是 cherry-pick 進正本、還是判定作廢，都是有憑據的決定，而非現在這樣「不知道存不存在」。

註：`icnclabstust-hub/art_icnclab` 存檔 repo 內**沒有 `docs/designs/` 目錄**（只有 `docs/templates/`）。
所以報告引用的兩份設計文件只存在於 ZIP 快照或正本 repo 之一，這點可在 Phase 1 一併確認。

### 1.4 Phase 1 平行項：公開 repo 的歷史稽核（可與上述並行）

```bash
cd ~/icnclabstust-hub/art_icnclab
git fetch --unshallow || git fetch --depth=1000 origin
git log --all --diff-filter=A --name-only --format='%h %ad' \
  | grep -iE '(^|/)\.env($|\.)|webui_secret_key|\.pem$|id_rsa'
```

有命中 → 該金鑰視同已外洩，**輪換（rotate）金鑰**即可，不需要改寫 git 歷史
（改寫公開 repo 歷史成本高、風險大，而且金鑰一旦公開過，改寫也救不回來）。
沒命中 → 記錄「已稽核、無命中」，結案。

## 2. Phase 2：設定與埠號的唯一真相源（約 1 小時）

發現2與發現5其實是同一類 bug：**執行期實際值**與**程式碼假設值**沒有任何一處被共同定義。

### 2.1 一個現在就能證實／推翻的具體故障

`langchain-rag/unified_rag_manager_v2.py:154`（本次於存檔 repo 查證原文）：

```python
# 原生 Neo4j（WSL 直接執行，非 Docker）；7688 是因為 WSL 環境本身有另一個系統 Neo4j 服務佔用了 7687
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7688")
```

報告已查證現場 Neo4j 實際監聽 **7687**。因此：

> **若 `.env` 未設 `NEO4J_URI`，這支程式的預設值 7688 上沒有任何服務，它連不上任何 Neo4j。**

這不只是「註解與現況不一致」的紀錄問題，是會直接故障。驗證只要一行：

```bash
grep -nE '^NEO4J_URI' <正本>/.env ; ss -tlnp | grep -E '768[78]'
```

### 2.2 死變數

`.env.example:23` 是 `RAG_API_PORT=8008`，但程式讀的是 `RAG_MANAGER_PORT`
（`unified_rag_manager_v2.py:1626`：`int(os.getenv("RAG_MANAGER_PORT", "8007"))`）。
`RAG_API_PORT` 沒有任何程式碼讀取——這正是報告「查無程式碼讀取」的原因。
修法：把 `.env.example` 的變數名改成 `RAG_MANAGER_PORT`，發現5的「三重身份混淆」就只剩兩個來源。

### 2.3 結構性修法：讓錯誤大聲失敗

目前每個設定都是 `os.getenv("X", "預設值")`。這種寫法會在設定缺漏時**安靜地用錯的值繼續跑**，
正是本次「註解說 7688、現場是 7687、沒人發現」的成因。改成必要變數缺漏即啟動失敗：

```python
def required_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"必要環境變數 {name} 未設定；請參照 .env.example")
    return v

NEO4J_URI = required_env("NEO4J_URI")
```

搭配一份 `docs/ports.md` 作為埠號的唯一宣告處，`.env.example` 作為設定的唯一宣告處。

## 3. Phase 3：服務歸屬（發現2／3／4，約 1–2 小時）

### 3.1 發現2｜Ollama 埠 11434——這題是可決定的，不是謎團

原則：**整台機器上只能有一個 Ollama**。決策樹：

1. 先確認佔用者。在 Windows PowerShell：`netstat -ano | findstr :11434`，再用 PID 查程序名。
2. 若佔用者是另一個 WSL 發行版 `Ubuntu`：`wsl --terminate Ubuntu`，然後在 Ubuntu-22.04
   `sudo systemctl restart ollama && systemctl is-active ollama`。若轉為 `active`，根因即確認。
3. 若佔用者是 Windows 主機本身：**建議保留 Windows 這一個**（它直接持有 GPU，效能最好），
   然後在 Ubuntu-22.04 `sudo systemctl disable --now ollama`，並把 `.env` 設成
   `OLLAMA_BASE_URL=http://127.0.0.1:11434`（`.wslconfig` 已開 `localhostForwarding=true`，可直接連通）。

驗收條件（兩者都要成立，缺一不可）：

```bash
curl -s http://127.0.0.1:11434/api/tags          # 要回傳模型清單
systemctl is-active ollama                        # 要是 inactive，且是 disabled，不是 crash-loop
journalctl -u ollama --since '10 min ago' | grep -c 'address already in use'   # 要是 0
```

### 3.2 發現3｜Neo4j／Elasticsearch 反覆重啟

報告已排除「本次診斷操作造成」，方向正確。以下把「成因未定」收斂成兩個可檢定的假說。

**假說A（Neo4j）**：`Neo4j is already running (pid:492)` 這句話本身就是線索——
它代表**有東西在 systemd 之外啟動了 Neo4j**（例如 `neo4j console`、某支腳本、或桌面版），
systemd 的 unit 與那個既存程序互搶。檢定：

```bash
ps -o pid,ppid,user,cmd -p 492          # PPID=1 是 systemd；非 1 就是某支腳本，cmd 會指出是誰
systemctl cat neo4j                      # 看 ExecStart 與 Restart 設定
systemctl show neo4j -p Restart -p RestartSec
crontab -l; sudo crontab -l; systemctl list-timers --all | head -20
```
再加 Windows 端：工作排程器（Task Scheduler）是否有定期觸發的項目。

**假說B（Elasticsearch）**：**每 30 秒一輪**的 Start→Stopped 高度符合 OOM 被殺或健康檢查逾時。
報告量到當下 12Gi/21Gi，看似未用罄，但 ES 預設 heap 會取實體記憶體的一半（約 10Gi），
在 Neo4j(JVM) + PostgreSQL + Redis + Ollama 同時在跑的情況下，啟動瞬間要到那麼多是會失敗的。檢定：

```bash
journalctl -u elasticsearch --since '1 hour ago' | grep -iE 'oom|killed|memory|timeout'
dmesg -T | grep -i 'out of memory'
grep -rnE '^-Xm[sx]' /etc/elasticsearch/jvm.options /etc/elasticsearch/jvm.options.d/ 2>/dev/null
```
若確認為 OOM，修法便宜且成功率高——明確釘死 heap：

```
# /etc/elasticsearch/jvm.options.d/heap.options
-Xms2g
-Xmx2g
```

報告建議「由同學直接在機器上 `journalctl -f` 觀察」是對的，但可以更省力——
請直接跑 §5 的 `scripts/doctor.sh`，它一次把上述所有檢定的輸出印出來。

### 3.3 發現4／5｜OpenWebUI 與 8080（已決定：OpenWebUI 用 8080）

使用者已決定（2026-09-20）：**OpenWebUI 保留，且必須使用 8080**。
因此 8080 歸 OpenWebUI，**ml-service 必須遷出**（`ml-service/start.sh:138` 現綁 `127.0.0.1:8080`）。
新埠建議 **8002**，完整理由與遷移清單見 `docs/ports.md`。

遷移不是改一行就好——本次以 `grep -rn '8080'` 清查出 **8 處呼叫端**
（`src/config/mlConfig.js`、`src/api/routes/mlRoutes.js`、`src/mcp/mcp_tool_registry.py` ×2、
`langchain-rag/knowledge_graph_rag.py`、`langchain-rag/integrated_rag_optimizer.py`、
`monitoring/prometheus.yml`、`system_full_diagnostic.py`）。**漏改任一處，ml-service 呼叫即失敗。**

#### 本次額外發現：與 NEO4J_URI 同類的第二個隱性故障

```javascript
// src/config/mlConfig.js:4 與 src/api/routes/mlRoutes.js:7
const ML_SERVICE_URL = process.env.ML_SERVICE_URL || 'http://cuda-ml-service:8080';
```

`cuda-ml-service` 是 **docker-compose 的服務名**。Docker 已於本次查證確認**完全移除**（發現4），
該主機名在原生環境下**無法解析**。所以只要 `.env` 未設 `ML_SERVICE_URL`，
Node 後端就連不到 ml-service。

這與 §2.1 的 `NEO4J_URI` 預設 7688 是**同一種 bug**：設定缺漏時安靜地用錯的預設值繼續跑。
兩者都適用 §2.3 的結構性修法（缺漏即啟動失敗）。判準是：
**只要一個設定值在不同環境會不同，就不該有預設值。**

#### ChromaDB

pip 套件已裝但無常駐程序，而 `unified_rag_manager_v2.py:251` 用的是
`chromadb.HttpClient(host, port=8001)`——**HttpClient 需要一個常駐 server**。
現況是「程式碼要求 server 模式、環境沒有 server」。需決定改用嵌入式模式（`PersistentClient`）
或補啟 `chroma run --port 8001` 為 systemd 服務。

### 3.4 發現4 的文件問題

2026-08-29 的 migration 設計文件狀態已失真（假設 Docker 仍在使用，實際已完全移除，
且原生化範圍超出原清單——多了 PostgreSQL 18 與 Redis）。
建議：**不要修補該文件**，把它標記為 superseded，用 Phase 1～3 的實測結果重寫一份現況文件。
修補一份前提已經不成立的文件，成本高於重寫，而且改完還是沒有簽核紀錄。

## 4. 建議執行順序（含相依性）

```
Phase 0 止血 ──→ Phase 1 確立正本 ──┬──→ Phase 2 設定真相源 ──→ Phase 3.3 服務取捨
    (10 min)        (30 min)         │         (1 hr)                  (30 min)
                                     ├──→ Phase 1.4 公開repo歷史稽核（可並行）
                                     └──→ Phase 3.1/3.2 服務歸屬（可並行，不依賴正本）
                                              (1-2 hr)
```

關鍵相依性：Phase 2 **必須**等 Phase 1，因為「要改哪一份 `.env.example`」取決於正本是哪一份。
Phase 3.1／3.2 是純環境問題，**不依賴**正本，可以立刻並行開工——
這是本計畫相對報告原順序（1→2/3→4→5 全序列）最主要的提速點。

## 5. 防止復發：`scripts/doctor.sh`

本次之所以需要一輪耗時的 AI 調查才知道現況，是因為「現況」本身沒有任何一個可查詢的來源。
`scripts/doctor.sh`（與本文件同時提交）用一道指令印出：
我是哪一份副本、git HEAD 是什麼、哪些服務在跑、哪些埠被誰佔、`.env` 實際生效值為何、
以及這些值與程式碼預設值是否一致。

每次開工前先跑它，「現況調查」就從兩小時變成十秒鐘。

## 6. 決策紀錄與待辦

### 已決定（2026-09-20）

| 項目 | 決定 | 影響 |
|---|---|---|
| 正本 | `icnclabstust-hub/art_icnclab_main` | Phase 1 改為「種正本」，見 §1.2 |
| OpenWebUI | 保留，使用 8080 | ml-service 遷至 8002，8 處呼叫端須同步改，見 §3.3 與 `ports.md` |
| 現場指令 | 由使用者於 WSL 執行後回貼輸出 | 所有現場檢定以可複製貼上的指令形式交付 |

### 待決定

| 項目 | 卡在哪 | 解法 |
|---|---|---|
| **種子選誰** | 不知道 `metaversestust-pms/art_icnclab` 是否有 2026-08-18 之後的工作 | 跑 `phase1-seed-canon.md` STEP 0，回貼輸出 |
| **Ollama 保留哪一個** | 不知道 11434 的實際佔用者是 Windows 主機還是另一個 WSL 發行版 | 跑 §3.1 的 `netstat -ano \| findstr :11434`，回貼輸出 |
| **另一個 WSL 發行版 `Ubuntu` 還需不需要** | 若不需要，發現2 可能一個 `wsl --terminate` 就解決 | 使用者判斷 |
| **ChromaDB 用 server 還是嵌入式** | 見 §3.3 | 使用者判斷 |
| **`db_backups/`（LFS）是否搬進正本** | 物件很大 | 建議不搬，正本 README 指向存檔 repo |
