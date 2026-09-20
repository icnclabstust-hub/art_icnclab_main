# Phase 1 執行手冊：把正本種起來

> **正本**：`icnclabstust-hub/art_icnclab_main`（已確定，但目前是空的）
> **種子**：`metaversestust-pms/art_icnclab` @ `ad7eb6c`（已於 2026-09-20 實測定案，依據見第一節）
> **快照**：`F:\art_icnclab-main`（2026-09-20 由 D 槽搬移）
> 所有指令在 WSL `Ubuntu-22.04` 內執行；標示 PowerShell 者在 Windows 執行。

---

## 一、已確認的事實（2026-09-20 實測）

### 1.1 四份候選的實測結果

| 候選 | HEAD | 日期 | commit 數 | 樹狀結構 | `docs/designs` | 8/29 與今日工作 |
|---|---|---|---|---|---|---|
| **精整版** `metaversestust-pms/art_icnclab` | `ad7eb6c` | 08-18 **12:24:42** | 2 | 已重整 | ❌ | ❌ |
| 存檔版 `icnclabstust-hub/art_icnclab` | `9c4aebd` | 08-18 **12:23:01** | **28** | 舊版 | ❌ | ❌ |
| 本機 clone（原 `D:\art_icnclab`） | `979745c` | 08-17 | 2 | 舊版 | ❌ | ❌ |
| **快照** `F:\art_icnclab-main` | 無 `.git` | — | — | — | ✅ | ✅ |

### 1.2 三項判讀

**① 「遺失一個月工作」的風險不存在。**
精整版最後一筆 `ad7eb6c` 是 2026-08-18 12:24:42，僅比存檔版的搬家公告 `9c4aebd`（12:23:01）
晚 1 分 41 秒，且全 repo 只有 2 個 commit。搬家後至今沒有任何新提交。

**② 本機 clone 落後 26 個 commit —— 推翻調查報告的前提。**
本機只有 2 個 commit（皆 08-17），存檔 repo 有 **28** 個。08-18 當天提交了 26 次，含：

```
8c13905  eslint 納入 139 個 JS，修復其揪出的 7 個真 bug
0b232f0  解除全部 0.0.0.0 綁定，順修例外原文外洩
9110d34  清零 F841 22 處，含兩個實際缺陷修復
d33de74  補上 8 處 requests 呼叫缺少的 timeout
5857cd2  obsidian-tool 憑證驗證改為可啟用
41ca6eb  納入 CLAUDE.md、上線前檢視標準與 GD 模板
```

已驗證 `dadaa47`、`979745c` 均存在於存檔 repo 歷史中 → 本機是正牌 clone，只是從未 pull。
**調查報告研判它是「真正的開發用 repo」，方向相反；若據此當正本，會丟失上述整日修復（含兩項資安修復）。**

**③ 選精整版當種子的依據。**
HEAD 最新且獨有 `ad7eb6c`（requirements 加 UTF-8 BOM，修復 Windows cp950 下 pip 讀不到）；
其 init `1540b97` 自述源自存檔版 `@80f6cf9`——正是存檔版倒數第二筆，故**程式內容完全涵蓋**，
差別只在目錄重整（爬蟲收進 `crawlers/`）。且此為團隊 08-18 既有決定。

**代價（須知情）**：精整版是全新歷史、僅 2 個 commit，採用它等同放棄存檔版 28 個 commit 的
`git blame` 追溯。但這個代價在 08-18 就已付出，非本次新增；存檔 repo 續存可供考古。

### 1.3 兩項附帶確認

- **三個 git 候選都沒有 `docs/designs/`。** 8/29 的 Docker 遷移文件、今日兩份架構設計文件、
  以及調查報告本身，**只存在於快照**。調查報告擔心的「變更只是紙上存在」屬實，
  這些會在 STEP 3 完整撈回。
- **精整版沒有 `db_backups/`**（存檔版有 4 檔走 Git LFS：`neo4j_data.tar.gz`、
  `chromadb_data.tar.gz`、`openwebui_data.tar.gz`、`README.md`）。
  **建議不搬入正本**，在正本 README 註明還原資料來源即可。

---

## 二、路徑基準

快照是用 GitHub「Download ZIP」解壓的，典型結構會多包一層同名目錄。搬到 F 槽後層數可能改變，
**層數判斷錯，後面每一條 `rsync` 都會對錯目錄**。所以第一件事是把它釘死：

```bash
SNAP=/mnt/f/art_icnclab-main
[ -e "$SNAP/art_icnclab-main/package.json" ] && SNAP="$SNAP/art_icnclab-main"

echo "快照根目錄 = $SNAP"
ls "$SNAP" | head -12          # 應看到 package.json / langchain-rag / ml-service / docs
[ -d "$SNAP/docs/designs" ] && echo "✅ docs/designs 在，設計文件確實在這份" \
                            || echo "❌ 找不到 docs/designs，路徑可能不對，先停下來"
```

另外兩份副本的位置（是否隨快照搬到 F 槽未確認，先探測）：

```bash
for d in /mnt/*/; do
  find "$d" -maxdepth 3 -type d \
    \( -name node_modules -o -name '*venv*' -o -name site-packages -o -name .git \) -prune -o \
    -type d \( -iname '*art*icnclab*' -o -iname '*藝術史*' \) -print 2>/dev/null
done
```

---

## STEP 1：先查搬動造成的破口（與發現3 可能直接相關）

專案換磁碟後，任何寫死舊路徑的東西都會斷。若時間點與「Neo4j／Elasticsearch 反覆重啟」吻合，
**這可能就是發現3 的成因**，所以排在種正本之前。

```bash
# 1. 已斷的符號連結（調查報告提到 /home/user/icnclab/art_history_db）
find "$HOME" -maxdepth 4 -type l ! -exec test -e {} \; -print

# 2. systemd unit 裡寫死的舊路徑
grep -rnE '/mnt/[a-z]/' /etc/systemd/system/*.service 2>/dev/null | head -20

# 3. 服務實際指向的工作目錄
for s in neo4j elasticsearch ollama; do
  printf '%s: ' "$s"
  systemctl show "$s" -p WorkingDirectory -p ExecStart --value 2>/dev/null | tr '\n' ' '
  echo
done
```

**任何一條指向已不存在的路徑，就是搬動造成的破口。** 修法：

```bash
ln -sfn "$SNAP" "$HOME/icnclab/art_history_db"    # 重建符號連結（路徑依實際狀況）
sudo systemctl daemon-reload                       # 改過 unit 檔後必須執行
```

---

## STEP 2：種正本

```bash
# 取乾淨的種子。不要用本機那份 clone —— 它落後 26 個 commit
git clone https://github.com/metaversestust-pms/art_icnclab.git ~/seed
cd ~/seed
git log -1 --format='%h %s'      # 必須是 ad7eb6c fix(deps): requirements 檔加 UTF-8 BOM...

# 把種子的完整歷史推成正本的 main
git remote add canon https://github.com/icnclabstust-hub/art_icnclab_main.git
git push canon HEAD:refs/heads/main

git ls-remote canon | head       # 驗收：應看到 refs/heads/main
```

**為什麼用 `git push` 而不是複製檔案**：這樣正本會繼承種子的 commit 歷史。
若改成複製檔案加一個 initial commit，`git blame` / `git log` 的追溯能力就永久消失。

> 正本的 `claude/problem-solving-help-egvjnu` 分支上已有本批規劃文件。
> `main` 種好後兩者是**無共同祖先的獨立歷史**，需把規劃文件以一個 commit 補到 `main` 上，
> 不要嘗試 merge。

---

## STEP 3：撈回快照的獨有內容

設計重點：**不需要任何人為判斷。** `git status --porcelain` 的輸出就是答案。
全程在分支上操作，隨時可回退，**不可能覆蓋掉別人的工作**——這正是調查報告
「貿然搬動有覆蓋他人工作的風險」那個顧慮的解法。

### 3.1 先乾跑，確認排除清單有效

快照裡有 `py311_venv/`（Windows 版 venv，數千個 site-packages 檔案）。排除若失效會整包倒進正本。

```bash
git clone https://github.com/icnclabstust-hub/art_icnclab_main.git ~/canon
cd ~/canon && git checkout main && git checkout -b rescue/zip-snapshot

EX=(--exclude='.git/' --exclude='node_modules/' --exclude='data/' --exclude='db_backups/'
    --exclude='*venv*/' --exclude='py311_venv/' --exclude='.env'
    --exclude='.webui_secret_key' --exclude='__pycache__/')

# 三個數字一起看，才能確定這道檢查本身是有效的
TOTAL=$(rsync -avn --delete          "$SNAP"/ ./ | wc -l)
KEPT=$( rsync -avn --delete "${EX[@]}" "$SNAP"/ ./ | wc -l)
BAD=$(  rsync -avn --delete "${EX[@]}" "$SNAP"/ ./ \
        | grep -cE 'py311_venv|site-packages|node_modules|/\.env$|webui_secret')

echo "不排除的檔案數 TOTAL = $TOTAL"
echo "排除後的檔案數 KEPT  = $KEPT"
echo "漏網的敏感/垃圾檔 BAD = $BAD"

if [ "$TOTAL" -lt 5 ]; then
  echo "❌ TOTAL 太小，代表 rsync 沒跑成功或 SNAP 路徑錯了。停下來，不要往下做。"
elif [ "$BAD" -ne 0 ]; then
  echo "❌ 有 $BAD 個該擋的檔案沒擋掉。停下來，把輸出貼出來。"
elif [ "$KEPT" -ge "$TOTAL" ]; then
  echo "❌ 排除前後檔案數一樣，代表排除清單根本沒生效。停下來。"
else
  echo "✅ 通過：排除清單有效，$((TOTAL - KEPT)) 個檔案被正確擋下"
fi
```

> **為什麼要同時看三個數字**：只看 `BAD -eq 0` 是不夠的。
> `rsync -an` **不加 `-v` 就不會輸出檔案清單**，此時 `grep -c` 永遠回傳 0，
> 指令沒裝、路徑打錯、rsync 失敗——全都會得到「BAD = 0」這個假通過。
> 加上 `TOTAL` 與 `KEPT` 的對照，才能區分「真的乾淨」與「根本沒跑到」。
> （本檢查已用含 `py311_venv`、`.env`、`node_modules` 的樣本目錄實測：
> 不排除時命中 9 筆、排除後命中 0 筆。）

> `--exclude` 清單是**安全關鍵**，不是效能考量。漏掉 `.env` 或 `.webui_secret_key`
> 會把真實金鑰 commit 進去；漏掉 `data/`、`db_backups/` 會塞爆 repo。

### 3.2 上一步印出 ✅ 之後才實跑

```bash
rsync -av --delete "${EX[@]}" "$SNAP"/ ./ | tail -5

git status --porcelain           # ← 這就是快照相對正本的獨有內容
```

### 3.3 判讀規則（只有三種結果）

| `git status --porcelain` 輸出 | 意義 | 處置 |
|---|---|---|
| 空 | 完全被正本涵蓋 | `git checkout main && git branch -D rescue/zip-snapshot`，該副本可封存 |
| 只有 `D ` 開頭 | 是正本的子集 | 同上 |
| 有 `M ` 或 `?? ` | **有獨有變更** | `git add -A && git commit -m "rescue: 快照獨有內容"` → `git push -u origin rescue/zip-snapshot` |

預期會落在第三種，且至少包含：

```
docs/designs/2026-08-29-remove-docker-native-migration.md
docs/designs/2026-09-20-target-architecture-consistency-eval-faithfulness.md
docs/designs/2026-09-20-target-architecture-consistency-eval-faithfulness-assessment.md
docs/reports/2026-09-20-infra-findings-report.md
CLAUDE.md / CODE_REVIEW_STANDARD.md / CODING_STYLE.md
```

**commit 前務必確認沒有金鑰混進去：**

```bash
git status --porcelain | grep -iE '\.env|secret|\.pem|id_rsa|webui_secret' \
  && echo "⚠ 有敏感檔案，先處理再 commit" || echo "✅ 無敏感檔案"
```

---

## STEP 4：處理另外兩份副本

### 4.1 本機 clone —— 不用撈，可直接刪

已有證據證明它**沒有任何獨有內容**：

| 證據 | 結果 |
|---|---|
| `git status --porcelain \| wc -l` | **0**（無未提交變更） |
| `dadaa47`、`979745c` 是否在存檔 repo 歷史中 | **兩者皆在** |

兩者合起來 = 這份副本 100% 可由 `git clone` 重建，**沒有任何 byte 是別處找不到的**。
所以不需要 rescue 分支，也不需要搬到 F 槽。直接改名封存：

```bash
mv /mnt/d/art_icnclab /mnt/d/_ARCHIVED_2026-09-20_art_icnclab
```

（先改名而非刪除，留退路。確認一週無異狀再刪。）

### 4.2 執行期目錄 —— 現在不要動

`C:\Users\user\Desktop\藝術史資料庫` 與 `D:\藝術史資料庫` 可能是服務正在使用的工作目錄。
**必須等 Phase 3 確認服務歸屬之後再處理。** 現在只做唯讀比對，不搬不刪：

```bash
diff -rq "/mnt/c/Users/user/Desktop/藝術史資料庫" "/mnt/d/藝術史資料庫" 2>&1 | head -20
```

若之後確認要撈其獨有內容，比照 STEP 3，但排除清單要更嚴（`--exclude='.env*'`、
`--exclude='logs/'`），因為執行期目錄裡的資料與金鑰絕不該進版控。

---

## STEP 5：處置表與封存

每份副本一列，**每列都要有分支名與 commit hash 作為憑據**：

| 副本 | 分支 | 獨有檔案數 | commit | 處置 |
|---|---|---|---|---|
| `F:\art_icnclab-main` | `rescue/zip-snapshot` | ? | ? | 待填 |
| 本機 clone | 不需要（見 4.1） | **0** | — | 改名封存 |
| 執行期目錄 | 待 Phase 3 | ? | — | 暫不處理 |

完成後在正本 README 補上：

```markdown
## 資料還原
Neo4j / ChromaDB / OpenWebUI 的備份資料在 icnclabstust-hub/art_icnclab 的
db_backups/（Git LFS），本 repo 不收錄。

## 歷史考古
本 repo 的 main 源自 metaversestust-pms/art_icnclab（全新歷史）。
2026-08-18 之前的完整 commit 歷史在 icnclabstust-hub/art_icnclab。
```

---

## 附錄A：若要把副本集中到 F 槽

**先確認：多數副本其實不需要搬。**

| 副本 | 需要搬嗎 | 依據 |
|---|---|---|
| 快照 | 已搬完 | — |
| 本機 clone | **不需要，直接刪** | 見 4.1，無獨有內容 |
| 執行期目錄 | **現在不要搬** | 服務可能正在使用，搬了立刻斷線 |

若仍要集中（例如 D 槽空間不足）：

### 三個地雷

**1. 跨磁碟不是改名，是整包複製再刪。** 同磁碟 `mv` 是瞬間的（只改目錄項）；
D: → F: 會實際搬每一個 byte。執行期目錄若含 `data/`、`db_backups/`，可能是數十 GB。

**2. venv 搬完就壞，只能重建。** `py311_venv\pyvenv.cfg` 與 `Scripts\*.exe` 內嵌**絕對路徑**，
路徑一變立刻失效。`node_modules` 若有原生編譯模組（`sharp`、`better-sqlite3`）同理。
搬移時排除，到新位置重建：

```powershell
python -m venv F:\art_icnclab-main\py311_venv
F:\art_icnclab-main\py311_venv\Scripts\pip install -r F:\art_icnclab-main\requirements.txt
```

**3. WSL 內跨 `/mnt/` 搬 Windows 檔案很慢且會弄壞屬性。** 用 Windows 原生工具。

### 程序（PowerShell）

```powershell
# 乾跑，先看要搬什麼、多大
robocopy "D:\art_icnclab" "F:\art_icnclab" /E /L /XD node_modules py311_venv .venv __pycache__ /NFL /NDL

# 複製。刻意不用 /MOVE —— 先複製、驗證、再手動刪，出錯才有退路
robocopy "D:\art_icnclab" "F:\art_icnclab" /E /COPY:DAT /XJ /R:1 /W:1 `
  /XD node_modules py311_venv .venv __pycache__ `
  /LOG:F:\move.log /TEE

# 驗證後才動來源
git -C F:\art_icnclab fsck
git -C F:\art_icnclab log -1 --format='%h %s'    # 應為 979745c
Rename-Item "D:\art_icnclab" "_ARCHIVED_2026-09-20_art_icnclab"
```

| 參數 | 用意 |
|---|---|
| `/E` | 含子目錄與空目錄 |
| `/COPY:DAT` | 只複製資料、屬性、時間戳，不複製 ACL，跨磁碟較不會出權限問題 |
| `/XJ` | 排除 junction，避免符號連結造成無限遞迴 |
| `/R:1 /W:1` | 失敗只重試 1 次等 1 秒。**預設是重試一百萬次，會整個卡死** |

搬完務必回到 **STEP 1** 修復斷掉的引用。

### 搬執行期目錄前必須停服務

```bash
sudo systemctl stop neo4j elasticsearch ollama
# 搬移、修正路徑、daemon-reload 之後
sudo systemctl start neo4j elasticsearch ollama
systemctl is-active neo4j elasticsearch ollama
```

服務執行中搬其工作目錄，輕則崩潰，重則資料檔寫到一半被截斷而毀損。

---

## 附錄B：本手冊未涵蓋

1. **`db_backups/`（Git LFS）是否納入正本** —— 建議不納入，理由見 1.3。
2. **公開 repo 的歷史金鑰稽核** —— 已驗證存檔 repo 的 HEAD 檔案樹未追蹤任何 `.env`
   （`.gitignore` 第 7–14、114 行已排除），但**歷史提交未查**。指令見主計畫 §1.4。
3. **Phase 2／Phase 3** —— 設定真相源與服務歸屬，見主計畫。
