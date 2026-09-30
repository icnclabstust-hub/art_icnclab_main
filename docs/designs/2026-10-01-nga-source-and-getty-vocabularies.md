# 設計文件：新增 NGA 館藏來源，並以 Getty 詞彙庫整併藝術家身分與中文術語

> GD 設計閘門步驟 3 產出。步驟 1（需求釐清）、步驟 2（現況調查）已於 2026-10-01 對話中經使用者確認。
> 本文為設計層級文件，只含資料流、介面、schema 草案，不含可執行實作（`CLAUDE.md` R2）。
> 評估表（步驟 4）待本文確認後另行撰寫。

## 1. 背景與問題

Yale 於 2026-09-23 因來源端 403 完全移除（catalog 289 份已軟刪除、ChromaDB／ES 已撤出，Neo4j 節點將於 2026-10-23 起由 30 天保留期清理實體刪除），系統少了一個美術館來源。使用者要求補上**開放館藏資料**：不需要 API 金鑰（符合金鑰管理規則）、授權在論文與研討會投稿時沒有爭議。

三問結論（步驟 1，使用者確認）：

1. **解決什麼問題？** 補回館藏涵蓋，並以 CC0 來源取代授權較模糊的資料；同時處理已觀測到的兩個品質缺陷——藝術家重複節點、中文查詢召回差。
2. **誰會用？** 現有 RAG 使用者（Open WebUI），以及論文／研討會的評測（黃金集）。
3. **不做會怎樣？** 館藏停在 9 個來源、5,434 個 chunk；加入 NGA 而不整併藝術家身分，重複節點會隨 NGA 約 2.8 萬位藝術家大幅增加，「某藝術家的所有作品」類問題漏得更多。

使用者已決定（步驟 1）：只做 NGA、不做 SMK；**NGA 全部 14.6 萬件都收**；**先接 NGA，再重產黃金集候選表並標註**；Getty 四種用途先比較後由 AI 建議，使用者同意本輪做 ① ULAN 身分整併、② AAT 中文術語，③ TGN、④ 圖譜知識節點延後。

## 2. 目標與非目標

**目標**

- G1：NGA 開放資料（146,099 件）經既有 catalog → outbox → 三庫路徑進入系統，每晚增量同步。
- G2：以 ULAN 編號整併同一藝術家的多個節點，NGA 藝術家帶入 ULAN 編號。
- G3：以 AAT 官方繁體中文標籤擴充查詢翻譯詞典，經人工審核後才生效。
- G4：新來源與整併全程可回滾，不影響現有 9 個來源與既有檢索策略。

**非目標（本次不做）**

- 不收圖片（NGA 本就不附圖檔，只有 IIIF 連結；不下載、不做影像檢索）。
- 不做 SMK、Rijksmuseum、LUX（使用者決定）。
- 不做 TGN 地點正規化：現有 Place 節點是國籍形容詞（Italian、Dutch），不是地名，對應價值低。
- 不做 ULAN 師承等關係入圖譜：依賴 G2 的編號，且黃金集沒有此類題目、無法量測效益。
- 不清理 Harvard 重複實作（`langchain-rag/` 下約 1,080 行未使用程式），另案處理。
- 不在本案處理 Neo4j 每萬筆分片備份（DAT-15／16，另案）。

## 3. 現況與重用

步驟 2 調查結果（2026-10-01）：

| 項目 | 現況 | 本案如何銜接 |
|---|---|---|
| NGA／Getty 相關程式 | **repo 內沒有**（只有 `data_mapper.py` 一段未被使用的 Getty 欄位對應） | 全新實作，但只走一條路徑，避免 Harvard 那種 JS／Python 兩套並存 |
| 來源接入方式 | 9 個來源：`crawlers/*.js` 寫原始 JSON → `import_all_museums_to_neo4j.py` 的 `NORMALIZERS`；Europeana 為唯一原生 adapter（`ingest/sources.py`） | NGA 是整批 CSV、不是爬蟲，比照 **Europeana 原生 adapter** |
| catalog／outbox／三庫訂閱／驗證／告警 | 已上線（Phase 1／2），每晚一致 | **直接重用，不改**；新來源只補「取得」與「正規化」 |
| 嵌入模型標註（DAT-30） | 已上線 | 新 chunk 自動帶標註 |
| 查詢翻譯詞典 | 手動維護 30 個英文詞條＋藝術家與作品；三份相同檔案並存 | 本案新增審核後匯入流程；三份檔案整併列為 §9 待議 |
| Neo4j Artist | 2,936 個節點；**157 組疑似重複、涉及 562 個節點**（Rembrandt 分成 6 個）；部分名稱是 URI（`http://d-nb.info/gnd/…`） | G2 整併；URI 名稱一併納入審核清單 |

**外部資料（已實測／查官方說明）**

| | NGA Open Data | Getty Vocabularies |
|---|---|---|
| 取得方式 | GitHub `NationalGalleryOfArt/opendata` 的 CSV（非 LFS），官方說明通常每日更新 | SPARQL `vocab.getty.edu/sparql.json`、逐筆 JSON、整批 N-Triples 下載 |
| 金鑰 | 不需要 | 不需要 |
| 授權 | **CC0-1.0** | **ODC-By 1.0**（須註明出處） |
| 規模 | 物件 146,099；藝術家等 27,981（8,304 有 ULAN 編號、9,155 有 Wikidata 編號） | AAT 有繁中標籤的概念 27,566 個 |
| 主要檔案 | `objects.csv` 78.6 MB、`objects_constituents.csv` 37.3 MB、`constituents.csv` 4.3 MB、`objects_terms.csv` 19.4 MB、`objects_text_entries.csv` 35.4 MB | — |

## 4. 方案比較

### 4.1 NGA 資料怎麼取得與正規化

| | 方案 A：Python 原生 adapter 直讀 CSV | 方案 B：Node 爬蟲轉成 JSON，沿用 `NORMALIZERS` |
|---|---|---|
| 做法概述 | 下載 5 個 CSV 到 `crawlers/data/raw/nga/<日期>/`，在 `ingest/` 內以 Python join 成作品紀錄，直接交給既有 `ingest_artworks` | 寫 `crawlers/nga-crawler.js` 下載並轉成與其他來源相同的 JSON，再在舊匯入腳本加一個 `normalize_nga` |
| 優點 | 只有一條路徑；join（作品↔藝術家↔風格）用 Python 最直接；可用 HTTP 條件請求（ETag）跳過未變更的檔案 | 與 8 個既有來源寫法一致 |
| 缺點／風險 | 與多數來源寫法不同（但 Europeana 已是先例） | 「爬蟲」其實只是下載＋轉檔，多一次 JSON 中介；14.6 萬件 JSON 約數百 MB；正規化邏輯分散在 JS 與 Python 兩處，重蹈 Harvard 覆轍 |
| 成本 | 中 | 中偏高（兩種語言） |

**選定方案 A。** 理由：NGA 是整批資料集而非需要翻頁的 API，爬蟲框架帶不來價值；單一 Python 路徑可測試、可避免雙實作。

### 4.2 文件文字包含哪些欄位

| | 方案 A：只放基本欄位 | 方案 B：基本欄位＋來源史（provenance） |
|---|---|---|
| 內容 | 標題、作者、年代、媒材、分類、風格／畫派 | 方案 A＋`provenancetext`（81,540 件有） |
| chunk 數（實測估算） | 146,414（每件 1.00） | 162,395（每件 1.11） |
| 優點 | 最省嵌入時間 | 能回答「這件作品曾由誰收藏」這類問題；只多 11% |
| 缺點 | 失去 NGA 最有特色的欄位 | 少數來源史極長（最長 11,696 字），會切成多塊 |

**選定方案 B。** 書目（158,952 筆）與展覽紀錄（67,516 筆）不納入：多為引用格式，對問答幫助小、會稀釋向量檢索。

### 4.3 14.6 萬件的首次載入怎麼做

| | 方案 A：直接放進每晚流程 | 方案 B：首次載入另外分批跑，之後每晚只做增量 |
|---|---|---|
| 做法概述 | 第一個晚上攝取全部，訂閱器照常消化 | 在夜間流程以外的時段，依分類分批（繪畫、雕塑、素描 → 其他 → 版畫與攝影）攝取並讓訂閱器追上；之後每晚依內容雜湊只處理變動 |
| 優點 | 不用額外步驟 | 不壓縮每晚流程時間窗；每批可檢查一致性與品質、有問題可停 |
| 缺點／風險 | 首次載入嵌入實測約 1.4 小時（bge-m3 32.2 chunk／秒，2026-10-01 以 NGA 真實文字抽樣量測），含寫入三庫估計共 2～3 小時，遠超每晚流程約 31 分鐘的窗口，會拖到隔天上午並與使用者查詢搶 Ollama | 需要人工排定數個時段 |
| 成本 | 低 | 中 |

**選定方案 B。** 首次載入完成前，`hybrid` 等策略照常服務；每批完成後跑 `ingest verify`。

### 4.4 藝術家身分怎麼整併（ULAN）

| | 方案 A：實體合併節點 | 方案 B：不刪節點，加 `SAME_AS` 指向代表節點 |
|---|---|---|
| 做法概述 | 同一 ULAN 的多個 Artist 節點合併為一個，關係全部改接 | 每個 ULAN 建一個代表節點（`ulan_id` 屬性）；其他同人節點以 `(:Artist)-[:SAME_AS]->(:Artist {ulan_id})` 連過去，檢索時沿 `SAME_AS` 聚合 |
| 優點 | 圖最乾淨 | **可回滾**（刪除 `SAME_AS` 即恢復）；不動既有節點與訂閱器的寫入邏輯；誤判只影響一條邊 |
| 缺點／風險 | 不可逆；社群版沒有交易式合併工具，要自己搬關係；訂閱器下次寫入可能又建出重複節點 | 查詢要多走一步；圖裡仍保留重複節點 |
| 成本 | 高 | 中 |

**選定方案 B。** 對應來源分三級，**只有第 1、2 級自動建 `SAME_AS`**：

1. NGA 自帶 ULAN 編號 → 直接採用。
2. 名稱與生卒年都與 ULAN 一致、且只有一個候選 → 自動採用。
3. 其他（同名多人、無年代、名稱是 URI 等）→ 產出審核清單（Excel），**人工確認才建立**。

### 4.5 AAT 中文術語怎麼進詞典

| | 方案 A：自動匯入全部繁中標籤 | 方案 B：限定類別產生候選，人工審核後匯入 |
|---|---|---|
| 做法概述 | 把 AAT 所有 zh-hant 標籤對應英文 prefLabel 寫進詞典 | 只取風格與時期、材料、技法、作品類型等類別；產出「英文 → 中文」候選表，審核通過的才寫入 |
| 優點 | 一次到位 | 避免歧義 |
| 缺點／風險 | **已實測到誤譯**：Realism 含「唯實論」（哲學）、bronze 含「古銅色」（顏色）；日常詞被轉換會讓一般提問變成錯的英文 | 需要人工時間（估數百詞） |
| 成本 | 低 | 中 |

**選定方案 B。** 實測：現有詞典 30 個英文詞條中 22 個能在 AAT 找到繁中標籤，其餘 8 個（如 Impressionism，AAT 用 Impressionist）需人工對應。

## 5. 系統設計

**資料流**

```
NGA GitHub CSV ──(條件下載)──► crawlers/data/raw/nga/<日期>/*.csv
        │
        ▼
ingest/sources_nga.py：join objects＋objects_constituents（role=artist）＋constituents＋objects_terms（Style/School）
        │  產出作品紀錄 id=nga_<objectid>，含 artist_ulan_ids、wikidata_id
        ▼
既有 ingest_artworks → catalog.documents/chunks → outbox → ChromaDB／ES／Neo4j 訂閱器（不改）

Getty ULAN ──(SPARQL，本地快取)──► 對應清單 ──► Neo4j：代表節點 ulan_id＋SAME_AS（第 1、2 級）
                                        └──► 審核清單.xlsx（第 3 級，人工確認後匯入）
Getty AAT ──(SPARQL，本地快取)──► 候選表.xlsx ──人工審核──► 查詢翻譯詞典
```

**對外介面（CLI，沿用既有指令風格）**

- `python -m ingest fetch-nga [--force]`：條件下載 CSV（未變更則略過）。
- `python -m ingest run --source nga [--only-classification Painting,...]`：攝取（分批參數供首次載入用）。
- `python -m getty ulan-match [--apply]`、`python -m getty ulan-review --import <xlsx>`：產生對應、匯入審核結果。
- `python -m getty aat-candidates`、`python -m getty aat-import <xlsx>`：產生與匯入中文術語。
- 每晚流程新增「NGA 下載＋攝取」一步；Getty 不進每晚流程（詞彙變動慢，手動或每月一次）。

**資料模型／schema 變更**

- catalog：無 schema 變更（新 `source = 'nga'`；作品的 ULAN／Wikidata 編號放在既有 `metadata`）。
- Neo4j：Artist 新增屬性 `ulan_id`；新增關係 `SAME_AS`；`ulan_id` 加唯一性約束（只限代表節點）。
- 檢索：`SystemGraphRAG` 由藝術家展開作品時沿 `SAME_AS` 聚合（舊策略不改，保持對照組）。
- 新增本地快取：`crawlers/data/raw/getty/`（SPARQL 結果，避免重複查詢）。

**錯誤處理與日誌**

- 下載失敗：保留前一版 CSV、該晚跳過 NGA 攝取並寫入日誌，不影響其他來源。
- 單筆正規化失敗：記錄 objectid 後跳過，整批不中斷；失敗數超過 1% 時開 `eval.alerts`。
- Getty 查詢：限速（每秒 ≤ 2 次）、失敗重試 3 次、結果寫快取；查不到不視為錯誤。

## 6. 安全與隱私考量

- **無金鑰**：NGA、Getty 皆免金鑰，不新增任何機密設定。
- **授權**：NGA 為 CC0；Getty 為 ODC-By 1.0，**須註明出處**——系統說明、論文與投稿需加上「This work contains information from Getty's Union List of Artist Names (ULAN)® and Art & Architecture Thesaurus (AAT)®, made available under the ODC Attribution License」。
- **個資**：來源史會出現歷代收藏者姓名，屬 NGA 公開的館藏研究資料；不涉及系統使用者個資，不需 `BIZ_LOGGING`。
- **外部請求**：只對 `raw.githubusercontent.com`、`vocab.getty.edu` 發出唯讀請求，並限速。

## 7. 測試策略

- **單元**：以 NGA CSV 真實樣本（數十列、含多作者、無作者、極長來源史）作為測試資料，驗證 join、欄位對應、文件文字組成；ULAN 三級對應規則；AAT 候選的類別篩選與歧義排除。
- **整合**：拋棄式 PostgreSQL 攝取樣本，確認 catalog／outbox 事件正確；Neo4j `SAME_AS` 建立與回滾。
- **驗收**：
  - 每批載入後 `ingest verify --source nga` 一致；
  - 檢索實測：「Vermeer Woman Holding a Balance」等 NGA 名作可由 `hybrid` 找到；
  - 「林布蘭有哪些作品」經 `SAME_AS` 聚合後，作品數大於任一單一節點；
  - 重產黃金集候選表，確認含 NGA 巴洛克作品。

## 8. 部署與運維

- **機器**：現行單機（WSL `Ubuntu-22.04`），不新增服務。
- **首次載入**：依 4.3 方案 B 分批，避開 03:00–03:40 夜間流程，每批後檢查一致性與告警。
- **容量**：ChromaDB／ES 向量量約為現在的 30 倍；已有 DAT-17 磁碟告警（F 槽剩 98.5%、WSL 剩 82.6%）。ES 目前未設 heap 上限（OPS-07），建議先完成 heap 設定。
- **監控**：沿用 `eval.alerts`（一致性、磁碟、嵌入標註）；新增 NGA 正規化失敗率告警。
- **回滾**：
  - NGA：以 `ingest run --source nga --prune` 搭配空快照，對全部 NGA 文件發出 soft_delete 事件，三庫自動撤出；
  - ULAN：刪除所有 `SAME_AS` 與代表節點上的 `ulan_id`；
  - AAT：詞典檔在 git 版控內，回復前一版即可。

## 9. 未解決問題

- **首次嵌入需要多久**：已實測（見 4.3）。每晚增量的嵌入只需平日約 0.2 分鐘、峰值日（2,708 件）約 1.6 分鐘，夜間流程的額外時間主要在下載與比對。
- **14.6 萬件中約 6.5 萬件是版畫、2.3 萬件是攝影**：同一版畫常有多個狀態（states），可能讓檢索結果被相似版畫淹沒。本文照使用者決定全收，但建議在黃金集基準出來後檢查，必要時降低其權重。
- **ES 記憶體**：OPS-07 發現 ES 未設 heap、佔 12.3 GB；資料量 30 倍後壓力更大，需使用者以 sudo 設定。
- **三份詞典檔**：AAT 匯入前，建議先整併成一份（後端與分類腳本讀不同檔）。
- **Tier 與核可**：本系統為 Tier B，依 `CLAUDE.md` 須指導老師核可才能實作；2026-09-23 的豁免只涵蓋 Phase 3／4／5，**不含本案**，需另行取得核可或確認豁免範圍（評估表 §八）。
- **審核人力**：ULAN 第 3 級清單與 AAT 候選表都需人工審核，數量待產出後估算。
