"""重跑因逾時失敗的組合（DeepSeekR1-32B / Qwen3-30B 在部分題目+策略下生成失敗）。
沿用原本 write_docx 邏輯，直接覆蓋失敗的 docx 檔案。
"""

import sys
from datetime import datetime

from docx import Document

sys.path.insert(0, "/mnt/c/Users/user/Desktop/藝術史資料庫/art-history-database/scripts")
from run_24combo_evaluation import (
    OUTPUT_ROOT,
    QUESTIONS,
    query_rag,
    write_docx,
)

LLM_NAME_TO_TAG = {
    "Llama3.1-8B": "llama3.1:8b",
    "DeepSeekR1-8B": "deepseek-r1:8b",
    "Qwen3-8B": "qwen3:8b",
    "DeepSeekR1-32B": "deepseek-r1:32b",
    "Qwen3-30B": "qwen3:30b",
    "GPTOSS-20B": "gpt-oss:20b",
}
STRATEGY_NAME_TO_CODE = {
    "NaiveRAG": "naive_rag",
    "AdvancedRAG": "advanced_rag",
    "GraphRAG": "graph_only",
    "AgenticRAG": "agentic_rag",
}

LOG_FILE = OUTPUT_ROOT / "rerun_log.txt"


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def find_failed() -> list:
    """掃描 360 份檔案，找出回答為空錯誤的組合"""
    failed = []
    for q_idx in range(15):
        folder = OUTPUT_ROOT / f"第{q_idx + 1:02d}題"
        for llm_name, llm_tag in LLM_NAME_TO_TAG.items():
            for strat_name, strat_code in STRATEGY_NAME_TO_CODE.items():
                fp = folder / f"{llm_name}_{strat_name}.docx"
                if not fp.exists():
                    continue
                doc = Document(str(fp))
                text = "\n".join(p.text for p in doc.paragraphs)
                idx = text.find("回答")
                snippet = text[idx : idx + 30]
                if "錯誤:" in snippet:
                    failed.append((q_idx, llm_tag, llm_name, strat_code, strat_name))
    return failed


def main():
    failed = find_failed()
    log(f"共找到 {len(failed)} 個失敗組合，開始重跑")

    for i, (q_idx, llm_tag, llm_name, strat_code, strat_name) in enumerate(failed, start=1):
        question = QUESTIONS[q_idx]
        folder = OUTPUT_ROOT / f"第{q_idx + 1:02d}題"
        filepath = folder / f"{llm_name}_{strat_name}.docx"

        log(f"[{i}/{len(failed)}] 第{q_idx + 1}題 - {llm_name} + {strat_name} 重新生成中...")
        try:
            data, elapsed = query_rag(question, llm_tag, strat_code)
            write_docx(filepath, q_idx, question, llm_name, strat_name, data, elapsed)
            log(f"  完成，耗時 {elapsed:.1f} 秒")
        except Exception as e:
            log(f"  仍然失敗: {e}")
            write_docx(filepath, q_idx, question, llm_name, strat_name, None, 0, error=str(e))

    log("=== 重跑結束 ===")


if __name__ == "__main__":
    main()
