# 設計文件：收藏機構上下文標示（P1-4a）與 MET 輪替擴充（方案 C）

> 狀態：**草案**（GD 步驟 3）。風險 Tier：**B**（art_icnclab RAG 服務，見 CODE_REVIEW_STANDARD §2）——**實作前須老師核可**。
> GD 步驟 1 的 13 個選項，使用者於 2026-10-07 回覆「兩項都依建議」，逐項採用見 §2 與 §9。
> 兩項合併成一份文件：都改動「資料進入系統→提供給模型」這一段，且都會影響黃金集基準（路線圖 R2）。
> 評估表：`2026-10-07-institution-context-and-met-rotation-assessment.md`。

## 1. 背景與問題

- **機構**：問「大都會收藏了哪些維梅爾」時，所有策略都找不到 MET 的作品，llama3.1:8b 還把 Rijksmuseum 的作品說成大都會的。提示詞規則（commit `50204ee`）讓模型改說「沒有找到」，但仍答不出來。
- **MET 覆蓋**：MET 是巴洛克主力來源（黃金集候選 39%、關係題相關文件 86%），符合條件的作品約 46,000 件，只收錄 1,329 件；舊爬蟲每晚抓回同一批（兩週新增 4 件）。

**誰會用**：Open WebUI 使用者、論文的檢索評估。**不做會怎樣**：「某館有什麼」答不出來或答錯；關係題召回受限於收錄範圍。

## 2. 目標與非目標

- 目標：
  1. **4a**：提供給 LLM 的上下文，每份文件標出「收藏機構」的英文正式名稱（決策 1、3）。
  2. **C**：MET 每晚抓 200 件**尚未收錄**、屬研究主題四個部門的作品，總數達 5,000 件即停（決策 1～4）。
- 非目標：
  - **4b** 依機構過濾或加權、從問題自動判斷機構（RET-01 不自動判斷；另案，看 4a 效果再議）。
  - 中文館名別名表（留給 4b，決策 3）；Europeana 207 個第三方機構名稱正規化（決策 4）。
  - 改動現行「每部門前 15 件」爬蟲（決策 6：保留，用來追蹤修訂與下架）。
  - 重新嵌入任何既有文件（決策 2）。

## 3. 現況與重用（2026-10-07 查證）

| 項目 | 現況 | 本設計如何用 |
|---|---|---|
| 機構資訊 | **已全部存在 catalog**：博物館來源由 `source` 決定；`europeana` 的 `provider` 987/987；`specialized_art` 把 provider 存在 **`department`**（Europeana 來源 552/552、MET 來源 345/345 為 Metropolitan Museum of Art） | 直接讀取，不補資料 |
| ⚠ 更正 | 10-03 記錄的「Europeana 來源只有 64% 可依機構過濾」「須修爬蟲補 provider」**不成立**（當時只查了 `provider` 欄） | 決策 5「修爬蟲補 provider」因此不需要 |
| 上下文格式 | `_format_context` 只輸出 `[文檔 i] 來源: met_museum` | 改這一處 |
| ChromaDB／ES metadata | 沒有機構欄位 | 4a 不改（避免重新嵌入）；4b 再處理 |
| MET API | `/v1/objects?departmentIds=` 列出部門全部 id；`/v1.1/search` 分頁；`/v1/objects/{id}` 取詳情 | 輪替用列舉＋詳情 |
| 攝取 | `ingest run --source met_museum --file <檔>` 可指定檔案；雜湊比對、冪等 | 輪替檔另走一次攝取 |
| 爬蟲產出告警 | P0-2 的 `check-crawl`（待提交） | 輪替爬蟲也掛上 |

## 4. 方案比較

### 4.1 4a：機構從哪裡來

| | 方案 A：查詢時從 catalog 讀（**選定**） | 方案 B：攝取時寫入檢索庫 metadata |
|---|---|---|
| 做法 | 生成前以本次 5 筆的 `doc_id` 查一次 catalog，依 §5.1 規則推出機構，寫進上下文 | `artwork.institution` 寫進 catalog 與 Chroma／ES metadata，上下文直接讀 |
| 優點 | 不動資料、不重新嵌入；規則改了立即生效 | 4b 過濾可直接用；查詢路徑不多一次 DB 查詢 |
| 缺點 | 每次查詢多一次 PostgreSQL 查詢（5 筆主鍵，預估 <5 ms）；DB 異常時需降級 | `content_hash` 涵蓋整個 artwork，**全部約 4,500 份文件判為變更、6,300 個 chunk 重新嵌入**，違反決策 2；語料在基準前大幅變動 |
| 成本 | 約 40 行＋測試 | 約 80 行＋全量重嵌（估 1 小時以上）＋基準需重做 |

**選定 A**：決策 2 要求不重新嵌入；機構資訊本來就在 catalog，問題只在沒被送到模型面前。4b 若需要檢索庫 metadata，屆時以 Chroma `update(metadatas=)` 回填（不重算向量）另行設計。

### 4.2 C：輪替怎麼選下一批

| | 方案 A：列舉部門全部 id，扣除已收錄（**選定**） | 方案 B：搜尋 API 的 offset 逐頁往後 |
|---|---|---|
| 做法 | `/v1/objects?departmentIds=` 取全部 id → 扣掉 catalog 已有的 `met_*` → 依 objectID 遞增取前 200 → 逐件取詳情，無圖片者略過 | 記錄每部門游標，`/v1.1/search?offset=` 往後取 |
| 優點 | 不需保存游標；不重複、不漏；中斷後自動續跑 | 搜尋已帶 `hasImages`，不浪費詳情請求 |
| 缺點 | 列舉結果含無圖片作品，需取詳情後才知道（浪費部分請求） | 搜尋排序可能變動（10-03 換版即發生），游標會重複或漏抓；需新增狀態儲存 |
| 成本 | 約 120 行（新爬蟲）＋夜間腳本 3 行 | 約 120 行＋游標表 |

**選定 A**（決策 2）：10-03 的事件證明搜尋排序不可靠；以 catalog 為唯一真相源（DAT-01）推算「下一批」，不需另存狀態。

## 5. 系統設計

### 5.1 4a 機構推導規則（依序，第一個有值者）
1. `source` 為博物館：`met_museum`→The Metropolitan Museum of Art、`art_institute_chicago`→Art Institute of Chicago、`cleveland_museum`→Cleveland Museum of Art、`harvard`→Harvard Art Museums、`va_museum`→Victoria and Albert Museum（固定對照表）。
2. `europeana`：`artwork.provider`。
3. `specialized_art`：`artwork.department`（爬蟲存放 provider 的位置）。
4. 其餘（`google_books`、`wikipedia_pilot`、`masterpieces_curated`）：不標（它們不是館藏紀錄）。

上下文格式：`[文檔 1] 來源: met_museum｜收藏機構: The Metropolitan Museum of Art`。
限制：Europeana 的 provider 有時是**彙整平台**而非實際收藏館（例：Swedish Open Cultural Heritage）；照原樣標示，不另判斷（決策 4）。

### 5.2 C 資料流
```
夜間流程（MET 爬蟲之後、攝取之前）
  met-rotation 爬蟲：
    讀 catalog 已有 met_* id（唯讀）
    → /v1/objects?departmentIds=11,9,12,15（European Paintings、Drawings and Prints、
       European Sculpture and Decorative Arts、Robert Lehman；部門 id 實作時以 API 確認）
    → 扣除已收錄 → objectID 遞增取 200 → 逐件 /v1/objects/{id}（間隔 1 秒，無圖片略過）
    → crawlers/data/raw/met_rotation/met_rotation_<時間>.json（格式同 met_museum）
  ingest run --source met_museum --file <該檔>
  ingest check-crawl --name "MET rotation" --dir .../met_rotation --since <開始時間>
停止條件：catalog 的 met_museum 文件數 ≥ 5,000 → 爬蟲直接結束（不算失敗）
啟用開關：.env 的 MET_ROTATION_ENABLED（預設 false；黃金集基準完成後才改 true，決策 5）
```

### 5.3 對外介面
- 無新 API、port。新增 CLI：`node crawlers/met-rotation-crawler.js`；新增設定 `MET_ROTATION_ENABLED`、`MET_ROTATION_PER_NIGHT`（200）、`MET_ROTATION_CAP`（5000）。

### 5.4 Schema
- 無變更。

### 5.5 錯誤處理
- 4a：catalog 查詢失敗或逾時 → 退回只顯示「來源」（現行格式），記 warning，**不影響回答**。
- C：列舉或詳情失敗 → 該件略過；整批 0 件 → `check-crawl` 開 critical（沿用 P0-2）。MET 限流（403／429）→ 停止本次、隔晚續跑（catalog 推算，不會重複）。

## 6. 安全與隱私考量

- 4a 只多讀 catalog 的公開館藏欄位，不涉個資；上下文新增的是館名字串，沿用既有的提示注入掃描（機構名稱來自外部 API，視為資料不當指令）。
- C 對外呼叫僅 MET 公開 API，沿用識別 UA（`art-history-research (+mailto:…)`）與 1 秒間隔；不送任何使用者資料出境。

## 7. 測試策略

- 單元：機構推導規則（五個博物館、europeana、specialized、無機構來源）；上下文格式；DB 失敗降級。輪替：扣除已收錄、遞增取 N、達上限停止、無圖片略過（以假 API 回應測）。
- 整合：拋棄式 PostgreSQL 驗證 catalog 讀取；`--dry-run` 跑一次輪替只列出將抓的 id。
- 驗收（決策 6、7）：
  - 4a：新增 5～8 題「機構題」（MET、AIC、Cleveland、Rijksmuseum、無此館），llama3.1:8b@hybrid 錯誤歸屬 = 0；黃金集 15 題回歸不退步。
  - C：關係題召回不退步（以黃金集量測 `evalrun` 比較基準）；前 10 筆中與題目無關來源的比例不增加；夜間流程增加 ≤ 10 分鐘。

## 8. 部署與運維

- 4a：改 `unified_rag_manager_v2.py` 後依流程 F 重啟 rag-manager-v2（約 10 秒）。回滾：`git revert` 後重啟。
- C：新增爬蟲檔與夜間腳本 3 行，`MET_ROTATION_ENABLED=false` 時完全不執行。回滾：開關改回 false；已收錄的作品以 `ingest run --prune` 不適用（MET 非完整快照），如需撤出另以 catalog 軟刪除（依 external_id 清單）處理。
- 監控：`crawl_output`（P0-2）、`eval_regression`（Phase 3 量測）。

## 9. 未解決問題

1. **10-03 新增的非巴洛克 MET 作品**（決策 1 的連帶）：現行「每部門前 15 件」爬蟲（決策 6 保留）每晚仍抓 19 個部門，只刪不改會被抓回。建議：**不刪**，基準建立後以量測判斷雜訊是否造成退步，再決定是否把現行爬蟲也限縮到主題部門。
2. `/v1/objects?departmentIds=` 回傳的是全部作品（含無圖片），Drawings and Prints 可能有數萬件；「依 objectID 遞增」會先抓到年代較早編號者，不保證是巴洛克。是否改為以 `/v1.1/search?departmentId=&hasImages=true&q=*` 列舉（待實作時驗證 `q=*` 是否可用）。
3. 機構題小題組的題目由誰出（建議：使用者出題，AI 依 catalog 確認答案）。
