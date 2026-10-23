#!/usr/bin/env python3
# ruff: noqa: E501 -- 報表內的公式、出處與說明為長中文字串，拆行反而難以對照原文
"""黃金 15 題 × 5 模型 × 4 RAG 評估報表（.xlsx，2026-10-18）。

輸入：logs/eval/golden15-2026-10-18/judged.jsonl（scripts/eval_golden15_matrix.py judge 產生）、
overview.json（各來源筆數、Neo4j 分類筆數）、參考答案草稿。
輸出：桌面 RAG黃金15題評估_2026-10-18.xlsx。
矩陣與彙總一律以 AVERAGEIFS 公式從「原始資料」計算（開檔時 Excel 重算）。

用法（Windows py311_venv）：
    python scripts/build_golden15_report.py --overview <overview.json> [--out <xlsx>]
"""

import argparse
import json
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

REPO = Path(__file__).resolve().parent.parent
RUN = REPO / "logs" / "eval" / "golden15-2026-10-18"
MODELS = ["llama3.1:8b", "qwen3:8b", "deepseek-r1:8b", "gemma4:12b", "qwen3:14b"]
ROUTES = ["vector", "fulltext", "graph", "hybrid"]
ROUTE_ZH = {"vector": "向量 vector", "fulltext": "全文 fulltext", "graph": "圖譜 graph",
            "hybrid": "混合 hybrid"}  # fmt: skip
SOURCE_ZH = {
    "met_museum": "大都會藝術博物館（The Met）",
    "europeana": "Europeana（歐洲數位文化遺產）",
    "specialized_art": "專業藝術資料庫（拍賣目錄／地區館藏）",
    "harvard": "哈佛藝術博物館",
    "cleveland_museum": "克里夫蘭藝術博物館",
    "va_museum": "維多利亞與艾伯特博物館（V&A）",
    "art_institute_chicago": "芝加哥藝術博物館",
    "google_books": "Google Books（藝術史書目）",
    "masterpieces_curated": "精選名作集",
    "wikipedia_pilot": "Wikipedia 藝術史條目（試行）",
    "yale_university_art_gallery": "耶魯大學美術館（2026-09-23 已撤出）",
}
LABEL_ZH = {
    "Artwork": "作品", "Artist": "藝術家", "Translation": "譯名", "Institution": "收藏機構",
    "Source": "資料來源", "Place": "地點／文化", "Period": "時期", "Material": "材質",
    "Technique": "技法", "Style": "風格", "Concept": "概念", "Theme": "主題",
}  # fmt: skip
REL_ZH = {
    "CREATED": "藝術家創作作品", "HELD_BY": "作品收藏於機構", "USES_MATERIAL": "作品使用材質",
    "FROM_PLACE": "作品來自地點／文化", "USES_TECHNIQUE": "作品使用技法",
    "MENTIONS_CONCEPT": "作品提及概念", "DEPICTS_THEME": "作品描繪主題",
    "BELONGS_TO_STYLE": "作品屬於風格", "HAS_TRANSLATION": "詞條的中文譯名",
    "CREATED_IN_PERIOD": "作品屬於時期",
}  # fmt: skip
FACT_KEYS = {
    1: [["1642"], ["油", "oil"]], 2: [["1665"]], 3: [["1656"]], 4: [["1599", "1600"]],
    5: [["1612", "1614"], ["木板", "板上", "panel"]], 6: [["大理石", "marble"]],
}  # fmt: skip
REFUSAL = re.compile(
    r"沒有找到|未找到|沒有相關|無法回答|沒有提及|未提及|沒有提供|資料中沒有|無法依|沒有.*資料"
)

# 原始資料欄位：(欄名, judged.jsonl 鍵, 數字格式)
COLUMNS = [
    ("模型", "model", None), ("RAG", "route", None), ("題號", "no", "0"), ("題型", "type", None),
    ("回答準確度 Answer Correctness", "answer_correctness", "0.000"),
    ("事實 F1", "f1", "0.000"), ("TP", "TP", "0"), ("FP", "FP", "0"), ("FN", "FN", "0"),
    ("忠實度 Faithfulness", "faithfulness", "0.000"),
    ("主張數", "faith_n", "0"), ("被支持主張", "faith_supported", "0"),
    ("矛盾主張", "faith_contradicted", "0"),
    ("檢索精準度 Context Precision@5", "context_precision", "0.000"),
    ("召回率 Context Recall（LLM）", "context_recall", "0.000"),
    ("召回率 ID-based Context Recall", "id_context_recall", "0.000"),
    ("語義相似度 Semantic Similarity", "semantic_similarity", "0.000"),
    ("Semantic Affinity（以 Answer Relevancy 代替）", "answer_relevancy", "0.000"),
    ("迴避回答", "noncommittal", "0"),
    ("無幻覺率 DeepEval Hallucination", "no_hallucination", "0.000"),
    ("回應時間（秒）", "response_s", "0.00"), ("首段時間（秒）", "first_s", "0.00"),
    ("思考時間（秒）", "thinking_s", "0.00"),
    ("MEXA", None, None), ("DALI", None, None),
    ("規則判定（事實關鍵字／拒答）", "rule_correct", "0.000"),
    ("答對（準確度≥0.5）", None, None),
    ("回答原文", "answer", None),
]  # fmt: skip
COL = {name: i + 1 for i, (name, _, _) in enumerate(COLUMNS)}

# 矩陣：(標題, 原始資料欄名, 越大越好, 說明)
MATRICES = [
    ("Correctness（回答準確度）", "回答準確度 Answer Correctness", True, "Ragas Answer Correctness"),
    ("Faithfulness（忠實度）", "忠實度 Faithfulness", True, "Ragas Faithfulness"),
    ("Retrieval Precision（檢索精準度）", "檢索精準度 Context Precision@5", True,
     "Ragas Context Precision@K；同一 RAG×題的來源與模型無關，各列相同"),
    ("Response Time（回應時間，秒）", "回應時間（秒）", False, "實測：送出到收到完整回答"),
    ("MEXA", "MEXA", True, "無法計算：Ollama 0.32 不提供生成模型的隱藏層向量（/api/embed 回 501）"),
    ("DALI", "DALI", True, "無法計算：同 MEXA"),
    ("Semantic Affinity（以 Answer Relevancy 代替）", "Semantic Affinity（以 Answer Relevancy 代替）",
     True, "無官方定義；以 Ragas Answer Relevancy 代替（使用者 2026-10-18 同意）"),
    ("召回率（Context Recall，LLM）", "召回率 Context Recall（LLM）", True,
     "Ragas Context Recall；與模型無關"),
    ("召回率（ID-based，關係題 6 題）", "召回率 ID-based Context Recall", True,
     "Ragas ID-based Context Recall；分母＝參考 id 總數（6～28），前 5 筆上限偏低"),
    ("語義相似度（Semantic Similarity）", "語義相似度 Semantic Similarity", True, "Ragas"),
    ("無幻覺率（DeepEval Hallucination）", "無幻覺率 DeepEval Hallucination", True, "DeepEval"),
    ("思考時間（秒）", "思考時間（秒）", False, "實測：只有 deepseek-r1 有思考段"),
    ("首段時間（秒）", "首段時間（秒）", False, "實測：使用者看到第一段文字的時間"),
]  # fmt: skip
REQUESTED = MATRICES[:7]

FORMULAS = [
    ("Faithfulness", "忠實度", "忠實度 Faithfulness",
     "Faithfulness = 回答中被檢索來源支持的主張數 ÷ 回答的主張總數",
     "裁判 gemma4:12b 先把回答拆成原子主張，再逐條判定 supported／unsupported／contradicted（一次呼叫完成兩步）",
     "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/"),
    ("Answer Correctness", "回答準確度", "回答準確度 Answer Correctness",
     "Answer Correctness = 0.75 × F1 + 0.25 × Semantic Similarity（np.average，weights=[0.75, 0.25]）",
     "權重取自 Ragas 原始碼預設值；F1 見下列",
     "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_correctness/ ；預設權重："
     "https://github.com/explodinggradients/ragas/blob/main/src/ragas/metrics/_answer_correctness.py"),
    ("F1（Answer Correctness 的事實部分）", "事實 F1", "事實 F1",
     "F1 = |TP| ÷ (|TP| + 0.5 × (|FP| + |FN|))；TP＝回答與參考答案共有的陳述，FP＝只在回答，FN＝只在參考答案",
     "裁判把回答與參考答案拆成陳述後分類",
     "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_correctness/"),
    ("Semantic Similarity", "語義相似度", "語義相似度 Semantic Similarity",
     "Semantic Similarity = cos(E(回答), E(參考答案))",
     "嵌入模型 bge-m3（Ollama 11435）",
     "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/semantic_similarity/"),
    ("Answer Relevancy（Semantic Affinity 代替）", "Semantic Affinity", "Semantic Affinity（以 Answer Relevancy 代替）",
     "Answer Relevancy = (1/N) Σ cos(E(g_i), E(o))，N = 3；g_i＝由回答反推的問題，o＝原問題；迴避回答記 0",
     "Semantic Affinity 查無官方定義（2026-10-18 搜尋三次、MEXA／DALI 兩篇論文皆無），使用者同意以 Answer Relevancy 代替；"
     "依 Ragas 定義，拒答（迴避）記 0，故拒答題正確拒答也會得 0",
     "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_relevance/"),
    ("Context Precision@K", "檢索精準度", "檢索精準度 Context Precision@5",
     "Context Precision@K = Σ_{k=1..K}(Precision@k × v_k) ÷ 前 K 筆中相關數；Precision@k = TP@k ÷ (TP@k + FP@k)；v_k∈{0,1}",
     "K = 5；v_k 由裁判依參考答案判定（with-reference 版本）；前 K 筆皆不相關時記 0",
     "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/"),
    ("Context Recall（LLM）", "召回率", "召回率 Context Recall（LLM）",
     "Context Recall = 參考答案中可歸因於檢索來源的主張數 ÷ 參考答案主張總數",
     "裁判拆解參考答案並逐條判定",
     "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/"),
    ("ID-based Context Recall", "召回率（ID 版）", "召回率 ID-based Context Recall",
     "ID-based Context Recall = 檢索結果中找到的參考 id 數 ÷ 參考 id 總數",
     "只有關係題 B7～B12 有參考 id（2026-10-09-relation-rule-relevant.json，每題 6～28 個）；取前 5 筆",
     "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/"),
    ("Hallucination（DeepEval）", "無幻覺率", "無幻覺率 DeepEval Hallucination",
     "Hallucination = 與回答一致（無矛盾）的來源數 ÷ 來源總數（越高越好，預設門檻 0.5）",
     "現行 DeepEval 文件定義即「一致比例」，本報表直接作為無幻覺率；裁判逐來源判定是否被回答矛盾",
     "https://deepeval.com/docs/metrics-hallucination"),
    ("Response Time", "回應時間", "回應時間（秒）",
     "回應時間 = 收到完整回答的時刻 − 送出問題的時刻（秒）",
     "實測值，無統一官方公式；走正式 8001 /api/v1/query/stream（與 Open WebUI 相同路徑），每題先清快取",
     "（實測，非引用公式）"),
    ("Thinking Time", "思考時間", "思考時間（秒）",
     "思考時間 = 第一段回答時刻 − 檢索完成（meta 事件）時刻；僅在串流出現 thinking 事件時計算，否則 0",
     "qwen3、gemma4 依設定關閉思考（RAG_NO_THINK_MODELS），只有 deepseek-r1 有思考段",
     "（實測，非引用公式）"),
    ("MEXA", "跨語言對齊", "MEXA",
     "μ(C(L1,L2,m,l)) = (1/n) Σ_i 1( c_ii(l) > max_{j≠i}{ c_ij(l), c_ji(l) } )；token 加權平均 w_t = t ÷ Σk；跨層取平均",
     "無法計算：需各層隱藏狀態，Ollama 0.32 對生成模型 /api/embed 回 HTTP 501（使用者 2026-10-18 決定標示無法計算）",
     "Kargaran et al., MEXA, ACL 2025 Findings：https://arxiv.org/abs/2410.05873 ；https://github.com/cisnlp/MEXA"),
    ("DALI", "判別式對齊指標", "DALI",
     "DALI = 1 若 S((P+o_i)_L1, (P+o_i)_L2) > S((P+o_i)_L1, (P+o_j)_L2) 對所有 j≠i 成立，否則 0；S＝最後一個 token 隱藏狀態的 cosine",
     "無法計算：同 MEXA；且需選擇題（前提＋選項），黃金 15 題為問答題",
     "Can you map it to English? The Role of Cross-Lingual Alignment in Multilingual Performance of LLMs："
     "https://arxiv.org/abs/2504.09378"),
]  # fmt: skip

TITLE_FONT = Font(name="Arial", size=14, bold=True)
HEAD_FONT = Font(name="Arial", bold=True, color="FFFFFF")
HEAD_FILL = PatternFill("solid", fgColor="305496")
BODY_FONT = Font(name="Arial", size=10)
NOTE_FONT = Font(name="Arial", size=9, italic=True, color="595959")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def head(ws, row: int, values: list[str], col: int = 1) -> None:
    for i, v in enumerate(values):
        c = ws.cell(row=row, column=col + i, value=v)
        c.font, c.fill, c.border = HEAD_FONT, HEAD_FILL, BORDER
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def body(cell, fmt: str | None = None):
    cell.font, cell.border = BODY_FONT, BORDER
    if fmt:
        cell.number_format = fmt
    return cell


def rule_correct(r: dict) -> float | None:
    no, ans = int(r["no"]), r["answer"]
    if no in FACT_KEYS:
        groups = FACT_KEYS[no]
        return sum(any(k.lower() in ans.lower() for k in g) for g in groups) / len(groups)
    if r["type"] == "refuse":
        return 1.0 if REFUSAL.search(ans) else 0.0
    return None


def overview_sheet(wb, ov: dict) -> None:
    ws = wb.active
    ws.title = "總覽"
    ws["A1"] = "RAG 黃金 15 題評估報表（5 模型 × 4 RAG）"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = (
        f"資料時間：{ov['generated']}　｜　評估：巴洛克黃金集 15 題 × llama3.1:8b、qwen3:8b、deepseek-r1:8b、gemma4:12b、qwen3:14b × vector／fulltext／graph／hybrid"
    )
    ws["A2"].font = NOTE_FONT
    ws["A4"] = "一、爬蟲各博物館（資料來源）總筆數"
    ws["A4"].font = Font(name="Arial", size=12, bold=True)
    head(
        ws,
        5,
        [
            "來源代碼",
            "博物館／資料來源",
            "有效文件數（catalog）",
            "已刪除文件",
            "段落數（catalog）",
            "段落數（Elasticsearch）",
        ],
    )
    r = 6
    for src, live, deleted in ov["catalog"]:
        vals = [
            src,
            SOURCE_ZH.get(src, src),
            live,
            deleted,
            ov["chunks"].get(src, 0),
            ov.get("es", {}).get(src, 0),
        ]
        for i, v in enumerate(vals, 1):
            body(ws.cell(row=r, column=i, value=v), "#,##0" if i > 2 else None)
        r += 1
    first, last = 6, r - 1
    body(ws.cell(row=r, column=1, value="合計")).font = Font(name="Arial", bold=True)
    body(ws.cell(row=r, column=2, value=""))
    for col in range(3, 7):
        L = get_column_letter(col)
        body(ws.cell(row=r, column=col, value=f"=SUM({L}{first}:{L}{last})"), "#,##0").font = Font(
            name="Arial", bold=True
        )
    ws.cell(
        row=r + 1,
        column=1,
        value=f"ChromaDB 向量段落總數：{ov['chroma_total']:,}（向量庫不分來源統計；catalog、Elasticsearch 為每晚一致性檢查的比對基準）",
    ).font = NOTE_FONT
    ch = BarChart()
    ch.type, ch.title, ch.y_axis.title = "bar", "各來源有效文件數", "文件數"
    ch.add_data(Reference(ws, min_col=3, min_row=5, max_row=last), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=2, min_row=first, max_row=last))
    ch.height, ch.width, ch.legend = 9, 18, None
    ws.add_chart(ch, "I4")

    r += 3
    ws.cell(row=r, column=1, value="二、Neo4j 圖譜各分類（節點標籤）筆數").font = Font(
        name="Arial", size=12, bold=True
    )
    head(ws, r + 1, ["標籤", "中文分類", "節點數"])
    n0 = r + 2
    for i, (label, n) in enumerate(ov["neo4j_labels"]):
        body(ws.cell(row=n0 + i, column=1, value=label))
        body(ws.cell(row=n0 + i, column=2, value=LABEL_ZH.get(label, label)))
        body(ws.cell(row=n0 + i, column=3, value=n), "#,##0")
    n1 = n0 + len(ov["neo4j_labels"]) - 1
    body(ws.cell(row=n1 + 1, column=1, value="合計")).font = Font(name="Arial", bold=True)
    body(ws.cell(row=n1 + 1, column=3, value=f"=SUM(C{n0}:C{n1})"), "#,##0").font = Font(
        name="Arial", bold=True
    )
    ws.cell(
        row=n1 + 2,
        column=1,
        value=f"有效作品（未刪除）：{ov['neo4j_artworks_live']:,} 件；藝術家含 30 天保留期內已到期的舊作者節點",
    ).font = NOTE_FONT
    ch2 = BarChart()
    ch2.type, ch2.title = "bar", "Neo4j 各分類節點數"
    ch2.add_data(Reference(ws, min_col=3, min_row=n0 - 1, max_row=n1), titles_from_data=True)
    ch2.set_categories(Reference(ws, min_col=2, min_row=n0, max_row=n1))
    ch2.height, ch2.width, ch2.legend = 9, 18, None
    ws.add_chart(ch2, f"I{n0 - 2}")

    r = n1 + 4
    ws.cell(row=r, column=1, value="三、Neo4j 關係類型筆數").font = Font(
        name="Arial", size=12, bold=True
    )
    head(ws, r + 1, ["關係類型", "中文說明", "關係總數", "有效（未到期）"])
    k0 = r + 2
    for i, (t, n, a) in enumerate(ov["neo4j_rels"]):
        body(ws.cell(row=k0 + i, column=1, value=t))
        body(ws.cell(row=k0 + i, column=2, value=REL_ZH.get(t, t)))
        body(ws.cell(row=k0 + i, column=3, value=n), "#,##0")
        body(ws.cell(row=k0 + i, column=4, value=a), "#,##0")
    k1 = k0 + len(ov["neo4j_rels"]) - 1
    body(ws.cell(row=k1 + 1, column=1, value="合計")).font = Font(name="Arial", bold=True)
    for col in (3, 4):
        L = get_column_letter(col)
        body(ws.cell(row=k1 + 1, column=col, value=f"=SUM({L}{k0}:{L}{k1})"), "#,##0").font = Font(
            name="Arial", bold=True
        )

    r = k1 + 4
    ws.cell(row=r, column=1, value="四、作品收藏機構（HELD_BY）前 15 名").font = Font(
        name="Arial", size=12, bold=True
    )
    head(ws, r + 1, ["收藏機構", "", "作品數"])
    for i, (inst, n) in enumerate(ov["neo4j_inst"]):
        body(ws.cell(row=r + 2 + i, column=1, value=inst))
        body(ws.cell(row=r + 2 + i, column=3, value=n), "#,##0")
    for col, w in zip("ABCDEF", (26, 40, 20, 14, 18, 22), strict=True):
        ws.column_dimensions[col].width = w


def formula_sheet(wb) -> None:
    ws = wb.create_sheet("公式與出處")
    ws["A1"] = "指標公式與官方出處（2026-10-18 查證）"
    ws["A1"].font = TITLE_FONT
    head(ws, 3, ["指標", "中文", "本報表欄位", "公式（官方定義）", "本報表實作方式", "出處"])
    for i, row in enumerate(FORMULAS, 4):
        for j, v in enumerate(row, 1):
            c = body(ws.cell(row=i, column=j, value=v))
            c.alignment = Alignment(wrap_text=True, vertical="top")
    for col, w in zip("ABCDEF", (26, 14, 30, 60, 60, 60), strict=True):
        ws.column_dimensions[col].width = w


def raw_sheet(wb, rows: list[dict]) -> int:
    ws = wb.create_sheet("原始資料")
    head(ws, 1, [c[0] for c in COLUMNS])
    for i, r in enumerate(rows, 2):
        for j, (name, key, fmt) in enumerate(COLUMNS, 1):
            if name in ("MEXA", "DALI"):
                v = "N/A"
            elif name == "答對（準確度≥0.5）":
                ac = get_column_letter(COL["回答準確度 Answer Correctness"])
                v = f'=IF({ac}{i}="","",IF({ac}{i}>=0.5,1,0))'
                fmt = "0"
            elif key == "answer":
                v = (r.get(key) or "")[:2000]
            elif key == "no":
                v = int(r["no"])
            else:
                v = r.get(key)
            body(ws.cell(row=i, column=j, value=v), fmt)
    ws.freeze_panes = "E2"
    for j in range(1, len(COLUMNS) + 1):
        ws.column_dimensions[get_column_letter(j)].width = 14
    ws.column_dimensions[get_column_letter(COL["回答原文"])].width = 80
    return len(rows) + 1


def matrix_block(
    ws, top: int, title: str, colname: str, higher: bool, note: str, last: int
) -> tuple[int, int]:
    """在 top 列寫一個 模型 × RAG 矩陣（AVERAGEIFS），回傳 (表頭列, 最後列)。"""
    ws.cell(row=top, column=1, value=title).font = Font(name="Arial", size=12, bold=True)
    ws.cell(row=top, column=7, value=note).font = NOTE_FONT
    head(ws, top + 1, ["模型 ＼ RAG", *[ROUTE_ZH[r] for r in ROUTES], "模型平均"])
    v = get_column_letter(COL[colname])
    rng = lambda c: f"原始資料!${c}$2:${c}${last}"  # noqa: E731
    mcol, rcol = get_column_letter(COL["模型"]), get_column_letter(COL["RAG"])
    for i, m in enumerate(MODELS):
        row = top + 2 + i
        body(ws.cell(row=row, column=1, value=m)).font = Font(name="Arial", bold=True)
        for j, route in enumerate(ROUTES):
            f = f'=IFERROR(AVERAGEIFS({rng(v)},{rng(mcol)},$A{row},{rng(rcol)},"{route}"),"N/A")'
            body(ws.cell(row=row, column=2 + j, value=f), "0.000")
        body(
            ws.cell(
                row=row, column=6, value=f'=IFERROR(AVERAGEIFS({rng(v)},{rng(mcol)},$A{row}),"N/A")'
            ),
            "0.000",
        )
    avg_row = top + 2 + len(MODELS)
    body(ws.cell(row=avg_row, column=1, value="RAG 平均")).font = Font(name="Arial", bold=True)
    for j, route in enumerate(ROUTES):
        body(
            ws.cell(
                row=avg_row,
                column=2 + j,
                value=f'=IFERROR(AVERAGEIFS({rng(v)},{rng(rcol)},"{route}"),"N/A")',
            ),
            "0.000",
        )
    body(ws.cell(row=avg_row, column=6, value=f'=IFERROR(AVERAGE({rng(v)}),"N/A")'), "0.000")
    area = f"B{top + 2}:E{top + 1 + len(MODELS)}"
    good, bad = "63BE7B", "F8696B"
    lo, hi = (bad, good) if higher else (good, bad)
    ws.conditional_formatting.add(area, ColorScaleRule(start_type="min", start_color=lo, mid_type="percentile",
                                                       mid_value=50, mid_color="FFEB84", end_type="max", end_color=hi))  # fmt: skip
    return top + 1, avg_row


def matrix_sheet(wb, last: int) -> dict[str, tuple[int, int]]:
    ws = wb.create_sheet("矩陣")
    ws["A1"] = "模型 × RAG 矩陣（AVERAGEIFS 自「原始資料」計算；色階：綠＝較佳、紅＝較差）"
    ws["A1"].font = TITLE_FONT
    pos, top = {}, 3
    for title, colname, higher, note in MATRICES:
        pos[title] = matrix_block(ws, top, title, colname, higher, note, last)
        top = pos[title][1] + 3
    ws.column_dimensions["A"].width = 18
    for col in "BCDEF":
        ws.column_dimensions[col].width = 16
    return pos


def chart_sheet(wb, pos: dict[str, tuple[int, int]]) -> None:
    ws = wb.create_sheet("圖表")
    ws["A1"] = "七項矩陣圖（模型 × RAG）；MEXA、DALI 無法計算，以文字說明"
    ws["A1"].font = TITLE_FONT
    src = wb["矩陣"]
    anchor_row = 3
    for i, (title, colname, higher, note) in enumerate(REQUESTED):
        cell = f"{'A' if i % 2 == 0 else 'L'}{anchor_row}"
        if colname in ("MEXA", "DALI"):
            ws[cell] = f"{title}：{note}"
            ws[cell].font = Font(name="Arial", size=11, bold=True, color="C00000")
        else:
            h, avg_row = pos[title]
            ch = BarChart()
            ch.type, ch.title = "col", title
            ch.y_axis.title = "秒" if not higher else "分數"
            ch.add_data(
                Reference(src, min_col=2, max_col=5, min_row=h, max_row=h + len(MODELS)),
                titles_from_data=True,
            )
            ch.set_categories(Reference(src, min_col=1, min_row=h + 1, max_row=h + len(MODELS)))
            ch.height, ch.width = 8, 17
            ws.add_chart(ch, cell)
        if i % 2 == 1:
            anchor_row += 17


def summary_sheet(wb, last: int) -> None:
    ws = wb.create_sheet("彙總")
    ws["A1"] = "彙總（依模型、依 RAG；AVERAGEIFS）"
    ws["A1"].font = TITLE_FONT
    metrics = [m for m in MATRICES if m[1] not in ("MEXA", "DALI")]
    rng = lambda c: f"原始資料!${c}$2:${c}${last}"  # noqa: E731
    for block, (label, key_col, items) in enumerate(
        (("模型", "模型", MODELS), ("RAG", "RAG", ROUTES))
    ):
        top = 3 + block * (len(MODELS) + 5)
        head(ws, top, [label, *[m[0] for m in metrics], "答對率（準確度≥0.5）"])
        kc = get_column_letter(COL[key_col])
        ok = get_column_letter(COL["答對（準確度≥0.5）"])
        for i, it in enumerate(items):
            row = top + 1 + i
            body(ws.cell(row=row, column=1, value=it)).font = Font(name="Arial", bold=True)
            for j, (_, colname, _, _) in enumerate(metrics):
                v = get_column_letter(COL[colname])
                body(
                    ws.cell(
                        row=row,
                        column=2 + j,
                        value=f'=IFERROR(AVERAGEIFS({rng(v)},{rng(kc)},$A{row}),"N/A")',
                    ),
                    "0.000",
                )
            body(
                ws.cell(
                    row=row,
                    column=2 + len(metrics),
                    value=f'=IFERROR(AVERAGEIFS({rng(ok)},{rng(kc)},$A{row}),"N/A")',
                ),
                "0.0%",
            )
    ws.column_dimensions["A"].width = 16
    for j in range(2, len(metrics) + 3):
        ws.column_dimensions[get_column_letter(j)].width = 18
    ws.row_dimensions[3].height = 48
    ws.row_dimensions[3 + len(MODELS) + 5].height = 48


def reference_sheet(wb) -> None:
    ws = wb.create_sheet("參考答案")
    qs = json.loads(
        (REPO / "docs/golden-set/2026-10-01-baroque-questions.json").read_text(encoding="utf-8")
    )["questions"]
    refs = json.loads(
        (REPO / "docs/golden-set/2026-10-18-baroque-reference-answers-draft.json").read_text(
            encoding="utf-8"
        )
    )
    ws["A1"] = "參考答案（草稿，待人工審核）"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = refs["_meta"]["status"]
    ws["A2"].font = NOTE_FONT
    head(ws, 4, ["題號", "題型", "問題", "參考答案", "依據"])
    for i, q in enumerate(qs, 5):
        a = refs["answers"][str(q["no"])]
        for j, v in enumerate(
            [int(q["no"]), q["type"], q["question"], a["reference"], "；".join(a["sources"])], 1
        ):
            body(ws.cell(row=i, column=j, value=v)).alignment = Alignment(
                wrap_text=True, vertical="top"
            )
    for col, w in zip("ABCDE", (8, 10, 50, 80, 40), strict=True):
        ws.column_dimensions[col].width = w


def notes_sheet(wb, n: int) -> None:
    ws = wb.create_sheet("說明與限制")
    ws["A1"] = "說明與限制"
    ws["A1"].font = TITLE_FONT
    notes = [
        f"評估規模：15 題 × 5 模型 × 4 RAG = {n} 個回答；每組合 1 次。走正式 8001（臺灣繁體、台灣譯名、K 影子模式等現行設定）。",
        "裁判：gemma4:12b（temperature 0、JSON 輸出）；未經人工 κ 驗證，分數為「暫定」。",
        "參考答案：Claude 依館藏來源起草（使用者 2026-10-18 同意），未經標註者審核；影響 Answer Correctness、Semantic Similarity、Context Precision、Context Recall。",
        "Ragas 原為兩步（先抽主張、再判定），本報表合併為一次裁判呼叫；判定標準相同。",
        "來源內文每筆截取前 1,200 字給裁判（num_ctx 8192）。",
        "檢索指標（Context Precision／Recall、ID Recall）只取決於 RAG×題：同一題的來源與模型無關（翻譯模型固定），矩陣各列相同屬正常。",
        "ID-based Context Recall：分母為參考 id 總數（每題 6～28 個），只看前 5 筆，因此上限常低於 1。",
        "Semantic Affinity：查無官方定義，以 Ragas Answer Relevancy 代替；依其定義，拒答題（B13～B15）正確拒答也記 0。",
        "MEXA、DALI：屬跨語言對齊指標（衡量模型多語言能力，非 RAG 回答品質），需模型各層隱藏狀態；Ollama 0.32 對生成模型 /api/embed 回 501，依使用者決定標示 N/A。",
        "規則判定：事實題 B1～B6＝關鍵字（年份、媒材）命中比例；拒答題 B13～B15＝回答是否表明資料不足；關係題空白。",
        "答對：Answer Correctness ≥ 0.5 記為 1（本報表自訂門檻，非官方）。",
        "重評 1 筆：gemma4:12b＠hybrid 第 8 題的回答含不成對英文引號，裁判 JSON 輸出卡死；將回答中的英文雙引號替換為「」後重評忠實度（9 條主張）。",
        "回應時間含翻譯、檢索、K 評分與生成；gemma4:12b、qwen3:14b 部分層在 CPU 執行，生成較慢屬硬體限制（8 GB 顯示卡）。",
    ]
    for i, t in enumerate(notes, 3):
        c = ws.cell(row=i, column=1, value=f"{i - 2}. {t}")
        c.font, c.alignment = BODY_FONT, Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 140


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--overview", required=True)
    ap.add_argument("--judged", default=str(RUN / "judged.jsonl"))
    ap.add_argument(
        "--out", default=str(Path.home() / "Desktop" / "RAG黃金15題評估_2026-10-18.xlsx")
    )
    args = ap.parse_args()
    ov = json.loads(Path(args.overview).read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in Path(args.judged).open(encoding="utf-8")]
    order = {(m, r): i for i, (m, r) in enumerate((m, r) for m in MODELS for r in ROUTES)}
    rows.sort(key=lambda r: (order[(r["model"], r["route"])], int(r["no"])))
    for r in rows:
        r["rule_correct"] = rule_correct(r)
    wb = Workbook()
    overview_sheet(wb, ov)
    formula_sheet(wb)
    last = raw_sheet(wb, rows)
    pos = matrix_sheet(wb, last)
    chart_sheet(wb, pos)
    summary_sheet(wb, last)
    reference_sheet(wb)
    notes_sheet(wb, len(rows))
    order = ["總覽", "公式與出處", "矩陣", "圖表", "彙總", "原始資料", "參考答案", "說明與限制"]
    wb._sheets = [wb[name] for name in order]  # noqa: SLF001 -- openpyxl 無公開的重排 API
    wb.calculation.fullCalcOnLoad = True  # 開檔時 Excel 重算全部公式
    wb.save(args.out)
    print(f"輸出 {args.out}：{len(rows)} 筆")


if __name__ == "__main__":
    main()
