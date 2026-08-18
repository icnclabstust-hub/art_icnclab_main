"""
title: 博物館知識圖譜 GraphRAG
author: Art History Database Team
version: 1.0.0
description: 整合各博物館 API 的 Neo4j 知識圖譜，透過圖譜關係推理回答問題
"""

import requests
from opencc import OpenCC
from pydantic import BaseModel, Field

_opencc = OpenCC("s2twp")


class Pipe:
    class Valves(BaseModel):
        RAG_MANAGER_URL: str = Field(
            default="http://localhost:8007",
            description="rag-manager-v2 服務位址",
        )
        MODEL_COMBINATION_ID: str = Field(
            default="qwen3:8b@graph_only",
            description="格式為 '{ollama模型}@graph_only'，純 Neo4j 圖譜檢索",
        )
        MAX_RESULTS: int = Field(default=5, description="檢索文件數上限")
        TIMEOUT: int = Field(default=90, description="請求逾時秒數")
        SHOW_SOURCES: bool = Field(default=True, description="是否在回答後附上參考來源")

    def __init__(self):
        self.id = "museums_graphrag"
        self.name = "qwen3 8B + 博物館知識圖譜 GraphRAG"
        self.valves = self.Valves()

    def pipes(self):
        return [{"id": self.id, "name": ""}]

    def pipe(self, body: dict) -> str:
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
                    "model_combination_id": self.valves.MODEL_COMBINATION_ID,
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
            lines = ["", "---", "**🕸️ 知識圖譜參考來源：**"]
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
            answer += "\n\n---\n> ⚠️ 知識圖譜中尚無相關資料，回答僅來自模型本身知識。"

        return _opencc.convert(answer)
