"""評測步驟 4：把 360 份生成答案翻譯成英文，作為 MEXA / DALI / Semantic Affinity 的平行語料基礎。

方法學說明：MEXA/DALI 原始定義需要模型「內部隱藏層向量」，Ollama API 無法取得，
因此以 BGE-M3 句子向量取代，作為有明確交代取捨的簡化替代方案。
"""

import json
import re
import time
from pathlib import Path

import requests
from eval_step2_compute_metrics import load_all_generated

DATA_DIR = Path("/mnt/c/Users/user/Desktop/驗證/數據資料")
TRANSLATION_FILE = DATA_DIR / "answer_translations_en.json"
LOG_FILE = DATA_DIR / "eval_step4_log.txt"

OLLAMA_URL = "http://localhost:11434"
TRANSLATE_MODEL = "qwen3:8b"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def translate_to_english(text: str) -> str:
    prompt = f"""請把以下藝術史學術文字翻譯成英文，保留專有名詞與人名的正確拼寫。
只輸出翻譯結果，不要有任何說明或前綴。

{text[:2500]}"""
    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": TRANSLATE_MODEL,
            "prompt": prompt,
            "temperature": 0.1,
            "stream": False,
            "think": False,
        },
        timeout=180,
    )
    resp.raise_for_status()
    translated = resp.json().get("response", "").strip()
    translated = re.sub(r"<think>.*?</think>", "", translated, flags=re.DOTALL).strip()
    return translated


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log("載入 360 份生成回答...")
    generated_all = load_all_generated()

    translations = {}
    if TRANSLATION_FILE.exists():
        translations = json.loads(TRANSLATION_FILE.read_text(encoding="utf-8"))

    total = len(generated_all)
    count = 0
    for (q_idx, llm_tag, strategy_code), gen in generated_all.items():
        count += 1
        key = f"{q_idx}|{llm_tag}|{strategy_code}"
        if key in translations:
            continue
        log(f"[{count}/{total}] 翻譯 第{q_idx + 1}題 - {llm_tag} + {strategy_code} ...")
        try:
            en_text = translate_to_english(gen["answer"])
            translations[key] = en_text
        except Exception as e:
            log(f"  失敗: {e}")
            translations[key] = ""
        TRANSLATION_FILE.write_text(
            json.dumps(translations, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    log(f"=== 翻譯完成，共 {len(translations)} 筆 ===")


if __name__ == "__main__":
    main()
