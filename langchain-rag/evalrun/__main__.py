"""命令列：``python -m evalrun import-golden|run|report``（需在 langchain-rag 目錄下執行）。"""

import argparse
import glob
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from ingest.db import connect

from evalrun import golden, runner

REPO_ROOT = Path(__file__).resolve().parents[2]


def _commit_sha() -> str | None:
    try:
        command = ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]
        return subprocess.check_output(command, text=True).strip()  # noqa: S603, S607 -- 固定指令
    except (OSError, subprocess.CalledProcessError):
        return None


def _latest_snapshot() -> dict | None:
    files = sorted(glob.glob(str(REPO_ROOT / "docs" / "golden-set" / "*-corpus-snapshot.json")))
    if not files:
        return None
    with open(files[-1], encoding="utf-8") as f:
        return json.load(f)


def _cmd_import(args: argparse.Namespace) -> int:
    only = {int(n) for n in args.only.split(",")} if args.only else None
    items = golden.read_workbook(args.xlsx, only)
    found = golden.problems(items)
    for problem in found:
        print(f"  ⚠ {problem}")
    if found and not args.allow_partial:
        print("有未完成的標註，未匯入（試標可加 --allow-partial）")
        return 1
    with connect() as conn:
        stats = golden.upsert_golden(conn, items, args.annotator)
    print(f"匯入 {len(items)} 題：新增 {stats['inserted']}／更新 {stats['updated']}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    with connect() as conn:
        corpus = runner.corpus_fingerprint(conn, _latest_snapshot())
        try:
            run_id = runner.run(
                conn,
                runner.http_retriever(args.api),
                args.trigger,
                commit_sha=_commit_sha(),
                config={"api": args.api},
                corpus=corpus,
                set_baseline=args.set_baseline,
            )
        except runner.NoGoldenQueries as exc:
            print(f"略過：{exc}")
            return 0
        outcomes = runner.record_regressions(conn, run_id)
        _print_summary(conn, run_id)
    print(f"語料：{corpus}")
    print(
        "退步告警："
        + ("、".join(f"{r} {o}" for r, o in outcomes.items()) or "未判斷（無基準或本次即基準）")
    )
    return 0


def _print_summary(conn, run_id: str) -> None:
    summary = runner.summarize(conn, run_id)
    print(f"run {run_id}")
    for route, stage in runner.ROUTES.items():
        cells = "  ".join(
            f"{metric}@{k} {summary.get((route, stage, metric, k), float('nan')):.3f}"
            for k in runner.KS
            for metric in runner.METRICS
        )
        print(f"  {route:9} {stage:10} {cells}")


def _cmd_report(args: argparse.Namespace) -> int:
    with connect() as conn:
        run_id = (
            args.run_id
            or conn.execute(
                "SELECT run_id::text FROM eval.runs WHERE status = 'done'"
                " ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        )
        if not run_id:
            print("尚無完成的量測 run")
            return 0
        _print_summary(conn, run_id if isinstance(run_id, str) else run_id[0])
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 進入點。"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(prog="evalrun", description="黃金集召回率量測（EVL-01～08）")
    sub = parser.add_subparsers(dest="command", required=True)

    imp = sub.add_parser("import-golden", help="匯入人工標註的候選表到 eval.golden_queries")
    imp.add_argument("--xlsx", required=True)
    imp.add_argument("--annotator", required=True, help="標註者（EVL-03）")
    imp.add_argument("--only", help="只匯入這些題號，逗號分隔（試標用）")
    imp.add_argument("--allow-partial", action="store_true", help="有未標註列仍匯入（試標用）")
    imp.set_defaults(handler=_cmd_import)

    run = sub.add_parser("run", help="對黃金集量測一次，寫入 eval.measurements 並與基準比較")
    run.add_argument("--trigger", choices=["nightly", "pre_deploy", "manual"], default="manual")
    run.add_argument("--set-baseline", action="store_true", help="把本次設為基準（人工確認後使用）")
    run.add_argument("--api", default=os.getenv("RAG_API_URL", "http://127.0.0.1:8001"))
    run.set_defaults(handler=_cmd_run)

    report = sub.add_parser("report", help="顯示某次（預設最新）run 的平均指標")
    report.add_argument("--run-id")
    report.set_defaults(handler=_cmd_report)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
