# 設計文件：RAG 系統目標架構改版（PostgreSQL 一致性層／召回率量測回饋迴路／忠實度安全防護＋模糊檢索＋實驗層）

> GD 設計閘門步驟 3 產出。對應評估表：`docs/designs/2026-09-20-target-architecture-consistency-eval-faithfulness-assessment.md`
> 依 `docs/templates/DESIGN_DOC.md` 指引，因涉及 Tier 判定討論（見第 6 節與評估表），本文篇幅不設上限。
> 本文為**設計層級文件**，僅含資料流、對外介面、schema 草案（型別／DDL 草稿）等示意內容，不含可執行實作程式碼，符合 `CLAUDE.md` R2。

## 1. 背景與問題

實驗室與指導老師已就「修正後 RAG 架構總覽圖」達成共識，作為現有藝術史 RAG 系統的**目標藍圖**，預計逐步（而非一次性）取代現行 Node.js／Open WebUI pipes／langchain-rag 腳本組成的架構。

三問結論：

1. **要解決什麼問題？** 現況有三類具體痛點：(a) ChromaDB／Elasticsearch／Neo4j 三個檢索庫各自獨立寫入，沒有單一事實來源，容易飄移不一致；(b) 沒有任何可量化的召回率／nDCG 評測機制，策略調整全靠人工肉眼判斷答案好壞；(c) 生成路徑沒有忠實度／安全把關與檢索不足時的分支處理，幻覺與提示注入風險無防護。
2. **誰會用？** 內部（實驗室與美術系合作對象）於內網／校內環境使用之研究型 RAG 服務，非公開對外服務，無個資或成績資料。對照 `CODE_REVIEW_STANDARD.md` 表列，本系統即「art_icnclab RAG 服務」，現行分級為 **Tier B**。
3. **不做會怎樣？** 三庫資料飄移會持續累積、無法被系統性偵測；路由策略（Naive/Advanced/Graph/Agentic）的優劣無法量化比較，導致後續論文／專題產出的實驗結論缺乏可信的評測基礎；生成端沒有忠實度把關，幻覈與拒答不足的問題無法被觀測與追蹤，也沒有機制在答錯時進行風險標示。

## 2. 目標與非目標

### 目標

- 建立 PostgreSQL 為單一事實來源的資料一致性層（`catalog` schema + outbox 事件），讓 ChromaDB／Elasticsearch／Neo4j／Redis 皆為訂閱者，取代現行手動全量重掃腳本。
- 建立以 `eval.golden_queries` 為核心的召回率量測與回饋迴路，產出可長期追蹤的 Recall／nDCG／忠實度指標與告警。
- 建立線上忠實度／安全守門員、模糊檢索備援、以及依 `route_id` 分組的實驗層，並讓實驗結果回饋 RAG Router。
- 整個過程採漸進式（strangler-fig）遷移，任何階段中斷都不影響現行服務可用性。

### 非目標（本次明確不做）

- 不在本次重寫 Open WebUI 前端本身，僅調整其呼叫的後端介面。
- 不追求圖中所有埠號與現況強制一致（見第 5.5 節埠號規劃，現況衝突需要一次獨立決策，不在本設計文件內拍板）。
- 不實作 Google Books 即時補充查詢以外的其他外部資料源整合。
- 不做多租戶／使用者權限系統；`biz.users` 僅供對應 Open WebUI 既有使用者 id，不新建認證機制。
- 不追求金融等級的內容審核；惡意內容掃描器以「偵測已知注入樣式＋人工複審佇列」為範圍，不做端到端的內容審核 ML 模型訓練。
- 本文不含實際 Neo4j／Postgres 遷移腳本、不含可執行程式碼；僅提供 schema 與介面草案，實作留待 GD 通過後另行進行。

## 3. 現況與重用

（完整逐項調查見附錄 A；以下為摘要）

**主幹管線可重用項目：**

- Open WebUI、Ollama、ChromaDB、Elasticsearch、Neo4j 等基礎服務本身可直接沿用。
- `langchain-rag/unified_rag_manager_v2.py`：現行唯一的正式 FastAPI 後端，具路由分派字典模式與健康檢查端點，可作為新 Backend API 的漸進改造基礎，而非砍掉重練。
- `openwebui_hybrid_es_rag_multi_pipe.py` 內已有正確的 RRF 實作（`score=Σ1/(k+rank)`, k=60），可直接抽取為系統級 Fusion 節點的核心演算法。
- `langchain-rag/enhanced_neo4j_retriever.py` 內的 CrossEncoder（`bge-reranker-base`）reranker 程式碼完整可用，只是從未接入生產路徑，是 Reranker 節點最快的落地方式。
- `scripts/eval_step2_compute_metrics.py` 的 RAGAS 式 Faithfulness／Correctness／Retrieval Precision 計算方法論，可作為線上 Faithfulness Gate 與四段式量測的演算法基礎。
- `scripts/run_24combo_evaluation.py` + `eval_step3_build_xlsx.py` 已證明「force-switch 策略＋產出比較矩陣」技術可行，是實驗層的雛形。
- `src/database/connection.js`／`cacheManager.js`：Redis 連線抽象層可重用，快取語意需重做。
- `src/utils/cronScheduler.js`：既有 node-cron 排程基礎設施，可直接掛載 nightly 評測 job。

**缺口（需新建，詳見附錄 A 缺口清單）：** Postgres `catalog`/`biz` schema 全套、outbox 事件驅動同步機制、語意快取、意圖路由、系統級三路 Fusion、evidence sufficiency 分支、prompt 結構化分離、線上 Faithfulness Gate、模糊檢索、`eval.golden_queries`／`eval.alerts`／四段式量測管線、Neo4j 五種原子操作與生命週期管理、惡意內容掃描器、`route_id` 實驗層回饋閉環、統一埠號規劃。

**現況需先解的技術債（非新功能，但會卡住新架構）：**

- Backend API 埠號三方衝突：圖上寫 `:8001`，`docs/designs/2026-08-29-remove-docker-native-migration.md` 記載 ChromaDB 現行佔用 `8001`，`unified_rag_manager_v2.py` 實際預設埠是 `8007`，`.env.example` 卻寫 `8008`。此為現況設定漂移，需在 Phase 0 一併釐清（見第 5.5 節）。

## 4. 方案比較

### 4.1 總體遷移策略（至少兩案）

| | 方案 A：漸進式絞殺者遷移（Strangler Fig） | 方案 B：一次性大改版（Big Bang） |
|---|---|---|
| 做法概述 | 新模組（Postgres 一致性層／評測迴路／忠實度守門員）以「旁掛」方式先建置並在唯讀／觀測模式下並行驗證，確認穩定後才逐一切換成為關鍵路徑；四個階段（見第 5.1 節）可獨立上線、獨立回滾 | 依圖一次性重寫整條管線，新舊系統同時切換 |
| 優點 | 任一階段失敗只影響該階段，不影響現行服務；每階段皆可獨立產出可驗證的成果（符合實驗室學期式進度）；風險可分批由老師覆核 | 架構一致性最高，沒有新舊並存期的資料語意落差 |
| 缺點／風險 | 過渡期間需維護兩套邏輯（如新舊快取並存），總工時略高；新舊系統資料語意需刻意對齊 | 單次變更範圍過大，一旦出錯難以定位；現行服務會有明顯的中斷風險；不符合實驗室學生輪替、以學期為單位交付的現實 |
| 成本 | 分攤到多個小型可交付階段，各階段皆可獨立走 G0–G2 | 集中在單一次高風險上線，G2 覆核壓力極大 |

**選定方案：方案 A（漸進式絞殺者遷移）。** 理由：本系統為研究用內網服務（Tier B），沒有立即停機重建的急迫性；且已確認要「逐步取代」而非一次性替換（使用者於 Step 1 已確認）；分階段亦符合 GD 流程「每階段各自過 G0–G2」的精神，避免單一巨大變更闖關。

### 4.2 子系統 1：資料一致性層——同步機制

| | 方案 A：Postgres outbox + 事件訂閱（圖中設計） | 方案 B：既有全量重掃腳本＋加上 hash 比對，改為排程 diff-sync |
|---|---|---|
| 做法概述 | 寫入 `catalog.documents/chunks` 時，同一交易內寫入 `sync_events`；各檢索庫的訂閱器輪詢／訂閱 `sync_events`，依 `event_id` 增量套用 | 沿用 `sync_chromadb_to_elasticsearch.py` 的全量掃描邏輯，加上 `content_hash` 欄位比對，改為每日排程執行，只加不減 |
| 優點 | 增量、低延遲、可精確追蹤每個檢索庫的同步游標（`sync_cursor`）與落後量；符合圖中設計，且可原生支援 Neo4j 五種原子操作 | 改動小、風險低，現有腳本邏輯可延用 |
| 缺點／風險 | 需新增 outbox 表與訂閱器常駐程式，開發量較大 | 全量掃描隨資料量成長會變慢；仍是批次而非即時，無法精確定位「哪個事件、哪個庫還沒套用」；無法優雅支援 Neo4j 軟刪除/到期等狀態轉換語意 |

**選定方案：方案 A，但以方案 B 作為 Phase 1 過渡手段。** 理由：outbox 模式是本次改版的核心價值（解決三庫飄移），值得投入；但為避免第一階段就要求同時做完 schema＋訂閱器＋四種訂閱端，Phase 1 先用「方案 B 加 hash 比對」的排程 diff-sync 頂著現況需求，Phase 2 再替換為真正的 outbox 事件驅動，讓風險與工作量分兩批消化。

### 4.3 子系統 3：忠實度守門員——同步或非同步

| | 方案 A：全同步線上檢查（逐句忠實度在回應前完成） | 方案 B：兩段式（輕量同步前篩 + 重量非同步覆核） |
|---|---|---|
| 做法概述 | 回應前逐句跑完 NLI 精篩才回傳答案 | 先用輕量規則／小模型做粗篩（同步、低延遲），完整 NLI 精篩非同步跑，異常時才回頭標記/通知，必要時對高風險查詢類型（如需引用來源的問答）才走全同步 |
| 優點 | 保證使用者看到的答案已通過完整把關，安全性最高 | 延遲低，多數查詢體驗不受影響；重量模型可批次/離峰執行 |
| 缺點／風險 | 逐句 NLI 精篩為 LLM/NLI 模型呼叫，延遲可能達數秒至十數秒，影響使用體驗 | 非同步覆核發現異常時答案已送出，需靠事後標記／人工複審彌補，即時攔截率較低 |

**選定方案：方案 B，但粗篩為必經關卡、精篩比例可調。** 理由：圖中本身即標註「粗篩＋NLI精篩」兩段式，與方案 B 精神一致；同步全 NLI 精篩在研究型服務可接受的延遲預算下不切實際。粗篩（如關鍵詞黑名單、答案與檢索內容的向量相似度門檻）同步執行、未過即直接降級拒答；精篩（NLI 模型逐句比對）非同步執行並寫入 `eval` 側的攔截記錄，用於子系統2的回饋迴路與事後稽核，異常率高的模式再回頭調整粗篩門檻。

## 5. 系統設計

### 5.1 遷移階段（漸進式，對應第 4.1 節方案 A）

- **Phase 0（地基）**：釐清並鎖定服務埠號規劃（見 5.5 節）；在 Postgres 新建 `catalog`／`biz`／`eval` 三個 schema（僅建表，不切流量）；`unified_rag_manager_v2.py` 增加以 event_id 為主鍵的稽核 log（唯讀觀察現況，不改變行為）。
- **Phase 1（一致性層 v1：diff-sync）**：`documents`/`chunks` 表上線並成為爬蟲/匯入流程的寫入目標之一（與現行直接寫入 Chroma/ES/Neo4j 並行雙寫，非取代）；加入 `content_hash` 比對與惡意內容掃描器；既有 `sync_chromadb_to_elasticsearch.py` 改造為讀取 Postgres 而非直接掃 Chroma，改為排程 diff-sync。
- **Phase 2（一致性層 v2：outbox）**：`sync_events` outbox 上線，訂閱器取代 diff-sync 排程；Neo4j 五種原子操作與軟到期機制上線；此時可將現行直接寫入 Chroma/ES/Neo4j 的路徑正式收斂為「只寫 Postgres，其餘由訂閱器套用」。
- **Phase 3（評測迴路）**：`eval.golden_queries`／`eval.alerts` 上線；四段式量測管線串接既有 `eval_step` 系列邏輯，掛上 nightly cron；建立拒答/低相似度抽樣佇列。
- **Phase 4（忠實度守門員＋模糊檢索＋實驗層）**：線上粗篩／非同步精篩上線；模糊檢索 fallback 上線；實驗層以 `route_id` 分組運作，比較報表回饋 RAG Router 的路由權重。
- **Phase 5（Router 與 Fusion 收斂）**：RAG Router 從「使用者手動選模型」正式收斂為「依查詢意圖＋實驗層回饋自動路由」；系統級 RRF Fusion 節點上線，取代各策略各自為政的排序邏輯。

每個 Phase 皆可獨立驗收、獨立走 G0–G2，也是各自的最小可回滾單位（見第 8 節）。

### 5.2 資料模型／Schema 草案

以下為**示意用 DDL 草稿**（型別與欄位可能於實作階段微調，不代表最終遷移腳本）：

```sql
-- schema: catalog（單一事實來源）
CREATE TABLE catalog.documents (
    doc_id           UUID PRIMARY KEY,
    source           TEXT NOT NULL,          -- 例如 'harvard_art_museums'
    content_hash     TEXT NOT NULL,
    version          INTEGER NOT NULL DEFAULT 1,
    is_deleted       BOOLEAN NOT NULL DEFAULT FALSE,
    quarantine_status TEXT NOT NULL DEFAULT 'clean', -- clean | quarantined | reviewed
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE catalog.chunks (
    chunk_id       UUID PRIMARY KEY,
    doc_id         UUID NOT NULL REFERENCES catalog.documents(doc_id),
    content_hash   TEXT NOT NULL,
    chunk_index    INTEGER NOT NULL,
    version        INTEGER NOT NULL DEFAULT 1,
    is_deleted     BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE catalog.sync_events (        -- outbox
    event_id     BIGSERIAL PRIMARY KEY,
    entity_type  TEXT NOT NULL,           -- 'document' | 'chunk'
    entity_id    UUID NOT NULL,
    op           TEXT NOT NULL,           -- 'upsert' | 'soft_delete'
    payload      JSONB NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE catalog.sync_cursor (        -- 各訂閱者各自的消費進度
    subscriber   TEXT PRIMARY KEY,        -- 'chromadb' | 'elasticsearch' | 'neo4j' | 'redis'
    last_event_id BIGINT NOT NULL DEFAULT 0,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- schema: biz
CREATE TABLE biz.users (
    user_id      TEXT PRIMARY KEY,        -- 對應 Open WebUI 既有使用者 id，不新建認證
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE biz.conversations (
    conversation_id UUID PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES biz.users(user_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE biz.messages (
    message_id       UUID PRIMARY KEY,
    conversation_id  UUID NOT NULL REFERENCES biz.conversations(conversation_id),
    role             TEXT NOT NULL,       -- 'user' | 'assistant'
    content          TEXT NOT NULL,
    route_id         TEXT,                -- 本次回答使用的策略路由，供實驗層分組
    cited_chunk_ids  UUID[] NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- schema: eval
CREATE TABLE eval.golden_queries (
    query_id           UUID PRIMARY KEY,
    query_text         TEXT NOT NULL,
    relevant_chunk_ids UUID[] NOT NULL,
    source             TEXT NOT NULL,      -- 'manual' | 'sampled_from_production'
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE eval.measurements (
    measurement_id  UUID PRIMARY KEY,
    query_id        UUID NOT NULL REFERENCES eval.golden_queries(query_id),
    route_id        TEXT NOT NULL,
    stage           TEXT NOT NULL,   -- pre_fusion | post_rrf | post_rerank | post_generation
    metric_name     TEXT NOT NULL,   -- recall | ndcg | faithfulness | answer_relevance
    metric_value    NUMERIC NOT NULL,
    run_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE eval.alerts (
    alert_id     UUID PRIMARY KEY,
    metric_name  TEXT NOT NULL,
    route_id     TEXT,
    delta_pct    NUMERIC NOT NULL,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at  TIMESTAMPTZ
);
```

Neo4j 五種原子操作以圖節點/關係屬性 `valid_from`/`valid_to`/`status` 表達（草案，非最終 Cypher）：`ADD_ENTITY`／`UPDATE_ENTITY`（寫入新版本並更新 `valid_from`）、`ADD_RELATIONSHIP`／`EXPIRE_RELATIONSHIP`（設定 `valid_to`，不物理刪除）、`SOFT_DELETE`（`status='deleted'`，保留 30 天後由排程物理清除）。

### 5.3 對外介面草案

```
POST /api/v1/query                 現行 unified_rag_manager_v2 端點，Phase 5 前沿用；新增回應欄位：
  response.evidence_status: "sufficient" | "insufficient" | "ambiguous"
  response.route_id: string
  response.risk_flag: "none" | "faithfulness_review" | "refused"

GET  /api/v1/eval/routes/compare?since=...   Phase 3 起新增，回傳依 route_id 分組的四段式量測比較報表

POST /internal/sync/ack            Phase 2 起，各訂閱者套用完 event 後回報 sync_cursor（內部服務間介面，不對外）
```

### 5.4 錯誤處理與日誌策略

- 惡意內容掃描器判定「可疑」時，寫入 `catalog.documents.quarantine_status='quarantined'`，不進入任何檢索庫，並記錄告警供人工複審；不得靜默丟棄或靜默放行。
- 忠實度粗篩未過：直接降級為「無檢索支撐／拒答」分支並標示 `risk_flag`；不得在未標示風險的情況下輸出模型知識回答。
- 訂閱器套用 event 失敗：比照 outbox 模式標準做法，不前移 `sync_cursor`，並重試＋告警，避免資料落後被靜默吞掉。
- 所有告警（`eval.alerts`、quarantine、忠實度異常）皆需可追溯到觸發當下的 `event_id`／`query_id`／`route_id`，供 RV-3 回檢使用。

### 5.5 埠號規劃（Phase 0 待決事項，**已更新，比原判斷更複雜**）

原判斷（設計文件初版）以為只是 `.env.example` 的 `8008` 打錯成該寫 `8007`，但實作前複查 `scripts/ops/*.sh` 後發現實情更複雜，**不可直接視為單純筆誤修正**：

- `langchain-rag/unified_rag_manager_v2.py`：讀取環境變數 `RAG_MANAGER_PORT`，預設 `8007`。
- `langchain-rag/create_graphrag_models.py:516`：**另一支獨立的 FastAPI 服務**，硬編碼監聽 `8010`，對應 ops 腳本中稱呼的「Multi-DB RAG Server」（`setup-ollama-rag-proxy.sh`、`verify-multi-database-system.sh`、`verify-rag-system.sh`、`check_system_status.sh` 皆打 `:8010/health`／`:8010/query`）。
- `.env.example` 的 `RAG_API_PORT=8008`：目前找不到任何程式碼實際讀取 `RAG_API_PORT` 這個變數名，但 `scripts/ops/run_tests.sh`、`verify-multi-database-system.sh` 仍會去打 `:8008/health` 並稱為「標準 RAG 服務器」——目前無法確認這是（a）過去存在、現已移除的第三支服務殘留的健康檢查、還是（b）預期以 `RAG_API_PORT=8008` 覆寫 `unified_rag_manager_v2.py` 卻因變數名不符而從未生效。
- ChromaDB 現行佔用 `8001`（`docs/designs/2026-08-29-remove-docker-native-migration.md` 記載）。

換言之現況可能同時存在（或曾經存在）**三支**不同的 RAG 相關 FastAPI 服務（`unified_rag_manager_v2.py`／`create_graphrag_models.py`／`.env.example` 假設中的第三支），對應到圖上單一個「Backend API」節點。**這已超出本次改版可單方面猜測修正的範圍**——貿然把 `.env.example` 改成 8007 可能反而蓋掉 8008 原本要對應的另一支服務。

**建議處理方式**：不在 Phase 0 動 `.env.example`／埠號設定，先由同學實際啟動並確認目前機器上哪些連接埠真的有服務在監聽（如 `netstat`／逐一打 `/health`），把三支服務的現況（哪支還在用、哪支已廢棄）記錄清楚後，再決定 Backend API 最終要對應哪一支、佔用哪個埠號。此項改列為 Phase 0 的**調查任務**而非直接修正，避免在未查證前做出破壞性猜測。

#### 5.5.1 全系統埠號盤點結果（2026-09-20 追加調查）

應要求對全 repo 做了一次埠號盤點，發現一個比 Backend API 三方混淆**風險更高**的既有衝突，記錄如下（完整方法與逐項清單見附錄 B）：

- **【高風險，靜態分析高度確信】ml-service（CUDA/Torch）與 OpenWebUI 搶同一個埠 `8080`**：`ml-service/start.sh` 生產模式用 `gunicorn --bind 127.0.0.1:8080` 啟動（`ml-service/app.py:515`、`ml-service/simple-app.py:992` 的開發模式 `app.run(port=8080)` 亦同），而 OpenWebUI 經確認是用 `docker run -p 8080:8080`（`scripts/ops/setup-ollama-rag-proxy.sh:160`）發布到**同一台主機**的 8080。repo 內**找不到任何 Dockerfile 或 docker-compose 檔案**，代表 ml-service 只能是原生行程直接綁主機埠，不像 OpenWebUI 有 Docker 網路命名空間隔離。兩者若在同一台主機上同時啟動，必有一方绑定失敗或流量被搶走。此為現況既有問題，**與本次 RAG 架構改版無關**，但因為影響到「Backend API 最終要落在哪個埠」的判斷基礎，建議一併處理。
- 現場即時查證（2026-09-20）：Windows 主機與目前執行中的 WSL 發行版 `Ubuntu`（`wsl -l -v` 顯示另有 `Ubuntu-22.04` 目前是 Stopped 狀態，本次未啟動它）都只查到 `11434`（Ollama）在監聽，其餘服務目前都沒在跑，所以無法「即時重現」上述衝突，**此結論屬靜態程式碼分析，強烈建議實際同時啟動 OpenWebUI 與 ml-service 做一次即時驗證**，並確認真正的部署目標是 `Ubuntu` 還是 `Ubuntu-22.04` 這個發行版本（兩者目前只有一個在跑，需要確認哪個才是圖上說的「WSL2 + Ubuntu 22.04」）。
- **【已知且已有 workaround，非待辦】** Neo4j：WSL 系統本身內建的 Neo4j 服務已佔用 `7687`，本專案原生 Neo4j 因此改用 `7688`（`unified_rag_manager_v2.py:154` 註解已說明），純供紀錄，不需再處理。
- **【確認為死碼，暫不構成實際衝突，但具誤導性】** `config/production.js` 的 Node 應用 `app.port: 8080`：與 OpenWebUI/ml-service 同數字，但追查後 `src/app.js`（真正的啟動進入點）是讀 `process.env.API_PORT || 3000`，完全不 `require('config')`（`config` 套件甚至不在 `package.json` 依賴清單中）。`config/*.js` 整組檔案目前對執行沒有任何實際影響，建議之後統一清理或明確標記為 deprecated，避免有人誤以為改這裡有用。
- **【疑似死配置，待確認】** `config/nginx/nginx.conf` 與 `context/deployment/nginx.conf`／`nginx-simple.conf` 都是假設 Docker Compose 網路存在的設定（upstream 寫 `cuda-ml-service:8080`、`art-database-api:3000`、`art-history-openwebui:8080` 等 Docker service name），但 repo 內沒有對應的 docker-compose 檔案可以佐證這些網路真的被建立過。這些 nginx 設定目前很可能整組都沒在用，建議之後與教師確認是否為前期（RAG 架構轉向前）遺留、可以整組歸檔或刪除。

**修正後的建議處理順序**：Phase 0 埠號調查任務範圍擴大為兩件事——(1) 原本的 Backend API 三重身份確認（8007/8008/8010）；(2) 新發現的 ml-service vs OpenWebUI 8080 衝突排除（建議 ml-service 改用其他埠，例如 8082，因為 OpenWebUI 8080 是對外入口、優先權較高）。這兩項都屬於「現況修復」而非「新架構設計」，性質上可能落在 `CLAUDE.md` 第3節的小型修正豁免範圍內（各自預估都是個位數行數的設定變更、不新增依賴、不變更 schema），但因為涉及對外服務埠號變更，建議仍讓老師知會一聲再動手。

## 6. 安全與隱私考量

- **Tier 分級沿用現況判斷為 Tier B**（內網／校內使用、無個資、非公網服務）。本次改版新增 `biz.users/conversations/messages` 雖然儲存對話內容，但仍限於既有 Open WebUI 使用者 id 對應，不新增個資欄位、不對外公網開放，暫不觸發升級為 Tier A；若未來對外開放或蒐集姓名/學號等個資，依 `CODE_REVIEW_STANDARD.md` T-Tier-02 必須重新分級。
- 惡意內容掃描器與 prompt injection 偵測是本次新增的主要安全機制，對應 `CODE_REVIEW_STANDARD.md` 表 E（LLM/RAG 專用檢核）。
- `quarantine` 佇列與 `eval.alerts` 皆需人工可視（避免自動化黑箱判定造成內容被無故封鎖或錯誤放行）。
- Google Books 線上補充查詢屬對外呼叫外部 API，需檢視是否有速率限制／金鑰外洩風險（沿用 `crawlers/fetch_google_books.js` 既有 429 重試邏輯）。

## 7. 測試策略

- **單元測試**：RRF 融合分數計算、evidence sufficiency 門檻判斷、Neo4j 五種原子操作的狀態轉換邏輯、outbox 事件序列化/反序列化。
- **整合測試**：Phase 1/2 上線後，以既有 15 題測試問題集（`scripts/eval_step` 使用的資料）驗證雙寫/切換前後答案品質無明顯劣化；訂閱器斷線重連後 `sync_cursor` 是否正確追上。
- **驗收測試**：以 `eval.golden_queries`（初期可由現有 15 題轉換／擴充）驗證四段式量測管線輸出的 Recall／nDCG 數值與人工評估结果方向一致；忠實度粗篩對已知的幾類幻覺案例（可由現有評測資料整理）做誤判率驗證。
- 測試資料來源：現有 `scripts/eval_step*` 使用的 15 題問答集為起點，逐步透過 `biz.messages.cited_chunk_ids` 抽樣正式問題擴充 `eval.golden_queries`。

## 8. 部署與運維

- 沿用現行本地端 WSL2 + Ubuntu 22.04 部署環境，不引入新的容器編排（對照 `docs/designs/2026-08-29-remove-docker-native-migration.md` 的 Docker-to-Native 遷移方向）。
- 各 Phase 上線前需完成 `CODE_REVIEW_STANDARD.md` G0–G2；Tier B 對應表 A/B/C/D/G + LLM 專用表 E 必做。
- 監控：`eval.alerts` 是本次新增的核心監控訊號，建議串接既有 `monitoring/prometheus.yml`／告警管道（沿用現有機制，不重建新的告警系統）。
- 回滾方式見第 9 節「回滾與退場」（於評估表中詳列，此處摘要：每個 Phase 皆保留舊路徑一段觀察期，確認穩定才收斂/移除舊路徑）。

## 9. 未解決問題

- 埠號規劃最終定案（見 5.5 節）需要實際盤點目前機器上 `unified_rag_manager_v2.py`（8007）／`create_graphrag_models.py`（8010）／`.env.example` 假設中對應 8008 的第三支服務，哪些仍在運作、哪些已廢棄，才能決定 Backend API 最終落在哪個埠號，此文件不貿然給出修正。
- `eval.golden_queries` 初期資料從 15 題人工問答集轉換為逐 chunk 標註，實際標註工作量與人力（誰來標）尚未評估，需在評估表中列為時程風險。
- Faithfulness Gate 粗篩的具體門檻（相似度分數、關鍵詞規則）需要先用現有 15 題評測資料做離線校準，本文未給出具體數值。
- `langchain-rag/adaptive_strategy_monitor.py`、`optimization_manager.py`、`alert_and_optimization_system.py` 三支檔案是否可局部重用於子系統2/3，調查階段因篇幅限制未逐行核對，需在 Phase 3/4 開工前補做細讀。
- 模糊檢索 fallback 的「confidence K>0.7」門檻定義（K 是什麼分數？如何校準？）圖面未說明細節，需要與老師/圖面原作者再確認語意。

---

## 附錄 A：現況與重用調查完整報告

（原始調查報告全文，供查證用；摘要已併入第 3 節）

### 一、既有主幹管線

1. **Open WebUI 前端 (:8080)** — 可重用。已在 `docs/designs/2026-08-29-remove-docker-native-migration.md` 確認為現行 Docker 容器 `art-history-openwebui`，是實際對外入口。
2. **Backend API (FastAPI :8001)** — 需大改後重用。`langchain-rag/unified_rag_manager_v2.py`（1600+ 行）是貨真價實的 FastAPI 服務，具 `/api/v1/query`、`/api/v1/retrieve`、`/health`、`/api/v1/models`、`/api/v1/strategies`、`/api/v1/cache/*`。但埠號實際是 `RAG_MANAGER_PORT` 預設 `8007`（`unified_rag_manager_v2.py:1626`），部署文件卻寫 `RAG_API_PORT=8008`（`.env.example:23`），與圖上 `8001` 三方不一致；`docs/designs/...md` 記載目前 ChromaDB 實際佔用 `8001`，與圖上「Backend API :8001」直接衝突。
3. **Redis 語意快取 (:6379)** — 需大改後重用。`src/database/connection.js`（`redisClient`, `connectRedis()`）、`src/utils/cacheManager.js`（get/set/del，含 Redis 不可用時退回記憶體快取），`config/default.js:165-167` 有 `redis.host/port`。但這是一般 key-value TTL 快取，非「語意快取」。真正在跑的 `unified_rag_manager_v2.py` 用自己的行程內 LRU+TTL 快取（`QueryCache` class，`unified_rag_manager_v2.py:43-80`，key 為 `md5(query|strategy|max_results)`，精確字串比對），完全沒接 Redis。
4. **查詢前處理（改寫＋意圖偵測）** — 部分存在。`langchain-rag/multilingual_query_translator.py` 做中英術語翻譯，`langchain-rag/smart_keyword_extractor.py` 做關鍵詞抽取，在 `unified_rag_manager_v2.py:1411-1420` 被呼叫。但沒有意圖分類、沒有依意圖路由的邏輯。
5. **RAG Router** — 部分存在，需大改。`openwebui-pipes/*.py` 每個策略是獨立 Pipe（`openwebui_naive_rag_multi_pipe.py:29-48`），使用者選模型＝選策略；後端用固定字典 `RAG_STRATEGIES`（`unified_rag_manager_v2.py:1273-1278`）查表分派。「路由」目前＝使用者手動選模型，沒有依查詢內容自動判斷的路由節點。
6. **Embedding 模型** — 可重用。`langchain-rag/bge_m3_embedding.py` + Ollama `/api/embed`（`bge-m3:latest`）。
7. **ChromaDB** — 可重用，埠號待第 5.5 節決議。
8. **Elasticsearch (:9200)** — 部分存在。`openwebui_hybrid_es_rag_multi_pipe.py` 的 `HybridESRAG` 是唯一使用 ES 的策略，BM25＋向量 kNN。
9. **Neo4j (:7687)** — 圖檢索本身可重用，五種原子操作/軟刪除/30天保留需新建。全庫搜尋 `valid_to`/`valid_from`/`soft delete`/`EXPIRE_RELATIONSHIP` 無結果，現有腳本只用 `MERGE` upsert。
10. **Fusion 節點（RRF）** — 部分存在，範圍過窄。`openwebui_hybrid_es_rag_multi_pipe.py:459,520-531` 有真正 RRF 實作（k=60），但只融合 ES 索引內 BM25 與向量 kNN 兩路，非跨三種資料層的系統級融合。其餘策略的「rerank」多是單純排序（`unified_rag_manager_v2.py:1167-1170,930-931,971-983`）。
11. **Reranker（cross-encoder）** — 存在但是孤兒模組。`enhanced_neo4j_retriever.py:18,83,448-476` 有完整 CrossEncoder 重排（`bge-reranker-base`），`integrated_rag_optimizer.py` 的 `_rerank()` 實際只是排序（`integrated_rag_optimizer.py:472-483` 註解明寫「模擬重排序算法」）。兩者都沒有被 `unified_rag_manager_v2.py` import，只在各自測試中被單獨測過。
12. **Evidence sufficiency 判斷** — 不存在對應功能。`AgenticGraphRAG._assess_sufficiency`（`unified_rag_manager_v2.py:1017-1026`）是「判斷要不要再查一輪」的 agentic 停止條件，非「生成前用相似度分數決定拒答」的最終把關。
13. **拒答/風險標示分支** — 不存在。`/health` 的 `"degraded"` 僅代表服務健康狀態。
14. **Ollama (:11434) + Google Books** — Ollama 埠號吻合，`unified_rag_manager_v2.py:357` 呼叫 `/api/generate`；prompt 組裝（`_build_prompt`, `unified_rag_manager_v2.py:386`）是單一字串，未做指令與參考資料結構化分離。Google Books 現況只有 `crawlers/fetch_google_books.js`，是離線爬蟲，非線上即時補查。
15. **Faithfulness/safety gatekeeper** — 不存在線上版本。`scripts/eval_step2_compute_metrics.py:233-256` 的 `compute_faithfulness()` 用 LLM 裁判逐句判斷支持度，方法論精神一致，但是離線批次評測腳本，非線上即時攔截，也沒有粗篩+NLI細篩兩段式設計。

### 二、子系統1：PostgreSQL 資料一致性層

現有 Postgres schema（`context/database/01-init-schema.sql` = `database_schema.sql`，加上 `02-fix-schema.sql`、`03-performance-indexes*.sql`）全部在 `public` schema，只有 `artists/artworks/institutions/collections/art_movements/tags/document_vectors/search_queries/crawl_tasks/processing_logs` 12 張表。完全沒有 `catalog`/`biz` schema、沒有 `documents`/`chunks`（最接近的是 `document_vectors`，`context/database/01-init-schema.sql:143-157`，只有 `content_id/content_type/embedding(TEXT)/chunk_index`，無 `content_hash`、無版本欄位）、沒有 `sync_events`、沒有 `sync_cursor`、沒有 `users/conversations/messages`。

內容雜湊變更偵測不存在；惡意內容/注入掃描器（quarantine）不存在（全庫搜尋 `quarantine/malicious/moderation/sanitiz` 無結果）。

三個檢索庫作為 outbox 訂閱者不存在，且方向相反：唯一的跨庫同步 `scripts/sync_chromadb_to_elasticsearch.py` 是全量 offset 分頁掃描整個 ChromaDB collection（`sync_chromadb_to_elasticsearch.py:65-104`），沒有變更偵測，每次全量重掃，方向是 Chroma→ES 單向，人工手動執行。

`users/conversations/messages`（含 `cited_chunk_ids`）不存在；Open WebUI 有自己的使用者/對話儲存（容器內，非本專案 schema 管轄）。

### 三、子系統2：Recall 量測與回饋迴圈

`eval.golden_queries` 不存在。全庫搜尋 `golden`、`relevant_chunk`、`route_id`、`nDCG` 均無命中。目前最接近的「標準答案」是 15 題人工寫的 docx 全文（`scripts/eval_step2_compute_metrics.py:27` 指向使用者桌面的研究計畫資料夾），不在 repo 內、不是資料庫表、不是逐 chunk 標註。

四階段量測不存在，只有相當於「post_generation」單一階段的替代品：`scripts/eval_step0~6` 系列是手動批次評測腳本（`eval_step1` 重新檢索快取原文、`eval_step2` 算 Correctness/Faithfulness/Retrieval Precision/Response Time、`eval_step3` 彙整 6×4 矩陣 xlsx、`eval_step4` 翻譯答案、`eval_step5` 算跨語言對齊指標、`eval_step6` 彙整完整報表、`eval_step0` 補跑失敗組合），針對 15 題固定題目與 24 種組合的一次性研究評測，沒有 Recall/nDCG，也沒有中間管線階段量測。

Nightly cron 觸發不存在專用機制，但 `src/utils/cronScheduler.js`（`node-cron` 封裝）可重用。`eval.alerts`、拒答/低相似度事件抽樣人工標註回饋、Faithfulness Gate 即時攔截日誌皆不存在。

### 四、子系統3：忠實度/安全防護 + 模糊檢索 fallback + 實驗層

Faithfulness/safety gatekeeper 線上版本不存在（同上）；Prompt injection/instruction leakage 偵測不存在（全庫搜尋 `injection` 無命中）。

模糊檢索 fallback 不存在。`AgenticGraphRAG` 的多輪迭代檢索（`unified_rag_manager_v2.py:986-1038`）概念上最接近，但觸發條件與 confidence 定義不同，且僅存在於 Graph 策略。

實驗層部分存在雛形：`scripts/run_24combo_evaluation.py` 已證明 force-switch 策略可行（`model_combination_id = f"{llm_tag}@{strategy_code}"`，`run_24combo_evaluation.py:73-89`），`eval_step3_build_xlsx.py` 的 6×4 矩陣是策略比較報告雛形。但缺少正式 `route_id`、`eval.golden_queries` 驅動、四階段量測分組、回饋 RAG Router 的閉環機制。`langchain-rag/adaptive_strategy_monitor.py`、`optimization_manager.py`、`alert_and_optimization_system.py` 名稱相關但屬監控指標蒐集＋簡單規則告警層級，未串接策略路由決策，建議後續再細讀評估。

### 可重用清單

- Open WebUI、Ollama、ChromaDB、Neo4j、Elasticsearch 基礎服務本身
- `unified_rag_manager_v2.py`：FastAPI 服務骨架、路由分派字典模式、健康檢查端點、行程內快取邏輯
- `openwebui-pipes/*.py`：四種策略的 Pipe 介面模式
- `openwebui_hybrid_es_rag_multi_pipe.py` 的 RRF 實作
- `enhanced_neo4j_retriever.py` 的 CrossEncoder reranker
- `bge_m3_embedding.py`、`multilingual_query_translator.py`、`smart_keyword_extractor.py`
- `eval_step2_compute_metrics.py` 的 Faithfulness/Correctness/Retrieval Precision 計算方法論
- `run_24combo_evaluation.py` + `eval_step3_build_xlsx.py`
- `src/database/connection.js` / `cacheManager.js`
- `src/utils/cronScheduler.js`
- `crawlers/fetch_google_books.js`

### 缺口清單

- Postgres `catalog`/`biz` schema 全套
- outbox 事件驅動同步機制
- 真正的語意快取
- 具意圖偵測的查詢前處理節點
- 依查詢類型自動判斷策略的 RAG Router
- 系統級三路 RRF Fusion 節點
- 生產路徑上的 evidence sufficiency 判斷與拒答/風險標示分支
- Prompt 指令與參考資料結構化分離
- 線上 Faithfulness/safety gatekeeper
- 模糊檢索 fallback
- `eval.golden_queries`/`eval.alerts`/四段式量測管線
- Neo4j 五種原子操作與生命週期管理
- 惡意內容/注入掃描器與 quarantine 流程
- `route_id` 實驗層與回饋 RAG Router 的閉環
- 統一的服務埠號規劃

## 附錄 B：全系統埠號盤點（2026-09-20）

方法：對 `*.js/*.py/*.sh/*.ps1/*.yaml/*.yml/*.json/*.conf/*.env*` 全文搜尋已知/常見埠號數字，逐一追到「真正被程式碼讀取／腳本綁定」的位置（而非只看文件敘述），並於本機以 `netstat -ano`（Windows）與 `wsl -d Ubuntu -- ss -tlnp`（WSL）做一次即時監聽狀態查證。

| 埠 | 服務 | 狀態 | 依據 |
|---|---|---|---|
| 3000 | Node 後端 `src/app.js`（`API_PORT` 環境變數，預設值） | 現行程式碼真實讀取的預設值 | `src/app.js:34`、`healthcheck.js:5` |
| 3000（另一組，死碼） | `config/default.js` 的 `app.port` | 死碼，`src/app.js` 不使用 `config` 套件 | `config/default.js:11`；`package.json` 無 `config` 依賴 |
| 3001 | nginx（`config/nginx/nginx.conf`）代理 Grafana 管理介面 | 疑似死配置（見下） | `config/nginx/nginx.conf:180` |
| 5432 | PostgreSQL | 現行程式碼真實讀取的預設值 | `src/database/connection.js:31`（`DB_PORT`，預設5432） |
| 6379 | Redis | 現行程式碼真實讀取的預設值 | `src/database/connection.js:56`（`REDIS_URL`，預設 `redis://localhost:6379`） |
| 7474 / 7687 | Neo4j（HTTP／Bolt），標準埠 | 系統層級已佔用（WSL 內建 Neo4j） | `docs/designs/2026-08-29-...md` |
| 7688 | 本專案原生 Neo4j 實際使用埠（避開 7687 衝突的 workaround） | 現行程式碼真實讀取的預設值，已知衝突已解決 | `unified_rag_manager_v2.py:154`（`NEO4J_URI` 預設 `bolt://127.0.0.1:7688`，註解說明原因） |
| 8000 | ChromaDB 向量搜尋（圖上標註） | 待與下方 8001 對照確認何者為真 | 架構圖 |
| 8001 | ChromaDB 實際佔用（依既有部署文件） | 依文件記載，本次未即時查證 | `docs/designs/2026-08-29-remove-docker-native-migration.md`；`unified_rag_manager_v2.py:164`（`CHROMADB_PORT` 預設8001） |
| 8007 | `unified_rag_manager_v2.py`（統一 RAG 管理器） | 現行程式碼真實讀取的預設值 | `unified_rag_manager_v2.py:1626`（`RAG_MANAGER_PORT`） |
| 8008 | `.env.example` 的 `RAG_API_PORT` | **無任何程式碼讀取此變數名**，疑似孤兒設定 | `.env.example:23`；`requirements.txt:43` 註解提及但無對應程式碼 |
| 8010 | `create_graphrag_models.py`（Multi-DB RAG Server，ops 腳本稱呼） | 現行程式碼硬編碼綁定 | `create_graphrag_models.py:516`；`scripts/ops/setup-ollama-rag-proxy.sh`、`verify-multi-database-system.sh`、`verify-rag-system.sh`、`check_system_status.sh` |
| 8010（不同用途，容易混淆） | `src/mcp/mcp_tool_registry.py` 內一筆 CLIP 視覺模型工具的宣告埠 | 與上一列的 Multi-DB RAG Server **同號但不同服務**，屬 MCP 工具註冊表的靜態宣告，未查證是否真的有服務綁在這個埠 | `src/mcp/mcp_tool_registry.py:182` |
| 8011 | `src/agents/rl/rl_server.py`（RL-Agentic RAG Server） | 現行程式碼真實讀取的預設值 | `src/agents/rl/rl_server.py:304`（`RL_SERVER_PORT`） |
| **8080** | **OpenWebUI（對外入口，Docker 發布）** | 現行部署真實使用，唯一有找到 `docker run -p` 證據的服務 | `scripts/ops/setup-ollama-rag-proxy.sh:160`（`-p 8080:8080`） |
| **8080（衝突）** | **ml-service（CUDA/Torch，gunicorn 生產模式／Flask 開發模式）** | **與上一列同埠**，且無 Docker 隔離（repo 內無 Dockerfile/docker-compose） | `ml-service/start.sh`（`gunicorn --bind 127.0.0.1:8080`）；`ml-service/app.py:515`；`ml-service/simple-app.py:992` |
| 8080（死碼） | `config/production.js` 的 Node 應用 `app.port` | 死碼，同上（`src/app.js` 不讀此設定） | `config/production.js:9` |
| 8080（疑似死配置） | nginx upstream `cuda_ml_service`／`art-history-openwebui` 等 Docker service name 寫法 | 找不到對應 docker-compose 佐證這些網路存在 | `config/nginx/nginx.conf:63`；`context/deployment/nginx.conf:43` |
| 8888 | nginx（`config/nginx/nginx.conf`）代理 Jupyter | 疑似死配置（同上） | `config/nginx/nginx.conf:219` |
| 9090 | Prometheus | 待查證是否現行有跑 | `config/nginx/nginx.conf:198`；`monitoring/prometheus.yml` |
| 9200 | Elasticsearch | 現行程式碼真實讀取的預設值 | `unified_rag_manager_v2.py:181`（`ES_URL` 預設 `https://localhost:9200`） |
| 11434 | Ollama | **現場即時查證為真：目前唯一在監聽的服務**（Windows 與 WSL `Ubuntu` 皆有） | 本次 `netstat`/`ss` 查證 |
| 11435 | Ollama RAG Proxy | 依文件記載，本次未即時查證 | `docs/designs/2026-08-29-remove-docker-native-migration.md` |

**結論排序（風險由高到低）：**

1. **ml-service vs OpenWebUI 搶 8080** — 靜態分析高度確信，建議實際同時啟動兩者驗證後盡快修正（建議 ml-service 改埠，因 OpenWebUI 是對外入口）。
2. **Backend API 三重身份混淆（8007/8008/8010）** — 需要盤點清楚哪支服務還在用，才能決定圖上「Backend API」最終落點。
3. **一批疑似死碼／死配置**（`config/*.js`、`config/nginx/nginx.conf`、`context/deployment/nginx*.conf`）— 不構成現行衝突，但持續存在會誤導之後的維護者，建議找時間確認並清理或封存。
4. Neo4j 7687 衝突 — 已有 workaround，僅供紀錄，不需再處理。

**本次調查的限制**：現場查證僅涵蓋「Windows 主機」與「目前開機中的 WSL 發行版 `Ubuntu`」，兩者當下只有 Ollama（11434）在監聽，其餘服務都沒啟動，因此上述衝突多數是**靜態程式碼分析**的結論，不是「即時重現」的結論。另外 `wsl -l -v` 顯示還有一個 `Ubuntu-22.04` 發行版目前是 Stopped 狀態——這個名稱與架構圖標註的「WSL2 + Ubuntu 22.04」更吻合，本次未啟動它做查證，建議由同學確認實際部署與服務啟動是在哪一個 WSL 發行版上，再重跑一次即時監聽查證。
