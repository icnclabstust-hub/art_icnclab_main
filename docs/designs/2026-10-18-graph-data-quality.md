# 設計文件：Neo4j 圖譜資料品質修正（館藏連結、作者解析、Harvard 作者）

> 範本：`docs/templates/DESIGN_DOC.md`＋`docs/templates/PRE_DEV_ASSESSMENT.md`（§10）。
> 狀態：**草案，待指導老師核可**（Tier B：改變攝取流程與正式圖譜資料）。目前只做了只讀健檢與離線測試，正式圖譜未改。
> 量測紀錄：`docs/reports/2026-10-14-layer2-experiments.md` 追加 27（E28）、28（E29）。

## 1. 背景與問題
使用者 2026-10-18 要求「Neo4j 圖譜也完善起來」。只讀健檢（未刪除作品 4,664 件、作者節點 3,203 個）發現三個系統性缺陷，都會讓圖譜檢索查不到或查錯：

| # | 缺陷 | 規模 | 根因 |
|---|---|---|---|
| D1 | 作品沒有館藏連結（HELD_BY） | 940 件（芝加哥 299、V&A 310、克里夫蘭 331） | `classify_art_history_graph.py` 的 `FIXED_SOURCE_INSTITUTIONS` 只列 4 個來源，後加的三館漏列 |
| D2 | 作者名字被切壞 | 疑似片段名字 1,618／3,261；有具名作者的博物館作品只有 65.2% 連到正確作者 | `subscribers/neo4j_sub.py:_artist_names`（及舊 `import_all_museums_to_neo4j.py`）一律以逗號切開；各來源逗號意義不同（「Feure, Georges de」→「Feure」「Georges de」；「Salvador Dalí⏎Spanish, 1904–1989」→「Salvador Dalí⏎Spanish」「1904–1989」） |
| D3 | Harvard 作品全部沒有作者 | 430 件（原始檔可補 284 件，其中 55 件為 Unidentified Artist） | JS 爬蟲存 `people[].name`，攝取沿用的 `normalize_harvard` 讀 `people[].displayname` |

不修會怎樣：問「芝加哥藝術博物館有哪些達利的作品」圖譜查不到（D1＋D2）；羅丹等 Harvard 作品在圖譜沒有作者（D3）；圖譜錨點擴充（E28）能認得的畫家受限於名字品質（D2）。

## 2. 目標與非目標
- 目標：D1 館藏連結 ≥ 99%；D2 有具名作者的博物館作品作者連結正確 ≥ 95%、片段名字 ≤ 10%；D3 可補回的 Harvard 作者全部補回。修正後圖譜錨點與既有題組召回率不下降。
- 非目標：作者實體合併（同一人多個節點、希臘文與拉丁文重複）——以別名表的 `neo4j_names` 處理，不改節點；不新增資料來源；不改 Chroma／ES 的文件內容（D3 例外：攝取會更新 Harvard 文件的 Creator 行，屬正確化）。

## 3. 現況與重用
- 重用：`classify_art_history_graph.py`（每晚以 `--no-clean` 疊加，D1 只需補對照表）；`ingest`（重攝即可更新 Harvard 文件，D3）；`subscribers/neo4j_sub.py` 的 `_write` 與失效邏輯（D2 只換 `_artist_names`）；`scripts/build_artist_terms.py`（修正後重建別名表與詞典）。
- 缺口：沒有依來源解析作者字串的模組；圖譜沒有「重建某作品作者連結」的遷移腳本。

## 4. 方案比較（至少兩案）
| | 方案 A：修源頭＋一次性遷移（建議） | 方案 B：只做圖譜後處理清理 | 方案 C：不改資料，只在檢索端補救 |
|---|---|---|---|
| 作法 | D1 補對照表；D2 新增 `ingest/artist_names.py`（依來源解析），`neo4j_sub` 改用之，並以遷移腳本重建全部作品的 CREATED；D3 修 `normalize_harvard` 欄位後重攝 Harvard | 寫腳本在圖譜上合併／刪除片段節點、補 HELD_BY；攝取流程不改 | 圖譜錨點以 `source` 判館（已做，E28 開關）、別名表收片段名字 |
| 優點 | 根因修正，之後每晚新資料也正確；可重跑、可驗證 | 不動攝取流程 | 不動資料，風險最低 |
| 缺點 | 改動較多（攝取＋訂閱器＋遷移），需停用期間外執行 | 每晚新資料會再產生錯誤，需每天清理；合併規則難以驗證 | 片段名字無法對到 Wikidata，問題留在資料裡；其他使用圖譜的功能（分類、題目產生）仍錯 |
| 回退 | 遷移前 Neo4j 備份（每晚已有）；CREATED 依 `source` 重建可再跑舊規則 | 同左 | 關開關 |

選 A：D1、D3 都是一兩行的根因修正；D2 的解析規則已離線驗證（E29），遷移可重跑。方案 C 的開關（`GRAPH_MUSEUMS_EXT`）保留作為過渡，D1 上線後仍相容。

## 5. 系統設計
- **D1**：`FIXED_SOURCE_INSTITUTIONS` 加入 `art_institute_chicago → Art Institute of Chicago`、`cleveland_museum → Cleveland Museum of Art`、`va_museum → Victoria and Albert Museum`、`yale_university_art_gallery → Yale University Art Gallery`（與 `graph_anchor.MUSEUMS_EXT` 的機構名一致）。下一次每晚 classify 自動建立。
- **D2**：`ingest/artist_names.py: parse_artists(source, raw) -> list[str]`（草案見 E29）：
  1. 有換行取第一行；去 URI、角色註記（「. Auteur du texte」）、年份；括號內是人名（「Perugino (Pietro di Cristoforo Vannucci)」）保留，其餘去掉；
  2. 逗號分段，去掉國籍、世紀、「Workshop」等角色詞、頭銜（MBE、Mrs）；已有拉丁字母寫法時去掉純希臘文等重複；
  3. 「姓, 名」合併（含 & 的公司名、Google Books 多位作者不合併）；去重；Anonymous／Unknown／Unidentified／Unbekannt／onbekend 視為無作者。
  - `neo4j_sub._artist_names` 改為呼叫 `parse_artists`；遷移腳本 `scripts/migrate_artist_links.py`：對每件作品以新規則算作者，刪除不在新清單內的 CREATED、補上新清單的 CREATED（`valid_to` 規則沿用訂閱器），最後刪除孤立 Artist 節點；`--dry-run` 先輸出差異統計。
- **D3**：`normalize_harvard` 改為 `p.get("displayname") or p.get("name")`；執行 `python3 -m ingest run --source harvard`（重攝，content hash 變動的文件才更新）。
- 修正後：重跑 `build_artist_terms.py`（別名表與詞典的 `neo4j_names` 依新節點重建）。

## 6. 安全與隱私考量
- 只處理公開館藏的作者欄位；不涉個資。遷移在 Neo4j 每晚備份之後、02:55～03:40 以外執行。

## 7. 測試策略
- 單元測試：`parse_artists` 以 E29 的 16 個範例＋各來源各 10 筆人工標註為測試資料（人工標註待做）。
- 遷移 `--dry-run`：變動的 CREATED 數、孤立節點數、各來源差異抽樣，人工檢查後才實際執行。
- 迴歸：8011 上量限制條件 33 題、關係 6 題、E28 新增畫家 30 題（重建別名表後）、K canary；Recall@5 不得下降。
- 遷移後健檢：S1～S4（`docs/designs/2026-10-18-completeness-scorecard.md`）。

## 8. 部署與運維
- 順序：D3（修欄位＋重攝 Harvard）→ D2（訂閱器改用新解析＋遷移 dry-run → 人工確認 → 執行）→ D1（對照表，隔天每晚 classify 生效）→ 重建別名表與詞典 → 8011 迴歸 → 依各自評估表上線相關開關。
- 每一步都可單獨回退：D1 刪除四館 HELD_BY（`MATCH (w)-[h:HELD_BY]->(i) WHERE w.source IN [...] DELETE h`）；D2 以舊規則重跑遷移或還原 Neo4j 備份；D3 還原 `normalize_harvard` 後重攝。

## 9. 未解決問題
- 解析規則對 Europeana／specialized 的機構名（「Lköpping University」）、頭銜（「barone di S. Egidio」）仍有少量誤判；以 dry-run 抽樣決定是否加規則。
- 「Unknown Artist」等無作者作品是否保留一個「佚名」節點以支援「佚名作品」查詢（目前規則是不連）。

## 10. 開發前評估（PRE_DEV_ASSESSMENT 摘要）
| 項目 | 內容 |
|---|---|
| 三問 | 解決圖譜館藏與作者缺陷（D1～D3）；使用者是查詢館藏與畫家的學生／研究者；不做則圖譜檢索對四館與 Harvard 作品查不到或查錯 |
| 風險 Tier | B（改攝取流程與正式圖譜資料；可回退） |
| 成本 | 實作約半天（解析模組＋遷移腳本＋測試）；遷移執行數分鐘；重攝 Harvard 約 10 分鐘 |
| 成功指標 | §2 目標；8011 迴歸召回率不下降 |
| 回滾 | §8 |
| 豁免 | 無 |

## 簽核
| 角色 | 姓名 | 日期 | 結果 |
|---|---|---|---|
| 提案學生 | | | □ 確認 |
| 指導老師 | | | □ 核可　□ 退回 |
