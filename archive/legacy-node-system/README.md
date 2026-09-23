# 舊版 Node.js 第一代架構（已封存，2026-09-24）

本目錄保存專案最早期的架構：Node.js（Express）API＋資料庫層（`src/`）、4 個 Node.js
AI Agent（`agents/`）、Python agent／強化學習訓練系統與獨立爬蟲／匯入器
（原 `src/agents/`、`src/crawler/`、`src/importer/`、`src/mcp/`、`src/experiments/`），
以及對應的 jest 測試（`tests/`）。

## 為什麼被封存

**現行系統是 `langchain-rag/`（RAG 核心，主服務 `unified_rag_manager_v2.py`）
＋ `crawlers/`（爬蟲）＋ `scripts/`（維運），這套 Node.js 架構已經不是現行系統
的一部分**，判定依據（2026-09-24 查證）：

1. **沒有任何啟動路徑**：`scripts/Start-NativeServices.ps1`（現行服務啟動腳本，
   每日排程實際會執行的入口）完全沒有提到 `npm start`、`node src/app.js`
   或本目錄底下任何東西。
2. **git 歷史停滯超過一個月**：本目錄各部分最後一次有實質內容變動是
   2026-08-18（repo 剛精整匯入那天），之後只有全域批次改動（埠號、清 Docker
   殘留）碰過，沒有任何功能開發；同期 `langchain-rag/` 每天都有實質改動。
3. **完全沒有被現行系統 import**：現行 RAG 後端 `unified_rag_manager_v2.py`
   沒有一行 import 本目錄底下任何模組。
4. **4 天前就已被標記為舊版**：`docs/reports/2026-09-20-phase0-status.md`
   已明確記載 `src/agents/rl/rl_server.py`（8011 埠）、`create_graphrag_models.py`
   （8010 埠）等「屬舊版／已停用服務，不在架構圖上」，只是當時沒有實際執行
   清理，本次封存即是接續處理該筆記錄。

完整判斷過程與決定見 `docs/decision-log.md` 2026-09-24「封存舊版 Node.js
第一代架構」條目。

## 內容仍完整保留

所有檔案以 `git mv` 搬移，內容與內部相對路徑（例如測試檔案對 `src/` 的
`require` 相對路徑）皆未變動，理論上仍可運作。根目錄 `package.json` 的
`start`／`dev`／`format` 腳本已改指到本目錄下的對應路徑，`test`／`test:watch`
（jest）維持不變——jest 預設會掃描整個 repo，仍找得到 `tests/` 底下移入本目錄
的測試檔。`package.json` 的相依套件（`dependencies`／`devDependencies`）維持
不變，未確認是否有套件只被本目錄使用、可以移除，本次未處理。

## 若要復原

`git mv` 是可逆的一般檔案異動，用 `git log --follow` 或直接 `git mv` 回原位置
即可還原到搬移前的路徑結構；也可以直接回看本次搬移前的 commit。
