"""評測步驟 1：重新查詢 rag-manager-v2 的 /api/v1/retrieve，
把 15 題 x 4 種 RAG 策略（檢索結果與 LLM 選擇無關，60 組即可涵蓋全部 360 筆資料）
實際檢索到的原文片段快取下來，供 Faithfulness / Retrieval Precision 使用。
"""

import json
from pathlib import Path

import requests

RAG_MANAGER_URL = "http://localhost:8007"
OUTPUT_ROOT = Path("/mnt/c/Users/user/Desktop/驗證")
CONTEXT_CACHE_FILE = OUTPUT_ROOT / "數據資料" / "retrieval_context_cache.json"

QUESTIONS = [
    "辨識「Opera」「Opera del Duomo」「Opera di Santa Maria del Fiore」"
    "在混合語料資料庫中的指涉實體。",
    "Figura 的英語術語對應、歷史—神學義及其在教父至早期文藝復興中的承接。",
    "Disegno 的歷史收縮。",
    "Kunstwollen 的四層結構。",
    "達文西的邊界理論與暈塗法的光學優位。",
    "Medici Bank、Poggio 網絡與聖羅倫佐教堂：十五世紀佛羅倫斯秩序形式的比較考察。",
    "十四世紀煉金蒸餾、尼德蘭媒介改良與北方光學寫實。",
    "米開朗基羅天頂畫中先知與巫女的空間重構。",
    "從威尼斯 Colorito 到魯本斯祭壇畫色彩邏輯。",
    "Isabella d'Este 的怪誕審美與瓦薩里式藝術史的張力。",
    "《雅典學院》與《夜巡》的形式史深度對比。",
    "拉斐爾《雅典學院》中柏拉圖與亞里斯多德手勢的哲學分歧。",
    "從材料化學與光學散射看盛期文藝復興濕壁畫與威尼斯油畫的內部發光感。",
    "從「威壓的生命能量」到 Terribilità。",
    "伊兒汗細密畫、地中海節點與特雷琴托祭壇畫。",
]

STRATEGIES = ["naive_rag", "advanced_rag", "graph_only", "agentic_rag"]


def fetch_context(query: str, strategy: str) -> list:
    resp = requests.post(
        f"{RAG_MANAGER_URL}/api/v1/retrieve",
        json={
            "query": query,
            "model_combination_id": f"dummy@{strategy}",
            "max_results": 5,
            "include_sources": True,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["sources"]


def main():
    CONTEXT_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    cache = {}
    if CONTEXT_CACHE_FILE.exists():
        cache = json.loads(CONTEXT_CACHE_FILE.read_text(encoding="utf-8"))

    total = len(QUESTIONS) * len(STRATEGIES)
    count = 0
    for q_idx, question in enumerate(QUESTIONS):
        for strategy in STRATEGIES:
            key = f"{q_idx}|{strategy}"
            count += 1
            if key in cache:
                print(f"[{count}/{total}] 第{q_idx + 1}題 - {strategy} 已快取，跳過")
                continue
            print(f"[{count}/{total}] 第{q_idx + 1}題 - {strategy} 檢索中...", flush=True)
            try:
                sources = fetch_context(question, strategy)
                cache[key] = sources
            except Exception as e:
                print(f"  失敗: {e}")
                cache[key] = []
            CONTEXT_CACHE_FILE.write_text(
                json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8"
            )

    print(f"完成，快取寫入 {CONTEXT_CACHE_FILE}")


if __name__ == "__main__":
    main()
