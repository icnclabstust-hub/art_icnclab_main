#!/usr/bin/env python3
# spec-update.py — 讓程式／代理安全地更新規格狀態，且不製造第二份真相源
#
# 為什麼不直接改 spec.json：那會讓衍生物與 Markdown 分歧，正是 spec-export.py
# 極力避免的事（理由見規格書「機器可讀版本」一節）。所以更新一律寫回 Markdown：
#
#     系統 ──spec-update.py──▶ Markdown（唯一真相源） ──spec-export.py──▶ spec.json
#
# 刻意只支援兩種改動，因為它們是實作過程中會反覆發生、且能以確定性規則完成的：
#   1. 需求狀態轉換（❌ → ⚠️ → ✅）
#   2. 流程／階段步驟的結案與復開
# 其餘改動（改寫規格文字、新增需求、調整相依）牽涉語意判斷，一律由人或
# LLM 直接編輯 Markdown。自動化那些只會製造無聲的語意損壞。
#
# 安全性：
#   - 只置換目標儲存格，不重寫整行
#   - 寫入後立即跑 spec-export.py --check；驗證不過就**還原**（原子性）
#   - 未知編號、未知狀態一律拒絕
#   - 同值重設為 no-op（冪等）
#   - 每次成功更新追加一筆到 docs/spec-changelog.md（僅追加，不改寫）
#
# 用法：
#   python3 scripts/spec-update.py --set GRD-09=done --by agent --why "已實作並通過測試"
#   python3 scripts/spec-update.py --close P0-6 --why "執行期目錄已改為正本 checkout"
#   python3 scripts/spec-update.py --reopen P0-6 --why "回退"
#   python3 scripts/spec-update.py --from updates.json          # 批次
#   python3 scripts/spec-update.py --set X=done --dry-run       # 只看差異
#   python3 scripts/spec-update.py --set X=done --json          # 機器可讀結果
#
# 批次檔格式：[{"set": "GRD-09", "status": "done", "why": "..."},
#              {"close": "P0-6", "why": "..."}]
#
# 結束碼：0 成功（含 no-op）；1 更新失敗或驗證不過（已還原）；2 參數或檔案錯誤。

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRS = os.path.join(ROOT, "docs", "2026-09-22-system-spec-srs.md")
FLOWS = os.path.join(ROOT, "docs", "2026-09-22-system-flow-steps.md")
CHANGELOG = os.path.join(ROOT, "docs", "spec-changelog.md")
EXPORTER = os.path.join(ROOT, "scripts", "spec-export.py")

GLYPH = {"done": "✅", "partial": "⚠️", "todo": "❌", "decided": "✔", "deferred": "⏸"}
STATUS_GLYPHS = "✅✔⚠❌⏸☐️"
RE_REQ = re.compile(r"^(SYS|DAT|RET|GRD|GEN|EVL|BIZ|NFR|OPS)-\d+[a-z]?(?:-T)?$")
RE_STEP = re.compile(r"^(?:P0|[A-GM])-\d+[a-z]?$|^\d-\d+[a-z]?$")


def split_cells(line):
    """與 spec-export.py 同規則：只在未跳脫的管線符上切欄。"""
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return re.split(r"(?<!\\)\|", body)


def join_cells(cells):
    return "| " + " | ".join(c.strip() for c in cells) + " |"


def bare_id(cell_text):
    """去掉狀態符號、強調與刪除線，取出純編號。"""
    t = cell_text.strip()
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"~~(.+?)~~", r"\1", t)
    return t.strip(STATUS_GLYPHS + " ").strip()


def locate(path, target):
    """回傳 (lines, 行號, 儲存格, 表頭)。找不到回 None。

    同時往上找最近的表頭列，才能知道「狀態」在第幾欄——本專案表格欄數 2～5 浮動。
    """
    lines = open(path, encoding="utf-8").read().split("\n")
    header = None
    for i, ln in enumerate(lines):
        if (ln.startswith("|") and i + 1 < len(lines) and lines[i + 1].startswith("|")
                and set(lines[i + 1].replace("|", "").strip()) <= set("-: ")):
            header = [c.strip() for c in split_cells(ln)]
            continue
        if ln.startswith("|") and header:
            cells = split_cells(ln)
            if cells and bare_id(cells[0]) == target:
                return lines, i, cells, header
    return None


def do_set(target, status, dry):
    if status not in GLYPH:
        return False, f"未知狀態 {status!r}，可用：{'、'.join(GLYPH)}"
    if not RE_REQ.match(target):
        return False, f"{target} 不是需求編號（--set 只用於需求；步驟請用 --close／--reopen）"
    found = locate(SRS, target)
    if not found:
        return False, f"規格書中找不到需求 {target}"
    lines, idx, cells, header = found
    if "狀態" not in header:
        return False, f"{target} 所在的表沒有狀態欄，無法以本工具更新"
    col = header.index("狀態")
    if col >= len(cells):
        return False, f"{target} 該列欄數少於表頭——請先修正表格（spec-export.py 的 C8 會指出）"
    before = cells[col].strip()
    if before.startswith(GLYPH[status]):
        return None, f"{target} 已是 {status}，未變更"
    cells[col] = GLYPH[status]
    lines[idx] = join_cells(cells)
    if not dry:
        open(SRS, "w", encoding="utf-8").write("\n".join(lines))
    return True, f"{target}：狀態 {before!r} → {GLYPH[status]}（{status}）"


def do_close(target, why, dry, reopen=False):
    if not RE_STEP.match(target):
        return False, f"{target} 不是流程／階段步驟編號"
    found = locate(FLOWS, target)
    if not found:
        return False, f"流程文件中找不到步驟 {target}"
    lines, idx, cells, header = found
    already = cells[0].strip().startswith("~~") or "~~" in cells[0]
    if reopen:
        if not already:
            return None, f"{target} 並未結案，未變更"
        cells[0] = f" {target} "
        cells[-1] = re.sub(r"✅ \*\*已結案\*\*（[\d-]+）：.*?。", "", cells[-1]).strip()
        msg = f"{target}：已復開"
    else:
        if already:
            return None, f"{target} 已結案，未變更"
        cells[0] = f" ~~{target}~~ "
        note = f"✅ **已結案**（{date.today().isoformat()}）：{why or '未註明原因'}。"
        cells[-1] = f" {note} {cells[-1].strip()} "
        msg = f"{target}：已結案"
    lines[idx] = join_cells(cells)
    if not dry:
        open(FLOWS, "w", encoding="utf-8").write("\n".join(lines))
    return True, msg


def run_export(check=True):
    """跑匯出器。check=True 時只驗證，用於確認改動沒有破壞一致性。"""
    cmd = [sys.executable, EXPORTER] + (["--check", "--quiet"] if check else ["--quiet"])
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    ap = argparse.ArgumentParser(description="安全地更新系統規格狀態（寫回 Markdown）")
    ap.add_argument("--set", action="append", default=[], metavar="ID=STATUS",
                    help=f"設定需求狀態，STATUS ∈ {{{'|'.join(GLYPH)}}}")
    ap.add_argument("--close", action="append", default=[], metavar="STEP", help="將步驟標記為結案")
    ap.add_argument("--reopen", action="append", default=[], metavar="STEP", help="復開已結案的步驟")
    ap.add_argument("--from", dest="batch", metavar="FILE", help="批次更新的 JSON 檔")
    ap.add_argument("--why", default="", help="變更原因，寫入變更日誌")
    ap.add_argument("--by", default="unknown", help="執行者識別（人名或代理名稱）")
    ap.add_argument("--dry-run", action="store_true", help="只顯示會改什麼，不寫檔")
    ap.add_argument("--json", action="store_true", help="以 JSON 輸出結果，供程式解析")
    a = ap.parse_args()

    ops = []
    for spec in a.set:
        if "=" not in spec:
            print(f"❌ --set 需為 ID=STATUS 形式，收到 {spec!r}", file=sys.stderr)
            return 2
        t, st = spec.split("=", 1)
        ops.append(("set", t.strip(), st.strip(), a.why))
    ops += [("close", t, None, a.why) for t in a.close]
    ops += [("reopen", t, None, a.why) for t in a.reopen]

    if a.batch:
        try:
            for item in json.load(open(a.batch, encoding="utf-8")):
                why = item.get("why", a.why)
                if "set" in item:
                    ops.append(("set", item["set"], item.get("status"), why))
                elif "close" in item:
                    ops.append(("close", item["close"], None, why))
                elif "reopen" in item:
                    ops.append(("reopen", item["reopen"], None, why))
        except (OSError, json.JSONDecodeError, TypeError, AttributeError) as e:
            print(f"❌ 無法讀取批次檔：{e}", file=sys.stderr)
            return 2

    if not ops:
        ap.print_help()
        return 2

    # 先存原狀，任何一步失敗就整批還原——避免留下改了一半的規格
    backup = {p: open(p, encoding="utf-8").read() for p in (SRS, FLOWS)}
    results, changed, failed = [], 0, 0

    for kind, target, arg, why in ops:
        if kind == "set":
            ok, msg = do_set(target, arg, a.dry_run)
        else:
            ok, msg = do_close(target, why, a.dry_run, reopen=(kind == "reopen"))
        results.append({"op": kind, "target": target, "status": arg,
                        "result": "changed" if ok else ("noop" if ok is None else "failed"),
                        "message": msg})
        if ok:
            changed += 1
        elif ok is False:
            failed += 1

    def restore():
        for p, c in backup.items():
            open(p, "w", encoding="utf-8").write(c)

    validation = None
    if failed:
        restore()
        validation = "未執行（有操作失敗，已全數還原）"
    elif changed and not a.dry_run:
        rc, out = run_export(check=True)
        # 匯出器用 ❌ 標錯誤、⚠ 標警告。只有錯誤才該還原——
        # 警告（例如 C5 覆蓋率不足）是提醒，不是「這次改動壞了規格」。
        # C7「spec.json 已過期」更是必然出現：Markdown 才剛被改，本來就該重產。
        hard_errors = [ln for ln in out.split("\n")
                       if ln.lstrip().startswith("❌") and "[C7]" not in ln]
        if hard_errors:
            restore()
            validation = "驗證失敗，已還原：" + " / ".join(e.strip() for e in hard_errors)
            failed += 1
        else:
            rc2, out2 = run_export(check=False)   # 驗證過關，重新產生 spec.json
            validation = "通過，spec.json 已更新" if rc2 == 0 else f"匯出失敗：{out2}"
            if rc2 != 0:
                restore()
                failed += 1

    if changed and not a.dry_run and not failed:
        head = "" if os.path.exists(CHANGELOG) else (
            "# 規格變更日誌\n\n"
            "> 由 `scripts/spec-update.py` 自動追加，**僅追加不改寫**。\n"
            "> 規格本文的唯一真相源仍是兩份 Markdown；本檔只記錄「誰、何時、為何」改了狀態。\n\n")
        with open(CHANGELOG, "a", encoding="utf-8") as fh:
            if head:
                fh.write(head)
            fh.write(f"## {date.today().isoformat()} — {a.by}\n\n")
            for r in results:
                if r["result"] == "changed":
                    fh.write(f"- {r['message']}" + (f"　理由：{a.why}" if a.why else "") + "\n")
            fh.write("\n")

    out = {"changed": changed, "noop": sum(1 for r in results if r["result"] == "noop"),
           "failed": failed, "dry_run": a.dry_run, "validation": validation, "results": results}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for r in results:
            icon = {"changed": "✅", "noop": "－", "failed": "❌"}[r["result"]]
            print(f"  {icon} {r['message']}")
        if validation:
            print(f"\n驗證：{validation}")
        if a.dry_run:
            print("（--dry-run，未寫檔）")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
