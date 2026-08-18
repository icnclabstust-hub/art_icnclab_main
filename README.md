# 藝術史資料庫爬蟲系統

專注於RAG集成的藝術史資料庫爬蟲系統，透過精簡的4個AI Agent協同工作，建立高品質的藝術史資料收集、處理與API服務系統。

## 🎯 核心目標

- 自動化收集權威藝術史資料
- 標準化資料處理與分類
- 提供多格式RAG系統API端點
- 支援不同RAG框架無縫集成

## 🏗️ 系統架構

### 4個AI Agent架構
1. **WebCrawlerAgent** - 網路爬蟲與資料收集
2. **MetadataExtractorAgent** - 元資料提取與標準化
3. **ClassificationAgent** - 多維度分類與標籤生成
4. **SummarizationTranslationAgent** - 摘要翻譯與多語言支援

### 技術棧
- **後端**: Node.js + Express
- **資料庫**: PostgreSQL + Redis + Elasticsearch
- **爬蟲**: Playwright + Cheerio
- **AI處理**: OpenAI API + HuggingFace

## 🚀 快速開始

### 環境需求
- Node.js >= 18.0.0
- 必要的API Keys (OpenAI, HuggingFace, DeepL)

### 安裝步驟
```bash
# 1. 複製環境變數文件
cp .env.example .env

# 2. 編輯環境變數 (填入你的API keys)
nano .env

# 3. 安裝依賴
npm install

# 4. 啟動開發服務器
npm run dev
```

### 服務端點
- **API服務**: http://localhost:3000
- **監控面板**: http://localhost:3001
- **資料庫管理**: localhost:5432 (PostgreSQL)

## 📊 API端點

### RAG集成端點
```
/api/v1/rag/
├── langchain/      # LangChain格式
├── llamaindex/     # LlamaIndex格式
├── openai/         # OpenAI格式
└── custom/         # 自定義格式
```

### 核心資源端點
```
/api/v1/
├── artworks/       # 藝術品資料
├── artists/        # 藝術家資料
├── collections/    # 館藏資料
├── metadata/       # 元資料查詢
└── search/         # 搜索服務
```

## 📁 專案結構

```
art_icnclab/
├── src/                    # Node API（Express）與 Python agent 系統
├── agents/                 # 4 個 AI Agent 實作
├── crawlers/               # 各博物館爬蟲與啟動器
├── langchain-rag/          # RAG 核心（Neo4j + ChromaDB + Ollama，主服務 unified_rag_manager_v2.py）
├── openwebui-pipes/        # OpenWebUI 整合 pipes
├── scripts/                # 維運腳本（scripts/ops/ 含部署、資料管線）
├── tests/                  # jest 單元測試；tests/manual/ 為手動整合腳本
├── docs/                   # 設計文件模板（GD 流程）
└── config/                 # Node 端設定與 schema
```

> 本 repo 為 icnclabstust-hub/art_icnclab 的精整版：全新歷史、移除執行產出物與
> 資料傾印、根目錄散檔歸位。資料庫備份（db_backups）留在原 repo 的 LFS。

## 🔧 開發資訊

### 開發時程
- **階段一** (4週): 基礎架構建設
- **階段二** (6週): 核心功能開發
- **階段三** (2週): 整合測試與部署

### 當前狀態
🚧 專案初始化階段 - 環境準備與基礎架構建設中

## 📞 支援

如有問題或建議，請提交issue或聯繫開發團隊。