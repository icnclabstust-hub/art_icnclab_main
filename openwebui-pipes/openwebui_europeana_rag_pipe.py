"""
title: Europeana 數位文化遺產 RAG
author: Art History Database Team
version: 1.0.0
description: 透過 rag-manager-v2 (Neo4j + ChromaDB) 檢索 Europeana 數位文化遺產資料並回答問題
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
            default="qwen3:8b@vector_only",
            description="格式為 '{ollama模型}@{rag策略}'，僅 vector_only 支援 source_filter",
        )
        SOURCE_FILTER: str = Field(
            default="europeana",
            description="限定只檢索 metadata.source 等於此值的文件",
        )
        MAX_RESULTS: int = Field(default=5, description="檢索文件數上限")
        TIMEOUT: int = Field(default=90, description="請求逾時秒數")
        SHOW_SOURCES: bool = Field(default=True, description="是否在回答後附上參考來源")

    def __init__(self):
        self.id = "europeana_rag"
        self.name = "Qwen3 8B + Europeana 數位文化遺產 RAG"
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
                    "source_filter": self.valves.SOURCE_FILTER,
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
            lines = ["", "---", "**📚 參考來源（Europeana）：**"]
            for i, source in enumerate(sources[: self.valves.MAX_RESULTS], 1):
                metadata = source.get("metadata", {})
                title = metadata.get("title") or source.get("source") or "未知"
                score = source.get("score")
                score_text = f"（相關度 {score:.2f}）" if isinstance(score, (int, float)) else ""
                lines.append(f"{i}. {title} {score_text}")
            answer += "\n" + "\n".join(lines)
        elif self.valves.SHOW_SOURCES and not sources:
            answer += "\n\n---\n> ⚠️ Europeana 知識庫中尚無相關資料，回答僅來自模型本身知識。"

        return _opencc.convert(answer)
