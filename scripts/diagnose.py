#!/usr/bin/env python3
"""
系統診斷腳本：檢查各服務健康狀態 + 掃描 log 檔案比對已知錯誤知識庫，
針對找到的錯誤直接輸出「出處（哪個服務/哪個檔案）→ 問題原因 → 建議解法」。

用法:
    python3 diagnose.py                  # 檢查健康狀態 + 掃描各服務最近的 log
    echo "<錯誤訊息>" | python3 diagnose.py   # 額外比對貼上的錯誤訊息
"""

import glob
import json
import os
import re
import socket
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
KB_FILE = SCRIPT_DIR / "error_knowledge_base.json"
TAIL_LINES = 200

LOG_FILES = {
    "rag_manager_v2.log": "/tmp/rag_manager_v2.log",
    "neo4j-native.log": "/tmp/neo4j-native.log",
    "chromadb.log": "/tmp/chromadb.log",
    "openwebui.log": "/tmp/openwebui.log",
}

HEALTH_CHECKS = [
    ("Neo4j (7688)", "127.0.0.1", 7688),
    ("ChromaDB (8000)", "127.0.0.1", 8000),
    ("rag-manager-v2 (8007)", "127.0.0.1", 8007),
    ("Open WebUI (8080)", "127.0.0.1", 8080),
]


def load_kb():
    with open(KB_FILE, encoding="utf-8") as f:
        return json.load(f)["entries"]


def check_port(host, port, timeout=2):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def tail(path, n=TAIL_LINES):
    if not os.path.exists(path):
        return ""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except Exception:
        return ""


def latest_daily_crawl_log():
    project_dir = SCRIPT_DIR.parent
    candidates = glob.glob(str(project_dir / "logs" / "daily_crawl" / "crawl_*.log"))
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def scan_text(text, source_name, kb, seen):
    findings = []
    for entry in kb:
        if source_name != "piped_input" and source_name not in entry.get("log_sources", []):
            continue
        if re.search(entry["pattern"], text):
            key = (entry["id"], source_name)
            if key in seen:
                continue
            seen.add(key)
            findings.append((source_name, entry))
    return findings


def print_finding(source_name, entry):
    print(f"\n🔴 發現問題 —— 出處: {source_name}")
    print(f"   標題: {entry['title']}")
    print(f"   原因: {entry['diagnosis']}")
    print("   建議解法:")
    for i, step in enumerate(entry["fix"], 1):
        print(f"     {i}. {step}")


def main():
    kb = load_kb()

    print("=" * 60)
    print("📡 服務健康狀態")
    print("=" * 60)
    all_healthy = True
    for name, host, port in HEALTH_CHECKS:
        ok = check_port(host, port)
        status = "✅ 運作中" if ok else "❌ 無回應"
        if not ok:
            all_healthy = False
        print(f"  {name}: {status}")

    print("\n" + "=" * 60)
    print("🔍 掃描各服務 log 檔案")
    print("=" * 60)

    seen = set()
    findings = []

    for source_name, path in LOG_FILES.items():
        text = tail(path)
        if text:
            findings.extend(scan_text(text, source_name, kb, seen))

    daily_log = latest_daily_crawl_log()
    if daily_log:
        text = tail(daily_log)
        findings.extend(scan_text(text, "daily_crawl", kb, seen))
        print(f"  已掃描: {os.path.basename(daily_log)}")

    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            print("  已掃描: 貼上的錯誤訊息")
            for entry in kb:
                if re.search(entry["pattern"], piped):
                    findings.append(("piped_input", entry))

    if findings:
        print(f"\n共發現 {len(findings)} 個已知問題：")
        for source_name, entry in findings:
            print_finding(source_name, entry)
    else:
        print("\n✅ 沒有比對到已知的錯誤模式")

    print("\n" + "=" * 60)
    if all_healthy and not findings:
        print("🎉 系統狀態正常")
    elif not all_healthy:
        print("⚠️ 有服務無回應，建議執行 scripts/Start-NativeServices.ps1")
    print("=" * 60)


if __name__ == "__main__":
    main()
