# 決策日記

> 記錄「為什麼這樣決定」，讓之後的人（包含未來的自己）不必重新查證。每筆含日期、決定、依據、影響與待決定事項；新的放最上面。
> 格式沿用 `docs/2026-09-20-infra-remediation-plan.md` §6 的「已決定／待決定」。

---

## 2026-09-21　Yale 館藏來源：停止爬取，並評估恢復方式

### 已決定
| 項目 | 決定 | 決定者 |
|---|---|---|
| 夜間流程對 Yale 的爬取與攝取 | **停止**（自 2026-09-21 起，commit `dea3969`） | 使用者 |
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

### 尚未做（待使用者決定）
- 是否實際套用這次攝取（新增 4、變更 22）。變更會重寫這 22 件的 chunk 並經 outbox 同步三庫；Neo4j 端藝術家名單以逗號拆開，順序改變不會產生新的藝術家，關係不會變動。
- 是否把 Yale 加回 `daily_crawl_and_sync_catalog.sh` 的爬蟲與攝取兩處清單。

### 影響
- 目前夜間流程仍不含 Yale（不再每晚固定失敗一次）；已收進來的 Yale 作品仍可被檢索，只是尚無新作品進來。爬蟲本身已修好，隨時可加回。
- 相關紀錄：`docs/reports/2026-09-21-neo4j-status.md` 第四節。
