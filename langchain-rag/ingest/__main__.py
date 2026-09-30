"""命令列：``python -m ingest run|verify``（需在 langchain-rag 目錄下執行）。"""

import argparse
import logging
import os
import sys

from ingest import backfill as backfill_module
from ingest import sources
from ingest.db import connect
from ingest.pipeline import ingest_artworks
from ingest.verify import (
    catalog_chunk_ids,
    chroma_chunk_ids,
    compare_ids,
    elasticsearch_chunk_ids,
)

DEFAULT_COLLECTION = "art_history_bgem3"
DEFAULT_ES_INDEX = "art_history_hybrid"


def _cmd_run(args: argparse.Namespace) -> int:
    if args.source not in sources.source_names():
        raise SystemExit(f"未知來源：{args.source}（可用：{', '.join(sources.source_names())}）")
    adapter = sources.get_adapter(args.source)
    try:
        artworks = sources.load_artworks(adapter, args.file)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    with connect() as conn:
        stats = ingest_artworks(
            conn,
            args.source,
            artworks,
            adapter.document_text,
            dry_run=args.dry_run,
            prune=args.prune,
        )
    mode = "（dry-run，未寫入）" if args.dry_run else ""
    print(f"[{args.source}] 來源 {len(artworks)} 筆{mode}")
    print(
        f"  新增 {stats.new}／變更 {stats.changed}／未變 {stats.unchanged}／"
        f"隔離 {stats.quarantined}／移除 {stats.pruned}／事件 {stats.events}"
    )
    return 0


def _print_comparison(label: str, comparison) -> None:
    print(f"[{label}] catalog {comparison.catalog_count}／檢索庫 {comparison.store_count}")
    print(
        f"  只在 catalog（未同步）{comparison.only_in_catalog}"
        f"／只在檢索庫（未認領或應刪除）{comparison.only_in_store}"
    )
    if comparison.catalog_samples:
        print(f"  只在 catalog 範例：{comparison.catalog_samples}")
    if comparison.store_samples:
        print(f"  只在檢索庫範例：{comparison.store_samples}")


def _cmd_verify(args: argparse.Namespace) -> int:
    import chromadb  # noqa: PLC0415 -- 只有 verify 需要連 ChromaDB

    with connect() as conn:
        catalog_ids = catalog_chunk_ids(conn, args.source)
    client = chromadb.HttpClient(
        host=os.getenv("CHROMADB_HOST", "localhost"), port=int(os.getenv("CHROMADB_PORT", "8000"))
    )
    collection = client.get_collection(name=os.getenv("CHROMADB_COLLECTION", DEFAULT_COLLECTION))
    chroma = compare_ids(catalog_ids, chroma_chunk_ids(collection, args.source))
    _print_comparison("ChromaDB", chroma)
    consistent = chroma.consistent

    if args.es:
        from elasticsearch import Elasticsearch  # noqa: PLC0415 -- 僅 --es 需要

        password = os.getenv("ES_PASSWORD")
        if not password:
            raise SystemExit("缺少 ES_PASSWORD 環境變數")
        es = Elasticsearch(
            os.getenv("ES_URL", "https://localhost:9200"),
            basic_auth=(os.getenv("ES_USERNAME", "elastic"), password),
            verify_certs=False,
        )
        es_result = compare_ids(
            catalog_ids, elasticsearch_chunk_ids(es, DEFAULT_ES_INDEX, args.source)
        )
        _print_comparison("Elasticsearch", es_result)
        consistent = consistent and es_result.consistent

    print("結果：一致" if consistent else "結果：不一致")
    if args.record_alerts:
        from ingest.alerts import record_consistency  # noqa: PLC0415 -- 僅寫告警時需要

        results = {"chromadb": chroma}
        if args.es:
            results["elasticsearch"] = es_result
        with connect() as conn:
            outcomes = {
                store: record_consistency(conn, args.source, store, comparison)
                for store, comparison in results.items()
            }
        print("告警：" + "／".join(f"{store} {outcome}" for store, outcome in outcomes.items()))
    return 0 if consistent else 1


def _cmd_check_disk(args: argparse.Namespace) -> int:
    from ingest import alerts  # noqa: PLC0415

    with connect() as conn:
        for spec in args.path:
            label, _, path = spec.partition("=")
            if not os.path.isdir(path):
                print(f"[{label}] 略過：{path} 不存在或未掛載")
                continue
            status = alerts.disk_status(label, path)
            outcome = alerts.record_disk(conn, status)
            print(
                f"[{label}] 剩餘 {status.free_pct}%"
                f"（{status.free_bytes / 1024**3:.1f}／{status.total_bytes / 1024**3:.1f} GB）"
                f"→ 告警 {outcome}"
            )
    return 0


def _cmd_check_guard(args: argparse.Namespace) -> int:
    from ingest import alerts  # noqa: PLC0415

    with connect() as conn:
        outcome, stats = alerts.record_gate_errors(conn, hours=args.hours)
    print(f"防護出錯比例（近 {args.hours} 小時）：{stats} → 告警 {outcome}")
    return 0


def _cmd_alerts_summary(args: argparse.Namespace) -> int:
    from ingest import alerts  # noqa: PLC0415

    with connect() as conn:
        text = alerts.format_summary(alerts.open_alerts(conn))
    print(text)
    if args.out:
        out = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    return 0


def _cmd_backfill(args: argparse.Namespace) -> int:
    import chromadb  # noqa: PLC0415 -- 只有 backfill 需要連 ChromaDB 與 Neo4j
    from neo4j import GraphDatabase  # noqa: PLC0415

    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        raise SystemExit("缺少 NEO4J_PASSWORD 環境變數")
    client = chromadb.HttpClient(
        host=os.getenv("CHROMADB_HOST", "localhost"), port=int(os.getenv("CHROMADB_PORT", "8000"))
    )
    collection = client.get_collection(name=os.getenv("CHROMADB_COLLECTION", DEFAULT_COLLECTION))
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), password),
    )
    with connect() as conn, driver.session() as session:
        managed = {
            r[0] for r in conn.execute("SELECT external_id FROM catalog.documents").fetchall()
        }
        documents, unreadable = backfill_module.read_legacy_documents(collection, session, managed)
        if args.source:
            documents = [d for d in documents if d.source in args.source]
        per_source: dict[str, list[int]] = {}
        for doc in documents:
            entry = per_source.setdefault(doc.source, [0, 0])
            entry[0] += 1
            entry[1] += len(doc.chunks)
        print(f"待補登來源（文件／chunk）：{len(documents)} 份文件")
        for source, (n_docs, n_chunks) in sorted(per_source.items()):
            print(f"  {source:32s} {n_docs:5d} 份／{n_chunks:5d} chunk")
        if unreadable["neo4j_node_without_source"]:
            skipped = unreadable["neo4j_node_without_source"]
            print(f"  （另有 {skipped} 個 Neo4j 節點沒有 source，無法補登）")
        stats = backfill_module.backfill_documents(conn, documents, apply=args.apply)
    mode = "已寫入" if args.apply else "預覽（未寫入，加 --apply 才會寫入）"
    print(f"[{mode}]")
    print(f"  文件 {stats.documents}／chunk {stats.chunks}／已存在略過 {stats.skipped_existing}")
    print(f"  隔離 {stats.quarantined}／撤出事件 {stats.events}")
    if stats.quarantined_ids:
        print(f"  隔離的文件：{stats.quarantined_ids[:10]}")
    return 0


def _cmd_retire_stale(args: argparse.Namespace) -> int:
    import collections  # noqa: PLC0415

    import chromadb  # noqa: PLC0415 -- 只有此指令需要連 ChromaDB

    client = chromadb.HttpClient(
        host=os.getenv("CHROMADB_HOST", "localhost"), port=int(os.getenv("CHROMADB_PORT", "8000"))
    )
    collection = client.get_collection(name=os.getenv("CHROMADB_COLLECTION", DEFAULT_COLLECTION))
    with connect() as conn:
        stale = backfill_module.find_stale_chunks(collection, conn)
        by_source = collections.Counter(c.source for c in stale)
        print(f"過時 chunk：{len(stale)} 個")
        for source, n in sorted(by_source.items()):
            print(f"  {source:32s} {n:5d}")
        for chunk in stale[: args.show]:
            current = conn.execute(
                "SELECT c.external_id FROM catalog.chunks c JOIN catalog.documents d USING (doc_id)"
                " WHERE d.external_id = %s ORDER BY c.chunk_index LIMIT 1",
                (chunk.doc_external_id,),
            ).fetchone()
            current_id = current[0] if current else "無"
            print(f"\n  ▸ {chunk.external_id}（文件 {chunk.doc_external_id}；現行：{current_id}）")
            print(f"    過時文字：{chunk.text[:110]!r}")
        count = backfill_module.retire_stale_chunks(conn, stale, apply=args.apply)
    mode = "已寫入 soft_delete 事件" if args.apply else "預覽（未寫入，加 --apply 才會寫入）"
    print(f"\n[{mode}] {count} 個；寫入後請執行 subscribers（chromadb、elasticsearch）讓事件生效")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 進入點。

    Args:
        argv: 參數清單；省略時用 ``sys.argv``。

    Returns:
        行程結束碼（verify 不一致時為 1）。
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(prog="ingest", description="catalog 攝取與驗證")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="攝取某來源的資料進 catalog")
    run.add_argument("--source", required=True, help="來源名稱，例如 harvard")
    run.add_argument(
        "--file", action="append", default=[], help="資料檔（可重複）；省略則自動選最新"
    )
    run.add_argument("--dry-run", action="store_true", help="只統計，不寫入")
    run.add_argument(
        "--prune", action="store_true", help="標記刪除來源快照中已消失的文件（僅完整快照可用）"
    )
    run.set_defaults(handler=_cmd_run)

    verify = sub.add_parser("verify", help="比對 catalog 與檢索庫的 id 集合")
    verify.add_argument("--source", required=True)
    verify.add_argument("--es", action="store_true", help="同時比對 Elasticsearch")
    verify.add_argument(
        "--record-alerts", action="store_true", help="結果寫入 eval.alerts（不一致開立、恢復結案）"
    )
    verify.set_defaults(handler=_cmd_verify)

    disk = sub.add_parser("check-disk", help="備份磁碟剩餘空間；<20%% warning、<10%% critical")
    disk.add_argument(
        "--path", action="append", required=True, help="標籤=路徑，可重複（例 wsl=/home/user）"
    )
    disk.set_defaults(handler=_cmd_check_disk)

    guard = sub.add_parser("check-guard", help="防護元件 hang／crash 比例；>1%% 開 critical")
    guard.add_argument("--hours", type=int, default=24)
    guard.set_defaults(handler=_cmd_check_guard)

    summary = sub.add_parser("alerts-summary", help="列出未處理告警（給 Operator 的每日彙總）")
    summary.add_argument("--out", help="另寫入此檔案（覆寫）")
    summary.set_defaults(handler=_cmd_alerts_summary)

    bf = sub.add_parser("backfill", help="把檢索庫已有、catalog 不認得的舊資料補登進 catalog")
    bf.add_argument("--source", action="append", default=[], help="只補登指定來源（可重複）")
    bf.add_argument("--apply", action="store_true", help="實際寫入（預設只預覽）")
    bf.set_defaults(handler=_cmd_backfill)

    rs = sub.add_parser("retire-stale", help="撤出檢索庫中過時的 chunk（catalog 已有更新版本）")
    rs.add_argument("--apply", action="store_true", help="實際寫入事件（預設只預覽）")
    rs.add_argument("--show", type=int, default=5, help="預覽時顯示的範例數")
    rs.set_defaults(handler=_cmd_retire_stale)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
