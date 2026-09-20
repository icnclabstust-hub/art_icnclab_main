# 埠號配置表（唯一宣告處）

> 本檔是本專案埠號的**唯一真相源**。任何程式碼、腳本、文件若與本表不符，以本表為準並修正之。
> 變更埠號 = 修改本表 + 同步修改 §3 列出的所有引用點，兩者缺一即視為未完成。
> 最後更新：2026-09-20

## 1. 配置表

| 埠 | 擁有者 | 設定變數 | 依據 | 狀態 |
|---|---|---|---|---|
| 8080 | **OpenWebUI** | — | 使用者決定（2026-09-20） | 已指派，尚未部署 |
| 8002 | **ml-service** (gunicorn/CUDA) | `ML_SERVICE_URL` | **由 8080 遷出**，見 §2 | 待遷移 |
| 8007 | unified_rag_manager_v2.py | `RAG_MANAGER_PORT` | `unified_rag_manager_v2.py:1626` | 使用中 |
| 8010 | create_graphrag_models.py | （硬編碼，應外部化） | 調查報告發現5 | 待修正 |
| 8001 | ChromaDB (server 模式) | `CHROMADB_PORT` | `unified_rag_manager_v2.py:164` | **無常駐程序**，見發現4 |
| 7687 | Neo4j | `NEO4J_URI` | **現場實測**，非程式碼預設的 7688 | 使用中 |
| 11434 | Ollama | `OLLAMA_BASE_URL` | `unified_rag_manager_v2.py:152` | **埠衝突中**，見發現2 |
| 5432 | PostgreSQL 18 | — | 原生 systemd 服務 | 使用中 |
| 6379 | Redis | — | 原生 systemd 服務 | 使用中 |
| 9200 | Elasticsearch | — | 原生 systemd 服務 | **重啟迴圈中**，見發現3 |
| 3000 | 待確認 | — | `config/default.js:177` CORS 白名單列有此埠 | 用途未確認 |

### 已廢止

| 埠／變數 | 廢止原因 |
|---|---|
| `RAG_API_PORT=8008` | **死變數**。`.env.example:23` 有宣告，但全專案無任何程式碼讀取；程式碼讀的是 `RAG_MANAGER_PORT`。應自 `.env.example` 刪除。 |
| `bolt://127.0.0.1:7688` | `unified_rag_manager_v2.py:154` 的預設值。現場 Neo4j 實際聽 7687，此預設值指向的埠上沒有任何服務。 |
| `http://cuda-ml-service:8080` | `src/config/mlConfig.js:4`、`src/api/routes/mlRoutes.js:7` 的預設值。`cuda-ml-service` 是 docker-compose 服務名，Docker 移除後此主機名**無法解析**。 |

## 2. 為什麼 ml-service 從 8080 搬到 8002

OpenWebUI 已確定使用 8080（使用者決定）。ml-service 原本也綁 8080
（`ml-service/start.sh:138`：`gunicorn --bind 127.0.0.1:8080`），兩者衝突。

選 8002 的理由：與 RAG 服務群（8001/8007/8010）同一區段、目前未被任何服務佔用、
且不與 OpenWebUI 預設值（3000/8080）相撞。

## 3. ml-service 遷移必須同步修改的引用點

**這是本次遷移的完整清單。漏改任何一處都會造成 ml-service 呼叫失敗。**

### 伺服器端（ml-service 自己綁定的埠）
| 檔案:行 | 現值 | 應改為 |
|---|---|---|
| `ml-service/start.sh:138` | `--bind 127.0.0.1:8080` | `--bind 127.0.0.1:${ML_SERVICE_PORT:-8002}` |
| `config/production.js:9` | `port: 8080` | `port: 8002` |

### 呼叫端（連到 ml-service 的地方）
| 檔案:行 | 現值 | 應改為 |
|---|---|---|
| `src/config/mlConfig.js:4` | `process.env.ML_SERVICE_URL \|\| 'http://cuda-ml-service:8080'` | 改為必填，缺漏即啟動失敗（見 §4） |
| `src/api/routes/mlRoutes.js:7` | 同上 | 同上 |
| `langchain-rag/knowledge_graph_rag.py:345` | `ml_service_url: str = "http://localhost:8080"` | `os.environ["ML_SERVICE_URL"]` |
| `langchain-rag/integrated_rag_optimizer.py:99` | 同上 | 同上 |
| `src/mcp/mcp_tool_registry.py:228` | `port=8080` | 改讀設定 |
| `src/mcp/mcp_tool_registry.py:377` | `8080` | 改讀設定 |
| `monitoring/prometheus.yml:52` | `targets: ['cuda-ml-service:8080']` | `targets: ['127.0.0.1:8002']` |
| `system_full_diagnostic.py:176` | `curl -s http://localhost:8080/health` | `curl -s http://localhost:8002/health` |
| `gpu-setup.sh:98,115,116` | 說明文字中的 8080 | 更新為 8002 |

### 不要動（這些指的是 OpenWebUI，本來就該是 8080）
- `setup-ollama-rag-proxy.sh:93,160,169`
- `test-all-rag-methods.js:329`、`test-chinese-query-fix.js:142`
- `config/default.js:177`（CORS 白名單，OpenWebUI 前端來源）

### 不要動（這些指的是 OpenWebUI，本來就該是 8080）（續）
- `langchain-rag/unified_rag_manager_v2.py:137-138`
  ——這是 **CORS 白名單**，註解寫明「僅信任本機 Open WebUI 來源」。
  OpenWebUI 既然留在 8080，這兩行**維持原樣**：

  ```python
  allow_origins=[
      "http://localhost:8080",
      "http://127.0.0.1:8080",
  ],
  ```

> **行號已核對（2026-09-20）**：上表行號原依存檔版 `icnclabstust-hub/art_icnclab` @ `9c4aebd`，
> 現已於種子 `metaversestust-pms/art_icnclab` @ `ad7eb6c` 重新核對，
> `ml-service/start.sh:138`、`unified_rag_manager_v2.py:154/164`、`.env.example:23`、
> `config/production.js:9`、`src/config/mlConfig.js:4`、`src/api/routes/mlRoutes.js:7`
> **全部一致**，可直接照用。

## 4. 結構性修法：讓設定錯誤大聲失敗

本次三個「已廢止」項目是**同一種 bug**：`os.getenv("X", "某個預設值")` 在設定缺漏時
**安靜地用錯的值繼續跑**，於是錯誤要等到執行期才以「連不上」的形式浮現，且難以歸因。

修法是讓必要設定缺漏時直接啟動失敗：

```python
# Python
def required_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"必要環境變數 {name} 未設定；請參照 .env.example")
    return v

NEO4J_URI      = required_env("NEO4J_URI")
ML_SERVICE_URL = required_env("ML_SERVICE_URL")
```

```javascript
// Node
function requiredEnv(name) {
  const v = process.env[name];
  if (!v) throw new Error(`必要環境變數 ${name} 未設定；請參照 .env.example`);
  return v;
}
const ML_SERVICE_URL = requiredEnv('ML_SERVICE_URL');
```

判準：**只要一個設定值在不同環境會不同，就不該有預設值。**
埠號、主機名、連線字串全部屬於此類。
