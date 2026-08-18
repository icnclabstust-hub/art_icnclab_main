#!/usr/bin/env python3
"""
MCP工具代理系統
提供Agent與MCP工具之間的標準化接口和通信代理
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import aiohttp

from mcp.mcp_tool_registry import MCPToolRegistry, MCPToolType, get_mcp_registry


class ProxyCallType(Enum):
    """代理調用類型"""

    SYNC = "sync"
    ASYNC = "async"
    STREAM = "stream"
    BATCH = "batch"


@dataclass
class ProxyRequest:
    """代理請求格式"""

    tool_name: str
    method: str
    params: dict[str, Any] = None
    call_type: ProxyCallType = ProxyCallType.SYNC
    timeout: int = 30
    retry_count: int = 3
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.params is None:
            self.params = {}
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ProxyResponse:
    """代理響應格式"""

    success: bool
    data: Any = None
    error: str | None = None
    execution_time: float = 0.0
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MCPToolProxy(ABC):
    """MCP工具代理基類"""

    def __init__(self, tool_name: str, registry: MCPToolRegistry):
        self.tool_name = tool_name
        self.registry = registry
        self.logger = logging.getLogger(f"mcp_proxy_{tool_name}")

        # 統計信息
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "avg_response_time": 0.0,
            "last_call": None,
        }

    @abstractmethod
    async def execute(self, request: ProxyRequest) -> ProxyResponse:
        """執行代理請求"""
        pass

    def update_stats(self, execution_time: float, success: bool):
        """更新統計信息"""
        self.stats["total_calls"] += 1
        if success:
            self.stats["successful_calls"] += 1
        else:
            self.stats["failed_calls"] += 1

        # 更新平均響應時間
        total_time = self.stats["avg_response_time"] * (self.stats["total_calls"] - 1)
        self.stats["avg_response_time"] = (total_time + execution_time) / self.stats["total_calls"]
        self.stats["last_call"] = datetime.now()


class HTTPToolProxy(MCPToolProxy):
    """HTTP-based MCP工具代理"""

    def __init__(self, tool_name: str, registry: MCPToolRegistry):
        super().__init__(tool_name, registry)
        self.base_url = None
        self.session = None

    async def initialize(self):
        """初始化代理"""
        instance = self.registry.tool_instances.get(self.tool_name)
        if not instance or not instance.endpoint_url:
            raise ValueError(f"工具 {self.tool_name} 沒有可用的端點")

        self.base_url = instance.endpoint_url
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60), headers={"Content-Type": "application/json"}
        )
        self.logger.info(f"HTTP代理初始化完成: {self.base_url}")

    async def execute(self, request: ProxyRequest) -> ProxyResponse:
        """執行HTTP請求"""
        if not self.session:
            await self.initialize()

        start_time = time.time()
        retry_count = 0

        while retry_count <= request.retry_count:
            try:
                url = f"{self.base_url}/{request.method}"

                async with self.session.post(
                    url, json=request.params, timeout=aiohttp.ClientTimeout(total=request.timeout)
                ) as response:
                    execution_time = time.time() - start_time

                    if response.status == 200:
                        result = await response.json()
                        self.update_stats(execution_time, True)
                        return ProxyResponse(
                            success=True,
                            data=result,
                            execution_time=execution_time,
                            metadata={"status_code": response.status, "retry_count": retry_count},
                        )
                    else:
                        error_text = await response.text()
                        self.logger.warning(f"HTTP錯誤 {response.status}: {error_text}")

                        if retry_count < request.retry_count:
                            retry_count += 1
                            await asyncio.sleep(2**retry_count)  # 指數退避
                            continue
                        else:
                            self.update_stats(execution_time, False)
                            return ProxyResponse(
                                success=False,
                                error=f"HTTP {response.status}: {error_text}",
                                execution_time=execution_time,
                                metadata={
                                    "status_code": response.status,
                                    "retry_count": retry_count,
                                },
                            )

            except TimeoutError:
                execution_time = time.time() - start_time
                if retry_count < request.retry_count:
                    retry_count += 1
                    self.logger.warning(f"請求超時，重試 {retry_count}/{request.retry_count}")
                    await asyncio.sleep(1)
                    continue
                else:
                    self.update_stats(execution_time, False)
                    return ProxyResponse(
                        success=False,
                        error="請求超時",
                        execution_time=execution_time,
                        metadata={"retry_count": retry_count},
                    )

            except Exception as e:
                execution_time = time.time() - start_time
                if retry_count < request.retry_count:
                    retry_count += 1
                    self.logger.warning(
                        f"請求異常，重試 {retry_count}/{request.retry_count}: {str(e)}"
                    )
                    await asyncio.sleep(1)
                    continue
                else:
                    self.update_stats(execution_time, False)
                    return ProxyResponse(
                        success=False,
                        error=str(e),
                        execution_time=execution_time,
                        metadata={"retry_count": retry_count},
                    )

    async def close(self):
        """關閉代理連接"""
        if self.session:
            await self.session.close()


class LLMToolProxy(HTTPToolProxy):
    """LLM工具專用代理"""

    async def chat_completion(
        self, messages: list[dict[str, str]], model: str = None, **kwargs
    ) -> ProxyResponse:
        """聊天完成請求"""
        params = {"messages": messages, "model": model, **kwargs}

        request = ProxyRequest(
            tool_name=self.tool_name,
            method="chat/completions",
            params=params,
            call_type=ProxyCallType.SYNC,
        )

        return await self.execute(request)

    async def embeddings(self, text: str | list[str], model: str = None) -> ProxyResponse:
        """文本嵌入請求"""
        params = {"input": text, "model": model}

        request = ProxyRequest(tool_name=self.tool_name, method="embeddings", params=params)

        return await self.execute(request)


class VectorDBToolProxy(HTTPToolProxy):
    """向量資料庫工具專用代理"""

    async def create_collection(
        self, collection_name: str, dimension: int = None, **kwargs
    ) -> ProxyResponse:
        """創建集合"""
        params = {"collection_name": collection_name, "dimension": dimension, **kwargs}

        request = ProxyRequest(tool_name=self.tool_name, method="collections/create", params=params)

        return await self.execute(request)

    async def insert_vectors(
        self,
        collection_name: str,
        vectors: list[list[float]],
        ids: list[str] = None,
        metadata: list[dict] = None,
    ) -> ProxyResponse:
        """插入向量"""
        params = {
            "collection_name": collection_name,
            "vectors": vectors,
            "ids": ids,
            "metadata": metadata,
        }

        request = ProxyRequest(
            tool_name=self.tool_name,
            method="vectors/insert",
            params=params,
            call_type=ProxyCallType.BATCH,
        )

        return await self.execute(request)

    async def search_vectors(
        self, collection_name: str, query_vector: list[float], top_k: int = 10, **kwargs
    ) -> ProxyResponse:
        """向量搜索"""
        params = {
            "collection_name": collection_name,
            "query_vector": query_vector,
            "top_k": top_k,
            **kwargs,
        }

        request = ProxyRequest(tool_name=self.tool_name, method="vectors/search", params=params)

        return await self.execute(request)


class MultimodalToolProxy(HTTPToolProxy):
    """多模態工具專用代理"""

    async def process_image(
        self, image_data: bytes, task: str = "caption", **kwargs
    ) -> ProxyResponse:
        """處理圖像"""
        # 這裡需要處理圖像數據的編碼
        import base64

        image_b64 = base64.b64encode(image_data).decode("utf-8")

        params = {"image": image_b64, "task": task, **kwargs}

        request = ProxyRequest(
            tool_name=self.tool_name,
            method="image/process",
            params=params,
            timeout=60,  # 圖像處理可能需要更長時間
        )

        return await self.execute(request)

    async def process_audio(
        self, audio_data: bytes, task: str = "transcribe", **kwargs
    ) -> ProxyResponse:
        """處理音頻"""
        import base64

        audio_b64 = base64.b64encode(audio_data).decode("utf-8")

        params = {"audio": audio_b64, "task": task, **kwargs}

        request = ProxyRequest(
            tool_name=self.tool_name,
            method="audio/process",
            params=params,
            timeout=120,  # 音頻處理可能需要更長時間
        )

        return await self.execute(request)


class MCPProxyManager:
    """MCP代理管理器"""

    def __init__(self, registry: MCPToolRegistry = None):
        self.registry = registry or get_mcp_registry()
        self.logger = logging.getLogger("mcp_proxy_manager")

        # 代理實例管理
        self.proxies: dict[str, MCPToolProxy] = {}
        self.proxy_classes = {
            MCPToolType.AI_LLM: LLMToolProxy,
            MCPToolType.VECTOR_DB: VectorDBToolProxy,
            MCPToolType.MULTIMODAL: MultimodalToolProxy,
            MCPToolType.WEB_SCRAPING: HTTPToolProxy,
            MCPToolType.EXPERIMENT: HTTPToolProxy,
            MCPToolType.MONITORING: HTTPToolProxy,
            MCPToolType.DOCUMENT: HTTPToolProxy,
        }

    async def create_proxy(self, tool_name: str) -> MCPToolProxy | None:
        """創建工具代理"""
        if tool_name in self.proxies:
            return self.proxies[tool_name]

        # 獲取工具規格
        if tool_name not in self.registry.tool_specs:
            self.logger.error(f"工具 {tool_name} 未註冊")
            return None

        tool_spec = self.registry.tool_specs[tool_name]
        proxy_class = self.proxy_classes.get(tool_spec.tool_type, HTTPToolProxy)

        try:
            proxy = proxy_class(tool_name, self.registry)
            await proxy.initialize()
            self.proxies[tool_name] = proxy

            self.logger.info(f"成功創建 {tool_name} 的代理")
            return proxy

        except Exception as e:
            self.logger.error(f"創建 {tool_name} 代理失敗: {str(e)}")
            return None

    async def get_proxy(self, tool_name: str) -> MCPToolProxy | None:
        """獲取工具代理"""
        if tool_name in self.proxies:
            return self.proxies[tool_name]

        return await self.create_proxy(tool_name)

    async def execute_tool_request(
        self, tool_name: str, method: str, params: dict[str, Any] = None, **kwargs
    ) -> ProxyResponse:
        """執行工具請求"""
        proxy = await self.get_proxy(tool_name)
        if not proxy:
            return ProxyResponse(success=False, error=f"無法獲取工具 {tool_name} 的代理")

        request = ProxyRequest(tool_name=tool_name, method=method, params=params or {}, **kwargs)

        return await proxy.execute(request)

    async def broadcast_request(
        self, tool_type: MCPToolType, method: str, params: dict[str, Any] = None
    ) -> dict[str, ProxyResponse]:
        """向同類型的所有工具廣播請求"""
        tool_names = self.registry.get_tools_by_type(tool_type)
        results = {}

        tasks = []
        for tool_name in tool_names:
            task = self.execute_tool_request(tool_name, method, params)
            tasks.append((tool_name, task))

        # 並發執行
        for tool_name, task in tasks:
            try:
                result = await task
                results[tool_name] = result
            except Exception as e:
                results[tool_name] = ProxyResponse(success=False, error=f"廣播請求失敗: {str(e)}")

        return results

    def get_proxy_stats(self, tool_name: str = None) -> dict[str, Any]:
        """獲取代理統計信息"""
        if tool_name:
            proxy = self.proxies.get(tool_name)
            return proxy.stats if proxy else {}

        return {name: proxy.stats for name, proxy in self.proxies.items()}

    async def cleanup_proxies(self):
        """清理代理連接"""
        self.logger.info("正在清理MCP代理連接...")

        for proxy in self.proxies.values():
            try:
                if hasattr(proxy, "close"):
                    await proxy.close()
            except Exception as e:
                self.logger.error(f"清理代理時發生錯誤: {str(e)}")

        self.proxies.clear()
        self.logger.info("MCP代理清理完成")


# 全局代理管理器實例
_proxy_manager = None


def get_proxy_manager() -> MCPProxyManager:
    """獲取MCP代理管理器單例實例"""
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = MCPProxyManager()
    return _proxy_manager
