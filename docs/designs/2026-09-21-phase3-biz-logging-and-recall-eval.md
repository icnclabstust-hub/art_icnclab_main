# 設計文件：Phase 3「評測迴路」——對話記錄（biz）與召回率量測（eval）

> 狀態：**草案，待使用者確認**（GD 步驟 3）。確認前不寫實作。
> 上位設計：`docs/designs/2026-09-20-target-architecture-consistency-eval-faithfulness.md`（§5.1 Phase 3、§4.3、§7、§9）
> 評估表簽核：`...-assessment.md` §九 目前仍為空白，依 `CLAUDE.md` R5 由使用者／老師填寫。
> 風險 Tier：**B**（會修改線上後端的請求路徑與 Open WebUI 的 pipe，並新增排程）。實作前需老師核可。

## 1. 背景與問題

架構圖下半部的「召回率量測與回饋迴圈」目前完全沒有內容：`biz.users／conversations／messages` 三張表與 `eval.golden_queries／measurements／alerts` 三張表已建好（`context/database/04-catalog-biz-eval-schema.sql`），但**全部是 0 筆**，後端沒有任何程式寫入或讀取它們。

後果：
- 不知道使用者實際問了什麼、系統引用了哪些資料；`messages.cited_chunk_ids` 沒有來源，也就無法從正式流量抽樣擴充黃金測試集。
- 改了檢索邏輯或資料（例如這次的 Neo4j 過濾、Yale 資料更新）**沒有客觀數字**告訴我們召回率是升是降，只能靠人工看 15 題的 Word 檔（`scripts/run_24combo_evaluation.py`）。
- 後續 Phase 4（證據判定與拒答、忠實度守門員）的門檻需要用黃金測試集校準，沒有它就是憑感覺訂。

**誰會用**：實驗室成員（看每晚量測報表、處理告警）；後續 Phase 4／5 的程式（用同一套量測選門檻、選路由）。
**不做會怎樣**：Phase 4／5 無法被驗證，架構圖的「回饋迴圈」只是圖。

## 2. 目標與非目標

### 目標
1. 後端把每次問答（問題、答案、策略路由、引用的資料）記錄到 `biz`，失敗不得影響回答。
2. 建立 `eval.golden_queries`：以現有 15 題為起點，含人工確認的相關資料標註。
3. 每晚（資料同步完成後）對黃金測試集重放檢索，量測三個檢索階段（融合前、RRF 後、重排後）的 Recall@K 與 nDCG@K，依路由分組寫入 `eval.measurements`。
4. 指標較基準下降超過 10% 時寫入 `eval.alerts`。
5. 提供 `GET /api/v1/eval/routes/compare` 比較報表（上位設計 §5.3）。

### 非目標（本 Phase 不做）
- **`post_generation` 階段**（忠實度、答案相關性）：忠實度守門員屬 Phase 4。
- **拒答率告警（>15%）與拒答抽樣佇列**：拒答機制尚不存在（Phase 4）；本 Phase 只做「低相似度抽樣」。
- 自動改路由（Phase 5）、Redis 語意快取（另案）。

## 3. 現況與重用

| 既有件 | 現況 | 本 Phase 如何使用 |
|---|---|---|
| `biz`／`eval` 六張表 | 已建、0 筆 | 直接使用；預計以**新增欄位**的方式補足（§5.2），不改動既有欄位 |
| `/api/v1/retrieve` | 僅檢索、不生成，已被 `eval_step1_fetch_context.py` 使用 | 量測用的檢索入口（不呼叫 LLM，成本低） |
| `scripts/run_24combo_evaluation.py` 的 `QUESTIONS` | 硬編碼 15 題 | 轉為黃金測試集的初始題目 |
| `scripts/eval_step1~6` | 一次性離線評測（Word／Excel 輸出） | 參考其指標邏輯；不直接改寫，避免影響既有論文資料 |
| 稽核 middleware（`event_id`） | 只記 log | 沿用其 `event_id` 作為 `messages` 的追溯鍵 |
| `catalog.chunks`／`documents` | 5,747 chunk／3,955 文件，`external_id` 對應檢索庫 id | 標註與量測時用 UUIDv5（`ingest/ids.py`）對齊 |
| `adaptive_strategy_monitor.py`（659 行）、`optimization_manager.py`（500 行）、`alert_and_optimization_system.py`（803 行） | 主設計 §9 註明「尚未逐行核對」；目前後端**未引用**它們 | **需在開工前補做細讀**，判斷是否可局部重用，否則不引入 |

### 調查發現的三個缺口（會影響設計）
1. **Open WebUI 的 pipe 沒有傳身分**：三支 pipe（`openwebui-pipes/*.py`）只送 `query／model_combination_id／max_results`，後端拿不到 `user_id`、`conversation_id`，`biz.conversations` 無從建立。
2. **檢索結果沒有帶 chunk id**：`VectorOnlyRAG` 的回傳項目只有 `content／metadata／score／source`，沒有讀 ChromaDB 回傳的 `ids`；`cited_chunk_ids` 目前**算不出來**。
3. **圖檢索的結果是「實體」不是 chunk**：Neo4j 策略回傳的是 Artist／Artwork 節點文字，與 chunk 無一對一關係。

## 4. 方案比較

### 4.1 召回率的計算粒度
| | 方案 A：chunk 層級（schema 現況：`relevant_chunk_ids`） | 方案 B：文件層級（以 `parent_id`／作品 id 為單位） |
|---|---|---|
| 做法 | 標註與比對都用 chunk id | 命中任何屬於該文件的 chunk／實體就算命中該文件 |
| 優點 | 精細；貼近上位設計 | 三種檢索庫（向量、全文、圖）**可用同一把尺比較**；標註量小一個量級（一件作品只標一次） |
| 缺點 | 圖檢索無法對到 chunk，只能排除圖路由；chunk 切法一變（如過時 chunk 被撤出）標註即失效；標註量大 | 看不出「同一文件哪一段更好」 |
| **建議** | | **方案 B**：架構圖的目的是比較 Naive／Advanced／Graph／Agentic 四路由，圖路由必須能被量測；標註欄位仍沿用 `relevant_chunk_ids`（存文件的 doc_id 也可，或新增 `relevant_doc_ids`，見 §5.2） |

### 4.2 記錄與量測放在哪裡
| | 方案 A：同步內嵌於 `/api/v1/query` | 方案 B：非同步寫入＋獨立量測程式（**建議**） |
|---|---|---|
| biz 記錄 | 回答前同步寫 Postgres | 回答後由背景工作寫入（有上限的佇列；佇列滿或 DB 失敗只記 log，不影響回答） |
| 量測 | 在正式請求中順便算各階段分數 | 由夜間排程的量測程式呼叫一個**專用的 trace 入口**（回傳各階段候選），與正式請求分離 |
| 優點 | 簡單、資料即時 | 服務在線時不增加延遲、DB 出問題不拖垮回答；量測用固定的黃金題目，結果可跨日比較（正式流量每天不同，不可比） |
| 缺點 | DB 抖動直接變成使用者延遲；量測結果被流量組成影響 | 多一個排程與 trace 入口；背景佇列的資料在程式重啟時可能遺失少量記錄 |
| **建議** | | **方案 B**；`BIZ_LOGGING=0` 環境變數可一鍵關閉記錄 |

## 5. 系統設計（草案）

### 5.1 資料流
```
Open WebUI pipe ──(user_id, chat_id)──► /api/v1/query ──► 回答（不受影響）
                                              └─背景佇列─► biz.users / conversations / messages（含 cited 文件 id）

夜間流程：… 三庫同步 → 一致性驗證 → 【eval 量測】→ 備份
  eval runner ──► /api/v1/eval/trace（不呼叫 LLM，回傳 pre_fusion／post_rrf／post_rerank 候選）
             └──► 對照 eval.golden_queries → eval.measurements → 與基準比較 → eval.alerts
```

### 5.2 Schema 補充（草案，皆為新增，不改既有欄位）
```sql
ALTER TABLE eval.golden_queries  ADD COLUMN relevant_doc_ids UUID[] NOT NULL DEFAULT '{}',
                                 ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'
                                     CHECK (status IN ('active','stale','retired'));  -- 標註的文件被撤出時標 stale
ALTER TABLE eval.measurements    ADD COLUMN run_id UUID, ADD COLUMN k INT;
CREATE TABLE eval.runs (run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), started_at TIMESTAMP DEFAULT now(),
                        trigger VARCHAR(20) CHECK (trigger IN ('nightly','pre_deploy','manual')),
                        is_baseline BOOLEAN NOT NULL DEFAULT FALSE);   -- 人工確認的基準 run
ALTER TABLE biz.messages         ADD COLUMN event_id UUID, ADD COLUMN cited_doc_ids UUID[] NOT NULL DEFAULT '{}';
```

### 5.3 介面草案
```
POST /api/v1/query            新增可選 body 欄位：user_id?, conversation_id?（pipe 從 Open WebUI 的 __user__／__metadata__ 取得）
                              回應新增：event_id, cited_doc_ids（不改變既有欄位）
POST /api/v1/eval/trace       內部用；輸入 query＋route_id，輸出各階段候選（doc_id、rank、score），不呼叫 LLM
GET  /api/v1/eval/routes/compare?since=…   依 route_id 分組的 Recall@K／nDCG@K 比較（上位設計 §5.3）
CLI  python -m evalrun run --trigger nightly|manual [--set-baseline]
     python -m evalrun seed-golden        由 15 題產生候選標註清單供人工確認
```

### 5.4 黃金測試集建立流程（半自動，避免全手工）
1. 把 15 題放進 `eval.golden_queries`（`source='manual'`）。
2. 每題以四種路由各取 Top-20 候選聯集，輸出成一份**標註清單**（題目、候選文件標題／來源／摘要）。
3. 由人工勾選相關文件 → 寫入 `relevant_doc_ids`。
4. 之後從 `biz.messages` 抽樣正式問題（`source='sampled_from_production'`），同樣經人工確認才進測試集。

### 5.5 錯誤處理與運維
- biz 寫入失敗：只記 log，計數器超過門檻才提示；**不重試阻塞、不影響回答**。
- 量測失敗：該次 run 標記失敗、不產生告警（避免把「量測壞了」誤報成「召回率掉了」）；夜間流程沿用 `run_step`，失敗不中斷後續備份。
- 黃金題目標註的文件被撤出或隔離：該題標 `stale`，排除於指標之外並列入報表，提示人工複審。
- 基準：`is_baseline` 的 run，由人工設定；告警＝目前 run 相對基準下降超過 10%。
- **回滾**：`BIZ_LOGGING=0` 關記錄；量測從夜間腳本移除一行即停；新增欄位與表可保留，不影響既有功能。

## 6. 安全與隱私考量
- `biz.messages` 會保存使用者的問題與答案：屬個人可識別資料的邊緣（S-15）。建議只存 Open WebUI 的**內部 user id（匿名 UUID）**，不存姓名與信箱；保存期限與刪除方式需要拍板（§9）。
- trace 入口為內部用途，只綁 `127.0.0.1`，不經 Open WebUI 暴露；不接受任意路徑或指令。
- 記錄與標註內容一律視為資料、不當指令執行（沿用掃描器對提示注入的原則）。

## 7. 測試策略
- **單元**：Recall@K／nDCG@K 計算（含空標註、重複命中、K 大於候選數）；基準比較與 10% 門檻邊界；stale 判定；佇列滿與 DB 失敗時「回答不受影響」。
- **整合**（沿用 `tests/python/` 的真實 PostgreSQL fixture）：寫入後可查、`cited_doc_ids` 與 catalog 的 doc id 對得上；trace 入口三階段輸出與 `/retrieve` 一致。
- **驗收**：15 題黃金集跑出的數值方向與既有 `metrics_results` 的人工評估一致；故意把某路由的檢索弄壞，量測應報出下降並觸發告警。
- **線上安全**：開啟記錄前後，`/api/v1/query` 的延遲分布比較（P50／P95）無明顯劣化。

## 8. 部署與運維
1. 新增欄位與表（可重複執行的 SQL，仿 `04`／`05`／`06` 的做法）。
2. 後端加入記錄與 trace 入口（預設 `BIZ_LOGGING=0`，驗證後再開）；重啟約 10 秒。
3. pipe 傳身分（三支 pipe 各改一處）；Open WebUI 端需在管理介面更新 pipe 內容。
4. 建黃金集（需人工標註）→ 設基準 run → 才把量測加進夜間流程。
- 監控：`eval.alerts` 先只寫表與報表；串接 Prometheus／通知管道視需求再議，不重建告警系統（沿用主設計 §8）。

## 9. 未解決問題（**需要使用者回答**）
1. **誰來標註？** 15 題 × 約 20 候選，預估 2～3 小時；由你、實驗室成員或老師？（主設計 §9 已列為時程風險）
2. **召回率粒度**是否同意採**文件層級**（§4.1 方案 B）？
3. **`biz.messages` 保存期限**？（建議 180 天，到期刪除；或永久保存但匿名化）
4. Open WebUI 的使用者是否**單人使用**（只有你）？若是，`biz.users` 可簡化為單一使用者，隱私考量大幅降低。
5. 三支未引用的監控檔（1,962 行）是否同意在開工前**先花一次細讀**判斷可否重用，還是**一律不用、只寫必要的最小程式**？（建議後者）
6. 量測要涵蓋哪些路由？架構圖只畫 Naive／Advanced／Graph／Agentic 四類，但後端實際註冊了 **11 個策略 id**（`vector_only`、`hybrid_es_rag`、`graph_only`、`hybrid_balanced`、`advanced_rag`、`agentic_rag`、`self_rag`、`naive_rag`、`naive_graph_rag`〔與 `graph_only` 是同一個實例〕、`advanced_graph_rag`、`agentic_graph_rag`）。建議先量與 24 組合評測相同的 4 個 RAG 策略（以 `scripts/run_24combo_evaluation.py` 的 `STRATEGIES` 為準），其餘之後再加；`route_id` 欄位直接使用策略 id。

---

## 附錄：後續 Phase 路線與依賴（各自另寫設計文件、各自過 GD）

| 順序 | 內容 | 依賴 | 卡點（需先解決） |
|---|---|---|---|
| **Phase 3（本文件）** | biz 記錄、黃金集、三階段量測、告警 | — | 上方 §9 六題 |
| Phase 4a | 證據判定＋無檢索支援／拒答 | Phase 3 的黃金集（校準門檻） | 門檻數值需離線校準（主設計 §9） |
| Phase 4b | 忠實度守門員（粗篩同步＋NLI 精篩非同步）、線上攔截記錄 | 4a、`post_generation` 量測 | NLI 模型選擇與延遲預算 |
| Phase 4c | 模糊檢索 fallback | 4a | 圖面「K>0.7」的語意需與老師／圖面作者確認（主設計 §9） |
| Phase 5 | Router 自動路由＋系統級 RRF 收斂、實驗層 | Phase 3 的路由比較報表 | 需累積足夠的量測資料 |
| 另案 | Redis 語意快取＋outbox 觸發失效；嵌入模型「名稱＋版本」標註；每週全量一致性稽核 | 各自獨立 | Redis 目前已在 6379 執行但後端未使用（現為記憶體快取） |
