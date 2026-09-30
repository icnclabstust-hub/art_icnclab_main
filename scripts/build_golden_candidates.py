#!/usr/bin/env python3
"""產生黃金測試集標註用的候選表（流程 C-3，規格 EVL-01～05）。

每題以現況系統的多個策略檢索（pooling），合併為約 20 個候選文件，輸出 Excel 供
標註者逐一標記是否相關。候選只取自單一策略會讓黃金集偏袒該策略，之後比較新舊策略
就不公平，所以同時取新舊策略的結果。只呼叫 /api/v1/retrieve（不生成、不寫任何紀錄）。

題目設定 ``catalog_artist`` 時，另以 catalog 的 artist 欄位補充候選（標為「catalog 補充」）：
系統沒檢索到的相關文件若不進候選，就不會進黃金集，召回率會被高估。補充需要 DB 連線
參數（.env 的 DB_*）。

用法（需 rag-manager-v2 在 8001 運作，並先載入 .env，例如 set -a; . .env; set +a）：
    python3 scripts/build_golden_candidates.py
    python3 scripts/build_golden_candidates.py --questions docs/golden-set/xxx.json --out out.xlsx
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "langchain-rag"))
DEFAULT_QUESTIONS = REPO_ROOT / "docs" / "golden-set" / "2026-10-01-baroque-questions.json"
API_URL = "http://127.0.0.1:8001/api/v1/retrieve"

# 新舊策略都納入，避免候選池偏袒任何一方
POOL_STRATEGIES = ["hybrid", "vector", "fulltext", "graph", "hybrid_es_rag", "graph_only"]
PER_STRATEGY = 10
MAX_CANDIDATES = 25
MAX_CATALOG_SUPPLEMENT = 30
SNIPPET_CHARS = 220
CATALOG_HIT = "catalog 補充"

CATALOG_BY_ARTIST = """
SELECT external_id, doc_id::text, source, metadata->'artwork'
FROM catalog.documents
WHERE NOT is_deleted AND quarantine_status <> 'quarantined'
  AND metadata->'artwork'->>'artist' ILIKE %s
ORDER BY source, metadata->'artwork'->>'title'
LIMIT %s
"""

TYPE_LABELS = {"fact": "事實查詢", "relation": "關係查詢", "refuse": "應拒答"}
FONT = Font(name="Arial", size=10)
BOLD = Font(name="Arial", size=10, bold=True)
INPUT_FILL = PatternFill("solid", fgColor="FFFF00")
HEADER_FILL = PatternFill("solid", fgColor="D9D9D9")
WRAP = Alignment(wrap_text=True, vertical="top")

# 說明頁內容（接在標題、日期、候選來源三列之後；要填的四個欄位落在工作表第 6～9 列，標黃底）
GUIDE_ROWS = [
    ["", ""],
    ["要填的欄位（黃底）", ""],
    ["「候選」表的「相關」欄", "1＝這份文件能回答（或部分回答）題目；0＝不相關。每列都要填。"],
    ["「題目」表的「答案要點」欄", "正確答案應涵蓋的要點，一點一行（規格 C-5，供忠實度評分）。"],
    [
        "「題目」表的「漏掉的相關文件」欄",
        "知道資料庫有相關文件但沒出現在候選中時，填它的 external_id（逗號分隔）。",
    ],
    ["「題目」表的題目欄", "可直接修改題目；改了請告訴 AI 重產該題候選（候選隨題目改變）。"],
    ["", ""],
    ["判斷原則", ""],
    ["文件層級", "判斷「這份文件」是否相關，不是這一小段文字（規格 EVL-05）。"],
    ["應拒答題", "第 13～15 題預期資料庫沒有相關文件；若真的有，照實標 1 並在備註說明。"],
    [
        "「catalog 補充」",
        "系統六個策略都沒找到、由館藏資料依藝術家補進來的文件；一樣照內容判斷相關與否。",
    ],
    ["", ""],
    ["範例（候選表的一列）", "題號 1｜The Night Watch｜Rembrandt van Rijn｜1642｜相關＝1"],
]


def retrieve(question: str, strategy: str) -> dict:
    """呼叫 /api/v1/retrieve，回傳 sources 與 citations。"""
    body = json.dumps(
        {"query": question, "model_combination_id": f"x@{strategy}", "max_results": PER_STRATEGY}
    ).encode()
    request = urllib.request.Request(
        API_URL, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310 -- 固定本機位址
        return json.load(response)


def pool_candidates(question: str) -> tuple[list[dict], int]:
    """合併各策略結果：以文件 external_id 去重，依最佳名次、被幾個策略找到排序。

    Returns:
        (候選清單, 因沒有文件 id 而略過的結果數)。
    """
    pooled: dict[str, dict] = {}
    skipped = 0
    for strategy in POOL_STRATEGIES:
        data = retrieve(question, strategy)
        for rank, (source, citation) in enumerate(
            zip(data["sources"], data["citations"], strict=True), 1
        ):
            external_id = citation["external_id"]
            if not external_id:
                skipped += 1  # 例如舊 graph_only 回傳的 Artist 節點：不是文件，無法做文件層級標註
                continue
            meta = source.get("metadata") or {}
            entry = pooled.setdefault(
                external_id,
                {
                    "external_id": external_id,
                    "doc_id": citation["doc_id"],
                    "source": citation["source"],
                    "title": meta.get("title") or citation["title"] or "",
                    "artist": meta.get("artist") or "",
                    "date": meta.get("date") or "",
                    "snippet": re.sub(r"\s+", " ", str(source.get("content", "")))[:SNIPPET_CHARS],
                    "hits": {},
                },
            )
            entry["hits"].setdefault(strategy, rank)
    ordered = sorted(
        pooled.values(), key=lambda e: (min(e["hits"].values()), -len(e["hits"]), e["external_id"])
    )
    return ordered[:MAX_CANDIDATES], skipped


def catalog_supplement(conn, artist: str, known: set[str]) -> list[dict]:
    """以 catalog 的 artist 欄位補充系統沒檢索到的文件（已在候選中的略過）。"""
    rows = conn.execute(CATALOG_BY_ARTIST, (f"%{artist}%", MAX_CATALOG_SUPPLEMENT)).fetchall()
    supplements = []
    for external_id, doc_id, source, artwork in rows:
        if external_id in known:
            continue
        artwork = artwork or {}
        text = " ".join(
            f"{label}: {artwork[key]}"
            for label, key in (("Medium", "medium"), ("Description", "description"))
            if artwork.get(key)
        )
        supplements.append(
            {
                "external_id": external_id,
                "doc_id": doc_id,
                "source": source,
                "title": artwork.get("title") or "",
                "artist": artwork.get("artist") or "",
                "date": artwork.get("date") or "",
                "snippet": re.sub(r"\s+", " ", text)[:SNIPPET_CHARS],
                "hits": {CATALOG_HIT: None},
            }
        )
    return supplements


def _format_hits(hits: dict) -> str:
    ranked = sorted(hits.items(), key=lambda item: (item[1] is None, item[1] or 0))
    return "、".join(name if rank is None else f"{name}#{rank}" for name, rank in ranked)


def _style_sheet(sheet, widths: list[int]) -> None:
    for column, width in enumerate(widths, 1):
        sheet.column_dimensions[chr(64 + column)].width = width
    for row in sheet.iter_rows():
        for cell in row:
            cell.font = BOLD if cell.row == 1 else FONT
            cell.alignment = WRAP
            if cell.row == 1:
                cell.fill = HEADER_FILL
    sheet.freeze_panes = "A2"


def build_workbook(spec: dict, results: list[tuple[dict, list[dict], int]], out: Path) -> None:
    """輸出三張工作表：說明、題目（填答案要點）、候選（填相關與否）。"""
    wb = Workbook()
    guide = wb.active
    guide.title = "說明"
    guide_rows = [
        ["黃金測試集標註（巴洛克時期，15 題）", ""],
        ["產生日期", date.today().isoformat()],
        [
            "候選來源",
            "現況系統 "
            + "、".join(POOL_STRATEGIES)
            + f" 各取前 {PER_STRATEGY}，合併去重後最多 {MAX_CANDIDATES} 筆",
        ],
        *GUIDE_ROWS,
    ]
    for row in guide_rows:
        guide.append(row)
    _style_sheet(guide, [34, 100])
    for row in (6, 7, 8, 9):
        guide.cell(row=row, column=1).fill = INPUT_FILL

    questions = wb.create_sheet("題目")
    questions.append(
        ["題號", "題型", "題目", "候選數", "答案要點（請填）", "漏掉的相關文件（選填）", "備註"]
    )
    for q, candidates, _ in results:
        questions.append(
            [
                q["no"],
                TYPE_LABELS.get(q["type"], q["type"]),
                q["question"],
                len(candidates),
                "",
                "",
                "",
            ]
        )
    _style_sheet(questions, [6, 10, 48, 8, 50, 28, 30])
    for row in range(2, questions.max_row + 1):
        questions.cell(row=row, column=5).fill = INPUT_FILL
        questions.cell(row=row, column=6).fill = INPUT_FILL

    cands = wb.create_sheet("候選")
    cands.append(
        [
            "題號",
            "序",
            "相關（1/0）",
            "標題",
            "藝術家",
            "年代",
            "來源",
            "內容摘要",
            "被哪些策略找到（名次）",
            "external_id",
            "doc_id",
        ]
    )
    for q, candidates, _ in results:
        for index, c in enumerate(candidates, 1):
            hits = _format_hits(c["hits"])
            cands.append(
                [
                    q["no"],
                    index,
                    None,
                    c["title"],
                    c["artist"],
                    c["date"],
                    c["source"],
                    c["snippet"],
                    hits,
                    c["external_id"],
                    c["doc_id"],
                ]
            )
    _style_sheet(cands, [6, 5, 10, 34, 22, 14, 16, 60, 30, 26, 38])
    relevance = DataValidation(type="list", formula1='"1,0"', allow_blank=True)
    cands.add_data_validation(relevance)
    for row in range(2, cands.max_row + 1):
        cands.cell(row=row, column=3).fill = INPUT_FILL
        relevance.add(cands.cell(row=row, column=3))
    cands.auto_filter.ref = cands.dimensions

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="產生黃金測試集候選表")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    spec = json.loads(args.questions.read_text(encoding="utf-8"))
    out = args.out or args.questions.with_name(
        args.questions.name.replace("-questions.json", "-candidates.xlsx")
    )
    conn = None
    if any(q.get("catalog_artist") for q in spec["questions"]):
        from ingest.db import connect  # noqa: PLC0415 -- 只有 catalog 補充需要 DB

        conn = connect()
    results = []
    try:
        for q in spec["questions"]:
            candidates, skipped = pool_candidates(q["question"])
            added = []
            if conn and q.get("catalog_artist"):
                known = {c["external_id"] for c in candidates}
                added = catalog_supplement(conn, q["catalog_artist"], known)
                candidates += added
            results.append((q, candidates, skipped))
            print(
                f"第 {q['no']:2d} 題：系統候選 {len(candidates) - len(added):2d} 筆"
                f"＋catalog 補充 {len(added):2d} 筆（略過無文件 id 結果 {skipped} 筆）"
            )
    finally:
        if conn:
            conn.close()
    build_workbook(spec, results, out)
    print(f"已輸出：{out}")


if __name__ == "__main__":
    main()
