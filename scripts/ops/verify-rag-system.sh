#!/bin/bash
# RAG 系統驗證腳本

echo "==========================================="
echo "🎉 RAG 功能整合完成 - 最終驗證"
echo "==========================================="
echo ""
echo "📊 所有服務狀態:"
echo ""

echo "1. Neo4j (7474):"
curl -s http://localhost:7474 > /dev/null && echo "   ✅ 運行中" || echo "   ❌ 未運行"

echo ""
echo "2. ChromaDB (8001):"
curl -s http://localhost:8001/api/v1/heartbeat > /dev/null && echo "   ✅ 運行中" || echo "   ❌ 未運行"

echo ""
echo "3. Ollama (11434):"
curl -s http://localhost:11434/api/tags > /dev/null && echo "   ✅ 運行中" || echo "   ❌ 未運行"

echo ""
echo "4. Multi-DB RAG Server (8010):"
curl -s http://localhost:8010/health > /dev/null && echo "   ✅ 運行中" || echo "   ❌ 未運行"

echo ""
echo "5. Ollama RAG Proxy (11435):"
curl -s http://localhost:11435/health > /dev/null && echo "   ✅ 運行中" || echo "   ❌ 未運行"

echo ""
echo "6. OpenWebUI (8080):"
docker ps --filter name=art-history-openwebui --format "   ✅ {{.Status}}"

echo ""
echo "==========================================="
echo "📊 RAG 模型統計:"
echo "==========================================="
echo ""

RAG_COUNT=$(docker exec art-history-openwebui curl -s http://172.26.104.197:11435/api/tags 2>/dev/null | grep -o '"is_rag_model":true' | wc -l)
echo "可用的 RAG 組合模型: $RAG_COUNT 個"

echo ""
echo "==========================================="
echo "🎯 下一步操作:"
echo "==========================================="
echo ""
echo "1. 訪問 OpenWebUI: http://localhost:8080"
echo "2. 選擇 RAG 模型（例如：qwen2.5-vector_rag）"
echo "3. 開始提問藝術史問題！"
echo ""
echo "📚 推薦問題:"
echo "   • 莫內的代表作品有哪些？"
echo "   • 印象派和後印象派的區別？"
echo "   • 梵高和高更的關係？"
echo ""
echo "==========================================="
echo "📖 文檔清單:"
echo "==========================================="
echo ""
echo "✅ 快速開始指南.md - 3 分鐘快速上手"
echo "✅ RAG功能整合完成報告.md - 完整系統說明"
echo "✅ 後續步驟_添加RAG功能.md - 詳細配置步驟"
echo "✅ WSL2環境配置說明.md - WSL2 特定問題"
echo "✅ restart-openwebui-wsl2.sh - 自動配置腳本"
echo ""
echo "==========================================="
echo ""
