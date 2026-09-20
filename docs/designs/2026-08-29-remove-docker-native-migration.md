# 設計文件：移除 Docker，四項服務改原生部署

> 狀態：**草案，GD 步驟3（設計）產出，尚未走完步驟4（評估／老師核可）**。
> 依 `CLAUDE.md` R2：本文件為 GD 通過前允許輸出的「設計文件」，不含可執行的實作程式碼/腳本。
> `docs/templates/DESIGN_DOC.md`、`PRE_DEV_ASSESSMENT.md` 尚未建立，本檔為 ad hoc 格式，
> 項目依 `CODE_REVIEW_STANDARD.md` 第 89-97 行「G1 送審包」要求排列。

## 0. 提案人與日期
- 提出日期：2026-08-29
- 提出人：（使用者填）
- 對應對話：與 Claude 討論「移除 Docker 部署」

## 1. 系統一頁說明

**用途**：art-history-database 的 RAG + LLM 服務堆疊，透過 OpenWebUI 提供對話介面，
背後由 Neo4j（知識圖譜）、ChromaDB（向量檢索）、Ollama（本地 LLM 推論）三個資料/推論服務支撐。

**使用者是誰**：實驗室成員，透過 tunnel 對外存取（見 `.env.example` 的 `RAG_API_PORT`、
`OLLAMA_BASE_URL=http://host.docker.internal:11434` 等設定隱含的對外服務性質）——**多人使用、非單人自用工具**。

**資料流**：
```
使用者瀏覽器 → OpenWebUI (8080) → Ollama RAG Proxy (11435) / Multi-DB RAG Server (8010)
                                        ↓                           ↓
                                  Ollama (11434)          ChromaDB (8001) + Neo4j (7474/7687)
```

**對外端點清單**（目前已知，來自 `scripts/ops/*.sh` 與 `.env.example`）：
| 服務 | Port | 用途 |
|---|---|---|
| OpenWebUI | 8080 | 對話介面（使用者入口） |
| Multi-DB RAG Server | 8010 | RAG 檢索 API |
| Ollama RAG Proxy | 11435 | 帶 RAG 上下文的 Ollama 相容代理 |
| Ollama | 11434 | LLM 推論 |
| ChromaDB | 8001 | 向量檢索 |
| Neo4j | 7474 (HTTP) / 7687 (Bolt) | 圖譜查詢 |
| RAG API (FastAPI, unified_rag_manager_v2) | 8008 (`RAG_API_PORT`) | 核心 RAG 服務 |

**Tier 自評**：**Tier B（暫定，待老師確認）**——公網可達（tunnel）+ 多人使用，
但目前未確認是否經手個資／成績（`.env.example` 只看到 API 金鑰與資料庫密碼，
未見學生個資欄位）。依 `CODE_REVIEW_STANDARD.md` T-Tier-01「有疑義時一律往上取」，
先以 Tier B 起算，若確認經手個資則升 Tier A。

**不做會怎樣**：維持現狀，繼續用 Docker（`docker run`/`docker start`/`docker exec`）
管理四個容器。功能不受影響，但部署機若真的不能裝/管理 Docker，則此系統無法在該機器上線。

## 2. 現況調查（GD 步驟2）

### 2.1 現有 Docker 依賴盤點
四個容器由 `docker run`/`docker start`/`docker exec` 管理，指令散布於：
- [scripts/ops/setup-ollama-rag-proxy.sh](../../scripts/ops/setup-ollama-rag-proxy.sh) — 啟動檢查、OpenWebUI 的完整 `docker run` 指令
- [scripts/ops/check_system_status.sh](../../scripts/ops/check_system_status.sh) — 四容器健康檢查、Neo4j/Ollama 的 `docker exec`
- [scripts/ops/download-models.sh](../../scripts/ops/download-models.sh) — `docker exec art-history-ollama ollama pull/list/run`
- [scripts/ops/verify-rag-system.sh](../../scripts/ops/verify-rag-system.sh)、`verify-multi-database-system.sh`、`test_rag_performance.sh`、`start_graph_viz_demo.sh` — 驗證腳本，內含 `docker exec` 呼叫

容器清單：`art-history-neo4j`、`art-history-chromadb`、`art-history-ollama`、`art-history-openwebui`。

### 2.2 一個重要發現：`deploy.sh` 引用的 Docker Compose 堆疊本身不存在
[scripts/ops/deploy.sh](../../scripts/ops/deploy.sh) 是另一套（看似更完整的）部署腳本，
依賴 `docker-compose.optimized.yml`、`ml-service/Dockerfile`、`config/nginx/nginx.conf`、
`monitoring/prometheus.yml` 等檔案——**經確認這些檔案目前都不存在於 repo 中**。
也就是說 `deploy.sh` 目前執行到 `check_prerequisites()` 就會直接 exit 1，是一支現在就跑不動的腳本。

**這對本次任務的意義**：真正在運作的是 `check_system_status.sh` / `setup-ollama-rag-proxy.sh`
描述的「四個 `docker run` 手動容器」這條線，不是 `deploy.sh` 的 Docker Compose 那條線。
`deploy.sh` 本身已經是死碼，遷移範圍可以不含它（或視為順便清理）。

### 2.3 可重用性結論
- 「不寫程式」不成立：四個服務都需要實際的原生安裝與資料遷移，無法只靠參數化解決
- 但每個服務的原生部署方式都是**官方主推路徑**，不是冷門技巧（見下方方案 A 明細）——複用官方安裝腳本/套件，不必自己重造輪子

## 3. 方案比較（GD 步驟3，至少兩案）

| | 方案 A：全面原生化 | 方案 B：部分遷移（留 Neo4j 在 Docker） | 方案 C：改用 Podman |
|---|---|---|---|
| 作法 | Neo4j/ChromaDB/Ollama/OpenWebUI 全改 systemd 常駐服務 | 只把 Ollama+ChromaDB+OpenWebUI 原生化，Neo4j 留容器 | 不改架構，容器工具從 Docker 換成 Podman（CLI 相容、免 root daemon） |
| 是否解決「不能裝/管理 Docker」 | 是，徹底不依賴 Docker | 否，仍殘留一個容器 | 部分——如果卡點是「Docker 需要 root daemon」，Podman 可 rootless 執行；如果卡點是「完全不能有任何容器化技術」，則不成立 |
| 遷移風險 | 高：四份資料都要搬家（Neo4j 圖資料、ChromaDB 向量、Ollama 模型、OpenWebUI 使用者資料） | 中：少一份資料要搬 | 極低：資料原地不動，換的只是容器 runtime |
| 已知額外相依衝突 | OpenWebUI 必須裝在獨立 venv，理由：已實測 `pip install open-webui` 會把 `langchain` 拉到 1.2.10、`langchain-core` 拉到 1.6.1，直接違反 `requirements.txt` 對 langchain-neo4j 0.5.0 / langchain-openai 0.3.35 釘死 0.3.x 的硬性要求 | 同左（OpenWebUI 那部分風險一樣） | 無新增衝突 |
| 維運負擔變化 | 增加：4 個 systemd unit、log rotation、重啟策略要自己顧，換掉 Docker `--restart always` 的免費機制 | 增加但範圍較小 | 幾乎不變，Podman 提供近似 `docker restart --restart=always` 的機制（quadlet / systemd 整合） |
| 副作用 | 順便解掉 Ollama 的 GPU passthrough 風險（Windows/容器 GPU 直通常見痛點），因為 Ollama 原生本來就是官方預設用法 | 同左，Ollama 那部分一樣受益 | 不解決 GPU passthrough，仍是容器內存取 GPU |

**使用者已選定：方案 A（全面原生化）**，理由是「部署機不能裝/不想管理 Docker（權限、資源、維持成本考量）」——這個限制條件下，殘留任何容器（含 Podman）都不成立，只有方案 A 徹底滿足。

### 3.1 方案 A 技術細節（各服務原生化做法）

| 服務 | 原生做法 | 資料遷移 |
|---|---|---|
| Neo4j | 官方 apt repo 安裝 Community Edition，`systemctl enable --now neo4j` | `neo4j-admin database dump` 從容器匯出 → 原生服務 `neo4j-admin database load` 匯入 |
| Ollama | 官方腳本 `curl -fsSL https://ollama.com/install.sh \| sh`，內建 systemd unit | 複製容器內 `/root/.ollama/models` 到原生路徑（`$OLLAMA_MODELS` 或預設 `/usr/share/ollama/.ollama/models`） |
| ChromaDB | `pip install chromadb`，用內建 `chroma run --path <data> --port 8001` 常駐（包成 systemd unit） | 複製容器 volume 的持久化資料夾到原生 `<data>` 路徑 |
| OpenWebUI | **獨立 venv**（例如 `/opt/arthistory/openwebui_venv`，Python 3.11，已驗證相容），`pip install open-webui`，`open-webui serve` 包成 systemd unit | 複製容器 volume `open-webui:/app/backend/data` 到原生資料夾，透過 `DATA_DIR` 環境變數指向 |

## 4. 風險與回滾方案（R-05：需具體，不得寫「重新部署」）

**停服務指令**（原生化後，若要緊急退回舊 Docker 架構）：
```bash
sudo systemctl stop neo4j ollama chromadb openwebui   # 停原生服務
```

**退版**：本設計文件對應的實作 PR／commit 尚未產生；一旦進入實作階段，
回滾點為「遷移前的最後一個 commit」（實作 PR 合併前的 commit hash，屆時填入）。

**備份檔實際路徑與還原指令**（實作階段需在遷移腳本中落實，此處為設計階段的路徑規劃）：
```bash
# 遷移前備份（範例路徑，實作時需寫死在腳本並驗證存在）
docker exec art-history-neo4j neo4j-admin database dump neo4j --to-path=/backup
docker cp art-history-neo4j:/backup /opt/arthistory/migration-backup/neo4j-$(date +%F)
docker cp art-history-chromadb:/chroma/data /opt/arthistory/migration-backup/chromadb-$(date +%F)
docker cp art-history-ollama:/root/.ollama/models /opt/arthistory/migration-backup/ollama-$(date +%F)
docker cp art-history-openwebui:/app/backend/data /opt/arthistory/migration-backup/openwebui-$(date +%F)

# 還原（若原生化失敗，退回 Docker）
docker start art-history-neo4j art-history-chromadb art-history-ollama art-history-openwebui
```

> Tier A 系統要求上線前**實際演練一次還原**（R-05）——本系統若確認為 Tier A，
> 此演練需排入實作計畫，不能只是紙上方案。

## 5. 待評估 / 待老師拍板事項（GD 步驟4）

- [ ] Tier 分級最終確認（暫定 B，待確認是否經手個資／成績）
- [ ] Tier A／B 依 `CLAUDE.md`：**須取得指導老師核可後才能進入步驟5實作**
- [ ] 是否需要停機維護窗口？四項服務資料遷移期間服務會中斷，需與使用者（實驗室成員）協調時間
- [ ] `deploy.sh` 引用的 Docker Compose 堆疊（不存在的檔案）是否一併移除或補完，還是保留現狀不理
- [ ] 原生服務的監控/告警機制（Docker 沒了之後，`docker ps` 式的健康檢查要換成 `systemctl status` + 是否要接 Prometheus，見 `check_system_status.sh` 目前的檢查邏輯需要同步改寫）
- [ ] 回滾演練的實際排程（若 Tier A）

## 6. 本文件範圍外（明確排除）

- 不包含實作腳本／systemd unit 檔案本身（GD 未過前不得輸出）
- 不包含 `scripts/ops/*.sh` 的實際修改
- 不包含 GPU 相關腳本（`gpu-setup.sh`、`deploy.sh` 內的 `--gpus all`）的處理，因其依賴的 Docker Compose 堆疊本身不存在，視為獨立問題
