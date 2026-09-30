# 決策日記

> 記錄「為什麼這樣決定」，讓之後的人（包含未來的自己）不必重新查證。每筆含日期、決定、依據、影響與待決定事項；新的放最上面。
> 格式沿用 `docs/2026-09-20-infra-remediation-plan.md` §6 的「已決定／待決定」。

---

## 2026-10-01　系統級三路 RRF：新增 4 個策略，與舊 11 個並存（RET-01～07）

### 背景
Phase 5 主幹：向量／全文／圖三路檢索後以 RRF 融合。Phase 5 決策 #3 取消「與舊 11 個策略 id 並存觀察期」，照字面做會讓 Open WebUI 11 支 pipe 與 24 組合評測腳本失效。使用者要求先做比較（兩案表格見本日對話），**選定方案 A**。

### 已決定
| 項目 | 決定 | 決定者 |
|---|---|---|
| 新舊策略 | **方案 A：新增 `vector`／`fulltext`／`graph`／`hybrid`，舊 11 個 id 保留**。舊策略當黃金集基準比較的對照組；比較完成、確認 `hybrid` 不劣於舊策略後，另開 commit 移除 | 使用者，2026-10-01 |
| 決策 #3 的解讀 | #3 取消的是「自動路由（`auto`）與舊 id 並存觀察」那套方案；保留舊 id 作為**量測對照組**不在 #3 範圍內 | 使用者選方案 A 時一併確認 |
| 融合粒度 | 以**文件**對齊（Chroma／ES `parent_id` ＝ Neo4j Artwork `id`），同一文件多個 chunk 在同一路只計最前名次；與召回率粒度 EVL-05 一致 | AI 依規格判斷 |
| 參數 | `RRF_K`=60、`HYBRID_TOP_K`=20、`HYBRID_ROUTES`=`vector,fulltext,graph`（環境變數，可逐路關閉） | 依規格 RET-03／04／07 預設值 |
| 預設策略 | `/api/v1/query` 只給模型名稱（不帶 `@策略`，原本回 400）時採 `hybrid`；`/api/v1/retrieve` 保留「單給策略名」的舊行為，非策略名時才採 `hybrid` | AI 判斷：不改變任何既有可用請求的行為 |
| 重排 | 不做（RET-05／06：先取得基準） | 既有決策 #2 |

### 執行
- `langchain-rag/retrieval_fusion.py`（新）：`document_key`、`rrf_fuse`（純函式）
- `unified_rag_manager_v2.py`：新增 `FulltextESRAG`（BM25）、`SystemHybridRAG`（三路並行＋RRF，單路失敗時以其餘路融合）；`VectorOnlyRAG` 的 metadata 補 `chunk_id`（只增欄位）；預設策略
- `rag_config.json` 登記 4 個新策略（只加 `rag_strategies`，未加 `model_combinations`，Open WebUI 選單不變）
- 規格：RET-01／02／03／04／07 → ✅；RET-05 → ⚠️（RRF 已做，基準待黃金集）

### 驗證
- `tests/python/test_retrieval_fusion.py` 8 項；全量 98 通過、3 略過
- 實機（2026-10-01 01:31 重啟後端）以 `/api/v1/retrieve` 查「Rembrandt The Night Watch Baroque painting」：四個新策略皆有結果；`hybrid` 第一名 The Night Watch（vector 1、fulltext 1），其餘為 MET 館藏 Rembrandt 作品；`vector_only` 結果與 `vector` 相同（無回歸）；只給模型名稱時走 `hybrid`

### 發現、未處理
- **圖路品質差**：`graph`（即既有 `graph_only`）對每個關鍵詞做模糊比對（`~`），此例 "Watch" 命中 Walsh、Lach 等無關藝術家。RRF 會把它們擠出前 5，暫不影響 `hybrid`，但圖路實際貢獻接近零，需另案改善（與 OPS-06 相關）。
- 三路的 `retrieve` 內部是同步呼叫（Chroma／Neo4j 同步 client），`asyncio.gather` 實際上仍逐路執行；目前延遲可接受（實測約 0.4–0.6 秒，首次向量化暖機另計）。
- 尚未提供 Open WebUI 的 `hybrid` pipe；目前只能透過 API 使用。

---

## 2026-10-01　一致性稽核寫入 `eval.alerts`（DAT-05、EVL-11）

### 背景
架構盤點（2026-09-30）確認：夜間 `ingest verify` 發現不一致時只寫進 log，沒有人會看到（缺陷 B12）。使用者指示依建議順序執行，此為第一步。GD：屬 Phase 3 範圍，適用 2026-09-23 已記載的教師豁免（評估表 §八）。

### 已決定
| 項目 | 決定 | 決定者 |
|---|---|---|
| `eval.alerts` 欄位 | 以 migration 07 **新增** `severity`（info／warning／critical）與 `detail`（JSONB），不改既有欄位；規格 EVL-10、DAT-17、GRD-10 的告警等級之後共用 | AI 依規格判斷（Phase 3 設計「以新增欄位補足」），使用者可提出異議 |
| 告警粒度 | 每個「檢索庫 × 來源」同時只留一筆未處理告警（部分唯一索引）；再次偵測到只更新明細，恢復一致自動填 `resolved_at` | 同上。理由：夜間每天跑，逐日新增會淹沒未處理清單 |
| 欄位對應 | `metric_name = consistency_<chromadb｜elasticsearch>`、`route_id = 來源`、`delta_pct = 差異 id 數 ÷ catalog 應有數 × 100`、`severity = warning` | 同上 |
| 手動執行行為 | `ingest verify` 預設仍唯讀；加 `--record-alerts` 才寫表，夜間流程加上此旗標 | 同上 |

### 執行
- `context/database/07-eval-alerts-severity-and-grants.sql`：新增欄位、檢查約束、部分唯一索引；授予 `art_user` 對 `eval` 的 SELECT／INSERT／UPDATE（原本只有 `catalog`）。2026-10-01 01:2x 以 `postgres` 套用於 `art_history_db`（套用前最近備份：`art_history_db_20260930_033056.dump`）
- `langchain-rag/ingest/alerts.py`（新）、`ingest/__main__.py` 加 `--record-alerts`、`scripts/daily_crawl_and_sync_catalog.sh` 驗證步驟加上旗標
- 規格狀態：DAT-05、EVL-11 → ✅；EVL-10 → ⚠️（目前只有一致性稽核會寫入，量測退步／gate_error／服務異常尚未串接）

### 驗證
- `tests/python/test_alerts_db.py` 6 項（開立、重複更新不重複新增、恢復結案、依庫與來源分開、空 catalog 百分比）；全量 90 通過、3 略過
- 實機以 `art_user` 對 harvard、cleveland_museum 執行 `verify --es --record-alerts`：兩庫皆一致，輸出「告警：chromadb ok／elasticsearch ok」，`eval.alerts` 0 筆（正確，無不一致）

### 未處理
- **EVL-12（告警須被看到）尚未做**：目前要自己查表 `SELECT * FROM eval.alerts WHERE resolved_at IS NULL`；每日彙總呈現給 Operator 另行處理。

---

## 2026-09-28　`.env`（金鑰與密碼）從舊 repo 搬到現行專案根目錄

### 背景
所有 API 金鑰與資料庫密碼只存在 `D:\art_icnclab\.env`，也就是已轉為歷史存檔的舊 repo 資料夾；現行程式在 F 槽，靠兩個工作排程設定 `ART_ENV_FILE` 跨槽指過去。若之後有人把 `D:\art_icnclab` 當舊資料清掉，服務與每日排程會直接啟動失敗。

### 已決定
| 項目 | 決定 | 決定者 |
|---|---|---|
| `.env` 位置 | 搬到專案根目錄 `F:\art_icnclab-main\art_icnclab-main\.env`（WSL：`/mnt/f/art_icnclab-main/art_icnclab-main/.env`） | 使用者，2026-09-28 |

### 執行
- 複製後比對 SHA-256 一致，再刪除 `D:\art_icnclab\.env`；內容未修改
- 工作排程 `ArtHistoryDB-StartServices`、`ArtHistoryDB-DailyCrawl` 的 `ART_ENV_FILE` 改指新位置；觸發條件未動（登入時／每日 03:00）
- `Register-StartupTask.ps1` 用法範例、`Start-NativeServices.ps1` 註解、`collect.sh` 的 `.env` 候選清單同步更新

### 影響
- `.env` 已被 `.gitignore:8` 排除，不會進版控。
- `Start-NativeServices.ps1`／`Run-DailyCrawl.ps1` 未設 `ART_ENV_FILE` 時預設就讀專案根目錄，排程裡的明確指定只是保險。
- `D:\art_icnclab\.env.crawler`（2026-08-13 舊爬蟲設定，可能含金鑰）同日一併搬到 `F:\art_icnclab-main\art_icnclab-main\.env.crawler`，同樣比對 SHA-256 後刪除原檔；已被 `.gitignore:11` 排除。現行排程與程式都沒有引用它，搬移只為讓金鑰集中一處。`D:\art_icnclab` 內已無任何 `.env` 實檔（僅剩範本 `.env.example`）。
- `D:\art_icnclab\.webui_secret_key`（2026-08-17）同日搬到 `F:\art_icnclab-main\art_icnclab-main\.webui_secret_key`，已被 `.gitignore:111` 排除。現行 Open WebUI 由 `Start-NativeServices.ps1` 以 `cd /home/user`、`DATA_DIR=/home/user/openwebui-data` 啟動，用的是 WSL 內的金鑰，不讀這份，搬移不影響登入狀態。至此 `D:\art_icnclab` 已無任何機敏檔。
- 2026-09-29 對照 `D:\art_icnclab` 與本 repo：D 獨有的 127 項中，82 項已搬到新位置（`crawlers/`、`tests/manual/`、`scripts/ops/`、`archive/`），14 項已在 `36e9942`（清 Docker）／`6a063f9`（移除 Yale）刻意刪除，31 項為精整時未帶入的資料與產出物。其中無法重新產生的兩項**複製**（原檔仍留 D 槽）到 `backups/from_D_art_icnclab_2026-09-29/`，逐檔比對 SHA-256 一致，由既有 `.gitignore:110`（`backups/`）排除、不進版控：
  - `db_backups/`：2026-08-17 的 Neo4j／ChromaDB／OpenWebUI 資料目錄封存（216 MB），還原方式見 `scripts/backup_databases.sh` 註解
  - `query_logs/`：2026-07-27～08-17 的使用者查詢抽取紀錄 12 檔（含使用者提問原文，屬使用者資料）
  其餘 29 項（舊爬蟲 JSON、測試／報告輸出、v1 `unified_rag_manager.py` 等 3 支未被引用的程式）未帶入。
- 早期報告（如 `docs/reports/2026-09-20-phase1-status.md`）寫的「`.env` 只在 `D:\art_icnclab\.env`」為當時狀態，不回頭改寫。

---

## 2026-09-24　封存舊版 Node.js 第一代架構（`src/`、頂層 `agents/`、對應 jest 測試）

### 背景
審視「系統是否全面採用新架構」的過程中，發現除了先前處理的幾支孤兒 Python 腳本外，還有一整套規模大得多、完全獨立的**第一代架構**：`src/app.js`＋`src/database/`（Node.js Express API）、`src/agents/`（含強化學習訓練 `rl/`）、`src/crawler/`、`src/importer/`、`src/mcp/`、`src/experiments/`，以及頂層 `agents/`（4 個獨立的 Node.js AI Agent：分類、metadata 抽取、摘要翻譯、網頁爬蟲），加上對應測試這整套系統的 7 支 jest 測試檔。

### 診斷（四項獨立證據，判定為已淘汰、非現行系統）
1. **無任何啟動路徑**：`scripts/Start-NativeServices.ps1`（現行服務啟動、每日排程實際入口）完全沒有提到 `npm start`、`node src/app.js` 或這整批檔案。
2. **git 歷史停滯超過一個月**：這批檔案最後一次有實質內容變動是 2026-08-18（repo 精整匯入當天），此後只被全域批次改動（埠號、清 Docker）碰過，無任何功能開發；同期 `langchain-rag/` 每天都有實質改動。
3. **完全未被現行系統 import**：現行 RAG 後端 `unified_rag_manager_v2.py` 沒有一行 import 這批模組任何一個。
4. **4 天前已被標記、但沒人跟進**：`docs/reports/2026-09-20-phase0-status.md` 已記載 `src/agents/rl/rl_server.py`（8011 埠）、`create_graphrag_models.py`（8010 埠）等「屬舊版／已停用服務，不在架構圖上」，並寫「若要清理這些舊服務的引用，需先確認哪些已廢棄」——這句話放了 4 天沒被處理，本次即接續處理。

### 已決定
| 項目 | 決定 | 決定者 |
|---|---|---|
| 是否確定不再需要 | **確定不需要了**，同意上述四項證據的判斷 | 使用者，2026-09-24 |
| 處理方式 | `git rm` 會被權限系統擋下（不可逆本地刪除），改用 `git mv` 整批搬到 `archive/legacy-node-system/`；內容與相對路徑完整保留，非真的刪除 | 使用者，2026-09-24（於兩者間選擇 `git mv`，而非逐檔清空內容換警告標頭，或由使用者自行刪除） |

### 執行
- `git mv src archive/legacy-node-system/src`、`git mv agents archive/legacy-node-system/agents`
- `git mv tests/{agents,api,database,setup} archive/legacy-node-system/tests/`、4 支頂層 `.test.js`（`errorHandling`、`performance-optimization`、`schedulingSystem`、`validation`）同樣搬入
- 共 102 個檔案以 rename 方式搬移（`git status` 全數顯示 `R`，非新增／刪除）
- 新增 `archive/legacy-node-system/README.md` 說明封存原因、判斷依據、復原方式
- 更新根目錄 `README.md` 的「專案結構」區塊，移除已不存在原位置的 `src/`／`agents/` 條目，改列 `archive/legacy-node-system/`
- 更新 `package.json` 的 `start`／`dev`／`format` 腳本路徑指到新位置，避免搬移後路徑失效；`test`／`test:watch`（jest）不需要改，jest 預設掃描整個 repo，仍會找到搬移後的測試檔

### 驗證
- `python3 -m pytest tests/python/` 全量：54 通過、33 略過，跟搬移前一致，無新增失敗
- `git status` 確認全數為 rename（`R`），無檔案內容遺失

### 影響
- 現行系統（`langchain-rag/`＋`crawlers/`＋`scripts/`）完全不受影響，這批檔案原本就沒被引用。
- **未處理、刻意保留原狀的部分**：`package.json` 的 `dependencies`／`devDependencies` 裡，`express`／`helmet`／`joi`／`jsonwebtoken`／`morgan`／`node-cron`／`openai`／`playwright`／`puppeteer`／`redis`／`winston`／`bcrypt` 等疑似只被已封存的 Node API／Agent 系統使用，`crawlers/` 只需要 `axios`／`cheerio` 等少數套件；本次**未確認**哪些可以移除，避免誤刪 `crawlers/` 實際依賴的套件，列為之後可考慮的清理項目，非立即待辦。
- `CLAUDE.md` §3 第 4 點提到「一次性分析腳本…不進 `src/`」，該處的 `src/` 是抽象指「production 程式碼目錄」的慣例用法，現在 `src/` 已封存、現行 production 程式碼實際落在 `langchain-rag/`／`crawlers/`／`scripts/`，此規則文字已與現況有落差——`CLAUDE.md` 屬治理文件，本次未逕自修改，列為向使用者／老師回報的項目。
- 昨天（2026-09-23）處理的 7 支孤兒 langchain-rag 腳本（`create_graphrag_models.py` 等，見前續討論）**本次未一併封存**，範圍只限使用者本次明確核准的 Node.js 第一代架構；那 7 支風險更低（不在任何排程或殼腳本路徑上），仍待使用者另外決定是否處理。

---

## 2026-09-23　清除舊版每日流程腳本（`scripts/daily_crawl_and_sync.sh`）

### 背景
審視「系統是否全面採用新架構（catalog／outbox）」時發現：`scripts/daily_crawl_and_sync.sh`（新架構上線前的舊版每日流程）仍留在 repo 裡，雖然已查證沒有任何排程（Windows 工作排程器、cron）指向它，但它會直接呼叫 `import_all_museums_to_neo4j.py`、`sync_europeana_to_databases.py`，**繞過 PostgreSQL catalog／outbox** 直接寫 Neo4j／ChromaDB。若被誤執行，會在唯一真相源之外多寫入一份不受 outbox 追蹤的資料，且不會被 `ingest verify` 的一致性稽核發現（因為 verify 只比對 catalog 與三庫，不知道這些寫入曾經發生過）。

### 已決定
| 項目 | 決定 | 決定者 |
|---|---|---|
| 舊版腳本處理方式 | 內容清空，改為執行即報錯並印出提示訊息的停用標頭；不用 `git rm` 刪除檔案（本次執行環境的權限規則禁止不可逆的本地刪除動作） | 使用者，2026-09-23 |

### 影響
- 原始內容可由 git 歷史還原（本次變更前的版本）；若真的需要恢復舊流程，需先讀本條目並重新評估。
- **殘留、本次未處理的較小風險**：`import_all_museums_to_neo4j.py`（`--clean` 模式）與 `sync_europeana_to_databases.py` 這兩支 Python 腳本本身仍可被直接執行（`python3 import_all_museums_to_neo4j.py`），一樣會繞過 outbox 直寫 Neo4j／ChromaDB。這次只處理了「一鍵跑全套舊流程」的殼腳本，沒有動這兩支底層腳本本身——它們的正規化函式（`NORMALIZERS`、`build_document_text`）仍被新架構的 `ingest/legacy.py` 匯入沿用，不能刪除；如果要完全封死「直接執行」這條路，需要另外評估怎麼在不影響匯入用途的前提下擋住其 `if __name__ == "__main__"` 的直接執行入口，本次未做，列為之後可考慮的項目，非立即待辦。

### 後續（同日）：封住 import_all_museums_to_neo4j.py／sync_europeana_to_databases.py 的直接執行

上一段列的殘留風險，使用者確認要處理，且指示**先確認方式再動手**（特別是 `sync_europeana_to_databases.py`——它完全沒被新架構 import，是否要整支清空像殼腳本一樣處理，還是保留內容只加防呆，讓使用者選）。

**已決定**：兩支都採「加防呆檢查，保留檔案內容」，理由：`import_all_museums_to_neo4j.py` 的正規化函式仍被 `ingest/legacy.py` import 使用，不能清空；`sync_europeana_to_databases.py` 雖然沒被 import，但為了跟另一支處理方式一致、且保留其獨有的 Cypher 邏輯供之後參考，同樣採防呆而非清空。

**做法**：兩支腳本的 `main()` 開頭都加上 `_require_direct_execution_opt_in()`——沒有設定環境變數 `ALLOW_LEGACY_DIRECT_WRITE=yes-i-know-this-bypasses-outbox` 就直接報錯（exit code 1）並印出改用 `python3 -m ingest run --source <來源>` 的提示；**只在 `main()` 被呼叫時檢查，import 模組本身不受影響**（`ingest/legacy.py` 的用法只讀 `NORMALIZERS` 等成員，不會呼叫 `main()`）。留一個明確的環境變數當作「緊急逃生門」而非完全封死，避免真的需要手動除錯時求助無門。

**驗證**：
| 測試 | 結果 |
|---|---|
| `ingest/legacy.py` 的 import 路徑（`NORMALIZERS` 讀取） | ✅ 正常，8 個來源 key 齊全，exit 0 |
| `import_all_museums_to_neo4j.py` 沒設 opt-in 直接執行 | ✅ 擋下，exit 1，印出提示 |
| `sync_europeana_to_databases.py` 沒設 opt-in 直接執行 | ✅ 擋下，exit 1，印出提示 |
| `pytest tests/python/` 全量 | ✅ 54 通過、33 略過，無失敗 |

---

## 2026-09-23　MET Museum 403 診斷與修復：部門搜尋無節流＋沒有識別 UA

### 背景
移除 Yale 後手動實跑（見同日「Yale 完全移除」條目）意外與 03:00 排程撞期，兩次執行都出現 MET Museum 403。查歷史 log 排除撞期為主因——09-21 03:00 單獨排程（無撞期）同樣有 31 次 403，跟 09-23 撞期那次的 32 次幾乎相同，確認是**既有現象**，只是從未被查過原因。

### 診斷
比對兩支會呼叫 MET API 的爬蟲程式碼：
- `crawlers/start-single-crawler.js` 的 `getArtworkDetails()`（單一作品詳情）每次呼叫後有 1 秒延遲，但 `searchDepartment()`（部門搜尋，27 個部門逐一呼叫）**完全沒有節流**；今晚的 403 幾乎全部集中在「搜尋部門失敗」。
- 兩支爬蟲（含 `renaissance-baroque-crawler.js`）都用 axios 預設 User-Agent，沒有自我識別——與 Yale 一開始的狀況相同（見 09-21 條目），但失敗模式不同：Yale 是 100% 全部請求被擋，MET 是部分／間歇性失敗，兩者機制不判定為同一種問題，只是同樣源自「爬蟲沒考慮目標服務的防護策略」。

### 已決定
| 項目 | 決定 | 決定者 |
|---|---|---|
| 修復方式 | 比照 Yale 的做法：兩支爬蟲的所有 axios 請求加上識別 UA（沿用同一字串 `art-history-research (+mailto:icnclab.stust@gmail.com)`）；並在 `start-single-crawler.js` 的部門搜尋迴圈補上 1 秒節流延遲（`renaissance-baroque-crawler.js` 本來就有節流，只缺 UA） | 使用者，2026-09-23 |

### 驗證結果（獨立重跑兩支爬蟲，不經完整夜間流程）
| 爬蟲 | 修復前（今晚 03:00 撞期實跑） | 修復後（獨立驗證） |
|---|---|---|
| MET（`start-single-crawler.js`） | 27 次「搜尋部門失敗」403 | **0 次**部門搜尋失敗；剩 4 個零星單一作品 403（詳情頁，非本次修復範圍） |
| 文藝復興/巴洛克（`renaissance-baroque-crawler.js`） | 有 403（併在 32 次總數內） | **0 次** 403，479 件作品全部收集成功，涵蓋文藝復興 47／巴洛克 67／其他 365 |

### 影響
- 兩支爬蟲的修改只涉及請求標頭與節流延遲，不改資料結構、不改輸出格式，屬 CLAUDE.md 定義的低風險維護性修改。
- 本次驗證產生的原始資料檔（`crawlers/data/raw/met_museum/`、`.../renaissance_baroque/`）留在原地，**未手動匯入**；會在下一次排定的每日流程中被正常攝取，不需要額外動作。
- 剩餘的 4 個單一作品 403（詳情頁）判斷為個別物件本身的存取限制，非節流或 UA 問題，不在本次修復範圍內；若之後持續出現同一批 ID，才需要進一步查。

### 後續（同日）：排查其餘 8 支爬蟲，發現 Specialized Art 有同一問題

**排查方法**：比對最近 6 次夜間 log（含無撞期的 09-21 03:00 正常排程），按爬蟲分段統計 403／429 次數。

| 爬蟲 | 403／429 量級 | 判定 |
|---|---|---|
| Harvard、Google Books、Art Institute of Chicago | 0（六次全部） | 乾淨，不處理 |
| Europeana、V&A、Cleveland | 1～2（零星） | 量級與系統性問題不同，不處理 |
| **Specialized Art** | **7～14（每次執行）** | 與 MET 修復前同量級，需處理 |

**Specialized Art 診斷**：逐行核對失敗訊息，**全部**是「Met Museum 搜尋失敗」403——這支爬蟲除了打 Europeana，也會呼叫 MET API（`searchMetMuseum`），且同樣沒有設定 User-Agent。修復方式與上面相同：`crawlers/specialized-art-crawler.js` 的三處 axios 請求（Europeana 搜尋、MET 搜尋、MET 作品詳情）加上同一識別 UA，不需額外節流（該檔已有 1 秒／200 毫秒延遲）。

**驗證**（獨立重跑，不經完整夜間流程）：40 個主題全部成功，0 次 403／429（原判讀出現的 1 筆「40」比對其實是時間戳記 `.402Z` 的毫秒數，非真實錯誤），收集 719 項（Europeana 534、MET Museum 185）。

**更正與後續（2026-09-24）——用真實排程數據驗證後的結論**

*我先前的計數有誤*：上面與對話中用「`40x`」樣式統計 403，會把 **404（物件已不存在，屬正常）** 與 log 時間戳裡的毫秒數（如 `.402Z`）誤算進去，導致 MET／文藝復興/巴洛克／Europeana／V&A／Cleveland 的「403 次數」被高估。改用精確樣式（`status code 403|429`）重算：

| 執行 | 真正的 403／429（全爬蟲合計） | 來源 |
|---|---|---|
| 修復前（09-23 03:00 排程） | 32 | MET 27（17 搜尋＋10 詳情）＋ Specialized 5 |
| 修復後（09-24 03:00 排程） | 13 | **MET 0、文藝復興/巴洛克 0、Specialized 13** |
| 修復後（09-24 08:14 手動全流程） | 11 | **MET 0、文藝復興/巴洛克 0、Specialized 11** |

結論：**MET 與文藝復興/巴洛克的修復有效（403 歸零）**；MET 詳情頁「剩 4 個零星 403」的說法也是同一誤算，實際為 404。時段（凌晨 vs 白天）無影響。**剩下的 11～13 次全部來自 Specialized Art，且全是對 MET「搜尋」端點的 403**。

*Specialized 為何仍失敗*：三支會打 MET 的爬蟲中，只有它的 MET 詳情請求間隔是 **200ms**（約 5 次/秒；MET 爬蟲 1000ms、文藝復興/巴洛克 800ms，兩者已歸零），且詳情失敗被靜默 `continue`、不記錄。五晚資料顯示失敗主題每晚不同（交集 0／聯集 22／40），屬機率性而非特定查詢被擋，失敗成串出現。**此為依證據的推論，未經實驗證明**——注意修復前的獨立測試（Specialized 單獨跑）也是 0 次失敗，代表獨立測試無法重現問題，只有夜間流程接連跑才會出現。

*修正*（`crawlers/specialized-art-crawler.js`，小型修正、不新增依賴、不改輸出格式）：MET 詳情請求間隔 200ms → 1000ms（失敗時也等）；對 MET 搜尋與詳情請求遇 403／429 時退避重試（5 秒、15 秒，最多 2 次，重試時印出 log）；詳情失敗不再靜默，彙總記錄狀態碼。獨立驗證：40 個主題全數成功、0 次搜尋失敗、重試未觸發、詳情有 4 個主題共 6 項失敗（非 403／429，判斷為 404）。

**驗證狀態：尚未真正驗證**。獨立測試不能證明修復有效；要看 2026-09-25 03:00 排程（三支接連跑）的 Specialized 段：真正 403／429 是否降到 0，並以新增的「↻ MET 回…重試」log 判斷重試是否有救回請求。若仍有殘留，再評估拉長三支 MET 爬蟲之間的冷卻或去除重複抓取。

**先前保留意見（原文，保留存查）**：夜間流程裡 MET（`start-single-crawler.js`）→ 文藝復興/巴洛克 → Specialized Art 依序執行，三支都打 MET API。若 MET 端的防護是**依 IP 累積流量**而非單純比對 User-Agent 黑名單，則今天三次獨立驗證（各自單獨執行、無前置負載）即使全部乾淨，也不能完全代表三支接續執行的真實夜間流程不會再度觸發限制。**真正的驗證要看下一次（今晚 03:00）三支依序執行的實跑結果**；若屆時仍有零星 403，成因會是流量累積而非 UA／節流不足，須另外評估（例如把三支對 MET 的呼叫錯開間隔，或降低單次請求量）。

---

## 2026-09-23　Phase 4／5 設計文件與 09-23 規格書對齊：Router 不做規則式自動判斷

### 背景
`docs/designs/2026-09-21-phase4-*.md`、`2026-09-21-phase5-*.md` 是 09-21 寫的草案，§9 各留有「待訂項目」表。09-23 依附件（`system-flow-steps.md`／`system-spec-srs.md`）重寫規格書後，多數待訂項目其實已在新規格書（GRD／RET／EVL 系列需求）或先前的 09-22 決策中有答案，只是兩份設計文件沒有回頭同步，此次逐項核對並更新。

### 已決定
| 項目 | 決定 | 決定者 |
|---|---|---|
| Router 是否做規則式自動判斷（Phase5 原案的 `auto` 策略、與舊 11 個策略 id 並存觀察期） | **不做**。Router 維持 09-23 規格書 RET-01 的字面定義：完全依請求指定的 4 種策略（`vector`／`fulltext`／`graph`／`hybrid`，預設 `hybrid`），不新增 `auto` id，不補強 `_analyze_intent` | 使用者，2026-09-23（理由：自動判斷需另立意圖分類與黃金集驗證，屬範圍擴張；且會讓「RRF 融合是否優於單路」的驗收與「自動選路對不對」的誤差混在一起，難以歸因退步原因） |

### 一併核對出的既有決定（非本次新決定，只是把 09-22 已定案的值回填進兩份設計文件）
| 設計文件 | 項目 | 09-23 規格書依據 |
|---|---|---|
| Phase4 §9 #4 | 防護元件出錯 → 原建議「放行並標示」，**已被推翻**改為**拒答** | GRD-09（決策 B3） |
| Phase4 §9 #5 | 精篩模型 → 原建議「先用 LLM 判官」，**已被推翻**改為**專用 NLI 模型** | GRD-07（決策 B4） |
| Phase4 §9 #6 | 延遲預算 → 不是單純接受 300ms 與否，而是不設逾時＋300ms 降為觀測目標＋另設 30 秒硬上限 | GRD-06／06a／06c／06d |
| Phase4 §9 #2、#3、#7 | 無檢索支撐政策、K>0.7 定義、複審人選 | GRD-01～03、EVL-16，與原建議一致，僅確認定案 |
| Phase5 §9 #2、#5、#6、#7、#8 | cross-encoder 重排、Redis 快取方案、嵌入模型版本標註、每週稽核、Google Books | RET-05／06、RET-10～13、DAT-30～32、EVL-10～12、RET-08，與原建議一致，僅確認定案 |

### 影響
- 兩份設計文件的 §9 已重寫為「已決定／待訂」兩表；§4.2、§4.3、§5、§5.3、§8 等本文段落**保留原始草案文字**（含被推翻的建議），只在旁加「更正（2026-09-23）」註記——保留決策過程可追溯，不掩蓋草案曾經的建議值。
- Phase4／Phase5 剩餘唯一的待訂項目只剩「前置：Phase 3 基準值尚未跑出來」，屬進度依賴，非需要裁決的事項。
- 這兩份文件不是 `spec-export.py` 的輸入（只吃 `docs/2026-09-23-system-spec-srs.md` 與 `system-flow-steps.md`），本次修改不影響 `docs/spec.json`，未重新匯出。

---

## 2026-09-23　Yale 完全移除（爬蟲、程式碼、既有資料全部撤出）

### 已決定
| 項目 | 決定 | 決定者 |
|---|---|---|
| Yale 相關的一切 | **全部移除**，包含已入庫的資料；透過既有 soft_delete／30 天保留機制執行，30 天內可還原，30 天後由既有的每日 `purge-neo4j --days 30 --apply` 自動永久刪除 | 使用者，2026-09-21 曾決定保留既有資料、修復並重新啟用（見同日條目），2026-09-23 改為全部移除 |

### 執行步驟與實測結果
1. **catalog 撤出**：以空清單對來源 `yale_university_art_gallery` 執行 `ingest run --prune`，把 catalog 中 289 筆未刪除的 Yale 文件標記刪除，寫入 646 個 soft_delete 事件（chunk＋文件）。
2. **三庫同步**：ChromaDB／Elasticsearch／Neo4j 訂閱器各處理 357、357、289 筆，落後皆為 0。
3. **驗證**：`ingest verify --es`：ChromaDB 與 Elasticsearch 皆 catalog 0／檢索庫 0，結果「一致」。Neo4j：289 件 Yale 作品全部 `is_deleted=true`，圖檢索端（`coalesce(is_deleted,false)=false` 的過濾條件）可見數為 0。
4. **副作用（預期內）**：153 位藝術家的 `sources` 因此變成空清單——這些是只在 Yale 有現存作品的藝術家，`Artist.sources` 由現存作品動態推導，Yale 作品消失後自然歸零；他們的節點暫時保留，30 天保留期滿後，既有的 `purge-neo4j` 孤兒藝術家規則會自動一併清除（前提是他們沒有其他任何關係）。
5. **`purge-neo4j --days 30`（僅預覽）**：目前三類皆為 0，確認 30 天保留期完整、沒有東西被提前清除。
6. **程式碼移除**：
   - 刪除 `crawlers/yale-university-art-gallery-crawler.js`。
   - `langchain-rag/import_all_museums_to_neo4j.py` 移除 `yale_university_art_gallery` 的檔名比對規則、`normalize_yale_university_art_gallery` 正規化函式、`NORMALIZERS` 註冊——之後 `yale_university_art_gallery` 不再是系統認得的來源名稱，`ingest run --source yale_university_art_gallery` 會直接報「未知來源」。
   - `scripts/daily_crawl_and_sync_catalog.sh`（現行流程）與 `scripts/daily_crawl_and_sync.sh`（舊流程，未排程但保留一致性）皆移除 Yale 的爬蟲、攝取、驗證清單。
   - `docs/2026-09-23-system-spec-srs.md`、`docs/2026-09-23-system-flow-steps.md` 同步更正來源數（10→9）與 OPS-02 描述。

### 未刪除的東西（刻意保留，供追溯）
- 過去的執行紀錄：`docs/decision-log.md` 2026-09-21 的 Yale 403 診斷、修復、重新啟用全過程原樣保留，不覆寫、不刪除——那是真實發生過的除錯過程，之後若要參考「Yale 的 403 其實是 User-Agent 問題」的診斷方法仍看得到。
- `docs/reports/2026-09-21-neo4j-status.md` 的 Yale 相關段落，附加一行指向本條目，未刪除原文。
- Neo4j 裡 289 個已軟刪除的 Artwork 節點與 153 位歸零 `sources` 的 Artist 節點，30 天內仍可用既有的 `_REACTIVATE_QUERY`（重新攝取同一 id）機制還原；30 天後由既有排程自動永久清除，不需要另外手動處理。

### 待訂項目
| # | 項目 | 說明 |
|---|---|---|
| 15 | 30 天後確認 Yale 的軟刪除資料與孤兒藝術家確實被自動清除 | 屬既有 `purge-neo4j` 機制的例行驗證，非新增待辦 |

---

## 2026-09-23　外部文件核對：與現況不符之處（教師核可待確認，埠號已更正）

使用者貼上兩份文件（`2026-09-22-system-flow-steps.md`、`2026-09-22-system-spec-srs.md`），宣稱依
「2026-09-21 決策簡報」（`docs/reports/2026-09-21-pending-items-and-architecture-gaps.md`）做出大量新決策。
核對後部分主張與現況不符，記錄如下，避免之後又被當成既定事實引用。

| 文件主張 | 核對結果 |
|---|---|
| RAG 後端埠號為 8007（文件稱「已結案」） | `docs/ports.md` 原記 8007，但該行最後更新 2026-09-20、早於埠號整併；實際在跑、`.env.example`、程式碼預設值皆為 **8001**（本次對話多次 `curl 127.0.0.1:8001/health` 驗證）。**已更正 `ports.md`**（見下）|
| 執行期目錄與正本脫鉤，需要遷移（文件的 P0-6／SYS-05／M-1～M-6） | Windows 工作排程器實際登記的動作直接執行 `F:\art_icnclab-main\art_icnclab-main\scripts\Run-DailyCrawl.ps1`，即本對話全程在改的 repo；文件提到的桌面路徑 `Test-Path` 為 False，不存在。**此缺陷判定不成立，不採用** |
| `scripts/verify-nightly.sh`、`scripts/spec-export.py`、`scripts/spec-update.py`、`docs/spec.json`、`docs/spec.schema.json`、`docs/spec-changelog.md` | 皆**不存在**於本 repo（`scripts/diagnose.py`、`scripts/collect.sh` 存在） |
| P0-4／BIZ-06：老師已核可、簽名程序免除 | 與 repo 內實際的評估表原本矛盾（§九簽核欄空白）；**2026-09-23 已由使用者直接確認並記載豁免**，見下方「已結案」 |

### 已更正
- `docs/ports.md`：rag-manager-v2 由 8007 改為 8001，並附更正說明；Neo4j 7687／7474 標記由「待機器端套用」改為「已套用並驗證」（2026-09-21 已完成，該行先前未同步更新）。

### 已結案（2026-09-23）
- 第 14 項：AI 明確詢問「P0-4／BIZ-06 老師已核可一事，是真的發生還是文件推論？」，使用者答覆「是，老師已同意豁免簽核」。依 CLAUDE.md R3，豁免自此生效，已記載於 `docs/designs/2026-09-11-target-architecture-consistency-eval-faithfulness-assessment.md` §八；適用於 Phase 3、4、5 三份設計文件進入實作。§九簽核欄本身仍未代填（R5），維持空白。

### 提供出處說明（重要，供之後追溯）
貼上的兩份文件內含約 20 項具體數值／政策決定（標註「使用者裁定 2026-09-22」），例如：忠實度粗篩 30 秒硬上限、`gate_error` 1% 告警門檻、量測退步 5 個百分點門檻、服務復原 5 分鐘、F 槽容量 20%／10% 告警、GRD-09 防護出錯時**拒答**（覆蓋 Phase 4 設計文件原建議的「放行」）、忠實度精篩採**專用 NLI 模型**（覆蓋原建議的 LLM 判官）、黃金測試集以**巴洛克時期**為基準主題等。**這些在本對話（本 session）中沒有出現過使用者拍板的紀錄**，2026-09-22 這天本 session 只處理了 Yale 爬蟲修復與待訂項目總表。使用者於 2026-09-23 以「直接執行」回覆，指示依文件內容繼續，故本 session **依使用者指示採信並落地**，但無法如同其餘決策一樣附上「本 session 內的拍板依據」；若這些數值並非使用者本人（或與老師）確認過的決定，請盡快更正，以免以訛傳訛寫進正式規格。

---

## 2026-09-23　部署流程：停用 PR，改為本地 merge --no-ff 直接推送 main

### 已決定（使用者，2026-09-23）
| 項目 | 決定 |
|---|---|
| PR 審查 | **停用**。不再開 GitHub PR 供審查 |
| 併入方式 | 功能分支本地驗證通過後，`git switch main && git merge --no-ff <分支> && git push origin main` |

### 影響
- 先前準備中的「PR 說明」作廢，不再需要。
- 併入 `main` 前的唯一把關，落在本地驗證（測試、lint、對照設計文件），沒有第二人審查這一關；這是使用者知情後的取捨，此處僅存證。
- `phase0-docs-and-tidy` 之後併入 `main`，改用上述指令，不開 PR。

---

## 2026-09-23　`biz.messages` 保存期限與歸檔：由待定改為已決定（永久保留）

### 已決定（使用者，2026-09-23，撤銷 2026-09-21 的「待定」狀態）
| 項目 | 決定 |
|---|---|
| 保存期限 | 18 週後自線上資料庫（`biz.messages`）移除 |
| 歸檔 | 移除前歸檔至備份位置，**永久保留、不自動清除** |
| 對外用語 | 不得宣稱「18 週後刪除」；一律使用「18 週後自線上資料庫移除，歸檔留存」 |

### 保留的邏輯前提（**未撤銷**，仍待完成才能生效）
- P0-2（適用法規與告知文字，見下方 2026-09-21 Phase 3 條目 #4）**仍為待定**；本次只決定「若保存，保存方式為何」，不等於「已核准開始保存」。`BIZ_LOGGING` 在 P0-2 確認前仍須維持關閉。
- 之後向老師／法務確認適用法規時，**必須以「永久保留」為前提提問**，不可沿用「18 週後刪除」的舊前提——兩者的法規結論可能完全不同，用錯前提取得的核可不成立。
- 永久保留個資的隱私風險高於原提案「180 天後自動刪除」；此為使用者知情後的決定，本記錄僅為存證。

### 影響
- `docs/designs/2026-09-21-phase3-biz-logging-and-recall-eval.md` §6.1、§9 已同步更新為此決定。

---

## 2026-09-21　Phase 4／5 與另案設計草案：全部待訂（共 13 項）

設計文件（皆為草案，待使用者確認；Tier B，實作前需老師核可）：
- `docs/designs/2026-09-21-phase4-evidence-refusal-faithfulness-fuzzy.md`（證據判定與拒答、忠實度守門員、模糊檢索）
- `docs/designs/2026-09-21-phase5-router-fusion-and-side-items.md`（Router、系統級 RRF、重排、實驗層；另案：Redis 語意快取、嵌入模型版本標註、每週稽核）

### 調查發現（會影響決策）
| 發現 | 內容 |
|---|---|
| **架構圖的 Reranker 名不副實** | 圖上寫 Cross-encoder，實際**沒有**：圖檢索用「全文分數＋擴展豐富度加成」，其餘只依分數排序。（更正先前「有 `_rerank` 函式、是否為 cross-encoder 未驗證」的說法） |
| 融合節點（RRF） | 只有 `HybridESRAG` 自己手動做；`HybridBalancedRAG` 是向量取一半、圖取一半直接串接，**沒有分數融合** |
| RAG Router | 沒有；由請求的 `模型@策略` 指定，只有 `AgenticRAG._analyze_intent` 用約 6 個中文關鍵字內部分流 |
| 相似度門檻／證據判定／拒答／忠實度守門員 | 後端**完全沒有**（無任何 threshold）；忠實度只有離線腳本 `eval_step2` 以 LLM 事後整份判斷 |
| 分數尺度 | 向量、ES-RRF、圖全文分數彼此不可比，門檻必須分路由校準（依賴 Phase 3 黃金集） |
| 已安裝模型 | 只有 `bge-m3` 與多個對話 LLM；**沒有** NLI 模型或 cross-encoder 重排模型，新增須做來源／授權／供應鏈評估 |
| 快取 | 後端用記憶體內 `QueryCache`（1000 筆、TTL 1 小時、精確比對）；Redis 在 6379 執行但後端沒有使用 |
| 嵌入模型標註 | ingest／訂閱器沒有記錄向量由哪個模型與版本產生 |

### 待訂項目（尚未決定，**不要當成已決定**）
| # | 所屬 | 項目 | 目前的建議 | 卡在哪 |
|---|---|---|---|---|
| 1 | Phase 4 | 無檢索支撐的政策：拒答，或標示風險後用模型知識回答 | 預設拒答，可設定開關 | 使用者／老師決定預設值 |
| 2 | Phase 4 | 「可信度 K>0.7」的定義（圖面未說明） | K＝最佳模糊命中的正規化分數，且僅在證據不足時觸發 | 需與老師／圖面原作者確認 |
| 3 | Phase 4 | 防護元件本身出錯時：放行並標示，或拒答 | 放行並標 `gate_error`（保可用性） | 老師確認風險取捨 |
| 4 | Phase 4 | 精篩用 LLM 判官或專用 NLI 模型 | 先 LLM 判官 | 若選 NLI 需另做供應鏈評估 |
| 5 | Phase 4 | 同步粗篩延遲預算（提案 ≤ 300 ms） | 提案值 | 使用者確認 |
| 6 | Phase 4 | 每週人工複審拒答佇列的人選 | 無人選 | 需要人力，否則回饋迴圈斷掉 |
| 7 | Phase 5 | 是否新增真正的 cross-encoder 重排 | 先只做 RRF，量出基準再議 | 新依賴評估、硬體需求實測 |
| 8 | Phase 5 | Router 第一版範圍與權重調整需人工確認 | 規則式補強（多語、實體偵測） | 使用者確認 |
| 9 | Phase 5 | 新路徑 `auto` 何時成為預設 | 黃金集上不劣於最佳單一策略且觀察期無告警 | 需 Phase 3 數據 |
| 10 | 另案 | Redis 語意快取採 A（outbox 精準失效、不引入 Redis）或 B（Redis＋語意近似） | A | 使用者確認；B 需 Redis 密碼與存取控制 |
| 11 | 另案 | 嵌入模型「名稱＋版本」標註 | 做，並納入 `ingest verify` | 使用者確認範圍 |
| 12 | 另案 | 每週稽核：擴充 `verify` 並寫入 `eval.alerts` | 同左 | 使用者確認 |
| 13 | 另案 | **Google Books 後置補充查詢**（圖上生成後的補充來源；目前檢索端沒有接，只有爬蟲離線入庫，**尚無設計**）：A 不做（維持離線入庫）；B 生成後只用**書目關鍵字**（書名、作者、ISBN）查 Google Books 補「延伸閱讀」，不送使用者原文；C 把使用者問題即時送 Google Books | 先不做（A）；若要做採 B，C 不建議（違反「資料不出境」原則） | 使用者決定要不要做；B 屬對外呼叫，須先做隱私與外部服務評估（金鑰、配額、失敗降級），並另寫設計文件 |

### 整體依賴（卡點）
Phase 4、5 的門檻與路由比較都依賴 **Phase 3 黃金測試集**；Phase 3 又卡在**標註人力**與**老師核可／法規確認**（見上方 Phase 3 條目）。在這些解決前，Phase 3–5 均不進入實作。

---

## 2026-09-21　Phase 3 評測迴路（biz 記錄＋召回率量測）與隱私設計：多項待訂

設計文件：`docs/designs/2026-09-21-phase3-biz-logging-and-recall-eval.md`（草案，待使用者確認；Tier B，實作前需老師核可）。

### 已決定
| 項目 | 決定 | 決定者 |
|---|---|---|
| 量測涵蓋的路由 | 先量 `naive_rag`、`advanced_rag`、`graph_only`、`agentic_rag` 四個策略（後端共註冊 11 個策略 id，其餘之後再加）；`route_id` 直接用策略 id | 使用者 |
| 三支未使用的監控檔（`adaptive_strategy_monitor.py`、`alert_and_optimization_system.py`、`optimization_manager.py`） | 細讀後**不重用**；Phase 3 只寫必要的最小程式。理由：前兩支量營運效能且會自動改系統參數，與「告警只通知、由人決定」相反；第三支是 md5 精確比對、無失效機制、連 Redis 未帶密碼，不是語意快取 | 使用者要求確認，結論由調查得出（使用者可提出異議） |
| 使用者範圍 | 日後開放更多使用者，隱私須符合 AI 相關法規 | 使用者 |

### 隱私設計（**待定**：以下是設計提案，尚未經老師／單位確認，適用法規尚未確認）
> 我（AI 助理）無法確認哪些法規條文適用，也不提供法律意見；以下依一般資料保護原則設計，用來降低日後被要求調整的成本。

| 原則 | 提案內容 |
|---|---|
| 資料最少化 | `biz` 只存匿名使用者代號、對話 id、問題與答案文字、路由、引用文件 id、時間；**不存**姓名、信箱、IP、瀏覽器資訊 |
| 匿名化 | Open WebUI 使用者 id 加鹽雜湊後存入 `biz.users.user_id`；鹽放 `.env`，不進 repo |
| 目的限定 | 只用於除錯、評測、改進檢索；不做使用者行為分析、不對外提供 |
| 告知 | Open WebUI 頁面顯示簡短告知（記錄內容、用途、保存期限、如何要求刪除）；文字需經老師／單位確認 |
| 保存期限與自動刪除 | 期限待定（建議 180 天）；排程自動清除，先預覽再套用；備份保留 7 批，刪除最多 7 天後才從備份完全消失，需在告知中說明 |
| 使用者權利 | 依匿名代號查詢、匯出、刪除全部記錄的指令（schema 已有 `ON DELETE CASCADE`） |
| 個資混入問題 | 存入前以規則式遮罩信箱、電話、證號格式 |
| 存取控制 | 專用資料庫角色：後端只能 INSERT `biz`；量測程式讀寫 `eval`、讀 `biz`；人工檢視用唯讀角色；不用超級使用者 |
| 日誌 | 稽核 log 只記 `event_id`／路徑／耗時，不記問題與答案原文 |
| 資料不出境 | 生成與嵌入皆在本地（Ollama、BGE-M3），記錄不送外部服務 |
| 二次使用 | 從正式流量抽樣進黃金測試集**預設不做**；要做須告知涵蓋此用途，並經人工去識別化；進測試集的題目不帶使用者資訊 |
| 開啟前置條件 | 適用法規確認、告知文字定案並顯示、保存期限定案、遮罩與刪除指令就緒、資料庫角色建立——**全部就緒前 `BIZ_LOGGING` 維持關閉** |

### 待訂項目（卡住 Phase 3 的事項；**不要當成已決定**）
| # | 項目 | 目前狀態／建議 | 卡在哪、誰能解 |
|---|---|---|---|
| 1 | **黃金測試集誰來標註**（15 題 × 約 20 個候選，預估 2～3 小時） | 無人選 | 需要人力；**沒有標註就沒有黃金測試集，量測無法開始（Phase 3 關鍵路徑）**。使用者／實驗室成員／老師 |
| 2 | **召回率粒度**：文件層級或 chunk 層級 | 建議文件層級（圖檢索回傳實體、無法對到 chunk；標註量小一個量級） | 使用者選擇先列為待訂 |
| 3 | **`biz.messages` 保存期限** | 建議 180 天並自動刪除 | 與法規要求有關，待 #4 確認 |
| 4 | **適用法規與告知文字** | 我無法判定 | 需指導老師、學校資訊或法務確認；同時決定是否需要研究倫理審查 |
| 5 | **老師核可 Tier B 實作** | `docs/designs/…-assessment.md` §九 簽名欄空白；評估表須補**隱私影響評估** | 依 CLAUDE.md R5，只有使用者／老師能填，我不代填 |
| 6 | **多人使用時的存取控制**：Open WebUI 帳號策略、頻率限制；後端 8001 目前**無任何驗證**，連得到就能直接呼叫 | 另案處理；Phase 3 先登記 | 需決定帳號與登入方式 |

### 影響
- 在 #4、#5 解決前，Phase 3 不進入實作；`BIZ_LOGGING` 不開啟，`biz` 三張表維持 0 筆。
- 後續 Phase 4／5 與 Redis 語意快取只寫設計文件，同樣依賴 Phase 3 的黃金測試集才能校準門檻。

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
