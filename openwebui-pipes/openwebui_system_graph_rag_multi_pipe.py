"""
title: 圖 RAG（系統路由，多模型）
author: Art History Database Team
version: 1.1.0
description: 圖檢索（Neo4j 關係），單一系統路由（後端策略 graph），可切換 LLM 模型
"""

import json

import httpx
from opencc import OpenCC
from pydantic import BaseModel, Field

_opencc = OpenCC("s2twp")

# 後端系統路由（規格 RET-01）；與舊策略並存，黃金集基準比較完成前標示為實驗
RAG_STRATEGY = "graph"

# 選單排序：依實測回答速度由快到慢（2026-10-09 量測）
LLM_MODELS = {
    "llama3-1-8b": ("llama3.1:8b", "Llama 3.1 8B"),
    "qwen3-8b": ("qwen3:8b", "Qwen3 8B"),
    "deepseek-r1-8b": ("deepseek-r1:8b", "DeepSeek-R1 8B"),
}
# gemma4:12b、qwen3:14b 自 2026-10-15 起不作為本系統模型（8 GB VRAM 硬體限制，見 decision-log）

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
        STREAM: bool = Field(
            default=True,
            description="串流顯示（後端整句送出）；關閉＝等完整回答後一次顯示（舊行為）",
        )

    def __init__(self):
        self.id = "system_graph_rag_multi"
        self.name = ""
        self.valves = self.Valves()

    def pipes(self):
        return [
            {"id": sub_id, "name": f"圖 RAG（系統路由）｜{llm_name}"}
            for sub_id, (llm_tag, llm_name) in LLM_MODELS.items()
        ]

    async def pipe(self, body: dict, __event_emitter__=None):
        model_id = body.get("model", "")
        sub_id = model_id.split(".", 1)[1] if "." in model_id else model_id
        llm_tag = LLM_MODELS.get(sub_id, (None, None))[0]
        if not llm_tag:
            return f"❌ 未知的模型: {sub_id}"

        user_message = ""
        for msg in reversed(body.get("messages", [])):
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

        payload = {
            "query": user_message,
            "model_combination_id": f"{llm_tag}@{RAG_STRATEGY}",
            "max_results": self.valves.MAX_RESULTS,
            "include_sources": True,
        }
        if not self.valves.STREAM:
            return await self._blocking(payload)
        return self._stream(payload, __event_emitter__)

    async def _status(self, emitter, text: str, done: bool = False):
        if emitter:
            await emitter({"type": "status", "data": {"description": text, "done": done}})

    async def _blocking(self, payload: dict) -> str:
        """舊行為：等 /api/v1/query 完整回答。"""
        try:
            async with httpx.AsyncClient(timeout=self.valves.TIMEOUT) as client:
                response = await client.post(
                    f"{self.valves.RAG_MANAGER_URL}/api/v1/query", json=payload
                )
                response.raise_for_status()
                result = response.json()
        except httpx.HTTPError as e:
            return f"❌ 無法連接 RAG 服務 ({self.valves.RAG_MANAGER_URL}): {e}"
        except Exception as e:
            return f"❌ 發生錯誤: {e}"
        answer = result.get("answer", "（沒有回答內容）")
        return _opencc.convert(answer + self._sources_text(result.get("sources", [])))

    async def _stream(self, payload: dict, emitter):
        """串流：後端 /api/v1/query/stream（NDJSON，整句送出）；端點不可用時退回完整回答。"""
        await self._status(emitter, "🔎 正在檢索…")
        sources, sent_any = [], False
        try:
            async with httpx.AsyncClient(timeout=self.valves.TIMEOUT) as client:
                async with client.stream(
                    "POST", f"{self.valves.RAG_MANAGER_URL}/api/v1/query/stream", json=payload
                ) as response:
                    if response.status_code == 404:  # 後端尚未有串流端點
                        yield await self._blocking(payload)
                        await self._status(emitter, "", done=True)
                        return
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        event = json.loads(line)
                        if event["type"] == "meta":
                            sources = event.get("sources") or []
                            await self._status(emitter, "✍️ 生成中…")
                        elif event["type"] == "waiting":
                            seconds = round((event.get("elapsed_ms") or 0) / 1000)
                            await self._status(emitter, f"⏳ 模型準備中…（{seconds} 秒）")
                        elif event["type"] == "thinking":
                            seconds = round((event.get("elapsed_ms") or 0) / 1000)
                            await self._status(emitter, f"🧠 思考中…（{seconds} 秒）")
                        elif event["type"] == "delta":
                            sent_any = True
                            yield _opencc.convert(event["text"])
                        elif event["type"] == "error":
                            yield f"\n\n❌ 生成中斷：{event.get('detail', '')}"
                            await self._status(emitter, "", done=True)
                            return
        except httpx.HTTPError as e:
            if not sent_any:
                yield await self._blocking(payload)
            else:
                yield f"\n\n❌ 連線中斷：{e}"
            await self._status(emitter, "", done=True)
            return
        await self._status(emitter, "", done=True)
        yield _opencc.convert(self._sources_text(sources))

    def _sources_text(self, sources: list) -> str:
        if self.valves.SHOW_SOURCES and sources:
            lines = ["", "---", "**📚 參考來源：**"]
            for i, source in enumerate(sources[: self.valves.MAX_RESULTS], 1):
                metadata = source.get("metadata", {})
                title = metadata.get("title") or metadata.get("name") or "未知"
                src_museum = metadata.get("source", "")
                museum_text = f" [{src_museum}]" if src_museum else ""
                lines.append(f"{i}. {title}{museum_text} {_route_text(metadata)}")
            return "\n" + "\n".join(lines)
        if self.valves.SHOW_SOURCES and not sources:
            return "\n\n---\n> ⚠️ 知識庫中尚無相關資料，回答僅來自模型本身知識。"
        return ""
