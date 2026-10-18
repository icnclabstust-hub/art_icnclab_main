#!/usr/bin/env python3
"""黃金 15 題 × 5 模型 × 4 RAG 評估（2026-10-18）：第一段＝生成並記錄時間。

走正式 8001 的 /api/v1/query/stream（與 Open WebUI pipe 相同路徑），每題先清快取。
記錄：回答、來源內文（評分用 contexts）、來源 id、回應時間、首段時間、思考時間。
思考時間：串流中出現 thinking 事件時，從 meta（檢索完成）到第一段回答的時間；沒有思考則 0。

用法（WSL）：
    python3 scripts/eval_golden15_matrix.py generate --out logs/eval/golden15-2026-10-18
可中斷續跑（已完成的 模型×RAG×題 會略過）。
"""

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
API = "http://127.0.0.1:8001"
MODELS = ["llama3.1:8b", "qwen3:8b", "deepseek-r1:8b", "gemma4:12b", "qwen3:14b"]
ROUTES = ["vector", "fulltext", "graph", "hybrid"]


def post(path: str, body: dict, timeout: int = 900):
    req = urllib.request.Request(  # noqa: S310 -- 本機位址
        API + path, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 -- 本機位址


def ask(model: str, route: str, question: str) -> dict:
    t0 = time.monotonic()
    t_meta = t_first = None
    thinking = False
    meta, done = {}, {}
    body = {"query": question, "model_combination_id": f"{model}@{route}", "max_results": 5}
    with post("/api/v1/query/stream", body) as r:
        for line in r:
            e = json.loads(line)
            now = time.monotonic() - t0
            if e["type"] == "meta":
                t_meta, meta = now, e
            elif e["type"] == "thinking":
                thinking = True
            elif e["type"] == "delta" and t_first is None:
                t_first = now
            elif e["type"] == "done":
                done = e
            elif e["type"] == "error":
                done = {"answer": "", "error": e.get("detail")}
    total = time.monotonic() - t0
    sources = meta.get("sources") or []
    return {
        "answer": done.get("answer", ""),
        "error": done.get("error"),
        "contexts": [str(s.get("content") or "") for s in sources],
        "context_ids": [c.get("external_id") for c in meta.get("citations") or []],
        "response_s": round(total, 2),
        "first_s": round(t_first, 2) if t_first is not None else None,
        "thinking_s": round(t_first - t_meta, 2) if thinking and t_first and t_meta else 0.0,
        "retrieval_ms": meta.get("retrieval_time_ms"),
        "generation_ms": done.get("generation_time_ms"),
    }


def generate(out: Path) -> None:
    qs = json.load(
        open(REPO / "docs/golden-set/2026-10-01-baroque-questions.json", encoding="utf-8")
    )
    path = out / "answers.jsonl"
    done = set()
    if path.exists():
        done = {
            (r["model"], r["route"], r["no"]) for r in map(json.loads, path.open(encoding="utf-8"))
        }
    with path.open("a", encoding="utf-8") as f:
        for model in MODELS:  # 模型放最外層：每個模型只載入一次
            for route in ROUTES:
                for q in qs["questions"]:
                    if (model, route, q["no"]) in done:
                        continue
                    post("/api/v1/cache/clear", {}, 60).read()
                    try:
                        r = ask(model, route, q["question"])
                    except Exception as e:  # noqa: BLE001 -- 記錄失敗、繼續下一題
                        r = {
                            "answer": "",
                            "error": repr(e)[:200],
                            "contexts": [],
                            "context_ids": [],
                        }
                    row = {"model": model, "route": route, "no": q["no"], "type": q["type"], **r}
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f.flush()
                print(f"{model}@{route} 完成", flush=True)


# ==================== 第二段：評分（官方公式，LLM 裁判 gemma4:12b） ====================
# 公式出處（報表「公式與出處」頁逐條列出）：
# - Faithfulness＝被來源支持的主張數／回答主張總數（Ragas Faithfulness）
# - Answer Correctness＝0.75×F1＋0.25×Semantic Similarity；F1＝TP/(TP+0.5×(FP+FN))（Ragas）
# - Semantic Similarity＝cos(E(回答), E(參考答案))（Ragas）
# - Answer Relevancy＝(1/N)Σcos(E(g_i), E(原問題))，N=3；迴避回答記 0（Ragas）
# - Context Precision@K＝Σ(Precision@k×v_k)／前 K 筆相關數（Ragas）
# - Context Recall＝參考答案主張被來源支持數／參考答案主張總數（Ragas LLM 版）；
#   ID-based Context Recall＝找到的參考 id 數／參考 id 總數（Ragas）
# - Hallucination（DeepEval，越高越好）＝與回答一致的來源數／來源總數＝無幻覺率
JUDGE = "gemma4:12b"
OLLAMA = "http://127.0.0.1:11434"
EMBED_URL = "http://127.0.0.1:11435"
EMBED_MODEL = "bge-m3"
CTX_CHARS = 1200
YES = ("1", "True", "true", "yes")


def ollama_json(prompt: str) -> dict:
    body = {
        "model": JUDGE,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": "json",
        "keep_alive": "30m",
        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 1500},
    }
    req = urllib.request.Request(  # noqa: S310 -- 本機位址
        f"{OLLAMA}/api/generate", json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=900) as r:  # noqa: S310 -- 本機位址
        text = json.load(r).get("response", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def embed(texts: list[str]) -> list[list[float]]:
    req = urllib.request.Request(  # noqa: S310 -- 本機位址
        f"{EMBED_URL}/api/embed",
        json.dumps({"model": EMBED_MODEL, "input": texts}).encode(),
        {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310 -- 本機位址
        return json.load(r)["embeddings"]


def cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def ctx_block(contexts: list[str]) -> str:
    return "\n\n".join(f"[{i}] {c[:CTX_CHARS]}" for i, c in enumerate(contexts, 1))


def judge_faithfulness(question: str, answer: str, contexts: list[str]) -> dict:
    j = ollama_json(
        "You are evaluating a RAG answer (Ragas Faithfulness).\n"
        "Step 1: break the ANSWER into atomic factual statements (claims).\n"
        "Step 2: for each statement decide using ONLY the CONTEXT: "
        '"supported" (directly inferable), "unsupported" (not in context), '
        'or "contradicted" (context says otherwise).\n'
        'Return JSON {"statements":[{"text":"...","verdict":"supported"}]}.\n\n'
        f"QUESTION: {question}\n\nCONTEXT:\n{ctx_block(contexts)}\n\nANSWER:\n{answer}"
    )
    st = [x for x in j.get("statements") or [] if isinstance(x, dict)]
    n = len(st)
    sup = sum(x.get("verdict") == "supported" for x in st)
    con = sum(x.get("verdict") == "contradicted" for x in st)
    return {
        "faith_n": n,
        "faith_supported": sup,
        "faith_contradicted": con,
        "faithfulness": sup / n if n else None,
    }


def judge_correctness(question: str, answer: str, reference: str) -> dict:
    j = ollama_json(
        "You are evaluating answer correctness against a reference (Ragas Answer Correctness).\n"
        "Break both ANSWER and REFERENCE into atomic statements, then classify:\n"
        "TP = statements in the answer that are supported by the reference;\n"
        "FP = statements in the answer not present in the reference;\n"
        "FN = statements in the reference missing from the answer.\n"
        'Return JSON {"TP":["..."],"FP":["..."],"FN":["..."]}.\n\n'
        f"QUESTION: {question}\n\nREFERENCE:\n{reference}\n\nANSWER:\n{answer}"
    )
    tp, fp, fn = (len(j.get(k) or []) for k in ("TP", "FP", "FN"))
    denom = tp + 0.5 * (fp + fn)
    return {"TP": tp, "FP": fp, "FN": fn, "f1": tp / denom if denom else 0.0}


def judge_relevancy(question: str, answer: str) -> dict:
    j = ollama_json(
        "Generate 3 questions in Traditional Chinese that the following ANSWER directly answers, "
        "and decide whether the answer is noncommittal (evasive, vague, or a refusal such as "
        "'I do not know' or 'the data does not contain it'): 1 = noncommittal, 0 = committal.\n"
        'Return JSON {"questions":["...","...","..."],"noncommittal":0}.\n\n'
        f"ANSWER:\n{answer}"
    )
    gen = [q for q in j.get("questions") or [] if isinstance(q, str) and q.strip()][:3]
    if not gen:
        return {"answer_relevancy": None, "noncommittal": None}
    vecs = embed([question, *gen])
    score = sum(cos(vecs[0], v) for v in vecs[1:]) / len(gen)
    nc = 1 if str(j.get("noncommittal")) in YES else 0
    return {"answer_relevancy": 0.0 if nc else score, "noncommittal": nc}


def judge_hallucination(answer: str, contexts: list[str]) -> dict:
    prompt = (
        "For EACH numbered CONTEXT, decide whether the ANSWER contradicts it "
        f"(DeepEval Hallucination). There are exactly {len(contexts)} contexts. Return JSON "
        '{"verdicts":["no", ...]} with exactly one entry per context in order, '
        '"yes" meaning the answer contradicts that context.\n\n'
        f"CONTEXT:\n{ctx_block(contexts)}\n\nANSWER:\n{answer}"
    )
    v: list[str] = []
    for _ in range(2):  # 數量不符時重試一次
        v = [str(x).lower() for x in ollama_json(prompt).get("verdicts") or []][: len(contexts)]
        if len(v) == len(contexts):
            break
    if not v:
        return {"no_hallucination": None}
    # 重試後仍少於來源數：以已判定的來源計算（分母＝已判定數）
    return {"no_hallucination": sum(x != "yes" for x in v) / len(v), "halluc_judged": len(v)}


def judge_retrieval(question: str, reference: str, contexts: list[str]) -> dict:
    j = ollama_json(
        "Ragas Context Precision and Context Recall.\n"
        "A) For EACH numbered CONTEXT, is it useful for arriving at the REFERENCE answer? "
        "1 = useful, 0 = not.\n"
        "B) Break the REFERENCE into atomic statements; for each, 1 if it can be attributed to "
        "the contexts, else 0.\n"
        'Return JSON {"precision_verdicts":[1,0],'
        '"recall":[{"statement":"...","attributed":1}]}.\n\n'
        f"QUESTION: {question}\n\nREFERENCE:\n{reference}\n\nCONTEXT:\n{ctx_block(contexts)}"
    )
    v = [1 if str(x) in YES else 0 for x in j.get("precision_verdicts") or []][: len(contexts)]
    cp = None
    if v:  # Ragas Context Precision@K：Σ(Precision@k × v_k)／相關數；沒有相關時為 0
        cp = (
            sum((sum(v[: k + 1]) / (k + 1)) * v[k] for k in range(len(v))) / sum(v)
            if sum(v)
            else 0.0
        )
    rec = [x for x in j.get("recall") or [] if isinstance(x, dict)]
    cr = sum(str(x.get("attributed")) in YES for x in rec) / len(rec) if rec else None
    return {"context_precision": cp, "context_recall": cr, "precision_verdicts": v}


def judge(out: Path) -> None:
    qs = {
        q["no"]: q
        for q in load(REPO / "docs/golden-set/2026-10-01-baroque-questions.json")["questions"]
    }
    refs = load(REPO / "docs/golden-set/2026-10-18-baroque-reference-answers-draft.json")["answers"]
    gold = load(REPO / "docs/golden-set/2026-10-09-relation-rule-relevant.json")
    rows = [json.loads(line) for line in (out / "answers.jsonl").open(encoding="utf-8")]
    path = out / "judged.jsonl"
    done, retrieval_cache = set(), {}
    if path.exists():
        for r in map(json.loads, path.open(encoding="utf-8")):
            done.add((r["model"], r["route"], r["no"]))
            retrieval_cache[r["ctx_key"]] = {
                k: r[k] for k in ("context_precision", "context_recall", "precision_verdicts")
            }
    with path.open("a", encoding="utf-8") as f:
        for i, r in enumerate(rows, 1):
            if (r["model"], r["route"], r["no"]) in done:
                continue
            wait_for_night_window()  # 02:55～03:40 每晚排程期間暫停並卸載裁判
            q, ref = qs[r["no"]]["question"], refs[str(r["no"])]["reference"]
            # 同一 RAG×題的來源相同（翻譯模型固定），檢索指標只評一次
            ctx_key = f"{r['route']}|{r['no']}|{'|'.join(r['context_ids'])}"
            if ctx_key not in retrieval_cache:
                retrieval_cache[ctx_key] = judge_retrieval(q, ref, r["contexts"])
            res = {**r, "ctx_key": ctx_key, **retrieval_cache[ctx_key]}
            res.update(judge_faithfulness(q, r["answer"], r["contexts"]))
            res.update(judge_correctness(q, r["answer"], ref))
            a_vec, r_vec = embed([r["answer"], ref])
            res["semantic_similarity"] = cos(a_vec, r_vec)
            res["answer_correctness"] = 0.75 * res["f1"] + 0.25 * res["semantic_similarity"]
            res.update(judge_relevancy(q, r["answer"]))
            res.update(judge_hallucination(r["answer"], r["contexts"]))
            g = set(gold.get(str(r["no"]), []))
            res["id_context_recall"] = len(g & set(r["context_ids"][:5])) / len(g) if g else None
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
            f.flush()
            if i % 20 == 0:
                print(f"評分 {i}/{len(rows)}", flush=True)
    # 評分完卸載裁判（約 10 GB RAM）
    urllib.request.urlopen(  # noqa: S310 -- 本機位址
        urllib.request.Request(  # noqa: S310 -- 本機位址
            f"{OLLAMA}/api/generate",
            json.dumps({"model": JUDGE, "keep_alive": 0}).encode(),
            {"Content-Type": "application/json"},
        ),
        timeout=60,
    ).read()


def wait_for_night_window() -> None:
    from eval_24combo import wait_for_night_window as wait  # noqa: PLC0415 -- 同一套夜間時段規則

    wait()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("step", choices=["generate", "judge"])
    ap.add_argument("--out", default=str(REPO / "logs/eval/golden15-2026-10-18"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.step == "generate":
        generate(out)
    else:
        judge(out)


if __name__ == "__main__":
    main()
