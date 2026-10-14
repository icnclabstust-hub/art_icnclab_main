"""K（檢索信心）評分器：bge-reranker-base（MIT）以 ONNX int8 在 CPU 對「問題 × 來源」打分。

依據：規格書 Q9（K＝最佳候選含有證據的機率）、Q5（reranker 不重排、只當 K）；
2026-10-14 E6：reranker 分數分辨力 AUROC 0.951（base）、檢索分數 0.31～0.52 不可用。

- K = sigmoid(PLATT_A × 最高分 + PLATT_B)：Platt 校準參數以 E6 的 41 題（可答 33＋canary 8，
  規則型標準答案）擬合，屬替代量尺、樣本內擬合，**暫定**；人工 golden set 完成後重擬。
- 模型目錄（含 tokenizer.json 與 onnx/model_int8.onnx）由 K_SCORER_MODEL_DIR 指定；
  第一次使用時才載入（約 0.3 GB RAM）。
"""

import math
import os
import threading
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

PLATT_A = 0.9777
PLATT_B = 2.5060
MAX_LENGTH = 512
_lock = threading.Lock()
_model = None


def _load():
    global _model
    with _lock:
        if _model is None:
            import numpy as np  # noqa: PLC0415 -- 只有啟用時才需要
            import onnxruntime as ort  # noqa: PLC0415
            from tokenizers import Tokenizer  # noqa: PLC0415

            folder = Path(os.environ["K_SCORER_MODEL_DIR"])
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = int(os.getenv("K_SCORER_THREADS", "4"))
            sess = ort.InferenceSession(
                str(folder / "onnx" / "model_int8.onnx"),
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            tok = Tokenizer.from_file(str(folder / "tokenizer.json"))
            tok.enable_truncation(max_length=MAX_LENGTH)
            tok.enable_padding()
            _model = (sess, tok, {i.name for i in sess.get_inputs()}, np)
    return _model


def raw_scores(query: str, texts: Sequence[str]) -> list[float]:
    sess, tok, inputs, np = _load()
    enc = tok.encode_batch([(query, t or " ") for t in texts])
    feed = {
        "input_ids": np.array([e.ids for e in enc], dtype=np.int64),
        "attention_mask": np.array([e.attention_mask for e in enc], dtype=np.int64),
    }
    if "token_type_ids" in inputs:
        feed["token_type_ids"] = np.array([e.type_ids for e in enc], dtype=np.int64)
    return sess.run(None, feed)[0].reshape(-1).tolist()


def calibrate(top: float) -> float:
    return 1 / (1 + math.exp(-(PLATT_A * top + PLATT_B)))


def score_k(query: str, sources: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """回傳 k（機率）、top（最高原始分數）、best（最高分來源索引）、scores、ms。"""
    start = time.monotonic()
    texts = [str(s.get("content") or "") for s in sources]
    if not texts:
        return {"k": 0.0, "top": None, "best": None, "scores": [], "ms": 0.0}
    scores = raw_scores(query, texts)
    best = max(range(len(scores)), key=lambda i: scores[i])
    return {
        "k": round(calibrate(scores[best]), 4),
        "top": round(scores[best], 4),
        "best": best,
        "scores": [round(s, 4) for s in scores],
        "ms": round((time.monotonic() - start) * 1000, 1),
    }
