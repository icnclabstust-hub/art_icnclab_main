#!/usr/bin/env python3
"""把 docs/*-system-spec-srs.md 與 docs/*-system-flow-steps.md 編譯成機器可讀的 docs/spec.json。

單向衍生：Markdown 是唯一真相源，spec.json 是產物，不得手改。見 SRS 附錄 A。

用法：
    python3 scripts/spec-export.py            # 產生／更新 docs/spec.json
    python3 scripts/spec-export.py --check     # 只驗證，不寫檔；不一致則以非零碼結束
    python3 scripts/spec-export.py --next      # 印出可開工／被擋住／已暫緩的項目

本版實作的一致性檢查（刻意只做這 4 項，其餘見 SRS 附錄 A.1 表格的註記，
不假裝已完整覆蓋原設計的 11 項）：
  C1  需求／步驟編號是否重複（同一編號出現在不同地方，通常是複製貼上留下的錯誤）
  C2  有狀態欄的需求列，其狀態符號是否可判讀
  C8  每一列的欄數是否等於表頭欄數（欄數不符會整列錯位，肉眼不易發現）
  C11 「## 目錄」條列是否與文件實際的標題逐條對應
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from spec_lib import (  # noqa: E402
    extract_requirements,
    extract_steps,
    parse_markdown,
    section_lookup,
    sha256_of,
)

DOCS_DIR = Path(__file__).parent.parent / "docs"
SRS_PATH = DOCS_DIR / "2026-09-23-system-spec-srs.md"
FLOW_PATH = DOCS_DIR / "2026-09-23-system-flow-steps.md"
SPEC_JSON_PATH = DOCS_DIR / "spec.json"


def _check_duplicate_ids(requirements, steps) -> list[str]:
    """C1：同一編號若在不同（檔案, 行號）出現，視為重複。"""
    seen: dict[str, tuple[str, int]] = {}
    errors = []
    for item in [*requirements, *steps]:
        key = item.id
        loc = (item.file, item.line_no)
        if key in seen and seen[key] != loc:
            errors.append(f"C1 重複編號 {key}：{seen[key]} 與 {loc}")
        else:
            seen[key] = loc
    return errors


def _check_status_readable(requirements) -> list[str]:
    """C2：需求列的狀態欄必須以已知符號開頭。"""
    errors = []
    for r in requirements:
        if r.status_glyph is None:
            errors.append(f"C2 狀態無法判讀 {r.id}（{r.file}:{r.line_no}）：{r.status_raw!r}")
    return errors


def _check_column_counts(doc, label) -> list[str]:
    """C8：每一列的欄數須等於表頭欄數。"""
    errors = []
    for table in doc.tables:
        expected = len(table.header)
        for row in table.rows:
            if len(row.cells) != expected:
                got = len(row.cells)
                errors.append(
                    f"C8 欄數不符 {label}:{row.line_no}：表頭 {expected} 欄，此列 {got} 欄"
                )
    return errors


def _check_toc(doc, label) -> list[str]:
    """C11：目錄條列（## 目錄）逐條比對是否能在標題清單找到對應（寬鬆子字串比對）。"""
    if not doc.toc_entries:
        return []
    errors = []
    heading_texts = [h for _, h in doc.headings]
    joined = "\n".join(heading_texts)
    for entry in doc.toc_entries:
        # 目錄項目可能只是標題的一部分（如 "1. 系統概觀" 對到 "1. 系統概觀"），
        # 用去除編號後的核心字串做寬鬆比對。
        core = entry.split(" ", 1)[-1] if " " in entry and entry[0].isdigit() else entry
        core = core.lstrip("0123456789. ").strip()
        if core and core not in joined:
            errors.append(f"C11 目錄項目找不到對應標題 {label}：{entry!r}")
    return errors


def build_spec(*, strict: bool) -> tuple[dict, list[str]]:
    srs_doc = parse_markdown(SRS_PATH)
    flow_doc = parse_markdown(FLOW_PATH)

    srs_lookup = section_lookup(srs_doc)
    flow_lookup = section_lookup(flow_doc)

    requirements = [
        *extract_requirements(srs_doc, srs_lookup),
        *extract_requirements(flow_doc, flow_lookup),
    ]
    steps = [
        *extract_steps(srs_doc, srs_lookup),
        *extract_steps(flow_doc, flow_lookup),
    ]

    errors: list[str] = []
    errors += _check_duplicate_ids(requirements, steps)
    errors += _check_status_readable(requirements)
    errors += _check_column_counts(srs_doc, "srs")
    errors += _check_column_counts(flow_doc, "flow")
    errors += _check_toc(srs_doc, "srs")
    errors += _check_toc(flow_doc, "flow")

    # 相依計算：state = closed / deferred / blocked / ready（見 SRS 附錄 A.4）
    step_by_id = {s.id: s for s in steps}
    step_states = {}
    for s in steps:
        if s.closed:
            state = "closed"
        elif s.deferred:
            state = "deferred"
        else:
            blocked_by = [d for d in s.depends_on if d in step_by_id and not step_by_id[d].closed]
            state = "blocked" if blocked_by else "ready"
        step_states[s.id] = state

    next_actions = sorted(s.id for s in steps if s.kind == "task" and step_states[s.id] == "ready")

    spec = {
        "source": {
            "srs": {
                "path": str(SRS_PATH.relative_to(DOCS_DIR.parent)),
                "sha256": sha256_of(SRS_PATH),
            },
            "flow": {
                "path": str(FLOW_PATH.relative_to(DOCS_DIR.parent)),
                "sha256": sha256_of(FLOW_PATH),
            },
        },
        "stats": {
            "requirements": len(requirements),
            "steps": len(steps),
            "requirements_done": sum(1 for r in requirements if r.status_glyph == "✅"),
            "requirements_todo": sum(1 for r in requirements if r.status_glyph == "❌"),
        },
        "next_actions": next_actions,
        "requirements": [
            {
                "id": r.id,
                "title": r.title,
                "status_glyph": r.status_glyph,
                "status_raw": r.status_raw,
                "file": r.file,
                "line": r.line_no,
                "section": r.section,
            }
            for r in sorted(requirements, key=lambda r: r.id)
        ],
        "steps": [
            {
                "id": s.id,
                "action": s.action,
                "kind": s.kind,
                "depends_on": s.depends_on,
                "blocked_by": [d for d in s.depends_on if step_states.get(d) not in ("closed",)],
                "state": step_states[s.id],
                "file": s.file,
                "line": s.line_no,
                "section": s.section,
            }
            for s in sorted(steps, key=lambda s: (s.file, s.line_no))
        ],
        "validation": {
            "checks_implemented": ["C1", "C2", "C8", "C11"],
            "errors": errors,
            "ok": len(errors) == 0,
        },
    }
    return spec, errors


def cmd_next(spec: dict) -> None:
    print(f"可立即開工（{len(spec['next_actions'])}）：")
    for step_id in spec["next_actions"]:
        step = next(s for s in spec["steps"] if s["id"] == step_id)
        print(f"  {step_id}\t{step['action']}")

    blocked = [s for s in spec["steps"] if s["kind"] == "task" and s["state"] == "blocked"]
    print(f"\n被擋住（{len(blocked)}）：")
    for s in blocked:
        print(f"  {s['id']}\t等待 {', '.join(s['blocked_by'])}")

    deferred = [s for s in spec["steps"] if s["kind"] == "task" and s["state"] == "deferred"]
    print(f"\n已暫緩（{len(deferred)}）：")
    for s in deferred:
        print(f"  {s['id']}\t{s['action']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只驗證，不寫檔")
    parser.add_argument("--next", action="store_true", help="印出可開工／被擋住／已暫緩的項目")
    args = parser.parse_args()

    spec, errors = build_spec(strict=args.check)

    if args.next:
        cmd_next(spec)
        return 0

    if errors:
        for e in errors:
            print(f"❌ {e}", file=sys.stderr)
        print(f"\n共 {len(errors)} 個一致性錯誤，未寫檔。", file=sys.stderr)
        return 1

    serialized = json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    if args.check:
        if SPEC_JSON_PATH.exists() and SPEC_JSON_PATH.read_text(encoding="utf-8") == serialized:
            print("✅ spec.json 與 Markdown 一致，無需重產。")
            return 0
        print(
            "❌ spec.json 已過期（Markdown 有變更但未重新匯出）。"
            "請執行：python3 scripts/spec-export.py",
            file=sys.stderr,
        )
        return 1

    SPEC_JSON_PATH.write_text(serialized, encoding="utf-8")
    stats = spec["stats"]
    print(f"✅ 已寫入 {SPEC_JSON_PATH}（{stats['requirements']} 項需求、{stats['steps']} 個步驟）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
