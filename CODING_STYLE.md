# 實驗室 Coding Style 規範 v1.0

> 適用對象：本實驗室所有 Python／FastAPI 系統與工具腳本的開發者（研究生、專題生、助理）。
> 制定日期：2026-08-12。狀態：**正式生效（2026-08-12 蔡老師拍板）**。

---

## 0. 為什麼要有這份文件

實驗室已有六套上線系統（PMS3、creathink、ipas_learn、ai_quiz、anchor_system、comm_advisor）。人力紀律在單人開發時撐得住，多位同學接手後必然失守。

這份文件做三件事：

1. 把已經在實踐、且被證明有效的慣例**寫成明文**，讓新同學不必靠讀舊碼猜規矩。
2. 把稽核發現的真實踩坑案例**寫成規則**（每條附反例出處），不是抄國外清單。
3. 補上缺席的**機器閘門**（Ruff、pre-commit、gitleaks、pip-audit），讓規則可被自動查核。
4. 所有同學開發系統前，要讓AI先讀本實驗室的Coding style規範，開發後，也要由老師進行程式碼檢視後才能上線。

### 規則分級（仿 SEI CERT 兩級制）

| 標記 | 意義 | 執行方式 |
|------|------|----------|
| **[MUST]** | 違反即不得合入／交付；能自動查核的由工具擋下 | CI／pre-commit 擋、review 退件 |
| **[SHOULD]** | 預設遵循；違反須在 review 說明理由 | review 提醒 |

### 基準文件（本規範未涵蓋處，依序參照）

1. [PEP 8](https://peps.python.org/pep-0008/)、[PEP 257](https://peps.python.org/pep-0257/)
2. [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
3. [OWASP Top 10 (2021)](https://owasp.org/Top10/2021/)（注意：2025 版已發布，本規範 v1 以 2021 版編號對映，改版時同步更新）
4. [OWASP Developer Guide — Web App Checklist](https://devguide.owasp.org/en/04-design/02-web-app-checklist/)（Secure Coding Practices Quick Reference 的後繼版本）
5. [OWASP ASVS 5.0](https://owasp.org/www-project-application-security-verification-standard/)
6. [NIST SP 800-218 SSDF v1.1](https://csrc.nist.gov/pubs/sp/800/218/final)

衝突時優先序：**本規範 > Google Style Guide > PEP 8**。

---

## 1. 總則（G）

- **G-01 [MUST]** 新專案自第一個 commit 起掛齊工具鏈（§6）；既有系統依《合規對照表》排程補課，不要求一次到位。
- **G-02 [MUST]** 規則能寫成工具設定的，一律交給工具，不靠口頭叮嚀（加重語氣不會讓人獲得沒有的能力；格式爭論交給 formatter 終結）。
- **G-03 [SHOULD]** 一致性優先序：模組內一致 > 專案內一致 > 本規範。改既有檔案時跟隨該檔慣例，不順手重排無關程式碼。

## 2. 格式與命名（N)

- **N-01 [MUST]** 函式／變數／模組用 `snake_case`，類別用 `PascalCase`，常數用 `UPPER_CASE`。
- **N-02 [MUST]** 格式全權交給 **Ruff formatter**（行長 100，設定見附錄 A）；不手動調整、不在 review 爭論格式。
- **N-03 [MUST]** import 置於檔案頂端、分三群（標準庫 → 第三方 → 本地），禁止 `import *`。由 Ruff `I` 規則自動排序。
- **N-04 [SHOULD]** 名稱表達意圖與單位（`timeout_seconds` 不是 `t`）；單字母名僅限迴圈索引與 comprehension 內部。極短的高頻工具函式（如 `db.q`）允許存在，但 docstring 必須交代全名語意。

## 3. 文件化與型別（D）

- **D-01 [MUST]** 所有公開函式附 **Google style docstring**（`Args:`／`Returns:`／`Raises:`，必要時 `Note:`）。單行摘要用命令語氣、句號結尾（PEP 257）。
  - 現況錨點：ai_quiz 100%、ipas_learn 98%、pms3 85% 覆蓋率——這是實驗室已達成的水準，新程式碼不得低於它。
- **D-02 [MUST]** 註解寫「**為什麼**」（決策依據、威脅模型、前提假設），不寫「做什麼」。
  - 正面範例：creathink `security.py` 把「為何用 dummy_verify 防帳號枚舉」寫進 docstring——註解本身就是教材。
  - 前提假設必須寫在**會被讀到的地方**：creathink 的「節流狀態在記憶體、僅限單 worker」只寫在 serve.ps1 註解，程式內無防呆——反例。
- **D-03 [SHOULD]** 新程式碼附型別註記（PEP 484）；核心模組（security、判分、金流類）通過 `mypy` 檢查。
- **D-04 [MUST]** 檔案 I/O 一律顯式編碼：Python `encoding="utf-8"`（讀 Excel 系 CSV 用 `utf-8-sig`）；PowerShell `-Encoding utf8`。**永不依賴 shell 預設編碼**（Windows cp950 是慣性故障源）。

## 4. 安全編碼（S）——對映 OWASP，附錄 B 有完整對照

### 密鑰與憑證

- **S-01 [MUST]** 禁止在程式碼、README、seed 腳本中硬編碼任何密碼／API key／token。一律走 `.env` 或環境變數。
  - 反例（本次稽核實際發現）：ai_quiz `seed.py:44` 硬編碼教師初始密碼 `teacher168`，且明載於 README——兩者皆已隨 repo 推上 GitHub。
- **S-02 [MUST]** `.env` 必進 `.gitignore`（即使目前還沒有 .env 檔，防線先立）；同時提供 `.env.example`（只有變數名與說明，無真值）。
- **S-03 [MUST]** 密碼與金鑰**不得印到 stdout 或寫入 log**。首次啟動的初始憑證改用：寫入權限受控的本機檔案、或空密碼＋首登強制設定，**不走 print**。
  - 反例：anchor_system 與 creathink 首次啟動把教師密碼 print 到 stdout，經 `serve.ps1` 重導向後永存 `data/*.log`。
- **S-04 [MUST]** 初始密碼與重設密碼**不可預測**：用 `secrets.token_urlsafe()` 產生一次性隨機值，並強制 `must_change_pw=True`。禁止「密碼＝學號」「密碼＝常數」。
  - 反例：ai_quiz 學生初始／重設密碼＝學號，校園環境學號半公開，重設後視窗期任何知道學號的人可搶登。

### 資料庫存取

- **S-05 [MUST]** 優先用 SQLAlchemy 2.0 ORM（`select()` 風格）。刻意走輕量路線的小系統允許裸 `sqlite3`，但**一律參數化佔位（`?`）**，禁止把任何外部輸入以 f-string／`%`／`+` 拼進 SQL。
- **S-06 [SHOULD]** DDL／PRAGMA 需動態組表名時，表名只能來自程式內常數清單，並就地註解說明非使用者輸入（anchor、creathink 現行做法，可沿用）。

### 輸入驗證

- **S-07 [MUST]** 對外 JSON API 一律以 **Pydantic schema** 定義請求／回應契約（獨立 `schemas.py`，並用 `response_model`）。Server-rendered 表單站至少做到 `Form(...)` 型別註記＋白名單／範圍驗證。
- **S-08 [SHOULD]** 所有自由文字輸入設長度上限；數值輸入 clamp 到合法範圍；識別字（帳號、代碼）用 regex 白名單。
- **S-09 [MUST]** 讀取 query／form 參數並轉型時必須處理轉型失敗（`?min=abc` 不得炸出 500）。反例：anchor_system `main.py:653` 的裸 `int()`。

### 身分驗證與 Session（實驗室標準骨架）

> ipas_learn／ai_quiz／creathink／anchor_system 的 `security.py` 已是同源骨架，v1 直接把它定為標準。

- **S-10 [MUST]** 密碼雜湊：PBKDF2-HMAC-SHA256、≥200,000 次迭代、每人獨立隨機 salt（標準庫即可）；或 bcrypt／argon2。禁止明文、禁止單輪雜湊。
- **S-11 [MUST]** 憑證比較用 `hmac.compare_digest`（防時序攻擊）；登入失敗節流（帳號＋IP 雙鍵）；查無帳號時跑 `dummy_verify()` 防帳號枚舉。
- **S-12 [MUST]** Session cookie 設 `httpOnly`；逾時 ≤ 8 小時；session token 用 `secrets.token_urlsafe(32)`。
- **S-13 [MUST]** 無認證系統（如 PMS3 的個人工具定位）必須同時滿足：(1) 威脅模型與網路邊界假設明文寫在 `main.py` 檔頭；(2) TrustedHost／Origin 白名單；(3) 僅在受控網段（Tailscale／防火牆）暴露。三者缺一即須補認證。

### 錯誤處理與日誌

- **S-14 [MUST]** 未攔截例外不得把原文回給前端。`detail=str(exc)` 只允許用在**自訂領域例外**；接在 `except Exception` 之後即為違規。健康檢查端點（`/healthz`）只回狀態字（`ok`／`degraded`），不回例外原文。
  - 反例：creathink `main.py:58` 的 `/healthz` 未登入即可觸發、DB 故障時回洩含路徑的例外原文。
- **S-15 [MUST]** log 不得含密碼、token、個資原文；log 檔一律進 `.gitignore`。隱私敏感系統參照 comm_advisor 模式：log 只記 id 與類別，不記內容。

### 依賴管理

- **S-16 [MUST]** `requirements.txt` 一律 `==` 釘死版本，檔頭註記釘版日期（creathink 模式：`# 釘版 2026-08-09`）。升級是有意識的動作：跑 `pip-audit` → 改版號 → 跑測試 → 更新日期。
- **S-17 [MUST]** 交付／部署前跑一次 `pip-audit`（PyPA 官方，用 OSV 資料庫）；有 CVE 未處理不得上線。

### 資料與版控邊界

- **S-18 [MUST]** 資料庫檔（含 `-wal`／`-shm`）、機敏 `data/` 目錄、`*.pem`、log 檔全數 ignore。**在 repo 目錄內存在 ≠ 可以被追蹤**——用 `git ls-files` 驗證，不用肉眼。
- **S-19 [MUST]** repo 有 GitHub remote（即使 private）時，**被追蹤的檔案**（含測試、prompt、詞表、README）不得含真實人名、可識別個資、或會揭露機敏脈絡的中繼資料。
  - 反例：comm_advisor 的 `data/` 隔離做得極好，但被追蹤的 `eval/backtest.py` 與 testcases 含真實人名、機敏詞表明文上雲——資料層守住了，中繼資料層漏了。

## 5. FastAPI 部署專章（F）

- **F-01 [MUST]** 生產啟動：無 `--reload`、無 debug；`docs_url=None, redoc_url=None`（或對文件頁加認證）。
- **F-02 [MUST]** 經 Cloudflare Tunnel 等公網出口的服務，一律掛 `TrustedHostMiddleware` 白名單（防 DNS rebinding／Host 偽造）。
  - 反例：ai_quiz 公網部署卻沒掛（兄弟系統 ipas_learn 有掛，屬骨架複製時漏抄）。
- **F-03 [MUST]** CORS：同源架構**不掛** CORSMiddleware（不掛＝不開放，最安全）；確有跨域需求時明列 `allow_origins`，禁止 `["*"]`，`allow_credentials=True` 時更禁萬用字元。
- **F-04 [MUST]** 節流用的 client IP 判定：只有在「服務埠已被防火牆限制為僅接受 tunnel／localhost 來源」時，才可信任 `x-forwarded-for`／`cf-connecting-ip`；否則以帳號鍵節流為主，IP 鍵視為輔助。
  - 反例：ipas_learn 與 ai_quiz 的 `_client_ip()` 無條件信任 proxy header，直連服務埠即可偽造 IP 洗掉節流。
- **F-05 [SHOULD]** 記憶體型節流（dict 存失敗次數）的單 worker 前提，必須在**程式內**寫防呆或明顯註解，不能只寫在啟動腳本。
- **F-06 [SHOULD]** 專案結構：小系統用 `app/` ＋ `routers/` 分檔；中大型系統用 pms3 的模組三件套（`router.py`＋`service.py`＋`schemas.py`）。單一 `main.py` 超過約 500 行即拆分。

## 6. 工具鏈與閘門（T）——本次稽核最大缺口，v1 的核心增量

> 六套系統此項全數掛零。以下是最小可行組合，範本檔在 `lab_standards/templates/`，複製兩個檔案即完成安裝。

- **T-01 [MUST]** 每專案根目錄放 `pyproject.toml`，設定 Ruff lint＋format：規則集 `E,W,F,I,B,S,UP`（`S` 即 flake8-bandit 安全規則），行長 100。
- **T-02 [MUST]** 掛 `pre-commit`：`ruff check --fix` → `ruff format` → `gitleaks`（擋 secrets 進版控）。安裝：`pip install pre-commit && pre-commit install`。
- **T-03 [MUST]** 交付前三連：`ruff check .`、`pip-audit`、`pytest`（若有測試）。全綠才交。
- **T-04 [MUST]** 影響**成績、金錢、不可逆資料**的邏輯（判分器、成績重算、使用者合併／刪除）必附自動化測試，改動時先跑測試再合入。
  - 反例：ai_quiz 的 `grading.py` 四題型判分與 `_regrade_question` 全額重算直接影響學生成績，零測試。
- **T-05 [SHOULD]** 每套 web 系統至少有一支端到端冒煙測試（anchor_system `tests/test_smoke.py` 模式：臨時 DB 隔離正式資料）。
- **T-06 [SHOULD]** 抑制警告必附規則碼與理由（`# noqa: S608 -- 表名來自程式內常數`），禁止裸 `# noqa`。

## 7. 流程（P）

- **P-01 [MUST]** Commit message 沿用現行慣例：`type(scope): 正體中文摘要`（type = feat/fix/docs/refactor/test/chore）。
- **P-02 [MUST]** 破壞性或有時效窗的功能，先在**臨時／拋棄式資料**上驗證，再碰正式資料（實驗室既定拍板）。
- **P-03 [SHOULD]** Code review 用附錄 C 檢核表；review 挑毛病是職責不是失禮，對事不對人。

---

## 附錄 A：工具設定範本

完整檔案在 `lab_standards/templates/`，此處為核心內容。

### `pyproject.toml`（節錄）

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
# E/W: pycodestyle  F: pyflakes  I: isort  B: bugbear  S: 安全(bandit)  UP: pyupgrade
select = ["E", "W", "F", "I", "B", "S", "UP"]
ignore = [
    "S101",  # assert 用於測試屬正常
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S105", "S106"]  # 測試內的假密碼常數
```

### `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.12.5
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.27.2
    hooks:
      - id: gitleaks
```

> `rev` 版號安裝時以 `pre-commit autoupdate` 取當時最新，之後隨釘版紀律固定。

## 附錄 B：規範 ↔ OWASP Top 10 (2021) 對映

| OWASP | 名稱 | 本規範條文 |
|-------|------|-----------|
| A01 | 存取控制失效 | S-13、F-02 |
| A02 | 密碼學失敗 | S-10、S-12 |
| A03 | 注入 | S-05、S-06、S-07 |
| A04 | 不安全設計 | S-04、S-11、F-04、F-05 |
| A05 | 安全設定錯誤 | F-01、F-02、F-03、S-02 |
| A06 | 易受攻擊與過時元件 | S-16、S-17 |
| A07 | 身分驗證失敗 | S-04、S-10、S-11 |
| A08 | 軟體與資料完整性失敗 | T-02（gitleaks）、S-16 |
| A09 | 日誌與監控失敗 | S-03、S-15 |
| A10 | SSRF | （本實驗室系統無代理外部 URL 需求，暫不立條，出現時補） |

## 附錄 C：Code Review 檢核表（10 項）

1. 密鑰／密碼是否只存在於 `.env`？（grep 一次）
2. 新增的 SQL 是否全參數化？
3. 對外輸入是否有 schema 或白名單驗證？
4. `except` 是否精準捕捉？`str(exc)` 是否只包自訂例外？
5. 新增檔案 I/O 是否顯式 UTF-8？
6. 新增依賴是否釘版、是否過 `pip-audit`？
7. 公開函式是否有 Google docstring？
8. 影響成績／不可逆資料的改動是否附測試？
9. log 有沒有多印了不該印的東西？
10. `git status`：有沒有不該追蹤的檔案混進來？

## 附錄 D：主要參考來源

- PEP 8 / PEP 257 — https://peps.python.org/pep-0008/ 、https://peps.python.org/pep-0257/
- Google Python Style Guide — https://google.github.io/styleguide/pyguide.html
- OWASP Top 10 (2021) — https://owasp.org/Top10/2021/
- OWASP Developer Guide Web App Checklist — https://devguide.owasp.org/en/04-design/02-web-app-checklist/
- OWASP ASVS 5.0 — https://owasp.org/www-project-application-security-verification-standard/
- SEI CERT Coding Standards（兩級制的出處）— https://wiki.sei.cmu.edu/confluence/display/seccode/SEI+CERT+Coding+Standards
- NIST SP 800-218 SSDF — https://csrc.nist.gov/pubs/sp/800/218/final
- Twelve-Factor App III. Config — https://12factor.net/config
- Ruff — https://docs.astral.sh/ruff/ ；pre-commit — https://pre-commit.com/
- pip-audit — https://pypi.org/project/pip-audit/ ；gitleaks — https://github.com/gitleaks/gitleaks
- FastAPI Security / CORS — https://fastapi.tiangolo.com/tutorial/security/ 、https://fastapi.tiangolo.com/tutorial/cors/

## 版本紀錄

| 版本 | 日期 | 變更 |
|------|------|------|
| v1.0 草案 | 2026-08-12 | 初版：基於六系統全面稽核＋權威標準調查制定 |
| v1.0 正式 | 2026-08-12 | 蔡老師拍板生效；rubric-grader 驗收 9/9 全過 |

---

## 適用性備註（本專案 art-history-database）

這份規範原本是為實驗室其他六套系統（PMS3、creathink、ipas_learn、ai_quiz、anchor_system、comm_advisor）制定的，本專案架構不同（Node.js 爬蟲 + Python/FastAPI RAG 後端 + Neo4j/ChromaDB，非傳統帳密系統），套用時的對應關係：

- **S-10～S-13（密碼雜湊/Session/認證）**：本專案沒有自建使用者認證系統，帳密相關規則對映到 Open WebUI 本身的登入機制，非本專案程式碼管轄範圍
- **S-05～S-06（SQL 注入）**：本專案主要用 Cypher（Neo4j）與 ChromaDB API，非傳統 SQL；對映規則精神為「查詢一律參數化，不用字串拼接」
- **N-01～N-03（命名/格式/import）**：僅適用於 Python 檔案（`langchain-rag/`、`scripts/*.py` 等），JS 爬蟲另有慣例
- 其餘 S/F/T/D 系列規則直接適用，稽核結果見專案根目錄稽核報告
