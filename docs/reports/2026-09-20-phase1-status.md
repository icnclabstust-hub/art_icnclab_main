# Phase 1 執行狀態（2026-09-20）

> 設計：`docs/designs/2026-09-20-phase1-catalog-ingestion.md`（使用者已確認第 11 節決定）

## 已完成

| 項目 | 狀態 | 證據 |
|---|---|---|
| 攝取層 `langchain-rag/ingest/`（雜湊比對、掃描器、單交易寫 catalog＋outbox、`--dry-run`、`--prune`、`verify`） | ✅ | 55 個測試通過（38 個 DB 整併測試於拋棄式資料庫＋17 個單元／相容性測試）；`ruff check`／`ruff format --check` 全過 |
| 與既有匯入邏輯相容 | ✅ | 測試以既有 `ChromaBatchWriter` 對同一筆資料比對，chunk id、文字、metadata 逐項相同 |
| ChromaDB／ES 訂閱器與游標迴圈 `langchain-rag/subscribers/` | ✅（僅以假物件測過） | 至少一次投遞、失敗不前移游標、同批以最後事件為準、ES 向量取自 Chroma 且未就緒時等待 |
| 05 遷移（`external_id`、`art_user` 對 catalog 的資料權限） | ✅ 已套用 `art_history_db` | 套用前備份 `/var/lib/postgresql/art_history_db_pre_phase1_20260920_183704.dump`（56K） |
| `psycopg[binary]==3.3.6` | ✅ | 已釘進 `requirements.txt`，pip-audit 無已知漏洞 |
| 影子模式實跑（Harvard，`--file` 舊 repo 的 `harvard_objects.json`） | ✅ | 第 1 次：新增 150 文件／158 chunk／308 事件；第 2 次：未變 150、事件 0（冪等）；隔離 0 |

## 尚未完成

| 項目 | 原因 |
|---|---|
| 訂閱器實際寫入 ChromaDB／ES | ChromaDB 目前沒在執行；且需 BGE-M3 embedding 服務（Ollama）可用。事件已在 outbox 等待，游標為 0，不會遺失 |
| `verify` 對 ChromaDB／ES 的實際比對，與既有資料「認領」相容性的實測 | 同上（Chroma 未啟動）。目前只有程式碼層的相容性測試 |
| Neo4j 訂閱器 | 待 Neo4j 埠號整併（使用者尚未在 WSL 執行 `consolidate_neo4j_ports.sh`）；7687 仍是系統實例 |
| 其餘 9 個來源 | 依設計先以 Harvard 驗收 |
| 完整 Harvard 爬取 | 目前只匯入舊 repo 的 150 筆樣本檔；爬蟲尚未重新執行（桌面執行期目錄不存在） |
| 併入 `daily_crawl_and_sync.sh` 排程 | 穩定後另依 GD 處理 |

## 回滾

```sql
-- 影子模式的資料（只在 catalog，未影響任何檢索庫）
TRUNCATE catalog.sync_events, catalog.sync_cursor, catalog.chunks, catalog.documents RESTART IDENTITY CASCADE;
```
