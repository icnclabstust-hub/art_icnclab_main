#!/usr/bin/env python3
"""
回報各來源最新一份爬蟲資料的平均品質分數。
目前有品質分數機制的來源：Europeana、Art Institute of Chicago、V&A Museum、Cleveland Museum of Art。
（Harvard 只有「研究價值」不是同一套 0-100 分制，不在此比較；其餘來源尚無品質分數機制。）
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "raw"
MIN_FILE_SIZE_BYTES = 1024

SOURCES = {
    "Europeana": "europeana_crawled_*.json",
    "Art Institute of Chicago": "art_institute_chicago_crawled_*.json",
    "Victoria and Albert Museum": "va_museum_crawled_*.json",
    "Cleveland Museum of Art": "cleveland_museum_crawled_*.json",
}


def latest_file(pattern):
    candidates = [f for f in DATA_DIR.rglob(pattern) if f.stat().st_size >= MIN_FILE_SIZE_BYTES]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.stat().st_mtime)


def report_source(name, pattern):
    f = latest_file(pattern)
    if not f:
        print(f"❌ {name}: 找不到資料檔案")
        return

    with open(f, encoding="utf-8") as fh:
        payload = json.load(fh)
    data = payload["data"] if isinstance(payload, dict) else payload

    scores = [item.get("qualityScore", 0) for item in data]
    if not scores:
        print(f"⚠️ {name}: 資料為空")
        return

    print(f"📂 {name} ({f.name})")
    print(f"   總筆數: {len(data)}")
    print(f"   平均品質分數: {sum(scores) / len(scores):.2f}/100")
    print(f"   最高分: {max(scores)}, 最低分: {min(scores)}")
    print()


def main():
    print("=" * 60)
    print("📊 各來源資料品質分數")
    print("=" * 60)
    for name, pattern in SOURCES.items():
        report_source(name, pattern)
    print("=" * 60)


if __name__ == "__main__":
    main()
