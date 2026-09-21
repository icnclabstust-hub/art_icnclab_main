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

### 待決定（尚未選擇，**不要當成已決定**）
| 方案 | 內容 | 建議 |
|---|---|---|
| **A** | 只在現有爬蟲兩處 axios 請求加識別 UA（寫明專案名與聯絡信箱，不偽裝成瀏覽器）；單獨跑一次確認 403 消失、格式不變；用 `ingest run` 預覽確認 281 件既有資料判為「未變」後，再決定是否加回夜間流程 | ✅ 建議：一行修正、無新依賴、不改資料格式 |
| **B** | 改用 luxy，另寫小轉接程式把輸出轉成現有格式 | 工作量較大；日後若要做「按館藏、材質篩選」的查詢再考慮 |

- 選 A 或 B 之前，需使用者確認：UA 說明文字會帶 `icnclab.stust@gmail.com`，會出現在耶魯的請求紀錄中。
- 無論選哪個，請求間隔沿用既有 `STEP_PAUSE_SECONDS`，對耶魯保持友善。

### 影響
- 夜間流程不再每晚固定失敗一次（原本 Yale 攝取因無資料檔而 ❌）。
- 已收進來的 Yale 作品仍可被檢索；只是不再有新作品進來。
- 相關紀錄：`docs/reports/2026-09-21-neo4j-status.md` 第四節。
