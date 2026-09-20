# Phase 1 執行手冊：把正本種起來（art_icnclab_main）

> 對象：`icnclabstust-hub/art_icnclab_main`——已確定為新正本，但**目前是空的**（除了本分支的文件）。
> 因此 Phase 1 不是「比對副本」，而是「**先選種子把正本種起來，再把其餘副本的獨有內容撈回來**」。
> 所有指令請在 WSL `Ubuntu-22.04` 內執行，並把輸出回貼。

## ✅ 已解除的風險：遺失一個月的工作

原本的顧慮是：存檔 repo 的 README（2026-08-18）指明開發移至 `metaversestust-pms/art_icnclab`，
距今整整一個月；若該處有人開發過而我們用舊 clone 當種子，那一個月的工作會被靜默丟掉。

**STEP 0 已查證：該 repo 在 2026-08-18 之後沒有任何提交，此風險不存在。**
（保留本節是為了記錄「為什麼要先做 STEP 0」——換成另一種結果，這一步就是不可逆的資料損失。）

---

## STEP 0：清點候選種子 —— ✅ 已完成（2026-09-20）

指令已執行、輸出已判讀。**結論：種子 = `metaversestust-pms/art_icnclab` @ `ad7eb6c`。**

### 實測結果

| 候選 | HEAD | 日期 | commit 數 | 樹狀結構 | 有 `docs/designs`？ | 有 8/29 與今天的工作？ |
|---|---|---|---|---|---|---|
| **精整版** `metaversestust-pms/art_icnclab` | `ad7eb6c` | 2026-08-18 **12:24:42** | 2 | **已重整**（爬蟲收進 `crawlers/`、根目錄雜檔已清） | ❌ | ❌ |
| 存檔版 `icnclabstust-hub/art_icnclab` | `9c4aebd` | 2026-08-18 **12:23:01** | **28** | 舊版（檔案散在根目錄） | ❌ | ❌ |
| `D:\art_icnclab` | `979745c` | 2026-08-17 | 2 | 舊版 | ❌ | ❌ |
| `D:\art_icnclab-main\art_icnclab-main`（ZIP） | 無 `.git` | — | — | — | ✅ | ✅ |

### 判讀一：原先擔心的「遺失一個月工作」風險 —— 不存在

`metaversestust-pms/art_icnclab` 的兩個 commit 都在 2026-08-18，最後一筆是 12:24:42
（僅比存檔版的搬家公告 `9c4aebd` 12:23:01 晚 **1 分 41 秒**）。
**搬家之後到今天為止，該 repo 沒有任何新開發。** 所以無論選誰當種子，都不會丟掉那一個月的工作
——因為那一個月根本沒有 git 提交。風險解除。

### 判讀二：`D:\art_icnclab` 落後 **26 個 commit**（這點推翻了調查報告的前提）

本機 clone 只有 2 個 commit（`dadaa47`、`979745c`，皆為 2026-08-17），
但存檔 repo 共有 **28 個**——2026-08-18 當天一口氣做了 26 次提交，其中包含大量實質修復：

```
8c13905 feat(lint): 建立 eslint flat config，139 個 JS 首次納入 lint；修復其揪出的 7 個真 bug
0b232f0 fix: 解除全部 0.0.0.0 綁定並清零 B904，順修 S-14 例外原文外洩
9110d34 fix: 清零 F841 全部 22 處，含兩個實際缺陷修復與三個設計缺口註記
d33de74 fix: 補上 8 處 requests 呼叫缺少的 timeout
5857cd2 fix(obsidian-tool): 憑證驗證改為可啟用，新增 CA_CERT valve
22aba38 fix(ml-service): simple-app 不再寫死 debug=True，改由 FLASK_DEBUG 控制
41ca6eb docs: 納入 AI 協作規範（CLAUDE.md）、上線前檢視標準與 GD 模板
...（另有 19 筆）
```

已驗證 `dadaa47`、`979745c` 兩個 commit **確實存在於存檔 repo 的歷史中**，
所以 `D:\art_icnclab` 是正牌 clone，只是**沒有 pull 過，停在 8/17**。

**若當初照調查報告的研判，把 `D:\art_icnclab` 當成正本，會丟掉上面這一整天的修復**
（含資安性質的 0.0.0.0 綁定解除與憑證驗證修復）。這是本次 STEP 0 最大的實際收穫。

### 判讀三：選精整版當種子的理由

1. **最新**：它是所有 git 候選中 HEAD 最晚的，且獨有一筆 `ad7eb6c`（requirements 加 UTF-8 BOM，
   修復 Windows cp950 下 pip 讀不到的問題）——這筆只有它有。
2. **內容無損**：其 init commit `1540b97` 自述「源自 `icnclabstust-hub/art_icnclab` @ `80f6cf9`」，
   而 `80f6cf9` 正是存檔版的倒數第二筆（最後一筆只是加搬家公告）。
   也就是說**精整版已涵蓋存檔版的全部程式內容**，只是重新整理了目錄結構。
3. **這是團隊 8/18 已經做過的決定**，沒有理由推翻。

### 代價（必須知情）

精整版是「全新歷史」，只有 2 個 commit。**採用它 = 放棄存檔版那 28 個 commit 的 `git blame` 追溯能力。**
但這個代價在 8/18 就已經付了，不是本次新增的。存檔 repo 會繼續存在，
需要考古時仍可到 `icnclabstust-hub/art_icnclab` 查。

### 另外確認

- **精整版沒有 `db_backups/`**（存檔版有 4 個檔，含 `neo4j_data.tar.gz`、`chromadb_data.tar.gz`、
  `openwebui_data.tar.gz`，走 Git LFS）。存檔 README 說的「還原資料仍需從這裡取得」屬實。
  **建議不要搬進正本**，改在正本 README 註明來源。
- **三個 git 候選都沒有 `docs/designs/`。** 8/29 的 Docker 遷移設計文件、今天的架構改版設計文件、
  以及那份調查報告本身，**全部只存在於 ZIP 快照**。這正是調查報告最擔心的情況，現已精確確認。
  這些檔案會在 STEP 2 的 `rescue/zip-snapshot` 分支被完整撈回。

---

## STEP 1：種正本（保留 git 歷史）

種子已定案為 `metaversestust-pms/art_icnclab` @ `ad7eb6c`。

```bash
# 取一份乾淨的種子（不要用 /mnt/d/art_icnclab，它落後 26 個 commit）
git clone https://github.com/metaversestust-pms/art_icnclab.git ~/seed
cd ~/seed
git log -1 --format='%h %s'      # 應為 ad7eb6c fix(deps): requirements 檔加 UTF-8 BOM...
git remote add canon https://github.com/icnclabstust-hub/art_icnclab_main.git
git fetch canon

# 把種子的完整歷史推成正本的 main
git push canon HEAD:refs/heads/main
```

> 注意：正本 `art_icnclab_main` 目前的 `claude/problem-solving-help-egvjnu` 分支上已有
> 本批規劃文件（`docs/ports.md` 等）。種完 `main` 之後，該分支需要 rebase 或 merge 到 `main` 上，
> 否則兩者是無共同祖先的獨立歷史。建議：先種 `main`，再把規劃文件以一個 commit 補上去。

為什麼是 `git push` 而不是複製檔案：**這樣正本會繼承種子的完整 commit 歷史**。
若改用複製檔案 + 一個 initial commit，所有 `git blame` / `git log` 的追溯能力就永久消失了。

驗收：

```bash
git ls-remote canon | head      # 應看到 refs/heads/main
```

---

## STEP 2：把其餘每份副本的「獨有內容」撈成 rescue 分支

這一步的設計重點：**不需要任何人為判斷**。`git status --porcelain` 的輸出就是答案，
而且因為全程在分支上操作，隨時可回退，**不可能覆蓋掉別人的工作**。

```bash
git clone https://github.com/icnclabstust-hub/art_icnclab_main.git ~/canon
cd ~/canon

# 每份副本一個 rescue 分支。以 ZIP 快照為例：
git checkout main
git checkout -b rescue/zip-snapshot

rsync -a --delete \
  --exclude='.git/' --exclude='node_modules/' --exclude='data/' \
  --exclude='db_backups/' --exclude='*venv*/' --exclude='.env' \
  --exclude='.webui_secret_key' --exclude='__pycache__/' \
  /mnt/d/art_icnclab-main/art_icnclab-main/ ./

git status --porcelain          # ← 這就是這份副本相對正本的獨有內容
```

#### 執行前務必先乾跑一次（`-n`）

ZIP 快照裡有 `py311_venv/`（Windows 版 venv，內含數千個 site-packages 檔案）。
排除清單若沒生效，會把整包 venv 倒進正本。先乾跑確認：

```bash
rsync -an --delete --stats \
  --exclude='.git/' --exclude='node_modules/' --exclude='data/' \
  --exclude='db_backups/' --exclude='*venv*/' --exclude='py311_venv/' \
  --exclude='.env' --exclude='.webui_secret_key' --exclude='__pycache__/' \
  /mnt/d/art_icnclab-main/art_icnclab-main/ ./ | tail -20

# 再直接確認幾個不該出現的路徑有沒有被漏掉：
rsync -an --delete \
  --exclude='.git/' --exclude='node_modules/' --exclude='data/' \
  --exclude='db_backups/' --exclude='*venv*/' --exclude='py311_venv/' \
  --exclude='.env' --exclude='.webui_secret_key' --exclude='__pycache__/' \
  /mnt/d/art_icnclab-main/art_icnclab-main/ ./ \
  | grep -cE 'py311_venv|site-packages|node_modules|\.env$'
# ↑ 必須輸出 0。不是 0 就不要往下做，把輸出貼回來。
```

### 判讀規則（只有三種結果）

| `git status --porcelain` 輸出 | 意義 | 處置 |
|---|---|---|
| 空 | 內容完全被正本涵蓋 | `git checkout main && git branch -D rescue/...`，該副本可直接封存 |
| 只有 `D ` 開頭 | 是正本的子集 | 同上，可直接封存 |
| 有 `M ` 或 `?? ` | **有獨有變更** | `git add -A && git commit -m "rescue: ZIP 快照獨有內容"` 然後 `git push -u origin rescue/zip-snapshot` |

其餘副本重複同一套（記得換分支名與來源路徑）：

```bash
# 過期 clone
git checkout main && git checkout -b rescue/stale-clone
rsync -a --delete --exclude='.git/' --exclude='node_modules/' --exclude='data/' \
  --exclude='db_backups/' --exclude='*venv*/' --exclude='.env' \
  --exclude='.webui_secret_key' --exclude='__pycache__/' \
  /mnt/d/art_icnclab/ ./
git status --porcelain

# 執行期目錄（排除清單更嚴格：資料與金鑰絕不進版控）
git checkout main && git checkout -b rescue/runtime-dir
rsync -a --delete --exclude='.git/' --exclude='node_modules/' --exclude='data/' \
  --exclude='db_backups/' --exclude='*venv*/' --exclude='.env*' \
  --exclude='.webui_secret_key' --exclude='__pycache__/' --exclude='logs/' \
  "/mnt/c/Users/user/Desktop/藝術史資料庫/" ./
git status --porcelain
```

> **`--exclude` 清單是安全關鍵**，不是效能考量。漏掉 `.env` 或 `.webui_secret_key`
> 會把真實金鑰 commit 進去；漏掉 `data/`、`db_backups/` 會塞爆 repo。

---

## STEP 3：產出處置表並封存

每份副本記錄一列，**每列都要有 rescue 分支名與 commit hash 作為憑據**：

| 副本路徑 | rescue 分支 | 獨有檔案數 | commit | 處置 |
|---|---|---|---|---|
| `D:\art_icnclab-main\art_icnclab-main` | `rescue/zip-snapshot` | ? | ? | 待決定 |
| `D:\art_icnclab` | `rescue/stale-clone` | ? | ? | 待決定 |
| `C:\...\藝術史資料庫` | `rescue/runtime-dir` | ? | ? | 待決定 |

封存動作（**不要刪除，先改名**，這樣出錯可以反悔）：

```bash
mv /mnt/d/art_icnclab-main "/mnt/d/_ARCHIVED_2026-09-20_art_icnclab-main"
mv /mnt/d/art_icnclab      "/mnt/d/_ARCHIVED_2026-09-20_art_icnclab"
```

執行期目錄 `藝術史資料庫` **先不要動**——服務可能正指著它跑，
要等 Phase 3 確認服務歸屬之後再處理。

---

## 本手冊未涵蓋（需另行處理）

1. **`db_backups/`（Git LFS）**：存檔 repo 的 README 明講「部署還原資料時仍需從這裡取得」。
   正本要不要一併承接這些 LFS 物件，是獨立決定——LFS 物件很大，建議**不要**搬進正本，
   而是在正本 README 註明「還原資料請至 `icnclabstust-hub/art_icnclab` 取得」。
2. **公開 repo 的歷史金鑰稽核**：見主計畫 §1.4。已驗證存檔 repo 的 HEAD 檔案樹未追蹤任何
   `.env`，但**歷史提交未查**。
