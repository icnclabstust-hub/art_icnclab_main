#!/usr/bin/env python3
# spec-export.py — 把系統規格書與流程步驟轉成機器可讀的 spec.json，並驗證一致性
#
# 為什麼有這支：需要一份給程式／代理讀取的規格，但**不能**因此多出第二份真相源。
# 本 repo 已經為「兩份真相源必然分歧」付過代價（ports.md 的唯一真相源宣告、
# problem-register A4 執行期目錄與正本脫鉤）。所以設計是單向的：
#
#     Markdown（唯一真相源） ──本腳本──▶ spec.json（衍生物，可隨時重建）
#
# spec.json 不得手動編輯。要改規格就改 Markdown，然後重跑本腳本。
#
# 驗證與匯出綁在一起：驗證不過就不寫檔，避免產出內部矛盾的 spec.json。
#
# 用法：
#   python3 scripts/spec-export.py              # 驗證並寫出 docs/spec.json
#   python3 scripts/spec-export.py --check      # 只驗證，不寫檔（CI／提交前用）
#   python3 scripts/spec-export.py --quiet      # 只輸出錯誤
#
# 結束碼：0 通過；1 驗證失敗（發現錯誤）；2 檔案缺失或解析失敗。

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRS = os.path.join(ROOT, "docs", "2026-09-22-system-spec-srs.md")
FLOWS = os.path.join(ROOT, "docs", "2026-09-22-system-flow-steps.md")
OUT = os.path.join(ROOT, "docs", "spec.json")

# 需求編號：GRD-09、GRD-06c、SYS-05-T、BIZ-04b 皆須涵蓋
RE_REQ = re.compile(r"\b(SYS|DAT|RET|GRD|GEN|EVL|BIZ|NFR|OPS)-\d+[a-z]?(?:-T)?\b")
# 流程步驟：A-13b、P0-2、B-9；階段步驟：3-2、4-6、5-1
RE_FLOWSTEP = re.compile(r"^(?:P0|[A-GM])-\d+[a-z]?$")
RE_PHASESTEP = re.compile(r"^\d-\d+[a-z]?$")
RE_RISK = re.compile(r"^R\d+[a-z]?$")
RE_Q = re.compile(r"^Q\d+$")
RE_CONFIG = re.compile(r"`([A-Z][A-Z0-9_]{3,})`")
# 涵蓋範圍寫法：RET-01～13、GRD-06～07、DAT-01～05（全形與半形波浪號都用過）
RE_RANGE = re.compile(r"\b(SYS|DAT|RET|GRD|GEN|EVL|BIZ|NFR|OPS)-(\d+)[～~](\d+)\b")


def expand_refs(text):
    """把文字中的需求編號抽出來，並把「RET-01～13」展開為個別編號。

    §9 流程↔需求對照表與多處說明用範圍寫法表達涵蓋範圍；不展開的話
    覆蓋率檢查（C5）會把這些需求誤判為沒人管，產生大量假警報。
    """
    if not text:
        return set()
    found = {m.group(0) for m in RE_REQ.finditer(text)}
    for cat, lo, hi in RE_RANGE.findall(text):
        width = len(lo)
        for n in range(int(lo), int(hi) + 1):
            found.add(f"{cat}-{str(n).zfill(width)}")
    return found

STATUS_MAP = {
    "✅": "done",          # 已實作且已實跑驗證
    "✔": "decided",        # 已定案（決策類，非實作狀態）
    "⚠️": "partial",       # 部分實作
    "⚠": "partial",
    "❌": "todo",          # 僅有設計，待實作
    "⏸": "deferred",      # 經決定延後，連帶限制須明列
}

errors, warnings = [], []


def err(code, msg):
    errors.append(f"[{code}] {msg}")


def warn(code, msg):
    warnings.append(f"[{code}] {msg}")


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


STATUS_GLYPHS = "✅✔⚠️⚠❌⏸☐"


def split_marker(cell_text):
    """把「⏸ 3-7」拆成（狀態符號, 純編號）。

    表格裡在編號前加狀態符號是很自然的寫法，但會讓編號比對失效——
    曾因此把 BIZ-04b 誤報為「未被任何流程步驟涵蓋」。故在此統一正規化。
    """
    t = strip_md(cell_text)
    marker = ""
    while t and t[0] in STATUS_GLYPHS:
        marker += t[0]
        t = t.lstrip(STATUS_GLYPHS).lstrip()
    return (marker or None), t


def strip_md(text):
    """去掉 Markdown 強調與刪除線，保留可讀文字（行內 code 的反引號保留，因為設定變數靠它辨識）。"""
    t = text.replace("<br>", " ").strip()
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"~~(.+?)~~", r"\1", t)
    return t.strip()


def parse_tables(path):
    """走訪 Markdown，回傳 [(heading_path, header_cells, [row_cells...])]。

    表頭的判定：某行以 | 開頭，且下一行是分隔列（只含 -、:、|、空白）。
    這比用固定欄數穩健——本專案的表格欄數在 2～5 之間浮動。
    """
    lines = open(path, encoding="utf-8").read().split("\n")
    heads, out, i = {}, [], 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            lvl = len(m.group(1))
            heads[lvl] = strip_md(m.group(2))
            for deeper in [k for k in heads if k > lvl]:
                heads.pop(deeper)
        if (
            ln.startswith("|")
            and i + 1 < len(lines)
            and lines[i + 1].startswith("|")
            and set(lines[i + 1].replace("|", "").strip()) <= set("-: ")
        ):
            cells = lambda s: [c.strip() for c in s.strip().strip("|").split("|")]
            header = cells(ln)
            rows, j = [], i + 2
            while j < len(lines) and lines[j].startswith("|"):
                rows.append(cells(lines[j]))
                j += 1
            out.append(("/".join(heads[k] for k in sorted(heads)), header, rows))
            i = j
            continue
        i += 1
    return out


def norm_status(raw):
    """狀態欄可能混寫，例如「✅ 已驗證還原／⚠️ 分片規格待實作」。
    取最保守的一個：只要出現未完成標記，整體就不算 done。"""
    if not raw:
        return None, None
    found = [v for k, v in STATUS_MAP.items() if k in raw]
    if not found:
        return None, raw
    for level in ("deferred", "todo", "partial", "decided", "done"):
        if level in found:
            return level, raw
    return found[0], raw


def cell(row, header, *names):
    for n in names:
        if n in header:
            idx = header.index(n)
            if idx < len(row):
                return strip_md(row[idx])
    return None


# ------------------------------------------------------------------ 解析 SRS
def parse_srs():
    reqs, decisions, risks, questions, ports, roles = [], [], [], [], [], []
    for section, header, rows in parse_tables(SRS):
        h0 = header[0]

        # 需求表：表頭第一欄形如 「GRD-ID」
        if re.match(r"^(SYS|DAT|RET|GRD|GEN|EVL|BIZ|NFR|OPS)-ID$", h0):
            for r in rows:
                _, rid = split_marker(r[0])
                if not RE_REQ.fullmatch(rid):
                    continue
                has_status_col = "狀態" in header
                status, raw = norm_status(cell(r, header, "狀態"))
                spec = cell(r, header, "規格", "關鍵規格", "需求", "說明", "驗收標準")
                # NFR/SYS 目標表把「需求」放第 2 欄、「驗收標準」放第 3 欄
                title = cell(r, header, "需求", "項目", "庫", "類別")
                if title == spec:
                    title = None
                acc = cell(r, header, "驗收標準", "驗收方式", "阻擋什麼")
                if acc == spec:
                    acc = None
                body = " ".join(x for x in (title, spec, acc) if x)
                reqs.append({
                    "id": rid,
                    "category": rid.split("-")[0],
                    "section": section,
                    "title": title,
                    "spec": spec,
                    "acceptance": acc,
                    "current": cell(r, header, "現況"),
                    "status": status,
                    "status_raw": raw,
                    "has_status_col": has_status_col,
                    "closed": "~~" in r[0],
                    "refs": sorted({x.group(0) for x in RE_REQ.finditer(body)} - {rid}),
                    "config_keys": sorted(set(RE_CONFIG.findall(body))),
                })

        # 追溯矩陣
        elif h0 == "決策":
            for r in rows:
                d = strip_md(r[0])
                if d in ("—", ""):
                    d = None
                decisions.append({
                    "decision": d,
                    "value": cell(r, header, "決議值"),
                    "requirements": sorted({x.group(0) for x in RE_REQ.finditer(r[2] if len(r) > 2 else "")}),
                    "acceptance": cell(r, header, "驗收方式"),
                })

        # 風險登記 / 待澄清
        elif h0 == "#":
            for r in rows:
                ident = strip_md(r[0])
                closed = "~~" in r[0]
                if RE_RISK.fullmatch(ident):
                    risks.append({
                        "id": ident, "closed": closed,
                        "risk": cell(r, header, "風險", "事項"),
                        "cause": cell(r, header, "成因"),
                        "treatment": cell(r, header, "建議處置", "目前處理"),
                        "refs": sorted(expand_refs(" ".join(r))),
                    })
                elif RE_Q.fullmatch(ident):
                    questions.append({
                        "id": ident, "closed": closed,
                        "question": cell(r, header, "事項", "風險"),
                        "impact": cell(r, header, "影響範圍"),
                        "handling": cell(r, header, "目前處理", "建議處置"),
                    })

        elif h0 == "埠":
            for r in rows:
                ports.append({
                    "port": strip_md(r[0]),
                    "owner": cell(r, header, "擁有者"),
                    "env": cell(r, header, "設定變數"),
                    "status": cell(r, header, "狀態"),
                    "retired": "~~" in r[0],
                })

        elif h0 == "角色":
            for r in rows:
                roles.append({
                    "role": strip_md(r[0]), "code": cell(r, header, "代號"),
                    "duty": cell(r, header, "權責"),
                    "requirements": sorted({x.group(0) for x in RE_REQ.finditer(" ".join(r))}),
                })
    return reqs, decisions, risks, questions, ports, roles


# ------------------------------------------------------------------ 解析流程
def parse_diagram_refs(path):
    """流程 B 以 ASCII 圖表達，不是表格；§9 對照表則用範圍寫法。
    兩者都是真實的涵蓋來源，覆蓋率檢查必須納入，否則會誤報整個防護層無人涵蓋。"""
    text = open(path, encoding="utf-8").read()
    refs = set()
    for block in re.findall(r"```.*?```", text, re.S):
        refs |= expand_refs(block)
    for section, header, rows in parse_tables(path):
        if header[0] in ("流程", "事項", "徵狀", "告警類型"):
            for r in rows:
                refs |= expand_refs(" ".join(r))
    return refs


def parse_flows():
    flows, phases = [], []
    for section, header, rows in parse_tables(FLOWS):
        if header[0] != "步驟":
            continue
        steps = []
        for r in rows:
            marker, sid = split_marker(r[0])
            if not (RE_FLOWSTEP.fullmatch(sid) or RE_PHASESTEP.fullmatch(sid)):
                continue
            step_status, _ = norm_status(marker) if marker else (None, None)
            body = " ".join(r)
            steps.append({
                "id": sid,
                "action": cell(r, header, "動作"),
                "owner": cell(r, header, "執行者"),
                "prereq": cell(r, header, "前置"),
                "done_when": cell(r, header, "完成條件", "產出"),
                "on_failure": cell(r, header, "失敗處理", "判斷與處理", "注意", "風險控制"),
                "closed": "~~" in r[0],
                "status": step_status,
                "refs": sorted(expand_refs(body)),
            })
        if not steps:
            continue
        bucket = phases if RE_PHASESTEP.fullmatch(steps[0]["id"]) or steps[0]["id"].startswith("P0") else flows
        bucket.append({"section": section, "steps": steps})
    return flows, phases


# ------------------------------------------------------------------ 驗證
def validate(reqs, decisions, risks, flows, phases):
    ids = [r["id"] for r in reqs]
    known = set(ids)

    # C1 編號唯一
    for i in sorted({x for x in ids if ids.count(x) > 1}):
        err("C1", f"需求編號重複：{i}")

    # C2 狀態標記合法
    for r in reqs:
        if r["has_status_col"] and r["status"] is None:
            warn("C2", f"{r['id']} 有狀態欄但無法判讀（原值：{r['status_raw']!r}）")

    # C3 懸空引用（需求之間、流程→需求、風險→需求、追溯矩陣→需求）
    def check_refs(refs, where):
        for x in refs:
            if x not in known:
                err("C3", f"{where} 引用了不存在的需求 {x}")

    for r in reqs:
        check_refs(r["refs"], r["id"])
    for grp in flows + phases:
        for s in grp["steps"]:
            check_refs(s["refs"], f"流程步驟 {s['id']}")
    for rk in risks:
        check_refs(rk["refs"], f"風險 {rk['id']}")
    for d in decisions:
        check_refs(d["requirements"], f"追溯矩陣決策 {d['decision']}")

    # C4 已結案的風險不應再被當作有效風險引用
    closed_risks = {r["id"] for r in risks if r["closed"]}
    blob = open(SRS, encoding="utf-8").read() + open(FLOWS, encoding="utf-8").read()
    for rid in closed_risks:
        live = re.findall(r"(?<!~)(?<!~~)\b" + rid + r"\b(?!~)", blob)
        for m in re.finditer(r"[^\n]*\b" + rid + r"\b[^\n]*", blob):
            line = m.group(0)
            if "~~" in line or "已裁定" in line or "已解除" in line or "結案" in line:
                continue
            warn("C4", f"已結案風險 {rid} 仍被當作未決引用：{line.strip()[:70]}")

    # C5 覆蓋率：待實作的需求是否被任一流程步驟涵蓋
    covered = {x for grp in flows + phases for s in grp["steps"] for x in s["refs"]}
    covered |= parse_diagram_refs(FLOWS)   # 流程 B 的 ASCII 圖與 §9 對照表
    for r in reqs:
        if r["status"] in ("todo", "partial") and not r["closed"] and r["id"] not in covered:
            warn("C5", f"{r['id']}（{r['status']}）未被任何流程步驟涵蓋，實作時可能被遺漏")

    # C6 每條需求都該說得出怎麼驗收（規格或驗收欄至少有一個）
    for r in reqs:
        if not r["spec"] and not r["acceptance"]:
            err("C6", f"{r['id']} 既無規格也無驗收標準")

    return errors, warnings


def main():
    quiet = "--quiet" in sys.argv
    check_only = "--check" in sys.argv

    for p in (SRS, FLOWS):
        if not os.path.exists(p):
            print(f"❌ 找不到來源文件：{p}", file=sys.stderr)
            return 2

    reqs, decisions, risks, questions, ports, roles = parse_srs()
    flows, phases = parse_flows()
    if not reqs:
        print("❌ 未解析到任何需求——來源文件的表格格式可能已變動", file=sys.stderr)
        return 2
    validate(reqs, decisions, risks, flows, phases)

    stats = {"total": len(reqs)}
    for s in ("done", "partial", "todo", "decided", "deferred"):
        stats[s] = sum(1 for r in reqs if r["status"] == s)
    stats["by_category"] = {c: sum(1 for r in reqs if r["category"] == c)
                            for c in sorted({r["category"] for r in reqs})}

    doc = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "scripts/spec-export.py",
        "DO_NOT_EDIT": "本檔為自動產生的衍生物。唯一真相源是 source 所列的 Markdown；"
                       "要改規格請改 Markdown 後重跑 scripts/spec-export.py。手改本檔會在下次產生時被覆蓋。",
        "source": {
            "srs": {"path": os.path.relpath(SRS, ROOT), "sha256": sha256(SRS)},
            "flows": {"path": os.path.relpath(FLOWS, ROOT), "sha256": sha256(FLOWS)},
        },
        "status_legend": {
            "done": "已實作且已實跑驗證", "partial": "部分實作",
            "todo": "僅有設計，待實作", "decided": "已定案（決策類，非實作狀態）",
            "deferred": "經決定延後，連帶限制見該條規格",
        },
        "stats": stats,
        "roles": roles,
        "ports": ports,
        "requirements": reqs,
        "decisions": decisions,
        "risks": risks,
        "open_questions": questions,
        "flows": flows,
        "phases": phases,
        "validation": {"errors": errors, "warnings": warnings},
    }

    if not quiet:
        print(f"需求 {stats['total']} 條："
              f"done {stats['done']} / partial {stats['partial']} / todo {stats['todo']} / "
              f"decided {stats['decided']} / deferred {stats['deferred']}")
        print(f"決策 {len(decisions)}、風險 {len(risks)}、待澄清 {len(questions)}、"
              f"流程 {len(flows)} 組、階段 {len(phases)} 組")
    for w in warnings:
        print(f"⚠  {w}", file=sys.stderr)
    for e in errors:
        print(f"❌ {e}", file=sys.stderr)

    if errors:
        print(f"\n驗證未通過（{len(errors)} 項錯誤），未寫出 spec.json", file=sys.stderr)
        return 1
    if check_only:
        # C7：已提交的 spec.json 是否仍對應目前的 Markdown。
        # 沒有這道檢查，有人改了規格卻忘了重跑，衍生物就會悄悄過期——
        # 那就等於又多了一份與真相源不符的資料，正是本腳本要防的事。
        if os.path.exists(OUT):
            try:
                old = json.load(open(OUT, encoding="utf-8"))
                stale = [k for k in ("srs", "flows")
                         if old.get("source", {}).get(k, {}).get("sha256") != doc["source"][k]["sha256"]]
            except (json.JSONDecodeError, OSError) as e:
                print(f"❌ [C7] 無法讀取現有 {os.path.relpath(OUT, ROOT)}：{e}", file=sys.stderr)
                return 1
            if stale:
                print(f"❌ [C7] {os.path.relpath(OUT, ROOT)} 已過期（{'、'.join(stale)} 已變動）。"
                      f"請重跑 python3 scripts/spec-export.py", file=sys.stderr)
                return 1
        else:
            print(f"❌ [C7] 找不到 {os.path.relpath(OUT, ROOT)}，請先執行不帶 --check 的匯出", file=sys.stderr)
            return 1
        if not quiet:
            print("✅ 驗證通過，且 spec.json 與來源一致（--check，未寫檔）")
        return 0

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    if not quiet:
        print(f"✅ 已寫出 {os.path.relpath(OUT, ROOT)}"
              f"（{os.path.getsize(OUT) // 1024} KB，警告 {len(warnings)} 項）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
