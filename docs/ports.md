# 埠號配置表（唯一宣告處）

> 本檔是本專案埠號的**唯一真相源**。任何程式碼、腳本、文件若與本表不符，以本表為準並修正之。
> 最後更新：2026-09-20（依 `scripts/Start-NativeServices.ps1` 與 `scripts/diagnose.py` 校正）

## 0. 先理解架構：本專案不用 systemd 啟動服務

這是調查報告最大的盲點——報告只查了 `systemctl`，但**專案的服務不是由 systemd 啟動的**。

實際啟動機制是 `scripts/Start-NativeServices.ps1`（PowerShell，在 Windows 側執行），
它透過 `Start-Process wsl.exe -d Ubuntu-22.04 -- bash -c "..."` 把每個服務
拉成**獨立的 Windows 背景程序**。腳本內註解說明了原因：

> 用 `Start-Process` 讓 `wsl.exe` 成為獨立的 Windows 背景程序⋯⋯
> 這樣程序的存活期由 Windows 管理，不受 WSL session 中斷影響；
> 用 `nohup+disown` 的寫法在 WSL 底下並不可靠，服務會悄悄被砍掉

**因此「systemd 上查不到 / 服務沒在跑」不等於「沒安裝」。**

觸發來源：
- 手動執行 `Start-NativeServices.ps1`
- `scripts/Run-DailyCrawl.ps1` 第 2 行呼叫它
- 該腳本由 **Windows 工作排程器每日 03:00** 觸發
  （`scripts/ArtHistoryDB-DailyCrawl_TaskExport.xml`）
- `scripts/backup_databases.sh` 備份後也會要求重新執行它

## 1. 配置表

| 埠 | 擁有者 | 設定變數 | 依據 | 狀態 |
|---|---|---|---|---|
| **7688** | **Neo4j（專案原生實例，bolt）** | `NEO4J_URI` | `Start-NativeServices.ps1` 以 `neo4j console` 啟動；`diagnose.py:31` | 使用中 |
| **7475** | Neo4j（專案原生實例，HTTP） | — | 同上 | 使用中 |
| 7687 / 7474 | **Neo4j（WSL 系統的 systemd 實例，非專案使用）** | — | 調查報告 `ss -tlnp` 實測 | 與專案無關 |
| **8000** | **ChromaDB** | `CHROMADB_PORT` | `Start-NativeServices.ps1` 啟動 `chroma run --port 8000` 並傳入 `CHROMADB_PORT=8000`；`diagnose.py:32` | 使用中 |
| 8007 | rag-manager-v2 | `RAG_MANAGER_PORT` | `unified_rag_manager_v2.py:1626`；`diagnose.py:33` | 使用中 |
| **8080** | **Open WebUI** | — | `Start-NativeServices.ps1` 啟動 `open-webui serve --port 8080`；`diagnose.py:34`；使用者決定確認保留 | 使用中 |
| **8002** | **ml-service** (gunicorn/CUDA) | `ML_SERVICE_URL` | **由 8080 遷出**，見 §3 | 待遷移 |
| 8010 | create_graphrag_models.py | （硬編碼，應外部化） | 調查報告發現5 | 待修正 |
| 11434 | Ollama | `OLLAMA_BASE_URL` | `Start-NativeServices.ps1` 傳 `OLLAMA_BASE_URL=http://localhost:11434` | **埠衝突中**，見發現2 |
| 5432 | PostgreSQL 18 | — | 原生 systemd 服務 | 使用中 |
| 6379 | Redis | — | 原生 systemd 服務 | 使用中 |
| 9200 | Elasticsearch | `ES_PASSWORD` | systemd 服務 | **重啟迴圈中**，見發現3 |

## 2. 更正紀錄（本文件 2026-09-20 稍早版本的兩處錯誤）

### ❌ 錯誤一：曾宣稱「`NEO4J_URI` 預設 7688 是必然故障」

先前依據 `unified_rag_manager_v2.py:154` 的 `os.getenv("NEO4J_URI", "bolt://127.0.0.1:7688")`，
對照調查報告實測「現場 Neo4j 聽 7687」，推論該預設值指向空埠、RAG 後端必然連不上。

**此推論錯誤。** 這台機器上有**兩個** Neo4j：

| 實例 | 埠 | 誰啟動 | 用途 |
|---|---|---|---|
| WSL 系統的 `neo4j.service` | 7687 / 7474 | systemd | **與本專案無關** |
| 專案原生實例 | **7688 / 7475** | `Start-NativeServices.ps1` 的 `neo4j console` | 本專案使用 |

`Start-NativeServices.ps1` 啟動 rag-manager-v2 時明確傳入 `NEO4J_URI=bolt://127.0.0.1:7688`。
所以程式碼第 153 行的註解（「7688 是因為 WSL 環境本身有另一個系統 Neo4j 服務佔用了 7687」）
**是正確且仍然成立的**，不是過時註解。

調查報告只看到 7687，是因為查證當下**專案的原生 Neo4j 沒有在跑**（`Start-NativeServices.ps1` 未執行）。

### ❌ 錯誤二：曾將 ChromaDB 列為 8001

`unified_rag_manager_v2.py:164` 的預設值確實是 8001，但**執行時會被覆寫**——
`Start-NativeServices.ps1` 以 `chroma run --port 8000` 啟動，並傳入 `CHROMADB_PORT=8000`。
`diagnose.py:32` 也是 8000。**實際使用的是 8000**，程式碼預設值 8001 從未生效。

建議把 `unified_rag_manager_v2.py:164` 的預設值改為 8000 以消除落差，或依 §5 改為必填。

### 同時更正調查報告發現4 的兩列

| 服務 | 調查報告的結論 | 實際情況 |
|---|---|---|
| ChromaDB | 「pip 套件已裝，**未查到常駐服務程序**，現況不明」 | 本來就該是常駐服務（`chroma run --path /home/user/native-chromadb/data --port 8000`），只是查證當下沒在跑 |
| OpenWebUI | 「❌ **完全未安裝、未找到任何進程或套件**」 | **已安裝**，在 venv 內：`/home/user/openwebui-venv/bin/open-webui`，資料目錄 `/home/user/openwebui-data`。因為不是系統套件、查證當下也沒在跑，所以 `which` 與 `systemctl` 都查不到 |

另：`Start-NativeServices.ps1` 檔頭註明「系統已完全不使用 Docker（**2026-07-28** 移除）」，
早於 2026-08-29 的那份遷移設計文件。該文件確實是事後補寫且未更新現況。

## 3. ml-service 遷移必須同步修改的引用點

OpenWebUI 已確定保留 8080（使用者決定，且 `Start-NativeServices.ps1` 本來就是這樣啟動）。
ml-service 原本也綁 8080（`ml-service/start.sh:138`），衝突，須遷至 **8002**。

**漏改任何一處都會造成 ml-service 呼叫失敗。**

### 伺服器端
| 檔案:行 | 現值 | 應改為 |
|---|---|---|
| `ml-service/start.sh:138` | `--bind 127.0.0.1:8080` | `--bind 127.0.0.1:${ML_SERVICE_PORT:-8002}` |
| `config/production.js:9` | `port: 8080` | `port: 8002` |

### 呼叫端
| 檔案:行 | 現值 | 應改為 |
|---|---|---|
| `src/config/mlConfig.js:4` | `process.env.ML_SERVICE_URL \|\| 'http://cuda-ml-service:8080'` | 改為必填（見 §5） |
| `src/api/routes/mlRoutes.js:7` | 同上 | 同上 |
| `langchain-rag/knowledge_graph_rag.py:345` | `ml_service_url: str = "http://localhost:8080"` | 讀 `ML_SERVICE_URL` |
| `langchain-rag/integrated_rag_optimizer.py:99` | 同上 | 同上 |
| `src/mcp/mcp_tool_registry.py:228,377` | `port=8080` / `8080` | 改讀設定 |
| `monitoring/prometheus.yml:52` | `targets: ['cuda-ml-service:8080']` | `targets: ['127.0.0.1:8002']` |
| `system_full_diagnostic.py:176` | `curl http://localhost:8080/health` | `curl http://localhost:8002/health` |
| `gpu-setup.sh:98,115,116` | 說明文字 | 更新為 8002 |

### 不要動（這些指的是 OpenWebUI，本來就該是 8080）
- `langchain-rag/unified_rag_manager_v2.py:137-138` —— CORS 白名單，註解寫明「僅信任本機 Open WebUI 來源」
- `scripts/diagnose.py:34` —— Open WebUI 健康檢查
- `scripts/Start-NativeServices.ps1` —— OpenWebUI 啟動指令
- `setup-ollama-rag-proxy.sh:93,160,169`
- `test-all-rag-methods.js:329`、`test-chinese-query-fix.js:142`
- `config/default.js:177`（CORS 白名單）

> 行號已於種子 `metaversestust-pms/art_icnclab` @ `ad7eb6c` 核對。

## 4. 仍然成立的設定缺陷

### `RAG_API_PORT` 是死變數
`.env.example:23` 宣告 `RAG_API_PORT=8008`，但全專案無程式碼讀取；
程式讀的是 `RAG_MANAGER_PORT`（`unified_rag_manager_v2.py:1626`）。應自 `.env.example` 刪除。

### `cuda-ml-service` 主機名已無法解析
`src/config/mlConfig.js:4`、`src/api/routes/mlRoutes.js:7` 的預設值 `http://cuda-ml-service:8080`
是 docker-compose 服務名。Docker 已於 2026-07-28 移除，**此主機名在原生環境下無法解析**。
`.env` 未設 `ML_SERVICE_URL` 時，Node 後端連不到 ml-service。

（注意：`NEO4J_URI` 的 7688 預設值**不屬於此類**，理由見 §2。）

## 5. 結構性修法：讓設定錯誤大聲失敗

`RAG_API_PORT`、`cuda-ml-service`、`CHROMADB_PORT` 預設 8001 與實際 8000 的落差，
都源自同一種寫法：`os.getenv("X", "某個預設值")` 在設定缺漏或不符時
**安靜地用錯的值繼續跑**，錯誤要等執行期才以「連不上」的形式浮現。

```python
def required_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"必要環境變數 {name} 未設定；請參照 .env.example")
    return v

NEO4J_URI      = required_env("NEO4J_URI")
ML_SERVICE_URL = required_env("ML_SERVICE_URL")
CHROMADB_PORT  = int(required_env("CHROMADB_PORT"))
```

判準：**只要一個設定值在不同環境會不同，就不該有預設值。**

由於 `Start-NativeServices.ps1` 已經把所有必要變數明確傳入，改為必填不會影響正常啟動路徑，
反而能讓「有人繞過該腳本直接跑」這件事立刻曝光，而不是默默連到錯的實例。
