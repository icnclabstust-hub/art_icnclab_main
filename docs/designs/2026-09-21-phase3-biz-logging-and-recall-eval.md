# 設計文件：Phase 3「評測迴路」——對話記錄（biz）與召回率量測（eval）

> 狀態：**草案，待使用者確認**（GD 步驟 3）。確認前不寫實作。
> 上位設計：`docs/designs/2026-09-20-target-architecture-consistency-eval-faithfulness.md`（§5.1 Phase 3、§4.3、§7、§9）
> 評估表簽核：`...-assessment.md` §九 目前仍為空白，依 `CLAUDE.md` R5 由使用者／老師填寫。
> 風險 Tier：**B**（會修改線上後端的請求路徑與 Open WebUI 的 pipe，並新增排程）；開放多人使用後**新增個資處理**，評估表須補「隱私影響評估」。實作前需老師核可。
> 使用者回覆（2026-09-21）已併入：見 §6（隱私）與 §9（已決定／待訂項目）。

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
| `adaptive_strategy_monitor.py`（659 行）、`alert_and_optimization_system.py`（803 行）、`optimization_manager.py`（500 行） | **已細讀，結論：Phase 3 不重用**（見下方「三支檔案的調查結論」） | 不引入 |

### 三支檔案的調查結論（2026-09-21 細讀，回應原 §9 第 5 題）
| 檔案 | 實際用途 | 為何不適用於 Phase 3 |
|---|---|---|
| `adaptive_strategy_monitor.py` | 監控「自適應策略」（依賴 `enhanced_adaptive_strategies`）的延遲、成功率、探索率，輸出 Prometheus 指標 | 量的是**營運效能**，不是檢索的 Recall／nDCG；且綁定自適應策略模組；只被 `realtime_monitoring_service.py`、`unified_monitoring_service.py` 引用，兩者沒有出現在任何啟動腳本或文件中 |
| `alert_and_optimization_system.py` | 依上述指標告警，並**自動調整**學習率、探索率、重設策略權重、清快取 | 「無人介入、自動改系統參數」與本設計「告警只通知、由人決定」的原則相反；Phase 5 的路由回饋也應由實驗層報表人工確認後才生效 |
| `optimization_manager.py` | Redis 快取（`SmartCache`）、混合檢索、查詢擴充、非同步處理 | 沒有任何地方引用它；其快取是以「查詢字串的 md5」精確比對，**不是語意快取**，連 Redis 時沒有帶密碼、資料更新後**沒有失效機制**（會回傳舊答案）。與 Phase 3 無關，但與「Redis 語意快取」另案有關，該案應重新設計而非直接沿用 |

結論：Phase 3 **只寫必要的最小程式**（記錄、trace 入口、量測、比較），不引入這三支檔案；它們列入後續清理候選，另案處理。

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

## 6. 安全與隱私考量（**系統將開放更多人使用，須符合 AI 與個資相關法規**）

> 使用者已說明（2026-09-21）：日後會有更多使用者，隱私權要符合 AI 合格法規。
> **限制聲明**：我（AI 助理）無法確認哪些法規條文適用於本系統，也不提供法律意見。適用法規（例如個人資料保護法、人工智慧相關法規、學校／研究倫理規定）與具體義務，請由指導老師、學校資訊或法務單位確認；下列是**依一般資料保護原則做的設計**，用來降低之後被要求調整的成本，並列為評估表的必填項目。

### 6.1 設計原則
| 原則 | 本 Phase 的做法 |
|---|---|
| 資料最少化 | `biz` 只存：匿名使用者代號、對話 id、問題與答案文字、路由、引用的文件 id、時間。**不存**姓名、信箱、IP、瀏覽器資訊 |
| 匿名化 | Open WebUI 的使用者 id 以**加鹽雜湊**後存入 `biz.users.user_id`（鹽存在 `.env`，不進 repo）；不存原始 id |
| 目的限定 | 記錄只用於「除錯、評測、改進檢索」，不用於使用者行為分析或對外提供；此用途寫在告知文字中 |
| 告知 | Open WebUI 頁面顯示簡短告知（會記錄問答內容、用途、保存期限、如何要求刪除）；上線前文字需經老師／單位確認 |
| 保存期限與自動刪除 | 有明確期限（見 §9 待訂），由排程自動清除（做法仿 Neo4j 的 `purge`，先預覽再套用）；備份輪替（目前保留 7 批）意味著刪除最多 7 天後才完全從備份消失，需在告知中說明 |
| 使用者權利 | 提供依匿名代號**查詢、匯出、刪除**某使用者全部記錄的指令（`ON DELETE CASCADE` 已在 schema 中）；刪除後不影響黃金測試集（見下） |
| 個資混入問題內容 | 使用者可能在問題中打入個資（信箱、電話、身分證字號）。存入前以規則式遮罩（信箱、電話、證號格式），遮罩後才寫入；此規則可重用 `ingest/scanner.py` 的做法與測試方式 |
| 存取控制 | 資料庫新增專用角色：後端只有 `biz` 的 INSERT，量測程式只有 `eval` 的讀寫與 `biz` 的 SELECT，人工檢視用唯讀角色；不使用超級使用者連線（延續備份帳號 `06-backup-read-grants.sql` 的做法） |
| 日誌 | 稽核 log 只記 `event_id`／路徑／耗時，**不記問題與答案原文**（S-15，沿用現況） |
| 資料不出境 | 生成與嵌入皆在本地（Ollama、BGE-M3）；記錄不送任何外部服務 |

### 6.2 黃金測試集與正式流量的關係
- 從 `biz.messages` 抽樣進 `eval.golden_queries` 屬於**二次使用**，用途與原告知不同：預設**不抽樣**；只有在告知文字明確涵蓋「用於改進評測」，且題目經**人工去識別化檢視**後才進測試集。
- 進入測試集的題目**不帶 `user_id`／`conversation_id`**，使用者要求刪除時不需修改測試集，測試集也不能被反查到人。

### 6.3 其他安全項目
- trace 入口只綁 `127.0.0.1`，不經 Open WebUI 暴露；不接受任意路徑或指令。
- 記錄與標註內容一律視為資料、不當指令執行（沿用掃描器對提示注入的原則）。
- **多人使用另帶來的問題（不在本 Phase 解決，先登記）**：請求頻率限制、Open WebUI 的帳號管理與登入、後端 API 目前無驗證（Open WebUI 之外的人若能連到 8001 即可直接呼叫）。

## 7. 測試策略
- **單元**：Recall@K／nDCG@K 計算（含空標註、重複命中、K 大於候選數）；基準比較與 10% 門檻邊界；stale 判定；佇列滿與 DB 失敗時「回答不受影響」。
- **整合**（沿用 `tests/python/` 的真實 PostgreSQL fixture）：寫入後可查、`cited_doc_ids` 與 catalog 的 doc id 對得上；trace 入口三階段輸出與 `/retrieve` 一致。
- **驗收**：15 題黃金集跑出的數值方向與既有 `metrics_results` 的人工評估一致；故意把某路由的檢索弄壞，量測應報出下降並觸發告警。
- **線上安全**：開啟記錄前後，`/api/v1/query` 的延遲分布比較（P50／P95）無明顯劣化。

## 8. 部署與運維
0. **前置條件（開啟 `BIZ_LOGGING` 之前必須完成）**：適用法規確認、告知文字定案並顯示、保存期限定案、遮罩與刪除指令就緒、資料庫專用角色建立。未滿足前 `BIZ_LOGGING` 保持關閉。
1. 新增欄位與表（可重複執行的 SQL，仿 `04`／`05`／`06` 的做法）。
2. 後端加入記錄與 trace 入口（預設 `BIZ_LOGGING=0`，驗證後再開）；重啟約 10 秒。
3. pipe 傳身分（三支 pipe 各改一處）；Open WebUI 端需在管理介面更新 pipe 內容。
4. 建黃金集（需人工標註）→ 設基準 run → 才把量測加進夜間流程。
- 監控：`eval.alerts` 先只寫表與報表；串接 Prometheus／通知管道視需求再議，不重建告警系統（沿用主設計 §8）。

## 9. 決定與待訂項目

### 已決定（使用者，2026-09-21）
| # | 項目 | 決定 |
|---|---|---|
| 6 | 量測涵蓋的路由 | 先量與 24 組合評測相同的 4 個策略：`naive_rag`、`advanced_rag`、`graph_only`、`agentic_rag`（後端共註冊 11 個策略 id，其餘之後再加）；`route_id` 直接使用策略 id |
| 5 | 三支監控檔 | 使用者要求「確認一下」→ 細讀結論為**不重用**（見 §3）；Phase 3 只寫最小程式。使用者若對結論有異議請提出 |
| 4 | 使用者範圍 | 日後開放更多使用者；隱私須符合 AI 相關法規 → 已改寫 §6 與 §8 前置條件；**適用法規需由老師／單位確認** |

### 待訂項目（尚未決定，**不要當成已決定**；實作前必須定案）
| # | 項目 | 目前的建議 | 卡在哪 |
|---|---|---|---|
| 1 | **誰來標註**黃金測試集（15 題 × 約 20 個候選，預估 2～3 小時） | 無（需要人選） | 需要有人力；沒有標註就沒有黃金測試集，量測無法開始（這是 Phase 3 的關鍵路徑） |
| 2 | **召回率粒度**：文件層級或 chunk 層級 | 文件層級（方案 B，見 §4.1） | 使用者選擇先列為待訂 |
| 3 | **`biz.messages` 保存期限** | 180 天，到期自動刪除；黃金測試集不帶使用者資訊（見 §6.2） | 期限與法規要求有關，須待 #4 的法規確認後定案（使用者將此項記為待訂） |
| 7（新增） | **適用法規與告知文字** | 由老師／學校資訊或法務確認 | 我無法確認法規條文，不代為判定 |
| 8（新增） | **開放多人使用時的存取控制**（登入、頻率限制、後端 8001 無驗證） | 另案處理，本 Phase 先登記 | 需要決定 Open WebUI 的帳號策略 |

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
