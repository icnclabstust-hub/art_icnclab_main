# Neo4j 補強執行紀錄（2026-09-21）

> 依 2026-09-21 對專案 Neo4j（7,458 節點）的檢查所列項目逐一處理；設計依據：`docs/designs/2026-09-20-target-architecture-consistency-eval-faithfulness.md` Phase 2。

| # | 項目 | 結果 |
|---|---|---|
| 1 | 唯一性約束（`Artwork.id`、`Artist.name`） | ✅ 已建立並確認 ONLINE；訂閱器啟動時自動確保。曾嘗試改綁 `127.0.0.1`，因 Java 預設的 IPv6 雙堆疊 socket 不被 WSL 轉發而還原；已於文末更新以純 IPv4 解決 |
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
- V&A 302 件中 157 件沒有豐富關係（來源資料缺欄位）。
- 訂閱器的 ADD／EXPIRE 關係目前只處理 `CREATED`；分類關係（`HELD_BY` 等）由分類腳本疊加產生，作品內容改變時不會自動到期舊的分類關係。

## 更新：Artist 來源與 Neo4j 綁定（2026-09-21）

### 一、Artist 沒有 `source`（973 個）
- **根因**：不是舊資料，而是**寫入路徑的缺口**。Europeana 的藝術家 Cypher（`_EUROPEANA_ARTIST_QUERY`）從來不設 `Artist.source`，而其他館藏走舊匯入腳本的 `SET artist.source = coalesce(artist.source, row.source)`。所以只要每日流程繼續匯入 Europeana，缺口就會持續增加，單純「補一次舊資料」不夠。
- **單值 `source` 在邏輯上不對**：一位藝術家可以同時出現在多個館藏（59 位兩個來源、14 位三個以上，如梵谷橫跨 Cleveland／Yale／Europeana），`coalesce` 只記下第一個看到的來源。實測還有一位（Vincent van Gogh）的舊 `source` 是 `met_museum`，但他已沒有任何現存的 Met 作品，舊值是過時的。
- **確認沒有讀取端依賴**：檢索端的圖查詢完全不讀 `Artist.source`，所以改成清單不影響任何查詢。
- **做法（與動態資料庫一致）**：新增 `Artist.sources`（清單，排序後去重），**由現存作品推導**——只算 `CREATED` 關係未到期（`valid_to IS NULL`）且作品未軟刪除的來源。Neo4j 訂閱器每批事件寫完後，只對「本批新增、更新、軟刪除的作品所連到的藝術家」重算；因此新資料進來、作者更正、關係到期、作品軟刪除，都會自動反映，不需要人工維護，也不必知道是哪個來源的寫入路徑。舊 `source` 只在為空時補上第一個來源，維持相容，不再當作判斷依據。
- **一次性補齊舊資料**：`python -m subscribers refresh-artist-sources`（可重複執行、只寫推導欄位）。實測 2,915 位藝術家全部有 `sources`（1 個來源 2,842、2 個 59、3 個 11、4 個 2、5 個 1），0 位為空。
- **保留期清理不受影響**：`purge` 只刪除到期超過 30 天的關係與孤立藝術家；來源在到期當下已重算過。
- **測試**：新增「每批最後重算所有受影響作品的藝術家」「只算現存作品」「舊 `source` 只作備援」「全量重算回傳處理數」四個測試；全部 84 通過、2 略過。

### 二、Neo4j 綁定 `0.0.0.0`
- **先前判斷不完整**：先前把「只綁 127.0.0.1」失敗歸因於 WSL 不轉發本機綁定；實測發現轉發器**只認純 IPv4 的 socket**。Java 預設建立的是 IPv6 雙堆疊 socket，綁 `127.0.0.1` 時會顯示成 `[::ffff:127.0.0.1]`，因此不被轉發；綁 `0.0.0.0` 則因為是萬用位址而被轉發。
- **做法**：`neo4j.conf` 改為 `server.bolt.listen_address=127.0.0.1:7687`、`server.http.listen_address=127.0.0.1:7474`，並加上 `server.jvm.additional=-Djava.net.preferIPv4Stack=true` 讓 Neo4j 只用純 IPv4。
- **驗證**：`ss` 顯示 `127.0.0.1:7474`、`127.0.0.1:7687`；Windows 端 `localhost:7474` 回 200、`Test-NetConnection localhost -Port 7687` 為 True；RAG 後端健康檢查 Neo4j 為 true。Windows 的 Neo4j Browser 仍可連上，同時 Neo4j 不再監聽所有網卡。
- **限制**：設定檔位於 Neo4j 安裝目錄（`/home/user/neo4j-community-2026.06.0/conf/neo4j.conf`），不在 repo 內；還原點為同目錄的 `neo4j.conf.bak-ipv4-*`。若重裝 Neo4j 需重新套用這三行。備份腳本（停止→dump→重啟）沿用同一份設定，不受影響。

### 三、Artist.sources 的動態資料庫、召回率與線上服務檢視（2026-09-21）
- **動態寫入**：重算是「重新計算」而非「累加」，重送事件（至少一次語意）結果相同；重算與寫入失敗會使該批事件整批重試，游標不前進。實測 500 件作品的重算 1.1 秒、全量重算（2,915 位）0.5 秒；最大的樞紐藝術家（`Unknown Artist`，353 件作品）不成問題。全量重算只在一次性補齊時使用，**請勿與每日流程同時執行**（同時寫同一批節點可能死結，後果是該批事件重試，不會壞資料）。
- **召回率**：全文索引只涵蓋 `Artist.name`，不含來源欄位，檢索命中與排序不受影響。但發現一個**真實的副作用**：`GraphOnlyRAG._format_graph_node` 會把節點的**所有屬性**寫進給模型的文字，因此線上原本就會輸出 `source: met_museum`（梵谷已無 Met 作品，屬過時資訊，可能被模型當成事實引用），Phase 2 新增的 `valid_from` 等生命週期欄位與新的 `sources` 也會一併輸出。已修正為：生命週期欄位不輸出；已有 `sources` 時不輸出舊的單值 `source`。修正前後以同一個查詢（`graph_only`、「Vincent van Gogh」）比對，前者含過時的 `source: met_museum`，後者只留 `sources`，關係列表不變（前 5 筆一致）。
- **線上服務**：來源重算與綁定變更不需要停機；只有讀取端程式碼要重啟 RAG 後端才會生效，實測從關閉到 `/health` 回報 healthy 約 10 秒，未觸及每日流程。每晚備份（`backup_neo4j.sh`）仍會讓 Neo4j 停約 1 分鐘，這段時間圖檢索會失敗，屬既有限制。
- **待觀察**：第一次完整夜間流程（2026-09-21 03:00 起）會是重算在真實增量下的首次驗證，跑完後應確認新進藝術家都有 `sources`。
- **資安提醒（已處理）**：RAG 後端原本由 `Start-NativeServices.ps1` 以命令列環境變數帶入 `NEO4J_PASSWORD`、`ES_PASSWORD`，同機任何使用者用 `ps` 都看得到明文。現在啟動指令只帶 `ENV_FILE=<.env 路徑>`，後端自己用 python-dotenv 讀取（已存在的環境變數優先，不會被 `.env` 內的舊值覆蓋）；重啟後 `ps` 看不到任何密碼，`/health` 為 healthy，`hybrid_es_rag`（需要 ES 密碼）檢索回傳 3 筆。`.env.example` 補上 `ES_PASSWORD` 佔位符。曾在 `ps` 輸出中出現過的 ES 密碼仍建議更換。

### 四、停止爬取 Yale（2026-09-21）
Yale University Art Gallery 的 API（`lux.collections.yale.edu`）對爬蟲的每次搜尋都回 HTTP 403，夜間流程每晚固定失敗一次且沒有新資料。已從 `daily_crawl_and_sync_catalog.sh` 的爬蟲與攝取清單移除；**既有 Yale 資料（Neo4j 約 281 件）保留在 catalog 與三庫，不刪除**，一致性驗證仍涵蓋它。爬蟲檔 `crawlers/yale-university-art-gallery-crawler.js` 與攝取設定保留，要恢復只需把 Yale 加回兩處清單。403 的確切原因未查明。

**後續（同日）**：403 原因是 CloudFront 擋掉預設的程式庫 User-Agent（axios／curl／python-requests），改用自我識別的 UA 後爬蟲回復（280 件、0 次 403）。已套用攝取（新增 4、變更 22）並同步三庫，一致性驗證通過，Yale 已加回夜間流程。詳見 `docs/decision-log.md`。

**再後續（2026-09-23）**：使用者決定完全移除 Yale，含既有資料。已透過 outbox 的 soft_delete 機制撤出，crawler 檔案與 catalog／ingest 註冊皆已刪除；細節見 `docs/decision-log.md` 2026-09-23 條目。
