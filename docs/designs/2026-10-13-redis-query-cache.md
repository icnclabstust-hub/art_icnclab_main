# 設計文件：查詢快取遷至 Redis（RET-11～13，決策 B10）

- 日期：2026-10-13
- 需求：使用者要求「Redis 快取 :6379 完成部署」；經比較後選定**一般鍵值快取**（依規格決策 B10，非語意近似快取）。
- 規格：`docs/2026-09-23-system-spec-srs.md` §5.4 RET-10～13、決策 B10。
- 評估表：`2026-10-13-redis-query-cache-assessment.md`（Tier B，使用者表示老師已同意豁免）。

## 一、現況（步驟 2 調查）

| 項目 | 現況 |
|---|---|
| 快取 | 程序內 `QueryCache`（OrderedDict LRU＋TTL，1000 筆、3600 秒）；鍵＝MD5(query｜strategy｜max_results)，**未正規化**；重啟即清空 |
| 兩層使用 | 檢索結果（鍵含路由與 source_filter）、答案（鍵含組合、溫度、長度上限、source_filter） |
| Redis | 6.0.16 運作中，0 筆；無密碼（`.env` 的 `REDIS_PASSWORD` 實際未啟用）；`maxmemory` 未設、`noeviction`；無向量模組 |
| 依賴 | RAG 執行環境（WSL 系統 python3.10）未安裝 `redis` 套件 |
| 失效 | 無；夜間流程最後一步清空快取 |

## 二、設計

1. **`langchain-rag/redis_cache.py`：`RedisQueryCache`**，介面與 `QueryCache` 相同（get／set／clear／get_stats），`unified_rag_manager_v2.py` 呼叫端不變。
   - 鍵：`rag:q:` ＋ SHA-256（正規化問題｜策略鍵｜max_results）。正規化：NFKC、去頭尾空白、連續空白合一、英文小寫、去句末標點（？?。.!！）。（RET-11）
   - 值：JSON；`SETEX` 帶 TTL（沿用 `QUERY_CACHE_TTL`，預設 3600 秒）。
   - 統計：hits／misses 以 Redis 計數器保存（`rag:stats:*`），多程序共用。
   - 清空：只以 `SCAN` 刪 `rag:*` 前綴，不 `FLUSHDB`（Redis 可能與他人共用）。
2. **來源變動失效（RET-12）**：寫入時把該項目用到的每個 `doc_id` 加入反向索引集合 `rag:doc:<doc_id>`（同 TTL）；新增訂閱器 `subscribers/cache_sub.py`（`python -m subscribers run --target cache`），讀 outbox 的 document／chunk 事件，刪除受影響的快取項。夜間流程在三個資料庫訂閱器之後執行。
3. **不快取拒答（RET-13）**：檢索結果為空不寫入；答案符合拒答句型（「檢索結果中沒有找到」「無法回答」「知識庫中尚無」等）或來源為空時不寫入。
4. **退回**：`CACHE_BACKEND=redis`（預設）；Redis 連不上時記警告並退回程序內 `QueryCache`，服務不中斷。`CACHE_BACKEND=memory` 可直接回到現行行為。
5. 命中時回應的 `cache_hit: true` 已存在，不變。

## 三、不做

- 語意近似快取（B10 否決：相似但不同的藝術史問題會拿到錯誤答案）。
- 修改 Redis 伺服器設定（maxmemory、密碼）：Redis 可能共用，另案處理；本設計以 TTL 控制容量。
