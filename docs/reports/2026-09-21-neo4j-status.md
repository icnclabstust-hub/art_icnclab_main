# Neo4j 補強執行紀錄（2026-09-21）

> 依 2026-09-21 對專案 Neo4j（7,458 節點）的檢查所列項目逐一處理；設計依據：`docs/designs/2026-09-20-target-architecture-consistency-eval-faithfulness.md` Phase 2。

| # | 項目 | 結果 |
|---|---|---|
| 1 | 唯一性約束（`Artwork.id`、`Artist.name`） | ✅ 已建立並確認 ONLINE；訂閱器啟動時自動確保。曾嘗試改綁 `127.0.0.1`，因 WSL 不轉發只綁本機的服務使 Windows 的 Neo4j Browser 連不上而還原 |
| 2 | 備份 | ✅ `scripts/ops/backup_neo4j.sh`：短暫停止（約 40 秒）→ `neo4j-admin database dump`（`neo4j`、`system`，共約 60MB）→ 無論成敗都重啟 → 保留 7 批 → 鏡像到 F:；已納入每日流程。還原驗證：把鏡像檔載入臨時目錄，`database load` 與 `database check` 結束碼皆為 0 |
| 3 | 手工示範節點 | ✅ 刪除 `A001`（蒙娜麗莎）、`P001`（達文西）、`PD001`（時期）三個互相連結、無 `source`／`name`、與正式資料無關的種子資料（刪除前已有備份）；節點 7,458→7,455 |
| 4 | 豐富關係缺口 | ✅ 執行規則式分類（`classify_art_history_graph.py --no-clean`，詞典與屬性比對、不呼叫 LLM、只疊加）：關係 12,109→13,380。有豐富關係的作品比例：europeana／met／specialized／harvard／google_books 100%、yale 264／281（原 0）、cleveland 303／316、art_institute 288／292；**va_museum 仍 145／302**（該來源資料缺材質／文化／時期欄位，非腳本遺漏）。已納入每日流程（訂閱器之後） |
| 5 | Phase 2 生命週期 | ✅ 見下 |

## 修正的問題
- `classify_art_history_graph.py` 的詞典路徑指到 repo 上一層目錄（舊目錄結構遺留），在現在的目錄結構下直接失敗；改為腳本旁邊的詞典，並可用 `TERMS_FILE` 覆寫。
- 該腳本預設模式會先刪除並重建分類節點，**不可**用於每日流程；每日流程一律使用 `--no-clean`。

## Phase 2：五種原子操作與軟到期
Neo4j 訂閱器對每筆 document 事件套用：

1. **ADD_ENTITY／UPDATE_ENTITY**：MERGE，補 `valid_from`、清除 `valid_to`。
2. **ADD_RELATIONSHIP**：`CREATED` 關係補 `valid_from`、清除 `valid_to`。
3. **EXPIRE_RELATIONSHIP**：作品的藝術家名單改變時，不再列出的舊 `CREATED` 關係設 `valid_to`（不刪除）；**新名單為空時不動**，避免來源暫時缺欄位就讓作者資訊全數到期。
4. **SOFT_DELETE**：作品設 `is_deleted`／`deleted_at`／`valid_to`；同 id 再次 upsert 會重新啟用。
5. **保留期清理**：`python -m subscribers purge-neo4j --days 30 [--apply]`（預設預覽）只刪除到期或軟刪除**超過 30 天**的關係與作品，以及因此孤立的藝術家；已納入每日流程。

**檢索端過濾**：RAG 後端 4 段圖查詢（`GraphOnlyRAG`、`AdvancedGraphRAG` 各兩段）排除軟刪除的作品與已到期的關係，否則「到期」只是標記、仍會被查出來。

**實測**（真實 Neo4j 與後端，合成資料 `zz_lc_1`，測後清除、節點數維持 7,468）：新增後欄位與關係正確且檢索端查得到 → 藝術家改變後舊關係到期但未刪除 → 空名單不誤傷 → 軟刪除後檢索端查不到 → 同 id 再 upsert 重新啟用 → 資料改成 40 天前後，清理預覽只涵蓋合成資料，套用後清除。目前真實資料的清理預覽為 0／0／0。

## 仍未處理
- 舊資料（補登前）沒有 `valid_from`；到期判斷只看 `valid_to`，不受影響。
- 974 個 Artist 沒有 `source`（舊資料）。
- V&A 302 件中 157 件沒有豐富關係（來源資料缺欄位）。
- Neo4j 仍綁 `0.0.0.0`（改綁本機會讓 Windows 端的 Neo4j Browser 連不上）。
- 訂閱器的 ADD／EXPIRE 關係目前只處理 `CREATED`；分類關係（`HELD_BY` 等）由分類腳本疊加產生，作品內容改變時不會自動到期舊的分類關係。
