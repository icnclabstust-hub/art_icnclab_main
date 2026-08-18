"""評測步驟 5：計算 MEXA / DALI / DALI_st / Semantic Affinity。

方法學說明（重要，務必保留於報告中）：
原始定義（Kargaran et al. 2410.05873 / Ravisankar et al. 2504.09378 / Gong 2601.09732）
皆需要模型「內部隱藏層向量」或「選擇題選項」，本評測系統透過 Ollama API 僅能取得
文字輸出與句子級 embedding（BGE-M3），無法取得隱藏層。因此本步驟以「BGE-M3 句子向量」
取代「模型隱藏層向量 e_L^(l)」作為簡化替代方案，並以「同一 LLM+RAG 組合底下的15題」
作為配對母體，取代原始定義中的「選擇題選項」。此為有明確交代的方法學簡化，非原始論文
的精確重現。

計算邏輯（每個 LLM+RAG 組合各自建立 15x15 中英相似度矩陣 C，其中 C[i][j] =
cos(embed(zh_i), embed(en_j))）：
- MEXA = (1/15) * sum_i [ 1(C[i][i] > max_{j!=i}(C[i][j], C[j][i])) ]
- DALI（逐題二元指標，此處回報平均值）= 1(C[i][i] > max_{j!=i} C[i][j])
- DALI_st = DALI=1 且 C[i][i] > 同語言內部（zh vs zh、en vs en）跨題最大相似度
- Semantic Affinity = mean(1-C[i][i]) / mean(1-C[i][j], i!=j)  （越接近0代表跨語言對齊越好，
  依論文定義其值介於0~1，此處採标准定義：分子為同題跨語言距離，分母為異題跨語言距離）
"""

import json
from pathlib import Path

import numpy as np
import requests
from eval_step2_compute_metrics import LLMS, STRATEGIES, load_all_generated

DATA_DIR = Path("/mnt/c/Users/user/Desktop/驗證/數據資料")
TRANSLATION_FILE = DATA_DIR / "answer_translations_en.json"
EMBED_CACHE_FILE = DATA_DIR / "semantic_embed_cache.json"
RESULTS_FILE = DATA_DIR / "semantic_metrics_results.json"

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "bge-m3:latest"


def embed_text(text: str, cache: dict) -> np.ndarray:
    if not text.strip():
        return np.zeros(1024)
    key = text[:200]
    if key in cache:
        return np.array(cache[key])
    for limit in (2500, 1500, 800, 400):
        resp = requests.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": text[:limit]},
            timeout=60,
        )
        if resp.status_code == 200:
            vec = resp.json()["embeddings"][0]
            cache[key] = vec
            return np.array(vec)
    resp.raise_for_status()


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def compute_combo_metrics(zh_answers: list, en_answers: list, embed_cache: dict) -> dict:
    n = len(zh_answers)
    zh_vecs = [embed_text(t, embed_cache) for t in zh_answers]
    en_vecs = [embed_text(t, embed_cache) for t in en_answers]

    # C[i][j] = cos(zh_i, en_j)
    C = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            C[i][j] = cosine_sim(zh_vecs[i], en_vecs[j])

    # 同語言內部相似度矩陣，供 DALI_st 使用
    ZZ = np.zeros((n, n))  # zh vs zh
    EE = np.zeros((n, n))  # en vs en
    for i in range(n):
        for j in range(n):
            ZZ[i][j] = cosine_sim(zh_vecs[i], zh_vecs[j])
            EE[i][j] = cosine_sim(en_vecs[i], en_vecs[j])

    dali_per_q = []  # 逐題 0/1，供 MEXA/DALI 誤差棒使用
    dali_st_per_q = []
    affinity_per_q = []  # 逐題 semantic affinity（該題 diag 距離 / 該題對外距離平均）
    diag_dists = []
    offdiag_dists = []

    for i in range(n):
        diag = C[i][i]
        off_row = [C[i][j] for j in range(n) if j != i]
        off_col = [C[j][i] for j in range(n) if j != i]
        max_mismatch = max(off_row + off_col) if (off_row + off_col) else -1.0

        is_dali = diag > max_mismatch
        dali_per_q.append(1 if is_dali else 0)

        is_dali_st = False
        if is_dali:
            intra_max = max(
                [ZZ[i][j] for j in range(n) if j != i] + [EE[i][j] for j in range(n) if j != i]
            )
            is_dali_st = diag > intra_max
        dali_st_per_q.append(1 if is_dali_st else 0)

        q_offdiag = off_row + off_col
        q_offdiag_dist_mean = float(np.mean([1 - v for v in q_offdiag])) if q_offdiag else 1.0
        q_diag_dist = 1 - diag
        affinity_per_q.append(q_diag_dist / q_offdiag_dist_mean if q_offdiag_dist_mean > 0 else 0.0)

        diag_dists.append(q_diag_dist)
        offdiag_dists.extend(1 - v for v in q_offdiag)

    mean_diag_dist = float(np.mean(diag_dists))
    mean_offdiag_dist = float(np.mean(offdiag_dists)) if offdiag_dists else 1.0
    semantic_affinity = mean_diag_dist / mean_offdiag_dist if mean_offdiag_dist > 0 else 0.0

    return {
        "mexa": float(np.mean(dali_per_q)),  # 此簡化下 MEXA 逐題條件與 DALI 相同，故共用陣列
        "dali": float(np.mean(dali_per_q)),
        "dali_st": float(np.mean(dali_st_per_q)),
        "semantic_affinity": semantic_affinity,
        "mexa_dali_per_q": dali_per_q,
        "dali_st_per_q": dali_st_per_q,
        "affinity_per_q": affinity_per_q,
    }


def main():
    translations = json.loads(TRANSLATION_FILE.read_text(encoding="utf-8"))
    generated_all = load_all_generated()

    embed_cache = {}
    if EMBED_CACHE_FILE.exists():
        embed_cache = json.loads(EMBED_CACHE_FILE.read_text(encoding="utf-8"))

    results = {}
    total = len(LLMS) * len(STRATEGIES)
    count = 0
    for llm_tag, _ in LLMS:
        for strategy_code, _ in STRATEGIES:
            count += 1
            print(f"[{count}/{total}] {llm_tag} + {strategy_code} 計算中...", flush=True)
            zh_answers = []
            en_answers = []
            for q_idx in range(15):
                key = f"{q_idx}|{llm_tag}|{strategy_code}"
                gen = generated_all.get((q_idx, llm_tag, strategy_code))
                zh_answers.append(gen["answer"] if gen else "")
                en_answers.append(translations.get(key, ""))

            metrics = compute_combo_metrics(zh_answers, en_answers, embed_cache)
            results[f"{llm_tag}|{strategy_code}"] = metrics
            EMBED_CACHE_FILE.write_text(
                json.dumps(embed_cache, ensure_ascii=False), encoding="utf-8"
            )
            RESULTS_FILE.write_text(
                json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8"
            )

    print(f"完成，共 {len(results)} 組合，寫入 {RESULTS_FILE}")


if __name__ == "__main__":
    main()
