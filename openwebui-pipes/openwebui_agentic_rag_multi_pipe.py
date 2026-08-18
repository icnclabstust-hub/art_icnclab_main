"""
title: Agentic RAG（多模型）
author: Art History Database Team
version: 1.0.0
description: 智能代理推理（Agentic RAG），可切換 6 種 LLM 模型
"""

import requests
from opencc import OpenCC
from pydantic import BaseModel, Field

_opencc = OpenCC("s2twp")

RAG_STRATEGY = "agentic_rag"

LLM_MODELS = {
    "llama3-1-8b": ("llama3.1:8b", "Llama 3.1 8B"),
    "deepseek-r1-8b": ("deepseek-r1:8b", "DeepSeek-R1 8B"),
    "qwen3-8b": ("qwen3:8b", "Qwen3 8B"),
    # 20B 以上暫時下架（2026-08-18 拍板：課堂以 8B/12B 為主；模型仍在 Ollama，
    # 重新上架解除下列註解即可）
    # "deepseek-r1-32b": ("deepseek-r1:32b", "DeepSeek-R1 32B"),
    # "qwen3-30b": ("qwen3:30b", "Qwen3 30B"),
    # "gpt-oss-20b": ("gpt-oss:20b", "GPT-OSS 20B"),
    "gemma4-12b": ("gemma4:12b", "Gemma 4 12B"),
}


class Pipe:
    class Valves(BaseModel):
        RAG_MANAGER_URL: str = Field(
            default="http://localhost:8007",
            description="rag-manager-v2 服務位址",
        )
        MAX_RESULTS: int = Field(default=5, description="檢索文件數上限")
        TIMEOUT: int = Field(
            default=320, description="請求逾時秒數（Agentic 多輪推理 + 大型模型冷啟動，預設拉長）"
        )
        SHOW_SOURCES: bool = Field(default=True, description="是否在回答後附上參考來源")

    def __init__(self):
        self.id = "agentic_rag_multi"
        self.name = ""
        self.valves = self.Valves()

    def pipes(self):
        return [
            {"id": sub_id, "name": f"{llm_name} + Agentic RAG"}
            for sub_id, (llm_tag, llm_name) in LLM_MODELS.items()
        ]

    def pipe(self, body: dict) -> str:
        model_id = body.get("model", "")
        sub_id = model_id.split(".", 1)[1] if "." in model_id else model_id
        llm_tag = LLM_MODELS.get(sub_id, (None, None))[0]
        if not llm_tag:
            return f"❌ 未知的模型: {sub_id}"

        messages = body.get("messages", [])
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        if isinstance(user_message, list):
            user_message = " ".join(
                part.get("text", "")
                for part in user_message
                if isinstance(part, dict) and part.get("type") == "text"
            )

        if not user_message:
            return "請輸入您的問題。"

        try:
            response = requests.post(
                f"{self.valves.RAG_MANAGER_URL}/api/v1/query",
                json={
                    "query": user_message,
                    "model_combination_id": f"{llm_tag}@{RAG_STRATEGY}",
                    "max_results": self.valves.MAX_RESULTS,
                    "include_sources": True,
                },
                timeout=self.valves.TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.RequestException as e:
            return f"❌ 無法連接 RAG 服務 ({self.valves.RAG_MANAGER_URL}): {e}"
        except Exception as e:
            return f"❌ 發生錯誤: {e}"

        answer = result.get("answer", "（沒有回答內容）")
        sources = result.get("sources", [])

        if self.valves.SHOW_SOURCES and sources:
            lines = ["", "---", "**🤖 參考來源：**"]
            for i, source in enumerate(sources[: self.valves.MAX_RESULTS], 1):
                metadata = source.get("metadata", {})
                title = metadata.get("title") or metadata.get("name") or "未知"
                src_museum = metadata.get("source", "")
                score = source.get("score")
                score_text = f"（相關度 {score:.2f}）" if isinstance(score, (int, float)) else ""
                museum_text = f" [{src_museum}]" if src_museum else ""
                lines.append(f"{i}. {title}{museum_text} {score_text}")
            answer += "\n" + "\n".join(lines)
        elif self.valves.SHOW_SOURCES and not sources:
            answer += "\n\n---\n> ⚠️ 知識庫中尚無相關資料，回答僅來自模型本身知識。"

        return _opencc.convert(answer)
