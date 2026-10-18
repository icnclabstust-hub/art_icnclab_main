#!/usr/bin/env python3
"""台灣譯名比對用的「簡體字 → 繁體字」單字對照表（2026-10-18 8080 測試發現）。

qwen3:8b 常繁簡混用：「委拉斯開兹」（開＝繁、兹＝簡），譯名表只有「委拉斯開茲」而比對不到；
Open WebUI pipe 之後以 OpenCC 轉繁，使用者看到未替換的「委拉斯開茲」（10 次中 2 次）。
display_names.normalize 比對前先以本表逐字轉繁（一對一、長度不變），替換再對回原文位置。

範圍：artist_aliases.json 別名、display_names.json 顯示名、display_overrides.json 用到的字。
對照：每個繁體字 c 經 OpenCC t2s 得 s；s != c 時記 s → c（同一簡體字對到多個繁體字者不收）。

用法（WSL；OpenCC 用 Open WebUI venv 的 python，只在建置時需要）：
    python3 scripts/build_display_char_fold.py
輸出：langchain-rag/display_char_fold.json
"""

import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RAG = REPO / "langchain-rag"
OUT = RAG / "display_char_fold.json"
OPENCC_PY = "/home/user/openwebui-venv/bin/python"
CJK = re.compile(r"[一-鿿]")


def t2s(chars: list[str]) -> list[str]:
    code = (
        "import json,sys,opencc;c=opencc.OpenCC('t2s');"
        "print(json.dumps([c.convert(t) for t in json.load(sys.stdin)]))"
    )
    r = subprocess.run(  # noqa: S603 -- 固定直譯器與程式碼，輸入只經 stdin
        [OPENCC_PY, "-c", code], input=json.dumps(chars), capture_output=True, text=True, check=True
    )
    return json.loads(r.stdout)


def main() -> None:
    text = "".join(
        (RAG / name).read_text(encoding="utf-8")
        for name in ("artist_aliases.json", "display_names.json", "display_overrides.json")
        if (RAG / name).exists()
    )
    chars = sorted(set(CJK.findall(text)))
    simp = t2s(chars)
    owners = defaultdict(set)
    for trad, s in zip(chars, simp, strict=True):
        if len(s) == 1 and s != trad:
            owners[s].add(trad)
    fold = {s: next(iter(t)) for s, t in sorted(owners.items()) if len(t) == 1}
    ambiguous = sorted(s for s, t in owners.items() if len(t) > 1)
    OUT.write_text(
        json.dumps(
            {
                "_meta": {"source": "OpenCC t2s", "chars": len(chars), "ambiguous": ambiguous},
                "fold": fold,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"輸出 {OUT}：{len(fold)} 個簡體字對照（字元 {len(chars)}，歧義捨棄 {len(ambiguous)}）")


if __name__ == "__main__":
    main()
