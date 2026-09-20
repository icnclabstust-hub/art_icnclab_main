# Phase 1 執行手冊：把正本種起來（art_icnclab_main）

> 對象：`icnclabstust-hub/art_icnclab_main`——已確定為新正本，但**目前是空的**（除了本分支的文件）。
> 因此 Phase 1 不是「比對副本」，而是「**先選種子把正本種起來，再把其餘副本的獨有內容撈回來**」。
> 所有指令請在 WSL `Ubuntu-22.04` 內執行，並把輸出回貼。

## ⚠️ 開始前：一個會靜默毀掉一個月工作的風險

`icnclabstust-hub/art_icnclab` 的 README（2026-08-18）明確寫著：

> 後續開發一律在 `metaversestust-pms/art_icnclab`（全新歷史的精整版）

從 2026-08-18 到今天 2026-09-20 是**整整一個月**。若這段期間有人在
`metaversestust-pms/art_icnclab` 上開發，而我們用 `D:\art_icnclab`（停在 2026-08-17）
當種子，**那一個月的工作會被靜默丟掉，而且事後很難發現**。

**所以 STEP 0 不可跳過。**

---

## STEP 0：清點所有候選種子的新舊（唯讀，約 5 分鐘）

```bash
# --- 候選 A：公告指定的開發 repo（本 session 無存取權，需你來跑） ---
git ls-remote https://github.com/metaversestust-pms/art_icnclab.git HEAD
# 若上面成功，再 clone 一份來看時間：
git clone --depth 5 https://github.com/metaversestust-pms/art_icnclab.git /tmp/cand-a 2>&1 | tail -2
git -C /tmp/cand-a log -5 --format='%h %ad %s' --date=short

# --- 候選 B：本機的過期 clone ---
git -C /mnt/d/art_icnclab log -5 --format='%h %ad %s' --date=short
git -C /mnt/d/art_icnclab status --porcelain | wc -l     # 有幾個未提交變更
git -C /mnt/d/art_icnclab remote -v

# --- 候選 C：ZIP 快照（無 .git，只能看檔案時間） ---
ls -la --time-style=long-iso /mnt/d/art_icnclab-main/art_icnclab-main | head -20
find /mnt/d/art_icnclab-main/art_icnclab-main -name '*.md' -newermt '2026-08-18' \
     -not -path '*/node_modules/*' | head -30

# --- 候選 D：執行期目錄 ---
ls -la --time-style=long-iso "/mnt/c/Users/user/Desktop/藝術史資料庫" | head -20
ls -la --time-style=long-iso "/mnt/d/藝術史資料庫" | head -20
diff -rq "/mnt/c/Users/user/Desktop/藝術史資料庫" "/mnt/d/藝術史資料庫" 2>&1 | head -20
```

### 判讀規則

| STEP 0 的結果 | 種子該選誰 |
|---|---|
| 候選 A 存在，且 HEAD 日期 > 2026-08-18 | **選 A**。它有那一個月的工作，其餘都是舊的。 |
| 候選 A 存在，但 HEAD 就是 2026-08-18 前後 | 搬家後沒人在那開發過。選 **B**（有完整 git 歷史）。 |
| 候選 A 不存在／沒有權限 | 選 **B**，並在正本 README 註明「metaversestust-pms 未納入，原因：無法存取」。 |

**請把 STEP 0 的輸出貼回來，我依上表幫你定種子，再給 STEP 1 的指令。**
（下面的 STEP 1～3 先寫出來讓你知道全貌，但**請等種子確定後再執行**。）

---

## STEP 1：種正本（保留 git 歷史）

假設 STEP 0 選出的種子在 `$SEED`（A 是 `/tmp/cand-a`，B 是 `/mnt/d/art_icnclab`）。

```bash
SEED=/mnt/d/art_icnclab          # ← 依 STEP 0 結果替換

cd "$SEED"
git remote add canon https://github.com/icnclabstust-hub/art_icnclab_main.git
git fetch canon

# 把種子的完整歷史推成正本的 main
git push canon HEAD:refs/heads/main
```

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
