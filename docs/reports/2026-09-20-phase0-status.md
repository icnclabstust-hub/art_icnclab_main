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
