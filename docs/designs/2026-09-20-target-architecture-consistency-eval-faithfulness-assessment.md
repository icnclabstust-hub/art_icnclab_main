# 開發前評估表（PRE_DEV_ASSESSMENT）

## 一、基本資料

- 任務名稱：RAG 系統目標架構改版（PostgreSQL 一致性層／召回率量測回饋迴路／忠實度安全防護＋模糊檢索＋實驗層）
- 提案學生：（請填寫）
- 日期：2026-09-20
- 對應設計文件：`docs/designs/2026-09-20-target-architecture-consistency-eval-faithfulness.md`

## 二、問題定義（三問）

1. **要解決什麼問題？** ChromaDB／Elasticsearch／Neo4j 三檢索庫無單一事實來源導致資料飄移；沒有可量化的召回率／nDCG 評測機制；生成路徑無忠實度／安全把關與檢索不足分支。
2. **誰會用？多常用？** 實驗室內部與美術系合作對象，內網/校內使用之研究型 RAG 服務；日常研究/實驗頻率使用，非公開對外服務。
3. **不做會怎樣？** 三庫資料飄移持續累積且無法偵測；路由策略優劣無法量化比較，影響論文/專題產出的實驗可信度；幻覺與拒答不足問題無法被觀測與追蹤。

## 三、現況調查結論

- **既有可重用的實作／腳本**：`unified_rag_manager_v2.py`（FastAPI 骨架）、`openwebui_hybrid_es_rag_multi_pipe.py`（RRF 實作）、`enhanced_neo4j_retriever.py`（CrossEncoder reranker）、`eval_step2_compute_metrics.py`（RAGAS 式指標計算）、`run_24combo_evaluation.py` + `eval_step3_build_xlsx.py`（force-switch 與比較報表雛形）、`src/database/connection.js`/`cacheManager.js`（Redis 連線）、`src/utils/cronScheduler.js`（排程）、`crawlers/fetch_google_books.js`。完整清單見設計文件第 3 節與附錄 A。
- **可直接採用的現成套件／服務**：Open WebUI、Ollama、ChromaDB、Elasticsearch、Neo4j、PostgreSQL 本身皆為現成服務，無需另尋替代品；忠實度 NLI 精篩可評估採用現成套件（如 sentence-transformers cross-encoder 或開源 NLI 模型）而非自行訓練。
- **仍需自行開發的缺口**：Postgres `catalog`/`biz`/`eval` schema、outbox 同步機制、語意快取、意圖路由、系統級 RRF Fusion、evidence sufficiency 判斷、線上 Faithfulness Gate、模糊檢索、Neo4j 五種原子操作、惡意內容掃描器、`route_id` 實驗層閉環、統一埠號規劃。完整清單見設計文件附錄 A「缺口清單」。
- ☐ 調查後結論為「不需開發」（不適用，本案確有明確開發缺口）

## 四、風險分級（沿用 CODE_REVIEW_STANDARD.md 第 2 節）

- Tier：☐ A　☒ B　☐ C
- **分級理由**：碰到的資料為研究用藝術史文獻、對話紀錄與使用者查詢（無姓名／學號／成績等個資）；對外介面僅限內網/校內存取，非公網服務；`CODE_REVIEW_STANDARD.md` 第2節已將「art_icnclab RAG 服務」直接列為 Tier B 對照案例。本次改版新增 `biz.users/conversations/messages` 儲存對話內容，但使用者識別仍沿用 Open WebUI 既有 id、不新增個資欄位，且系統定位（內網、研究用）未改變，依 T-Tier-02 不需升級為 Tier A。**若未來此服務轉為公網開放或蒐集個資，須立即重新分級。**

## 五、成本與時程

- **預估工時**：分階段估算（Phase 0–5，見設計文件第 5.1 節），實際人日需於各 Phase 開工前依當時人力另行估算；此處僅列各 Phase 相對工作量供排優先序參考——Phase 0（地基／小）、Phase 1（diff-sync 一致性層 v1／中）、Phase 2（outbox 一致性層 v2／大）、Phase 3（評測迴路／中大）、Phase 4（忠實度守門員＋模糊檢索＋實驗層／大）、Phase 5（Router/Fusion 收斂／中）。
- **新增依賴（套件／服務／port／排程）**：
  - 新增 Postgres schema：`catalog`、`biz`、`eval`（同一 Postgres 實例內，非新服務）
  - 可能新增套件：NLI 模型（忠實度精篩）、prompt-injection 偵測規則/套件（待第 6 節安全評估後選定）
  - 新增排程：nightly 評測 job（掛載於既有 `cronScheduler.js`）、週期性一致性稽核 job
  - 埠號：無新增對外埠，但需解決現行 Backend API 埠號規劃衝突（設計文件第 5.5 節）
- **需要的機器資源（GPU／磁碟／記憶體）**：CrossEncoder／NLI 模型推論建議沿用現行 GPU 資源（若有）；outbox 事件表與 `eval.measurements` 長期累積需評估額外磁碟需求，量體未評估，建議 Phase 1 上線後實測。

## 六、成功指標與驗證方式

- **怎樣算做完（可量測標準，至少一項）**：
  1. Phase 2 完成後，三檢索庫與 Postgres `catalog` 的資料一致性稽核（週期性 diff）不一致率趨近於零。
  2. Phase 3 完成後，`eval.golden_queries` 累積達一定題數（初期以現有 15 題轉換為起點，逐步擴充），且四段式量測可自動化產出 Recall/nDCG 報表。
  3. Phase 4 完成後，忠實度粗篩對已知幻覺案例的攔截率可量測並記錄於 `eval.alerts`。
- **怎麼驗證**：見設計文件第 7 節「測試策略」。

## 七、回滾與退場

- **上線後發現不對，如何回滾**：各 Phase 遷移期間新舊路徑並行（見設計文件第 5.1 節），確認新路徑穩定前不移除舊路徑；若 Phase N 出問題，流量/寫入切回 Phase N-1 的既有路徑即可回滾，不需回退資料庫 schema（新 schema 保留，僅停止使用）。
- **若專案中止，留下的東西如何清理**：已建立的 `catalog`/`biz`/`eval` schema 可保留作為既有系統的觀測用途（不影響現行服務運作）；若確定不再使用，比照一般資料庫 schema 下線流程處理，並於 `docs/designs/` 對應設計文件加註中止紀錄。

## 八、豁免記載（如適用）

- 是否有流程豁免：☒ 無
- 補充說明：本案設計方向（架構藍圖）已與指導老師討論並達成共識，但此共識屬於「目標架構藍圖」層級，尚未等同於本設計文件與本評估表的正式核可；依 `CLAUDE.md` R5，AI 不得代為認定「老師已同意」本文件內容，仍需下方簽核欄位由老師實際覆核後才能視為通過 GD。

## 九、簽核

| 角色 | 姓名 | 日期 | 結果 |
|---|---|---|---|
| 提案學生 | | | ☐ 確認 |
| 指導老師（Tier A/B 必填） | | | ☐ 核可　☐ 退回 |

> 退回意見：
