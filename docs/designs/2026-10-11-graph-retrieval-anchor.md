# 設計文件：圖譜檢索修復（方案 A：先對實體、再套模板）

- 日期：2026-10-11
- 提案：@Icnclab（使用者規劃書「藝術史 RAG 圖譜檢索修復系統規劃書」，2026-10-11；使用者選定方案 A）
- GD 狀態：步驟 1（需求）、步驟 3（設計）＝使用者規劃書；步驟 2（現況調查）＝本文件 §二；步驟 4＝`2026-10-11-graph-retrieval-anchor-assessment.md`（Tier B，待指導老師核可）
- 評估表未核可前不實作（CLAUDE.md §1 步驟 4、R2）

---

## 一、規劃書摘要（原文要點）

- 問題：graph 路由關係題正確率 0.03–0.20，五模型皆同，屬檢索層問題——關鍵詞對所有節點類型模糊比對，錯配到其他畫家（B11 洛蘭→Monet）、主題標籤（B12 卡拉契→Salvation Army、B10 普桑→Classical scene）、人物節點而非作品（B8）；限制條件題（B7 大都會的維梅爾）四路由全失敗。
- 範圍：只修 graph 路由；單機 RTX 5060 8 GB、無付費資源。不做 Text2Cypher、理論語料擴充、微調、付費 API。
- 方案 A 五模組（皆不呼叫 LLM）：
  - **M1 別名表**：PostgreSQL catalog（唯一真實來源）→ 同步 Neo4j `Artist.aliases`；Wikidata zh-tw／zh-hant／zh／en 標籤＋OpenCC s2twp＋姓氏拆段（唯一性檢查）＋手動別名（委拉斯奎茲→Q297、卡拉契→Annibale／Ludovico、阿特米西亞·真蒂萊斯基→Q212657）。
  - **M2 錨點器**：只涵蓋 `:Artist` 的全文索引；先比英文原名、再比中文別名，只接受完整字串命中；輸出 hit／abstain。
  - **M3 模板**：T1 畫家→作品（預設）、T2 ＋館藏、T3 ＋類型（AAT）、T4 ＋主題（AAT）；關鍵詞規則選模板。
  - **M4 退回**：錨點查無或模板 0 列時，關係題→fulltext、事實題→vector；理論題不經 graph。
  - **M5 檢索日誌**：每題 JSONL（錨點、模板與參數、列數、退回、實際上下文）。
- 成功指標：錨點正確率 ≥95% 且錯配 0；關係題 ≥0.90（現況 0.133）；限制條件集合 F1 高於 fulltext；事實題 ≥0.95（現況 0.758）；關係題矛盾 ≤0.03。
- 評估：檢索層規則指標→120 次實跑對照模擬（關卡一）→自動出題 30–100 題、McNemar／Wilcoxon＋Holm（關卡二，老師審閱）。時程約 7 週。
- 規劃書全文由使用者保存（Claude Docs）；模擬數據 `sim.py`、`sim_results.csv`。

---

## 二、現況調查（步驟 2，2026-10-11，唯讀查詢 Neo4j 7687 與 catalog）

### 2.1 實際 schema

| 項目 | 實際 |
|---|---|
| 節點 | Artwork 4,892、**Artist 3,199**、Translation 268、Institution 233、Source 58、Place 47、Period 45、Material 32、Technique 17、Style 9、**Concept 8**、**Theme 3** |
| 關係 | `(Artist)-[:CREATED]->(Artwork)` 5,731；`(Artwork)-[:HELD_BY]->(Institution)` 3,666；USES_MATERIAL 3,241；FROM_PLACE 2,168；USES_TECHNIQUE 653；MENTIONS_CONCEPT 539；DEPICTS_THEME 272；BELONGS_TO_STYLE 271；HAS_TRANSLATION 268；CREATED_IN_PERIOD 102 |
| Artist 屬性 | 只有 `name`、`source`、`sources`（14 個有 `has_translation_seed`）——**沒有 ID、沒有 Wikidata／ULAN** |
| Artwork 屬性 | id、title、date、description、url、source；department／period／culture／medium（約 60%）；country／provider |
| 既有索引 | `artist_name_fulltext`（FULLTEXT，僅 Artist.name）、`artwork_title_fulltext`、`artwork_description_fulltext`；各類型 name 唯一索引 |

規劃書 Cypher 草案的對應：`HELD_BY` 終點是 `:Institution`（非 `:Museum`），名稱屬性為 `name`（非 `name_en`）；`HAS_TAG`／`aat_id` 不存在。

### 2.2 與規劃書前提不符之處（須修正設計）

| # | 規劃書前提 | 實際 | 影響與修正 |
|---|---|---|---|
| 1 | 大都會 API 提供 `artistWikidata_URL`、`artistULAN_URL`，可直接當畫家 ID | **catalog 全部 10 個來源 0 筆**有這兩欄；met 文件只存 artist、culture、date、department、description、id、medium、period、title、url | M1 的 QID 來源改為：(a) 修改大都會爬蟲保存這兩欄（爬蟲變更，另需評估）；或 (b) 以英文畫家名查 Wikidata 對應 QID（離線一次性，需人工確認歧義）。建議 (b) 先做黃金題 11 位＋高頻畫家 |
| 2 | 每位畫家一個 `:Artist` 節點 | **同一畫家多個節點、名稱髒**：Rembrandt 6 個（Rembrandt／Rembrandt (Rembrandt van Rijn)／Rembrandt van Rijn／"Rembrandt van Rijn (Dutch"／"Rembrandt, Harmensz van Rijn"…）、Velázquez 4 個、Caravaggio 2、Vermeer 2、Poussin 2、Claude Lorrain 2；名稱含換行與註記（"Paul Gauguin\nFrench"、"(Künstler_in)"、"born England"、"Maker:"） | **新增 M0 畫家實體合併**：別名表把多個節點對到同一 canonical ID（不刪節點，查詢時以 ID 集合展開）。錨點正確率要以「ID 集合」計 |
| 3 | 大都會作品 `tags` 有 AAT 類型／主題 ID，可做 T3／T4 | catalog **0 筆**有 tags；圖中 Concept 只有 8 個（perspective、chiaroscuro…）、Theme 只有 3 個（portrait、landscape、still life） | T3／T4 目前幾乎沒有資料可篩。第一版只做 **T1、T2**；T3 先用 Theme 3 類＋標題關鍵詞（規劃書風險表的退化方案）；T4 待爬蟲補 tags 後再做 |
| 4 | 大都會維梅爾入庫只有 3 件（B7 上限 0.6） | 圖中大都會維梅爾 **6 件**（A Young Woman Reading、A Maid Asleep、Study of a Young Woman、Young Woman with a Water Pitcher、Allegory of the Catholic Faith、Young Woman with a Lute） | B7 上限較預期高；T2 可直接驗證 |

### 2.3 錨點陷阱（支持「只接受完整字串命中」）

用 `CONTAINS` 比對時會誤中：Rembrandt **Peale**（另一位畫家）、**Cecco del** Caravaggio、**Polidoro da** Caravaggio、**Pietro** Bernini、**Orazio** Gentileschi（Artemisia 的父親；圖中沒有 Artemisia 節點，B13 應 abstain）。

### 2.4 Wikidata 中文譯名實查（2026-10-11，`logs/eval/wikidata-2026-10-11/artist_names.json`）

黃金題 11 位畫家：8 位以題目用語完全命中，3 位查無（委拉斯奎茲：Wikidata 為「迪亞哥·維拉斯奎茲」／「委拉斯開茲」；卡拉契：「安尼巴萊·卡拉齊」；阿特米西亞·真蒂萊斯基：僅簡體）。詞典 26 位：完全命中 18、只在全名內 3、查無 5。與規劃書 M1 手動別名清單一致。

---

## 三、修正後範圍（建議第一版）

| 模組 | 第一版 | 延後 |
|---|---|---|
| M0 畫家實體合併（新增） | 黃金題 11 位＋入庫作品數前 N 位畫家，canonical ID＝Wikidata QID（英文名查詢＋人工確認） | 全部 3,199 節點 |
| M1 別名表 | Wikidata 中英標籤＋s2twp＋姓氏（唯一性檢查）＋手動別名；存 catalog、同步 Neo4j | ULAN |
| M2 錨點器 | 完整字串命中；以 ID 集合展開多個節點 | — |
| M3 模板 | T1、T2（Institution.name） | T3（Theme 3 類＋標題關鍵詞）、T4（待 AAT tags） |
| M4 退回 | 依規劃書 | — |
| M5 日誌 | 依規劃書 | — |

需另行評估的前置變更：大都會爬蟲保存 `artistWikidata_URL`、`artistULAN_URL`、`tags`（影響夜間流程，Tier B）。

---

## 四、spike 結果（2026-10-11，關卡一預演）

- 實作：分支 `spike/graph-anchor`（worktree `F:/art_icnclab-main/spike-graph-anchor`）；`langchain-rag/graph_anchor.py`、`artist_aliases.json`（27 位，含卡拉契家族）、`scripts/build_artist_aliases.py`、`tests/python/test_graph_anchor.py`（9 項通過）；`unified_rag_manager_v2.py` 以 `GRAPH_RETRIEVAL=anchor` 啟用，三路融合呼叫 graph 時不退回。
- 實跑：8011（翻譯逾時 3 秒，與線上同），B1–B15 × 5 模型 × 2 次＝150 次生成，0 錯誤（10-11 13:15～14:22）。忠實度由 gemma4:12b 判定（未經 κ 驗證），向 8011 重取來源。
- 資料：`logs/eval/graph-spike-2026-10-11/`；錨點日誌 `spike-graph-anchor/logs/graph_anchor/`。

### 檢索層
- 錨點：15／15 正確、錯配 0（12 題命中；B12 卡拉契家族兩位；B13 真蒂萊斯基、B14 博羅米尼圖中無節點 → abstain → 退回 vector／fulltext）。
- 事實題 B1–B6 目標作品皆排第 1；關係題 B7–B12 取回作品皆屬該畫家（B7 為大都會 5 件維梅爾）。

### 對照（巴洛克 15 題，五模型平均；現況值取自 8080 評估）

| 路由 | 事實題 | 關係題 | 忠實度（15 題） | 關係題忠實度 | 關係題矛盾 | 關係題每答有依據句 | 每題秒數 |
|---|---|---|---|---|---|---|---|
| **graph（錨點，spike）** | **1.000** | **1.000** | **0.906** | **0.911** | **0.005** | **12.4** | 14.0 |
| graph（現況） | 0.758 | 0.133 | 0.769 | 0.711 | 0.052 | 2.3 | 10.4 |
| fulltext（現況） | 0.883 | 0.780 | 0.817 | 0.827 | 0.022 | 7.4 | 9.3 |
| hybrid（現況） | 0.983 | 0.733 | 0.754 | 0.730 | 0.038 | 5.4 | 11.9 |
| vector（現況） | 0.983 | 0.720 | 0.788 | 0.780 | 0.035 | 7.5 | 12.9 |

| 模型（spike） | 事實 | 關係 | 忠實度 | 關係題矛盾 | 翻譯退回詞典 |
|---|---|---|---|---|---|
| llama3.1:8b | 1.00 | 1.00 | 0.800 | 0.000 | 0／30 |
| qwen3:8b | 1.00 | 1.00 | 0.880 | 0.003 | 2／30 |
| deepseek-r1:8b | 1.00 | 1.00 | 0.904 | 0.011 | 30／30 |
| gemma4:12b | 1.00 | 1.00 | 0.942 | 0.012 | 14／30 |
| qwen3:14b | 1.00 | 1.00 | 0.990 | 0.000 | 16／30 |

翻譯逾時退回詞典的題目錨點照樣命中（詞典譯文含英文畫家名，且中文別名比對原問題）。

### 成功指標對照（規劃書）

| 指標 | 目標 | spike | 判定 |
|---|---|---|---|
| 錨點正確率 | ≥95%、錯配 0 | 15／15、錯配 0 | ✅ |
| 關係題正確率 | ≥0.90 | 1.000 | ✅（指標只查畫家，對 A 有利） |
| 事實題正確率 | ≥0.95 | 1.000 | ✅ |
| 關係題矛盾比例 | ≤0.03 | 0.005 | ✅（裁判待 κ 驗證） |
| 限制條件集合 F1 | 高於 fulltext | 未量（需自動出題與標準答案集合） | ⏳ |

### 限制與待辦
- 題數少（關係題 6 題）；現行關係題指標只檢查「是否該畫家的作品」，不檢查題材——B10（古典神話）忠實度 0.69、B12（宗教）0.77，主題篩選（T4）尚無資料。
- spike 直接呼叫 8011 API（溫度 0.1、長度 2048），現況值經 8080 pipe；檢索與翻譯設定相同，生成參數可能略有差異。
- 下一步依規劃書：自動出題（畫家 × 館藏／類型）量限制條件 F1、擴題至 30–100 題做統計檢定；hybrid 路由同步受益（graph 不再貢獻錯配文件），需另跑驗證。
- spike 時限至 2026-10-13；核可前不合併。

## 五、自動出題與限制條件評估（2026-10-11，規則比對，不用 LLM 裁判）

- 出題：`scripts/gen_constraint_questions.py`。別名表擴充為 40 位畫家（三館作品數最多的畫家自動查 Wikidata；只收 P31＝Q5 人物；姓氏撞名時全名／手動譯名優先；Wikidata 拆出的姓氏至少 3 字；只用台灣繁體寫法）。37 題＝正例 33 題（266 件標準答案，全部為大都會）＋應拒答 4 題（哈佛、荷蘭國家博物館）；畫家寫法輪替台灣譯名／全名／姓氏／英文。黃金題錨點重測 15／15、錯配 0。
- 評估：`scripts/eval_constraint_retrieval.py`，只呼叫 `/api/v1/retrieve`（翻譯模型 llama3.1:8b），前 5 筆；召回率＝|R∩G|／min(|G|,5)。資料 `logs/eval/constraint-2026-10-11/`。

| 路由 | 精確率 | 召回率 | F1 | 畫家條件 | 館藏條件 |
|---|---|---|---|---|---|
| **graph（錨點）** | 0.970 | 0.970 | **0.970** | 0.970 | 1.000 |
| hybrid（錨點） | 0.624 | 0.790 | 0.665 | 0.661 | 0.673 |
| fulltext（現況） | 0.376 | 0.465 | 0.399 | 0.467 | 0.515 |
| hybrid（現況） | 0.333 | 0.413 | 0.354 | 0.382 | 0.352 |
| vector（現況） | 0.286 | 0.347 | 0.299 | 0.359 | 0.329 |
| graph（現況） | 0.018 | 0.030 | 0.023 | 0.036 | 0.061 |

Wilcoxon 符號等級（F1，33 題配對）＋Holm（事前指定 4 組）：

| 比較 | F1 平均差 | 非零差題數 | Holm p |
|---|---|---|---|
| graph 錨點 vs graph 現況 | +0.947 | 32 | 9.7×10⁻⁸ |
| graph 錨點 vs fulltext | +0.571 | 30 | 4.4×10⁻⁶ |
| graph 錨點 vs hybrid 現況 | +0.616 | 29 | 4.4×10⁻⁶ |
| hybrid 錨點 vs hybrid 現況 | +0.311 | 25 | 1.2×10⁻⁵ |

→ 規劃書指標「限制條件集合 F1 高於 fulltext」達成（5 項指標全數達成）。

### hybrid（錨點）實跑：B1–B15 × 5 模型 × 2 次（8011，0 錯誤）

| 模型 | 事實題 | 關係題 |
|---|---|---|
| llama3.1:8b | 1.00 | 0.93 |
| qwen3:8b | 1.00 | 0.93 |
| deepseek-r1:8b | 1.00 | 0.90 |
| gemma4:12b | 1.00 | 0.93 |
| qwen3:14b | 1.00 | 0.93 |
| 平均（現況 hybrid：0.983／0.733） | **1.00** | **0.92** |

### 觀察與待辦
1. hybrid 錨點的限制條件 F1（0.665）低於單獨 graph（0.970）：RRF 融合時 fulltext／vector 取到的其他作品擠掉 graph 的正確結果。可評估「錨點命中時 hybrid 優先採 graph 結果」。
2. 應拒答 4 題：graph 錨點 T2 為 0 列後依設計退回 fulltext，仍取回 5 筆；是否拒答由生成決定，需另以回答檢查（尚未量）。
3. 正例只有大都會（別名表 40 位畫家在哈佛、荷蘭國家博物館無作品）；擴題至 100 題需更多畫家或其他限制類型（T3／T4 待資料）。

## 六、公平對照：忠實度（2026-10-12）

§四的「現況」忠實度取自 8080（經 pipe）且來源截前 900 字，與 spike（8011 API）條件不同；另發現 900 字截斷會低估忠實度（llama3.1:8b 關係題樣本 0.446→0.632）。因此重做公平對照：

- 現況 graph／hybrid 改以**相同 API 方式**在 8001 重跑（B1–B15 × 5 模型 × 2 次，`logs/eval/graph-legacy-api-2026-10-11/`）。
- 四組回答**全部以每份來源 4,000 字重判**（`FAITH_DOC_CHARS=4000`，各目錄 `faith4000/`）；裁判 gemma4:12b（未經 κ 驗證）。
- 本節取代 §四表中的忠實度數字（§四為 900 字、非同條件）。

| 路由 | 事實題 | 關係題 | 忠實度 | 關係題忠實度 | 關係題矛盾 | 關係題每答有依據句 |
|---|---|---|---|---|---|---|
| **graph（錨點）** | **1.000** | **1.000** | **0.862** | **0.858** | **0.012** | **11.7** |
| graph（現況，同條件） | 0.750 | 0.100 | 0.840 | 0.855 | 0.035 | 2.5 |
| **hybrid（錨點）** | **1.000** | **0.927** | 0.714 | 0.678 | 0.023 | 8.3 |
| hybrid（現況，同條件） | 0.992 | 0.733 | 0.817 | 0.781 | 0.044 | 5.7 |

| 模型 | graph 錨點 | graph 現況 | hybrid 錨點 | hybrid 現況 |
|---|---|---|---|---|
| llama3.1:8b | 0.800 | 0.856 | 0.667 | 0.815 |
| qwen3:8b | 0.766 | 0.756 | 0.559 | 0.712 |
| deepseek-r1:8b | 0.912 | 0.856 | 0.842 | 0.810 |
| gemma4:12b | 0.923 | 0.966 | 0.920 | 0.983 |
| qwen3:14b | 0.957 | 0.913 | 0.750 | 0.883 |

### 解讀
1. **graph 錨點**：忠實度比例與現況相當（0.862 vs 0.840），但關係題每答有依據句數 2.5→11.7（約 4.7 倍）、矛盾 0.035→0.012——現況比例高是因為檢索錯誤時模型只回很短的回答（規劃書已指出「比例須與句數並報」）。
2. **hybrid 錨點**：正確率提升（關係題 0.733→0.927），有依據句數 5.7→8.3、矛盾 0.044→0.023，但**忠實度比例下降**（0.817→0.714），主要在 qwen3:8b（0.712→0.559）、qwen3:14b、llama。取回更多對的作品後，模型寫出更長的清單並加入來源沒有的細節（每答無依據句約 1.6→3.9）。
3. 規劃書關係題矛盾指標（≤0.03）：graph 錨點 0.012 ✅、hybrid 錨點 0.023 ✅。
4. 待辦：hybrid 的生成提示需約束「只列來源中的作品與欄位」，或錨點命中時優先採 graph 結果（§五觀察 1）；忠實度裁判須完成 κ 驗證後才能作正式結論。
