# Phase 1 執行狀態（2026-09-20，Neo4j 整併與三庫同步完成後更新）

> 設計：`docs/designs/2026-09-20-phase1-catalog-ingestion.md`（使用者已確認第 11 節決定）

## 已完成

| 項目 | 狀態 | 證據 |
|---|---|---|
| 攝取層 `langchain-rag/ingest/`（雜湊比對、掃描器、單交易寫 catalog＋outbox、`--dry-run`、`--prune`、`verify`）與來源介面卡（含 Europeana） | ✅ | 測試 49 個（拋棄式資料庫）＋ 28 個單元／相容性測試通過；`ruff check`／`format --check` 全過；與既有 `ChromaBatchWriter` 產出逐項比對一致 |
| 訂閱器 `langchain-rag/subscribers/`：ChromaDB、Elasticsearch（向量取自 Chroma）、Neo4j | ✅ | Neo4j 訂閱器以假 session 測過，Cypher 取自既有匯入腳本；CLI 有「目標 Neo4j 無 Artwork 節點就拒絕」的防錯實例保護 |
| 05 遷移（`external_id`、`art_user` 對 catalog 的權限） | ✅ 已套用 | 套用前備份 `/var/lib/postgresql/art_history_db_pre_phase1_20260920_183704.dump` |
| 重新爬取（依使用者選項 1） | ✅ 9／10 個來源 | Harvard 96、Europeana 913、MET 系 752、專門藝術 668、Google Books 29、AIC／V&A／Cleveland 各 300；**Yale 回 HTTP 403**（來源端拒絕，未嘗試繞過） |
| 匯入 catalog（影子模式）→ 同步 ChromaDB／ES | ✅ 8 個來源 | 全部無內容隔離。ChromaDB 5,598 → 5,799（多出的 201 個＝各來源「待新增」167＋Europeana 34，與比對預估完全吻合）；兩訂閱器游標追上，落後 0 |
| 認領驗證 | ✅ | Harvard 新爬的 107 個 chunk 與線上文字 107/107 相同；其餘來源多數相同，少數差異為較新的爬取內容（Europeana 為多語系欄位語言順序不同），與舊每日匯入重跑結果一致 |
| 新架構每日流程腳本 `scripts/daily_crawl_and_sync_catalog.sh` | ✅ 已寫好、**尚未取代排程** | 語法檢查通過，未實跑完整流程 |

## 尚未完成

| 項目 | 原因 |
|---|---|
| （已完成）Neo4j 埠號整併與訂閱器寫入 | 使用者執行整併後，專案 Neo4j 在 7687／7474（7,276 節點／11,954 關係完整），訂閱器處理 3,288 筆事件：Artwork 3,831→3,938、Artist 2,841→2,916、CREATED 4,656→4,813；三庫游標皆追上、落後 0 |
| Yale 來源 | 來源端 403，需另外處理（帳號／授權／換管道），非程式問題 |
| `verify` 全綠 | catalog 只涵蓋本次爬到的資料；檢索庫另有更早爬取而本次未再出現的 chunk（例如 Harvard 74 個），`verify` 會回報「只在檢索庫」。屬預期，不代表壞資料 |
| 排程切換 | 新腳本 `daily_crawl_and_sync_catalog.sh` 已以 `SKIP_CRAWL=1` 完整實測（攝取→三庫訂閱→驗證），第二次執行 8 個來源全部「未變」、0 事件（冪等）。實測抓到兩個問題並已修正：`.env` 的 `DATA_RAW_DIR=./data/raw` 與 `NEO4J_URI=…:7688` 會覆蓋腳本設定（腳本改為強制指定）、MET 兩個檔案含相同 id 造成每次都產生變更事件（改為載入時去重）。舊 `daily_crawl_and_sync.sh` 仍是現行排程，切換仍待您決定 |
| 執行期目錄 | 桌面執行期目錄不存在；`.env` 目前只在舊 repo `D:\art_icnclab\.env` |

## 回滾

```sql
-- 影子資料只在 catalog
TRUNCATE catalog.sync_events, catalog.sync_cursor, catalog.chunks, catalog.documents RESTART IDENTITY CASCADE;
```
ChromaDB／ES 中本次新增或更新的資料：舊每日匯入腳本重跑即可用當次爬取覆蓋；若要精確還原需以爬取前的資料目錄備份（本次未另備份 ChromaDB，內容皆為新爬取資料的 upsert）。
