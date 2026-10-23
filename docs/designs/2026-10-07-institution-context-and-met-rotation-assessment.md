# 開發前評估表：收藏機構上下文標示（P1-4a）與 MET 輪替擴充（方案 C）

## 一、基本資料

- 任務名稱：收藏機構上下文標示（P1-4a）＋ MET 輪替擴充（方案 C）
- 提案學生：（待填）
- 日期：2026-10-07
- 對應設計文件：`docs/designs/2026-10-07-institution-context-and-met-rotation.md`

## 二、問題定義（三問）

1. 要解決什麼問題？問到收藏機構時找不到該館資料、模型把別館作品歸給它；MET（巴洛克主力來源）只收錄約 3%。
2. 誰會用？多常用？Open WebUI 使用者每次查詢（4a）；夜間流程每晚一次（C）；論文檢索評估。
3. 不做會怎樣？「某館有什麼」答不出來或答錯；關係題召回受限於收錄範圍。

## 三、現況調查結論

- 既有可重用：catalog 已有全部機構資訊（`source`／`provider`／`specialized_art.department`）；`ingest run --file`；P0-2 `check-crawl`；Phase 3 `evalrun` 量測。
- 可直接採用的現成套件／服務：MET Collection API（公開、免金鑰）。
- 仍需自行開發的缺口：上下文加機構（約 40 行）、輪替爬蟲（約 120 行）、夜間腳本 3 行、機構題小題組。
- □ 調查後結論為「不需開發」
- 更正：10-03「Europeana 來源只有 64% 有機構」不成立，不需修爬蟲補 provider。

## 四、風險分級

- Tier：□ A　■ B　□ C
- 分級理由：改動 art_icnclab RAG 服務的線上查詢路徑（CODE_REVIEW_STANDARD §2 對照表列為 Tier B）；不對公網開新入口、不涉個資、無不可逆動作（輪替新增的作品可依 external_id 軟刪除）。

## 五、成本與時程

- 預估工時：1.5 人日（4a 0.5、C 1.0），另需使用者出機構題 5～8 題（約 30 分鐘）。
- 新增依賴：無套件；新增設定 `MET_ROTATION_ENABLED`／`_PER_NIGHT`／`_CAP`；夜間流程增加約 4～8 分鐘。
- 機器資源：MET 從 1,329 增至上限 5,000 件，chunk 約 +4,000、嵌入時間每晚 +1～2 分鐘；磁碟可忽略。

## 六、成功指標與驗證方式

- 4a：機構題小題組錯誤歸屬 = 0；黃金集 15 題事實題與拒答題不退步。
- C：`evalrun` 與基準比較關係題 Recall@10／@20 不退步；前 10 筆無關來源比例不增加；夜間流程增加 ≤ 10 分鐘。
- 驗證：單元＋拋棄式 PostgreSQL 整合測試；輪替先以 `--dry-run` 跑一次；啟用後第一晚檢查 log 與 `open_alerts.txt`。

## 七、回滾與退場

- 4a：`git revert <commit>` → 執行 `scripts/Start-NativeServices.ps1`（先停 rag-manager-v2）。
- C：`.env` 設 `MET_ROTATION_ENABLED=false` 即停；已收錄作品如需撤出，依 `crawlers/data/raw/met_rotation/*.json` 的 id 清單於 catalog 軟刪除（由訂閱器同步撤出三庫）。
- 退場清理：刪除 `crawlers/met-rotation-crawler.js` 與 `crawlers/data/raw/met_rotation/`。

## 八、豁免記載

- 是否有流程豁免：■ 無

## 九、簽核

| 角色 | 姓名 | 日期 | 結果 |
|---|---|---|---|
| 提案學生 | | | □ 確認 |
| 指導老師（Tier A/B 必填） | | | □ 核可　□ 退回 |

> 退回意見：
