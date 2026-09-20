# 設計文件：Phase 1「新架構跑法」——爬蟲資料經 PostgreSQL catalog 攝取並同步三檢索庫

> 狀態：**草案，待使用者確認**（GD 步驟 3）。確認前不寫實作。
> 上位設計：`docs/designs/2026-09-20-target-architecture-consistency-eval-faithfulness.md`（§5.1 Phase 1／2）
> 評估表簽核：`...-assessment.md` §九 目前仍為空白，依 `CLAUDE.md` R5 由使用者／老師填寫。

## 1. 背景與問題

現行匯入是「爬蟲 → `data/raw/*.json` → `import_all_museums_to_neo4j.py` 同時寫 Neo4j 與 ChromaDB → `sync_chromadb_to_elasticsearch.py` 再由 Chroma 全量掃描寫 ES」。
問題：沒有單一來源、沒有變更偵測（每次全量）、沒有內容掃描、三庫是否一致無法檢查。
現況數據：Neo4j 7,276 節點／11,954 關係（Artwork 3,831、Artist 2,841…）、ChromaDB 88M、PostgreSQL `art_history_db` 幾乎是空的（備份僅 36K），`catalog` schema 已建立但無資料。

## 2. 目標與非目標

目標：
- 爬蟲資料改走：**攝取 → hash 比對 → 內容掃描 → 寫 `catalog` + 同交易寫 `sync_events` → 訂閱器增量套用到 ChromaDB／ES／Neo4j**。
- **沿用現有 ID 與切塊邏輯**（`chunking.build_chunk_records` 產生的 `chunk_id`、Neo4j 的 `clean_id`），使既有資料可被「認領」而不必重新 embedding、也不會產生重複。
- 影子模式（shadow）先行：新流程先只寫 `catalog` 並與現有三庫比對，確認一致後才切換訂閱器寫入。

非目標（本階段不做）：Neo4j 五種原子操作與 30 天軟刪除（Phase 2）、Redis 語意快取、RAG Router、忠實度守門、評測迴路。

## 3. 資料對應

| 現有概念 | catalog 對應 | 說明 |
|---|---|---|
| 一筆爬蟲作品紀錄（如一件 Harvard artwork） | `catalog.documents` 一列 | `doc_id` 以「來源＋來源內 id」做確定性 UUIDv5，重跑不產生新列；`source`＝來源名（harvard、met…） |
| 該作品切出的文字塊（Chroma 的一個 id） | `catalog.chunks` 一列 | `chunk_id` 沿用現有 Chroma id 的確定性 UUIDv5 映射，並在 `metadata` 保存原字串 id，供訂閱器寫回 Chroma 時使用相同 id |
| 作品／藝術家／機構等圖節點與關係 | `documents.metadata` 內的正規化欄位（normalize_* 輸出） | Neo4j 訂閱器從 `payload` 重建 `MERGE`，不另建圖表 |
| `content_hash` | 對正規化後 JSON（排序鍵）取 SHA-256 | 變更偵測依據；與 `chunks.content_hash`（對 chunk 文字）分開 |

## 4. 流程

```
data/raw/*.json（爬蟲既有產出，不改爬蟲）
  → ingest（讀檔 → normalize_* 沿用現有函式 → 算 content_hash）
  → 與 catalog 比對：無變更略過；新增／變更才往下
  → scanner（見 §5）：clean → 繼續；可疑 → quarantined，不寫 outbox、留待人工
  → 單一交易：upsert documents/chunks（version+1）＋寫 sync_events（upsert）
  → 訂閱器（每庫一支，依 sync_cursor 增量消費）：ChromaDB upsert／ES index／Neo4j MERGE
  → 成功後才前移該訂閱者的 last_event_id（失敗不前移、重試）
```
變更偵測用「來源檔案中已消失」標記為 `is_deleted=true` 並寫 `soft_delete` 事件；本階段訂閱器對 `soft_delete` 只做「從 ChromaDB／ES 刪除、Neo4j 標記」，不物理刪 Neo4j 節點（留待 Phase 2）。

## 5. 惡意內容掃描器（最小可行）

僅做確定性規則，不引入模型：提示注入樣式（如「ignore previous instructions」「忽略以上指令」、system prompt 洩漏語）、隱藏字元（零寬字元、雙向控制字元）、異常長度／異常比例的非文字內容。命中即 `quarantine_status='quarantined'`，附命中規則寫入 `metadata.scan`，**不進 outbox、不進任何檢索庫**；人工複審後改 `reviewed` 才放行。規則清單以檔案維護，可擴充。

## 6. 方案比較

| | 方案 A：新增獨立攝取程式＋訂閱器，影子模式後切換（建議） | 方案 B：改寫現有 `import_all_museums_to_neo4j.py` 為直接寫 catalog 並同步 |
|---|---|---|
| 做法 | 新增 `ingest/` 與三支訂閱器；沿用 normalize／chunking 函式；舊匯入腳本保留到切換完成 | 就地修改舊匯入腳本，去掉直接寫庫的部分 |
| 優點 | 舊流程不動、可隨時回退；影子比對可量化一致性；訂閱器可各自測試 | 檔案少、改動集中 |
| 缺點 | 過渡期兩套並存；新增檔案較多 | 舊流程一改就無回退；耦合 normalize 與寫入，難單元測試 |
| 風險 | 低 | 中高（動到每日排程正在用的腳本） |

選定：**方案 A**。

## 7. 對外介面與排程

- 新增 CLI：`python -m ingest run --source <名稱|all> [--dry-run]`、`python -m ingest verify`（catalog 與三庫筆數／hash 比對）、`python -m subscribers run --target chromadb|elasticsearch|neo4j [--once]`。
- 不新增對外 HTTP 埠。排程：先手動，穩定後才併入 `daily_crawl_and_sync.sh`（屆時依規範重新走 GD 的排程項）。
- 新增依賴：`psycopg`（PostgreSQL 連線，需釘版）。其餘沿用現有套件。

## 8. 安全與測試

- 連線密碼只讀 `.env`（`DB_*`），不入程式與 log（S-01／S-15）；SQL 全參數化（S-05）。
- 掃描器規則有單元測試（含惡意樣本與良性樣本）；ingest 以拋棄式資料庫做整合測試（同 Phase 0 做法，P-02）；影子模式以 `verify` 輸出作為驗收證據。
- 驗收標準：對 Harvard 單一來源跑完整流程後，catalog 筆數＝來源檔筆數；重跑一次新增／變更數為 0；三庫與 catalog 的 id 集合差異為 0。

## 9. 部署與回滾

- 先影子模式：只寫 `catalog`，訂閱器不啟動；回滾＝`TRUNCATE` catalog 相關表（`docs/reports/2026-09-20-phase0-status.md` 有 DROP SCHEMA 回滾）。
- 切換後：停訂閱器即回到舊匯入流程（舊腳本保留）。

## 10. 前置條件（目前未滿足）

1. Neo4j 埠號整併尚未由使用者執行：7687 仍是**系統實例**，專案資料實例（7,276 節點）在 7688 且未啟動。
2. ChromaDB（8000）未在執行；執行期專案目錄（桌面路徑）不存在，`daily_crawl_and_sync.sh` 目前無法照原樣執行。
3. 評估表老師簽核欄未填。

## 11. 需要使用者確認的問題

1. **ID 相容策略**：是否同意沿用現有 Chroma／Neo4j id（確定性 UUIDv5 映射）以「認領」既有資料？（替代：全新 id＋清空重匯，需重算 embedding，耗時且要先備份三庫）
2. **範圍**：影子模式先只跑 **Harvard 單一來源**驗收，再擴到其餘 9 個來源，可以嗎？
3. **Neo4j 訂閱器的寫入目標**：以整併後的 7687（專案實例）為準，還是在整併前先用 7688 過渡？
4. **掃描器命中時**：只隔離不通知即可，還是要寫入告警表 `eval.alerts`？
5. 是否同意新增 `psycopg` 依賴？
