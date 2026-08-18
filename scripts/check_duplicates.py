#!/usr/bin/env python3
"""
檢查每個博物館來源最新一份爬蟲快照裡，資料是否有重複。
比對兩種重複：
  1. 完全重複的 ID（同一筆資料被寫入兩次）
  2. 標題+創作者 完全相同（不同 ID 但實質是同一筆資料的近似重複）
"""

import json
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "raw"
MIN_FILE_SIZE_BYTES = 1024

SOURCE_PATTERNS = {
    "europeana": ["europeana_crawled_*.json"],
    "harvard": ["harvard_art_museums_*.json", "harvard_objects.json"],
    "met_museum": ["met_museum_crawled_*.json"],
    "renaissance_baroque": ["renaissance_baroque_*.json"],
    "specialized_art": ["specialized_art_*.json"],
    "google_books": ["google_books_art_*.json"],
    "art_institute_chicago": ["art_institute_chicago_crawled_*.json"],
    "va_museum": ["va_museum_crawled_*.json"],
    "cleveland_museum": ["cleveland_museum_crawled_*.json"],
}


def latest_file(patterns):
    candidates = []
    for p in patterns:
        candidates.extend(f for f in DATA_DIR.rglob(p) if f.stat().st_size >= MIN_FILE_SIZE_BYTES)
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.stat().st_mtime)


def load_items(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        for key in ("data", "items", "records"):
            if key in data and isinstance(data[key], list):
                return data[key]
    if isinstance(data, list):
        return data
    return []


def get_id(item):
    for key in ("europeanaId", "harvardId", "objectID", "id"):
        if key in item and item[key]:
            return str(item[key])
    return None


def get_title_creator(item):
    title = (item.get("title") or "").strip().lower()
    creator = item.get("creator") or item.get("artist") or ""
    if isinstance(creator, list):
        creator = ",".join(creator)
    return f"{title}|{str(creator).strip().lower()}"


def main():
    print("=" * 60)
    print("📋 各來源重複資料檢查")
    print("=" * 60)

    total_items = 0
    total_dup_ids = 0
    total_dup_titles = 0

    for source, patterns in SOURCE_PATTERNS.items():
        f = latest_file(patterns)
        if not f:
            print(f"\n⚠️ {source}: 找不到資料檔案")
            continue

        items = load_items(f)
        n = len(items)
        total_items += n

        ids = [get_id(it) for it in items if get_id(it)]
        id_counts = Counter(ids)
        dup_ids = {k: v for k, v in id_counts.items() if v > 1}

        title_keys = [get_title_creator(it) for it in items]
        title_counts = Counter(title_keys)
        dup_titles = {k: v for k, v in title_counts.items() if v > 1 and k != "|"}

        total_dup_ids += sum(v - 1 for v in dup_ids.values())
        total_dup_titles += sum(v - 1 for v in dup_titles.values())

        print(f"\n📂 {source} ({f.name})")
        print(f"   總筆數: {n}")
        print(f"   ID 重複: {sum(v - 1 for v in dup_ids.values())} 筆多餘（{len(dup_ids)} 組重複)")
        print(
            f"   標題+創作者 重複: {sum(v - 1 for v in dup_titles.values())} 筆多餘（{len(dup_titles)} 組重複)"
        )
        if dup_ids:
            sample = list(dup_ids.items())[:3]
            print(f"   範例重複ID: {sample}")

    print("\n" + "=" * 60)
    print(
        f"📊 總計: {total_items} 筆資料，ID重複 {total_dup_ids} 筆，標題重複 {total_dup_titles} 筆"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
