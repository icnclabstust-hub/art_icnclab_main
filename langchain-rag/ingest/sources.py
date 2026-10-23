"""來源介面卡：每個來源提供「原始資料 → 正規化 dict」與「文件文字」兩個函式。

九個博物館來源沿用既有 ``import_all_museums_to_neo4j`` 的實作；Europeana 過去由獨立的
``sync_europeana_to_databases.py`` 處理（欄位與文字組合不同），這裡照它的規則重現，
使既有 Europeana 資料的 id 與內容維持相同。
"""

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ingest import legacy

EUROPEANA = "europeana"
EUROPEANA_FILE_PATTERN = "europeana_crawled_*.json"
EUROPEANA_ID_MAX = 128
EUROPEANA_DESCRIPTION_MAX = 1000
MIN_FILE_SIZE_BYTES = 1024


@dataclass(frozen=True)
class SourceAdapter:
    """一個來源的處理方式。

    Attributes:
        name: 來源名稱（catalog.documents.source）。
        normalize: ``(原始項目, 序號)`` → 正規化 dict（必含 id、title、artist、date）。
        document_text: 正規化 dict → 送進 ChromaDB／ES 的文件文字。
        resolve_files: 回傳該來源要讀取的檔案清單（未指定 --file 時使用）。
        load_items: 讀檔並回傳原始項目清單。
    """

    name: str
    normalize: Callable[[dict, int], dict]
    document_text: Callable[[dict], str]
    resolve_files: Callable[[], list[str]]
    load_items: Callable[[str], list[dict]]


def _safe_date(value: object) -> str:
    """Europeana 部分 date 是 ``{'def': '1900/1907'}`` 這類語系物件，轉成純字串。"""
    if value is None:
        return ""
    if isinstance(value, dict):
        return value.get("def") or next(iter(value.values()), "") or ""
    return str(value)


def normalize_europeana(item: dict, position: int = 0) -> dict:
    """把 Europeana 原始項目轉成正規化 dict，規則與 ``sync_europeana_to_databases.py`` 相同。

    Args:
        item: 爬蟲輸出的單筆資料。
        position: 缺少 ``europeanaId`` 時用來組替代 id 的序號。

    Returns:
        含 ``id``、``title``、``artist``、``creators``、``date``、``description``、
        ``provider``、``country``、``url`` 的 dict。
    """
    europeana_id = item.get("europeanaId") or f"euro_unknown_{position}"
    raw_creators = item.get("creator") or []
    return {
        "id": f"europeana_{europeana_id}".replace("/", "_")[:EUROPEANA_ID_MAX],
        "title": item.get("title") or "Untitled",
        "artist": ", ".join(raw_creators) if raw_creators else "",
        "creators": [c.strip() for c in raw_creators if c and c.strip()],
        "date": _safe_date(item.get("date")),
        "description": (item.get("description") or "")[:EUROPEANA_DESCRIPTION_MAX],
        "provider": item.get("provider") or "",
        "country": item.get("country") or "",
        "url": item.get("europeanaUrl") or "",
    }


def europeana_document_text(artwork: dict) -> str:
    """Europeana 的文件文字組合（Title／Creator／Date／Country／Provider／Description）。"""
    parts = [f"Title: {artwork['title']}"]
    for label, key in (
        ("Creator", "artist"),
        ("Date", "date"),
        ("Country", "country"),
        ("Provider", "provider"),
        ("Description", "description"),
    ):
        if artwork.get(key):
            parts.append(f"{label}: {artwork[key]}")
    return "\n".join(parts)


def _latest_europeana_file() -> list[str]:
    default = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
    raw_dir = Path(os.getenv("DATA_RAW_DIR", str(default)))
    candidates = [
        f for f in raw_dir.rglob(EUROPEANA_FILE_PATTERN) if f.stat().st_size >= MIN_FILE_SIZE_BYTES
    ]
    if not candidates:
        return []
    return [str(max(candidates, key=lambda f: f.stat().st_mtime))]


def _load_europeana_items(filename: str) -> list[dict]:
    with open(filename, encoding="utf-8") as f:
        payload = json.load(f)
    return payload["data"] if isinstance(payload, dict) else payload


def get_adapter(name: str) -> SourceAdapter:
    """取得來源介面卡。

    Args:
        name: 來源名稱（含 ``europeana``）。

    Returns:
        對應的 ``SourceAdapter``。

    Raises:
        KeyError: 未知來源。
    """
    if name == EUROPEANA:
        return SourceAdapter(
            name=EUROPEANA,
            normalize=normalize_europeana,
            document_text=europeana_document_text,
            resolve_files=_latest_europeana_file,
            load_items=_load_europeana_items,
        )
    module = legacy.load_legacy_module()
    normalizer = module.NORMALIZERS[name]
    return SourceAdapter(
        name=name,
        normalize=lambda item, _position: normalizer(item),
        document_text=module.build_document_text,
        resolve_files=lambda: module.resolve_sources().get(name, []),
        load_items=module.load_items,
    )


def source_names() -> list[str]:
    """所有可用來源名稱（含 Europeana）。"""
    return [*legacy.load_legacy_module().NORMALIZERS, EUROPEANA]


def load_artworks(adapter: SourceAdapter, files: list[str]) -> list[dict]:
    """讀取並正規化一個來源的所有項目；相同 id 只保留最後一筆。

    多個檔案（或同一檔案）可能含有相同 id 但內容略異（例如 MET 與文藝復興／巴洛克共用 id 空間）。
    既有匯入是「後寫者覆蓋」，這裡照同一語意先去重，避免同一份文件在一次攝取內被來回改寫、
    每次執行都產生多餘的變更事件。

    Args:
        adapter: 來源介面卡。
        files: 指定檔案；為空時用介面卡自動挑選最新檔。

    Returns:
        去重後的正規化作品 dict 清單（依各 id 最後一次出現的順序）。

    Raises:
        FileNotFoundError: 找不到任何資料檔。
    """
    filenames = files or adapter.resolve_files()
    if not filenames:
        raise FileNotFoundError(f"找不到來源 {adapter.name} 的資料檔，請用 --file 指定")
    latest: dict[str, dict] = {}
    for filename in filenames:
        for position, item in enumerate(adapter.load_items(filename)):
            artwork = adapter.normalize(item, position)
            latest.pop(artwork["id"], None)
            latest[artwork["id"]] = artwork
    return list(latest.values())
