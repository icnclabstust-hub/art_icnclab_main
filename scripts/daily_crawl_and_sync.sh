#!/bin/bash
# ⚠️ 已停用（2026-09-23）——請勿執行 ⚠️
#
# 這是新架構（catalog／outbox）上線前的舊版每日流程，已被
# scripts/daily_crawl_and_sync_catalog.sh 取代。目前沒有任何排程
# （Windows 工作排程器、cron）指向這支腳本；已查證確認。
#
# 危險之處：本腳本會直接呼叫 import_all_museums_to_neo4j.py、
# sync_europeana_to_databases.py，**繞過 PostgreSQL catalog／outbox**
# 直接寫入 Neo4j／ChromaDB。若被誤執行，會在唯一真相源（catalog）
# 之外多寫入一份不受 outbox 追蹤的資料，破壞「catalog 是唯一真相源」
# 這個新架構的核心前提，且不會被 `ingest verify` 的一致性檢查發現
# （因為 verify 只比對 catalog 與三庫，不知道這些寫入曾經發生過）。
#
# 原始內容已從此檔移除，改以此警告取代，避免被誤執行；完整原始
# 內容仍可由 git 歷史還原（本次移除前的版本）。若要恢復舊流程，
# 請先讀 docs/decision-log.md 2026-09-23「清除舊版每日流程腳本」條目，
# 並重新評估是否真的需要——正常情況下一律使用
# scripts/daily_crawl_and_sync_catalog.sh。

echo "❌ 此腳本已停用，請改用 scripts/daily_crawl_and_sync_catalog.sh" >&2
echo "   詳見 docs/decision-log.md 2026-09-23「清除舊版每日流程腳本」條目" >&2
exit 1
