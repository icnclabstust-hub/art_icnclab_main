# Phase 0 執行狀態（2026-09-20）

> 對應設計文件：`docs/designs/2026-09-11-target-architecture-consistency-eval-faithfulness.md` §5.1 Phase 0
> 評估表簽核：**尚未取得**（`docs/designs/2026-09-11-target-architecture-consistency-eval-faithfulness-assessment.md` §九 仍為空）

## 已完成

| 項目 | 狀態 | 證據／說明 |
|---|---|---|
| `catalog`／`biz`／`eval` 三個 schema 建立 | ✅ 已套用到 `art_history_db` | 10 張表：`catalog.{documents,chunks,sync_events,sync_cursor}`、`biz.{users,conversations,messages}`、`eval.{golden_queries,measurements,alerts}` |
| 套用前驗證（P-02） | ✅ | 先在拋棄式資料庫 `zz_schema_scratch` 完整套用並冒煙測試（寫入、`updated_at` 觸發器、CHECK 限制拒絕非法值），通過後刪除該庫 |
| 套用前備份 | ✅ | `/var/lib/postgresql/art_history_db_pre_phase0_20260920_180452.dump`（36K，`pg_restore -l` 可讀） |
| 既有資料未受影響 | ✅ | `public` schema 仍為 13 張表；本次 DDL 只新增 schema，於單一交易內執行 |
| 稽核 log middleware | ✅ 程式碼在分支 | 尚未部署到執行中的服務（桌面執行期目錄不存在，見下） |
| 系統 Neo4j（7687）盤點 | ✅ | 只有 6 個設定節點，無藝術史資料；專案原生實例 7,276 節點／11,954 關係，資料完整 |
| Neo4j 系統實例密碼重設 | ✅ | 新密碼存於 WSL `/home/user/.neo4j-system-password`（權限 600） |

## 未完成

| 項目 | 狀態 | 原因／下一步 |
|---|---|---|
| Neo4j 埠號整併（7688→7687、停用系統 `neo4j.service`） | ⏸ 待使用者執行 | 需 root 且會停用系統服務，自動化執行被權限機制擋下。請在 WSL 執行 `sudo bash scripts/ops/consolidate_neo4j_ports.sh`（含 `--rollback`） |
| Open WebUI | ✅ 已啟動（2026-09-20 更正） | 先前誤判「未安裝」：它裝在 `/home/user/openwebui-venv`（資料 `/home/user/openwebui-data`），非系統 Python。已用既有方式啟動於 8080 |
| ChromaDB 常駐服務 | ✅ 已啟動 | 埠 8000，資料 `/home/user/native-chromadb/data`（目前約 5,799 個 chunk） |
| 稽核 middleware 部署 | ✅ | RAG 後端已改由 F: 這份程式碼啟動（8007），稽核 log 已實際記到每次 `/api/v1/query` 請求 |
| ml-service 與 OpenWebUI 同占 8080 | ❌ | 獨立變更，待 OpenWebUI 部署後處理 |
| Elasticsearch／Neo4j 反覆重啟成因 | ❌ | 尚未找出觸發者 |
| 評估表老師簽核 | ❌ | 依 CLAUDE.md，Tier B 須簽核後才算通過 GD |

## 回滾

```sql
-- 僅移除本次新增的三個 schema（不影響 public）
DROP SCHEMA eval CASCADE;
DROP SCHEMA biz CASCADE;
DROP SCHEMA catalog CASCADE;
```

完整還原（極端情況）：`pg_restore -d art_history_db --clean /var/lib/postgresql/art_history_db_pre_phase0_20260920_180452.dump`。

## 補充：Open WebUI 埠號改用 3000（2026-09-20）

- **現象**：Windows 瀏覽器開 `http://localhost:8080` 出現 `ERR_CONNECTION_REFUSED`，但 Open WebUI 在 WSL 內正常。
- **根因**：Windows 把 TCP 埠 7937–8340（含 8000、8007、8080）等範圍保留給 Hyper-V／WinNAT（`netsh interface ipv4 show excludedportrange protocol=tcp`），WSL 的 localhost 轉發程式無法在 Windows 端綁定這些埠；只有不在保留範圍的埠（例如 Neo4j 的 7474）有轉發。保留範圍可能隨系統重開機變動。
- **處理**：Open WebUI 改用 **3000**（`http://localhost:3000`）；RAG 後端 CORS 加入該來源；`Start-NativeServices.ps1` 改在 WSL 內偵測服務（原本從 Windows 連 localhost 測 8000/8007 永遠失敗，會誤判並重複啟動）。ChromaDB（8000）與 RAG 後端（8007）只在 WSL 內被使用，不需要 Windows 端可連。
- **登入自動啟動**：已註冊工作排程 `ArtHistoryDB-StartServices`（目前使用者、一般權限、登入時執行 `Start-NativeServices.ps1`，`.env` 位置以 `ART_ENV_FILE` 指向 `D:\art_icnclab\.env`）。重新註冊或改路徑用 `scripts/Register-StartupTask.ps1`；移除用 `Unregister-ScheduledTask -TaskName ArtHistoryDB-StartServices -Confirm:$false`。
- 與設計文件圖上標示的 8080 不同，屬環境限制；ml-service 與 OpenWebUI 搶 8080 的問題（附錄 B）因此在本機不再發生（Open WebUI 已不用 8080）。

## 補充：埠號對齊架構圖（2026-09-20）

| 服務 | 圖上 | 現況 | 說明 |
|---|---|---|---|
| Backend API | 8001 | **8001** ✅ | 原 8007 已全面改為 8001（程式預設、啟動腳本、ops／評測／測試腳本、`rag_config.json`、11 個 Open WebUI pipe 預設網址）；舊 8007 已無服務 |
| ChromaDB | 8000 | **8000** ✅ | 舊的 8001 殘留（`unified_rag_manager_v2.py` 預設、`importer.py`、ops 檢查腳本）改為 8000，避免與新的 Backend API 8001 衝突 |
| Elasticsearch | 9200 | 9200 ✅ | |
| Neo4j | 7687 | 7687 ✅ | 專案實例；7688／7475 已廢除 |
| Redis | 6379 | 6379 ✅ | |
| Ollama | 11434 | 11434 ✅ | |
| Open WebUI | 8080 | **3000** ❌ | Windows 保留 TCP 7937–8340（含 8080），沒有系統管理員權限無法解除保留；改回 8080 只需把 `Start-NativeServices.ps1` 的 `$WebUiPort` 改為 8080，但需先由使用者以系統管理員解除保留（例如重置 WinNAT 動態保留），且屆時 WSL 網路可能需重啟 |

- Open WebUI 資料庫（`/home/user/openwebui-data/webui.db`）已備份為 `/home/user/backups/webui.db_pre_port8001_20260920_220132` 後，把 `function` 表 11 筆 pipe 內容中的 `localhost:8007` 更新為 `localhost:8001`（`integrity_check: ok`）。
- `.env.example` 孤兒設定 `RAG_API_PORT=8008`（沒有任何程式讀取）已改為實際使用的 `RAG_MANAGER_PORT=8001`。
- **刻意未動**（不在架構圖上、屬舊版／已停用服務）：`create_graphrag_models.py` 的 8010（Multi-DB RAG Server）與相關 ops 腳本、`test_suite.py` 與 `tests/manual/*` 的 8008、`src/agents/rl/rl_server.py` 的 8011、`ml-service` 的 8080、MCP 工具登記表的 8001／8010／8011（純靜態宣告）。若要清理這些舊服務的引用，需先確認哪些已廢棄。
- 歷史文件（`docs/designs/`、本目錄舊報告）中的 8007 敘述保留原樣，屬當時紀錄。

**後續（2026-09-24）**：上面「`src/agents/rl/rl_server.py` 屬舊版／已停用服務」這句話已接續處理——確認整個 `src/`（含 `rl/`）連同頂層 `agents/`、對應 jest 測試已無任何啟動路徑、無 import、一個多月無實質異動，經使用者確認後以 `git mv` 封存至 `archive/legacy-node-system/`。`create_graphrag_models.py` 的 8010 仍在 `langchain-rag/` 內、屬另一批孤兒腳本，尚未處理。詳見 `docs/decision-log.md` 2026-09-24 條目。

## 補充：舊容器化環境遺留清除（2026-09-20）

系統已改為全部原生執行於 WSL（`Ubuntu-22.04` 內沒有容器執行環境，repo 內也從來沒有對應的映像與編排檔）。依使用者指示清除程式碼與設定中的舊遺留，已刪除的檔案可從 git 歷史還原。

- **刪除（16 個，全部只能在舊環境運作）**：`scripts/ops/` 的 `deploy.sh`、`gpu-setup.sh`、`download-models.sh`、`start_crawler_with_venv.sh`、`start_experiments.sh`、`start_graph_viz_demo.sh`、`test_rag_performance.sh`、`verify-rag-system.sh`、`check_system_status.sh`、`setup-ollama-rag-proxy.sh`；`scripts/deploy-mcp-tools.sh`、`scripts/prepare_experiment_environment.py`；三份以舊服務名為上游的 nginx 設定；`monitoring/prometheus.yml`。
- **改為原生**：`system_full_diagnostic.py` 直接呼叫 `cypher-shell`／`ollama`（Neo4j 密碼只取環境變數，不再猜測預設密碼）、`mcp_tool_registry.py` 移除舊的探索功能。
- **舊服務名／預設值改為本機位址**：舊主機別名、`cuda-ml-service`、`ollama`、`neo4j`、`chromadb`、`postgres`、`redis-cluster` 等只在舊網路內解析得到的主機名，一律改為 `127.0.0.1`；舊 ChromaDB 埠 8001 改為 8000。
- **文件**：`docs/` 內相關敘述與已無對應內容的舊遷移設計文件一併移除；repo 之外，舊 repo 的 `.env` 內仍有一個舊環境專用的主機變數（以環境名稱結尾的 `DB_HOST_*` 變數），建議刪除。
- **實驗室規範**：`CODE_REVIEW_STANDARD.md` 表 E 仍引用已刪除的 `download-models.sh` 作為範例，需由老師決定是否修訂。

### Open WebUI 埠

`Start-NativeServices.ps1` 現在每次啟動時判斷：**優先使用 8080**，若 Windows 已把 8080 保留（`netsh interface ipv4 show excludedportrange protocol=tcp`）才退回 3000。目前這台機器 8080 落在保留範圍（8037–8136），所以實際仍是 3000；保留範圍會隨 Windows 重開機變動，之後可能自動變成 8080。

## 補充：每日排程改指向新架構流程（2026-09-20）

- **問題**：Windows 工作排程 `ArtHistoryDB-DailyCrawl`（每日 03:00）仍指向已不存在的桌面目錄，最近一次結果為錯誤碼 `2147946720`，且原流程直接寫 Neo4j／ChromaDB、繞過 catalog，會讓各庫與 catalog 漂移。
- **處理**：`scripts/Run-DailyCrawl.ps1` 改為由自身位置推算路徑、先執行 `Start-NativeServices.ps1`（確保服務已啟動），再在 WSL 執行 `daily_crawl_and_sync_catalog.sh`（爬蟲 → catalog 攝取 → ChromaDB／ES／Neo4j 訂閱 → 驗證）；`-SkipCrawl` 可只做攝取與同步。工作排程的動作已改指向新包裝（`.env` 以 `ART_ENV_FILE` 指向 `D:\art_icnclab\.env`），並開啟「錯過時補跑」與「使用電池時也執行」。
- **驗證**：以與排程相同的呼叫方式執行 `-SkipCrawl`，服務偵測、8 個來源攝取、三個訂閱器全部成功（Yale 仍因來源端 403 失敗，屬預期）。完整含爬蟲的流程尚未實跑，第一次會是 2026-09-21 03:00，請於當天查看 `logs/daily_crawl/catalog_crawl_*.log`。
- 舊流程 `scripts/daily_crawl_and_sync.sh` 保留但不再被排程使用。

## 補充：PostgreSQL 例行備份（2026-09-21）

- **問題**：`backup_databases.sh` 不含 PostgreSQL 且沒有排程；catalog（單一真相來源）只存在 PostgreSQL，之前只有兩份一次性備份。
- **處理**：新增 `scripts/ops/backup_postgres.sh`（`pg_dump -Fc` → `pg_restore -l` 驗證可讀 → 輪替保留 14 份 → 鏡像到 F: 磁碟），並成為每日流程 `daily_crawl_and_sync_catalog.sh` 的最後一步（同步完成後執行）。備份用應用角色 `art_user` 執行，不需超級使用者；為此新增唯讀授權遷移 `context/database/06-backup-read-grants.sql`（只給 `biz`／`eval` 的 SELECT／USAGE，已套用）。
- **位置**：主要 `~/backups/postgres/`（WSL 內）、鏡像 `/mnt/f/art_backups/postgres/`（Windows F: 磁碟；用 `MIRROR_DIR` 可改，`BACKUP_DIR`、`BACKUP_KEEP_COUNT` 可調）。鏡像磁碟未掛載時會警告並以結束碼 2 回報，不會在 WSL 磁碟上偽造鏡像。
- **驗證**：正常備份＋鏡像成功；輪替（保留 2 份）正確刪除舊檔；錯誤密碼時結束碼 1 且不留殘檔；**實際還原測試**：把備份還原到拋棄式資料庫，8 張代表性資料表列數與線上庫逐表相同（catalog 3,281／4,267／7,590／3、`public.institutions` 4、`public.tags` 10 等）。
- **還原指令**：`pg_restore -d <目標庫> --no-owner --no-privileges <備份檔>`（先建立空的目標庫；要還原回線上庫前請先確認並另備份現況）。
- **仍未涵蓋**：Neo4j（7,458 節點）、ChromaDB、Elasticsearch、Open WebUI 資料目前沒有例行備份；catalog 可重建三個檢索庫的大部分內容（重跑訂閱器），但仍建議另行規劃；舊 `backup_databases.sh` 會停止服務，不適合放進每日流程。
