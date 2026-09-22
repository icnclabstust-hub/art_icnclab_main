"""spec-export.py／spec-update.py 共用的 Markdown 表格與規格解析器。

只讀規格文件（`docs/*-system-spec-srs.md`、`docs/*-system-flow-steps.md`），
解析出表格與需求／步驟編號。刻意保持單純：不理解 Markdown 的完整語法，
只處理本專案這兩份文件實際使用的表格寫法（GFM pipe table）。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

# 需求／步驟編號：如 SYS-01、GRD-06c、BIZ-04a、P0-6、DAT-15a、8007（誤判用，排除純數字）
ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{0,7}-\d+[a-z]?$")

# 已知的狀態符號（放在儲存格開頭才算數，避免內文提到符號被誤判）
STATUS_GLYPHS = ("✅", "⚠️", "❌", "⏸", "✔", "TBD")

STATUS_MAP_FOR_UPDATE = {
    "done": "✅",
    "partial": "⚠️",
    "todo": "❌",
    "decided": "✅",
    "deferred": "⏸",
}


@dataclass
class TableRow:
    cells: list[str]
    line_no: int  # 該列在檔案中的行號（1-based）


@dataclass
class Table:
    header: list[str]
    rows: list[TableRow]
    start_line: int
    end_line: int


@dataclass
class Requirement:
    id: str
    title: str
    status_raw: str
    status_glyph: str | None
    file: str
    line_no: int
    section: str


@dataclass
class ParsedDoc:
    path: Path
    text: str
    lines: list[str]
    tables: list[Table] = field(default_factory=list)
    headings: list[tuple[int, str]] = field(default_factory=list)  # (level, text)
    toc_entries: list[str] = field(default_factory=list)


_ESCAPED_PIPE_PLACEHOLDER = "\x00"


def _split_row(line: str) -> list[str]:
    r"""把一行 pipe table 拆成儲存格；``\|``（跳脫過的 pipe，常見於 code span 內的
    正則表達式，如本專案自己的 ``grep -E 'a\|b'`` 範例）先換成佔位字元避免被當成分隔號，
    分割完再換回來。"""
    line = line.strip().replace("\\|", _ESCAPED_PIPE_PLACEHOLDER)
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip().replace(_ESCAPED_PIPE_PLACEHOLDER, "\\|") for c in line.split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", c.strip()) is not None for c in cells if c.strip())


def parse_markdown(path: Path) -> ParsedDoc:
    """解析單一 Markdown 檔：抽出所有 pipe table 與標題（供 C1/C2/C8/C11 使用）。"""
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    doc = ParsedDoc(path=path, text=text, lines=lines)

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            doc.headings.append((level, heading_match.group(2).strip()))
            if line.strip() == "## 目錄":
                j = i + 1
                while j < n and lines[j].strip().startswith("- "):
                    doc.toc_entries.append(lines[j].strip()[2:].strip())
                    j += 1
        if line.strip().startswith("|") and i + 1 < n and lines[i + 1].strip().startswith("|"):
            header_cells = _split_row(line)
            sep_cells = _split_row(lines[i + 1])
            if _is_separator_row(sep_cells):
                rows: list[TableRow] = []
                j = i + 2
                while j < n and lines[j].strip().startswith("|"):
                    rows.append(TableRow(cells=_split_row(lines[j]), line_no=j + 1))
                    j += 1
                doc.tables.append(
                    Table(header=header_cells, rows=rows, start_line=i + 1, end_line=j)
                )
                i = j
                continue
        i += 1
    return doc


def _strip_markdown_emphasis(cell: str) -> str:
    return re.sub(r"[*_~]", "", cell).strip()


def _extract_id(cell: str) -> str | None:
    """從第一欄取出需求／步驟編號；允許刪除線（~~ID~~）與前綴符號（如 ⏸ P0-2）。"""
    cleaned = cell.replace("~~", "").strip()
    cleaned = re.sub(r"^[⏸✅⚠️❌✔]+\s*", "", cleaned)
    token = cleaned.split()[0] if cleaned.split() else ""
    token = token.strip("*`")
    if ID_PATTERN.match(token):
        return token
    return None


def _extract_status_glyph(cell: str) -> str | None:
    cleaned = _strip_markdown_emphasis(cell)
    for glyph in STATUS_GLYPHS:
        if cleaned.startswith(glyph):
            return glyph
    return None


def extract_requirements(doc: ParsedDoc, current_section_of_line) -> list[Requirement]:
    """只從「有狀態欄」的表格抽取需求：判斷依據是表頭最後一欄含「狀態」二字。"""
    out: list[Requirement] = []
    for table in doc.tables:
        if not table.header or "狀態" not in table.header[-1]:
            continue
        for row in table.rows:
            if len(row.cells) != len(table.header):
                continue  # C8 會另外報告欄數不符，這裡先跳過避免索引錯誤
            req_id = _extract_id(row.cells[0])
            if req_id is None:
                continue
            title = row.cells[1] if len(row.cells) > 1 else ""
            status_raw = row.cells[-1]
            out.append(
                Requirement(
                    id=req_id,
                    title=_strip_markdown_emphasis(title)[:120],
                    status_raw=status_raw,
                    status_glyph=_extract_status_glyph(status_raw),
                    file=doc.path.name,
                    line_no=row.line_no,
                    section=current_section_of_line(row.line_no),
                )
            )
    return out


def section_lookup(doc: ParsedDoc):
    """回傳一個函式：給行號，回傳該行所屬的最近一個 heading 文字。"""
    heading_lines: list[tuple[int, str]] = []
    for idx, line in enumerate(doc.lines, start=1):
        m = re.match(r"^#{1,6}\s+(.*)$", line)
        if m:
            heading_lines.append((idx, m.group(1).strip()))

    def lookup(line_no: int) -> str:
        current = ""
        for h_line, h_text in heading_lines:
            if h_line <= line_no:
                current = h_text
            else:
                break
        return current

    return lookup


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class Step:
    id: str
    action: str
    depends_on: list[str]
    kind: str  # "task" | "procedure"
    closed: bool
    deferred: bool
    file: str
    line_no: int
    section: str


_PROCEDURE_SECTION = re.compile(r"^\d+\.\s*流程\s*[A-Z]")


def extract_steps(doc: ParsedDoc, current_section_of_line) -> list[Step]:
    """從「步驟｜動作｜前置｜…」表格抽取步驟（P0～Phase5 為 task，流程 A～G 為 procedure）。

    只認可有「前置」欄的表格；「前置」欄只放依賴的步驟編號，不放理由——
    這是本文件自訂的兩項設計前提（見 SRS 附錄 A.4），解析器據此運作，違反前提會算錯。
    """
    out: list[Step] = []
    for table in doc.tables:
        if not table.header or "前置" not in table.header:
            continue
        step_col = 0
        action_col = 1 if len(table.header) > 1 else 0
        pre_col = table.header.index("前置")
        for row in table.rows:
            if len(row.cells) != len(table.header):
                continue
            raw_id = row.cells[step_col]
            closed = "~~" in raw_id
            step_id = _extract_id(raw_id) or raw_id.replace("~~", "").strip().lstrip("⏸").strip()
            if not step_id:
                continue
            pre_cell = row.cells[pre_col] if pre_col < len(row.cells) else ""
            # 步驟編號有兩種格式：SYS-/GRD-/P0- 這類字母開頭（同 ID_PATTERN），
            # 以及 Phase 3～5 專用的純數字「3-5」「4-7」；「前置」欄兩種都可能出現。
            depends_on = sorted(
                set(re.findall(r"\b(?:[A-Z][A-Z0-9]{0,7}|[0-9])-\d+[a-z]?\b", pre_cell))
            )
            section = current_section_of_line(row.line_no)
            kind = "procedure" if _PROCEDURE_SECTION.match(section) else "task"
            deferred = raw_id.strip().startswith("⏸") or pre_cell.strip().startswith("⏸")
            out.append(
                Step(
                    id=step_id,
                    action=_strip_markdown_emphasis(row.cells[action_col])[:120],
                    depends_on=depends_on,
                    kind=kind,
                    closed=closed,
                    deferred=deferred,
                    file=doc.path.name,
                    line_no=row.line_no,
                    section=section,
                )
            )
    return out
