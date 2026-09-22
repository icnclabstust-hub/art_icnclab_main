#!/usr/bin/env python3
"""更新 docs/*-system-spec-srs.md／*-system-flow-steps.md 的需求狀態或步驟結案狀態。

一律寫回 Markdown（唯一真相源），絕不寫進 docs/spec.json——那是衍生物，見 SRS 附錄 A。
寫入後立即以 spec-export.py 的檢查邏輯驗證，若產生新的錯誤，整批還原。

用法：
    python3 scripts/spec-update.py --set GRD-09=done
    python3 scripts/spec-update.py --close P0-6 --why "已查證非缺陷"
    python3 scripts/spec-update.py --reopen P0-6
    python3 scripts/spec-update.py --set GRD-09=done --dry-run
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from spec_lib import STATUS_MAP_FOR_UPDATE, _extract_id  # noqa: E402, SLF001 -- 同一套件內部重用

DOCS_DIR = Path(__file__).parent.parent / "docs"
SRS_PATH = DOCS_DIR / "2026-09-23-system-spec-srs.md"
FLOW_PATH = DOCS_DIR / "2026-09-23-system-flow-steps.md"
CHANGELOG_PATH = DOCS_DIR / "spec-changelog.md"
CANDIDATE_FILES = (SRS_PATH, FLOW_PATH)


class UpdateError(Exception):
    pass


def _split_cells(line: str) -> list[str]:
    from spec_lib import _split_row  # noqa: PLC0415 -- 避免循環匯入疑慮，僅此處需要

    return _split_row(line)


def _join_cells(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def do_set(req_id: str, status_key: str, *, dry_run: bool) -> str:
    if status_key not in STATUS_MAP_FOR_UPDATE:
        raise UpdateError(f"未知狀態 {status_key!r}；可用值：{', '.join(STATUS_MAP_FOR_UPDATE)}")
    glyph = STATUS_MAP_FOR_UPDATE[status_key]

    for path in CANDIDATE_FILES:
        text = path.read_text(encoding="utf-8")
        lines = text.split("\n")
        for idx, line in enumerate(lines):
            if not line.strip().startswith("|"):
                continue
            cells = _split_cells(line)
            if len(cells) < 2:
                continue
            row_id = _extract_id(cells[0])
            if row_id != req_id:
                continue
            # 只對「有狀態欄」的需求列生效（最後一欄），這是 spec_lib.extract_requirements
            # 判斷需求列的同一條規則；避免誤改到步驟表的「完成條件」欄。
            cells[-1] = glyph
            new_line = _join_cells(cells)
            if dry_run:
                return f"[dry-run] {path.name}:{idx + 1}\n- {line}\n+ {new_line}"
            lines[idx] = new_line
            path.write_text("\n".join(lines), encoding="utf-8")
            return f"已更新 {path.name}:{idx + 1} → {req_id} = {glyph}"
    raise UpdateError(f"找不到需求編號 {req_id}（只在有「狀態」欄的表格中查找）")


def do_close(step_id: str, why: str, *, dry_run: bool) -> str:
    for path in CANDIDATE_FILES:
        text = path.read_text(encoding="utf-8")
        lines = text.split("\n")
        for idx, line in enumerate(lines):
            if not line.strip().startswith("|"):
                continue
            cells = _split_cells(line)
            if not cells:
                continue
            first_clean = cells[0].replace("~~", "").strip()
            token = (first_clean.split() or [""])[0]
            if token != step_id:
                continue
            if "~~" in cells[0]:
                raise UpdateError(f"{step_id} 已經是結案狀態，不重複結案")
            cells[0] = f"~~{first_clean}~~"
            note = f" ✅ **已結案**（{_today()}）：{why}"
            cells[-1] = cells[-1].rstrip() + note
            new_line = _join_cells(cells)
            if dry_run:
                return f"[dry-run] {path.name}:{idx + 1}\n- {line}\n+ {new_line}"
            lines[idx] = new_line
            path.write_text("\n".join(lines), encoding="utf-8")
            return f"已結案 {path.name}:{idx + 1} → {step_id}"
    raise UpdateError(f"找不到步驟編號 {step_id}")


def do_reopen(step_id: str, *, dry_run: bool) -> str:
    import re  # noqa: PLC0415

    for path in CANDIDATE_FILES:
        text = path.read_text(encoding="utf-8")
        lines = text.split("\n")
        for idx, line in enumerate(lines):
            if not line.strip().startswith("|") or f"~~{step_id}~~" not in line:
                continue
            cells = _split_cells(line)
            cells[0] = cells[0].replace(f"~~{step_id}~~", step_id)
            cells[-1] = re.sub(r"\s*✅ \*\*已結案\*\*（[^）]*）：[^|]*$", "", cells[-1]).rstrip()
            new_line = _join_cells(cells)
            if dry_run:
                return f"[dry-run] {path.name}:{idx + 1}\n- {line}\n+ {new_line}"
            lines[idx] = new_line
            path.write_text("\n".join(lines), encoding="utf-8")
            return f"已復開 {path.name}:{idx + 1} → {step_id}"
    raise UpdateError(f"找不到已結案的步驟 {step_id}（需含 ~~{step_id}~~）")


def _today() -> str:
    return datetime.now(tz=UTC).astimezone().strftime("%Y-%m-%d")


def _backup() -> dict[Path, str]:
    return {p: p.read_text(encoding="utf-8") for p in CANDIDATE_FILES}


def _restore(snapshot: dict[Path, str]) -> None:
    for path, text in snapshot.items():
        path.write_text(text, encoding="utf-8")


def _validate_after_write() -> list[str]:
    """重新載入 spec-export 模組（檔名含連字號，`import` 語法不可用）並重跑其一致性檢查。"""
    import importlib.util  # noqa: PLC0415

    export_mod_path = Path(__file__).parent / "spec-export.py"
    spec = importlib.util.spec_from_file_location("spec_export_reload", export_mod_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _spec, errors = module.build_spec(strict=True)
    return errors


def _append_changelog(action: str, detail: str) -> None:
    line = f"- {_today()}　{action}：{detail}\n"
    existing = (
        CHANGELOG_PATH.read_text(encoding="utf-8")
        if CHANGELOG_PATH.exists()
        else (
            "# 規格變更紀錄\n\n> 僅追加，由 scripts/spec-update.py 自動寫入；不手動編輯既有列。\n\n"
        )
    )
    CHANGELOG_PATH.write_text(existing + line, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--set", metavar="ID=STATUS")
    group.add_argument("--close", metavar="ID")
    group.add_argument("--reopen", metavar="ID")
    parser.add_argument("--why", default="", help="--close 時的結案理由")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        try:
            if args.set:
                req_id, _, status_key = args.set.partition("=")
                print(do_set(req_id, status_key, dry_run=True))
            elif args.close:
                if not args.why:
                    raise UpdateError("--close 需要 --why 說明結案理由")
                print(do_close(args.close, args.why, dry_run=True))
            else:
                print(do_reopen(args.reopen, dry_run=True))
        except UpdateError as exc:
            print(f"❌ {exc}", file=sys.stderr)
            return 1
        return 0

    snapshot = _backup()
    try:
        if args.set:
            req_id, _, status_key = args.set.partition("=")
            if req_id == args.set or not status_key:
                raise UpdateError("--set 格式須為 ID=STATUS，例如 GRD-09=done")
            result = do_set(req_id, status_key, dry_run=False)
            action, detail = "set", f"{req_id}={status_key}"
        elif args.close:
            if not args.why:
                raise UpdateError("--close 需要 --why 說明結案理由")
            result = do_close(args.close, args.why, dry_run=False)
            action, detail = "close", f"{args.close}：{args.why}"
        else:
            result = do_reopen(args.reopen, dry_run=False)
            action, detail = "reopen", args.reopen
    except UpdateError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    errors = _validate_after_write()
    if errors:
        _restore(snapshot)
        print("❌ 更新後驗證失敗，已還原全部檔案：", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    _append_changelog(action, detail)
    print(f"✅ {result}")
    print("提醒：docs/spec.json 尚未重產，請執行 python3 scripts/spec-export.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
