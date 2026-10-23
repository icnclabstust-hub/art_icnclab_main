# 問題登錄表（2026-09-20）

> 彙整調查報告 5 項發現 + 本次追查新增的問題，含狀態、依據與解法。
> 「狀態」只有三種：**已解決**（有可驗證的結果）、**已確診**（成因確定、解法明確、尚未執行）、
> **待確認**（成因未定，需要現場資料）。不使用「疑似」之類無法行動的描述。

## 一、總表

### 🔴 高：會造成系統無法運作，或讓其他工作白費

| # | 問題 | 狀態 | 依據 | 解決方法 | 誰執行 |
|---|---|---|---|---|---|
| **A4** | **執行期目錄與正本脫鉤**——實際執行的程式在 `C:\Users\user\Desktop\藝術史資料庫\art-history-database`，`.env` 也在那裡。改正本的程式碼**不會改變實際執行的系統** | 已確診 | `Start-NativeServices.ps1` 的 `$ProjectDir`；rag-manager-v2 自 `/mnt/c/.../art-history-database/langchain-rag` 啟動 | 見 §二.1（我的判斷：這是目前最重要的一項） | 需決策 |
| B2 | Ollama 埠 11434 被 PID 47888 佔用，佔用者身分未知；`Ubuntu-22.04` 的 `ollama.service` 持續 crash-loop | 待確認 | 調查報告 `journalctl`；使用者提供 `netstat` 顯示 `127.0.0.1:11434 LISTENING 47888` | 分兩條路，見 §二.2 | 使用者跑 `collect.sh` |
| B1 | Neo4j 雙實例互搶——系統 `neo4j.service`（7687）與專案原生實例（7688）並存，前者反覆啟動失敗 | **已確診** | `Start-NativeServices.ps1:60` 以 `neo4j console` 啟動專案實例，不經 systemd；報告中 `already running (pid:492)` 即此衝突 | `sudo systemctl disable --now neo4j`（停用與專案無關的系統實例）。停用前先確認 7687 上無其他用途 | 使用者 |

### 🟠 中：目前沒爆，但會在特定時機爆，或有資料遺失風險

| # | 問題 | 狀態 | 依據 | 解決方法 | 誰執行 |
|---|---|---|---|---|---|
| A2 | ZIP 快照（`F:\art_icnclab-main`）持有**唯一一份**設計文件與調查報告，且無版控 | 已確診 | 三個 git 候選皆無 `docs/designs/`；快照有 4 份 8/18 後的文件 | 執行手冊 STEP 3 的 `rescue/zip-snapshot` 分支撈回 | 使用者 |
| B3 | Elasticsearch 每 30 秒 Start→Stopped 迴圈 | 待確認 | 調查報告觀測；已排除「診斷操作造成」 | 先檢定 OOM（見 §二.3）。若確認，釘死 heap `-Xms2g -Xmx2g` | 使用者跑 `collect.sh` |
| B5 | **服務無監管**——由 `Start-Process wsl.exe` 拉起的程序死掉後沒有任何東西重啟它，要等隔天 03:00 排程 | 已確診 | `Start-NativeServices.ps1` 無 watchdog；觸發僅工作排程器每日一次 | 見 §二.4 | 需決策 |
| C1 | ml-service 與 OpenWebUI 都綁 8080 | 已確診 | `ml-service/start.sh:138` vs `Start-NativeServices.ps1` 的 `open-webui serve --port 8080` | ml-service 遷 8002，**8 處引用點須同步改**，清單見 `ports.md` §3 | 可由 AI 改 |
| A5 | 公開 repo `icnclabstust-hub/art_icnclab` 的**歷史提交**未做金鑰稽核 | 待確認 | 已驗證 HEAD 檔案樹無追蹤 `.env`；歷史未查 | `git log --diff-filter=A --name-only \| grep -iE '\.env\|secret'`。有命中就輪換金鑰，不改寫歷史 | 可由 AI 做 |

### 🟡 低：設定不一致，會造成誤判與維護成本

| # | 問題 | 狀態 | 依據 | 解決方法 | 誰執行 |
|---|---|---|---|---|---|
| C3 | `cuda-ml-service:8080` 主機名無法解析（舊服務名） | 已確診 | `src/config/mlConfig.js:4`、`src/api/routes/mlRoutes.js:7` | 改為必填環境變數，缺漏即啟動失敗 | 可由 AI 改 |
| C4 | `CHROMADB_PORT` 程式碼預設 8001，實際執行為 8000 | 已確診 | `unified_rag_manager_v2.py:164` vs `Start-NativeServices.ps1`、`diagnose.py:32` | 預設值改 8000，或改為必填 | 可由 AI 改 |
| C2 | `.env.example:23` 的 `RAG_API_PORT` 是死變數，無程式碼讀取（程式讀 `RAG_MANAGER_PORT`） | 已確診 | 全庫 grep | 自 `.env.example` 刪除 | 可由 AI 改 |
| C5 | `create_graphrag_models.py` 硬編碼 8010 | 已確診 | 調查報告發現5 | 外部化為環境變數 | 可由 AI 改 |
| C6 | `os.getenv("X", "預設值")` 模式——設定缺漏時**安靜地用錯的值繼續跑** | 已確診 | C2/C3/C4 三項同源 | 必要設定改為缺漏即啟動失敗（`required_env`） | 可由 AI 改 |
| A3 | 本機 clone `D:\art_icnclab` 落後 26 個 commit | 已確診 | 本機 2 commit vs 存檔 repo 28 commit；`git status` 為 0 筆 | **無獨有內容，直接改名封存**，不需搬移也不需 rescue | 使用者 |
| A6 | 正本 repo 的預設分支仍是 `claude/problem-solving-help-egvjnu` | 已確診 | `git ls-remote` 的 HEAD | GitHub Settings → Branches 改為 `main`（我無此權限） | 使用者 |

### 🟢 文件類：不影響運作，但會誤導後續判斷

| # | 問題 | 狀態 | 解決方法 |
|---|---|---|---|
| D2 | 調查報告發現4 有兩列錯誤：ChromaDB「未查到常駐服務」、OpenWebUI「完全未安裝」 | 已確診 | 兩者都是「當下沒在跑」而非「不存在」；OpenWebUI 裝在 `/home/user/openwebui-venv/`。更正已記於 `ports.md` §2 |
| D3 | 無任何文件記載「這套系統實際上怎麼啟動」 | **已解決** | `ports.md` §0 已補上 |

### ✅ 已解決

| # | 問題 | 結果 |
|---|---|---|
| A1 | 正本不存在（`art_icnclab_main` 是空 repo） | `main` 已種，`ad7eb6c` → `cfcf9fe`，含規劃文件與兩支診斷腳本 |
| A0 | 不知道哪一份是正本 | 四份候選已實測比對，種子定案。查出本機 clone 落後 26 commit——若照調查報告研判採用它，會丟失 8/18 整日修復（含兩項資安性質） |

---

## 二、我的判斷

以下四點是我在整理過程中形成的看法，**與現行計畫的排序不同**，理由一併寫出。

### 1. A4 才是最重要的一項，它目前排在「Phase 3 再說」是錯的

現行計畫把執行期目錄歸為「服務歸屬問題，等 Phase 3 處理」。我認為這個排序有問題。

理由：`Start-NativeServices.ps1` 的 `$ProjectDir` 指向
`C:\Users\user\Desktop\藝術史資料庫\art-history-database`，rag-manager-v2 也是從
`/mnt/c/.../art-history-database/langchain-rag` 啟動的。這代表：

> **實際在跑的程式碼不在任何一個 git repo 裡。**
> 我們花力氣種好的正本，目前是一個「沒有任何東西從它執行」的 repo。

所以 C1～C6 那些程式碼修正，改在正本上**不會改變實際運行的系統**，除非有一條路把正本送到執行期目錄。
換句話說：**A4 不解決，C 類全部的修正都只是紙上作業**——這正是調查報告一開始擔心的那個問題，
只是層級更深一層。

**我的建議（兩個選項，我傾向前者）：**

| 選項 | 做法 | 優點 | 缺點 |
|---|---|---|---|
| **甲（建議）** | 把執行期目錄變成正本的 git checkout。先比對差異（`rescue/runtime-dir` 分支），把獨有內容收回正本，再讓該目錄 `git clone` 正本、保留本機 `.env` 不進版控 | 從此「改正本 = 改實際系統」，單一真相源真正成立 | 需要一次停機；`.env` 與資料目錄要小心處理 |
| 乙 | 維持兩份，寫一支部署腳本從正本同步到執行期目錄 | 不必停機，風險低 | 仍是兩份，同步沒做就會再次分歧——等於把問題延後 |

**但這一步不能現在做**，因為要先確認 B1/B2/B3（服務歸屬），否則停機時機無法掌握。
正確順序是：**B1 → B2/B3 → A2 → A4**。

### 2. B5（服務無監管）比它看起來嚴重，而且有個比現況更好的解法

`Start-NativeServices.ps1` 刻意避開 systemd，腳本註解說明理由是
「`nohup+disown` 在 WSL 底下並不可靠，服務會悄悄被砍掉」。這個判斷在**當時**是對的。

但現在情況不同了：這台機器的 `Ubuntu-22.04` **已經有 systemd**
（`neo4j.service`、`elasticsearch.service`、`postgresql`、`redis` 都是 systemd 服務）。
既然 systemd 可用，用 `Start-Process wsl.exe` 繞過它就沒有必要，而且付出了代價：

- 服務死了沒有任何東西重啟它，要等隔天 03:00
- 這正是調查報告查證當下「什麼都沒在跑」的原因
- 也是 B1（雙 Neo4j 互搶）的成因——一個走 systemd、一個不走

**建議**：把專案的四個服務改寫成 systemd unit，綁專案自己的埠（7688/8000/8007/8080），
並設 `Restart=always`。系統那個 `neo4j.service` 依 B1 停用。
這樣 B1 與 B5 一起消失，`Start-NativeServices.ps1` 退化成一句 `systemctl start`。

**可行性**：四支 unit 檔，每支約 10 行，是我可以直接寫的。
風險在於要改變既有運維習慣，需要你同意。

### 3. C1（8080 之爭）應該和 C2～C6 綁在一起做，不要單獨做

C1 要改 8 處引用點。C2～C6 也都是改同一批設定讀取處。
分兩次做等於把同一批檔案動兩次、測兩次、審兩次。**併成一個 PR 做完，成本低於分開做。**

而且 C6（`required_env`）應該**最後做**——先把 C2～C5 的值修正確，再上「缺漏即失敗」的閘門。
順序反過來會讓系統一開始就起不來，難以分辨是設定錯還是閘門誤擋。

### 4. 不要現在重寫 D1 那份設計文件

D1 的 2026-08-29 文件前提已失真。直覺反應是「趕快更新它」，但我認為現在不該做：
**B2/B3 還沒確認，現在寫的「現況」一樣會在幾天內過期。**
正確做法是等 B 類全部收斂後一次寫，並且標記舊文件 superseded 而非原地修補
（修補一份前提不成立的文件，成本高於重寫，改完還是沒有簽核紀錄）。

---

## 三、執行順序（含相依性）

```
第一階段（今天就能做，不互相依賴）
  B1  停用系統 neo4j.service ─────┐
  B2  跑 collect.sh 確認 11434 ───┼── 都是現場指令，可一次做完
  B3  跑 collect.sh 檢定 ES OOM ──┘
  A5  公開 repo 歷史金鑰稽核（可由我並行執行）

第二階段（B 類收斂後）
  A2  撈回 ZIP 快照的設計文件
  C1~C6  設定與埠號一次改完（C6 最後）

第三階段（需要停機，需先確認服務歸屬）
  A4  執行期目錄與正本合一   ← 我認為這是整件事的終點
  B5  服務改 systemd unit

隨時可做
  A3  封存本機 clone      A6  改預設分支
  D1  重寫設計文件（等 B 類收斂後）
```

## 四、卡在哪

| 缺什麼 | 誰能給 | 影響哪幾項 |
|---|---|---|
| `collect.sh` 的輸出 | 使用者（一行指令） | B2、B3 |
| A4 要選甲案還是乙案 | 使用者決策 | A4、C 類是否有意義 |
| B5 是否改用 systemd | 使用者決策 | B5、B1 |
