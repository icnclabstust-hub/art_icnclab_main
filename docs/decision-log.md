# 決策日記

> 記錄「為什麼這樣決定」，讓之後的人（包含未來的自己）不必重新查證。每筆含日期、決定、依據、影響與待決定事項；新的放最上面。
> 格式沿用 `docs/2026-09-20-infra-remediation-plan.md` §6 的「已決定／待決定」。

---

## 2026-09-21　Yale 館藏來源：停止爬取，並評估恢復方式

### 已決定
| 項目 | 決定 | 決定者 |
|---|---|---|
| 夜間流程對 Yale 的爬取與攝取 | **停止**（commit `dea3969`）；**同日修好 403 後已恢復**，見下方「已執行」 | 使用者 |
| 既有 Yale 資料（Neo4j 約 281 件及 catalog／ChromaDB／Elasticsearch 對應內容） | **保留，不刪除**；一致性驗證仍涵蓋 | 使用者（「刪除 Yale API」解讀為停止呼叫，未要求刪資料） |
| 爬蟲檔 `crawlers/yale-university-art-gallery-crawler.js` 與攝取設定 | **保留**，恢復只需把 Yale 加回 `daily_crawl_and_sync_catalog.sh` 的爬蟲與攝取兩處清單 | 使用者 |

### 依據（2026-09-21 實測）
- Yale 是資料來源（Yale University Art Gallery，LUX API：`lux.collections.yale.edu`），不是我們的資料庫。
- 每次搜尋回 HTTP 403，回應來自 CloudFront。**原因是 User-Agent，不是被禁止爬取**：

  | User-Agent | 結果 |
  |---|---|
  | curl／python-requests／axios（我們爬蟲的預設） | 403 |
  | 自我識別的 UA（含專案名與聯絡信箱） | 200 |
  | luxy 自帶的 UA | 200 |

- `robots.txt` 只禁止 `/view/results/`，`/api/` 未被禁止。
- 爬蟲的兩處 axios 請求（第 113、128 行）沒有設標頭，所以被擋。

### 對 luxy 套件的掃描結論（https://pypi.org/project/luxy/ ，0.0.8，2026-04-16）
- 來源為 Yale LUX 專案的 GitHub 組織 `project-lux`，Apache 授權；原始碼壓縮檔 SHA256 與 PyPI 公布值一致。
- 依賴只有 `requests`；`setup.py` 為標準寫法；靜態掃描無 `eval`／`exec`／`subprocess`／`pickle`／`socket`／base64；連線位址只有 `lux.collections.yale.edu`。→ **安全，可用**。
- 但**不是修復 403 的必要條件**：修法只需在現有爬蟲加一個識別 UA。luxy 回傳原始 Linked Art JSON，與我們攝取層吃的扁平格式（`id/title/artist/date/…`）不同，需另寫轉接層，且多一個 Python 依賴。

### 使用者選擇：方案 A（2026-09-21）
只在現有爬蟲的兩處 axios 請求加上識別 UA（`art-history-research (+mailto:icnclab.stust@gmail.com)`，不偽裝成瀏覽器；請求間隔沿用爬蟲既有的 200／800 毫秒）。不引入 luxy；方案 B（改用 luxy＋轉接層）不採用，日後若要做「按館藏、材質篩選」的查詢再評估。

### 方案 A 的驗證結果
| 步驟 | 結果 |
|---|---|
| 單獨執行爬蟲 | 0 次 403，收集 280 件，輸出格式不變 |
| `ingest run --dry-run` | 新增 4／變更 22／未變 254／隔離 0／移除 0／事件 0 |
| 22 件「變更」的原因 | 主要是 `artist` 字串順序（14 件，例：舊 `attributed to: Ugolino di Nerio, Artist`，新 `Artist, attributed to: Ugolino di Nerio`）；另有 description 5、culture 2、title 1。舊值是先前補登時由 Neo4j 節點重建（以逗號拆開再合併，順序被打亂），新值忠於來源，屬預期差異 |
| catalog 有、本次爬取沒有 | 5 件；本爬蟲是按關鍵字取樣而非完整快照，不代表來源已移除，**Yale 不可使用 `--prune`** |

### 已執行（2026-09-21，使用者同意「要」）
1. **套用攝取**：新增 4／變更 22／未變 254，產生 48 個事件；ChromaDB、Elasticsearch 各處理 22 筆、Neo4j 26 筆，三個游標落後皆為 0；規則式分類（疊加）已補跑。
2. **驗證**：`ingest verify --es`：ChromaDB 與 Elasticsearch 皆 catalog 348／檢索庫 348，結果「一致」。Neo4j：Yale 作品 281→285（0 軟刪除）、`CREATED` 關係 336（0 到期），藝術家 2,915→2,917 且全部有 `sources`（首次真實增量驗證了 `Artist.sources` 會自動更新）。
3. **加回夜間流程**：`daily_crawl_and_sync_catalog.sh` 的爬蟲與攝取清單已恢復 Yale。**仍不可對 Yale 使用 `--prune`**。

### 夜間流程實跑驗證（2026-09-21 10:58，使用者要求先驗證）
用夜間腳本的**真實程式路徑**（同一份腳本、同一個 `crawl` 函式與 nvm node 24 環境）跑一次，只把爬蟲與攝取清單縮成 Yale，其餘步驟（三個訂閱器、分類、30 天清理、11 個來源一致性驗證、清快取）照常；備份兩步驟不在驗證範圍，暫時移除；暫存腳本已刪除。

| 步驟 | 結果 |
|---|---|
| 爬蟲 Yale | ✅ 155 秒，收集 280 件，0 次 403 |
| 攝取 | ✅ 新增 0／變更 0／未變 280（與稍早套用的結果完全一致，證明攝取具冪等性） |
| 訂閱器 ChromaDB／Elasticsearch／Neo4j | ✅ 各處理 0 筆，落後 0 |
| 分類、30 天清理 | ✅ |
| 11 個來源一致性驗證 | ✅ 全部「一致」 |

**未涵蓋**：完整 10 個來源同時爬取（本次只跑 Yale，避免重複打其他來源的 API）、備份步驟（不受這次改動影響，前一輪已驗證）。明晚 03:00 是完整流程的第一次含 Yale 實跑；若 LUX 再回 403，先檢查 `REQUEST_HEADERS` 的 UA 是否被列入封鎖。

### 影響
- Yale 已恢復每晚爬取與攝取；新增 4 件作品，22 件的藝術家字串等欄位更正為忠於來源的版本。
- 相關紀錄：`docs/reports/2026-09-21-neo4j-status.md` 第四節。
