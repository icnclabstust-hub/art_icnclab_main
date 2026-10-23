#!/usr/bin/env python3
"""新系統架構端到端串接測試：逐層檢查上下游是否接好（只讀與查詢，不改資料）。

架構各層（2026-10-18）：⓪採集 → ①攝取 catalog → ②同步儲存（ChromaDB／ES／Neo4j／Redis）
→ ③查詢理解（翻譯、人名防呆）→ ④檢索（vector／fulltext／graph／hybrid）
→ ⑤判斷與生成（K、5 模型、串流）→ ⑥介面（Open WebUI pipe）；⑦維運（告警）。

用法（WSL）：
    python3 scripts/system_e2e_check.py --api http://127.0.0.1:8001 --webui http://127.0.0.1:8080 \\
        --key-file ~/.openwebui_key                       # 正式
    python3 scripts/system_e2e_check.py --api http://127.0.0.1:8011 --new   # 新架構（開關全開）
結果：每項 PASS／FAIL／WARN，最後一行為總計；--out 另存 JSON。任一 FAIL 時結束碼 1。
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "langchain-rag"))
sys.path.insert(0, str(REPO / "scripts"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO / ".env")

from ingest.artist_names import parse_artists  # noqa: E402
from ingest.db import connect  # noqa: E402
from subscribers.base import lag  # noqa: E402

MODELS = ["llama3.1:8b", "qwen3:8b", "deepseek-r1:8b", "gemma4:12b", "qwen3:14b"]
ROUTES = ["vector", "fulltext", "graph", "hybrid"]
SUBSCRIBERS = ["chromadb", "elasticsearch", "neo4j", "redis"]
RAW = REPO / "crawlers" / "data" / "raw"
# 已撤出的來源（Yale 2026-09-23 移除，見 docs/decision-log.md）：原始檔不再更新
RETIRED_RAW = {"yale_university_art_gallery"}
STEP_FAILED = re.compile(r"❌ .+ 失敗（")
RESULTS: list[dict] = []


def check(layer: str, name: str, ok: bool | None, detail: str = "") -> None:
    status = "PASS" if ok else ("WARN" if ok is None else "FAIL")
    RESULTS.append({"layer": layer, "name": name, "status": status, "detail": detail})
    print(f"[{status}] {layer} {name}｜{detail}", flush=True)


def post(url: str, body: dict, timeout: int = 900, headers: dict | None = None) -> dict:
    req = urllib.request.Request(  # noqa: S310 -- 本機位址
        url, json.dumps(body).encode(), {"Content-Type": "application/json", **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 -- 本機位址
        return json.load(r)


def get(url: str, timeout: int = 60) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 -- 本機位址
        return json.load(r)


def neo4j_driver():
    from neo4j import GraphDatabase  # noqa: PLC0415

    return GraphDatabase.driver(
        "bolt://127.0.0.1:7687",
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )


def layer0() -> None:
    now = time.time()
    for d in sorted(p for p in RAW.iterdir() if p.is_dir() and p.name not in RETIRED_RAW):
        files = list(d.glob("*.json"))
        if not files:
            continue
        age = (now - max(f.stat().st_mtime for f in files)) / 3600
        check("⓪採集", f"{d.name} 最新原始檔", age <= 36, f"{age:.1f} 小時前")
    logs = sorted((REPO / "logs" / "daily_crawl").glob("catalog_crawl_*.log"))
    if logs:
        text = logs[-1].read_text(encoding="utf-8", errors="replace")
        # run_step 的失敗格式「❌ 步驟 失敗（」；爬蟲自身的「❌ 沒有找到作品」不算
        failed = [ln for ln in text.splitlines() if STEP_FAILED.search(ln)]
        done = "同步結束" in text
        check(
            "⓪採集",
            "最近每晚排程",
            not failed and done,
            f"{logs[-1].name}｜失敗步驟 {len(failed)}｜跑完 {done}"
            + (f"｜{failed[0][:60]}" if failed else ""),
        )


def layer1_2() -> None:
    with connect() as conn:
        for name in SUBSCRIBERS:
            n = lag(conn, name)
            check("①攝取", f"訂閱器 {name} 落後事件", n == 0, str(n))
        sources = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT source FROM catalog.documents WHERE NOT is_deleted ORDER BY 1"
            )
        ]
        live_chunks = conn.execute(
            "SELECT count(*) FROM catalog.chunks c JOIN catalog.documents d USING (doc_id)"
            " WHERE NOT c.is_deleted AND NOT d.is_deleted AND d.quarantine_status = 'clean'"
        ).fetchone()[0]
    for src in sources:
        r = subprocess.run(  # noqa: S603 -- 固定指令
            [sys.executable, "-m", "ingest", "verify", "--source", src, "--es"],
            cwd=REPO / "langchain-rag",
            capture_output=True,
            text=True,
        )
        last = (r.stdout.strip().splitlines() or [""])[-1]
        check("①攝取", f"catalog↔Chroma／ES 一致 {src}", r.returncode == 0, last[:80])
    check("②儲存", "catalog 有效段落", live_chunks > 0, str(live_chunks))
    with neo4j_driver() as drv, drv.session() as s:
        live = "coalesce(w.is_deleted, false) = false"
        no_held = s.run(
            f"MATCH (w:Artwork) WHERE {live} AND NOT (w)-[:HELD_BY]->() RETURN count(w) AS n"
        ).single()["n"]
        check("②儲存", "Neo4j 作品都有館藏連結", no_held == 0, f"缺 {no_held}")
        rows = s.run(
            "MATCH (a:Artist)-[c:CREATED]->(w:Artwork) WHERE c.valid_to IS NULL AND "
            + live
            + " RETURN a.name AS n, w.source AS s, count(*) AS k"
        ).data()
        junk = [r for r in rows if not parse_artists(r["s"], r["n"])]
        check(
            "②儲存",
            "Neo4j 有效作者關係無佚名／片段",
            not junk,
            f"{sum(r['k'] for r in junk)} 條" + (f"，例 {junk[0]['n']!r}" if junk else ""),
        )
        n_art = s.run(f"MATCH (w:Artwork) WHERE {live} RETURN count(w) AS n").single()["n"]
        check("②儲存", "Neo4j 有效作品", n_art > 0, str(n_art))


def layer3(api: str, new: bool) -> None:
    d = post(
        f"{api}/api/v1/query",
        {
            "query": "克林姆有哪些作品收藏在大都會藝術博物館？",
            "model_combination_id": "llama3.1:8b@hybrid",
        },
    )
    tr = d["metadata"].get("translation") or {}
    check(
        "③查詢", "翻譯走 LLM（非退回詞典）", tr.get("method") == "llm_hinted", str(tr.get("method"))
    )
    if new:
        terms = " ".join(tr.get("found_terms") or [])
        check("③查詢", "館藏外畫家詞典命中（克林姆）", "Klimt" in terms, terms[:80])
        check(
            "③查詢",
            "人名防呆已啟用（names_appended）",
            "names_appended" in tr,
            str(tr.get("names_appended")),
        )
        rq = tr.get("retrieval_query") or ""
        check("③查詢", "譯文含正確人名", "klimt" in rq.lower(), rq[:80])


def layer4(api: str, new: bool) -> None:
    qs = [
        "林布蘭的《夜巡》是何時完成的？",
        "卡拉瓦喬如何運用明暗對比？",
        "大都會藝術博物館收藏了哪些林布蘭的作品？",
    ]
    for route in ROUTES:
        n = [
            len(
                post(
                    f"{api}/api/v1/retrieve",
                    {"query": q, "model_combination_id": f"llama3.1:8b@{route}", "max_results": 5},
                )["sources"]
            )  # noqa: E501
            for q in qs
        ]
        check("④檢索", f"{route} 有來源", all(n), f"來源數 {n}")
    cons = json.load(
        open(REPO / "logs/eval/constraint-2026-10-11/questions.json", encoding="utf-8")
    )
    c = next(x for x in cons if x["key"] == "C1")
    ids = [
        x.get("external_id")
        for x in post(
            f"{api}/api/v1/retrieve",
            {"query": c["question"], "model_combination_id": "llama3.1:8b@graph", "max_results": 5},
        )["citations"]  # noqa: E501
    ]
    hit = sum(i in set(c["gold_ids"]) for i in ids)
    check(
        "④檢索", "圖譜錨點（C1 達文西@大都會）", hit == min(5, len(c["gold_ids"])), f"命中 {hit}/5"
    )
    if new:
        qs28 = json.load(
            open(REPO / "logs/eval/layer2-2026-10-14/e28_anchor_questions.json", encoding="utf-8")
        )
        q = next(x for x in qs28 if x["source"] != "met_museum")
        ids = [
            x.get("external_id")
            for x in post(
                f"{api}/api/v1/retrieve",
                {
                    "query": q["question"],
                    "model_combination_id": "llama3.1:8b@graph",
                    "max_results": 5,
                },
            )["citations"]  # noqa: E501
        ]
        hit = sum(i in set(q["gold_ids"]) for i in ids)
        check("④檢索", "擴充錨點＋館名擴充（大都會以外）", hit > 0, f"{q['question']}｜命中 {hit}")


def layer5(api: str) -> None:
    for model in MODELS:
        post(f"{api}/api/v1/cache/clear", {})  # 不清快取時回答直接取自 Redis，測不到生成
        t = time.time()
        try:
            d = post(
                f"{api}/api/v1/query",
                {
                    "query": "林布蘭的《夜巡》是何時完成的？",
                    "model_combination_id": f"{model}@hybrid",
                },
                timeout=900,
            )
            ans = d.get("answer") or ""
            ok = bool(ans.strip()) and not ans.lstrip().startswith("❌") and "1642" in ans
            check(
                "⑤生成",
                f"{model} 回答（含 1642）",
                ok,
                f"{time.time() - t:.0f} 秒｜K={(d['metadata'].get('k') or {}).get('k')}",
            )
        except Exception as e:  # noqa: BLE001 -- 測試要記錄所有失敗
            check("⑤生成", f"{model} 回答", False, repr(e)[:100])
    post(f"{api}/api/v1/cache/clear", {})
    req = urllib.request.Request(  # noqa: S310 -- 本機位址
        f"{api}/api/v1/query/stream",
        json.dumps(
            {
                "query": "維梅爾的《戴珍珠耳環的少女》收藏在哪裡？",
                "model_combination_id": "qwen3:8b@hybrid",
            }
        ).encode(),
        {"Content-Type": "application/json"},
    )
    types = []
    with urllib.request.urlopen(req, timeout=900) as r:  # noqa: S310 -- 本機位址
        for line in r:
            if line.strip():
                types.append(json.loads(line)["type"])
    ok = types[:1] == ["meta"] and "delta" in types and types[-1:] == ["done"]
    check("⑤生成", "串流 meta→delta→done", ok, f"事件 {len(types)}，最後 {types[-1:]}")


def layer6(webui: str, key_file: str) -> None:
    from eval_24combo import query_webui  # noqa: PLC0415

    key = Path(key_file).expanduser().read_text().strip()
    d = query_webui(webui, key, "llama3.1:8b", "hybrid", "林布蘭的《夜巡》是何時完成的？")
    ok = not d.get("error") and "1642" in d["answer"]
    check("⑥介面", "Open WebUI pipe（hybrid／llama）", ok, f"來源標題 {len(d['cited_titles'])}")


def layer7(api: str) -> None:
    try:
        d = get(f"{api}/api/v1/eval/alerts")
        items = d.get("alerts", d) if isinstance(d, dict) else d
        crit = (
            [a for a in items if (a.get("severity") == "critical")]
            if isinstance(items, list)
            else []
        )
        check("⑦維運", "未處理 critical 告警", None if crit else True, f"{len(crit)} 筆")
    except Exception as e:  # noqa: BLE001
        check("⑦維運", "告警端點", None, repr(e)[:80])
    h = get(f"{api}/health")
    check(
        "⑦維運",
        "/health 各服務",
        h.get("status") == "healthy",
        json.dumps(h.get("services"), ensure_ascii=False),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default="http://127.0.0.1:8001")
    ap.add_argument("--webui")
    ap.add_argument("--key-file")
    ap.add_argument("--new", action="store_true", help="新架構：額外檢查開關功能")
    ap.add_argument("--out")
    args = ap.parse_args()
    start = dt.datetime.now()
    print(f"=== 系統串接測試 {args.api} {'（新架構）' if args.new else ''} {start:%m-%d %H:%M} ===")
    for fn in (layer0, layer1_2):
        fn()
    layer3(args.api, args.new)
    layer4(args.api, args.new)
    layer5(args.api)
    if args.webui and args.key_file:
        layer6(args.webui, args.key_file)
    layer7(args.api)
    total = {s: sum(r["status"] == s for r in RESULTS) for s in ("PASS", "WARN", "FAIL")}
    print(f"=== 總計 {total}｜{(dt.datetime.now() - start).seconds // 60} 分鐘 ===")
    if args.out:
        Path(args.out).write_text(
            json.dumps(RESULTS, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return 1 if total["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
