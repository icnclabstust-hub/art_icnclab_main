# 開發前評估表：查詢快取遷至 Redis（RET-11～13）

## 一、基本資料

- 任務名稱：查詢快取遷至 Redis（一般鍵值快取，決策 B10）
- 提案學生：（待填）
- 日期：2026-10-13
- 對應設計文件：`docs/designs/2026-10-13-redis-query-cache.md`

## 二、問題定義（三問）

1. 要解決什麼問題？快取只在程序記憶體、重啟即清空、未正規化（多一個問號就不命中）、來源變動不失效、拒答也被快取。
2. 誰會用？多常用？每一次 /query、/retrieve（研究者與學生）。
3. 不做會怎樣？規格 RET-11～13 未達成；同題重問付全額生成時間；來源更新後可能回舊答案。

## 三、現況調查結論

- 既有可重用：`QueryCache` 介面、兩層快取鍵設計、`/api/v1/cache/stats|clear`、outbox 訂閱器框架（`subscribers/base.py`）、`citations.py` 的 doc_id 推導。
- 現成套件／服務：Redis 6.0.16（已運作）、`redis`（redis-py，MIT）。
- 缺口：Redis 快取類別、正規化、doc_id 反向索引與失效訂閱器、拒答判斷。
- □ 調查後結論為「不需開發」

## 四、風險分級

- Tier：□ A　■ B　□ C
- 分級理由：改變 art_icnclab RAG 服務每次查詢的快取行為（CODE_REVIEW_STANDARD §2）；新增 Python 依賴與夜間流程步驟。不新增對外入口、不涉個資。

## 五、成本與時程

- 預估工時：1–1.5 人日。
- 新增依賴：`redis`（redis-py）；夜間流程新增「訂閱器 cache」一步。
- 機器資源：Redis 記憶體（以 TTL 3600 秒控制）；無 GPU。

## 六、成功指標與驗證方式

- 正規化後同題命中（含標點、空白差異）；重啟 rag-manager-v2 後快取仍在；來源 doc 更新後相關項目被刪；拒答不入快取；Redis 停止時服務照常（退回記憶體快取）。
- 驗證：單元測試（假 Redis）；部署後以 /query 實測命中、重啟後命中、失效訂閱器實測。

## 七、回滾與退場

- 設 `CACHE_BACKEND=memory` 後重啟 rag-manager-v2（約 10 秒）即回到現行行為；`git revert` 後執行 `scripts/Start-NativeServices.ps1`。
- 退場：`redis-cli --scan --pattern 'rag:*' | xargs redis-cli del`。

## 八、豁免記載

- 是否有流程豁免：■ 有——**使用者 2026-10-13 於對話中明確表示「老師已同意豁免」**本項 Tier B 簽核（依 CLAUDE.md R3 記載；§九簽核欄依 R5 不代填）。

## 九、簽核

| 角色 | 姓名 | 日期 | 結果 |
|---|---|---|---|
| 提案學生 | | | □ 確認 |
| 指導老師（Tier A/B 必填） | | | □ 核可　□ 退回 |

> 退回意見：
