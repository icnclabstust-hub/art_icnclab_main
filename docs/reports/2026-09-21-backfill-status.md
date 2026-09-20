# 舊資料補登（backfill）執行紀錄（2026-09-21）

> 設計：`docs/designs/2026-09-20-phase1-catalog-ingestion.md`（擴充：讓 catalog 涵蓋既有檢索庫的全部資料）

## 問題
catalog 只涵蓋這次重新爬取的資料：ChromaDB／ES 共 5,799 個 chunk，catalog 僅 4,267（26% 不在 catalog）；Neo4j Artwork 3,938 個，catalog 文件僅 3,281。Yale 因來源端 403 無法重爬，只能從既有資料補登。

## 做法
`python -m ingest backfill [--source S] [--apply]`（預設只預覽）：
- 由 ChromaDB 讀出 catalog 不認得的 chunk（依 `parent_id` 分組成文件），由 Neo4j 讀出 Artwork 節點屬性與 `CREATED` 關係的藝術家，重建與 `normalize_*` 相同形狀的作品 dict。
- 只寫 catalog（`metadata.backfill.origin` 標記來源），**不寫 outbox 事件**（各庫本來就有）、**不覆蓋任何既有 catalog 列**；雜湊規則與正式攝取相同，之後同一筆資料重新爬到且內容相同會判定「未變」。
- 掃描器命中的文件依政策補登為隔離並寫 soft_delete 事件撤出各庫（本次 0 筆）。

## 過程中修正的問題
- 預覽時掃描器唯一一次命中是 Yale 的 chunk，原因是文字含**軟連字號（U+00AD）**，屬正常排版字元 → 掃描器的「隱藏字元」規則原本把整類格式控制字元（Cf）都算可疑，會誤殺正常的多語系資料。已收斂為只標記能藏指令或欺騙顯示的字元（零寬空格、字詞連接符、雙向覆寫／隔離、Unicode 標籤字元），並允許軟連字號、ZWNJ／ZWJ、LRM／RLM；補了正反向測試。

## 結果
補登前先備份（`~/backups/postgres/art_history_db_20260921_014803.dump`）。補登 **670 份文件／1,476 個 chunk**，0 隔離、0 事件：

| 來源 | 文件 | chunk |
|---|---|---|
| yale_university_art_gallery | 281 | 344 |
| wikipedia_pilot | 14 | 741 |
| harvard | 99 | 74 |
| europeana | 74 | 82 |
| specialized_art | 60 | 76 |
| met_museum | 51 | 47 |
| cleveland_museum | 27 | 52 |
| google_books | 20 | 20 |
| masterpieces_curated | 15 | 15 |
| va_museum | 15 | 12 |
| art_institute_chicago | 14 | 13 |

補登後：catalog 文件 3,951（＝Neo4j Artwork 3,937，另 wikipedia_pilot 14 份無圖節點）、chunk 5,743。再以排程相同方式執行完整流程：8 個來源全部「未變」、0 事件、三個訂閱器落後 0。

## 仍未處理
- **56 個過時 chunk**：ChromaDB／ES 有、catalog 沒有，且其文件已在 catalog（更早的切塊方式殘留：specialized_art 48、europeana 4、met_museum 2、art_institute_chicago 2）。內容與現行版本重複或過時，建議從兩庫刪除，但屬刪除線上資料，需另行確認。
- **1 個 Neo4j Artwork 節點沒有 `source`**（無法判斷來源，未補登）。
- `wikipedia_pilot`（14 份文件、741 chunk）沒有來源介面卡與圖節點，是試驗性資料，目前只登記在 catalog。

## 回滾
```sql
-- 只移除補登的資料（chunk 會隨文件連鎖刪除）
DELETE FROM catalog.documents WHERE metadata ? 'backfill';
```

## 更新：過時 chunk 已撤出，四個資料庫完全一致（2026-09-21）

- **56 個過時 chunk**（`specialized_art` 48、`europeana` 4、`met_museum` 2、`art_institute_chicago` 2）是同一份文件舊的切塊方式留下的重複內容（例如 `met_438427` 過去切成 `_chunk0`／`_chunk1`，現在是單一 chunk），現行版本都在 catalog。
- 透過正式流程撤出：`python -m ingest retire-stale`（預設預覽，`--apply` 才寫入）對每個 chunk 寫一筆 `soft_delete` 事件（`reason: stale_chunk`），再由 ChromaDB 與 Elasticsearch 訂閱器刪除；執行前先備份（`art_history_db_20260921_015239.dump`）。
- **結果**：ChromaDB 5,743、Elasticsearch 5,743、catalog chunk 5,743，三者相同；`python -m ingest verify --es` 對 11 個來源全部回報「一致」；Neo4j Artwork 與 catalog 文件逐來源相同（wikipedia_pilot 無圖節點）。再預覽過時 chunk 為 0。
- 每日流程的驗證步驟現在涵蓋全部 11 個來源；今後若回報「不一致」代表出現新的漂移。
- **仍未處理**：1 個沒有 `source` 的 Neo4j Artwork 節點（無法判斷來源）；`wikipedia_pilot` 沒有來源介面卡與圖節點。
