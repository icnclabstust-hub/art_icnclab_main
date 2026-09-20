# 現況問題報告：專案資料夾分歧與 WSL 服務現況（2026-09-20）

> 性質：純調查／診斷報告，不含實作變更，符合 `CLAUDE.md` R2 允許輸出的「調查結果」。
> 起因：因應 RAG 架構改版設計案（`docs/designs/2026-09-20-target-architecture-consistency-eval-faithfulness.md`）的埠號規劃調查，實際打開 WSL 環境查證時，發現數個範圍更廣、且不限於本次改版的現況問題，獨立整理成本報告。
> 本檔存放於 `D:\art_icnclab-main`（目前工作資料夾，見下方發現1的說明與限制）。

## 摘要（風險由高到低）

1. **專案資料夾分歧**：至少存在三份不同路徑的專案副本，彼此關係與新舊程度未完全確認，本次對話的所有修改都寫在其中一份，需要人工確認才能決定後續動作。
2. **Ollama 埠 11434 跨環境搶佔**：WSL `Ubuntu-22.04` 的 `ollama.service` 持續重啟失敗（`address already in use`），現場即時重現，非假設。
3. **Neo4j／Elasticsearch 服務反覆重啟**：查證期間持續觀察到，成因未定。
4. **Docker 已從 `Ubuntu-22.04` 完全移除，但遷移不完整**：三項服務已原生化，OpenWebUI／ChromaDB 常駐服務現況不明或缺席。
5. **埠號規劃混亂（含 ml-service vs OpenWebUI 搶 8080）**：已在設計文件附錄B詳列，此處僅摘要並補上與本報告其他發現的關聯。

---

## 發現1：專案資料夾分歧（最優先待確認）

現場（WSL `Ubuntu-22.04`）查證發現，同一台機器上至少有三個地方都放著疑似同一專案的內容，彼此關係未完全查證：

| 路徑 | 特徵 | 研判 |
|---|---|---|
| `D:\art_icnclab-main\art_icnclab-main`（本次對話全程工作的資料夾） | **無 `.git`**，資料夾名稱帶 `-main` 後綴 | 高度疑似從 GitHub 用「Download ZIP」下載展開的離線快照，與版控歷史脫鉤 |
| `D:\art_icnclab`（WSL 內路徑 `/mnt/d/art_icnclab`） | **有 `.git`**，`git remote -v` 指向 `https://github.com/icnclabstust-hub/art_icnclab.git`，最新 commit `979745c` (2026-08-17)，內含真實 `.env`／`.webui_secret_key` 等機敏設定檔 | 高度疑似真正的開發用 git repo |
| `C:\Users\user\Desktop\藝術史資料庫` | 透過 WSL 內 symlink `/home/user/icnclab/art_history_db` 指向此路徑；另外 `D:\` 下也有一個同名資料夾 `D:\藝術史資料庫`（本次未展開細查，兩者是否相同尚未確認） | 可能是實際服務啟動時使用的工作目錄（原生服務常見會設在使用者桌面/家目錄下，而非 D 槽），也可能是另一份獨立副本 |

**影響**：本次對話中所有的設計文件、評估表、SQL migration 草稿、`unified_rag_manager_v2.py` 的稽核 log middleware 修改，**全部寫在 `D:\art_icnclab-main\art_icnclab-main`**。如果這份不是實際部署/開發依據的那一份，這些變更目前只是「紙上」存在，尚未進入真正會被執行的程式碢。

**本報告不擅自搬移或合併任何檔案**——三份內容可能有各自尚未同步的獨立變更，貿然搬動有覆蓋他人工作的風險。需要人工確認：

- [ ] `D:\art_icnclab` 是否為目前唯一的開發/部署依據？
- [ ] `D:\art_icnclab-main` 這份快照是什麼時候、為什麼建立的？是否已經沒有用途、可以封存？
- [ ] `C:\Users\user\Desktop\藝術史資料庫` 與 `D:\藝術史資料庫` 是否為同一份、是否為服務實際執行時的工作目錄？
- [ ] 確認後，今天在 `D:\art_icnclab-main` 產出的設計文件／SQL／程式碼修改，是否需要移植到正本？

## 發現2：`ollama.service`（WSL `Ubuntu-22.04`）埠 11434 持續衝突，現場即時重現

`journalctl -u ollama.service` 顯示持續性的重啟失敗迴圈：

```
Error: listen tcp 127.0.0.1:11434: bind: address already in use
Main process exited, code=exited, status=1/FAILURE
Scheduled restart job, restart counter is at N...
```

現場同時查到這台機器上至少有三個 Ollama 候選佔用者：Windows 主機本身（`netstat` 查到 PID 監聽 11434）、另一個仍在執行中的 WSL 發行版 `Ubuntu`（非 `Ubuntu-22.04`，本次先前查證時已在跑 Ollama）、以及 `Ubuntu-22.04` 自己的 `ollama.service`。三者搶同一個埠，只有一個能真正提供服務，其餘持續 crash-loop。`.wslconfig` 設定 `localhostForwarding=true`，這類設定在特定 WSL2 版本下可能讓多個發行版共用 loopback 埠命名空間，此為推測成因，未逐一排除其他可能性。

**影響**：若圖上「本地端後端系統」的 Ollama 呼叫（`:11434`）實際指向的是不穩定、持續重啟的那個實例，會造成生成請求間歇性失敗。

## 發現3：`neo4j.service`／`elasticsearch.service` 反覆重啟，成因未定

查證期間（約 14:16–14:18 這段時間內）觀察到：

- `elasticsearch.service`：反覆 Start→Started→Stopping→Stopped，每次間隔約 30 秒。
- `neo4j.service`：`journalctl` 出現「Neo4j is already running (pid:492)」的啟動失敗訊息，代表有東西在既有實例還跑著的狀態下又嘗試重新啟動它。

**已排除的可能性**：在停止對 WSL 下任何指令一段時間後重新查詢，`neo4j.service`／`elasticsearch.service` 仍分別回報 `failed`／`activating`，代表**這個重啟迴圈並非只在我密集下指令的當下才發生**，不能簡單歸因於本次診斷操作本身。

**尚未排除的可能性**：

- 系統上是否有既定的健康檢查/看門狗腳本（例如 `scripts/utils/schedulerMonitor.js` 或某個 cron／Task Scheduler 項目）在週期性重啟這些服務？
- 是否為資源競爭（`free -h` 查得當下用掉 12Gi／21Gi，非用罄，但 Neo4j／Elasticsearch／Postgres／Ollama 同時搶 JVM 啟動時間可能導致健康檢查逾時）？
- 是否為 WSL2 本身在多個發行版同時啟動時的已知資源/排程問題？

**建議**：由同學在不透過本次 AI 對話的情況下，直接在該機器上觀察 `journalctl -u neo4j -f` 與 `journalctl -u elasticsearch -f` 一段時間，確認重啟迴圈是否持續存在、找出真正觸發者，而非僅憑本次一次性查證下結論。

## 發現4：Docker 已從 `Ubuntu-22.04` 完全移除，但對照 2026-08-29 migration 草案，遷移不完整

現場查證：`which docker dockerd containerd` 全部查無結果，`docker ps` 回報「command not found」。對照 `docs/designs/2026-08-29-remove-docker-native-migration.md` 草案（該文件狀態仍是「GD 步驟3產出，尚未走完步驟4評估」）列出的四項服務：

| 服務 | 該草案原規劃 | 本次現場查證現況 |
|---|---|---|
| Neo4j | Docker 容器 `art-history-neo4j` | ✅ 已原生化，`neo4j.service`（但見發現3，不穩定） |
| ChromaDB | Docker 容器 `art-history-chromadb` | ⚠️ pip 套件已裝（1.5.9），**未查到常駐服務程序**，現況不明 |
| Ollama | Docker 容器 `art-history-ollama` | ✅ 已原生化，`ollama.service`（但見發現2，埠衝突） |
| OpenWebUI | Docker 容器 `art-history-openwebui` | ❌ **完全未安裝、未找到任何進程或套件** |

另外查到 PostgreSQL 18、Redis 也已是原生 systemd 服務，這兩項不在原草案的「四項服務」範圍內，代表原生化的實際範圍已超出該草案原本規劃的清單。

**影響**：這份 2026-08-29 的設計文件目前的「現況」章節已經過時（假設 Docker 仍在使用），且遷移動作看起來已經實際發生但沒有走完 GD 步驟4評估、沒有老師簽核紀錄。建議該文件需要重新走一次現況調查與評估，而不是視為仍停留在草案構想階段。

## 發現5：埠號規劃混亂（摘要，完整清單見設計文件附錄B）

已完整記錄於 `docs/designs/2026-09-20-target-architecture-consistency-eval-faithfulness.md` 第5.5.1節與附錄B，此處僅列摘要並標註與本報告發現的交互關係：

- **ml-service（CUDA/Torch）與 OpenWebUI 靜態分析確認搶同一個埠 `8080`**（`ml-service/start.sh` gunicorn 綁定 `127.0.0.1:8080`，OpenWebUI 用 `docker run -p 8080:8080`），因 repo 內無任何 Dockerfile/docker-compose，ml-service 無容器隔離。**但本次在 `Ubuntu-22.04` 現場查證時，OpenWebUI 根本沒有安裝（見發現4），所以這個衝突目前無法重現**，需等 OpenWebUI 實際部署後才能驗證。
- Backend API 三重身份混淆：`unified_rag_manager_v2.py`(8007) / `create_graphrag_models.py`(硬編碼8010) / `.env.example` 的 `RAG_API_PORT=8008`（查無程式碼讀取）。本次現場查證這兩支 Python 服務目前都沒有在 `Ubuntu-22.04` 上執行，同樣無法即時重現，仍屬靜態分析結論。
- Neo4j 7687／7688：`unified_rag_manager_v2.py` 註解說明因 WSL 系統內建 Neo4j 佔用 7687 而改用 7688，但本次現場查證 `Ubuntu-22.04` 上的 Neo4j 實際監聽的是標準的 **7687**（非7688）。這代表現場這個 Neo4j 很可能就是「系統內建」的那個、或是專案的 Neo4j 現在其實用標準埠沒有改，與程式碼註解的假設不一致，**需要進一步確認 `unified_rag_manager_v2.py` 目前連的到底是哪一個 Neo4j 實例**。

## 建議處理順序

1. **先確認發現1（資料夾分歧）**——這是所有後續動作的前提，不確認清楚，後面查到的任何「現況」都可能查錯份。
2. **確認發現2/3是否仍持續發生**，且與本次診斷操作無關（已有初步證據支持無關，但建議獨立驗證）。
3. **重新評估 2026-08-29 的 Docker 遷移設計文件**（發現4），補上真實現況與 GD 步驟4評估，而非放著當作未執行的草案。
4. 埠號規劃（發現5）等 OpenWebUI／RAG 後端實際部署起來後再現場驗證一次，目前多數結論仍是靜態分析。

## 附錄：本次查證方法

- `wsl.exe -l -v` 確認發行版清單與執行狀態。
- `wsl.exe -d Ubuntu-22.04 -- ss -tlnp` 查即時監聽埠。
- `wsl.exe -d Ubuntu-22.04 -- systemctl list-units --type=service --all` 查服務清單與狀態。
- `wsl.exe -d Ubuntu-22.04 -- journalctl -u <service> --no-pager -n 40` 查個別服務錯誤日誌。
- `wsl.exe -d Ubuntu-22.04 -- which docker dockerd containerd` 確認 Docker 是否存在。
- `wsl.exe -d Ubuntu-22.04 -- find / -maxdepth 4 -iname '*art*history*'` 找專案相關路徑。
- 全程僅執行唯讀查詢指令（`ss`／`systemctl status`／`journalctl`／`ls`／`git remote -v`／`git log`／`free -h`），未執行任何 `start`／`stop`／`restart`／`rm` 等變更性指令。
