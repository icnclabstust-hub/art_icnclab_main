"""
title: 向量 RAG（系統路由，多模型）
author: Art History Database Team
version: 1.0.0
description: 向量檢索（ChromaDB 語意相近），單一系統路由（後端策略 vector），可切換 LLM 模型
"""

import requests
from opencc import OpenCC
from pydantic import BaseModel, Field

_opencc = OpenCC("s2twp")

# 後端系統路由（規格 RET-01）；與舊策略並存，黃金集基準比較完成前標示為實驗
RAG_STRATEGY = "vector"

# 選單排序：依實測回答速度由快到慢（2026-10-09 量測）
LLM_MODELS = {
    "llama3-1-8b": ("llama3.1:8b", "Llama 3.1 8B"),
    "qwen3-8b": ("qwen3:8b", "Qwen3 8B"),
    "deepseek-r1-8b": ("deepseek-r1:8b", "DeepSeek-R1 8B"),
    "qwen3-14b": ("qwen3:14b", "Qwen3 14B"),
    "gemma4-12b": ("gemma4:12b", "Gemma 4 12B"),
}

ROUTE_LABELS = {"vector": "向量", "fulltext": "全文", "graph": "圖"}


def _route_text(metadata: dict) -> str:
    """把 RRF 各路名次轉成「向量#1／全文#3」；RRF 分數本身不直觀，不顯示。"""
    ranks = (metadata.get("fusion") or {}).get("ranks") or {}
    parts = [
        f"{ROUTE_LABELS.get(route, route)}#{rank}"
        for route, rank in sorted(ranks.items(), key=lambda item: item[1])
    ]
    return f"（{'／'.join(parts)}）" if parts else ""


class Pipe:
    class Valves(BaseModel):
        RAG_MANAGER_URL: str = Field(
            default="http://localhost:8001",
            description="rag-manager-v2 服務位址",
        )
        MAX_RESULTS: int = Field(default=5, description="檢索文件數上限")
        TIMEOUT: int = Field(default=320, description="請求逾時秒數（含大型模型冷啟動時間）")
        SHOW_SOURCES: bool = Field(default=True, description="是否在回答後附上參考來源")

    def __init__(self):
        self.id = "system_vector_rag_multi"
        self.name = ""
        self.valves = self.Valves()

    def pipes(self):
        return [
            {"id": sub_id, "name": f"向量 RAG（系統路由）｜{llm_name}"}
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
            lines = ["", "---", "**📚 參考來源：**"]
            for i, source in enumerate(sources[: self.valves.MAX_RESULTS], 1):
                metadata = source.get("metadata", {})
                title = metadata.get("title") or metadata.get("name") or "未知"
                src_museum = metadata.get("source", "")
                museum_text = f" [{src_museum}]" if src_museum else ""
                lines.append(f"{i}. {title}{museum_text} {_route_text(metadata)}")
            answer += "\n" + "\n".join(lines)
        elif self.valves.SHOW_SOURCES and not sources:
            answer += "\n\n---\n> ⚠️ 知識庫中尚無相關資料，回答僅來自模型本身知識。"

        return _opencc.convert(answer)
