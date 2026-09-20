# Phase 0 執行狀態（2026-09-20）

> 對應設計文件：`docs/designs/2026-09-20-target-architecture-consistency-eval-faithfulness.md` §5.1 Phase 0
> 評估表簽核：**尚未取得**（`docs/designs/2026-09-20-target-architecture-consistency-eval-faithfulness-assessment.md` §九 仍為空）

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
| ChromaDB | 8000 | **8000** ✅ | 原 Docker 時代的 8001 殘留（`unified_rag_manager_v2.py` 預設、`importer.py`、ops 檢查腳本）改為 8000，避免與新的 Backend API 8001 衝突 |
| Elasticsearch | 9200 | 9200 ✅ | |
| Neo4j | 7687 | 7687 ✅ | 專案實例；7688／7475 已廢除 |
| Redis | 6379 | 6379 ✅ | |
| Ollama | 11434 | 11434 ✅ | |
| Open WebUI | 8080 | **3000** ❌ | Windows 保留 TCP 7937–8340（含 8080），沒有系統管理員權限無法解除保留；改回 8080 只需把 `Start-NativeServices.ps1` 的 `$WebUiPort` 改為 8080，但需先由使用者以系統管理員解除保留（例如重置 WinNAT 動態保留），且屆時 WSL 網路可能需重啟 |

- Open WebUI 資料庫（`/home/user/openwebui-data/webui.db`）已備份為 `/home/user/backups/webui.db_pre_port8001_20260920_220132` 後，把 `function` 表 11 筆 pipe 內容中的 `localhost:8007` 更新為 `localhost:8001`（`integrity_check: ok`）。
- `.env.example` 孤兒設定 `RAG_API_PORT=8008`（沒有任何程式讀取）已改為實際使用的 `RAG_MANAGER_PORT=8001`。
- **刻意未動**（不在架構圖上、屬舊版／已停用服務）：`create_graphrag_models.py` 的 8010（Multi-DB RAG Server）與相關 ops 腳本、`test_suite.py` 與 `tests/manual/*` 的 8008、`src/agents/rl/rl_server.py` 的 8011、`ml-service` 的 8080、MCP 工具登記表的 8001／8010／8011（純靜態宣告）。若要清理這些舊服務的引用，需先確認哪些已廢棄。
- 歷史文件（`docs/designs/`、本目錄舊報告）中的 8007 敘述保留原樣，屬當時紀錄。

## 補充：Docker 相關內容清除（2026-09-20）

Docker 已於 2026-07-28 從系統移除（`Ubuntu-22.04` 內無 `docker` 指令、repo 內從來沒有 Dockerfile／docker-compose），依使用者指示清除程式碼與設定中的 Docker 遺留。已刪除的檔案可從 git 歷史還原。

- **刪除（16 個，全部只能在 Docker 環境運作）**：`scripts/ops/` 的 `deploy.sh`、`gpu-setup.sh`、`download-models.sh`、`start_crawler_with_venv.sh`、`start_experiments.sh`、`start_graph_viz_demo.sh`、`test_rag_performance.sh`、`verify-rag-system.sh`、`check_system_status.sh`、`setup-ollama-rag-proxy.sh`；`scripts/deploy-mcp-tools.sh`、`scripts/prepare_experiment_environment.py`；三份 Docker 服務名 nginx 設定（`config/nginx/nginx.conf`、`context/deployment/nginx.conf`、`nginx-simple.conf`）；`monitoring/prometheus.yml`（全部目標為 compose 服務名）。
- **改為原生**：`system_full_diagnostic.py`（`docker exec` 改成直接呼叫 `cypher-shell`／`ollama`；Neo4j 密碼只取環境變數，不再猜測預設密碼）、`mcp_tool_registry.py`（移除 Docker 欄位與探索）。
- **Docker 服務名／預設值改為本機位址**：`host.docker.internal` → `127.0.0.1`（Open WebUI 設定、`prometheus.yml`）；`http://cuda-ml-service:8080`（Node 後端預設、doctor／collect 提示）→ `http://127.0.0.1:8080`；`rag_config.json` 的 `ollama`／`neo4j`／`chromadb`／`postgres` 主機名 → `127.0.0.1`；`config/production.js` 的 `redis-cluster` → `127.0.0.1`；舊 ChromaDB 埠 8001 → 8000（前一節）。
- **其他**：`.gitignore` 的 Docker 條目、各檔「非 Docker」註解與 `docker-compose` 提示文字一併移除；`doctor.sh` 不再檢查 `docker` 服務。
- **刻意保留**：`docs/` 底下記錄 Docker 移除過程與當時現況的文件（例如 `2026-08-29-remove-docker-native-migration.md`、問題登錄表、本目錄各報告）以及實驗室規範 `CODE_REVIEW_STANDARD.md`（其表 E 仍引用已刪除的 `download-models.sh` 作為範例，需由老師決定是否修訂）。
- **repo 之外**：舊 repo `D:\art_icnclab\.env` 內仍有 `DB_HOST_DOCKER`，建議刪除。

### Open WebUI 埠

`Start-NativeServices.ps1` 現在每次啟動時判斷：**優先使用 8080**，若 Windows 已把 8080 保留（`netsh interface ipv4 show excludedportrange protocol=tcp`）才退回 3000。目前這台機器 8080 落在保留範圍（8037–8136），所以實際仍是 3000；保留範圍會隨 Windows 重開機變動，之後可能自動變成 8080。
